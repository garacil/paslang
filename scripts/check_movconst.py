#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A constant from 0 to 2^32 - 1 goes into its register by a movl of 32
bits, and 0 by an xorl where nothing reads the flags (P321). In the
amd64 assembly paslangc wrote, the runtime included, no movq or movabsq
of such a constant into a register is left; in the compiled routines
every xorl of a register with itself, a zero, has before any
instruction that reads the flags one that writes them all; and every
movl $0 left into a register stands where the flags may be read, or
before a label, a jump, a call or a return.
"""

import re
import sys

READS = re.compile(r"^  (j(?!mp)\w+|set\w+|cmov\w+|adc\w*|sbb\w*|rcl\w*|rcr\w*|pushf\w*|lahf)\b")
WRITES = re.compile(r"^  (cmp[bwlq]|test[bwlq]|add[lq]|sub[lq]|and[lq]|or[lq]|xor[lq]|neg[lq]|u?comis[sd]) ")
PASS = re.compile(r"^  (mov[bwlq]|movabsq|movz[bw][lq]|movs[bw][lq]|movslq|lea[lq]|push[q]|pop[q]|"
                  r"movsd|movss|movd|movaps|movups|movdqa|movdqu) ")


def flags_dead_after(lines, i):
    """True when an instruction that writes every flag comes after line i
    before one that reads them, a label, a jump or anything unknown."""
    for x in lines[i + 1:i + 40]:
        if x.startswith("  .") or re.match(r"^\.LL\d+:$", x) or not x.strip():
            continue
        if READS.match(x):
            return False
        if WRITES.match(x):
            return True
        if PASS.match(x):
            continue
        return False
    return False


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_movconst.py file.s")
    lines = open(sys.argv[1]).read().splitlines()
    wide, badzero, missed, zeros = [], [], [], 0
    compiled = False
    for n, l in enumerate(lines):
        r = re.match(r"^(p_[A-Za-z0-9_]+|rt_[A-Za-z0-9_]+|pas_main):$", l)
        if r:
            compiled = not r.group(1).startswith("rt_")
        m = re.match(r"^  (movq|movabsq) \$(\d+), %r\w+$", l)
        if m and int(m.group(2)) <= 0xFFFFFFFF:
            wide.append(f"{n + 1}: {l.strip()}")
        if re.match(r"^  xorl (%e\w\w|%r\d+d), \1$", l):
            zeros += 1
            # in a compiled routine an xorl of a register by itself is a
            # zero the flags die after; the runtime's hand-written ones
            # zero before a call or a return, its own reading of them
            if compiled and not flags_dead_after(lines, n):
                badzero.append(f"{n + 1}: {l.strip()}")
        if re.match(r"^  movl \$0, (%e\w\w|%r\d+d)$", l) and flags_dead_after(lines, n):
            missed.append(f"{n + 1}: {l.strip()}")
    if wide or badzero or missed or zeros == 0:
        print("\n".join((wide + badzero + missed)[:20]))
        raise SystemExit(f"check_movconst: {len(wide)} 64-bit moves of a 32-bit constant, "
                         f"{len(badzero)} xorl zeros the flags may be read after, {len(missed)} "
                         f"movl zeros that could be xorl, {zeros} xorl zeros in {sys.argv[1]}")
    print(f"check_movconst: no 64-bit move of a 32-bit constant, {zeros} zeros by xorl in {sys.argv[1]}")


if __name__ == "__main__":
    main()
