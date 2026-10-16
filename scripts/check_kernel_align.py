#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""Every loop of an asm kernel starts aligned (P302): in the units given,
each label an asm block branches back to (a number N named as Nb) has a
.p2align line right before it, as paslangc starts the loops it compiles,
so a change of the code before a kernel does not move its loop.
"""

import re
import sys


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: check_kernel_align.py unit.paslang...")
    bad, loops = [], 0
    for path in sys.argv[1:]:
        lines = open(path).read().split("\n")
        i = 0
        while i < len(lines):
            m = re.match(r"^(\s*)asm (amd64|arm64)\b", lines[i])
            if not m:
                i += 1
                continue
            j = i + 1
            while j < len(lines) and not re.match(r"^" + m.group(1) + r"end\b", lines[j]):
                j += 1
            block = lines[i:j]
            back = set(re.findall(r"\b(\d+)b\b", "\n".join(block)))
            for k in range(1, len(block)):
                lm = re.match(r"^\s*(\d+):\s*$", block[k])
                if lm and lm.group(1) in back:
                    loops += 1
                    if not block[k - 1].strip().startswith(".p2align"):
                        bad.append(f"{path}:{i + k + 1}")
            i = j
    if bad:
        raise SystemExit("a kernel's loop starts unaligned at " + ", ".join(bad))
    print(f"check_kernel_align: {loops} kernel loops start aligned")


main()
