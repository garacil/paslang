#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""Writes testdata/signs.paslang and testdata/signs.out (P542): Abs and the
negation of a Double kept in the register file, sums and products with a
constant or a variable on the left worked out from the right operand, and
Horner chains of any depth. The program runs each routine on eight values
of each of its arguments and prints the 64 bits of every result; the
expected output is worked out in Python floats (IEEE binary64, the same
operations in the same order: the compiler fuses nothing).

usage: gen_signs.py [--check]    --check writes nothing and fails when the two
files in testdata are not what this script writes"""
import os
import struct
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata', 'signs')
CHECK = sys.argv[1:] == ['--check']
XS = [0.0, -0.0, 1.5, -2.25, 1e-310, 1e300, -1e300, 0.3333333333333333]
YS = [0.5, -1.0, 2.0, -0.0, 7.75, 1e-5, 100.0, -3.5]
NS = [0, 1, 2, 3, 5, 7, 9, 11]
C = [0.1, -0.7, 1.3, 2.9, -0.45, 0.06, -1.7, 3.3, 0.27, -0.81, 1.1, -2.2, 0.05]


def lit(v):
    r = repr(v)
    return '(%s)' % r if r.startswith('-') else r


def bits(v):
    return 'nan' if v != v else str(struct.unpack('<q', struct.pack('<d', v))[0])


def right(c, v):
    # c0 + v * (c1 + v * (c2 + ... + v * cn))
    s = lit(c[-1])
    for k in range(len(c) - 2, -1, -1):
        s = '%s + %s * (%s)' % (lit(c[k]), v, s) if k < len(c) - 2 else '%s + %s * %s' % (lit(c[k]), v, s)
    return s


def py_right(c, v):
    r = c[-1]
    for k in range(len(c) - 2, -1, -1):
        r = c[k] + v * r
    return r


def left(c, v):
    # ((cn * v + c(n-1)) * v + ...) * v + c0
    s = '%s * %s + %s' % (lit(c[-1]), v, lit(c[-2]))
    for k in range(len(c) - 3, -1, -1):
        s = '(%s) * %s + %s' % (s, v, lit(c[k]))
    return s


def py_left(c, v):
    r = c[-1] * v + c[-2]
    for k in range(len(c) - 3, -1, -1):
        r = r * v + c[k]
    return r


def py_hs8(x, y):
    return C[0] - x * (C[1] + y * (C[2] - x * (C[3] + y * (C[4] - x * (C[5] + y * (C[6] - x * C[7]))))))


def py_hx(x, y):
    return 2.5 * x * (y + 1.5) * (3.0 - y)


def py_ab(x, y):
    return abs(x) * y - abs(x - y)


def py_ng(x, y):
    return -(x * y) + -x * y


def py_lp(x, y):
    s = 0.0
    for i in range(1, 7):
        s = s + abs(x - i) * -y
        y = y * 0.5
    return s


def py_dv(x, y):
    return 1.0 / (x * x + 1.0) + y / (2.0 + x * x) - 3.5 / (y * y + 0.25)


def py_cm(x, y):
    return -x if abs(x) > abs(y) else -y


def py_sg(x, k):
    b = struct.unpack('<q', struct.pack('<d', x))[0]
    s = 0
    for t in (1, 2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31):
        if k == t:
            s = t & 1
    if k == 0:
        s = 1
    r = ((b & 0x7FFFFFFFFFFFFFFF) | (s << 63))
    r = r - (1 << 64) if r >= (1 << 63) else r
    return struct.unpack('<d', struct.pack('<q', r))[0]


def py_se(x, k):
    if k == 0:
        return x + x
    return -x


SRC = """program signs;

function Sg(x: Double; k: Integer): Double;
var
  b, s: Int64;
begin
  b := x as Int64;
  s := 0;
  if k = 1 then s := 1;
  if k = 2 then s := 0;
  if k = 3 then s := 1;
  if k = 5 then s := 1;
  if k = 7 then s := 1;
  if k = 11 then s := 1;
  if k = 13 then s := 1;
  if k = 17 then s := 1;
  if k = 19 then s := 1;
  if k = 23 then s := 1;
  if k = 29 then s := 1;
  if k = 31 then s := 1;
  if k = 0 then s := 1;
  Result := ((b and $7FFFFFFFFFFFFFFF) or (s shl 63)) as Double;
end;

function Se(x: Double; k: Integer): Double;
var
  b: Int64;
begin
  b := x as Int64;
  if k = 0 then
  begin
    Result := x + x;
    Exit;
  end;
  Result := (b xor $8000000000000000) as Double;
end;

function Dv(x, y: Double): Double;
begin
  Result := 1.0 / (x * x + 1.0) + y / (2.0 + x * x) - 3.5 / (y * y + 0.25);
end;

function Ab(x, y: Double): Double;
begin
  Result := Abs(x) * y - Abs(x - y);
end;

function Ng(x, y: Double): Double;
begin
  Result := -(x * y) + -x * y;
end;

function Hr(x: Double): Double;
begin
  Result := RIGHT;
end;

function Hl(x: Double): Double;
begin
  Result := LEFT;
end;

function Hs(x, y: Double): Double;
begin
  Result := 0.1 - x * ((-0.7) + y * (1.3 - x * (2.9 + y * ((-0.45) - x * (0.06 + y * ((-1.7) - x * 3.3))))));
end;

function Hx(x, y: Double): Double;
begin
  Result := 2.5 * x * (y + 1.5) * (3.0 - y);
end;

function Lp(x, y: Double): Double;
var
  i: Integer;
  s: Double;
begin
  s := 0.0;
  for i := 1 to 6 do
  begin
    s := s + Abs(x - i) * -y;
    y := y * 0.5;
  end;
  Result := s;
end;

function Cm(x, y: Double): Double;
begin
  if Abs(x) > Abs(y) then
    Result := -x
  else
    Result := -y;
end;

procedure P(r: Double);
var
  b: Int64;
begin
  if r <> r then
    WriteLn('nan')
  else
  begin
    b := r as Int64;
    WriteLn(b);
  end;
end;

begin
CALLS
end.
"""


def build():
    calls = []
    exp = []
    for x in XS:
        for k in NS:
            calls.append('  P(Sg(%s, %d));' % (lit(x), k))
            exp.append(bits(py_sg(x, k)))
            calls.append('  P(Se(%s, %d));' % (lit(x), k))
            exp.append(bits(py_se(x, k)))
    for x in XS:
        for y in YS:
            for name, fn in (('Ab', py_ab), ('Ng', py_ng), ('Hs', py_hs8), ('Hx', py_hx), ('Lp', py_lp), ('Cm', py_cm), ('Dv', py_dv)):
                calls.append('  P(%s(%s, %s));' % (name, lit(x), lit(y)))
                exp.append(bits(fn(x, y)))
    for x in XS:
        calls.append('  P(Hr(%s));' % lit(x))
        exp.append(bits(py_right(C, x)))
        calls.append('  P(Hl(%s));' % lit(x))
        exp.append(bits(py_left(C, x)))
    src = SRC.replace('RIGHT', right(C, 'x')).replace('LEFT', left(C, 'x')).replace('CALLS', '\n'.join(calls))
    return src, '\n'.join(exp) + '\n'


def emit(path, text):
    if CHECK:
        if open(path).read() != text:
            sys.exit(path + ' is not what scripts/gen_signs.py writes')
    else:
        open(path, 'w').write(text)


prog, exp = build()
emit(OUT + '.paslang', prog)
emit(OUT + '.out', exp)
