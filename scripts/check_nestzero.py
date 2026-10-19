#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A routine with nested ones zeroes only the locals a read may reach
first (P358), read in the assembly of testdata/nestzero built with
-inline 0: the words of its frame each routine named stores zero into
(movq $0, N(%rbp) on amd64; str or stur xzr, [x29, #N] on arm64 with
--arm, one word each, as ZeroFrame writes up to 16 words) are as many
as --expect says, routine:words separated by commas.

usage: check_nestzero.py file.s [--arm] --expect=p_a:0,p_b:2
"""

import re
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arm = "--arm" in sys.argv[1:]
    expect = {}
    for a in sys.argv[1:]:
        if a.startswith("--expect="):
            for kv in a.split("=", 1)[1].split(","):
                k, v = kv.split(":")
                expect[k] = int(v)
    if len(args) != 1 or not expect:
        raise SystemExit(__doc__)
    words, name = {}, None
    for l in open(args[0]).read().splitlines():
        m = re.match(r"^([A-Za-z_][\w.]*):$", l)
        if m:
            name = m.group(1)
            words.setdefault(name, 0)
            continue
        s = l.strip()
        if name is None:
            continue
        if (not arm and re.match(r"^movq \$0, -?\d+\(%rbp\)$", s)) or \
                (arm and re.match(r"^stu?r xzr, \[x29, #-?\d+\]$", s)):
            words[name] += 1
    bad = []
    for r, n in expect.items():
        if r not in words:
            bad.append(f"{r}: not found")
        elif words[r] != n:
            bad.append(f"{r}: {words[r]} words zeroed, {n} expected")
    if bad:
        print("\n".join(bad))
        raise SystemExit(f"check_nestzero: {len(bad)} routines zero other words in {args[0]}")
    print(f"check_nestzero: {len(expect)} routines zero only what a read may reach first, in {args[0]}")


if __name__ == "__main__":
    main()
