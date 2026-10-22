#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""check_ptrelem.py FILE.s [--arm]: testdata/ptrelem built at -inline 0
takes the address of a pointer's element in one instruction from the
registers of the pointer and the index, and its loads and stores take
them themselves (P385). amd64: copywords loads and stores (B,X,1),
sumwords reads (B,X,2), runints (B,X,4), runlongs (B,X,8); arm64:
copywords ldr and str [B, X], sumwords ldrh [B, X, lsl #1], runints
[B, X, lsl #2], runlongs [B, X, lsl #3]. In none of them does the old
path show: the pointer popped back, added to the index and read or
written through (popq %rcx, addq %rcx, %rax or leaq (%rcx,%rax,K), then
(%rax); ldr x1, [sp], #16, add x0, x1, x0, then [x0])."""
import re
import sys


def routine(lines, name):
    out, on = [], False
    for ln in lines:
        if ln.startswith(name + ':'):
            on = True
            continue
        if on:
            if '.cfi_endproc' in ln:
                break
            if not re.match(r'^\s*\.(loc|cfi)', ln) and not ln.startswith('.LL'):
                out.append(ln.strip())
    if not out:
        sys.exit(f'check_ptrelem: {name} not found')
    return out


def main():
    arm = '--arm' in sys.argv[1:]
    path = [a for a in sys.argv[1:] if not a.startswith('--')][0]
    lines = open(path).read().split('\n')
    R = r'%r\w+'
    if arm:
        want = {
            'p_copywords': [r'^ldr x\d+, \[x\d+, x\d+\]$', r'^str x\d+, \[x\d+, x\d+\]$'],
            'p_sumwords': [r'^ldrh w\d+, \[x\d+, x\d+, lsl #1\]$'],
            'p_runints': [r'\[x\d+, x\d+, lsl #2\]$'],
            'p_runlongs': [r'\[x\d+, x\d+, lsl #3\]$'],
        }
    else:
        want = {
            'p_copywords': [rf'^movq \({R},{R},1\), {R}$', rf'^movq {R}, \({R},{R},1\)$'],
            'p_sumwords': [rf'\({R},{R},2\)'],
            'p_runints': [rf'\({R},{R},4\)'],
            'p_runlongs': [rf'\({R},{R},8\)'],
        }
    bad = []
    for name, pats in want.items():
        body = routine(lines, name)
        for p in pats:
            if not any(re.search(p, ins) for ins in body):
                bad.append(f'{name}: no {p}')
        for i in range(len(body) - 2):
            if arm:
                old = body[i] == 'ldr x1, [sp], #16' and \
                    re.match(r'^add x0, x1, x0(, lsl #\d)?$', body[i + 1]) and \
                    re.search(r'\[x0\]$', body[i + 2])
            else:
                old = body[i] == 'popq %rcx' and (body[i + 1] == 'addq %rcx, %rax' or
                                                  body[i + 1].startswith('leaq (%rcx,%rax,')) and \
                    '(%rax)' in body[i + 2]
            if old:
                bad.append(f'{name}: the pointer pushed and added back at "{body[i + 1]}"')
    for b in bad:
        print(b)
    if bad:
        sys.exit(1)
    print(f'check_ptrelem: an element of a pointer in one instruction, its loads and stores '
          f'taking base and index, in {path}')


if __name__ == '__main__':
    main()
