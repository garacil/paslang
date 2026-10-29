#!/usr/bin/env python3
"""Writes testdata/pdftext.txt: the PDF files the paspdf test reads, each with
the text it must give. The files are built here by hand, byte by byte, so
every structure paspdf reads (cross-reference tables and streams, object
streams, the filters, the fonts' encodings and maps, forms, incremental
updates, damage) is exercised from a file whose content is known. Fixed
seed, no clock: the file is the same each time.

    python3 scripts/gen_pdf_tests.py [--check | --verify]

--check writes nothing and fails when testdata/pdftext.txt is not what this
makes (make check). --verify checks every file that is meant to be valid with
qpdf --check and compares the text with pdftotext, ligatures normalized (the
two tools are not needed anywhere else); a file where the two differ on
purpose (spacing from a character space, a font with no map) is left out of
the comparison. The files in testdata/pdfreal were made by other programs
(cairo, Skia, LibreOffice, Ghostscript, groff, librsvg) from invented text and
are kept as they came; their .txt is the text paspdf gives, checked by
--verify against pdftotext."""
import base64
import os
import random
import re
import struct
import subprocess
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'testdata', 'pdftext.txt')

CASES = []   # (name, kind, pdf bytes, expected bytes, valid)


def esc(s):
    return s.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


class Pdf:
    """objects numbered from 1; build() writes a classic table"""

    def __init__(self):
        self.bodies = {}
        self.next = 1

    def reserve(self):
        n = self.next
        self.next += 1
        return n

    def put(self, n, body):
        self.bodies[n] = body if isinstance(body, bytes) else body.encode('latin-1')

    def add(self, body):
        n = self.reserve()
        self.put(n, body)
        return n

    def stream(self, dict_extra, data, flate=False, n=None):
        if n is None:
            n = self.reserve()
        d = dict_extra
        if flate:
            data = zlib.compress(data, 9)
            d += ' /Filter /FlateDecode'
        self.put(n, ('<< %s /Length %d >>\nstream\n' % (d, len(data))).encode('latin-1') + data + b'\nendstream')
        return n

    def build(self, root, header=b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n', info=None):
        out = bytearray(header)
        offs = {}
        for n in sorted(self.bodies):
            offs[n] = len(out)
            out += b'%d 0 obj\n' % n + self.bodies[n] + b'\nendobj\n'
        xr = len(out)
        size = max(self.bodies) + 1
        out += b'xref\n0 %d\n' % size
        out += b'0000000000 65535 f \n'
        for n in range(1, size):
            if n in offs:
                out += b'%010d 00000 n \n' % offs[n]
            else:
                out += b'0000000000 00000 f \n'
        out += b'trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (size, root, xr)
        return bytes(out)


def font_simple(p, name='Helv', enc='/Encoding /WinAnsiEncoding', extra='', widths=600, base='Helvetica'):
    """a Type1 font with every width 600 so the geometry is exact"""
    ws = ' '.join([str(widths)] * 224)
    return p.add('<< /Type /Font /Subtype /Type1 /BaseFont /%s %s /FirstChar 32 /LastChar 255 /Widths [%s] %s >>' % (base, enc, ws, extra))


def one_page(content, fonts, extra_res='', mediabox='[0 0 612 792]', flate=False, p=None):
    """a document with one page and these fonts {name: object number}; returns (pdf bytes)"""
    p = p or Pdf()
    cont = p.stream('', content if isinstance(content, bytes) else content.encode('latin-1'), flate=flate)
    pages = p.reserve()
    page = p.add('<< /Type /Page /Parent %d 0 R /MediaBox %s /Contents %d 0 R /Resources << /Font << %s >> %s >> >>' % (pages, mediabox, cont, ' '.join('/%s %d 0 R' % (k, v) for k, v in fonts.items()), extra_res))
    p.put(pages, '<< /Type /Pages /Kids [%d 0 R] /Count 1 >>' % page)
    root = p.add('<< /Type /Catalog /Pages %d 0 R >>' % pages)
    return p, root


def case(name, kind, pdf, expect, valid=True, cmp=True):
    CASES.append((name, kind, pdf, expect.encode('utf-8') if isinstance(expect, str) else expect, valid, cmp))


def txt(*pages):
    return ''.join(pg + '\n\f' for pg in pages)


# ---------------------------------------------------------------------------
# 1. the simple page, the text operators
p = Pdf()
f = font_simple(p)
c = 'BT /Helv 12 Tf 72 700 Td (Line one) Tj 0 -14 Td (Line two) Tj 0 -14 Td (Line three) Tj ET'
p, root = one_page(c, {'Helv': f}, p=p)
case('basic', 'text', p.build(root), txt('Line one\nLine two\nLine three'))

p = Pdf()
f = font_simple(p)
c = ('BT /Helv 10 Tf 14 TL 72 700 Td (A first) Tj T* (second by T star) Tj (third by quote) \' '
     '3 1 (fourth with spacing) " ET '
     'BT /Helv 10 Tf 1 0 0 1 300 500 Tm (placed by Tm) Tj ET '
     'q 1 0 0 1 100 400 cm BT /Helv 10 Tf 0 0 Td (moved by cm) Tj ET Q '
     'BT /Helv 10 Tf 72 300 Td 0 -12 TD (by TD) Tj T* (and T star after TD) Tj ET')
p, root = one_page(c, {'Helv': f}, p=p)
case('operators', 'text', p.build(root), txt('A first\nsecond by T star\nthird by quote\nfourth with spacing\nplaced by Tm\nmoved by cm\nby TD\nand T star after TD'))

# spacing: kerning in TJ, adjacent shows, gaps between shows
p = Pdf()
f = font_simple(p)
c = ('BT /Helv 10 Tf 72 700 Td [(Hel) -20 (lo) -300 (World)] TJ ET '
     'BT /Helv 10 Tf 72 680 Td (Hello) Tj (World) Tj ET '
     'BT /Helv 10 Tf 72 660 Td (Hello) Tj 40 0 Td (World) Tj ET '
     'BT /Helv 10 Tf 72 640 Td (Hello) Tj 30 0 Td (World) Tj ET '
     'BT /Helv 10 Tf 72 620 Td 5 Tc (AB) Tj 0 Tc ( ) Tj (CD) Tj ET '
     'BT /Helv 10 Tf 72 600 Td 50 Tz (half) Tj 100 Tz ( full) Tj ET')
p, root = one_page(c, {'Helv': f}, p=p)
case('spacing', 'text', p.build(root), txt('Hello World\nHelloWorld\nHello World\nHelloWorld\nAB CD\nhalf full'), cmp=False)

# 'Hello' is 5 glyphs of 600: 30 units at size 10; Td 40 leaves a gap of 10 (> 1.5): a space;
# Td 30 leaves none: joined.

# rotated text, text rendering mode 3 (invisible), a rise
p = Pdf()
f = font_simple(p)
c = ('BT /Helv 12 Tf 72 700 Td (horizontal first) Tj ET '
     'BT /Helv 12 Tf 0 1 -1 0 300 300 Tm (upward) Tj ET '
     'BT /Helv 12 Tf 3 Tr 72 680 Td (invisible but text) Tj ET '
     'BT /Helv 12 Tf 72 660 Td (base) Tj 5 Ts (up) Tj 0 Ts (base) Tj ET')
p, root = one_page(c, {'Helv': f}, p=p)
case('rotated', 'text', p.build(root), txt('horizontal first\ninvisible but text\nbaseupbase\nupward'))

# strings: escapes, octal, hex, nested parentheses, line continuation
p = Pdf()
f = font_simple(p)
c = ('BT /Helv 12 Tf 72 700 Td (nested (parens) and \\(escaped\\)) Tj ET '
     'BT /Helv 12 Tf 72 680 Td (octal \\101\\102\\103 and \\n newline-free) Tj ET '
     'BT /Helv 12 Tf 72 660 Td <48656C6C6F20686578> Tj ET '
     'BT /Helv 12 Tf 72 640 Td <48656C6C6F2> Tj ET '
     'BT /Helv 12 Tf 72 620 Td (joined \\\nby backslash) Tj ET')
p, root = one_page(c, {'Helv': f}, p=p)
case('strings', 'text', p.build(root), txt('nested (parens) and (escaped)\noctal ABC and  newline-free\nHello hex\nHello \njoined by backslash'))


# ---------------------------------------------------------------------------
# 2. encodings of simple fonts
def tounicode_stream(p, body):
    return p.stream('', body.encode('latin-1'), flate=True)


p = Pdf()
fw = font_simple(p, 'W', '/Encoding /WinAnsiEncoding')
fm = font_simple(p, 'M', '/Encoding /MacRomanEncoding')
fs = font_simple(p, 'S', '/Encoding /StandardEncoding')
fd = font_simple(p, 'D', '/Encoding << /Type /Encoding /BaseEncoding /WinAnsiEncoding /Differences [65 /Euro /uni00E9 /f_i /ffi /fl /u1F600 /nonexistentglyph /A.sc 100 /eacute /Aacute] >>')
fn = font_simple(p, 'N', '')
wb = b'win: \x80 \xe9 \xfc \x93q\x94 \x96'
mb = b'mac: \x8e \x9f \xd2q\xd3 \xd0'
c = (b'BT /W 12 Tf 72 700 Td (' + wb + b') Tj ET '
     b'BT /M 12 Tf 72 680 Td (' + mb + b') Tj ET '
     b'BT /S 12 Tf 72 660 Td (std: \xae \xaf \xc1) Tj ET '
     b'BT /D 12 Tf 72 640 Td (x: ABCDEFGH defg) Tj ET '
     b'BT /N 12 Tf 72 620 Td (none: plain) Tj ET')
p, root = one_page(c, {'W': fw, 'M': fm, 'S': fs, 'D': fd, 'N': fn}, p=p)
case('encodings', 'text', p.build(root), txt(wb.decode('cp1252') + '\n' + mb.decode('mac_roman') + '\nstd: fi fl `\nx: €éfiffifl\U0001F600GA éÁfg\nnone: plain'))


# a ToUnicode CMap on a simple font: single codes, ranges, a range with an
# array, a multi-character target, a surrogate pair
p = Pdf()
tu = tounicode_stream(p, """/CIDInit /ProcSet findresource begin 12 dict begin begincmap
/CMapName /Adobe-Identity-UCS def /CMapType 2 def
1 begincodespacerange <00> <FF> endcodespacerange
3 beginbfchar
<01> <0048>
<02> <00650073>
<03> <D83DDE00>
endbfchar
3 beginbfrange
<10> <19> <0030>
<20> <22> [<0058> <0059> <005A>]
<30> <32> <03B1>
endbfrange
endcmap CMapName currentdict /CMap defineresource pop end end""")
f = p.add('<< /Type /Font /Subtype /TrueType /BaseFont /Sub+Font /FirstChar 0 /LastChar 255 /Widths [%s] /ToUnicode %d 0 R >>' % (' '.join(['600'] * 256), tu))
c = b'BT /F 12 Tf 72 700 Td <010203101112131415161718192021223031' + b'32> Tj ET'
p, root = one_page(c, {'F': f}, p=p)
case('tounicode', 'text', p.build(root), txt('Hes\U0001F6000123456789XYZ\u03b1\u03b2\u03b3'))

# a Type0 font with Identity-H, a W array in both forms, a ToUnicode
p = Pdf()
tu = tounicode_stream(p, """/CIDInit /ProcSet findresource begin 12 dict begin begincmap
1 begincodespacerange <0000> <FFFF> endcodespacerange
4 beginbfchar
<0001> <0050>
<0002> <0061>
<0003> <0073>
<0004> <0020>
endbfchar
1 beginbfrange
<0010> <0013> <0041>
endbfrange
endcmap end end""")
desc = p.add('<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Sub+CID /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /DW 1000 /W [1 [600 600 600 300] 16 19 600] /CIDToGIDMap /Identity >>')
f = p.add('<< /Type /Font /Subtype /Type0 /BaseFont /Sub+CID /Encoding /Identity-H /DescendantFonts [%d 0 R] /ToUnicode %d 0 R >>' % (desc, tu))
c = b'BT /F 12 Tf 72 700 Td <0001000200030003000400100011001200130001> Tj ET BT /F 12 Tf 72 680 Td [<00010002> -400 <0003>] TJ ET'
p, root = one_page(c, {'F': f}, p=p)
case('type0', 'text', p.build(root), txt('Pass ABCDP\nPa s'))

# a Type0 font with an embedded CMap of mixed code lengths: one byte 00-7F, two bytes 8000-FFFF
p = Pdf()
cm = p.stream('/Type /CMap /CMapName /Test /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >>', b"""/CIDInit /ProcSet findresource begin 12 dict begin begincmap
/CMapName /Test def
2 begincodespacerange
<00> <7F>
<8000> <FFFF>
endcodespacerange
2 begincidrange
<41> <5A> 1
<8001> <8003> 100
endcidrange
endcmap end end""")
tu = tounicode_stream(p, """begincmap
2 begincodespacerange
<00> <7F>
<8000> <FFFF>
endcodespacerange
1 beginbfrange
<41> <5A> <0041>
endbfrange
3 beginbfchar
<8001> <00E9>
<8002> <00FC>
<8003> <20AC>
endbfchar
endcmap""")
desc = p.add('<< /Type /Font /Subtype /CIDFontType0 /BaseFont /Mixed /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /DW 600 >>')
f = p.add('<< /Type /Font /Subtype /Type0 /BaseFont /Mixed /Encoding %d 0 R /DescendantFonts [%d 0 R] /ToUnicode %d 0 R >>' % (cm, desc, tu))
c = b'BT /F 12 Tf 72 700 Td (AB\x80\x01C\x80\x02\x80\x03D) Tj ET'
p, root = one_page(c, {'F': f}, p=p)
case('type0mixed', 'text', p.build(root), txt('AB\u00e9C\u00fc\u20acD'))

# predefined Unicode CMaps: UniJIS-UCS2-H as two-byte Unicode
p = Pdf()
desc = p.add('<< /Type /Font /Subtype /CIDFontType0 /BaseFont /KozMinPro-Regular /CIDSystemInfo << /Registry (Adobe) /Ordering (Japan1) /Supplement 4 >> /DW 1000 >>')
f = p.add('<< /Type /Font /Subtype /Type0 /BaseFont /KozMinPro-Regular /Encoding /UniJIS-UCS2-H /DescendantFonts [%d 0 R] >>' % desc)
c = b'BT /F 12 Tf 72 700 Td <00480069306F4E16754C> Tj ET'
p, root = one_page(c, {'F': f}, p=p)
case('ucs2', 'text', p.build(root), txt('Hi\u306f\u4e16\u754c'), cmp=False)

# a font whose codes have no map: the replacement character
p = Pdf()
desc = p.add('<< /Type /Font /Subtype /CIDFontType2 /BaseFont /NoMap /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /DW 500 >>')
f = p.add('<< /Type /Font /Subtype /Type0 /BaseFont /NoMap /Encoding /Identity-H /DescendantFonts [%d 0 R] >>' % desc)
c = b'BT /F 12 Tf 72 700 Td <00010002> Tj ET'
p, root = one_page(c, {'F': f}, p=p)
case('nomap', 'text', p.build(root), txt('\ufffd\ufffd'), cmp=False)

# form XObjects: a matrix, a nested form, the form's own resources, a loop
p = Pdf()
f = font_simple(p)
inner = p.stream('/Type /XObject /Subtype /Form /BBox [0 0 200 50] /Matrix [1 0 0 1 0 -20] /Resources << /Font << /Helv %d 0 R >> >>' % f, b'BT /Helv 12 Tf 0 0 Td (inner form) Tj ET')
outer_n = p.reserve()
p.stream('/Type /XObject /Subtype /Form /BBox [0 0 300 100] /Matrix [1 0 0 1 0 0] /Resources << /Font << /Helv %d 0 R >> /XObject << /In %d 0 R /Self %d 0 R >> >>' % (f, inner, outer_n), b'BT /Helv 12 Tf 0 0 Td (outer form) Tj ET q 1 0 0 1 0 -15 cm /In Do Q /Self Do', n=outer_n)
c = b'BT /Helv 12 Tf 72 700 Td (page text) Tj ET q 1 0 0 1 72 600 cm /Out Do Q'
p, root = one_page(c, {'Helv': f}, extra_res='/XObject << /Out %d 0 R >>' % outer_n, p=p)
case('forms', 'text', p.build(root), txt('page text\nouter form\ninner form'))

# an inline image whose data holds EI and text-like bytes
p = Pdf()
f = font_simple(p)
c = b'BT /Helv 12 Tf 72 700 Td (before) Tj ET q 20 0 0 20 72 650 cm BI /W 4 /H 2 /BPC 8 /CS /G ID \x00\x01EI \x02(fake)Tj\x03\xff\xfe\x80 EI Q BT /Helv 12 Tf 72 600 Td (after) Tj ET'
p, root = one_page(c, {'Helv': f}, p=p)
case('inlineimage', 'text', p.build(root), txt('before\nafter'))


# ---------------------------------------------------------------------------
# 3. the filters on a content stream
def lzw_encode(data, early=1):
    """PDF's LZW: MSB first, codes of 9 to 12 bits, clear 256, end 257"""
    out = bytearray()
    acc = 0
    nb = 0

    def put(code, width):
        nonlocal acc, nb
        acc = (acc << width) | code
        nb += width
        while nb >= 8:
            out.append((acc >> (nb - 8)) & 255)
            nb -= 8
        acc &= (1 << nb) - 1

    table = {bytes([i]): i for i in range(256)}
    nxt = 258
    width = 9
    put(256, width)
    w = b''
    for b in data:
        wc = w + bytes([b])
        if wc in table:
            w = wc
        else:
            put(table[w], width)
            table[wc] = nxt
            nxt += 1
            # the encoder is one entry ahead of the decoder: the width grows
            # when the table holds 511 (early change) entries
            if nxt + early > (1 << width) and width < 12:
                width += 1
            if nxt >= 4094:
                put(256, width)
                table = {bytes([i]): i for i in range(256)}
                nxt = 258
                width = 9
            w = bytes([b])
    if w:
        put(table[w], width)
    put(257, width)
    if nb:
        out.append((acc << (8 - nb)) & 255)
    return bytes(out)


def runlength_encode(data):
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        j = i
        while j + 1 < n and data[j + 1] == data[i] and j - i < 127:
            j += 1
        if j > i:
            out.append(257 - (j - i + 1))
            out.append(data[i])
            i = j + 1
        else:
            k = i
            while k + 1 < n and k - i < 127 and not (k + 2 < n and data[k + 1] == data[k + 2]):
                k += 1
            out.append(k - i)
            out += data[i:k + 1]
            i = k + 1
    out.append(128)
    return bytes(out)


def png_encode(data, columns, kinds=(0, 1, 2, 3, 4)):
    """PNG predictor rows (bytes per pixel 1), the filter of each row from kinds in turn"""
    rows = [data[i:i + columns] for i in range(0, len(data), columns)]
    out = bytearray()
    prev = bytes(columns)
    for r, row in enumerate(rows):
        row = row + bytes(columns - len(row))
        k = kinds[r % len(kinds)]
        out.append(k)
        for i, x in enumerate(row):
            a = row[i - 1] if i > 0 else 0
            b = prev[i]
            c = prev[i - 1] if i > 0 else 0
            if k == 0:
                v = x
            elif k == 1:
                v = x - a
            elif k == 2:
                v = x - b
            elif k == 3:
                v = x - ((a + b) // 2)
            else:
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                v = x - pr
            out.append(v & 255)
        prev = row
    return bytes(out)


def tiff_encode(data, columns):
    out = bytearray()
    for r in range(0, len(data), columns):
        row = data[r:r + columns]
        prev = 0
        for x in row:
            out.append((x - prev) & 255)
            prev = x
    return bytes(out)


CONTENT = b'BT /Helv 12 Tf 72 700 Td (filtered content one) Tj 0 -14 Td (filtered content two) Tj 0 -14 Td [(f)10(i)-5(l)(tered)-250(three)] TJ ET'
CONTENT_TEXT = txt('filtered content one\nfiltered content two\nfiltered three')


def filtered(name, filt, data, parms='', valid=True):
    p = Pdf()
    f = font_simple(p)
    cont = p.reserve()
    p.put(cont, ('<< /Filter %s %s /Length %d >>\nstream\n' % (filt, parms, len(data))).encode('latin-1') + data + b'\nendstream')
    pages = p.reserve()
    page = p.add('<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] /Contents %d 0 R /Resources << /Font << /Helv %d 0 R >> >> >>' % (pages, cont, f))
    p.put(pages, '<< /Type /Pages /Kids [%d 0 R] /Count 1 >>' % page)
    root = p.add('<< /Type /Catalog /Pages %d 0 R >>' % pages)
    case(name, 'text', p.build(root), CONTENT_TEXT, valid=valid)


filtered('f_hex', '/ASCIIHexDecode', CONTENT.hex().upper().encode() + b'>')
filtered('f_hex_ws', '/ASCIIHexDecode', b' '.join(CONTENT.hex().encode()[i:i + 6] for i in range(0, len(CONTENT) * 2, 6)) + b' >')
filtered('f_a85', '/ASCII85Decode', base64.a85encode(CONTENT) + b'~>')
filtered('f_a85_z', '/ASCII85Decode', base64.a85encode(CONTENT + bytes(8), adobe=False, foldspaces=False) + b'~>')
filtered('f_lzw', '/LZWDecode', lzw_encode(CONTENT))
filtered('f_lzw0', '/LZWDecode', lzw_encode(CONTENT, early=0), '/DecodeParms << /EarlyChange 0 >>')
filtered('f_rl', '/RunLengthDecode', runlength_encode(CONTENT))
filtered('f_flate', '/FlateDecode', zlib.compress(CONTENT, 9))
filtered('f_chain', '[/ASCII85Decode /FlateDecode]', base64.a85encode(zlib.compress(CONTENT, 9)) + b'~>')
filtered('f_png', '/FlateDecode', zlib.compress(png_encode(CONTENT, 16), 9), '/DecodeParms << /Predictor 15 /Columns 16 >>')
filtered('f_png_none', '/FlateDecode', zlib.compress(png_encode(CONTENT, 7, (0,)), 9), '/DecodeParms << /Predictor 10 /Columns 7 >>')
filtered('f_tiff', '/FlateDecode', zlib.compress(tiff_encode(CONTENT, 13), 9), '/DecodeParms << /Predictor 2 /Columns 13 >>')
filtered('f_lzw_png', '[/LZWDecode]', lzw_encode(png_encode(CONTENT, 20)), '/DecodeParms [<< /Predictor 12 /Columns 20 >>]')
# a long content stream: the LZW table fills and clears, the Flate blocks change
LONG = b'BT /Helv 8 Tf 20 100000 Td\n' + b''.join(b'(line number %04d of the long page with a few more words in it) Tj 0 -12 Td\n' % i for i in range(400)) + b'ET'
LONG_TEXT = txt('\n'.join('line number %04d of the long page with a few more words in it' % i for i in range(400)))
for nm, filt, dat, prm in (('f_long_lzw', '/LZWDecode', lzw_encode(LONG), ''), ('f_long_flate', '/FlateDecode', zlib.compress(LONG, 9), ''), ('f_long_a85', '/ASCII85Decode', base64.a85encode(LONG) + b'~>', ''), ('f_long_rl', '/RunLengthDecode', runlength_encode(LONG), '')):
    p = Pdf()
    f = font_simple(p)
    cont = p.reserve()
    p.put(cont, ('<< /Filter %s %s /Length %d >>\nstream\n' % (filt, prm, len(dat))).encode('latin-1') + dat + b'\nendstream')
    pages = p.reserve()
    page = p.add('<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] /Contents %d 0 R /Resources << /Font << /Helv %d 0 R >> >> >>' % (pages, cont, f))
    p.put(pages, '<< /Type /Pages /Kids [%d 0 R] /Count 1 >>' % page)
    root = p.add('<< /Type /Catalog /Pages %d 0 R >>' % pages)
    case(nm, 'text', p.build(root), LONG_TEXT, cmp=False)


# ---------------------------------------------------------------------------
# 4. the structure of the file
def base_doc(text_lines=('structure one', 'structure two'), fontname='Helv'):
    """(pdf object bodies as a Pdf, root number, expected text)"""
    p = Pdf()
    f = font_simple(p, fontname)
    c = ('BT /%s 12 Tf 72 700 Td ' % fontname) + ' 0 -14 Td '.join('(%s) Tj' % t for t in text_lines) + ' ET'
    p, root = one_page(c, {fontname: f}, p=p)
    return p, root, txt('\n'.join(text_lines))


def build_xrefstm(objs, root, objstm_members=(), predictor=True, hybrid=False, width=(1, 3, 1), extra_trailer=''):
    """a file with an xref stream; the objects in objstm_members live in an object stream"""
    out = bytearray(b'%PDF-1.5\n%\xe2\xe3\xcf\xd3\n')
    offs = {}
    inobj = {}
    members = [n for n in sorted(objs) if n in objstm_members]
    nxt = max(objs) + 1
    stmnum = nxt
    xrefnum = nxt + 1
    if members:
        hdr = b''
        body = b''
        for n in members:
            hdr += b'%d %d ' % (n, len(body))
            body += objs[n] + b'\n'
        first = len(hdr)
        data = zlib.compress(hdr + body, 9)
        objs = dict(objs)
        objs[stmnum] = ('<< /Type /ObjStm /N %d /First %d /Filter /FlateDecode /Length %d >>\nstream\n' % (len(members), first, len(data))).encode() + data + b'\nendstream'
        for i, n in enumerate(members):
            inobj[n] = (stmnum, i)
    for n in sorted(objs):
        if n in inobj:
            continue
        offs[n] = len(out)
        out += b'%d 0 obj\n' % n + objs[n] + b'\nendobj\n'
    xoff = len(out)
    size = xrefnum + 1
    rows = bytearray()
    w0, w1, w2 = width
    for n in range(size):
        if n == 0:
            t, a, b = 0, 0, 255
        elif n in inobj:
            t, a, b = 2, inobj[n][0], inobj[n][1]
        elif n == xrefnum:
            t, a, b = 1, xoff, 0
        elif n in offs:
            t, a, b = 1, offs[n], 0
        else:
            t, a, b = 0, 0, 0
        rows += t.to_bytes(w0, 'big') + a.to_bytes(w1, 'big') + b.to_bytes(w2, 'big')
    rowlen = w0 + w1 + w2
    if predictor:
        data = zlib.compress(png_encode(bytes(rows), rowlen, (2,)), 9)
        parms = '/Filter /FlateDecode /DecodeParms << /Predictor 12 /Columns %d >>' % rowlen
    else:
        data = zlib.compress(bytes(rows), 9)
        parms = '/Filter /FlateDecode'
    out += b'%d 0 obj\n<< /Type /XRef /Size %d /W [%d %d %d] /Root %d 0 R %s %s /Length %d >>\nstream\n' % (xrefnum, size, w0, w1, w2, root, extra_trailer.encode(), parms.encode(), len(data)) + data + b'\nendstream\nendobj\n'
    out += b'startxref\n%d\n%%%%EOF\n' % xoff
    return bytes(out)


p, root, want = base_doc()
case('xrefstm', 'text', build_xrefstm(p.bodies, root), want)
case('xrefstm_nopred', 'text', build_xrefstm(p.bodies, root, predictor=False, width=(1, 2, 1)), want)
case('objstm', 'text', build_xrefstm(p.bodies, root, objstm_members=[n for n in p.bodies if b'stream' not in p.bodies[n]]), want)
case('objstm_wide', 'text', build_xrefstm(p.bodies, root, objstm_members=[n for n in p.bodies if b'stream' not in p.bodies[n]], width=(2, 4, 2)), want)

# a hybrid file: the font is only in the xref stream; the table says it is free
def hybrid_file():
    p, root, want = base_doc()
    fontn = [n for n in p.bodies if b'/Type /Font' in p.bodies[n]][0]
    out = bytearray(b'%PDF-1.5\n%\xe2\xe3\xcf\xd3\n')
    offs = {}
    for n in sorted(p.bodies):
        if n == fontn:
            continue
        offs[n] = len(out)
        out += b'%d 0 obj\n' % n + p.bodies[n] + b'\nendobj\n'
    # the object stream holding the font
    stm = max(p.bodies) + 1
    xs = stm + 1
    body = p.bodies[fontn]
    hdr = b'%d 0 ' % fontn
    data = zlib.compress(hdr + body, 9)
    offs[stm] = len(out)
    out += b'%d 0 obj\n<< /Type /ObjStm /N 1 /First %d /Filter /FlateDecode /Length %d >>\nstream\n' % (stm, len(hdr), len(data)) + data + b'\nendstream\nendobj\n'
    # the table: the font is free, the stream numbers are in use
    size = xs + 1
    t0 = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % size
    for n in range(1, size):
        if n in offs:
            out += b'%010d 00000 n \n' % offs[n]
        else:
            out += b'0000000000 65535 f \n'
    # the xref stream with the font as a compressed object
    rows = bytearray()
    for n in range(size):
        if n == fontn:
            rows += bytes([2]) + stm.to_bytes(3, 'big') + bytes([0])
        else:
            rows += bytes([0, 0, 0, 0, 0])
    data2 = zlib.compress(bytes(rows), 9)
    xoff = len(out)
    # the trailer has XRefStm: that object is not in the table (the stream stands alone)
    out += b'%d 0 obj\n<< /Type /XRef /Size %d /W [1 3 1] /Filter /FlateDecode /Length %d >>\nstream\n' % (xs, size, len(data2)) + data2 + b'\nendstream\nendobj\n'
    out += b'trailer\n<< /Size %d /Root %d 0 R /XRefStm %d >>\nstartxref\n%d\n%%%%EOF\n' % (size, root, xoff, t0)
    return bytes(out), want


pdf, want = hybrid_file()
case('hybrid', 'text', pdf, want, valid=False)

# an incremental update: a new content stream and a new xref section with Prev
def updated_file():
    p, root, want = base_doc(('before the update', 'old second line'))
    base = p.build(root)
    cont = [n for n in p.bodies if b'BT' in p.bodies[n]][0]
    newc = b'BT /Helv 12 Tf 72 700 Td (after the update) Tj 0 -14 Td (new second line) Tj ET'
    body = ('<< /Length %d >>\nstream\n' % len(newc)).encode() + newc + b'\nendstream'
    prev = int(re.search(rb'startxref\n(\d+)', base).group(1))
    out = bytearray(base)
    off = len(out)
    out += b'%d 0 obj\n' % cont + body + b'\nendobj\n'
    x2 = len(out)
    size = max(p.bodies) + 1
    out += b'xref\n%d 1\n%010d 00000 n \ntrailer\n<< /Size %d /Root %d 0 R /Prev %d >>\nstartxref\n%d\n%%%%EOF\n' % (cont, off, size, root, prev, x2)
    return bytes(out)


case('incremental', 'text', updated_file(), txt('after the update\nnew second line'))

# the page tree: nested nodes, inherited resources, a loop, a node that is no page
p = Pdf()
f = font_simple(p)
c1 = p.stream('', b'BT /Helv 12 Tf 72 700 Td (first page) Tj ET')
c2 = p.stream('', b'BT /Helv 12 Tf 72 700 Td (second page) Tj ET')
c3 = p.stream('', b'BT /Helv 12 Tf 72 700 Td (third page) Tj ET')
root_pages = p.reserve()
mid = p.reserve()
leaf1 = p.add('<< /Type /Page /Parent %d 0 R /Contents %d 0 R >>' % (mid, c1))
leaf2 = p.add('<< /Type /Page /Parent %d 0 R /Contents %d 0 R /Resources << /Font << /Helv %d 0 R >> >> >>' % (mid, c2, f))
leaf3 = p.add('<< /Type /Page /Parent %d 0 R /Contents %d 0 R >>' % (root_pages, c3))
p.put(mid, '<< /Type /Pages /Parent %d 0 R /Kids [%d 0 R %d 0 R %d 0 R 99 0 R] /Count 2 >>' % (root_pages, leaf1, leaf2, mid))
p.put(root_pages, '<< /Type /Pages /Kids [%d 0 R %d 0 R %d 0 R] /Count 3 /Resources << /Font << /Helv %d 0 R >> >> >>' % (mid, leaf3, root_pages, f))
root = p.add('<< /Type /Catalog /Pages %d 0 R >>' % root_pages)
case('pagetree', 'text', p.build(root), txt('first page', 'second page', 'third page'), valid=False)

# contents as an array of streams
p = Pdf()
f = font_simple(p)
a = p.stream('', b'BT /Helv 12 Tf 72 700 Td (part one) Tj')
b = p.stream('', b'0 -14 Td (part two) Tj')
c = p.stream('', b'ET')
pages = p.reserve()
page = p.add('<< /Type /Page /Parent %d 0 R /Contents [%d 0 R %d 0 R %d 0 R] /Resources << /Font << /Helv %d 0 R >> >> >>' % (pages, a, b, c, f))
p.put(pages, '<< /Type /Pages /Kids [%d 0 R] /Count 1 >>' % page)
root = p.add('<< /Type /Catalog /Pages %d 0 R >>' % pages)
case('contents_array', 'text', p.build(root), txt('part one\npart two'))

# ---------------------------------------------------------------------------
# 5. damage
def basic_pdf():
    p, root, want = base_doc(('damage test line one', 'damage test line two'))
    return p, root, want


p, root, want = basic_pdf()
good = p.build(root)
xr = good.index(b'xref\n')
case('rebuild_noxref', 'text', good[:xr], want, valid=False)
case('rebuild_badstartxref', 'text', re.sub(rb'startxref\n\d+', b'startxref\n7', good), want, valid=False)
case('rebuild_nostartxref', 'text', good[:good.index(b'startxref')], want, valid=False)
case('rebuild_junk_front', 'text', b'JUNK' * 40 + good, want, valid=False)
case('rebuild_junk_back', 'text', good + b'\x00\x01garbage' * 4000, want, valid=False)
case('rebuild_badoffsets', 'text', re.sub(rb'(\d{10}) 00000 n', lambda m: b'%010d 00000 n' % (int(m.group(1)) + 5), good), want, valid=False)

# the trailer lost its Root: the catalog is found by its type
case('rebuild_noroot', 'text', good.replace(b'/Root', b'/Rooot'), want, valid=False)

# stream lengths wrong
def with_length(delta):
    out = bytearray()
    done = False
    d = good
    m = re.search(rb'/Length (\d+) >>\nstream', d)
    ln = int(m.group(1))
    return d[:m.start(1)] + (b'%d' % max(0, ln + delta)) + d[m.end(1):]


case('length_short', 'text', with_length(-5), want, valid=False)
case('length_long', 'text', with_length(7), want, valid=False)
case('length_zero', 'text', with_length(-10000), want, valid=False)
case('length_missing', 'text', re.sub(rb'/Length \d+ ', b'', good, count=1), want, valid=False)
case('no_endstream', 'text', good.replace(b'\nendstream', b'', 1), want, valid=False)
case('no_endobj', 'text', good.replace(b'\nendobj\n', b'\n', 1), want, valid=False)

# a Flate stream cut short: the text before the cut; a bad checksum: all of it
p2, root2, _ = base_doc(('flate line one', 'flate line two', 'flate line three', 'flate line four'))
p2 = Pdf()
f2 = font_simple(p2)
cdata = b'BT /Helv 12 Tf 72 700 Td ' + b' 0 -14 Td '.join(b'(flate line number %d which is long enough to matter) Tj' % i for i in range(1, 60)) + b' ET'
cz = zlib.compress(cdata, 9)
def flate_doc(z, ln=None):
    p = Pdf()
    f = font_simple(p)
    cont = p.reserve()
    p.put(cont, ('<< /Filter /FlateDecode /Length %d >>\nstream\n' % (ln if ln else len(z))).encode() + z + b'\nendstream')
    pages = p.reserve()
    page = p.add('<< /Type /Page /Parent %d 0 R /Contents %d 0 R /Resources << /Font << /Helv %d 0 R >> >> >>' % (pages, cont, f))
    p.put(pages, '<< /Type /Pages /Kids [%d 0 R] /Count 1 >>' % page)
    root = p.add('<< /Type /Catalog /Pages %d 0 R >>' % pages)
    return p.build(root)


all_lines = ['flate line number %d which is long enough to matter' % i for i in range(1, 60)]
case('flate_checksum', 'text', flate_doc(cz[:-4] + b'\x00\x00\x00\x00'), txt('\n'.join(all_lines)), valid=False)
case('flate_nochecksum', 'text', flate_doc(cz[:-4]), txt('\n'.join(all_lines)), valid=False)
case('flate_nozlibheader', 'text', flate_doc(cz[2:-4]), txt('\n'.join(all_lines)), valid=False)

# encryption and no PDF at all
case('encrypted', 'error', good.replace(b'/Root', b'/Encrypt << /Filter /Standard /V 1 /R 2 /O (x) /U (y) /P -4 >> /Root'), 'password', valid=False)
case('notpdf', 'error', b'hello, this is not a PDF file at all\n' * 20, 'not a PDF', valid=False)
case('empty', 'error', b'', 'not a PDF', valid=False)
case('headeronly', 'error', b'%PDF-1.4\n%%EOF\n', 'catalog', valid=False)


def real_samples():
    """the files other programs made (cairo, Skia, LibreOffice, Ghostscript,
    groff, librsvg), kept as they are in testdata/pdfreal with the text each
    gives, checked against pdftotext by --verify"""
    d = os.path.join(ROOT, 'testdata', 'pdfreal')
    if not os.path.isdir(d):
        return
    for fn in sorted(os.listdir(d)):
        if fn.endswith('.pdf'):
            pdf = open(os.path.join(d, fn), 'rb').read()
            exp = open(os.path.join(d, fn[:-4] + '.txt'), 'rb').read()
            CASES.append(('real_' + fn[:-4], 'text', pdf, exp, True, True))


def write_corpus():
    real_samples()
    lines = []
    for name, kind, pdf, expect, valid, cmp in CASES:
        lines.append('%s\t%s\t%s\t%s' % (name, kind, base64.b64encode(pdf).decode(), base64.b64encode(expect).decode()))
    return '\n'.join(lines) + '\n'


def verify():
    import tempfile
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
            import unicodedata
            a = re.findall(r'\S+', unicodedata.normalize('NFKC', t))
            b = re.findall(r'\S+', unicodedata.normalize('NFKC', expect.decode('utf-8')))
            if cmp and a != b:
                print('pdftotext differs on', name)
                print('  pdftotext:', ' '.join(a)[:160])
                print('  expected :', ' '.join(b)[:160])
    return bad


if __name__ == '__main__':
    if '--verify' in sys.argv:
        real_samples()
        sys.exit(1 if verify() else 0)
    text = write_corpus()
    if '--check' in sys.argv:
        if open(OUT).read() != text:
            sys.exit('scripts/gen_pdf_tests.py: testdata/pdftext.txt is not what the generator writes')
        print('pdftext.txt is the generator\'s,', len(CASES), 'cases')
    else:
        open(OUT, 'w').write(text)
        print('wrote', OUT, len(CASES), 'cases')
