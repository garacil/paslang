#!/usr/bin/env python3
"""Writes testdata/flatelen.paslang and testdata/flatelen.out (P530): the Huffman
codes the deflater builds for 4000 tables of frequencies of every shape (a few
frequencies of 1 beside one of 100000, spread over 22 powers of two, growing by half
at each symbol), for the three alphabets of a block (the 19 code lengths limited to
7 bits, the 30 distances and the 286 literals and lengths limited to 15). Each code
must be whole (the sum of 2^-length is exactly 1), no longer than its limit, and
every symbol with a frequency must have a length; the program says how many cases
fail that and the sum of frequency * length over all of them, which is worked out
here by the same algorithm in Python (the nodes made in order of weight, the leaves
past the limit brought back as zlib's trees.c does) and not by the compiler.

usage: gen_flatelen.py [--check]    --check writes nothing and fails when the two
files in testdata are not what this script writes
"""
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata', 'flatelen')
CHECK = sys.argv[1:] == ['--check']
MASK = (1 << 64) - 1
CASES = 4000


def emit(path, text):
    if CHECK:
        if open(path).read() != text:
            sys.exit(path + ' is not what scripts/gen_flatelen.py writes')
    else:
        open(path, 'w').write(text)


def s64(x):
    x &= MASK
    return x - (1 << 64) if x >> 63 else x


class Rng:
    def __init__(self, seed):
        self.s = seed

    def below(self, m):
        self.s = s64(self.s * 6364136223846793005 + 1442695040888963407)
        return ((self.s & MASK) >> 33) % m


TABLE = [0, 0, 1, 1, 2, 3, 5, 100000]


def tables(rng):
    n = [19, 19, 30, 286, 30][rng.below(5)]
    kind = rng.below(3)
    freq = []
    a = 1
    for i in range(n):
        if kind == 0:
            f = 0 if rng.below(5) == 0 else TABLE[rng.below(8)]
        elif kind == 1:
            f = 0 if rng.below(10) == 0 else 1 << rng.below(22)
        else:
            f = 0 if rng.below(20) == 0 else a
            a = min(a + a // 2 + 1, 1000000000)
        freq.append(f)
    return n, freq


def lengths(freq, mb):
    """the code BuildCodes makes: None if fewer than two symbols have a frequency"""
    syms = sorted((f, i) for i, f in enumerate(freq) if f > 0)
    cnt = len(syms)
    if cnt < 2:
        return None
    w = [s[0] for s in syms] + [0] * cnt
    par = [0] * (2 * cnt)
    a, b, ni = 0, cnt, cnt
    for _ in range(cnt - 1):
        if a < cnt and (b >= ni or w[a] <= w[b]):
            x = a
            a += 1
        else:
            x = b
            b += 1
        if a < cnt and (b >= ni or w[a] <= w[b]):
            y = a
            a += 1
        else:
            y = b
            b += 1
        par[x] = ni
        par[y] = ni
        w[ni] = w[x] + w[y]
        ni += 1
    depth = [0] * (2 * cnt)
    for x in range(ni - 2, -1, -1):
        depth[x] = depth[par[x]] + 1
    bl = [0] * 17
    overflow = 0
    for i in range(cnt):
        d = depth[i]
        if d > mb:
            d = mb
            overflow += 1
        bl[d] += 1
    for x in range(cnt, ni - 1):
        if depth[x] > mb:
            overflow += 1
    while overflow > 0:
        bits = mb - 1
        while bl[bits] == 0:
            bits -= 1
        bl[bits] -= 1
        bl[bits + 1] += 2
        bl[mb] -= 1
        overflow -= 2
    ln = [0] * len(freq)
    pos = 0
    for bits in range(mb, 0, -1):
        for _ in range(bl[bits]):
            ln[syms[pos][1]] = bits
            pos += 1
    return ln


def expected():
    rng = Rng(530)
    done = skipped = bad = 0
    cost = 0
    for _ in range(CASES):
        n, freq = tables(rng)
        mb = 7 if n == 19 else 15
        ln = lengths(freq, mb)
        if ln is None:
            skipped += 1
            continue
        done += 1
        kraft = sum(1 << (mb - l) for l in ln if l > 0)
        if kraft != 1 << mb or any(l > mb for l in ln) or any(f > 0 and l == 0 for f, l in zip(freq, ln)):
            bad += 1
        cost += sum(f * l for f, l in zip(freq, ln))
    return 'cases %d skipped %d bad %d cost %d\n' % (done, skipped, bad, cost)


PROGRAM = '''program flatelen;

{ The Huffman codes of the deflater (P530) for 4000 tables of frequencies of
  every shape, for the alphabets of a block: each code whole, within its
  limit, a length for every symbol that has a frequency; the counts and the
  sum of frequency * length are the ones scripts/gen_flatelen.py works out. }

uses
  pasflate;

var
  d: TDeflater;
  freq, f2, lng, code: array[0..299] of Integer;
  tab: array[0..7] of Integer;
  seed: Int64;
  c, i, n, mb, kind, nz, a, f, done, skipped, bad: Integer;
  kraft, cost: Int64;
  fail: Boolean;

function Rnd(m: Integer): Integer;
begin
  seed := seed * 6364136223846793005 + 1442695040888963407;
  Result := Integer((seed shr 33) mod m);
end;

begin
  tab[0] := 0; tab[1] := 0; tab[2] := 1; tab[3] := 1;
  tab[4] := 2; tab[5] := 3; tab[6] := 5; tab[7] := 100000;
  d := TDeflater.Create(0, 6);
  seed := 530;
  done := 0;
  skipped := 0;
  bad := 0;
  cost := 0;
  for c := 1 to 4000 do
  begin
    case Rnd(5) of
      0, 1: n := 19;
      2, 4: n := 30;
    else
      n := 286;
    end;
    kind := Rnd(3);
    a := 1;
    nz := 0;
    for i := 0 to n - 1 do
    begin
      case kind of
        0:
          if Rnd(5) = 0 then
            f := 0
          else
            f := tab[Rnd(8)];
        1:
          if Rnd(10) = 0 then
            f := 0
          else
            f := 1 shl Rnd(22);
      else
        begin
          if Rnd(20) = 0 then
            f := 0
          else
            f := a;
          a := a + a div 2 + 1;
          if a > 1000000000 then
            a := 1000000000;
        end;
      end;
      freq[i] := f;
      if f > 0 then
        nz := nz + 1;
    end;
    if nz < 2 then
    begin
      skipped := skipped + 1;
      Continue;
    end;
    done := done + 1;
    if n = 19 then
      mb := 7
    else
      mb := 15;
    for i := 0 to n - 1 do
      f2[i] := freq[i];
    d.BuildCodes(@f2[0], n, mb, @lng[0], @code[0]);
    kraft := 0;
    fail := False;
    for i := 0 to n - 1 do
    begin
      if lng[i] > mb then
        fail := True;
      if (freq[i] > 0) and (lng[i] = 0) then
        fail := True;
      if lng[i] > 0 then
        kraft := kraft + (Int64(1) shl (mb - lng[i]));
      cost := cost + Int64(freq[i]) * lng[i];
    end;
    if kraft <> (Int64(1) shl mb) then
      fail := True;
    if fail then
      bad := bad + 1;
  end;
  WriteLn('cases ', done, ' skipped ', skipped, ' bad ', bad, ' cost ', cost);
end.
'''

emit(OUT + '.paslang', PROGRAM)
emit(OUT + '.out', expected())
