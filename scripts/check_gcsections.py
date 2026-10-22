#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""What a program does not reach leaves it (P417): a unit's read-only
items are each a section of their own, so hello, which names nothing of
passqlite, carries no class table of it (vmt_, rtti_), none of its
methods and none of its routines, while sqluses, which opens a database,
carries TSqlite's. It prints hello's loaded bytes (all its sections but
the debug ones), and refuses more than BUDGET when one is given.

usage: check_gcsections.py HELLO SQLUSES [BUDGET] [--arm]
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


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    arm = '--arm' in sys.argv[1:]
    hello, uses = args[0], args[1]
    budget = int(args[2]) if len(args) > 2 else 0
    h = syms(hello, arm)
    bad = sorted(s for s in h if ('sqlite' in s.lower() or 'tsql' in s.lower())
                 and not s.startswith(('v_passqlite.', 'u_passqlite_')))
    if bad:
        raise SystemExit('check_gcsections: hello carries %d of passqlite: %s' % (len(bad), ' '.join(bad[:8])))
    u = syms(uses, arm)
    for s in ('vmt_tsqlite', 'p_tsqlite_open', 'vmt_esqliteerror'):
        if not any(x.startswith(s) for x in u):
            raise SystemExit('check_gcsections: sqluses carries no %s' % s)
    n = loaded(hello, arm)
    if budget and n > budget:
        raise SystemExit('check_gcsections: hello loads %d bytes, budget %d' % (n, budget))
    print('check_gcsections: hello carries nothing of passqlite, loads %d bytes; sqluses carries TSqlite' % n)


if __name__ == '__main__':
    main()
