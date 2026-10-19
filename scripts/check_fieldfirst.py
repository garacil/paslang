#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A record written field by field before it is read starts as it is
(P367), read in the assembly of testdata/fieldfirst built with -inline
0: each routine --zeros names stores exactly N zeros into its frame
(movq $0 or movl $0 to the frame on amd64; stur, str or stp of xzr to
the frame on arm64 with --arm), 0 where every field is written first.

usage: check_fieldfirst.py file.s [--arm] --zeros=p_a:0,p_b:2
"""

import re
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arm = "--arm" in sys.argv[1:]
    zeros = {}
    for a in sys.argv[1:]:
        if a.startswith("--zeros="):
            for kv in a.split("=", 1)[1].split(","):
                k, v = kv.split(":")
                zeros[k] = int(v)
    if len(args) != 1 or not zeros:
        raise SystemExit(__doc__)
    zero = re.compile(r"^(stur xzr, \[x29|str xzr, \[x29|stp xzr, xzr, \[x29)" if arm
                      else r"^mov[lq] \$0, -?\d+\(%rbp\)$")
    bodies, fn = {}, None
    for l in open(args[0]).read().splitlines():
        m = re.match(r"^([A-Za-z_][\w.]*):$", l)
        if m and not l.startswith(".L"):
            fn = m.group(1)
            bodies[fn] = []
            continue
        if fn is not None:
            bodies[fn].append(l.strip())
    bad = []
    for r, n in zeros.items():
        if r not in bodies:
            bad.append(f"{r}: not found")
            continue
        k = len([l for l in bodies[r] if zero.match(l)])
        if k != n:
            bad.append(f"{r}: {k} zero stores, {n} wanted")
    if bad:
        print("\n".join(bad))
        raise SystemExit(f"check_fieldfirst: {len(bad)} routines zero what they should not, or not what they should, in {args[0]}")
    print(f"check_fieldfirst: {len(zeros)} routines zero only what a path may read first, in {args[0]}")


if __name__ == "__main__":
    main()
