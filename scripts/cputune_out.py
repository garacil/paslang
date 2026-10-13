#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""The output testdata/cputune.paslang must print (P261), worked out with
Python's integers: the leading and trailing zeros of each value of the
test as every integer width takes it (Integer, Int32, UInt32, Int16,
Word, Int8, Byte; a narrow width keeps the low bits), the width when it
is 0. The values are read from the test's own vals[i] := lines."""
import re
import sys

src = open(sys.argv[1] if len(sys.argv) > 1 else 'testdata/cputune.paslang').read()
vals = []
for m in re.finditer(r'vals\[(\d+)\] := (.+?);', src):
    expr = m.group(2)
    if not re.fullmatch(r'[-+0-9 ]+', expr):
        sys.exit('cannot read ' + expr)
    vals.append(eval(expr))
assert len(vals) == 12, vals


def lz(v, w):
    v &= (1 << w) - 1
    return w - v.bit_length()


def tz(v, w):
    v &= (1 << w) - 1
    if v == 0:
        return w
    return (v & -v).bit_length() - 1


out = []
for v in vals:
    line = ''
    for w in (64, 32, 32, 16, 16, 8, 8):
        line += '%d/%d ' % (lz(v, w), tz(v, w))
    out.append(line + str(lz(v, 64) + tz(v, 64)))
out.append('disagree 0')
# BaseHasMore, FastHasMore (BMI1 or LSE), One(Two(39)); a Boolean is
# written 1 or 0 (manual, 19)
out.append('0 1 42')
# the string comparisons, byte by byte as Python's bytes compare
pairs = [(b'abcdefgh', b'abcdefgi'), (b'abcdefgi', b'abcdefgh'), (b'abc', b'abd'), (b'ab', b'a'),
         (b'abcdefghijklmnopq', b'abcdefghijklmnopr')]
out.append(' '.join('1' if a < b else '0' for a, b in pairs))
# the counts of a whole string: its bytes one number, the first byte the
# lowest, the highest bit bit 7 of the last byte (manual, bit words)
words = []
for b in (b'A', b'P\0\0', b'     P', b'\0\0  p'):
    n = int.from_bytes(b, 'little')
    words.append('%d %d' % (lz(n, 8 * len(b)), tz(n, 8 * len(b))))
out.append(' '.join(words))
print('\n'.join(out))
