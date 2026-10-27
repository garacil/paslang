#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""testdata/splitcall's forms (P400), built with -inline 0.

A call alone in a region takes its arguments straight from the
registers that hold them and leaves its value in its variable's
register: LoopCalls' k := Step(k, N) ends in two register moves into
the argument registers, the call and one move of rax or x0 into a
register; Chain's head := MkNode(i, head) the same, after a store of
head, a reference the collector reads at home. Sums' calls, split out of its sums, are such calls
too: at least three of its five take their first argument from a
register and leave their value in one.

usage: check_splitcall.py file.s [--arm]
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
        if line.lstrip().startswith('.') or re.match(r'^\.L[A-Za-z0-9_]*:$', line):
            continue
        out.append(line)
    return out


def calls(b, callee, arm):
    """Each call of callee in b: the instructions before it back to the
    previous call or branch, and the one after it."""
    site = re.compile(r'^\s+bl ' + callee + '$' if arm else r'^\s+call ' + callee + '$')
    out = []
    for i, line in enumerate(b):
        if site.match(line):
            before = []
            for prev in reversed(b[:i]):
                if re.match(r'^\s+(bl|b\.|cb|tb|b |call|j)', prev):
                    break
                before.insert(0, prev)
            after = b[i + 1] if i + 1 < len(b) else ''
            out.append((before, after))
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    arm = '--arm' in sys.argv[1:]
    if len(args) != 1:
        raise SystemExit(__doc__.strip().splitlines()[-1])
    path = args[0]
    lines = open(path).read().splitlines()
    if arm:
        argmove = lambda n: re.compile(r'^\s+mov x%d, x(19|2[0-6])$' % n)
        valmove = re.compile(r'^\s+mov x(19|2[0-6]), x0$')
        frame = re.compile(r'\[x29, #-?\d+\]')
    else:
        regs = r'%(rbx|r1[0-5]|r[89])'
        names = ['rdi', 'rsi', 'rdx', 'rcx']
        argmove = lambda n: re.compile(r'^\s+movq ' + regs + ', %' + names[n] + '$')
        valmove = re.compile(r'^\s+movq %rax, ' + regs + '$')
        frame = re.compile(r'\(%rbp\)')

    def alone(before, after, n):
        moves = before[len(before) - n:]
        if len(moves) != n or any(not argmove(i).match(moves[i]) for i in range(n)):
            return False
        return bool(valmove.match(after))

    for name, callee, n in (('p_loopcalls', 'p_step', 2), ('p_chain', 'p_mknode', 2)):
        cs = calls(body(lines, name), callee, arm)
        if len(cs) != 1:
            raise SystemExit(f'{path}: {name} calls {callee} {len(cs)} times, once expected')
        before, after = cs[0]
        if not alone(before, after, n):
            raise SystemExit(f'{path}: {name}\'s {callee} is no call alone in registers: '
                             f'{before} / {after}')
    ok = 0
    total = 0
    for callee in ('p_twice', 'p_tag'):
        for before, after in calls(body(lines, 'p_sums'), callee, arm):
            total += 1
            first = [l for l in before if argmove(0).match(l)]
            if first and valmove.match(after) and not any(frame.search(l) for l in first):
                ok += 1
    if total != 5:
        raise SystemExit(f'{path}: Sums makes {total} calls, 5 expected')
    if ok < 3:
        raise SystemExit(f'{path}: {ok} of Sums\' calls take a register and leave one, 3 expected')
    print(f'check_splitcall: LoopCalls and Chain call alone in registers, {ok} of Sums\' 5 calls too')


if __name__ == '__main__':
    main()
