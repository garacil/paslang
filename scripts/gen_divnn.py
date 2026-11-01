#!/usr/bin/env python3
"""Writes testdata/divnn.paslang and testdata/divnn.out (P536): div and mod by a constant of
a value the compiler can prove not negative (a masked word, a shifted word, a narrow
unsigned variable, a counter, a remainder) across the edges of its range, and of values
it cannot (a word, a signed narrow variable), for constants of every size. The expected
output is worked out here with Python integers (div and mod truncate towards zero), not
by the compiler.

usage: gen_divnn.py [--check]    --check writes nothing and fails when the two files in
testdata are not what this script writes
"""
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata', 'divnn')
CHECK = sys.argv[1:] == ['--check']
M64 = (1 << 64) - 1


def emit(path, text):
    if CHECK:
        if open(path).read() != text:
            sys.exit(path + ' is not what scripts/gen_divnn.py writes')
    else:
        open(path, 'w').write(text)


def tdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def tmod(a, b):
    return a - tdiv(a, b) * b


def s64(x):
    x &= M64
    return x - (1 << 64) if x >> 63 else x


CS = [2, 3, 5, 6, 7, 9, 10, 11, 12, 13, 24, 25, 60, 100, 255, 256, 641, 1000, 2141, 3600, 4096,
      65521, 86400, 146097, 1000003, 2939745, 16777213, 2147483647, 4294967295, 4294967297,
      1000000007, 1000000000039, 1 << 40, (1 << 61) + 1]
MASKS = [0x7, 0xFF, 0xFFF, 0xFFFF, 0xFFFFF, 0xFFFFFFF, 0x7FFFFFFF, 0xFFFFFFFF, 0x3FFFFFFFFFF,
         (1 << 52) - 1, (1 << 62) - 1, (1 << 63) - 1]
XS = [0, 1, 2, 3, 7, 10, 255, 256, 65535, 65536, 2141 * 30, 0x7FFFFFFF, 0xFFFFFFFF, 1 << 40,
      (1 << 52) + 12345, (1 << 62) + 99, (1 << 63) - 1, -1, -2, -(1 << 63), 123456789123456789,
      -987654321987654321]


def lit(v):
    if v == -(1 << 63):
        return '-9223372036854775807 - 1'
    return str(v)


funcs = []
calls = []
exp = []


def add_int_func(name, expr, ref, xs, typ='Integer'):
    """a function of one Integer returning an Integer, called on xs"""
    funcs.append('function %s(x: %s): Integer;\nbegin\n  Result := %s;\nend;\n' % (name, typ, expr))
    for x in xs:
        calls.append('  WriteLn(%s(%s));\n' % (name, lit(x)))
        exp.append('%d\n' % ref(x))


# A: masked, constants by a rotating choice of masks
n = 0
for ci, c in enumerate(CS):
    for j in range(3):
        m = MASKS[(ci * 5 + j * 4 + 1) % len(MASKS)]
        n += 1
        add_int_func('da%d' % n, '(x and %d) div %d' % (m, c), lambda x, m=m, c=c: tdiv(x & m, c), XS)
        add_int_func('ra%d' % n, '(x and %d) mod %d' % (m, c), lambda x, m=m, c=c: tmod(x & m, c), XS)

# B: shifted
n = 0
for ci, c in enumerate(CS):
    sh = (ci * 7) % 62 + 1
    n += 1
    add_int_func('db%d' % n, '(x shr %d) div %d' % (sh, c), lambda x, sh=sh, c=c: tdiv((x & M64) >> sh, c), XS)
    add_int_func('rb%d' % n, '(x shr %d) mod %d' % (sh, c), lambda x, sh=sh, c=c: tmod((x & M64) >> sh, c), XS)

# C: narrow variables
NARROW = [('Byte', 0, 255), ('Word', 0, 65535), ('UInt32', 0, (1 << 32) - 1), ('Int8', -128, 127),
          ('Int16', -32768, 32767), ('Int32', -(1 << 31), (1 << 31) - 1)]
for (t, lo, hi) in NARROW:
    xs = sorted(set([lo, lo + 1, -1 if lo < 0 else 1, 0, 1, 2, 9, 10, 99, 100, hi // 3, hi // 2, hi - 1, hi]))
    xs = [x for x in xs if lo <= x <= hi]
    for c in (3, 7, 10, 100, 255, 1000, 65521, 1000003):
        if c > hi:
            continue
        k = '%s%d' % (t.lower(), c)
        add_int_func('dc' + k, 'x div %d' % c, lambda x, c=c: tdiv(x, c), xs, t)
        add_int_func('rc' + k, 'x mod %d' % c, lambda x, c=c: tmod(x, c), xs, t)

# D: sums that wrap in a narrow type, then divided
for (t, lo, hi, bits, signed) in (('Byte', 0, 255, 8, False), ('Word', 0, 65535, 16, False),
                                  ('UInt32', 0, (1 << 32) - 1, 32, False), ('Int8', -128, 127, 8, True)):
    def wrap(v, bits=bits, signed=signed):
        v &= (1 << bits) - 1
        if signed and v >> (bits - 1):
            v -= 1 << bits
        return v
    pts = [lo, lo + 1, 0, 1, 7, hi // 3, hi // 2, hi - 1, hi]
    for c in (3, 10, 100, 1000):
        if c > hi:
            continue
        name = 'dd%s%d' % (t.lower(), c)
        funcs.append('function %s(a, b: %s): %s;\nbegin\n  Result := (a + b) div %d;\nend;\n' % (name, t, t, c))
        name2 = 'rd%s%d' % (t.lower(), c)
        funcs.append('function %s(a, b: %s): %s;\nbegin\n  Result := (a * b) mod %d;\nend;\n' % (name2, t, t, c))
        for i, a in enumerate(pts):
            b = pts[(i * 4 + 1) % len(pts)]
            calls.append('  WriteLn(%s(%s, %s));\n' % (name, lit(a), lit(b)))
            exp.append('%d\n' % wrap(tdiv(wrap(a + b), c)))
            calls.append('  WriteLn(%s(%s, %s));\n' % (name2, lit(a), lit(b)))
            exp.append('%d\n' % wrap(tmod(wrap(a * b), c)))

# E: counters
for c in (3, 7, 10, 60, 1000, 2141):
    name = 'le%d' % c
    funcs.append('''function %s(n: Integer): Integer;
var
  i, t: Integer;
begin
  t := 0;
  for i := 0 to n do
    t := t + i div %d * 3 + i mod %d;
  Result := t;
end;
''' % (name, c, c))
    for nn in (0, 1, 9, 100, 4999):
        calls.append('  WriteLn(%s(%d));\n' % (name, nn))
        exp.append('%d\n' % sum(tdiv(i, c) * 3 + tmod(i, c) for i in range(nn + 1)))

# F: the shapes the Makefile reads, with the sign of the dividend unknown for the last
add_int_func('dsmall', '(x and $FFFF) div 2141', lambda x: tdiv(x & 0xFFFF, 2141), XS)
add_int_func('rsmall', '(x and $FFFF) mod 2141', lambda x: tmod(x & 0xFFFF, 2141), XS)
add_int_func('dpow', '(x and $FFFF) div 256', lambda x: tdiv(x & 0xFFFF, 256), XS)
add_int_func('rpow', '(x and $FFFF) mod 1024', lambda x: tmod(x & 0xFFFF, 1024), XS)
add_int_func('dwide', '(x and $7FFFFFFFFFFFFFFF) div 1000', lambda x: tdiv(x & ((1 << 63) - 1), 1000), XS)
add_int_func('rwide', '(x and $7FFFFFFFFFFFFFFF) mod 1000', lambda x: tmod(x & ((1 << 63) - 1), 1000), XS)
add_int_func('dbyte', 'x div 10', lambda x: tdiv(x, 10), [0, 1, 9, 10, 99, 100, 199, 200, 254, 255], 'Byte')
add_int_func('dneg', 'x div 1000', lambda x: tdiv(x, 1000), XS)
add_int_func('rneg', 'x mod 1000', lambda x: tmod(x, 1000), XS)

# G: a division or modulo worked out straight into an argument register of a call, in every position
funcs.append('''function Take6(a, b, c, d, e, f: Integer): Integer;
begin
  Result := a + b * 3 + c * 5 + d * 7 + e * 11 + f * 13;
end;
''')
G_MASKS = [255, 65535, 16777215, 0xFFFFFFFF, (1 << 40) - 1, 1 << 20]
G_MODS = [1 << 32, 1 << 40, 1 << 33, 1 << 62, 1 << 36, 1 << 50]
G_DIVS = [3, 10, 256, 1000, 4096, 2141]
for form in range(4):
    parts = []
    for i in range(6):
        m = G_MASKS[(i + form) % 6]
        if form == 0:
            parts.append('((x and %d) mod %d)' % (m, G_MODS[i]))
        elif form == 1:
            parts.append('((x and %d) div %d)' % (m, G_DIVS[i]))
        elif form == 2:
            parts.append('((x and %d) mod %d)' % (m, G_DIVS[i]))
        else:
            parts.append('((x shr %d) mod %d)' % (i * 9 + 3, G_MODS[(i + 2) % 6]))
    funcs.append('function G%d(x: Integer): Integer;\nbegin\n  Result := Take6(%s);\nend;\n' % (form, ', '.join(parts)))
    for x in XS:
        vals = []
        for i in range(6):
            m = G_MASKS[(i + form) % 6]
            if form == 0:
                vals.append(tmod(x & m, G_MODS[i]))
            elif form == 1:
                vals.append(tdiv(x & m, G_DIVS[i]))
            elif form == 2:
                vals.append(tmod(x & m, G_DIVS[i]))
            else:
                vals.append(tmod((x & M64) >> (i * 9 + 3), G_MODS[(i + 2) % 6]))
        r = s64(vals[0] + vals[1] * 3 + vals[2] * 5 + vals[3] * 7 + vals[4] * 11 + vals[5] * 13)
        calls.append('  WriteLn(G%d(%s));\n' % (form, lit(x)))
        exp.append('%d\n' % r)

# H: the same after arguments that need the divider, so that the last is worked out straight into its register
funcs.append('''function Take3(a, b, c: Integer): Integer;
begin
  Result := a + b * 3 + c * 5;
end;
''')
funcs.append('''function Take4(a, b, c, d: Integer): Integer;
begin
  Result := a + b * 3 + c * 5 + d * 7;
end;
''')
for pos in (3, 4):
    for mk in range(3):
        m = [16777215, 0xFFFFFFFF, 65535][mk]
        md = [1 << 40, 1 << 33, 1 << 62][mk]
        cx = '((x mod ((x and 15) + 1)) and %d) mod %d' % (m, md)
        args = ['(x mod ((x and 15) + 1))', '(x div ((x and 7) + 1))', '(x mod ((x and 31) + 3))'][:pos - 1] + ['(%s)' % cx]
        name = 'H%d_%d' % (pos, mk)
        funcs.append('function %s(x: Integer): Integer;\nbegin\n  Result := Take%d(%s);\nend;\n' % (name, pos, ', '.join(args)))
        for x in XS:
            v = [tmod(x, (x & 15) + 1), tdiv(x, (x & 7) + 1), tmod(x, (x & 31) + 3)][:pos - 1] + [tmod(tmod(x, (x & 15) + 1) & m, md)]
            r = s64(v[0] + v[1] * 3 + v[2] * 5 + (v[3] * 7 if pos == 4 else 0)) if pos == 4 else s64(v[0] + v[1] * 3 + v[2] * 5)
            calls.append('  WriteLn(%s(%s));\n' % (name, lit(x)))
            exp.append('%d\n' % r)

PROGRAM = '''program divnn;

{ P536: div and mod by a constant of a value that cannot be negative }

%s
begin
%send.
''' % ('\n'.join(funcs), ''.join(calls))

emit(OUT + '.paslang', PROGRAM)
emit(OUT + '.out', ''.join(exp))
