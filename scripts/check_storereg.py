#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""check_storereg.py FILE.s [--arm]: testdata/storereg built at -inline 0
stores to a place whose address is registers and a constant alone at
once, from the register the value was worked out in (P386). amd64:
fill stores (B,X,8) with no push in the routine; narrow stores a byte,
a word and a doubleword at (B,X,1), (B,X,2) and (B,X,4); views a
doubleword at (B,X,1) and a word at (B,X,4); target a word at 8(B); in
none of them a value pushed and popped back for a store (pushq then
popq %rcx then a store of %rcx). arm64: fill str [B, X, lsl #3];
narrow strb [B, X], strh [B, X, lsl #1], str w [B, X, lsl #2]; views
str w [B, X] and a word's strh through x16, the address an add of the
Int32's index; target str [B] and [B, #8]; in none of them a value
stored to [sp, #-16]! and loaded back into x1 for a store of x1."""
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
        sys.exit(f'check_storereg: {name} not found')
    return out


def main():
    arm = '--arm' in sys.argv[1:]
    path = [a for a in sys.argv[1:] if not a.startswith('--')][0]
    lines = open(path).read().split('\n')
    R = r'%r\w+'
    if arm:
        want = {
            'p_fill': [r'^str x\d+, \[x\d+, x\d+, lsl #3\]$'],
            'p_narrow': [r'^strb w\d+, \[x\d+, x\d+(, lsl #0)?\]$', r'^strh w\d+, \[x\d+, x\d+, lsl #1\]$',
                         r'^str w\d+, \[x\d+, x\d+, lsl #2\]$'],
            'p_views': [r'^str w\d+, \[x\d+, x\d+\]$', r'^strh w\d+, \[x16\]$'],
            'p_target': [r'^str x\d+, \[x\d+\]$', r'^str x\d+, \[x\d+, #8\]$'],
        }
    else:
        want = {
            'p_fill': [rf'^movq {R}, \({R},{R},8\)$'],
            'p_narrow': [rf'^movb %\w+, \({R},{R},1\)$', rf'^movw %\w+, \({R},{R},2\)$',
                         rf'^movl %\w+, \({R},{R},4\)$'],
            'p_views': [rf'^movl %\w+, \({R},{R},1\)$', rf'^movw %\w+, \({R},{R},4\)$'],
            'p_target': [rf'^movq {R}, 8\({R}\)$'],
        }
    bad = []
    for name, pats in want.items():
        body = routine(lines, name)
        for p in pats:
            if not any(re.search(p, ins) for ins in body):
                bad.append(f'{name}: no {p}')
        for i in range(len(body) - 2):
            if arm:
                pushed = body[i] == 'str x0, [sp, #-16]!' and any(
                    body[j] == 'ldr x1, [sp], #16' and re.match(r'^str[bh]? [wx]1, ', body[j + 1])
                    for j in range(i + 1, min(i + 4, len(body) - 1)))
            else:
                pushed = body[i] == 'pushq %rax' and any(
                    body[j] == 'popq %rcx' and re.match(r'^mov[bwlq] %[a-z0-9]*c[xl]?, ', body[j + 1])
                    for j in range(i + 1, min(i + 4, len(body) - 1)))
            if pushed:
                bad.append(f'{name}: a value pushed and popped for its store at line {i + 1}')
    if not arm and any(ins.startswith('pushq') for ins in routine(lines, 'p_fill')):
        bad.append('p_fill: a push in a routine with no frame')
    for b in bad:
        print(b)
    if bad:
        sys.exit(1)
    print(f'check_storereg: stores name their places at once and push no value, in {path}')


if __name__ == '__main__':
    main()
