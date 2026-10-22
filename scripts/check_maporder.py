#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""The two tables a program reads by address, in order as linked (P388).

pasgcmaps holds a pair per call site, its return address and its
descriptor; pasasync a pair per routine a signal may stop, where its
code starts and ends. The runtime looks both up by address (MapFind's
binary search, rt_sigurg's), and sorts them at the start when they are
not in order: the link lays every piece in the order of its code, so
each table must come out of it sorted, its addresses strictly growing,
and a routine's end in pasasync must not pass the next one's start.
Reads the ELF itself, so it checks an arm64 executable on any machine.

usage: check_maporder.py executable...
"""

import struct
import sys


def sections(data, path):
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        raise SystemExit(f"{path}: not a 64-bit little-endian ELF file")
    shoff = struct.unpack_from("<Q", data, 0x28)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x3A)
    heads = []
    for i in range(shnum):
        o = shoff + i * shentsize
        name, typ, flags, addr, off, size = struct.unpack_from("<IIQQQQ", data, o)
        heads.append((name, typ, addr, off, size))
    stroff = heads[shstrndx][3]

    def nm(n):
        e = data.index(b"\0", stroff + n)
        return data[stroff + n:e].decode()
    return {nm(h[0]): h for h in heads}


def pairs(data, head):
    _, _, _, off, size = head
    if size % 16:
        raise SystemExit(f"a table of {size} bytes, not of pairs of words")
    return [struct.unpack_from("<QQ", data, off + i) for i in range(0, size, 16)]


def main():
    paths = sys.argv[1:]
    if not paths:
        raise SystemExit(__doc__.strip().splitlines()[-1])
    sites = stops = 0
    for path in paths:
        data = open(path, "rb").read()
        secs = sections(data, path)
        if "pasgcmaps" not in secs:
            raise SystemExit(f"{path}: no pasgcmaps section")
        maps = pairs(data, secs["pasgcmaps"])
        if not maps:
            raise SystemExit(f"{path}: the stack maps are empty")
        for i in range(1, len(maps)):
            if maps[i][0] <= maps[i - 1][0]:
                raise SystemExit(f"{path}: stack map {i} at {maps[i][0]:#x} comes after "
                                 f"{maps[i - 1][0]:#x}: the table is not in the order of the code")
        sites += len(maps)
        if "pasasync" in secs:
            tab = pairs(data, secs["pasasync"])
            for i, (s, e) in enumerate(tab):
                if e <= s:
                    raise SystemExit(f"{path}: pasasync entry {i} {s:#x}-{e:#x} is empty")
                if i and s < tab[i - 1][1]:
                    raise SystemExit(f"{path}: pasasync entry {i} at {s:#x} comes before the end "
                                     f"{tab[i - 1][1]:#x} of the one before: the table is not in order")
            stops += len(tab)
    print(f"check_maporder: {len(paths)} programs, {sites} stack maps and {stops} routines "
          "of pasasync in the order of their code")


if __name__ == "__main__":
    main()
