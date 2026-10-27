#!/usr/bin/env python3
"""check_sliceat.py FILE.s [--arm]: testdata/sliceat's forms (P398).

An element of a slice an object's field holds, the object in a
register, takes the pointer and the length where they lie: TC.At,
TC.Addr and TC.LvAt (a slice in a record in the object) push nothing
and test no descriptor for nil; on amd64 the index is compared with
the length word in memory (cmpq off(%reg), %reg)."""
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
    if arm:
        push = re.compile(r'^str x0, \[sp, #-16\]!|^stp x0, ')
        niltest = re.compile(r'^cbz ')
    else:
        push = re.compile(r'^pushq ')
        niltest = re.compile(r'^testq %(\w+), %\1$')
    for r in ('p_tc_at', 'p_tc_addr', 'p_tc_lvat'):
        b = body(lines, r)
        if not b:
            bad.append(r + ': not found')
            continue
        if any(push.search(i) for i in b):
            bad.append(r + ': a push: ' + '; '.join(b))
        if any(niltest.search(i) for i in b):
            bad.append(r + ': a nil test of a descriptor: ' + '; '.join(b))
        if not arm and not any(re.match(r'^cmpq \d+\(%r\w+\), %r\w+$', i) for i in b):
            bad.append(r + ': no compare with the length where it lies: ' + '; '.join(b))
    if bad:
        for m in bad:
            print('check_sliceat:', m)
        sys.exit(1)
    print('check_sliceat: ok', path)


if __name__ == '__main__':
    main()
