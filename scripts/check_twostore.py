#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A value goes to its place without the stack (P330), read in the
assembly paslangc wrote for testdata/twostore.paslang, amd64 or with
--arm arm64: FillFns stores routine values and strings into elements
with nothing pushed for them (amd64: the words from r11 and r10, into
the element's own operand since P329; arm64: one stp of x8 and x27, its
offset the field's or the frame's), and FillRecs stores interfaces,
routine values, strings and method values so too (amd64 its slices from
r11, r10 and r9; arm64 keeps a slice's three words on the stack).
"""

import re
import sys


def body(lines, name):
    out, on = [], False
    for l in lines:
        if l == name + ":":
            on = True
            continue
        if on and re.match(r"^\.set \.Lfr", l):
            break
        if on and not re.match(r"^\s*\.(loc|cfi)", l) and not l.startswith(".LL"):
            out.append(l)
    return out


def next8(a, b):
    """movq %r11, X then movq %r10, X + 8: a displacement, a label plus
    one or none before X's registers (P329)"""
    m = re.match(r"^  movq %r11, (.*?)(\((?:%|,%).*)$", a)
    n = re.match(r"^  movq %r10, (.*?)(\((?:%|,%).*)$", b)
    if not m or not n or m.group(2) != n.group(2):
        return False
    da, db = m.group(1), n.group(1)
    if re.match(r"^-?\d*$", da) and re.match(r"^-?\d+$", db):
        return int(db) == int(da or "0") + 8
    return db == da + "+8"


def main():
    arm = "--arm" in sys.argv[1:]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        raise SystemExit("usage: check_twostore.py file.s [--arm]")
    lines = open(args[0]).read().splitlines()
    bad = []
    for name, want in (("p_fillfns", 2), ("p_fillrecs", 7)):
        b = body(lines, name)
        if arm:
            kept = sum(1 for l in b if re.match(r"^  stp x8, x27, \[(x\d+|sp)(, #-?\d+)?\]$", l))
        else:
            kept = sum(1 for i, l in enumerate(b) if i + 1 < len(b) and
                       next8(l, b[i + 1]))
        if kept < want:
            bad.append(f"{name}: {kept} two-word stores from registers, {want} at least")
        # a push of rdx then rax right before an address, the old store
        for i in range(len(b) - 1):
            if not arm and b[i] == "  pushq %rdx" and b[i + 1] == "  pushq %rax":
                nxt = b[i + 2] if i + 2 < len(b) else ""
                if not re.match(r"^  (call|movq .*, %rdi)", nxt):
                    bad.append(f"{name}: a value's words pushed before its place: {nxt.strip()}")
            if arm and b[i] == "  str x2, [sp, #-16]!" and b[i + 1] == "  str x0, [sp, #-16]!" and \
                    (i == 0 or b[i - 1] != "  str x3, [sp, #-16]!") and \
                    not any(l.startswith("  bl ") for l in b[i + 2:i + 5]):
                bad.append(f"{name}: a value's two words pushed before its place")
    if bad:
        print("\n".join(bad[:10]))
        raise SystemExit(f"check_twostore: {len(bad)} forms missing in {args[0]}")
    print(f"check_twostore: values go to their places from registers in {args[0]}")


if __name__ == "__main__":
    main()
