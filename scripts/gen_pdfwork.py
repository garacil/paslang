#!/usr/bin/env python3
"""Writes testdata/pdfwork.txt: the PDF files the paspdf work-limit test reads,
each with the text it must give under the limits it names (P520). A form that
draws forms is a few bytes for many: ten forms that each draw ten, twelve deep,
are a file of a few hundred bytes and ten to the twelfth draws, and the reader
of a service that takes the files of its customers would not return. A page now
reads at most PageWorkLimit bytes of content stream (a form counted again each
time it is drawn; 100 MB by default) and a document DocWorkLimit (1 GB); what
is past them is left out, with a warning. The files here are small and the
limits in the test smaller, so that it runs in no time; each says the limits it
is read with in its kind:

    limit:PAGE:DOC:WARNINGS   the text, and how many warnings say that a limit
                              was reached (one for each page that reached one)

The text expected is made here by running the reading of the page again in
Python: the bytes of each content stream added as it is read, and from the
first one that does not fit (the page's total past the limit) nothing more. The
files are built here byte by byte; fixed seed, no clock.

    python3 scripts/gen_pdfwork.py [--check | --verify]

--check writes nothing and fails when testdata/pdfwork.txt is not what this
makes (make check). --verify checks every file with qpdf --check (neither tool
is needed anywhere else)."""
import base64
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_pdf_tests as G  # noqa: E402

ROOT = G.ROOT
OUT = os.path.join(ROOT, 'testdata', 'pdfwork.txt')
CASES = []   # (name, kind, pdf bytes, expected bytes, valid)


def case(name, kind, pdf, expect):
    CASES.append((name, kind, pdf, expect.encode('utf-8') if isinstance(expect, str) else expect))


def txt(*pages):
    return ''.join(pg + '\n\f' for pg in pages)


# a tree of forms: level k draws the form of level k + 1 `fan` times, moving
# down by STEP[k] before each; the last level shows a line
def tree(depth, fan, steps):
    p = G.Pdf()
    f1 = G.font_simple(p, base='Helvetica')
    ids = [p.reserve() for _ in range(depth + 1)]
    bodies = []
    for k in range(depth + 1):
        res = '/Resources << /Font << /F %d 0 R >> /XObject << /X %d 0 R >> >>' % (f1, ids[k + 1] if k < depth else ids[k])
        if k == depth:
            body = 'BT /F 12 Tf 72 700 Td (leaf) Tj ET'
        else:
            body = ' '.join('1 0 0 1 0 -%d cm /X Do' % steps[k] for _ in range(fan))
        bodies.append(body)
        p.stream('/Type /XObject /Subtype /Form /BBox [0 0 612 792] ' + res, body.encode(), n=ids[k])
    page = '/X Do'
    p, root = G.one_page(page, {'F': f1}, extra_res='/XObject << /X %d 0 R >>' % ids[0], p=p)
    return p.build(root), page, bodies


def tree_case(name, depth, fan, steps, limit):
    pdf, page, bodies = tree(depth, fan, steps)
    # level -1 (the page) draws level 0 once with no shift
    work = [0]
    ys = []
    cut = [False]

    def run(data_len, level, dy):
        if work[0] + data_len > limit:
            work[0] = limit + 1
            cut[0] = True
            return
        work[0] += data_len
        if level == depth:
            ys.append(dy)
            return
        shift = dy
        for _ in range(fan):
            shift += steps[level]
            run(len(bodies[level + 1]), level + 1, shift)
    # the page's content is read first, then the form it draws
    if work[0] + len(page) > limit:
        cut[0] = True
    else:
        work[0] += len(page)
        run(len(bodies[0]), 0, 0)
    text = '\n'.join(['leaf'] * len(set(ys)))
    case(name, 'limit:%d:1000000000:%d' % (limit, 1 if cut[0] else 0), pdf, txt(text))


# 1. a tree that fits: 8 leaves, each at its own height
tree_case('work_fits', 3, 2, [100, 20, 5], 100000)
# 2. the same under limits that cut it: the first leaves are read, the rest left out
tree_case('work_cut_100', 3, 2, [100, 20, 5], 100)
tree_case('work_cut_60', 3, 2, [100, 20, 5], 60)
tree_case('work_cut_all', 3, 2, [100, 20, 5], 10)
# 3. a tree of 10 forms to a form, 6 deep: a million draws, a few hundred bytes
tree_case('work_square_bomb', 6, 10, [5000, 500, 50, 20, 10, 5], 20000)
tree_case('work_square_bomb_fits', 3, 10, [5000, 500, 50], 100000)

# 4. the limit of the document: two pages of the same size, the limit of the
# document a page and a half
p = G.Pdf()
f1 = G.font_simple(p, base='Helvetica')
c1 = ('BT /F 12 Tf 72 700 Td (one) Tj ET ' + ' ' * 100).encode()
c2 = ('BT /F 12 Tf 72 700 Td (two) Tj ET ' + ' ' * 100).encode()
s1 = p.stream('', c1)
s2 = p.stream('', c2)
pages = p.reserve()
pg = [p.add('<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] /Contents %d 0 R /Resources << /Font << /F %d 0 R >> >> >>' % (pages, c, f1))
      for c in (s1, s2)]
p.put(pages, '<< /Type /Pages /Kids [%s] /Count 2 >>' % ' '.join('%d 0 R' % n for n in pg))
root = p.add('<< /Type /Catalog /Pages %d 0 R >>' % pages)
two = p.build(root)
n1 = len(c1)
case('work_doc_fits', 'limit:1000:1000:0', two, txt('one', 'two'))
case('work_doc_cut', 'limit:1000:%d:1' % (n1 + n1 // 2), two, txt('one', ''))
case('work_page_cut_each', 'limit:%d:1000:2' % (n1 - 1), two, txt('', ''))
case('work_page_exact', 'limit:%d:%d:0' % (n1, 2 * n1), two, txt('one', 'two'))


def write_corpus():
    lines = []
    for name, kind, pdf, expect in CASES:
        lines.append('%s\t%s\t%s\t%s' % (name, kind, base64.b64encode(pdf).decode(), base64.b64encode(expect).decode()))
    return '\n'.join(lines) + '\n'


def verify():
    import tempfile
    bad = 0
    d = tempfile.mkdtemp()
    for name, kind, pdf, expect in CASES:
        fn = os.path.join(d, name + '.pdf')
        open(fn, 'wb').write(pdf)
        q = subprocess.run(['qpdf', '--check', fn], capture_output=True, text=True)
        if q.returncode not in (0, 3):
            print('qpdf --check', name, q.stdout[-300:], q.stderr[-300:])
            bad += 1
    print('verified', len(CASES), 'files, differ', bad)
    return bad


if __name__ == '__main__':
    if '--verify' in sys.argv:
        sys.exit(1 if verify() else 0)
    text = write_corpus()
    if '--check' in sys.argv:
        if not os.path.exists(OUT) or open(OUT).read() != text:
            sys.exit('scripts/gen_pdfwork.py: testdata/pdfwork.txt is not what the generator writes')
        print('pdfwork.txt is the generator\'s,', len(CASES), 'cases')
    else:
        open(OUT, 'w').write(text)
        print('wrote', OUT, len(CASES), 'cases')
