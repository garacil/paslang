#!/usr/bin/env python3
"""check_regleaf.py FILE.s [--arm]: testdata/regleaf's forms (P397).

A word field of an object a register holds is one load at an offset
from that register: TR.Same and TR.Moved compare Base with
Pointer(S), two fields of Self, with no push (amd64: one load and
cmpq off(%reg), %rax; arm64: two loads at an offset from one
register); TR.Addr, @FP[FTA], is one lea or add from the registers of
the pointer and the index; TR.Bit shifts a constant by a count with no
push."""
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
    for r in ('p_tr_same', 'p_tr_moved'):
        b = body(lines, r)
        if not b:
            bad.append(r + ': not found')
            continue
        if any(push.search(i) for i in b):
            bad.append(r + ': a push: ' + '; '.join(b))
        if arm:
            loads = [i for i in b if re.match(r'^ldr x\d+, \[x\d+, #\d+\]$', i)]
            if len(loads) < 2:
                bad.append(r + ': the two fields are not loads at an offset: ' + '; '.join(b))
        elif not any(re.match(r'^cmpq -?\d+\(%r\w+\), %rax$', i) for i in b):
            bad.append(r + ': no cmpq of a field where it lies: ' + '; '.join(b))
    for r in ('p_tr_addr', 'p_tr_bit'):
        b = body(lines, r)
        if not b:
            bad.append(r + ': not found')
            continue
        if any(push.search(i) for i in b):
            bad.append(r + ': a push: ' + '; '.join(b))
    b = body(lines, 'p_tr_addr')
    if b and not arm and not any(i.startswith('leaq (') for i in b):
        bad.append('p_tr_addr: no lea of the pointer and the index: ' + '; '.join(b))
    if bad:
        for m in bad:
            print('check_regleaf:', m)
        sys.exit(1)
    print('check_regleaf: ok', path)


if __name__ == '__main__':
    main()
