#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A bounds check that an earlier one of the same index and length
proves is left out (P316). In the assembly paslangc wrote, each routine
named with its most (name:count) branches to no more failures out of
line than that: a jump or branch to a label the routine defines after
its ret, where P299 puts the checks' failures, is a check.
"""

import re
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        raise SystemExit("usage: check_chkcse.py file.s name:count,...")
    want = {}
    for item in args[1].split(","):
        n, c = item.split(":")
        want[n] = int(c)
    lines = open(args[0]).read().splitlines()
    starts = [(i, m.group(1)) for i, l in enumerate(lines)
              for m in [re.match(r"^(p_[A-Za-z0-9_]+|rt_[A-Za-z0-9_]+|pas_main):$", l)] if m]
    got = {}
    for j, (i, name) in enumerate(starts):
        if not name.startswith("p_") or name[2:] not in want:
            continue
        end = starts[j + 1][0] if j + 1 < len(starts) else len(lines)
        body = lines[i:end]
        ret = next((k for k, l in enumerate(body) if l.strip() == "ret"), len(body))
        cold = {m.group(1) for l in body[ret:] for m in [re.match(r"^(\.L\d+):$", l)] if m}
        n = 0
        for l in body[:ret]:
            m = re.match(r"^  (?:j\w+|b\.\w+|cbn?z \w+,|tbn?z \w+, #\d+,) (\.L\d+)$", l)
            if m and m.group(1) in cold:
                n += 1
        got[name[2:]] = n
    missing = set(want) - set(got)
    if missing:
        raise SystemExit(f"check_chkcse: no routine {', '.join(sorted(missing))} in {args[0]}")
    bad = [f"{f}: {got[f]} checks where {c} at most" for f, c in want.items() if got[f] > c]
    if bad:
        raise SystemExit("check_chkcse: " + "; ".join(bad) + f" in {args[0]}")
    print("check_chkcse: " + ", ".join(f"{f} {got[f]}" for f in want) + f" in {args[0]}")


if __name__ == "__main__":
    main()
