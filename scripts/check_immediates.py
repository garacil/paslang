#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A constant an instruction can take is its immediate (P306): in the
assembly paslangc wrote, no routine named loads a constant into a
register for the next instruction to use when that instruction encodes
it and the register is not read again. On arm64 ADD, SUB, CMP and CMN
take 0 to 4095 and such a value shifted by 12, a negative one by the
opposite operation, and AND, ORR, EOR and TST a logical immediate (ARM
DDI 0487 M.c, DecodeBitMasks); on amd64 ADD, SUB, AND, OR, XOR and CMP
a sign-extended imm32. With no routine named it reads every routine
paslangc compiled and prints the count, failing on none.
"""

import re
import sys


def logimm(v):
    v &= (1 << 64) - 1
    if v == 0 or v == (1 << 64) - 1:
        return False
    for size in (2, 4, 8, 16, 32, 64):
        mask = (1 << size) - 1
        e = v & mask
        if all(((v >> (i * size)) & mask) == e for i in range(64 // size)):
            for r in range(size):
                rot = ((e >> r) | (e << (size - r))) & mask
                if rot != 0 and rot != mask and (rot & (rot + 1)) == 0:
                    return True
            return False
    return False


def addimm(k):
    k = abs(k)
    return 0 <= k <= 4095 or ((k & 0xFFF) == 0 and (k >> 12) <= 4095)


R64 = {"eax": "rax", "ebx": "rbx", "ecx": "rcx", "edx": "rdx", "esi": "rsi", "edi": "rdi",
       "ebp": "rbp", **{f"r{i}d": f"r{i}" for i in range(8, 16)}}


def read_again(lines, i, reg):
    """reg is read after line i before it is written or control leaves."""
    word = re.compile(r"(?<![a-z0-9])%?" + re.escape(reg) + r"(?![a-z0-9])")
    for x in lines[i + 1:i + 12]:
        if re.match(r"^\.?[A-Za-z0-9_.]+:$", x) or re.match(r"^  (b|jmp|ret|bl|call)\b", x):
            return False
        ops = x.split(None, 1)
        if len(ops) < 2:
            continue
        args = [a.strip() for a in ops[1].split(",")]
        if not word.search(ops[1]):
            continue
        # amd64 writes its last operand, arm64 its first
        if x.startswith("  mov") and not x.startswith("  movs") and (
                (args[0] in (reg, "%" + reg) and not ops[1].startswith("%")) or
                (args[-1] in (reg, "%" + reg) and ops[1].startswith(("$", "%")) and len(args) == 2 and
                 not word.search(",".join(args[:-1])))):
            return False
        return True
    return False


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: check_immediates.py file.s [name,name,...]")
    path = sys.argv[1]
    names = set(n for n in sys.argv[2].split(",") if n) if len(sys.argv) > 2 else None
    lines = [l.rstrip("\n") for l in open(path)]
    bad = []
    fn = ""
    for i in range(len(lines) - 1):
        l = lines[i]
        m = re.match(r"^(p_[A-Za-z0-9_]+|pas_main):$", l)
        if m:
            fn = m.group(1)
            continue
        if re.match(r"^rt_[A-Za-z0-9_]+:$", l):
            fn = ""
            continue
        if not fn or (names is not None and fn[2:] not in names):
            continue
        nx = lines[i + 1]
        m = re.match(r"^  (?:mov|ldr) (x\d+), [#=](-?\d+)$", l)
        if m:
            reg, k = m.group(1), int(m.group(2))
            m2 = re.match(r"^  (and|orr|eor|add|sub|cmp|cmn|ands|tst) [^,]+(, [^,]+)?, " + reg + "$", nx)
            if m2:
                ok = logimm(k) if m2.group(1) in ("and", "orr", "eor", "ands", "tst") else addimm(k)
                if ok and not read_again(lines, i + 1, reg):
                    bad.append(f"{fn}: {l.strip()} | {nx.strip()}")
            continue
        # a movl of 32 bits zeroes the upper half: a constant from 0 to
        # 2^32 - 1 goes into a register so (P321)
        m = re.match(r"^  mov[lq] \$(-?\d+), %(r[a-z0-9]+|e[a-z]{2})$", l)
        if m:
            k, reg = int(m.group(1)), R64.get(m.group(2), m.group(2))
            m2 = re.match(r"^  (addq|subq|andq|orq|xorq|cmpq) %" + reg + ", ", nx)
            if m2 and -2 ** 31 <= k < 2 ** 31 and not read_again(lines, i + 1, reg):
                bad.append(f"{fn}: {l.strip()} | {nx.strip()}")
    if names is None:
        print(f"check_immediates: {len(bad)} constants through a register in {path}")
        return
    if bad:
        raise SystemExit(f"{path}: a constant its instruction takes went through a register: " +
                         "; ".join(bad[:20]))
    print(f"check_immediates: {len(names)} routines take their constants as immediates")


main()
