#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""An element's index is scaled by shifts and leas (P310): in the
assembly paslangc wrote, the routines named multiply nothing (no imulq
on amd64; with --arm, tuned for a core whose recipes cost less than a
MADD, no mul or madd on arm64), and no routine of the file, the runtime
included, multiplies by a power of two (imulq $2, $4, ... on amd64).
"""

import re
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arm = "--arm" in sys.argv
    if len(args) != 2:
        raise SystemExit("usage: check_scale.py file.s name,name,... [--arm]")
    path, names = args[0], set(n for n in args[1].split(",") if n)
    fn = ""
    bad, pow2 = [], []
    seen = set()
    mul = re.compile(r"^  (mul|madd) " if arm else r"^  imulq ")
    for n, line in enumerate(open(path), 1):
        line = line.rstrip("\n")
        m = re.match(r"^(p_[A-Za-z0-9_]+|rt_[A-Za-z0-9_]+|pas_main):$", line)
        if m:
            fn = m.group(1)
            if fn[2:] in names:
                seen.add(fn[2:])
            continue
        if not arm:
            k = re.match(r"^  imulq \$(\d+),", line)
            if k and int(k.group(1)) > 1 and (int(k.group(1)) & (int(k.group(1)) - 1)) == 0:
                pow2.append(f"{n}: {fn}: {line.strip()}")
        if fn.startswith("p_") and fn[2:] in names and mul.match(line):
            bad.append(f"{n}: {fn}: {line.strip()}")
    missing = names - seen
    if missing:
        raise SystemExit(f"{path}: routines not found: {', '.join(sorted(missing))}")
    if pow2:
        raise SystemExit(f"{path}: a multiply by a power of two: " + "; ".join(pow2[:10]))
    if bad:
        raise SystemExit(f"{path}: a scale multiplied: " + "; ".join(bad[:10]))
    print(f"check_scale: {len(names)} routines multiply nothing in {path}")


main()
