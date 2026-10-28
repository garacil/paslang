#!/usr/bin/env python3
"""Writes src/lib/paspdfenc.paslang: the Latin-text encodings of a PDF simple
font (ISO 32000-1, annex D.2: StandardEncoding, MacRomanEncoding,
WinAnsiEncoding, PDFDocEncoding) as the Unicode scalar of each code, and the
Adobe Glyph List as one string, for the glyph names of a font's Differences.

    python3 scripts/gen_pdfenc.py [--check]

Reads docs/ref/pdf/PDF32000_2008.txt (pdftotext of the standard) and
docs/ref/pdf/agl/glyphlist.txt (Adobe, BSD-3-Clause, kept in the unit's
header). --check writes nothing and fails when the unit is not what this
makes (make check). The encodings are checked here against Python's cp1252
and mac_roman codecs where those define the code."""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, 'docs', 'ref', 'pdf', 'PDF32000_2008.txt')
AGL = os.path.join(ROOT, 'docs', 'ref', 'pdf', 'agl', 'glyphlist.txt')
OUT = os.path.join(ROOT, 'src', 'lib', 'paspdfenc.paslang')

def read_agl():
    names = {}
    order = []
    for line in open(AGL, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        n, u = line.strip().split(';')
        names[n] = [int(x, 16) for x in u.split()]
        order.append(n)
    return names, order


def read_tables(agl):
    lines = open(SPEC, encoding='utf-8').read().split('\n')
    start = next(i for i, l in enumerate(lines) if l.startswith('D.2 Latin Character Set and Encodings'))
    end = next(i for i, l in enumerate(lines) if i > start and l.startswith('D.3 PDFDocEncoding'))
    pat = re.compile(r'(\S+)\s+([A-Za-z][A-Za-z0-9]*)(?:\s+\d)?\s+(—|[0-7]{3})\s+(—|[0-7]{3})\s+(—|[0-7]{3})\s+(—|[0-7]{3})')
    enc = [dict() for _ in range(4)]
    seen = 0
    spat = re.compile(r'\s(space)(?:\s+\d)?\s+(—|[0-7]{3})\s+(—|[0-7]{3})\s+(—|[0-7]{3})\s+(—|[0-7]{3})')
    for l in lines[start:end]:
        # the space has no character in the table's first column
        sm = spat.search(l)
        ms = list(pat.finditer(l))
        if sm and not any(m.group(2) == 'space' for m in ms):
            ms.append(sm)
        for m in ms:
            name = m.group(2) if m.re is pat else m.group(1)
            first = 3 if m.re is pat else 2
            for k in range(4):
                c = m.group(first + k)
                if c != '—':
                    code = int(c, 8)
                    assert code not in enc[k], (name, k, code)
                    enc[k][code] = name
            seen += 1
    assert seen == 229, seen
    tables = []
    for k in range(4):
        row = [-1] * 256
        for code, name in enc[k].items():
            assert name in agl, name
            row[code] = agl[name][0]
        tables.append(row)
    # the footnotes: space and hyphen are doubled, unused WinAnsi codes are bullets
    tables[1][0o312] = 32
    tables[2][0o240] = 32
    tables[2][0o255] = 45
    for c in range(0o41, 256):
        if tables[2][c] < 0:
            tables[2][c] = 0x2022
    return tables


def check_codecs(t):
    for c in range(32, 256):
        try:
            u = ord(bytes([c]).decode('cp1252'))
            assert t[2][c] == u or c in (0x7F, 0xA0, 0xAD), ("win", c, t[2][c], u)
        except UnicodeDecodeError:
            assert t[2][c] == 0x2022, ('win bullet', c)
    for c in range(32, 256):
        u = ord(bytes([c]).decode('mac_roman'))
        if t[1][c] < 0:
            continue
        # PDF's MacRoman keeps currency at 333 and differs at a few codes
        if t[1][c] != u:
            assert c in (0xDB, 0xCA, 0xDA, 0xF0, 0xBD, 0xC6, 0xB5, 0xB0), ('mac', hex(c), hex(t[1][c]), hex(u))


def lit(chunks):
    return " +\n    ".join("'" + c + "'" for c in chunks)


def build():
    agl, order = read_agl()
    t = read_tables(agl)
    check_codecs(t)
    rows = []
    for n in order:
        rows.append('|' + n + ';' + ' '.join('%04X' % u for u in agl[n]))
    chunks = []
    cur = ''
    for r in rows:
        cur += r
        if len(cur) > 90:
            chunks.append(cur)
            cur = ''
    cur += '|'
    chunks.append(cur)
    out = []
    names = ['StdU', 'MacU', 'WinU', 'DocU']
    for k in range(4):
        vals = t[k]
        lines = []
        for i in range(0, 256, 16):
            lines.append('    ' + ', '.join(str(v) for v in vals[i:i + 16]))
        out.append('  %s: array[0..255] of Integer = (\n%s);\n\n' % (names[k], ',\n'.join(lines)))
    out.append('  GlyphList = ' + lit(chunks) + ';\n')
    return UNIT_PRE + ''.join(out) + UNIT_POST


UNIT_PRE = """{ This file is part of paslang.
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

{ The Latin-text encodings of a PDF simple font and the Adobe Glyph List
  (P476). THIS UNIT IS WRITTEN BY scripts/gen_pdfenc.py: change the script
  and run it, make check runs it with --check.

  The codes of StandardEncoding, MacRomanEncoding, WinAnsiEncoding and
  PDFDocEncoding come from ISO 32000-1, annex D.2, as the Unicode scalar
  each stands for (-1 where the encoding has none); WinAnsiEncoding maps
  its unused codes above 32 to the bullet, as the note of the annex says.
  The glyph list is Adobe's glyphlist.txt of the AGL, which is
  Copyright 2002-2019 Adobe (http://www.adobe.com/) and is
  redistributed under this licence:

  Redistribution and use in source and binary forms, with or without
  modification, are permitted provided that the following conditions are
  met:

  Redistributions of source code must retain the above copyright notice,
  this list of conditions and the following disclaimer.

  Redistributions in binary form must reproduce the above copyright
  notice, this list of conditions and the following disclaimer in the
  documentation and/or other materials provided with the distribution.

  Neither the name of Adobe nor the names of its contributors may be
  used to endorse or promote products derived from this software
  without specific prior written permission.

  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
  A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
  HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
  LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE. }
unit paspdfenc;

interface

const
  { the encodings PdfEncodingRune takes }
  peStandard = 0;
  peMacRoman = 1;
  peWinAnsi = 2;
  pePdfDoc = 3;

{ the Unicode scalar the code stands for in the encoding, or -1 }
function PdfEncodingRune(Enc, Code: Integer): Integer;

{ the text of a glyph name as the Adobe Glyph List specification reads it:
  the part before the first point; its components between underscores;
  each a name of the list, or uniXXXX (any number of four digits), or
  uXXXX to uXXXXXX; as UTF-8. An unknown component gives nothing, and the
  name of nothing known gives an empty string. }
function PdfGlyphText(const Name: string): string;

{ a Unicode scalar as UTF-8 (U+FFFD for a surrogate or a value past
  $10FFFF) }
function PdfRuneToUtf8(C: Integer): string;

implementation

const
"""

UNIT_POST = """
function PdfEncodingRune(Enc, Code: Integer): Integer;
begin
  Result := -1;
  if (Code < 0) or (Code > 255) then
    Exit;
  if Enc = peStandard then
    Result := StdU[Code]
  else if Enc = peMacRoman then
    Result := MacU[Code]
  else if Enc = peWinAnsi then
    Result := WinU[Code]
  else if Enc = pePdfDoc then
    Result := DocU[Code];
end;

function PdfRuneToUtf8(C: Integer): string;
begin
  if (C < 0) or (C > $10FFFF) or ((C >= $D800) and (C <= $DFFF)) then
    C := $FFFD;
  if C < $80 then
    Result := Chr(C)
  else if C < $800 then
    Result := Chr($C0 or (C shr 6)) + Chr($80 or (C and $3F))
  else if C < $10000 then
    Result := Chr($E0 or (C shr 12)) + Chr($80 or ((C shr 6) and $3F)) + Chr($80 or (C and $3F))
  else
    Result := Chr($F0 or (C shr 18)) + Chr($80 or ((C shr 12) and $3F)) + Chr($80 or ((C shr 6) and $3F)) + Chr($80 or (C and $3F));
end;

function HexRun(const S: string; From, N: Integer; out V: Integer): Boolean;
var
  i, d, c: Integer;
begin
  Result := False;
  V := 0;
  if From + N - 1 > Length(S) then
    Exit;
  for i := From to From + N - 1 do
  begin
    c := Ord(S[i]);
    if (c >= 48) and (c <= 57) then
      d := c - 48
    else if (c >= 65) and (c <= 70) then
      d := c - 55
    else
      Exit;
    V := V * 16 + d;
  end;
  Result := True;
end;

{ the text of one component of a glyph name }
function ComponentText(const C: string): string;
var
  at, e, v, i, n: Integer;
  list: string;
begin
  Result := '';
  if C = '' then
    Exit;
  at := Pos('|' + C + ';', GlyphList);
  if at > 0 then
  begin
    at := at + Length(C) + 2;
    while (at <= Length(GlyphList)) and (GlyphList[at] <> '|') do
    begin
      if GlyphList[at] = ' ' then
        at := at + 1
      else if HexRun(GlyphList, at, 4, v) then
      begin
        Result := Result + PdfRuneToUtf8(v);
        at := at + 4;
      end
      else
        Break;
    end;
    Exit;
  end;
  if (Length(C) >= 7) and (Copy(C, 1, 3) = 'uni') and ((Length(C) - 3) mod 4 = 0) then
  begin
    n := (Length(C) - 3) div 4;
    list := '';
    for i := 0 to n - 1 do
    begin
      if not HexRun(C, 4 + i * 4, 4, v) then
      begin
        list := '';
        Break;
      end;
      if (v >= $D800) and (v <= $DFFF) then
      begin
        list := '';
        Break;
      end;
      list := list + PdfRuneToUtf8(v);
    end;
    if list <> '' then
    begin
      Result := list;
      Exit;
    end;
  end;
  if (Length(C) >= 5) and (Length(C) <= 7) and (C[1] = 'u') then
  begin
    e := Length(C) - 1;
    if HexRun(C, 2, e, v) and (v <= $10FFFF) and not ((v >= $D800) and (v <= $DFFF)) then
      Result := PdfRuneToUtf8(v);
  end;
end;

function PdfGlyphText(const Name: string): string;
var
  nm: string;
  p, start, i: Integer;
begin
  Result := '';
  nm := Name;
  p := Pos('.', nm);
  if p = 1 then
    Exit;
  if p > 1 then
    nm := Copy(nm, 1, p - 1);
  start := 1;
  for i := 1 to Length(nm) + 1 do
    if (i > Length(nm)) or (nm[i] = '_') then
    begin
      Result := Result + ComponentText(Copy(nm, start, i - start));
      start := i + 1;
    end;
end;

end.
"""

if __name__ == '__main__':
    if not (os.path.exists(SPEC) and os.path.exists(AGL)):
        # docs/ref is not part of a clone: the check has nothing to read
        print('gen_pdfenc.py: docs/ref/pdf is not here, nothing to check')
        sys.exit(0 if '--check' in sys.argv else 1)
    text = build()
    if '--check' in sys.argv:
        if open(OUT).read() != text:
            sys.exit('scripts/gen_pdfenc.py: src/lib/paspdfenc.paslang is not what the generator writes')
        print('paspdfenc.paslang is the generator\'s')
    else:
        open(OUT, 'w').write(text)
        print('wrote', OUT, len(text), 'bytes')
