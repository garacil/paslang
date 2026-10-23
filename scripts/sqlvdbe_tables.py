#!/usr/bin/env python3
"""P405: the tables of the unit sqlite's virtual machine, read from SQLite
3.54.1's amalgamation in docs/ref/sqlite (the opcodes.h and opcodes.c
that tool/mkopcodeh.tcl and tool/mkopcodec.tcl make from vdbe.c and
parse.h): each opcode's number, its name and synopsis as EXPLAIN shows
them, and its properties (OPFLG_INITIALIZER).

usage: sqlvdbe_tables.py > tables.paslang
"""
import os
import re
import sys

ROOT = os.environ.get('PASLANG_ROOT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AMALG = os.path.join(ROOT, 'docs/ref/sqlite/amalg/sqlite-amalgamation-3540100/sqlite3.c')


def tables(text):
    ops = {}
    for m in re.finditer(r'^#define OP_(\w+)\s+(\d+)', text, re.M):
        ops[m.group(1)] = int(m.group(2))
    flags_src = text[text.index('#define OPFLG_INITIALIZER {'):]
    flags_src = flags_src[:flags_src.index('}')]
    flags = [int(x, 16) for x in re.findall(r'0x([0-9a-f]{2})', flags_src)]
    mx = int(re.search(r'#define SQLITE_MX_JUMP_OPCODE\s+(\d+)', text).group(1))
    names_src = text[text.index('const char *sqlite3OpcodeName(int i){'):]
    names_src = names_src[:names_src.index('};')]
    names = {}
    for m in re.finditer(r'/\*\s*(\d+)\s*\*/\s*"(\w+)"\s*OpHelp\("((?:[^"\\]|\\.)*)"\)', names_src):
        names[int(m.group(1))] = (m.group(2), m.group(3))
    return ops, flags, mx, names


def q(s):
    return "'" + s.replace("'", "''") + "'"


def main():
    ops, flags, mx, names = tables(open(AMALG, encoding='utf-8').read())
    n = max(names) + 1
    assert sorted(names) == list(range(n)), 'opcode names not dense'
    for name, (num) in ops.items():
        if num < n and names[num][0] != name:
            raise SystemExit('opcode %s is %d, named %s' % (name, num, names[num][0]))
    out = ['{ ---- the virtual machine\'s opcodes (opcodes.h, opcodes.c of SQLite',
           '  3.54.1, made by scripts/sqlvdbe_tables.py) ---- }', '', 'const']
    for name, num in sorted(ops.items(), key=lambda x: (x[1], x[0])):
        out.append('  OP_%s = %d;' % (name, num))
    out.append('  SQLITE_MX_JUMP_OPCODE = %d;' % mx)
    out.append('  SqlOpCount = %d;' % n)
    for tag, bit in (('JUMP', 1), ('IN1', 2), ('IN2', 4), ('IN3', 8), ('OUT2', 16), ('OUT3', 32),
                     ('NCYCLE', 64), ('JUMP0', 128)):
        out.append('  OPFLG_%s = %d;' % (tag, bit))
    out.append('  SqlOpName: array[0..%d] of string = (' % (n - 1))
    out.append(',\n'.join('    ' + q(names[i][0]) for i in range(n)) + ');')
    out.append('  SqlOpHelp: array[0..%d] of string = (' % (n - 1))
    out.append(',\n'.join('    ' + q(names[i][1]) for i in range(n)) + ');')
    out.append('  SqlOpFlags: array[0..%d] of Integer = (' % (n - 1))
    rows = [', '.join(str(f) for f in flags[i:i + 16]) for i in range(0, n, 16)]
    out.append('    ' + ',\n    '.join(rows) + ');')
    assert len(flags) >= n
    sys.stdout.write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
