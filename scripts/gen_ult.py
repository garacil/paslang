#!/usr/bin/env python3
"""Writes testdata/ult.paslang and testdata/ult.out (P507): the order of
unsigned words written with the sign flipped, (x xor Low(Int64)) < (y xor
Low(Int64)), in every form the emitter turns into one compare and an
unsigned condition, and the forms that must keep their signed meaning.
The expected output is worked out here, from the unsigned order of the
values and from the signed order of the xored ones, not by the compiler.

usage: gen_ult.py [--check]    --check writes nothing and fails when the two
files in testdata are not what this script writes
"""
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata', 'ult')
CHECK = sys.argv[1:] == ['--check']


def emit(path, text):
    if CHECK:
        if open(path).read() != text:
            sys.exit(path + ' is not what scripts/gen_ult.py writes')
    else:
        open(path, 'w').write(text)


MASK = (1 << 64) - 1
def s64(x):
    x &= MASK
    return x - (1 << 64) if x >> 63 else x
# (source spelling, value)
V = [("0", 0), ("1", 1), ("2", 2), ("7", 7), ("4095", 4095), ("4096", 4096), ("65535", 65535),
     ("2147483647", 2147483647), ("2147483648", 2147483648), ("4294967296", 4294967296),
     ("4611686018427387904", 1 << 62), ("9223372036854775807", (1 << 63) - 1),
     ("Low(Int64)", 1 << 63), ("Low(Int64) + 1", (1 << 63) + 1), ("-2", MASK - 1), ("-1", MASK)]
K = [0, 1, 7, 4095, 4096, 2147483647, 2147483648, 4294967296, (1 << 63) - 1, 1 << 63, (1 << 63) + 1, MASK - 1, MASK]
def src(k):
    for t, v in V:
        if v == k:
            return t
    raise SystemExit('no spelling for %d' % k)

P = []
w = P.append
w("""{ ULt and its kin as one compare (P507): (x xor Low(Int64)) < (y xor
  Low(Int64)) is x below y as words of 64 bits without a sign, a CMP
  and an unsigned jump or set (jb, jbe, ja, jae on amd64; lo, ls, hi, hs
  on arm64), where the xors were two loads of the constant, two xors, the
  compare and a signed set. The forms below are tried on the boundary
  values in both orders: two variables, a variable and a constant on
  either side, a branch and a value, the condition kept and negated,
  loops, and ULt as a routine the inliner opens. Each answer is checked
  against RefLt, the same order written with no xor of the sign (Hacker's
  Delight 2-12: the sign of (not a and b) or (not (a xor b) and (a - b))),
  and the table of a below b is printed, which does not depend on the
  compiler. }
program ult;

const
  M = Low(Int64);

var
  V: array[0..15] of Int64;
  bad, cells, i, j, n, steps: Int64;
  row: string;

{ the forms that are not the pattern keep their signed meaning: another
  constant, one side flipped and the other not }
function Other(a, b: Int64; Form: Int64): Boolean;
begin
  case Form of
    0: Result := (a xor 5) < (b xor 5);
    1: Result := (a xor M) < b;
    2: Result := a < (b xor M);
    3: Result := (a xor M) < (b xor 5);
    4: Result := (a xor 5) >= (b xor 5);
    5: Result := (a xor M) <= b;
    6: Result := a > (b xor M);
    7: Result := (a xor 5) < (b xor M);
    8: Result := (5 xor a) < (M xor b);
    9: Result := (M xor a) < (5 xor b);
    10: Result := (5 xor a) < (5 xor b);
    11: Result := (a xor M) = (b xor M);
    12: Result := (a xor M) <> (b xor M);
  else
    Result := (M xor a) = (M xor b);
  end;
end;

function RefLt(A, B: Int64): Boolean;
begin
  Result := ((not A and B) or (not (A xor B) and (A - B))) < 0;
end;

function ULt(A, B: Int64): Boolean;
begin
  Result := (A xor Low(Int64)) < (B xor Low(Int64));
end;

{ the answers the 24 forms must give for a and b: bit n for form n (the constants have the first 20) }
function Expect(A, B: Int64): Int64;
var
  lt, gt: Boolean;
begin
  lt := RefLt(A, B);
  gt := RefLt(B, A);
  Result := 0;
  if lt then Result := Result or 1;
  if not gt then Result := Result or 2;
  if gt then Result := Result or 4;
  if not lt then Result := Result or 8;
  if lt then Result := Result or 16;
  if not gt then Result := Result or 32;
  if gt then Result := Result or 64;
  if not lt then Result := Result or 128;
  if gt then Result := Result or 256;
  if not lt then Result := Result or 512;
  if lt then Result := Result or 1024;
  if not gt then Result := Result or 2048;
  if gt then Result := Result or 4096;
  if not lt then Result := Result or 8192;
  if lt then Result := Result or 16384;
  if not gt then Result := Result or 32768;
  if not lt then Result := Result or 65536;
  if not lt then Result := Result or 131072;
  if lt then Result := Result or 1048576;
  if not gt then Result := Result or 2097152;
  if gt then Result := Result or 4194304;
  if not lt then Result := Result or 8388608;
  Result := Result or 262144 or 524288;
end;

procedure Check(Got, Want, A, B: Int64);
begin
  if Got <> Want then
  begin
    Inc(bad);
    WriteLn('differs: ', A, ' ', B, ' got ', Got, ' want ', Want);
  end;
end;

{ two variables }
procedure Vars(a, b: Int64);
var
  c: Int64;
  t: Boolean;
begin
  c := 0;
  if (a xor M) < (b xor M) then c := c or 1;
  if (a xor M) <= (b xor M) then c := c or 2;
  if (a xor M) > (b xor M) then c := c or 4;
  if (a xor M) >= (b xor M) then c := c or 8;
  t := (a xor M) < (b xor M);
  if t then c := c or 16;
  t := (a xor M) <= (b xor M);
  if t then c := c or 32;
  t := (a xor M) > (b xor M);
  if t then c := c or 64;
  t := (a xor M) >= (b xor M);
  if t then c := c or 128;
  if (b xor M) < (a xor M) then c := c or 256;
  if (b xor M) <= (a xor M) then c := c or 512;
  if (b xor M) > (a xor M) then c := c or 1024;
  if (b xor M) >= (a xor M) then c := c or 2048;
  t := (b xor M) < (a xor M);
  if t then c := c or 4096;
  t := (b xor M) <= (a xor M);
  if t then c := c or 8192;
  t := (b xor M) > (a xor M);
  if t then c := c or 16384;
  t := (b xor M) >= (a xor M);
  if t then c := c or 32768;
  if not ((a xor M) < (b xor M)) then c := c or 65536;
  if (a xor M) < (b xor M) then
    c := c or 0
  else
    c := c or 131072;
  if ULt(a, b) = ((a xor M) < (b xor M)) then c := c or 262144;
  if Ord(ULt(a, b)) = Ord((a xor M) < (b xor M)) then c := c or 524288;
  { the sign written first in the xor, on either side }
  if (M xor a) < (M xor b) then c := c or 1048576;
  t := (M xor a) <= (M xor b);
  if t then c := c or 2097152;
  if (a xor M) > (M xor b) then c := c or 4194304;
  t := (M xor a) >= (b xor M);
  if t then c := c or 8388608;
  Check(c, Expect(a, b), a, b);
end;
""")
# constant forms: Expect for the left-constant forms uses (K, a), so one
# procedure per constant shape: a against K (variable on the left) and K
# against a (constant on the left)
w("""
{ a variable and a constant, the constant xored once by the compiler }
procedure Consts(a: Int64);
var
  c: Int64;
  t: Boolean;
begin""")
for k in K:
    s = src(k)
    w("  c := 0;")
    ks = "(%s xor M)" % s
    for n, op in enumerate(["<", "<=", ">", ">="]):
        w("  if (a xor M) %s %s then c := c or %d;" % (op, ks, 1 << n))
    for n, op in enumerate(["<", "<=", ">", ">="]):
        w("  t := (a xor M) %s %s;" % (op, ks))
        w("  if t then c := c or %d;" % (1 << (n + 4)))
    for n, op in enumerate(["<", "<=", ">", ">="]):
        w("  if %s %s (a xor M) then c := c or %d;" % (ks, op, 1 << (n + 8)))
    for n, op in enumerate(["<", "<=", ">", ">="]):
        w("  t := %s %s (a xor M);" % (ks, op))
        w("  if t then c := c or %d;" % (1 << (n + 12)))
    w("  if not ((a xor M) < %s) then c := c or 65536;" % ks)
    w("  if (a xor M) < %s then" % ks)
    w("    c := c or 0")
    w("  else")
    w("    c := c or 131072;")
    w("  if ULt(a, %s) = RefLt(a, %s) then c := c or 262144;" % (s, s))
    w("  if Ord(ULt(%s, a)) = Ord(RefLt(%s, a)) then c := c or 524288;" % (s, s))
    w("  Check(c, Expect(a, %s) and 1048575, a, %s);" % (s, s))
w("""end;
""")
w("""{ the order in loops: i counts up to n below it as words }
function CountUp(n: Int64): Int64;
var
  i: Int64;
begin
  i := 0;
  while (i xor M) < (n xor M) do
    Inc(i);
  Result := i;
end;

function CountRepeat(n: Int64): Int64;
var
  i: Int64;
begin
  i := 0;
  repeat
    Inc(i);
  until (i xor M) >= (n xor M);
  Result := i;
end;

function CountConst: Int64;
var
  i: Int64;
begin
  i := 0;
  while (i xor M) < (100 xor M) do
    Inc(i);
  Result := i;
end;

begin""")
for t, v in V:
    pass
w("  " + "\n  ".join("V[%d] := %s;" % (n, t) for n, (t, v) in enumerate(V)))
w("""  bad := 0;
  cells := 0;
  for i := 0 to 15 do
  begin
    row := '';
    for j := 0 to 15 do
    begin
      Vars(V[i], V[j]);
      if (V[i] xor M) < (V[j] xor M) then
      begin
        row := row + '1';
        Inc(cells);
      end
      else
        row := row + '0';
    end;
    Consts(V[i]);
    WriteLn(row);
  end;
  for n := 0 to 13 do
    for i := 0 to 15 do
    begin
      row := '';
      for j := 0 to 15 do
        if Other(V[i], V[j], n) then
          row := row + '1'
        else
          row := row + '0';
      WriteLn(row);
    end;
  steps := CountUp(300) + CountRepeat(1000) + CountConst;
  WriteLn('below ', cells);
  WriteLn('loops ', steps);
  WriteLn('mismatches ', bad);
end.

{ This file is part of paslang's tests.
  Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
  paslang is free software under the GNU General Public License,
  version 3 or (at your option) any later version; see the file
  COPYING. It comes with ABSOLUTELY NO WARRANTY. }
""")
emit(OUT + '.paslang', "\n".join(P))
vals = [v for t, v in V]
o = []
cells = 0
for a in vals:
    r = ''
    for b in vals:
        if a < b:
            r += '1'; cells += 1
        else:
            r += '0'
    o.append(r)
for form in range(14):
    for a in vals:
        r = ''
        for b in vals:
            sa, sb = s64(a), s64(b)
            x = {0: (s64(a ^ 5), s64(b ^ 5), '<'), 1: (s64(a ^ (1 << 63)), sb, '<'), 2: (sa, s64(b ^ (1 << 63)), '<'),
                 3: (s64(a ^ (1 << 63)), s64(b ^ 5), '<'), 4: (s64(a ^ 5), s64(b ^ 5), '>='),
                 5: (s64(a ^ (1 << 63)), sb, '<='), 6: (sa, s64(b ^ (1 << 63)), '>'),
                 7: (s64(a ^ 5), s64(b ^ (1 << 63)), '<'),
                 8: (s64(a ^ 5), s64(b ^ (1 << 63)), '<'), 9: (s64(a ^ (1 << 63)), s64(b ^ 5), '<'),
                 10: (s64(a ^ 5), s64(b ^ 5), '<'), 11: (s64(a ^ (1 << 63)), s64(b ^ (1 << 63)), '='),
                 12: (s64(a ^ (1 << 63)), s64(b ^ (1 << 63)), '<>'),
                 13: (s64(a ^ (1 << 63)), s64(b ^ (1 << 63)), '=')}[form]
            l, rr, op = x
            v = {'<': l < rr, '>=': l >= rr, '<=': l <= rr, '>': l > rr, '=': l == rr, '<>': l != rr}[op]
            r += '1' if v else '0'
        o.append(r)
o.append('below %d' % cells)
o.append('loops %d' % (300 + 1000 + 100))
o.append('mismatches 0')
emit(OUT + '.out', "\n".join(o) + "\n")
