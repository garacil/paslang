#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""The failures of a program's checks are out of line (P299): in the
assembly paslangc wrote, no call of rt_boundsfail or rt_divzero in a
routine paslangc compiled (p_... or pas_main) comes before that
routine's first ret, so the path where a check holds takes no branch,
and at least the given number come after one. A third argument names
other routines of the runtime, joined by commas, whose calls must sit
there too: the other failures and the slow paths that come back
(P300). Reads amd64's call and arm64's bl alike.
"""

import re
import sys


def main():
    if len(sys.argv) not in (3, 4):
        raise SystemExit("usage: check_cold.py file.s least [names]")
    path, least = sys.argv[1], int(sys.argv[2])
    names = "boundsfail|divzero"
    if len(sys.argv) == 4:
        names = "|".join(n for n in sys.argv[3].split(",") if n)
    fn, after, bad = "", False, []
    count = 0
    for line in open(path):
        line = line.rstrip("\n")
        if re.match(r"^(p_[A-Za-z0-9_]+|pas_main):$", line):
            fn, after = line[:-1], False
        elif re.match(r"^rt_[A-Za-z0-9_]+:$", line) or line.startswith(".section"):
            fn = ""
        elif fn and line == "  ret":
            after = True
        elif fn and re.match(r"^  (call|bl) rt_(" + names + r")$", line):
            if after:
                count += 1
            else:
                bad.append(fn)
    if bad:
        raise SystemExit(f"{path}: a check's failure before the ret of {', '.join(sorted(set(bad)))}")
    if count < least:
        raise SystemExit(f"{path}: {count} failures after a ret, fewer than {least}")
    print(f"check_cold: {count} failures after their routine's ret")


main()
