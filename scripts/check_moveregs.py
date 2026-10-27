#!/usr/bin/env python3
"""check_moveregs.py FILE.s [--arm]: testdata/moveregs' forms (P399).

Move whose arguments call nothing pushes nothing: CopyOn, Swapped,
TBuf.Fill, TBuf.Take, Shifted and Chunks set rt_memcpy's three
registers with no push, and Chunks' loop forms the two addresses from
its registers with one lea each (amd64) or one add each (arm64)."""
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
    push = re.compile(r'^str x0, \[sp, #-16\]!|^stp x0, ') if arm else re.compile(r'^pushq %(?!rbp$)')
    call = 'bl rt_memcpy' if arm else 'call rt_memcpy'
    for r in ('p_copyon', 'p_swapped', 'p_tbuf_fill', 'p_tbuf_take', 'p_shifted', 'p_chunks'):
        b = body(lines, r)
        if not b:
            bad.append(r + ': not found')
            continue
        if call not in b:
            bad.append(r + ': no ' + call + ': ' + '; '.join(b))
        if any(push.search(i) for i in b):
            bad.append(r + ': a push: ' + '; '.join(b))
    b = body(lines, 'p_chunks')
    if b and call in b:
        k = b.index(call)
        prev = b[max(0, k - 3):k]
        if arm:
            ok = sum(1 for i in prev if re.match(r'^add x[01], x\d+, x\d+$', i)) == 2
        else:
            ok = (any(re.match(r'^leaq \(%r\w+,%r\w+,1\), %rsi$', i) for i in prev) and
                  any(re.match(r'^leaq \(%r\w+,%r\w+,1\), %rdi$', i) for i in prev))
        if not ok:
            bad.append('p_chunks: the addresses are not one instruction each: ' + '; '.join(prev))
    if bad:
        for m in bad:
            print('check_moveregs:', m)
        sys.exit(1)
    print('check_moveregs: ok', path)


if __name__ == '__main__':
    main()
