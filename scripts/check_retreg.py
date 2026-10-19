#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A routine with no frame works its value out in the register it
returns it in (P361), read in the assembly of testdata/retreg built
with -inline 0: in each routine --routines names, the step before the
return is no move into rax (x0 with --arm) of a register the step before
it wrote, labels no jump reaches skipped, a label one reaches a join
where the move belongs; and each routine --short names is at most N
instructions, ret and labels not counted.

usage: check_retreg.py file.s [--arm] --routines=p_a,p_b [--short=p_c:2,p_d:3]
"""

import re
import sys


def dest(l, arm):
    if arm:
        m = re.match(r"^[a-z.0-9]+ ([xw]\d+),", l)
        return ("x" + m.group(1)[1:]) if m else None
    m = re.match(r"^[a-z]+ .*, %(\w+)$", l)
    return m.group(1) if m else None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arm = "--arm" in sys.argv[1:]
    routines, short = [], {}
    for a in sys.argv[1:]:
        if a.startswith("--routines="):
            routines = a.split("=", 1)[1].split(",")
        if a.startswith("--short="):
            for kv in a.split("=", 1)[1].split(","):
                k, v = kv.split(":")
                short[k] = int(v)
    if len(args) != 1 or not routines:
        raise SystemExit(__doc__)
    bodies, fn = {}, None
    for l in open(args[0]).read().splitlines():
        m = re.match(r"^([A-Za-z_][\w.]*):$", l)
        if m and not l.startswith(".L"):
            fn = m.group(1)
            bodies[fn] = []
            continue
        if fn is not None:
            s = l.strip()
            if s and not s.startswith(".loc") and not s.startswith(".cfi") and not re.match(r"^\.LL\d+:$", s) and not s.startswith(".p2align"):
                bodies[fn].append(s)
    bad = []
    ret = "x0" if arm else "rax"
    for r in routines + list(short):
        if r not in bodies:
            bad.append(f"{r}: not found")
    for r in routines:
        b = bodies.get(r, [])
        if "ret" not in b:
            continue
        jumps = set()
        for l in b:
            m = re.search(r"(\.L\d+)$", l)
            if m and not l.endswith(":"):
                jumps.add(m.group(1))
        seq = [l for l in b[:b.index("ret")] if not (l.endswith(":") and l[:-1] not in jumps)]
        if len(seq) < 2 or seq[-1].endswith(":") or seq[-2].endswith(":"):
            continue
        mv = re.match(r"^mov x0, (x\d+)$", seq[-1]) if arm else re.match(r"^movq %(\w+), %rax$", seq[-1])
        if mv and dest(seq[-2], arm) == mv.group(1):
            bad.append(f"{r}: {seq[-2]}; {seq[-1]}")
    for r, n in short.items():
        b = bodies.get(r, [])
        if "ret" in b:
            b = b[:b.index("ret")]
        k = len([l for l in b if not l.endswith(":")])
        if k > n:
            bad.append(f"{r}: {k} instructions, {n} at most")
    if bad:
        print("\n".join(bad))
        raise SystemExit(f"check_retreg: {len(bad)} values moved into {ret} after they were worked out, in {args[0]}")
    print(f"check_retreg: {len(routines)} routines work their value out in {ret}, in {args[0]}")


if __name__ == "__main__":
    main()
