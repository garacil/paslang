#!/usr/bin/env python3
"""Writes testdata/dloop.paslang and testdata/dloop.out (P531): small leaf routines whose
Double variables a loop works on (Horner's rule with a product and a sum and with Fma,
sums, Newton's square root, a halving while, the logistic map, a mix of integer and
Double, routines of seven and of three Doubles, a Double parameter changed in the loop,
a Result worked in the loop). They are the routines that had no frame and kept their
Doubles in general registers; each now has a frame and its Doubles in xmm registers
whenever a loop is in it. Each result is printed as the 64 bits of the Double. The
expected output is worked out here with Python floats (IEEE double, the same
operations in the same order, math.fma for Fma), not by the compiler.

usage: gen_dloop.py [--check]    --check writes nothing and fails when the two
files in testdata are not what this script writes
"""
import math
import os
import struct
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata', 'dloop')
CHECK = sys.argv[1:] == ['--check']


def emit(path, text):
    if CHECK:
        if open(path).read() != text:
            sys.exit(path + ' is not what scripts/gen_dloop.py writes')
    else:
        open(path, 'w').write(text)


def bits(d):
    return struct.unpack('<q', struct.pack('<d', d))[0]


def fma(a, b, c):
    return math.fma(a, b, c)


# name, parameters, locals, body (Pascal), python function of the arguments
R = []


def routine(name, params, locs, body, fn):
    R.append((name, params, locs, body, fn))


def h_plain(x, y):
    r = 0.0
    for i in range(1, 17):
        r = r * x + float(i)
    return r


routine('HornerPlain', 'x, y: Double', 'r: Double; i: Integer;', """  r := 0.0;
  for i := 1 to 16 do
    r := r * x + i;
  Result := r;""", h_plain)


def h_fma(x, y):
    r = 0.0
    for i in range(1, 17):
        r = fma(r, x, float(i))
    return r


routine('HornerFma', 'x, y: Double', 'r: Double; i: Integer;', """  r := 0.0;
  for i := 1 to 16 do
    r := Fma(r, x, i);
  Result := r;""", h_fma)


def h_res(x, y):
    r = 1.0
    for i in range(1, 9):
        r = r * x + y
    return r


routine('ResultLoop', 'x, y: Double', 'i: Integer;', """  Result := 1.0;
  for i := 1 to 8 do
    Result := Result * x + y;""", h_res)


def h_sum(x, y):
    s = 0.0
    for i in range(1, 101):
        s = s + x * i
    return s


routine('SumLoop', 'x, y: Double', 's: Double; i: Integer;', """  s := 0.0;
  for i := 1 to 100 do
    s := s + x * i;
  Result := s;""", h_sum)


def h_newton(x, y):
    z = x if x > 1.0 else 1.0
    for _ in range(12):
        z = (z + x / z) / 2.0
    return z


routine('Newton', 'x, y: Double', 'z: Double; k: Integer;', """  if x > 1.0 then
    z := x
  else
    z := 1.0;
  for k := 1 to 12 do
    z := (z + x / z) / 2.0;
  Result := z;""", h_newton)


def h_while(x, y):
    z = abs(x) + 1.0
    n = 0.0
    while z > 1.0:
        z = z * 0.5
        n = n + 1.0
    return z + n


routine('Halve', 'x, y: Double', 'z, n: Double;', """  z := Abs(x) + 1.0;
  n := 0.0;
  while z > 1.0 do
  begin
    z := z * 0.5;
    n := n + 1.0;
  end;
  Result := z + n;""", h_while)


def h_logistic(x, y):
    a = 0.3
    b = 0.0
    r = 3.7
    for _ in range(40):
        a = r * a * (1.0 - a)
        b = b + a
    return a + b * 0.001 + x * 0.0


routine('Logistic', 'x, y: Double', 'a, b, r: Double; k: Integer;', """  a := 0.3;
  b := 0.0;
  r := 3.7;
  for k := 1 to 40 do
  begin
    a := r * a * (1.0 - a);
    b := b + a;
  end;
  Result := a + b * 0.001 + x * 0.0;""", h_logistic)


def h_mixed(x, y):
    t = 0.0
    for i in range(1, 61):
        t = t + i / 7.0
        if t > 50.0:
            t = t - 50.0
    return t + x


routine('Mixed', 'x, y: Double', 't: Double; i: Integer;', """  t := 0.0;
  for i := 1 to 60 do
  begin
    t := t + i / 7.0;
    if t > 50.0 then
      t := t - 50.0;
  end;
  Result := t + x;""", h_mixed)


def h_seven(x, y):
    a, b, c, d, e, f, g = 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0
    for _ in range(20):
        a = a * 0.5 + b * 0.25
        b = b + c * 0.125
        c = c - d * 0.0625
        d = d * 0.75 + e
        e = e + f * 0.5 - g * 0.125
        f = f * 0.9 + a
        g = g + (a - b) * 0.01 + x * 0.001
    return a + b + c + d + e + f + g


routine('Seven', 'x, y: Double', 'a, b, c, d, e, f, g: Double; k: Integer;', """  a := 1.0; b := 2.0; c := 3.0; d := 4.0; e := 5.0; f := 6.0; g := 7.0;
  for k := 1 to 20 do
  begin
    a := a * 0.5 + b * 0.25;
    b := b + c * 0.125;
    c := c - d * 0.0625;
    d := d * 0.75 + e;
    e := e + f * 0.5 - g * 0.125;
    f := f * 0.9 + a;
    g := g + (a - b) * 0.01 + x * 0.001;
  end;
  Result := a + b + c + d + e + f + g;""", h_seven)


def h_param(x, y):
    for _ in range(10):
        x = x * y + 1.0
        if x > 1000.0:
            x = x / 1000.0
    return x


routine('ParamLoop', 'x, y: Double', 'k: Integer;', """  for k := 1 to 10 do
  begin
    x := x * y + 1.0;
    if x > 1000.0 then
      x := x / 1000.0;
  end;
  Result := x;""", h_param)


def h_two(x, y):
    p = 1.0
    q = 0.0
    for i in range(1, 31):
        p = p * (1.0 + x / (i + 10.0))
        q = q + p / (i + y * 0.0 + 1.0)
    return q


routine('TwoStates', 'x, y: Double', 'p, q: Double; i: Integer;', """  p := 1.0;
  q := 0.0;
  for i := 1 to 30 do
  begin
    p := p * (1.0 + x / (i + 10.0));
    q := q + p / (i + y * 0.0 + 1.0);
  end;
  Result := q;""", h_two)


def h_repeat(x, y):
    z = x * x
    n = 0
    while True:
        z = z * 0.9 + 0.1
        n += 1
        if z < 0.2 or n >= 50:
            break
    return z + n


routine('RepeatLoop', 'x, y: Double', 'z: Double; n: Integer;', """  z := x * x;
  n := 0;
  repeat
    z := z * 0.9 + 0.1;
    n := n + 1;
  until (z < 0.2) or (n >= 50);
  Result := z + n;""", h_repeat)


def h_dcount(x, y):
    s = 0.0
    t = x
    while t < y:
        s = s + t
        t = t + 0.5
    return s


routine('DoubleCount', 'x, y: Double', 's, t: Double;', """  s := 0.0;
  t := x;
  while t < y do
  begin
    s := s + t;
    t := t + 0.5;
  end;
  Result := s;""", h_dcount)


def h_noloop(x, y):
    return x * y + 1.0


routine('NoLoop', 'x, y: Double', 'z: Double;', """  z := x * y;
  Result := z + 1.0;""", h_noloop)

INPUTS = [(0.5, 1.25), (1.0, 1.0), (1.5, -0.75), (-2.25, 0.5), (3.1415926, 2.7182818), (0.001, 100.0), (123456.789, 0.0001), (0.0, 0.0), (-0.0, 3.0), (2.0, 1.0001), (10.0, 0.5), (0.75, -1.5)]


def lit(v):
    if v == 0.0 and math.copysign(1.0, v) < 0:
        return '(-0.0)'
    s = repr(v)
    return s if v >= 0 else '(' + s + ')'


def main():
    P = ["""program dloop;

{ Small leaf routines whose Doubles a loop works on (P531): each had no
  frame and kept its Doubles in general registers; with a loop in it each
  has a frame and its Doubles in xmm registers. The 64 bits of every result
  are what scripts/gen_dloop.py works out with Python floats. }

function Bits(d: Double): Int64;
begin
  Result := d as Int64;
end;
"""]
    X = []
    for name, params, locs, body, fn in R:
        P.append('function %s(%s): Double;' % (name, params))
        P.append('var')
        P.append('  ' + locs)
        P.append('begin')
        P.append(body)
        P.append('end;')
        P.append('')
    P.append('begin')
    for name, params, locs, body, fn in R:
        for x, y in INPUTS:
            P.append("  WriteLn('%s %s %s ', Bits(%s(%s, %s)));" % (name, repr(x), repr(y), name, lit(x), lit(y)))
            X.append('%s %s %s %d\n' % (name, repr(x), repr(y), bits(fn(x, y))))
    P.append('end.')
    return '\n'.join(P) + '\n', ''.join(X)


prog, out = main()
emit(OUT + '.paslang', prog)
emit(OUT + '.out', out)
