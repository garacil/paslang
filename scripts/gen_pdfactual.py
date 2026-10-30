#!/usr/bin/env python3
"""Writes testdata/pdfactual.txt: the PDF files the paspdf replacement-text test
reads, each with the text it must give (P516). A marked-content sequence with
the tag Span may carry an ActualText entry, "an exact replacement" for the
content it holds (ISO 32000-1 14.9.4): a producer writes it for a ligature, a
hyphen, a glyph its font has no Unicode for, a character drawn as a shape.
Chromium writes /Span <</ActualText <feff672c>>> BDC <0000> Tj EMC for a
character its font lacks. The reader gives the text of the entry once, where
the first string of the sequence begins, and none of the glyphs' own; of
nested sequences the outermost counts; consecutive ones have no break
between them. The files are built here byte by byte; fixed seed, no clock.

    python3 scripts/gen_pdfactual.py [--check | --verify]

--check writes nothing and fails when testdata/pdfactual.txt is not what this
makes (make check). --verify checks every file with qpdf --check and compares
the characters with pdftotext's, white space left out (the files in
KNOWN_DIFFERENT differ on purpose, see there; neither tool is needed anywhere
else)."""
import base64
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_pdf_tests as G  # noqa: E402

ROOT = G.ROOT
OUT = os.path.join(ROOT, 'testdata', 'pdfactual.txt')
CASES = []   # (name, kind, pdf bytes, expected bytes, valid, compare with pdftotext)
T = 'BT /F 12 Tf 72 700 Td '


def case(name, kind, pdf, expect, valid=True, cmp=True):
    CASES.append((name, kind, pdf, expect.encode('utf-8') if isinstance(expect, str) else expect, valid, cmp))


def txt(*pages):
    return ''.join(pg + '\n\f' for pg in pages)


def u16(t):
    """a text string in UTF-16BE with the byte order mark, as a hex string"""
    return '<feff' + t.encode('utf-16-be').hex() + '>'


def doc(content, extra_res='', p=None, font='F'):
    p = p or G.Pdf()
    f = G.font_simple(p, base='Helvetica')
    p, root = G.one_page(content, {font: f}, extra_res=extra_res, p=p)
    return p.build(root)


def span(text, glyphs, tag='Span'):
    return '/%s <</ActualText %s>> BDC %s EMC ' % (tag, text, glyphs)


# ---------------------------------------------------------------------------
# 1. one sequence
case('act_one_glyph', 'text', doc(T + '(a) Tj ' + span(u16('é'), '(X) Tj') + '(c) Tj ET'), txt('aéc'))
case('act_plain_string', 'text', doc(T + '(a) Tj ' + span('(Q)', '(X) Tj') + '(c) Tj ET'), txt('aQc'))
case('act_several_strings', 'text', doc(T + span('(WORD)', '(ab) Tj (cd) Tj (ef) Tj') + '( z) Tj ET'), txt('WORD z'))
case('act_tj_array', 'text', doc(T + span('(WORD)', '[(ab) -50 (cd)] TJ') + 'ET'), txt('WORD'))
case('act_no_glyph', 'text', doc(T + '(a) Tj ' + span('(NONE)', '') + '(c) Tj ET'), txt('ac'))
case('act_space_in_span', 'text', doc(T + span('(X)', '(a b) Tj') + 'ET'), txt('X'))
case('act_spaces_in_text', 'text', doc(T + '(a) Tj ' + span('( q )', '(X) Tj') + '(b) Tj ET'), txt('a q b'))
case('act_other_keys', 'text',
     doc(T + '/Span <</Lang (en) /ActualText (K) /MCID 3>> BDC (ab) Tj EMC ET'), txt('K'))
case('act_invisible', 'text', doc(T + '3 Tr ' + span('(K)', '(ab) Tj') + 'ET'), txt('K'))

# 2. what text strings may be
case('act_utf16', 'text', doc(T + span(u16('日本'), '(ab) Tj') + 'ET'), txt('日本'))
# the ligature a producer says (Skia writes U+FB01 for the fi it drew as one glyph) is written as its letters, as the glyphs' own are
case('act_ligature', 'text', doc(T + span(u16('\ufb01'), '(X) Tj') + '(nal) Tj ET'), txt('final'))
case('act_escapes', 'text', doc(T + span('(a\\(b\\)c\\\\d\\101)', '(ab) Tj') + 'ET'), txt('a(b)c\\dA'))
case('act_escaped_close', 'text', doc(T + span('(a\\)bbbbbbbbbb)', '(ab) Tj') + 'ET'), txt('a)bbbbbbbbbb'))
case('act_nested_parentheses', 'text', doc(T + span('(a(b(c))d)', '(ab) Tj') + 'ET'), txt('a(b(c))d'))
case('act_pdfdoc', 'text', doc(T + span('(caf\\351)', '(ab) Tj') + 'ET'), txt('café'))
# the escape sequences of the language are not text (7.9.2.2); pdftotext leaves them in
case('act_language', 'text', doc(T + span('<feff001b0065006e001b00480069>', '(ab) Tj') + 'ET'), txt('Hi'), cmp=False)
# the glyphs are replaced by nothing; pdftotext leaves a gap where they were
case('act_empty', 'text', doc(T + '(a) Tj ' + span('()', '(XYZ) Tj') + '(c) Tj ET'), txt('ac'))

# 3. the tag, the property list
case('act_tag_p', 'text', doc(T + span('(PP)', '(ab) Tj', tag='P') + 'ET'), txt('ab'))
case('act_properties', 'text',
     doc(T + '/Span /MC0 BDC (ab) Tj EMC ET', extra_res='/Properties << /MC0 << /ActualText (RES) >> >>'), txt('RES'))
case('act_properties_missing', 'text', doc(T + '/Span /MC9 BDC (ab) Tj EMC ET'), txt('ab'))

# 4. how sequences nest and follow one another
case('act_consecutive', 'text', doc(T + span('(n)', '(A) Tj') + span('(o)', '(B) Tj') + '(-) Tj ET'), txt('no-'))
case('act_inner_only', 'text',
     doc(T + '/Span <</Lang (en)>> BDC (ab) Tj ' + span('(IN)', '(cd) Tj') + '(ef) Tj EMC ET'), txt('abINef'))
# the outermost counts (the specification: the value replaces the content);
# pdftotext keeps the inner one
case('act_nested', 'text',
     doc(T + '/Span <</ActualText (OUT)>> BDC (ab) Tj ' + span('(IN)', '(cd) Tj') + '(ef) Tj EMC ET'), txt('OUT'), cmp=False)
case('act_bmc_inside', 'text', doc(T + '/Span <</ActualText (OUT)>> BDC /Foo BMC (ab) Tj EMC (cd) Tj EMC (z) Tj ET'), txt('OUTz'))
case('act_unbalanced_emc', 'text', doc(T + '(a) Tj EMC (b) Tj ET'), txt('ab'))
case('act_across_text_objects', 'text',
     doc('/Span <</ActualText (WHOLE)>> BDC ' + T + '(ab) Tj ET BT /F 12 Tf 72 680 Td (cd) Tj ET EMC'), txt('WHOLE'))
case('act_spec_example', 'text', doc(T + '(Dru) Tj ' + span('(c)', '(k-) Tj') + '(ker) Tj ET'), txt('Drucker'))
deep = '/Span <</ActualText (XY)>> BDC ' + '/A BMC ' * 299 + '(ab) Tj ' + 'EMC ' * 300
case('act_deep', 'text', doc(T + deep + '(cd) Tj ET'), txt('XYcd'))
case('act_deep_unclosed', 'text', doc(T + '/A BMC ' * 400 + '(ab) Tj ' + 'EMC ' * 100 + '(cd) Tj ET'), txt('abcd'))

case('act_empty_string_only', 'text', doc(T + '(a) Tj /Span <</ActualText (NONE)>> BDC () Tj EMC (c) Tj ET'), txt('ac'))
# the levels a reader keeps are bounded (256); a sequence beyond them is not read
case('act_depth_five', 'text', doc(T + '/A BMC ' * 5 + span('(K)', '(ab) Tj') + 'EMC ' * 5 + 'ET'), txt('K'))
case('act_depth_over', 'text', doc(T + '/A BMC ' * 300 + span('(K)', '(ab) Tj') + 'EMC ' * 300 + 'ET'), txt('ab'), cmp=False)

# 5. forms and pages
p = G.Pdf()
f1 = G.font_simple(p, base='Helvetica')
form = p.stream('/Type /XObject /Subtype /Form /BBox [0 0 612 792] /Resources << /Font << /F %d 0 R >> >>' % f1,
                (T + span('(FORM)', '(ab) Tj') + 'ET').encode())
p, root = G.one_page('BT /F 12 Tf 72 680 Td (x) Tj ET /X1 Do', {'F': f1}, extra_res='/XObject << /X1 %d 0 R >>' % form, p=p)
case('act_form', 'text', p.build(root), txt('FORM\nx'))

# a form that opens a sequence and leaves it open does not hold the page's text
p = G.Pdf()
f1 = G.font_simple(p, base='Helvetica')
form = p.stream('/Type /XObject /Subtype /Form /BBox [0 0 612 792] /Resources << /Font << /F %d 0 R >> >>' % f1,
                (T.replace('700', '720') + '/Span <</ActualText (FORM)>> BDC (ab) Tj ET').encode())
p, root = G.one_page('/X1 Do BT /F 12 Tf 72 680 Td (tail) Tj ET', {'F': f1}, extra_res='/XObject << /X1 %d 0 R >>' % form, p=p)
# pdftotext keeps the sequence open to the end of the page and reads nothing
case('act_form_left_open', 'text', p.build(root), txt('FORM\ntail'), cmp=False)

# a form that ends one it did not begin does not end the page's
p = G.Pdf()
f1 = G.font_simple(p, base='Helvetica')
form = p.stream('/Type /XObject /Subtype /Form /BBox [0 0 612 792] /Resources << /Font << /F %d 0 R >> >>' % f1,
                ('EMC ' + T + '(ab) Tj ET').encode())
p, root = G.one_page('/Span <</ActualText (PAGE)>> BDC /X1 Do BT /F 12 Tf 72 680 Td (cd) Tj ET EMC BT /F 12 Tf 72 660 Td (z) Tj ET',
                     {'F': f1}, extra_res='/XObject << /X1 %d 0 R >>' % form, p=p)
# pdftotext ends the page's sequence at the form's EMC
case('act_form_extra_emc', 'text', p.build(root), txt('PAGE\nz'), cmp=False)

# a sequence left open on a page does not hold the next page's text
p = G.Pdf()
f1 = G.font_simple(p, base='Helvetica')
c1 = p.stream('', ('/Span <</ActualText (P1)>> BDC ' + T + '(ab) Tj ET').encode())
c2 = p.stream('', (T + '(cd) Tj ET').encode())
pages = p.reserve()
pg = [p.add('<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] /Contents %d 0 R /Resources << /Font << /F %d 0 R >> >> >>' % (pages, c, f1))
      for c in (c1, c2)]
p.put(pages, '<< /Type /Pages /Kids [%s] /Count 2 >>' % ' '.join('%d 0 R' % n for n in pg))
root = p.add('<< /Type /Catalog /Pages %d 0 R >>' % pages)
case('act_two_pages', 'text', p.build(root), txt('P1', 'cd'), cmp=False)

# 6. the replacement of a string drawn twice is read once
case('act_drawn_twice', 'text',
     doc(T + span('(XY)', '(ab) Tj') + 'ET BT /F 12 Tf 72.3 700 Td ' + span('(XY)', '(ab) Tj') + 'ET'), txt('XY'))

# 7. damaged operands: the sequence is read as far as it can be
case('act_damaged_dict', 'text', doc(T + '/Span <</ActualText ( BDC (ab) Tj EMC ET'), txt(''), valid=False, cmp=False)
case('act_no_operands', 'text', doc(T + 'BDC (ab) Tj EMC ET'), txt('ab'), cmp=False)
case('act_actualtext_not_a_string', 'text', doc(T + '/Span <</ActualText 12>> BDC (ab) Tj EMC ET'), txt('ab'))

KNOWN_DIFFERENT = ('act_language', 'act_nested', 'act_damaged_dict', 'act_form_left_open', 'act_form_extra_emc',
                   'act_two_pages', 'act_no_operands', 'act_depth_over')


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
            a = sorted(re.sub(r'\s', '', unicodedata.normalize('NFKC', t)))
            b = sorted(re.sub(r'\s', '', unicodedata.normalize('NFKC', expect.decode('utf-8'))))
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
            sys.exit('scripts/gen_pdfactual.py: testdata/pdfactual.txt is not what the generator writes')
        print('pdfactual.txt is the generator\'s,', len(CASES), 'cases')
    else:
        open(OUT, 'w').write(text)
        print('wrote', OUT, len(CASES), 'cases')
