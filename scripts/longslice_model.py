#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""What testdata/longslice.paslang must print (P270), from Python's own
answers: bytes.find for IndexByte and Pos, the first byte that differs
for CompareByte and, the ASCII letters made capitals, for CompareText,
bytes.upper and bytes.lower, the first byte JSON writes escaped, hashlib
for SHA-1 and SHA-2, zlib for CRC-32, a table for CRC-32C (RFC 3720),
and a rotation as one integer whose bit i is bit i mod 8 of byte i div
8. The random texts come from the same xorshift as the test; the tables
are read from the test itself."""
import hashlib
import re
import sys
import zlib

src = open(sys.argv[1] if len(sys.argv) > 1 else 'testdata/longslice.paslang').read()
M64 = (1 << 64) - 1


def table(name):
    m = re.search(name + r': array\[0\.\.\d+\] of Integer = \((.*?)\);', src, re.S)
    return [int(x) for x in m.group(1).replace('\n', ' ').split(',')]


starts = table('Starts')
ds = table('Ds')
rots = table('Rots')
escs = table('Escs')
NTEXT = 4 * 65536 + 999
assert re.search(r'NText = 4 \* 65536 \+ 999;', src)

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


def mix_str(s):
    mix(len(s))
    for b in s:
        mix(b)


def rand_text(n, letters):
    if letters:
        return bytes(97 + rnd() % 26 for _ in range(n))
    return bytes(rnd() & 255 for _ in range(n))


def put(s, i, b):
    return s[:i] + bytes([b]) + s[i + 1:]


def first_diff(a, b):
    """The place of the first byte where a and b differ over the shorter
    one, -1 when none: the longest equal prefix by halving."""
    n = min(len(a), len(b))
    if a[:n] == b[:n]:
        return -1
    lo, hi = 0, n
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if a[:mid] == b[:mid]:
            lo = mid
        else:
            hi = mid
    return lo


def cmp_bytes(a, b):
    i = first_diff(a, b)
    return 0 if i < 0 else a[i] - b[i]


def compare_text(a, b):
    ua, ub = a.upper(), b.upper()
    i = first_diff(ua, ub)
    if i >= 0:
        return ua[i] - ub[i]
    return (len(a) > len(b)) - (len(a) < len(b))


ESC = re.compile(rb'[\x00-\x1f"\\]')
ESC_HTML = re.compile(rb'[\x00-\x1f"\\&<>]')


def esc_first(s, html):
    m = (ESC_HTML if html else ESC).search(s)
    return m.start() if m else -1


def crc32c(s):
    tab = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ 0x82F63B78 if c & 1 else c >> 1
        tab.append(c)
    c = 0xFFFFFFFF
    for b in s:
        c = tab[(c ^ b) & 255] ^ (c >> 8)
    return c ^ 0xFFFFFFFF


def rotate(s, n):
    nb = len(s) * 8
    n %= nb
    x = int.from_bytes(s, 'little')
    x = ((x << n) | (x >> (nb - n))) & ((1 << nb) - 1)
    return x.to_bytes(len(s), 'little')


out = []
seed = 88172645463325252
t = rand_text(NTEXT, True)

H = 0
cnt = 0
for a in starts:
    for k in (1, 2, 3):
        for d in range(-3, 3):
            p = k * 65536 + d
            u = put(t, a + p, 35)
            mix(u.find(b'#', a) - a)
            mix(u.find(b'#', a) + 1)
            cnt += 1
    mix(-1)
    mix(0)
out.append('indexbyte %d %d' % (cnt, H))

H = 0
cnt = 0
for k in (1, 2, 3):
    for d in range(-3, 3):
        p = k * 65536 + d
        u = put(put(put(t, p, 35), p + 1, 33), p + 2, 35)
        mix(u.find(b'#!#') + 1)
        mix(u.find(b'#!#', 36) + 1)
        cnt += 1
sub = t[100000:170000]
mix(t.find(sub) + 1)
sub = sub[:-1] + b'#'
mix(t.find(sub) + 1)
mix(t.find(b'#z') + 1)
u = put(put(t, 200000, 97), 200001, 35)
mix(u.find(b'a#') + 1)
out.append('pos %d %d' % (cnt, H))

H = 0
cnt = 0
for a in starts:
    for k in (1, 2, 3):
        for d in range(-3, 3):
            p = k * 65536 + d
            u = put(t, a + p, 35)
            mix(cmp_bytes(t[a:], u[a:]))
            mix(cmp_bytes(u[a:], t[a:]))
            cnt += 1
    mix(0)
out.append('comparebyte %d %d' % (cnt, H))

H = 0
cnt = 0
v = t.upper()
mix(compare_text(t, v))
for k in (1, 2, 3):
    for d in range(-3, 3):
        p = k * 65536 + d
        u = put(v, p, 35)
        mix(compare_text(t, u))
        mix(compare_text(u, t))
        cnt += 1
out.append('comparetext %d %d' % (cnt, H))

H = 0
cnt = 0
for a in starts:
    for k in (1, 2, 3):
        for d in range(-3, 3):
            for e in escs:
                for mode in (0, 1):
                    p = k * 65536 + d
                    u = put(t, a + p, e)
                    mix(esc_first(u[a:], mode == 1))
                    cnt += 1
    mix(esc_first(t[a:], True))
out.append('jsonesc %d %d' % (cnt, H))

H = 0
w = rand_text(NTEXT, False)
mix_str(w.upper())
mix_str(w.lower())
out.append('case %d %d' % (NTEXT, H))

w = rand_text(3 * 65536, False)
algs = [
    lambda s: hashlib.sha1(s).digest(),
    lambda s: hashlib.sha224(s).digest(),
    lambda s: hashlib.sha256(s).digest(),
    lambda s: hashlib.sha384(s).digest(),
    lambda s: hashlib.sha512(s).digest(),
    lambda s: str(zlib.crc32(s)).encode(),
    lambda s: str(crc32c(s)).encode(),
]
for c, alg in enumerate(algs):
    H = 0
    cnt = 0
    for k in (1, 2):
        for d in ds:
            mix_str(alg(w[:k * 65536 + d]))
            cnt += 1
    out.append('hash %d %d %d' % (c, cnt, H))

H = 0
w = rand_text(300000, False)
for n in rots:
    mix_str(rotate(w, n))
    mix_str(rotate(w, -n))
out.append('rotate 8 %d' % H)
out.append('disagree 0')
print('\n'.join(out))
