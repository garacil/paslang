#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""testdata/bitnz's counts of a value an if proved not zero (P394): built
with -cpu base, the routines Nz* count their bits with bsf or bsr and
no sentinel (no cmovz, bts, movl $64 or $127, nor the leaq of 2x + 1),
and the routines Keep*, whose value the branch writes or a call may,
keep the cmovz; on arm64 the narrow trailing counts of NzTz32 and NzTz8
take no sentinel bit (orr).

usage: check_bitnz.py file.s [--arm]
"""

import re
import sys

NZ = ('p_nztz64', 'p_nzlz64', 'p_nztz32', 'p_nzlz16', 'p_nztz8', 'p_nzbits')
KEEP = ('p_keepwritten', 'p_keepvar', 'p_keepglobal')


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
    if arm:
        for name in ('p_nztz32', 'p_nztz8'):
            b = body(lines, name, path)
            bad = [l.strip() for l in b if re.match(r'^\s+orr x\d+, x\d+, #', l)]
            if bad:
                raise SystemExit(f'{path}: {name}: {bad[0]}, a sentinel bit for a value known not zero')
            if not any(re.match(r'^\s+rbit x', l) for l in b):
                raise SystemExit(f'{path}: {name} counts no trailing zeros')
        print(f'check_bitnz: the narrow trailing counts take no sentinel, in {path}')
        return
    for name in NZ:
        b = body(lines, name, path)
        bad = [l.strip() for l in b if re.search(r'\bcmovz|\bbts|movl \$(64|127),|leaq 1\(%', l)]
        if bad:
            raise SystemExit(f'{path}: {name}: {bad[0]}, a sentinel for a value known not zero')
        if not any(re.match(r'^\s+bs[fr]q %', l) for l in b):
            raise SystemExit(f'{path}: {name} counts no bits by bsf or bsr')
    for name in KEEP:
        b = body(lines, name, path)
        if not any(re.match(r'^\s+cmovzq %', l) for l in b):
            raise SystemExit(f'{path}: {name} lost its sentinel, where its value may be zero')
    print(f'check_bitnz: {len(NZ)} counts of a value known not zero take no sentinel, {len(KEEP)} keep it, in {path}')


if __name__ == '__main__':
    main()
