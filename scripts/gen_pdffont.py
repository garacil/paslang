#!/usr/bin/env python3
"""Writes testdata/pdffont.txt: the PDF files the paspdf font test reads, each
with the text it must give. They are files whose fonts carry no map to text
(no ToUnicode, no Encoding, no Widths) and the reader has to know what the
font itself says (P495): the 14 standard fonts with Adobe's widths and their
own encodings, Symbol and ZapfDingbats with the built-in encodings of the AFM
files. The files are built here byte by byte; fixed seed, no clock.

    python3 scripts/gen_pdffont.py [--check | --verify]

--check writes nothing and fails when testdata/pdffont.txt is not what this
makes (make check). --verify checks every file with qpdf --check and compares
the text with pdftotext's, ligatures normalized (neither tool is needed
anywhere else)."""
import base64
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_pdfafm as A  # noqa: E402
import gen_pdf_tests as G  # noqa: E402

ROOT = G.ROOT
OUT = os.path.join(ROOT, 'testdata', 'pdffont.txt')

# the published tree has no docs/ref: nothing to read the AFM files from, and
# testdata/pdffont.txt is what make check uses
if __name__ == '__main__' and not (os.path.isdir(A.AFMDIR) and os.path.exists(A.E.SPEC) and os.path.exists(A.E.AGL)
                                   and os.path.exists(A.ZAPF)):
    print('gen_pdffont.py: docs/ref/pdf is not here, nothing to check')
    sys.exit(0 if '--check' in sys.argv else 1)
CASES = []   # (name, kind, pdf bytes, expected bytes, valid, compare with pdftotext)

TABS = None


def widths():
    global TABS
    if TABS is None:
        TABS, _ = A.width_tables()
    return TABS


STD = {name: i for i, (name, _) in enumerate(A.FONTS)}
ENC = {'Standard': 0, 'MacRoman': 1, 'WinAnsi': 2}


def width_of(font, enc, data):
    """the width of a byte string in thousandths, from the AFM files"""
    t = widths()[STD[font]][ENC[enc]]
    return sum(t[b] for b in data)


def case(name, kind, pdf, expect, valid=True, cmp=True):
    CASES.append((name, kind, pdf, expect.encode('utf-8') if isinstance(expect, str) else expect, valid, cmp))


def txt(*pages):
    return ''.join(pg + '\n\f' for pg in pages)


def std_font(p, base, extra=''):
    """a standard font as a producer may leave it: no Widths, no map"""
    return p.add('<< /Type /Font /Subtype /Type1 /BaseFont /%s %s >>' % (base, extra))


def page(fonts, content, p):
    return G.one_page(content, fonts, p=p)


def show(font, size, x, y, data):
    """a string at x, y"""
    s = data.replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)')
    return b'BT /%s %s Tf %s %s Td (%s) Tj ET ' % (font.encode(), str(size).encode(), ('%.3f' % x).encode(), str(y).encode(), s)


# ---------------------------------------------------------------------------
# 1. the standard fonts with no Widths: the next word begins where the AFM
# width of this one says it ends. With every glyph taken as 500 thousandths
# the first pair would be joined (the guessed end of "Hello" is 2.7 units past
# the real one) and the second would be split (the guessed end of "WWWW" is
# 21 units short).
p = G.Pdf()
fh = std_font(p, 'Helvetica')
ft = std_font(p, 'Times-Roman')
fc = std_font(p, 'Courier')
fb = std_font(p, 'Helvetica-Bold')
c = b''
size = 12
x0 = 72
for i, (font, base, a, b, sep) in enumerate([
        ('H', 'Helvetica', b'Hello', b'World', b' '),
        ('H', 'Helvetica', b'WWWW', b'MMMM', b''),
        ('T', 'Times-Roman', b'Illinois', b'Wisconsin', b' '),
        ('T', 'Times-Roman', b'mmmm', b'wwww', b''),
        ('C', 'Courier', b'Hello', b'World', b' '),
        ('B', 'Helvetica-Bold', b'Total', b'1.234,56', b' '),
        ('B', 'Helvetica-Bold', b'MMMM', b'WWWW', b'')]):
    y = 720 - 20 * i
    w = width_of(base, 'Standard', a) * size / 1000.0
    ws = width_of(base, 'Standard', sep) * size / 1000.0
    c += show(font, size, x0, y, a)
    c += show(font, size, x0 + w + ws, y, b)
lines = ['Hello World', 'WWWWMMMM', 'Illinois Wisconsin', 'mmmmwwww', 'Hello World', 'Total 1.234,56', 'MMMMWWWW']
p, root = page({'H': fh, 'T': ft, 'C': fc, 'B': fb}, c, p)
case('std_widths', 'text', p.build(root), txt('\n'.join(lines)))

# the same by the aliases a producer writes for them and with a subset prefix
p = G.Pdf()
fa = std_font(p, 'Arial,Bold')
fn = std_font(p, 'TimesNewRoman')
fk = std_font(p, 'CourierNew')
c = b''
for i, (font, base, a, b, sep) in enumerate([
        ('A', 'Helvetica-Bold', b'Hello', b'World', b' '),
        ('N', 'Times-Roman', b'WWWW', b'MMMM', b''),
        ('K', 'Courier', b'Hello', b'World', b' ')]):
    y = 720 - 20 * i
    w = width_of(base, 'Standard', a) * size / 1000.0
    ws = width_of(base, 'Standard', sep) * size / 1000.0
    c += show(font, size, x0, y, a) + show(font, size, x0 + w + ws, y, b)
p, root = page({'A': fa, 'N': fn, 'K': fk}, c, p)
case('std_aliases', 'text', p.build(root), txt('Hello World\nWWWWMMMM\nHello World'))

# a Widths array wins over the AFM files: the same strings with every width 500
p = G.Pdf()
ws500 = ' '.join(['500'] * 224)
fh = std_font(p, 'Helvetica', '/FirstChar 32 /LastChar 255 /Widths [%s]' % ws500)
c = show('H', size, x0, 720, b'WWWW') + show('H', size, x0 + 4 * 500 * size / 1000.0, 720, b'MMMM')
p, root = page({'H': fh}, c, p)
case('std_widths_given', 'text', p.build(root), txt('WWWWMMMM'))

# Differences name glyphs, and the width follows the name: the codes 65 and 66
# are the glyphs i and l (222 thousandths each), not the A and B (667) the AFM
# file has there; the next string begins a space (3.5 units) after them, which
# the widths of A and B (or the guess of 500) would make no gap at all
p = G.Pdf()
fh = std_font(p, 'Helvetica', '/Encoding << /Type /Encoding /Differences [65 /i /l] >>')
w1 = (222 + 222) * size / 1000.0
c = show('H', size, x0, 720, b'AB') + show('H', size, x0 + w1 + 3.5, 720, b'CD')
p, root = page({'H': fh}, c, p)
case('std_differences_widths', 'text', p.build(root), txt('il CD'))

# a standard text font flagged symbolic with no Encoding is in StandardEncoding,
# whose 0x27 is the right single quote, 0x60 the left one, 0xAE and 0xAF the
# fi and fl ligatures
p = G.Pdf()
desc = p.add('<< /Type /FontDescriptor /FontName /Times-Roman /Flags 4 /FontBBox [-168 -218 1000 898] /ItalicAngle 0 /Ascent 683 /Descent -217 /CapHeight 662 /StemV 84 >>')
ft = std_font(p, 'Times-Roman', '/FontDescriptor %d 0 R' % desc)
c = show('T', size, x0, 720, b"it" + b"\x27" + b"s \x60quoted\x27 \xaeve \xafag")
p, root = page({'T': ft}, c, p)
case('std_symbolic_flag', 'text', p.build(root), txt('it’s ‘quoted’ five flag'.replace('five', 'five')), cmp=False)

# ---------------------------------------------------------------------------
# 2. Symbol and ZapfDingbats: the codes of their own encodings
sym = {}
for l in open(os.path.join(A.AFMDIR, 'psyr.afm'), encoding='latin-1'):
    m = re.match(r'C (\d+) ; WX (\d+) ; N (\S+) ;', l)
    if m:
        sym[int(m.group(1))] = (int(m.group(2)), m.group(3))
agl, _ = A.E.read_agl()

p = G.Pdf()
fs = std_font(p, 'Symbol')
# "abgd" are the Greek letters alpha, beta, gamma, delta; 0x70 pi; 0xA5 the
# infinity; 0xB1 plus-minus; 0xE5 summation; 0xF2 integral
codes = b'abgd p \xa5 \xb1 \xe5 \xf2'
text = ''.join(chr(agl[sym[b][1]][0]) if b in sym else ' ' for b in codes)
assert text == '\u03b1\u03b2\u03b3\u03b4 \u03c0 \u221e \u00b1 \u2211 \u222b', text
w = sum(sym[b][0] for b in codes) * size / 1000.0
c = show('S', size, x0, 720, codes)
# the next word begins at the end of the first by the AFM widths: joined
c += show('S', size, x0 + w, 720, b'ab')
# four summation signs (713 each) and the next string where they end: with a
# width of 500 each the guessed end is 10 units short and a space is read
wide = sym[0xe5][0] * 4 * size / 1000.0
c += show('S', size, x0, 700, b'\xe5\xe5\xe5\xe5') + show('S', size, x0 + wide, 700, b'ab')
p, root = page({'S': fs}, c, p)
case('symbol_builtin', 'text', p.build(root), txt(text + '\u03b1\u03b2\n\u2211\u2211\u2211\u2211\u03b1\u03b2'))

# Symbol with a named Encoding (9.6.6.1: "if different from its built-in
# encoding") is read by that encoding, as pdftotext reads it
p = G.Pdf()
fs = std_font(p, 'Symbol', '/Encoding /WinAnsiEncoding')
p, root = page({'S': fs}, show('S', size, x0, 720, b'abg'), p)
case('symbol_winansi', 'text', p.build(root), txt('abg'))

# Differences on Symbol name glyphs of the Adobe Glyph List
p = G.Pdf()
fs = std_font(p, 'Symbol', '/Encoding << /Type /Encoding /Differences [65 /omega /Omega /summation] >>')
p, root = page({'S': fs}, show('S', size, x0, 720, b'ABC a'), p)
case('symbol_differences', 'text', p.build(root), txt(chr(agl['omega'][0]) + chr(agl['Omega'][0]) + chr(agl['summation'][0]) + ' ' + chr(agl['alpha'][0])))

zap = {}
for l in open(os.path.join(A.AFMDIR, 'pzdr.afm'), encoding='latin-1'):
    m = re.match(r'C (\d+) ; WX (\d+) ; N (\S+) ;', l)
    if m:
        zap[int(m.group(1))] = (int(m.group(2)), m.group(3))
zl = A.read_zapf()
p = G.Pdf()
fz = std_font(p, 'ZapfDingbats')
codes = b'!"#4lnuv\xa1\xa8\xfe'
ztext = ''.join(chr(zl[zap[b][1]][0]) for b in codes)
c = show('Z', size, x0, 720, codes)
# four a1 (974 each) and the next glyph where they end
wide = zap[33][0] * 4 * size / 1000.0
c += show('Z', size, x0, 700, b'!!!!') + show('Z', size, x0 + wide, 700, b'"')
p, root = page({'Z': fz}, c, p)
case('zapf_builtin', 'text', p.build(root), txt(ztext + '\n' + chr(zl['a1'][0]) * 4 + chr(zl['a2'][0])))

# Differences on ZapfDingbats use its names a1 to a206
p = G.Pdf()
fz = std_font(p, 'ZapfDingbats', '/Encoding << /Type /Encoding /Differences [65 /a1 /a2 /a100] >>')
p, root = page({'Z': fz}, show('Z', size, x0, 720, b'ABC'), p)
case('zapf_differences', 'text', p.build(root), txt(chr(zl['a1'][0]) + chr(zl['a2'][0]) + chr(zl['a100'][0])))

# a1 in another font is only a name the Adobe Glyph List has not: the code is
# read as the character it would be (as pdftotext reads it), not as a dingbat
p = G.Pdf()
fh = std_font(p, 'Helvetica', '/Encoding << /Type /Encoding /Differences [65 /a1 /B] >>')
p, root = page({'H': fh}, show('H', size, x0, 720, b'xABy'), p)
case('other_a1_is_a_name', 'text', p.build(root), txt('xABy'))


# every code of the two fonts' own encodings, one string each on a grid: the
# text is the scalar the Adobe Glyph List (and its ZapfDingbats list) gives
# for the name the AFM file has at the code
for fontname, afm, table in (('Symbol', 'psyr', agl), ('ZapfDingbats', 'pzdr', zl)):
    codes = []
    for l in open(os.path.join(A.AFMDIR, afm + '.afm'), encoding='latin-1'):
        m = re.match(r'C (\d+) ; WX (\d+) ; N (\S+) ;', l)
        if m and int(m.group(1)) > 32:
            codes.append((int(m.group(1)), m.group(3)))
    p = G.Pdf()
    f = std_font(p, fontname)
    c = b''
    rows = []
    for i, (code, nm) in enumerate(codes):
        c += show('F', 10, 72 + (i % 10) * 40, 780 - (i // 10) * 14, bytes([code]))
        if i % 10 == 0:
            rows.append([])
        rows[-1].append(chr(table[nm][0]))
    p, root = page({'F': f}, c, p)
    case(fontname.lower().replace('dingbats', '') + '_all', 'text', p.build(root), txt('\n'.join(' '.join(r) for r in rows)))


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
            a = re.findall(r'\S+', unicodedata.normalize('NFKC', t))
            b = re.findall(r'\S+', unicodedata.normalize('NFKC', expect.decode('utf-8')))
            if cmp and a != b:
                bad += 1
                print('pdftotext differs on', name)
                print('  pdftotext:', ' '.join(a)[:160])
                print('  expected :', ' '.join(b)[:160])
    print('verified', len(CASES), 'files, differ', bad)
    return bad


if __name__ == '__main__':
    if '--verify' in sys.argv:
        sys.exit(1 if verify() else 0)
    text = write_corpus()
    if '--check' in sys.argv:
        if not os.path.exists(OUT) or open(OUT).read() != text:
            sys.exit('scripts/gen_pdffont.py: testdata/pdffont.txt is not what the generator writes')
        print('pdffont.txt is the generator\'s,', len(CASES), 'cases')
    else:
        open(OUT, 'w').write(text)
        print('wrote', OUT, len(CASES), 'cases')
