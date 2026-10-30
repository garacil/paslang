#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""pasxml against the W3C XML Conformance Test Suite (P426).

  scripts/xmlconf.py [--ext|--dtd] SUITE_DIR [UNITS]   SUITE_DIR is the xmlconf
                                   directory of xmlts20130923.tar.gz
                                   (w3.org/XML/Test); UNITS where pasxml is
                                   compiled, if it is not installed; --ext
                                   gives the reader a resolver that reads an
                                   external entity from a file beside the
                                   document (P477); --dtd also asks it for
                                   the external subset and the external
                                   parameter entities (P511)

Every case of the suite's catalogs that applies to a processor that reads
the DOCTYPE's internal subset and no external entity, in the Fifth Edition
(not XML 1.1, not an edition before the fifth): a not-well-formed document
(ENTITIES none) must be refused, a valid or invalid one must be read. With
--ext the processor reads external general entities too, and a
not-well-formed document with ENTITIES general must be refused as well; with
--dtd it reads the external subset and the parameter entities, and one with
ENTITIES parameter or both must be refused too. The
namespace cases are read with namespaces, the rest without. Prints the
counts and the cases that go the other way; the expected ones are in
ENGINEERING (P426). The suite is not part of the repository: it is not
ours to redistribute."""
import os
import re
import subprocess
import sys
import tempfile

args = sys.argv[1:]
ext = '--ext' in args
if ext:
    args.remove('--ext')
dtd = '--dtd' in args
if dtd:
    args.remove('--dtd')
    ext = True
root = os.path.abspath(args[0]) if len(args) > 0 else None
if not root or not os.path.isdir(root):
    sys.exit(__doc__)
here = os.path.dirname(os.path.abspath(__file__))
work = tempfile.mkdtemp(prefix='xmlconf')
exe = os.path.join(work, 'xmldump')
build = subprocess.run(['paslangc'] + (['-Fu', args[1]] if len(args) > 1 else []) + ['-o', exe, os.path.join(here, 'xmldump.paslang')],
                       capture_output=True, text=True)
if build.returncode != 0:
    sys.exit(build.stderr)
cats = subprocess.run(['grep', '-rl', '<TESTCASES', root, '--include=*.xml'], capture_output=True, text=True).stdout.split()
cases = []
for c in sorted(cats):
    if c.endswith('/xmlconf.xml'):
        continue
    base = os.path.dirname(c)
    txt = open(c, encoding='utf-8', errors='replace').read()
    mb = re.search(r'<TESTCASES[^>]*xml:base="([^"]*)"', txt)
    if mb:
        base = os.path.join(base, mb.group(1))
    for m in re.finditer(r'<TEST\s([^>]*)>', txt):
        a = dict(re.findall(r'([\w:]+)="([^"]*)"', m.group(1)))
        if 'URI' not in a:
            continue
        a['path'] = os.path.normpath(os.path.join(base, a['URI']))
        a['cat'] = os.path.relpath(c, root)
        cases.append(a)
checked = 0
missed, refused = [], []
for a in cases:
    if a.get('VERSION') == '1.1' or not os.path.exists(a['path']):
        continue
    ed = a.get('EDITION')
    if ed is not None and '5' not in ed.split():
        continue
    rec = a.get('RECOMMENDATION', '')
    if 'XML1.1' in rec or 'NS1.1' in rec:
        continue
    flat = 'namespaces' not in a['cat']
    r = subprocess.run([exe, a['path']] + (['flat'] if flat else []) + (['dtd'] if dtd else ['ext'] if ext else []), capture_output=True, timeout=60)
    out = r.stdout.decode('utf-8', 'replace').rstrip('\n')
    refuse = out.endswith('ERR') or not out.endswith('OK')
    checked += 1
    if a['TYPE'] == 'not-wf':
        if a.get('ENTITIES', 'none') in (('none', 'general', 'parameter', 'both') if dtd else ('none', 'general') if ext else ('none',)) and not refuse:
            missed.append(a)
    elif a['TYPE'] in ('valid', 'invalid') and refuse:
        why = [l for l in out.split('\n') if l.startswith('# ')]
        a['why'] = why[0][2:] if why else ''
        refused.append(a)
print('cases checked: %d' % checked)
print('not well-formed and read: %d' % len(missed))
for a in missed:
    print('  %s %s %s' % (a['cat'], a['URI'], a.get('SECTIONS', '')))
print('valid or invalid and refused: %d' % len(refused))
for a in refused:
    print('  %s %s [%s] %s' % (a['cat'], a['URI'], a.get('ENTITIES', ''), a['why']))
