#!/usr/bin/env python3
"""Writes testdata/slots.paslang and testdata/slots.out (P510): routines of
many integer locals whose lives do not meet (the compiler gives them one slot
and so one register), beside the ones whose lives do meet and the ones that
must start as zero, in every shape of statement a routine without calls has:
straight code, if and else, for, while, repeat and case loops, loop-carried
values, early exits. A seeded generator makes the routines; the expected
output is worked out here by running the same tree in Python (64-bit wrap,
a narrow local cut to its width at every assignment, a local that no path
wrote reading as 0), not by the compiler.

usage: gen_slots.py [--check]    --check writes nothing and fails when the two
files in testdata are not what this script writes
"""
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata', 'slots')
CHECK = sys.argv[1:] == ['--check']
MASK = (1 << 64) - 1


def emit(path, text):
    if CHECK:
        if open(path).read() != text:
            sys.exit(path + ' is not what scripts/gen_slots.py writes')
    else:
        open(path, 'w').write(text)


class Rng:
    """a small generator that does not depend on the Python version"""

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


NARROW = {'Int64': (64, True), 'Byte': (8, False), 'Word': (16, False), 'Int32': (32, True), 'Int8': (8, True)}


def cut(x, t):
    n, sg = NARROW[t]
    x &= (1 << n) - 1
    if sg and x >> (n - 1):
        x -= 1 << n
    return x


# expressions: ('c', k) ('v', name) ('b', op, a, b) ('sh', op, a, k)
def ev(e, env):
    k = e[0]
    if k == 'c':
        return s64(e[1])
    if k == 'v':
        return env.get(e[1], 0)
    if k == 'sh':
        a = ev(e[2], env)
        if e[1] == 'shl':
            return s64(a << e[3])
        return s64((a & MASK) >> e[3])
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
    o, a, b = c[1], ev(c[2], env), ev(c[3], env)
    return {'<': a < b, '<=': a <= b, '>': a > b, '>=': a >= b, '=': a == b, '<>': a != b}[o]


def ptxt(e, R):
    k = e[0]
    if k == 'c':
        v = s64(e[1])
        return '(%d)' % v if v < 0 else str(v)
    if k == 'v':
        t = R.types.get(e[1], 'Int64')
        return e[1] if t == 'Int64' else 'Int64(%s)' % e[1]
    if k == 'sh':
        return '(%s %s %d)' % (ptxt(e[2], R), e[1], e[3])
    return '(%s %s %s)' % (ptxt(e[2], R), e[1], ptxt(e[3], R))


def ctxt(c, R):
    return '(%s %s %s)' % (ptxt(c[2], R), c[1], ptxt(c[3], R))


def hasvar(e):
    if e[0] == 'v':
        return True
    if e[0] == 'c':
        return False
    if e[0] == 'sh':
        return hasvar(e[2])
    return hasvar(e[2]) or hasvar(e[3])


class Routine:
    def __init__(self, name, rng, typ, phases, few=False, call=False):
        self.name = name
        self.rng = rng
        self.typ = typ
        self.locals = []     # (name, type)
        self.body = []
        self.few = few
        self.call = call
        self.nphase = 0
        self.build(phases)

    def local(self, name, typ=None):
        self.locals.append((name, typ or self.typ))
        return name

    def expr(self, vs, depth=2):
        r = self.rng
        if depth == 0 or r.below(5) == 0:
            if r.below(3) == 0:
                return ('c', r.pick([1, 3, 7, 255, 4096, 65537, 0x9E3779B1, 0x7FFFFFFF, 12345678901]))
            return ('v', r.pick(vs))
        if r.below(5) == 0:
            return ('sh', r.pick(['shl', 'shr']), self.expr(vs, depth - 1), 1 + r.below(13))
        return ('b', r.pick(['+', '-', '*', 'and', 'or', 'xor', '+', 'xor']), self.expr(vs, depth - 1), self.expr(vs, depth - 1))

    def cond(self, vs):
        r = self.rng
        if r.below(2) == 0:
            return ('cmp', r.pick(['<', '<=', '>', '>=', '<>']), self.expr(vs, 1), self.expr(vs, 1))
        return ('cmp', r.pick(['=', '<>']), ('b', 'and', self.expr(vs, 1), ('c', 7)), ('c', r.below(8)))

    def asg(self, v, e):
        # an expression of constants alone is folded, and the folded value
        # must fit a narrow local: keep a variable in every right side
        if not hasvar(e) and dict(self.locals).get(v, 'Int64') != 'Int64':
            e = ('b', '+', ('v', 'x'), e)
        return ('asg', v, e)

    def fresh(self, base):
        self.nphase += 1
        return '%s%d' % (base, self.nphase)

    def tmp(self, base, narrow=True):
        n = self.fresh(base)
        return self.local(n, self.typ if narrow else 'Int64')

    def phase(self, kind, vs):
        """statements of one phase over the variables vs, its own temps new"""
        r = self.rng
        acc = 'acc'
        if kind == 0:
            a, b = self.tmp('ta'), self.tmp('tb')
            return [self.asg(a, self.expr(vs + [acc])), self.asg(b, self.expr(vs + [acc, a])),
                    self.asg(acc, ('b', '+', ('v', acc), ('b', 'xor', ('v', a), ('v', b))))]
        if kind == 1:
            a, b = self.tmp('ta'), self.tmp('tb')
            return [('if', self.cond(vs + [acc]),
                     [self.asg(a, self.expr(vs + [acc])), self.asg(acc, ('b', '+', ('v', acc), ('v', a)))],
                     [self.asg(b, self.expr(vs + [acc])), self.asg(acc, ('b', 'xor', ('v', acc), ('v', b)))])]
        if kind == 2:
            i = self.tmp('ti', False)
            a, b = self.tmp('ta'), self.tmp('tb')
            return [('for', i, 1, 2 + r.below(5),
                     [self.asg(a, self.expr(vs + [acc, i])), self.asg(b, ('sh', 'shl', ('v', a), 1)),
                      self.asg(acc, ('b', 'xor', ('v', acc), ('b', '+', ('v', b), ('v', i))))])]
        if kind == 3:
            i = self.tmp('ti', False)
            a = self.tmp('ta')
            return [self.asg(a, ('c', 0)),
                    ('for', i, 1, 2 + r.below(5), [self.asg(a, ('b', '+', ('v', a), ('b', '*', ('v', i), self.expr(vs, 1))))]),
                    self.asg(acc, ('b', '+', ('v', acc), ('v', a)))]
        if kind == 4:
            n = self.tmp('tn', False)
            a = self.tmp('ta')
            return [self.asg(n, ('c', 1 + r.below(5))),
                    ('while', ('cmp', '>', ('v', n), ('c', 0)),
                     [self.asg(a, self.expr(vs + [acc, n])), self.asg(acc, ('b', '+', ('v', acc), ('v', a))),
                      self.asg(n, ('b', '-', ('v', n), ('c', 1)))])]
        if kind == 5:
            n = self.tmp('tn', False)
            a = self.tmp('ta')
            return [self.asg(n, ('c', 1 + r.below(5))),
                    ('repeat', [self.asg(a, self.expr(vs + [acc, n])), self.asg(acc, ('b', 'xor', ('v', acc), ('v', a))),
                                self.asg(n, ('b', '-', ('v', n), ('c', 1)))],
                     ('cmp', '<=', ('v', n), ('c', 0)))]
        if kind == 6:
            a, b, c = self.tmp('ta'), self.tmp('tb'), self.tmp('tc')
            return [('case', ('b', 'and', ('v', acc), ('c', 3)),
                     [([0], [self.asg(a, self.expr(vs)), self.asg(acc, ('b', '+', ('v', acc), ('v', a)))]),
                      ([1, 2], [self.asg(b, self.expr(vs + [acc])), self.asg(acc, ('b', 'xor', ('v', acc), ('v', b)))])],
                     [self.asg(c, self.expr(vs + [acc])), self.asg(acc, ('b', '-', ('v', acc), ('v', c)))])]
        if kind == 7:
            a = self.tmp('ta')
            return [self.asg(a, self.expr(vs + [acc])),
                    ('if', self.cond(vs + [acc]), [('exit', ('b', '+', ('v', acc), ('v', a)))], []),
                    self.asg(acc, ('b', '+', ('v', acc), ('v', a)))]
        if kind == 8:
            # a local no path may have written when it is read: it starts as zero
            z = self.tmp('tz')
            return [('if', self.cond(vs), [self.asg(z, self.expr(vs + [acc]))], []),
                    self.asg(acc, ('b', '+', ('v', acc), ('v', z)))]
        if kind == 9:
            # two loops, a value of the first read in the second
            i, j = self.tmp('ti', False), self.tmp('tj', False)
            a = self.tmp('ta')
            return [self.asg(a, ('c', 0)),
                    ('for', i, 1, 3, [self.asg(a, ('b', '+', ('v', a), ('b', '*', ('v', i), ('c', 3))))]),
                    ('for', j, 1, 2 + r.below(3), [self.asg(acc, ('b', '+', ('v', acc), ('b', 'xor', ('v', a), ('v', j))))])]
        if kind == 11:
            # a value read at every pass of a loop, before the pass's own temps
            a, b = self.tmp('ta'), self.tmp('tb')
            i = self.tmp('ti', False)
            return [self.asg(a, self.expr(vs + [acc])),
                    ('for', i, 1, 2 + r.below(4),
                     [self.asg(acc, ('b', '+', ('v', acc), ('v', a))),
                      self.asg(b, self.expr(vs + [acc, i])),
                      self.asg(acc, ('b', 'xor', ('v', acc), ('v', b)))])]
        # 10: an if in a loop, the inner temps of one pass
        i = self.tmp('ti', False)
        a, b = self.tmp('ta'), self.tmp('tb')
        return [('for', i, 1, 3 + r.below(4),
                 [('if', self.cond(vs + [acc, i]),
                   [self.asg(a, self.expr(vs + [acc, i])), self.asg(acc, ('b', '+', ('v', acc), ('v', a)))],
                   [self.asg(b, self.expr(vs + [acc, i])), self.asg(acc, ('b', '-', ('v', acc), ('v', b)))])])]

    def build(self, phases):
        r = self.rng
        self.local('acc', 'Int64')
        b = [self.asg('acc', ('b', 'xor', ('v', 'x'), ('b', '*', ('v', 'y'), ('c', 31))))]
        keep = None
        for k in range(phases):
            if keep is None and k == 0 and r.below(2) == 0:
                keep = self.local('kp', 'Int64')
                b.append(self.asg(keep, self.expr(['x', 'y', 'acc'])))
            vs = ['x', 'y'] + ([keep] if keep else [])
            b.extend(self.phase(r.below(12), vs))
        if keep:
            b.append(self.asg('acc', ('b', '+', ('v', 'acc'), ('v', keep))))
        self.body = b
        if self.call:
            # a call in the routine: it is not one of the call-free kind
            self.body.insert(1, ('callmix',))

    # the Python run
    def run(self, x, y):
        env = {'x': x, 'y': y}
        self.types = dict(self.locals)
        try:
            self.exec_list(self.body, env)
        except Exit as e:
            return e.v
        return env.get('acc', 0)

    def exec_list(self, ss, env):
        for s in ss:
            self.exec1(s, env)

    def setv(self, env, v, val):
        env[v] = cut(val, self.types.get(v, 'Int64'))

    def exec1(self, s, env):
        k = s[0]
        if k == 'asg':
            self.setv(env, s[1], ev(s[2], env))
        elif k == 'if':
            self.exec_list(s[2] if evc(s[1], env) else s[3], env)
        elif k == 'for':
            for i in range(s[2], s[3] + 1):
                env[s[1]] = i
                self.exec_list(s[4], env)
        elif k == 'while':
            while evc(s[1], env):
                self.exec_list(s[2], env)
        elif k == 'repeat':
            while True:
                self.exec_list(s[1], env)
                if evc(s[2], env):
                    break
        elif k == 'case':
            v = ev(s[1], env)
            for vals, body in s[2]:
                if v in vals:
                    self.exec_list(body, env)
                    return
            self.exec_list(s[3], env)
        elif k == 'exit':
            raise Exit(ev(s[1], env))
        elif k == 'callmix':
            env['acc'] = s64(env.get('acc', 0) * 3 + 1)


class Exit(Exception):
    def __init__(self, v):
        self.v = v


def stmts_txt(ss, ind, R):
    out = []
    p = '  ' * ind
    for s in ss:
        k = s[0]
        if k == 'asg':
            t = R.types.get(s[1], 'Int64')
            e = ptxt(s[2], R)
            out.append('%s%s := %s;' % (p, s[1], e if t == 'Int64' else '%s(%s)' % (t, e)))
        elif k == 'if':
            out.append('%sif %s then' % (p, ctxt(s[1], R)))
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
        elif k == 'while':
            out.append('%swhile %s do' % (p, ctxt(s[1], R)))
            out.append('%sbegin' % p)
            out.extend(stmts_txt(s[2], ind + 1, R))
            out.append('%send;' % p)
        elif k == 'repeat':
            out.append('%srepeat' % p)
            out.extend(stmts_txt(s[1], ind + 1, R))
            out.append('%suntil %s;' % (p, ctxt(s[2], R)))
        elif k == 'case':
            out.append('%scase %s of' % (p, ptxt(s[1], R)))
            for vals, body in s[2]:
                out.append('%s  %s:' % (p, ', '.join(str(v) for v in vals)))
                out.append('%s  begin' % p)
                out.extend(stmts_txt(body, ind + 2, R))
                out.append('%s  end;' % p)
            out.append('%selse' % p)
            out.append('%sbegin' % p)
            out.extend(stmts_txt(s[3], ind + 1, R))
            out.append('%send;' % p)
            out.append('%send;' % p)
        elif k == 'exit':
            out.append('%sExit(%s);' % (p, ptxt(s[1], R)))
        elif k == 'callmix':
            out.append('%sacc := Mix(acc, 2);' % p)
    return out


def main():
    rng = Rng(510)
    R = []
    typs = ['Int64'] * 5 + ['Byte', 'Word', 'Int32', 'Int8']
    for n in range(36):
        t = typs[n % len(typs)]
        # few phases: fewer than nine locals, no sharing; many: nine or more
        phases = 2 + (n % 3) if n % 6 == 5 else 6 + (n % 5)
        R.append(Routine('R%02d' % n, rng, t, phases, call=(n % 9 == 8)))
    # one of forty-odd locals, whose frame the Makefile reads
    R.append(Routine('RWide', rng, 'Int64', 20))
    inputs = [(0, 0), (1, -1), (7, 300), (-123456789, 98765), (0x7FFFFFFFFFFFFFFF, 3), (-9223372036854775807 - 1, 5), (65537, -65537), (4242, 17)]
    P = []
    X = []
    P.append("""program slots;

{ Routines of many integer locals whose lives do not meet (P510), beside
  the ones whose lives meet and the ones that start as zero, in every shape
  of statement: scripts/gen_slots.py makes the routines from a seed and
  works out the output by running the same tree in Python. }

function Mix(a: Int64; d: Integer): Int64;
begin
  if d <= 0 then
    Result := a * 3 + 1
  else
    Result := Mix(a, d - 1);
end;
""")
    for r in R:
        r.types = dict(r.locals)
        P.append('\nfunction %s(x, y: Int64): Int64;\nvar' % r.name)
        for nm, t in r.locals:
            P.append('  %s: %s;' % (nm, t))
        P.append('begin')
        P.extend(stmts_txt(r.body, 1, r))
        P.append('  Result := acc;')
        P.append('end;')
    P.append('\nbegin')
    for r in R:
        for (x, y) in inputs:
            xs = 'Low(Int64)' if x == -(1 << 63) else ('(%d)' % x if x < 0 else str(x))
            ys = '(%d)' % y if y < 0 else str(y)
            P.append("  WriteLn('%s %d %d ', %s(%s, %s));" % (r.name, x, y, r.name, xs, ys))
            v = r.run(x, y)
            X.append('%s %d %d %d\n' % (r.name, x, y, v))
    P.append('end.')
    return '\n'.join(P) + '\n', ''.join(X), R


prog, out, R = main()
emit(OUT + '.paslang', prog)
emit(OUT + '.out', out)
