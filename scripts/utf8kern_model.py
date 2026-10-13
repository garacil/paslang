#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""What testdata/utf8kern.paslang must print (P201), from Python's strict
UTF-8 decoder: the place of the first byte of the first sequence that
is wrong (UnicodeDecodeError's start), or -1; in I-JSON's mode a
noncharacter (U+FDD0 to U+FDEF, U+xFFFE and U+xFFFF, RFC 7493 2.1) is
wrong too, at its first byte. The classes, the fillers and the lengths
are read from the test itself."""
import re
import sys

src = open(sys.argv[1] if len(sys.argv) > 1 else 'testdata/utf8kern.paslang').read()


def table(name):
    m = re.search(name + r': array\[0\.\.\d+\] of (?:string|Integer) = \((.*?)\);', src, re.S)
    return [t.strip().strip("'") for t in m.group(1).replace('\n', ' ').split(',')]


classes = [bytes.fromhex(x) for x in table('Classes')]
fills = [bytes.fromhex(x) for x in table('Fills')]
longs = [int(x) for x in table('Longs')]


def answer(b, ij):
    try:
        text = b.decode('utf-8')
        bad = None
    except UnicodeDecodeError as e:
        bad = e.start
        text = b[:bad].decode('utf-8')
    if ij:
        pos = 0
        for ch in text:
            cp = ord(ch)
            if 0xFDD0 <= cp <= 0xFDEF or (cp & 0xFFFE) == 0xFFFE:
                return pos
            pos += len(ch.encode('utf-8'))
    return -1 if bad is None else bad


def build(cls, fil, L, O):
    out = bytearray()
    while len(out) + len(fil) <= O:
        out += fil
    while len(out) < O:
        out.append(97)
    out += cls
    while len(out) + len(fil) <= L:
        out += fil
    while len(out) < L:
        out.append(97)
    return bytes(out)


lines = []
for cls in classes:
    n = 0
    s = 0
    for mode in (0, 1):
        for fil in fills:
            for li in list(range(-70, 0)) + list(range(len(longs))):
                L = li + 71 if li < 0 else longs[li]
                if L < len(cls):
                    continue
                for O in range(0, L - len(cls) + 1):
                    r = answer(build(cls, fil, L, O), mode == 1)
                    n += 1
                    s = (s * 31 + r + 2) % 1000000007
    lines.append('%s %d %d' % (cls.hex().upper(), n, s))
n = 0
s = 0
for cls in classes:
    for L in range(len(cls), 141):
        b = build(cls, fills[1], L, L - len(cls))
        for mode in (0, 1):
            r = answer(b, mode == 1)
            n += 1
            s = (s * 31 + r + 2) % 1000000007
lines.append('guard 0 %d %d' % (n, s))
lines.append('disagree 0')
print('\n'.join(lines))
