#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A routine that calls nothing keeps its locals, parameters and Result
in registers, with no frame (P296). In the assembly paslangc wrote,
every routine whose name starts with flat has no frame (amd64 no
pushq %rbp and no word at %rbp; arm64 no stp x29, x30 and no x29) and no
stack check, Clamp3 at most --clamp=N instructions; Many, with more
variables than registers, keeps its frame. --arm reads arm64's.
"""

import re
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arm = "--arm" in sys.argv[1:]
    clamp = 99
    for a in sys.argv[1:]:
        if a.startswith("--clamp="):
            clamp = int(a[8:])
    if len(args) != 1:
        raise SystemExit("usage: check_flatproc.py file.s [--arm] [--clamp=N]")
    lines = open(args[0]).read().splitlines()
    bodies, fn = {}, ""
    for l in lines:
        m = re.match(r"^(p_[A-Za-z0-9_]+|rt_[A-Za-z0-9_]+|pas_main):$", l)
        if m:
            fn = m.group(1)
            bodies[fn] = []
            continue
        if fn:
            bodies[fn].append(l)
    frame = re.compile(r"stp x29, x30|\bx29\b|x28, #16" if arm else r"pushq %rbp|\(%rbp\)|cmpq 16\(%r14\)")
    flat = [f for f in bodies if re.match(r"^p_(tbox_)?flat", f)]
    bad = []
    for f in flat:
        body = [l for l in bodies[f] if not l.startswith("  .") and not re.match(r"^\.L", l)]
        if any(frame.search(l) for l in body):
            bad.append(f"{f} has a frame or a stack check")
    c = [l for l in bodies.get("p_flatclamp3", []) if l.startswith("  ") and not l.startswith("  .")]
    if len(c) > clamp:
        bad.append(f"flatclamp3 is {len(c)} instructions where {clamp} at most")
    if not any(frame.search(l) for l in bodies.get("p_many", [])):
        bad.append("many has no frame, though its variables outnumber the registers")
    if len(flat) < 8:
        bad.append(f"only {len(flat)} flat routines")
    if bad:
        raise SystemExit("check_flatproc: " + "; ".join(bad) + f" in {args[0]}")
    print(f"check_flatproc: {len(flat)} routines with no frame, Clamp3 {len(c)} instructions in {args[0]}")


if __name__ == "__main__":
    main()
