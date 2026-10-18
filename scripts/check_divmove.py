#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A division's value lands in the register that reads it (P356), read
in the assembly of testdata/divreg built with -inline 0, in each routine
named By: on amd64 no division's value moved twice (movq %rax or %rdx
to a pool register and that register moved on at once) and no dividend
moved from the pool to rax just before the zero check (movq %rsi, %rax;
testq %rcx, %rcx); on arm64 (--arm) no operand moved to x0 or x1 just
before the zero check, no quotient moved from x16, and no value of
sdiv or msub moved from its pool register at once. At least --min
divisions (idivq, imulq by a magic number or a shift of a power of two
on amd64; sdiv or smulh on arm64) are seen, so the routines are there.

usage: check_divmove.py file.s [--arm] [--min=N]
"""

import re
import sys

POOL_AMD = ("rsi", "rdi", "r8")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arm = "--arm" in sys.argv[1:]
    least = 1
    for a in sys.argv[1:]:
        if a.startswith("--min="):
            least = int(a.split("=", 1)[1])
    if len(args) != 1:
        raise SystemExit(__doc__)
    body, name = {}, None
    for l in open(args[0]).read().splitlines():
        m = re.match(r"^([A-Za-z_][\w.]*):$", l)
        if m:
            name = m.group(1)
            body[name] = []
            continue
        if name is not None:
            s = l.strip()
            if s and not s.startswith(".loc") and not s.startswith(".cfi") and not re.match(r"^\.LL\d+:$", s):
                body[name].append(s)
    bad, divs = [], 0
    for r, ls in body.items():
        if not r.startswith("p_by"):
            continue
        for i, l in enumerate(ls):
            nxt = ls[i + 1] if i + 1 < len(ls) else ""
            if not arm:
                if l.startswith("idivq") or re.match(r"^imulq %(rsi|rdi|r8|rcx)$", l):
                    divs += 1
                m = re.match(r"^movq %(rax|rdx), %(\w+)$", l)
                if m and m.group(2) in POOL_AMD and re.match(r"^movq %" + m.group(2) + r", %\w+$", nxt):
                    bad.append(f"{r}: {l}; {nxt}")
                m = re.match(r"^movq %(\w+), %rax$", l)
                if m and m.group(1) in POOL_AMD and nxt == "testq %rcx, %rcx":
                    bad.append(f"{r}: {l}; {nxt}")
            else:
                if l.startswith("sdiv ") or l.startswith("smulh "):
                    divs += 1
                if re.match(r"^mov x[01], ", l) and nxt.startswith("cbz "):
                    bad.append(f"{r}: {l}; {nxt}")
                if re.match(r"^mov x\d+, x16$", l):
                    bad.append(f"{r}: {l}")
                m = re.match(r"^(sdiv|msub) (x\d+), ", l)
                if m and 9 <= int(m.group(2)[1:]) <= 15 and re.match(r"^mov x\d+, " + m.group(2) + "$", nxt):
                    bad.append(f"{r}: {l}; {nxt}")
    if bad:
        print("\n".join(bad[:20]))
        raise SystemExit(f"check_divmove: {len(bad)} moves of a division's operands or value in {args[0]}")
    if divs < least:
        raise SystemExit(f"check_divmove: {divs} divisions in the routines named By, {least} expected, in {args[0]}")
    print(f"check_divmove: {divs} divisions, their values where they are read, in {args[0]}")


if __name__ == "__main__":
    main()
