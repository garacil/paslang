#!/usr/bin/env python3
"""P539: testdata/mathacc.paslang and its expected output.

Tan, Sinh, Cosh, Tanh, ArcSinh, ArcCosh, ArcTanh, LnXP1 and Power (the core unit pasmath: Go's tan.go,
sinh.go, tanh.go, asinh.go, acosh.go, atanh.go, log1p.go and pow.go written out in Pascal), each at a
hundred arguments or more of every size, small ones and ones at both sides of every branch included,
two ways:
  accuracy: against the correctly rounded value, worked out here in 110 digits (decimal: exp, ln and
    sqrt of the module, Taylor series for the sine and cosine); the program prints "name ok" when the
    largest distance of a result from it, in units in the last place, is not above the bound that Go's
    own function has on the same arguments (measured when this script was written);
  bits: against the model of Go's own code in this file, operation for operation in Python floats (as
    scripts/gen_mathgo.py does for Sin, Cos, Exp, Ln and ArcTan, whose models are copied here); the
    program prints "name go ok" when every result has the bits of the model's. Go's Exp on amd64 is
    assembly, so the model of the functions that call it is Go's with exp.go: the bits Go gives on
    the machines that have no assembly for it (arm64), within a unit of the amd64 ones.
Then the special arguments, zeros of both signs, infinities, NaN, the denormals and the boundaries of
the branches, each against the bits Go gives (a NaN is any NaN).

usage: gen_mathacc.py            write testdata/mathacc.paslang and testdata/mathacc.out
       gen_mathacc.py --check    compare them with what this script writes"""
import math
import os
import random
import struct
import sys
from decimal import Decimal, getcontext

getcontext().prec = 110
rnd = random.Random(5390)


def bits(x):
    return struct.unpack('<q', struct.pack('<d', x))[0]


def frombits(b):
    return struct.unpack('<d', struct.pack('<q', b))[0]


def rng(lo, hi, n):
    return [rnd.uniform(lo, hi) for _ in range(n)]


def logu(lo, hi, n):
    return [math.exp(rnd.uniform(math.log(lo), math.log(hi))) for _ in range(n)]


def signed(v):
    return [x * rnd.choice((-1, 1)) for x in v]


D = Decimal
ONE = D(1)


def pi_dec():
    # Machin: pi = 16 atan(1/5) - 4 atan(1/239)
    def atan_inv(n):
        x = ONE / n
        t = x
        s = x
        k = 1
        while True:
            t = -t / (n * n)
            k += 2
            term = t / k
            if abs(term) < D(10) ** -115:
                break
            s += term
        return s
    return 16 * atan_inv(5) - 4 * atan_inv(239)


PI = pi_dec()


def d_sincos(x):
    """sine and cosine of a Decimal, by reduction to [-pi/4, pi/4] and Taylor series"""
    q = (x / (PI / 2)).to_integral_value()
    r = x - q * (PI / 2)
    n = int(q) % 4
    s, c = r, ONE
    ts, tc = r, ONE
    k = 1
    while True:
        tc = -tc * r * r / ((2 * k - 1) * (2 * k))
        ts = -ts * r * r / ((2 * k) * (2 * k + 1))
        c += tc
        s += ts
        k += 1
        if abs(ts) < D(10) ** -118 and abs(tc) < D(10) ** -118:
            break
    return [(s, c), (c, -s), (-s, -c), (-c, s)][n]


def r_tan(x):
    s, c = d_sincos(D(x))
    return s / c


def r_sinh(x):
    d = D(x)
    if abs(x) < 1e-10:
        return d + d ** 3 / 6 + d ** 5 / 120 + d ** 7 / 5040
    return (d.exp() - (-d).exp()) / 2


def r_cosh(x):
    d = D(x)
    return (d.exp() + (-d).exp()) / 2


def r_tanh(x):
    d = D(x)
    if abs(x) < 1e-10:
        return d - d ** 3 / 3 + 2 * d ** 5 / 15 - 17 * d ** 7 / 315
    e = (2 * d).exp()
    return (e - 1) / (e + 1)


def r_asinh(x):
    d = D(x)
    if abs(x) < 1e-10:
        return d - d ** 3 / 6 + 3 * d ** 5 / 40
    a = abs(d)
    v = (a + (a * a + 1).sqrt()).ln()
    return v if x >= 0 else -v


def r_acosh(x):
    d = D(x)
    return (d + (d * d - 1).sqrt()).ln()


def r_atanh(x):
    d = D(x)
    if abs(x) < 1e-10:
        return d + d ** 3 / 3 + d ** 5 / 5
    return ((1 + d) / (1 - d)).ln() / 2


def r_lnxp1(x):
    d = D(x)
    if abs(x) < 1e-10:
        return d - d ** 2 / 2 + d ** 3 / 3 - d ** 4 / 4 + d ** 5 / 5
    return (1 + d).ln()


def r_pow(x, y):
    dx, dy = D(x), D(y)
    if x < 0:
        v = (dy * (-dx).ln()).exp()
        return -v if y == int(y) and int(y) % 2 else v
    return (dy * dx.ln()).exp()


def to_double(d):
    return float(d)


# ---- the models of Go's code (math/*.go) in Python floats, operation for operation ----
M64 = (1 << 64) - 1
INF_, NAN_ = math.inf, math.nan
PI_F = math.pi
PI4A = 7.85398125648498535156e-1
PI4B = 3.77489470793079817668e-8
PI4C = 2.69515142907905952645e-15
FOUR_OVER_PI = 1.2732395447351628
REDUCE = 1 << 29
MPI4 = [0x0000000000000001, 0x45f306dc9c882a53, 0xf84eafa3ea69bb81, 0xb6c52b3278872083,
        0xfca2c757bd778ac3, 0x6e48dc74849ba5c0, 0x0c925dd413a32439, 0xfc3bd63962534e7d,
        0xd1046bea5d768909, 0xd338e04d68befc82, 0x7323ac7306a673e9, 0x3908bf177bf25076,
        0x3ff12fffbc0b301f, 0xde5e2316b414da3e, 0xda6cfd9e4f96136e, 0x9e8c7ecd3cbfd45a,
        0xea4f758fd7cbe2f6, 0x7a0e73ef14a525d4, 0xd7f6bf623f1aba10, 0xac06608df8f6d757]


def ubits(x):
    return struct.unpack('<Q', struct.pack('<d', x))[0]


def ufrom(b):
    return struct.unpack('<d', struct.pack('<Q', b & M64))[0]


def trig_reduce(x):
    ix = ubits(x)
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
    z = ufrom(hi)
    if j & 1 == 1:
        j += 1
        j &= 7
        z -= 1
    return j, z * (PI_F / 4)


def g_ldexp(frac, exp):
    if frac == 0 or frac != frac or frac in (INF_, -INF_):
        return frac
    if abs(frac) < 2.2250738585072014e-308:
        frac, e = frac * (1 << 52), -52
    else:
        e = 0
    exp += e
    x = ubits(frac)
    exp += ((x >> 52) & 0x7FF) - 1023
    if exp < -1075:
        return math.copysign(0.0, frac)
    if exp > 1023:
        return -INF_ if frac < 0 else INF_
    m = 1.0
    if exp < -1022:
        exp += 53
        m = 1.0 / (1 << 53)
    x &= ~(0x7FF << 52) & M64
    x |= (exp + 1023) << 52
    return m * ufrom(x)


def g_exp(x):
    Ln2Hi, Ln2Lo, Log2e = 6.93147180369123816490e-01, 1.90821492927058770002e-10, 1.44269504088896338700e+00
    Overflow, Underflow, NearZero = 7.09782712893383973096e+02, -7.45133219101941108420e+02, 1.0 / (1 << 28)
    P1, P2, P3 = 1.66666666666666657415e-01, -2.77777777770155933842e-03, 6.61375632143793436117e-05
    P4, P5 = -1.65339022054652515390e-06, 4.13813679705723846039e-08
    if x != x:
        return x
    if x > Overflow:
        return INF_
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
    return g_ldexp(y, k)


def g_log(x):
    Ln2Hi, Ln2Lo = 6.93147180369123816490e-01, 1.90821492927058770002e-10
    L1, L2, L3 = 6.666666666666735130e-01, 3.999999999940941908e-01, 2.857142874366239149e-01
    L4, L5, L6, L7 = 2.222219843214978396e-01, 1.818357216161805012e-01, 1.531383769920937332e-01, 1.479819860511658591e-01
    if x != x or x == INF_:
        return x
    if x < 0:
        return NAN_
    if x == 0:
        return -INF_
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


def g_tan(x):
    P = (-1.30936939181383777646e4, 1.15351664838587416140e6, -1.79565251976484877988e7)
    Q = (1.00000000000000000000e0, 1.36812963470692954678e4, -1.32089234440210967447e6, 2.50083801823357915839e7, -5.38695755929454629881e7)
    if x == 0 or x != x:
        return x
    if x in (INF_, -INF_):
        return NAN_
    sign = False
    if x < 0:
        x = -x
        sign = True
    if x >= REDUCE:
        j, z = trig_reduce(x)
    else:
        j = int(x * FOUR_OVER_PI)
        y = float(j)
        if j & 1 == 1:
            j += 1
            y += 1
        z = ((x - y * PI4A) - y * PI4B) - y * PI4C
    zz = z * z
    if zz > 1e-14:
        y = z + z * (zz * (((P[0] * zz) + P[1]) * zz + P[2]) / ((((zz + Q[1]) * zz + Q[2]) * zz + Q[3]) * zz + Q[4]))
    else:
        y = z
    if j & 2 == 2:
        y = -1 / y
    if sign:
        y = -y
    return y


def g_sinh(x):
    P0, P1, P2, P3 = -0.6307673640497716991184787251e+6, -0.8991272022039509355398013511e+5, -0.2894211355989563807284660366e+4, -0.2630563213397497062819489e+2
    Q0, Q1, Q2 = -0.6307673640497716991212077277e+6, 0.1521517378790019070696485176e+5, -0.173678953558233699533450911e+3
    sign = False
    if x < 0:
        x = -x
        sign = True
    if x > 21:
        temp = g_exp(x) * 0.5
    elif x > 0.5:
        ex = g_exp(x)
        temp = (ex - 1 / ex) * 0.5
    else:
        sq = x * x
        temp = (((P3 * sq + P2) * sq + P1) * sq + P0) * x
        temp = temp / (((sq + Q2) * sq + Q1) * sq + Q0)
    return -temp if sign else temp


def g_cosh(x):
    x = abs(x)
    if x > 21:
        return g_exp(x) * 0.5
    ex = g_exp(x)
    return (ex + 1 / ex) * 0.5


def g_tanh(x):
    P = (-9.64399179425052238628e-1, -9.92877231001918586564e1, -1.61468768441708447952e3)
    Q = (1.12811678491632931402e2, 2.23548839060100448583e3, 4.84406305325125486048e3)
    MAXLOG = 8.8029691931113054295988e+01
    z = abs(x)
    if z > 0.5 * MAXLOG:
        return -1.0 if x < 0 else 1.0
    if z >= 0.625:
        s = g_exp(2 * z)
        z = 1 - 2 / (s + 1)
        if x < 0:
            z = -z
    else:
        if x == 0:
            return x
        s = x * x
        z = x + x * s * ((P[0] * s + P[1]) * s + P[2]) / (((s + Q[0]) * s + Q[1]) * s + Q[2])
    return z


def g_log1p(x):
    Sqrt2M1, Sqrt2HalfM1 = 4.142135623730950488017e-01, -2.928932188134524755992e-01
    Small, Tiny, Two53 = 1.0 / (1 << 29), 1.0 / (1 << 54), float(1 << 53)
    Ln2Hi, Ln2Lo = 6.93147180369123816490e-01, 1.90821492927058770002e-10
    Lp = (6.666666666666735130e-01, 3.999999999940941908e-01, 2.857142874366239149e-01, 2.222219843214978396e-01,
          1.818357216161805012e-01, 1.531383769920937332e-01, 1.479819860511658591e-01)
    if x < -1 or x != x:
        return NAN_
    if x == -1:
        return -INF_
    if x == INF_:
        return INF_
    absx = abs(x)
    f = 0.0
    iu = 0
    k = 1
    if absx < Sqrt2M1:
        if absx < Small:
            if absx < Tiny:
                return x
            return x - x * x * 0.5
        if x > Sqrt2HalfM1:
            k = 0
            f = x
            iu = 1
    c = 0.0
    if k != 0:
        if absx < Two53:
            u = 1.0 + x
            iu = ubits(u)
            k = (iu >> 52) - 1023
            if k > 0:
                c = 1.0 - (u - x)
            else:
                c = x - (u - 1.0)
            c /= u
        else:
            u = x
            iu = ubits(u)
            k = (iu >> 52) - 1023
            c = 0.0
        iu &= 0x000fffffffffffff
        if iu < 0x0006a09e667f3bcd:
            u = ufrom(iu | 0x3ff0000000000000)
        else:
            k += 1
            u = ufrom(iu | 0x3fe0000000000000)
            iu = (0x0010000000000000 - iu) >> 2
        f = u - 1.0
    hfsq = 0.5 * f * f
    if iu == 0:
        if f == 0:
            if k == 0:
                return 0.0
            c += float(k) * Ln2Lo
            return float(k) * Ln2Hi + c
        R = hfsq * (1.0 - 0.66666666666666666 * f)
        if k == 0:
            return f - R
        return float(k) * Ln2Hi - ((R - (float(k) * Ln2Lo + c)) - f)
    s = f / (2.0 + f)
    z = s * s
    R = z * (Lp[0] + z * (Lp[1] + z * (Lp[2] + z * (Lp[3] + z * (Lp[4] + z * (Lp[5] + z * Lp[6]))))))
    if k == 0:
        return f - (hfsq - s * (hfsq + R))
    return float(k) * Ln2Hi - ((hfsq - (s * (hfsq + R) + (float(k) * Ln2Lo + c))) - f)


def g_asinh(x):
    Ln2, NearZero, Large = 6.93147180559945286227e-01, 1.0 / (1 << 28), float(1 << 28)
    if x != x or x in (INF_, -INF_):
        return x
    sign = False
    if x < 0:
        x = -x
        sign = True
    if x > Large:
        temp = g_log(x) + Ln2
    elif x > 2:
        temp = g_log(2 * x + 1 / (math.sqrt(x * x + 1) + x))
    elif x < NearZero:
        temp = x
    else:
        temp = g_log1p(x + x * x / (1 + math.sqrt(1 + x * x)))
    return -temp if sign else temp


def g_acosh(x):
    Ln2, Large = 6.93147180559945286227e-01, float(1 << 28)
    if x < 1 or x != x:
        return NAN_
    if x == 1:
        return 0.0
    if x >= Large:
        return g_log(x) + Ln2
    if x > 2:
        return g_log(2 * x - 1 / (x + math.sqrt(x * x - 1)))
    t = x - 1
    return g_log1p(t + math.sqrt(2 * t + t * t))


def g_atanh(x):
    NearZero = 1.0 / (1 << 28)
    if x < -1 or x > 1 or x != x:
        return NAN_
    if x == 1:
        return INF_
    if x == -1:
        return -INF_
    sign = False
    if x < 0:
        x = -x
        sign = True
    if x < NearZero:
        temp = x
    elif x < 0.5:
        temp = x + x
        temp = 0.5 * g_log1p(temp + temp * x / (1 - x))
    else:
        temp = 0.5 * g_log1p((x + x) / (1 - x))
    return -temp if sign else temp


def is_odd_int(x):
    if abs(x) >= (1 << 53):
        return False
    xf, xi = math.modf(x)
    return xf == 0 and int(xi) & 1 == 1


def signbit(x):
    return math.copysign(1.0, x) < 0


def g_pow(x, y):
    if y == 0 or x == 1:
        return 1.0
    if y == 1:
        return x
    if x != x or y != y:
        return NAN_
    if x == 0:
        if y < 0:
            return -INF_ if signbit(x) and is_odd_int(y) else INF_
        return x if signbit(x) and is_odd_int(y) else 0.0
    if y in (INF_, -INF_):
        if x == -1:
            return 1.0
        if (abs(x) < 1) == (y == INF_):
            return 0.0
        return INF_
    if x in (INF_, -INF_):
        if x < 0:
            return g_pow(1 / x, -y)
        return 0.0 if y < 0 else INF_
    if y == 0.5:
        return math.sqrt(x)
    if y == -0.5:
        return 1 / math.sqrt(x)
    yf, yi = math.modf(abs(y))
    if yf != 0 and x < 0:
        return NAN_
    if yi >= 2.0 ** 63:
        if x == -1:
            return 1.0
        if (abs(x) < 1) == (y > 0):
            return 0.0
        return INF_
    a1 = 1.0
    ae = 0
    if yf != 0:
        if yf > 0.5:
            yf -= 1
            yi += 1
        a1 = g_exp(yf * g_log(x))
    x1, xe = math.frexp(x)
    i = int(yi)
    while i != 0:
        if xe < -(1 << 12) or (1 << 12) < xe:
            ae += xe
            break
        if i & 1 == 1:
            a1 *= x1
            ae += xe
        x1 *= x1
        xe <<= 1
        if x1 < .5:
            x1 += x1
            xe -= 1
        i >>= 1
    if y < 0:
        a1 = 1 / a1 if a1 != 0 else INF_
        ae = -ae
    return g_ldexp(a1, ae)


def ulp_up(x, n=1):
    return struct.unpack('<d', struct.pack('<q', struct.unpack('<q', struct.pack('<d', x))[0] + n))[0]


def around(*xs):
    """each x, its neighbours one unit in the last place each way, and the negative of each"""
    out = []
    for x in xs:
        for v in (x, ulp_up(x, 1), ulp_up(x, -1)):
            out += [v, -v]
    return out


# function name in the language, the reference, the model of Go's code, its arguments, the bound in units
# in the last place (the largest distance Go's function has from the correctly rounded value on these
# arguments)
SETS = [
    ('Tan', r_tan, g_tan,
     rng(-1, 1, 25) + rng(-10, 10, 25) + rng(-1000, 1000, 20) + rng(-1e6, 1e6, 10) + signed(logu(1e-300, 1e-3, 20)),
     around(1e-8, 1e-7, 0.5, math.pi / 4, math.pi / 2, 3 * math.pi / 4, math.pi, 100.0, 536870911.0, 536870912.0, 536870913.0, 1e10, 1e22), 1),
    ('Sinh', r_sinh, g_sinh,
     rng(-1, 1, 25) + rng(-20, 20, 25) + rng(-700, 700, 25) + signed(logu(1e-300, 1e-3, 25)),
     around(0.5, 21.0, 1e-5, 700.0, 709.0), 1),
    ('Cosh', r_cosh, g_cosh,
     rng(-1, 1, 25) + rng(-20, 20, 25) + rng(-700, 700, 25),
     around(21.0, 1e-5, 700.0, 709.0), 1),
    ('Tanh', r_tanh, g_tanh,
     rng(-1, 1, 30) + rng(-20, 20, 30) + signed(logu(1e-300, 1e-3, 30)),
     around(0.625, 0.5, 1e-5, 20.0, 44.0, 44.0148459655565), 1),
    ('ArcSinh', r_asinh, g_asinh,
     signed(logu(1e-300, 1e300, 80)) + rng(-10, 10, 20),
     around(2.0 ** -28, 2.0, 2.0 ** 28, 1.0, 1e300), 1),
    ('ArcCosh', r_acosh, g_acosh,
     [1 + x for x in logu(1e-16, 1, 40)] + logu(1, 1e300, 40) + rng(1, 10, 20),
     [x for x in around(2.0, 2.5, 3.0, 2.0 ** 28, 1.0, 1.5) if x >= 1], 1),
    ('ArcTanh', r_atanh, g_atanh,
     rng(-1, 1, 30) + [1 - x for x in logu(1e-16, 1, 30)] + signed(logu(1e-300, 1e-3, 30)),
     [x for x in around(2.0 ** -28, 0.5, 0.25, 0.9) if abs(x) < 1], 1),
    ('LnXP1', r_lnxp1, g_log1p,
     rng(-0.99, 10, 30) + signed(logu(1e-300, 1e-3, 30)) + logu(1e-3, 1e300, 20) + [-1 + x for x in logu(1e-16, 0.5, 20)],
     [x for x in around(0.41421356237309503, 0.2928932188134524, 2.0 ** -29, 2.0 ** -54, 0.5, 1.0, 3.0, 7.0, 15.0, 1e-5, float(1 << 53), 1e300) if x > -1] + [-0.5, -0.75, -0.875, 1.9e-9, 6e-17, 5.0e-17], 1),
]
POW_RANDOM = ([(a, b) for a, b in zip(logu(1e-3, 1e3, 60), rng(-8, 8, 60))] + [(a, float(rnd.randint(-9, 9))) for a in rng(-5, 5, 30)] +
              [(a, b) for a, b in zip(rng(0.01, 1, 30), rng(-40, 40, 30))])
POW = (
       # the fraction above a half, exactly a half, below; big integer exponents; the scaling out of the normal range
       [(3.0, 1.7), (3.0, 2.5), (3.0, 2.3), (0.5, 0.9), (7.0, -2.75), (1.0000001, 1e9), (1.0000001, -1e9), (2.0, 1000.0), (0.5, 1100.0), (2.0, -1060.0),
        (1e300, 20.0), (1e-300, 20.0), (1e300, -20.0), (5e-324, 3.0), (5e-324, -1.5), (1e-310, 1.5), (1.5, 100.0), (1.5, -100.0), (10.0, 300.0), (10.0, -300.0),
        (10.0, 308.5), (10.0, -320.5), (0.9999999999999999, 3e15), (1.0000000000000002, 3e15), (-1.5, 11.0), (-1.5, 10.0), (-7.0, 3.0), (-7.0, -4.0), (2.0, 0.5000000000000001),
        (2.0, 1.4999999999999998), (1e-5, 123.456), (123.456, 1e-5), (9.5, 5000.0), (0.99, 5000.0), (4096.0, 1000.0), (4097.0, 1000.0), (1.01, 5000.0),
        (3e-320, -0.9), (1e-310, -0.9), (2.5e-315, 0.9), (-2.0, 1023.0), (-2.0, 1024.0), (-2.0, -1074.0), (-2.0, -1075.0), (-2.0, -1022.0), (-2.0, -1023.0),
        (2.0, -1023.0), (2.0, -1022.0), (3.0, -645.5), (7.0, 400.25)])
POW_BOUND = 7

NAN, INF = math.nan, math.inf
DEN = 5e-324
# special arguments and the bits Go gives; (function, argument(s), result)
SPECIAL = [
    ('Tan', (0.0,), 0.0), ('Tan', (-0.0,), -0.0), ('Tan', (INF,), NAN), ('Tan', (-INF,), NAN), ('Tan', (NAN,), NAN), ('Tan', (DEN,), DEN), ('Tan', (1e-300,), 1e-300),
    ('Sinh', (0.0,), 0.0), ('Sinh', (-0.0,), -0.0), ('Sinh', (INF,), INF), ('Sinh', (-INF,), -INF), ('Sinh', (NAN,), NAN), ('Sinh', (1e-310,), 1e-310),
    ('Sinh', (711.0,), INF), ('Sinh', (-711.0,), -INF), ('Sinh', (1e300,), INF),
    ('Cosh', (0.0,), 1.0), ('Cosh', (-0.0,), 1.0), ('Cosh', (INF,), INF), ('Cosh', (-INF,), INF), ('Cosh', (NAN,), NAN), ('Cosh', (711.0,), INF), ('Cosh', (1e300,), INF),
    ('Tanh', (0.0,), 0.0), ('Tanh', (-0.0,), -0.0), ('Tanh', (INF,), 1.0), ('Tanh', (-INF,), -1.0), ('Tanh', (NAN,), NAN), ('Tanh', (100.0,), 1.0), ('Tanh', (-1e300,), -1.0), ('Tanh', (1e-300,), 1e-300),
    ('ArcSinh', (0.0,), 0.0), ('ArcSinh', (-0.0,), -0.0), ('ArcSinh', (INF,), INF), ('ArcSinh', (-INF,), -INF), ('ArcSinh', (NAN,), NAN), ('ArcSinh', (DEN,), DEN),
    ('ArcCosh', (1.0,), 0.0), ('ArcCosh', (INF,), INF), ('ArcCosh', (NAN,), NAN),
    ('ArcTanh', (0.0,), 0.0), ('ArcTanh', (-0.0,), -0.0), ('ArcTanh', (NAN,), NAN), ('ArcTanh', (DEN,), DEN), ('ArcTanh', (1e-300,), 1e-300),
    ('LnXP1', (0.0,), 0.0), ('LnXP1', (-0.0,), -0.0), ('LnXP1', (INF,), INF), ('LnXP1', (NAN,), NAN), ('LnXP1', (DEN,), DEN), ('LnXP1', (1e-300,), 1e-300),
    ('Power', (0.0, 0.0), 1.0), ('Power', (0.0, 1.0), 0.0), ('Power', (0.0, 2.0), 0.0), ('Power', (-0.0, 3.0), -0.0), ('Power', (-0.0, 2.0), 0.0), ('Power', (2.0, 0.0), 1.0),
    ('Power', (1.0, NAN), 1.0), ('Power', (2.0, NAN), NAN), ('Power', (NAN, 0.0), 1.0), ('Power', (NAN, 1.0), NAN), ('Power', (2.0, 1.0), 2.0), ('Power', (4.0, 0.5), 2.0), ('Power', (4.0, -0.5), 0.5),
    ('Power', (2.0, 1e19), INF), ('Power', (2.0, -1e19), 0.0), ('Power', (0.5, 1e19), 0.0), ('Power', (0.5, -1e19), INF), ('Power', (INF, 2.0), INF), ('Power', (INF, -2.0), 0.0),
    ('Power', (-INF, 3.0), -INF), ('Power', (-INF, 2.0), INF), ('Power', (-INF, -3.0), -0.0), ('Power', (2.0, INF), INF), ('Power', (0.5, INF), 0.0), ('Power', (2.0, -INF), 0.0),
    ('Power', (0.5, -INF), INF), ('Power', (INF, INF), INF), ('Power', (1e300, 2.0), INF), ('Power', (1e-300, 2.0), 0.0), ('Power', (10.0, 309.0), INF), ('Power', (2.0, 1023.0), 2.0 ** 1023),
    ('Power', (2.0, 1024.0), INF), ('Power', (2.0, -1074.0), DEN), ('Power', (2.0, -1075.0), 0.0), ('Power', (-2.0, 3.0), -8.0), ('Power', (-2.0, 2.0), 4.0), ('Power', (-2.0, -3.0), -0.125),
    ('Power', (-2.0, 1e15), INF), ('Power', (2.0, 63.0), 2.0 ** 63), ('Power', (2.0, 64.0), 2.0 ** 64), ('Power', (-3.0, 41.0), -(3.0 ** 41)), ('Power', (10.0, 2.0), 100.0), ('Power', (10.0, -2.0), 0.01),
    ('Power', (5e-324, 2.0), 0.0), ('Power', (5e-324, 0.5), 2.2227587494850775e-162),
]




def hexlit(b):
    return '$%016X' % (b & 0xFFFFFFFFFFFFFFFF)


def table(name, vals):
    lines = []
    row = []
    for i, v in enumerate(vals):
        row.append(hexlit(v))
        if len(row) == 5:
            lines.append('    ' + ', '.join(row))
            row = []
    if row:
        lines.append('    ' + ', '.join(row))
    return '  %s: array[0..%d] of Int64 = (\n%s\n  );' % (name, len(vals) - 1, ',\n'.join(lines))


def same_bits(a, b):
    return (a != a and b != b) or bits(a) == bits(b)


def build():
    consts = []
    body = []
    for fn, ref, model, rargs, bargs, bound in SETS:
        args = rargs + bargs
        a = [bits(x) for x in args]
        e = [bits(to_double(ref(x))) for x in rargs]
        g = [bits(model(x)) for x in args]
        consts += [table(fn + 'A', a), table(fn + 'E', e), table(fn + 'G', g)]
        body.append("  Worst := 0;\n  Bad := 0;\n  for i := 0 to %d do\n  begin\n    r := %s(%sA[i] as Double);\n    if i <= %d then\n    begin\n      d := Dist(r as Int64, %sE[i]);\n      if d > Worst then\n        Worst := d;\n    end;\n    if (r as Int64) <> %sG[i] then\n      Inc(Bad);\n  end;\n  Report('%s', Worst, %d, Bad);"
                    % (len(a) - 1, fn, fn, len(rargs) - 1, fn, fn, fn.lower(), bound))
    pargs = POW_RANDOM + POW
    a = [bits(x) for x, _ in pargs]
    b = [bits(y) for _, y in pargs]
    e = [bits(to_double(r_pow(x, y))) for x, y in POW_RANDOM]
    g = [bits(g_pow(x, y)) for x, y in pargs]
    consts += [table('PowA', a), table('PowB', b), table('PowE', e), table('PowG', g)]
    body.append("  Worst := 0;\n  Bad := 0;\n  for i := 0 to %d do\n  begin\n    r := Power(PowA[i] as Double, PowB[i] as Double);\n    if i <= %d then\n    begin\n      d := Dist(r as Int64, PowE[i]);\n      if d > Worst then\n        Worst := d;\n    end;\n    if (r as Int64) <> PowG[i] then\n      Inc(Bad);\n  end;\n  Report('power', Worst, %d, Bad);" % (len(a) - 1, len(POW_RANDOM) - 1, POW_BOUND))
    # the special arguments
    sp = []
    for fn, args, res in SPECIAL:
        sp.append((fn, [bits(x) for x in args], bits(res), res != res))
    consts.append(table('SpA', [x[1][0] for x in sp]))
    consts.append(table('SpB', [x[1][1] if len(x[1]) > 1 else 0 for x in sp]))
    consts.append(table('SpE', [x[2] for x in sp]))
    consts.append('  SpNaN: array[0..%d] of Integer = (%s);' % (len(sp) - 1, ', '.join('1' if x[3] else '0' for x in sp)))
    names = [s[0] for s in SETS] + ['Power']
    consts.append('  SpFn: array[0..%d] of Integer = (%s);' % (len(sp) - 1, ', '.join(str(names.index(x[0])) for x in sp)))
    cases = []
    for k, nm in enumerate(names):
        call = '%s(x)' % nm if nm != 'Power' else 'Power(x, y)'
        cases.append("      %d: r := %s;" % (k, call))
    body.append("""  Bad := 0;
  for i := 0 to %d do
  begin
    x := SpA[i] as Double;
    y := SpB[i] as Double;
    case SpFn[i] of
%s
    end;
    if SpNaN[i] = 1 then
    begin
      if r = r then
        Inc(Bad);
    end
    else if (r as Int64) <> SpE[i] then
      Inc(Bad);
  end;
  if Bad = 0 then
    WriteLn('special ok')
  else
    WriteLn('special FAIL ', Bad);""" % (len(sp) - 1, '\n'.join(cases)))
    head_txt = """{ P539: Tan, Sinh, Cosh, Tanh, ArcSinh, ArcCosh, ArcTanh, LnXP1 and Power at their accuracy: each result
  within the number of units in the last place that Go's own function is of the correctly rounded value
  (worked out in 110 digits by scripts/gen_mathacc.py), the bits those of the model of Go's code in the
  script, and the special arguments to the bit. }
program mathacc;

const
"""
    prog = head_txt + '\n'.join(consts) + """

var
  i, Bad: Integer;
  Worst, d: Int64;
  x, y, r: Double;

function Ordered(b: Int64): Int64;
begin
  if b < 0 then
    Result := -(b and $7FFFFFFFFFFFFFFF)
  else
    Result := b;
end;

function Dist(a, b: Int64): Int64;
begin
  Result := Ordered(a) - Ordered(b);
  if Result < 0 then
    Result := -Result;
end;

procedure Report(const Name: string; W, Bound: Int64; BadBits: Integer);
begin
  if W <= Bound then
    WriteLn(Name, ' ok')
  else
    WriteLn(Name, ' FAIL ', W, ' units, bound ', Bound);
  if BadBits = 0 then
    WriteLn(Name, ' go ok')
  else
    WriteLn(Name, ' go FAIL ', BadBits, ' results differ from the model of Go');
end;

begin
""" + '\n'.join(body) + '\nend.\n'
    out = ''.join('%s ok\n%s go ok\n' % (s[0].lower(), s[0].lower()) for s in SETS) + 'power ok\npower go ok\nspecial ok\n'
    return prog, out


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    td = os.path.join(here, '..', 'testdata')
    prog, out = build()
    if len(sys.argv) > 1 and sys.argv[1] == '--check':
        if open(os.path.join(td, 'mathacc.paslang')).read() != prog or open(os.path.join(td, 'mathacc.out')).read() != out:
            print('testdata/mathacc.* is not what scripts/gen_mathacc.py writes')
            sys.exit(1)
        return
    open(os.path.join(td, 'mathacc.paslang'), 'w').write(prog)
    open(os.path.join(td, 'mathacc.out'), 'w').write(out)


if __name__ == '__main__':
    main()
