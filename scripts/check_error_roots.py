#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Every error class of the library descends from Exception (P660).

  scripts/check_error_roots.py

Reads the interfaces of src/lib and src/rtl: a class whose name is E and
a capital letter, declared there, must name Exception or another such
class as its parent, never TObject or nothing. Prints the classes found
and fails on the first that does not descend from Exception."""
import re
import sys
from pathlib import Path

tree = Path(__file__).resolve().parents[1]
decl = re.compile(r'^\s*(E[A-Z][A-Za-z0-9_]*)\s*=\s*class\s*(?:\(\s*([A-Za-z0-9_.]+)\s*\))?', re.M)
parents = {}
where = {}
for path in sorted(list((tree / 'src/lib').glob('*.paslang')) + list((tree / 'src/rtl').glob('*.paslang'))):
    text = path.read_text(encoding='utf-8')
    cut = text.find('\nimplementation')
    for m in decl.finditer(text if cut < 0 else text[:cut]):
        parents[m.group(1).lower()] = (m.group(2) or 'TObject').split('.')[-1].lower()
        where[m.group(1).lower()] = '%s %s' % (path.name, m.group(1))
bad = []
for name in parents:
    seen, p = set(), name
    while p in parents and p not in seen:
        seen.add(p)
        p = parents[p]
    if p != 'exception':
        bad.append('%s descends from %s, not from Exception' % (where[name], p))
if bad:
    print('\n'.join(bad))
    sys.exit(1)
print('ok error roots: %d error classes of the library, every one an Exception' % len(parents))
