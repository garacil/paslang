#!/usr/bin/env python3
"""Writes testdata/pdfannot.txt: the PDF files the paspdf annotation test reads,
each with the text it must give (P521). The text of a page is not all in its
content stream: a form field (a widget) draws its value from its appearance
stream, a stamp or a free text note its own, and a file filled in by a program
that does not write the page again has its customer's data only there. The
reader gives, after the page's own text, that of the annotations that are shown
(not those with the flag Hidden, 2, or NoView, 32): the normal appearance of
each (/AP /N, or for a dictionary of states the one /AS names, else Off, else
the first), drawn into the box of the annotation's Rect as ISO 32000-1 12.5.5
(Algorithm 8.1) asks; and for a text or choice widget that has no appearance
its value, the options of a list box, a star for each character of a password.
The files are built here byte by byte; fixed seed, no clock.

    python3 scripts/gen_pdfannot.py [--check | --verify]

--check writes nothing and fails when testdata/pdfannot.txt is not what this
makes (make check). --verify checks every file with qpdf --check and compares
the words with pdftotext's as a multiset (it lays the annotations out with
blank lines of its own; the files in KNOWN_DIFFERENT differ on purpose; neither
tool is needed anywhere else)."""
import base64
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_pdf_tests as G  # noqa: E402

ROOT = G.ROOT
OUT = os.path.join(ROOT, 'testdata', 'pdfannot.txt')
CASES = []   # (name, kind, pdf bytes, expected bytes, valid, compare with pdftotext)
PAGE = b'BT /Helv 12 Tf 72 700 Td (Page text) Tj ET'


def case(name, kind, pdf, expect, valid=True, cmp=True):
    CASES.append((name, kind, pdf, expect.encode('utf-8') if isinstance(expect, str) else expect, valid, cmp))


def txt(*pages):
    return ''.join(pg + '\n\f' for pg in pages)


def build(annots, acro_extra='', page=PAGE):
    """one page and these annotations: functions (p, font) -> object number"""
    p = G.Pdf()
    f1 = G.font_simple(p, base='Helvetica')
    ids = [a(p, f1) for a in annots]
    cont = p.stream('', page)
    pages = p.reserve()
    pg = p.add('<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] /Contents %d 0 R /Resources << /Font << /Helv %d 0 R >> >> /Annots [%s] >>'
               % (pages, cont, f1, ' '.join('%d 0 R' % i for i in ids)))
    p.put(pages, '<< /Type /Pages /Kids [%d 0 R] /Count 1 >>' % pg)
    root = p.add('<< /Type /Catalog /Pages %d 0 R /AcroForm << /Fields [%s] /DA (/Helv 12 Tf 0 g) /DR << /Font << /Helv %d 0 R >> >> %s >> >>'
                 % (pages, ' '.join('%d 0 R' % i for i in ids), f1, acro_extra))
    return p.build(root)


def ap(p, f1, text, bbox='[0 0 200 20]', extra=''):
    return p.stream('/Type /XObject /Subtype /Form /BBox %s %s /Resources << /Font << /Helv %d 0 R >> >>' % (bbox, extra, f1),
                    ('BT /Helv 12 Tf 2 5 Td (%s) Tj ET' % text).encode())


def widget(text, flags=4, rect='[72 600 272 620]', bbox='[0 0 200 20]', extra='', apextra='', sub='Widget'):
    def b(p, f1):
        a = ap(p, f1, text, bbox, apextra)
        return p.add('<< /Type /Annot /Subtype /%s /FT /Tx /T (f) /Rect %s /AP << /N %d 0 R >> /F %d %s >>' % (sub, rect, a, flags, extra))
    return b


def raw(dictionary):
    def b(p, f1):
        return p.add(dictionary)
    return b


# ---------------------------------------------------------------------------
# 1. the appearance, by flags
case('annot_widget', 'text', build([widget('A1')]), txt('Page text\nA1'))
case('annot_hidden', 'text', build([widget('A2', flags=2)]), txt('Page text'))
case('annot_noview', 'text', build([widget('A3', flags=32)]), txt('Page text'))
case('annot_hidden_and_print', 'text', build([widget('A3b', flags=6)]), txt('Page text'))
case('annot_invisible_flag', 'text', build([widget('A4', flags=1)]), txt('Page text\nA4'))
case('annot_print', 'text', build([widget('A5', flags=4)]), txt('Page text\nA5'))
case('annot_no_flags', 'text', build([widget('A6', flags=0)]), txt('Page text\nA6'))
case('annot_free_text', 'text', build([widget('Note in a box', sub='FreeText')]), txt('Page text\nNote in a box'))
case('annot_stamp', 'text', build([widget('APPROVED', sub='Stamp')]), txt('Page text\nAPPROVED'))
case('annot_popup', 'text', build([widget('POPUPTEXT', sub='Popup')]), txt('Page text\nPOPUPTEXT'))
case('annot_oc_dict', 'text', build([widget('OCTEXT', extra='/OC << /Type /OCMD /OCGs [] >>')]), txt('Page text\nOCTEXT'))

# 2. where it is: the box of the appearance goes to the Rect
case('annot_bbox_smaller', 'text', build([widget('A7', bbox='[0 0 100 20]')]), txt('Page text\nA7'))
case('annot_bbox_offset', 'text', build([widget('A8', bbox='[50 50 250 70]')]), txt('Page text\nA8'))
case('annot_matrix_turned', 'text', build([widget('A9', apextra='/Matrix [0 1 -1 0 0 0]', bbox='[0 0 20 200]')]), txt('Page text\nA9'))
case('annot_rect_upside_down', 'text', build([widget('SW', rect='[272 620 72 600]')]), txt('Page text\nSW'))
case('annot_two_widgets', 'text', build([widget('B1', rect='[72 600 272 620]'), widget('B2', rect='[72 560 272 580]')]), txt('Page text\nB1\nB2'))
case('annot_same_line', 'text', build([widget('C1', rect='[200 698 400 718]')]), txt('Page text C1'))
case('annot_above_page_text', 'text', build([widget('TOP', rect='[72 740 272 760]')]), txt('TOP\nPage text'))


# the scale and the order of the Rect decide where the text falls: two fields one above the other
def scaled(p, f1):
    a = ap(p, f1, 'P')
    return p.add('<< /Type /Annot /Subtype /Widget /FT /Tx /T (p) /Rect [72 600 272 700] /AP << /N %d 0 R >> /F 4 >>' % a)


case('annot_scale_y', 'text', build([scaled, widget('Q', rect='[72 612 272 632]')]), txt('Page text\nP\nQ'))
case('annot_rect_order', 'text', build([widget('A', rect='[272 620 72 600]'), widget('B', rect='[72 605 272 625]')]), txt('Page text\nB\nA'))

# 3. states
def states(asx, vx='', order=0):
    def b(p, f1):
        on = ap(p, f1, 'ON')
        off = ap(p, f1, 'OFF')
        st = '/Yes %d 0 R /Off %d 0 R' % (on, off) if order == 0 else '/Off %d 0 R /Yes %d 0 R' % (off, on)
        return p.add('<< /Type /Annot /Subtype /Widget /FT /Btn /T (c) %s %s /Rect [72 480 272 500] /AP << /N << %s >> >> /F 4 >>' % (asx, vx, st))
    return b


case('annot_state_yes', 'text', build([states('/AS /Yes', '/V /Yes')]), txt('Page text\nON'))
case('annot_state_off', 'text', build([states('/AS /Off', '/V /Yes')]), txt('Page text\nOFF'))
case('annot_state_none', 'text', build([states('')]), txt('Page text\nOFF'))
case('annot_state_none_off_first', 'text', build([states('', order=1)]), txt('Page text\nOFF'))


def only_yes(p, f1):
    on = ap(p, f1, 'ON')
    return p.add('<< /Type /Annot /Subtype /Widget /FT /Btn /T (c) /Rect [72 480 272 500] /AP << /N << /Yes %d 0 R >> >> /F 4 >>' % on)


case('annot_state_only_yes', 'text', build([only_yes]), txt('Page text\nON'))
# pdftotext draws a check mark of its own for a state the annotation names and has not
case('annot_state_missing', 'text', build([states('/AS /Zzz')]), txt('Page text'), cmp=False)

# 4. no appearance: the value of the field
case('annot_value_only', 'text', build([raw('<< /Type /Annot /Subtype /Widget /FT /Tx /T (n) /V (Value only) /Rect [72 520 272 540] /F 4 /DA (/Helv 12 Tf 0 g) >>')]), txt('Page text\nValue only'))
case('annot_value_need_appearances', 'text', build([raw('<< /Type /Annot /Subtype /Widget /FT /Tx /T (n) /V (Value only) /Rect [72 520 272 540] /F 4 >>')], acro_extra='/NeedAppearances true'), txt('Page text\nValue only'))
case('annot_value_utf16', 'text', build([raw('<< /Type /Annot /Subtype /Widget /FT /Tx /T (u) /V <feff00e90074006f0069006c0065> /Rect [72 600 272 620] /F 4 >>')]), txt('Page text\nétoile'))
case('annot_value_empty', 'text', build([raw('<< /Type /Annot /Subtype /Widget /FT /Tx /T (e) /V () /Rect [72 600 272 620] /F 4 >>')]), txt('Page text'))
case('annot_value_hidden', 'text', build([raw('<< /Type /Annot /Subtype /Widget /FT /Tx /T (h) /V (not shown) /Rect [72 600 272 620] /F 2 >>')]), txt('Page text'))
case('annot_value_multiline', 'text', build([raw('<< /Type /Annot /Subtype /Widget /FT /Tx /Ff 4096 /T (ml) /V (line one\\rline two\\nline three) /Rect [72 600 272 680] /F 4 /DA (/Helv 12 Tf 0 g) >>')]),
     txt('Page text\nline one\nline two\nline three'))
case('annot_value_password', 'text', build([raw('<< /Type /Annot /Subtype /Widget /FT /Tx /Ff 8192 /T (pw) /V (secret123) /Rect [72 600 272 620] /F 4 >>')]), txt('Page text\n*********'))
case('annot_value_size_zero', 'text', build([raw('<< /Type /Annot /Subtype /Widget /FT /Tx /T (s) /V (Tiny) /DA (/Helv 0 Tf 0 g) /Rect [72 600 272 606] /F 4 >>')]), txt('Page text\nTiny'))
case('annot_list_box', 'text', build([raw('<< /Type /Annot /Subtype /Widget /FT /Ch /T (c) /V (Option two) /Opt [(Option one) (Option two)] /Rect [72 600 272 640] /F 4 >>')]), txt('Page text\nOption one\nOption two'))
case('annot_radio_no_appearance', 'text', build([raw('<< /Type /Annot /Subtype /Widget /FT /Btn /Ff 32768 /T (r) /V /A /Rect [72 480 272 500] /F 4 >>')]), txt('Page text'))


def inherited(p, f1):
    par = p.reserve()
    kid = p.add('<< /Type /Annot /Subtype /Widget /Parent %d 0 R /Rect [72 600 272 620] /F 4 >>' % par)
    p.put(par, '<< /FT /Tx /T (par) /V (Inherited value) /DA (/Helv 10 Tf 0 g) /Kids [%d 0 R] >>' % kid)
    return kid


case('annot_value_from_parent', 'text', build([inherited]), txt('Page text\nInherited value'))

# 5. what has no text
case('annot_value_of_a_stamp', 'text', build([raw('<< /Type /Annot /Subtype /Stamp /FT /Tx /V (not a field) /Rect [72 600 272 620] /F 4 >>')]), txt('Page text'))
case('annot_value_of_a_button', 'text', build([raw('<< /Type /Annot /Subtype /Widget /FT /Btn /T (b) /V (a string) /Rect [72 600 272 620] /F 4 >>')]), txt('Page text'))
case('annot_link', 'text', build([raw('<< /Type /Annot /Subtype /Link /Rect [72 360 272 380] /Border [0 0 0] /A << /S /URI /URI (http://x.y) >> >>')]), txt('Page text'))
case('annot_note_no_appearance', 'text', build([raw('<< /Type /Annot /Subtype /Text /Contents (sticky note) /Rect [72 320 92 340] /F 4 >>')]), txt('Page text'))


# 6. what the page left in the state of the graphics and of the marked content
case('annot_after_unbalanced_page', 'text',
     build([widget('A1', rect='[72 600 272 620]')], page=b'q 2 0 0 2 0 0 cm BT /Helv 12 Tf 36 350 Td (Page text) Tj ET'), txt('Page text\nA1'))
case('annot_after_open_span', 'text',
     build([widget('A1')], page=b'/Span <</ActualText (X)>> BDC BT /Helv 12 Tf 72 700 Td (Page text) Tj ET'), txt('X\nA1'), cmp=False)

# 7. hostile
def selfref(p, f1):
    a = p.reserve()
    p.stream('/Type /XObject /Subtype /Form /BBox [0 0 200 20] /Resources << /Font << /Helv %d 0 R >> /XObject << /Me %d 0 R >> >>' % (f1, a),
             b'BT /Helv 12 Tf 2 5 Td (LOOP) Tj ET /Me Do', n=a)
    return p.add('<< /Type /Annot /Subtype /Widget /FT /Tx /T (s) /Rect [72 600 272 620] /AP << /N %d 0 R >> /F 4 >>' % a)


case('annot_appearance_draws_itself', 'text', build([selfref]), txt('Page text\nLOOP'))


def parent_loop(p, f1):
    par = p.reserve()
    kid = p.add('<< /Type /Annot /Subtype /Widget /Parent %d 0 R /Rect [72 600 272 620] /F 4 >>' % par)
    p.put(par, '<< /Parent %d 0 R /Kids [%d 0 R] >>' % (par, kid))
    return kid


case('annot_parent_loop', 'text', build([parent_loop]), txt('Page text'))
case('annot_not_a_dictionary', 'text', build([raw('(a string)'), raw('42'), widget('OK')]), txt('Page text\nOK'))
case('annot_no_rect', 'text', build([raw('<< /Type /Annot /Subtype /Widget /FT /Tx /V (no rect) /F 4 >>')]), txt('Page text'))


def build_many(n):
    """n annotations that share one appearance and meet in one place"""
    p = G.Pdf()
    f1 = G.font_simple(p, base='Helvetica')
    a = ap(p, f1, 'SHARED')
    ids = [p.add('<< /Type /Annot /Subtype /Widget /FT /Tx /T (f) /Rect [72 500 272 520] /AP << /N %d 0 R >> /F 4 >>' % a) for i in range(n)]
    cont = p.stream('', PAGE)
    pages = p.reserve()
    pg = p.add('<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] /Contents %d 0 R /Resources << /Font << /Helv %d 0 R >> >> /Annots [%s] >>'
               % (pages, cont, f1, ' '.join('%d 0 R' % i for i in ids)))
    p.put(pages, '<< /Type /Pages /Kids [%d 0 R] /Count 1 >>' % pg)
    root = p.add('<< /Type /Catalog /Pages %d 0 R >>' % pages)
    return p.build(root)


# one appearance shared by 200 annotations of one place: read once (P514)
case('annot_shared_appearance', 'text', build_many(200), txt('Page text\nSHARED'))

KNOWN_DIFFERENT = ('annot_state_missing', 'annot_after_open_span')


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
            sys.exit('scripts/gen_pdfannot.py: testdata/pdfannot.txt is not what the generator writes')
        print('pdfannot.txt is the generator\'s,', len(CASES), 'cases')
    else:
        open(OUT, 'w').write(text)
        print('wrote', OUT, len(CASES), 'cases')
