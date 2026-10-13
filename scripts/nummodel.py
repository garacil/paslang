#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
#
# paslang is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# paslang is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with paslang.  If not, see <https://www.gnu.org/licenses/>.

"""The model of pasnum (P200): seeded cases for testdata/numtext and the
answers worked out exactly, in Python's integers, never through a
float's arithmetic.

    scripts/nummodel.py --seed S --count N CASES EXPECT

writes N cases to CASES, one a line, and the answer to each to EXPECT,
as testdata/numtext prints it:

    p TEXT, j TEXT  scan TEXT with Pascal's grammar or JSON's (RFC 8259):
                    "bad OFFSET", or the bytes taken, the nearest
                    Double's bits and 1 (0 past the largest), the
                    nearest Single's bits and the same, then 1 and the
                    Int64 or 0 0, 1 and the QWord or 0 0
    a BITS, b BITS  the Double or the Single with those bits, in the
                    fewest digits that read back as it, laid out as
                    ECMAScript writes a number (ECMA-262 Number::
                    toString), -0 kept, NaN, +Inf, -Inf
    i V, u V        V as an Int64, and as a QWord

    scripts/nummodel.py --go-vectors GOSTRCONV OUT

writes OUT, testdata/numgo.txt, from Go's own tests in GOSTRCONV
(golang/src/internal/strconv): every input of atoftests and atof32tests
(but the one with a NUL in it) as a p and a j case, and every value of
ftoatests as an a case; gen puts those cases first.

The nearest binary float is the rational value rounded once, a tie to
even, below the smallest subnormal to 0. The fewest digits are the
shortest decimal that rounds back to the float, and among those the
nearest to it, a tie to an even last digit: for a Double, Python's
repr (David Gay's shortest mode); for a Single, a search over the
lengths 1 to 9 against the interval that rounds to it. The cases mix
random floats written in every form, more digits than 19 and up to the
exact halfway points between two floats (a thousand digits for a
subnormal one), and a hair to either side of those, the integer ends,
and the grammar's edges.
"""
import random
import sys
from decimal import Decimal

M64 = (1 << 64) - 1
DIGITS = "0123456789"


def scan(t, json):
    """(ok, len, intlit) as PasNumScan reads t."""
    n = len(t)
    i = 0
    if n > 0:
        if t[0] == "-":
            i = 1
        elif t[0] == "+" and not json:
            i = 1
    if json:
        if i >= n or t[i] not in DIGITS:
            return False, i, False
        if t[i] == "0" and i + 1 < n and t[i + 1] in DIGITS:
            return False, i + 1, False
    sawdot = sawdigits = False
    dot = -1
    while i < n:
        c = t[i]
        if c in DIGITS:
            sawdigits = True
            i += 1
            continue
        if c == ".":
            if sawdot:
                break
            sawdot = True
            dot = i
            i += 1
            continue
        break
    if not sawdigits or (json and sawdot and i == dot + 1):
        return False, i, False
    intlit = not sawdot
    if i < n and t[i] in "eE":
        intlit = False
        i += 1
        if i >= n:
            return False, i, False
        if t[i] in "+-":
            i += 1
        if i >= n or t[i] not in DIGITS:
            return False, i, False
        while i < n and t[i] in DIGITS:
            i += 1
    return True, i, intlit


def value(t):
    """(neg, mant, exp10) of a scanned number: mant * 10^exp10 exactly,
    the exponent's digits read as the scanner reads them (a long one
    only moves the point far enough)."""
    i = 0
    neg = False
    if t[0] in "+-":
        neg = t[0] == "-"
        i = 1
    j = i
    while j < len(t) and t[j] not in "eE":
        j += 1
    body = t[i:j]
    if "." in body:
        a, b = body.split(".")
    else:
        a, b = body, ""
    mant = int(a + b) if a + b else 0
    exp10 = -len(b)
    if j < len(t):
        k = j + 1
        es = 1
        if t[k] in "+-":
            es = -1 if t[k] == "-" else 1
            k += 1
        e = 0
        while k < len(t):
            if e < 10000:
                e = e * 10 + int(t[k])
            k += 1
        exp10 += es * e
    return neg, mant, exp10


def round_bin(num, den, p, minq, bias):
    """num/den (> 0) to the nearest binary float of p significant bits,
    the smallest subnormal 2^-minq: (bits without the sign, in range)."""
    e = num.bit_length() - den.bit_length()
    if e >= 0:
        if num < den << e:
            e -= 1
    elif num << -e < den:
        e -= 1
    q = max(e - (p - 1), -minq)
    if q >= 0:
        n2, d2 = num, den << q
    else:
        n2, d2 = num << -q, den
    m, r = divmod(n2, d2)
    if 2 * r > d2 or (2 * r == d2 and m & 1):
        m += 1
    if m == 1 << p:
        m >>= 1
        q += 1
    if m < 1 << (p - 1):
        return m, True
    field = q + (p - 1) + bias
    top = (1 << (64 - p)) - 1 if p == 53 else 255
    if field >= top:
        return top << (p - 1), False
    return (field << (p - 1)) | (m - (1 << (p - 1))), True


def nearest(neg, mant, exp10, single):
    """the bits of the nearest Double or Single and whether in range"""
    p, minq, bias, sbit = (24, 149, 127, 31) if single else (53, 1074, 1023, 63)
    sign = (1 << sbit) if neg else 0
    if mant == 0:
        return sign, True
    order = len(str(mant)) + exp10
    if order > 400:
        top = 255 if single else 2047
        return sign | (top << (p - 1)), False
    if order < -400:
        return sign, True
    if exp10 >= 0:
        num, den = mant * 10 ** exp10, 1
    else:
        num, den = mant, 10 ** -exp10
    bits, ok = round_bin(num, den, p, minq, bias)
    return sign | bits, ok


def signed64(v):
    v &= M64
    return v - (1 << 64) if v >> 63 else v


def scan_answer(t, json):
    ok, n, intlit = scan(t, json)
    if not ok:
        return "bad %d" % n
    neg, mant, exp10 = value(t[:n])
    b64, r64 = nearest(neg, mant, exp10, False)
    b32, r32 = nearest(neg, mant, exp10, True)
    oki = oku = 0
    vi = vu = 0
    if intlit:
        v = -mant if neg else mant
        if -(1 << 63) <= v < 1 << 63:
            oki, vi = 1, v
        if 0 <= v <= M64:
            oku, vu = 1, signed64(v)
    return "%d %d %d %d %d %d %d %d %d" % (n, signed64(b64), r64, b32, r32, oki, vi, oku, vu)


def layout(neg, digits, dp):
    """digits (no trailing zeros), the point after dp of them, as
    ECMAScript writes the number"""
    nd = len(digits)
    s = "-" if neg else ""
    if dp >= 22 or dp <= -6:
        s += digits[0]
        if nd > 1:
            s += "." + digits[1:]
        x = dp - 1
        s += "e" + ("-" if x < 0 else "+") + str(abs(x))
    elif dp <= 0:
        s += "0." + "0" * -dp + digits
    elif dp >= nd:
        s += digits + "0" * (dp - nd)
    else:
        s += digits[:dp] + "." + digits[dp:]
    return s


def parts(bits, single):
    """(kind, neg, num, den): kind 0 a number num/den, 1 zero, 2 inf, 3 NaN"""
    if single:
        bits &= 0xFFFFFFFF
        neg = bits >> 31 != 0
        ex = (bits >> 23) & 255
        man = bits & ((1 << 23) - 1)
        emax, mb, bias = 255, 23, 127
    else:
        bits &= M64
        neg = bits >> 63 != 0
        ex = (bits >> 52) & 2047
        man = bits & ((1 << 52) - 1)
        emax, mb, bias = 2047, 52, 1023
    if ex == emax:
        return (3 if man else 2), neg, 0, 1
    if ex == 0 and man == 0:
        return 1, neg, 0, 1
    if ex == 0:
        ex = 1
    else:
        man |= 1 << mb
    e = ex - bias - mb
    if e >= 0:
        return 0, neg, man << e, 1
    return 0, neg, man, 1 << -e


def short_digits32(bits):
    """the shortest digits that read back as the Single, the nearest of
    them: (digits, dp)"""
    _, neg, num, den = parts(bits, True)
    b = bits & 0x7FFFFFFF
    # the interval of the reals that round to it
    def val(x):
        if x >= 0x7F800000:
            return 1 << 128, 1
        _, _, n, d = parts(x, True)
        return n, d
    hn, hd = val(b + 1)
    if b > 0:
        ln, ld = val(b - 1)
    else:
        ln, ld = 0, 1
    from fractions import Fraction
    v = Fraction(num, den)
    lo = (Fraction(ln, ld) + v) / 2
    hi = (Fraction(hn, hd) + v) / 2
    even = (b & 1) == 0
    def inside(x):
        if even:
            return lo <= x <= hi
        return lo < x < hi
    # the order of v: 10^(o-1) <= v < 10^o
    o = len(str(num // den)) if num >= den else 0
    if num < den:
        o = 0
        while Fraction(10) ** (o - 1) > v:
            o -= 1
    while Fraction(10) ** o <= v:
        o += 1
    while Fraction(10) ** (o - 1) > v:
        o -= 1
    for k in range(1, 12):
        q = o - k
        unit = Fraction(10) ** q
        c0 = (v / unit).numerator // (v / unit).denominator
        best = None
        for c in (c0, c0 + 1):
            if c > 0 and inside(c * unit):
                dist = abs(c * unit - v)
                if best is None or dist < best[0] or (dist == best[0] and c % 2 == 0):
                    best = (dist, c)
        if best:
            c = best[1]
            ds = str(c)
            dp = len(ds) + q
            return ds.rstrip("0"), dp
    raise AssertionError("no digits for %x" % bits)


def short_answer(bits, single):
    kind, neg, num, den = parts(bits, single)
    if kind == 3:
        return "NaN"
    if kind == 2:
        return "-Inf" if neg else "+Inf"
    if kind == 1:
        return "-0" if neg else "0"
    if single:
        digits, dp = short_digits32(bits)
    else:
        import struct
        f = struct.unpack("<d", struct.pack("<Q", bits & M64))[0]
        sign, ds, ex = Decimal(repr(abs(f))).as_tuple()
        digits = "".join(map(str, ds))
        dp = len(digits) + ex
        digits = digits.rstrip("0")
        dp -= 0
        lead = len(digits) - len(digits.lstrip("0"))
        digits = digits.lstrip("0")
        dp -= lead
    return layout(neg, digits, dp)


# ---- the cases ----

def rand_double_bits(rng):
    r = rng.random()
    if r < 0.05:
        return rng.getrandbits(52) | (rng.getrandbits(1) << 63)            # subnormal
    if r < 0.10:
        return rng.choice([0, 1 << 63, 0x7FF << 52, 0xFFF << 52, (0x7FF << 52) | 1,
                           0x7FEFFFFFFFFFFFFF, 1, 0x0010000000000000, 0x000FFFFFFFFFFFFF])
    if r < 0.40:
        # around 1, the common case
        return ((1023 + rng.randint(-60, 60)) << 52) | rng.getrandbits(52) | (rng.getrandbits(1) << 63)
    return rng.getrandbits(64)


def finite_double(rng):
    while True:
        b = rand_double_bits(rng)
        if (b >> 52) & 2047 != 2047:
            return b


def exact_text(num, den):
    """num/den (den a power of two) as an exact decimal"""
    if den == 1:
        return str(num)
    k = den.bit_length() - 1
    digits = str(num * 5 ** k)
    if len(digits) <= k:
        digits = "0" * (k - len(digits) + 1) + digits
    return digits[:-k] + "." + digits[-k:]


def float_texts(rng, bits, json):
    """texts of the Double with these bits, or near it"""
    import struct
    kind, neg, num, den = parts(bits, False)
    f = struct.unpack("<d", struct.pack("<Q", bits))[0]
    sign = "-" if neg else ("+" if (not json and rng.random() < 0.1) else "")
    a = abs(f)
    forms = [repr(a), "%.17e" % a, "%.16e" % a, "%.20e" % a, "%.25e" % a, "%.40e" % a,
             "%.3e" % a, "%.19g" % a, "%.15g" % a]
    t = rng.choice(forms)
    if t.endswith(".0") and rng.random() < 0.5:
        t = t[:-2]
    r = rng.random()
    if r < 0.15 and kind == 0:
        # the halfway point to the next Double up, exactly, or a hair off
        up = bits + 1
        _, _, n2, d2 = parts(up, False)
        if (up >> 52) & 2047 != 2047:
            from fractions import Fraction
            mid = (Fraction(num, den) + Fraction(n2, d2)) / 2
            t = exact_text(mid.numerator, mid.denominator)
            w = rng.random()
            if w < 0.33:
                t = t + ("" if "." in t else ".") + "0" * rng.randint(0, 30) + "1"
            elif w < 0.66 and t[-1] != "0":
                t = t[:-1] + str(int(t[-1]) - 1) + "9" * rng.randint(0, 30)
    elif r < 0.25 and kind == 0:
        t = exact_text(num, den)
    if json:
        if t.startswith("."):
            t = "0" + t
        if t.endswith("."):
            t = t + "0"
        t = t.replace("e+0", "e+").replace("e-0", "e-")
    else:
        if rng.random() < 0.1 and t.startswith("0."):
            t = t[1:]
        if rng.random() < 0.05:
            t = t.replace("e", "E")
    return sign + t


def random_digits_text(rng, json):
    nd = rng.choice([1, 2, 5, 8, 15, 16, 17, 18, 19, 20, 21, 25, 30, 40, 60, 100, 300, 800, 900])
    d = "".join(rng.choice(DIGITS) for _ in range(nd))
    if json:
        d = d.lstrip("0") or "0"
    if rng.random() < 0.6 and len(d) > 1:
        k = rng.randint(1, len(d) - 1)
        if json and d[:k].lstrip("0") == "" and k > 1:
            k = 1
        d = d[:k] + "." + d[k:]
    if rng.random() < 0.7:
        d += rng.choice("eE") + rng.choice(["", "+", "-"]) + str(rng.choice(
            [rng.randint(0, 30), rng.randint(0, 350), rng.randint(280, 360), rng.randint(0, 1200), 99999,
             123456789]))
    if rng.random() < 0.3:
        d = "-" + d
    return d


INT_EDGES = [0, 1, -1, 9, 10, 99, 100, 2 ** 53, 2 ** 63 - 1, -(2 ** 63), 2 ** 63, -(2 ** 63) - 1,
             2 ** 64 - 1, 2 ** 64, 10 ** 18, 10 ** 19 - 1, 10 ** 19, 10 ** 20 - 1, 10 ** 20,
             18446744073709551610, 18446744073709551616, 18446744073709551619,
             18446744073709551625, 9223372036854775806, -9223372036854775807]

GRAMMAR = ["", "+", "-", ".", "+.", "-.", "e", "e5", ".e5", "1e", "1e+", "1e-", "1E5", "1.5x",
           "01", "-01", "00", "0.", ".5", "5.", "-.5", "1.2.3", "1e5.5", "1.e5", "0e0", "-0", "+0",
           "0.0", "-0.0", "00000000000000000000001", "1" * 30, "0x10", "1_000", " 1", "1 ",
           "1e0000000000000000000000000005", "1e-99999999999", "1e99999999999", "9" * 400,
           "0." + "0" * 400 + "1", "1." + "0" * 400 + "1e-400", "inf", "NaN", "-", "--1",
           "+-1", "1e++1", "2.2250738585072011e-308", "2.2250738585072012e-308",
           "1.7976931348623157e308", "1.7976931348623158e308", "1.7976931348623159e308",
           "4.9406564584124654e-324", "2.4703282292062327e-324", "2.4703282292062328e-324",
           "3.4028235e38", "3.4028236e38", "3.4028235677973366e38", "1.4e-45", "7.0e-46",
           "7.006492321624085354618e-46", "7.006492321624086e-46", "123456789012345678901234567890",
           "0.000000000000000000000000000000000000000000001", "1e-45", "1e39", "1e38",
           "9007199254740993", "9007199254740992.5", "-9223372036854775808",
           "9223372036854775807", "9223372036854775808", "18446744073709551615",
           "18446744073709551616", "-18446744073709551615", "1e22", "1e23", "8.5e-6", "1e21",
           "999999999999999999999", "1000000000000000000000"]


GO_VECTORS = "testdata/numgo.txt"


def go_vectors(gosrc, out):
    """the inputs of Go's atof and ftoa tests as cases"""
    import math
    import re
    import struct
    from pathlib import Path
    atof = (Path(gosrc) / "atof_test.go").read_text()
    lines = ["# The inputs of Go's tests of strconv (golang/src/internal/strconv,",
             "# atof_test.go: atoftests and atof32tests; ftoa_test.go: ftoatests),",
             "# written by scripts/nummodel.py --go-vectors; # starts a comment."]
    for name in ("atoftests", "atof32tests"):
        a = atof.index("var %s = []atofTest{" % name)
        body = atof[a:atof.index("\n}\n", a)]
        for t in re.findall(r'\{"((?:[^"\\]|\\.)*)",', body):
            if "\\" in t:
                continue
            lines.append("p " + t)
            lines.append("j " + t)
    ftoa = (Path(gosrc) / "ftoa_test.go").read_text()
    a = ftoa.index("var ftoatests = []ftoaTest{")
    body = ftoa[a:ftoa.index("\n}\n", a)]
    names = {"math": math, "fdiv": lambda x, y: x / y,
             "above1e23": float(100000000000000008388608), "below1e23": float(99999999999999974834176)}
    seen = set()
    for e in re.findall(r"^\s*\{(.*), '.', -?\d+, \"[^\"]*\"\},", body, re.M):
        e = re.sub(r"0x[0-9a-fA-F.]+p[-+]?\d+", lambda m: "float.fromhex('%s')" % m.group(0), e)
        e = e.replace("math.Inf(0)", "math.inf").replace("math.Inf(-1)", "-math.inf")
        e = e.replace("math.NaN()", "math.nan")
        f = float(eval(e, {"__builtins__": {"float": float}}, names))
        bits = struct.unpack("<q", struct.pack("<d", f))[0]
        if bits not in seen:
            seen.add(bits)
            lines.append("a %d" % bits)
    Path(out).write_text("\n".join(lines) + "\n")


def gen(seed, count):
    rng = random.Random(seed)
    cases = []
    with open(GO_VECTORS) as f:
        cases += [line.rstrip("\n") for line in f if not line.startswith("#")]
    for g in GRAMMAR:
        cases.append("p " + g)
        cases.append("j " + g)
    for v in INT_EDGES:
        for g in ("p", "j"):
            cases.append("%s %d" % (g, v))
        if -(1 << 63) <= v < 1 << 63:
            cases.append("i %d" % v)
        if 0 <= v <= M64:
            cases.append("u %d" % signed64(v))
    for b in [0, 1 << 63, 0x7FF << 52, 0xFFF << 52, (0x7FF << 52) | 1, 1, 0x7FEFFFFFFFFFFFFF,
              0x3FF0000000000000, 0x4415AF1D78B58C40, 0x444B1AE4D6E2EF50, 0x3EB0C6F7A0B5ED8D,
              0x3EB0C6F7A0B5ED8C, 0x3EAAD7F29ABCAF48]:
        cases.append("a %d" % signed64(b))
    for b in [0, 0x80000000, 0x7F800000, 0xFF800000, 0x7FC00000, 1, 0x7F7FFFFF, 0x3F800000,
              0x00800000, 0x007FFFFF]:
        cases.append("b %d" % b)
    while len(cases) < count:
        r = rng.random()
        json = rng.random() < 0.5
        g = "j" if json else "p"
        if r < 0.45:
            cases.append("%s %s" % (g, float_texts(rng, finite_double(rng), json)))
        elif r < 0.60:
            cases.append("%s %s" % (g, random_digits_text(rng, json)))
        elif r < 0.67:
            v = rng.choice([rng.getrandbits(64), rng.getrandbits(rng.randint(1, 64)),
                            -rng.getrandbits(rng.randint(1, 63))])
            cases.append("%s %d" % (g, v))
            cases.append("i %d" % signed64(v))
            cases.append("u %d" % signed64(v))
        elif r < 0.87:
            cases.append("a %d" % signed64(rand_double_bits(rng)))
        else:
            e = rng.random()
            if e < 0.1:
                b = rng.getrandbits(23) | (rng.getrandbits(1) << 31)
            elif e < 0.5:
                b = ((127 + rng.randint(-30, 30)) << 23) | rng.getrandbits(23) | (rng.getrandbits(1) << 31)
            else:
                b = rng.getrandbits(32)
            cases.append("b %d" % b)
    return cases[:max(count, len(cases))]


def answer(line):
    k, t = line[0], line[2:]
    if k in "pj":
        return scan_answer(t, k == "j")
    v = int(t)
    if k == "a":
        return short_answer(v & M64, False)
    if k == "b":
        return short_answer(v, True)
    if k == "i":
        return str(v)
    return str(v & M64)


def main(argv):
    args = argv[1:]
    if args[:1] == ["--go-vectors"] and len(args) == 3:
        go_vectors(args[1], args[2])
        return
    seed, count = 1, 1000
    while args and args[0].startswith("--"):
        if args[0] == "--seed":
            seed = int(args[1])
        elif args[0] == "--count":
            count = int(args[1])
        else:
            sys.exit(__doc__)
        args = args[2:]
    if len(args) != 2:
        sys.exit(__doc__)
    cases = gen(seed, count)
    with open(args[0], "w") as fc, open(args[1], "w") as fe:
        for c in cases:
            fc.write(c + "\n")
            fe.write(answer(c) + "\n")
        fc.write("\n")


if __name__ == "__main__":
    main(sys.argv)
