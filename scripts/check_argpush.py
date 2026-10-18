#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""Arguments worked out in the pool push nothing (P332, P355), read in
the assembly of a test built with -inline 0: each routine named, a call
with several arguments worked out in the pool among its own, pushes no
word (pushq on amd64, str ... [sp, #-16]! on arm64 with --arm) and pops
none, the frame's own aside. The routines are testdata/manyargs's
ByDirect, ByMethod and ByValue unless --routines names others.

usage: check_argpush.py file.s [--arm] [--routines=p_a,p_b,...]
"""

import re
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arm = "--arm" in sys.argv[1:]
    routines = ["p_bydirect", "p_bymethod", "p_byvalue"]
    for a in sys.argv[1:]:
        if a.startswith("--routines="):
            routines = a.split("=", 1)[1].split(",")
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
            body[name].append(l.strip())
    bad = []
    for r in routines:
        if r not in body:
            bad.append(f"{r}: not found")
            continue
        for l in body[r]:
            if l in ("pushq %rbp", "popq %rbp"):
                continue
            if (not arm and (l.startswith("pushq") or l.startswith("popq"))) or \
                    (arm and (re.match(r"^str x\d+, \[sp, #-16\]!$", l) or re.match(r"^ldr x\d+, \[sp\], #16$", l))):
                if arm and l in ("str x30, [sp, #-16]!", "ldr x30, [sp], #16"):
                    continue
                bad.append(f"{r}: {l}")
    if bad:
        print("\n".join(bad[:20]))
        raise SystemExit(f"check_argpush: {len(bad)} pushes or pops around the calls in {args[0]}")
    print(f"check_argpush: {len(routines)} routines push nothing, in {args[0]}")


if __name__ == "__main__":
    main()
