#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""The lines of a program's code, read as the runtime reads them (P572).

Every object file adds a record per routine to section paslines: where
the routine starts, how long it is, where its table of lines is and
where its unit's name is. rt_pcline finds the routine of a pc by halving
the records, which the link must therefore lay in the order of the code,
and reads the routine's table: a count and, for each line label, a step
of address and a step of line (folded as Go folds a step of value), each
an unsigned LEB128. This script reads
the ELF itself (an arm64 executable on any machine), does what rt_pcline
does, and compares with the line table the assembler wrote from the same
.loc directives (.debug_line, by readelf), which no code of paslang
wrote:

  - the records are in the order of the code, none empty, none over the
    next, every one inside .text, in a section nothing writes;
  - the line labels of a routine are in the order of their addresses,
    so every step is forward and short;
  - at every address the assembler's table gives a line, rt_pcline gives
    that line, and the unit whose file it is (no unit for the program's
    own file); between two of its rows, up to the routine's end, the
    line of the first, or the next one's where a label stands before
    the padding that aligns it;
  - every line label of the tables is a row of the assembler's table
    with that line, at its address or at the next instruction's;
  - a record ends where the code of its section ends (a program's main
    block's where the runtime starts);
  - the first byte of .text, the byte before the first routine and the
    runtime's rt_boot and rt_pcline have no line.

With --sizes it also says what the tables cost each program.

With --ask the one executable is testdata/units/placeask, which writes
what the runtime's own rt_pcline gives for each pc it reads: it is run
(by RUNNER when it is another machine's) on every address of the
assembler's table, the ones beside them, the ends of every routine and
a few outside all code, and each answer must be the one worked out
here, which the checks above tie to the assembler's table. That program
carries one table written by hand whose labels are out of the order of
the code (its routine p_placeask_made), which the runtime must read
right too; it is the one table allowed a step back, and it must have it.

usage: check_paslines.py [--sizes] executable...
       check_paslines.py --ask executable [RUNNER ...]
"""

import bisect
import os
import struct
import subprocess
import sys

M64 = (1 << 64) - 1
ASK_SECONDS = 120       # the program asked answers in a second or two, in ten under an emulator


def sections(data, path):
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        raise SystemExit(f"{path}: not a 64-bit little-endian ELF file")
    shoff = struct.unpack_from("<Q", data, 0x28)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x3A)
    heads = []
    for i in range(shnum):
        o = shoff + i * shentsize
        name, typ, flags, addr, off, size = struct.unpack_from("<IIQQQQ", data, o)
        heads.append((name, typ, addr, off, size, flags))
    stroff = heads[shstrndx][3]

    def nm(n):
        e = data.index(b"\0", stroff + n)
        return data[stroff + n:e].decode()
    return {nm(h[0]): h for h in heads}


def writable(data, addr):
    """whether the segment that holds addr may be written (PT_LOAD 1, PF_W 2)"""
    phoff = struct.unpack_from("<Q", data, 0x20)[0]
    phentsize, phnum = struct.unpack_from("<HH", data, 0x36)
    for i in range(phnum):
        typ, flags, _, vaddr, _, _, memsz = struct.unpack_from("<IIQQQQQ", data, phoff + i * phentsize)
        if typ == 1 and vaddr <= addr < vaddr + memsz:
            return flags & 2 != 0
    raise SystemExit(f"address {addr:#x} is in no segment of the program")


class Image:
    """the bytes of the program by their addresses"""

    def __init__(self, data, secs):
        self.data = data
        # the sections that are in memory and in the file (not .bss, type 8)
        self.spans = sorted((h[2], h[2] + h[4], h[3]) for h in secs.values() if h[2] and h[1] != 8 and h[4])

    def off(self, addr):
        for lo, hi, o in self.spans:
            if lo <= addr < hi:
                return o + addr - lo
        raise SystemExit(f"address {addr:#x} is in no section of the file")


def uleb(data, o):
    """the unsigned LEB128 at o (DWARF 5, 7.6, figure C.3), read into 64 bits as rt_pcline reads it (the bits
    past the 64th fall off), and where the next starts"""
    v = shift = 0
    while True:
        b = data[o]
        o += 1
        v |= ((b & 127) << shift) & M64
        shift += 7
        if not b & 128:
            return v, o


def records(data, secs, img, path):
    """[(start, length, [(offset, line)...] in the table's order, name or None, bytes of the table)] and the
    starts of the routines whose table has a step back"""
    if "paslines" not in secs:
        raise SystemExit(f"{path}: no paslines section")
    _, _, addr, off, size, flags = secs["paslines"]
    if size == 0 or size % 16:
        raise SystemExit(f"{path}: paslines has {size} bytes, not records of 16")
    # SHF_WRITE 1, SHF_ALLOC 2: in memory, among the pages nothing writes
    if flags & 3 != 2 or writable(data, addr):
        raise SystemExit(f"{path}: paslines (flags {flags:#x}) must be in memory and among the pages nothing writes")
    out = []
    backs = set()
    for i in range(0, size, 16):
        w0, w1, w2, w3 = struct.unpack_from("<iIii", data, off + i)
        rec = addr + i
        start = rec + w0
        t0 = img.off(rec + 8 + w2)
        n, o = uleb(data, t0)
        if n == 0 or n > w1 + 1:
            raise SystemExit(f"{path}: the table of the routine at {start:#x} counts {n} line labels in {w1} bytes")
        entries = []
        at = line = 0
        for _ in range(n):
            d, o = uleb(data, o)
            # the labels are written in the order of their addresses, the body's and then those of the blocks
            # after the ret: a step back is read right (the 64 bits wrap) and costs ten bytes; check says where
            # one is found
            if d >> 63:
                backs.add(start)
            at = (at + d) & M64
            d, o = uleb(data, o)
            # a step of line folded as Go folds a step of value (runtime/symtab.go, step)
            line += (d >> 1) ^ -(d & 1)
            if at >= w1:
                raise SystemExit(f"{path}: a line label {at} bytes into the routine at {start:#x}, which has {w1}")
            if line <= 0:
                raise SystemExit(f"{path}: line {line} in the table of the routine at {start:#x}")
            entries.append((at, line))
        name = None
        if w3:
            no = img.off(rec + 12 + w3)
            name = data[no + 1:no + 1 + data[no]].decode()
            if not name:
                raise SystemExit(f"{path}: a unit with no name for the routine at {start:#x}")
        out.append((start, w1, entries, name, o - t0))
    return out, backs


def pcline(recs, starts, pc):
    """rt_pcline: the line of pc, 0 for none, and the unit's name"""
    lo, hi = 0, len(recs)
    while lo < hi:
        mid = (lo + hi) // 2
        if starts[mid] <= pc:
            lo = mid + 1
        else:
            hi = mid
    if lo == 0:
        return 0, None
    start, length, entries, name, _ = recs[lo - 1]
    at = pc - start
    if at >= length:
        return 0, None
    best = -1
    line = 0
    for o, l in entries:
        if o > at or o < best:
            continue
        best, line = o, l
    if line == 0:
        return 0, None
    return line, name


def asm_rows(path, lo, hi):
    """the assembler's line table: the sequences of (address, file, line) inside [lo, hi), each ended by its
    last address"""
    r = subprocess.run(["readelf", "-W", "--debug-dump=decodedline", path], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"{path}: readelf failed: {r.stderr.strip()[:200]}")
    seqs = []
    cur = []
    for l in r.stdout.split("\n"):
        t = l.split()
        if len(t) < 3:
            continue
        try:
            addr = int(t[2], 16)
        except ValueError:
            continue
        if t[1] == "-":
            if cur and lo <= cur[0][0] < hi:
                seqs.append((cur, addr))
            cur = []
            continue
        if not t[1].isdigit():
            continue
        cur.append((addr, t[0], int(t[1])))
    if cur:
        raise SystemExit(f"{path}: a sequence of the assembler's line table has no end")
    return seqs


def unit_of(fname):
    b = os.path.basename(fname)
    if b.endswith(".paslang"):
        b = b[:-8]
    return b.lower()


def symbol(path, name):
    """the address of a symbol of the program, None when it has none of that name"""
    r = subprocess.run(["readelf", "-sW", path], capture_output=True, text=True)
    for l in r.stdout.split("\n"):
        t = l.split()
        if len(t) == 8 and t[7] == name:
            return int(t[1], 16)
    return None


def check(path, sizes, made=None):
    """made: the routine whose table, written by hand, has its labels out of the order of the code"""
    data = open(path, "rb").read()
    secs = sections(data, path)
    img = Image(data, secs)
    if ".text" not in secs:
        raise SystemExit(f"{path}: no .text section")
    tlo = secs[".text"][2]
    thi = tlo + secs[".text"][4]
    recs, backs = records(data, secs, img, path)
    starts = [r[0] for r in recs]
    for start in sorted(backs - {made}):
        raise SystemExit(f"{path}: a line label of the routine at {start:#x} stands before the one written before "
                         "it: the labels of a table are not in the order of the code")
    if made is not None and made not in backs:
        raise SystemExit(f"{path}: the table written by hand, of the routine at {made:#x}, has no step back")
    for i, (start, length, entries, name, _) in enumerate(recs):
        if length == 0:
            raise SystemExit(f"{path}: the record of the routine at {start:#x} is empty")
        if start < tlo or start + length > thi:
            raise SystemExit(f"{path}: the routine at {start:#x} of {length} bytes is not inside .text")
        if i and start < recs[i - 1][0] + recs[i - 1][1]:
            raise SystemExit(f"{path}: record {i} at {start:#x} comes before the end "
                             f"{recs[i - 1][0] + recs[i - 1][1]:#x} of the one before: paslines is not in the "
                             "order of the code")
    if ".debug_line" not in secs:
        raise SystemExit(f"{path}: no .debug_line to compare with (a stripped program)")
    seqs = asm_rows(path, tlo, thi)
    if not seqs:
        raise SystemExit(f"{path}: the assembler's line table has no row inside .text")
    rows = 0
    own = set()
    at_addr = {}
    for seq, end in seqs:
        for addr, fname, line in seq:
            at_addr.setdefault(addr, []).append(line)
    # a record ends where the code of its section ends, which is where the assembler's rows of it end; but the
    # one of a program's main block, which the runtime follows in its section
    short = 0
    for seq, end in seqs:
        r = bisect.bisect_right(starts, seq[0][0]) - 1
        if r < 0 or seq[0][0] >= recs[r][0] + recs[r][1]:
            raise SystemExit(f"{path}: the code at {seq[0][0]:#x}, line {seq[0][2]} of {seq[0][1]}, is in no record")
        rend = recs[r][0] + recs[r][1]
        if rend > end:
            raise SystemExit(f"{path}: the record of the routine at {recs[r][0]:#x} ends at {rend:#x}, past the "
                             f"end {end:#x} of its code")
        if rend < end:
            short += 1
            if recs[r][3] is not None or short > 1:
                raise SystemExit(f"{path}: the record of the routine at {recs[r][0]:#x} ends at {rend:#x}, before "
                                 f"the end {end:#x} of its code")
    # the lines of the tables' labels at each address, in the order written
    labels_at = {}
    for start, length, entries, name, _ in recs:
        for o, l in entries:
            labels_at.setdefault(start + o, []).append(l)
    for seq, end in seqs:
        # the later of two rows at one address is the one in force
        last = {}
        for addr, fname, line in seq:
            last[addr] = (fname, line)
        addrs = sorted(last)
        for k, addr in enumerate(addrs):
            fname, line = last[addr]
            nxt = addrs[k + 1] if k + 1 < len(addrs) else end
            # a line label written before the padding that aligns the next instruction (a loop's head) gives
            # the padding its line, where the assembler's row waits for the instruction: both lines are right
            # for bytes nothing stops at. With two labels before the padding the assembler gives it the first
            # one's line (a second .loc forces the row of the first out where it stands) and the tables the
            # second's, the later of two at one address: there the two differ at the row's own address too
            pad = set(at_addr.get(nxt, ()))
            # the assembler's row holds until the next one or the end of its section; the routine's lines end
            # with the routine (a program's main block is followed, in its section, by the runtime, which has
            # no line: there the assembler's table goes on saying the main block's last)
            r = bisect.bisect_right(starts, addr) - 1
            if r >= 0:
                nxt = min(nxt, recs[r][0] + recs[r][1])
            for pc in (addr, addr + 1, nxt - 1):
                if not addr <= pc < nxt:
                    continue
                got, unit = pcline(recs, starts, pc)
                if got != line and (got not in pad or (pc == addr and line not in labels_at.get(addr, ()))):
                    raise SystemExit(f"{path}: pc {pc:#x} is line {line} of {fname} by the assembler's table "
                                     f"and line {got} by rt_pcline")
                if unit is None:
                    own.add(unit_of(fname))
                elif unit.lower() != unit_of(fname):
                    raise SystemExit(f"{path}: pc {pc:#x} is in {fname} by the assembler's table and in unit "
                                     f"{unit} by rt_pcline")
            rows += 1
    if len(own) > 1:
        raise SystemExit(f"{path}: code of {sorted(own)} with no unit's name: one file is the program's")
    # every line label of the tables is a row of the assembler's: at its address, or at the next instruction's
    # when padding follows the label (after a first label whose row was forced out at the label's address)
    row_addrs = sorted(at_addr)
    labels = 0
    for start, length, entries, name, _ in recs:
        for o, l in entries:
            k = bisect.bisect_left(row_addrs, start + o)
            ok = k < len(row_addrs) and row_addrs[k] < start + length and l in at_addr[row_addrs[k]]
            if not ok and k + 1 < len(row_addrs) and row_addrs[k] == start + o and row_addrs[k + 1] < start + length:
                ok = l in at_addr[row_addrs[k + 1]]
            if not ok:
                raise SystemExit(f"{path}: a line label at {start + o:#x} says line {l}, and the assembler's "
                                 "table has no row of that line there")
        labels += len(entries)
    # no line outside the routines: before the first, and in the runtime, which follows a program's main block
    # (rt_boot and rt_pcline are the runtime's in every program)
    outside = [("the first byte of .text", tlo), ("the byte before the first routine", starts[0] - 1)]
    for name in ("rt_boot", "rt_pcline"):
        pc = symbol(path, name)
        if pc is None:
            raise SystemExit(f"{path}: {name} is not in its symbols")
        outside.append((name, pc))
    for what, pc in outside:
        if pcline(recs, starts, pc) != (0, None):
            raise SystemExit(f"{path}: {what}, pc {pc:#x}, is in no routine of the source and rt_pcline gives "
                             f"it line {pcline(recs, starts, pc)[0]}")
    names = {r[3] for r in recs if r[3]}
    cost = (secs["paslines"][4], sum(r[4] for r in recs), sum(len(n) + 1 for n in names))
    if sizes:
        text = secs[".text"][4]
        print(f"  {os.path.basename(path)}: {len(recs)} routines, {labels} line labels, {sum(cost)} bytes "
              f"({cost[0]} of records, {cost[1]} of tables, {cost[2]} of names) beside {text} of code: "
              f"{100.0 * sum(cost) / text:.1f} %")
    return len(recs), labels, rows, len(names), (recs, starts, seqs, tlo, thi)


def ask(path, runner):
    """the program's own answers against pcline's"""
    # Made embeds this literal GAS symbol and a hand-written table.
    # It is independent of the compiler-generated Pascal routine name.
    made = symbol(path, "p_placeask_made")
    if made is None:
        raise SystemExit(f"{path}: no routine p_placeask_made: it is not testdata/units/placeask")
    nrec, labels, rows, _, (recs, starts, seqs, tlo, thi) = check(path, False, made)
    pcs = {0, 1, tlo - 1, tlo, thi - 1, thi, thi + 4096, (1 << 63) - 1, 1 << 63, M64}
    for start, length, entries, name, _ in recs:
        pcs.update((start - 1, start, start + length - 1, start + length))
        for o, _ in entries:
            pcs.update((start + o - 1, start + o, start + o + 1))
    for seq, end in seqs:
        for addr, _, _ in seq:
            pcs.update((addr - 1, addr, addr + 1))
        pcs.update((end - 1, end))
    pcs = sorted(pcs)
    # the program reads signed numbers
    text = "%d\n" % len(pcs) + "".join("%d\n" % (pc - (1 << 64) if pc >> 63 else pc) for pc in pcs)
    try:
        r = subprocess.run(runner + [path], input=text, capture_output=True, text=True, timeout=ASK_SECONDS)
    except subprocess.TimeoutExpired:
        raise SystemExit(f"{path}: no answer in {ASK_SECONDS} seconds")
    if r.returncode != 0:
        raise SystemExit(f"{path}: ended with status {r.returncode}: {r.stderr.strip()[:200]}")
    got = r.stdout.split("\n")
    if got and got[-1] == "":
        got.pop()
    if len(got) != len(pcs):
        raise SystemExit(f"{path}: {len(got)} answers to {len(pcs)} questions")
    lined = 0
    for pc, g in zip(pcs, got):
        line, name = pcline(recs, starts, pc)
        want = "%d %s" % (line, name or "")
        if g != want:
            raise SystemExit(f"{path}: the runtime says {g!r} for pc {pc:#x}; its tables, read here, say {want!r}")
        lined += line != 0
    print(f"check_paslines: {os.path.basename(path)} asked about {len(pcs)} addresses, {lined} of them with a "
          f"line: every answer of its rt_pcline is the one its tables give ({nrec} routines, {labels} line "
          f"labels, {rows} rows of the assembler's table)")


def main():
    args = sys.argv[1:]
    if args[:1] == ["--ask"]:
        if len(args) < 2:
            raise SystemExit(__doc__.strip().splitlines()[-1])
        ask(args[1], args[2:])
        return
    sizes = "--sizes" in args
    paths = [a for a in args if a != "--sizes"]
    if not paths:
        raise SystemExit(__doc__.strip().splitlines()[-2])
    tot = [0, 0, 0]
    for path in paths:
        r = check(path, sizes)
        for i in range(3):
            tot[i] += r[i]
    print(f"check_paslines: {len(paths)} programs, {tot[0]} routines and {tot[1]} line labels, every line as "
          f"the assembler's table says it ({tot[2]} rows)")


if __name__ == "__main__":
    main()
