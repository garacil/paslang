#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A field of an element is read and written through one address (P311):
in the routines named of the assembly paslangc wrote, no lea forms an
address that the next instruction reads or writes at an offset from it
(amd64: leaq X, %r then N(%r)), and on arm64 (--arm) no add of an
immediate makes the address the next load or store takes with none
(add xa, xa, #k then [xa]): the offset is the access's own.
"""

import re
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arm = "--arm" in sys.argv
    if len(args) != 2:
        raise SystemExit("usage: check_fieldaddr.py file.s name,name,... [--arm]")
    path, names = args[0], set(n for n in args[1].split(",") if n)
    fn, prev = "", ""
    bad, seen = [], set()
    for n, line in enumerate(open(path), 1):
        line = line.rstrip("\n")
        m = re.match(r"^(p_[A-Za-z0-9_]+|rt_[A-Za-z0-9_]+|pas_main):$", line)
        if m:
            fn = m.group(1)
            if fn[2:] in names:
                seen.add(fn[2:])
            prev = ""
            continue
        if not line.startswith("  ") or line.startswith("  ."):
            if re.match(r"^\.L[0-9A-Za-z_]*:$", line) and not line.startswith(".LL"):
                prev = ""
            continue
        if fn.startswith("p_") and fn[2:] in names and prev:
            if arm:
                p = re.match(r"^  add (x\d+), \1, #\d+$", prev)
                if p and re.search(r"\[" + p.group(1) + r"\]", line) and re.match(r"^  (ldr|str|ldrb|strb|ldrh|strh|ldrsw|ldrsb|ldrsh) ", line):
                    bad.append(f"{n}: {fn}: {prev.strip()} | {line.strip()}")
            else:
                p = re.match(r"^  leaq [^,]+(,[^,]+)*, (%r[a-z0-9]+)$", prev)
                if p and re.search(r"-?\d*\(" + re.escape(p.group(2)) + r"\)", line) and not line.startswith("  lea"):
                    bad.append(f"{n}: {fn}: {prev.strip()} | {line.strip()}")
        prev = line
    missing = names - seen
    if missing:
        raise SystemExit(f"{path}: routines not found: {', '.join(sorted(missing))}")
    if bad:
        raise SystemExit(f"{path}: an address formed before its field: " + "; ".join(bad[:10]))
    print(f"check_fieldaddr: {len(names)} routines take their fields' offsets in the access in {path}")


main()
