#!/usr/bin/env python3
"""Writes testdata/mathgo.paslang and testdata/mathgo.out (P538): Sin, Cos, Exp, Ln and ArcTan
of about 1500 arguments, each result as the 64 bits of its Double. The expected output is Go's
math.Sin, math.Cos, math.Exp (exp.go, not the assembly of amd64), math.Log and math.Atan worked
out here in Python floats, operation for operation (the module below; checked against Go's own
results on 250,000 arguments when it was written), so a program whose results are those bits
has the accuracy of Go's code: within one ulp of the correctly rounded value, except near the
zeros of Sin and Cos past 2^29 where Go's reduction is what it is.

usage: gen_mathgo.py [--check]    --check writes nothing and fails when the two files in
testdata are not what this script writes
"""
import os
import random
import sys

import math
import struct

M64 = (1 << 64) - 1
PI = math.pi
PI4 = PI / 4


def bits(x):
    return struct.unpack('<Q', struct.pack('<d', x))[0]


def frombits(b):
    return struct.unpack('<d', struct.pack('<Q', b & M64))[0]


SIN = [1.58962301576546568060e-10, -2.50507477628578072866e-8, 2.75573136213857245213e-6,
       -1.98412698295895385996e-4, 8.33333333332211858878e-3, -1.66666666666666307295e-1]
COS = [-1.13585365213876817300e-11, 2.08757008419747316778e-9, -2.75573141792967388112e-7,
       2.48015872888517045348e-5, -1.38888888888730564116e-3, 4.16666666666665929218e-2]
PI4A = 7.85398125648498535156e-1
PI4B = 3.77489470793079817668e-8
PI4C = 2.69515142907905952645e-15
MPI4 = [0x0000000000000001, 0x45f306dc9c882a53, 0xf84eafa3ea69bb81, 0xb6c52b3278872083,
        0xfca2c757bd778ac3, 0x6e48dc74849ba5c0, 0x0c925dd413a32439, 0xfc3bd63962534e7d,
        0xd1046bea5d768909, 0xd338e04d68befc82, 0x7323ac7306a673e9, 0x3908bf177bf25076,
        0x3ff12fffbc0b301f, 0xde5e2316b414da3e, 0xda6cfd9e4f96136e, 0x9e8c7ecd3cbfd45a,
        0xea4f758fd7cbe2f6, 0x7a0e73ef14a525d4, 0xd7f6bf623f1aba10, 0xac06608df8f6d757]
REDUCE = 1 << 29


def trig_reduce(x):
    if x < PI4:
        return 0, x
    ix = bits(x)
    exp = ((ix >> 52) & 0x7FF) - 1023 - 52
    ix &= ~(0x7FF << 52) & M64
    ix |= 1 << 52
    digit, bitshift = (exp + 61) // 64, (exp + 61) % 64

    def shl(a, b):
        return (a << b) & M64

    def shr(a, b):
        return a >> b if b < 64 else 0
    z0 = shl(MPI4[digit], bitshift) | shr(MPI4[digit + 1], 64 - bitshift)
    z1 = shl(MPI4[digit + 1], bitshift) | shr(MPI4[digit + 2], 64 - bitshift)
    z2 = shl(MPI4[digit + 2], bitshift) | shr(MPI4[digit + 3], 64 - bitshift)
    z2hi = (z2 * ix) >> 64
    z1p = z1 * ix
    z1hi, z1lo = z1p >> 64, z1p & M64
    z0lo = (z0 * ix) & M64
    lo = z1lo + z2hi
    c = lo >> 64
    lo &= M64
    hi = (z0lo + z1hi + c) & M64
    j = hi >> 61
    hi = ((hi << 3) & M64) | (lo >> 61)
    lz = 64 - hi.bit_length()
    e = 1023 - (lz + 1)
    hi = ((hi << (lz + 1)) & M64) | (lo >> (64 - (lz + 1)))
    hi >>= 64 - 52
    hi |= e << 52
    z = frombits(hi)
    if j & 1 == 1:
        j += 1
        j &= 7
        z -= 1
    return j, z * PI4


def _kernel(x):
    """x >= 0: the octant j and the reduced z"""
    if x >= REDUCE:
        return trig_reduce(x)
    j = int(x * (4 / PI))
    y = float(j)
    if j & 1 == 1:
        j += 1
        y += 1
    j &= 7
    z = ((x - y * PI4A) - y * PI4B) - y * PI4C
    return j, z


def sin(x):
    if x == 0 or x != x:
        return x
    if x in (math.inf, -math.inf):
        return math.nan
    sign = False
    if x < 0:
        x = -x
        sign = True
    j, z = _kernel(x)
    if j > 3:
        sign = not sign
        j -= 4
    zz = z * z
    if j == 1 or j == 2:
        y = 1.0 - 0.5 * zz + zz * zz * ((((((COS[0] * zz) + COS[1]) * zz + COS[2]) * zz + COS[3]) * zz + COS[4]) * zz + COS[5])
    else:
        y = z + z * zz * ((((((SIN[0] * zz) + SIN[1]) * zz + SIN[2]) * zz + SIN[3]) * zz + SIN[4]) * zz + SIN[5])
    return -y if sign else y


def cos(x):
    if x != x or x in (math.inf, -math.inf):
        return math.nan
    sign = False
    x = abs(x)
    j, z = _kernel(x)
    if j > 3:
        j -= 4
        sign = not sign
    if j > 1:
        sign = not sign
    zz = z * z
    if j == 1 or j == 2:
        y = z + z * zz * ((((((SIN[0] * zz) + SIN[1]) * zz + SIN[2]) * zz + SIN[3]) * zz + SIN[4]) * zz + SIN[5])
    else:
        y = 1.0 - 0.5 * zz + zz * zz * ((((((COS[0] * zz) + COS[1]) * zz + COS[2]) * zz + COS[3]) * zz + COS[4]) * zz + COS[5])
    return -y if sign else y


def ldexp(frac, exp):
    if frac == 0 or frac != frac or frac in (math.inf, -math.inf):
        return frac
    if abs(frac) < 2.2250738585072014e-308:
        frac, e = frac * (1 << 52), -52
    else:
        e = 0
    exp += e
    x = bits(frac)
    exp += ((x >> 52) & 0x7FF) - 1023
    if exp < -1075:
        return math.copysign(0.0, frac)
    if exp > 1023:
        return -math.inf if frac < 0 else math.inf
    m = 1.0
    if exp < -1022:
        exp += 53
        m = 1.0 / (1 << 53)
    x &= ~(0x7FF << 52) & M64
    x |= (exp + 1023) << 52
    return m * frombits(x)


def exp(x):
    Ln2Hi = 6.93147180369123816490e-01
    Ln2Lo = 1.90821492927058770002e-10
    Log2e = 1.44269504088896338700e+00
    Overflow = 7.09782712893383973096e+02
    Underflow = -7.45133219101941108420e+02
    NearZero = 1.0 / (1 << 28)
    P1, P2, P3 = 1.66666666666666657415e-01, -2.77777777770155933842e-03, 6.61375632143793436117e-05
    P4, P5 = -1.65339022054652515390e-06, 4.13813679705723846039e-08
    if x != x:
        return x
    if x > Overflow:
        return math.inf
    if x < Underflow:
        return 0.0
    if -NearZero < x < NearZero:
        return 1 + x
    k = 0
    if x < 0:
        k = int(Log2e * x - 0.5)
    elif x > 0:
        k = int(Log2e * x + 0.5)
    hi = x - float(k) * Ln2Hi
    lo = float(k) * Ln2Lo
    r = hi - lo
    t = r * r
    c = r - t * (P1 + t * (P2 + t * (P3 + t * (P4 + t * P5))))
    y = 1 - ((lo - (r * c) / (2 - c)) - hi)
    return ldexp(y, k)


def log(x):
    Ln2Hi = 6.93147180369123816490e-01
    Ln2Lo = 1.90821492927058770002e-10
    L1, L2, L3 = 6.666666666666735130e-01, 3.999999999940941908e-01, 2.857142874366239149e-01
    L4, L5, L6, L7 = 2.222219843214978396e-01, 1.818357216161805012e-01, 1.531383769920937332e-01, 1.479819860511658591e-01
    if x != x or x == math.inf:
        return x
    if x < 0:
        return math.nan
    if x == 0:
        return -math.inf
    f1, ki = math.frexp(x)
    if f1 < math.sqrt(2) / 2:
        f1 *= 2
        ki -= 1
    f = f1 - 1
    k = float(ki)
    s = f / (2 + f)
    s2 = s * s
    s4 = s2 * s2
    t1 = s2 * (L1 + s4 * (L3 + s4 * (L5 + s4 * L7)))
    t2 = s4 * (L2 + s4 * (L4 + s4 * L6))
    R = t1 + t2
    hfsq = 0.5 * f * f
    return k * Ln2Hi - ((hfsq - (s * (hfsq + R) + k * Ln2Lo)) - f)


def _xatan(x):
    P0, P1, P2, P3, P4 = -8.750608600031904122785e-01, -1.615753718733365076637e+01, -7.500855792314704667340e+01, -1.228866684490136173410e+02, -6.485021904942025371773e+01
    Q0, Q1, Q2, Q3, Q4 = 2.485846490142306297962e+01, 1.650270098316988542046e+02, 4.328810604912902668951e+02, 4.853903996359136964868e+02, 1.945506571482613964425e+02
    z = x * x
    z = z * ((((P0 * z + P1) * z + P2) * z + P3) * z + P4) / (((((z + Q0) * z + Q1) * z + Q2) * z + Q3) * z + Q4)
    return x * z + x


def _satan(x):
    Morebits = 6.123233995736765886130e-17
    Tan3pio8 = 2.41421356237309504880
    if x <= 0.66:
        return _xatan(x)
    if x > Tan3pio8:
        return PI / 2 - _xatan(1 / x) + Morebits
    return PI / 4 + _xatan((x - 1) / (x + 1)) + 0.5 * Morebits


def atan(x):
    if x == 0:
        return x
    if x > 0:
        return _satan(x)
    return -_satan(-x)


OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata', 'mathgo')
CHECK = sys.argv[1:] == ['--check']


def emit(path, text):
    if CHECK:
        if open(path).read() != text:
            sys.exit(path + ' is not what scripts/gen_mathgo.py writes')
    else:
        open(path, 'w').write(text)


def hexs(x):
    return 'nan' if x != x else '%016x' % bits(x)


rnd = random.Random(538)
INF = math.inf
EDGES = [0.0, -0.0, 5e-324, -5e-324, 2.2250738585072014e-308, 1e-300, 1e-20, 1e-10, 1e-5, 0.1, 0.25, 0.5, 0.66, 0.7853981633974483, 1.0,
         1.5, 2.0, 2.414213562373095, 2.5, 3.0, 3.141592653589793, 4.0, 6.283185307179586, 10.0, 100.0, 1000.0, 12345.678,
         536870911.9, 536870912.0, 536870913.0, 1e9, 1e12, 1e15, 1e22, 1e100, 1.7976931348623157e308, INF, math.nan]
SIGNED = []
for v in EDGES:
    SIGNED.append(v)
    if v == v and v != 0:
        SIGNED.append(-v)
FUNCS = ['sin', 'cos', 'exp', 'ln', 'atan']
ARGS = {}
for f in FUNCS:
    a = list(SIGNED)
    for _ in range(150):
        e = rnd.choice([-3, -1, 0, 1, 2, 3, 5, 8, 12, 20])
        a.append(rnd.uniform(-1, 1) * 10.0 ** e)
    if f in ('sin', 'cos'):
        # every digit of the table of 2/Pi and the exponents where the shift is nil (exponent 55 modulo 64)
        for k in range(16):
            a += [1.37 * 2.0 ** (55 + 64 * k), 2.0 ** (55 + 64 * k), 1.99 * 2.0 ** (54 + 64 * k), 1.5 * 2.0 ** (30 + 64 * k)]
    if f == 'exp':
        a += [709.782712893384, 709.79, -745.1332191019411, -745.2, -708.3964185322641, -746.0, 3.5e-9, -3.5e-9, 3.8e-9, 700.0, -700.0]
        a += [rnd.uniform(-720, 720) for _ in range(100)]
    if f == 'ln':
        a = [v for v in a if v == v]
        a += [2.718281828459045, 1 - 2.0 ** -53, 1 + 2.0 ** -52, 0.7071067811865476, 0.7071067811865475, 1.4142135623730951]
        a += [10.0 ** rnd.uniform(-320, 308) for _ in range(100)]
        a += [x * 5e-324 for x in (1, 2, 3, 1000, 2 ** 51)]
    if f == 'atan':
        a += [0.6600000000000001, 0.6599999999999999, 2.414213562373095, 2.4142135623730954, 1e-17, 1e17]
        a += [rnd.uniform(2.41, 2.52) for _ in range(30)] + [rnd.uniform(0.6, 0.72) for _ in range(30)]
    ARGS[f] = a


def fn(f, x):
    return {'sin': sin, 'cos': cos, 'exp': exp, 'ln': log, 'atan': atan}[f](x)


calls = []
exp_ = []
for k, f in enumerate(FUNCS):
    for x in ARGS[f]:
        if f == 'ln' and x <= 0:
            continue
        calls.append('  One(%d, $%016x);\n' % (k, bits(x)))
        exp_.append(hexs(fn(f, x)) + '\n')

PROGRAM = '''program mathgo;

{ P538: Sin, Cos, Exp, Ln and ArcTan, each result as the bits of its Double }

function Hex16(v: Int64): string;
const
  Digs = '0123456789abcdef';
var
  i: Integer;
begin
  Result := '';
  for i := 15 downto 0 do
    Result := Result + Digs[((v shr (i * 4)) and 15) + 1];
end;

procedure P(r: Double);
begin
  if r <> r then
    WriteLn('nan')
  else
    WriteLn(Hex16(r as Int64));
end;

procedure One(k: Integer; b: Int64);
var
  x: Double;
begin
  x := b as Double;
  case k of
    0: P(Sin(x));
    1: P(Cos(x));
    2: P(Exp(x));
    3: P(Ln(x));
    4: P(ArcTan(x));
  end;
end;

{ the functions called deep in a stack that must grow, with strings live }
function Deep(n: Integer; const s: string): string;
var
  t: string;
  r: Double;
begin
  t := s + 'x';
  r := Sin(n * 0.001) + Cos(n * 0.002) + Exp(-n * 0.0001) + Ln(n + 1.5) + ArcTan(n * 0.01);
  if n = 0 then
    Result := t
  else
    Result := Deep(n - 1, Copy(t, 1, 3));
  if r > 1e300 then
    Result := Result + 'z';
end;

begin
%s  WriteLn(Deep(3000, 'ab'));
end.
'''


emit(OUT + '.paslang', PROGRAM % ''.join(calls))
emit(OUT + '.out', ''.join(exp_) + 'abxx\n')
