#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""The scaled index of an element is computed once for the fields read
or written of it (P314). In the assembly paslangc wrote, each routine
named with its most (name:count) makes no more than that many scales of
an index on amd64 (a lea, shift or add whose register the next address
takes as its index) and no more element addresses on arm64 (with
--arm: an ADD of a shifted register or a MADD whose register the next
load or store takes as its base).
"""

import re
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arm = "--arm" in sys.argv
    if len(args) != 2:
        raise SystemExit("usage: check_fieldcse.py file.s name:count,... [--arm]")
    want = {}
    for item in args[1].split(","):
        n, c = item.split(":")
        want[n] = int(c)
    lines = open(args[0]).read().splitlines()
    fn, got, starts = "", {}, []
    for n, line in enumerate(lines):
        m = re.match(r"^(p_[A-Za-z0-9_]+|rt_[A-Za-z0-9_]+|pas_main):$", line)
        if m:
            fn = m.group(1)[2:] if m.group(1).startswith("p_") and m.group(1)[2:] in want else ""
            continue
        if not fn:
            continue
        if arm:
            k = re.match(r"^  (?:add (x\d+), x\d+, x\d+, lsl #\d+|madd (x\d+), x\d+, x\d+, x\d+)$", line)
            if k:
                reg = k.group(1) or k.group(2)
                for nxt in lines[n + 1:n + 4]:
                    if re.search(r"\[" + reg + r"[,\]]", nxt):
                        got[fn] = got.get(fn, 0) + 1
                        break
        else:
            k = re.match(r"^  (?:leaq \(%r\w+(?:,%r\w+)?(?:,\d)?\)|shlq \$\d+|addq %r\w+), (%r\w+)$", line)
            if k:
                reg = k.group(1)
                for nxt in lines[n + 1:n + 4]:
                    if re.search(r"\(%\w*,%" + reg[1:] + r",\d\)|\(,%" + reg[1:] + r",\d\)", nxt):
                        got[fn] = got.get(fn, 0) + 1
                        break
    bad = [f"{f}: {got.get(f, 0)} where {c} at most" for f, c in want.items() if got.get(f, 0) > c]
    if bad:
        raise SystemExit("check_fieldcse: " + "; ".join(bad) + f" in {args[0]}")
    print(f"check_fieldcse: " + ", ".join(f"{f} {got.get(f, 0)}" for f in want) + f" in {args[0]}")


if __name__ == "__main__":
    main()
