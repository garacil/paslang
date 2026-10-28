#!/usr/bin/env python3
"""P486: testdata/realregs.paslang, made by this script (seed 4860).

Functions of Double and Integer variables whose bodies are loops, ifs and
assignments of random real expressions: + - * / over variables, locals kept in
registers by a loop or not, constants, integers mixed in, comparisons of all six
kinds in if, while and repeat with their negations, expressions deeper than the
xmm registers go, Singles mixed with Doubles, fields and elements, a global.
Each function is called with a set of arguments that has zeros of both signs,
infinities and NaN, and the bits of its result are folded into a hash that the
program prints with the count of calls. The expected output is made by the
compiler before the change, so the two are shown equal.

    gen_realregs.py > testdata/realregs.paslang
"""
import random
import sys

R = random.Random(4860)
NV = ["a", "b", "c", "d"]
CONSTS = ["0.0", "1.0", "2.0", "0.5", "(-1.5)", "3.14159", "1e10", "1e-10", "100.25", "7.0"]


def real(depth, vs, allow_int=True):
    if depth == 0 or R.random() < 0.18:
        k = R.random()
        if k < 0.60:
            return R.choice(vs)
        if k < 0.80:
            return R.choice(CONSTS)
        if k < 0.90 and allow_int:
            return R.choice(["i", "j", "(i + j)", "(i * 3)"])
        return R.choice(vs)
    op = R.choice(["+", "-", "*", "/", "+", "-", "*"])
    return "(%s %s %s)" % (real(depth - 1, vs), op, real(depth - 1, vs))


def cond(vs, depth):
    op = R.choice(["<", "<=", ">", ">=", "=", "<>"])
    c = "(%s %s %s)" % (real(depth, vs), op, real(depth, vs))
    if R.random() < 0.25:
        c = "not " + c
    if R.random() < 0.2:
        c = "(%s and (i < 5))" % c
    if R.random() < 0.15:
        c = "(%s or (j > 3))" % c
    return c


def stmt(vs, depth, ind, inloop):
    pad = " " * ind
    k = R.random()
    if k < 0.45:
        return pad + "%s := %s;" % (R.choice(["a", "b", "c", "d", "t"]), real(depth, vs))
    if k < 0.60:
        return pad + "if %s then\n%s  %s := %s\n%selse\n%s  %s := %s;" % (
            cond(vs, depth - 1), pad, R.choice(["a", "b", "c", "t"]), real(depth, vs),
            pad, pad, R.choice(["b", "c", "d", "t"]), real(depth, vs))
    if k < 0.70:
        return pad + "i := i + 1;"
    if k < 0.80 and inloop:
        return pad + "if %s then Break;" % cond(vs, 1)
    if k < 0.90:
        return pad + "s := s + %s;" % real(depth, vs)
    return pad + "if %s then x := x + 1;" % cond(vs, 1)


def func(n):
    vs = list(NV) + ["t", "s"]
    depth = R.randint(1, 5)
    lines = []
    lines.append("function F%d(a, b, c, d: Double; i, j: Integer): Double;" % n)
    lines.append("var")
    lines.append("  t, s: Double;")
    lines.append("  k, x: Integer;")
    lines.append("begin")
    lines.append("  t := %s;" % real(2, NV))
    lines.append("  s := 0.0;")
    lines.append("  x := 0;")
    kind = R.choice(["for", "while", "repeat", "plain", "for", "while"])
    body = [stmt(vs, depth, 4, kind != "plain") for _ in range(R.randint(2, 6))]
    if kind == "for":
        lines.append("  for k := 1 to %d do" % R.randint(2, 9))
        lines.append("  begin")
        lines += body
        lines.append("  end;")
    elif kind == "while":
        lines.append("  k := 0;")
        lines.append("  while (k < %d) and %s do" % (R.randint(2, 9), cond(vs, 1)))
        lines.append("  begin")
        lines += body
        lines.append("    k := k + 1;")
        lines.append("  end;")
    elif kind == "repeat":
        lines.append("  k := 0;")
        lines.append("  repeat")
        lines += body
        lines.append("    k := k + 1;")
        lines.append("  until (k >= %d) or %s;" % (R.randint(2, 9), cond(vs, 1)))
    else:
        lines += [b[2:] for b in body]
    lines.append("  Result := %s + s + x;" % real(2, vs))
    lines.append("end;")
    return "\n".join(lines)


N = 120
out = []
out.append("{ P486: real expressions worked out in the xmm registers and Doubles kept in them by a")
out.append("  loop. Made by scripts/gen_realregs.py (seed 4860): %d functions of random loops, ifs and" % N)
out.append("  expressions of Doubles and Integers, each called with arguments that include zeros of both")
out.append("  signs, infinities and a NaN; the bits of every result are folded into a hash. The expected")
out.append("  output was made by the compiler before the change. }")
out.append("program realregs;")
out.append("")
out.append("type")
out.append("  TRec = record")
out.append("    p, q: Double;")
out.append("    n: Integer;")
out.append("  end;")
out.append("")
out.append("var")
out.append("  h: Int64;")
out.append("  calls: Integer;")
out.append("  gd: Double;")
out.append("  ga: array[0..3] of Double;")
out.append("  rec: TRec;")
out.append("")
for n in range(N):
    out.append(func(n))
    out.append("")
out.append("""function TryLoop(a: Double; n: Integer): Double;
var
  s, t: Double;
  i, z: Integer;
begin
  s := 1.0;
  t := a;
  z := 3;
  try
    for i := 0 to n do
    begin
      s := s * 1.5 + t;
      t := t - 0.25;
      z := z - 1;
      i := i + 10 div z;
    end;
  except
    s := s + 1000.0 + t;
  end;
  Result := s + t;
end;

procedure Mix(X: Double);
var
  b: Int64;
begin
  b := 0;
  Move(X, b, 8);
  if X <> X then
    b := 7;
  h := (h * 1000003 + b) xor (h shr 29);
  calls := calls + 1;
end;

function Shapes(a, b: Double; i: Integer; f: Single): Double;
var
  s: Single;
  t: Double;
begin
  s := f;
  t := a * s + b / s - i * a;
  gd := t * 2.0 + gd;
  ga[i and 3] := ga[i and 3] + t;
  rec.p := rec.p * a + b;
  rec.q := rec.q - rec.p / 3.0;
  rec.n := rec.n + i;
  if (a < b) = (t > gd) then
    t := t + 1.0;
  Result := t + gd + ga[i and 3] + rec.p - rec.q + rec.n;
end;

var
  args: array[0..9] of Double;
  ai, aj, ak, al, i, j: Integer;
begin
  args[0] := 0.0;
  args[1] := -0.0;
  args[2] := 1.0;
  args[3] := -2.5;
  args[4] := 0.1;
  args[5] := 1e300;
  args[6] := 1.0 / 0.0;
  args[7] := -1.0 / 0.0;
  args[8] := 0.0 / 0.0;
  args[9] := 123456.789;
  h := 5;
  gd := 1.0;
  rec.p := 2.0;
  rec.q := 3.0;
  for ai := 0 to 9 do
    for aj := 0 to 9 do
    begin
      i := (ai + aj) mod 6;
      j := ai mod 4;
      ak := (ai * 3 + aj) mod 10;
      al := (ai + aj * 7) mod 10;""")
for n in range(N):
    out.append("      Mix(F%d(args[ai], args[aj], args[ak], args[al], i, j));" % n)
out.append("""      Mix(Shapes(args[ai], args[aj], i, 1.5));
      Mix(TryLoop(args[ai], 5));
    end;
  WriteLn('calls ', calls, ' hash ', h);
end.""")
sys.stdout.write("\n".join(out) + "\n")
