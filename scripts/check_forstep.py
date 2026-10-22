#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A for loop whose counter lives at its home reads it once a pass
(P327), read in the assembly paslangc wrote, amd64 or with --arm arm64:
no back edge whose test loaded the counter from its home into rax (x0)
reaches a top that loads it from the same home again; and at least
--loops=N tops take the counter as the test left it, stepping it in
place first (incq/decq %rax; add/sub x0, x0, #1), or step it in the
register a loop that calls keeps it in across its calls (P384: rbx,
r12, r13 or r15; x19 to x26), where it is read at no home at all.
"""

import re
import sys


def main():
    arm = "--arm" in sys.argv[1:]
    want = 1
    for a in sys.argv[1:]:
        if a.startswith("--loops="):
            want = int(a[8:])
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        raise SystemExit("usage: check_forstep.py file.s [--arm] [--loops=N]")
    lines = [l for l in open(args[0]).read().splitlines()
             if not re.match(r"^\s*\.(loc|cfi)", l) and not l.startswith(".LL")]
    at = {}
    for i, l in enumerate(lines):
        m = re.match(r"^(\.L\w+):$", l)
        if m:
            at[m.group(1)] = i
    bad, held, kept = [], 0, 0
    if arm:
        jump = re.compile(r"^  b\.(lt|gt|le|ge) (\.L\w+)$")
        load = re.compile(r"^  ldr x0, (\[x29, #-?\d+\])$")
        step = re.compile(r"^  (add|sub) x0, x0, #1$")
        regcmp = re.compile(r"^  cmp (x19|x2[0-6]), ")
    else:
        jump = re.compile(r"^  (jl|jg|jle|jge) (\.L\w+)$")
        load = re.compile(r"^  movq (-?\d+\(%rbp\)|v_\w+\(%rip\)), %rax$")
        step = re.compile(r"^  (incq|decq) %rax$")
        regcmp = re.compile(r"^  cmpq [^,]+, %(rbx|r12|r13|r15)$")
    for i, l in enumerate(lines):
        m = jump.match(l)
        if not m or m.group(2) not in at or i < 2:
            continue
        cmp_ = lines[i - 1]
        if arm:
            ld = load.match(lines[i - 2]) if re.match(r"^  cmp x0, ", cmp_) else None
            if not ld and re.match(r"^  cmp x0, x1$", cmp_) and i >= 3:
                ld = load.match(lines[i - 3])
        else:
            ld = load.match(lines[i - 2]) if re.match(r"^  cmpq .*, %rax$", cmp_) else None
        if not ld:
            rc = regcmp.match(cmp_)
            if rc and m.group(2) in at:
                reg = rc.group(1)
                nxt = lines[at[m.group(2)] + 1] if at[m.group(2)] + 1 < len(lines) else ""
                if (arm and re.match(rf"^  (add|sub) {reg}, {reg}, #1$", nxt)) or \
                        ((not arm) and re.match(rf"^  (incq|decq) %{reg}$", nxt)):
                    kept += 1
            continue
        top = at[m.group(2)]
        nxt = lines[top + 1] if top + 1 < len(lines) else ""
        if load.match(nxt) and load.match(nxt).group(1) == ld.group(1):
            bad.append(f"{i + 1}: {m.group(2)} loads {ld.group(1)} the test loaded")
        elif step.match(nxt):
            held += 1
    if bad or held + kept < want:
        print("\n".join(bad[:10]))
        raise SystemExit(f"check_forstep: {len(bad)} counters loaded twice a pass, {held} held "
                         f"and {kept} in a kept register ({want} at least) in {args[0]}")
    print(f"check_forstep: {held} loops step the counter the test left, {kept} the register "
          f"they keep it in, none loads it twice, in {args[0]}")


if __name__ == "__main__":
    main()
