#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""check_sqlite.py PROG DIR [QEMU]: the unit sqlite and the system's
SQLite (Python's sqlite3 module) on the same files.

Each side writes a database the other reads back, after PRAGMA
integrity_check, with the same rows; a writer of each side killed at
many points of its commit leaves a file both sides recover to the state
before the transaction or the one after, and to the same one; readers of
one side and writers of the other at once, in rollback-journal and WAL
mode, never see half a transaction; the checkpoints of every kind give
the same answers; a million rows in one transaction. PROG is the
compiled testdata/sqlcompat.paslang, DIR a directory for the files,
QEMU the arm64 runner, when PROG is an arm64 program."""
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time

PROG, DIR = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
RUN = [os.path.abspath(q) for q in sys.argv[3:4]]
os.makedirs(DIR, exist_ok=True)
BATCH = 100
DIGEST = [
    "PRAGMA integrity_check",
    "SELECT count(*), sum(a), printf('%.6f', total(b)), sum(length(c)), sum(length(d)), sum(e) FROM t",
    "SELECT count(*), sum(v), min(k), max(k) FROM w",
    "SELECT count(*) FROM t INDEXED BY tc WHERE c > 'row 5'",
]


def prog(*args, timeout=600):
    r = subprocess.run(RUN + [PROG] + list(args), capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        sys.exit(f'sqlite: {args} exit {r.returncode}: {r.stdout}{r.stderr}')
    return r.stdout


def ours(db):
    return [prog('query', db, q).strip() for q in DIGEST]


def theirs(db):
    c = sqlite3.connect(db, timeout=20)
    out = ['\n'.join('|'.join('NULL' if v is None else str(v) for v in row) for row in c.execute(q)) for q in DIGEST]
    c.close()
    return out


def py_rows(c, first, n):
    for i in range(first, first + n):
        c.execute('INSERT INTO t VALUES(?, ?, ?, zeroblob(?), ?)', (i, i / 7, 'row %d' % (i * 7919 % 100003), (i * 13) % 3000, None))
        c.execute('INSERT INTO w VALUES(?, ?)', ('k%d' % i, i * i))
    c.execute('UPDATE t SET e = a * 2 WHERE a % 5 = 0 AND a >= ? AND a < ?', (first, first + n))
    c.execute('DELETE FROM w WHERE v % 11 = 3')


def py_schema(c, mode):
    c.execute('PRAGMA journal_mode=' + mode)
    c.execute('CREATE TABLE IF NOT EXISTS t(a INTEGER PRIMARY KEY, b REAL, c TEXT, d BLOB, e)')
    c.execute('CREATE INDEX IF NOT EXISTS tc ON t(c)')
    c.execute('CREATE TABLE IF NOT EXISTS w(k TEXT PRIMARY KEY, v INTEGER) WITHOUT ROWID')


def fresh(name):
    for ext in ('', '-journal', '-wal', '-shm'):
        if os.path.exists(name + ext):
            os.remove(name + ext)
    return name


def same(what, a, b):
    if a != b:
        sys.exit(f'sqlite: {what} differ:\n  ours   {a}\n  theirs {b}')


# one side writes, the other reads back
for mode in ('delete', 'wal'):
    db = fresh(os.path.join(DIR, 'w1.db'))
    prog('write', db, '3000', mode)
    a, b = ours(db), theirs(db)
    same('our file read by SQLite (%s)' % mode, a, b)
    if a[0] != 'ok':
        sys.exit('sqlite: our file not sound: ' + a[0])
    db = fresh(os.path.join(DIR, 'w2.db'))
    c = sqlite3.connect(db, isolation_level=None)
    py_schema(c, mode)
    c.execute('BEGIN')
    py_rows(c, 1, 3000)
    c.execute('COMMIT')
    c.close()
    same('SQLite\'s file read by us (%s)' % mode, ours(db), theirs(db))
    same('the two files (%s)' % mode, ours(db), ours(os.path.join(DIR, 'w1.db')))


# a writer killed in its commit: both sides recover the same state
PYCRASH = """import sqlite3, sys
c = sqlite3.connect(sys.argv[1], isolation_level=None)
c.execute('PRAGMA journal_mode=' + sys.argv[2])
n = c.execute('SELECT count(*) FROM t').fetchone()[0]
c.execute('BEGIN')
for i in range(n + 1, n + 2001):
    c.execute('INSERT INTO t VALUES(?, ?, ?, zeroblob(?), ?)', (i, i / 7, 'row %d' % (i * 7919 % 100003), (i * 13) % 3000, None))
    c.execute('INSERT INTO w VALUES(?, ?)', ('k%d' % i, i * i))
c.execute('UPDATE t SET e = a * 2 WHERE a % 5 = 0 AND a >= ? AND a < ?', (n + 1, n + 2001))
c.execute('DELETE FROM w WHERE v % 11 = 3')
print('begun', flush=True)
c.execute('COMMIT')
print('done', flush=True)
"""
def recover_both(db, before, after, what):
    d1, d2 = db + '.a', db + '.b'
    for ext in ('', '-journal', '-wal', '-shm'):
        for d in (d1, d2):
            if os.path.exists(d + ext):
                os.remove(d + ext)
        if os.path.exists(db + ext):
            shutil.copyfile(db + ext, d1 + ext)
            shutil.copyfile(db + ext, d2 + ext)
    a, b = ours(d1), theirs(d2)
    same(what + ': the recoveries', a, b)
    if a[0] != 'ok' or (a != before and a != after):
        sys.exit(f'sqlite: {what}: recovered to neither state: {a}')
    return a == after


for mode in ('delete', 'wal'):
    for side in ('ours', 'theirs'):
        base = fresh(os.path.join(DIR, 'k.db'))
        prog('write', base, '200', mode)
        before = ours(base)
        prog('crash', fresh(os.path.join(DIR, 'k2.db')), '1', mode)
        shutil.copyfile(base, os.path.join(DIR, 'k3.db'))
        if os.path.exists(base + '-wal'):
            shutil.copyfile(base + '-wal', os.path.join(DIR, 'k3.db-wal'))
        prog('crash', os.path.join(DIR, 'k3.db'), '2000', mode)
        after = ours(os.path.join(DIR, 'k3.db'))
        kept = 0
        for step in range(24):
            db = fresh(os.path.join(DIR, 'kill.db'))
            shutil.copyfile(base, db)
            if os.path.exists(base + '-wal'):
                shutil.copyfile(base + '-wal', db + '-wal')
            if side == 'ours':
                p = subprocess.Popen(RUN + [PROG, 'crash', db, '2000', mode], stdout=subprocess.PIPE, text=True)
            else:
                p = subprocess.Popen([sys.executable, '-I', '-c', PYCRASH, db, mode], stdout=subprocess.PIPE, text=True)
            p.stdout.readline()
            time.sleep(step * 0.0015)
            p.send_signal(signal.SIGKILL)
            p.wait()
            if recover_both(db, before, after, f'{side} killed {step} ({mode})'):
                kept += 1
        print(f'sqlite: {side} writer killed 24 times ({mode}): {kept} after, {24 - kept} before')


# readers of one side, writers of the other, at once
for mode in ('delete', 'wal'):
    db = fresh(os.path.join(DIR, 'rw.db'))
    c = sqlite3.connect(db, isolation_level=None, timeout=20)
    py_schema(c, mode)
    c.close()
    r = subprocess.Popen(RUN + [PROG, 'readloop', db, '300'], stdout=subprocess.PIPE, text=True)
    c = sqlite3.connect(db, isolation_level=None, timeout=20)
    for k in range(30):
        c.execute('BEGIN IMMEDIATE')
        n = c.execute('SELECT count(*) FROM t').fetchone()[0]
        py_rows(c, n + 1, BATCH)
        c.execute('COMMIT')
    c.close()
    out = r.communicate(timeout=600)[0]
    if out.strip() != 'read 300':
        sys.exit(f'sqlite: our reader beside SQLite\'s writer ({mode}): {out}')
    w = subprocess.Popen(RUN + [PROG, 'writeloop', db, '30', mode], stdout=subprocess.PIPE, text=True)
    c = sqlite3.connect(db, timeout=20)
    for k in range(300):
        n = c.execute('SELECT count(*) FROM t').fetchone()[0]
        if n % BATCH:
            sys.exit(f'sqlite: SQLite\'s reader saw half of our transaction ({mode}): {n}')
    c.close()
    out = w.communicate(timeout=600)[0]
    if out.strip() != 'wrote 30':
        sys.exit(f'sqlite: our writer beside SQLite\'s reader ({mode}): {out}')
    same('after the readers and writers (%s)' % mode, ours(db), theirs(db))
    print(f'sqlite: readers and writers at once ({mode}) ok')


# the checkpoints, with a reader of SQLite's holding a snapshot
def ckpt_run(checkpointer):
    db = fresh(os.path.join(DIR, 'ck.db'))
    prog('write', db, '500', 'wal')
    c = sqlite3.connect(db, isolation_level=None, timeout=1)
    c.execute('PRAGMA wal_autocheckpoint=0')
    res = []
    for kind in ('PASSIVE', 'FULL', 'RESTART', 'TRUNCATE'):
        c.execute('INSERT INTO w VALUES(?, 1)', ('ck' + kind,))
        r = sqlite3.connect(db, isolation_level=None, timeout=1)
        r.execute('BEGIN')
        r.execute('SELECT count(*) FROM t').fetchone()
        q = 'PRAGMA wal_checkpoint(%s)' % kind
        if checkpointer == 'ours':
            res.append(prog('ckpt', db, kind).strip())
        else:
            x = sqlite3.connect(db, isolation_level=None, timeout=0)
            res.append('|'.join(str(v) for v in x.execute(q).fetchone()))
            x.close()
        r.execute('COMMIT')
        r.close()
        q2 = 'PRAGMA wal_checkpoint(%s)' % kind
        if checkpointer == 'ours':
            res.append(prog('ckpt', db, kind).strip())
        else:
            x = sqlite3.connect(db, isolation_level=None, timeout=0)
            res.append('|'.join(str(v) for v in x.execute(q2).fetchone()))
            x.close()
    c.close()
    return res + [os.path.getsize(db + '-wal') if os.path.exists(db + '-wal') else -1]


same('the checkpoints', ckpt_run('ours'), ckpt_run('theirs'))
print('sqlite: checkpoints of every kind ok')

# a million rows in one transaction
db = fresh(os.path.join(DIR, 'm.db'))
t0 = time.time()
out = prog('million', db, timeout=3600).strip()
c = sqlite3.connect(db)
want = '|'.join(str(v) for v in c.execute('SELECT count(*), sum(b), max(length(c)) FROM m').fetchone())
ok = c.execute('PRAGMA integrity_check').fetchone()[0]
c.close()
same('a million rows', out, want)
if ok != 'ok':
    sys.exit('sqlite: the million rows not sound: ' + ok)
print(f'sqlite: a million rows in one transaction ({time.time() - t0:.1f} s) ok')
for f in os.listdir(DIR):
    if f.endswith(('.db', '.db-journal', '.db-wal', '.db-shm', '.a', '.b')) or '.db.' in f:
        os.remove(os.path.join(DIR, f))
print('ok sqlite')
