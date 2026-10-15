#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""The pasasync table of an executable (P293): every entry is the code of
one routine paslangc compiled, so rt_sigurg stops a routine only there.

Each (start, end) pair must start in a routine (p_... or pas_main), at
its symbol or after the stack check of its prologue, end after it, and
hold no symbol of the runtime (rt_...) or _start: an entry that spans
the runtime would let a signal stop a routine inside the allocator or
the scheduler. No entry may hold a call to rt_morestack: a routine
stopped between its load of the guard word and that call would come
back with the request cleared and double its stack for nothing (Go's
issue 35470). Reads the ELF itself, so it checks an arm64 executable on
any machine.
"""

import bisect
import struct
import sys


def sections(data):
    shoff = struct.unpack_from("<Q", data, 0x28)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x3A)
    heads = []
    for i in range(shnum):
        o = shoff + i * shentsize
        name, typ, flags, addr, off, size, link = struct.unpack_from("<IIQQQQI", data, o)
        heads.append((name, typ, addr, off, size, link))
    stroff = heads[shstrndx][3]

    def nm(n):
        e = data.index(b"\0", stroff + n)
        return data[stroff + n:e].decode()
    return {nm(h[0]): h for h in heads}, heads


def calls(data, heads, start, end, target, arm):
    """The direct calls to target in [start, end): bl on arm64, call
    rel32 on amd64."""
    for _, typ, addr, off, size, _ in heads:
        if typ == 1 and addr <= start and end <= addr + size:
            break
    else:
        raise SystemExit(f"{sys.argv[1]}: entry {start:#x}-{end:#x} lies in no section")
    found = []
    if arm:
        a = (start + 3) & ~3
        while a + 4 <= end:
            w = struct.unpack_from("<I", data, off + a - addr)[0]
            if w & 0xFC000000 == 0x94000000:
                imm = w & 0x3FFFFFF
                if imm & 0x2000000:
                    imm -= 1 << 26
                if a + 4 * imm == target:
                    found.append(a)
            a += 4
    else:
        for a in range(start, end - 4):
            if data[off + a - addr] == 0xE8:
                rel = struct.unpack_from("<i", data, off + a - addr + 1)[0]
                if a + 5 + rel == target:
                    found.append(a)
    return found


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_pasasync.py executable")
    data = open(sys.argv[1], "rb").read()
    arm = struct.unpack_from("<H", data, 0x12)[0] == 183
    secs, heads = sections(data)
    if "pasasync" not in secs:
        raise SystemExit(f"{sys.argv[1]}: no pasasync section")
    _, _, _, off, size, _ = secs["pasasync"]
    entries = [struct.unpack_from("<QQ", data, off + i) for i in range(0, size, 16)]
    sym = secs[".symtab"]
    stroff = heads[sym[5]][3]
    names = {}
    for i in range(0, sym[4], 24):
        n, info, other, shndx, value, sz = struct.unpack_from("<IBBHQQ", data, sym[3] + i)
        if n == 0:
            continue
        e = data.index(b"\0", stroff + n)
        names.setdefault(value, []).append(data[stroff + n:e].decode())
    runtime = sorted(v for v, ns in names.items()
                     if any(x.startswith("rt_") or x == "_start" for x in ns))
    morestack = [v for v, ns in names.items() if "rt_morestack" in ns]
    if not morestack:
        raise SystemExit(f"{sys.argv[1]}: no rt_morestack")
    syms = sorted(names)
    if not entries:
        raise SystemExit(f"{sys.argv[1]}: the pasasync table is empty")
    after = 0
    for start, end in entries:
        k = bisect.bisect_right(syms, start)
        base = syms[k - 1] if k else 0
        own = names.get(base, [])
        if not any(x.startswith("p_") or x == "pas_main" for x in own):
            raise SystemExit(f"{sys.argv[1]}: entry {start:#x}-{end:#x} starts in no routine ({own})")
        if start - base > 64:
            raise SystemExit(f"{sys.argv[1]}: entry {start:#x}-{end:#x} starts {start - base} bytes into {own[0]}, past a stack check")
        if start > base:
            after += 1
        if not start < end <= start + (1 << 20):
            raise SystemExit(f"{sys.argv[1]}: entry {start:#x}-{end:#x} has no length a routine has")
        inside = [v for v in runtime if base < v < end]
        if inside:
            raise SystemExit(f"{sys.argv[1]}: entry {start:#x}-{end:#x} holds the runtime at {inside[0]:#x} ({names[inside[0]]})")
        ms = calls(data, heads, start, end, morestack[0], arm)
        if ms:
            raise SystemExit(f"{sys.argv[1]}: entry {start:#x}-{end:#x} ({own[0]}) calls rt_morestack at {ms[0]:#x}")
    print(f"check_pasasync: {len(entries)} routines ({after} from after their stack check), none spans the runtime or calls rt_morestack")


main()
