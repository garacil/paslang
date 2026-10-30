#!/usr/bin/env python3
"""Writes src/lib/paspdfafm.paslang: the widths of the 14 standard PDF fonts
(Courier, Helvetica and Times in four styles each, Symbol, ZapfDingbats), for
laying text out in a form field or on a page without the fonts being in the
file, and for reading a file whose Widths array is absent (P437, P495).

    python3 scripts/gen_pdfafm.py [--check | --verify]

Reads Adobe's AFM files in docs/ref/pdf/afm and, for the glyph name of each
code of StandardEncoding, MacRomanEncoding and WinAnsiEncoding, annex D.2 of
ISO 32000-1 through gen_pdfenc.py. The AFM files are from 1990 and have no Euro
(added in PDF 1.3); its widths are 556 for Helvetica, 500 for Times and 600 for
Courier, as Ghostscript's metric-compatible fonts give them (--verify asks).
--check writes nothing and fails when the unit is not what this makes (make
check; without docs/ref it has nothing to read and passes); --verify compares
every width of every Latin font with what Ghostscript measures, when it is
there."""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_pdfenc as E  # noqa: E402

ROOT = E.ROOT
AFMDIR = os.path.join(ROOT, 'docs', 'ref', 'pdf', 'afm')
OUT = os.path.join(ROOT, 'src', 'lib', 'paspdfafm.paslang')

FONTS = [
    ('Courier', 'pcrr8a'), ('Courier-Bold', 'pcrb8a'), ('Courier-Oblique', 'pcrro8a'), ('Courier-BoldOblique', 'pcrbo8a'),
    ('Helvetica', 'phvr8a'), ('Helvetica-Bold', 'phvb8a'), ('Helvetica-Oblique', 'phvro8a'), ('Helvetica-BoldOblique', 'phvbo8a'),
    ('Times-Roman', 'ptmr8a'), ('Times-Bold', 'ptmb8a'), ('Times-Italic', 'ptmri8a'), ('Times-BoldItalic', 'ptmbi8a'),
    ('Symbol', 'psyr'), ('ZapfDingbats', 'pzdr'),
]
EURO = {'Courier': 600, 'Helvetica': 556, 'Times': 500}
ZAPF = os.path.join(E.ROOT, 'docs', 'ref', 'pdf', 'agl', 'zapfdingbats.txt')


def read_afm(fn):
    names = {}
    codes = {}
    head = {}
    for l in open(os.path.join(AFMDIR, fn + '.afm'), encoding='latin-1'):
        if l.startswith('C '):
            m = re.match(r'C (-?\d+) ; WX (\d+) ; N (\S+) ;', l)
            c, w, n = int(m.group(1)), int(m.group(2)), m.group(3)
            names[n] = w
            if c >= 0:
                codes[c] = w
        else:
            for k in ('FontName', 'Ascender', 'Descender', 'CapHeight', 'XHeight', 'ItalicAngle', 'FontBBox'):
                if l.startswith(k + ' '):
                    head[k] = l.split(None, 1)[1].strip()
    return names, codes, head


def read_zapf():
    """the names of the ZapfDingbats list (Adobe, with the Adobe Glyph List) and their scalars"""
    names = {}
    for line in open(ZAPF, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        n, u = line.strip().split(';')
        names[n] = [int(x, 16) for x in u.split()]
    return names


def glyph_tables():
    """every glyph name of the 14 AFM files, sorted; the width of each in each font (-1 where the
    font lacks it, the Euro as in euro()); the Unicode scalar of each name (the Adobe Glyph List,
    the ZapfDingbats list for a1 to a206, -1 where neither has it); and the built-in encoding of
    Symbol and ZapfDingbats, the scalar of each code"""
    agl, _ = E.read_agl()
    zapf = read_zapf()
    per = []
    codes = []
    for fontname, fn in FONTS:
        names, cs, _ = read_afm(fn)
        if fontname not in ('Symbol', 'ZapfDingbats'):
            names['Euro'] = euro(fontname)
        per.append(names)
    alln = sorted(set().union(*[set(n) for n in per]))
    gw = []
    for names in per:
        gw += [names.get(n, -1) for n in alln]
    gr = []
    for n in alln:
        u = zapf.get(n) or agl.get(n)
        gr.append(u[0] if u and len(u) == 1 else -1)
    enc = []
    for fontname, fn in FONTS[12:]:
        row = [-1] * 256
        for l in open(os.path.join(AFMDIR, fn + '.afm'), encoding='latin-1'):
            m = re.match(r'C (\d+) ; WX \d+ ; N (\S+) ;', l)
            if m:
                u = zapf.get(m.group(2)) or agl.get(m.group(2))
                assert u and len(u) == 1, (fontname, m.group(2))
                row[int(m.group(1))] = u[0]
        enc += row
    return alln, gw, gr, enc


def euro(fontname):
    for k, v in EURO.items():
        if fontname.startswith(k):
            return v
    raise KeyError(fontname)


def width_tables():
    """[font][enc][code] in thousandths, -1 where the encoding has no glyph; and the heads"""
    agl, _ = E.read_agl()
    enc = E.read_names(agl)[:3]
    tabs = []
    heads = []
    for fontname, fn in FONTS:
        names, codes, head = read_afm(fn)
        heads.append(head)
        rows = []
        for k in range(3):
            row = [-1] * 256
            if fontname in ('Symbol', 'ZapfDingbats'):
                for c, w in codes.items():
                    if c < 256:
                        row[c] = w
            else:
                for c, n in enc[k].items():
                    w = names.get(n)
                    if w is None and n == 'Euro':
                        w = euro(fontname)
                    assert w is not None, (fontname, n)
                    row[c] = w
                if k == 1:
                    row[0o312] = names['space']
                if k == 2:
                    row[0o240] = names['space']
                    row[0o255] = names['hyphen']
                    for c in range(0o41, 256):
                        if row[c] < 0:
                            row[c] = names['bullet']
            rows.append(row)
        tabs.append(rows)
    return tabs, heads


UNIT_PRE = '''{ This file is part of paslang.
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

{ The widths of the 14 standard PDF fonts (P437, P495). THIS UNIT IS WRITTEN
  BY scripts/gen_pdfafm.py: change the script and run it, make check runs it
  with --check.

  The numbers are the glyph widths of Adobe's AFM files of the 14 fonts
  (Copyright (c) 1985-1991 Adobe Systems Incorporated), in thousandths of the
  font size, for each code of StandardEncoding, MacRomanEncoding and
  WinAnsiEncoding (the glyph names of ISO 32000-1, annex D.2); Symbol and
  ZapfDingbats have their own encoding, the same in all three. The Euro, which
  the 1990 files lack, is 556, 500 and 600 for Helvetica, Times and Courier. A
  code with no glyph is -1. By the name of the glyph the widths are there too
  (a Differences array names glyphs), with the Unicode scalar of each name and
  the built-in encoding of Symbol and ZapfDingbats (P495). }
unit paspdfafm;

interface

const
  { the fonts PdfStdFont gives }
  sfCourier = 0;
  sfCourierBold = 1;
  sfCourierOblique = 2;
  sfCourierBoldOblique = 3;
  sfHelvetica = 4;
  sfHelveticaBold = 5;
  sfHelveticaOblique = 6;
  sfHelveticaBoldOblique = 7;
  sfTimesRoman = 8;
  sfTimesBold = 9;
  sfTimesItalic = 10;
  sfTimesBoldItalic = 11;
  sfSymbol = 12;
  sfZapfDingbats = 13;

{ which standard font a BaseFont name is, or -1: the 14 names, with the
  prefix a subset adds (ABCDEF+) taken off, and the names Arial, Times New
  Roman and Courier New go by, with their Bold, Italic and Oblique, spelled as
  PostScript names, TrueType family names or both }
function PdfStdFont(const BaseFont: string): Integer;

{ the PostScript name of a standard font }
function PdfStdName(Font: Integer): string;

{ the width of a code in thousandths of the size, -1 where the encoding has
  no glyph; Enc is peStandard, peMacRoman or peWinAnsi of paspdfenc (and
  ignored by Symbol and ZapfDingbats) }
function PdfStdWidth(Font, Enc, Code: Integer): Integer;

{ the width of a glyph by its name in the AFM file of the font, in
  thousandths of the size; -1 where the font has no glyph of the name. The
  Euro, which the 1990 files lack, is 556, 500 and 600 as for PdfStdWidth }
function PdfStdGlyphWidth(Font: Integer; const Name: string): Integer;

{ the Unicode scalar of a glyph name of the AFM files (the names of the Adobe
  Glyph List and of its ZapfDingbats list: alpha, a1), -1 for a name they do
  not have or that makes more than one character }
function PdfStdGlyphRune(const Name: string): Integer;

{ the Unicode scalar of a code in the built-in encoding of Symbol and
  ZapfDingbats (the fonts that have one of their own), -1 for another font or
  a code with no glyph }
function PdfStdRune(Font, Code: Integer): Integer;

{ the font's Ascender and Descender, and the corners of its FontBBox (K 0 to
  3), in thousandths }
function PdfStdAscender(Font: Integer): Integer;
function PdfStdDescender(Font: Integer): Integer;
function PdfStdBBox(Font, K: Integer): Integer;

implementation

const
'''

UNIT_POST = '''
function Lower(const S: string): string;
var
  i, c: Integer;
begin
  Result := S;
  for i := 1 to Length(Result) do
  begin
    c := Ord(Result[i]);
    if (c >= 65) and (c <= 90) then
      Result[i] := Chr(c + 32);
  end;
end;

{ the first W out of T }
procedure Drop(var T: string; const W: string);
var
  p: Integer;
begin
  p := Pos(W, T);
  if p > 0 then
    T := Copy(T, 1, p - 1) + Copy(T, p + Length(W), Length(T));
end;

function PdfStdName(Font: Integer): string;
begin
  if (Font < 0) or (Font > 13) then
    Result := ''
  else
    Result := Names[Font];
end;

function PdfStdFont(const BaseFont: string): Integer;
var
  s, t: string;
  i, fam: Integer;
  bold, ital: Boolean;
begin
  Result := -1;
  s := BaseFont;
  { the subset prefix: six capitals and a plus }
  if (Length(s) > 7) and (s[7] = '+') then
    s := Copy(s, 8, Length(s));
  t := '';
  for i := 1 to Length(s) do
    if (s[i] <> ' ') and (s[i] <> '-') and (s[i] <> ',') and (s[i] <> '_') then
      t := t + s[i];
  t := Lower(t);
  if t = 'symbol' then
  begin
    Result := sfSymbol;
    Exit;
  end;
  if t = 'zapfdingbats' then
  begin
    Result := sfZapfDingbats;
    Exit;
  end;
  fam := -1;
  if Copy(t, 1, 7) = 'courier' then
  begin
    fam := 0;
    t := Copy(t, 8, Length(t));
    if Copy(t, 1, 3) = 'new' then
      t := Copy(t, 4, Length(t));
  end
  else if Copy(t, 1, 9) = 'helvetica' then
  begin
    fam := 4;
    t := Copy(t, 10, Length(t));
  end
  else if Copy(t, 1, 5) = 'arial' then
  begin
    fam := 4;
    t := Copy(t, 6, Length(t));
  end
  else if Copy(t, 1, 5) = 'times' then
  begin
    fam := 8;
    t := Copy(t, 6, Length(t));
    if Copy(t, 1, 8) = 'newroman' then
      t := Copy(t, 9, Length(t));
    if Copy(t, 1, 2) = 'ps' then
      t := Copy(t, 3, Length(t));
  end;
  if fam < 0 then
    Exit;
  bold := Pos('bold', t) > 0;
  ital := (Pos('italic', t) > 0) or (Pos('oblique', t) > 0);
  { what is left after the style words must be nothing, or MT, or Roman }
  Drop(t, 'bold');
  Drop(t, 'italic');
  Drop(t, 'oblique');
  Drop(t, 'regular');
  Drop(t, 'roman');
  Drop(t, 'mt');
  if t <> '' then
    Exit;
  if fam = 8 then
  begin
    if bold and ital then
      Result := sfTimesBoldItalic
    else if bold then
      Result := sfTimesBold
    else if ital then
      Result := sfTimesItalic
    else
      Result := sfTimesRoman;
  end
  else
  begin
    Result := fam;
    if bold then
      Result := Result + 1;
    if ital then
      Result := Result + 2;
  end;
end;

function PdfStdWidth(Font, Enc, Code: Integer): Integer;
begin
  Result := -1;
  if (Font < 0) or (Font > 13) or (Code < 0) or (Code > 255) then
    Exit;
  if (Enc < 0) or (Enc > 2) then
    Enc := 2;
  Result := Widths[(Font * 3 + Enc) * 256 + Code];
end;

{ the index of a glyph name in GlyphNames, or -1: the number of bars before
  its own, less one }
function GlyphIndex(const Name: string): Integer;
var
  at, i: Integer;
begin
  Result := -1;
  if (Name = '') or (Pos('|', Name) > 0) then
    Exit;
  at := Pos('|' + Name + '|', GlyphNames);
  if at = 0 then
    Exit;
  Result := -1;
  for i := 1 to at do
    if GlyphNames[i] = '|' then
      Result := Result + 1;
end;

function PdfStdGlyphWidth(Font: Integer; const Name: string): Integer;
var
  k: Integer;
begin
  Result := -1;
  if (Font < 0) or (Font > 13) then
    Exit;
  k := GlyphIndex(Name);
  if k >= 0 then
    Result := GlyphWidth[Font * NGlyphs + k];
end;

function PdfStdGlyphRune(const Name: string): Integer;
var
  k: Integer;
begin
  Result := -1;
  k := GlyphIndex(Name);
  if k >= 0 then
    Result := GlyphRune[k];
end;

function PdfStdRune(Font, Code: Integer): Integer;
begin
  Result := -1;
  if (Font < 12) or (Font > 13) or (Code < 0) or (Code > 255) then
    Exit;
  Result := CodeRune[(Font - 12) * 256 + Code];
end;

function PdfStdAscender(Font: Integer): Integer;
begin
  if (Font < 0) or (Font > 13) then
    Result := 0
  else
    Result := Asc[Font];
end;

function PdfStdDescender(Font: Integer): Integer;
begin
  if (Font < 0) or (Font > 13) then
    Result := 0
  else
    Result := Desc[Font];
end;

function PdfStdBBox(Font, K: Integer): Integer;
begin
  if (Font < 0) or (Font > 13) or (K < 0) or (K > 3) then
    Result := 0
  else
    Result := BBox[Font * 4 + K];
end;

end.
'''


def build():
    tabs, heads = width_tables()
    out = [UNIT_PRE]
    names = [f for f, _ in FONTS]
    out.append('  Names: array[0..13] of string = (\n' + ',\n'.join("    '%s'" % n for n in names) + ');\n\n')
    flat = []
    for rows in tabs:
        for row in rows:
            flat += row
    lines = []
    for i in range(0, len(flat), 16):
        lines.append('    ' + ', '.join(str(v) for v in flat[i:i + 16]))
    out.append('  Widths: array[0..%d] of SmallInt = (\n%s);\n\n' % (len(flat) - 1, ',\n'.join(lines)))
    alln, gw, gr, enc = glyph_tables()
    out.append('  NGlyphs = %d;\n\n' % len(alln))
    packed = '|' + '|'.join(alln) + '|'
    chunks = []
    cur = ''
    for n in alln:
        cur += '|' + n
        if len(cur) > 90:
            chunks.append(cur)
            cur = ''
    cur += '|'
    chunks.append(cur)
    assert ''.join(chunks) == packed
    out.append('  { the glyph names of the 14 AFM files, sorted, between bars }\n  GlyphNames =\n    ' +
               " +\n    ".join("'" + c + "'" for c in chunks) + ';\n\n')
    lines = []
    for i in range(0, len(gw), 16):
        lines.append('    ' + ', '.join(str(v) for v in gw[i:i + 16]))
    out.append('  GlyphWidth: array[0..%d] of SmallInt = (\n%s);\n\n' % (len(gw) - 1, ',\n'.join(lines)))
    lines = []
    for i in range(0, len(gr), 16):
        lines.append('    ' + ', '.join(str(v) for v in gr[i:i + 16]))
    out.append('  GlyphRune: array[0..%d] of Integer = (\n%s);\n\n' % (len(gr) - 1, ',\n'.join(lines)))
    lines = []
    for i in range(0, len(enc), 16):
        lines.append('    ' + ', '.join(str(v) for v in enc[i:i + 16]))
    out.append('  CodeRune: array[0..%d] of Integer = (\n%s);\n\n' % (len(enc) - 1, ',\n'.join(lines)))
    out.append('  Asc: array[0..13] of SmallInt = (%s);\n' % ', '.join(h.get('Ascender', '0') for h in heads))
    out.append('  Desc: array[0..13] of SmallInt = (%s);\n' % ', '.join(h.get('Descender', '0') for h in heads))
    bb = []
    for h in heads:
        bb += h['FontBBox'].split()
    out.append('  BBox: array[0..%d] of SmallInt = (%s);\n' % (len(bb) - 1, ', '.join(bb)))
    return ''.join(out) + UNIT_POST


def verify():
    """every width of every Latin font against what Ghostscript measures"""
    tabs, _ = width_tables()
    agl, _ = E.read_agl()
    enc = E.read_names(agl)[:3]
    bad = 0
    n = 0
    for fi, (fontname, fn) in enumerate(FONTS[:12]):
        ps = []
        names = sorted(set(enc[0].values()) | set(enc[1].values()) | set(enc[2].values()))
        prog = '/%s findfont 1000 scalefont setfont\n' % fontname
        for nm in names:
            prog += 'newpath 0 0 moveto /%s glyphshow currentpoint pop (%s ) print = flush\n' % (nm, nm)
        import tempfile
        with tempfile.NamedTemporaryFile('w', suffix='.ps', delete=False) as tf:
            tf.write(prog + 'quit\n')
        r = subprocess.run(['gs', '-q', '-dNODISPLAY', '-dBATCH', '-dNOPAUSE', tf.name], capture_output=True, text=True)
        os.unlink(tf.name)
        got = {}
        for l in r.stdout.split('\n'):
            if ' ' in l:
                a, b = l.split(' ')[0], l.split(' ')[-1]
                try:
                    got[a] = float(b)
                except ValueError:
                    pass
        for k in range(3):
            for c, nm in enc[k].items():
                w = tabs[fi][k][c]
                if nm in got:
                    # Ghostscript's Helvetica-compatible fonts make the fraction bar
                    # 278 wide where Adobe's metrics say 167: Adobe's are the standard's
                    if nm == 'fraction' and fontname.startswith('Helvetica'):
                        continue
                    n += 1
                    if abs(got[nm] - w) > 0.51:
                        bad += 1
                        if bad < 20:
                            print('DIFF', fontname, nm, 'afm', w, 'gs', got[nm])
    print('compared', n, 'widths, differ', bad)
    return bad


if __name__ == '__main__':
    if not (os.path.isdir(AFMDIR) and os.path.exists(E.SPEC) and os.path.exists(E.AGL)):
        print('gen_pdfafm.py: docs/ref/pdf is not here, nothing to check')
        sys.exit(0 if '--check' in sys.argv else 1)
    if '--verify' in sys.argv:
        sys.exit(1 if verify() else 0)
    text = build()
    if '--check' in sys.argv:
        if open(OUT).read() != text:
            sys.exit('scripts/gen_pdfafm.py: src/lib/paspdfafm.paslang is not what the generator writes')
        print('paspdfafm.paslang is the generator\'s')
    else:
        open(OUT, 'w').write(text)
        print('wrote', OUT, len(text), 'bytes')
