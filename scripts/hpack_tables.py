#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""HPACK's tables for pashttp2 and its examples for the tests, from RFC 7541.

  scripts/hpack_tables.py --check   the tables in src/lib/pashttp2.paslang are
                                    those of testdata/hpack/tables.txt, and,
                                    where the RFC's text is at hand, that file
                                    and testdata/hpack/rfc7541.txt are the RFC's
  scripts/hpack_tables.py --write   write all three again from the RFC's text

The RFC's text is docs/ref/http/rfc7541.txt (rfc-editor.org), which a
tree that was only cloned does not have: what the unit and the tests need
of it is kept in testdata/hpack, and make check compares the unit with
that. From the RFC are read:

- Appendix A, the static table of 61 header fields;
- Appendix B, the Huffman code of 256 octets and EOS; each code's bits are
  compared with its hexadecimal form and its length as they are read, and
  the code is checked to be a prefix code that fills every leaf;
- Appendix C.2 to C.6, the examples: each one's octets, the header list
  they decode to and the dynamic table after it.

From the code a decoding table is made: one state for each inner node of
the code's tree (256 of them) and, for each state and each four bits of
input, the state that follows, the octet that is complete if one is, whether
a string may end there (what is left over is at most seven bits, all ones:
RFC 7541 5.2) and whether the bits can be no string at all (EOS inside it).
A code is at least five bits, so four bits never complete two octets.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RFC = REPO / 'docs/ref/http/rfc7541.txt'
UNIT = REPO / 'src/lib/pashttp2.paslang'
VECTORS = REPO / 'testdata/hpack/rfc7541.txt'
TABLES = REPO / 'testdata/hpack/tables.txt'
BEGIN = '{ hpack tables: written by scripts/hpack_tables.py from RFC 7541, appendices A and B }\n'
END = '{ end of the hpack tables }\n'


def rfc_lines():
    out = []
    for line in RFC.read_text().split('\n'):
        if line.startswith('Peon & Ruellan') or line.startswith('RFC 7541  ') or line == '\f':
            continue
        out.append(line.replace('\f', ''))
    return out


def static_table(lines):
    rows = []
    first = max(i for i, l in enumerate(lines) if l.startswith('Appendix A.  Static Table Definition'))
    last = max(i for i, l in enumerate(lines) if l.startswith('Appendix B.  Huffman Code'))
    for line in lines[first:last]:
        m = re.match(r'\s+\| (\d+)\s+\| (\S+)\s+\| (.*?)\s*\|$', line)
        if m:
            rows.append((int(m.group(1)), m.group(2), m.group(3)))
    assert [r[0] for r in rows] == list(range(1, 62)), len(rows)
    return [(n, v) for _, n, v in rows]


def checked_codes(codes):
    assert sorted(codes) == list(range(257)), len(codes)
    assert min(l for _, l in codes.values()) >= 5 and max(l for _, l in codes.values()) == 30
    assert all(0 <= c < 1 << l for c, l in codes.values())
    # a complete prefix code: Kraft's sum is exactly one
    assert sum(1 << (30 - l) for _, l in codes.values()) == 1 << 30
    return codes


def huffman(lines):
    codes = {}
    for line in lines:
        m = re.match(r"\s*(?:'.'|EOS)?\s*\(\s*(\d+)\)\s+((?:\|[01]+)+)\s+([0-9a-f]+)\s+\[\s*(\d+)\]$", line)
        if not m:
            continue
        sym, bits, hx, ln = int(m.group(1)), m.group(2).replace('|', ''), int(m.group(3), 16), int(m.group(4))
        assert len(bits) == ln and int(bits, 2) == hx, (sym, bits, hx, ln)
        assert sym not in codes
        codes[sym] = (hx, ln)
    return checked_codes(codes)


def tables_text(st, codes):
    t = ['# RFC 7541, appendices A and B, written by scripts/hpack_tables.py from the RFC\'s text.',
         '# static N NAME VALUE: the static table, - for no value and | for a space inside one.',
         '# code OCTET HEX BITS: the Huffman code of an octet, its bits in hexadecimal and how many; 256 is EOS.']
    for i, (n, v) in enumerate(st):
        t.append('static %d %s %s' % (i + 1, n, v.replace(' ', '|') or '-'))
    for sym in range(257):
        t.append('code %d %x %d' % (sym, codes[sym][0], codes[sym][1]))
    return '\n'.join(t) + '\n'


def read_tables():
    st, codes = [], {}
    for line in TABLES.read_text().split('\n'):
        f = line.split(' ')
        if f[0] == 'static':
            assert int(f[1]) == len(st) + 1 and len(f) == 4, line
            st.append((f[2], '' if f[3] == '-' else f[3].replace('|', ' ')))
        elif f[0] == 'code':
            assert len(f) == 4 and int(f[1]) not in codes, line
            codes[int(f[1])] = (int(f[2], 16), int(f[3]))
        else:
            assert line == '' or line.startswith('#'), line
    assert len(st) == 61, len(st)
    return st, checked_codes(codes)


def decode_table(codes):
    # the tree: node -> [child0, child1]; a leaf is ('sym', n)
    tree = [[None, None]]
    for sym, (code, ln) in sorted(codes.items()):
        node = 0
        for i in range(ln - 1, -1, -1):
            bit = (code >> i) & 1
            if i == 0:
                assert tree[node][bit] is None
                tree[node][bit] = ('sym', sym)
            else:
                nxt = tree[node][bit]
                if nxt is None:
                    tree.append([None, None])
                    nxt = len(tree) - 1
                    tree[node][bit] = nxt
                assert isinstance(nxt, int)
                node = nxt
    assert len(tree) == 256 and all(a is not None and b is not None for a, b in tree)
    # a string may end in a node reached by ones alone, at most seven of them
    ones = {0: 0}
    node = 0
    for depth in range(1, 8):
        node = tree[node][1]
        if not isinstance(node, int):
            break
        ones[node] = depth
    table = []
    for state in range(256):
        for nibble in range(16):
            node, emitted, fail = state, None, False
            for i in (3, 2, 1, 0):
                nxt = tree[node][(nibble >> i) & 1]
                if isinstance(nxt, int):
                    node = nxt
                else:
                    assert emitted is None
                    if nxt[1] == 256:
                        fail = True
                    emitted = nxt[1]
                    node = 0
            entry = node
            if fail:
                entry |= 1 << 18
            else:
                if emitted is not None:
                    entry |= (emitted << 8) | (1 << 16)
                # a node says the bits that led to it: the string may end where
                # they are ones alone, at most seven (after an octet they are the
                # last bits of these four)
                if node in ones:
                    entry |= 1 << 17
            table.append(entry)
    return table


def pas_string(s):
    return "'" + s.replace("'", "''") + "'"


def rows(items, per, indent='    '):
    out = []
    for i in range(0, len(items), per):
        out.append(indent + ', '.join(items[i:i + per]))
    return ',\n'.join(out)


def unit_text(st, codes):
    table = decode_table(codes)
    t = [BEGIN, 'const\n',
         '  { the static table (appendix A): names and values, from 1 }\n',
         '  HpackStaticLen = 61;\n',
         '  HpackStaticName: array[1..61] of string = (\n' + rows([pas_string(n) for n, _ in st], 4) + ');\n',
         '  HpackStaticValue: array[1..61] of string = (\n' + rows([pas_string(v) for _, v in st], 4) + ');\n',
         '  { the Huffman code (appendix B): each octet\'s code, its last bit the\n'
         '    lowest, and its length in bits; EOS is thirty ones }\n',
         '  HuffCode: array[0..255] of Integer = (\n' + rows(['$%x' % codes[i][0] for i in range(256)], 8) + ');\n',
         '  HuffBits: array[0..255] of Integer = (\n' + rows(['%d' % codes[i][1] for i in range(256)], 16) + ');\n',
         '  { the decoder: for a state (an inner node of the code\'s tree, 0 the\n'
         '    root) and four bits of input, at state * 16 + bits: the state that\n'
         '    follows in bits 0 to 7, the octet that is complete in bits 8 to 15\n'
         '    when bit 16 is set, bit 17 when a string may end there, bit 18 when\n'
         '    the bits are no string (EOS) }\n',
         '  HuffStep: array[0..4095] of Integer = (\n' + rows(['$%x' % e for e in table], 8) + ');\n',
         END]
    return ''.join(t)


def examples():
    """C.2 to C.6: (section, title, table size, hex, header list, dynamic table, table size after)."""
    lines = rfc_lines()
    start = next(i for i, l in enumerate(lines) if l.startswith('C.2.  Header Field Representation Examples'))
    end = next(i for i, l in enumerate(lines) if l.startswith('Acknowledgments'))
    out, cur, mode = [], None, None
    size = 4096
    for line in lines[start:end]:
        m = re.match(r'(C\.\d\.\d)\.  (.*)$', line)
        if m:
            cur = {'sec': m.group(1), 'title': m.group(2), 'hex': '', 'list': [], 'table': [], 'size': None}
            out.append(cur)
            mode = None
            continue
        if re.match(r'C\.\d\.  ', line):
            # a group's heading: the example before it has ended
            size = 256 if line[2] in '56' else 4096
            cur, mode = None, None
            continue
        if cur is None:
            continue
        cur.setdefault('max', size)
        s = line.strip()
        if s.startswith('Hex dump of encoded data'):
            mode = 'hex'
        elif s.startswith('Decoded header list'):
            mode = 'list'
        elif s.startswith('Dynamic Table (after decoding)') or s.startswith('Dynamic table (after decoding)'):
            mode = 'table'
        elif s.startswith('Decoding process') or s.startswith('Header list to encode') or \
                s.startswith('Encoding process') or s.startswith('Dynamic Table (after encoding)'):
            mode = None
        elif mode == 'hex':
            m = re.match(r'((?:[0-9a-f]{2,4} ?)+)\s*\|', s)
            if m:
                cur['hex'] += m.group(1).replace(' ', '')
            elif s:
                mode = None
        elif mode == 'list' and not s and cur['list']:
            mode = None
        elif mode == 'list' and s:
            m = re.match(r'(:?[a-z0-9-]+): (.*)$', s)
            if m:
                cur['list'].append((m.group(1), m.group(2)))
            else:
                # a value that went on to the next line of the RFC's page
                name, value = cur['list'][-1]
                cur['list'][-1] = (name, value + ' ' + s)
        elif mode == 'table' and s:
            m = re.match(r'\[\s*(\d+)\] \(s =\s*(\d+)\) (:?[a-z0-9-]+): (.*)$', s)
            if m:
                cur['table'].append((m.group(3), m.group(4)))
            elif s.startswith('Table size:'):
                cur['size'] = int(s.split(':')[1])
                mode = None
            elif s == 'empty.':
                pass
            elif cur['table']:
                name, value = cur['table'][-1]
                cur['table'][-1] = (name, value + ' ' + s)
    out = [e for e in out if e['hex']]
    assert [e['sec'] for e in out] == ['C.2.1', 'C.2.2', 'C.2.3', 'C.2.4', 'C.3.1', 'C.3.2', 'C.3.3', 'C.4.1', 'C.4.2',
                                       'C.4.3', 'C.5.1', 'C.5.2', 'C.5.3', 'C.6.1', 'C.6.2', 'C.6.3'], [e['sec'] for e in out]
    return out


def vectors_text():
    t = ['# RFC 7541, appendix C.2 to C.6, written by scripts/hpack_tables.py from the RFC\'s text.',
         '# example SECTION MAXSIZE new|same: a block; new begins with an empty dynamic table of MAXSIZE octets,',
         '# same goes on with the one the example before left. Then block HEX, field NAME VALUE for each field',
         '# of the decoded list in order, entry NAME VALUE for the dynamic table after it from the newest,',
         '# and size N, its size. | stands for a space inside a value.']
    prev = None
    for e in examples():
        group = e['sec'][:3]
        fresh = group == 'C.2' or group != prev
        prev = group
        t.append('example %s %d %s' % (e['sec'], e['max'], 'new' if fresh else 'same'))
        t.append('block ' + e['hex'])
        for n, v in e['list']:
            t.append('field %s %s' % (n, v.replace(' ', '|') or '-'))
        for n, v in e['table']:
            t.append('entry %s %s' % (n, v.replace(' ', '|') or '-'))
        t.append('size %d' % (e['size'] or 0))
    return '\n'.join(t) + '\n'


def main():
    have_rfc = RFC.exists()
    if sys.argv[1:] == ['--write']:
        lines = rfc_lines()
        st, codes = static_table(lines), huffman(lines)
        vec = vectors_text()
        s = UNIT.read_text()
        a, b = s.index(BEGIN), s.index(END) + len(END)
        UNIT.write_text(s[:a] + unit_text(st, codes) + s[b:])
        VECTORS.parent.mkdir(parents=True, exist_ok=True)
        VECTORS.write_text(vec)
        TABLES.write_text(tables_text(st, codes))
        print('wrote the hpack tables and %d examples' % sum(1 for l in vec.split('\n') if l.startswith('example ')))
    elif sys.argv[1:] == ['--check']:
        st, codes = read_tables()
        s = UNIT.read_text()
        a, b = s.index(BEGIN), s.index(END) + len(END)
        if s[a:b] != unit_text(st, codes):
            raise SystemExit('the hpack tables of src/lib/pashttp2.paslang are not those of testdata/hpack/tables.txt: '
                             'scripts/hpack_tables.py --write')
        examples_kept = sum(1 for l in VECTORS.read_text().split('\n') if l.startswith('example '))
        if not have_rfc:
            print('hpack tables: 61 static fields, 257 codes and 4096 steps are those of testdata/hpack/tables.txt '
                  '(RFC 7541 is not at docs/ref/http to compare it with)')
            return
        lines = rfc_lines()
        if TABLES.read_text() != tables_text(static_table(lines), huffman(lines)):
            raise SystemExit('testdata/hpack/tables.txt is not RFC 7541\'s appendices A and B')
        if VECTORS.read_text() != vectors_text():
            raise SystemExit('testdata/hpack/rfc7541.txt is not RFC 7541\'s appendix C')
        print('hpack tables: 61 static fields, 257 codes, 4096 steps and %d examples are RFC 7541\'s' % examples_kept)
    elif sys.argv[1:] == ['--show']:
        sys.stdout.write(vectors_text())
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
