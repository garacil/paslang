#!/usr/bin/env python3
"""Writes testdata/adler.paslang and testdata/adler.out (P532): the Adler-32 of data
made from a seed (random bytes, all 255, all 0, a short period), for every length
from 0 to 70 and around every boundary of the eight-byte step and of the
mebibyte between reductions (1048575 to 1048577, 2 MiB + 13, 3,000,001), from the
start value 1 and from others (0, one with s2 at its top, 12345 + 678 * 65536). The
expected output is zlib.adler32 of the same data (made here by the same generator),
not the compiler's.

usage: gen_adler.py [--check]    --check writes nothing and fails when the two
files in testdata are not what this script writes
"""
import os
import sys
import zlib

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata', 'adler')
CHECK = sys.argv[1:] == ['--check']
M = (1 << 64) - 1


def emit(path, text):
    if CHECK:
        if open(path).read() != text:
            sys.exit(path + ' is not what scripts/gen_adler.py writes')
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


CASES = [(n, k, 1) for n in range(71) for k in range(4)]
CASES += [(n * 7 + 100, 0, 0) for n in range(21)]
for k in range(4):
    CASES += [(1048575, k, 1), (1048576, k, 1), (1048577, k, 1), (1048576 + 8, k, 65521 * 65536 - 1),
              (2097152 + 13, k, 1), (3000001, k, 12345 + 678 * 65536)]

PROGRAM = "program adler;\n\n{ P532: Adler-32 of data made from a seed, for lengths around every boundary of the eight-byte step and of the mebibyte between reductions, from the start value 1 and from others }\n\nuses\n  sysutils, pashash;\n\nvar\n  seed: Int64;\n\nfunction Rnd: Integer;\nbegin\n  seed := seed * 6364136223846793005 + 1442695040888963407;\n  Result := Integer((seed shr 33) and 255);\nend;\n\nfunction Data(n, kind: Integer): string;\nvar\n  i: Integer;\nbegin\n  SetLength(Result, n);\n  for i := 1 to n do\n    case kind of\n      0: Result[i] := Chr(Rnd);\n      1: Result[i] := Chr(255);\n      2: Result[i] := Chr(0);\n    else\n      Result[i] := Chr(97 + (i mod 7));\n    end;\nend;\n\nprocedure One(n, kind, start: Integer);\nvar\n  s: string;\nbegin\n  seed := 449 + n * 31 + kind;\n  s := Data(n, kind);\n  WriteLn(n, ' ', kind, ' ', start, ' ', PasAdler32(s, start));\nend;\n\nvar\n  n, k: Integer;\nbegin\n  for n := 0 to 70 do\n    for k := 0 to 3 do\n      One(n, k, 1);\n  for n := 0 to 20 do\n    One(n * 7 + 100, 0, 0);\n  for k := 0 to 3 do\n  begin\n    One(1048575, k, 1);\n    One(1048576, k, 1);\n    One(1048577, k, 1);\n    One(1048576 + 8, k, 65521 * 65536 - 1);\n    One(2097152 + 13, k, 1);\n    One(3000001, k, 12345 + 678 * 65536);\n  end;\nend.\n"


def expected():
    out = []
    for n, kind, start in CASES:
        d = data(n, kind, 449 + n * 31 + kind)
        out.append('%d %d %d %d\n' % (n, kind, start, zlib.adler32(d, start & 0xFFFFFFFF)))
    return ''.join(out)


emit(OUT + '.paslang', PROGRAM)
emit(OUT + '.out', expected())
