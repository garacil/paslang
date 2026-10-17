#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""An and with 0xFF, 0xFFFF or 0xFFFFFFFF is a zero extension from its
source (P320). In the assembly paslangc wrote, the routines whose names
start with reg or home hold no AND of those masks: on amd64 no and of
$255 or $65535 and no movabsq of 4294967295 into the AND after it (the
third mask's way), on arm64 (--arm) no and of #0xff, #0xffff or
#0xffffffff, which it writes padded to 16 digits; and
they hold at least one zero extension each (movzbl, movzwl or movl of
32 bits; uxtb, uxth, ldrb, ldrh or a mov of W registers).
"""

import re
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arm = "--arm" in sys.argv[1:]
    if len(args) != 1:
        raise SystemExit("usage: check_andmask.py file.s [--arm]")
    lines = open(args[0]).read().splitlines()
    fn, bad, ext = "", [], {}
    for n, line in enumerate(lines):
        m = re.match(r"^(p_[A-Za-z0-9_]+|rt_[A-Za-z0-9_]+|pas_main):$", line)
        if m:
            name = m.group(1)
            fn = name if name.startswith("p_reg") or name.startswith("p_home") else ""
            if fn:
                ext.setdefault(fn, 0)
            continue
        if not fn:
            continue
        ins = line.strip()
        if arm:
            if re.match(r"^and x\d+, x\d+, #0x0*(ff|ffff|ffffffff)$", ins):
                bad.append(f"{n + 1}: {fn}: {ins}")
            if re.match(r"^(uxtb|uxth|ldrb|ldrh) |^mov w\d+, w\d+$", ins):
                ext[fn] += 1
        else:
            mv = re.match(r"^movabsq \$4294967295, (%\w+)$", ins)
            nxt = lines[n + 1].strip() if n + 1 < len(lines) else ""
            if re.match(r"^and[ql] \$(255|65535|0xff|0xffff), ", ins) or \
                    (mv and nxt.startswith("andq " + mv.group(1) + ", ")):
                bad.append(f"{n + 1}: {fn}: {ins}")
            if re.match(r"^(movzbl|movzwl|movzbq|movzwq) |^movl %\w+, %\w+$", ins):
                ext[fn] += 1
    if len(ext) < 14:
        raise SystemExit(f"check_andmask: only {len(ext)} reg and home routines in {args[0]}")
    none = [f for f, c in ext.items() if c == 0]
    if bad or none:
        print("\n".join(bad[:20]))
        raise SystemExit(f"check_andmask: {len(bad)} ANDs of a mask, {len(none)} routines with no "
                         f"zero extension ({', '.join(none[:5])}) in {args[0]}")
    print(f"check_andmask: {len(ext)} routines extend with no AND of a mask in {args[0]}")


if __name__ == "__main__":
    main()
