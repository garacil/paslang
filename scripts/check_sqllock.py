#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""passqlite takes SQLite's locks (P403): while the C library holds a
database EXCLUSIVE, testdata/sqlread's open meets SQLITE_BUSY ('database
is locked'); while it holds RESERVED, a reader still reads, as SQLite's
readers do; when it lets go, the dump is the whole database. The process
that holds the lock runs the reader, so nothing waits on a clock.

usage: check_sqllock.py READER DB [RUNNER...]
"""

import sqlite3
import subprocess
import sys


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300).stdout


def main():
    reader, db = sys.argv[1], sys.argv[2]
    pre = sys.argv[3:]
    con = sqlite3.connect(db, isolation_level=None)
    con.execute('begin exclusive')
    got = run(pre + [reader, db, 'busy'])
    if got != 'busy 5 5 database is locked\n':
        raise SystemExit('check_sqllock: under EXCLUSIVE the reader said %r' % got)
    con.execute('commit')
    con.execute('begin immediate')
    got = run(pre + [reader, db, 'reserved'])
    if not got.startswith('pagesize '):
        raise SystemExit('check_sqllock: under RESERVED the reader said %r' % got[:200])
    con.execute('commit')
    con.close()
    got2 = run(pre + [reader, db, 'free'])
    if got2 != got:
        raise SystemExit('check_sqllock: the dump changed after the lock went')
    print('check_sqllock: BUSY under EXCLUSIVE, a read under RESERVED and after')


if __name__ == '__main__':
    main()
