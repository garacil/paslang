#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""Every product by a constant takes its recipe, the remainder's
multiply back included (P312). In modconst's assembly the routines M<C>
(x mod C), Loop<C> (products and remainders of a loop's register
variables) and Glob<C> (a global through rax) multiply by C only where
no recipe of Go's linear combinations costs less than the multiply
(cmd/compile/internal/ssa/config.go, BuildRecipes), its costs those of
the processor, and on arm64 no shift whose result the next add or
sub reads beside its source, which Go folds into one ADD or SUB of a
shifted register (ARM64.rules ADDshiftLL, SUBshiftLL). The costs: on amd64 Go's (IMUL 30, an add and a lea of two parts
10, a neg, a sub and a shift 11), a source in r13 or rbp a move more
(10), as pasemit's MulByKVia counts it; on arm64 Go's (MUL 35) with no
tune, Neoverse N1's (45, a shifted add 10 up to a shift of 4) with
--tune n1, and a remainder's MSUB against the forms of ScaleSubArm.
"""

import re
import sys


def combos(arch, tune):
    c = []
    if arch == "amd64":
        mul = 30
        c += [(1, 1, 10, 1), (-1, 0, 11, 2), (1, -1, 11, 3), (1, 2, 10, 8), (1, 4, 10, 8), (1, 8, 10, 8)]
        c += [(1 << i, 0, 11, 7) for i in range(2, 64)]
        return mul, c
    n1 = tune == "n1"
    mul = 45 if n1 else 35

    def sa(i):
        if n1:
            return 10 if i <= 4 else 20
        return 20 if i <= 4 else 21

    c += [(1, 1, 10, 1), (-1, 0, 10, 2), (1, -1, 10, 3)]
    for i in range(1, 64):
        c += [(1, 1 << i, sa(i), 4), (-(1 << i), 0, sa(i), 5), (1, -(1 << i), sa(i), 6),
              ((1 << i), 0, 9 if i == 1 else 10, 7)]
    return mul, c


def recipe(k, mul, c):
    """The cost of k's cheapest recipe under mul, its form and its
    second combination's kind, or None (pasemit's MulRecipe)."""
    best, got = mul, None
    for a, b, cost, kind in c:
        if a + b == k and cost < best:
            best, got = cost, (cost, 1, kind)
    for ia, ib, icost, _ in c:
        vi = ia + ib
        for oa, ob, ocost, okind in c:
            cost = icost + ocost
            if cost >= best:
                continue
            if vi * (oa + ob) == k:
                best, got = cost, (cost, 2, okind)
            elif ob != 0 and oa + ob * vi == k:
                best, got = cost, (cost, 3, okind)
            elif ob != 0 and oa * vi + ob == k:
                best, got = cost, (cost, 4, okind)
    return got


def pow2(v):
    return v > 1 and v & (v - 1) == 0


def msub_better(k, mul, c, tune):
    """True when ScaleSubArm keeps the MSUB for k: no form of it costs
    less than the multiply."""
    def sa(i):
        if tune == "n1":
            return 10 if i <= 4 else 20
        return 20 if i <= 4 else 21
    costs = []
    if pow2(k + 1):
        costs.append(10 + sa((k + 1).bit_length() - 1))
    if pow2(k - 1):
        costs.append(10 + sa((k - 1).bit_length() - 1))
    r = recipe(k, mul, c)
    if r:
        costs.append(r[0] + 10)
    m, s = k, 0
    while m > 1 and m % 2 == 0:
        m, s = m // 2, s + 1
    if s > 0 and m > 1:
        r = recipe(m, mul, c)
        if r:
            costs.append(r[0] + sa(s))
    return not any(x < mul for x in costs)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    arm = "--arm" in sys.argv
    tune = "n1" if "--tune=n1" in sys.argv else "none"
    if len(args) != 1:
        raise SystemExit("usage: check_modconst.py file.s [--arm [--tune=n1]]")
    mul, c = combos("arm64" if arm else "amd64", tune)
    fn, bad, seen, last = "", [], set(), {}
    want = re.compile(r"^p_(m|loop|glob)(n?)(\d+):$")
    k = 0
    for n, line in enumerate(open(args[0]), 1):
        line = line.rstrip("\n")
        m = re.match(r"^(p_[A-Za-z0-9_]+|rt_[A-Za-z0-9_]+|pas_main):$", line)
        if m:
            w = want.match(line)
            fn = line[:-1] if w else ""
            if w:
                seen.add(fn)
                k = -int(w.group(3)) if w.group(2) else int(w.group(3))
            last = {}
            continue
        if not fn:
            continue
        if not arm:
            im = re.match(r"^  imulq \$(-?\d+), (%[a-z0-9]+)(?:, (%[a-z0-9]+))?$", line)
            if im:
                v, src = int(im.group(1)), im.group(2)
                r = recipe(v, mul, c)
                if r is None:
                    continue
                cost = r[0] + (10 if src in ("%r13", "%rbp") else 0)
                dst = im.group(3) or src
                if dst in ("%r13", "%rbp") and r[1] == 2 and r[2] == 8:
                    cost += 10
                if cost < mul:
                    bad.append(f"{n}: {fn}: {line.strip()} (a recipe of cost {cost} under {mul})")
            continue
        ls = re.match(r"^  lsl (x\d+), (x\d+), #(\d+)$", line)
        if ls:
            last["lsl"] = (ls.group(1), ls.group(2), n, line.strip())
            continue
        fu = re.match(r"^  (add|sub) x\d+, (x\d+), (x\d+)$", line)
        if fu and "lsl" in last:
            t, src, ln, txt = last["lsl"]
            a, b = fu.group(2), fu.group(3)
            if ln == n - 1 and ((b == t and a == src) or (fu.group(1) == "add" and a == t and b == src)):
                bad.append(f"{ln}: {fn}: {txt} then {line.strip()}, one {fu.group(1)} of a shifted register")
        last.pop("lsl", None)
        mv = re.match(r"^  mov (x\d+), #(-?\d+)$", line)
        if mv:
            last[mv.group(1)] = int(mv.group(2))
            continue
        mm = re.match(r"^  (mul|msub) x\d+, x\d+, (x\d+)", line)
        if mm and mm.group(2) in last:
            v = last[mm.group(2)]
            if mm.group(1) == "mul":
                if recipe(v, mul, c) is not None:
                    bad.append(f"{n}: {fn}: {line.strip()} by {v}, which has a recipe under {mul}")
            elif not msub_better(v, mul, c, tune):
                bad.append(f"{n}: {fn}: {line.strip()} by {v}, which a form of ScaleSubArm makes cheaper")
    if len(seen) < 3:
        raise SystemExit(f"check_modconst: only {len(seen)} of modconst's routines in {args[0]}")
    if bad:
        print("\n".join(bad))
        raise SystemExit(f"check_modconst: {len(bad)} products by a constant that a recipe makes cheaper in {args[0]}")
    print(f"check_modconst: {len(seen)} routines multiply only where no recipe is cheaper in {args[0]}")


if __name__ == "__main__":
    main()
