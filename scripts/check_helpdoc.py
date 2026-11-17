#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""check_helpdoc.py PASLANGC MANUAL (P646): every limit and default that
the compiler's help and the manual both state is the same in both.

The help states the parameters of a routine and the arms of a select
from the compiler's own constants (pasast's MaxParams and MaxSelectArms),
so the help is the compiler's word; FACTS below says where each fact
stands in the help and in the manual, and each must be found in both,
with one value. A statement of the help that the manual contradicts is
listed in CONTRADICTIONS: 7KSP found the help saying that a method takes
no default, which it has taken since 1.1.6. Exit 1 on the first fact that
differs, with both texts."""
import re
import subprocess
import sys

WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
         'nine': 9, 'ten': 10, 'sixteen': 16}

# name, the help's patterns, the manual's patterns: the first group of each
# is the value; every pattern of a list that matches must give that value,
# and at least one of each list must match
FACTS = [
    ('the parameters of a routine', [r'At most (\d+) parameters', r'up to (\d+) parameters'],
     [r'takes up to (\d+) parameters', r'takes at most (\d+) parameters']),
    ('the arms of a select', [r'A select has at most (\d+) arms'], [r'A select has at most (\d+) arms']),
    ('the oldest kernel', [r'kernel (\d+\.\d+) or newer'], [r'kernel (\d+\.\d+) or newer']),
    ('-inline by default', [r'-inline 0 keeps one copy of every routine\. (\d+) by default'],
     [r'`-inline 0` keeps one copy of every routine and every loop; (\d+) by default']),
    ('the collector\'s default', [r'PASLANG_GC=(\d+) \(the default\)'], [r'`PASLANG_GC=(\d+)` is the default']),
    ('the most threads that mark', [r'at most (\d+), PASLANG_GCWORKERS'], [r'At most (\d+) of them mark']),
    ('the decimals of a real WriteLn writes', [r'up to (\d+) fractional digits'],
     [r'real prints up to (\w+) decimals']),
]

# what the help must not say when the manual says the other
CONTRADICTIONS = [
    ('a method takes defaults', r'take defaults as a routine does',
     r'[Aa] method has no default|default value on a method'),
]


def value(v):
    v = v.strip()
    return WORDS.get(v.lower(), v)


def found(text, patterns):
    vals = []
    for p in patterns:
        for m in re.finditer(p, text):
            vals.append((value(m.group(1)), m.group(0)))
    return vals


def main():
    help_text = subprocess.run([sys.argv[1], '--help'], capture_output=True, text=True).stdout
    help_text = re.sub(r'\n\s+', ' ', help_text)
    manual = re.sub(r'\s+', ' ', open(sys.argv[2], encoding='utf-8').read())
    bad = []
    for name, hp, mp in FACTS:
        h = found(help_text, hp)
        m = found(manual, mp)
        if not h:
            bad.append('%s: the help does not state it' % name)
            continue
        if not m:
            bad.append('%s: the manual does not state it' % name)
            continue
        vals = set(str(v) for v, _ in h + m)
        if len(vals) > 1:
            bad.append('%s: %s' % (name, ' / '.join(t for _, t in h + m)))
    for name, manual_says, help_must_not in CONTRADICTIONS:
        if re.search(manual_says, manual) and re.search(help_must_not, help_text):
            bad.append('%s: the manual says it and the help says otherwise (%s)' %
                       (name, re.search(help_must_not, help_text).group(0)))
    for b in bad:
        print('check_helpdoc:', b)
    if bad:
        return 1
    print('check_helpdoc: %d facts and %d contradictions checked, the help and the manual agree' %
          (len(FACTS), len(CONTRADICTIONS)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
