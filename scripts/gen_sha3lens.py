#!/usr/bin/env python3
"""Writes testdata/sha3lens.paslang and testdata/sha3lens.out (P550): SHA3-224, SHA3-256, SHA3-384 and
SHA3-512 of data made from a seed (random bytes, all 255, all 0, a short period) for every length
from 0 to 150 (which takes every padding case of the last block of each: rates of 144, 136, 104 and
72 bytes, one byte short of full, full and one over) and for 1000, 4095, 4096 and 65536 bytes. The
expected output is hashlib's sha3_224 to sha3_512 of the same data (made here by the same generator),
not the compiler's.

usage: gen_sha3lens.py [--check]    --check writes nothing and fails when the two
files in testdata are not what this script writes
"""
import hashlib
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata', 'sha3lens')
CHECK = sys.argv[1:] == ['--check']
M = (1 << 64) - 1


def emit(path, text):
    if CHECK:
        if open(path).read() != text:
            sys.exit(path + ' is not what scripts/gen_sha3lens.py writes')
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


CASES = [(n, k) for n in range(151) for k in range(4)]
for n in (1000, 4095, 4096, 65536):
    CASES += [(n, 0), (n, 3)]

PROGRAM = "program sha3lens;\n\n{ P550: SHA3-224, SHA3-256, SHA3-384 and SHA3-512 of data made from a seed, for every length from 0 to 150 (every padding case of the last block of each) and for some longer ones }\n\nuses\n  sysutils;\n\nvar\n  seed: Int64;\n\nfunction Rnd: Integer;\nbegin\n  seed := seed * 6364136223846793005 + 1442695040888963407;\n  Result := Integer((seed shr 33) and 255);\nend;\n\nfunction Data(n, kind: Integer): string;\nvar\n  i: Integer;\nbegin\n  SetLength(Result, n);\n  for i := 1 to n do\n    case kind of\n      0: Result[i] := Chr(Rnd);\n      1: Result[i] := Chr(255);\n      2: Result[i] := Chr(0);\n    else\n      Result[i] := Chr(97 + (i mod 7));\n    end;\nend;\n\nprocedure One(n, kind: Integer);\nvar\n  s: string;\nbegin\n  seed := 550 + n * 31 + kind;\n  s := Data(n, kind);\n  WriteLn(n, ' ', kind, ' ', Hex(Sha3_224(s)), ' ', Hex(Sha3_256(s)), ' ', Hex(Sha3_384(s)), ' ', Hex(Sha3_512(s)));\nend;\n\nconst\n  Big: array[0..3] of Integer = (1000, 4095, 4096, 65536);\n\nvar\n  n, k: Integer;\nbegin\n  for n := 0 to 150 do\n    for k := 0 to 3 do\n      One(n, k);\n  for k := 0 to 3 do\n  begin\n    One(Big[k], 0);\n    One(Big[k], 3);\n  end;\nend.\n"


def expected():
    out = []
    for n, kind in CASES:
        d = data(n, kind, 550 + n * 31 + kind)
        out.append('%d %d %s %s %s %s\n' % (n, kind, hashlib.sha3_224(d).hexdigest(), hashlib.sha3_256(d).hexdigest(),
                                          hashlib.sha3_384(d).hexdigest(), hashlib.sha3_512(d).hexdigest()))
    return ''.join(out)


emit(OUT + '.paslang', PROGRAM)
emit(OUT + '.out', expected())
