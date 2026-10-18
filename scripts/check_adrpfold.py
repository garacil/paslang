#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""An arm64 global is loaded and stored by adrp and its low twelve bits
(P331), read in the arm64 assembly paslangc wrote: in the compiled
routines and the main block no adrp x16, v_X and add x16, x16,
:lo12:v_X are followed by a load or a store through [x16] that the next
write of x16, a call or a return makes the last reader of x16, on a
path with no branch or label a jump reaches (a line label is none:
P346); and at least --folds=N accesses take :lo12:v_X themselves, each
right after the adrp of its own word (v_X+8 may lie on the next page).
A routine with an asm block keeps its code as written (HasAsm): the
files read have none.
"""

import re
import sys


def dead(lines, q):
    """x16 is not read again on the path from line q: a write of it alone,
    a call or a return before any read, as AdrpPass reads it; a branch or
    a label a jump reaches ends the path (no answer), a line label and a
    directive do not (P346)"""
    while q < len(lines):
        t = lines[q]
        if t == "" or t.startswith("  .") or re.match(r"^\.LL\d+:$", t):
            q += 1
            continue
        if not t.startswith(" ") or re.match(r"^  (b |b\.|cbz|cbnz|tbz|tbnz|br )", t):
            return False
        if re.match(r"^  (bl |blr |ret)", t):
            return "x16" not in t
        if "x16" in t:
            return bool(re.match(r"^  (adrp|mov|movz|ldr) x16, ", t)) and "x16" not in t[11:]
        q += 1
    return False


def main():
    want = 1
    for a in sys.argv[1:]:
        if a.startswith("--folds="):
            want = int(a[8:])
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        raise SystemExit("usage: check_adrpfold.py file.s [--folds=N]")
    lines = [l for l in open(args[0]).read().splitlines() if not re.match(r"^\s*\.(loc|cfi)", l)]
    compiled, bad, folds = False, [], 0
    acc = re.compile(r"^  (ldr|str|ldrb|strb|ldrh|strh|ldrsb|ldrsh|ldrsw) ([xw])(\d+), \[x16(?:, #(\d+))?\]$")
    for i, l in enumerate(lines):
        m = re.match(r"^(p_[A-Za-z0-9_.]+|rt_[A-Za-z0-9_]+|pas_main):$", l)
        if m:
            compiled = not m.group(1).startswith("rt_")
            continue
        if not compiled:
            continue
        f = re.search(r"\[x16, :lo12:(v_[\w.]+)(\+\d+)?\]$", l)
        if f:
            folds += 1
            # the page of the word itself: adrp of the same symbol and offset
            if i == 0 or lines[i - 1] != "  adrp x16, " + f.group(1) + (f.group(2) or ""):
                bad.append(f"{i + 1}: {l.strip()} not after adrp x16, {f.group(1)}{f.group(2) or ''}")
        a = re.match(r"^  adrp x16, (v_[\w.]+)$", l)
        if not a or i + 3 >= len(lines):
            continue
        c = acc.match(lines[i + 2])
        if lines[i + 1] != "  add x16, x16, :lo12:" + a.group(1) or not c or c.group(3) == "16":
            continue
        op, w, off = c.group(1), c.group(2), int(c.group(4) or 0)
        size = {"ldrb": 1, "strb": 1, "ldrsb": 1, "ldrh": 2, "strh": 2, "ldrsh": 2,
                "ldrsw": 4}.get(op, 8 if w == "x" else 4)
        if off >= 4096 or off % size:
            continue
        if dead(lines, i + 3):
            bad.append(f"{i + 1}: {a.group(1)} {lines[i + 2].strip()} left with its add")
    if bad or folds < want:
        print("\n".join(bad[:10]))
        raise SystemExit(f"check_adrpfold: {len(bad)} accesses left with their add, {folds} folded "
                         f"({want} at least) in {args[0]}")
    print(f"check_adrpfold: {folds} accesses take the low twelve bits, none left with an add, in {args[0]}")


if __name__ == "__main__":
    main()
