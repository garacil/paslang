#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""An arm64 constant goes into its register as Go puts it there, with
no literal load (P315). In the arm64 assembly paslangc wrote, the
runtime included, no ldr of a literal (ldr xN, =...) is left; and with
--source, in each routine K<n> of armconst the first load of its
constant takes as many instructions as Go's assembler would
(cmd/internal/obj/arm64/asm7.go con64class and omovlconst: one MOV of a
halfword, of an inverted one or of a bitmask, two when two halfwords
are 0 or 0xffff or a bitmask and a MOVK make it, three when one is,
four otherwise).
"""

import re
import sys

M64 = (1 << 64) - 1


def bitcon(v):
    v &= M64
    if v in (0, M64):
        return False
    size = 64
    while size > 2:
        half = size // 2
        mask = (1 << half) - 1
        if (v & mask) != ((v >> half) & mask):
            break
        size = half
    mask = (1 << size) - 1
    e = v & mask
    for i in range(size):
        x = ((e >> i) | (e << (size - i))) & mask
        if x not in (0, mask) and (x & (x + 1)) == 0:
            return True
    return False


def go_count(v):
    v &= M64
    if v < 65536 or v >= M64 - 65535:
        return 1
    h = [(v >> (16 * i)) & 0xFFFF for i in range(4)]
    zc, nc = h.count(0), h.count(0xFFFF)
    if zc >= 3 or nc >= 3 or bitcon(v):
        return 1
    if zc == 2 or nc == 2:
        return 2
    for i in range(4):
        mask = 0xFFFF << (16 * i)
        for r in (16, 32):
            rv = ((v << r) | (v >> (64 - r))) & M64
            if bitcon((v & ~mask & M64) | (rv & mask)):
                return 2
    if zc == 1 or nc == 1:
        return 3
    return 4


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--source=")), None)
    if len(args) != 1:
        raise SystemExit("usage: check_armconst.py file.s [--source=armconst.paslang]")
    lines = open(args[0]).read().splitlines()
    bad = [f"{n}: {l.strip()}" for n, l in enumerate(lines, 1) if re.match(r"^\s+ldr [wx]\d+, =", l)]
    want = {}
    if src:
        for m in re.finditer(r"function K(\d+)\(x: Integer\): Integer;\nvar\n  v: Integer;\nbegin\n  v := (-?\d+);", open(src).read()):
            want[int(m.group(1))] = int(m.group(2))
    seen = 0
    fn = None
    for n, l in enumerate(lines, 1):
        m = re.match(r"^p_k(\d+):$", l)
        if m:
            fn = int(m.group(1))
            continue
        if fn is None or fn not in want:
            continue
        k = re.match(r"^  (mov|movz|movn|orr) (x\d+), (xzr, )?#", l)
        if k and not l.startswith("  mov x29"):
            reg, cnt, j = k.group(2), 1, n
            while j < len(lines) and re.match(r"^  movk " + reg + ", ", lines[j]):
                cnt, j = cnt + 1, j + 1
            if cnt != go_count(want[fn]):
                bad.append(f"{n}: p_k{fn}: {want[fn]} takes {cnt} instructions where Go's take {go_count(want[fn])}")
            seen += 1
            fn = None
    if src and seen < len(want):
        bad.append(f"only {seen} of the {len(want)} constants found loaded")
    if bad:
        print("\n".join(bad[:40]))
        raise SystemExit(f"check_armconst: {len(bad)} constants not loaded as Go loads them in {args[0]}")
    print(f"check_armconst: no literal load, {seen} constants as Go loads them in {args[0]}")


if __name__ == "__main__":
    main()
