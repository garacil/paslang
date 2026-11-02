#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""The location lists of a routine whose Doubles live in xmm registers
(P540): in the lists readelf reads from the program, the eight Doubles of
the routine hq are the registers xmm8 to xmm15 and no others (xmm9 is
its Result, which has no entry), each as the
DWARF number 17 + N (DW_OP_reg0 to reg31 are one byte, so xmm15, number
32, is DW_OP_regx), and no list is one readelf cannot read. Reads the
program's symbol table to find where hq ends."""

import re
import subprocess
import sys

exe = sys.argv[1]
syms = []
for line in subprocess.run(['nm', '-n', exe], capture_output=True, text=True, check=True).stdout.splitlines():
    f = line.split()
    if len(f) == 3:
        syms.append((int(f[0], 16), f[2]))
start = end = None
for i, (a, n) in enumerate(syms):
    if n == 'p_hq':
        start = a
        end = next(b for b, m in syms[i + 1:] if b > a)
        break
if start is None:
    sys.exit('check_dflat_loc: no p_hq in ' + exe)
out = subprocess.run(['readelf', '--debug-dump=loc', exe], capture_output=True, text=True)
text = out.stdout + out.stderr
if 'end of data' in text:
    sys.exit('check_dflat_loc: a location list readelf cannot read')
seen = set()
for m in re.finditer(r'^\s+[0-9a-f]+ ([0-9a-f]{16}) ([0-9a-f]{16}) \(DW_OP_(?:reg|regx: )(\d+) \((\w+)\)\)', text, re.M):
    b, e, num, name = int(m.group(1), 16), int(m.group(2), 16), int(m.group(3)), m.group(4)
    if start <= b and e <= end:
        seen.add((num, name))
want = {(17 + n, 'xmm%d' % n) for n in range(8, 16) if n != 9}
if seen != want:
    sys.exit('check_dflat_loc: the registers of hq are %r, not %r' % (sorted(seen), sorted(want)))
print('check_dflat_loc: ok')
