#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A lea of three components is split where the processor makes it slow
(P298). In the assembly paslangc wrote, a lea of a base, an index and a
displacement, or of a base of rbp or r13 beside an index (whose
encoding has a displacement byte), is counted over the whole file, the
runtime included: with slow there must be none (-tune names Haswell to
Cascade Lake), with whole at least the count given (the processor keeps
it whole, the runtime's own among them). In either mode no address has
a base of r13 or rbp, an unscaled index and no displacement, which the
index as base writes a byte shorter (SDM vol. 2A table 2-3, note 1).
"""

import re
import sys

LEA = re.compile(r"^  lea[lqw] ([^(]*)\((%[a-z0-9]+),(%[a-z0-9]+)(?:,([1248]))?\), (%[a-z0-9]+)$")
SLOWB = ("%rbp", "%ebp", "%r13", "%r13d")
WASTE = re.compile(r"(?<![0-9A-Za-z_.])(?:0)?\((%rbp|%r13),%[a-z0-9]+(?:,1)?\)")


def main():
    if len(sys.argv) < 3 or sys.argv[2] not in ("slow", "whole"):
        raise SystemExit("usage: check_lea.py file.s slow|whole [count]")
    path, mode = sys.argv[1], sys.argv[2]
    want = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    three, waste = [], []
    for n, line in enumerate(open(path), 1):
        line = line.rstrip("\n")
        if not line.startswith("  ") or line.startswith("  ."):
            continue
        m = LEA.match(line)
        if m and ((m.group(1) not in ("", "0")) or m.group(2) in SLOWB):
            three.append(f"{n}: {line.strip()}")
        if WASTE.search(line):
            waste.append(f"{n}: {line.strip()}")
    if waste:
        raise SystemExit(f"{path}: a base of r13 or rbp beside an unscaled index with no displacement: " +
                         "; ".join(waste[:10]))
    if mode == "slow" and three:
        raise SystemExit(f"{path}: {len(three)} leas of three components where they are slow: " +
                         "; ".join(three[:10]))
    if mode == "whole" and len(three) < want:
        raise SystemExit(f"{path}: {len(three)} leas of three components kept whole, fewer than {want}")
    print(f"check_lea: {len(three)} leas of three components in {path} ({mode})")


main()
