#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""An element's index that is a sum takes its constant into the
displacement (P313). In the routines named of the assembly paslangc
wrote, an index v + c is v scaled, the constant in the element's
displacement: on amd64 no lea of a constant plus a register into
another (rcx aside, the check's) that the next instruction scales or
reads as an address's index, and no imulq of an index; on arm64 (--arm)
no add of a constant to a register that the next instruction scales,
and no add or sub of a constant to the address an ADD or MADD of the
scaled index just made, a low bound's, that the load or store's offset
takes.
"""

import re
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arm = "--arm" in sys.argv
    if len(args) != 2:
        raise SystemExit("usage: check_idxsum.py file.s name,name,... [--arm]")
    path, names = args[0], set(n for n in args[1].split(",") if n)
    fn, bad, seen = "", [], set()
    prev = None
    for n, line in enumerate(open(path), 1):
        line = line.rstrip("\n")
        m = re.match(r"^(p_[A-Za-z0-9_]+|rt_[A-Za-z0-9_]+|pas_main):$", line)
        if m:
            fn = m.group(1)[2:] if m.group(1).startswith("p_") else ""
            if fn in names:
                seen.add(fn)
            prev = None
            continue
        if fn not in names or not line.startswith("  ") or line.startswith("  ."):
            continue
        ins = line.strip()
        if not arm:
            if ins.startswith("imulq "):
                bad.append(f"{n}: {fn}: {ins}")
            if prev:
                pr, pn, pins = prev
                scaled = re.search(r"\(%[a-z0-9]*,%" + pr[1:] + r"(,[1248])?\)", ins) or \
                    re.match(r"^(leaq \(%(" + pr[1:] + r"),%(" + pr[1:] + r")|shlq \$\d+, " + pr + r"$|addq " + pr + ", " + pr + "$)", ins)
                if scaled:
                    bad.append(f"{pn}: {fn}: {pins} then {ins}: the index's constant before its scale")
            prev = None
            k = re.match(r"^leaq (-?\d+)\((%[a-z0-9]+)\), (%[a-z0-9]+)$", ins)
            if k and k.group(1) != "0" and k.group(3) not in ("%rcx", k.group(2)):
                prev = (k.group(3), n, ins)
            continue
        if prev:
            pr, pn, pins, kind = prev
            if kind == "add":
                if re.match(r"^(madd \w+, " + pr + r", |add \w+, \w+, " + pr + r", lsl #|lsl \w+, " + pr + r", #)", ins):
                    bad.append(f"{pn}: {fn}: {pins} then {ins}: the index's constant before its scale")
            elif re.match(r"^(add|sub) " + pr + ", " + pr + r", #\d+$", ins):
                bad.append(f"{n}: {fn}: {pins} then {ins}: a displacement the access takes")
        prev = None
        k = re.match(r"^(add|sub) (x\d+), (x\d+), #(\d+)$", ins)
        if k and k.group(2) != k.group(3):
            prev = (k.group(2), n, ins, "add")
            continue
        k = re.match(r"^(madd (x\d+), x\d+, x\d+, x\d+|add (x\d+), x\d+, x\d+, lsl #\d+)$", ins)
        if k:
            prev = (k.group(2) or k.group(3), n, ins, "addr")
    missing = names - seen
    if missing:
        raise SystemExit(f"check_idxsum: no routine {', '.join(sorted(missing))} in {path}")
    if bad:
        print("\n".join(bad))
        raise SystemExit(f"check_idxsum: {len(bad)} indexes summed before their scale in {path}")
    print(f"check_idxsum: {len(seen)} routines take an index's constant in the displacement in {path}")


if __name__ == "__main__":
    main()
