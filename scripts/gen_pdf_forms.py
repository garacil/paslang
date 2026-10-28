#!/usr/bin/env python3
"""Writes testdata/pdfform.txt: the PDF forms the paspdfform test fills, each
with the operations to do to it, one line each:

    NAME <TAB> BASE64(pdf) <TAB> OPS

OPS is the operations joined by the character U+0001, each operation's words
joined by U+0002: text NAME VALUE, check NAME 0|1, radio NAME STATE, choice
NAME VALUE, draw PAGE X Y SIZE FONT ALIGN TEXT, needapp, dropxfa; and
fail followed by an operation, which must be refused. The forms are built here
by hand, byte by byte, as scripts/gen_pdf_tests.py builds its files, and fixed:
no clock, no random number.

    python3 scripts/gen_pdf_forms.py [--check | --verify]

--check writes nothing and fails when testdata/pdfform.txt is not what this
makes (make check). --verify fills every form with a script of its own
(the same operations, in Python) and has qpdf --check and qpdf's JSON say that
the file is valid, that every value is the one written, that the file begins
with the original's bytes, and that Ghostscript renders it; the two tools
are not needed anywhere else."""
import base64
import os
import re
import subprocess
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_pdf_tests as G  # noqa: E402

ROOT = G.ROOT
OUT = os.path.join(ROOT, 'testdata', 'pdfform.txt')
SEP = '\x01'
ARG = '\x02'

CASES = []   # (name, pdf, [ops])


def op(*a):
    return ARG.join(str(x) for x in a)


def case(name, pdf, ops):
    CASES.append((name, pdf, ops))


HELV = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>'
ZADB = '<< /Type /Font /Subtype /Type1 /BaseFont /ZapfDingbats >>'


class Form:
    """a one-page form under construction: a Pdf, its page, its fields"""

    def __init__(self, pages=1, da='/Helv 0 Tf 0 g', acro_extra='', direct_acro=False, resources=True, helv=HELV):
        self.p = G.Pdf()
        self.helv = self.p.add(helv)
        self.zadb = self.p.add(ZADB)
        self.pages_n = self.p.reserve()
        self.page_n = [self.p.reserve() for _ in range(pages)]
        self.fields = []
        self.annots = [[] for _ in range(pages)]
        self.da = da
        self.acro_extra = acro_extra
        self.direct_acro = direct_acro
        self.resources = resources
        self.contents = [None] * pages
        self.page_extra = [''] * pages

    def widget(self, extra, rect, ft='Tx', flags=0, name=None, parent=None, page=0, merged_field=True):
        n = self.p.reserve()
        d = '<< /Type /Annot /Subtype /Widget /Rect [%s] /F 4 /P %d 0 R ' % (' '.join(str(x) for x in rect), self.page_n[page])
        if ft:
            d += '/FT /%s ' % ft
        if name is not None:
            d += '/T (%s) ' % name
        if flags:
            d += '/Ff %d ' % flags
        if parent:
            d += '/Parent %d 0 R ' % parent
        d += extra + ' >>'
        self.p.put(n, d)
        self.annots[page].append(n)
        return n

    def field(self, n):
        self.fields.append(n)

    def build(self, mode='table', header=b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'):
        p = self.p
        dr = '<< /Font << /Helv %d 0 R /ZaDb %d 0 R >> >>' % (self.helv, self.zadb)
        acro_body = '<< /Fields [%s] /DR %s %s %s >>' % (' '.join('%d 0 R' % f for f in self.fields), dr, ('/DA (%s)' % self.da) if self.da else '', self.acro_extra)
        if self.direct_acro:
            acro_entry = '/AcroForm ' + acro_body
        else:
            acro = p.add(acro_body)
            acro_entry = '/AcroForm %d 0 R' % acro
        for i, pg in enumerate(self.page_n):
            cont = self.contents[i]
            if cont is None:
                cont = p.stream('', ('BT /F1 10 Tf 72 780 Td (Page %d) Tj ET' % (i + 1)).encode())
            res = '/Resources << /Font << /F1 %d 0 R >> >>' % self.helv if self.resources else ''
            p.put(pg, '<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] /Contents %s %s /Annots [%s] %s >>' % (self.pages_n, cont if isinstance(cont, str) else '%d 0 R' % cont, res, ' '.join('%d 0 R' % a for a in self.annots[i]), self.page_extra[i]))
        pr = '/Resources << /Font << /F1 %d 0 R >> >>' % self.helv if not self.resources else ''
        p.put(self.pages_n, '<< /Type /Pages /Kids [%s] /Count %d %s >>' % (' '.join('%d 0 R' % x for x in self.page_n), len(self.page_n), pr))
        root = p.add('<< /Type /Catalog /Pages %d 0 R %s >>' % (self.pages_n, acro_entry))
        if mode == 'table':
            return p.build(root, header=header)
        members = [n for n in p.bodies if b'stream' not in p.bodies[n]]
        return G.build_xrefstm(p.bodies, root, objstm_members=members)


def standard_form(mode='table', **kw):
    f = Form(**kw)
    p = f.p
    f1 = f.widget('/DA (/Helv 12 Tf 0 g) /MK << /BC [0 0 0] /BG [1 1 0.8] >> /BS << /W 1 /S /S >>', [72, 700, 272, 722], name='name')
    ap2 = p.stream('/Type /XObject /Subtype /Form /BBox [0 0 200 80] /Resources << /Font << /Helv %d 0 R >> >>' % f.helv, b'q 0.9 g 0 0 200 80 re f Q q 0 0 1 RG 1 w 0.5 0.5 199 79 re S Q /Tx BMC q BT /Helv 12 Tf 0 g 2 66 Td () Tj ET Q EMC')
    f2 = f.widget('/DA (/Helv 0 Tf 0 0 0.6 rg) /AP << /N %d 0 R >> /MK << /BC [0 0 1] /BG [0.9] >>' % ap2, [72, 600, 272, 680], name='address', flags=4096)
    f3 = f.widget('/DA (/Helv 14 Tf 0 g) /MaxLen 8 /MK << /BC [0] >>', [72, 560, 232, 582], name='dni', flags=16777216)
    f4 = f.widget('/DA (/Helv 10 Tf 0 g) /Q 2 /MK << /BC [0.5 0.5 0.5] >>', [300, 700, 400, 716], name='amount')
    par = p.reserve()
    k1 = f.widget('/DA (/Helv 11 Tf 0 g) /MK << /BC [0 0 0] >>', [72, 520, 172, 536], ft=None, name='first', parent=par)
    k2 = f.widget('/DA (/Helv 11 Tf 0 g) /MK << /BC [0 0 0] >>', [180, 520, 280, 536], ft=None, name='last', parent=par)
    p.put(par, '<< /T (person) /FT /Tx /Kids [%d 0 R %d 0 R] >>' % (k1, k2))
    on = p.stream('/Type /XObject /Subtype /Form /BBox [0 0 14 14] /Resources << /Font << /ZaDb %d 0 R >> >>' % f.zadb, b'q 0 g BT /ZaDb 12 Tf 2 2 Td (4) Tj ET Q')
    off = p.stream('/Type /XObject /Subtype /Form /BBox [0 0 14 14]', b' ')
    f6 = f.widget('/V /Off /AS /Off /MK << /BC [0] >> /AP << /N << /Yes %d 0 R /Off %d 0 R >> >>' % (on, off), [72, 480, 86, 494], ft='Btn', name='agree')
    rpar = p.reserve()
    rads = []
    for st, y in (('basic', 450), ('plus', 430), ('max', 410)):
        a_on = p.stream('/Type /XObject /Subtype /Form /BBox [0 0 14 14] /Resources << /Font << /ZaDb %d 0 R >> >>' % f.zadb, b'q 0 g BT /ZaDb 12 Tf 2 2 Td (l) Tj ET Q')
        a_off = p.stream('/Type /XObject /Subtype /Form /BBox [0 0 14 14]', b' ')
        rads.append(f.widget('/AS /Off /AP << /N << /%s %d 0 R /Off %d 0 R >> >>' % (st, a_on, a_off), [72, y, 86, y + 14], ft=None, parent=rpar))
    p.put(rpar, '<< /T (plan) /FT /Btn /Ff 32768 /V /Off /Kids [%s] >>' % ' '.join('%d 0 R' % r for r in rads))
    f8 = f.widget('/DA (/Helv 11 Tf 0 g) /Opt [(Madrid) (Barcelona) [(VLC) (Valencia)]] /MK << /BC [0] >>', [300, 650, 420, 668], ft='Ch', name='city', flags=131072)
    f9 = f.widget('/DA (/Helv 11 Tf 0 g) /Opt [(Alpha) (Beta) (Gamma) (Delta) (Epsilon)] /MK << /BC [0] /BG [1] >>', [300, 560, 420, 620], ft='Ch', name='greek')
    f10 = f.widget('/MK << /BC [0] >>', [300, 500, 420, 530], ft='Sig', name='sign')
    for x in (f1, f2, f3, f4, par, f6, rpar, f8, f9, f10):
        f.field(x)
    return f.build(mode)


STD_OPS = [
    op('text', 'name', 'Ana García Núñez'),
    op('text', 'address', 'Calle Mayor 12, 3º B. 28013 Madrid. Línea fija 91 555 01 23 y móvil +34 600 123 456 para avisos.'),
    op('text', 'dni', '12345678'),
    op('text', 'amount', '1.234,56 €'),
    op('text', 'person.first', 'Ana'),
    op('text', 'person.last', 'García'),
    op('check', 'agree', 1),
    op('radio', 'plan', 'plus'),
    op('choice', 'city', 'Valencia'),
    op('choice', 'greek', 'Gamma'),
    op('draw', 0, 72, 760, 11, 'Helvetica', 0, 'Overlay: ref 2026-0042 (Ñandú)'),
    op('draw', 0, 540, 40, 9, 'Times-Roman', 2, 'right aligned'),
    op('draw', 0, 306, 20, 10, 'Courier', 1, 'centred'),
]

case('std_table', standard_form('table'), STD_OPS)
case('std_stm', standard_form('stm'), STD_OPS)
case('std_nothing', standard_form('table'), [])
case('std_off', standard_form('table'), [op('check', 'agree', 1), op('check', 'agree', 0), op('radio', 'plan', 'basic'), op('text', 'name', '')])
case('std_refused', standard_form('table'), [
    op('fail', 'text', 'nosuchfield', 'x'),
    op('fail', 'text', 'agree', 'x'),
    op('fail', 'check', 'name', 1),
    op('fail', 'radio', 'plan', 'gold'),
    op('fail', 'choice', 'city', 'Sevilla'),
    op('fail', 'choice', 'name', 'x'),
    op('fail', 'draw', 0, 10, 10, 10, 'Symbol', 0, 'x'),
    op('fail', 'draw', 3, 10, 10, 10, 'Helvetica', 0, 'x'),
    op('text', 'name', 'still works'),
])
case('std_utf16', standard_form('table'), [op('text', 'name', 'Ω ≈ π €'), op('text', 'address', 'Ünïcödé 日本 ok')])
case('std_maxlen', standard_form('table'), [op('text', 'dni', '123456789012345')])
case('std_multiline_long', standard_form('table'), [op('text', 'address', 'one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty\nsecond paragraph here\r\nthird after crlf')])

# a password field is refused, a read-only one is filled
f = Form()
a = f.widget('/DA (/Helv 12 Tf 0 g) /MK << /BC [0] >>', [72, 700, 272, 720], name='pwd', flags=8192)
b = f.widget('/DA (/Helv 12 Tf 0 g) /MK << /BC [0] >>', [72, 660, 272, 680], name='ro', flags=1)
f.field(a)
f.field(b)
case('flags', f.build(), [op('fail', 'text', 'pwd', 'secret'), op('text', 'ro', 'filled by the program')])

# inherited DA and Q from the AcroForm and the parent; auto sizes
f = Form(da='/Helv 9 Tf 0 0 1 rg', acro_extra='/Q 1')
p = f.p
par = p.reserve()
k = f.widget('/MK << /BC [0] >>', [72, 700, 272, 720], ft=None, name='a', parent=par)
k2 = f.widget('/MK << /BC [0] >>', [72, 660, 272, 676], ft=None, name='b', parent=par)
p.put(par, '<< /T (grp) /FT /Tx /DA (/Helv 0 Tf 1 0 0 rg) /Q 2 /Kids [%d 0 R %d 0 R] >>' % (k, k2))
t = f.widget('/MK << /BC [0] >>', [72, 620, 272, 640], name='top')
f.field(par)
f.field(t)
case('inherit', f.build(), [op('text', 'grp.a', 'right, red, auto'), op('text', 'grp.b', 'right, red, small box'), op('text', 'top', 'centred, blue, 9')])

# two widgets of one field on two pages
f = Form(pages=2)
p = f.p
fp = p.reserve()
w1 = f.widget('/MK << /BC [0] >>', [72, 700, 272, 720], ft=None, parent=fp, page=0)
w2 = f.widget('/MK << /BC [0] >>', [72, 700, 272, 720], ft=None, parent=fp, page=1)
p.put(fp, '<< /T (twice) /FT /Tx /DA (/Helv 12 Tf 0 g) /Kids [%d 0 R %d 0 R] >>' % (w1, w2))
f.field(fp)
case('two_pages', f.build(), [op('text', 'twice', 'on both pages'), op('draw', 0, 72, 40, 9, 'Helvetica', 0, 'page one'), op('draw', 1, 72, 40, 9, 'Helvetica', 0, 'page two'), op('draw', 1, 72, 52, 9, 'Helvetica', 0, 'page two again')])

# buttons with no appearance at all, and with Opt export values
f = Form()
p = f.p
c1 = f.widget('/MK << /BC [0] >>', [72, 700, 86, 714], ft='Btn', name='plainbox')
rp = p.reserve()
r1 = f.widget('/MK << /BC [0] >>', [72, 660, 86, 674], ft=None, parent=rp)
r2 = f.widget('/MK << /BC [0] >>', [72, 640, 86, 654], ft=None, parent=rp)
p.put(rp, '<< /T (opt) /FT /Btn /Ff 32768 /Opt [(red) (green)] /Kids [%d 0 R %d 0 R] >>' % (r1, r2))
f.field(c1)
f.field(rp)
case('noappearance', f.build(), [op('check', 'plainbox', 1), op('radio', 'opt', 'green')])

# a font that cannot be measured, a rotated widget, a missing font: NeedAppearances
f = Form()
p = f.p
tt = p.add('<< /Type /Font /Subtype /TrueType /BaseFont /ArialNarrow /Encoding /WinAnsiEncoding >>')
f.p.bodies[f.helv] = (HELV).encode()
w1 = f.widget('/DA (/TT 12 Tf 0 g) /MK << /BC [0] >>', [72, 700, 272, 720], name='unknownfont')
w2 = f.widget('/DA (/Helv 12 Tf 0 g) /MK << /BC [0] /R 90 >>', [72, 600, 92, 680], name='rotated')
w3 = f.widget('/DA (/Nope 12 Tf 0 g) /MK << /BC [0] >>', [72, 560, 272, 580], name='nofont')
w4 = f.widget('/MK << /BC [0] >>', [72, 520, 272, 540], name='noda')
for x in (w1, w2, w3, w4):
    f.field(x)
f.acro_extra = ''
f.da = ''
f.p.bodies[f.helv] = (HELV).encode()
bld = f.build()
case('needapp', bld, [op('text', 'unknownfont', 'v1'), op('text', 'rotated', 'v2'), op('text', 'nofont', 'v3'), op('text', 'noda', 'v4')])

# the AcroForm inside the catalog, no resources on the page (inherited), contents as an array
f = Form(direct_acro=True, resources=False)
p = f.p
a = p.stream('', b'BT /F1 10 Tf 72 780 Td (first part) Tj')
b = p.stream('', b'0 -14 Td (second part) Tj ET')
wd = f.widget('/DA (/Helv 12 Tf 0 g) /MK << /BC [0] >>', [72, 700, 272, 720], name='direct')
f.field(wd)
f.contents[0] = '[%d 0 R %d 0 R]' % (a, b)
case('direct_acro', f.build(), [op('text', 'direct', 'in a direct AcroForm'), op('draw', 0, 72, 100, 12, 'Helvetica', 0, 'over inherited resources')])
case('direct_acro_stm', Form.build(f, 'stm') if False else f.build('stm'), [op('text', 'direct', 'in a direct AcroForm'), op('draw', 0, 72, 100, 12, 'Helvetica', 0, 'over inherited resources')])

# a page with an indirect Contents array whose graphics state is left changed
f = Form()
p = f.p
c1 = p.stream('', b'BT /F1 10 Tf 72 780 Td (before) Tj ET 0.5 0 0 0.5 0 0 cm 1 0 0 rg')
arr = p.add('[%d 0 R]' % c1)
f.contents[0] = '%d 0 R' % arr
wd = f.widget('/DA (/Helv 12 Tf 0 g) /MK << /BC [0] >>', [72, 700, 272, 720], name='f')
f.field(wd)
case('state_left', f.build(), [op('draw', 0, 200, 300, 14, 'Helvetica', 0, 'not scaled, not red'), op('text', 'f', 'x')])

# no AcroForm at all: text over a page only
f = Form()
f.fields = []
bld = f.build()
bld = bld.replace(b'/AcroForm', b'/AcroFor1')
case('no_acroform', bld, [op('draw', 0, 72, 700, 12, 'Helvetica', 0, 'a page with no form'), op('fail', 'text', 'x', 'y')])

# XFA: kept, then dropped
f = Form(acro_extra='/XFA [(preamble) 99 0 R]')
wd = f.widget('/DA (/Helv 12 Tf 0 g) /MK << /BC [0] >>', [72, 700, 272, 720], name='x')
f.field(wd)
case('xfa_kept', f.build(), [op('text', 'x', 'xfa stays')])
case('xfa_dropped', f.build(), [op('dropxfa'), op('text', 'x', 'xfa goes')])
case('needapp_asked', standard_form('table'), [op('needapp'), op('text', 'name', 'flagged')])

# a file that already was updated twice, and one with a trailing blank
base = standard_form('table')
upd = base + b'\n%comment\n'
case('std_trailing', upd, [op('text', 'name', 'after a trailing comment')])
# several draws on one page in a row, the same font twice
f = Form()
f.fields = []
case('draws', f.build(), [op('draw', 0, 72, 700 - 14 * i, 10, 'Helvetica', 0, 'line %d' % i) for i in range(30)] + [op('draw', 0, 72, 200, 10, 'Arial', 0, 'Arial is Helvetica'), op('draw', 0, 72, 180, 10, 'Times New Roman', 0, 'TNR'), op('draw', 0, 72, 160, 10, 'Courier-BoldOblique', 0, 'cbo')])


# the default font as Acrobat writes it: Standard base, Differences to PDFDocEncoding's Latin letters
LATIN1 = ('Agrave Aacute Acircumflex Atilde Adieresis Aring AE Ccedilla Egrave Eacute Ecircumflex Edieresis Igrave Iacute Icircumflex Idieresis '
          'Eth Ntilde Ograve Oacute Ocircumflex Otilde Odieresis multiply Oslash Ugrave Uacute Ucircumflex Udieresis Yacute Thorn germandbls '
          'agrave aacute acircumflex atilde adieresis aring ae ccedilla egrave eacute ecircumflex edieresis igrave iacute icircumflex idieresis '
          'eth ntilde ograve oacute ocircumflex otilde odieresis divide oslash ugrave uacute ucircumflex udieresis yacute thorn ydieresis').split()
ACROBAT_HELV = ('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Name /Helv /Encoding << /Type /Encoding /Differences '
                '[24 /breve /caron /circumflex /dotaccent /hungarumlaut /ogonek /ring /tilde 39 /quotesingle 96 /grave '
                '128 /bullet /dagger /daggerdbl /ellipsis /emdash /endash /florin /fraction /guilsinglleft /guilsinglright /minus /perthousand '
                '/quotedblbase /quotedblleft /quotedblright /quoteleft /quoteright /quotesinglbase /trademark /fi /fl /Lslash /OE /Scaron /Ydieresis /Zcaron '
                '/dotlessi /lslash /oe /scaron /zcaron 160 /Euro 164 /currency 166 /brokenbar 168 /dieresis /copyright /ordfeminine 172 /logicalnot '
                '/.notdef /registered /macron /degree /plusminus /twosuperior /threesuperior /acute /mu 183 /periodcentered /cedilla /onesuperior '
                '/ordmasculine 188 /onequarter /onehalf /threequarters 191 /questiondown ' + ' '.join('/' + n for n in LATIN1) + '] >> >>')
f = Form(helv=ACROBAT_HELV)
p = f.p
a1 = f.widget('/DA (/Helv 12 Tf 0 g) /MK << /BC [0] >> /AA << /K << /S /JavaScript /JS (AFNumber_Keystroke\\(2,0,0,0,"",true\\);) >> >> /TU (Importe)', [72, 700, 272, 720], name='importe')
a2 = f.widget('/DA (/Helv 0 Tf 0 g) /MK << /BC [0] /BG [1 1 1] >>', [72, 660, 272, 690], name='nombre')
a3 = f.widget('/DA (/Helv 10 Tf 0 g) /MK << /BC [0] /CA (4) >> /Ff 4096', [72, 560, 272, 640], name='notas')
f.field(a1)
f.field(a2)
f.field(a3)
case('acrobat_dr', f.build(), [op('text', 'importe', '1.234,56 € • ½'), op('text', 'nombre', 'José Peña Ñandú, ¿qué tal? Ünïcode ß ÿ'), op('text', 'notas', 'Línea uno\nLínea dos «con comillas» y “otras”')])

# forms other programs wrote (qpdf's linearized, object-stream and QDF rewrites of the standard form)
REAL = os.path.join(ROOT, 'testdata', 'pdfformreal')
if os.path.isdir(REAL):
    for fn in sorted(os.listdir(REAL)):
        if fn.endswith('.pdf'):
            case('real_' + fn[:-4], open(os.path.join(REAL, fn), 'rb').read(), STD_OPS)


def write_corpus():
    lines = []
    for name, pdf, ops in CASES:
        lines.append('%s\t%s\t%s' % (name, base64.b64encode(pdf).decode(), base64.b64encode(SEP.join(ops).encode('utf-8')).decode()))
    return '\n'.join(lines) + '\n'


_DOC = []


class _Doc:
    def __getitem__(self, b):
        if not _DOC:
            import gen_pdfenc as E2
            agl, _ = E2.read_agl()
            _DOC.append(E2.read_tables(agl)[3])
        return _DOC[0][b] if _DOC[0][b] >= 0 else b


DOC = _Doc()


def qpdf_json(fn):
    r = subprocess.run(['qpdf', '--json=2', '--json-output', '--json-stream-data=none', fn], capture_output=True, text=True)
    if r.returncode not in (0, 3):
        return None
    import json
    return json.loads(r.stdout)['qpdf'][1]


def field_table(j):
    """fully qualified name -> field dictionary, from the AcroForm of qpdf's JSON"""
    def obj(ref):
        return j.get('obj:' + ref, {}).get('value')
    root = None
    for k, v in j.items():
        if k == 'trailer':
            root = obj(v['value']['/Root'])
    acro = root.get('/AcroForm') if root else None
    if isinstance(acro, str):
        acro = obj(acro)
    out = {}

    def walk(ref, prefix):
        d = obj(ref)
        if not isinstance(d, dict):
            return
        t = d.get('/T', '')
        t = t[2:] if t.startswith('u:') else t
        name = prefix + ('.' if prefix and t else '') + t
        kids = d.get('/Kids')
        if kids and any(isinstance(obj(k), dict) and ('/T' in obj(k) or '/Kids' in obj(k)) for k in kids):
            for k in kids:
                walk(k, name)
        else:
            out[name] = (d, [obj(k) for k in kids] if kids else [d])
    for r in (acro or {}).get('/Fields', []):
        walk(r, '')
    return out


def verify(dirname):
    """each filled file of dirname (made by the paspdfform test with `out DIR`)
    against what its operations wrote: qpdf --check, qpdf's JSON for the
    values, Ghostscript's rendering, pdftotext for the text laid over the page"""
    bad = 0
    for name, pdf, ops in CASES:
        fn = os.path.join(dirname, name + '.pdf')
        if not os.path.exists(fn):
            print('missing', fn)
            bad += 1
            continue
        out = open(fn, 'rb').read()
        if ops and not out.startswith(pdf):
            print(name, 'does not begin with the original')
            bad += 1
        r = subprocess.run(['qpdf', '--check', fn], capture_output=True, text=True)
        if r.returncode not in (0, 3):
            print(name, 'qpdf --check', r.stdout[-200:], r.stderr[-200:])
            bad += 1
        r = subprocess.run(['gs', '-q', '-dNOPAUSE', '-dBATCH', '-sDEVICE=nullpage', fn], capture_output=True, text=True)
        if r.returncode != 0 or 'rror' in r.stdout + r.stderr:
            print(name, 'ghostscript', (r.stdout + r.stderr)[-200:])
            bad += 1
        j = qpdf_json(fn)
        if j is None:
            print(name, 'no json')
            bad += 1
            continue
        tab = field_table(j)
        text = subprocess.run(['pdftotext', fn, '-'], capture_output=True, text=True).stdout
        flat = re.sub(r'\s+', ' ', text)
        last = {}
        for o in ops:
            a = o.split(ARG)
            if a[0] in ('text', 'choice', 'check', 'radio'):
                last[a[1]] = o
        for o in ops:
            a = o.split(ARG)
            if a[0] == 'fail':
                continue
            if a[0] in ('text', 'choice', 'check', 'radio') and last.get(a[1]) != o:
                continue
            if a[0] in ('text', 'choice', 'check', 'radio'):
                ent = tab.get(a[1])
                if ent is None:
                    print(name, 'no field', a[1])
                    bad += 1
                    continue
                d, widgets = ent
                v = d.get('/V')
                if a[0] == 'text':
                    want = 'u:' + a[2]
                    if isinstance(v, str) and v.startswith('b:'):
                        # bytes in PDFDocEncoding, which qpdf shows as hexadecimal
                        v = 'u:' + ''.join(chr(DOC[b]) for b in bytes.fromhex(v[2:]))
                    if v != want and v != a[2]:
                        # a text outside PDFDocEncoding is UTF-16: qpdf shows u:
                        print(name, a[1], 'value', repr(v), 'wanted', repr(want))
                        bad += 1
                elif a[0] == 'check':
                    if a[2] == '1':
                        ok = v not in (None, '/Off') and all(w.get('/AS') == v for w in widgets)
                    else:
                        ok = v == '/Off' and all(w.get('/AS') == '/Off' for w in widgets)
                    if not ok:
                        print(name, a[1], 'check', v, [w.get('/AS') for w in widgets])
                        bad += 1
                elif a[0] == 'radio':
                    ons = [w for w in widgets if w.get('/AS') not in (None, '/Off')]
                    if v in (None, '/Off') or len(ons) != 1:
                        print(name, a[1], 'radio', v, [w.get('/AS') for w in widgets])
                        bad += 1
            elif a[0] == 'draw':
                want = re.sub(r'\s+', ' ', a[7])
                if want not in flat:
                    print(name, 'text not on the page:', want)
                    bad += 1
    return bad


if __name__ == '__main__':
    if '--verify' in sys.argv:
        d = sys.argv[sys.argv.index('--verify') + 1]
        n = verify(d)
        print('verified', len(CASES), 'forms, problems', n)
        sys.exit(1 if n else 0)
    text = write_corpus()
    if '--check' in sys.argv:
        if open(OUT).read() != text:
            sys.exit('scripts/gen_pdf_forms.py: testdata/pdfform.txt is not what the generator writes')
        print('pdfform.txt is the generator\'s,', len(CASES), 'cases')
    else:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        open(OUT, 'w').write(text)
        print('wrote', OUT, len(CASES), 'cases')
