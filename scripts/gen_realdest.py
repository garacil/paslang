#!/usr/bin/env python3
"""P541: the golden program testdata/realdest.paslang and its expected output.

Random functions of Doubles (x, y, z, w locals, a, b, c parameters), each statement of one of the
shapes the compiler works out in the variable's own xmm register: x := e with no x in e, x := x op e,
x := (x op e1) op e2, longer chains on x, x := Abs(x), x := -x, x := x op x, a Horner step
x := c + x * z, x := c - f(x), constants and integer literals on either side, comparisons of
variables and of integer literals. The program prints the 64 bits of what each function returns for
eight sets of arguments (or nan for any NaN); the expected output is worked out here with Python
floats, which are IEEE binary64 operations in the order the program writes them (the compiler
fuses nothing by itself).

usage: gen_realdest.py              write testdata/realdest.paslang and testdata/realdest.out
       gen_realdest.py --check      compare them with what this script writes
       gen_realdest.py --fuzz SEED COUNT DIR   COUNT small programs from SEED into DIR (dSEED.paslang, dSEED.exp)"""
import math
import os
import random
import struct
import sys

CONSTS = ['0.0', '1.0', '2.0', '0.5', '0.1', '3.14159', '-1.5', '100.25', '1e-9', '1e10', '-7.0', '0.3333333333333333',
          '12345.678', '1e300', '-2.5e-5', '255.0', '0.001', '65536.0']
ICONSTS = [0, 1, 2, 3, -1, 7, 10, 255, 1000000, 9007199254740991, 9007199254740992, 9007199254740993, -9007199254740991,
           -9007199254740993, 4611686018427387904]
INPUTS = [(0.0, 0.0, 0.0), (1.0, 2.0, 3.0), (-1.5, 2.5, -3.5), (1e10, -1e-10, 0.1), (3.14159, 2.71828, 1.41421),
          (100.0, 0.001, 65536.0), (1e300, -1e300, 1e-300), (0.5, 0.25, 0.125)]
VARS = ['x', 'y', 'z', 'w']


class Skip(Exception):
    pass


class Gen:
    def __init__(self, rnd):
        self.r = rnd

    def leaf(self, vars_, loops):
        r = self.r
        k = r.random()
        if k < 0.55:
            return ('v', r.choice(vars_))
        if k < 0.65 and loops:
            return ('i', r.choice(loops))
        if k < 0.78:
            return ('ic', r.choice(ICONSTS))
        return ('c', r.choice(CONSTS))

    def nv(self, e, vars_):
        return ('v', self.r.choice(vars_)) if e[0] in ('c', 'ic') else e

    def expr(self, depth, vars_, loops, fi):
        r = self.r
        if depth <= 0 or r.random() < 0.2:
            return self.leaf(vars_, loops)
        k = r.random()
        if k < 0.54:
            l, rt = self.expr(depth - 1, vars_, loops, fi), self.expr(depth - 1, vars_, loops, fi)
            if l[0] in ('c', 'ic') and rt[0] in ('c', 'ic'):
                l = ('v', r.choice(vars_))
            return ('bin', r.choice(['+', '-', '*']), l, rt)
        if k < 0.68:
            return self.div(self.expr(depth - 1, vars_, loops, fi), self.expr(depth - 1, vars_, loops, fi), vars_)
        if k < 0.78:
            return ('abs', self.nv(self.expr(depth - 1, vars_, loops, fi), vars_))
        if k < 0.86:
            return ('neg', self.nv(self.expr(depth - 1, vars_, loops, fi), vars_))
        if k < 0.93:
            return ('fma',) + tuple(self.expr(depth - 1, vars_, loops, fi) for _ in range(3))
        return ('neg', ('v', r.choice(vars_)))

    def div(self, num, den, vars_):
        return ('bin', '/', self.nv(num, vars_), ('sq1', self.nv(den, vars_)))

    def binop(self, op, l, rt, vars_):
        if op == '/':
            return self.div(l, rt, vars_)
        return ('bin', op, l, rt)

    def shaped(self, v, vars_, loops, fi):
        r = self.r
        k = r.random()
        me = ('v', v)
        others = [u for u in vars_ if u != v]
        e2 = lambda: self.expr(2, vars_, loops, fi)
        ops = ['+', '-', '*', '/']
        if k < 0.17:
            return self.binop(r.choice(ops), me, e2(), vars_)
        if k < 0.26:
            return self.binop(r.choice(ops), self.binop(r.choice(ops), me, e2(), vars_), e2(), vars_)
        if k < 0.34:
            e = me
            for _ in range(r.randint(3, 5)):
                e = self.binop(r.choice(ops), e, self.leaf(vars_, loops), vars_)
            return e
        if k < 0.40:
            m = r.randrange(5)
            if m == 0:
                return ('abs', me)
            if m == 1:
                return ('neg', me)
            if m == 2:
                return self.binop(r.choice(ops), ('abs', me), e2(), vars_)
            if m == 3:
                return ('neg', self.binop(r.choice(ops), me, e2(), vars_))
            return ('abs', self.binop(r.choice(ops), me, e2(), vars_))
        if k < 0.50:
            # c + x * z, e + x * z, c * (x + z): the Horner steps, the constant or the place on the left
            op = r.choice(['+', '*'])
            inner = self.binop(r.choice(['+', '*', '-']), me, self.leaf(others, loops), vars_)
            l = r.choice([('c', r.choice(CONSTS)), ('ic', r.choice(ICONSTS)), ('v', r.choice(others))])
            return ('bin', op, l, inner)
        if k < 0.55:
            return ('bin', r.choice(['+', '-', '*']), me, me)
        if k < 0.60:
            # x + x * y and x * y + x: x is read again after the chain has begun
            inner = self.binop(r.choice(ops), me, self.leaf(vars_, loops), vars_)
            if r.random() < 0.5:
                return self.binop(r.choice(ops), me, inner, vars_)
            return self.binop(r.choice(ops), inner, me, vars_)
        if k < 0.69:
            # c - f(x): the left operand cheap and the right one reads x
            l = r.choice([('c', r.choice(CONSTS)), ('ic', r.choice(ICONSTS)), ('v', r.choice(others))])
            return self.binop(r.choice(['-', '/', '+', '*']), l, self.binop(r.choice(['+', '-', '*']), me, self.leaf(vars_, loops), vars_), vars_)
        if k < 0.74:
            return self.expr(3, others, loops, fi)
        if k < 0.81:
            # Fma with x in the multiplicand (worked out where x lies), the addend, or not at all
            m = r.randrange(4)
            if m == 0:
                return ('fma', me, self.leaf(vars_, loops), self.leaf(vars_, loops))
            if m == 1:
                return ('fma', self.leaf(vars_, loops), self.leaf(vars_, loops), me)
            if m == 2:
                return ('fma', self.leaf(others, loops), e2(), self.leaf(others, loops))
            return ('bin', r.choice(['+', '-', '*']), ('fma', me, self.leaf(vars_, loops), self.leaf(vars_, loops)), e2())
        return self.expr(3, vars_, loops, fi)

    def cond(self, vars_, loops, fi):
        r = self.r
        op = r.choice(['<', '<=', '>', '>=', '=', '<>'])
        k = r.random()
        if k < 0.3:
            return ('cmp', op, ('v', r.choice(vars_)), ('ic', r.choice(ICONSTS[:9])))
        if k < 0.5:
            return ('cmp', op, ('v', r.choice(vars_)), ('v', r.choice(vars_)))
        if k < 0.6:
            return ('cmp', op, ('c', r.choice(CONSTS)), ('v', r.choice(vars_)))
        return ('cmp', op, self.expr(2, vars_, loops, fi), self.expr(2, vars_, loops, fi))

    def stmts(self, depth, vars_, loops, fi, n, flat):
        out = []
        for _ in range(n):
            r = self.r.random()
            if r < 0.62 or depth <= 0:
                v = self.r.choice(VARS)
                out.append(('asg', v, self.shaped(v, vars_, loops, fi)))
            elif r < 0.70:
                # Trunc, Round, Floor and Ceil of a variable, kept in range, the integer then put into a Double
                out.append(('tc', self.r.choice(VARS), self.r.choice(['Trunc', 'Round', 'Floor', 'Ceil']),
                            self.r.choice(vars_), self.r.randrange(3)))
            elif r < 0.82:
                out.append(('if', self.cond(vars_, loops, fi), self.stmts(depth - 1, vars_, loops, fi, self.r.randint(1, 2), flat),
                            self.stmts(depth - 1, vars_, loops, fi, self.r.randint(0, 2), flat)))
            elif not flat and len(loops) < 2:
                lv = ['i', 'j'][len(loops)]
                out.append(('for', lv, self.r.randint(0, 3), self.r.randint(3, 9), self.r.random() < 0.3,
                            self.stmts(depth - 1, vars_, loops + [lv], fi, self.r.randint(1, 4), flat)))
            else:
                v = self.r.choice(VARS)
                out.append(('asg', v, self.shaped(v, vars_, loops, fi)))
        return out


def pe(e):
    t = e[0]
    if t == 'c':
        return '(%s)' % e[1] if e[1].startswith('-') else e[1]
    if t == 'ic':
        return '(%d)' % e[1] if e[1] < 0 else '%d' % e[1]
    if t == 'v':
        return e[1]
    if t == 'i':
        return '(%s * 1.0)' % e[1]
    if t == 'bin':
        return '(%s %s %s)' % (pe(e[2]), e[1], pe(e[3]))
    if t == 'sq1':
        return '(%s * %s + 1.0)' % (pe(e[1]), pe(e[1]))
    if t == 'abs':
        return 'Abs(%s)' % pe(e[1])
    if t == 'neg':
        return '(-%s)' % pe(e[1])
    if t == 'fma':
        return 'Fma(%s, %s, %s)' % (pe(e[1]), pe(e[2]), pe(e[3]))
    raise ValueError(t)


def ps(ss, ind):
    out = []
    p = '  ' * ind
    for s in ss:
        if s[0] == 'asg':
            out.append('%s%s := %s;' % (p, s[1], pe(s[2])))
        elif s[0] == 'tc':
            v, fn, src, form = s[1:]
            out.append('%sif (%s > -1e15) and (%s < 1e15) then' % (p, src, src))
            out.append('%s  nI := %s(%s)' % (p, fn, src))
            out.append('%selse' % p)
            out.append('%s  nI := 0;' % p)
            out.append('%s%s := %s;' % (p, v, ('nI', 'nI + 3', '%s * 0.5 + nI' % v)[form]))
        elif s[0] == 'if':
            out.append('%sif (%s %s %s) then' % (p, pe(s[1][2]), s[1][1], pe(s[1][3])))
            out.append('%sbegin' % p)
            out += ps(s[2], ind + 1)
            if s[3]:
                out += ['%send' % p, '%selse' % p, '%sbegin' % p] + ps(s[3], ind + 1)
            out.append('%send;' % p)
        else:
            lv, lo, hi, down, body = s[1:]
            out.append('%sfor %s := %s do' % (p, lv, ('%d downto %d' % (hi, lo)) if down else ('%d to %d' % (lo, hi))))
            out.append('%sbegin' % p)
            out += ps(body, ind + 1)
            out.append('%send;' % p)
    return out


def ev(e, env, funs):
    t = e[0]
    if t == 'c':
        return float(e[1])
    if t == 'ic':
        return float(e[1])
    if t == 'v':
        return env[e[1]]
    if t == 'i':
        return float(env[e[1]])
    if t == 'bin':
        a, b = ev(e[2], env, funs), ev(e[3], env, funs)
        if e[1] == '+':
            return a + b
        if e[1] == '-':
            return a - b
        if e[1] == '*':
            return a * b
        return a / b
    if t == 'sq1':
        a = ev(e[1], env, funs)
        return a * a + 1.0
    if t == 'abs':
        return abs(ev(e[1], env, funs))
    if t == 'neg':
        return -ev(e[1], env, funs)
    if t == 'fma':
        return math.fma(ev(e[1], env, funs), ev(e[2], env, funs), ev(e[3], env, funs))
    raise ValueError(t)


def rs(ss, env, funs):
    for s in ss:
        if s[0] == 'asg':
            env[s[1]] = ev(s[2], env, funs)
        elif s[0] == 'tc':
            v, fn, src, form = s[1:]
            a = env[src]
            if -1e15 < a < 1e15:
                n = {'Trunc': int, 'Round': round, 'Floor': math.floor, 'Ceil': math.ceil}[fn](a)
            else:
                n = 0
            env[v] = (float(n), float(n + 3), env[v] * 0.5 + float(n))[form]
        elif s[0] == 'if':
            a, b = ev(s[1][2], env, funs), ev(s[1][3], env, funs)
            ok = {'<': a < b, '<=': a <= b, '>': a > b, '>=': a >= b, '=': a == b, '<>': a != b}[s[1][1]]
            rs(s[2] if ok else s[3], env, funs)
        else:
            lv, lo, hi, down, body = s[1:]
            for v in (range(hi, lo - 1, -1) if down else range(lo, hi + 1)):
                env[lv] = v
                rs(body, env, funs)


def run(funs, i, args):
    body, res = funs[i]
    env = {'a': args[0], 'b': args[1], 'c': args[2], 'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 0.0, 'i': 0, 'j': 0}
    rs(body, env, funs)
    return ev(res, env, funs)


def bits(v):
    return 'nan' if v != v else str(struct.unpack('<q', struct.pack('<d', v))[0])


def build(seed, nfun, header):
    rnd = random.Random(seed)
    g = Gen(rnd)
    funs = []
    src = header + ['program realdest;', '', 'uses pasnum;', '']
    allv = ['a', 'b', 'c'] + VARS
    i = 0
    while i < nfun:
        flat = i % 2 == 0
        init = [('asg', v, g.expr(2, ['a', 'b', 'c'], [], i)) for v in VARS]
        body = init + g.stmts(2, allv, [], i, rnd.randint(4, 9), flat)
        res = g.expr(3, allv, [], i)
        funs.append((body, res))
        try:
            for (a, b, c) in INPUTS:
                run(funs, i, [a, b, c])
        except (OverflowError, ZeroDivisionError, ValueError):
            funs.pop()
            continue
        src += ['function F%d(a, b, c: Double): Double;' % i, 'var', '  x, y, z, w: Double;', '  i, j, nI: Integer;', 'begin']
        src += ps(body, 1)
        src += ['  Result := %s;' % pe(res), 'end;', '']
        i += 1
    src += ['procedure P(r: Double);', 'var', '  b: Int64;', 'begin', '  if r <> r then', "    WriteLn('nan')", '  else', '  begin',
            '    b := r as Int64;', '    WriteLn(b);', '  end;', 'end;', '', 'begin']
    exp = []
    for i in range(nfun):
        for (a, b, c) in INPUTS:
            src.append('  P(F%d(%r, %r, %r));' % (i, a, b, c))
            exp.append(bits(run(funs, i, [a, b, c])))
    src.append('end.')
    return '\n'.join(src) + '\n', '\n'.join(exp) + '\n'


HEADER = ['{ P541: Doubles worked out in the register of the variable they are stored in. Made by',
          '  scripts/gen_realdest.py (seed 5520): 100 functions of Doubles whose statements are of the shapes',
          '  that change a variable in place or in its own register, with constants and integer literals on',
          '  either side, loops, ifs and comparisons of registers; each is called with eight sets of arguments',
          '  and the 64 bits of its result are printed (nan for any NaN). The expected output was worked out',
          '  with Python floats, the operations in the order written, none fused. }']


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    td = os.path.join(here, '..', 'testdata')
    if len(sys.argv) > 1 and sys.argv[1] == '--fuzz':
        first, count, d = int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
        os.makedirs(d, exist_ok=True)
        for sd in range(first, first + count):
            prog, exp = build(sd, 6, [])
            open(os.path.join(d, 'd%d.paslang' % sd), 'w').write(prog)
            open(os.path.join(d, 'd%d.exp' % sd), 'w').write(exp)
        return
    prog, exp = build(5520, 100, HEADER)
    if len(sys.argv) > 1 and sys.argv[1] == '--check':
        ok = open(os.path.join(td, 'realdest.paslang')).read() == prog and open(os.path.join(td, 'realdest.out')).read() == exp
        if not ok:
            print('testdata/realdest.* is not what scripts/gen_realdest.py writes')
            sys.exit(1)
        return
    open(os.path.join(td, 'realdest.paslang'), 'w').write(prog)
    open(os.path.join(td, 'realdest.out'), 'w').write(exp)


main()
