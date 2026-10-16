#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""An if whose arm only assigns a word is a conditional select (P307):
in the assembly paslangc wrote for the program, the code of every if
the source marks { select } is a select (CMOVcc on amd64; CSEL, CSINC
or CINC on arm64) and no conditional jump, and the code of every if it
marks { branch } a conditional jump and no select. The code of a line
is what follows its .loc in the routines of the program (p_ labels)
until the next .loc, or the next label once a select or a jump was
seen (the end of a loop that follows its last statement); every marked
line must be found.
"""

import re
import sys

SEL = re.compile(r"^  (cmov[a-z]+|csel|csinc|cinc|csinv|csneg|cset|csetm) ")
JCC = re.compile(r"^  (j(?!mp)[a-z]+|b\.[a-z]+|cbn?z|tbn?z) ")


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: check_select.py file.s source.paslang")
    path, src = sys.argv[1], sys.argv[2]
    want = {}
    for n, line in enumerate(open(src), 1):
        if "{ select }" in line:
            want[n] = "select"
        elif "{ branch }" in line:
            want[n] = "branch"
    sel, jcc, seen = {}, {}, set()
    cur = None
    inprog = False
    for line in open(path):
        line = line.rstrip("\n")
        if re.match(r"^p_[A-Za-z0-9_]+:$", line):
            inprog = True
            cur = None
            continue
        if re.match(r"^(rt_[A-Za-z0-9_]+|pas_main):$", line):
            inprog = False
            continue
        if not inprog:
            continue
        m = re.match(r"^  \.loc (\d+) (\d+)", line)
        if m:
            cur = int(m.group(2)) if m.group(1) == "1" else None
            if cur in want:
                seen.add(cur)
            continue
        if re.match(r"^\.L(?!L)[0-9A-Za-z_]*:$", line):
            if cur is not None and (sel.get(cur, 0) or jcc.get(cur, 0)):
                cur = None
            continue
        if cur is None:
            continue
        if SEL.match(line):
            sel[cur] = sel.get(cur, 0) + 1
        elif JCC.match(line):
            jcc[cur] = jcc.get(cur, 0) + 1
    bad = []
    for n, kind in sorted(want.items()):
        if n not in seen:
            bad.append(f"line {n}: no code")
        elif kind == "select" and (sel.get(n, 0) == 0 or jcc.get(n, 0) > 0):
            bad.append(f"line {n}: {sel.get(n, 0)} selects and {jcc.get(n, 0)} jumps, not a select")
        elif kind == "branch" and (sel.get(n, 0) > 0 or jcc.get(n, 0) == 0):
            bad.append(f"line {n}: {sel.get(n, 0)} selects and {jcc.get(n, 0)} jumps, not a branch")
    if bad:
        raise SystemExit(f"{path}: " + "; ".join(bad))
    nsel = sum(1 for k in want.values() if k == "select")
    print(f"check_select: {nsel} ifs are selects and {len(want) - nsel} branch in {path}")


main()
