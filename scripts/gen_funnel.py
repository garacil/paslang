#!/usr/bin/env python3
"""Writes testdata/funnel.paslang and testdata/funnel.out (P509): FunnelLeft and
FunnelRight of every width (Int64, Int32, UInt32, Int16, Word, Int8, Byte) with
the operands in every form (locals, globals, array elements, expressions the
register pool works out, constants, a call) and the count in every form: a
variable, the ones whose range the compiler proves lies in 0..63 (x and 63,
x mod 64 of a masked value, x shr 58, the counter of a for loop, a byte masked)
and the near misses that it must not take for proven (x and 127, x and 64,
(x and 63) - 1, (x and 63) + 1, a byte, a loop counter that reaches 64 or goes
below 0), and constants from -1 to 129. Each procedure folds the results of
133 counts (-2..130) over 8 pairs of values into one hash per form (a constant count once a pair) and writes
one line of hashes. The expected output is worked out here from the meaning
of the words (the top or the low half of hi:lo shifted, a count of 0 or less
leaves the word, a count of twice the width or more gives 0), not by the
compiler.

usage: gen_funnel.py [--check]    --check writes nothing and fails when the two
files in testdata are not what this script writes
"""
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata', 'funnel')
CHECK = sys.argv[1:] == ['--check']
MASK = (1 << 64) - 1


def emit(path, text):
    if CHECK:
        if open(path).read() != text:
            sys.exit(path + ' is not what scripts/gen_funnel.py writes')
    else:
        open(path, 'w').write(text)


# type name, width, signed
TYPES = [('Int64', 64, True), ('Int32', 32, True), ('UInt32', 32, False), ('Int16', 16, True),
         ('Word', 16, False), ('Int8', 8, True), ('Byte', 8, False)]
def pairs(n):
    """eight pairs of values of n bits: zero, ones, single bits, alternating bits, the halves"""
    m = (1 << n) - 1
    half = (1 << (n // 2)) - 1
    return [(0, 0), (m, m), (1, 0), (0, 1 << (n - 1)),
            (0xAAAAAAAAAAAAAAAA & m, 0x5555555555555555 & m), (1 << (n - 1), 1),
            (0x0123456789ABCDEF & m, 0xFEDCBA9876543210 & m), (m ^ half, half)]


VS = list(range(-2, 131))
SC = [-3, 0, 1, 5, 63, 64, 65, 127, 128, 130]


def s64(x):
    x &= MASK
    return x - (1 << 64) if x >> 63 else x


def as_t(x, n, signed):
    x &= (1 << n) - 1
    if signed and x >> (n - 1):
        x -= 1 << n
    return x


def lit(v):
    if v == -(1 << 63):
        return 'Low(Int64)'
    return str(v)


def funnel(left, n, hi, lo, c):
    m = (1 << n) - 1
    hi &= m
    lo &= m
    if c <= 0:
        return hi if left else lo
    if n == 64:
        if c < 64:
            if left:
                return ((hi << c) | (lo >> (64 - c))) & m
            return ((lo >> c) | (hi << (64 - c))) & m
        if c < 128:
            return (lo << (c - 64)) & m if left else hi >> (c - 64)
        return 0
    if c >= 2 * n:
        return 0
    v = (hi << n) | lo
    if left:
        return ((v << c) >> n) & m
    return (v >> c) & m


# the count forms that depend on n (the loop value v) : source, value
COUNTS = [
    ('n', lambda v: v),
    ('n and 63', lambda v: v & 63),
    ('n and 127', lambda v: v & 127),
    ('n and 64', lambda v: v & 64),
    ('(n and 255) mod 64', lambda v: (v & 255) % 64),
    ('(n and 63) - 1', lambda v: (v & 63) - 1),
    ('(n and 63) + 1', lambda v: (v & 63) + 1),
    ('(n * 7919) shr 58', lambda v: ((v * 7919) & MASK) >> 58),
    ('nb', lambda v: v & 255),
    ('nb and 63', lambda v: v & 63),
    ('nb mod 64', lambda v: (v & 255) % 64),
    ('IdI(n, 0) and 63', lambda v: v & 63),
]
KONST = [-1, 0, 1, 5, 7, 8, 15, 16, 31, 32, 33, 63, 64, 65, 127, 128, 129]
# the counters of a for loop: source of the bounds, the values
LOOPS = [('0 to 63', range(0, 64)), ('0 to 64', range(0, 65)), ('-1 to 62', range(-1, 63))]

# argument forms: name, setup (per pair), hi source, lo source, how to turn the pair into the value
# the operands as the program passes them: (hi, lo) of the pair worked out here
ARGS = [
    ('locals', 'hv := PH{T}[i]; lv := PL{T}[i];', 'hv', 'lv', lambda hi, lo, n, s: (hi, lo)),
    ('globals', 'GH{T} := PH{T}[i]; GL{T} := PL{T}[i];', 'GH{T}', 'GL{T}', lambda hi, lo, n, s: (hi, lo)),
    ('elements', '', 'PH{T}[i]', 'PL{T}[i]', lambda hi, lo, n, s: (hi, lo)),
    ('pool', 'hv := PH{T}[i]; lv := PL{T}[i];', '{T}(hv xor 5)', '{T}(lv + 3)',
     lambda hi, lo, n, s: (as_t(hi ^ 5, n, s), as_t(lo + 3, n, s))),
    ('constant hi', 'lv := PL{T}[i];', '{T}(77)', 'lv', lambda hi, lo, n, s: (77, lo)),
    ('call hi', 'hv := PH{T}[i]; lv := PL{T}[i];', 'IdT{T}(hv, 0)', 'lv', lambda hi, lo, n, s: (hi, lo)),
    ('computed lo', 'hv := PH{T}[i]; lv := PL{T}[i];', 'hv', '{T}(lv + 3)',
     lambda hi, lo, n, s: (hi, as_t(lo + 3, n, s))),
    ('constants', '', '{T}(77)', '{T}(100)', lambda hi, lo, n, s: (77, 100)),
]


def fold(h, val):
    # the program's (H xor x) * 1099511628211 + 7 in 64 bits, x as its type holds it
    return (((h ^ (val & MASK)) * 1099511628211) + 7) & MASK


def proc_name(t, d, a):
    return 'F_%s_%s_%d' % (t, d, a)


def gen():
    P = []
    X = []
    P.append("""program funnel;

{ FunnelLeft and FunnelRight (P509): the operands and the count in every
  form, a count the compiler can prove lies in 0..63 and the ones that only
  look as if it did. Each procedure folds 133 counts over 8 pairs of values
  into one hash a form and writes one line; the hashes are the ones
  scripts/gen_funnel.py works out from the meaning of the words. }

var
  HS: array[0..%d] of Int64;
  SCounts: array[0..9] of Integer;
""" % (len(COUNTS) + len(LOOPS) + len(KONST) - 1))
    for t, n, s in TYPES:
        P.append("""  PH%(t)s, PL%(t)s: array[0..7] of %(t)s;
  GH%(t)s, GL%(t)s: %(t)s;
""" % {'t': t})
    P.append("""
function IdI(x: Int64; d: Integer): Int64;
begin
  if d <= 0 then
    Result := x
  else
    Result := IdI(x, d - 1);
end;
""")
    for t, n, s in TYPES:
        P.append("""
function IdT%(t)s(x: %(t)s; d: Integer): %(t)s;
begin
  if d <= 0 then
    Result := x
  else
    Result := IdT%(t)s(x, d - 1);
end;
""" % {'t': t})
    for t, n, s in TYPES:
        P.append("\nprocedure Init%s;\nbegin\n" % t)
        for i, (hi, lo) in enumerate(pairs(n)):
            P.append("  PH%s[%d] := %s;\n  PL%s[%d] := %s;\n" % (
                t, i, lit(as_t(hi, n, s)), t, i, lit(as_t(lo, n, s))))
        P.append("end;\n")
    P.append("""
{ small routines whose assembly the Makefile reads (compiled with -inline 0):
  a count and 63 is in 0..63 and needs no test, and 127 does }
function S_SafeL(h, l, c: Int64): Int64;
begin
  Result := FunnelLeft(h, l, c and 63);
end;

function S_SafeR(h, l, c: Int64): Int64;
begin
  Result := FunnelRight(h, l, c and 63);
end;

function S_WideL(h, l, c: Int64): Int64;
begin
  Result := FunnelLeft(h, l, c and 127);
end;

function S_ByteR(h, l: Byte; c: Int64): Byte;
begin
  Result := FunnelRight(h, l, c and 63);
end;

function S_ByteU(h, l: Byte; c: Int64): Byte;
begin
  Result := FunnelRight(h, l, c);
end;

procedure Shapes;
var
  k: Integer;
  c: Int64;
  h, l: Int64;
  hb, lb: Byte;
begin
  h := $0123456789ABCDEF;
  l := $FEDCBA9876543210;
  hb := $A5;
  lb := $3C;
  for k := 0 to 9 do
  begin
    c := SCounts[k];
    WriteLn('shape ', c, ' ', S_SafeL(h, l, c), ' ', S_SafeR(h, l, c), ' ', S_WideL(h, l, c), ' ',
      S_ByteR(hb, lb, c), ' ', S_ByteU(hb, lb, c));
  end;
end;
""")
    # the procedures
    for t, n, s in TYPES:
        for d in ('Left', 'Right'):
            left = d == 'Left'
            for ai, (an, setup, hs, ls, pairfn) in enumerate(ARGS):
                hs2 = hs.replace('{T}', t)
                ls2 = ls.replace('{T}', t)
                su = setup.replace('{T}', t)
                fn = 'Funnel' + d
                name = proc_name(t, d, ai)
                B = []
                B.append("\nprocedure %s;\nvar\n  i, j: Integer;\n  v, n: Int64;\n  nb: Byte;\n  hv, lv, x: %s;\nbegin\n" % (name, t))
                B.append("  FillChar(HS, SizeOf(HS), 0);\n")
                B.append("  for i := 0 to 7 do\n  begin\n")
                if su:
                    B.append("    " + su + "\n")
                B.append("    for v := -2 to 130 do\n    begin\n      n := v;\n      nb := Byte(v and 255);\n")
                k = 0
                for cs, cf in COUNTS:
                    B.append("      x := %s(%s, %s, %s);\n      HS[%d] := (HS[%d] xor x) * 1099511628211 + 7;\n" % (fn, hs2, ls2, cs, k, k))
                    k += 1
                B.append("    end;\n")
                for ks in KONST:
                    B.append("    x := %s(%s, %s, %s);\n    HS[%d] := (HS[%d] xor x) * 1099511628211 + 7;\n" % (fn, hs2, ls2, '(' + str(ks) + ')' if ks < 0 else str(ks), k, k))
                    k += 1
                for lsrc, rng in LOOPS:
                    B.append("    for j := %s do\n    begin\n      x := %s(%s, %s, j);\n      HS[%d] := (HS[%d] xor x) * 1099511628211 + 7;\n    end;\n" % (lsrc, fn, hs2, ls2, k, k))
                    k += 1
                B.append("  end;\n")
                B.append("  Write('%s %s %s:');\n  for i := 0 to %d do\n    Write(' ', HS[i]);\n  WriteLn;\nend;\n" % (t, d, an, k - 1))
                P.append(''.join(B))
                # expected
                H = []
                for cs, cf in COUNTS:
                    h = 0
                    for (hi, lo) in pairs(n):
                        a, b = pairfn(hi, lo, n, s)
                        for v in VS:
                            h = fold(h, as_t(funnel(left, n, a, b, cf(v)), n, s))
                    H.append(h)
                for ks in KONST:
                    h = 0
                    for (hi, lo) in pairs(n):
                        a, b = pairfn(hi, lo, n, s)
                        h = fold(h, as_t(funnel(left, n, a, b, ks), n, s))
                    H.append(h)
                for lsrc, rng in LOOPS:
                    h = 0
                    for (hi, lo) in pairs(n):
                        a, b = pairfn(hi, lo, n, s)
                        for j in rng:
                            h = fold(h, as_t(funnel(left, n, a, b, j), n, s))
                    H.append(h)
                X.append('%s %s %s: %s\n' % (t, d, an, ' '.join(str(s64(h)) for h in H)))
    P.append("\nbegin\n")
    for i, c in enumerate(SC):
        P.append("  SCounts[%d] := %d;\n" % (i, c))
    for t, n, s in TYPES:
        P.append("  Init%s;\n" % t)
    for t, n, s in TYPES:
        for d in ('Left', 'Right'):
            for ai in range(len(ARGS)):
                P.append("  %s;\n" % proc_name(t, d, ai))
    P.append("  Shapes;\n")
    P.append("end.\n")
    for c in SC:
        h, l = 0x0123456789ABCDEF, 0xFEDCBA9876543210
        hb, lb = 0xA5, 0x3C
        X.append('shape %d %d %d %d %d %d\n' % (
            c, as_t(funnel(True, 64, h, l, c & 63), 64, True), as_t(funnel(False, 64, h, l, c & 63), 64, True),
            as_t(funnel(True, 64, h, l, c & 127), 64, True), as_t(funnel(False, 8, hb, lb, c & 63), 8, False),
            as_t(funnel(False, 8, hb, lb, c), 8, False)))
    return ''.join(P), ''.join(X)


prog, out = gen()
emit(OUT + '.paslang', prog)
emit(OUT + '.out', out)
