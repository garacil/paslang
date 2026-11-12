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
    bad_count = 0
    jumps = 0
    jump = re.compile(r"^  (jmp|b) (\.L[0-9A-Za-z_]+)$")
    label = re.compile(r"^\.L[0-9A-Za-z_]+:$")
    for path in sys.argv[1:]:
        # A real instruction ends the previous jump's lookahead. Keep
        # only that jump while streaming labels and metadata, and at
        # most the first 20 diagnostics. No file or tail list is needed.
        target = None
        with open(path) as source:
            for line_no, line in enumerate(source, 1):
                line = line.rstrip("\n")
                if target is not None:
                    if label.match(line):
                        if line[:-1] == target:
                            bad_count += 1
                            if len(bad) < 20:
                                bad.append(f"{path}:{pending_no}: {pending_line.strip()}")
                            target = None
                        continue
                    if line.startswith("  .loc ") or line.startswith("  .cfi_") or line == "":
                        continue
                    target = None
                match = jump.match(line)
                if match:
                    jumps += 1
                    target = match.group(2)
                    pending_no = line_no
                    pending_line = line
    if bad:
        raise SystemExit("a jump to the next instruction: " + "; ".join(bad) +
                         (f"; and {bad_count - 20} more" if bad_count > 20 else ""))
    print(f"check_nextjump: {jumps} jumps in {len(sys.argv) - 1} files, none to the next instruction")


main()
