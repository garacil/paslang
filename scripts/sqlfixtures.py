#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""SQLite databases made by the C library and what passqlite must read in
them (P403): every database as SQLite 3 writes it (Python's sqlite3 module
is the system's libsqlite3), and its dump as testdata/sqlread prints it:
the header's page size, text encoding and user version, sqlite_schema's
rows, then each table's rows by rowid and each index's keys in key order,
an integer in decimal, a real as the hexadecimal of its 64 bits, a text
and a blob as quote() writes them, NULL.

usage: sqlfixtures.py OUTDIR
"""

import os
import random
import sqlite3
import struct
import sys


def q(v):
    if v is None:
        return 'NULL'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return struct.pack('>d', v).hex().upper()
    if isinstance(v, bytes):
        return "X'" + v.hex().upper() + "'"
    return "'" + v.replace("'", "''") + "'"


def dump(path):
    con = sqlite3.connect(path)
    con.text_factory = str
    enc = {'UTF-8': 1, 'UTF-16le': 2, 'UTF-16be': 3}[con.execute('pragma encoding').fetchone()[0]]
    out = ['pagesize %d encoding %d userversion %d' % (
        con.execute('pragma page_size').fetchone()[0], enc,
        con.execute('pragma user_version').fetchone()[0])]
    objs = con.execute('select type, name, tbl_name, rootpage, sql from sqlite_schema order by rowid').fetchall()
    for t, n, tb, rp, sql in objs:
        out.append('%s|%s|%s|%d|%s' % (t, n, tb, rp or 0, sql or ''))
    for t, n, tb, rp, sql in objs:
        if not rp:
            continue
        out.append('== ' + n)
        if t == 'table':
            wr = con.execute("select wr from pragma_table_list where name = ?", (n,)).fetchone()[0]
            cols = [r[1] for r in con.execute('pragma table_info("%s")' % n)]
            sel = ', '.join('"%s"' % c for c in cols)
            if wr:
                pk = [r[1] for r in sorted(con.execute('pragma table_info("%s")' % n), key=lambda r: r[5]) if r[5]]
                rows = con.execute('select %s from "%s" order by %s' % (
                    sel, n, ', '.join('"%s"' % c for c in pk))).fetchall()
                for r in rows:
                    out.append('|'.join(q(v) for v in r))
            else:
                rows = con.execute('select rowid, %s from "%s" order by rowid' % (sel, n)).fetchall()
                for r in rows:
                    out.append(str(r[0]) + '|' + '|'.join(q(v) for v in r[1:]))
        else:
            xi = con.execute('pragma index_xinfo("%s")' % n).fetchall()
            keys = [r for r in xi if r[5]]
            sel = ', '.join('"%s"' % r[2] for r in keys) + ', rowid'
            order = ', '.join('"%s" COLLATE %s %s' % (r[2], r[4], 'DESC' if r[3] else 'ASC') for r in keys)
            rows = con.execute('select %s from "%s" order by %s, rowid' % (sel, tb, order)).fetchall()
            for r in rows:
                out.append('|'.join(q(v) for v in r))
    con.close()
    return '\n'.join(out) + '\n'


def make(path, page, script, enc=None, rows=None):
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.execute('pragma page_size = %d' % page)
    if enc:
        con.execute("pragma encoding = '%s'" % enc)
    con.executescript(script)
    if rows:
        rows(con)
    con.commit()
    con.close()


def values(con):
    # every serial type: integers of every width at their edges, reals,
    # texts and blobs of every length class, NULL
    ints = [0, 1, -1, 127, -128, 128, 32767, -32768, 32768, 8388607, -8388608, 8388608,
            2147483647, -2147483648, 2147483648, 140737488355327, -140737488355328,
            140737488355328, 9223372036854775807, -9223372036854775808]
    reals = [0.5, -0.5, 3.141592653589793, 1e300, -1e-300, 2.5e-310, 1e100, 123456.789]
    texts = ['', 'a', "it's", 'añadir ünïcödé €', 'x' * 300, 'y' * 3000, 'z' * 70000]
    blobs = [b'', b'\x00\xff', bytes(range(256)) * 12, bytes((i * 31 + 7) % 256 for i in range(100000))]
    vals = ints + reals + texts + blobs + [None]
    r = random.Random(403)
    for i in range(400):
        con.execute('insert into t values (?, ?, ?)', (vals[i % len(vals)], r.choice(vals), i))


def many(con):
    r = random.Random(4031)
    con.executemany('insert into big values (?, ?)',
                    ((i * 7 + r.randrange(5), 'row %d %s' % (i, 'q' * r.randrange(60))) for i in range(100000)))


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for page in (512, 1024, 4096, 8192, 65536):
        make(os.path.join(out, 'p%d.db' % page), page,
             'create table t(a, b, c); create index tb on t(b); create index tac on t(a, c);',
             rows=values)
    make(os.path.join(out, 'big.db'), 4096,
         'create table big(k, v); create index bigk on big(k);', rows=many)
    make(os.path.join(out, 'wr.db'), 1024,
         'create table w(k text primary key, v, n) without rowid; create table u(x unique, y);',
         rows=lambda c: (c.executemany('insert into w values (?, ?, ?)',
                                       (('key %05d' % ((i * 37) % 3000), 'v' * (i % 500), i) for i in range(3000))),
                         c.executemany('insert into u values (?, ?)', ((i * 3, -i) for i in range(2000)))))
    make(os.path.join(out, 'u16le.db'), 4096, 'create table s(a, b); pragma user_version = 403;', enc='UTF-16le',
         rows=lambda c: c.executemany('insert into s values (?, ?)',
                                      (('ünïcödé %d ' % i + '😀' * (i % 4), i) for i in range(500))))
    make(os.path.join(out, 'u16be.db'), 4096, 'create table s(a, b);', enc='UTF-16be',
         rows=lambda c: c.executemany('insert into s values (?, ?)',
                                      (('€ %d' % i, 'x' * i) for i in range(500))))
    make(os.path.join(out, 'nocase.db'), 4096,
         'create table n(a collate nocase, b); create index na on n(a); create index nbd on n(b desc);',
         rows=lambda c: c.executemany('insert into n values (?, ?)',
                                      ((('Ab', 'aB', 'ab', 'AC', 'b', None, 3, 2.5)[i % 8], i % 13) for i in range(200))))
    # a database with free pages: rows deleted after a big insert
    make(os.path.join(out, 'free.db'), 1024, 'create table f(a);',
         rows=lambda c: (c.executemany('insert into f values (?)', (('w' * 200,) for i in range(2000))),
                         c.execute('delete from f where rowid % 3 <> 0')))
    open(os.path.join(out, 'empty.db'), 'wb').close()
    with open(os.path.join(out, 'notadb.db'), 'wb') as f:
        f.write(b'this is not a database file at all' * 40)
    for name in sorted(os.listdir(out)):
        if name.endswith('.db') and name not in ('empty.db', 'notadb.db'):
            with open(os.path.join(out, name[:-3] + '.exp'), 'w') as f:
                f.write(dump(os.path.join(out, name)))


if __name__ == '__main__':
    main()
