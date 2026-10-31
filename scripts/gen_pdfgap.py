#!/usr/bin/env python3
"""Writes testdata/pdfgap.txt: the PDF files the paspdf word-gap test reads,
each with the text it must give (P518). Where two strings of a line are apart
the reader puts a space; the question is how far is apart. Measured on
generated files against pdftotext (Helvetica 12, every glyph 600 thousandths,
the gap between two glyphs moved a step at a time):

  a line of words (a glyph of it next to another, gap 0) has a space where the
    gap is wider than 0.1 of the size (pdftotext) and 0.15 (this reader);
  a line whose every string is one glyph (letter-spaced text: Chromium writes
    each glyph as a Tj with a Td) has the spacing of its letters in its least
    gap, and a space where a gap is more than 1.3 times that, at least 0.15 of
    the size, and never more than 0.4 of the size;
  the same for the pieces of a TJ array, in thousandths;
  no space is put after a space (a space glyph beside a wide gap);
  a string whose glyphs the TJ array takes back as far as they advanced ends
    where it began (P522): it is a point, and the text it is in goes on, along
    the line it is set in (a layout program that sets each letter of a turned
    line by itself ends the line so).

The expected text is made here from that rule, and --verify compares it with
pdftotext's, line by line, word by word: the files in KNOWN_DIFFERENT differ on
purpose. The files are built here byte by byte; fixed seed, no clock.

    python3 scripts/gen_pdfgap.py [--check | --verify]

--check writes nothing and fails when testdata/pdfgap.txt is not what this
makes (make check). --verify checks every file with qpdf --check (neither tool
is needed anywhere else)."""
import base64
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_pdf_tests as G  # noqa: E402

ROOT = G.ROOT
OUT = os.path.join(ROOT, 'testdata', 'pdfgap.txt')
CASES = []   # (name, kind, pdf bytes, expected bytes, valid, compare with pdftotext)
SIZE = 12
W = 7.2      # the width of a glyph: 600 thousandths of 12
SPACE_GAP = 0.15
RATIO = 1.3
CAP = 0.4


def case(name, kind, pdf, expect, valid=True, cmp=True):
    CASES.append((name, kind, pdf, expect.encode('utf-8') if isinstance(expect, str) else expect, valid, cmp))


def txt(*pages):
    return ''.join(pg + '\n\f' for pg in pages)


def doc(content):
    p = G.Pdf()
    f = G.font_simple(p, base='Helvetica')
    p, root = G.one_page(content, {'F': f}, p=p)
    return p.build(root)


def gaps_line(letters, gaps, y=700):
    """the letters one to a Tj, each moved by Td from the one before"""
    c = 'BT /F 12 Tf 72 %d Td (%s) Tj ' % (y, letters[0])
    for i, g in enumerate(gaps):
        c += '%.4f 0 Td (%s) Tj ' % (W + g * SIZE, letters[i + 1])
    return c + 'ET\n'


def model(letters, gaps):
    """where this reader puts a space, from the rule above"""
    base = min(gaps) if len(gaps) >= 1 else 0
    out = letters[0]
    lim = max(SPACE_GAP, RATIO * base)
    lim = min(lim, CAP)
    for i, g in enumerate(gaps):
        if g > lim + 1e-9:
            out += ' '
        out += letters[i + 1]
    return out


# ---------------------------------------------------------------------------
# 1. letter-spaced text: uniform gaps
for g in (0.0, 0.05, 0.2, 0.3, 0.38):
    case('gap_uniform_%03d_x4' % round(g * 100), 'text', doc(gaps_line('ABCD', [g] * 3)), txt('ABCD'))
for g in (0.42, 0.5, 0.8):
    case('gap_uniform_%03d_x4' % round(g * 100), 'text', doc(gaps_line('ABCD', [g] * 3)), txt('A B C D'))
case('gap_two_glyphs_020', 'text', doc(gaps_line('AB', [0.2])), txt('AB'))
case('gap_two_glyphs_030', 'text', doc(gaps_line('AB', [0.3])), txt('AB'))
case('gap_two_glyphs_042', 'text', doc(gaps_line('AB', [0.42])), txt('A B'))
case('gap_two_glyphs_000', 'text', doc(gaps_line('AB', [0.0])), txt('AB'))

# 2. a gap wider than the others
for base, extra in [(0.2, 0.05), (0.2, 0.1), (0.2, 0.15), (0.3, 0.05), (0.3, 0.15), (0.25, 0.15), (0.0, 0.2), (0.05, 0.3)]:
    gaps = [base, base, base + extra, base, base]
    case('gap_wider_%03d_%03d' % (round(base * 100), round(extra * 100)), 'text',
         doc(gaps_line('ABCDEF', gaps)), txt(model('ABCDEF', gaps)))
for gaps in ([0.2, 0.0], [0.0, 0.2], [0.2, 0.0, 0.2], [0.2, 0.2, 0.2, 0.0, 0.2], [0.0, 0.0, 0.2, 0.0, 0.0],
             [0.2, 0.25, 0.2, 0.25], [0.25, 0.25, 0.25, 0.4, 0.25, 0.25]):
    letters = 'ABCDEFGH'[:len(gaps) + 1]
    case('gap_pattern_' + '_'.join('%02d' % round(g * 100) for g in gaps), 'text',
         doc(gaps_line(letters, gaps)), txt(model(letters, gaps)))

# 3. strings of words are as they were: 0.15 between strings, and the gap of the first pair
case('gap_words_018', 'text', doc('BT /F 12 Tf 72 700 Td (AB) Tj ET BT /F 12 Tf %.4f 700 Td (CD) Tj ET\n' % (72 + 2 * W + 0.18 * SIZE)), txt('AB CD'))
case('gap_words_005', 'text', doc('BT /F 12 Tf 72 700 Td (AB) Tj ET BT /F 12 Tf %.4f 700 Td (CD) Tj ET\n' % (72 + 2 * W + 0.05 * SIZE)), txt('ABCD'))
case('gap_words_030', 'text', doc('BT /F 12 Tf 72 700 Td (AB) Tj ET BT /F 12 Tf %.4f 700 Td (CD) Tj ET\n' % (72 + 2 * W + 0.3 * SIZE)), txt('AB CD'))
# pdftotext breaks a word at 0.1, this reader at 0.15
case('gap_words_012', 'text', doc('BT /F 12 Tf 72 700 Td (AB) Tj ET BT /F 12 Tf %.4f 700 Td (CD) Tj ET\n' % (72 + 2 * W + 0.12 * SIZE)), txt('ABCD'), cmp=False)

# 4. TJ arrays
for a in (200, 300, 380):
    case('gap_tj_uniform_%d' % a, 'text', doc('BT /F 12 Tf 72 700 Td [(A) -%d (B) -%d (C) -%d (D)] TJ ET\n' % (a, a, a)), txt('ABCD'))
for a in (420, 600):
    case('gap_tj_uniform_%d' % a, 'text', doc('BT /F 12 Tf 72 700 Td [(A) -%d (B) -%d (C) -%d (D)] TJ ET\n' % (a, a, a)), txt('A B C D'))
case('gap_tj_words_200', 'text', doc('BT /F 12 Tf 72 700 Td [(AB) -200 (CD)] TJ ET\n'), txt('AB CD'))
case('gap_tj_words_050', 'text', doc('BT /F 12 Tf 72 700 Td [(AB) -50 (CD)] TJ ET\n'), txt('ABCD'))
# pdftotext breaks at 0.1 of the size, this reader at 0.18 inside a TJ array
case('gap_tj_words_120', 'text', doc('BT /F 12 Tf 72 700 Td [(AB) -120 (CD)] TJ ET\n'), txt('ABCD'), cmp=False)
case('gap_tj_one_wider', 'text', doc('BT /F 12 Tf 72 700 Td [(A) -200 (B) -200 (C) -350 (D) -200 (E)] TJ ET\n'), txt('ABC DE'))
case('gap_tj_tight', 'text', doc('BT /F 12 Tf 72 700 Td [(A) -200 (B) 50 (C) -200 (D)] TJ ET\n'), txt('A BC D'))

# 5. no second space
sp = 'BT /F 12 Tf 72 700 Td (A) Tj %.4f 0 Td (B) Tj %.4f 0 Td ( ) Tj %.4f 0 Td (C) Tj %.4f 0 Td (D) Tj ET\n'
case('gap_space_glyph_uniform', 'text', doc(sp % (W + 0.2 * SIZE, W + 0.2 * SIZE, W + 0.2 * SIZE, W + 0.2 * SIZE)), txt('AB CD'))
case('gap_space_glyph_wide', 'text', doc(sp % (W, W, W + 0.5 * SIZE, W)), txt('AB CD'))
case('gap_space_glyph_wide_both', 'text', doc(sp % (W, W + 0.5 * SIZE, W + 0.5 * SIZE, W)), txt('AB CD'))
case('gap_space_in_string', 'text',
     doc('BT /F 12 Tf 72 700 Td (AB ) Tj %.4f 0 Td (CD) Tj ET\n' % (3 * W + 0.5 * SIZE)), txt('AB CD'))

# a space glyph in an array, with the adjustments around it
case('gap_tj_space_glyph', 'text', doc('BT /F 12 Tf 72 700 Td [(A) -500 ( ) -500 (B)] TJ ET\n'), txt('A B'))
case('gap_tj_space_glyph_uniform', 'text', doc('BT /F 12 Tf 72 700 Td [(A) -250 (B) -250 ( ) -250 (C) -250 (D)] TJ ET\n'), txt('AB CD'))
# two strings with nothing between them are a word: the gaps after it are spaces
case('gap_tj_adjacent_strings', 'text', doc('BT /F 12 Tf 72 700 Td [(A)(B) -300 (C) -300 (D)] TJ ET\n'), txt('AB C D'))
# turned text is read in the order of the stream: the same rule
rot = 'BT /F 12 Tf 0 1 -1 0 300 300 Tm (A) Tj %.4f 0 Td (B) Tj %.4f 0 Td ( ) Tj %.4f 0 Td (C) Tj %.4f 0 Td (D) Tj ET\n'
case('gap_turned_space_glyph_wide', 'text', doc(rot % (W, W, W + 0.5 * SIZE, W)), txt('AB CD'))
# the order of the stream has no line to take the spacing of the letters from: every gap over 0.15 is a space
case('gap_turned_uniform', 'text', doc(rot % (W + 0.2 * SIZE, W + 0.2 * SIZE, W + 0.2 * SIZE, W + 0.2 * SIZE)), txt('A B C D'), cmp=False)

# 6. two lines, each as its own
case('gap_two_lines', 'text', doc(gaps_line('ABCD', [0.2] * 3, 700) + gaps_line('EFGH', [0.0, 0.3, 0.0], 680)),
     txt('ABCD\nEF GH'))

# 7. a string that ends where it began (P522): the TJ number takes the glyph back as
# far as it advanced (600 thousandths of the size is the width of a glyph here)
def turn(a, b, c, d):
    return 'BT /F 12 Tf %s %s %s %s 300 300 Tm ' % (a, b, c, d)


ZL = '(A) Tj 7.2 0 Td (B) Tj 7.2 0 Td (C) Tj 7.2 0 Td [(D) 600] TJ ET\n'
ZM = '(A) Tj 7.2 0 Td [(B) 600] TJ 7.2 0 Td (C) Tj 7.2 0 Td (D) Tj ET\n'
ZG = '(A) Tj 7.2 0 Td [(B) 600] TJ 14.4 0 Td (C) Tj ET\n'
case('gap_zero_last_turned_90', 'text', doc(turn(0, 1, -1, 0) + ZL), txt('ABCD'))
case('gap_zero_last_turned_270', 'text', doc(turn(0, -1, 1, 0) + ZL), txt('ABCD'))
case('gap_zero_last_tilted', 'text', doc(turn(0.7071, 0.7071, -0.7071, 0.7071) + ZL), txt('ABCD'), cmp=False)
case('gap_zero_mid_turned_90', 'text', doc(turn(0, 1, -1, 0) + ZM), txt('ABCD'))
case('gap_zero_mid_turned_270', 'text', doc(turn(0, -1, 1, 0) + ZM), txt('ABCD'))
case('gap_zero_gap_turned_90', 'text', doc(turn(0, 1, -1, 0) + ZG), txt('AB C'))
case('gap_zero_gap_turned_270', 'text', doc(turn(0, -1, 1, 0) + ZG), txt('AB C'))
case('gap_zero_alone_turned', 'text', doc(turn(0, 1, -1, 0) + '[(A) 600] TJ ET\n'), txt('A'))
case('gap_zero_mid_horizontal', 'text', doc('BT /F 12 Tf 72 700 Td ' + ZM), txt('ABCD'))
case('gap_zero_gap_horizontal', 'text', doc('BT /F 12 Tf 72 700 Td ' + ZG), txt('AB C'))

# a glyph with no width (the Widths array says 0 for Z) is a point as well: the direction
# the text is set in says which way the line goes, and the next string is not set apart
def doc0(content):
    p = G.Pdf()
    ws = ' '.join(['0' if c == ord('Z') else '600' for c in range(32, 256)])
    f = p.add('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding /FirstChar 32 /LastChar 255 /Widths [%s] >>' % ws)
    p, root = G.one_page(content, {'F': f}, p=p)
    return p.build(root)


ZW = '(A) Tj 7.2 0 Td (B) Tj 7.2 0 Td (C) Tj 7.2 0 Td (Z) Tj ET\n'
ZX = '(A) Tj 7.2 0 Td (B) Tj 7.2 0 Td (Z) Tj 0 0 Td (C) Tj 7.2 0 Td (D) Tj ET\n'
case('gap_nowidth_last_turned_90', 'text', doc0(turn(0, 1, -1, 0) + ZW), txt('ABCZ'))
case('gap_nowidth_last_turned_270', 'text', doc0(turn(0, -1, 1, 0) + ZW), txt('ABCZ'))
case('gap_nowidth_mid_turned_90', 'text', doc0(turn(0, 1, -1, 0) + ZX), txt('ABZCD'))
case('gap_nowidth_mid_turned_270', 'text', doc0(turn(0, -1, 1, 0) + ZX), txt('ABZCD'))
case('gap_nowidth_mid_horizontal', 'text', doc0('BT /F 12 Tf 72 700 Td ' + ZX), txt('ABZCD'))
# a point followed by a string set apart from it: the gap is measured along the line
ZY = '(A) Tj 7.2 0 Td (Z) Tj 7.2 0 Td (C) Tj ET\n'
case('gap_nowidth_gap_turned_90', 'text', doc0(turn(0, 1, -1, 0) + ZY), txt('AZ C'))
case('gap_nowidth_gap_turned_270', 'text', doc0(turn(0, -1, 1, 0) + ZY), txt('AZ C'))
case('gap_nowidth_gap_horizontal', 'text', doc0('BT /F 12 Tf 72 700 Td ' + ZY), txt('AZ C'))

# the footer of a contract template, as a layout program (QuarkXPress 8.5) wrote it, turned
# a quarter: every glyph is a TJ array with its own number and a Td from the start of the
# line before, the last one 's' taken back by its whole width. The operators and the widths
# are the program's, the text a telephone number and a web address (given by the portal,
# 2026-10-31); the codes are read by the Differences array of the font.
URL_CODES = [0x17, 0x28, 0x1f, 0x29, 0x23, 0, 0x1f, 0x28, 0, 0x0e, 7, 7, 0, 13, 11, 0, 11, 8, 0, 9, 10, 0, 0, 0, 0x33, 0, 0, 0, 0x2b, 0x2a, 0x2b, 5, 0x23, 0x2f]
URL_TD = [0.48787, 0.26497, 0.50691, 0.80697, 0.53987, 0.26802, 0.50691, 0.26497, 0.26802, 0.58187, 0.58187, 0.58187, 0.26802,
          0.58187, 0.58187, 0.26802, 0.58187, 0.53182, 0.26802, 0.58187, 0.58187, 0.26802, 0.26802, 0.26802, 0.27498, 0.26802,
          0.26802, 0.26802, 0.55794, 0.54891, 0.55794, 0.2679, 0.53987]
URL_W = [260, 360, 509, 278, 442, 286, 402, 600, 550, 600, 600, 600, 600, 600, 600, 318, 666, 583, 644, 672, 540, 658, 281, 506,
         664, 700, 578, 589, 534, 651, 646, 525, 573, 537, 573, 558, 352, 569, 300, 283, 283, 825, 567, 576, 576, 573, 378, 445,
         381, 567, 513, 293, 525, 558, 292, 576, 567, 360]
URL_NAMES = ('space parenright asterisk comma hyphen period slash zero one two three five six eight nine colon A B C D E H I L N O P '
             'R S U V a b c d e f g i j l m n o p q r s t u v bar aacute eacute iacute oacute uacute parenleft').split()
URL_CHAR = {'space': ' ', 'period': '.', 'bar': '|', 'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'five': '5', 'six': '6',
            'eight': '8', 'nine': '9'}
assert len(URL_W) == 58 and len(URL_NAMES) == 58 and len(URL_CODES) == len(URL_TD) + 1


def url_line():
    ops = 'BT\n/F1 1 Tf\n0 12.646 -12.646 0 591.4733 342.133 Tm\n1 scn\n'
    for i, c in enumerate(URL_CODES):
        last = i == len(URL_CODES) - 1
        adj = 445 if last else (-8 if c == 0 else 18)
        ops += '[<%02x>%d]TJ\n' % (c, adj)
        if not last:
            ops += '%s 0 TD\n' % URL_TD[i]
    ops += 'ET\n'
    p = G.Pdf()
    f = p.add('<< /Type /Font /Subtype /Type1 /BaseFont /YHWCLH+Depot-Bold /FirstChar 0 /LastChar 57 /Widths [%s] '
              '/FontDescriptor << /Type /FontDescriptor /FontName /YHWCLH+Depot-Bold /Flags 262178 /Ascent 686 /Descent -209 '
              '/CapHeight 686 /StemV 145 /FontBBox [-101 -215 1237 991] >> '
              '/Encoding << /Type /Encoding /BaseEncoding /MacRomanEncoding /Differences [0 %s] >> >>'
              % (' '.join(map(str, URL_W)), ' '.join('/' + n for n in URL_NAMES)))
    p, root = G.one_page(ops, {'F1': f}, mediabox='[0 0 623.62 870.24]', p=p)
    text = ''.join(URL_CHAR.get(URL_NAMES[c], URL_NAMES[c]) for c in URL_CODES)
    return p.build(root), text


url_pdf, url_text = url_line()
assert url_text == 'Llame al 900 85 51 23   |   ono.es', url_text
case('gap_zero_url_footer', 'text', url_pdf, txt(url_text))

# gap_zero_last_tilted: pdftotext puts a space in a line turned 45 degrees (AB CD) where the glyphs touch
KNOWN_DIFFERENT = ('gap_words_012', 'gap_tj_words_120', 'gap_turned_uniform', 'gap_zero_last_tilted')


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
            sys.exit('scripts/gen_pdfgap.py: testdata/pdfgap.txt is not what the generator writes')
        print('pdfgap.txt is the generator\'s,', len(CASES), 'cases')
    else:
        open(OUT, 'w').write(text)
        print('wrote', OUT, len(CASES), 'cases')
