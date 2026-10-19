#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A routine whose result is a block writes it into its caller's buffer
(P153).

With --routines, in one file, the assembly of testdata/recres built with
-inline 0: each routine it names takes no block from rt_alloc to copy
Result into, keeps the buffer's address (rax, x8 with --arm) in its
frame before it calls anything but its stack check's rt_morestack, and
tests for a buffer of 0; every call of one of them sets rax (x8) right
before the call instruction; and at least N of those calls (--dest=N)
give a global's own address, the variable the assignment writes.

With --all, over every .s file in the directories named, a program's and
the units' alike: every routine marked .set .Lrb.<routine> takes a
buffer, and every call of one sets rax or x8 right before it, a unit's
from any file, a program's (a file with pas_main) from its own (an
arm64 file is one that names x29); the stage compiler's assembly, which
the boot compiler writes, is left out. A unit's routine a
program calls with no buffer, as the maker of a record's constructor
was, shows here.

usage: check_resbuf.py file.s [--arm] --routines=p_a,p_b --dest=N
       check_resbuf.py --all dir...
"""

import os
import re
import sys

CALL = re.compile(r"^(?:bl|call) ([A-Za-z_][\w.]*)$")


def lines_of(path):
    out = []
    for l in open(path, errors="replace").read().splitlines():
        s = l.strip()
        if not s or s.startswith(".loc") or s.startswith(".cfi") or re.match(r"^\.L(L|gm)\d+:$", s):
            continue
        out.append(s)
    return out


def sets_buffer(p, arm):
    if arm:
        return re.match(r"^(add|sub|mov) x8, ", p) is not None
    return re.match(r"^leaq .*, %rax$", p) is not None


def check_all(dirs):
    files = []
    for d in dirs:
        for n in sorted(os.listdir(d)):
            # the stage compiler is the boot compiler's work, an older
            # paslangc's convention (make's stage, P262)
            if n.endswith(".s") and not n.endswith("-stage.s"):
                files.append(os.path.join(d, n))
    # a unit's routine is called from any file; a program's routines are
    # its own (two programs may each have a p_outer of their own)
    units, own, texts = set(), {}, {}
    for f in files:
        L = lines_of(f)
        texts[f] = L
        own[f] = set()
        for l in L:
            m = re.match(r"^\.set \.Lrb\.([A-Za-z_][\w.]*), 1$", l)
            if m:
                own[f].add(m.group(1))
        if "pas_main:" not in L:
            units |= own[f]
    bad, calls = [], 0
    for f, L in texts.items():
        marked = own[f] | units
        arm = any("x29" in l for l in L)
        for i, l in enumerate(L):
            m = CALL.match(l)
            if not m or m.group(1) not in marked:
                continue
            calls += 1
            if i == 0 or not sets_buffer(L[i - 1], arm):
                bad.append(f"{f}: {l} after {L[i - 1] if i else ''}")
    if bad:
        print("\n".join(bad[:40]))
        raise SystemExit(f"check_resbuf: {len(bad)} calls give no buffer, in {len(files)} files")
    n = len(units | set().union(*own.values())) if own else 0
    print(f"check_resbuf: {n} routines take a buffer, all {calls} calls of them give one, in {len(files)} files")


def main():
    if "--all" in sys.argv[1:]:
        check_all([a for a in sys.argv[1:] if not a.startswith("--")])
        return
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arm = "--arm" in sys.argv[1:]
    routines, dest = [], 0
    for a in sys.argv[1:]:
        if a.startswith("--routines="):
            routines = a.split("=", 1)[1].split(",")
        if a.startswith("--dest="):
            dest = int(a.split("=", 1)[1])
    if len(args) != 1 or not routines:
        raise SystemExit(__doc__)
    bodies, fn, lines = {}, None, []
    for l in open(args[0]).read().splitlines():
        s = l.strip()
        m = re.match(r"^([A-Za-z_][\w.]*):$", l)
        if m and not l.startswith(".L"):
            fn = m.group(1)
            bodies[fn] = []
        if not s or s.startswith(".loc") or s.startswith(".cfi") or re.match(r"^\.L(L|gm)\d+:$", s):
            continue
        lines.append(s)
        if fn is not None:
            bodies[fn].append(s)
    bad = []
    alloc = "bl rt_alloc" if arm else "call rt_alloc"
    keep = re.compile(r"^str x8, \[x29, #-\d+\]$" if arm else r"^movq %rax, -\d+\(%rbp\)$")
    test = re.compile(r"^cbz x0, \.L\d+$" if arm else r"^jz \.L\d+$")
    for r in routines:
        b = bodies.get(r)
        if b is None:
            bad.append(f"{r}: not found")
            continue
        # the old epilogue: a block from rt_alloc, Result copied into it
        for i in range(len(b) - 1):
            if b[i] == alloc and b[i + 1] in ("mov x4, x0", "movq %rax, %rdi"):
                bad.append(f"{r}: {alloc}; {b[i + 1]}")
        first = next((i for i, l in enumerate(b) if (CALL.match(l) and "rt_morestack" not in l) or l.startswith("blr") or l.startswith("call *")), len(b))
        # arm64 past LDUR's reach: x16 = x29 - N, then str x8, [x16]
        far = arm and any(b[i] == "str x8, [x16]" and re.match(r"^(sub|add) x16, x29, ", b[i - 1])
                          for i in range(1, first))
        if not far and not any(keep.match(l) for l in b[:first]):
            bad.append(f"{r}: the buffer's address is not kept before the first call")
        if not any(test.match(l) for l in b):
            bad.append(f"{r}: no test of a buffer of 0")
    calls = glob = 0
    for i, l in enumerate(lines):
        m = CALL.match(l)
        if not m or m.group(1) not in routines:
            continue
        calls += 1
        p = lines[i - 1] if i > 0 else ""
        ok = sets_buffer(p, arm)
        if arm:
            g = re.match(r"^add x8, x8, :lo12:v_", p) is not None
        else:
            g = re.match(r"^leaq v_\w+(\+0)?\(%rip\), %rax$", p) is not None
        if not ok:
            bad.append(f"{l}: after {p}")
        glob += g
    if glob < dest:
        bad.append(f"{glob} calls give a global's address, {dest} at least")
    reg = "x8" if arm else "rax"
    if bad:
        print("\n".join(bad))
        raise SystemExit(f"check_resbuf: {len(bad)} calls or routines out of the buffer's rule, in {args[0]}")
    print(f"check_resbuf: {len(routines)} routines write their block into the buffer in {reg}, {calls} calls give one, {glob} a global's, in {args[0]}")


if __name__ == "__main__":
    main()
