#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A word worked out in the pool lands in the register that reads it
(P328), read in the assembly of testdata/argreg: in its compiled
routines no move of a pool register to rax that a move of rax to an
argument's register, a test of rax or a store of rax follows (amd64),
and no store of x0 or a pair through x16 for WriteLn's operands, nor a
move to x0 of a pool register that a move of x0 to an argument's
register follows (arm64, --arm). F(i and 15) must be worked out in its
argument's register: a load and an and into rdi (amd64) or x0 (arm64).

usage: check_argreg.py file.s [--arm]
"""

import re
import sys


def routines(lines):
    out, name = {}, None
    for l in lines:
        m = re.match(r"^([A-Za-z_][\w.]*):$", l)
        if m:
            name = m.group(1)
            out[name] = []
            continue
        if name is not None:
            out[name].append(l.strip())
    return {n: b for n, b in out.items() if n.startswith("p_") or n == "pas_main"}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arm = "--arm" in sys.argv[1:]
    if len(args) != 1:
        raise SystemExit(__doc__)
    bad = []
    body = routines(open(args[0]).read().splitlines())
    for n, ls in body.items():
        ls = [l for l in ls if l and not l.startswith(".loc") and not l.startswith(".cfi")]
        for a, b in zip(ls, ls[1:]):
            if not arm:
                if re.match(r"^movq %(rsi|rdi|r8|r9|r10|r11), %rax$", a) and (
                        re.match(r"^movq %rax, %(rdi|rsi|rdx|rcx|r8|r9)$", b) or
                        b == "testq %rax, %rax" or re.match(r"^movq %rax, -?\d+\(%rsp\)$", b)):
                    bad.append(f"{n}: {a}; {b}")
            else:
                if re.match(r"^mov x0, x(9|1[0-5])$", a) and re.match(r"^mov x[1-7], x0$", b):
                    bad.append(f"{n}: {a}; {b}")
                if b in ("str x0, [x16]", "stp x0, x2, [x16]") and a.startswith("add x16, sp"):
                    bad.append(f"{n}: {a}; {b}")
    main_body = "\n".join(body.get("pas_main", []))
    if arm:
        if not re.search(r"ldr x0, \[x16, :lo12:v_i\]\nand x0, x0, #(15|0x0*f)\n(\.\S+:\n)?bl p_f", main_body):
            bad.append("pas_main: F(i and 15) is not a load and an and in x0")
    elif not re.search(r"movq v_i\(%rip\), %rdi\nandq \$15, %rdi\n(\.\S+:\n)?call p_f", main_body):
        bad.append("pas_main: F(i and 15) is not a load and an and in rdi")
    if bad:
        print("\n".join(bad[:20]))
        raise SystemExit(f"check_argreg: {len(bad)} values moved on the way to their reader in {args[0]}")
    print(f"check_argreg: every value worked out in the pool where its reader takes it, in {args[0]}")


if __name__ == "__main__":
    main()
