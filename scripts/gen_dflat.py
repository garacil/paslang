#!/usr/bin/env python3
"""Writes testdata/dflat.paslang and testdata/dflat.out (P540): functions of Doubles that call
nothing and have no loop (the kind a frameless routine keeps in xmm8 to xmm15), random ones
from a generator (30, each on 8 argument sets) and a few by hand (a local read before it is
written, six Double parameters, nine Double locals that need a frame, an early Exit, Trunc and
Round, a negated zero, an Integer parameter beside a Double); each result as the 64 bits of
its Double or as an Integer. The expected output is worked out here in Python floats (IEEE
binary64; the compiler makes no fused multiply-add of its own), so a result is what the
arithmetic gives.

usage: gen_dflat.py [--check]    --check writes nothing and fails when the two files in
testdata are not what this script writes
"""
import math
import os
import random
import struct
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata', 'dflat')
CHECK = sys.argv[1:] == ['--check']
FLAT = True


def emit(path, text):
    if CHECK:
        if open(path).read() != text:
            sys.exit(path + ' is not what scripts/gen_dflat.py writes')
    else:
        open(path, 'w').write(text)


CONSTS = ['0.0', '1.0', '2.0', '0.5', '0.1', '3.14159', '-1.5', '100.25', '1e-9', '1e10', '-7.0', '0.3333333333333333', '12345.678', '1e300', '-2.5e-5', '255.0', '0.001', '65536.0']


def bits(x):
    return 'nan' if x != x else '%016x' % struct.unpack('<Q', struct.pack('<d', x))[0]


class Gen:
    def __init__(self, rnd):
        self.r = rnd

    def expr(self, depth, vars_, loops, fi):
        r = self.r
        if depth <= 0 or r.random() < 0.2:
            k = r.random()
            if k < 0.6:
                return ('v', r.choice(vars_))
            if k < 0.8 and loops:
                return ('i', r.choice(loops))
            return ('c', r.choice(CONSTS))
        k = r.random()
        if k < 0.55:
            l, rt = self.expr(depth - 1, vars_, loops, fi), self.expr(depth - 1, vars_, loops, fi)
            if l[0] == 'c' and rt[0] == 'c':
                l = ('v', r.choice(vars_))
            return ('bin', r.choice(['+', '-', '*']), l, rt)
        if k < 0.7:
            num = self.expr(depth - 1, vars_, loops, fi)
            den = ('sq1', self.nv(self.expr(depth - 1, vars_, loops, fi), vars_))
            return ('bin', '/', self.nv(num, vars_), den)
        if k < 0.8:
            return ('sqrt', self.nv(self.expr(depth - 1, vars_, loops, fi), vars_))
        if k < 0.88:
            return ('abs', self.nv(self.expr(depth - 1, vars_, loops, fi), vars_))
        if k < 0.94:
            return ('neg', self.nv(self.expr(depth - 1, vars_, loops, fi), vars_))
        if fi > 0 and not FLAT:
            return ('call', r.randrange(fi), [self.expr(depth - 1, vars_, loops, fi) for _ in range(3)])
        return ('neg', ('v', r.choice(vars_)))

    def nv(self, e, vars_):
        return ('v', self.r.choice(vars_)) if e[0] == 'c' else e

    def cond(self, vars_, loops, fi):
        return ('cmp', self.r.choice(['<', '<=', '>', '>=', '=', '<>']), self.expr(2, vars_, loops, fi), self.expr(2, vars_, loops, fi))

    def stmts(self, depth, vars_, loops, fi, n):
        out = []
        for _ in range(n):
            r = self.r.random()
            if r < 0.5 or depth <= 0:
                out.append(('asg', self.r.choice(['x', 'y', 'z', 'w']), self.expr(3, vars_, loops, fi)))
            elif r < 0.7:
                out.append(('if', self.cond(vars_, loops, fi), self.stmts(depth - 1, vars_, loops, fi, self.r.randint(1, 2)),
                            self.stmts(depth - 1, vars_, loops, fi, self.r.randint(0, 2))))
            elif r < 0.9 and len(loops) < 2 and not FLAT:
                lv = ['i', 'j'][len(loops)]
                out.append(('for', lv, self.r.randint(0, 3), self.r.randint(3, 9), self.r.random() < 0.3,
                            self.stmts(depth - 1, vars_, loops + [lv], fi, self.r.randint(1, 3))))
            elif FLAT:
                out.append(('asg', self.r.choice(['x', 'y', 'z', 'w']), self.expr(3, vars_, loops, fi)))
            else:
                out.append(('while', self.r.randint(2, 7), self.stmts(depth - 1, vars_, loops, fi, self.r.randint(1, 2))))
        return out


def pe(e):
    t = e[0]
    if t == 'c':
        return '(%s)' % e[1] if e[1].startswith('-') else e[1]
    if t == 'v':
        return e[1]
    if t == 'i':
        return '(%s * 1.0)' % e[1]
    if t == 'bin':
        return '(%s %s %s)' % (pe(e[2]), e[1], pe(e[3]))
    if t == 'sq1':
        return '(%s * %s + 1.0)' % (pe(e[1]), pe(e[1]))
    if t == 'sqrt':
        return 'Sqrt(%s * %s + 1.0)' % (pe(e[1]), pe(e[1]))
    if t == 'abs':
        return 'Abs(%s)' % pe(e[1])
    if t == 'neg':
        return '(-%s)' % pe(e[1])
    if t == 'call':
        return 'F%d(%s)' % (e[1], ', '.join(pe(a) for a in e[2]))
    raise ValueError(t)


def ps(ss, ind, wd=0):
    out = []
    p = '  ' * ind
    for s in ss:
        if s[0] == 'asg':
            out.append('%s%s := %s;' % (p, s[1], pe(s[2])))
        elif s[0] == 'if':
            out.append('%sif (%s %s %s) then' % (p, pe(s[1][2]), s[1][1], pe(s[1][3])))
            out.append('%sbegin' % p)
            out += ps(s[2], ind + 1, wd)
            if s[3]:
                out += ['%send' % p, '%selse' % p, '%sbegin' % p] + ps(s[3], ind + 1, wd)
            out.append('%send;' % p)
        elif s[0] == 'for':
            lv, lo, hi, down, body = s[1:]
            out.append('%sfor %s := %s do' % (p, lv, ('%d downto %d' % (hi, lo)) if down else ('%d to %d' % (lo, hi))))
            out.append('%sbegin' % p)
            out += ps(body, ind + 1, wd)
            out.append('%send;' % p)
        else:
            cn = 'cnt%d' % wd
            out += ['%s%s := 0;' % (p, cn), '%swhile %s < %d do' % (p, cn, s[1]), '%sbegin' % p] + ps(s[2], ind + 1, wd + 1)
            out += ['%s  %s := %s + 1;' % (p, cn, cn), '%send;' % p]
    return out


def ev(e, env, funs):
    t = e[0]
    if t == 'c':
        return float(e[1])
    if t == 'v':
        return env[e[1]]
    if t == 'i':
        return float(env[e[1]])
    if t == 'bin':
        a, b = ev(e[2], env, funs), ev(e[3], env, funs)
        if e[1] == '+': return a + b
        if e[1] == '-': return a - b
        if e[1] == '*': return a * b
        return a / b
    if t == 'sq1':
        a = ev(e[1], env, funs)
        return a * a + 1.0
    if t == 'sqrt':
        a = ev(e[1], env, funs)
        return math.sqrt(a * a + 1.0)
    if t == 'abs':
        return abs(ev(e[1], env, funs))
    if t == 'neg':
        return -ev(e[1], env, funs)
    if t == 'call':
        return run(funs, e[1], [ev(a, env, funs) for a in e[2]])
    raise ValueError(t)


def rs(ss, env, funs):
    for s in ss:
        if s[0] == 'asg':
            env[s[1]] = ev(s[2], env, funs)
        elif s[0] == 'if':
            a, b = ev(s[1][2], env, funs), ev(s[1][3], env, funs)
            ok = {'<': a < b, '<=': a <= b, '>': a > b, '>=': a >= b, '=': a == b, '<>': a != b}[s[1][1]]
            rs(s[2] if ok else s[3], env, funs)
        elif s[0] == 'for':
            lv, lo, hi, down, body = s[1:]
            for v in (range(hi, lo - 1, -1) if down else range(lo, hi + 1)):
                env[lv] = v
                rs(body, env, funs)
        else:
            for _ in range(s[1]):
                rs(s[2], env, funs)


def run(funs, i, args):
    body, res = funs[i]
    env = {'a': args[0], 'b': args[1], 'c': args[2], 'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 0.0, 'i': 0, 'j': 0}
    rs(body, env, funs)
    return ev(res, env, funs)


INPUTS = [(0.0, 0.0, 0.0), (1.0, 2.0, 3.0), (-1.5, 2.5, -3.5), (1e10, -1e-10, 0.1), (3.14159, 2.71828, 1.41421), (100.0, 0.001, 65536.0), (1e300, -1e300, 1e-300), (0.5, 0.25, 0.125)]



HAND = """function Hu(a: Double): Double;
var
  x: Double;
begin
  Result := x * 2.0 + a;
end;

function Hp(a, b, c, d, e, f: Double): Double;
begin
  Result := ((a - b) * c + d) / (e * e + 1.0) - f;
end;

function Hm(a: Double): Double;
var
  v1, v2, v3, v4, v5, v6, v7: Double;
begin
  v1 := a + 1.0;
  v2 := v1 * 2.0;
  v3 := v2 - a;
  v4 := v3 * v1;
  v5 := v4 + v2;
  v6 := v5 / (v1 * v1 + 1.0);
  v7 := v6 - v3;
  Result := v7 - v1 + v2 * v3 - v4 + v6 * v7 - v5;
end;

function Hq(a: Double): Double;
var
  v1, v2, v3, v4, v5, v6: Double;
begin
  v1 := a + 1.0;
  v2 := v1 * 2.0;
  v3 := v2 - a;
  v4 := v3 * v1;
  v5 := v4 + v2;
  v6 := v5 / (v1 * v1 + 1.0);
  Result := v6 - v3 + v5 * v6 - v4;
end;

function Hy(a, b, c, d, e, f: Double): Double;
var
  i1, i2, i3, i4, i5, i6, i7: Integer;
begin
  i1 := Trunc(a);
  i2 := Trunc(b) + i1;
  i3 := Trunc(c) + i2;
  i4 := Trunc(d) + i3;
  i5 := Trunc(e) + i4;
  i6 := Trunc(f) + i5;
  i7 := i6 - i1 + i2;
  Result := a + b * c - d / (e * e + 2.0) + f + i1 + i2 + i3 + i4 + i5 + i6 + i7;
end;

function Hi(a: Double): Double;
begin
  Result := a;
end;

function Hk(a, b: Double): Double;
begin
  Result := b;
end;

function Hc(a: Double): Double;
begin
  Result := 2.5;
end;

function Hb(a: Double): Double;
var
  t: Int64;
begin
  t := a as Int64;
  Result := (t xor $8000000000000000) as Double;
end;

function Hl(a, b: Double): Double;
begin
  Result := a;
  Result := Result + b;
end;

function Hn(a: Double; n: Int64): Double;
var
  t: Int64;
begin
  t := (a as Int64) xor n;
  Result := t as Double;
  Result := Result + a;
end;

function Hv(n: Integer; a: Double): Double;
var
  y: Double;
begin
  y := n + 3;
  Result := y * a;
end;

function Hg(a, b: Single): Integer;
begin
  Result := Trunc(a) + Round(b) + Floor(a) - Ceil(b);
end;

type
  TPair = record
    A, B: Int64;
  end;

function Hr(d: Double): TPair;
var
  n: Int64;
begin
  n := Trunc(d + 0.5);
  Result.A := Abs(n) mod 86400000;
  Result.B := 693594 + n div 86400000;
end;

function Hj(a, b: Double): Double;
begin
  if a > b then
    Result := a
  else
    Result := b;
end;

function He(a, b: Double): Double;
begin
  Result := a;
  if a > b then
    Exit;
  Result := b * 2.0;
end;

function Ht(a: Double): Integer;
begin
  Result := Trunc(a * 0.5) + Round(a) - Trunc(a) + Round(a * 3.0);
end;

function Hf(a: Double): Integer;
begin
  Result := Floor(a * 1.5) * 2 - Ceil(a * 0.5);
end;

function Hs(a, b: Single): Single;
var
  t: Single;
begin
  t := a * b;
  Result := t + 1.5;
end;

function Hz(a: Double): Double;
begin
  Result := -a * 1.0;
end;

function Hx(a: Double; n: Integer): Double;
begin
  Result := a * n + n / 2;
end;
"""

HARGS = [(0.0, 0.0), (1.5, -2.5), (-3.0, 7.25), (100.5, 0.5), (2.5, 3.5), (-0.5, -0.25), (1e10, 3.0), (-7.75, 2.0)]


def py_hu(a): return 0.0 * 2.0 + a
def py_hp(a, b, c, d, e, f): return ((a - b) * c + d) / (e * e + 1.0) - f
def py_hm(a):
    v1 = a + 1.0; v2 = v1 * 2.0; v3 = v2 - a; v4 = v3 * v1; v5 = v4 + v2; v6 = v5 / (v1 * v1 + 1.0)
    v7 = v6 - v3
    return v7 - v1 + v2 * v3 - v4 + v6 * v7 - v5
def py_hq(a):
    v1 = a + 1.0; v2 = v1 * 2.0; v3 = v2 - a; v4 = v3 * v1; v5 = v4 + v2; v6 = v5 / (v1 * v1 + 1.0)
    return v6 - v3 + v5 * v6 - v4
def py_hy(a, b, c, d, e, f):
    i1 = int(a); i2 = int(b) + i1; i3 = int(c) + i2; i4 = int(d) + i3; i5 = int(e) + i4; i6 = int(f) + i5; i7 = i6 - i1 + i2
    return a + b * c - d / (e * e + 2.0) + f + i1 + i2 + i3 + i4 + i5 + i6 + i7
def py_hj(a, b): return a if a > b else b
def py_hr(d):
    n = int(d + 0.5)
    return abs(n) % 86400000, 693594 + (n // 86400000 if n >= 0 else -((-n) // 86400000))
def py_hg(a, b): return int(a) + round(b) + math.floor(a) - math.ceil(b)
def py_hv(n, a): return float(n + 3) * a
def py_hn(a, n):
    t = struct.unpack('<q', struct.pack('<d', a))[0] ^ n
    return struct.unpack('<d', struct.pack('<q', t))[0] + a
def py_he(a, b): return a if a > b else b * 2.0
def py_ht(a): return int(a * 0.5) + round(a) - int(a) + round(a * 3.0)
def py_hf(a): return math.floor(a * 1.5) * 2 - math.ceil(a * 0.5)
def f32(v): return struct.unpack('<f', struct.pack('<f', v))[0]
def py_hs(a, b): return f32(f32(a * b) + 1.5)
def py_hz(a): return -a * 1.0
def py_hx(a, n): return a * n + n / 2


def build():
    rnd = random.Random(540)
    g = Gen(rnd)
    funs = []
    src = ['program dflat;', '']
    vars_ = ['a', 'b', 'c', 'x', 'y', 'z', 'w']
    for i in range(30):
        init = [('asg', v, g.expr(2, ['a', 'b', 'c'], [], 0)) for v in ('x', 'y', 'z', 'w')]
        body = init + g.stmts(2, vars_, [], 0, rnd.randint(3, 9))
        res = g.expr(3, vars_, [], 0)
        funs.append((body, res))
        src += ['function F%d(a, b, c: Double): Double;' % i, 'var', '  x, y, z, w: Double;', 'begin']
        src += ps(body, 1)
        src += ['  Result := %s;' % pe(res), 'end;', '']
    src.append(HAND)
    src += ['procedure P(r: Double);', 'var', '  b: Int64;', 'begin', '  if r <> r then', "    WriteLn('nan')", '  else', '  begin', '    b := r as Int64;', '    WriteLn(b);', '  end;', 'end;', '', 'begin']
    exp = []

    def bits(v):
        return 'nan' if v != v else str(struct.unpack('<q', struct.pack('<d', v))[0])
    for i in range(30):
        for (a, b, c) in INPUTS:
            src.append('  P(F%d(%r, %r, %r));' % (i, a, b, c))
            exp.append(bits(run(funs, i, [a, b, c])))
    for (a, b) in HARGS:
        src.append('  P(Hu(%r));' % a); exp.append(bits(py_hu(a)))
        src.append('  P(Hp(%r, %r, 1.5, -0.5, %r, %r));' % (a, b, b, a)); exp.append(bits(py_hp(a, b, 1.5, -0.5, b, a)))
        src.append('  P(Hm(%r));' % a); exp.append(bits(py_hm(a)))
        src.append('  P(Hq(%r));' % a); exp.append(bits(py_hq(a)))
        src.append('  P(Hy(%r, %r, 1.5, -0.5, %r, %r));' % (a, b, b, a)); exp.append(bits(py_hy(a, b, 1.5, -0.5, b, a)))
        src.append('  P(Hi(%r));' % a); exp.append(bits(a))
        src.append('  P(Hk(%r, %r));' % (a, b)); exp.append(bits(b))
        src.append('  P(Hc(%r));' % a); exp.append(bits(2.5))
        src.append('  P(Hj(%r, %r));' % (a, b)); exp.append(bits(py_hj(a, b)))
        src.append('  P(Hb(%r));' % a); exp.append(bits(-a))
        src.append('  WriteLn(Hr(%r).A, \' \', Hr(%r).B);' % (a, a)); exp.append('%d %d' % py_hr(a))
        src.append('  WriteLn(Hg(%r, %r));' % (a, b)); exp.append(str(py_hg(a, b)))
        src.append('  P(Hv(%d, %r));' % (int(b * 4), a)); exp.append(bits(py_hv(int(b * 4), a)))
        src.append('  P(Hn(%r, %d));' % (a, 1 << (int(b * 4) & 31))); exp.append(bits(py_hn(a, 1 << (int(b * 4) & 31))))
        src.append('  P(Hl(%r, %r));' % (a, b)); exp.append(bits(a + b))
        src.append('  P(He(%r, %r));' % (a, b)); exp.append(bits(py_he(a, b)))
        src.append('  WriteLn(Ht(%r));' % a); exp.append(str(py_ht(a)))
        src.append('  WriteLn(Hf(%r));' % a); exp.append(str(py_hf(a)))
        src.append('  P(Hs(%r, %r));' % (a, b)); exp.append(bits(py_hs(a, b)))
        src.append('  P(Hz(%r));' % a); exp.append(bits(py_hz(a)))
        src.append('  P(Hx(%r, %d));' % (a, int(b * 4))); exp.append(bits(py_hx(a, int(b * 4))))
    src.append('end.')
    return '\n'.join(src) + '\n', '\n'.join(exp) + '\n'


prog, exp = build()
emit(OUT + '.paslang', prog)
emit(OUT + '.out', exp)
