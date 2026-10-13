#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""What testdata/jsonkern.paslang must print (P202), from the definitions
of JSON's scans, written again here byte by byte: a backslash escapes the
next byte unless it is escaped itself; a quote not escaped opens or
closes a string and lies inside it when it opens it; an operator is a
comma, a colon, a bracket or a brace, white space a space, a tab, a line
feed or a carriage return; a scalar's first byte is one that is neither
an operator nor white space and does not follow a byte of a scalar
other than a quote. The index holds
every quote, every operator and scalar start outside a string, every
escaping backslash and control byte inside one; the counts are the
values and member names, the scalars that are not strings, and the
bytes of the strings from their opening quote and of the other scalars.
The escape finder gives the first byte below 20h, quote or backslash,
and with HTML ampersand or angle bracket. The random texts come from the
same xorshift as the test; the tables are read from the test itself."""
import re
import sys

src = open(sys.argv[1] if len(sys.argv) > 1 else 'testdata/jsonkern.paslang').read()
M64 = (1 << 64) - 1


def table(name):
    m = re.search(name + r': array\[0\.\.\d+\] of \w+ = \((.*?)\);', src, re.S)
    return m.group(1)


alpha = [int(x) for x in table('Alpha').replace('\n', ' ').split(',')]
fills = [int(x) for x in table('Fills').split(',')]
pats = [p.encode() for p in re.findall(r"'([^']*)'", table('Pats'))]
off_lo = int(re.search(r'OffLo = (\d+);', src).group(1))
off_hi = int(re.search(r'OffHi = (\d+);', src).group(1))
assert len(alpha) == 24 and len(fills) == 4 and len(pats) == 26

seed = 0
H = 0


def rnd():
    global seed
    seed ^= (seed << 13) & M64
    seed ^= seed >> 7
    seed ^= (seed << 17) & M64
    return seed & 0x7FFFFFFFFFFFFFFF


def mix(v):
    global H
    H = (H * 131 + (v & 0xFFFFFFFF) + 1) & 0xFFFFFFFFFFFF


def gen_text(n):
    out = bytearray()
    for _ in range(n):
        if rnd() % 5 == 0:
            out.append(rnd() & 255)
        else:
            out.append(alpha[rnd() % 24])
    return bytes(out)


def gen_str(n):
    out = bytearray()
    for _ in range(n):
        if rnd() % 9 == 0:
            out.append(rnd() & 255)
        else:
            out.append(97 + rnd() % 26)
    return bytes(out)


def scan(data, off, st):
    """The index of data from the state st (escaped, in string, scalar,
    nodes, scalars, bytes), which it updates."""
    esc, ins, prv = st[0] != 0, st[1] != 0, st[2] != 0
    idx = []
    for i, b in enumerate(data):
        op = b in (0x2C, 0x3A, 0x5B, 0x5D, 0x7B, 0x7D)
        ws = b in (0x20, 0x09, 0x0A, 0x0D)
        ctl = b < 0x20
        opening = b in (0x5B, 0x7B)
        escaped = esc
        escape = b == 0x5C and not escaped
        esc = escape
        quote = b == 0x22 and not escaped
        if quote:
            ins = not ins
        scalar = not (op or ws)
        nq = scalar and not quote
        pss = scalar and not prv
        prv = nq
        if ins or nq:
            st[5] += 1
        outs = pss and not quote and not ins
        if outs:
            st[4] += 1
        if (quote and ins) or outs or (opening and not ins):
            st[3] += 1
        if quote or (ins and (escape or ctl)) or (not ins and (op or pss)):
            idx.append((off + i) & 0xFFFFFFFF)
    st[0], st[1], st[2] = int(esc), -int(ins), int(prv)
    return idx


def reference(data, off):
    st = [0] * 6
    pad = ((len(data) + 63) & ~63) - len(data)
    idx = scan(data + b' ' * pad, off, st)
    mix(len(idx))
    for e in idx:
        mix(e)
    for v in st:
        mix(v)


def esc_first(data, html):
    for i, b in enumerate(data):
        if b < 0x20 or b in (0x22, 0x5C) or (html and b in (0x26, 0x3C, 0x3E)):
            return i
    return -1


seed = 88172645463325252
H = 0
cases = 0
for n in range(301):
    t = gen_text(n)
    for off in (off_lo, off_hi):
        reference(t, off)
        cases += 64
print('texts', cases, H)

H = 0
cases = 0
for s in pats:
    for f in fills:
        for mode in (0, 1):
            for o in range(192 - len(s)):
                if not (o < 8 or 48 <= o <= 80 or 112 <= o <= 144 or o >= 184 - len(s)):
                    continue
                t = bytearray([f] * 192)
                if mode == 1:
                    t[0] = 0x22
                t[o:o + len(s)] = s
                reference(bytes(t), off_lo)
                cases += 1
print('patterns', cases, H)

H = 0
cases = 0
for n in range(201):
    t = gen_str(n)
    for mode in (0, 1):
        mix(esc_first(t, mode == 1))
        cases += 64
print('escapes', cases, H)

H = 0
cases = 0
for b in range(256):
    for o in range(71):
        for mode in (0, 1):
            t = bytearray(b'a' * 71)
            t[o] = b
            mix(esc_first(bytes(t), mode == 1))
            cases += 1
print('escape bytes', cases, H)

H = 0
cases = 0
for n in range(1, 201):
    reference(gen_text(n), off_lo)
    t = gen_str(n)
    for mode in (0, 1):
        mix(esc_first(t, mode == 1))
    t = gen_str(n)
    for mode in (0, 1):
        mix(esc_first(t, mode == 1))
    cases += 1
print('guard', 0, cases, H)
print('routines 8 agree 8')
print('disagree', 0)
