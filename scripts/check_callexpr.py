#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A call inside an expression pushes nothing (P297), read in the
assembly paslangc wrote for testdata/callexpr.paslang, amd64 or with
--arm arm64:

- every loop of Run, Areas, Gets and Six reaches its call through a
  routine value, an interface or a virtual method with nothing pushed
  from the loop's head to the call;
- the code and second word go from their place to the call's registers:
  r11 and r10 (x8 and x27), on amd64 from the element's own operand
  (v_fns(,%rax,8), P329), Self through r10 (x27) when an argument is
  worked out first, an interface's code from its table in r11 (x8), a
  method value's from its home straight into r11 and rdi (one ldp into x8
  and x0);
- LocArr's element read from the frame at its scaled index after the
  index's check, no address formed (amd64, P329);
- an operand no call can change is read after the call: Run's t as the
  add's memory operand (a load after the call on arm64), the main
  block's mt the same, 7 * a call the product's recipe with no 7 in a
  register, and a constant right side in the instruction (addq $3,
  %rax; add x0, x0, #3) after Deep;
- one a call can change is read before it, pushed: g before BumpG, m
  before BumpVar, LocVar's v, Boxed's c and Outer's v before their
  calls;
- no mov x0, x0 on arm64, and a method table's slot read by one ldr at
  its offset, no add of the offset to x16 before it (P347).
"""

import re
import sys


def routines(lines):
    out, name = {}, None
    for l in lines:
        m = re.match(r"^(p_[A-Za-z0-9_.]+|rt_[A-Za-z0-9_]+|pas_main):$", l)
        if m:
            name = m.group(1)
            out[name] = []
            continue
        if name is not None:
            out[name].append(l)
    return out


def find(rs, prefix):
    for k in rs:
        if k == prefix or k.startswith(prefix + "_o_"):
            return k
    raise SystemExit(f"check_callexpr: no routine {prefix}")


def code(body):
    return [l for l in body if not re.match(r"^\s*\.(loc|cfi)", l) and not l.startswith(".LL")]


def main():
    arm = "--arm" in sys.argv[1:]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        raise SystemExit("usage: check_callexpr.py file.s [--arm]")
    rs = {k: code(v) for k, v in routines(open(args[0]).read().splitlines()).items()}
    bad = []
    push = re.compile(r"^  (pushq|popq) |^  str x\d+, \[sp, #-16\]!|^  ldr x\d+, \[sp\], #16")
    callre = re.compile(r"^  (call \*|blr )")

    def loops(name, want):
        body = rs[find(rs, name)]
        n = 0
        for i, l in enumerate(body):
            if l.strip() != ".p2align 5":
                continue
            for j in range(i + 1, len(body)):
                if push.match(body[j]):
                    bad.append(f"{name}: a push in the loop before its call: {body[j].strip()}")
                    break
                if callre.match(body[j]):
                    n += 1
                    seg = "\n".join(body[i:j + 1])
                    for w in want:
                        if not re.search(w, seg, re.M):
                            bad.append(f"{name}: the loop's call has no {w}")
                    break
        if n == 0:
            bad.append(f"{name}: no loop reaching an indirect call")

    def before(name, callpat, n=1):
        """a push between the routine's start or the previous call and each
        call matching callpat: the operand read before it"""
        body = rs[find(rs, name)]
        seen, last = 0, 0
        for i, l in enumerate(body):
            if re.match(callpat, l):
                seen += 1
                if not any(push.match(x) for x in body[last:i]):
                    bad.append(f"{name}: nothing pushed before {l.strip()}")
                last = i + 1
            elif re.match(r"^  (call|bl|blr) ", l):
                last = i + 1
        if seen < n:
            bad.append(f"{name}: {seen} calls {callpat}, {n} at least")

    def has(name, pat, what):
        if not re.search(pat, "\n".join(rs[find(rs, name)]), re.M):
            bad.append(f"{name}: no {what}")

    if not arm:
        loops("p_run", [r"^  movq v_fns\(,%rax,8\), %r11$", r"^  movq v_fns\+8\(,%rax,8\), %r10$",
                        r"^  call \*%r11$"])
        # Self straight into rdi since P332: the argument, a chain, is
        # worked out in its own register and leaves rdi alone
        loops("p_areas", [r"^  movq v_shapes\(,%rax,8\), %rdi$", r"^  movq v_shapes\+8\(,%rax,8\), %r11$",
                          r"^  movq 0\(%r11\), %r11$"])
        loops("p_gets", [r"^  movq %rax, %rdi$", r"^  call \*\d+\(%rax\)$"])
        loops("p_six", [r"^  call \*%r11$"])
        has("p_run", r"^  call \*%r11\n(\.Lgm\d+:\n)?  addq -\d+\(%rbp\), %rax$", "t added from its home after the call")
        has("p_gets", r"^  movq (-\d+)\(%rbp\), %r11\n  movq -\d+\(%rbp\), %rdi\n  movl \$5, %esi\n  call \*%r11$",
            "method value's code and Self from its home")
        has("pas_main", r"^  addq v_mt\(%rip\), %rax$", "mt added from its home after the call")
        has("pas_main", r"^  call \*%r11\n(\.Lgm\d+:\n)?  (imulq \$7, %rax|leaq \(%rax,%rax,2\), %rcx\n  leaq \(%rax,%rcx,2\), %rax)$",
            "7 times a call with 7 in the instruction or a recipe")
        has("pas_main", r"^  xorq v_mt\(%rip\), %rax$", "mt xor a call from its home")
        has("pas_main", r"^  andq v_mt\(%rip\), %rax$", "mt and a call from its home")
        has("pas_main", r"^  orq v_mt\(%rip\), %rax$", "mt or a call from its home")
        has("p_locarr", r"^  call p_deep\n(\.Lgm\d+:\n)?  addq \$3, %rax$", "Deep(N) + 3 as addq $3")
        has("p_locarr", r"^  imulq \$1000, %rax, %rax$", "a product by 1000 in the instruction")
        has("p_locarr", r"^  addq \$3, %rax\n  cmpq \$9, %rax\n  ja \.L\d+\n\.L\d+:\n  leaq \(%rax,%rax,2\), %rax\n"
            r"  movq -\d+\(%rbp,%rax,8\), %rax$", "the element read at its index after the check")
        before("pas_main", r"^  call p_bumpg$")
        before("pas_main", r"^  call p_bumpvar$")
        before("p_locvar", r"^  call \*%r11$")
        before("p_boxed", r"^  call \*%r11$")
        before("p_outer", r"^  call p_outer_inner$")
    else:
        loops("p_run", [r"^  ldp x8, x27, \[x0\]$", r"^  blr x8$"])
        loops("p_areas", [r"^  ldp x0, x8, \[x0\]$", r"^  ldr x8, \[x8, #0\]$"])
        loops("p_gets", [r"^  ldr x0, \[x9, x10, lsl #3\]$", r"^  ldr x16, \[x0\]\n  ldr x16, \[x16, #\d+\]\n  blr x16$"])
        loops("p_six", [r"^  blr x8$"])
        has("p_run", r"^  blr x8\n(\.Lgm\d+:\n)?  ldr x1, \[x29, #-\d+\]\n  add x0, x1, x0$", "t read after the call")
        has("p_gets", r"^  ldp x8, x0, \[x29, #-\d+\]\n  mov x1, #5\n  blr x8$", "method value's code and Self in one ldp")
        # folded since P328: WriteLn's operands are stored at sp's offset
        # and no longer take x16, so P331's fold takes the read
        has("pas_main", r"^  blr x8\n(\.Lgm\d+:\n)?  adrp x16, v_mt\n  ldr x1, \[x16, :lo12:v_mt\]$",
            "mt read after the call")
        has("p_locarr", r"^  bl p_deep\n(\.Lgm\d+:\n)?  add x0, x0, #3\n  cmp x0, #9$", "Deep(N) + 3 as add #3")
        before("pas_main", r"^  bl p_bumpg$")
        before("pas_main", r"^  bl p_bumpvar$")
        before("p_locvar", r"^  blr x8$")
        before("p_boxed", r"^  blr x8$")
        before("p_outer", r"^  bl p_outer_inner$")
        for k, body in rs.items():
            if k.startswith("rt_"):
                continue
            for i, l in enumerate(body):
                if l == "  mov x0, x0":
                    bad.append(f"{k}: mov x0, x0")
                if l == "  ldr x16, [x16]" and i > 0 and re.match(r"^  add x16, x\d+, #\d+$", body[i - 1]):
                    bad.append(f"{k}: {body[i - 1].strip()} before a slot's ldr")
    if bad:
        print("\n".join(bad[:20]))
        raise SystemExit(f"check_callexpr: {len(bad)} forms missing in {args[0]}")
    print(f"check_callexpr: calls through values push nothing, operands read in their order, in {args[0]}")


if __name__ == "__main__":
    main()
