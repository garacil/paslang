#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""check_sqlapi.py PROG DIR [QEMU] [--only A,B] [--corpus]: every script of testdata/sqlite run
by PROG (testdata/sqlapi.paslang, the unit sqlite's C interface) on a new
database in DIR, as SQLite 3.54.1 answered it (NAME.out, made by
scripts/sqlapi_oracle.c on SQLite's amalgamation), then again on a
UTF-16LE and a UTF-16BE database (NAME.le.out and NAME.be.out where the
answer is not the UTF-8 one). A group A+B runs its scripts on one
database, in order. With --corpus, the corpora of corpus.tar.xz too,
each script's answer against the SHA-256 of SQLite's in corpus.sha256.
QEMU runs PROG when it is an arm64 program; --only runs the groups whose
first script is named."""

import hashlib
import os
import subprocess
import sys
import tarfile

GROUPS = ('a1 c1 d1 d2 p2a p3 p4 p5 p6+p6b r1+r2+r3 an1+an2 v2 w1 w2 dt1 j1 vac1 bk1 md1 coll1 fn1 params fpd'
          ' m1').split()
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata', 'sqlite')


def main():
    args = sys.argv[1:]
    groups = GROUPS
    with_corpus = '--corpus' in args
    args = [a for a in args if a != '--corpus']
    if '--only' in args:
        k = args.index('--only')
        names = args[k + 1].split(',')
        groups = [g for g in GROUPS if g.split('+')[0] in names]
        args = args[:k] + args[k + 2:]
    prog, d = os.path.abspath(args[0]), os.path.abspath(args[1])
    run = [os.path.abspath(q) for q in args[2:3]]
    os.makedirs(d, exist_ok=True)
    n = 0
    for g in groups:
        for enc, tag in (('', ''), ('UTF-16le', '.le'), ('UTF-16be', '.be')):
            for f in ('t.db', 't.db-journal', 't.db-wal', 't.db-shm'):
                if os.path.exists(os.path.join(d, f)):
                    os.remove(os.path.join(d, f))
            for k, x in enumerate(g.split('+')):
                for f in ('vac_into.db', 'bk_dest.db', 'bk_dest.db-journal'):
                    if os.path.exists(os.path.join(d, f)):
                        os.remove(os.path.join(d, f))
                args = run + [prog, 't.db', os.path.abspath(os.path.join(SRC, x + '.sql'))]
                if enc and k == 0:
                    args.append(enc)
                got = subprocess.run(args, cwd=d, capture_output=True, timeout=900).stdout
                want = os.path.join(SRC, x + tag + '.out')
                if not os.path.exists(want):
                    want = os.path.join(SRC, x + '.out')
                if got != open(want, 'rb').read():
                    open(os.path.join(d, x + tag + '.got'), 'wb').write(got)
                    sys.exit('check_sqlapi: %s%s differs from SQLite: diff %s %s' % (
                        x, tag, want, os.path.join(d, x + tag + '.got')))
                n += 1
    # the corpora: each script's answer hashed, SQLite's hash beside it
    corpus = os.path.join(SRC, 'corpus.tar.xz')
    if with_corpus and os.path.exists(corpus):
        cd = os.path.join(d, 'corpus')
        os.makedirs(cd, exist_ok=True)
        with tarfile.open(corpus, 'r:xz') as t:
            t.extractall(cd, filter='data')
        for line in open(os.path.join(SRC, 'corpus.sha256')):
            name, want = line.split()
            for f in ('t.db', 't.db-journal', 't.db-wal', 't.db-shm', 'vac_into.db', 'bk_dest.db', 'bk_dest.db-journal'):
                if os.path.exists(os.path.join(d, f)):
                    os.remove(os.path.join(d, f))
            got = subprocess.run(run + [prog, 't.db', os.path.join(cd, name + '.sql')], cwd=d, capture_output=True,
                                 timeout=900).stdout
            if hashlib.sha256(got).hexdigest() != want:
                open(os.path.join(d, name + '.got'), 'wb').write(got)
                sys.exit('check_sqlapi: corpus %s differs from SQLite (%s; SQLite\'s answer is '
                         'scripts/sqlapi_oracle.c\'s)' % (name, os.path.join(d, name + '.got')))
            n += 1
    print('check_sqlapi: %d runs as SQLite answers them' % n)


if __name__ == '__main__':
    main()
