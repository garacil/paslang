#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""The oracle of testdata/xlsxdate (P563): every `serial` line of its output
is computed again with Python's datetime from the same decimal text, in
the date system the line names (ECMA-376 18.17.4.1: the 1900 system
counts 1 January 1900 as 1 and a 29 February 1900 that never was as 60,
the 1904 system counts 1 January 1904 as 0; the day's fraction is the
time, rounded to the second as Python rounds), and every `iso` line
with datetime.fromisoformat after the same cuts (a fraction of a second
dropped, a zone read and left alone, a space for the T). A line that
differs fails the check.

usage: xlsxdate_check.py OUTPUT
"""

import datetime
import re
import sys


def serial(text, d1904):
    try:
        x = float(text)
    except ValueError:
        return 'not a number'
    if not (x >= 0 and x < 3000000):
        return None
    days = int(x)
    tod = round((x - days) * 86400)
    if tod >= 86400:
        days += 1
        tod -= 86400
    if d1904:
        base = datetime.date(1904, 1, 1)
    else:
        if days == 60:
            return None
        if days < 60:
            days += 1
        base = datetime.date(1899, 12, 30)
    try:
        d = base + datetime.timedelta(days=days)
    except OverflowError:
        return None
    return '%04d-%02d-%02d %02d:%02d:%02d' % (d.year, d.month, d.day, tod // 3600, tod // 60 % 60, tod % 60)


def iso(text):
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:[.,]\d+)?)?(?:Z|[-+]\d{2}:?\d{2})?)?$', text)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    h, mi, s = int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0)
    try:
        datetime.datetime(y, mo, d, h, mi, s)
    except ValueError:
        return None
    return '%04d-%02d-%02d %02d:%02d:%02d' % (y, mo, d, h, mi, s)


def main():
    bad = 0
    n = 0
    for line in open(sys.argv[1], errors='replace'):
        line = line.rstrip('\n')
        m = re.match(r'^serial (1900|1904) (\S+) -> (.*)$', line)
        if m:
            n += 1
            want = serial(m.group(2), m.group(1) == '1904')
            got = m.group(3)
            ok = (want is None and got.startswith('none 000000')) or (want == got)
            if not ok:
                bad += 1
                print('xlsxdate_check: %s: python says %s' % (line, want))
            continue
        m = re.match(r'^iso (.*) -> (.*)$', line)
        if m:
            n += 1
            want = iso(m.group(1))
            got = m.group(2)
            ok = (want is None and got.startswith('none 000000')) or (want == got)
            if not ok:
                bad += 1
                print('xlsxdate_check: %s: python says %s' % (line, want))
    if n < 40:
        print('xlsxdate_check: only %d lines checked' % n)
        sys.exit(1)
    if bad:
        sys.exit(1)
    print('xlsxdate_check: %d lines agree with datetime' % n)


if __name__ == '__main__':
    main()
