#!/usr/bin/env python3
"""Writes testdata/pdffont.txt: the PDF files the paspdf font test reads, each
with the text it must give. They are files whose fonts carry no map to text
(no ToUnicode, no Encoding, no Widths) and the reader has to know what the
font itself says: the 14 standard fonts with Adobe's widths and their own
encodings, Symbol and ZapfDingbats with the built-in encodings of the AFM files
(P495), TrueType font programs (P512) and CFF and Type 1 ones (P513). The files
are built here byte by byte, but for two that other programs made
(testdata/pdfreal/edge.pdf, testdata/pdffontreal/gs-reencoded.pdf); fixed seed, no clock.

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
FONTS_REF = os.path.join(ROOT, 'docs', 'ref', 'pdf', 'fonts')
if __name__ == '__main__' and not (os.path.isdir(A.AFMDIR) and os.path.exists(A.E.SPEC) and os.path.exists(A.E.AGL)
                                   and os.path.exists(A.ZAPF) and os.path.exists(os.path.join(FONTS_REF, 'Chap6post.html'))
                                   and os.path.exists(os.path.join(FONTS_REF, '5176.CFF.txt'))):
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



# ---------------------------------------------------------------------------
# 3. TrueType font programs (P512). The fonts are made here: a unit square for
# each glyph, the tables a reader needs (head, hhea, maxp, hmtx, loca, glyf)
# and the cmap and post the case is about; nothing in them is anyone's design.
import struct  # noqa: E402


def mac_names():
    import gen_fontnames
    return gen_fontnames.mac_names()


def u16(v):
    return struct.pack('>H', v & 0xFFFF)


def u32(v):
    return struct.pack('>I', v & 0xFFFFFFFF)


def cmap_sub(fmt, mapping, ranges=False, reverse=False):
    """a cmap subtable from {code: glyph}; reverse puts the segments or groups in descending order, which the
    specification does not allow and a reader that enumerates them has to bear"""
    if fmt == 0:
        arr = bytearray(256)
        for c, g in mapping.items():
            arr[c] = g
        return u16(0) + u16(262) + u16(0) + bytes(arr)
    if fmt == 6:
        codes = sorted(mapping)
        first, last = codes[0], codes[-1]
        gl = b''.join(u16(mapping.get(c, 0)) for c in range(first, last + 1))
        return u16(6) + u16(10 + len(gl)) + u16(0) + u16(first) + u16(last - first + 1) + gl
    if fmt == 12:
        groups = []
        for c in sorted(mapping):
            if groups and c == groups[-1][1] + 1 and mapping[c] == groups[-1][2] + (c - groups[-1][0]):
                groups[-1][1] = c
            else:
                groups.append([c, c, mapping[c]])
        if reverse:
            groups.reverse()
        body = b''.join(u32(a) + u32(b) + u32(g) for a, b, g in groups)
        return u16(12) + u16(0) + u32(16 + len(body)) + u32(0) + u32(len(groups)) + body
    assert fmt == 4
    segs = []
    for c in sorted(mapping):
        if c > 0xFFFE:
            continue
        if segs and c == segs[-1][1] + 1 and mapping[c] - c == segs[-1][3]:
            segs[-1][1] = c
        else:
            segs.append([c, c, None, mapping[c] - c])
    if reverse:
        segs.reverse()
    glyph_array = []
    out = []
    n = len(segs) + 1
    # a segment that holds a single code or is not a run of one delta goes by the glyph array when `ranges`
    ro_list = []
    for i, (a, b, _, d) in enumerate(segs):
        if ranges and (i % 2 == 1):
            ro_list.append((len(glyph_array), a, b))
            for c in range(a, b + 1):
                glyph_array.append(mapping[c])
            out.append((a, b, 0))
        else:
            out.append((a, b, d))
    out.append((0xFFFF, 0xFFFF, 1))
    ends = b''.join(u16(b) for a, b, d in out)
    starts = b''.join(u16(a) for a, b, d in out)
    deltas = b''.join(u16(d) for a, b, d in out)
    offs = []
    k = 0
    for i, (a, b, d) in enumerate(out):
        if ranges and i < len(segs) and (i % 2 == 1):
            # from this idRangeOffset entry to the glyph array element
            idx = ro_list[k][0]
            k += 1
            offs.append(2 * (n - i) + 2 * idx)
        else:
            offs.append(0)
    ro = b''.join(u16(v) for v in offs)
    ga = b''.join(u16(v) for v in glyph_array)
    sr = 2 * (1 << (n.bit_length() - 1))
    body = (u16(2 * n) + u16(sr) + u16((n.bit_length() - 1)) + u16(2 * n - sr) + ends + u16(0) + starts + deltas + ro + ga)
    return u16(4) + u16(6 + len(body)) + u16(0) + body


def make_ttf(adv, cmaps=(), post=('v3',), scaler=0x00010000):
    """adv: the advance width of each glyph (glyph 0 first); cmaps: [(platform, encoding, subtable bytes)];
    post: ('v3',), ('v1',) or ('v2', [name of each glyph])"""
    n = len(adv)
    glyf = b''
    loca = [0]
    for i in range(n):
        if 2 <= i < 10:
            g = (u16(1) + u16(0) + u16(0) + u16(500) + u16(500) + u16(3) + u16(0) + bytes([1, 1, 1, 1]) +
                 u16(0) + u16(500) + u16(0) + u16(-500) + u16(0) + u16(0) + u16(500) + u16(0))
            g += b'\0' * (-len(g) % 4)
            glyf += g
        loca.append(len(glyf))
    head = (u32(0x00010000) + u32(0x00010000) + u32(0) + u32(0x5F0F3CF5) + u16(0) + u16(1000) + b'\0' * 16 +
            u16(0) + u16(0) + u16(500) + u16(500) + u16(0) + u16(8) + u16(2) + u16(1) + u16(0))
    hhea = (u32(0x00010000) + u16(900) + u16(-200) + u16(0) + u16(max(adv)) + u16(0) + u16(0) + u16(500) +
            u16(1) + u16(0) + u16(0) + b'\0' * 8 + u16(0) + u16(n))
    maxp = (u32(0x00010000) + u16(n) + u16(4) + u16(1) + u16(0) + u16(0) + u16(2) + u16(0) + u16(0) + u16(0) +
            u16(0) + u16(0) + u16(0) + u16(0) + u16(0))
    hmtx = b''.join(u16(a) + u16(0) for a in adv)
    locab = b''.join(u32(v) for v in loca)
    tables = {'glyf': glyf, 'head': head, 'hhea': hhea, 'hmtx': hmtx, 'loca': locab, 'maxp': maxp}
    if cmaps:
        recs = b''
        subs = b''
        base = 4 + 8 * len(cmaps)
        for plat, enc, sub in cmaps:
            recs += u16(plat) + u16(enc) + u32(base + len(subs))
            subs += sub + b'\0' * (-len(sub) % 2)
        tables['cmap'] = u16(0) + u16(len(cmaps)) + recs + subs
    if post[0] == 'v3':
        tables['post'] = u32(0x00030000) + b'\0' * 28
    elif post[0] == 'v1':
        tables['post'] = u32(0x00010000) + b'\0' * 28
    elif post[0] == 'v2':
        std = mac_names()
        idx = b''
        strs = b''
        k = 258
        for nm in post[1]:
            if nm in std:
                idx += u16(std.index(nm))
            else:
                idx += u16(k)
                k += 1
                strs += bytes([len(nm)]) + nm.encode('latin-1')
        tables['post'] = u32(0x00020000) + b'\0' * 28 + u16(len(post[1])) + idx + strs
    tags = sorted(tables)
    dirlen = 12 + 16 * len(tags)
    out = u32(scaler) + u16(len(tags)) + u16(0) + u16(0) + u16(0)
    body = b''
    for tg in tags:
        d = tables[tg]
        out += tg.encode() + u32(0) + u32(dirlen + len(body)) + u32(len(d))
        body += d + b'\0' * (-len(d) % 4)
    return out + body


def font_file(p, data, sub=None):
    """the stream of a TrueType program: stored, not compressed, so the bent copies bend it"""
    return p.stream('/Length1 %d' % len(data), data, flate=False)


def descriptor(p, ff, flags, name='AAAAAA+Toy'):
    return p.add('<< /Type /FontDescriptor /FontName /%s /Flags %d /FontBBox [0 0 1000 1000] /ItalicAngle 0 /Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 /FontFile2 %d 0 R >>' % (name, flags, ff))


def cid_font(p, data, togid='/Identity', name='AAAAAA+Toy'):
    ff = font_file(p, data)
    fd = descriptor(p, ff, 4, name)
    if togid != '/Identity':
        togid = '%d 0 R' % p.stream('', togid, flate=False)
    d = p.add('<< /Type /Font /Subtype /CIDFontType2 /BaseFont /%s /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor %d 0 R /DW 500 /CIDToGIDMap %s >>' % (name, fd, togid))
    return p.add('<< /Type /Font /Subtype /Type0 /BaseFont /%s /Encoding /Identity-H /DescendantFonts [%d 0 R] >>' % (name, d))


def simple_ttf(p, data, flags, enc='', name='AAAAAA+Toy'):
    ff = font_file(p, data)
    fd = descriptor(p, ff, flags, name)
    ws = ' '.join(['500'] * 224)
    return p.add('<< /Type /Font /Subtype /TrueType /BaseFont /%s %s /FirstChar 32 /LastChar 255 /Widths [%s] /FontDescriptor %d 0 R >>' % (name, enc, ws, fd))


def hexstr(gids):
    return b'<' + b''.join(b'%04X' % g for g in gids) + b'>'


def cid_page(p, fonts, content):
    p, root = G.one_page(content, fonts, p=p)
    return p.build(root)


# glyph ids as a real font has them: the printable ASCII from glyph 3, so a code is not its glyph
def ascii_glyphs(first=3):
    return {c: first + c - 32 for c in range(32, 127)}


ADV = [500] * 260

# 3.1 Identity-H, the Unicode subtable: delta form and glyph-array form both
asc = ascii_glyphs()
extra = {0x00E9: 200, 0x00F1: 201, 0x00FC: 202, 0x20AC: 203, 0x2013: 204, 0x00A0: 205}
um = dict(asc)
um.update(extra)
for form, rg in (('delta', False), ('ranges', True)):
    data = make_ttf(ADV, [(3, 1, cmap_sub(4, um, ranges=rg))])
    p = G.Pdf()
    f = cid_font(p, data)
    text = 'Total: 1.234,56 EUR – año ü € café'
    gl = [um[ord(ch)] for ch in text]
    c = b'BT /F 12 Tf 72 720 Td ' + hexstr(gl) + b' Tj ET'
    case('ttf_cid_unicode_' + form, 'text', cid_page(p, {'F': f}, c), txt(text), cmp=False)

# 3.2 a subtable of format 12 with characters past the BMP
um12 = dict(asc)
um12.update({0x1F600: 210, 0x10000: 211, 0x00E9: 200})
data = make_ttf(ADV, [(3, 10, cmap_sub(12, um12))])
p = G.Pdf()
f = cid_font(p, data)
text = 'ok \U0001F600 café \U00010000 end'
c = b'BT /F 12 Tf 72 720 Td ' + hexstr([um12[ord(ch)] for ch in text]) + b' Tj ET'
case('ttf_cid_cmap12', 'text', cid_page(p, {'F': f}, c), txt(text), cmp=False)

# 3.3 the Unicode platform (0,3) alone, and format 6
data = make_ttf(ADV, [(0, 3, cmap_sub(4, um))])
p = G.Pdf()
f = cid_font(p, data)
text = 'platform zero'
c = b'BT /F 12 Tf 72 720 Td ' + hexstr([um[ord(ch)] for ch in text]) + b' Tj ET'
case('ttf_cid_platform0', 'text', cid_page(p, {'F': f}, c), txt(text), cmp=False)
data = make_ttf(ADV, [(3, 1, cmap_sub(6, asc))])
p = G.Pdf()
f = cid_font(p, data)
text = 'format six'
c = b'BT /F 12 Tf 72 720 Td ' + hexstr([asc[ord(ch)] for ch in text]) + b' Tj ET'
case('ttf_cid_cmap6', 'text', cid_page(p, {'F': f}, c), txt(text), cmp=False)

# 3.4 no cmap: the names of `post`, format 2 with the font's own names and the Macintosh ones
names = ['.notdef', '.null', 'nonmarkingreturn', 'space', 'A', 'B', 'uni00E9', 'f_i', 'alpha', 'u1F600', 'glyph77']
data = make_ttf([500] * len(names), [], post=('v2', names))
p = G.Pdf()
f = cid_font(p, data)
c = b'BT /F 12 Tf 72 720 Td ' + hexstr([4, 5, 3, 6, 7, 8, 9, 10]) + b' Tj ET'
case('ttf_cid_post2', 'text', cid_page(p, {'F': f}, c), txt('AB éfiα\U0001F600�'), cmp=False)

# 3.5 post format 1: the 258 names of the Macintosh ordering, glyph 36 is A, 68 is a
std = mac_names()
data = make_ttf([500] * 258, [], post=('v1',))
p = G.Pdf()
f = cid_font(p, data)
text = 'ABC abc 123'
c = b'BT /F 12 Tf 72 720 Td ' + hexstr([std.index({' ': 'space', '1': 'one', '2': 'two', '3': 'three'}.get(ch, ch)) for ch in text]) + b' Tj ET'
case('ttf_cid_post1', 'text', cid_page(p, {'F': f}, c), txt(text), cmp=False)

# 3.6 a CIDToGIDMap stream: the CID is not the glyph
data = make_ttf(ADV, [(3, 1, cmap_sub(4, asc))])
perm = {i: (i * 7) % 90 + 3 for i in range(0, 90)}
perm_inv = {}
mp = bytearray(2 * 100)
text = 'mapped by stream'
cids = []
for k, ch in enumerate(text):
    g = asc[ord(ch)]
    cid = 10 + k
    mp[2 * cid:2 * cid + 2] = u16(g)
    cids.append(cid)
p = G.Pdf()
f = cid_font(p, data, togid=bytes(mp))
c = b'BT /F 12 Tf 72 720 Td ' + hexstr(cids) + b' Tj ET'
case('ttf_cid_cidtogid', 'text', cid_page(p, {'F': f}, c), txt(text), cmp=False)

# 3.7 the font says nothing: no cmap, post 3: U+FFFD for each, as before
data = make_ttf([500] * 20, [], post=('v3',))
p = G.Pdf()
f = cid_font(p, data)
c = b'BT /F 12 Tf 72 720 Td ' + hexstr([5, 6, 7]) + b' Tj ET'
case('ttf_cid_nothing', 'text', cid_page(p, {'F': f}, c), txt('���'), cmp=False)

# 3.8 two Unicode subtables: the better one decides where it has the glyph, the other fills
# in where it lacks it; of two codes for one glyph the lower is the text
bmp = dict(asc)
bmp[0x00A0] = 3             # a no-break space on the glyph of the space
bmp[0x2010] = asc[ord('-')]  # a hyphen on the glyph of the hyphen-minus
full = {0x0041: 40, 0x1F600: 41}   # glyph 40 is B in the BMP table and A here
bmp[ord('B')] = 40
bmp[0x00E9] = 99
data = make_ttf(ADV, [(3, 1, cmap_sub(4, bmp)), (3, 10, cmap_sub(12, full))])
p = G.Pdf()
f = cid_font(p, data)
c = b'BT /F 12 Tf 72 720 Td ' + hexstr([3, 40, 41, 99, asc[ord('-')], 42]) + b' Tj ET'
case('ttf_cid_preference', 'text', cid_page(p, {'F': f}, c), txt(' A\U0001F600é-' + chr(next(c2 for c2 in sorted(bmp) if bmp[c2] == 42))), cmp=False)

# 3.9 simple fonts, symbolic or with no Encoding: the code selects the glyph by (3,0) or (1,0)
alpha = {0x61: 20, 0x62: 21, 0x63: 22}
uni = {0x03B1: 20, 0x03B2: 21, 0x03B3: 22, 0x61: 30}
data = make_ttf(ADV, [(3, 0, cmap_sub(4, {0xF000 + c: g for c, g in alpha.items()})), (3, 1, cmap_sub(4, uni))])
p = G.Pdf()
f = simple_ttf(p, data, 4)
case('ttf_simple_symbolic_30', 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, b'abc')), txt('αβγ'), cmp=False)

# the ranges of (3,0): 0x0000 - 0x00FF, and 0xF100 - 0xF1FF
for nm, off in (('plain', 0), ('f1', 0xF100)):
    data = make_ttf(ADV, [(3, 0, cmap_sub(4, {off + c: g for c, g in alpha.items()})), (3, 1, cmap_sub(4, uni))])
    p = G.Pdf()
    f = simple_ttf(p, data, 4)
    case('ttf_simple_30_' + nm, 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, b'abc')), txt('αβγ'), cmp=False)

# (1,0) alone, the names of post saying what the glyphs are
names = ['.notdef', '.null'] + ['glyph%d' % i for i in range(2, 20)] + ['alpha', 'beta', 'uni00E9']
data = make_ttf([500] * len(names), [(1, 0, cmap_sub(0, {0x61: 20, 0x62: 21, 0x8E: 22}))], post=('v2', names))
p = G.Pdf()
f = simple_ttf(p, data, 4)
case('ttf_simple_symbolic_10', 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, b'ab\x8e')), txt('αβé'), cmp=False)

# no Encoding and not flagged symbolic: WinAnsi, as pdftotext reads it (the specification would have
# the font's (1,0) subtable decide, where 0x8E is e acute; a producer that leaves the Encoding out
# of a text font means WinAnsi more often than Mac OS Roman). 0x8E is Z caron in WinAnsi
mac = {0x8E: 50, 0x61: 51}
unim = {0x00E9: 50, 0x61: 51}
data = make_ttf(ADV, [(1, 0, cmap_sub(0, mac)), (3, 1, cmap_sub(4, unim))])
p = G.Pdf()
f = simple_ttf(p, data, 32)
case('ttf_simple_noenc_winansi', 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, b'a\x8e')), txt('a\u017d'))

# an Encoding the file names wins, symbolic flag or not: the names decide, the font is not asked
p = G.Pdf()
f = simple_ttf(p, data, 32, '/Encoding /WinAnsiEncoding')
case('ttf_simple_winansi', 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, b'a\x8e')), txt('a\u017d'))
p = G.Pdf()
f = simple_ttf(p, data, 4, '/Encoding /WinAnsiEncoding')
case('ttf_simple_symbolic_winansi', 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, b'a\x8e')), txt('a\u017d'))

# symbolic with Differences: the named codes keep their names, the others are the font's
data = make_ttf(ADV, [(3, 0, cmap_sub(4, {0xF000 + c: g for c, g in alpha.items()})), (3, 1, cmap_sub(4, uni))])
p = G.Pdf()
f = simple_ttf(p, data, 4, '/Encoding << /Type /Encoding /Differences [98 /Euro] >>')
case('ttf_simple_symbolic_diff', 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, b'abc')), txt('α€γ'), cmp=False)

# the glyph array form of format 4, format 6 for (1,0), format 12 for (3,0): the lookups of every format
# by the code of a simple font (the segment of abc is the second, so it goes by the glyph array)
rng = {0x41: 30, 0x61: 20, 0x62: 21, 0x63: 22}
data = make_ttf(ADV, [(3, 0, cmap_sub(4, {0xF000 + c: g for c, g in rng.items()}, ranges=True)), (3, 1, cmap_sub(4, uni))])
p = G.Pdf()
f = simple_ttf(p, data, 4)
case('ttf_simple_30_ranges', 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, b'abc')), txt('\u03b1\u03b2\u03b3'), cmp=False)
data = make_ttf(ADV, [(1, 0, cmap_sub(6, alpha)), (3, 1, cmap_sub(4, uni))])
p = G.Pdf()
f = simple_ttf(p, data, 4)
case('ttf_simple_10_fmt6', 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, b'abc')), txt('\u03b1\u03b2\u03b3'), cmp=False)
data = make_ttf(ADV, [(3, 0, cmap_sub(12, {0xF000 + c: g for c, g in alpha.items()})), (3, 1, cmap_sub(4, uni))])
p = G.Pdf()
f = simple_ttf(p, data, 4)
case('ttf_simple_30_fmt12', 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, b'abc')), txt('\u03b1\u03b2\u03b3'), cmp=False)

# the glyph 50 is A in (3,1) and B in (0,3): the Windows Unicode subtable is the better; 51 is only in (0,3)
data = make_ttf(ADV, [(0, 3, cmap_sub(4, {0x42: 50, 0x43: 51, 0x44: 52})), (3, 1, cmap_sub(4, {0x41: 50, 0x45: 52}))])
p = G.Pdf()
f = cid_font(p, data)
case('ttf_cid_rank_31_over_03', 'text', cid_page(p, {'F': f}, b'BT /F 12 Tf 72 720 Td ' + hexstr([50, 51, 52]) + b' Tj ET'), txt('ACE'), cmp=False)

# two codes for one glyph, the subtable's segments or groups in descending order: the lower code is the text
dups = {0x20: 3, 0xA0: 3, 0x2D: 4, 0x2010: 4, 0x2011: 4}
for fmt in (4, 12):
    data = make_ttf(ADV, [(3, 10 if fmt == 12 else 1, cmap_sub(fmt, dups, reverse=True))])
    p = G.Pdf()
    f = cid_font(p, data)
    case('ttf_cid_duplicates_fmt%d' % fmt, 'text', cid_page(p, {'F': f}, b'BT /F 12 Tf 72 720 Td ' + hexstr([3, 4, 3]) + b' Tj ET'), txt(' - '), cmp=False)

# 3.10 damaged programs: the directory cut, a table past the end, a cmap whose counts do not fit, a post
# with more names than it holds, no glyphs: the text is what it was without the font (U+FFFD for each
# glyph of a Type0 font), never a fault, and a damage in a table the text does not need changes nothing
goodc = make_ttf(ADV, [(3, 1, cmap_sub(4, um))])
goodp = make_ttf([500] * 5, [], post=('v2', ['.notdef', '.null', 'uni0061', 'uni0062', 'uni0063']))
goodm = make_ttf([500] * 5, [], post=('v2', ['.notdef', '.null', 'A', 'B', 'C']))


def bend(data, edits):
    b = bytearray(data)
    for pos, val in edits:
        b[pos:pos + len(val)] = val
    return bytes(b)


def table_at(data, tag):
    n = struct.unpack('>H', data[4:6])[0]
    for i in range(n):
        t, cs, off, ln = struct.unpack('>4sIII', data[12 + 16 * i:28 + 16 * i])
        if t == tag.encode():
            return 12 + 16 * i, off, ln
    raise KeyError(tag)


rec_cmap, off_cmap, len_cmap = table_at(goodc, 'cmap')
rec_maxp, off_maxp, len_maxp = table_at(goodc, 'maxp')
rec_head, off_head, len_head = table_at(goodc, 'head')
rec_glyf, off_glyf, len_glyf = table_at(goodc, 'glyf')
sub_off = off_cmap + struct.unpack('>I', goodc[off_cmap + 8:off_cmap + 12])[0]
rec_post, off_post, len_post = table_at(goodp, 'post')
rec_postm, off_postm, len_postm = table_at(goodm, 'post')
FF2 = '\ufffd\ufffd'
damaged = [
    ('cut', goodc[:60], FF2),
    ('cut_in_cmap', goodc[:off_cmap + 30], FF2),
    ('tables_zero', bend(goodc, [(4, u16(0))]), FF2),
    ('tables_many', bend(goodc, [(4, u16(60000))]), FF2),
    ('cmap_offset_past', bend(goodc, [(rec_cmap + 8, u32(0x7FFFFFF0))]), FF2),
    ('cmap_sub_offset_past', bend(goodc, [(off_cmap + 8, u32(0x7FFFFFF0))]), FF2),
    ('cmap_segcount_huge', bend(goodc, [(sub_off + 6, u16(0xFFFE))]), FF2),
    ('cmap_segcount_odd', bend(goodc, [(sub_off + 6, u16(7))]), FF2),
    ('cmap_format_unknown', bend(goodc, [(sub_off, u16(7))]), FF2),
    ('maxp_zero', bend(goodc, [(off_maxp + 4, u16(0))]), FF2),
    ('maxp_one', bend(goodc, [(off_maxp + 4, u16(1))]), FF2),
    ('scaler_wrong', bend(goodc, [(0, b'wOFF')]), FF2),
    # tables the text does not need
    ('head_zeroed', bend(goodc, [(off_head, b'\0' * 54)]), 'ab'),
    ('glyf_zeroed', bend(goodc, [(off_glyf, b'\0' * 64)]), 'ab'),
    # post: the intact one, the count of names past the table, a string whose length runs past the end,
    # a name index past the strings, a version that has no names
    ('post_intact', goodp, 'ab'),
    ('post_names_huge', bend(goodp, [(off_post + 32, u16(65535))]), FF2),
    ('post_string_long', bend(goodp, [(off_post + 34 + 2 * 5, b'\xFF')]), FF2),
    ('post_index_past', bend(goodp, [(off_post + 34 + 2 * 2, u16(60000))]), '\ufffdb'),
    ('post_version_25', bend(goodp, [(off_post, u32(0x00028000))]), FF2),
    # names that are all of the Macintosh set, so no string is read: the count still has to fit the table
    ('post_mac_intact', goodm, 'AB'),
    ('post_mac_count_huge', bend(goodm, [(off_postm + 32, u16(65535))]), FF2),
]
for nm, data, want in damaged:
    p = G.Pdf()
    f = cid_font(p, data)
    if nm.startswith('post'):
        c = b'BT /F 12 Tf 72 720 Td ' + hexstr([2, 3]) + b' Tj ET'
    else:
        c = b'BT /F 12 Tf 72 720 Td ' + hexstr([asc[ord('a')], asc[ord('b')]]) + b' Tj ET'
    case('ttf_bad_' + nm, 'text', cid_page(p, {'F': f}, c), txt(want), cmp=False)

# 3.11 a real program: the Chrome sample of testdata/pdfreal with the names of its ToUnicode maps
# changed to /Tounicode (the same length, so the table is still right): three CID TrueType
# subsets that keep the font's cmap, and nothing else to say what the glyphs are
rp = os.path.join(ROOT, 'testdata', 'pdfreal', 'edge.pdf')
if os.path.exists(rp):
    raw = open(rp, 'rb').read()
    assert raw.count(b'/ToUnicode') == 3
    want = open(os.path.join(ROOT, 'testdata', 'pdfreal', 'edge.txt'), 'rb').read()
    case('real_edge_nomap', 'text', raw.replace(b'/ToUnicode', b'/Tounicode'), want, cmp=False)



# ---------------------------------------------------------------------------
# 4. CFF and Type 1 font programs (P513). The CFF fonts are made here as the note
# (Adobe Technical Note 5176) lays them out: the header, the INDEXes, a top DICT
# whose offsets are 32-bit integers (so its size does not depend on them), the
# charset and the Encoding in the form the case is about, and a CharStrings
# INDEX of glyphs that are an endchar and nothing else.
STD_STRINGS = None


def cff_strings():
    global STD_STRINGS
    if STD_STRINGS is None:
        import gen_fontnames
        STD_STRINGS = gen_fontnames.cff_tables()
    return STD_STRINGS


def cff_index(items):
    if not items:
        return u16(0)
    offs = [1]
    for it in items:
        offs.append(offs[-1] + len(it))
    osz = 1 if offs[-1] < 256 else 2
    return u16(len(items)) + bytes([osz]) + b''.join(o.to_bytes(osz, 'big') for o in offs) + b''.join(items)


def dict_num(v):
    return b'\x1d' + struct.pack('>i', v)


def make_cff(glyphs, strings=(), charset='fmt0', encoding=None, cid=False, charset_at=None, enc_at=None, charset_format=None):
    """glyphs: the string id (the CID in a CID-keyed font) of glyphs 1..n, glyph 0 being .notdef;
    strings: the font's own strings (string id 391 on); charset: 'fmt0', 'fmt1', 'fmt2' or the number
    0, 1, 2 of a predefined one; encoding: None (the operator left out: Standard), 1 (Expert),
    ('fmt0', [code of glyph 1, code of glyph 2 ...]), ('fmt1', [(first, left), ...]) with
    supplements as a third item [(code, sid), ...]; cid: write a ROS operator;
    charset_at and enc_at write another offset in the top DICT (a damaged font), charset_format another
    first byte of the charset"""
    n = len(glyphs) + 1
    charset_data = b''
    if charset == 'fmt0':
        charset_data = b'\x00' + b''.join(u16(s) for s in glyphs)
    elif charset in ('fmt1', 'fmt2'):
        runs = []
        for s in glyphs:
            if runs and s == runs[-1][0] + runs[-1][1] + 1 and (charset == 'fmt2' or runs[-1][1] < 255):
                runs[-1][1] += 1
            else:
                runs.append([s, 0])
        if charset == 'fmt1':
            charset_data = b'\x01' + b''.join(u16(a) + bytes([b]) for a, b in runs)
        else:
            charset_data = b'\x02' + b''.join(u16(a) + u16(b) for a, b in runs)
    enc_data = b''
    if isinstance(encoding, tuple):
        kind = encoding[0]
        sup = encoding[2] if len(encoding) > 2 else []
        if kind == 'fmt0':
            enc_data = bytes([0x80 if sup else 0, len(encoding[1])]) + bytes(encoding[1])
        else:
            enc_data = bytes([0x81 if sup else 1, len(encoding[1])]) + b''.join(bytes([a, b]) for a, b in encoding[1])
        if sup:
            enc_data += bytes([len(sup)]) + b''.join(bytes([c]) + u16(s) for c, s in sup)
    if charset_format is not None:
        charset_data = bytes([charset_format]) + charset_data[1:]
    cs = cff_index([b'\x0e'] * n)
    header = bytes([1, 0, 4, 1])
    name = cff_index([b'Toy'])
    strs = cff_index([s.encode('latin-1') for s in strings])
    gsub = cff_index([])
    private = b''

    def top(off_charset, off_enc, off_cs, off_priv):
        d = b''
        if cid:
            d += dict_num(391) + dict_num(392) + dict_num(0) + b'\x0c\x1e'    # ROS
        if isinstance(charset, str):
            d += dict_num(off_charset) + b'\x0f'
        elif charset in (1, 2):
            d += dict_num(charset) + b'\x0f'
        if isinstance(encoding, tuple):
            d += dict_num(off_enc) + b'\x10'
        elif encoding == 1:
            d += dict_num(1) + b'\x10'
        d += dict_num(off_cs) + b'\x11'
        d += dict_num(0) + dict_num(off_priv) + b'\x12'
        return d
    topsize = len(cff_index([top(0, 0, 0, 0)]))
    base = len(header) + len(name) + topsize + len(strs) + len(gsub)
    off_charset = base
    off_enc = off_charset + len(charset_data)
    off_cs = off_enc + len(enc_data)
    off_priv = off_cs + len(cs)
    topd = cff_index([top(off_charset if charset_at is None else charset_at, off_enc if enc_at is None else enc_at, off_cs, off_priv)])
    assert len(topd) == topsize
    return header + name + topd + strs + gsub + charset_data + enc_data + cs


def cff_font_file(p, data, sub):
    return p.stream('/Subtype /%s /Length1 %d' % (sub, len(data)), data, flate=False)


def cff_desc(p, ff, flags, name='AAAAAA+Toy'):
    return p.add('<< /Type /FontDescriptor /FontName /%s /Flags %d /FontBBox [0 0 1000 1000] /ItalicAngle 0 /Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 /FontFile3 %d 0 R >>' % (name, flags, ff))


def simple_cff(p, data, flags, enc='', sub='Type1C', name='AAAAAA+Toy'):
    ff = cff_font_file(p, data, sub)
    fd = cff_desc(p, ff, flags, name)
    ws = ' '.join(['500'] * 224)
    return p.add('<< /Type /Font /Subtype /Type1 /BaseFont /%s %s /FirstChar 32 /LastChar 255 /Widths [%s] /FontDescriptor %d 0 R >>' % (name, enc, ws, fd))


def cid_cff(p, data, sub='CIDFontType0C', cidtype='CIDFontType0', name='AAAAAA+Toy'):
    ff = cff_font_file(p, data, sub)
    fd = cff_desc(p, ff, 4, name)
    d = p.add('<< /Type /Font /Subtype /%s /BaseFont /%s /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor %d 0 R /DW 500 >>' % (cidtype, name, fd))
    return p.add('<< /Type /Font /Subtype /Type0 /BaseFont /%s /Encoding /Identity-H /DescendantFonts [%d 0 R] >>' % (name, d))


def sid(name):
    return cff_strings()[0].index(name)


aglc, _ = A.E.read_agl()


def ch(name):
    return chr(aglc[name][0])


# 4.1 the built-in encoding of a simple font: format 0, format 1, with supplements
names3 = ['alpha', 'beta', 'gamma']
g3 = [391, 392, 393]     # glyph names the standard strings do not have are the font's own strings
text3 = ''.join(ch(x) for x in names3)
for nm, enc, flags in (
        ('fmt0', ('fmt0', [0x61, 0x62, 0x63]), 4),
        ('fmt1', ('fmt1', [(0x61, 2)]), 4),
        ('fmt1_runs', ('fmt1', [(0x61, 0), (0x62, 0), (0x63, 0)]), 4),
        ('sup', ('fmt0', [0x61, 0x62], [(0x63, 393)]), 4),
        ('nonsymbolic', ('fmt0', [0x61, 0x62, 0x63]), 32)):
    data = make_cff(g3, names3, 'fmt0', enc)
    p = G.Pdf()
    f = simple_cff(p, data, flags)
    case('cff_simple_enc_' + nm, 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, b'abc')), txt(text3), cmp=False)

# 4.2 the encoding left out is StandardEncoding, whatever the flags: 0xAE is the fi ligature there
std_names = ['A', 'B', 'fi', 'quoteright', 'quoteleft', 'Lslash']
std_codes = [0x41, 0x42, 0xAE, 0x27, 0x60, 0xE8]
data = make_cff([sid(x) for x in std_names], [], 'fmt0', None)
p = G.Pdf()
f = simple_cff(p, data, 4)
case('cff_simple_standard', 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, bytes(std_codes))), txt('ABﬁ’‘Ł'.replace('ﬁ', 'fi')), cmp=False)

# 4.3 the Expert encoding (an encoding of the note's Appendix B) and the predefined charsets
exp_names = ['exclamsmall', 'commasuperior', 'zerooldstyle', 'onequarter']
ecodes = {}
for c in range(256):
    s_ = cff_strings()[1][1][c]
    if s_:
        ecodes.setdefault(cff_strings()[0][s_], c)
data = make_cff([sid(x) for x in exp_names], [], 'fmt0', 1)
p = G.Pdf()
f = simple_cff(p, data, 4)
case('cff_simple_expert', 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, bytes(ecodes[x] for x in exp_names))), txt(''.join(ch(x) for x in exp_names)), cmp=False)
# charset 0 (ISOAdobe: glyph n is string id n), charset 1 (Expert), charset 2 (ExpertSubset), each with an encoding of format 0
for k, nm in ((0, 'isoadobe'), (1, 'expert'), (2, 'expertsubset')):
    tab = cff_strings()[2][k]
    glyph_sids = tab[1:5]
    gl = [cff_strings()[0][s_] for s_ in glyph_sids]
    data = make_cff(glyph_sids, [], k, ('fmt0', [0x61, 0x62, 0x63, 0x64]))
    p = G.Pdf()
    f = simple_cff(p, data, 4)
    case('cff_simple_charset_' + nm, 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, b'abcd')), txt(''.join(ch(x) for x in gl)), cmp=False)

# 4.4 the charset in its three formats, with names of the font's own (string id 391 on) and the standard ones
own = ['uni00E9', 'f_i', 'u1F600']
mix = [sid('A'), 391, 392, sid('B'), 393, sid('C'), sid('D'), sid('E')]
mix_text = 'AéfiB\U0001F600CDE'
for cs_ in ('fmt0', 'fmt1', 'fmt2'):
    data = make_cff(mix, own, cs_, ('fmt0', [0x41 + i for i in range(len(mix))]))
    p = G.Pdf()
    f = simple_cff(p, data, 4)
    case('cff_simple_charset_' + cs_, 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, bytes(0x41 + i for i in range(len(mix))))), txt(mix_text), cmp=False)

# 4.5 Differences name a code, the program has the others; a named Encoding is the author's
data = make_cff(g3, names3, 'fmt0', ('fmt0', [0x61, 0x62, 0x63]))
p = G.Pdf()
f = simple_cff(p, data, 4, '/Encoding << /Type /Encoding /Differences [98 /Euro] >>')
case('cff_simple_diff', 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, b'abc')), txt('α€γ'), cmp=False)
p = G.Pdf()
f = simple_cff(p, data, 4, '/Encoding /WinAnsiEncoding')
case('cff_simple_winansi', 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, b'abc')), txt('abc'), cmp=False)

# 4.6 Type0 over a CFF: the CID is the glyph when the CFF is not CID-keyed, and the glyph's name is the text
data = make_cff([sid('A'), sid('B'), 391], ['uni00E9'], 'fmt0', None)
p = G.Pdf()
f = cid_cff(p, data)
case('cff_cid_name_keyed', 'text', cid_page(p, {'F': f}, b'BT /F 12 Tf 72 720 Td ' + hexstr([1, 2, 3, 3, 1]) + b' Tj ET'), txt('ABééA'), cmp=False)
# the same with a CIDToGIDMap-less CIDFontType0 in an OpenType wrapper (FontFile3 /OpenType)


def make_otf(cff, nglyphs, cmaps=()):
    """an OpenType file around a CFF: the CFF table, head, hhea, maxp (0.5), hmtx and the cmap given"""
    head = (u32(0x00010000) + u32(0x00010000) + u32(0) + u32(0x5F0F3CF5) + u16(0) + u16(1000) + b'\0' * 16 +
            u16(0) + u16(0) + u16(500) + u16(500) + u16(0) + u16(8) + u16(2) + u16(1) + u16(0))
    hhea = (u32(0x00010000) + u16(900) + u16(-200) + u16(0) + u16(500) + u16(0) + u16(0) + u16(500) +
            u16(1) + u16(0) + u16(0) + b'\0' * 8 + u16(0) + u16(nglyphs))
    maxp = u32(0x00005000) + u16(nglyphs)
    hmtx = b''.join(u16(500) + u16(0) for _ in range(nglyphs))
    tables = {'CFF ': cff, 'head': head, 'hhea': hhea, 'maxp': maxp, 'hmtx': hmtx}
    if cmaps:
        recs = b''
        subs = b''
        base = 4 + 8 * len(cmaps)
        for plat, enc, sub in cmaps:
            recs += u16(plat) + u16(enc) + u32(base + len(subs))
            subs += sub + b'\0' * (-len(sub) % 2)
        tables['cmap'] = u16(0) + u16(len(cmaps)) + recs + subs
    tags = sorted(tables)
    out = b'OTTO' + u16(len(tags)) + u16(0) + u16(0) + u16(0)
    dirlen = 12 + 16 * len(tags)
    body = b''
    for tg in tags:
        d = tables[tg]
        out += tg.encode() + u32(0) + u32(dirlen + len(body)) + u32(len(d))
        body += d + b'\0' * (-len(d) % 4)
    return out + body


# an OpenType font with a name-keyed CFF and no cmap: the CFF names the glyphs
data = make_otf(make_cff([sid('A'), sid('B'), 391], ['uni00E9']), 4)
p = G.Pdf()
f = cid_cff(p, data, 'OpenType')
case('cff_otf_name_keyed', 'text', cid_page(p, {'F': f}, b'BT /F 12 Tf 72 720 Td ' + hexstr([1, 2, 3]) + b' Tj ET'), txt('ABé'), cmp=False)
# a CID-keyed CFF has no names; the CIDs 100, 200, 300 are the glyphs 1, 2, 3 by its charset, and the
# cmap of the OpenType wrapper says what the glyphs are
cm = {0x41: 1, 0x00E9: 2, 0x20AC: 3}
data = make_otf(make_cff([100, 200, 300], [], 'fmt0', None, cid=True), 4, [(3, 1, cmap_sub(4, cm))])
p = G.Pdf()
f = cid_cff(p, data, 'OpenType')
case('cff_otf_cid_keyed_cmap', 'text', cid_page(p, {'F': f}, b'BT /F 12 Tf 72 720 Td ' + hexstr([100, 200, 300, 200, 7]) + b' Tj ET'), txt('Aé€é�'), cmp=False)
# a bare CID-keyed CFF has nothing: U+FFFD, as before
data = make_cff([100, 200, 300], [], 'fmt0', None, cid=True)
p = G.Pdf()
f = cid_cff(p, data)
case('cff_cid_keyed_nothing', 'text', cid_page(p, {'F': f}, b'BT /F 12 Tf 72 720 Td ' + hexstr([100, 200]) + b' Tj ET'), txt('��'), cmp=False)

# two glyphs with one CID (not a font the note allows): the CID selects the lower glyph
cmd = {0x41: 1, 0x42: 2, 0x43: 3}
data = make_otf(make_cff([100, 100, 200], [], 'fmt0', None, cid=True), 4, [(3, 1, cmap_sub(4, cmd))])
p = G.Pdf()
f = cid_cff(p, data, 'OpenType')
case('cff_otf_cid_duplicate', 'text', cid_page(p, {'F': f}, b'BT /F 12 Tf 72 720 Td ' + hexstr([100, 200]) + b' Tj ET'), txt('AC'), cmp=False)

# 4.7 Type 1: the clear text of the program says the encoding
T1_HEAD = (b'%!PS-AdobeFont-1.0: Toy 001.000\n11 dict begin\n/FontInfo 1 dict dup begin /version (001.000) readonly def end readonly def\n'
           b'/FontName /Toy def\n/PaintType 0 def\n/FontType 1 def\n/FontMatrix [0.001 0 0 0.001 0 0] readonly def\n')
T1_TAIL = b'/FontBBox {0 0 1000 1000} readonly def\ncurrentdict end\ncurrentfile eexec\n'


def type1(enc_text):
    clear = T1_HEAD + enc_text + T1_TAIL
    secret = bytes((i * 37 + 11) & 0xFF for i in range(300))
    return clear, secret + b'\n' + (b'0' * 64 + b'\n') * 8 + b'cleartomark\n'


def simple_t1(p, clear, rest, flags, enc=''):
    data = clear + rest
    ff = p.stream('/Length1 %d /Length2 %d /Length3 0' % (len(clear), len(rest)), data, flate=False)
    fd = p.add('<< /Type /FontDescriptor /FontName /AAAAAA+Toy /Flags %d /FontBBox [0 0 1000 1000] /ItalicAngle 0 /Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 /FontFile %d 0 R >>' % (flags, ff))
    ws = ' '.join(['500'] * 224)
    return p.add('<< /Type /Font /Subtype /Type1 /BaseFont /AAAAAA+Toy %s /FirstChar 32 /LastChar 255 /Widths [%s] /FontDescriptor %d 0 R >>' % (enc, ws, fd))


t1cases = [
    ('standard', b'/Encoding StandardEncoding def\n', b'A\xae', 'Afi'),
    ('custom', b'/Encoding 256 array\n0 1 255 {1 index exch /.notdef put} for\ndup 97 /alpha put\ndup 98 /beta put\ndup 99 /gamma put\nreadonly def\n', b'abc', 'αβγ'),
    ('tight', b'/Encoding 256 array\n0 1 255 {1 index exch /.notdef put} for\ndup 97/alpha put dup 98/beta put\n% a comment, dup 99 /gamma put\ndup 99 /gamma put\nreadonly def\n', b'abc', 'αβγ'),
    ('def', b'/Encoding 256 array\n0 1 255 {1 index exch /.notdef put} for\ndup 97 /alpha put\ndup 98 /beta put\ndef\n', b'ab', 'αβ'),
    ('noencoding', b'', b'ab', 'ab'),
    ('far_dup', b'/Encoding 256 array\n' + b'0 1 255 {1 index exch /.notdef put} for\n' + b'junk ' * 100 + b'\ndup 97 /alpha put\ndup 98 /beta put\nreadonly def\n', b'ab', '\u03b1\u03b2'),
    ('cutat_dup', b'/Encoding 256 array\ndup 97 /alpha put\ndup 98', b'ab', 'aβ'.replace('β', 'b')),
]
for nm, enc_text, shown, want in t1cases:
    if nm == 'cutat_dup':
        clear = T1_HEAD + enc_text
        rest = b'\n' + b'x' * 20
        want = 'αb'
    else:
        clear, rest = type1(enc_text)
    p = G.Pdf()
    f = simple_t1(p, clear, rest, 4)
    case('t1_' + nm, 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, shown)), txt(want), cmp=False)
# Differences win over the program's, the Encoding the file names is the author's
clear, rest = type1(b'/Encoding 256 array\n0 1 255 {1 index exch /.notdef put} for\ndup 97 /alpha put\ndup 98 /beta put\ndup 99 /gamma put\nreadonly def\n')
p = G.Pdf()
f = simple_t1(p, clear, rest, 4, '/Encoding << /Type /Encoding /Differences [98 /Euro] >>')
case('t1_diff', 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, b'abc')), txt('α€γ'), cmp=False)
p = G.Pdf()
f = simple_t1(p, clear, rest, 4, '/Encoding /WinAnsiEncoding')
case('t1_winansi', 'text', cid_page(p, {'F': f}, show('F', 12, 72, 720, b'abc')), txt('abc'), cmp=False)

# 4.8 damaged CFF programs: the text is what it was without the font
goodcff = make_cff(g3, names3, 'fmt0', ('fmt0', [0x61, 0x62, 0x63]))
goodcid = make_cff([100, 200], [], 'fmt0', None, cid=True)


def cff_damaged(name, data, want, shown=b'abc', composite=False):
    p = G.Pdf()
    if composite:
        f = cid_cff(p, data)
        c = b'BT /F 12 Tf 72 720 Td ' + hexstr([1, 2]) + b' Tj ET'
    else:
        f = simple_cff(p, data, 4)
        c = show('F', 12, 72, 720, shown)
    case('cff_bad_' + name, 'text', cid_page(p, {'F': f}, c), txt(want), cmp=False)


cff_damaged('intact', goodcff, 'αβγ')
cff_damaged('cut_header', goodcff[:3], 'abc')
cff_damaged('cut_in_name_index', goodcff[:8], 'abc')
cff_damaged('major_2', bend(goodcff, [(0, b'\x02')]), 'abc')
cff_damaged('hdrsize_big', bend(goodcff, [(2, b'\xf0')]), 'abc')
cff_damaged('offsize_0', bend(goodcff, [(3, b'\x00')]), 'abc')
cff_damaged('offsize_5', bend(goodcff, [(3, b'\x05')]), 'abc')
cff_damaged('name_index_count_huge', bend(goodcff, [(4, u16(60000))]), 'abc')
cff_damaged('topdict_cut', goodcff[:30], 'abc')
cff_damaged('topdict_reserved_op', bend(goodcff, [(goodcff.index(b'\x1d') + 5, b'\x1f')]), 'abc')
cff_damaged('charstrings_past_end', bend(goodcff, [(goodcff.rindex(b'\x1d', 0, goodcff.rindex(b'\x11')) - 0 + 1, struct.pack('>i', 0x7FFFFF00))]), 'abc')
# the font is sound and the charset or the encoding is not: no names, no codes, the text is the guess
cff_damaged('charset_past_end', make_cff(g3, names3, 'fmt0', ('fmt0', [0x61, 0x62, 0x63]), charset_at=0x7FFFFF00), 'abc')
cff_damaged('charset_format_3', make_cff(g3, names3, 'fmt0', ('fmt0', [0x61, 0x62, 0x63]), charset_format=3), 'abc')
cff_damaged('encoding_past_end', make_cff(g3, names3, 'fmt0', ('fmt0', [0x61, 0x62, 0x63]), enc_at=0x7FFFFF00), 'abc')
cff_damaged('index_first_offset_2', bend(goodcff, [(7, b'\x02')]), 'abc')
cff_damaged('cid_nothing_intact', goodcid, '��', composite=True)
cff_damaged('cid_cut', goodcid[:20], '��', composite=True)

# 4.9 a real program: Ghostscript's Type1C subset of a re-encoded Nimbus Sans, whose codes 1 to 14 are
# H e l o space W r d, e acute, Euro, fi, n tilde, 2, 0; the PDF names an Encoding and has a ToUnicode map,
# and here both are renamed (/Encodinx, /Tounicode: the same length, so the table is right) so that the
# font's own encoding is all there is. pdftotext reads it the same way.
rp = os.path.join(ROOT, 'testdata', 'pdffontreal', 'gs-reencoded.pdf')
if os.path.exists(rp):
    raw = open(rp, 'rb').read()
    assert raw.count(b'/ToUnicode') == 1 and raw.count(b'/Encoding') == 2
    case('real_gs_type1c_nomap', 'text', raw.replace(b'/Encoding', b'/Encodinx').replace(b'/ToUnicode', b'/Tounicode'),
         txt('Hello World\n\u00e9\u20ac fi \u00f1 20'))
    case('real_gs_type1c', 'text', raw, txt('Hello World\n\u00e9\u20ac fi \u00f1 20'))


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
