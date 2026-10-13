#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Writes testdata/condjump.paslang (P265): seeded Boolean conditions
of and, or, not, comparisons of integers, bytes, characters and reals
(a NaN among them), Boolean variables and calls that leave their mark
in a trace, each worked out as the branch of an if, an if whose then is
an Exit, a while, a repeat and an if not, and as a value; for every
value of the variables, the branch and the value must agree and so must
the trace of the calls they made, in order (short circuit). The
program prints one line a condition and the count of disagreements, 0.

    scripts/condjump_gen.py [SEED [COUNT]] > testdata/condjump.paslang
"""
import random
import sys

INTS = ["a", "b", "Integer(c)", "a + 1", "b - a", "3", "-2"]
OPS = ["=", "<>", "<", "<=", ">", ">="]


def int_expr(rng, n):
    if rng.random() < 0.2:
        return "I(%d, %s)" % (n, rng.choice(["a", "b", "a + b"]))
    return rng.choice(INTS)


def leaf(rng, n):
    r = rng.random()
    if r < 0.45:
        return "(%s %s %s)" % (int_expr(rng, n), rng.choice(OPS), int_expr(rng, n + 1))
    if r < 0.55:
        return "(c %s %d)" % (rng.choice(OPS), rng.choice([0, 48, 57, 255]))
    if r < 0.62:
        return "(ch %s '%s')" % (rng.choice(OPS), rng.choice("0a9"))
    if r < 0.70:
        return "(d %s %s)" % (rng.choice(OPS), rng.choice(["0.5", "d", "0.0"]))
    if r < 0.82:
        return rng.choice(["p", "q"])
    return "T(%d, %s)" % (n, rng.choice(["p", "q", "a < b", "c > 50"]))


def cond(rng, depth, n):
    if depth == 0 or rng.random() < 0.25:
        return leaf(rng, n)
    r = rng.random()
    if r < 0.15:
        return "not %s" % cond(rng, depth - 1, n)
    op = "and" if r < 0.6 else "or"
    return "(%s %s %s)" % (cond(rng, depth - 1, n), op, cond(rng, depth - 1, n + 3))


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 265
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    rng = random.Random(seed)
    conds = [cond(rng, 4, 1) for _ in range(count)]
    out = []
    w = out.append
    w("{ This file is part of paslang.")
    w("  Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>")
    w("  GPL version 3 or later; see COPYING. No warranty. }")
    w("")
    w("{ P265: a condition as branches against the same condition as a value,")
    w("  written by scripts/condjump_gen.py %d %d. For every value of the" % (seed, count))
    w("  variables each condition is worked out as an if, an if whose then is")
    w("  an Exit, a while, a repeat and an if not, and as a value: the answers")
    w("  and the traces of the calls made, in order, must be the same. Digit")
    w("  is the shape make check greps in the .s of both machines: its")
    w("  condition is two compares and two branches, no Boolean in a")
    w("  register. }")
    w("program condjump;")
    w("")
    w("var")
    w("  a, b, total, bad, k: Integer;")
    w("  c: Byte;")
    w("  ch: Char;")
    w("  d: Double;")
    w("  p, q, v: Boolean;")
    w("  trace: string;")
    w("  ia, ib, ic, ich, id, ip, iq: Integer;")
    w("")
    w("function T(N: Integer; V: Boolean): Boolean;")
    w("begin")
    w("  trace := trace + Chr(64 + N);")
    w("  Result := V;")
    w("end;")
    w("")
    w("function I(N: Integer; V: Integer): Integer;")
    w("begin")
    w("  trace := trace + Chr(96 + N);")
    w("  Result := V;")
    w("end;")
    w("")
    w("function Digit(X: Integer): Boolean;")
    w("begin")
    w("  if (X >= 48) and (X <= 57) then")
    w("    Result := True")
    w("  else")
    w("    Result := False;")
    w("end;")
    w("")
    w("procedure Check(K: Integer; R1, R2: Boolean; const T1, T2: string);")
    w("begin")
    w("  total := total + 1;")
    w("  if (R1 <> R2) or (T1 <> T2) then")
    w("  begin")
    w("    bad := bad + 1;")
    w("    if bad < 20 then")
    w("      WriteLn('condition ', K, ': branch ', R1, ' ', T1, ', value ', R2, ' ', T2,")
    w("        ' at a=', a, ' b=', b, ' c=', c, ' ch=', ch, ' p=', p, ' q=', q);")
    w("  end;")
    w("end;")
    for k, e in enumerate(conds):
        w("")
        w("{ %s }" % e.replace("{", "(").replace("}", ")"))
        w("function Exits%d: Boolean;" % k)
        w("begin")
        w("  Result := True;")
        w("  if %s then" % e)
        w("    Exit;")
        w("  Result := False;")
        w("end;")
        w("")
        w("procedure Case%d;" % k)
        w("var")
        w("  r: Boolean;")
        w("  t0: string;")
        w("  n: Integer;")
        w("begin")
        w("  trace := '';")
        w("  v := %s;" % e)
        w("  t0 := trace;")
        w("  trace := '';")
        w("  if %s then r := True else r := False;" % e)
        w("  Check(%d, r, v, trace, t0);" % k)
        w("  trace := '';")
        w("  r := Exits%d;" % k)
        w("  Check(%d, r, v, trace, t0);" % k)
        w("  trace := '';")
        w("  r := False;")
        w("  while %s do" % e)
        w("  begin")
        w("    r := True;")
        w("    Break;")
        w("  end;")
        w("  Check(%d, r, v, trace, t0);" % k)
        w("  trace := '';")
        w("  n := 0;")
        w("  repeat")
        w("    n := n + 1;")
        w("    if n > 1 then")
        w("      Break;")
        w("  until %s;" % e)
        w("  Check(%d, n = 1, v, trace, t0);" % k)
        w("  trace := '';")
        w("  if not %s then r := False else r := True;" % e)
        w("  Check(%d, r, v, trace, t0);" % k)
        w("end;")
    w("")
    w("begin")
    w("  total := 0;")
    w("  bad := 0;")
    w("  for ia := 0 to 3 do")
    w("    for ib := 0 to 3 do")
    w("      for ic := 0 to 3 do")
    w("        for ich := 0 to 2 do")
    w("          for id := 0 to 2 do")
    w("            for ip := 0 to 1 do")
    w("              for iq := 0 to 1 do")
    w("              begin")
    w("                a := ia - 1;")
    w("                b := ib - 1;")
    w("                case ic of 0: c := 0; 1: c := 48; 2: c := 57; else c := 255; end;")
    w("                case ich of 0: ch := '0'; 1: ch := 'a'; else ch := '9'; end;")
    w("                case id of 0: d := 0.0; 1: d := 0.7; else begin d := 0.0; d := d / d; end; end;")
    w("                p := ip = 1;")
    w("                q := iq = 1;")
    for k in range(count):
        w("                Case%d;" % k)
    w("              end;")
    w("  k := 0;")
    w("  for ia := 0 to 255 do")
    w("    if Digit(ia) <> ((ia >= 48) and (ia <= 57)) then")
    w("      k := k + 1;")
    w("  WriteLn(total, ' checks, ', bad, ' disagree; Digit wrong ', k, ' times');")
    w("end.")
    print("\n".join(out))


if __name__ == "__main__":
    main()
