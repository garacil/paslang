#!/usr/bin/env python3
"""The vector words' model (P106, 1.0.125 and 1.0.126; P107, 1.0.128):
writes testdata/vectors.paslang, vecmore.paslang and vecpool.paslang and
the output they must print, worked out here lane by lane in Python,
not by the compiler. Every word runs on twelve pairs of V256 (eight from
xorshift64, four of edge bytes, the last two equal) and on their low
V128 halves; a line per word is a hash of every result byte."""
import sys, os

M64 = (1 << 64) - 1

def xorshift(seed):
    while True:
        seed ^= (seed << 13) & M64
        seed ^= seed >> 7
        seed ^= (seed << 17) & M64
        yield seed

def lanes(bs, L):
    n = L // 8
    return [int.from_bytes(bs[i:i + n], 'little') for i in range(0, len(bs), n)]

def pack(vals, L):
    n = L // 8
    return b''.join((v & ((1 << L) - 1)).to_bytes(n, 'little') for v in vals)

def sx(v, L):
    return v - (1 << L) if v >> (L - 1) else v

def lanewise(f, L):
    return lambda a, b: pack([f(x, y, L) for x, y in zip(lanes(a, L), lanes(b, L))], L)

def clampu(v, L): return max(0, min(v, (1 << L) - 1))
def clamps(v, L): return max(-(1 << (L - 1)), min(v, (1 << (L - 1)) - 1))
ONES = lambda L: (1 << L) - 1

BIN = {}
for L in (8, 16, 32, 64):
    BIN['Add%d' % L] = lanewise(lambda x, y, L: x + y, L)
    BIN['Sub%d' % L] = lanewise(lambda x, y, L: x - y, L)
for L in (8, 16):
    BIN['AddSatU%d' % L] = lanewise(lambda x, y, L: clampu(x + y, L), L)
    BIN['AddSatS%d' % L] = lanewise(lambda x, y, L: clamps(sx(x, L) + sx(y, L), L), L)
    BIN['SubSatU%d' % L] = lanewise(lambda x, y, L: clampu(x - y, L), L)
    BIN['SubSatS%d' % L] = lanewise(lambda x, y, L: clamps(sx(x, L) - sx(y, L), L), L)
    BIN['AvgU%d' % L] = lanewise(lambda x, y, L: (x + y + 1) >> 1, L)
BIN['Mul16'] = lanewise(lambda x, y, L: x * y, 16)
BIN['Mul32'] = lanewise(lambda x, y, L: x * y, 32)
for L in (8, 16, 32):
    BIN['MinU%d' % L] = lanewise(lambda x, y, L: min(x, y), L)
    BIN['MaxU%d' % L] = lanewise(lambda x, y, L: max(x, y), L)
    BIN['MinS%d' % L] = lanewise(lambda x, y, L: min(sx(x, L), sx(y, L)), L)
    BIN['MaxS%d' % L] = lanewise(lambda x, y, L: max(sx(x, L), sx(y, L)), L)
    BIN['CmpGtS%d' % L] = lanewise(lambda x, y, L: ONES(L) if sx(x, L) > sx(y, L) else 0, L)
    BIN['CmpGtU%d' % L] = lanewise(lambda x, y, L: ONES(L) if x > y else 0, L)
for L in (8, 16, 32, 64):
    BIN['CmpEq%d' % L] = lanewise(lambda x, y, L: ONES(L) if x == y else 0, L)
BIN['And'] = lanewise(lambda x, y, L: x & y, 64)
BIN['Or'] = lanewise(lambda x, y, L: x | y, 64)
BIN['Xor'] = lanewise(lambda x, y, L: x ^ y, 64)
BIN['AndNot'] = lanewise(lambda x, y, L: x & ~y, 64)

def shift(kind, L):
    def f(a, c):
        c &= M64
        out = []
        for x in lanes(a, L):
            if kind == 'Shl':
                out.append(0 if c >= L else x << c)
            elif kind == 'ShrU':
                out.append(0 if c >= L else x >> c)
            else:
                out.append(sx(x, L) >> min(c, L - 1))
        return pack(out, L)
    return f

SHIFTS = {}
for L in (16, 32, 64):
    SHIFTS['Shl%d' % L] = shift('Shl', L)
    SHIFTS['ShrU%d' % L] = shift('ShrU', L)
for L in (16, 32):
    SHIFTS['ShrS%d' % L] = shift('ShrS', L)
COUNTS = [0, 1, 3, 7, 8, 15, 16, 17, 31, 32, 33, 63, 64, 65, 200, -1]
CONSTS = [0, 5, 16, 40, 300]
SPLATS = [0, 1, -1, 127, 128, 255, 256, 65535, 65536, -129, 0x123456789ABCDEF0]

def main(tree):
    g = xorshift(88172645463325252)
    pat = [0, 1, 127, 128, 129, 254, 255, 85]
    A, B, Mk = [], [], []
    for i in range(8):
        w = [next(g) for _ in range(12)]
        A.append(b''.join(x.to_bytes(8, 'little') for x in w[0:12:3]))
        B.append(b''.join(x.to_bytes(8, 'little') for x in w[1:12:3]))
        Mk.append(b''.join(x.to_bytes(8, 'little') for x in w[2:12:3]))
    for i in range(8, 12):
        A.append(bytes(pat[(j + i) % 8] for j in range(32)))
        B.append(bytes(pat[(j * 3 + i) % 8] for j in range(32)))
        Mk.append(bytes(pat[(j * 5 + i) % 8] for j in range(32)))
    B[11] = A[11]
    out = []
    def hsh(results):
        h = 0
        for r in results:
            for byte in r:
                h = (h * 1099511628211 + byte) & M64
        return h - (1 << 64) if h >> 63 else h
    prog = []
    P = prog.append
    for name, f in BIN.items():
        res = []
        for i in range(12):
            res.append(f(A[i], B[i]))
            res.append(f(A[i][:16], B[i][:16]))
        out.append('%s %d' % (name, hsh(res)))
        P("  h := 0;\n  for i := 0 to 11 do\n  begin\n    r := V%s(a[i], b[i]);\n    Mix(@r, 32);\n"
          "    q := V%s(Lo(a[i]), Lo(b[i]));\n    Mix(@q, 16);\n  end;\n  WriteLn('%s ', h);" % (name, name, name))
    for name, f in SHIFTS.items():
        res = []
        for i in range(12):
            for c in COUNTS:
                res.append(f(A[i], c))
                res.append(f(A[i][:16], c))
        out.append('%s %d' % (name, hsh(res)))
        P("  h := 0;\n  for i := 0 to 11 do\n    for k := 0 to 15 do\n    begin\n      r := V%s(a[i], cnt[k]);\n"
          "      Mix(@r, 32);\n      q := V%s(Lo(a[i]), cnt[k]);\n      Mix(@q, 16);\n    end;\n  WriteLn('%s ', h);"
          % (name, name, name))
        res = []
        body = []
        for c in CONSTS:
            for i in range(12):
                res.append(f(A[i], c))
                res.append(f(A[i][:16], c))
            body.append("    r := V%s(a[i], %d);\n    Mix(@r, 32);\n    q := V%s(Lo(a[i]), %d);\n    Mix(@q, 16);"
                        % (name, c, name, c))
        # the program loops constants outside pairs: reorder the model to match
        res = []
        for c in CONSTS:
            for i in range(12):
                res.append(f(A[i], c))
                res.append(f(A[i][:16], c))
        out.append('%s const %d' % (name, hsh(res)))
        P("  h := 0;\n" + "\n".join(
            "  for i := 0 to 11 do\n  begin\n    r := V%s(a[i], %d);\n    Mix(@r, 32);\n"
            "    q := V%s(Lo(a[i]), %d);\n    Mix(@q, 16);\n  end;" % (name, c, name, c) for c in CONSTS)
          + "\n  WriteLn('%s const ', h);" % name)
    res = []
    for L in (8, 16, 32, 64):
        for v in SPLATS:
            res.append(pack([v] * (256 // L), L))
            res.append(pack([v] * (128 // L), L))
    out.append('Splat %d' % hsh(res))
    P("  h := 0;\n" + "\n".join(
        "  for k := 0 to 10 do\n  begin\n    r := VSplat%d(sp[k]);\n    Mix(@r, 32);\n    q := VSplat%d(sp[k]);\n"
        "    Mix(@q, 16);\n  end;" % (L, L) for L in (8, 16, 32, 64)) + "\n  WriteLn('Splat ', h);")
    res = []
    for i in range(12):
        sel = lambda m, a, b: bytes((x & y) | (~x & z) & 255 for x, y, z in zip(m, a, b))
        res.append(sel(Mk[i], A[i], B[i]))
        res.append(sel(Mk[i][:16], A[i][:16], B[i][:16]))
        res.append(bytes(~x & 255 for x in A[i]))
        res.append(bytes(~x & 255 for x in A[i][:16]))
    out.append('Select Not %d' % hsh(res))
    P("  h := 0;\n  for i := 0 to 11 do\n  begin\n    r := VSelect(m[i], a[i], b[i]);\n    Mix(@r, 32);\n"
      "    q := VSelect(Lo(m[i]), Lo(a[i]), Lo(b[i]));\n    Mix(@q, 16);\n    r := VNot(a[i]);\n    Mix(@r, 32);\n"
      "    q := VNot(Lo(a[i]));\n    Mix(@q, 16);\n  end;\n  WriteLn('Select Not ', h);")
    # the operators, compound assignment, a deep tree, parameters and results
    res = []
    for i in range(12):
        a, b = A[i], B[i]
        res.append(BIN['Xor'](a, b))
        res.append(bytes(~x & 255 for x in BIN['And'](a, b)))
        res.append(BIN['AndNot'](a, b))
        res.append(bytes(~x & 255 for x in BIN['Xor'](a, b)))
        res.append(bytes(~x & 255 for x in BIN['Or'](a, b)))
        t = BIN['Xor'](a, b)
        t = BIN['Or'](t, Mk[i])
        res.append(t)
        m16 = BIN['Mul16'](a, b)
        s = BIN['Sub16'](pack([3] * 16, 16), BIN['Xor'](a, Mk[i]))
        res.append(BIN['Add16'](m16, s))
        mx = BIN['MaxS32'](BIN['Add32'](a, b), BIN['MinU32'](a, pack([1000] * 8, 32)))
        res.append(BIN['CmpGtU16'](mx, BIN['AvgU16'](a, b)))
        res.append(BIN['Add8'](a[:16], a[:16]))
        res.append(BIN['Add8'](BIN['Sub8'](a, b), BIN['Sub8'](a, b)))
    out.append('Operators %d' % hsh(res))
    P("  h := 0;\n  for i := 0 to 11 do\n  begin\n"
      "    r := a[i] xor b[i];\n    Mix(@r, 32);\n"
      "    r := a[i] nand b[i];\n    Mix(@r, 32);\n"
      "    r := a[i] andnot b[i];\n    Mix(@r, 32);\n"
      "    r := a[i] xnor b[i];\n    Mix(@r, 32);\n"
      "    r := not (a[i] or b[i]);\n    Mix(@r, 32);\n"
      "    r := a[i];\n    r xor= b[i];\n    r or= m[i];\n    Mix(@r, 32);\n"
      "    r := VAdd16(VMul16(a[i], b[i]), VSub16(VSplat16(3), VXor(a[i], m[i])));\n    Mix(@r, 32);\n"
      "    r := VCmpGtU16(VMaxS32(VAdd32(a[i], b[i]), VMinU32(a[i], VSplat32(1000))), VAvgU16(a[i], b[i]));\n"
      "    Mix(@r, 32);\n"
      "    q := Twice(Lo(a[i]));\n    Mix(@q, 16);\n"
      "    r := Twice256(VSub8(a[i], b[i]));\n    Mix(@r, 32);\n"
      "  end;\n  WriteLn('Operators ', h);")
    head = '''program vectors;

{ The vector words of P106 (1.0.125) on V128 and V256, written by
  scripts/vecmodel.py with the output its Python model works out lane by
  lane: twelve pairs (eight from xorshift64, four of edge bytes, the
  last two equal) for every word, both widths; shift counts constant and
  variable, negative and past the lane; splats of values past the lane;
  the operators, compound assignment, a deep tree, a vector as parameter
  and result. On amd64 once with AVX2 (-cpu native) and once with -cpu base. }

var
  a, b, m: array[0..11] of V256;
  r: V256;
  q: V128;
  seed, h, i, k: Integer;
  cnt, sp: array[0..15] of Integer;

function Next: Integer;
begin
  seed := seed xor (seed shl 13);
  seed := seed xor (seed shr 7);
  seed := seed xor (seed shl 17);
  Result := seed;
end;

procedure Mix(p: Pointer; n: Integer);
var
  j: Integer;
begin
  for j := 0 to n - 1 do
    h := h * 1099511628211 + PByte(p)[j];
end;

function Lo(const v: V256): V128;
begin
  Result := (v as array[0..1] of V128)[0];
end;

function Twice(x: V128): V128;
begin
  Result := VAdd8(x, x);
end;

function Twice256(x: V256): V256;
begin
  Result := VAdd8(x, x);
end;

procedure Fill;
var
  i, j: Integer;
  pat: array[0..7] of Byte;
begin
  pat[0] := 0;
  pat[1] := 1;
  pat[2] := 127;
  pat[3] := 128;
  pat[4] := 129;
  pat[5] := 254;
  pat[6] := 255;
  pat[7] := 85;
  for i := 0 to 7 do
    for j := 0 to 3 do
    begin
      (a[i] as array[0..3] of Integer)[j] := Next;
      (b[i] as array[0..3] of Integer)[j] := Next;
      (m[i] as array[0..3] of Integer)[j] := Next;
    end;
  for i := 8 to 11 do
    for j := 0 to 31 do
    begin
      (a[i] as array[0..31] of Byte)[j] := pat[(j + i) mod 8];
      (b[i] as array[0..31] of Byte)[j] := pat[(j * 3 + i) mod 8];
      (m[i] as array[0..31] of Byte)[j] := pat[(j * 5 + i) mod 8];
    end;
  b[11] := a[11];
end;

begin
  seed := 88172645463325252;
  Fill;
'''
    head += ''.join("  cnt[%d] := %d;\n" % (i, c) for i, c in enumerate(COUNTS))
    head += ''.join("  sp[%d] := %d;\n" % (i, v) for i, v in enumerate(SPLATS))
    src = head + '\n'.join(prog) + '\nend.\n'
    open(os.path.join(tree, 'testdata/vectors.paslang'), 'w').write(src)
    open(os.path.join(tree, 'testdata/vectors.out'), 'w').write('\n'.join(out) + '\n')

import struct, math

def f32(w): return struct.unpack('<f', struct.pack('<I', w))[0]
def tof32(x):
    try:
        return struct.unpack('<I', struct.pack('<f', x))[0]
    except OverflowError:
        return 0xFF800000 if x < 0 else 0x7F800000
def f64(w): return struct.unpack('<d', struct.pack('<Q', w))[0]
def tof64(x): return struct.unpack('<Q', struct.pack('<d', x))[0]

def fdiv(a, b):
    if b == 0:
        if a == 0 or a != a:
            return float('nan')
        return math.copysign(float('inf'), a) * math.copysign(1.0, b)
    return a / b

def fsqrt(a):
    if a != a or a < 0:
        return float('nan')
    return math.sqrt(a)

FLOAT = {
    'Add': lambda a, b: a + b, 'Sub': lambda a, b: a - b, 'Mul': lambda a, b: a * b, 'Div': fdiv,
    'Min': lambda a, b: a if a < b else b, 'Max': lambda a, b: a if a > b else b,
}
FCMP = {'CmpEq': lambda a, b: a == b, 'CmpLt': lambda a, b: a < b, 'CmpLe': lambda a, b: a <= b}

def fop(f, L):
    un, to = (f32, tof32) if L == 32 else (f64, tof64)
    return lambda a, b: pack([to(f(un(x), un(y))) for x, y in zip(lanes(a, L), lanes(b, L))], L)

def fcmp(f, L):
    un = f32 if L == 32 else f64
    return lambda a, b: pack([ONES(L) if f(un(x), un(y)) else 0 for x, y in zip(lanes(a, L), lanes(b, L))], L)

def halves(f):
    """a word of whole 128-bit halves: f on each 16 bytes"""
    return lambda a, b: b''.join(f(a[k:k + 16], b[k:k + 16]) for k in range(0, len(a), 16))

def shuf(a, b):
    return bytes(a[x] if x < 16 else 0 for x in b)

def zipw(L, hi):
    def f(a, b):
        la, lb = lanes(a, L), lanes(b, L)
        n = len(la) // 2
        if hi:
            la, lb = la[n:], lb[n:]
        else:
            la, lb = la[:n], lb[:n]
        out = []
        for x, y in zip(la, lb):
            out += [x, y]
        return pack(out, L)
    return halves(f)

def packw(src, dst, unsigned):
    def f(a, b):
        lo, hi = (0, (1 << dst) - 1) if unsigned else (-(1 << (dst - 1)), (1 << (dst - 1)) - 1)
        vals = [max(lo, min(hi, sx(v, src))) for v in lanes(a, src) + lanes(b, src)]
        return pack(vals, dst)
    return halves(f)

def main2(tree):
    g = xorshift(2463534242)
    pat = [0, 1, 127, 128, 129, 254, 255, 85]
    A, B, Mk = [], [], []
    for i in range(8):
        w = [next(g) for _ in range(12)]
        A.append(b''.join(x.to_bytes(8, 'little') for x in w[0:12:3]))
        B.append(b''.join(x.to_bytes(8, 'little') for x in w[1:12:3]))
        Mk.append(bytes(x & 31 for x in b''.join(x.to_bytes(8, 'little') for x in w[2:12:3])))
    for i in range(8, 12):
        A.append(bytes(pat[(j + i) % 8] for j in range(32)))
        B.append(bytes(pat[(j * 3 + i) % 8] for j in range(32)))
        Mk.append(bytes((j * 7 + i) % 20 for j in range(32)))
    inf, nan = float('inf'), float('nan')
    A.append(pack([tof32(v) for v in [0.0, -0.0, 1.0, -1.5, inf, -inf, nan, 1e-40]], 32))
    B.append(pack([tof32(v) for v in [-0.0, 0.0, 3.0, -1.5, -inf, 1.0, 2.0, 1e-41]], 32))
    Mk.append(pack([tof32(v) for v in [2.0, -2.0, 0.5, 1e30, 3e38, -3e38, 1e-45, 16777217.0]], 32))
    A.append(pack([tof64(v) for v in [0.0, inf, -2.5, 1e-310]], 64))
    B.append(pack([tof64(v) for v in [-0.0, inf, 0.1, -1e-310]], 64))
    Mk.append(pack([tof64(v) for v in [1e300, -1e300, 3.0, -0.0]], 64))
    NP = len(A)
    out, prog = [], []
    P = prog.append
    def hsh(results):
        h = 0
        for kind, r in results:
            if kind == 'b':
                for byte in r:
                    h = (h * 1099511628211 + byte) & M64
            elif kind == 'i':
                h = (h * 1099511628211 + r) & M64
            else:
                L = 32 if kind == 'f' else 64
                for w in lanes(r, L):
                    if L == 32 and (w & 0x7F800000) == 0x7F800000 and (w & 0x7FFFFF):
                        w = 0x7FC00000
                    if L == 64 and (w & 0x7FF0000000000000) == 0x7FF0000000000000 and (w & 0xFFFFFFFFFFFFF):
                        w = 0x7FF8000000000000
                    h = (h * 1099511628211 + w) & M64
        return h - (1 << 64) if h >> 63 else h
    mixr = {'b': 'Mix(@r, 32)', 'f': 'MixF(@r, 8)', 'd': 'MixD(@r, 4)'}
    mixq = {'b': 'Mix(@q, 16)', 'f': 'MixF(@q, 4)', 'd': 'MixD(@q, 2)'}
    def binword(name, f, kind, second='b'):
        res = []
        for i in range(NP):
            y = B[i] if second == 'b' else Mk[i]
            res.append((kind, f(A[i], y)))
            res.append((kind, f(A[i][:16], y[:16])))
        arr = 'b' if second == 'b' else 'm'
        label = name if second == 'b' else name + ' m'
        out.append('%s %d' % (label, hsh(res)))
        P("  h := 0;\n  for i := 0 to %d do\n  begin\n    r := V%s(a[i], %s[i]);\n    %s;\n"
          "    q := V%s(Lo(a[i]), Lo(%s[i]));\n    %s;\n  end;\n  WriteLn('%s ', h);"
          % (NP - 1, name, arr, mixr[kind], name, arr, mixq[kind], label))
    binword('Shuffle8', halves(shuf), 'b', 'm')
    for L in (8, 16, 32, 64):
        binword('ZipLo%d' % L, zipw(L, False), 'b')
        binword('ZipHi%d' % L, zipw(L, True), 'b')
    binword('PackU16', packw(16, 8, True), 'b')
    binword('PackS16', packw(16, 8, False), 'b')
    binword('PackS32', packw(32, 16, False), 'b')
    for L, k in ((32, 'f'), (64, 'd')):
        for n, f in FLOAT.items():
            binword('%sF%d' % (n, L), fop(f, L), k)
            binword('%sF%d' % (n, L), fop(f, L), k, 'm')
        for n, f in FCMP.items():
            binword('%sF%d' % (n, L), fcmp(f, L), 'b')
    # unary words
    for name, f, kind in (('SqrtF32', lambda a: pack([tof32(fsqrt(f32(w))) for w in lanes(a, 32)], 32), 'f'),
                          ('SqrtF64', lambda a: pack([tof64(fsqrt(f64(w))) for w in lanes(a, 64)], 64), 'd'),
                          ('CvtS32F32', lambda a: pack([tof32(float(sx(w, 32))) for w in lanes(a, 32)], 32), 'f')):
        res = []
        for i in range(NP):
            for src in (A[i], Mk[i]):
                res.append((kind, f(src)))
                res.append((kind, f(src[:16])))
        out.append('%s %d' % (name, hsh(res)))
        P("  h := 0;\n  for i := 0 to %d do\n  begin\n    r := V%s(a[i]);\n    %s;\n    q := V%s(Lo(a[i]));\n    %s;\n"
          "    r := V%s(m[i]);\n    %s;\n    q := V%s(Lo(m[i]));\n    %s;\n  end;\n  WriteLn('%s ', h);"
          % (NP - 1, name, mixr[kind], name, mixq[kind], name, mixr[kind], name, mixq[kind], name))
    # splats of reals
    S32 = [0.0, -0.0, 1.5, -3.25, 0.1, 1e30, 3e38, -1e-40]
    S64 = [0.1, -2.0, 1e300, -0.0, 5e-324]
    res = []
    for v in S32:
        res.append(('f', pack([tof32(v)] * 8, 32)))
        res.append(('f', pack([tof32(v)] * 4, 32)))
    for v in S64:
        res.append(('d', pack([tof64(v)] * 4, 64)))
        res.append(('d', pack([tof64(v)] * 2, 64)))
    out.append('SplatF %d' % hsh(res))
    lines = ["  h := 0;"]
    for v in S32:
        lines.append("  r := VSplatF32(%r);\n  MixF(@r, 8);\n  q := VSplatF32(%r);\n  MixF(@q, 4);" % (v, v))
    for v in S64:
        lines.append("  r := VSplatF64(%r);\n  MixD(@r, 4);\n  q := VSplatF64(%r);\n  MixD(@q, 2);" % (v, v))
    lines.append("  WriteLn('SplatF ', h);")
    P('\n'.join(lines))
    # reductions
    RED = {
        'MoveMask8': lambda a: sum(((x >> 7) & 1) << k for k, x in enumerate(a)),
        'SumU8': lambda a: sum(a),
        'SumS32': lambda a: sum(sx(w, 32) for w in lanes(a, 32)),
        'Sum64': lambda a: sum(lanes(a, 64)) & M64,
    }
    for name, f in RED.items():
        res = []
        for i in range(NP):
            for src in (A[i], B[i]):
                v = f(src) & M64
                res.append(('i', v))
                res.append(('i', f(src[:16]) & M64))
        out.append('%s %d' % (name, hsh(res)))
        P("  h := 0;\n  for i := 0 to %d do\n  begin\n    h := h * 1099511628211 + V%s(a[i]);\n"
          "    h := h * 1099511628211 + V%s(Lo(a[i]));\n    h := h * 1099511628211 + V%s(b[i]);\n"
          "    h := h * 1099511628211 + V%s(Lo(b[i]));\n  end;\n  WriteLn('%s ', h);" % (NP - 1, name, name, name, name, name))
    # a reduction of a tree, and a tree that shuffles inside a V256 statement
    res = []
    for i in range(NP):
        m = BIN['CmpEq8'](A[i], B[i])
        res.append(('i', RED['MoveMask8'](m)))
        res.append(('i', RED['SumU8'](BIN['MaxU8'](A[i], B[i]))))
        res.append(('b', halves(shuf)(BIN['Add8'](A[i], B[i]), Mk[i])))
    out.append('Trees %d' % hsh(res))
    P("  h := 0;\n  for i := 0 to %d do\n  begin\n    h := h * 1099511628211 + VMoveMask8(VCmpEq8(a[i], b[i]));\n"
      "    h := h * 1099511628211 + VSumU8(VMaxU8(a[i], b[i]));\n    r := VShuffle8(VAdd8(a[i], b[i]), m[i]);\n"
      "    Mix(@r, 32);\n  end;\n  WriteLn('Trees ', h);" % (NP - 1))
    head = """program vecmore;

{ The vector words of P106 1.0.126, written by scripts/vecmodel.py with
  the output its Python model works out: VShuffle8, VZipLo and VZipHi,
  the packs, the lanes of Single and Double (add, sub, mul, div, min and
  max as x86 has them, compares, sqrt), VCvtS32F32, VSplatF32/F64 and
  the reductions VMoveMask8, VSumU8, VSumS32 and VSum64; fourteen pairs
  (eight random, four of edge bytes, two of edge reals: signed zeros,
  infinities, a NaN, subnormals). A NaN's bits may differ between the
  machines, so the hash reads every NaN as one. On amd64 with AVX2, with
  -cpu base, and on arm64. }

var
  a, b, m: array[0..%d] of V256;
  r: V256;
  q: V128;
  h, i: Integer;

procedure Mix(p: Pointer; n: Integer);
var
  j: Integer;
begin
  for j := 0 to n - 1 do
    h := h * 1099511628211 + PByte(p)[j];
end;

procedure MixF(p: Pointer; n: Integer);
var
  j, w: Integer;
begin
  for j := 0 to n - 1 do
  begin
    w := PUInt32(p)[j];
    if ((w and $7F800000) = $7F800000) and ((w and $7FFFFF) <> 0) then
      w := $7FC00000;
    h := h * 1099511628211 + w;
  end;
end;

procedure MixD(p: Pointer; n: Integer);
var
  j, w: Integer;
begin
  for j := 0 to n - 1 do
  begin
    w := PInteger(p)[j];
    if ((w and $7FF0000000000000) = $7FF0000000000000) and ((w and $FFFFFFFFFFFFF) <> 0) then
      w := $7FF8000000000000;
    h := h * 1099511628211 + w;
  end;
end;

function Lo(const v: V256): V128;
begin
  Result := (v as array[0..1] of V128)[0];
end;

begin
""" % (NP - 1)
    for i in range(NP):
        for nm, arr in (('a', A), ('b', B), ('m', Mk)):
            for j in range(4):
                v = int.from_bytes(arr[i][8 * j:8 * j + 8], 'little')
                if v >> 63:
                    v -= 1 << 64
                head += "  (%s[%d] as array[0..3] of Integer)[%d] := %d;\n" % (nm, i, j, v)
    src = head + '\n'.join(prog) + '\nend.\n'
    open(os.path.join(tree, 'testdata/vecmore.paslang'), 'w').write(src)
    open(os.path.join(tree, 'testdata/vecmore.out'), 'w').write('\n'.join(out) + '\n')

def main3(tree):
    """testdata/vecpool (P107, 1.0.128): vectors kept in registers across
    the statements of a loop, in routines the model mirrors."""
    g = xorshift(7777777)
    buf = b''.join(next(g).to_bytes(8, 'little') for _ in range(1024))
    fl = [((i * 7) % 23) - 11 for i in range(1024)]
    flb = pack([tof32(float(v)) for v in fl], 32)
    def fnv(bs):
        h = 0
        for b in bs:
            h = (h * 1099511628211 + b) & M64
        return h
    def s64(h):
        return h - (1 << 64) if h >> 63 else h
    def comb(*hs):
        r = 0
        for h in hs:
            r = (r * 31 + h) & M64
        return r
    V = lambda k: buf[16 * k:16 * k + 16]
    W = lambda k: buf[32 * k:32 * k + 32]
    splat = lambda v, L, n: pack([v] * (n * 8 // L), L)
    out = []
    # 1 Dot
    acc, acc2 = splat(0, 32, 16), splat(7, 32, 16)
    for i in range(512):
        x = V(i)
        acc = BIN['Add32'](acc, BIN['Mul32'](x, x))
        acc2 = BIN['Xor'](acc2, SHIFTS['ShrU32'](acc, 3))
    out.append(s64(comb(fnv(acc), fnv(acc2))))
    # 2 Wide
    m, s = splat(0, 8, 32), splat(0, 16, 32)
    z = splat(0, 8, 32)
    for i in range(256):
        x = W(i)
        m = BIN['MaxU8'](m, x)
        s = BIN['Add16'](s, zipw(8, False)(x, z))
        s = BIN['Add16'](s, zipw(8, True)(x, z))
    out.append(s64(comb(fnv(m), fnv(s))))
    # 3 FDot
    a, b = pack([tof32(0.0)] * 8, 32), pack([tof32(1.0)] * 8, 32)
    half = pack([tof32(0.5)] * 8, 32)
    for i in range(128):
        x = flb[32 * i:32 * i + 32]
        a = fop(FLOAT['Add'], 32)(a, fop(FLOAT['Mul'], 32)(x, half))
        b = fop(FLOAT['Max'], 32)(b, x)
    out.append(s64(comb(fnv(a), fnv(b))))
    # 4 CountBig
    lim = splat(200, 8, 16)
    c = sv = 0
    for i in range(512):
        mm = BIN['CmpGtU8'](V(i), lim)
        c += bin(sum(((x >> 7) & 1) << k for k, x in enumerate(mm))).count('1')
        sv += sum(V(i))
    out.append(c * 100000 + sv)
    # 5 Declined
    acc = splat(1, 8, 16)
    for i in range(512):
        acc = bytearray(BIN['Add8'](acc, V(i)))
        acc[i & 15] = i & 255
        acc = bytes(acc)
    out.append(s64(fnv(acc)))
    # 6 Nested
    a, b = splat(1, 16, 16), splat(-1, 16, 16)
    mk = splat(0, 16, 16)
    for i in range(8):
        for j in range(64):
            k = (i + j) & 15
            mk = BIN['CmpGtS16'](V(j), a)
            t1 = BIN['Add16'](a, SHIFTS['Shl16'](V(j), k))
            t2 = BIN['Sub16'](a, b)
            a = bytes((x & y) | (~x & z) & 255 for x, y, z in zip(mk, t1, t2))
            b = BIN['AddSatS16'](b, SHIFTS['ShrS16'](a, 2))
    out.append(s64(comb(fnv(a), fnv(b), fnv(mk))))
    # 7 Deep
    vs = [splat(k + 1, 8, 16) for k in range(8)]
    for i in range(256):
        A, B, C, D, E, F, G, H = vs
        A = BIN['Add8'](A, BIN['Add8'](B, BIN['Add8'](C, BIN['Add8'](D, BIN['Xor'](E, V(i))))))
        B = BIN['Sub8'](B, A)
        C = BIN['Xor'](C, SHIFTS['Shl16'](B, 1))
        D = BIN['AvgU8'](D, C)
        E = BIN['MaxU8'](E, D)
        F = BIN['Add16'](F, E)
        G = BIN['Xor'](G, F)
        H = BIN['Sub8'](H, G)
        vs = [A, B, C, D, E, F, G, H]
    out.append(s64(comb(*[fnv(v) for v in vs])))
    # 8 a global in the main program
    gacc = splat(3, 8, 16)
    for i in range(512):
        gacc = BIN['AvgU8'](gacc, V(i))
    out.append(s64(fnv(gacc)))
    # 9 workers, while the main routine allocates
    R = 30000
    tot = [0] * 8
    xs = [0] * 8
    for i in range(128):
        for k, v in enumerate(lanes(W(i), 32)):
            tot[k] = (tot[k] + v) & 0xFFFFFFFF
            xs[k] ^= (v << 1) & 0xFFFFFFFF
    for wid in range(4):
        acc = pack([(wid + R * tv) & 0xFFFFFFFF for tv in tot], 32)
        acc2 = pack([(wid * 7) ^ (xv if R % 2 else 0) for xv in xs], 32)
        out.append('worker %d %d %d' % (wid, s64(comb(fnv(acc), fnv(acc2))), R * 128))
    prog = """program vecpool;

{ Vectors kept in registers across the statements of a loop (P107,
  1.0.128), written by scripts/vecmodel.py with the output its model
  works out: V128 and V256 accumulators, loads copied to a variable,
  floats, reductions beside promoted integers, a variable used through a
  view (not promoted), nested loops with a select and a shift by a
  variable, a tree deep enough to leave only some variables a register,
  a global in the main program, and four routines running such loops
  while the main one allocates, so the collector stops them at their
  loops' checks, which spill and reload the registers. }

uses
  paslib;

type
  PV1 = ^V128;
  PV2 = ^V256;

var
  buf: array[0..8191] of Byte;
  fl: array[0..1023] of Single;
  seed, i: Integer;
  gacc: V128;
  gp: PV1;
  res: array[0..3] of Integer;
  cnts: array[0..3] of Integer;
  done: chan of Integer;
  junk: string;

function Next: Integer;
begin
  seed := seed xor (seed shl 13);
  seed := seed xor (seed shr 7);
  seed := seed xor (seed shl 17);
  Result := seed;
end;

function H128(v: V128): Integer;
var
  j: Integer;
begin
  Result := 0;
  for j := 0 to 15 do
    Result := Result * 1099511628211 + (v as array[0..15] of Byte)[j];
end;

function H256(v: V256): Integer;
var
  j: Integer;
begin
  Result := 0;
  for j := 0 to 31 do
    Result := Result * 1099511628211 + (v as array[0..31] of Byte)[j];
end;

function Dot(n: Integer): Integer;
var
  acc, acc2, x: V128;
  p: PV1;
  i: Integer;
begin
  p := PV1(@buf[0]);
  acc := VSplat32(0);
  acc2 := VSplat32(7);
  for i := 0 to n - 1 do
  begin
    x := p[i];
    acc := VAdd32(acc, VMul32(x, x));
    acc2 := VXor(acc2, VShrU32(acc, 3));
  end;
  Result := H128(acc) * 31 + H128(acc2);
end;

function Wide(n: Integer): Integer;
var
  m, s, x: V256;
  q: PV2;
  i: Integer;
begin
  q := PV2(@buf[0]);
  m := VSplat8(0);
  s := VSplat16(0);
  for i := 0 to n - 1 do
  begin
    x := q[i];
    m := VMaxU8(m, x);
    s := VAdd16(s, VZipLo8(x, VSplat8(0)));
    s := VAdd16(s, VZipHi8(x, VSplat8(0)));
  end;
  Result := H256(m) * 31 + H256(s);
end;

function FDot(n: Integer): Integer;
var
  a, b: V256;
  f: PV2;
  i: Integer;
begin
  f := PV2(@fl[0]);
  a := VSplatF32(0.0);
  b := VSplatF32(1.0);
  for i := 0 to n - 1 do
  begin
    a := VAddF32(a, VMulF32(f[i], VSplatF32(0.5)));
    b := VMaxF32(b, f[i]);
  end;
  Result := H256(a) * 31 + H256(b);
end;

function CountBig(n: Integer): Integer;
var
  lim: V128;
  p: PV1;
  i, c, s: Integer;
begin
  p := PV1(@buf[0]);
  lim := VSplat8(200);
  c := 0;
  s := 0;
  for i := 0 to n - 1 do
  begin
    c := c + PopCount(VMoveMask8(VCmpGtU8(p[i], lim)));
    s := s + VSumU8(p[i]);
  end;
  Result := c * 100000 + s;
end;

function Declined(n: Integer): Integer;
var
  acc: V128;
  p: PV1;
  i: Integer;
begin
  p := PV1(@buf[0]);
  acc := VSplat8(1);
  for i := 0 to n - 1 do
  begin
    acc := VAdd8(acc, p[i]);
    (acc as array[0..15] of Byte)[i and 15] := Byte(i);
  end;
  Result := H128(acc);
end;

function Nested(n: Integer): Integer;
var
  a, b, m: V128;
  p: PV1;
  i, j, k: Integer;
begin
  p := PV1(@buf[0]);
  a := VSplat16(1);
  b := VSplat16(-1);
  m := VSplat16(0);
  for i := 0 to 7 do
    for j := 0 to n - 1 do
    begin
      k := (i + j) and 15;
      m := VCmpGtS16(p[j], a);
      a := VSelect(m, VAdd16(a, VShl16(p[j], k)), VSub16(a, b));
      b := VAddSatS16(b, VShrS16(a, 2));
    end;
  Result := (H128(a) * 31 + H128(b)) * 31 + H128(m);
end;

function Deep(n: Integer): Integer;
var
  a, b, c, d, e, f, g, h: V128;
  p: PV1;
  i: Integer;
begin
  p := PV1(@buf[0]);
  a := VSplat8(1);
  b := VSplat8(2);
  c := VSplat8(3);
  d := VSplat8(4);
  e := VSplat8(5);
  f := VSplat8(6);
  g := VSplat8(7);
  h := VSplat8(8);
  for i := 0 to n - 1 do
  begin
    a := VAdd8(a, VAdd8(b, VAdd8(c, VAdd8(d, VXor(e, p[i])))));
    b := VSub8(b, a);
    c := VXor(c, VShl16(b, 1));
    d := VAvgU8(d, c);
    e := VMaxU8(e, d);
    f := VAdd16(f, e);
    g := VXor(g, f);
    h := VSub8(h, g);
  end;
  Result := H128(a);
  Result := Result * 31 + H128(b);
  Result := Result * 31 + H128(c);
  Result := Result * 31 + H128(d);
  Result := Result * 31 + H128(e);
  Result := Result * 31 + H128(f);
  Result := Result * 31 + H128(g);
  Result := Result * 31 + H128(h);
end;

procedure Worker(id: Integer);
var
  acc, acc2: V256;
  q: PV2;
  r, i, c: Integer;
begin
  q := PV2(@buf[0]);
  acc := VSplat32(id);
  acc2 := VSplat32(id * 7);
  c := 0;
  for r := 1 to %d do
    for i := 0 to 127 do
    begin
      acc := VAdd32(acc, q[i]);
      acc2 := VXor(acc2, VShl32(q[i], 1));
      c := c + 1;
    end;
  res[id] := H256(acc) * 31 + H256(acc2);
  cnts[id] := c;
  Send(done, 1);
end;

begin
  seed := 7777777;
  for i := 0 to 1023 do
    (buf as array[0..1023] of Integer)[i] := Next;
  for i := 0 to 1023 do
    fl[i] := ((i * 7) mod 23) - 11;
  WriteLn('Dot ', Dot(512));
  WriteLn('Wide ', Wide(256));
  WriteLn('FDot ', FDot(128));
  WriteLn('CountBig ', CountBig(512));
  WriteLn('Declined ', Declined(512));
  WriteLn('Nested ', Nested(64));
  WriteLn('Deep ', Deep(256));
  gp := PV1(@buf[0]);
  gacc := VSplat8(3);
  for i := 0 to 511 do
    gacc := VAvgU8(gacc, gp[i]);
  WriteLn('Global ', H128(gacc));
  done := MakeChan(4);
  for i := 0 to 3 do
    pas Worker(i);
  for i := 0 to 200000 do
    junk := 'x' + IntToStr(i);
  for i := 0 to 3 do
    seed := seed + Recv(done);
  for i := 0 to 3 do
    WriteLn('worker ', i, ' ', res[i], ' ', cnts[i]);
end.
""" % R
    names = ['Dot', 'Wide', 'FDot', 'CountBig', 'Declined', 'Nested', 'Deep', 'Global']
    lines = ['%s %d' % (n, v) for n, v in zip(names, out[:8])] + out[8:]
    open(os.path.join(tree, 'testdata/vecpool.paslang'), 'w').write(prog)
    open(os.path.join(tree, 'testdata/vecpool.out'), 'w').write('\n'.join(lines) + '\n')

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
    main2(sys.argv[1] if len(sys.argv) > 1 else '.')
    main3(sys.argv[1] if len(sys.argv) > 1 else '.')
