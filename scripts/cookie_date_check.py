#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""The oracle of the date lines of testdata/cookiejar (P564): RFC 6265 5.1.1
written out in Python (the tokens between the delimiters %x09 / %x20-2F /
%x3B-40 / %x5B-60 / %x7B-7E, the first token that is a time, a day of the
month, a month, a year, in any order; 70-99 are 19xx, 0-69 are 20xx;
the limits and the days a month has) against what CookieParseDate said.

usage: cookie_date_check.py OUTPUT
"""

import calendar
import re
import sys

MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']


def parse(s):
    time = day = month = year = None
    for t in re.split(r'[\x09\x20-\x2f\x3b-\x40\x5b-\x60\x7b-\x7e]+', s):
        if not t:
            continue
        if time is None:
            m = re.match(r'^(\d{1,2}):(\d{1,2}):(\d{1,2})(?!\d)', t)
            if m:
                time = tuple(int(x) for x in m.groups())
                continue
        if day is None:
            m = re.match(r'^(\d{1,2})(?!\d)', t)
            if m:
                day = int(m.group(1))
                continue
        if month is None and len(t) >= 3 and t[:3].lower() in MONTHS:
            month = MONTHS.index(t[:3].lower()) + 1
            continue
        if year is None:
            m = re.match(r'^(\d{2,4})(?!\d)', t)
            if m:
                year = int(m.group(1))
                continue
    if None in (time, day, month, year):
        return None
    if 70 <= year <= 99:
        year += 1900
    elif year <= 69:
        year += 2000
    hh, mm, ss = time
    if not 1 <= day <= 31 or year < 1601 or hh > 23 or mm > 59 or ss > 59:
        return None
    if day > calendar.monthrange(year, month)[1]:
        return None
    return calendar.timegm((year, month, day, hh, mm, ss))


def main():
    n = bad = 0
    for line in open(sys.argv[1], errors='replace'):
        m = re.match(r'^(?:! )?date (.*) -> (none|-?\d+)$', line.rstrip('\n'))
        if not m:
            continue
        n += 1
        want = parse(m.group(1))
        want = 'none' if want is None else str(want)
        if want != m.group(2):
            bad += 1
            print('cookie_date_check: %s: python says %s' % (line.rstrip(), want))
    if n < 30:
        print('cookie_date_check: only %d dates checked' % n)
        sys.exit(1)
    if bad:
        sys.exit(1)
    print('cookie_date_check: %d dates agree with RFC 6265 5.1.1 in Python' % n)


if __name__ == '__main__':
    main()
