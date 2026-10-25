#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""testdata/slicehead's elements from a slice's pointer and length (P392).

AddrField, AddrVar and HeadGlobal take the address of a slice's element,
which EmitAddr works out from the slice's place: on amd64 AddrField and
AddrVar name no r8, where the capacity was loaded; on arm64 none of the
three loads x3, the capacity's register, and each loads the pointer and
the length with one LDP into x0 and x2.

usage: check_slicehead.py file.s [--arm]
"""

import re
import sys


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
    lines = open(args[0]).read().splitlines()
    if arm:
        for name in ('p_addrfield', 'p_addrvar', 'p_headglobal'):
            b = body(lines, name, args[0])
            if any(re.search(r'\bx3\b', l) for l in b):
                raise SystemExit(f'{args[0]}: {name} names x3, a slice capacity loaded')
            if not any(re.match(r'^\s+ldp x0, x2, \[', l) for l in b):
                raise SystemExit(f'{args[0]}: {name} has no ldp x0, x2 of a slice pointer and length')
    else:
        for name in ('p_addrfield', 'p_addrvar'):
            b = body(lines, name, args[0])
            bad = [l.strip() for l in b if '%r8' in l]
            if bad:
                raise SystemExit(f'{args[0]}: {name} names r8, a slice capacity loaded: {bad[0]}')
    print('check_slicehead: slice elements from their pointer and length alone')


if __name__ == '__main__':
    main()
