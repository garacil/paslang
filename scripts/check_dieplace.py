#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""Every error of the parser and the emitter goes through a routine that
gives its place (P383): no routine of pasparse calls Die but Fail and
Refuse, which add the token's place, and none of pasemit but Refuse,
which adds the line being emitted.

usage: check_dieplace.py src/compiler/pasparse.paslang src/compiler/pasemit.paslang
"""

import re
import sys

KEEP = {'pasparse': ('TParser.Fail', 'TParser.Refuse'), 'pasemit': ('TEmitter.Refuse',)}


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__.strip().splitlines()[-1])
    total = 0
    for path in sys.argv[1:]:
        unit = path.rsplit('/', 1)[-1].split('.')[0]
        keep = KEEP[unit]
        cur = ''
        impl = False
        for n, l in enumerate(open(path).read().split('\n'), 1):
            if l.startswith('implementation'):
                impl = True
            m = re.match(r'^(procedure|function) ([\w.]+)', l)
            if m:
                cur = m.group(2)
            if impl and re.search(r'(?<![\w.])Die\(', l):
                if cur not in keep:
                    raise SystemExit(f'{path}:{n}: {cur} calls Die, whose message may name no place: {l.strip()}')
                total += 1
    print(f'check_dieplace: the parser and the emitter refuse through Fail and Refuse alone ({total} calls of Die left in them)')


if __name__ == '__main__':
    main()
