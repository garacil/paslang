#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""The manual's pastls example is testdata/tlsdoc (P473).

usage: check_tlsdoc.py MANUAL.md tlsdoc.paslang

The fenced block of the manual that starts with `program tlsdoc;` must be
the program make check compiles and runs against Go's crypto/tls, word
for word, so the example the manual shows is one that works.
"""

import sys


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__.strip().splitlines()[-1])
    man = open(sys.argv[1]).read()
    prog = open(sys.argv[2]).read()
    start = man.find('```\nprogram tlsdoc;')
    if start < 0:
        raise SystemExit(sys.argv[1] + ': no block that starts with program tlsdoc;')
    start += 4
    end = man.find('\n```', start)
    block = man[start:end] + '\n'
    if block != prog:
        raise SystemExit(sys.argv[1] + ': the example differs from ' + sys.argv[2])
    print('check_tlsdoc: the manual\'s pastls example is testdata/tlsdoc')


if __name__ == '__main__':
    main()
