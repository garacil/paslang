#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""Every stack frame fits the room the prologue's check gives (P342),
read in the assembly paslangc wrote, amd64 or with --arm arm64, as Go's
linker proves a chain of nosplit functions fits its guard
(cmd/link/internal/ld/stackcheck.go).

A routine that checks its stack at entry (amd64 leaq -(F+R)(%rsp), %r11
and cmpq 16(%r14), %r11; arm64 sub x9, sp, #F+R and cmp x9, x10 after
ldr x10, [x28, #16]) has F+R bytes below the stack pointer it came in
with. Its own pushes and subtractions of the stack pointer, a call's
return address on amd64, and the most a callee that checks nothing adds
in its turn, must stay within those bytes at every point. A routine that
checks nothing counts as the most it adds, its callees' included: its
height. A move into the stack pointer from anything but the frame
pointer is another stack, the M's, and ends the walk. An indirect call
reaches a compiled routine, which checks itself. A routine that checks
itself still takes its caller's bytes until its check sends it to
rt_morestack and the M's stack: the call of rt_morestack and the words
.ms_preempt writes under it, 8 and 32 on amd64, 16 and 96 on arm64
(--entry=N). A routine whose own code counts its room (rt_yieldpoint,
and rt_asyncpreempt, which rt_sigurg enters only with room) is named
with --room=NAME, or NAME:BYTES when it writes BYTES before it counts.

A routine of the pasasync table (its .section pasasync.NAME) may be
stopped by rt_sigurg at any instruction, and the stop writes --async=N
bytes below its stack pointer (the runtime's AsyncRoom: rt_sigurg asks
for them above the real guard, as Go's isAsyncSafePoint asks for
asyncPreemptStack): at its deepest it needs them too, and so does an
unchecked one it calls. With --async, rt_asyncpreempt and rt_yieldpoint,
where a file has them, are proved to write no more than N below the
stack pointer of the code they stop: their return address (8 on amd64)
or the 16 bytes rt_sigurg stores on arm64, and their own words.

usage: check_stack.py file.s... [--arm] [--room=NAME[:BYTES],...] [--async=N] [--margin=N]
       [--entry=N] [--least=N]
prints the least room left over every routine of every file (the N
least with --least), and fails when one has less than --margin bytes.
"""

import re
import sys


def routines(lines):
    out, name = {}, None
    for l in lines:
        m = re.match(r"^([A-Za-z_][\w.]*):$", l)
        if m:
            name = m.group(1)
            out[name] = []
            continue
        if name is not None:
            out[name].append(l)
    return out


def asyncs(lines):
    """the routines of the pasasync table"""
    out = set()
    for l in lines:
        m = re.match(r"^\.section pasasync\.([\w.]+),", l.strip())
        if m:
            out.add(m.group(1))
    return out


def sets(lines):
    out = {}
    for l in lines:
        m = re.match(r"^\.set (\S+), (-?\d+)$", l.strip())
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


class Walk:
    """the walk of one routine: the depth below its entry stack pointer
    at each instruction, by its control flow (a label takes the depth of
    the jumps and the fall that reach it, code after a ret or a jmp
    counts again at a label reached), and its calls with that depth"""

    def __init__(self, body, arm, symbols):
        self.budget = None
        self.events = []
        self.peak = 0
        self.unknown = []
        lines = [l.strip() for l in body if l.strip() and not l.strip().startswith(".loc")
                 and not l.strip().startswith(".cfi")]
        at = {}
        d, live, fp = 0, True, None
        for i, t in enumerate(lines):
            m = re.match(r"^([.\w]+):$", t)
            if m:
                if m.group(1) in at:
                    d = max(d, at[m.group(1)]) if live else at[m.group(1)]
                    live = True
                continue
            if not live:
                continue
            if self.check(lines, i, d, arm, symbols):
                pass
            if not arm:
                if re.match(r"^movq (?!%rbp)\S+, %rsp$", t):
                    live = False
                    continue
                if t == "movq %rsp, %rbp":
                    fp = d
                elif t == "movq %rbp, %rsp" and fp is not None:
                    d = fp
                elif t.startswith("pushq") or t == "pushfq":
                    d += 8
                elif t.startswith("popq") or t == "popfq":
                    d -= 8
                m = re.match(r"^subq \$(\d+), %rsp$", t)
                if m:
                    d += int(m.group(1))
                m = re.match(r"^addq \$(\d+), %rsp$", t)
                if m:
                    d -= int(m.group(1))
                m = re.match(r"^leaq (-?\d+)\(%rsp\), %rsp$", t)
                if m:
                    d -= int(m.group(1))
                m = re.match(r"^leaq -(\d+)\(%rbp\), %rsp$", t)
                if m and fp is not None:
                    d = fp + int(m.group(1))
                m = re.match(r"^subq \$\(?(\.\S+?)\)?, %rsp$", t)
                if m:
                    d += symbols.get(m.group(1), 0)
                    if m.group(1) not in symbols:
                        self.unknown.append(f"subq of {m.group(1)}")
                m = re.match(r"^call (\S+)$", t)
                if m:
                    self.events.append((d + 8, "*" if m.group(1).startswith("*") else m.group(1)))
                m = re.match(r"^(j[a-z]+) (\S+)$", t)
                if m:
                    tgt = m.group(2)
                    if tgt.startswith("*"):
                        live = False
                    elif not tgt.startswith("."):
                        # another routine: a tail call, taken or not
                        self.events.append((d, tgt))
                        if m.group(1) == "jmp":
                            live = False
                    else:
                        at[tgt] = max(at.get(tgt, d), d)
                        if m.group(1) == "jmp":
                            live = False
                if t == "ret" or t.startswith("ud2"):
                    live = False
            else:
                if re.match(r"^mov sp, (?!x29)\S+$", t):
                    live = False
                    continue
                if t == "mov x29, sp":
                    fp = d
                elif t == "mov sp, x29" and fp is not None:
                    d = fp
                m = re.match(r"^st[pr] \S+(, \S+)?, \[sp, #-(\d+)\]!$", t)
                if m:
                    d += int(m.group(2))
                m = re.match(r"^ld[pr] \S+(, \S+)?, \[sp\], #(\d+)$", t)
                if m:
                    d -= int(m.group(2))
                m = re.match(r"^sub sp, sp, #(\d+)(, lsl #12)?$", t)
                if m:
                    d += int(m.group(1)) << (12 if m.group(2) else 0)
                m = re.match(r"^add sp, sp, #(\d+)(, lsl #12)?$", t)
                if m:
                    d -= int(m.group(1)) << (12 if m.group(2) else 0)
                m = re.match(r"^sub sp, x29, #(\d+)$", t)
                if m and fp is not None:
                    d = fp + int(m.group(1))
                m = re.match(r"^bl (\S+)$", t)
                if m:
                    self.events.append((d, m.group(1)))
                if t.startswith("blr "):
                    self.events.append((d, "*"))
                m = re.match(r"^(b|b\.\w+|cbn?z \w+,|tbn?z \w+, #\d+,) (\S+)$", t)
                if m:
                    tgt = m.group(2)
                    if not tgt.startswith("."):
                        self.events.append((d, tgt))
                        if m.group(1) == "b":
                            live = False
                    else:
                        at[tgt] = max(at.get(tgt, d), d)
                        if m.group(1) == "b":
                            live = False
                if t == "ret" or t.startswith("br ") or t.startswith("udf"):
                    live = False
            self.peak = max(self.peak, d)

    def check(self, lines, i, d, arm, symbols):
        """the entry check at line i, with nothing pushed before it"""
        if self.budget is not None or d != 0:
            return False
        t = lines[i]
        if not arm:
            m = re.match(r"^leaq -\(?([^()]+?)\)?\(%rsp\), %r11$", t)
            if not m or i + 1 >= len(lines) or not lines[i + 1].startswith("cmpq 16(%r14), %r11"):
                return False
            total = 0
            for term in m.group(1).split("+"):
                if term.lstrip("-").isdigit():
                    total += int(term)
                elif term in symbols:
                    total += symbols[term]
                else:
                    self.unknown.append(f"frame {term}")
                    return False
            self.budget = total
            return True
        m = re.match(r"^sub x9, sp, #(\d+)(, lsl #12)?$", t)
        if not m:
            return False
        k = int(m.group(1)) << (12 if m.group(2) else 0)
        j = i + 1
        m2 = re.match(r"^sub x9, x9, #(\d+)(, lsl #12)?$", lines[j]) if j < len(lines) else None
        if m2:
            k += int(m2.group(1)) << (12 if m2.group(2) else 0)
            j += 1
        if j + 1 < len(lines) and lines[j] == "ldr x10, [x28, #16]" and lines[j + 1] == "cmp x9, x10":
            self.budget = k
            return True
        return False


def main():
    arm = "--arm" in sys.argv[1:]
    room = {}
    stop = 0
    margin = 0
    entry = 112 if arm else 40
    least = 0
    rows = []
    files = []
    for a in sys.argv[1:]:
        if a.startswith("--room="):
            for r in a[7:].split(","):
                n, _, b = r.partition(":")
                room[n] = int(b or 0)
        elif a.startswith("--async="):
            stop = int(a[8:])
        elif a.startswith("--margin="):
            margin = int(a[9:])
        elif a.startswith("--entry="):
            entry = int(a[8:])
        elif a.startswith("--least="):
            least = int(a[8:])
        elif not a.startswith("--"):
            files.append(a)
    if not files:
        raise SystemExit("usage: check_stack.py file.s... [--arm] [--room=NAME[:BYTES],...] [--async=N] [--margin=N]")
    worst = None
    bad = []
    for path in files:
        lines = open(path).read().splitlines()
        symbols = sets(lines)
        stoppable = asyncs(lines) if stop else set()
        walks = {n: Walk(b, arm, symbols) for n, b in routines(lines).items()}
        memo = {}

        def height(n, stack=()):
            """the most an unchecked routine adds below its caller's stack pointer"""
            if n == "*":
                return 0
            if n in room:
                return room[n]
            w = walks.get(n)
            if w is None:
                return 0
            if w.budget is not None:
                return entry
            if n in memo:
                return memo[n]
            if n in stack:
                return 0
            h = w.peak + (stop if n in stoppable else 0)
            for d, t in w.events:
                h = max(h, d + height(t, stack + (n,)))
            memo[n] = h
            return h

        # what a stop writes below the stack pointer it stops: rt_sigurg's
        # call of rt_asyncpreempt pushes the return address on amd64 and
        # stores 16 bytes on arm64, rt_yieldpoint's caller pushes 8 on
        # amd64 and nothing on arm64; then their own words, up to the
        # move to the M's stack
        if stop:
            for n, above in (("rt_asyncpreempt", 16 if arm else 8), ("rt_yieldpoint", 0 if arm else 8)):
                w = walks.get(n)
                if w is None:
                    continue
                need = w.peak
                for d, t in w.events:
                    need = max(need, d + height(t))
                if above + need > stop:
                    bad.append(f"{path}: {n} writes {above + need} bytes below the stack pointer it stops, "
                               f"more than --async={stop}")

        for n, w in walks.items():
            if w.budget is None:
                continue
            need = w.peak
            at = "its own frame"
            if n in stoppable:
                need, at = w.peak + stop, "a stop"
            for d, t in w.events:
                if d + height(t) > need:
                    need, at = d + height(t), t
            left = w.budget - need
            rows.append((left, n, at, w.budget, path))
            if worst is None or left < worst[0]:
                worst = (left, n, at, path)
            if left < margin:
                bad.append(f"{path}: {n}: {need} bytes below its entry (by {at}), its check gives {w.budget}")
            for u in w.unknown:
                bad.append(f"{path}: {n}: {u} not known")
    if bad:
        print("\n".join(bad[:20]))
        raise SystemExit(f"check_stack: {len(bad)} routines past their room")
    for left, n, at, budget, path in sorted(rows)[:least]:
        print(f"{left:6d} {n} (by {at}, check {budget}) {path}")
    left, n, at, path = worst
    print(f"check_stack: every frame within its check's room, the least {left} bytes left ({n}, by {at})")


if __name__ == "__main__":
    main()
