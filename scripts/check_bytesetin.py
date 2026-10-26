#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""testdata/bytesetin's tests of a value of 0..255 against a constant set
(P387): each routine In* pushes and pops nothing but a frame's rbp,
compares its value with no set's last element (255 or 63), and tests
the bit by bt (amd64) or by lsr of the set's word (arm64); InCount's two
conditions branch on the bit, with no setc (amd64) and no and (arm64).

usage: check_bytesetin.py file.s [--arm]
"""

import re
import sys

ROUTINES = ('p_injson', 'p_inlow', 'p_inword', 'p_inmasked', 'p_insmall', 'p_innone', 'p_incount')


def body(lines, name, path):
    try:
        k = lines.index(name + ':')
    except ValueError:
        raise SystemExit(f'{path}: no routine {name}')
    out = []
    for l in lines[k + 1:]:
        if l.startswith('.section') or l == '.text' or l.strip() == '.cfi_endproc':
            break
        out.append(l)
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    arm = '--arm' in sys.argv[1:]
    if len(args) != 1:
        raise SystemExit(__doc__.strip().splitlines()[-1])
    path = args[0]
    lines = open(path).read().splitlines()
    for name in ROUTINES:
        b = body(lines, name, path)
        if arm:
            bad = [l.strip() for l in b if re.search(r'\b(cmp \w+, #(255|63)|str x\d+, \[sp, #-|ldr x\d+, \[sp\], )', l)]
            test = [l for l in b if re.match(r'^\s+lsr x2, x1, x0$', l)]
        else:
            bad = [l.strip() for l in b if re.search(r'\b(pushq|popq) %(?!rbp\b)|cmpq \$(255|63),', l)]
            test = [l for l in b if re.match(r'^\s+btq %', l)]
        if bad:
            raise SystemExit(f'{path}: {name}: {bad[0]}, where a set constant is one bit test')
        if not test:
            raise SystemExit(f'{path}: {name} tests no bit of a set word')
    b = body(lines, 'p_incount', path)
    if arm:
        if any(re.match(r'^\s+and x0, x2, #1$', l) for l in b) or \
                len([l for l in b if re.match(r'^\s+b\.(eq|ne) ', l)]) < 2:
            raise SystemExit(f'{path}: p_incount makes a Boolean of a condition')
    else:
        if any(re.match(r'^\s+setc ', l) for l in b) or len([l for l in b if re.match(r'^\s+j(n?c) ', l)]) < 2:
            raise SystemExit(f'{path}: p_incount makes a Boolean of a condition')
    print(f'check_bytesetin: {len(ROUTINES)} routines test a set word\'s bit, nothing pushed, in {path}')


if __name__ == '__main__':
    main()
