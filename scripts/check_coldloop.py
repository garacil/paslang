#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A loop whose only calls sit on slow paths keeps its variables in
registers (P301): in the assembly paslangc wrote, the loop of each
routine named, from the first aligned head after the routine's label to
the first branch back to a label inside it, holds no call and writes
no word of its frame. A variable kept in the frame is written there at
every pass; the length s := s + c stores (movq %rdx on amd64, through
x0 on arm64) is a string's word, not a variable's. A call of the
runtime keeps or reloads the registers after the routine's ret. On
arm64 FillChar's own call, rt_fill, keeps every register a region
holds (it uses x0, x1, x3 and v31) and stays. Reads amd64's and
arm64's assembly alike.
"""

import re
import sys


def loop_of(lines, name):
    start = None
    for i, line in enumerate(lines):
        if line == f"p_{name}:":
            start = i
            break
    if start is None:
        raise SystemExit(f"no routine p_{name}")
    head = None
    for i in range(start + 1, len(lines)):
        if lines[i] == "  ret" or re.match(r"^p_[A-Za-z0-9_]+:$", lines[i]):
            break
        if lines[i] == "  .p2align 5":
            head = i
            break
    if head is None:
        raise SystemExit(f"p_{name}: no aligned loop head")
    labels = set()
    for i in range(head + 1, len(lines)):
        line = lines[i]
        m = re.match(r"^(\.L[0-9A-Za-z_]+):$", line)
        if m:
            labels.add(m.group(1))
            continue
        m = re.match(r"^  (j[a-z]+|b\.[a-z]+|cbn?z|tbn?z|b) (?:[a-z0-9]+, )*(?:#[0-9]+, )?(\.L[0-9A-Za-z_]+)$", line)
        if m and m.group(2) in labels and m.group(1) not in ("jmp", "b"):
            return lines[head:i + 1]
        if line == "  ret":
            break
    raise SystemExit(f"p_{name}: no branch back to its loop head")


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: check_coldloop.py file.s name,name,...")
    path = sys.argv[1]
    lines = [l.rstrip("\n") for l in open(path)]
    bad = []
    for name in (n for n in sys.argv[2].split(",") if n):
        for line in loop_of(lines, name):
            if re.match(r"^  (call|bl) ", line) and line != "  bl rt_fill":
                bad.append(f"p_{name} calls in its loop: {line.strip()}")
            elif (line.endswith("(%rbp)") and not re.match(r"^  (cmp|test)", line) and
                  not re.match(r"^  movq %rdx, -[0-9]+\(%rbp\)$", line)):
                bad.append(f"p_{name} writes its frame in its loop: {line.strip()}")
            elif re.match(r"^  (str|stp|stur)[a-z]* .*\[x29", line):
                bad.append(f"p_{name} writes its frame in its loop: {line.strip()}")
    if bad:
        raise SystemExit(f"{path}: " + "; ".join(bad))
    print(f"check_coldloop: {len(sys.argv[2].split(','))} loops in registers")


main()
