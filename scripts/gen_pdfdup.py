#!/usr/bin/env python3
"""Writes testdata/pdfdup.txt: the PDF files the paspdf repeat test reads, each
with the text it must give (P514). Text drawn twice a little apart fakes a
bold face or gives a title a shadow; a reader that takes both copies reads
FFllaannggee for Flange. The reader gives a string shown a second time, in its
place, once. In its place is what pdftotext measured on generated files
(Helvetica 12, the second copy moved a step at a time): along the line up to
0.1 of the size, across it up to 0.2 of the size, for the same font, size and
bytes; beyond that both are read. The files are built here byte by byte; fixed
seed, no clock.

    python3 scripts/gen_pdfdup.py [--check | --verify]

--check writes nothing and fails when testdata/pdfdup.txt is not what this
makes (make check). --verify checks every file with qpdf --check and compares
the words with pdftotext's as a multiset, ligatures normalized (pdftotext puts
the two copies of a line in an order of its own; neither tool is needed
anywhere else). Eight files differ from pdftotext on purpose, see
KNOWN_DIFFERENT: pdftotext decides by character and by where it falls, and
this reader by the string a Tj or a piece of a TJ shows, in its font."""
import base64
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_pdf_tests as G  # noqa: E402

ROOT = G.ROOT
OUT = os.path.join(ROOT, 'testdata', 'pdfdup.txt')
CASES = []   # (name, kind, pdf bytes, expected bytes, valid, compare with pdftotext)
W = 'Flange 666'


def case(name, kind, pdf, expect, valid=True, cmp=True):
    CASES.append((name, kind, pdf, expect.encode('utf-8') if isinstance(expect, str) else expect, valid, cmp))


def txt(*pages):
    return ''.join(pg + '\n\f' for pg in pages)


def fmt(v):
    return ('%.4f' % v).rstrip('0').rstrip('.') if v != int(v) else str(int(v))


def show(font, size, x, y, text, before=''):
    """a string at x, y: its own text object"""
    s = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    return '%sBT /%s %s Tf %s %s Td (%s) Tj ET\n' % (before + ' ' if before else '', font, fmt(size), fmt(x), fmt(y), s)


def doc(content, fonts=0, extra_res='', flate=False, p=None):
    """one page, font F1 and F2 if the content shows it (every width 600, so
    the geometry is exact)"""
    p = p or G.Pdf()
    fonts = fonts or (2 if '/F2 ' in content else 1)
    f = {}
    for i, base in enumerate(['Helvetica', 'Helvetica-Bold'][:fonts]):
        f['F%d' % (i + 1)] = G.font_simple(p, base=base)
    p, root = G.one_page(content, f, extra_res=extra_res, flate=flate, p=p)
    return p.build(root)


def two(size, dx, dy, font2='F1', size2=None, text2=None, before2='', text=W, before1=''):
    """the string and a second one moved by dx, dy"""
    return (show('F1', size, 72, 700, text, before1) +
            show(font2, size2 or size, 72 + dx, 700 + dy, text2 or text, before2))


# ---------------------------------------------------------------------------
# 1. the same string in the same place is read once
case('dup_same_place', 'text', doc(two(12, 0, 0)), txt(W))
case('dup_phone_bold', 'text',
     doc(show('F1', 11, 72, 700, 'Tel 666 77 88 99') + show('F1', 11, 72.4, 700, 'Tel 666 77 88 99')),
     txt('Tel 666 77 88 99'))
case('dup_three_copies', 'text',
     doc(show('F1', 12, 72, 700, W) + show('F1', 12, 72.5, 700, W) + show('F1', 12, 73, 700, W)), txt(W))
# a copy is compared with the strings kept: the third is 1.6 from the first
# and 0.8 from the second, which was left out
case('dup_three_spread', 'text',
     doc(show('F1', 12, 72, 700, W) + show('F1', 12, 72.8, 700, W) + show('F1', 12, 73.6, 700, W)),
     txt(W + ' ' + W))

# 2. the thresholds, on both sides, at three sizes: 0.1 along, 0.2 across
for size in (8, 12, 24):
    case('dup_along_below_%d' % size, 'text', doc(two(size, 0.09 * size, 0)), txt(W))
    case('dup_along_above_%d' % size, 'text', doc(two(size, 0.11 * size, 0)), txt(W + ' ' + W))
    case('dup_across_below_%d' % size, 'text', doc(two(size, 0, 0.19 * size)), txt(W))
    case('dup_across_above_%d' % size, 'text', doc(two(size, 0, 0.21 * size)), txt(W + ' ' + W))
    case('dup_both_below_%d' % size, 'text', doc(two(size, 0.09 * size, 0.19 * size)), txt(W))
    case('dup_both_one_above_%d' % size, 'text', doc(two(size, 0.09 * size, 0.21 * size)), txt(W + ' ' + W))
    case('dup_negative_%d' % size, 'text', doc(two(size, -0.09 * size, -0.19 * size)), txt(W))
case('dup_size_equal', 'text', doc(two(12, 0, 0, size2=12.01)), txt(W))
case('dup_size_other', 'text', doc(two(12, 0, 0, size2=24)), txt(W + ' ' + W))

# 3. what is not the same string is read
# pdftotext looks at where each character falls, not at the font: with the same
# widths in both it reads the second copy as a repeat; the bytes of two fonts
# are not the same text, so this reader keeps both
case('dup_other_font', 'text', doc(two(12, 0, 0, font2='F2')), txt(W + ' ' + W), cmp=False)
# with the widths the standard fonts have, the bold copy's glyphs fall elsewhere
p = G.Pdf()
fr = p.add('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
fb = p.add('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>')
p, root = G.one_page(two(12, 0, 0, font2='F2'), {'F1': fr, 'F2': fb}, p=p)
case('dup_std_bold_over_regular', 'text', p.build(root), txt(W + ' ' + W))
case('dup_other_text', 'text', doc(two(12, 0, 0, text2='Mirror 123')), txt(W + ' Mirror 123'))
# the second 666 is a repeat to pdftotext, which decides by word
case('dup_one_word_new', 'text', doc(two(12, 0, 0, text2='Flanxe 666')), txt(W + ' Flanxe 666'), cmp=False)
# pdftotext reads 66 under 666 as a repeat, this reader the string whole
case('dup_part_of_string', 'text',
     doc(show('F1', 12, 72, 700, W) + show('F1', 12, 72 + 7.2 * 8, 700, '66')), txt(W + ' 66'), cmp=False)
# a string shifted by one glyph is not a repeat to either
case('dup_shifted_glyph', 'text',
     doc(show('F1', 12, 72, 700, W) + show('F1', 12, 72 + 7.2, 700, W)), txt(W + ' ' + W), cmp=False)

# 4. how the strings are shown
# one glyph a Tj, as QCAD writes them (testdata is flange.pdf's shape)
glyphs = ''.join('%s 0 Td (%s) Tj\n' % (fmt(7.2 if i else 0), c) for i, c in enumerate('Flange'))
case('dup_glyph_by_glyph', 'text',
     doc('BT /F1 12 Tf 72 700 Td\n' + glyphs + 'ET\nBT /F1 12 Tf 72.4 700 Td\n' + glyphs + 'ET\n'), txt('Flange'))
hello = ''.join('%s 0 Td (%s) Tj\n' % (fmt(7.2 if i else 0), c) for i, c in enumerate('Hello'))
case('dup_letters_repeat', 'text', doc('BT /F1 12 Tf 72 700 Td\n' + hello + 'ET\n'), txt('Hello'))
tj = 'BT /F1 12 Tf 72 700 Td [(Fla) -20 (nge)] TJ ET\n'
case('dup_tj_array', 'text', doc(tj + tj.replace('72 700', '72.5 700')), txt('Flange'))
# the pen goes on as if the string were shown: what follows a repeat is placed
# where it would be
pen = 'BT /F1 12 Tf 72 700 Td (Flange) Tj ( 666) Tj ET\n'
case('dup_pen_advances', 'text', doc(pen + pen.replace('72 700', '72.4 700')), txt(W))
# one number over another: pdftotext drops the words the second shares with the
# first, this reader reads the second whole
case('dup_last_byte', 'text', doc(two(11, 0.3, 0, text='Tel 666 77 88 99', text2='Tel 666 77 88 98')),
     txt('Tel 666 77 88 99 Tel 666 77 88 98'), cmp=False)
# the pen goes back, and the second piece of a TJ starts where the first did:
# the bytes are other, so it is not a repeat (the key is of the piece's bytes)
case('dup_tj_back', 'text', doc('BT /F1 12 Tf 72 700 Td [(AB) 1200 (CD)] TJ ET\n'), txt('ABCD'), cmp=False)
# vertical writing is not tested for repeats: the file is read as it was
p = G.Pdf()
tu = p.stream('', b"""/CIDInit /ProcSet findresource begin 12 dict begin begincmap
1 begincodespacerange <0000> <FFFF> endcodespacerange
4 beginbfchar
<0001> <0050>
<0002> <0061>
<0003> <0073>
<0004> <0020>
endbfchar
endcmap end end""")
desc = p.add('<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Sub+CID /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /DW 1000 /CIDToGIDMap /Identity >>')
fv = p.add('<< /Type /Font /Subtype /Type0 /BaseFont /Sub+CID /Encoding /Identity-V /DescendantFonts [%d 0 R] /ToUnicode %d 0 R >>' % (desc, tu))
vs = 'BT /F 12 Tf 300 700 Td <0001000200030003> Tj ET\n'
p, root = G.one_page(vs + vs, {'F': fv}, p=p)
case('dup_vertical_read', 'text', p.build(root), txt('Pass Pass'), cmp=False)
case('dup_quote_operators', 'text',
     doc('BT /F1 12 Tf 14 TL 72 700 Td (Flange) Tj ET\nBT /F1 12 Tf 14 TL 72.5 700 Td (Flange) Tj ET\n'), txt('Flange'))
case('dup_invisible_copy', 'text', doc(two(12, 0, 0, before2='3 Tr')), txt(W))
case('dup_invisible_first', 'text', doc(two(12, 0, 0, before1='3 Tr', before2='0 Tr')), txt(W))
case('dup_stroke_copy', 'text', doc(two(12, 0.5, 0, before2='1 Tr')), txt(W))
case('dup_scale_cm', 'text',
     doc('12 0 0 12 72 700 cm\nBT /F1 1 Tf 0 0 Td (%s) Tj ET\nBT /F1 1 Tf 0.09 0 Td (%s) Tj ET\n' % (W, W)), txt(W))
case('dup_scale_cm_above', 'text',
     doc('12 0 0 12 72 700 cm\nBT /F1 1 Tf 0 0 Td (%s) Tj ET\nBT /F1 1 Tf 0.11 0 Td (%s) Tj ET\n' % (W, W)), txt(W + ' ' + W))

# 5. rotated text: along and across are the line's, not the page's
for size in (12,):
    for name, mat1, mat2, want in [
            ('rot90_along_below', (0, 1, -1, 0, 100, 300), (0, 1, -1, 0, 100, 300 + 0.09 * size), 1),
            ('rot90_along_above', (0, 1, -1, 0, 100, 300), (0, 1, -1, 0, 100, 300 + 0.11 * size), 2),
            ('rot90_across_below', (0, 1, -1, 0, 100, 300), (0, 1, -1, 0, 100 - 0.19 * size, 300), 1),
            ('rot90_across_above', (0, 1, -1, 0, 100, 300), (0, 1, -1, 0, 100 - 0.21 * size, 300), 2),
            ('rot180_along_below', (-1, 0, 0, -1, 300, 400), (-1, 0, 0, -1, 300 - 0.09 * size, 400), 1),
            ('rot180_along_above', (-1, 0, 0, -1, 300, 400), (-1, 0, 0, -1, 300 - 0.11 * size, 400), 2)]:
        def tm(m):
            return 'BT /F1 %d Tf %s Tm (%s) Tj ET\n' % (size, ' '.join(fmt(v) for v in m), W)
        case('dup_' + name, 'text', doc(tm(mat1) + tm(mat2)), txt(W if want == 1 else W + ' ' + W))

# 6. a form drawn twice, a string drawn after others
p = G.Pdf()
f1 = G.font_simple(p, base='Helvetica')
form = p.stream('/Type /XObject /Subtype /Form /BBox [0 0 612 792] /Resources << /Font << /F1 %d 0 R >> >>' % f1,
                show('F1', 12, 72, 700, W).encode())
p, root = G.one_page('/X1 Do\n/X1 Do\n', {'F1': f1}, extra_res='/XObject << /X1 %d 0 R >>' % form, p=p)
case('dup_form_twice', 'text', p.build(root), txt(W))

p = G.Pdf()
f1 = G.font_simple(p, base='Helvetica')
body = show('F1', 12, 72, 700, W)
rows = {}
for i in range(100):
    body += show('F1', 6, 10 + 20 * (i % 28), 680 - 7 * (i // 28), 'x%03d' % i)
    rows.setdefault(i // 28, []).append('x%03d' % i)
body += show('F1', 12, 72.5, 700, W)
p, root = G.one_page(body, {'F1': f1}, p=p)
case('dup_far_apart', 'text', p.build(root), txt('\n'.join([W] + [' '.join(rows[r]) for r in sorted(rows)])))

# many different strings at one place (more than the 64 that the search of a place
# goes through) are all read
many = ''.join(show('F1', 12, 72, 700, 's%d' % i) for i in range(150))
# (pdftotext lays the characters of strings on one another side by side)
case('dup_many_at_one_place', 'text', doc(many, flate=True), txt(' '.join('s%d' % i for i in range(150))), cmp=False)

# the same string drawn 300 times
case('dup_repeat_300', 'text', doc(show('F1', 12, 72, 700, W) * 300, flate=True), txt(W))

# the second page keeps what the first one had
p = G.Pdf()
f1 = G.font_simple(p, base='Helvetica')
c1 = p.stream('', show('F1', 12, 72, 700, W).encode())
c2 = p.stream('', show('F1', 12, 72, 700, W).encode())
pages = p.reserve()
pg = [p.add('<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] /Contents %d 0 R /Resources << /Font << /F1 %d 0 R >> >> >>' % (pages, c, f1))
      for c in (c1, c2)]
p.put(pages, '<< /Type /Pages /Kids [%s] /Count 2 >>' % ' '.join('%d 0 R' % n for n in pg))
root = p.add('<< /Type /Catalog /Pages %d 0 R >>' % pages)
case('dup_two_pages', 'text', p.build(root), txt(W, W))

# a page of 2100 strings, each drawn twice: the table of the page grows (it is made
# four times bigger when there are more than twice as many strings as places, 2048)
body = ''
rows = {}
for i in range(2100):
    col, row = i % 28, i // 28
    x, y = 10 + 20 * col, 780 - 7 * row
    body += show('F1', 6, x, y, 'n%04d' % i)
    rows.setdefault(row, []).append('n%04d' % i)
once = body
for i in range(2100):
    col, row = i % 28, i // 28
    body += show('F1', 6, 10 + 20 * col + 0.3, 780 - 7 * row, 'n%04d' % i)
case('dup_table_grows', 'text', doc(body, fonts=1, flate=True), txt('\n'.join(' '.join(rows[r]) for r in sorted(rows))))


# ---------------------------------------------------------------------------
# 7. a page that draws nothing twice reads as it did
case('dup_none', 'text', doc(show('F1', 12, 72, 700, 'First line') + show('F1', 12, 72, 686, 'Second line')),
     txt('First line\nSecond line'))
case('dup_empty_string', 'text', doc(show('F1', 12, 72, 700, '') + show('F1', 12, 72, 700, W)), txt(W))


KNOWN_DIFFERENT = ('dup_other_font', 'dup_last_byte', 'dup_one_word_new', 'dup_part_of_string', 'dup_shifted_glyph',
                   'dup_tj_back', 'dup_vertical_read', 'dup_many_at_one_place')


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
            a = sorted(re.findall(r'\S+', unicodedata.normalize('NFKC', t)))
            b = sorted(re.findall(r'\S+', unicodedata.normalize('NFKC', expect.decode('utf-8'))))
            if cmp and a != b:
                bad += 1
                print('pdftotext differs on', name)
                print('  pdftotext:', ' '.join(a)[:160])
                print('  expected :', ' '.join(b)[:160])
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
            sys.exit('scripts/gen_pdfdup.py: testdata/pdfdup.txt is not what the generator writes')
        print('pdfdup.txt is the generator\'s,', len(CASES), 'cases')
    else:
        open(OUT, 'w').write(text)
        print('wrote', OUT, len(CASES), 'cases')
