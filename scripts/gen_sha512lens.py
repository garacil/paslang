#!/usr/bin/env python3
"""Writes testdata/sha512lens.paslang and testdata/sha512lens.out (P551): SHA-384 and SHA-512, and
the HMAC of both under a 20-byte key, of data made from a seed (random bytes, all 255, all 0, a
short period) for every length from 0 to 300, which takes every padding case of the last block
(111, 112, 119, 127, 128, 129, 239, 240, 255, 256 and 257), and for 1000, 4095, 4096, 65535, 65536
and 1048576 bytes. The expected output is hashlib's sha384 and sha512 and hmac of the same data
(made here by the same generator), not the compiler's.

usage: gen_sha512lens.py [--check]    --check writes nothing and fails when the two
files in testdata are not what this script writes
"""
import hashlib
import hmac
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata', 'sha512lens')
CHECK = sys.argv[1:] == ['--check']
M = (1 << 64) - 1
KEY = bytes(range(1, 21))


def emit(path, text):
    if CHECK:
        if open(path).read() != text:
            sys.exit(path + ' is not what scripts/gen_sha512lens.py writes')
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


CASES = [(n, k) for n in range(301) for k in range(4)]
for n in (1000, 4095, 4096, 65535, 65536, 1048576):
    CASES += [(n, 0), (n, 3)]

PROGRAM = "program sha512lens;\n\n{ P551: SHA-384 and SHA-512, and the HMAC of both under a key of 20 bytes, of data made from a seed, for every length from 0 to 300 (every padding case of the last block) and for some longer ones }\n\nuses\n  sysutils;\n\nvar\n  seed: Int64;\n\nfunction Rnd: Integer;\nbegin\n  seed := seed * 6364136223846793005 + 1442695040888963407;\n  Result := Integer((seed shr 33) and 255);\nend;\n\nfunction Data(n, kind: Integer): string;\nvar\n  i: Integer;\nbegin\n  SetLength(Result, n);\n  for i := 1 to n do\n    case kind of\n      0: Result[i] := Chr(Rnd);\n      1: Result[i] := Chr(255);\n      2: Result[i] := Chr(0);\n    else\n      Result[i] := Chr(97 + (i mod 7));\n    end;\nend;\n\nprocedure One(n, kind: Integer);\nvar\n  s, key: string;\n  i: Integer;\nbegin\n  seed := 551 + n * 31 + kind;\n  s := Data(n, kind);\n  SetLength(key, 20);\n  for i := 1 to 20 do\n    key[i] := Chr(i);\n  WriteLn(n, ' ', kind, ' ', Hex(Sha384(s)), ' ', Hex(Sha512(s)), ' ', Hex(HmacSha384(key, s)), ' ', Hex(HmacSha512(key, s)));\nend;\n\nconst\n  Big: array[0..5] of Integer = (1000, 4095, 4096, 65535, 65536, 1048576);\n\nvar\n  n, k: Integer;\nbegin\n  for n := 0 to 300 do\n    for k := 0 to 3 do\n      One(n, k);\n  for k := 0 to 5 do\n  begin\n    One(Big[k], 0);\n    One(Big[k], 3);\n  end;\nend.\n"


def expected():
    out = []
    for n, kind in CASES:
        d = data(n, kind, 551 + n * 31 + kind)
        out.append('%d %d %s %s %s %s\n' % (n, kind, hashlib.sha384(d).hexdigest(), hashlib.sha512(d).hexdigest(),
                                          hmac.new(KEY, d, hashlib.sha384).hexdigest(), hmac.new(KEY, d, hashlib.sha512).hexdigest()))
    return ''.join(out)


emit(OUT + '.paslang', PROGRAM)
emit(OUT + '.out', expected())
