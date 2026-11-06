#!/usr/bin/env python3
"""A differential fuzzer for the runtime's failures taken by handlers (P567): random routines and main blocks whose
statements read and write arrays at indexes that may be out of range and divide by values that may be zero, inside
try/except and try/finally blocks, nested, in loops, with handlers that print every variable and go on.  A Python
model of the language (64-bit wrapping integers, an index outside its array and a zero divisor raise) gives the
output: what each handler sees of the variables at the failure (a region may have kept them in registers), which
handler takes it, what the finally parts did, and the state at the end.  Every variant must agree with the model.

usage: fuzz_faults.py --paslangc BIN --units DIR --work DIR [--variants LIST] [--units-arm64 DIR] [--qemu BIN]
                      FIRSTSEED COUNT
  --variants   comma-separated: native (the default), base (-cpu base -inline 0), gc (base under the collector's
               stress), arm64 and arm64base (those two need --units-arm64 and --qemu)
  --work       a directory for the programs; a seed that agrees leaves nothing there
Exit status 1 when a variant differs from the model.  make check runs a few seeds; a compiler change that touches
the regions, the failures or the try blocks wants a few hundred on every variant."""
import os
import random
import subprocess
import sys

M64 = 1 << 64


def w(x):
    x &= M64 - 1
    return x - M64 if x >= 1 << 63 else x


class OOB(Exception):
    pass


class DivZ(Exception):
    pass


def tdiv(a, b):
    if b == 0:
        raise DivZ()
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def tmod(a, b):
    if b == 0:
        raise DivZ()
    r = abs(a) % abs(b)
    return -r if a < 0 else r


def ix(arr, i):
    if i < 0 or i >= len(arr):
        raise OOB()
    return i


NA, NB = 8, 5
CMP = ['<', '<=', '=', '<>', '>', '>=']
PYCMP = {'<': '<', '<=': '<=', '=': '==', '<>': '!=', '>': '>', '>=': '>='}
CONSTS = [0, 1, 2, 3, 5, 7, 9, 255, 1000, -1, -4, 1 << 40, -(1 << 33)]


class Gen:
    """One body: Pascal lines and the model's lines side by side.  S the scalars, C the counters, N the read-only one."""

    def __init__(self, rnd, S, C, N, tag):
        self.r = rnd
        self.S, self.C, self.N, self.tag = S, C, N, tag
        self.busy = []      # counters of the loops around
        self.tid = 0
        self.budget = 40    # statements left

    def state(self):
        names = self.S + self.C
        pas = ", ' ', ".join(names)
        py = ', '.join(names)
        return pas, py

    def say(self, what, ind, pind):
        pas, py = self.state()
        return ([ind + "WriteLn('%s ', %s);" % (what, pas)], [pind + "P('%s', %s)" % (what, py)])

    # ---- expressions: (pascal, python) ----
    def idx(self):
        r = self.r
        f = r.random()
        if self.busy and f < 0.55:
            c = r.choice(self.busy)
            g = r.random()
            if g < 0.6:
                return c, c
            k = r.randint(1, 3)
            if g < 0.8:
                return '%s + %d' % (c, k), 'w(%s + %d)' % (c, k)
            return '%s - %d' % (c, k), 'w(%s - %d)' % (c, k)
        if f < 0.75:
            v = r.choice(self.S)
            m = r.choice([3, 7, 7, 15])
            return '(%s and %d)' % (v, m), '(%s & %d)' % (v, m)
        if f < 0.9:
            # a constant index, inside the arrays or past their end: one outside a static array is a failure the
            # compiler writes in place (P571)
            k = r.randint(0, 9)
            return str(k), str(k)
        return self.N, self.N

    def rd(self):
        r = self.r
        ip, iy = self.idx()
        f = r.random()
        if f < 0.4:
            return 'ga[%s]' % ip, 'ga[ix(ga, %s)]' % iy
        if f < 0.65:
            return 'gb[%s]' % ip, 'gb[ix(gb, %s)]' % iy
        if f < 0.85:
            return 'gd[%s]' % ip, 'gd[ix(gd, %s)]' % iy
        return 'Rd(%s)' % ip, 'rd(%s)' % iy

    def expr(self, depth, reads=True):
        r = self.r
        if depth <= 0 or r.random() < 0.3:
            k = r.random()
            if reads and k < 0.45:
                return self.rd()
            if k < 0.8:
                v = r.choice(self.S + self.busy + [self.N])
                return v, v
            c = r.choice(CONSTS)
            return ('(%d)' % c if c < 0 else str(c)), str(c)
        op = r.choice(['+', '-', '*', '+', '-', 'and', 'or', 'xor'])
        lp, ly = self.expr(depth - 1, reads)
        rp, ry = self.expr(depth - 1, reads)
        if op in '+-*':
            return '(%s %s %s)' % (lp, op, rp), 'w(%s %s %s)' % (ly, op, ry)
        return '(%s %s %s)' % (lp, op, rp), '(%s %s %s)' % (ly, {'and': '&', 'or': '|', 'xor': '^'}[op], ry)

    def cond(self, reads=True):
        r = self.r
        c = r.choice(CMP)
        lp, ly = self.expr(1, reads)
        rp, ry = self.expr(1, reads)
        return '(%s %s %s)' % (lp, c, rp), '(%s %s %s)' % (ly, PYCMP[c], ry)

    # ---- statements: (pascal lines, python lines) ----
    def simple(self, ind, pind):
        """an assignment that cannot fail: a handler's or a finally's own"""
        r = self.r
        v = r.choice(self.S)
        ep, ey = self.expr(1, reads=False)
        return [ind + '%s := %s;' % (v, ep)], [pind + '%s = %s' % (v, ey)]

    def block(self, depth, ind, pind, inloop, n):
        pas, py = [], []
        for _ in range(n):
            a, b = self.stmt(depth, ind, pind, inloop)
            pas += a
            py += b
        if not py:
            py = [pind + 'pass']
        return pas, py

    def stmt(self, depth, ind, pind, inloop):
        r = self.r
        self.budget -= 1
        f = r.random()
        free = [c for c in self.C if c not in self.busy]
        if depth <= 0 or self.budget <= 0 or f < 0.30:
            g = r.random()
            if g < 0.5:
                v = r.choice(self.S)
                ep, ey = self.expr(2)
                return [ind + '%s := %s;' % (v, ep)], [pind + '%s = %s' % (v, ey)]
            if g < 0.68:
                # a division: its operands read no array, so only the divisor can fail
                v = r.choice(self.S)
                ep, ey = self.expr(1, reads=False)
                u = r.choice(self.S + self.busy)
                op = r.choice(['div', 'mod'])
                fn = 'tdiv' if op == 'div' else 'tmod'
                return ([ind + '%s := %s %s (%s and 3);' % (v, ep, op, u)],
                        [pind + '%s = %s(%s, %s & 3)' % (v, fn, ey, u)])
            if g < 0.9:
                ip, iy = self.idx()
                ep, ey = self.expr(1)
                a = r.choice(['ga', 'gb', 'gd'])
                return ([ind + '%s[%s] := %s;' % (a, ip, ep)],
                        [pind + '_v = %s' % ey, pind + '%s[ix(%s, %s)] = _v' % (a, a, iy)])
            ip, iy = self.idx()
            ep, ey = self.expr(1, reads=False)
            return [ind + 'Wr(%s, %s);' % (ip, ep)], [pind + 'wr(%s, %s)' % (iy, ey)]
        if f < 0.42:
            cp, cy = self.cond()
            tp, ty = self.block(depth - 1, ind + '  ', pind + '    ', inloop, r.randint(1, 2))
            pas = [ind + 'if %s then' % cp, ind + 'begin'] + tp + [ind + 'end']
            py = [pind + 'if %s:' % cy] + ty
            if r.random() < 0.4:
                ep, ey = self.block(depth - 1, ind + '  ', pind + '    ', inloop, 1)
                pas += [ind + 'else', ind + 'begin'] + ep + [ind + 'end;']
                py += [pind + 'else:'] + ey
            else:
                pas[-1] += ';'
            return pas, py
        if f < 0.60 and free:
            c = r.choice(free)
            lo = r.randint(0, 3)
            hi = r.choice([4, 5, 7, 8, 9, 10])
            self.busy.append(c)
            bp, by = self.block(depth - 1, ind + '  ', pind + '    ', 'for', r.randint(1, 3))
            self.busy.pop()
            pas = [ind + 'for %s := %d to %d do' % (c, lo, hi), ind + 'begin'] + bp + [ind + 'end;', ind + '%s := 0;' % c]
            py = [pind + 'for %s in range(%d, %d):' % (c, lo, hi + 1)] + by + [pind + '%s = 0' % c]
            return pas, py
        if f < 0.68 and free:
            c = r.choice(free)
            k = r.randint(3, 10)
            cp, cy = self.cond()
            self.busy.append(c)
            bp, by = self.block(depth - 1, ind + '  ', pind + '    ', 'while', r.randint(1, 3))
            self.busy.pop()
            pas = ([ind + '%s := 0;' % c, ind + 'while (%s < %d) and %s do' % (c, k, cp), ind + 'begin'] + bp +
                   [ind + '  %s := %s + 1;' % (c, c), ind + 'end;', ind + '%s := 0;' % c])
            py = ([pind + '%s = 0' % c, pind + 'while %s < %d and %s:' % (c, k, cy)] + by +
                  [pind + '    %s += 1' % c, pind + '%s = 0' % c])
            return pas, py
        if f < 0.74 and free:
            c = r.choice(free)
            k = r.randint(2, 9)
            cp, cy = self.cond()
            self.busy.append(c)
            bp, by = self.block(depth - 1, ind + '  ', pind + '    ', 'while', r.randint(1, 3))
            self.busy.pop()
            pas = ([ind + '%s := 0;' % c, ind + 'repeat'] + bp +
                   [ind + '  %s := %s + 1;' % (c, c), ind + 'until (%s >= %d) or %s;' % (c, k, cp), ind + '%s := 0;' % c])
            py = ([pind + '%s = 0' % c, pind + 'while True:'] + by +
                  [pind + '    %s += 1' % c, pind + '    if %s >= %d or %s:' % (c, k, cy), pind + '        break',
                   pind + '%s = 0' % c])
            return pas, py
        if f < 0.92:
            self.tid += 1
            t = self.tid
            bp, by = self.block(depth - 1, ind + '  ', pind + '    ', inloop, r.randint(1, 3))
            pas = [ind + 'try'] + bp + [ind + 'except']
            py = [pind + 'try:'] + by
            for cls, exc, mark in (('ERangeError', 'OOB', 'R'), ('EDivByZero', 'DivZ', 'Z')):
                if r.random() < 0.15:
                    continue    # no handler of this class here: the failure goes on out
                sp, sy = self.say('%s%s%d' % (self.tag, mark, t), ind + '    ', pind + '    ')
                hp, hy = [], []
                for _ in range(r.randint(0, 2)):
                    a, b = self.simple(ind + '    ', pind + '    ')
                    hp += a
                    hy += b
                if r.random() < 0.15:
                    a, b = self.stmt(0, ind + '    ', pind + '    ', inloop)   # a handler that may fail itself
                    hp += a
                    hy += b
                pas += [ind + '  on Ex: %s do' % cls, ind + '  begin'] + sp + hp + [ind + '  end;']
                py += [pind + 'except %s:' % exc] + sy + hy
            if py[-1].endswith('try:') or not any(l.startswith(pind + 'except') for l in py):
                # no handler at all was chosen: a bare one
                sp, sy = self.say('%sB%d' % (self.tag, t), ind + '  ', pind + '    ')
                pas += sp
                py += [pind + 'except (OOB, DivZ):'] + sy
            pas += [ind + 'end;']
            return pas, py
        if f < 0.97:
            bp, by = self.block(depth - 1, ind + '  ', pind + '    ', inloop, r.randint(1, 2))
            fp, fy = self.simple(ind + '  ', pind + '    ')
            return [ind + 'try'] + bp + [ind + 'finally'] + fp + [ind + 'end;'], [pind + 'try:'] + by + [pind + 'finally:'] + fy
        if inloop == 'for':
            cp, cy = self.cond(reads=False)
            kw = r.choice(['Break', 'Continue'])
            return [ind + 'if %s then' % cp, ind + '  %s;' % kw], [pind + 'if %s:' % cy, pind + '    %s' % kw.lower()]
        if inloop == 'while':
            cp, cy = self.cond(reads=False)
            return [ind + 'if %s then' % cp, ind + '  Break;'], [pind + 'if %s:' % cy, pind + '    break']
        return self.simple(ind, pind)


FS = ['a', 'b', 'c', 'd', 'e']
FC = ['i', 'j', 'k', 'l']
MS = ['ma', 'mb', 'mc', 'md', 'me']
MC = ['mi', 'mj', 'mk', 'ml']


def build(seed):
    rnd = random.Random(seed)
    nfun = 2
    funs = []
    for f in range(nfun):
        g = Gen(rnd, FS, FC, 'n', 'F%d' % f)
        bp, by = g.block(3, '    ', '        ', '', rnd.randint(3, 6))
        funs.append((g, bp, by))
    gm = Gen(rnd, MS, MC, 'mn', 'M')
    mp, my = gm.block(3, '    ', '        ', '', rnd.randint(3, 6))
    cases = [(rnd.choice([0, 1, 2, 3, 5, 7, 8, 12]), rnd.choice([0, 3, 6, 10])) for _ in range(6)]
    src = ['program ft;', '', 'uses', '  sysutils;', '', 'type', '  TA = array[0..%d] of Int64;' % (NA - 1),
           '  TB = array[0..%d] of Int64;' % (NB - 1), '', 'var', '  ga: TA;', '  gb: TB;', '  gd: array of Int64;',
           '  ' + ', '.join(MS + MC + ['mn', 'cs', 'dl', 'q']) + ': Int64;', '',
           'function Rd(I: Int64): Int64;', 'begin', '  Result := ga[I];', 'end;', '',
           'procedure Wr(I, V: Int64);', 'begin', '  gb[I] := V;', 'end;', '',
           'function Chk: Int64;', 'var', '  t, u: Int64;', 'begin', '  t := 0;',
           '  for u := 0 to %d do' % (NA - 1), '    t := t * 31 + ga[u];',
           '  for u := 0 to %d do' % (NB - 1), '    t := t * 31 + gb[u];',
           '  for u := 0 to Length(gd) - 1 do', '    t := t * 31 + gd[u];', '  Result := t;', 'end;', '']
    for f, (g, bp, by) in enumerate(funs):
        sp, sy = g.say('F%dRT' % f, '      ', '')
        zp, zy = g.say('F%dZT' % f, '      ', '')
        ep, ey = g.say('F%dend' % f, '  ', '')
        src += ['procedure F%d(N: Int64);' % f, 'var', '  ' + ', '.join(FS + FC) + ': Int64;', 'begin',
                '  a := N; b := 1; c := N * 3; d := 0; e := -N; i := 0; j := 0; k := 0; l := 0;',
                '  try'] + bp + ['  except', '    on Ex: ERangeError do'] + sp + ['    on Ex: EDivByZero do'] + zp + ['  end;'] + ep + ['end;', '']
    sp, sy = gm.say('MRT', '      ', '')
    zp, zy = gm.say('MZT', '      ', '')
    ep, ey = gm.say('Mend', '  ', '')
    src += ['begin', '  cs := StrToInt(ParamStr(1));', '  case cs of']
    for c, (n, ln) in enumerate(cases):
        src.append('    %d: begin mn := %d; dl := %d; end;' % (c, n, ln))
    src += ['  else', '    Halt(3);', '  end;', '  SetLength(gd, dl);',
            '  for q := 0 to %d do' % (NA - 1), '    ga[q] := q * 7 - 3;',
            '  for q := 0 to %d do' % (NB - 1), '    gb[q] := 100 - q * 9;',
            '  for q := 0 to dl - 1 do', '    gd[q] := q * q + 1;']
    for f in range(nfun):
        src.append('  F%d(mn);' % f)
    src += ['  ma := mn; mb := 1; mc := mn * 3; md := 0; me := -mn; mi := 0; mj := 0; mk := 0; ml := 0;',
            '  try'] + mp + ['  except', '    on Ex: ERangeError do'] + sp + ['    on Ex: EDivByZero do'] + zp + ['  end;'] + ep
    src += ["  WriteLn('chk ', Chk);", 'end.']
    # the model
    py = ['def rd(i): return ga[ix(ga, i)]', 'def wr(i, v):', '    gb[ix(gb, i)] = v']
    for f, (g, bp, by) in enumerate(funs):
        names = ', '.join(FS + FC)
        py += ['def f%d(n):' % f, '    a = n; b = 1; c = w(n * 3); d = 0; e = -n; i = j = k = l = 0',
               '    try:', '        pass'] + by + ['    except OOB:', "        P('F%dRT', %s)" % (f, names),
                                                   '    except DivZ:', "        P('F%dZT', %s)" % (f, names),
                                                   "    P('F%dend', %s)" % (f, names)]
    names = ', '.join(MS + MC)
    py += ['def main(mn):', '    ma = mn; mb = 1; mc = w(mn * 3); md = 0; me = -mn; mi = mj = mk = ml = 0',
           '    try:', '        pass'] + my + ['    except OOB:', "        P('MRT', %s)" % names,
                                               '    except DivZ:', "        P('MZT', %s)" % names,
                                               "    P('Mend', %s)" % names]
    return '\n'.join(src) + '\n', '\n'.join(py) + '\n', cases, nfun


def model(py, cases, nfun):
    outs = []
    for (n, ln) in cases:
        out = []
        ga = [q * 7 - 3 for q in range(NA)]
        gb = [100 - q * 9 for q in range(NB)]
        gd = [q * q + 1 for q in range(ln)]
        ns = {'w': w, 'ix': ix, 'tdiv': tdiv, 'tmod': tmod, 'OOB': OOB, 'DivZ': DivZ, 'ga': ga, 'gb': gb, 'gd': gd,
              'P': lambda *a: out.append(' '.join(str(x) for x in a))}
        exec(compile(py, 'model', 'exec'), ns)
        for f in range(nfun):
            ns['f%d' % f](n)
        ns['main'](n)
        t = 0
        for v in ga + gb + gd:
            t = w(t * 31 + v)
        out.append('chk %d' % t)
        outs.append('\n'.join(out) + '\n')
    return outs


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, **kw)


def main():
    a = sys.argv[1:]
    opt = {'--variants': 'native'}
    pos = []
    k = 0
    while k < len(a):
        if a[k].startswith('--'):
            opt[a[k]] = a[k + 1]
            k += 2
        else:
            pos.append(a[k])
            k += 1
    if len(pos) != 2 or not all(x in opt for x in ('--paslangc', '--units', '--work')):
        sys.exit(__doc__)
    first, count = int(pos[0]), int(pos[1])
    cc = os.path.abspath(opt['--paslangc'])
    units = os.path.abspath(opt['--units'])
    work = os.path.abspath(opt['--work'])
    variants = opt['--variants'].split(',')
    arm = os.path.abspath(opt.get('--units-arm64', '.'))
    qemu = os.path.abspath(opt.get('--qemu', 'qemu-aarch64'))
    owner = None
    if os.geteuid() == 0:
        # root over another's tree: the programs are that user's, compiled and run as that user
        import pwd
        owner = pwd.getpwuid(os.stat(units).st_uid).pw_name
    bad = 0
    nrun = nflt = 0
    os.makedirs(work, exist_ok=True)
    for seed in range(first, first + count):
        prog, py, cases, nfun = build(seed)
        d = os.path.join(work, 't%d' % seed)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, 'ft.paslang'), 'w').write(prog)
        open(os.path.join(d, 'ft.py'), 'w').write(py)
        if owner:
            sh(['chown', '-R', owner, work])
        try:
            exp = model(py, cases, nfun)
        except Exception as e:
            print('seed', seed, 'MODEL FAILED', repr(e)[:200])
            bad += 1
            continue
        nrun += len(exp)
        nflt += sum(sum(1 for l in x.split('\n') if l[:1] in 'FM' and 'end' not in l.split(' ')[0]) for x in exp)
        failed = False
        for v in variants:
            env = dict(os.environ)
            if v == 'native':
                cmd, run_ = [cc, '-Fu', units, '-o', 'ft_n', 'ft.paslang'], ['./ft_n']
            elif v in ('base', 'gc'):
                cmd, run_ = [cc, '-Fu', units, '-inline', '0', '-cpu', 'base', '-o', 'ft_b', 'ft.paslang'], ['./ft_b']
                if v == 'gc':
                    env.update(PASLANG_GCVERIFY='1', PASLANG_GCSTRESS='3', PASLANG_GCPOISON='1')
            elif v == 'arm64':
                cmd, run_ = [cc, '-target', 'arm64', '-cpu', 'max', '-Fu', arm, '-o', 'ft_a', 'ft.paslang'], [qemu, './ft_a']
            elif v == 'arm64base':
                cmd, run_ = [cc, '-target', 'arm64', '-cpu', 'base', '-inline', '0', '-Fu', arm, '-o', 'ft_ab', 'ft.paslang'], [qemu, './ft_ab']
            else:
                sys.exit('unknown variant ' + v)
            pre = ['runuser', '-u', owner, '--'] if owner else []
            r = sh(pre + ['sh', '-c', 'ulimit -v 4194304; exec timeout 120 "$0" "$@"'] + cmd, cwd=d)
            if r.returncode:
                print('seed', seed, v, 'COMPILE FAILED', r.stderr[-300:].decode('utf-8', 'replace'))
                failed = True
                continue
            for c, want in enumerate(exp):
                r = sh(pre + ['timeout', '120'] + run_ + [str(c)], cwd=d, env=env)
                got = r.stdout.decode()
                if got != want or r.returncode != 0:
                    gl, wl = got.split('\n'), want.split('\n')
                    at = next((n for n in range(min(len(gl), len(wl))) if gl[n] != wl[n]), min(len(gl), len(wl)))
                    print('seed', seed, v, 'case', c, cases[c], 'DIFFERS at line', at, 'got', repr(gl[at][:90] if at < len(gl) else ''),
                          'the model', repr(wl[at][:90] if at < len(wl) else ''), 'exit', r.returncode, r.stderr[-120:])
                    failed = True
        if failed:
            bad += 1
        else:
            sh(['rm', '-rf', d])
    print('fuzz_faults: seeds', first, 'to', first + count - 1, 'variants', ','.join(variants), 'runs', nrun, 'handlers entered', nflt, 'problems', bad)
    sys.exit(1 if bad else 0)


main()
