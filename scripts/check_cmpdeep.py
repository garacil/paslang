#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""testdata/cmpdeep's conditions as compares and branches (P390).

Every comparison in the routines DeepLoop, DeepFlat and DeepLoops is a
condition, its sides deeper than the register pool: each must be one
compare and one branch, so none of the three holds a set (amd64) or a
cset (arm64), the Boolean CondBranch used to make and test.

usage: check_cmpdeep.py file.s [--arm]
"""

import re
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    arm = '--arm' in sys.argv[1:]
    if len(args) != 1:
        raise SystemExit(__doc__.strip().splitlines()[-1])
    lines = open(args[0]).read().splitlines()
    bad = re.compile(r'^\s+cset\s' if arm else r'^\s+set[a-z]+\s')
    found = 0
    for name in ('p_deeploop', 'p_deepflat', 'p_deeploops'):
        try:
            k = lines.index(name + ':')
        except ValueError:
            raise SystemExit(f'{args[0]}: no routine {name}')
        n = 0
        for l in lines[k + 1:]:
            if l.startswith('.section') or l == '.text' or l.strip() == '.cfi_endproc':
                break
            if bad.match(l):
                n += 1
                print(f'{args[0]}: {name}: {l.strip()}')
        if n:
            raise SystemExit(f'{args[0]}: {name} makes {n} Booleans of its conditions')
        found += 1
    print(f'check_cmpdeep: {found} routines, every deep comparison one compare and one branch')


if __name__ == '__main__':
    main()
