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

"""The rotation and shift words of P108 (1.0.129, 1.0.130), modelled
exactly, and testdata/rotwords.paslang with its .out: every word on every integer width
(signed and unsigned), with a count that varies and with constant counts,
in an expression and in place (a local, a global, a register a loop keeps
it in), the funnels, reals and Char, untyped constants, Carry kept across
calls and deep recursion, a routine's own Carry, and a CRC-8 and a 256-bit
shift written with Carry; and testdata/rotmem (1.0.130): every word on
byte arrays of 1 to 33 bytes, a record, a Quad, V128, V256, strings and
slices, with every kind of count, the funnels, literals and in place.

Run: python3 scripts/rotmodel.py  (writes the four files)."""

import os
import struct

WORDS = ['RotateLeft', 'RotateRight',
         'RotateLeftToCarry', 'RotateRightToCarry', 'RotateLeftThroughCarry',
         'RotateRightThroughCarry', 'ShiftLeft', 'ShiftRight', 'ShiftRightSigned',
         'ShiftLeftToCarry', 'ShiftRightToCarry', 'ShiftRightSignedToCarry']

TYPES = [('Byte', 8, False), ('Int8', 8, True), ('Word', 16, False), ('Int16', 16, True),
         ('UInt32', 32, False), ('Int32', 32, True), ('Integer', 64, True)]

COUNTS = [-(1 << 62), -5, -1, 0, 1, 2, 3, 7, 8, 9, 15, 16, 17, 31, 32, 33, 63, 64, 65,
          127, 128, 129, 1000, 1 << 40]


def sgn(v, n):
    v &= (1 << n) - 1
    return v - (1 << n) if v >> (n - 1) else v


def show(v, n, signed):
    return str(sgn(v, n)) if signed else str(v & ((1 << n) - 1))


def rot(word, n, v, c, k):
    """The value (n bits, unsigned) and Carry after word(v, k)."""
    mask = (1 << n) - 1
    v &= mask
    if word in ('RotateLeft', 'RotateRight') and n > 0:
        # rol and ror: a negative count turns the other way (1.0.147)
        s = k % n if word == 'RotateLeft' else (-k) % n
        return ((v << s) | (v >> (n - s))) & mask, c
    if k <= 0:
        return v, c
    if n == 0:
        # no bits: a shift to Carry has run out of them
        return 0, (0 if word in ('ShiftLeftToCarry', 'ShiftRightToCarry', 'ShiftRightSignedToCarry') else c)
    if word == 'RotateLeft':
        s = k % n
        return ((v << s) | (v >> (n - s))) & mask, c
    if word == 'RotateRight':
        s = k % n
        return ((v >> s) | (v << (n - s))) & mask, c
    if word == 'RotateLeftToCarry':
        s = k % n
        r = ((v << s) | (v >> (n - s))) & mask
        return r, r & 1
    if word == 'RotateRightToCarry':
        s = k % n
        r = ((v >> s) | (v << (n - s))) & mask
        return r, (r >> (n - 1)) & 1
    if word in ('RotateLeftThroughCarry', 'RotateRightThroughCarry'):
        m = n + 1
        s = k % m
        if word == 'RotateRightThroughCarry':
            s = (m - s) % m
        ring = (c << n) | v
        ring = ((ring << s) | (ring >> (m - s))) & ((1 << m) - 1)
        return ring & mask, ring >> n
    if word == 'ShiftLeft':
        return (v << k) & mask if k < n else 0, c
    if word == 'ShiftRight':
        return v >> k if k < n else 0, c
    if word == 'ShiftRightSigned':
        return (sgn(v, n) >> min(k, n)) & mask, c
    if word == 'ShiftLeftToCarry':
        if k > n:
            return 0, 0
        return (v << k) & mask, (v >> (n - k)) & 1
    if word == 'ShiftRightToCarry':
        if k > n:
            return 0, 0
        return v >> k, (v >> (k - 1)) & 1
    if word == 'ShiftRightSignedToCarry':
        m = min(k, n)
        s = sgn(v, n)
        return (s >> m) & mask, (s >> (m - 1)) & 1
    raise ValueError(word)


def funnel(left, n, hi, lo, k):
    if n == 0:
        return 0
    mask = (1 << n) - 1
    hi &= mask
    lo &= mask
    if k <= 0:
        return hi if left else lo
    if k >= 2 * n:
        return 0
    x = (hi << n) | lo
    return ((x << k) >> n) & mask if left else (x >> k) & mask


def values(n):
    """Three values of n bits: bits of both halves with the top one set,
    the lowest bit alone, the top bit alone."""
    pat = int('10110101' * (n // 8), 2)
    return [pat, 1, 1 << (n - 1)]


def lit(v, n, signed):
    return show(v, n, signed)


def const_counts(n):
    out = []
    for k in [-1, 0, 1, 2, 5, n - 1, n, n + 1, 2 * n - 1, 2 * n, 2 * n + 1, 64, 65, 100, 128, 129]:
        if k not in out:
            out.append(k)
    return out


def f64bits(d):
    return struct.unpack('<Q', struct.pack('<d', d))[0]


def f32bits(f):
    return struct.unpack('<I', struct.pack('<f', f))[0]


def main():
    src = []
    out = []
    w = src.append
    w('program rotwords;')
    w('')
    w('uses paslib;')
    w('')
    w('{ Generated by scripts/rotmodel.py (P108, 1.0.129): the rotation and')
    w('  shift words and Carry on every integer width, against an exact model. }')
    w('')
    w('var')
    w('  cnt: array[0..%d] of Integer;' % (len(COUNTS) - 1))
    for t, n, s in TYPES:
        w('  g%s: %s;' % (t, t))
    w('  done: chan of Integer;')
    w('  childSaw: Boolean;')
    w('')
    # a count that varies
    for t, n, s in TYPES:
        for word in WORDS:
            w('procedure V%s%s(v: %s);' % (t, word, t))
            w('var')
            w('  j, c: Integer;')
            w('  x: %s;' % t)
            w('begin')
            w('  for c := 0 to 1 do')
            w('  begin')
            w("    Write('%s %s ', v, ' ', c, ':');" % (word, t))
            w('    for j := 0 to High(cnt) do')
            w('    begin')
            w('      Carry := c = 1;')
            w('      x := %s(v, cnt[j]);' % word)
            w("      Write(' ', x, '/', Carry);")
            w('    end;')
            w('    WriteLn;')
            w('  end;')
            w('end;')
            w('')
        w('procedure F%s(hi, lo: %s);' % (t, t))
        w('var')
        w('  j: Integer;')
        w('begin')
        for d in ('FunnelLeft', 'FunnelRight'):
            w("  Write('%s %s ', hi, ' ', lo, ':');" % (d, t))
            w('  for j := 0 to High(cnt) do')
            w("    Write(' ', %s(hi, lo, cnt[j]));" % d)
            w('  WriteLn;')
            parts = []
            for k in const_counts(n):
                parts.append('%s(hi, lo, %d)' % (d, k))
            parts.append('%s(hi, lo)' % d)
            w("  WriteLn('%s %s const', %s);" % (d, t, ', '.join("' ', " + p for p in parts)))
        w('end;')
        w('')
    # constant counts, in an expression and in place
    for t, n, s in TYPES:
        w('procedure K%s;' % t)
        w('var')
        w('  x: %s;' % t)
        w('begin')
        for word in WORDS:
            for vi, v in enumerate(values(n)[:2]):
                for ki, k in enumerate(const_counts(n)):
                    c = (ki + vi) & 1
                    w('  x := %s;' % lit(v, n, s))
                    w('  Carry := %s;' % ('True' if c else 'False'))
                    w("  Write('%s %s %d: ', %s(x, %d), ' ', Carry);" % (word, t, k, word, k))
                    r, rc = rot(word, n, v, c, k)
                    line = '%s %s %d: %s %s' % (word, t, k, show(r, n, s), rc)
                    # in place: a local, or the global on odd counts
                    place = 'x' if ki % 2 == 0 else 'g' + t
                    w('  %s := %s;' % (place, lit(v, n, s)))
                    w('  Carry := %s;' % ('False' if c else 'True'))
                    w('  %s := %s(%s, %d);' % (place, word, place, k))
                    w("  WriteLn(' ', %s, ' ', Carry);" % place)
                    r2, rc2 = rot(word, n, v, 1 - c, k)
                    out_line = '%s %s %s' % (line, show(r2, n, s), rc2)
                    KOUT.append(out_line)
            # the count left out is 1
            v = values(n)[0]
            w('  x := %s;' % lit(v, n, s))
            w('  Carry := True;')
            w('  x := %s(x);' % word)
            w("  WriteLn('%s %s default ', x, ' ', Carry);" % (word, t))
            r, rc = rot(word, n, v, 1, 1)
            KOUT.append('%s %s default %s %s' % (word, t, show(r, n, s), rc))
        w('end;')
        w('')
    # in place in memory: a local whose address is taken stays in its slot
    for t, n, s in TYPES:
        w('procedure M%s;' % t)
        w('var')
        w('  x: %s;' % t)
        w('  p: Pointer;')
        w('begin')
        w('  p := @x;')
        w('  CarryOff;')
        c = 0
        for word in WORDS:
            for v in values(n):
                for k in (1, 3, n):
                    w('  x := %s;' % lit(v, n, s))
                    w('  x := %s(x, %d);' % (word, k))
                    w("  WriteLn('memory %s %s %d ', x, ' ', Carry);" % (word, t, k))
                    r, rc = rot(word, n, v, c, k)
                    if 'Carry' in word:
                        c = rc
                    MOUT.append('memory %s %s %d %s %d' % (word, t, k, show(r, n, s), c))
        w('end;')
        w('')
    # a signed value a loop keeps in a register, used there: its upper
    # bits must be the sign's again after each turn
    for t, n, s in TYPES[1:6:2]:
        w('procedure S%s;' % t)
        w('var')
        w('  x, y: %s;' % t)
        w('  i, sum: Integer;')
        w('begin')
        for word, k in (('RotateLeftThroughCarry', 1), ('ShiftLeftToCarry', 1), ('RotateLeftToCarry', 3),
                        ('ShiftRightSigned', 2), ('RotateRightThroughCarry', 5)):
            v = values(n)[0]
            w('  x := %s;' % lit(v, n, s))
            w('  y := %s;' % lit(values(n)[2], n, s))
            w('  sum := 0;')
            w('  CarryOn;')
            w('  for i := 1 to 20 do')
            w('  begin')
            w('    x := %s(x, %d);' % (word, k))
            w('    y := %s(y);' % word)
            w('    sum := sum + x + y;')
            w('    if x < 0 then')
            w('      sum := sum + 1000;')
            w('  end;')
            w("  WriteLn('sign %s %s ', x, ' ', y, ' ', sum, ' ', Carry);" % (word, t))
            x, y, c, sm = v, values(n)[2], 1, 0
            for _ in range(20):
                x, c = rot(word, n, x, c, k)
                y, c = rot(word, n, y, c, 1)
                sm += sgn(x, n) + sgn(y, n)
                if sgn(x, n) < 0:
                    sm += 1000
            SOUT.append('sign %s %s %d %d %d %d' % (word, t, sgn(x, n), sgn(y, n), sm, c))
        w('end;')
        w('')
    w('procedure SetOn;')
    w('begin')
    w('  CarryOn;')
    w('end;')
    w('')
    w('function Peek: Boolean;')
    w('begin')
    w('  Result := Carry;')
    w('end;')
    w('')
    w('procedure Deep(d: Integer);')
    w('var')
    w('  pad: array[0..63] of Integer;')
    w('begin')
    w('  pad[d and 63] := d;')
    w('  if d = 0 then')
    w('    CarryFlip')
    w('  else')
    w('    Deep(d - 1);')
    w('end;')
    w('')
    w('procedure Child(id: Integer);')
    w('var')
    w('  i: Integer;')
    w('begin')
    w('  childSaw := Carry;')
    w('  for i := 1 to 1000 do')
    w('    CarryFlip;')
    w('  CarryOn;')
    w('  Send(done, id);')
    w('end;')
    w('')
    # four routines flip their own Carry while their stacks grow and the
    # collector runs: none sees another's
    w('procedure Flipper(id: Integer);')
    w('var')
    w('  i, bad: Integer;')
    w('  want: Boolean;')
    w('begin')
    w('  bad := 0;')
    w('  want := (id and 1) = 1;')
    w('  Carry := want;')
    w('  for i := 1 to 200000 do')
    w('  begin')
    w('    CarryFlip;')
    w('    want := not want;')
    w('    if (i mod 20000) = 0 then')
    w('    begin')
    w('      Deep(400 + id * 100);')
    w('      want := not want;')
    w('    end;')
    w('    if Carry <> want then')
    w('      bad := bad + 1;')
    w('  end;')
    w('  Send(done, bad);')
    w('end;')
    w('')
    # Carry is a reserved word since 1.0.131: testdata/bitbad/respre
    # 256-bit shift left by 1, five times: the carry chain
    w('procedure Wide256;')
    w('var')
    w('  a: array[0..3] of Integer;')
    w('  k, i: Integer;')
    w('begin')
    A = [-1, 0, 0x7FFFFFFFFFFFFFFF, 1]
    for i, v in enumerate(A):
        w('  a[%d] := %d;' % (i, v))
    w('  for k := 1 to 5 do')
    w('  begin')
    w('    CarryOff;')
    w('    for i := 0 to 3 do')
    w('      a[i] := RotateLeftThroughCarry(a[i]);')
    w('  end;')
    w("  WriteLn('wide256 ', a[0], ' ', a[1], ' ', a[2], ' ', a[3], ' ', Carry);")
    w('end;')
    w('')
    x = sum((v & (2**64 - 1)) << (64 * i) for i, v in enumerate(A))
    top = 0
    for _ in range(5):
        top = (x >> 255) & 1
        x = (x << 1) & (2**256 - 1)
    parts = [sgn((x >> (64 * i)) & (2**64 - 1), 64) for i in range(4)]
    WOUT = 'wide256 %d %d %d %d %d' % (parts[0], parts[1], parts[2], parts[3], top)
    # a Byte a loop keeps in a register, through Carry: a ring of 9
    w('procedure Ring9;')
    w('var')
    w('  b: Byte;')
    w('  i, s, ones: Integer;')
    w('begin')
    w('  b := $B5;')
    w('  CarryOn;')
    w('  s := 0;')
    w('  ones := 0;')
    w('  for i := 1 to 100 do')
    w('  begin')
    w('    b := RotateLeftThroughCarry(b);')
    w('    s := s + b;')
    w('    if Carry then')
    w('      ones := ones + 1;')
    w('  end;')
    w("  WriteLn('ring9 ', b, ' ', Carry, ' ', s, ' ', ones);")
    w('end;')
    w('')
    b, c, s_, ones = 0xB5, 1, 0, 0
    for _ in range(100):
        b, c = rot('RotateLeftThroughCarry', 8, b, c, 1)
        s_ += b
        ones += c
    ROUT = 'ring9 %d %d %d %d' % (b, c, s_, ones)
    # CRC-8 (polynomial 7) with ShiftLeftToCarry
    w('function Crc8(const s: string): Byte;')
    w('var')
    w('  crc: Byte;')
    w('  i, k: Integer;')
    w('begin')
    w('  crc := 0;')
    w('  for i := 1 to Length(s) do')
    w('  begin')
    w('    crc := crc xor Byte(Ord(s[i]));')
    w('    for k := 0 to 7 do')
    w('    begin')
    w('      crc := ShiftLeftToCarry(crc);')
    w('      if Carry then')
    w('        crc := crc xor $07;')
    w('    end;')
    w('  end;')
    w('  Result := crc;')
    w('end;')
    w('')
    crc = 0
    for ch in b'123456789':
        crc ^= ch
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07 if crc & 0x80 else crc << 1) & 0xFF
    COUT = 'crc8 %d' % crc

    w('var')
    w('  b: Byte;')
    w('  w: Word;')
    w('  i: Integer;')
    w('  s8: Int8;')
    w('  u: UInt32;')
    w('  d: Double;')
    w('  sg: Single;')
    w('  ch: Char;')
    w('  hid: Integer;')
    w('  junk: string;')
    w('')
    w('begin')
    for j, k in enumerate(COUNTS):
        w('  cnt[%d] := %d;' % (j, k))
    for t, n, s in TYPES:
        for word in WORDS:
            for v in values(n):
                w('  V%s%s(%s);' % (t, word, lit(v, n, s)))
                for c in (0, 1):
                    items = []
                    for k in COUNTS:
                        r, rc = rot(word, n, v, c, k)
                        items.append('%s/%d' % (show(r, n, s), rc))
                    out.append('%s %s %s %d: %s' % (word, t, lit(v, n, s), c, ' '.join(items)))
        vals = values(n)
        for hi, lo in ((vals[0], vals[2]), (vals[1], vals[0])):
            w('  F%s(%s, %s);' % (t, lit(hi, n, s), lit(lo, n, s)))
            for d, left in (('FunnelLeft', True), ('FunnelRight', False)):
                out.append('%s %s %s %s: %s' % (d, t, lit(hi, n, s), lit(lo, n, s), ' '.join(
                    show(funnel(left, n, hi, lo, k), n, s) for k in COUNTS)))
                out.append('%s %s const %s' % (d, t, ' '.join(
                    show(funnel(left, n, hi, lo, k), n, s) for k in const_counts(n) + [1])))
    for t, n, s in TYPES:
        w('  K%s;' % t)
    out.extend(KOUT)
    for t, n, s in TYPES:
        w('  M%s;' % t)
    out.extend(MOUT)
    for t, n, s in TYPES[1:6:2]:
        w('  S%s;' % t)
    out.extend(SOUT)
    # in place on a global, in memory: the main body keeps it there
    w('  CarryOff;')
    for t, n, s in TYPES:
        v = values(n)[0]
        for word in WORDS:
            for k in (3, n):
                w('  g%s := %s;' % (t, lit(v, n, s)))
                w('  g%s := %s(g%s, %d);' % (t, word, t, k))
                w("  WriteLn('global %s %s %d ', g%s, ' ', Carry);" % (word, t, k, t))
                r, rc = rot(word, n, v, CARRY[0], k)
                if word in ('RotateLeftToCarry', 'RotateRightToCarry', 'RotateLeftThroughCarry',
                            'RotateRightThroughCarry', 'ShiftLeftToCarry', 'ShiftRightToCarry',
                            'ShiftRightSignedToCarry'):
                    CARRY[0] = rc
                out.append('global %s %s %d %s %d' % (word, t, k, show(r, n, s), CARRY[0]))
    # the reals and Char: the bits of their whole width
    w('  d := -2.5;')
    w('  d := RotateLeftToCarry(d, 12);')
    w("  WriteLn('double ', d as UInt64, ' ', Carry);")
    r, rc = rot('RotateLeftToCarry', 64, f64bits(-2.5), 0, 12)
    out.append('double %d %d' % (sgn(r, 64), rc))
    w('  sg := 1.5;')
    w('  CarryOff;')
    w('  sg := RotateRightThroughCarry(sg, 3);')
    w("  WriteLn('single ', sg as UInt32, ' ', Carry);")
    r, rc = rot('RotateRightThroughCarry', 32, f32bits(1.5), 0, 3)
    out.append('single %d %d' % (r, rc))
    w("  ch := 'A';")
    w('  ch := RotateLeftToCarry(ch, 3);')
    w("  WriteLn('char ', Ord(ch), ' ', Carry);")
    r, rc = rot('RotateLeftToCarry', 8, 65, 0, 3)
    out.append('char %d %d' % (r, rc))
    w("  ch := 'a';")
    w('  CarryOn;')
    w('  ch := RotateLeftThroughCarry(ch);')
    w("  WriteLn('char in place ', Ord(ch), ' ', Carry);")
    r, rc = rot('RotateLeftThroughCarry', 8, 97, 1, 1)
    out.append('char in place %d %d' % (r, rc))
    # an untyped constant takes the width of where it goes
    w('  b := RotateLeftToCarry($81);')
    w("  WriteLn('const byte ', b, ' ', Carry);")
    out.append('const byte 3 1')
    w('  w := RotateRightToCarry(1);')
    w("  WriteLn('const word ', w, ' ', Carry);")
    out.append('const word 32768 1')
    w('  i := RotateRightToCarry(1);')
    w("  WriteLn('const integer ', i, ' ', Carry);")
    out.append('const integer %d 1' % -(1 << 63))
    w('  s8 := ShiftRightSigned(-128, 3);')
    w("  WriteLn('const int8 ', s8);")
    out.append('const int8 -16')
    w('  u := ShiftLeftToCarry($80000001);')
    w("  WriteLn('const uint32 ', u, ' ', Carry);")
    out.append('const uint32 2 1')
    w("  WriteLn('const alone ', ShiftLeftToCarry($80), ' ', Carry);")
    out.append('const alone 256 0')
    w("  WriteLn('const count ', RotateLeftToCarry(b, 2 + 3), ' ', FunnelLeft(1, 2, 60));")
    r, _ = rot('RotateLeftToCarry', 8, 3, 0, 5)
    out.append('const count %d %d' % (r, funnel(True, 64, 1, 2, 60)))
    # a funnel's two sides join in one width, as in hi + lo
    w('  b := $81;')
    w('  w := $1234;')
    w('  s8 := -2;')
    w("  WriteLn('mixed ', FunnelLeft(b, w, 4), ' ', FunnelRight(s8, b, 4), ' ', FunnelLeft(w, 1, 12));")
    out.append('mixed %d %d %d' % (funnel(True, 16, 0x81, 0x1234, 4), sgn(funnel(False, 16, -2, 0x81, 4), 16),
                                   funnel(True, 16, 0x1234, 1, 12)))
    # a word as a statement: only its Carry is kept
    w('  i := 48;')
    w('  ShiftRightToCarry(i, 5);')
    w("  WriteLn('statement ', i, ' ', Carry);")
    out.append('statement 48 1')
    # the operators never touch Carry
    w('  CarryOn;')
    w('  i := (i rol 70) shl 3;')
    w('  i := i shr 1;')
    w("  WriteLn('operators ', i, ' ', Carry);")
    v = ((((48 << 6) | (48 >> 58)) & (2**64 - 1)) << 3) & (2**64 - 1)
    out.append('operators %d 1' % sgn(v >> 1, 64))
    # Carry is the routine's: kept across calls and recursion, 0 in a new routine
    w('  CarryOff;')
    w('  SetOn;')
    w("  WriteLn('after a call ', Carry, ' ', Peek);")
    out.append('after a call 1 1')
    w('  CarryOff;')
    w('  Deep(3000);')
    w("  WriteLn('after deep recursion ', Carry);")
    out.append('after deep recursion 1')
    w('  CarryOn;')
    w('  done := MakeChan(1);')
    w('  pas Child(7);')
    w('  hid := Recv(done);')
    w('  CarryFlip;')
    w("  WriteLn('a new routine starts with ', childSaw, '; this one kept ', Carry, ' ', hid);")
    out.append('a new routine starts with 0; this one kept 0 7')
    w('  done := MakeChan(4);')
    w('  for hid := 0 to 3 do')
    w('    pas Flipper(hid);')
    w('  for hid := 0 to 100000 do')
    w("    junk := 'x' + IntToStr(hid);")
    w('  hid := 0;')
    w('  for i := 0 to 3 do')
    w('    hid := hid + Recv(done);')
    w("  WriteLn('flippers ', hid);")
    out.append('flippers 0')
    w('  Wide256;')
    out.append(WOUT)
    w('  Ring9;')
    out.append(ROUT)
    w("  WriteLn('crc8 ', Crc8('123456789'));")
    out.append(COUT)
    w('end.')
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata')
    with open(os.path.join(base, 'rotwords.paslang'), 'w') as f:
        f.write('\n'.join(src) + '\n')
    with open(os.path.join(base, 'rotwords.out'), 'w') as f:
        f.write('\n'.join(out) + '\n')


MEMWORDS = WORDS


def lcg(seed, n):
    """The bytes Fill writes: the same generator in the test program."""
    s = seed
    out = []
    for _ in range(n):
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        out.append((s >> 16) & 255)
    return bytes(out)


def mem_counts(nb):
    out = []
    for k in [-3, 0, 1, 7, 8, 9, 64, 65, nb - 1, nb, nb + 1, 2 * nb + 1, 1000, 1 << 40]:
        if k not in out:
            out.append(k)
    return out


def hexb(b):
    return b.hex()


def rot_bytes(word, b, c, k):
    n = len(b) * 8
    v, rc = rot(word, n, int.from_bytes(b, 'little'), c, k)
    return v.to_bytes(len(b), 'little'), rc


def funnel_bytes(left, hi, lo, k):
    n = len(hi) * 8
    v = funnel(left, n, int.from_bytes(hi, 'little'), int.from_bytes(lo, 'little'), k)
    return v.to_bytes(len(hi), 'little')


# The values bigger than a register (1.0.130): name, type, bytes, how a
# procedure receives it
MEMTYPES = [('B1', 'array[0..0] of Byte', 1), ('B3', 'array[0..2] of Byte', 3),
            ('B8', 'array[0..7] of Byte', 8), ('B9', 'array[0..8] of Byte', 9),
            ('B17', 'array[0..16] of Byte', 17), ('B33', 'array[0..32] of Byte', 33),
            ('Rec', 'TRec', 12), ('Quad', 'Quad', 16), ('V128', 'V128', 16), ('V256', 'V256', 32)]


def main_mem():
    src = []
    out = []
    w = src.append
    w('program rotmem;')
    w('')
    w('uses paslib;')
    w('')
    w('{ Generated by scripts/rotmodel.py (P108, 1.0.130): the rotation words')
    w('  on values bigger than a register, strings and slices, their whole')
    w('  extent as one number, bit i being bit i mod 8 of byte i div 8. }')
    w('')
    w('type')
    w('  TRec = record')
    w('    A: Word;')
    w('    B: Byte;')
    w('    C: Int32;')
    w('    D: Int32;')
    w('  end;')
    w('  TWords = array of Word;')
    w('  TBytes = array of Byte;')
    for name, ty, size in MEMTYPES:
        if name.startswith('B'):
            w('  T%s = %s;' % (name, ty))
    w('')
    w('var')
    w('  cnt: array of Integer;')
    w('')
    w('procedure Fill(p: PByte; n, seed: Integer);')
    w('var')
    w('  i, s: Integer;')
    w('begin')
    w('  s := seed;')
    w('  for i := 0 to n - 1 do')
    w('  begin')
    w('    s := (s * 1103515245 + 12345) and $7FFFFFFF;')
    w('    p[i] := Byte((s shr 16) and 255);')
    w('  end;')
    w('end;')
    w('')
    w('procedure HexOut(p: PByte; n: Integer);')
    w('const')
    w("  Digits = '0123456789abcdef';")
    w('var')
    w('  i: Integer;')
    w('begin')
    w('  for i := 0 to n - 1 do')
    w('    Write(Digits[(p[i] shr 4) + 1], Digits[(p[i] and 15) + 1]);')
    w('end;')
    w('')
    w('procedure SetCnt(nb: Integer);')
    w('var')
    w('  k: array of Integer;')
    w('  i, j, n: Integer;')
    w('  dup: Boolean;')
    w('begin')
    w('  SetLength(k, 14);')
    for i, e in enumerate(['-3', '0', '1', '7', '8', '9', '64', '65', 'nb - 1', 'nb', 'nb + 1',
                           '2 * nb + 1', '1000', '1099511627776']):
        w('  k[%d] := %s;' % (i, e))
    w('  SetLength(cnt, 0);')
    w('  for i := 0 to 13 do')
    w('  begin')
    w('    dup := False;')
    w('    for j := 0 to i - 1 do')
    w('      if k[j] = k[i] then')
    w('        dup := True;')
    w('    if not dup then')
    w('    begin')
    w('      n := Length(cnt);')
    w('      SetLength(cnt, n + 1);')
    w('      cnt[n] := k[i];')
    w('    end;')
    w('  end;')
    w('end;')
    w('')
    for name, ty, size in MEMTYPES:
        tname = 'T' + name if name.startswith('B') else ty
        for word in MEMWORDS:
            w('procedure M%s%s(seed: Integer);' % (name, word))
            w('var')
            w('  x, y: %s;' % tname)
            w('  j, c: Integer;')
            w('begin')
            w('  Fill(PByte(@x), %d, seed);' % size)
            w('  for c := 0 to 1 do')
            w('  begin')
            w("    Write('%s %s ', seed, ' ', c, ':');" % (word, name))
            w('    for j := 0 to High(cnt) do')
            w('    begin')
            w('      Carry := c = 1;')
            w('      y := %s(x, cnt[j]);' % word)
            w("      Write(' ');")
            w('      HexOut(PByte(@y), %d);' % size)
            w("      Write('/', Carry);")
            w('    end;')
            w('    WriteLn;')
            w('  end;')
            w('end;')
            w('')
        w('procedure F%s(seed: Integer);' % name)
        w('var')
        w('  x, z, y: %s;' % tname)
        w('  j: Integer;')
        w('begin')
        w('  Fill(PByte(@x), %d, seed);' % size)
        w('  Fill(PByte(@z), %d, seed + 1);' % size)
        for d in ('FunnelLeft', 'FunnelRight'):
            w("  Write('%s %s ', seed, ':');" % (d, name))
            w('  for j := 0 to High(cnt) do')
            w('  begin')
            w('    y := %s(x, z, cnt[j]);' % d)
            w("    Write(' ');")
            w('    HexOut(PByte(@y), %d);' % size)
            w('  end;')
            w('  WriteLn;')
        w('end;')
        w('')
    # strings and slices
    for word in MEMWORDS:
        w('procedure S%s(const s: string);' % word)
        w('var')
        w('  y: string;')
        w('  j, c: Integer;')
        w('begin')
        w('  SetCnt(Length(s) * 8);')
        w('  for c := 0 to 1 do')
        w('  begin')
        w("    Write('%s string ', Length(s), ' ', c, ':');" % word)
        w('    for j := 0 to High(cnt) do')
        w('    begin')
        w('      Carry := c = 1;')
        w('      y := %s(s, cnt[j]);' % word)
        w("      Write(' ');")
        w('      HexOut(PByte(y), Length(y));')
        w("      Write('/', Carry);")
        w('    end;')
        w('    WriteLn;')
        w('  end;')
        w('end;')
        w('')
        w('procedure D%s(const d: TWords);' % word)
        w('var')
        w('  y: TWords;')
        w('  j, c: Integer;')
        w('begin')
        w('  SetCnt(Length(d) * 16);')
        w('  for c := 0 to 1 do')
        w('  begin')
        w("    Write('%s words ', Length(d), ' ', c, ':');" % word)
        w('    for j := 0 to High(cnt) do')
        w('    begin')
        w('      Carry := c = 1;')
        w('      y := %s(d, cnt[j]);' % word)
        w("      Write(' ', Length(y), '.');")
        w('      HexOut(PByte(y), Length(y) * 2);')
        w("      Write('/', Carry);")
        w('    end;')
        w('    WriteLn;')
        w('  end;')
        w('end;')
        w('')
    w('var')
    w('  s, s2: string;')
    w('  d, d2: TWords;')
    w('  bb: TBytes;')
    w('  big: TB33;')
    w('  r: TRec;')
    w('  q: Quad;')
    w('  i, k: Integer;')
    w('')
    w('begin')
    for name, ty, size in MEMTYPES:
        nb = size * 8
        w('  SetCnt(%d);' % nb)
        cs = mem_counts(nb)
        for seed in (7,):
            b = lcg(seed, size)
            for word in MEMWORDS:
                w('  M%s%s(%d);' % (name, word, seed))
                for c in (0, 1):
                    items = []
                    for k in cs:
                        r, rc = rot_bytes(word, b, c, k)
                        items.append('%s/%d' % (hexb(r), rc))
                    out.append('%s %s %d %d: %s' % (word, name, seed, c, ' '.join(items)))
            w('  F%s(%d);' % (name, seed))
            z = lcg(seed + 1, size)
            for d, left in (('FunnelLeft', True), ('FunnelRight', False)):
                out.append('%s %s %d: %s' % (d, name, seed, ' '.join(
                    hexb(funnel_bytes(left, b, z, k)) for k in cs)))
    # strings of 0, 1, 9 and 20 characters, slices of 0, 1 and 5 words
    strs = [b'', b'Z', b'paslang!!', bytes(range(33, 53))]
    words = [[], [0x8001], [1, 0x8000, 0xFFFF, 0x1234, 0x7FFF]]
    for word in MEMWORDS:
        for sv in strs:
            w("  s := '%s';" % sv.decode().replace("'", "''"))
            w('  S%s(s);' % word)
            cs = mem_counts(len(sv) * 8)
            for c in (0, 1):
                items = []
                for k in cs:
                    r, rc = rot_bytes(word, sv, c, k)
                    items.append('%s/%d' % (hexb(r), rc))
                out.append('%s string %d %d: %s' % (word, len(sv), c, ' '.join(items)))
        for wv in words:
            w('  SetLength(d, %d);' % len(wv))
            for i, x in enumerate(wv):
                w('  d[%d] := %d;' % (i, x))
            w('  D%s(d);' % word)
            b = b''.join(x.to_bytes(2, 'little') for x in wv)
            cs = mem_counts(len(b) * 8)
            for c in (0, 1):
                items = []
                for k in cs:
                    r, rc = rot_bytes(word, b, c, k)
                    items.append('%d.%s/%d' % (len(wv), hexb(r), rc))
                out.append('%s words %d %d: %s' % (word, len(wv), c, ' '.join(items)))
    # a literal, a constant count, in place, a record's fields
    w('  CarryOff;')
    w("  s := RotateLeftToCarry('paslang', 3);")
    w("  Write('literal ');")
    w('  HexOut(PByte(s), Length(s));')
    w("  WriteLn(' ', Carry);")
    r, rc = rot_bytes('RotateLeftToCarry', b'paslang', 0, 3)
    out.append('literal %s %d' % (hexb(r), rc))
    w("  WriteLn('literal right ', RotateRight('paslang', 8));")
    out.append('literal right ' + rot_bytes('RotateRight', b'paslang', 0, 8)[0].decode('ascii'))
    w('  Fill(PByte(@big), 33, 11);')
    w('  CarryOn;')
    w('  for i := 1 to 70 do')
    w('    big := RotateLeftThroughCarry(big);')
    w("  Write('in place ');")
    w('  HexOut(PByte(@big), 33);')
    w("  WriteLn('/', Carry);")
    b, c = lcg(11, 33), 1
    for _ in range(70):
        b, c = rot_bytes('RotateLeftThroughCarry', b, c, 1)
    out.append('in place %s/%d' % (hexb(b), c))
    w('  Fill(PByte(@big), 33, 12);')
    w('  big := ShiftRightSignedToCarry(big, 100);')
    w("  Write('constant ');")
    w('  HexOut(PByte(@big), 33);')
    w("  WriteLn('/', Carry);")
    b, c = rot_bytes('ShiftRightSignedToCarry', lcg(12, 33), 1, 100)
    out.append('constant %s/%d' % (hexb(b), c))
    w('  r.A := $8001;')
    w('  r.B := 3;')
    w('  r.C := -1;')
    w('  r.D := 5;')
    w('  CarryOff;')
    w('  r := RotateLeftToCarry(r, 17);')
    w("  WriteLn('record ', r.A, ' ', r.B, ' ', r.C, ' ', r.D, ' ', Carry);")
    rb = (0x8001).to_bytes(2, 'little') + bytes([3, 0]) + (0xFFFFFFFF).to_bytes(4, 'little') + (5).to_bytes(4, 'little')
    rr, rc = rot_bytes('RotateLeftToCarry', rb, 0, 17)
    out.append('record %d %d %d %d %d' % (int.from_bytes(rr[0:2], 'little'), rr[2],
                                          int.from_bytes(rr[4:8], 'little', signed=True),
                                          int.from_bytes(rr[8:12], 'little', signed=True), rc))
    w("  WriteLn('field ', RotateLeft(r, 16).A);")
    rr2, _ = rot_bytes('RotateLeft', rr, 0, 16)
    out.append('field %d' % int.from_bytes(rr2[0:2], 'little'))
    # a string made from another: the old one stays; a statement keeps Carry
    w("  s := 'AB';")
    w('  s2 := s;')
    w('  s := ShiftLeftToCarry(s, 9);')
    w("  WriteLn('copy ', Ord(s[1]), ' ', Ord(s[2]), ' ', s2, ' ', Carry);")
    r, rc = rot_bytes('ShiftLeftToCarry', b'AB', 0, 9)
    out.append('copy %d %d AB %d' % (r[0], r[1], rc))
    w("  ShiftRightToCarry('A', 1);")
    w("  Write('statement ', Carry);")
    w("  ShiftRightToCarry('AB', 9);")
    w("  Write(' ', Carry);")
    w("  ShiftRightToCarry('AB', 10);")
    w("  WriteLn(' ', Carry);")
    out.append('statement %d %d %d' % (rot('ShiftRightToCarry', 8, 65, 0, 1)[1],
                                       rot_bytes('ShiftRightToCarry', b'AB', 0, 9)[1],
                                       rot_bytes('ShiftRightToCarry', b'AB', 0, 10)[1]))
    # funnels of strings, of slices, and of reals
    w("  WriteLn('funnel strings ', FunnelLeft('ab', 'cd', 8), ' ', FunnelRight('ab', 'cd', 12));")
    out.append('funnel strings %s %s' % (funnel_bytes(True, b'ab', b'cd', 8).decode('ascii'),
                                         funnel_bytes(False, b'ab', b'cd', 12).decode('ascii')))
    w('  SetLength(d2, 2);')
    w('  d2[0] := 1;')
    w('  d2[1] := 2;')
    w('  SetLength(d, 2);')
    w('  d[0] := $FFFF;')
    w('  d[1] := 3;')
    w('  d := FunnelRight(d, d2, 20);')
    w("  WriteLn('funnel words ', d[0], ' ', d[1], ' ', Length(d));")
    fr = funnel_bytes(False, bytes([0xFF, 0xFF, 3, 0]), bytes([1, 0, 2, 0]), 20)
    out.append('funnel words %d %d 2' % (int.from_bytes(fr[0:2], 'little'), int.from_bytes(fr[2:4], 'little')))
    w("  WriteLn('funnel reals ', FunnelLeft(1.0, 2.0, 4) as UInt64);")
    out.append('funnel reals %d' % sgn(funnel(True, 64, f64bits(1.0), f64bits(2.0), 4), 64))
    w('  q := 1;')
    w('  q := FunnelLeft(q, q, 20);')
    w("  WriteLn('funnel quad ', (q as array[0..1] of Integer)[0], ' ', (q as array[0..1] of Integer)[1]);")
    qb = (0x3FFF << 112).to_bytes(16, 'little')
    qr = funnel_bytes(True, qb, qb, 20)
    out.append('funnel quad %d %d' % (sgn(int.from_bytes(qr[0:8], 'little'), 64),
                                      sgn(int.from_bytes(qr[8:16], 'little'), 64)))
    w('  SetLength(bb, 0);')
    w('  bb := ShiftLeftToCarry(bb, 1);')
    w("  WriteLn('empty ', Length(bb), ' ', Carry);")
    out.append('empty 0 0')
    w('end.')
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata')
    with open(os.path.join(base, 'rotmem.paslang'), 'w') as f:
        f.write('\n'.join(src) + '\n')
    with open(os.path.join(base, 'rotmem.out'), 'w') as f:
        f.write('\n'.join(out) + '\n')


KOUT = []
SOUT = []
MOUT = []
CARRY = [0]

if __name__ == '__main__':
    main()
    main_mem()
