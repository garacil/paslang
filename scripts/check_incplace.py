#!/usr/bin/env python3
"""check_incplace.py FILE.s [--arm]: testdata/incplace's forms (P402).

Inc and Dec of a place no register holds, by a constant, a variable or
a field of an object a register holds, push nothing: Globals, TC.Bump
and TC.Other have no push; on amd64 each is one add or sub at the
place's width with the place as its operand (addq $1, v_g(%rip),
addw $30000, v_g16(%rip), addb $100, v_g8(%rip), addq $1, 8(%rdi))."""
import re
import sys


def body(lines, name):
    out, on = [], False
    for ln in lines:
        if ln.rstrip() == name + ':':
            on = True
            continue
        if on:
            if '.cfi_endproc' in ln or re.match(r'^\.section ', ln):
                break
            s = ln.strip()
            if s and not s.startswith('.') and not s.endswith(':'):
                out.append(s)
    return out


def main():
    path = sys.argv[1]
    arm = '--arm' in sys.argv[2:]
    lines = open(path).read().split('\n')
    bad = []
    push = re.compile(r'^str x0, \[sp, #-16\]!|^stp x0, ') if arm else re.compile(r'^pushq ')
    want = {
        'p_globals': ['addq $1, v_g(%rip)', 'addq $7, v_g(%rip)', 'subq $1, v_g(%rip)',
                      'addw $30000, v_g16(%rip)', 'addb $100, v_g8(%rip)',
                      'addl $-1, v_gu(%rip)', 'addq $-2147483648, v_g(%rip)'],
        'p_tc_bump': ['addq $1, 8(%rdi)', 'addq $5, 8(%rdi)', 'subq $2, 8(%rdi)'],
        'p_tc_other': ['subw $1, 16(%rsi)', 'addq $1000, 24(%rsi)'],
    }
    for r, ins in want.items():
        b = body(lines, r)
        if not b:
            bad.append(r + ': not found')
            continue
        if any(push.search(i) for i in b):
            bad.append(r + ': a push: ' + '; '.join(b))
        if not arm:
            for i in ins:
                if i not in b:
                    bad.append(r + ': no ' + i + ': ' + '; '.join(b))
    if bad:
        for m in bad:
            print('check_incplace:', m)
        sys.exit(1)
    print('check_incplace: ok', path)


if __name__ == '__main__':
    main()
