#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A variable a register keeps is assigned in its register, and a narrow
one read in place (P318). In the assembly paslangc wrote, the loops of
the routines whose names start with mix (from their first aligned head
to their back edge) move no value from the pool into a variable's
register (amd64 movq %rsi or %rdi into a register outside the pool and
rax, rcx and rdx; arm64 mov of x9 to x15 into x19 to x28) and no
variable's register into rax or x17 to be an operand (a move into rax
whose next instruction reads rax and writes elsewhere; arm64 mov x17,
xN of a variable's register). --arm reads arm64's.
"""

import re
import sys

AMD_SCRATCH = {"rsi", "rdi", "rax", "rcx", "rdx", "r8", "r11"}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arm = "--arm" in sys.argv[1:]
    if len(args) != 1:
        raise SystemExit("usage: check_regassign.py file.s [--arm]")
    lines = open(args[0]).read().splitlines()
    bad, seen = [], set()
    fn, inloop = "", False
    for n, line in enumerate(lines):
        m = re.match(r"^(p_[A-Za-z0-9_]+|rt_[A-Za-z0-9_]+|pas_main):$", line)
        if m:
            fn = m.group(1) if m.group(1).startswith("p_mix") else ""
            inloop = False
            continue
        if not fn:
            continue
        if line.strip().startswith(".p2align"):
            inloop = True
            seen.add(fn)
            continue
        if not inloop:
            continue
        ins = line.strip()
        if re.match(r"^(jl|jle|jg|jge|b\.lt|b\.le|b\.gt|b\.ge) ", ins):
            inloop = False
            continue
        nxt = lines[n + 1].strip() if n + 1 < len(lines) else ""
        if arm:
            mv = re.match(r"^mov (x\d+), (x\d+)$", ins)
            if not mv:
                continue
            d, s = int(mv.group(1)[1:]), int(mv.group(2)[1:])
            if 19 <= d <= 28 and 9 <= s <= 15:
                bad.append(f"{n + 1}: {fn}: {ins} (a value moved into a variable)")
            elif d == 17 and 19 <= s <= 28:
                bad.append(f"{n + 1}: {fn}: {ins} (a variable through x17)")
            continue
        mv = re.match(r"^movq %(\w+), %(\w+)$", ins)
        if not mv:
            continue
        s, d = mv.group(1), mv.group(2)
        if s in ("rsi", "rdi") and d not in AMD_SCRATCH:
            bad.append(f"{n + 1}: {fn}: {ins} (a value moved into a variable)")
        elif d == "rax" and s not in AMD_SCRATCH and re.match(r"^\w+ %rax, %\w+$", nxt) \
                and not nxt.endswith("%rax"):
            bad.append(f"{n + 1}: {fn}: {ins} then {nxt} (a variable through rax)")
    if len(seen) < 7:
        raise SystemExit(f"check_regassign: only {len(seen)} mix loops in {args[0]}")
    if bad:
        print("\n".join(bad[:20]))
        raise SystemExit(f"check_regassign: {len(bad)} moves in the loops of {args[0]}")
    print(f"check_regassign: {len(seen)} loops with no move into a variable or through a scratch register in {args[0]}")


if __name__ == "__main__":
    main()
