#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""testdata/parkleft's partial values kept in registers (P391).

ParkHex, ParseStrEsc's digits, pushes nothing on amd64: each or's left
side waits in rdx while its right one, a table load, is worked out in
the pool. ParkMany and ParkWords keep at most 2 and 1 pushes there, the
expressions whose right side is itself deeper than the pool and keeps
its own left side in rdx. On arm64, whose pool has seven registers,
none of the three pushes a partial value.

usage: check_parkleft.py file.s [--arm]
"""

import re
import sys

LIMITS = {'p_parkhex': 0, 'p_parkmany': 2, 'p_parkwords': 1}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    arm = '--arm' in sys.argv[1:]
    if len(args) != 1:
        raise SystemExit(__doc__.strip().splitlines()[-1])
    lines = open(args[0]).read().splitlines()
    push = re.compile(r'^\s+str x0, \[sp, #-16\]!' if arm else r'^\s+pushq %rax$')
    for name, limit in LIMITS.items():
        try:
            k = lines.index(name + ':')
        except ValueError:
            raise SystemExit(f'{args[0]}: no routine {name}')
        n = 0
        for l in lines[k + 1:]:
            if l.startswith('.section') or l == '.text' or l.strip() == '.cfi_endproc':
                break
            if push.match(l):
                n += 1
        if arm:
            limit = 0
        if n > limit:
            raise SystemExit(f'{args[0]}: {name} pushes {n} partial values, at most {limit}')
    print(f'check_parkleft: {len(LIMITS)} routines, partial values in registers')


if __name__ == '__main__':
    main()
