#!/usr/bin/env python3
"""Writes src/lib/pasfontnames.paslang: the glyph names that font files do not
carry but point to by number (P512, P513): the 258 names of the standard
Macintosh glyph ordering that a TrueType or OpenType `post` table of format 1
or 2 refers to, and from the Compact Font Format the 391 standard strings that
a string id below 391 stands for, the Standard and Expert encodings and the
ISOAdobe, Expert and ExpertSubset charsets a CFF font may use by number.

    python3 scripts/gen_fontnames.py [--check]

Reads docs/ref/pdf/fonts/Chap6post.html (Apple's TrueType Reference Manual,
chapter 6, `post`: "The names for these 258 glyphs are, in order") and
docs/ref/pdf/fonts/5176.CFF.txt (pdftotext -layout of Adobe Technical Note
5176, The Compact Font Format Specification, appendices A, B and C; the names
of the encodings and the charsets are checked against the strings). --check
writes nothing and fails when the unit is not what this makes (make check;
without docs/ref it has nothing to read and passes)."""
import html
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POST = os.path.join(ROOT, 'docs', 'ref', 'pdf', 'fonts', 'Chap6post.html')
CFF = os.path.join(ROOT, 'docs', 'ref', 'pdf', 'fonts', '5176.CFF.txt')
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


def cff_tables():
    """the standard strings, the code to SID tables of the Standard and Expert encodings and the SIDs of the
    ISOAdobe, Expert and ExpertSubset charsets (glyph 0 first, .notdef), from Appendices A, B and C"""
    t = open(CFF, encoding='utf-8').read()
    a = t.index('Appendix A\n                 Standard Strings')
    b = t.index('Appendix B\n                          Predefined Encodings')
    c = t.index('Appendix C\n                  Predefined Charsets')
    d = t.index('Appendix D', c)

    def lines(x):
        for ln in x.split('\n'):
            ln = ln.strip()
            if ln and ln[0].isdigit() and 'Appendix' not in ln and 'Dec 03' not in ln:
                yield ln.split()

    pairs = []
    for tok in lines(t[a:b]):
        if len(tok) % 2 == 0:       # a page number alone on its line is one token
            pairs += [(int(tok[i]), tok[i + 1]) for i in range(0, len(tok), 2)]
    pairs.sort()
    assert [p[0] for p in pairs] == list(range(391)), 'the standard strings are not 0 to 390'
    strings = [p[1] for p in pairs]
    assert strings[0] == '.notdef' and strings[1] == 'space' and strings[390] == 'Semibold' and strings[379] == '001.000'
    sec = t[b:c]
    i2 = sec.index('ExpertEncoding (code / SID / name')
    encs = []
    for part in (sec[:i2], sec[i2:]):
        tr = []
        for tok in lines(part):
            if len(tok) % 3 == 0:
                tr += [(int(tok[i]), int(tok[i + 1]), tok[i + 2]) for i in range(0, len(tok), 3)]
        tr.sort()
        assert [x[0] for x in tr] == list(range(256)), 'an encoding is not codes 0 to 255'
        for code, sid, name in tr:
            assert strings[sid] == name, (code, sid, name)
        encs.append([x[1] for x in tr])
    sec = t[c:d]
    heads = [(m.start(), m.group(1)) for m in re.finditer(r'(ISOAdobe|Expert Subset|Expert) \(SID / name\)', sec)]
    assert [h for _, h in heads] == ['ISOAdobe', 'Expert', 'Expert Subset'], heads
    sets = []
    for k, (pos, h) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(sec)
        sids = []
        for tok in lines(sec[pos:end]):
            if len(tok) % 2 == 0:
                sids += [(int(tok[i]), tok[i + 1]) for i in range(0, len(tok), 2)]
        for sid, name in sids:
            assert strings[sid] == name, (h, sid, name)
        sets.append([0] + [x[0] for x in sorted(sids)])
    assert len(sets[0]) == 229 and sets[0] == list(range(229)), len(sets[0])
    assert len(sets[1]) == 166 and len(sets[2]) == 87, (len(sets[1]), len(sets[2]))
    return strings, encs, sets


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

{ The glyph names a font file points to by number (P512, P513). THIS UNIT IS
  WRITTEN BY scripts/gen_fontnames.py: change the script and run it, make
  check runs it with --check.

  The 258 names of the standard Macintosh glyph ordering, as Apple's
  TrueType Reference Manual gives them ("post" format 1 has exactly these
  glyphs, format 2 refers to them by index); and what Adobe Technical Note
  5176 (The Compact Font Format Specification) numbers: the 391 standard
  strings (a string id below 391 is one of them), the glyph names the
  Standard and Expert encodings give each code, and the string ids of the
  ISOAdobe, Expert and ExpertSubset charsets. }
unit pasfontnames;

interface

{ the name of a glyph of the standard Macintosh ordering, 0 to 257; empty
  for another index }
function FontMacGlyphName(Index: Integer): string;

const
  { the charsets of a CFF font that are named by number }
  cffISOAdobe = 0;
  cffExpert = 1;
  cffExpertSubset = 2;

{ the standard string of a CFF string id, 0 to 390; empty for another }
function FontCffString(Sid: Integer): string;

{ the string id the Standard (Expert false) or the Expert encoding gives a
  code, 0 (.notdef) for none }
function FontCffEncodingSid(Expert: Boolean; Code: Integer): Integer;

{ the number of glyphs (.notdef included) of a predefined charset, and the
  string id of its glyph Index; 0 outside }
function FontCffCharsetCount(Charset: Integer): Integer;
function FontCffCharsetSid(Charset, Index: Integer): Integer;

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

function FontCffString(Sid: Integer): string;
begin
  if (Sid < 0) or (Sid > 390) then
    Result := ''
  else
    Result := Copy(CffStrings, CffStart[Sid], CffStart[Sid + 1] - CffStart[Sid] - 1);
end;

function FontCffEncodingSid(Expert: Boolean; Code: Integer): Integer;
begin
  Result := 0;
  if (Code < 0) or (Code > 255) then
    Exit;
  if Expert then
    Result := CffExpertEnc[Code]
  else
    Result := CffStdEnc[Code];
end;

function FontCffCharsetCount(Charset: Integer): Integer;
begin
  case Charset of
    cffISOAdobe: Result := 229;
    cffExpert: Result := 166;
    cffExpertSubset: Result := 87;
  else
    Result := 0;
  end;
end;

function FontCffCharsetSid(Charset, Index: Integer): Integer;
begin
  Result := 0;
  if (Index < 0) or (Index >= FontCffCharsetCount(Charset)) then
    Exit;
  case Charset of
    cffISOAdobe: Result := Index;
    cffExpert: Result := CffExpertSet[Index];
    cffExpertSubset: Result := CffSubsetSet[Index];
  end;
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
    out.append('  { where each name begins in MacNames (1 based), and past the last }\n  MacStart: array[0..%d] of Word = (\n%s);\n\n' % (len(starts) - 1, ',\n'.join(lines)))
    strings, encs, sets = cff_tables()
    packed = ''
    starts = []
    chunks = []
    cur = ''
    for n in strings:
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
    out.append('  { the 391 standard strings of the Compact Font Format, each followed by a bar }\n  CffStrings =\n    ' + " +\n    ".join("'" + c + "'" for c in chunks) + ';\n\n')

    def table(name, comment, vals, kind):
        ls = []
        for i in range(0, len(vals), 16):
            ls.append('    ' + ', '.join(str(v) for v in vals[i:i + 16]))
        return '  { %s }\n  %s: array[0..%d] of %s = (\n%s);\n\n' % (comment, name, len(vals) - 1, kind, ',\n'.join(ls))

    out.append(table('CffStart', 'where each standard string begins in CffStrings (1 based), and past the last', starts, 'Word'))
    out.append(table('CffStdEnc', 'the string id the Standard Encoding gives each code', encs[0], 'Word'))
    out.append(table('CffExpertEnc', 'the string id the Expert Encoding gives each code', encs[1], 'Word'))
    out.append(table('CffExpertSet', 'the string ids of the Expert charset, glyph 0 first', sets[1], 'Word'))
    out.append(table('CffSubsetSet', 'the string ids of the ExpertSubset charset, glyph 0 first', sets[2], 'Word'))
    return ''.join(out).rstrip('\n') + '\n' + POST_


if __name__ == '__main__':
    if not (os.path.exists(POST) and os.path.exists(CFF)):
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
