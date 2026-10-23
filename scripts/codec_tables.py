#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""codec_tables.py TEMPLATE CASE.txt > src/lib/pascodec.paslang (P435): the
tables of the unit. UpperTab and LowerTab for U+0000 to U+017F are Go's
strings.ToUpper and ToLower (CASE.txt is `go run scripts/codec_tables.go`);
FoldTab for U+0080 to U+017F is each letter's Unicode canonical
decomposition (Python's unicodedata, Unicode 16) without its marks, and the
letters that do not decompose by the usual transliteration."""
import sys
import unicodedata

SPECIAL = {'ß': 'ss', 'ẞ': 'SS', 'Æ': 'AE', 'æ': 'ae', 'Œ': 'OE', 'œ': 'oe', 'Ø': 'O', 'ø': 'o', 'Đ': 'D', 'đ': 'd',
           'Ð': 'D', 'ð': 'd', 'Þ': 'TH', 'þ': 'th', 'ı': 'i', 'Ł': 'L', 'ł': 'l', 'Ŀ': 'L', 'ŀ': 'l', 'Ħ': 'H',
           'ħ': 'h', 'Ŧ': 'T', 'ŧ': 't', 'Ĳ': 'IJ', 'ĳ': 'ij', 'ŉ': "'n", 'ĸ': 'k', 'Ŋ': 'NG', 'ŋ': 'ng', 'ſ': 's'}
tmpl = open(sys.argv[1]).read()
up = list(range(0x180))
lo = list(range(0x180))
for line in open(sys.argv[2]):
    c, u, l = (int(x, 16) for x in line.split())
    up[c] = u
    lo[c] = l


def words(name, vals):
    out = ['  %s: array[0..383] of Word = (' % name]
    for i in range(0, 384, 12):
        out.append('    ' + ', '.join('$%04X' % v for v in vals[i:i + 12]) + (',' if i + 12 < 384 else ');'))
    return '\n'.join(out)


fold = []
for c in range(0x80, 0x180):
    ch = chr(c)
    if ch in SPECIAL:
        f = SPECIAL[ch]
    else:
        d = unicodedata.normalize('NFD', ch)
        f = ''.join(x for x in d if not unicodedata.combining(x))
    fold.append('' if f == ch else f)
lines = ['  FoldTab: array[0..255] of string = (']
for i in range(0, 256, 8):
    lines.append('    ' + ', '.join("'%s'" % x.replace("'", "''") for x in fold[i:i + 8]) + (',' if i + 8 < 256 else ');'))
tables = ('{ ---- the tables, scripts/codec_tables.py ---- }\n\nconst\n  { Go\'s strings.ToUpper and ToLower of each code point to U+017F }\n' +
          words('UpperTab', up) + '\n' + words('LowerTab', lo) +
          '\n  { each letter of U+0080 to U+017F without its marks, \'\' when it has none }\n' + '\n'.join(lines) + '\n')
sys.stdout.write(tmpl.replace('@TABLES@', tables))
