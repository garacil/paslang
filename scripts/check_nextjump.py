#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""No jump goes to the next instruction (P305): in the assembly paslangc
wrote, no jmp (amd64) or b (arm64) to a label is followed, before any
other instruction, by that label, with only labels, .loc and .cfi lines
between. An if without an else wrote one at the end of every then, the
last arm of a case without an else one at its end, and an Exit that
ended a routine one to its epilogue. Reads every file named.
"""

import re
import sys


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: check_nextjump.py file.s...")
    bad = []
    jumps = 0
    for path in sys.argv[1:]:
        lines = [l.rstrip("\n") for l in open(path)]
        for i, line in enumerate(lines):
            m = re.match(r"^  (jmp|b) (\.L[0-9A-Za-z_]+)$", line)
            if not m:
                continue
            jumps += 1
            target = m.group(2)
            for x in lines[i + 1:]:
                if re.match(r"^\.L[0-9A-Za-z_]+:$", x):
                    if x[:-1] == target:
                        bad.append(f"{path}:{i + 1}: {line.strip()}")
                        break
                    continue
                if x.startswith("  .loc ") or x.startswith("  .cfi_") or x == "":
                    continue
                break
    if bad:
        raise SystemExit("a jump to the next instruction: " + "; ".join(bad[:20]) +
                         (f"; and {len(bad) - 20} more" if len(bad) > 20 else ""))
    print(f"check_nextjump: {jumps} jumps in {len(sys.argv) - 1} files, none to the next instruction")


main()
