#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A closure or nested routine that calls nothing has no frame (P334),
read in the assembly of testdata/nestflat: each routine --flat names has
no frame and no stack check (amd64 no pushq %rbp, no word at %rbp and no
cmpq 16(%r14); arm64 with --arm no stp x29, x30, no x29 and no ldr of
x28's guard), reaches its outer variables through the link register it
came in (r10 or x27) and never stores that link; each --framed names
keeps its frame.

usage: check_nestflat.py file.s [--arm] --flat=p_a,p_b --framed=p_c
"""

import re
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arm = "--arm" in sys.argv[1:]
    flat, framed = [], []
    for a in sys.argv[1:]:
        if a.startswith("--flat="):
            flat = a.split("=", 1)[1].split(",")
        if a.startswith("--framed="):
            framed = a.split("=", 1)[1].split(",")
    if len(args) != 1 or not flat:
        raise SystemExit(__doc__)
    bodies, fn = {}, None
    for l in open(args[0]).read().splitlines():
        m = re.match(r"^([A-Za-z_][\w.]*):$", l)
        if m and not l.startswith(".L"):
            fn = m.group(1)
            bodies[fn] = []
            continue
        if fn is not None and l.startswith("  ") and not l.startswith("  ."):
            bodies[fn].append(l.strip())
    frame = re.compile(r"stp x29, x30|\bx29\b|\[x28, #16\]" if arm else r"pushq %rbp|\(%rbp\)|cmpq 16\(%r14\)")
    link = "x27" if arm else "%r10"
    keep = re.compile(r"^str x27, " if arm else r"^movq %r10, ")
    bad = []
    for f in flat:
        if f not in bodies:
            bad.append(f"{f}: not found")
            continue
        if any(frame.search(l) for l in bodies[f]):
            bad.append(f"{f} has a frame or a stack check")
        if not any(link in l for l in bodies[f]):
            bad.append(f"{f} reads nothing through {link}")
        if any(keep.match(l) for l in bodies[f]):
            bad.append(f"{f} stores its link")
    for f in framed:
        if f not in bodies:
            bad.append(f"{f}: not found")
        elif not any(frame.search(l) for l in bodies[f]):
            bad.append(f"{f} has no frame, though it calls")
    if bad:
        print("\n".join(bad))
        raise SystemExit(f"check_nestflat: {len(bad)} wrong forms in {args[0]}")
    print(f"check_nestflat: {len(flat)} routines with no frame, through {link}, in {args[0]}")


if __name__ == "__main__":
    main()
