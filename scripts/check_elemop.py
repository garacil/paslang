#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A value of two words is loaded from and stored to its element's own
operand (P329), read in the assembly paslangc wrote for
testdata/elemop.paslang, amd64 or with --arm arm64.

amd64: the words go to and from the element's operand, v_fns+8(,%rax,8),
-80(%rbp,%rax,8), (%rcx,%rax,8) or v_gpair+8(%rip), never through a lea
into rax right before them, and a field's offset is in that operand, no
add after the lea. arm64: one ldp or stp a pair, its offset the frame's
or the field's where the add before it was, and no add or sub of x0
right before an ldp or stp from [x0] that could take it.
"""

import re
import sys

ROUTINES = ("p_sumfns", "p_local", "p_strs", "p_boxes", "p_slices", "p_fields")


def body(lines, name):
    out, on = [], False
    for l in lines:
        if l == name + ":":
            on = True
            continue
        if on and (re.match(r"^\.set \.Lfr", l) or re.match(r"^[A-Za-z_][\w.]*:$", l)):
            break
        if on and not re.match(r"^\s*\.(loc|cfi)", l) and not l.startswith(".LL"):
            out.append(l)
    return out


def plus8(a, b):
    """b is a's operand 8 bytes on: a displacement, a label's or none."""
    m = re.match(r"^(.*?)(\((?:%|,%).*)$", a)
    n = re.match(r"^(.*?)(\((?:%|,%).*)$", b)
    if not m or not n or m.group(2) != n.group(2):
        return False
    da, db = m.group(1), n.group(1)
    if re.match(r"^-?\d*$", da) and re.match(r"^-?\d+$", db):
        return int(db) == int(da or "0") + 8
    return db == da + "+8" or db == re.sub(r"\+(\d+)$", lambda x: "+%d" % (int(x.group(1)) + 8), da) \
        or (re.search(r"-(\d+)$", da) and db == re.sub(r"-(\d+)$", lambda x: "%+d" % (8 - int(x.group(1))), da))


def elem(op):
    """an element's operand or a global's, not a frame variable's home"""
    return ",%" in op or op.startswith("v_")


def amd64(b):
    """the pairs read or written from an operand other than rax's, and
    the old forms left"""
    pairs, old = 0, []
    for i in range(len(b) - 1):
        l, n = b[i], b[i + 1]
        ld = re.match(r"^  movq (\S+), %rdx$", l), re.match(r"^  movq (\S+), %rax$", n)
        st = re.match(r"^  movq %r11, (\S+)$", l), re.match(r"^  movq %r10, (\S+)$", n)
        if ld[0] and ld[1] and plus8(ld[1].group(1), ld[0].group(1)) and elem(ld[1].group(1)):
            pairs += 1
        if st[0] and st[1] and plus8(st[0].group(1), st[1].group(1)) and elem(st[0].group(1)):
            pairs += 1
        m = re.match(r"^  leaq (\S*\(\S*), %rax$", l)
        if m and re.match(r"^  movq (%r1[01], )?\d*\(%rax\)", n):
            old.append(f"a lea into rax before {n.strip()}")
        if m and re.match(r"^  addq \$\d+, %rax$", n):
            old.append(f"an add after {l.strip()}")
    return pairs, old


def arm64(b):
    pairs, old = 0, []
    for i, l in enumerate(b):
        if re.match(r"^  (ldp x0, x2|stp x8, x27), \[x([0-9]|1[0-9]|2[0-8]), #-?\d+\]$", l):
            pairs += 1
        if i > 0 and re.match(r"^  (ldp x0, x2|stp x8, x27), \[x0\]$", l) and \
                re.match(r"^  (add|sub) x0, (x\d+|sp), #\d+$", b[i - 1]):
            old.append(f"an add before {l.strip()}")
        if i > 0 and l == "  ldr x0, [x0]" and b[i - 1] == "  ldr x2, [x0, #8]":
            old.append("two ldr where one ldp")
    return pairs, old


def main():
    arm = "--arm" in sys.argv[1:]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    want = 0
    for a in sys.argv[1:]:
        if a.startswith("--pairs="):
            want = int(a.split("=", 1)[1])
    if len(args) != 1:
        raise SystemExit("usage: check_elemop.py file.s [--arm] [--pairs=N]")
    lines = open(args[0]).read().splitlines()
    bad, total = [], 0
    for name in ROUTINES:
        b = body(lines, name)
        if not b:
            bad.append(f"{name}: not in {args[0]}")
            continue
        n, old = arm64(b) if arm else amd64(b)
        total += n
        bad += [f"{name}: {o}" for o in old]
    if total < want:
        bad.append(f"{total} pairs from their own operands, {want} at least")
    if bad:
        print("\n".join(bad[:10]))
        raise SystemExit(f"check_elemop: {len(bad)} forms missing in {args[0]}")
    print(f"check_elemop: {total} pairs from their elements' operands in {args[0]}")


if __name__ == "__main__":
    main()
