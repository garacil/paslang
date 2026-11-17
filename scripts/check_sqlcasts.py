#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""check_sqlcasts.py OUT (P622): the conversion lines testdata/sqlcols
printed into OUT (text | integer | real of each value, as
sqlite3_column_text, _int64 and _double give them) equal what the sqlite3
program gives the same values with CAST(x AS TEXT), CAST(x AS INTEGER)
and CAST(x AS REAL); a NULL is '' and 0 through the C interface, NULL
through CAST. Run only where the sqlite3 program is installed."""
import subprocess
import sys

VALUES = ("(42),(4.5),(-0.0),(1e100),(0.1),('0123'),('12abc'),('abc'),('1e3'),(' 42 '),(x'313233'),"
          "(NULL),(9.9e18),(-9.9e18),('9223372036854775808'),(1.0),(123456789012345678),(2.5e-7)")
sql = ("CREATE TABLE v(x); INSERT INTO v VALUES " + VALUES + "; "
       "SELECT typeof(x), CAST(x AS TEXT), CAST(x AS INTEGER), CAST(x AS REAL) FROM v;")
cli = [l for l in subprocess.run(['sqlite3', '-init', '/dev/null', '-batch', '-list', '-noheader', '-separator', '|', ':memory:', sql], capture_output=True, text=True,
                                check=True).stdout.splitlines() if '|' in l]
lines = open(sys.argv[1], encoding='utf-8').read().splitlines()
start = lines.index('the conversions of the C interface (text | integer | real):') + 1
ours = lines[start:start + len(cli)]
bad = 0
for c, o in zip(cli, ours):
    kind, text, integer, real = c.split('|')
    head, _, vals = o[2:].partition(': ')
    otext, ointeger, oreal = vals.rsplit(' | ', 2)
    if kind == 'null':
        integer, real = '0', '0.0'
    if head.split()[0] != kind or (otext, ointeger, oreal) != (text, integer, real):
        print('check_sqlcasts: %r gives %r, the sqlite3 program %r' % (kind, o.strip(), c))
        bad += 1
if bad or len(ours) != len(cli) or len(cli) != 18:
    sys.exit('check_sqlcasts: %d differ, %d values' % (bad, len(cli)))
print('check_sqlcasts: %d values convert as the sqlite3 program converts them' % len(cli))
