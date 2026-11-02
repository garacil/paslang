#!/usr/bin/env python3
"""Writes testdata/crclens.paslang and testdata/crclens.out (P549): the CRC-32 and the CRC-32C of
data made from a seed (random bytes, all 255, all 0, a short period), from the start value 0 and
from 3735928559, for every length from 0 to 70 (every remainder of the eight-byte step and the
bytes left over) and for 1000, 4093, 4094, 4095, 4096, 65535, 65536, 65537 and 1048576 bytes. The
expected CRC-32 is zlib.crc32 of the same data and the CRC-32C is the bit by bit CRC of RFC 3720
worked out here, not the compiler's.

usage: gen_crclens.py [--check]    --check writes nothing and fails when the two
files in testdata are not what this script writes
"""
import os
import sys
import zlib

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata', 'crclens')
CHECK = sys.argv[1:] == ['--check']
M = (1 << 64) - 1


def emit(path, text):
    if CHECK:
        if open(path).read() != text:
            sys.exit(path + ' is not what scripts/gen_crclens.py writes')
    else:
        open(path, 'w').write(text)


def s64(x):
    x &= M
    return x - (1 << 64) if x >> 63 else x


def data(n, kind, seed):
    out = bytearray()
    for i in range(1, n + 1):
        if kind == 0:
            seed = s64(seed * 6364136223846793005 + 1442695040888963407)
            out.append(((seed & M) >> 33) & 255)
        elif kind == 1:
            out.append(255)
        elif kind == 2:
            out.append(0)
        else:
            out.append(97 + (i % 7))
    return bytes(out)


TAB = []
for i in range(256):
    c = i
    for _ in range(8):
        c = (c >> 1) ^ 0x82F63B78 if c & 1 else c >> 1
    TAB.append(c)


def crc32c(d, start):
    c = ~start & 0xFFFFFFFF
    for b in d:
        c = TAB[(c ^ b) & 255] ^ (c >> 8)
    return ~c & 0xFFFFFFFF


STARTS = (0, 3735928559)
CASES = [(n, k, s) for n in range(71) for k in range(4) for s in STARTS]
for n in (1000, 4093, 4094, 4095, 4096, 65535, 65536, 65537, 1048576):
    CASES += [(n, 0, 0), (n, 3, 3735928559)]

PROGRAM = "program crclens;\n\n{ P549: the CRC-32 and the CRC-32C of data made from a seed, from two start values, for every length from 0 to 70 and for some longer ones }\n\nuses\n  sysutils;\n\nvar\n  seed: Int64;\n\nfunction Rnd: Integer;\nbegin\n  seed := seed * 6364136223846793005 + 1442695040888963407;\n  Result := Integer((seed shr 33) and 255);\nend;\n\nfunction Data(n, kind: Integer): string;\nvar\n  i: Integer;\nbegin\n  SetLength(Result, n);\n  for i := 1 to n do\n    case kind of\n      0: Result[i] := Chr(Rnd);\n      1: Result[i] := Chr(255);\n      2: Result[i] := Chr(0);\n    else\n      Result[i] := Chr(97 + (i mod 7));\n    end;\nend;\n\nprocedure One(n, kind, start: Integer);\nvar\n  s: string;\nbegin\n  seed := 549 + n * 31 + kind;\n  s := Data(n, kind);\n  WriteLn(n, ' ', kind, ' ', start, ' ', Crc32(s, start), ' ', Crc32c(s, start));\nend;\n\nconst\n  Big: array[0..8] of Integer = (1000, 4093, 4094, 4095, 4096, 65535, 65536, 65537, 1048576);\n\nvar\n  n, k: Integer;\nbegin\n  for n := 0 to 70 do\n    for k := 0 to 3 do\n    begin\n      One(n, k, 0);\n      One(n, k, 3735928559);\n    end;\n  for k := 0 to 8 do\n  begin\n    One(Big[k], 0, 0);\n    One(Big[k], 3, 3735928559);\n  end;\nend.\n"


def expected():
    out = []
    for n, kind, start in CASES:
        d = data(n, kind, 549 + n * 31 + kind)
        out.append('%d %d %d %d %d\n' % (n, kind, start, zlib.crc32(d, start), crc32c(d, start)))
    return ''.join(out)


emit(OUT + '.paslang', PROGRAM)
emit(OUT + '.out', expected())
