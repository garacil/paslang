#!/usr/bin/env python3
"""Writes testdata/outw.paslang and testdata/outw.out (P535): writes to var and out
parameters of every width and kind, with the value worked out in the pool (X := A * 3 + B),
read back from the parameter itself (X := X + A), taken from a call, written twice in
one routine, in a loop, and through a second routine that was given the parameter. The
expected output is worked out here with Python integers wrapped to each type's width, not
by the compiler.

usage: gen_outw.py [--check]    --check writes nothing and fails when the two files in
testdata are not what this script writes
"""
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata', 'outw')
CHECK = sys.argv[1:] == ['--check']

# name, bits, signed, the pairs (A, B) and starting values in range
TYPES = [('Byte', 8, False), ('Int8', 8, True), ('Word', 16, False), ('Int16', 16, True),
         ('UInt32', 32, False), ('Int32', 32, True), ('Integer', 64, True), ('Int64', 64, True)]


def emit(path, text):
    if CHECK:
        if open(path).read() != text:
            sys.exit(path + ' is not what scripts/gen_outw.py writes')
    else:
        open(path, 'w').write(text)


def wrap(v, bits, signed):
    v &= (1 << bits) - 1
    if signed and v >> (bits - 1):
        v -= 1 << bits
    return v


def pairs(bits, signed):
    lo = -(1 << (bits - 1)) if signed else 0
    hi = (1 << (bits - 1)) - 1 if signed else (1 << bits) - 1
    pts = [lo, lo + 1, -1 if signed else 1, 0, 1, 2, 7, hi // 3, hi // 2, hi - 1, hi]
    out = []
    for i, a in enumerate(pts):
        out.append((a, pts[(i * 5 + 3) % len(pts)]))
    return out


def lit(v, t):
    if v < 0:
        return '%s(%d)' % (t, v) if v != -(1 << 63) else '-9223372036854775807 - 1'
    return str(v)


prog = []
exp = []
call = []
prog.append('''program outw;

{ P535: writes to var and out parameters, every width and kind }

uses
  sysutils;

type
  TColor = (cRed, cGreen, cBlue, cWhite);
  PInt = ^Integer;

var
  gtotal: Integer;

''')
for (t, bits, signed) in TYPES:
    n = t
    prog.append('''function Mix%(n)s(A: %(t)s): %(t)s;
begin
  Result := A * 5 + 1;
end;

procedure Set%(n)s(A, B: %(t)s; out X: %(t)s);
begin
  X := A * 3 + B;
end;

procedure Inc%(n)s(var X: %(t)s; A: %(t)s);
begin
  X := X + A;
end;

procedure Call%(n)s(A, B: %(t)s; out X: %(t)s);
begin
  X := Mix%(n)s(A) + B;
end;

procedure Two%(n)s(A, B: %(t)s; out X, Y: %(t)s);
begin
  X := A + B;
  Y := A - B;
end;

procedure Loop%(n)s(var X: %(t)s; A: %(t)s);
var
  i: Integer;
begin
  for i := 1 to 4 do
    X := X + A;
end;

procedure Pass%(n)s(var X: %(t)s; A: %(t)s);
begin
  Inc%(n)s(X, A);
  Inc%(n)s(X, A);
end;

procedure Fill%(n)s(A: %(t)s; out X: %(t)s);
var
  i: Integer;
begin
  for i := 1 to 4 do
    X := A * 3 + %(t)s(i);
end;

procedure Wide%(n)s(A: %(t)s; out X: Integer);
begin
  X := A;
end;

procedure Conv%(n)s(A: Integer; out X: %(t)s);
begin
  X := %(t)s(A * 3);
end;

procedure Run%(n)s;
var
  x, y, z: %(t)s;
  cells: array[0..3] of %(t)s;
  w: Integer;
begin
''' % {'n': n, 't': t})
    for (a, b) in pairs(bits, signed):
        A, B = lit(a, t), lit(b, t)
        prog.append('''  x := %(A)s;
  y := %(B)s;
  Set%(n)s(x, y, z);
  WriteLn(z);
  Inc%(n)s(z, x);
  WriteLn(z);
  Call%(n)s(x, y, z);
  WriteLn(z);
  Two%(n)s(x, y, x, y);
  WriteLn(x, ' ', y);
  z := %(B)s;
  Loop%(n)s(z, %(A)s);
  WriteLn(z);
  Pass%(n)s(z, %(B)s);
  WriteLn(z);
  cells[0] := 11;
  cells[1] := 22;
  cells[2] := 33;
  cells[3] := 44;
  x := %(A)s;
  y := %(B)s;
  Set%(n)s(x, y, cells[2]);
  Inc%(n)s(cells[1], x);
  WriteLn(cells[0], ' ', cells[1], ' ', cells[2], ' ', cells[3]);
  Fill%(n)s(x, z);
  WriteLn(z);
  Wide%(n)s(x, w);
  WriteLn(w);
  Conv%(n)s(w, z);
  WriteLn(z);
''' % {'n': n, 'A': A, 'B': B})
        w = lambda v: wrap(v, bits, signed)
        mix = lambda v: w(v * 5 + 1)
        z = w(a * 3 + b)
        exp.append('%d\n' % z)
        z = w(z + a)
        exp.append('%d\n' % z)
        z = w(mix(a) + b)
        exp.append('%d\n' % z)
        x2, y2 = w(a + b), w(a - b)
        exp.append('%d %d\n' % (x2, y2))
        z = b
        z = w(z + 4 * a)
        exp.append('%d\n' % z)
        z = w(z + 2 * b)
        exp.append('%d\n' % z)
        exp.append('11 %d %d 44\n' % (w(22 + a), w(a * 3 + b)))
        exp.append('%d\n' % w(a * 3 + 4))
        exp.append('%d\n' % a)
        exp.append('%d\n' % w(a * 3))
    prog.append('end;\n\n')
    call.append('  Run%s;\n' % n)

# kinds with no arithmetic of their own
prog.append('''procedure SetBool(A, B: Integer; out X: Boolean);
begin
  X := A > B;
end;

procedure SetChar(A: Integer; out X: Char);
begin
  X := Chr(65 + A);
end;

procedure SetReal(A: Integer; out X: Double);
begin
  X := A * 1.5;
end;

procedure SetSingle(A: Integer; out X: Single);
begin
  X := A * 0.5;
end;

procedure SetColor(A: Integer; out X: TColor);
begin
  if A > 2 then
    X := cBlue
  else
    X := cRed;
end;

procedure SetStr(A: Integer; out X: string);
begin
  X := 'n=' + IntToStr(A);
end;

procedure SetPtr(var V: Integer; out X: PInt);
begin
  X := @V;
end;

procedure BumpRef(P: PInt; var X: Integer);
begin
  X := P^ + 1;
end;

procedure NestOuter(var X: Integer; A: Integer);
  procedure Inner;
  begin
    X := A * 2 + 1;
  end;
begin
  Inner;
  Inner;
end;

procedure Kinds;
var
  b: Boolean;
  c: Char;
  d: Double;
  s: Single;
  col: TColor;
  txt: string;
  p: PInt;
  v, w: Integer;
  i: Integer;
begin
  for i := 1 to 4 do
  begin
    SetBool(i, 2, b);
    WriteLn(b);
    SetChar(i, c);
    WriteLn(c);
    SetReal(i, d);
    WriteLn(d);
    SetSingle(i, s);
    WriteLn(s);
    SetColor(i, col);
    WriteLn(Ord(col));
    SetStr(i, txt);
    WriteLn(txt);
    v := i * 11;
    SetPtr(v, p);
    BumpRef(p, w);
    WriteLn(w);
    NestOuter(w, i);
    WriteLn(w);
  end;
end;

''')
call.append('  Kinds;\n')
for i in range(1, 5):
    exp.append('%s\n' % ('1' if i > 2 else '0'))
    exp.append('%s\n' % chr(65 + i))
    exp.append('%s\n' % repr(i * 1.5))
    exp.append('%s\n' % repr(i * 0.5))
    exp.append('%d\n' % (2 if i > 2 else 0))
    exp.append('n=%d\n' % i)
    exp.append('%d\n' % (i * 11 + 1))
    exp.append('%d\n' % (i * 2 + 1))
prog.append('begin\n' + ''.join(call) + 'end.\n')
emit(OUT + '.paslang', ''.join(prog))
emit(OUT + '.out', ''.join(exp))
