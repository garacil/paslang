#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A product inside a conversion reads its variable where the register
keeps it (P317). In the assembly paslangc wrote, the routines whose
names start with conv move no register into another that the next
instruction then multiplies in place: on amd64 a lea of it by itself, a
shift, an add of it to itself, a neg or an imul of it, unless the step
after reads the source again (x * -7 is a move, a neg and a lea of x
and the neg, as Go writes it); on arm64 (--arm) an add, sub, neg, shift
or mul that writes it and reads it. The recipe reads the variable's
register itself.
"""

import re
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arm = "--arm" in sys.argv[1:]
    if len(args) != 1:
        raise SystemExit("usage: check_convmul.py file.s [--arm]")
    lines = open(args[0]).read().splitlines()
    fn, bad, seen = "", [], set()
    for n, line in enumerate(lines):
        m = re.match(r"^(p_[A-Za-z0-9_]+|rt_[A-Za-z0-9_]+|pas_main):$", line)
        if m:
            fn = m.group(1) if m.group(1).startswith("p_conv") else ""
            if fn:
                seen.add(fn)
            continue
        if not fn or n + 1 >= len(lines):
            continue
        nxt = lines[n + 1].strip()
        if arm:
            mv = re.match(r"^  mov (x\d+), (x\d+)$", line)
            if not mv:
                continue
            d = mv.group(1)
            m2 = re.match(r"^(add|sub|neg|lsl|mul|madd|msub|mneg) " + d + r", (.*)$", nxt)
            if m2 and re.search(r"\b" + d + r"\b", m2.group(2)):
                bad.append(f"{n + 1}: {fn}: {line.strip()} then {nxt}")
            continue
        mv = re.match(r"^  movq (%r\w+), (%r\w+)$", line)
        if mv:
            src, d = mv.group(1), mv.group(2)
            after = lines[n + 2].strip() if n + 2 < len(lines) else ""
            # a move that keeps the source for the recipe's next step (x * -7,
            # x + 8 * -x, a neg in place of a copy) is the recipe's, as Go's
            if re.match(r"^(leaq \(" + d + "," + d + r"(,\d)?\), " + d + "|shlq \\$\\d+, " + d +
                        "|addq " + d + ", " + d + "|negq " + d + r"|imulq \$-?\d+, " + d + ")$", nxt) and \
                    not re.search(re.escape(src) + r"\b", after):
                bad.append(f"{n + 1}: {fn}: {line.strip()} then {nxt}")
    if len(seen) < 6:
        raise SystemExit(f"check_convmul: only {len(seen)} conv routines in {args[0]}")
    if bad:
        print("\n".join(bad[:20]))
        raise SystemExit(f"check_convmul: {len(bad)} variables moved before their recipe in {args[0]}")
    print(f"check_convmul: {len(seen)} routines read their variables in place in {args[0]}")


if __name__ == "__main__":
    main()
