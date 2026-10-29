#!/usr/bin/env python3
"""gen_fma.py: testdata/fma.paslang (P425). Cases of A * B + C for Doubles and
for Singles with the result rounded once: random operands of every exponent,
products that cancel the addend, exact ties, subnormals, overflow and
underflow, zeros of both signs, infinities and NaNs. The Double results are
Python's math.fma (C99 fma); the Single results are rounded from the exact
rational by this file, which checks the same routine on the Doubles against
math.fma. A NaN is expected only as 'any NaN', its bits being the machine's."""
import math
import random
import struct
import sys
from fractions import Fraction

rnd = random.Random(4250)


def d2b(x):
    return struct.unpack('<Q', struct.pack('<d', x))[0]


def b2d(b):
    return struct.unpack('<d', struct.pack('<Q', b))[0]


def s2b(x):
    return struct.unpack('<I', struct.pack('<f', x))[0]


def b2s(b):
    return struct.unpack('<f', struct.pack('<I', b))[0]


def round_frac(fr, mant, emin, emax, signbit):
    """Round the rational fr to nearest even in a format of mant bits (with the
    hidden one), smallest normal exponent emin, largest emax; the bits of a
    float64-like layout are made by the caller. Gives (kind, value) with kind
    'fin' and a Fraction, or 'inf'."""
    if fr == 0:
        return Fraction(0)
    neg = fr < 0
    a = -fr if neg else fr
    e = a.numerator.bit_length() - a.denominator.bit_length()
    if Fraction(2) ** e > a:
        e -= 1
    if e < emin:
        e = emin
    q = Fraction(2) ** (e - mant + 1)
    n = a / q
    fl = n.numerator // n.denominator
    rem = n - fl
    if rem > Fraction(1, 2) or (rem == Fraction(1, 2) and fl % 2 == 1):
        fl += 1
    r = fl * q
    if r >= Fraction(2) ** (emax + 1):
        return 'inf'
    return -r if neg else r


def frac_to_bits(r, double):
    if r == 'inf':
        return None
    if r == 0:
        return 0
    neg = r < 0
    a = -r if neg else r
    if double:
        mant, emin, eb, bias, w = 53, -1022, 52, 1023, 64
    else:
        mant, emin, eb, bias, w = 24, -126, 23, 127, 32
    e = a.numerator.bit_length() - a.denominator.bit_length()
    if Fraction(2) ** e > a:
        e -= 1
    if e < emin:
        m = a / (Fraction(2) ** (emin - eb))
        assert m.denominator == 1
        bits = int(m)
    else:
        m = a / (Fraction(2) ** (e - eb))
        assert m.denominator == 1
        bits = ((e + bias) << eb) | (int(m) - (1 << eb))
    if neg:
        bits |= 1 << (w - 1)
    return bits


def fma_exact(a, b, c, double):
    """bits of fma over floats a, b, c (Python floats holding the format's values)"""
    if any(math.isnan(v) for v in (a, b, c)):
        return 'nan'
    if math.isinf(a) or math.isinf(b):
        if a == 0 or b == 0:
            return 'nan'
        p = math.copysign(math.inf, a) * math.copysign(1.0, b)
        if math.isinf(c) and c != p:
            return 'nan'
        return d2b(p) if double else s2b(p)
    if math.isinf(c):
        return d2b(c) if double else s2b(c)
    fa, fb, fc = Fraction(a), Fraction(b), Fraction(c)
    ex = fa * fb + fc
    if ex == 0:
        # sign of an exact zero: both products and addend of the same sign keep it,
        # else +0 (round to nearest)
        ps = math.copysign(1.0, a) * math.copysign(1.0, b)
        pz = (a == 0 or b == 0)
        if pz and c == 0:
            neg = ps < 0 and math.copysign(1.0, c) < 0
        else:
            neg = False
        if double:
            return (1 << 63) if neg else 0
        return (1 << 31) if neg else 0
    if double:
        r = round_frac(ex, 53, -1022, 1023, 0)
    else:
        r = round_frac(ex, 24, -126, 127, 0)
    if r == 'inf':
        inf = math.inf if ex > 0 else -math.inf
        return d2b(inf) if double else s2b(inf)
    if r == 0:
        # underflow to a zero keeps the sign of the exact value
        if double:
            return (1 << 63) if ex < 0 else 0
        return (1 << 31) if ex < 0 else 0
    return frac_to_bits(r, double)


def rand_double():
    k = rnd.random()
    if k < 0.15:
        return b2d(rnd.getrandbits(64) & ~(1 << 63) | (rnd.getrandbits(1) << 63))
    e = rnd.randint(-40, 40) if k < 0.7 else rnd.randint(-1000, 1000)
    m = 1 + rnd.getrandbits(52) / 2.0 ** 52
    v = math.ldexp(m, e)
    return -v if rnd.getrandbits(1) else v


def rand_single():
    k = rnd.random()
    if k < 0.15:
        return b2s(rnd.getrandbits(32))
    e = rnd.randint(-10, 10) if k < 0.7 else rnd.randint(-140, 120)
    m = 1 + rnd.getrandbits(23) / 2.0 ** 23
    v = math.ldexp(m, e)
    return -v if rnd.getrandbits(1) else v


dcases = []
scases = []


def addd(a, b, c):
    if any(math.isnan(v) for v in (a, b, c)):
        pass
    dcases.append((a, b, c))


def tosingle(v):
    return struct.unpack('<f', struct.pack('<f', v))[0]


def adds(a, b, c):
    # every operand is a Single: a value a Single cannot hold is rounded to one
    try:
        scases.append((tosingle(a), tosingle(b), tosingle(c)))
    except OverflowError:
        pass


specials_d = [0.0, -0.0, 1.0, -1.0, 3.0, math.inf, -math.inf, math.nan,
              5e-324, -5e-324, 2.2250738585072014e-308, 1.7976931348623157e308,
              -1.7976931348623157e308, 1.0 + 2.0 ** -52, 1.0 - 2.0 ** -53, 2.0 ** -1022]
for a in specials_d:
    for b in specials_d:
        for c in (0.0, -0.0, 1.0, math.inf, math.nan, 5e-324, -1.0):
            addd(a, b, c)

for _ in range(900):
    addd(rand_double(), rand_double(), rand_double())
# cancellation: c is minus the rounded product, so the sum is the rounding error
for _ in range(500):
    a, b = rand_double(), rand_double()
    p = a * b
    if math.isfinite(p):
        addd(a, b, -p)
# ties: a, b of few bits, c at half an ulp of the exact product
for _ in range(250):
    a = float(rnd.getrandbits(rnd.randint(1, 26)) | 1) * 2.0 ** rnd.randint(-20, 20)
    b = float(rnd.getrandbits(rnd.randint(1, 26)) | 1) * 2.0 ** rnd.randint(-20, 20)
    p = a * b
    if p != 0 and math.isfinite(p):
        ulp = math.ulp(p)
        for f in (0.5, -0.5, 1.5, 2.0 ** -60):
            addd(a, b, p + f * ulp if rnd.getrandbits(1) else f * ulp)
# subnormal and underflow
for _ in range(150):
    e1 = rnd.randint(-600, -400)
    a = math.ldexp(1 + rnd.getrandbits(52) / 2.0 ** 52, e1)
    b = math.ldexp(1 + rnd.getrandbits(52) / 2.0 ** 52, rnd.randint(-600, -400))
    addd(a, b, b2d(rnd.getrandbits(52)))
    addd(a, b, -b2d(rnd.getrandbits(52)))
    addd(a, b, 0.0)
# overflow
for _ in range(100):
    a = math.ldexp(1 + rnd.getrandbits(52) / 2.0 ** 52, rnd.randint(500, 1023))
    b = math.ldexp(1 + rnd.getrandbits(52) / 2.0 ** 52, rnd.randint(400, 1023))
    addd(a, b, -a * 1e-300)
    addd(a, -b, rand_double())
    addd(a, 2.0 ** -rnd.randint(1, 500), rand_double())

specials_s = [0.0, -0.0, 1.0, -1.0, 3.0, math.inf, -math.inf, math.nan,
              b2s(1), b2s(0x80000001), b2s(0x00800000), b2s(0x7F7FFFFF), b2s(0xFF7FFFFF),
              1.0 + 2.0 ** -23, 1.0 - 2.0 ** -24, 2.0 ** -126]
for a in specials_s:
    for b in specials_s:
        for c in (0.0, -0.0, 1.0, math.inf, math.nan, b2s(1), -1.0):
            adds(a, b, c)
for _ in range(900):
    adds(rand_single(), rand_single(), rand_single())
for _ in range(500):
    a, b = rand_single(), rand_single()
    p = float(struct.unpack('<f', struct.pack('<f', a * b))[0]) if abs(a * b) < 3e38 else None
    if p is not None:
        adds(a, b, -p)
for _ in range(250):
    # a sum of two floats far apart in exponent: the double rounding trap
    a = float(rnd.getrandbits(rnd.randint(1, 12)) | 1) * 2.0 ** rnd.randint(-10, 10)
    b = float(rnd.getrandbits(rnd.randint(1, 12)) | 1) * 2.0 ** rnd.randint(-10, 10)
    p = a * b
    for f in (0.5, 1.5, 2.0 ** -30, -2.0 ** -45):
        c = struct.unpack('<f', struct.pack('<f', p))[0]
        try:
            adds(a, b, struct.unpack('<f', struct.pack('<f', p + f * math.ulp(p) * 2.0 ** 29))[0])
        except OverflowError:
            pass
        adds(a, b, c * f)
for _ in range(150):
    e1 = rnd.randint(-90, -60)
    a = math.ldexp(1 + rnd.getrandbits(23) / 2.0 ** 23, e1)
    b = math.ldexp(1 + rnd.getrandbits(23) / 2.0 ** 23, rnd.randint(-80, -60))
    a = struct.unpack('<f', struct.pack('<f', a))[0]
    b = struct.unpack('<f', struct.pack('<f', b))[0]
    adds(a, b, b2s(rnd.getrandbits(23)))
    adds(a, b, -b2s(rnd.getrandbits(23)))


def check_double_model():
    n = 0
    for a, b, c in dcases:
        try:
            ref = d2b(math.fma(a, b, c))
        except ValueError:
            ref = 'nan'
        except OverflowError:
            ref = None
        got = fma_exact(a, b, c, True)
        if ref is None:
            continue
        if ref == 'nan' or got == 'nan':
            assert (ref == 'nan') == (got == 'nan') or math.isnan(math.fma(a, b, c) if ref != 'nan' else 0), (a, b, c, ref, got)
            continue
        if math.isnan(b2d(ref)):
            assert got == 'nan', (a, b, c)
            continue
        assert ref == got, (a.hex(), b.hex(), c.hex(), hex(ref), hex(got))
        n += 1
    return n


n = check_double_model()
print('double model agrees with math.fma on %d cases' % n, file=sys.stderr)


def word(v, w):
    return '$%0*X' % (w // 4, v)


def emit_table(name, rows, double):
    out = []
    w = 64 if double else 32
    n = len(rows)
    out.append('  %s: array[0..%d] of Integer = (' % (name, n * 4 - 1))
    items = []
    for a, b, c in rows:
        r = fma_exact(a, b, c, double)
        ab, bb, cb = (d2b(a), d2b(b), d2b(c)) if double else (s2b(a), s2b(b), s2b(c))
        # NaN operands: bits kept; the expected word of a NaN result is -1
        rr = -1 if r == 'nan' else r
        for v in (ab, bb, cb):
            items.append('$%X' % v)
        items.append('-1' if rr == -1 else '$%X' % rr)
    lines = []
    for i in range(0, len(items), 8):
        lines.append('    ' + ', '.join(items[i:i + 8]))
    out.append(',\n'.join(lines) + ');')
    return '\n'.join(out), n


# Horner's rule with Fma in a loop (a promoted variable, an Integer addend), and
# nested and mixed calls: the expected words are Python's
hx = [rand_double() if rnd.random() < 0.5 else rnd.uniform(-2.0, 2.0) for _ in range(64)]
hx = [v for v in hx if math.isfinite(v) and abs(v) < 1e15]


def horner(x):
    r = 0.0
    for i in range(1, 17):
        r = math.fma(r, x, float(i))
    return r


hx = [v for v in hx if math.isfinite(horner(v))]
HX = ', '.join('$%X' % d2b(v) for v in hx)
HR = ', '.join('$%X' % d2b(horner(v)) for v in hx)
hn = len(hx)
nest = [(rand_double(), rand_double()) for _ in range(8)]
nest = [(a, b) for a, b in nest if abs(a) < 1e100 and abs(b) < 1e100]
NX = ', '.join('$%X, $%X' % (d2b(a), d2b(b)) for a, b in nest)
NR = ', '.join('$%X' % d2b(math.fma(math.fma(a, b, a), math.fma(b, a, 1.0), -a)) for a, b in nest)
nn = len(nest)


def mix(x, y):
    r, s = x, y
    for i in range(1, 9):
        r = math.fma(r, 0.5, s)
        s = math.fma(y, s, 0.25)
        r = math.fma(x, y, r)
        s = math.fma(s, 0.5, float(i)) - r * 0.5
        if math.fma(r, s, 1.0) > 2.0:
            r = r * 0.5
    return r + s


mxs = [(rnd.uniform(-1.0, 1.0), rnd.uniform(-1.0, 1.0)) for _ in range(40)]
MX = ', '.join('$%X, $%X' % (d2b(a), d2b(b)) for a, b in mxs)
MR = ', '.join('$%X' % d2b(mix(a, b)) for a, b in mxs)
mn = len(mxs)
dt, dn = emit_table('DTab', dcases, True)
st, sn = emit_table('STab', scases, False)

prog = """{ P425: Fma, the fused multiply-add, A * B + C rounded once. Made by scripts/gen_fma.py
  (seed 4250): %d cases of Doubles and %d of Singles (random operands of every exponent,
  products that cancel the addend, exact ties, subnormals, overflow and underflow, zeros of
  both signs, infinities and NaNs); four words a case, A, B, C and the result, which is
  Python's math.fma for the Doubles and the exact rational rounded once for the Singles
  (-1 for any NaN: its bits are the machine's). Each is worked out by the word Fma, by
  PasFma (the processor tested at run time), by PasFmaSoft (integers alone) and, for the
  Singles, by PasFmaS and PasFmaSoftS; every answer must be the expected one. }
program fmafused;

uses pasnum, sysutils;

const
%s

%s

const
  HX: array[0..%d] of Integer = (%s);
  HR: array[0..%d] of Integer = (%s);
  NX: array[0..%d] of Integer = (%s);
  NR: array[0..%d] of Integer = (%s);
  MX: array[0..%d] of Integer = (%s);
  MR: array[0..%d] of Integer = (%s);

var
  bad: Integer;

{ the forms a statement takes: the variable as the multiplicand, as the other
  factor, as the addend, a constant, an integer, a tree and a comparison }
function Mix(x, y: Double): Double;
var
  r, s: Double;
  i: Integer;
begin
  r := x;
  s := y;
  for i := 1 to 8 do
  begin
    r := Fma(r, 0.5, s);
    s := Fma(y, s, 0.25);
    r := Fma(x, y, r);
    s := Fma(s, 0.5, i) - r * 0.5;
    if Fma(r, s, 1.0) > 2.0 then
      r := r * 0.5;
  end;
  Result := r + s;
end;

function Horner(X: Double): Double;
var
  i: Integer;
  r: Double;
begin
  r := 0.0;
  for i := 1 to 16 do
    r := Fma(r, X, i);
  Result := r;
end;

function IsNaNBits(B: Integer): Boolean;
begin
  Result := ((B and $7FF0000000000000) = $7FF0000000000000) and ((B and $000FFFFFFFFFFFFF) <> 0);
end;

function SIsNaNBits(B: Integer): Boolean;
begin
  Result := ((B and $7F800000) = $7F800000) and ((B and $007FFFFF) <> 0);
end;

procedure CheckD(I: Integer; Which: Integer; Got: Double; Want: Integer);
var
  g: Integer;
begin
  g := Got as Integer;
  if Want = -1 then
  begin
    if not IsNaNBits(g) then
    begin
      Inc(bad);
      if bad <= 10 then
        WriteLn('double case ', I, ' way ', Which, ': got ', IntToHex(g, 16), ', wanted a NaN');
    end;
  end
  else if g <> Want then
  begin
    Inc(bad);
    if bad <= 10 then
      WriteLn('double case ', I, ' way ', Which, ': got ', IntToHex(g, 16), ', wanted ', IntToHex(Want, 16));
  end;
end;

procedure CheckS(I: Integer; Which: Integer; Got: Single; Want: Integer);
var
  g: Integer;
begin
  g := Got as UInt32;
  if Want = -1 then
  begin
    if not SIsNaNBits(g) then
    begin
      Inc(bad);
      if bad <= 10 then
        WriteLn('single case ', I, ' way ', Which, ': got ', IntToHex(g, 8), ', wanted a NaN');
    end;
  end
  else if g <> Want then
  begin
    Inc(bad);
    if bad <= 10 then
      WriteLn('single case ', I, ' way ', Which, ': got ', IntToHex(g, 8), ', wanted ', IntToHex(Want, 8));
  end;
end;

var
  i: Integer;
  a, b, c: Double;
  x, y, z: Single;
begin
  bad := 0;
  for i := 0 to %d do
  begin
    a := DTab[i * 4] as Double;
    b := DTab[i * 4 + 1] as Double;
    c := DTab[i * 4 + 2] as Double;
    CheckD(i, 0, Fma(a, b, c), DTab[i * 4 + 3]);
    CheckD(i, 1, PasFma(a, b, c), DTab[i * 4 + 3]);
    CheckD(i, 2, PasFmaSoft(a, b, c), DTab[i * 4 + 3]);
  end;
  for i := 0 to %d do
  begin
    x := UInt32(STab[i * 4]) as Single;
    y := UInt32(STab[i * 4 + 1]) as Single;
    z := UInt32(STab[i * 4 + 2]) as Single;
    CheckS(i, 0, Fma(x, y, z), STab[i * 4 + 3]);
    CheckS(i, 1, PasFmaS(x, y, z), STab[i * 4 + 3]);
    CheckS(i, 2, PasFmaSoftS(x, y, z), STab[i * 4 + 3]);
  end;
  { integers are converted: Fma(2, 3, 4) is 10 }
  if Fma(2, 3, 4) <> 10.0 then
    Inc(bad);
  { the classic: 0.1 * 10 - 1 is 2^-54 fused and 0 unfused }
  if (Fma(0.1, 10.0, -1.0) as Integer) <> $3C90000000000000 then
    Inc(bad);
  { a Single and a Double make a Double: the Single widens exactly }
  x := UInt32($3F800001) as Single;
  if (Fma(x, x, -1.0) as Integer) <> $3E90000010000000 then
    Inc(bad);
  for i := 0 to %d do
    CheckD(i, 3, Horner(HX[i] as Double), HR[i]);
  for i := 0 to %d do
    CheckD(i, 5, Mix(MX[i * 2] as Double, MX[i * 2 + 1] as Double), MR[i]);
  for i := 0 to %d do
  begin
    a := NX[i * 2] as Double;
    b := NX[i * 2 + 1] as Double;
    CheckD(i, 4, Fma(Fma(a, b, a), Fma(b, a, 1.0), -a), NR[i]);
  end;
  WriteLn('fma cases ', %d, ' doubles, ', %d, ' singles, ', 'wrong ', bad);
end.
""" % (dn, sn, dt, st, hn - 1, HX, hn - 1, HR, nn * 2 - 1, NX, nn - 1, NR, mn * 2 - 1, MX, mn - 1, MR, dn - 1, sn - 1, hn - 1, mn - 1, nn - 1, dn, sn)
open(sys.argv[1] if len(sys.argv) > 1 else 'testdata/fmafused.paslang', 'w').write(prog)
open((sys.argv[1] if len(sys.argv) > 1 else 'testdata/fmafused.paslang')[:-8] + '.out', 'w').write('fma cases %d doubles, %d singles, wrong 0\n' % (dn, sn))
