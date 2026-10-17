#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A product by a constant no recipe takes reads its variable's register,
or its home, into IMUL's destination (P323). In the amd64 assembly
paslangc wrote, no compiled routine moves a register or a word of memory
into a register that the next instruction multiplies by a constant in
place (imulq $c, %r, %r); and at least --three=N imulq of three operands
are there, one of them from memory.
"""

import re
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    three = 1
    for a in sys.argv[1:]:
        if a.startswith("--three="):
            three = int(a[8:])
    if len(args) != 1:
        raise SystemExit("usage: check_imulconst.py file.s [--three=N]")
    lines = open(args[0]).read().splitlines()
    compiled, bad, n3, mem = False, [], 0, 0
    for i, l in enumerate(lines):
        m = re.match(r"^(p_[A-Za-z0-9_]+|rt_[A-Za-z0-9_]+|pas_main):$", l)
        if m:
            compiled = not m.group(1).startswith("rt_")
            continue
        if not compiled:
            continue
        t = re.match(r"^  imulq \$-?\d+, ([^,]+), %r\w+$", l)
        if t:
            n3 += 1
            if "(" in t.group(1):
                mem += 1
        mv = re.match(r"^  movq [^,]+, %(r\w+)$", l)
        if mv and i + 1 < len(lines):
            r = mv.group(1)
            if re.match(r"^  imulq \$-?\d+, %" + r + ", %" + r + "$", lines[i + 1]):
                bad.append(f"{i + 1}: {l.strip()} then {lines[i + 1].strip()}")
    if bad or n3 < three or mem == 0:
        print("\n".join(bad[:10]))
        raise SystemExit(f"check_imulconst: {len(bad)} moves before an imulq in place, {n3} of three "
                         f"operands ({three} at least), {mem} from memory in {args[0]}")
    print(f"check_imulconst: {n3} imulq of three operands, {mem} from memory, no move before one in {args[0]}")


if __name__ == "__main__":
    main()
