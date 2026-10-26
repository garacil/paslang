#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""testdata/straight's forms (P396).

TryWrite's locals, which every path writes before anything reads them,
the try's handler and finally part too, start as they are: its prologue
stores no zero; TryRead's handler may read a before the body writes it,
and its prologue zeroes that one alone. MoveLoop's Move is a statement
of its loop's region, no island, so the loop runs in chunks of 1024 as
a loop without calls does: its for and the one that fills the source,
two run ends worked out. AndSplit tests the and's part that calls
nothing in the region, before the island that calls Probe: its first
test against 2 reads a register. Dead stores before its first call
only what that call or a later read needs, x dead there: at most 3
words on amd64, its parameter's among them, 4 on arm64, which keeps
x19's caller value in the frame too.

usage: check_straight.py file.s [--arm]
"""

import re
import sys


def body(lines, name):
    try:
        k = lines.index(name + ':')
    except ValueError:
        raise SystemExit(f'no routine {name}')
    out = []
    for line in lines[k + 1:]:
        if re.match(r'^p_[a-z0-9_]+:$', line):
            break
        out.append(line)
    return out


def prologue(b):
    out = []
    for line in b:
        if '.loc' in line:
            break
        out.append(line)
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    arm = '--arm' in sys.argv[1:]
    if len(args) != 1:
        raise SystemExit(__doc__.strip().splitlines()[-1])
    path = args[0]
    lines = open(path).read().splitlines()
    if arm:
        zero = re.compile(r'\b(str|stur|stp) xzr\b')
        chunk = re.compile(r'#1023\b')
        two = re.compile(r'^\s+cmp (x\d+), #2$')
        store = re.compile(r'^\s+(str|stur) x\d+, \[x29, #-\d+\]$')
        call = 'bl p_note'
        kept = lambda r: r in ['x%d' % i for i in range(19, 27)]
        most = 4
    else:
        zero = re.compile(r'movq \$0, -\d+\(%rbp\)')
        chunk = re.compile(r'leaq 1023\(')
        two = re.compile(r'^\s+cmpq \$2, (%?\S+)$')
        store = re.compile(r'^\s+movq %r[a-z0-9]+, -\d+\(%rbp\)$')
        call = 'call p_note'
        kept = lambda r: r.startswith('%r')
        most = 3
    n = sum(1 for l in prologue(body(lines, 'p_trywrite')) if zero.search(l))
    if n != 0:
        raise SystemExit(f'{path}: TryWrite zeroes {n} words at its entry, none expected')
    n = sum(1 for l in prologue(body(lines, 'p_tryread')) if zero.search(l))
    if n != 1:
        raise SystemExit(f'{path}: TryRead zeroes {n} words at its entry, one expected')
    n = sum(1 for l in body(lines, 'p_moveloop') if chunk.search(l))
    if n < 2:
        raise SystemExit(f'{path}: MoveLoop works out {n} run ends, 2 expected (Move an island?)')
    first = None
    for l in body(lines, 'p_andsplit'):
        m = two.match(l)
        if m:
            first = m.group(1)
            break
    if first is None or not kept(first):
        raise SystemExit(f'{path}: AndSplit tests a against 2 in {first}, a register expected')
    n = 0
    for l in body(lines, 'p_dead'):
        if call in l:
            break
        if store.match(l):
            n += 1
    if n > most:
        raise SystemExit(f'{path}: Dead stores {n} words before its first call, at most {most}')
    print('check_straight: TryWrite and TryRead zeroes, MoveLoop in chunks, AndSplit in registers, Dead stores')


if __name__ == '__main__':
    main()
