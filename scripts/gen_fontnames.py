#!/usr/bin/env python3
"""Writes src/lib/pasfontnames.paslang: the glyph names that font files do not
carry but point to by number (P512): the 258 names of the standard Macintosh
glyph ordering that a TrueType or OpenType `post` table of format 1 or 2
refers to.

    python3 scripts/gen_fontnames.py [--check]

Reads docs/ref/pdf/fonts/Chap6post.html (Apple's TrueType Reference Manual,
chapter 6, `post`: "The names for these 258 glyphs are, in order"). --check
writes nothing and fails when the unit is not what this makes (make check;
without docs/ref it has nothing to read and passes)."""
import html
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POST = os.path.join(ROOT, 'docs', 'ref', 'pdf', 'fonts', 'Chap6post.html')
OUT = os.path.join(ROOT, 'src', 'lib', 'pasfontnames.paslang')


def mac_names():
    s = open(POST, encoding='latin-1').read()
    t = html.unescape(re.sub(r'<[^>]+>', '\n', s))
    lines = [l.strip() for l in t.split('\n') if l.strip()]
    rows = lines[lines.index('Glyph ID') + 2:]
    out = []
    n = 0
    while n + 1 < len(rows) and len(out) < 258:
        if rows[n].isdigit() and not rows[n + 1].isdigit():
            out.append((int(rows[n]), rows[n + 1]))
            n += 2
        else:
            n += 1
    assert [a for a, _ in out] == list(range(258)), 'the table is not 0 to 257 in order'
    names = [b for _, b in out]
    assert names[0] == '.notdef' and names[3] == 'space' and names[36] == 'A' and names[257] == 'dcroat'
    assert all(re.fullmatch(r'[A-Za-z0-9._]+', x) for x in names)
    return names


PRE = '''{ This file is part of paslang.
  Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>

  paslang is free software: you can redistribute it and/or modify it
  under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.

  paslang is distributed in the hope that it will be useful, but
  WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
  General Public License for more details.

  Under Section 7 of GPL version 3, you are granted additional
  permissions described in the paslang Runtime Library Exception,
  version 1.0, in the file COPYING.RUNTIME.

  You should have received a copy of the GNU General Public License
  along with paslang.  If not, see <https://www.gnu.org/licenses/>. }

{ The glyph names a font file points to by number (P512). THIS UNIT IS
  WRITTEN BY scripts/gen_fontnames.py: change the script and run it, make
  check runs it with --check.

  The 258 names of the standard Macintosh glyph ordering, as Apple's
  TrueType Reference Manual gives them ("post" format 1 has exactly these
  glyphs, format 2 refers to them by index). }
unit pasfontnames;

interface

{ the name of a glyph of the standard Macintosh ordering, 0 to 257; empty
  for another index }
function FontMacGlyphName(Index: Integer): string;

implementation

const
'''

POST_ = '''
function FontMacGlyphName(Index: Integer): string;
begin
  if (Index < 0) or (Index > 257) then
    Result := ''
  else
    Result := Copy(MacNames, MacStart[Index], MacStart[Index + 1] - MacStart[Index] - 1);
end;

end.
'''


def build():
    names = mac_names()
    packed = ''
    starts = []
    chunks = []
    cur = ''
    for n in names:
        starts.append(len(packed) + 1)
        packed += n + '|'
        cur += n + '|'
        if len(cur) > 90:
            chunks.append(cur)
            cur = ''
    starts.append(len(packed) + 1)
    if cur:
        chunks.append(cur)
    assert ''.join(chunks) == packed
    out = [PRE]
    out.append('  { the names, each followed by a bar }\n  MacNames =\n    ' + " +\n    ".join("'" + c + "'" for c in chunks) + ';\n\n')
    lines = []
    for i in range(0, len(starts), 16):
        lines.append('    ' + ', '.join(str(v) for v in starts[i:i + 16]))
    out.append('  { where each name begins in MacNames (1 based), and past the last }\n  MacStart: array[0..%d] of Word = (\n%s);\n' % (len(starts) - 1, ',\n'.join(lines)))
    return ''.join(out) + POST_


if __name__ == '__main__':
    if not os.path.exists(POST):
        print('gen_fontnames.py: docs/ref/pdf/fonts is not here, nothing to check')
        sys.exit(0 if '--check' in sys.argv else 1)
    text = build()
    if '--check' in sys.argv:
        if not os.path.exists(OUT) or open(OUT).read() != text:
            sys.exit('scripts/gen_fontnames.py: src/lib/pasfontnames.paslang is not what the generator writes')
        print('pasfontnames.paslang is the generator\'s')
    else:
        open(OUT, 'w').write(text)
        print('wrote', OUT, len(text), 'bytes')
