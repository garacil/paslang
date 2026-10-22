#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""What a program does not reach leaves it (P417), and SQLite is the
library unit sqlite (P418). hello does not name sqlite and carries
nothing of it. sqlnone names it and reaches none of it: a unit's
read-only items are each a section of their own, so it carries no class
table of it (vmt_, rtti_), none of its methods and none of its routines,
only the unit's variables, its routines' typed constants among them, and
its start (v_sqlite., v_p_sqlite_, u_sqlite_: a unit's data is one
section, which its start keeps whole). sqluses,
which opens a database, carries TSqlite's (a library unit's names carry
the unit's: vmt_sqlite_tsqlite). It prints hello's loaded bytes
(all its sections but the debug ones), and refuses more than BUDGET when
one is given.

usage: check_gcsections.py HELLO SQLNONE SQLUSES [BUDGET] [--arm]
"""

import subprocess
import sys


def syms(path, arm):
    nm = 'aarch64-linux-gnu-nm' if arm else 'nm'
    out = subprocess.run([nm, path], capture_output=True, text=True, check=True).stdout
    return {line.split()[-1] for line in out.splitlines() if line.strip()}


def loaded(path, arm):
    size = 'aarch64-linux-gnu-size' if arm else 'size'
    out = subprocess.run([size, '-A', path], capture_output=True, text=True, check=True).stdout
    total = 0
    for line in out.splitlines():
        f = line.split()
        if len(f) == 3 and f[1].isdigit() and f[0].startswith(('.text', '.rodata', '.data', 'pas', '.eh_frame')):
            total += int(f[1])
    return total


def sqlite_syms(names):
    return sorted(s for s in names if 'sqlite' in s.lower() or 'tsql' in s.lower())


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    arm = '--arm' in sys.argv[1:]
    hello, none, uses = args[0], args[1], args[2]
    budget = int(args[3]) if len(args) > 3 else 0
    bad = sqlite_syms(syms(hello, arm))
    if bad:
        raise SystemExit('check_gcsections: hello carries %d of sqlite: %s' % (len(bad), ' '.join(bad[:8])))
    unit = sqlite_syms(syms(none, arm))
    bad = [s for s in unit if not s.startswith(('v_sqlite.', 'v_p_sqlite_', 'u_sqlite_'))]
    if bad:
        raise SystemExit('check_gcsections: sqlnone carries %d of sqlite: %s' % (len(bad), ' '.join(bad[:8])))
    if not unit:
        raise SystemExit('check_gcsections: sqlnone carries not even the start of sqlite')
    u = syms(uses, arm)
    for s in ('vmt_sqlite_tsqlite', 'p_sqlite_tsqlite_open', 'vmt_sqlite_esqliteerror'):
        if not any(x.startswith(s) for x in u):
            raise SystemExit('check_gcsections: sqluses carries no %s' % s)
    n = loaded(hello, arm)
    if budget and n > budget:
        raise SystemExit('check_gcsections: hello loads %d bytes, budget %d' % (n, budget))
    print('check_gcsections: hello carries nothing of sqlite, loads %d bytes; sqlnone only its start, %d names;'
          ' sqluses carries TSqlite' % (n, len(unit)))


if __name__ == '__main__':
    main()
