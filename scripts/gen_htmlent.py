#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""The table of named character references of pashtml (P565), from the
HTML Standard's list as Python ships it (html.entities.html5, the
standard's entities.json: 2231 names, 106 of them also without the
semicolon, 93 of two code points), written as three constant arrays
sorted by name for a binary search, between the markers
`{ ---- entities: written by scripts/gen_htmlent.py ---- }` and
`{ ---- end of the entities ---- }` of src/lib/pashtml.paslang.

usage: gen_htmlent.py src/lib/pashtml.paslang           write the table into the unit
       gen_htmlent.py --check src/lib/pashtml.paslang   exit 1 when the table in the unit is not this one
       gen_htmlent.py --go /usr/lib/go/src/html/entity.go
            report how Go's table differs from the standard's (Go leaves out nLt; and nGt;, which
            take six bytes of UTF-8 in five of source and do not fit its in-place decoder)
"""

import html.entities
import re
import sys

BEGIN = '{ ---- entities: written by scripts/gen_htmlent.py ---- }\n'
END = '{ ---- end of the entities ---- }\n'


def table():
    rows = []
    for name, text in html.entities.html5.items():
        cps = [ord(c) for c in text]
        assert 1 <= len(cps) <= 2, name
        rows.append((name, cps[0], cps[1] if len(cps) == 2 else 0))
    rows.sort(key=lambda r: r[0].encode())
    return rows


def wrap(items, head):
    """head and the items, comma-separated, in lines of at most 116 columns"""
    out = []
    line = head
    for i, item in enumerate(items):
        piece = item + (',' if i < len(items) - 1 else '')
        if len(line) + 1 + len(piece) > 116 and line.strip():
            out.append(line.rstrip() + '\n')
            line = '    ' + piece
        else:
            line += (' ' if line.strip() and not line.endswith('(') else '') + piece
    out.append(line + ');\n')
    return ''.join(out)


def pascal(rows):
    n = len(rows)
    out = [BEGIN, 'const\n', '  HtmlEntCount = %d;\n' % n]
    out.append('  { the names in byte order, each with its semicolon; the 106 legacy names come without it too }\n')
    out.append(wrap(["'%s'" % r[0] for r in rows], '  HtmlEntName: array[0..%d] of string = (' % (n - 1)))
    out.append('  { the code point of each name }\n')
    out.append(wrap(['$%X' % r[1] for r in rows], '  HtmlEntCode: array[0..%d] of Integer = (' % (n - 1)))
    out.append('  { the second code point of the 93 names that have two, 0 for the rest }\n')
    out.append(wrap(['$%X' % r[2] if r[2] else '0' for r in rows], '  HtmlEntCode2: array[0..%d] of Integer = (' % (n - 1)))
    out.append(END)
    return ''.join(out)


def splice(src, text):
    a = src.index(BEGIN)
    b = src.index(END) + len(END)
    return src[:a] + text + src[b:]


def main():
    args = sys.argv[1:]
    rows = table()
    if args and args[0] == '--go':
        go = open(args[1], errors='replace').read()
        one = dict(re.findall(r'^\t\t"([A-Za-z0-9]+;?)":\s+\'\\U([0-9A-F]{8})\',$', go, re.M))
        two = re.findall(r'^\t\t"([A-Za-z0-9]+;)":\s+\{\'\\u([0-9A-Fa-f]{4})\', \'\\u([0-9A-Fa-f]{4})\'\},$', go, re.M)
        gomap = {k: (int(v, 16), 0) for k, v in one.items()}
        gomap.update({k: (int(a, 16), int(b, 16)) for k, a, b in two})
        ours = {name: (a, b) for name, a, b in rows}
        missing = sorted(set(ours) - set(gomap))
        extra = sorted(set(gomap) - set(ours))
        differ = sorted(k for k in ours if k in gomap and gomap[k] != ours[k])
        print('standard %d names, Go %d; Go lacks %s; Go adds %s; values differ in %s' % (len(ours), len(gomap), ' '.join(missing) or 'none', ' '.join(extra) or 'none', ' '.join(differ) or 'none'))
        return
    check = args and args[0] == '--check'
    path = args[1] if check else args[0]
    src = open(path, errors='replace').read()
    text = pascal(rows)
    if check:
        if splice(src, text) != src:
            print('gen_htmlent: the table in %s is not the standard\'s: run scripts/gen_htmlent.py %s' % (path, path))
            sys.exit(1)
        print('gen_htmlent: %s holds the %d names of the standard' % (path, len(rows)))
        return
    open(path, 'w').write(splice(src, text))
    print('gen_htmlent: %d names written into %s' % (len(rows), path))


if __name__ == '__main__':
    main()
