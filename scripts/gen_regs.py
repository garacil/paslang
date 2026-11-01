#!/usr/bin/env python3
"""Writes testdata/regs.paslang and testdata/regs.out (P230): kernels of
integer arithmetic alone with nine to thirteen variables alive in a loop (the
locals of a routine, or the globals of the program as in scripts/bench/b10rot),
whose statements the compiler works out in the register pool and whose
variables it keeps in the registers a loop lends: r9, r10, r11, r8, rbx, r12,
r13, r15 and, where no expression needs the pool's second register, rdi. The
statements are of every shape the pool takes (an operation on a variable and
a constant, a chain of them, shifts and rotations by constants, a division by
a constant or by a variable, a compare in an if, a nested loop, a while, a
repeat) and some it cannot take in one register (an operation whose right
side is itself an operation). A seeded generator makes the kernels; the
expected output is worked out here by running the same tree in Python (64-bit
wrap), not by the compiler.

usage: gen_regs.py [--check]    --check writes nothing and fails when the two
files in testdata are not what this script writes
"""
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata', 'regs')
CHECK = sys.argv[1:] == ['--check']
MASK = (1 << 64) - 1


def emit(path, text):
    if CHECK:
        if open(path).read() != text:
            sys.exit(path + ' is not what scripts/gen_regs.py writes')
    else:
        open(path, 'w').write(text)


class Rng:
    def __init__(self, seed):
        self.s = seed & MASK

    def next(self):
        self.s = (self.s * 6364136223846793005 + 1442695040888963407) & MASK
        return self.s >> 33

    def below(self, n):
        return self.next() % n

    def pick(self, xs):
        return xs[self.below(len(xs))]


def s64(x):
    x &= MASK
    return x - (1 << 64) if x >> 63 else x


def tdiv(a, b):
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


# expressions: ('c', k) ('v', name) ('b', op, a, b) ('sh', 'shl'|'shr', a, k) ('rot', 'rol'|'ror', a, k) ('d', 'div'|'mod', a, k)
def ev(e, env):
    k = e[0]
    if k == 'c':
        return s64(e[1])
    if k == 'v':
        return env[e[1]]
    if k == 'sh':
        a = ev(e[2], env)
        return s64(a << e[3]) if e[1] == 'shl' else s64((a & MASK) >> e[3])
    if k == 'rot':
        a = ev(e[2], env) & MASK
        n = e[3] % 64
        if e[1] == 'ror':
            n = (64 - n) % 64
        return s64(((a << n) | (a >> (64 - n))) & MASK) if n else s64(a)
    if k == 'd':
        a = ev(e[2], env)
        q = tdiv(a, e[3])
        return s64(q) if e[1] == 'div' else s64(a - q * e[3])
    if k == 'call':
        return s64(ev(e[1], env) * 3 + ev(e[2], env) + 1)
    if k == 'dv':
        a = ev(e[2], env)
        d = env[e[3]]
        q = tdiv(a, d)
        return s64(q) if e[1] == 'div' else s64(a - q * d)
    a = ev(e[2], env)
    b = ev(e[3], env)
    o = e[1]
    if o == '+':
        return s64(a + b)
    if o == '-':
        return s64(a - b)
    if o == '*':
        return s64(a * b)
    if o == 'and':
        return s64(a & b)
    if o == 'or':
        return s64(a | b)
    return s64(a ^ b)


def evc(c, env):
    a, b = ev(c[2], env), ev(c[3], env)
    return {'<': a < b, '<=': a <= b, '>': a > b, '>=': a >= b, '=': a == b, '<>': a != b}[c[1]]


def ptxt(e):
    k = e[0]
    if k == 'c':
        v = s64(e[1])
        return '(%d)' % v if v < 0 else str(v)
    if k == 'v':
        return e[1]
    if k in ('sh', 'rot'):
        return '(%s %s %d)' % (ptxt(e[2]), e[1], e[3])
    if k == 'd':
        return '(%s %s %d)' % (ptxt(e[2]), e[1], e[3])
    if k == 'dv':
        return '(%s %s %s)' % (ptxt(e[2]), e[1], e[3])
    if k == 'call':
        return 'Mix(%s, %s, 1)' % (ptxt(e[1]), ptxt(e[2]))
    return '(%s %s %s)' % (ptxt(e[2]), e[1], ptxt(e[3]))


def ctxt(c):
    return '(%s %s %s)' % (ptxt(c[2]), c[1], ptxt(c[3]))


class Kernel:
    def __init__(self, name, rng, nvars, glob, deep, calls=False, sel=False):
        self.sel = sel          # ifs of single assignments, which may be conditional moves
        self.calls = calls
        self.name = name
        self.rng = rng
        self.nv = nvars
        self.glob = glob
        self.deep = deep          # statements whose right side is an operation too
        pre = name.lower() if glob else ''
        self.vars = ['%sv%d' % (pre, i) for i in range(nvars)]
        self.dv = pre + 'dv'
        self.ctrs = [pre + 'ci', pre + 'cj', pre + 'cw']
        self.body = []
        self.init = []
        self.build()

    def leafv(self, avoid=None):
        r = self.rng
        while True:
            v = r.pick(self.vars)
            if v != avoid:
                return ('v', v)

    def konst(self):
        return ('c', self.rng.pick([1, 3, 5, 7, 9, 17, 255, 4097, 65521, 0x9E3779B1, 0x7FFFFFFF, 0x5851F42D4C957F2D]))

    def chain(self, depth, avoid=None):
        """an expression whose right sides are variables or constants"""
        r = self.rng
        if depth == 0:
            return self.leafv(avoid) if r.below(4) else self.konst()
        t = r.below(10)
        a = self.chain(depth - 1, avoid)
        if t < 5:
            return ('b', r.pick(['+', '-', '*', 'and', 'or', 'xor', 'xor', '+']), a, self.leafv() if r.below(2) else self.konst())
        if t < 7:
            return ('sh', r.pick(['shl', 'shr']), a, 1 + r.below(31))
        if t < 9:
            return ('rot', r.pick(['rol', 'ror']), a, 1 + r.below(63))
        if r.below(3) == 0:
            return ('dv', r.pick(['div', 'mod']), a, self.dv)
        return ('d', r.pick(['div', 'mod']), a, r.pick([3, 5, 7, 10, 255, 1000003]))

    def expr(self):
        r = self.rng
        if self.deep and r.below(3) == 0:
            # an operation whose right side is an operation: two pool registers
            return ('b', r.pick(['+', 'xor', '-', 'or']), self.chain(1), self.chain(1))
        return self.chain(1 + r.below(2))

    def cond(self):
        r = self.rng
        if r.below(3) == 0:
            return ('cmp', r.pick(['=', '<>']), ('b', 'and', self.leafv(), ('c', r.pick([1, 3, 7, 255]))), ('c', r.below(2)))
        return ('cmp', r.pick(['<', '<=', '>', '>=', '=', '<>']), self.chain(1), self.leafv() if r.below(2) else self.konst())

    def stmt(self, depth):
        r = self.rng
        t = r.below(12 if depth else 10)
        if depth and r.below(7) == 0:
            # a sum of the counter over a loop: the accumulating for, which
            # works its run end out in rcx, rdx and rsi
            return ('accfor', r.pick(self.vars))
        if self.calls and depth and r.below(5) == 0:
            # a call: the loop is not one run, and a variable in a register
            # goes home and comes back around it
            return ('asg', r.pick(self.vars), ('call', self.leafv(), self.leafv()))
        if t < 6:
            v = r.pick(self.vars)
            return ('asg', v, self.expr())
        if t < 7:
            v = r.pick(self.vars)
            return ('asg', v, ('b', r.pick(['xor', '+']), ('v', v), self.leafv(v)))
        if t < 9:
            lo = 1 if self.sel else 2
            return ('if', self.cond(), [self.stmt(0) for _ in range(lo + r.below(2))], [self.stmt(0) for _ in range(r.below(2))])
        if t < 10:
            # the divisor of a division by a variable: 2 or more
            return ('asg', self.dv, ('b', '+', ('b', 'and', self.leafv(), ('c', 255)), ('c', 2)))
        if t < 11:
            c = self.ctrs[1]
            return ('for', c, 1, 2 + r.below(3), [self.stmt(0) for _ in range(1 + r.below(2))])
        c = self.ctrs[2]
        return ('while', c, 1 + r.below(3), [self.stmt(0) for _ in range(1 + r.below(2))])

    def build(self):
        r = self.rng
        self.init = []
        for i, v in enumerate(self.vars):
            self.init.append(('asg', v, ('b', 'xor', ('b', '*', ('v', 'x'), ('c', 2 * i + 3)), ('v', 'y'))))
            self.init.append(('asg', v, ('b', '+', ('v', v), ('c', 7 * i + 1))))
        self.init.append(('asg', self.dv, ('c', 5)))
        n = 8 + r.below(14)
        body = [self.stmt(1) for _ in range(n)]
        # division by a constant, once
        at = r.below(len(body) + 1)
        tv = self.vars[r.below(self.nv)]
        body.insert(at, ('asg', tv, ('d', 'div', ('v', self.vars[1]), 7)))
        body.insert(at + 1, ('asg', tv, ('b', 'xor', ('v', tv), ('v', self.vars[0]))))
        self.body = body
        self.iters = 3 + r.below(7)

    def run(self, x, y):
        env = {'x': x, 'y': y, self.dv: 0}
        for v in self.vars + self.ctrs:
            env[v] = 0
        self.exec_list(self.init, env)
        for i in range(1, self.iters + 1):
            env[self.ctrs[0]] = i
            self.exec_list(self.body, env)
        acc = 0
        for i, v in enumerate(self.vars):
            acc = s64(acc * 31 + env[v] + i)
        return acc

    def exec_list(self, ss, env):
        for s in ss:
            k = s[0]
            if k == 'asg':
                env[s[1]] = ev(s[2], env)
            elif k == 'if':
                self.exec_list(s[2] if evc(s[1], env) else s[3], env)
            elif k == 'for':
                for i in range(s[2], s[3] + 1):
                    env[s[1]] = i
                    self.exec_list(s[4], env)
            elif k == 'accfor':
                lim = env[self.dv]
                env[s[1]] = s64(sum(range(1, lim + 1)))
                env[self.ctrs[1]] = lim
            elif k == 'while':
                env[s[1]] = s[2]
                while env[s[1]] > 0:
                    self.exec_list(s[3], env)
                    env[s[1]] -= 1


def stmts_txt(ss, ind, R):
    out = []
    p = '  ' * ind
    for s in ss:
        k = s[0]
        if k == 'asg':
            out.append('%s%s := %s;' % (p, s[1], ptxt(s[2])))
        elif k == 'if':
            out.append('%sif %s then' % (p, ctxt(s[1])))
            out.append('%sbegin' % p)
            out.extend(stmts_txt(s[2], ind + 1, R))
            if s[3]:
                out.append('%send' % p)
                out.append('%selse' % p)
                out.append('%sbegin' % p)
                out.extend(stmts_txt(s[3], ind + 1, R))
            out.append('%send;' % p)
        elif k == 'for':
            out.append('%sfor %s := %d to %d do' % (p, s[1], s[2], s[3]))
            out.append('%sbegin' % p)
            out.extend(stmts_txt(s[4], ind + 1, R))
            out.append('%send;' % p)
        elif k == 'accfor':
            out.append('%s%s := 0;' % (p, s[1]))
            out.append('%sfor %s := 1 to %s do' % (p, R.ctrs[1], R.dv))
            out.append('%s  %s := %s + %s;' % (p, s[1], s[1], R.ctrs[1]))
        elif k == 'while':
            out.append('%s%s := %d;' % (p, s[1], s[2]))
            out.append('%swhile %s > 0 do' % (p, s[1]))
            out.append('%sbegin' % p)
            out.extend(stmts_txt(s[3], ind + 1, R))
            out.append('%s  %s := %s - 1;' % (p, s[1], s[1]))
            out.append('%send;' % p)
    return out


MIXER = '''{ the eight variables of scripts/bench/b10rot, xoshiro256**: the
  Makefile reads this routine's assembly, where mixt takes the register the
  pool does not need }
function Mixer(x, y: Int64): Int64;
var
  mixs0, mixs1, mixs2, mixs3, mixt, mixr, mixsum, mixi: Int64;
begin
  mixs0 := x;
  mixs1 := y or 1;
  mixs2 := x xor 3;
  mixs3 := y + 4;
  mixsum := 0;
  for mixi := 1 to 1000 do
  begin
    mixr := ((mixs1 * 5) rol 7) * 9;
    mixt := mixs1 shl 17;
    mixs2 := mixs2 xor mixs0;
    mixs3 := mixs3 xor mixs1;
    mixs1 := mixs1 xor mixs2;
    mixs0 := mixs0 xor mixs3;
    mixs2 := mixs2 xor mixt;
    mixs3 := mixs3 rol 45;
    mixsum := mixsum + mixr;
  end;
  Result := mixsum xor mixs0;
end;

{ ten variables in a loop whose every right side is an operation: two
  registers of the pool, so rdi stays the pool's }
function DeepLoop(x, y: Int64): Int64;
var
  a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, i: Int64;
begin
  a0 := x;
  a1 := y;
  a2 := x xor 5;
  a3 := y + 3;
  a4 := x + y;
  a5 := x - y;
  a6 := a0 xor a1;
  a7 := a2 + a3;
  a8 := a4 xor a5;
  a9 := 1;
  for i := 1 to 100 do
  begin
    a0 := a1 - (a2 - a3);
    a1 := a2 xor (a3 + a4);
    a2 := a3 + (a4 xor a5);
    a3 := a4 - (a5 + a6);
    a4 := a5 xor (a6 - a7);
    a5 := a6 + (a7 - a8);
    a6 := a7 xor (a8 + a9);
    a7 := a8 - (a9 xor a0);
    a8 := a9 + (a0 - a1);
    a9 := a0 xor (a1 + a2);
  end;
  Result := a0 xor a1 xor a2 xor a3 xor a4 xor a5 xor a6 xor a7 xor a8 xor a9;
end;

{ ten variables in a loop with ifs of single assignments, which are
  conditional moves: they work their values out in the pool's second
  register, so the loop keeps it and the moves }
function SelLoop(x, y: Int64): Int64;
var
  a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, i: Int64;
begin
  a0 := x;
  a1 := y;
  a2 := x xor 5;
  a3 := y + 3;
  a4 := x + y;
  a5 := x - y;
  a6 := a0 xor a1;
  a7 := a2 + a3;
  a8 := a4 xor a5;
  a9 := 1;
  for i := 1 to 100 do
  begin
    if a1 > a2 then
      a3 := a1;
    if a4 < a5 then
      a6 := a4
    else
      a6 := a5 + a7;
    a0 := a0 + a3;
    a1 := a1 xor a6;
    a2 := a2 + a0;
    a4 := a4 xor a2;
    a5 := a5 + a1;
    a7 := a7 xor a3;
    a8 := a8 + a6;
    a9 := a9 xor a8;
  end;
  Result := a0 xor a1 xor a2 xor a3 xor a4 xor a5 xor a6 xor a7 xor a8 xor a9;
end;

{ an expression two registers deep in a routine with no frame, after the
  kernels: it keeps the pool's second register }
function DeepLeaf(a, b, c: Int64): Int64;
begin
  Result := (a - (b - c)) xor (c - (a - b));
end;
'''


def rol64(a, n):
    a &= MASK
    return s64(((a << n) | (a >> (64 - n))) & MASK)


def mixer(x, y):
    s0, s1, s2, s3 = x, s64(y | 1), s64(x ^ 3), s64(y + 4)
    total = 0
    for _ in range(1000):
        r = s64(rol64(s64(s1 * 5), 7) * 9)
        t = s64(s1 << 17)
        s2 = s64(s2 ^ s0)
        s3 = s64(s3 ^ s1)
        s1 = s64(s1 ^ s2)
        s0 = s64(s0 ^ s3)
        s2 = s64(s2 ^ t)
        s3 = rol64(s3, 45)
        total = s64(total + r)
    return s64(total ^ s0)


def deeploop(x, y):
    a = [x, y, s64(x ^ 5), s64(y + 3), s64(x + y), s64(x - y)]
    a.append(s64(a[0] ^ a[1]))
    a.append(s64(a[2] + a[3]))
    a.append(s64(a[4] ^ a[5]))
    a.append(1)
    for _ in range(100):
        a[0] = s64(a[1] - (a[2] - a[3]))
        a[1] = s64(a[2] ^ s64(a[3] + a[4]))
        a[2] = s64(a[3] + (a[4] ^ a[5]))
        a[3] = s64(a[4] - s64(a[5] + a[6]))
        a[4] = s64(a[5] ^ s64(a[6] - a[7]))
        a[5] = s64(a[6] + s64(a[7] - a[8]))
        a[6] = s64(a[7] ^ s64(a[8] + a[9]))
        a[7] = s64(a[8] - (a[9] ^ a[0]))
        a[8] = s64(a[9] + s64(a[0] - a[1]))
        a[9] = s64(a[0] ^ s64(a[1] + a[2]))
    r = 0
    for v in a:
        r ^= v
    return s64(r)


def selloop(x, y):
    a = [x, y, s64(x ^ 5), s64(y + 3), s64(x + y), s64(x - y)]
    a.append(s64(a[0] ^ a[1]))
    a.append(s64(a[2] + a[3]))
    a.append(s64(a[4] ^ a[5]))
    a.append(1)
    for _ in range(100):
        if a[1] > a[2]:
            a[3] = a[1]
        a[6] = a[4] if a[4] < a[5] else s64(a[5] + a[7])
        a[0] = s64(a[0] + a[3])
        a[1] = s64(a[1] ^ a[6])
        a[2] = s64(a[2] + a[0])
        a[4] = s64(a[4] ^ a[2])
        a[5] = s64(a[5] + a[1])
        a[7] = s64(a[7] ^ a[3])
        a[8] = s64(a[8] + a[6])
        a[9] = s64(a[9] ^ a[8])
    r = 0
    for v in a:
        r ^= v
    return s64(r)


def deepleaf(a, b, c):
    return s64((a - (b - c)) ^ (c - (a - b)))


def main():
    rng = Rng(230)
    K = []
    for n in range(30):
        K.append(Kernel('K%02d' % n, rng, 9 + n % 5, n % 3 == 2, n % 4 == 3, n % 5 == 4, n % 3 == 0))
    inputs = [(0, 0), (1, -1), (7, 300), (-123456789, 98765), (0x7FFFFFFFFFFFFFFF, 3), (-9223372036854775807 - 1, 5), (65537, -65537), (4242, 17)]
    P = ["""program regs;

{ Kernels of integer arithmetic alone with nine to thirteen variables alive
  in a loop (P230), in locals and in globals: scripts/gen_regs.py makes
  them from a seed and works out the output by running the same tree in
  Python. }

function Mix(a, b: Int64; d: Integer): Int64;
begin
  if d <= 0 then
    Result := a * 3 + b + 1
  else
    Result := Mix(a, b, d - 1);
end;
"""]
    gl = []
    for k in K:
        if k.glob:
            gl.extend(k.vars + [k.dv] + k.ctrs)
    if gl:
        P.append('var')
        for v in gl:
            P.append('  %s: Int64;' % v)
        P.append('')
    X = []
    for k in K:
        P.append('function %s(x, y: Int64): Int64;' % k.name)
        if not k.glob:
            P.append('var')
            P.append('  %s: Int64;' % ', '.join(k.vars + [k.dv] + k.ctrs))
        P.append('begin')
        P.extend(stmts_txt(k.init, 1, k))
        P.append('  for %s := 1 to %d do' % (k.ctrs[0], k.iters))
        P.append('  begin')
        P.extend(stmts_txt(k.body, 2, k))
        P.append('  end;')
        P.append('  Result := 0;')
        for i, v in enumerate(k.vars):
            P.append('  Result := Result * 31 + %s + %d;' % (v, i))
        P.append('end;')
        P.append('')
    P.append(MIXER)
    P.append('begin')
    for (x, y) in inputs:
        xs = 'Low(Int64)' if x == -(1 << 63) else ('(%d)' % x if x < 0 else str(x))
        ys = '(%d)' % y if y < 0 else str(y)
        P.append("  WriteLn('Mixer %d %d ', Mixer(%s, %s));" % (x, y, xs, ys))
        X.append('Mixer %d %d %d\n' % (x, y, mixer(x, y)))
        P.append("  WriteLn('SelLoop %d %d ', SelLoop(%s, %s));" % (x, y, xs, ys))
        X.append('SelLoop %d %d %d\n' % (x, y, selloop(x, y)))
        P.append("  WriteLn('DeepLoop %d %d ', DeepLoop(%s, %s));" % (x, y, xs, ys))
        X.append('DeepLoop %d %d %d\n' % (x, y, deeploop(x, y)))
        P.append("  WriteLn('DeepLeaf %d %d ', DeepLeaf(%s, %s, %s));" % (x, y, xs, ys, '(%d)' % (x ^ y) if (x ^ y) < 0 else str(x ^ y)))
        X.append('DeepLeaf %d %d %d\n' % (x, y, deepleaf(x, y, x ^ y)))
    for k in K:
        for (x, y) in inputs:
            xs = 'Low(Int64)' if x == -(1 << 63) else ('(%d)' % x if x < 0 else str(x))
            ys = '(%d)' % y if y < 0 else str(y)
            P.append("  WriteLn('%s %d %d ', %s(%s, %s));" % (k.name, x, y, k.name, xs, ys))
            X.append('%s %d %d %d\n' % (k.name, x, y, k.run(x, y)))
    P.append('end.')
    return '\n'.join(P) + '\n', ''.join(X)


prog, out = main()
emit(OUT + '.paslang', prog)
emit(OUT + '.out', out)
