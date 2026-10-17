#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""An and compared with 0 is one test of its source (P322). In the
assembly paslangc wrote, the routines whose names start with reg, home
and narrow hold no AND whose next instruction tests its result against
zero (amd64 testq of the register by itself; arm64 cbz, cbnz, or cmp of
it with #0), but for the routines named with their most (name:count),
whose masks no TEST takes; and with --arm at least --tbz=N TBZ or TBNZ
in the compiled routines, the tests of one bit TbzPass joined to their
branches.
"""

import re
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arm = "--arm" in sys.argv[1:]
    tbz = 0
    for a in sys.argv[1:]:
        if a.startswith("--tbz="):
            tbz = int(a[6:])
    if len(args) not in (1, 2):
        raise SystemExit("usage: check_andtest.py file.s [name:count,...] [--arm] [--tbz=N]")
    allow = {}
    if len(args) == 2:
        for item in args[1].split(","):
            n, c = item.split(":")
            allow[n] = int(c)
    lines = open(args[0]).read().splitlines()
    fn, got, compiled, nt = "", {}, False, 0
    for i, l in enumerate(lines):
        m = re.match(r"^(p_[A-Za-z0-9_]+|rt_[A-Za-z0-9_]+|pas_main):$", l)
        if m:
            name = m.group(1)
            compiled = not name.startswith("rt_")
            fn = name[2:] if re.match(r"^p_(reg|home|narrow)", name) else ""
            if fn:
                got.setdefault(fn, 0)
            continue
        if compiled and re.match(r"^  tbn?z ", l):
            nt += 1
        if not fn or i + 1 >= len(lines):
            continue
        nx = lines[i + 1].strip()
        if arm:
            a = re.match(r"^  and (x\d+), ", l)
            if a and re.match(r"^(cbn?z " + a.group(1) + r",|cmp " + a.group(1) + r", #0$)", nx):
                got[fn] += 1
        else:
            a = re.match(r"^  and[lq] [^,]+, %(\w+)$", l)
            if a and nx == f"testq %{a.group(1)}, %{a.group(1)}":
                got[fn] += 1
    if len(got) < 20:
        raise SystemExit(f"check_andtest: only {len(got)} routines in {args[0]}")
    bad = [f"{f}: {c} ANDs before a zero test where {allow.get(f, 0)} at most"
           for f, c in sorted(got.items()) if c > allow.get(f, 0)]
    if arm and nt < tbz:
        bad.append(f"{nt} TBZ or TBNZ where {tbz} at least")
    if bad:
        raise SystemExit("check_andtest: " + "; ".join(bad[:12]) + f" in {args[0]}")
    print(f"check_andtest: {len(got)} routines test their ands" +
          (f", {nt} TBZ or TBNZ" if arm else "") + f" in {args[0]}")


if __name__ == "__main__":
    main()
