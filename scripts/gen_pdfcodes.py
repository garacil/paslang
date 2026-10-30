#!/usr/bin/env python3
"""Writes testdata/pdfcodes.txt: the PDF files the paspdf code test reads, each
with the text it must give (P517). A simple font that is not embedded and has
no ToUnicode map says what its codes are by its Encoding, and where it has
none, by the kind of font; the codes 0x80 to 0xFF are where the encodings
differ and where a reader that takes the code for a Unicode scalar gets
control characters. One file for each case, a page of the 128 codes each in its
own string between two bars:

  TrueType, symbolic or not or no flags, no Encoding: WinAnsi (the Windows
    characters; the unused codes are bullets, Annex D.2's note), as pdftotext
    reads it whatever the flags say
  TrueType and Type1, WinAnsiEncoding
  TrueType and Type1, MacRomanEncoding: the table of the specification and the
    fifteen signs of Mac OS Roman it leaves out (as Python's mac_roman codec
    has them but for 0xBD, which the Adobe Glyph List names Omega, U+2126)
  Type1 not symbolic, no Encoding, and StandardEncoding: the Adobe table,
    nothing for the codes it leaves undefined
  Type1 symbolic and MMType1, no Encoding: nothing says what the codes are
    (pdftotext reads none; this reader the Windows characters, a guess)
  Differences naming a glyph the Adobe Glyph List has not: the code's own
    Latin-1 character, as it was

The expected text is made here from the tables of the specification
(scripts/gen_pdfenc.py reads them) and Python's codecs; fixed, no clock.

    python3 scripts/gen_pdfcodes.py [--check | --verify]

--check writes nothing and fails when testdata/pdfcodes.txt is not what this
makes (make check). --verify checks every file with qpdf --check and compares
the characters with pdftotext's, white space and the bars left out (the files
listed in KNOWN_DIFFERENT differ on purpose; neither tool is needed anywhere
else)."""
import base64
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_pdf_tests as G  # noqa: E402
import gen_pdfenc as E  # noqa: E402

ROOT = G.ROOT
OUT = os.path.join(ROOT, 'testdata', 'pdfcodes.txt')
if __name__ == '__main__' and not (os.path.exists(E.SPEC) and os.path.exists(E.AGL)):
    print('gen_pdfcodes.py: docs/ref/pdf is not here, nothing to check')
    sys.exit(0 if '--check' in sys.argv else 1)
CASES = []   # (name, kind, pdf bytes, expected bytes, valid, compare with pdftotext)
TABLES = E.read_tables(E.read_agl()[0])
STD, MAC, WIN = TABLES[0], TABLES[1], TABLES[2]
# the signs of Mac OS Roman that the specification's table lacks
MAC_SIGNS = {}
for c in range(0x80, 0x100):
    if MAC[c] < 0:
        u = ord(bytes([c]).decode('mac_roman'))
        MAC_SIGNS[c] = 0x2126 if c == 0xBD else u
assert sorted(MAC_SIGNS) == [0xAD, 0xB0, 0xB2, 0xB3, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xBD, 0xC3, 0xC5, 0xC6, 0xD7, 0xF0], sorted(MAC_SIGNS)
PER_ROW = 12
# the reader writes the ligatures of the tables as their letters (P476)
LIGATURES = {0xFB01: 'fi', 0xFB02: 'fl'}


def case(name, kind, pdf, expect, valid=True, cmp=True):
    CASES.append((name, kind, pdf, expect.encode('utf-8') if isinstance(expect, str) else expect, valid, cmp))


def txt(*pages):
    return ''.join(pg + '\n\f' for pg in pages)


def doc(subtype, flags, enc, widths=True):
    """a page that shows 0x80 to 0xFF, each code between bars, 12 to a row"""
    p = G.Pdf()
    desc = p.add('<< /Type /FontDescriptor /FontName /ABCDEF+Foo /Flags %d /ItalicAngle 0 /Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 /FontBBox [0 0 1000 1000] >>' % flags)
    ws = ' '.join(['600'] * 224)
    f = p.add('<< /Type /Font /Subtype /%s /BaseFont /ABCDEF+Foo /FirstChar 32 /LastChar 255 /Widths [%s] /FontDescriptor %d 0 R %s >>' % (subtype, ws, desc, enc))
    body = b''
    for c in range(0x80, 0x100):
        i = c - 0x80
        s = bytes([c]).replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)')
        body += b'BT /F 12 Tf %d %d Td (|%s|) Tj ET\n' % (30 + 40 * (i % PER_ROW), 760 - 14 * (i // PER_ROW), s)
    p, root = G.one_page(body, {'F': f}, p=p)
    return p.build(root)


def page_text(table, nothing=()):
    """the text of the page when code c gives chr(table[c]), or nothing"""
    rows = []
    for r in range(0, 128, PER_ROW):
        items = []
        for i in range(r, min(r + PER_ROW, 128)):
            c = 0x80 + i
            u = table(c)
            items.append('|%s|' % (LIGATURES.get(u) or (chr(u) if u >= 0 else '')))
        rows.append(' '.join(items))
    return txt('\n'.join(rows))


def win(c):
    return WIN[c]


def mac(c):
    return MAC[c] if MAC[c] >= 0 else MAC_SIGNS[c]


def std(c):
    return STD[c]


# ---------------------------------------------------------------------------
# 1. TrueType: no Encoding is WinAnsi, with the symbolic flag or without it
for flags, label in [(4, 'symbolic'), (32, 'nonsymbolic'), (0, 'noflags')]:
    case('tt_%s_none' % label, 'text', doc('TrueType', flags, ''), page_text(win))
# StandardEncoding is not an encoding of a TrueType font: it is read as if there were none
case('tt_standard_explicit', 'text', doc('TrueType', 32, '/Encoding /StandardEncoding'), page_text(win))
case('tt_winansi', 'text', doc('TrueType', 32, '/Encoding /WinAnsiEncoding'), page_text(win))
case('tt_symbolic_winansi', 'text', doc('TrueType', 4, '/Encoding /WinAnsiEncoding'), page_text(win))
for flags, label in [(4, 'symbolic'), (32, 'nonsymbolic')]:
    case('tt_%s_macroman' % label, 'text', doc('TrueType', flags, '/Encoding /MacRomanEncoding'), page_text(mac))
case('tt_encoding_dict', 'text',
     doc('TrueType', 4, '/Encoding << /Type /Encoding /BaseEncoding /MacRomanEncoding /Differences [173 /bullet] >>'),
     page_text(lambda c: 0x2022 if c == 173 else mac(c)))

# 2. Type1 and MMType1
case('t1_winansi', 'text', doc('Type1', 32, '/Encoding /WinAnsiEncoding'), page_text(win))
case('t1_macroman', 'text', doc('Type1', 32, '/Encoding /MacRomanEncoding'), page_text(mac))
case('t1_standard_explicit', 'text', doc('Type1', 32, '/Encoding /StandardEncoding'), page_text(std))
case('t1_nonsymbolic_none', 'text', doc('Type1', 32, ''), page_text(std))
case('mm1_nonsymbolic_none', 'text', doc('MMType1', 32, ''), page_text(std))
case('t1_noflags_none', 'text', doc('Type1', 0, ''), page_text(std))
# nothing says what the codes of a symbolic Type 1 font are: the Windows
# characters are a guess, pdftotext reads none of them
case('t1_symbolic_none', 'text', doc('Type1', 4, ''), page_text(win), cmp=False)
case('mm1_symbolic_none', 'text', doc('MMType1', 4, ''), page_text(win), cmp=False)

# 3. a Differences entry names the code: its name wins, an unknown name keeps the
# code's own character, as pdftotext does for the codes named (even in the
# control range); with a Differences array pdftotext reads the other codes the
# Standard table leaves undefined from a table of its own, which this reader
# does not
case('t1_differences_over_standard', 'text',
     doc('Type1', 32, '/Encoding << /Type /Encoding /BaseEncoding /StandardEncoding /Differences [130 /eacute 131 /Euro 132 /notaglyphname 200 /notaglyphname] >>'),
     page_text(lambda c: {130: 0xE9, 131: 0x20AC, 132: 0x84, 200: 0xC8}.get(c, std(c))), cmp=False)

KNOWN_DIFFERENT = ('t1_symbolic_none', 'mm1_symbolic_none', 't1_differences_over_standard')


def write_corpus():
    lines = []
    for name, kind, pdf, expect, valid, cmp in CASES:
        lines.append('%s\t%s\t%s\t%s' % (name, kind, base64.b64encode(pdf).decode(), base64.b64encode(expect).decode()))
    return '\n'.join(lines) + '\n'


def verify():
    import tempfile
    import unicodedata
    bad = 0
    d = tempfile.mkdtemp()
    for name, kind, pdf, expect, valid, cmp in CASES:
        fn = os.path.join(d, name + '.pdf')
        open(fn, 'wb').write(pdf)
        if valid and kind == 'text':
            q = subprocess.run(['qpdf', '--check', fn], capture_output=True, text=True)
            if q.returncode not in (0, 3):
                print('qpdf --check', name, q.stdout[-300:], q.stderr[-300:])
                bad += 1
            t = subprocess.run(['pdftotext', '-layout', fn, '-'], capture_output=True, text=True).stdout
            a = sorted(re.sub(r'[\s|]', '', unicodedata.normalize('NFKC', t)))
            b = sorted(re.sub(r'[\s|]', '', unicodedata.normalize('NFKC', expect.decode('utf-8'))))
            if cmp and a != b:
                bad += 1
                print('pdftotext differs on', name)
                print('  pdftotext:', ''.join(a)[:160])
                print('  expected :', ''.join(b)[:160])
            if not cmp and a == b:
                bad += 1
                print('pdftotext agrees on', name, 'which is listed as different')
    print('verified', len(CASES), 'files, differ', bad)
    return bad


if __name__ == '__main__':
    assert set(KNOWN_DIFFERENT) == {c[0] for c in CASES if not c[5]}
    if '--verify' in sys.argv:
        sys.exit(1 if verify() else 0)
    text = write_corpus()
    if '--check' in sys.argv:
        if not os.path.exists(OUT) or open(OUT).read() != text:
            sys.exit('scripts/gen_pdfcodes.py: testdata/pdfcodes.txt is not what the generator writes')
        print('pdfcodes.txt is the generator\'s,', len(CASES), 'cases')
    else:
        open(OUT, 'w').write(text)
        print('wrote', OUT, len(CASES), 'cases')
