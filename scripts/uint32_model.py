# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Pure integer expression generator and independent arbitrary-precision model.

The model preserves Pascal context widths, conversions, calls and statement
effects. It never imports compiler output or executes generated programs.
"""
import random

M64 = (1 << 64) - 1


def s64(x):
    x &= M64
    return x - (1 << 64) if x >> 63 else x


def tdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def tmod(a, b):
    return a - tdiv(a, b) * b


CONV = {'Byte': (8, False), 'Int8': (8, True), 'Word': (16, False), 'Int16': (16, True),
        'UInt32': (32, False), 'Int32': (32, True)}


def conv(t, v):
    bits, signed = CONV[t]
    v &= (1 << bits) - 1
    if signed and v >> (bits - 1):
        v -= 1 << bits
    return v


NT = {'Byte': (8, False), 'Int8': (8, True), 'Word': (16, False), 'Int16': (16, True),
      'UInt32': (32, False), 'Int32': (32, True), 'Integer': (64, True)}
NVAR = {'Byte': 'vB', 'Int8': 'vS', 'Word': 'vW', 'Int16': 'vI', 'UInt32': 'vU', 'Int32': 'vL'}
VARTYPE = {v: k for k, v in NVAR.items()}
# which types widen implicitly into which
WIDENS = {'Byte': ['Byte', 'Word', 'Int16', 'UInt32', 'Int32', 'Integer'],
          'Int8': ['Int8', 'Int16', 'Int32', 'Integer'],
          'Word': ['Word', 'UInt32', 'Int32', 'Integer'],
          'Int16': ['Int16', 'Int32', 'Integer'],
          'UInt32': ['UInt32', 'Integer'],
          'Int32': ['Int32', 'Integer'],
          'Integer': ['Integer']}


def wrap_t(t, v):
    bits, signed = NT[t]
    v &= (1 << bits) - 1
    if signed and v >> (bits - 1):
        v -= 1 << bits
    return v


def shift_right(typ, value, count):
    """SHR uses the sign in signed narrow contexts and is logical in Integer."""
    count &= 63
    if typ in ("Int8", "Int16", "Int32"):
        return wrap_t(typ, value >> count)
    return wrap_t(typ, (value & M64) >> count)


def trange(t):
    bits, signed = NT[t]
    return (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if signed else (0, (1 << bits) - 1)


CONSTS = [0, 1, 2, 3, 5, 7, 9, 10, 13, 60, 100, 255, 256, 1000, 2141, 3600, 4096, 65535, 65536, 86400, 146097,
          0x7FFFFFFF, 0xFFFFFFFF, 1 << 31, 1 << 32, 1 << 40, (1 << 52) - 1, 1 << 61, (1 << 62) - 1, 1234567891,
          -1, -2, -3, -7, -100, -256, -65536, -(1 << 31), -(1 << 40), -(1 << 61), 1000000007, 2939745]
MASKS = [1, 3, 7, 15, 255, 0xFFF, 0xFFFF, 0xFFFFF, 0xFFFFFF, 0x7FFFFFFF, 0xFFFFFFFF, (1 << 40) - 1, (1 << 62) - 1,
         (1 << 63) - 1]
DIVS = [2, 3, 5, 6, 7, 9, 10, 12, 13, 24, 60, 100, 255, 256, 641, 1000, 2141, 3600, 4096, 65521, 86400, 146097,
        1000003, 2939745, 4294967295, 1000000007, 1 << 40, -3, -10, -256]


class Gen:
    def __init__(self, rnd, nfun, nproc=0):
        self.r = rnd
        self.nfun = nfun
        self.nproc = nproc

    def const(self):
        if self.r.random() < 0.25:
            return ('c', self.r.randint(-20, 40))
        if self.r.random() < 0.1:
            return ('c', self.r.randint(-(1 << 62), (1 << 62)))
        return ('c', self.r.choice(CONSTS))

    def expr(self, depth, vars_, fi):
        self.vars_ = vars_
        return self.expr0(depth, vars_, fi)

    def nv(self, e):
        """a constant child is replaced by a variable: no subtree is made of constants alone"""
        return ('v', self.r.choice(self.vars_)) if e[0] == 'c' else e

    def expr0(self, depth, vars_, fi):
        r = self.r
        if depth <= 0 or r.random() < 0.18:
            return ('v', r.choice(vars_)) if r.random() < 0.7 else self.const()
        k = r.random()
        if k < 0.46:
            op = r.choice(['+', '-', '*', 'and', 'or', 'xor'])
            if op == 'and' and r.random() < 0.5:
                return ('bin', 'and', self.nv(self.expr(depth - 1, vars_, fi)), ('c', r.choice(MASKS)))
            l, rt = self.expr(depth - 1, vars_, fi), self.expr(depth - 1, vars_, fi)
            if l[0] == 'c' and rt[0] == 'c':
                l = self.nv(l)
            return ('bin', op, l, rt)
        if k < 0.58:
            return ('bin', r.choice(['shl', 'shr']), self.nv(self.expr(depth - 1, vars_, fi)), ('c', r.randint(0, 63)))
        if k < 0.80:
            op = r.choice(['div', 'mod'])
            d = r.random()
            if d < 0.7:
                right = ('c', r.choice(DIVS))
            else:
                right = ('bin', '+', ('bin', 'and', self.expr(depth - 1, vars_, fi), ('c', 15)), ('c', 1))
            left = self.nv(self.expr(depth - 1, vars_, fi))
            if r.random() < 0.5:
                left = ('bin', 'and', left, ('c', r.choice(MASKS)))
            elif r.random() < 0.3:
                left = ('bin', 'shr', left, ('c', r.randint(1, 63)))
            return ('bin', op, left, right)
        if k < 0.88:
            return ('un', 'not', self.nv(self.expr(depth - 1, vars_, fi)))
        if k < 0.94:
            inner = self.nv(self.expr(depth - 1, vars_, fi))
            return ('conv', r.choice(list(CONV)), inner)
        if fi > 0:
            return ('call', r.randrange(fi), [self.expr(depth - 1, vars_, fi) for _ in range(3)])
        return ('un', 'neg', self.nv(self.expr(depth - 1, vars_, fi)))

    def expr_t(self, t, depth):
        return self.expr_t0(t, depth)

    def ntv(self, e, t):
        if e[0] == 'tc':
            return ('tv', self.r.choice([NVAR[u] for u in NVAR if t in WIDENS[u]]), t)
        return e

    def expr_t0(self, t, depth):
        """an expression worked out in the type t: leaves are variables whose type widens into t and
        constants that fit t"""
        r = self.r
        lo, hi = trange(t)
        leaves = [NVAR[u] for u in NVAR if t in WIDENS[u]]
        if depth <= 0 or r.random() < 0.2:
            if leaves and r.random() < 0.75:
                return ('tv', r.choice(leaves), t)
            c = r.choice([0, 1, 2, 3, 7, 10, 100, 127, 128, 255, 256, 1000, 32767, 65535, 2147483647, -1, -5, -128, -32768, r.randint(lo, hi)])
            if not (lo <= c <= hi):
                c = r.randint(max(lo, -20), min(hi, 40))
            return ('tc', c, t)
        k = r.random()
        if k < 0.55:
            l, rt = self.expr_t(t, depth - 1), self.expr_t(t, depth - 1)
            if l[0] == 'tc' and rt[0] == 'tc':
                l = self.ntv(l, t)
            return ('tb', r.choice(['+', '-', '*', 'and', 'or', 'xor']), l, rt, t)
        if k < 0.68:
            return ('ts', r.choice(['shl', 'shr']), self.ntv(self.expr_t(t, depth - 1), t), r.randint(0, 63), t)
        if k < 0.85:
            op = r.choice(['div', 'mod'])
            if r.random() < 0.6:
                c = r.choice([2, 3, 5, 7, 10, 13, 100, 127])
                c = min(c, hi)
                right = ('tc', c, t)
            else:
                right = ('tb', '+', ('tb', 'and', self.ntv(self.expr_t(t, depth - 1), t), ('tc', min(15, hi), t), t), ('tc', 1, t), t)
            return ('tb', op, self.ntv(self.expr_t(t, depth - 1), t), right, t)
        if k < 0.93:
            return ('tu', r.choice(['not', 'neg']), self.ntv(self.expr_t(t, depth - 1), t), t)
        # a conversion of an Integer expression with a variable in it
        iv = ['a', 'b', 'c', 'x', 'y', 'z', 'w']
        return ('tcv', t, self.nv_(self.expr(2, iv, 0), iv), t)

    def nv_(self, e, iv):
        return ('v', self.r.choice(iv)) if e[0] == 'c' else e

    def cond(self, depth, vars_, fi):
        r = self.r
        if depth > 0 and r.random() < 0.3:
            op = r.choice(['and', 'or'])
            return ('cb', op, self.cond(depth - 1, vars_, fi), self.cond(depth - 1, vars_, fi))
        return ('cmp', r.choice(['<', '<=', '>', '>=', '=', '<>']), self.expr(2, vars_, fi), self.expr(2, vars_, fi))

    def stmts(self, depth, vars_, loopvars, fi, n, targets=('x', 'y', 'z', 'w'), canpcall=True, typed=True):
        out = []
        for _ in range(n):
            r = self.r.random()
            if canpcall and self.nproc and self.r.random() < 0.2:
                a, b = self.r.sample(['x', 'y', 'z', 'w'], 2)
                out.append(('pcall', self.r.randrange(self.nproc), [self.expr(2, vars_ + loopvars, fi), self.expr(2, vars_ + loopvars, fi)], [a, b]))
                continue
            if typed and self.r.random() < 0.35:
                t = self.r.choice(list(NVAR))
                out.append(('asgt', NVAR[t], t, self.expr_t(t, self.r.randint(1, 4))))
                continue
            if r < 0.5 or depth <= 0:
                out.append(('asg', self.r.choice(list(targets)), self.expr(3, vars_ + loopvars, fi)))
            elif r < 0.72:
                out.append(('if', self.cond(1, vars_ + loopvars, fi), self.stmts(depth - 1, vars_, loopvars, fi, self.r.randint(1, 2), targets, canpcall, typed),
                            self.stmts(depth - 1, vars_, loopvars, fi, self.r.randint(0, 2), targets, canpcall, typed)))
            elif r < 0.9 and len(loopvars) < 3:
                lv = ['i', 'j', 'k'][len(loopvars)]
                lo, hi = self.r.randint(0, 3), self.r.randint(3, 11)
                out.append(('for', lv, lo, hi, self.r.random() < 0.3,
                            self.stmts(depth - 1, vars_, loopvars + [lv], fi, self.r.randint(1, 3), targets, canpcall, typed)))
            else:
                out.append(('while', self.r.randint(2, 9), self.stmts(depth - 1, vars_, loopvars, fi, self.r.randint(1, 2), targets, canpcall, typed)))
        return out


def has_var_t(e):
    k = e[0]
    if k == 'tv' or k == 'tcv':
        return True
    if k == 'tc':
        return False
    if k == 'tb':
        return has_var_t(e[2]) or has_var_t(e[3])
    if k in ('ts', 'tu'):
        return has_var_t(e[2])
    return True


def has_var(e):
    if e[0] == 'v':
        return True
    if e[0] == 'c':
        return False
    if e[0] == 'bin':
        return has_var(e[2]) or has_var(e[3])
    if e[0] in ('un', 'conv'):
        return has_var(e[2])
    return True


def pas_t(e):
    t = e[0]
    if t == 'tv':
        return e[1]
    if t == 'tc':
        return '(%d)' % e[1] if e[1] < 0 else str(e[1])
    if t == 'tb':
        return '(%s %s %s)' % (pas_t(e[2]), e[1], pas_t(e[3]))
    if t == 'ts':
        return '(%s %s %d)' % (pas_t(e[2]), e[1], e[3])
    if t == 'tu':
        return '(not %s)' % pas_t(e[2]) if e[1] == 'not' else '(-%s)' % pas_t(e[2])
    if t == 'tcv':
        return '%s(%s)' % (e[1], pas_expr(e[2]))
    raise ValueError(t)


def pas_expr(e):
    t = e[0]
    if t == 'c':
        v = e[1]
        if v == -(1 << 63):
            return '(-9223372036854775807 - 1)'
        return '(%d)' % v if v < 0 else str(v)
    if t == 'v':
        return 'Integer(%s)' % e[1] if e[1] in VARTYPE else e[1]
    if t == 'bin':
        return '(%s %s %s)' % (pas_expr(e[2]), e[1], pas_expr(e[3]))
    if t == 'un':
        return '(not %s)' % pas_expr(e[2]) if e[1] == 'not' else '(-%s)' % pas_expr(e[2])
    if t == 'conv':
        return 'Integer(%s(%s))' % (e[1], pas_expr(e[2]))
    if t == 'call':
        return 'F%d(%s)' % (e[1], ', '.join(pas_expr(a) for a in e[2]))
    raise ValueError(t)


def pas_cond(c):
    if c[0] == 'cb':
        return '(%s %s %s)' % (pas_cond(c[2]), c[1], pas_cond(c[3]))
    return '(Integer(%s) %s Integer(%s))' % (pas_expr(c[2]), c[1], pas_expr(c[3]))


def pas_stmts(ss, ind, wd=0):
    out = []
    p = '  ' * ind
    for s in ss:
        if s[0] == 'asg':
            out.append('%s%s := %s;' % (p, s[1], pas_expr(s[2])))
        elif s[0] == 'if':
            out.append('%sif %s then' % (p, pas_cond(s[1])))
            out.append('%sbegin' % p)
            out += pas_stmts(s[2], ind + 1, wd)
            if s[3]:
                out.append('%send' % p)
                out.append('%selse' % p)
                out.append('%sbegin' % p)
                out += pas_stmts(s[3], ind + 1, wd)
            out.append('%send;' % p)
        elif s[0] == 'for':
            lv, lo, hi, down, body = s[1:]
            if down:
                out.append('%sfor %s := %d downto %d do' % (p, lv, hi, lo))
            else:
                out.append('%sfor %s := %d to %d do' % (p, lv, lo, hi))
            out.append('%sbegin' % p)
            out += pas_stmts(body, ind + 1, wd)
            out.append('%send;' % p)
        elif s[0] == 'asgt':
            out.append('%s%s := %s;' % (p, s[1], pas_t(s[3])))
        elif s[0] == 'pcall':
            out.append('%sP%d(%s, %s, %s, %s);' % (p, s[1], pas_expr(s[2][0]), pas_expr(s[2][1]), s[3][0], s[3][1]))
        elif s[0] == 'while':
            cn = 'cnt%d' % wd
            out.append('%s%s := 0;' % (p, cn))
            out.append('%swhile %s < %d do' % (p, cn, s[1]))
            out.append('%sbegin' % p)
            out += pas_stmts(s[2], ind + 1, wd + 1)
            out.append('%s  %s := %s + 1;' % (p, cn, cn))
            out.append('%send;' % p)
    return out


def ev(e, env, funs):
    t = e[0]
    if t == 'c':
        return e[1]
    if t == 'v':
        return env[e[1]]
    if t == 'bin':
        a = ev(e[2], env, funs)
        b = ev(e[3], env, funs)
        op = e[1]
        if op == '+': return s64(a + b)
        if op == '-': return s64(a - b)
        if op == '*': return s64(a * b)
        if op == 'and': return a & b
        if op == 'or': return a | b
        if op == 'xor': return a ^ b
        if op == 'shl': return s64(a << b)
        if op == 'shr': return s64((a & M64) >> b)
        if op == 'div': return s64(tdiv(a, b))
        if op == 'mod': return s64(tmod(a, b))
    if t == 'un':
        a = ev(e[2], env, funs)
        return ~a if e[1] == 'not' else s64(-a)
    if t == 'conv':
        return conv(e[1], ev(e[2], env, funs))
    if t == 'call':
        return run_fun(funs, e[1], [ev(a, env, funs) for a in e[2]])
    raise ValueError(t)


def ev_t(e, env, funs):
    t = e[0]
    T = e[-1]
    if t == 'tv':
        return env[e[1]]
    if t == 'tc':
        return e[1]
    if t == 'tb':
        a = ev_t(e[2], env, funs)
        b = ev_t(e[3], env, funs)
        op = e[1]
        if op == '+': v = a + b
        elif op == '-': v = a - b
        elif op == '*': v = a * b
        elif op == 'and': v = a & b
        elif op == 'or': v = a | b
        elif op == 'xor': v = a ^ b
        elif op == 'div': v = tdiv(a, b)
        elif op == 'mod': v = tmod(a, b)
        return wrap_t(T, v)
    if t == 'ts':
        a = ev_t(e[2], env, funs)
        k = e[3]
        if e[1] == 'shl':
            return wrap_t(T, a << k)
        if T == 'Integer':
            return s64((a & M64) >> k)
        return wrap_t(T, a >> k)
    if t == 'tu':
        a = ev_t(e[2], env, funs)
        return wrap_t(T, ~a if e[1] == 'not' else -a)
    if t == 'tcv':
        return wrap_t(T, ev(e[2], env, funs))
    raise ValueError(t)


def evc(c, env, funs):
    if c[0] == 'cb':
        a = evc(c[2], env, funs)
        b = evc(c[3], env, funs)
        return (a and b) if c[1] == 'and' else (a or b)
    a = ev(c[2], env, funs)
    b = ev(c[3], env, funs)
    return {'<': a < b, '<=': a <= b, '>': a > b, '>=': a >= b, '=': a == b, '<>': a != b}[c[1]]


def run_proc(funs, j, a, b, r1, r2):
    body = funs['procs'][j]
    env = {'a': a, 'b': b, 'r1': r1, 'r2': r2, 'c': 0, 'x': 0, 'y': 0, 'z': 0, 'w': 0, 'i': 0, 'j': 0, 'k': 0}
    run_stmts(body, env, funs)
    return env['r1'], env['r2']


def run_stmts(ss, env, funs):
    for s in ss:
        if s[0] == 'asg':
            env[s[1]] = ev(s[2], env, funs)
        elif s[0] == 'asgt':
            env[s[1]] = ev_t(s[3], env, funs)
        elif s[0] == 'pcall':
            a = ev(s[2][0], env, funs)
            b = ev(s[2][1], env, funs)
            env[s[3][0]], env[s[3][1]] = run_proc(funs, s[1], a, b, env[s[3][0]], env[s[3][1]])
        elif s[0] == 'if':
            run_stmts(s[2] if evc(s[1], env, funs) else s[3], env, funs)
        elif s[0] == 'for':
            lv, lo, hi, down, body = s[1:]
            rng = range(hi, lo - 1, -1) if down else range(lo, hi + 1)
            for v in rng:
                env[lv] = v
                run_stmts(body, env, funs)
        elif s[0] == 'while':
            for _ in range(s[1]):
                run_stmts(s[2], env, funs)


def run_fun(funs, i, args):
    body, res = funs['f'][i]
    env = {'a': args[0], 'b': args[1], 'c': args[2], 'x': 0, 'y': 0, 'z': 0, 'w': 0, 'i': 0, 'j': 0, 'k': 0}
    for nm in NVAR.values():
        env[nm] = 0
    run_stmts(body, env, funs)
    return ev(res, env, funs)


INPUTS = [(0, 0, 0), (1, 2, 3), (-1, -2, -3), (255, 256, 65535), (1 << 31, -(1 << 31), 0x7FFFFFFF),
          (1 << 62, -(1 << 62), (1 << 62) - 1), (123456789012345, -987654321098765, 4242), (5, -7, 1000003),
          (-(1 << 63), (1 << 63) - 1, -1), (86400, 3600, 146097), (0xFFFFFFFF, 0x100000000, 99999),
          (-123, 4567, -(1 << 40))]


def build(seed):
    rnd = random.Random(seed)
    nfun = rnd.randint(3, 6)
    nproc = rnd.randint(0, 3)
    g = Gen(rnd, nfun, nproc)
    funs = {'f': [], 'procs': []}
    src = ['program fz;', '']
    for j in range(nproc):
        pv = ['a', 'b', 'r1', 'r2', 'x', 'y', 'z', 'w']
        g.nproc = 0
        init = [('asg', v, g.expr(2, ['a', 'b', 'r1', 'r2'], 0)) for v in ('x', 'y', 'z', 'w')]
        body = init + g.stmts(2, pv, [], 0, rnd.randint(2, 6), ('r1', 'r2', 'x', 'y', 'z', 'w'), False, False)
        g.nproc = nproc
        funs['procs'].append(body)
        src.append('procedure P%d(a, b: Integer; var r1, r2: Integer);' % j)
        src.append('var')
        src.append('  x, y, z, w, i, j, k, cnt0, cnt1, cnt2, cnt3, cnt4, c: Integer;')
        src.append('begin')
        src.append('  c := 0;')
        src += pas_stmts(body, 1)
        src.append('end;')
        src.append('')
    for i in range(nfun):
        vars_ = ['a', 'b', 'c', 'x', 'y', 'z', 'w'] + list(NVAR.values())
        init = [('asg', v, g.expr(2, ['a', 'b', 'c'], i)) for v in ('x', 'y', 'z', 'w')]
        body = init + g.stmts(2, vars_, [], i, rnd.randint(3, 7))
        res = g.expr(3, vars_, i)
        funs['f'].append((body, res))
        src.append('function F%d(a, b, c: Integer): Integer;' % i)
        src.append('var')
        src.append('  x, y, z, w, i, j, k, cnt0, cnt1, cnt2, cnt3, cnt4: Integer;')
        src.append('  vB: Byte;')
        src.append('  vS: Int8;')
        src.append('  vW: Word;')
        src.append('  vI: Int16;')
        src.append('  vU: UInt32;')
        src.append('  vL: Int32;')
        src.append('begin')
        src.append('  vB := 0; vS := 0; vW := 0; vI := 0; vU := 0; vL := 0;')
        src += pas_stmts(body, 1)
        src.append('  Result := %s;' % pas_expr(res))
        src.append('end;')
        src.append('')
    src.append('begin')
    exp = []
    for i in range(nfun):
        for (a, b, c) in INPUTS:
            lit = lambda v: '(-9223372036854775807 - 1)' if v == -(1 << 63) else ('(%d)' % v if v < 0 else str(v))
            src.append('  WriteLn(F%d(%s, %s, %s));' % (i, lit(a), lit(b), lit(c)))
            exp.append(str(run_fun(funs, i, [a, b, c])))
    src.append('end.')
    return '\n'.join(src) + '\n', '\n'.join(exp) + '\n'

