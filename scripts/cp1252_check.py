#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""The oracle of testdata/codec1252 (P562): every `byte` line of its
output is decoded again with Python's cp1252 codec (the five bytes it
leaves undefined, 81 8D 8F 90 9D, are the C1 controls of the same
number, as the WHATWG index has them), every `back` line is encoded
again with the same codec (refused where Python refuses, after the same
bytes), and every `utf8` line is decoded with Python's strict UTF-8
decoder, whose first bad byte must be the one Utf8BadAt names. A line
that differs fails the check.

usage: cp1252_check.py OUTPUT
"""

import re
import sys

UNDEFINED = {0x81, 0x8D, 0x8F, 0x90, 0x9D}


def cp1252(b):
    if b in UNDEFINED:
        return chr(b)
    return bytes([b]).decode('cp1252')


def main():
    bad = n = 0
    for line in open(sys.argv[1], errors='replace'):
        line = line.rstrip('\n')
        m = re.match(r'^byte ([0-9A-F]{2}) -> ([0-9A-F]*)$', line)
        if m:
            n += 1
            want = cp1252(int(m.group(1), 16)).encode('utf-8').hex().upper()
            if want != m.group(2):
                bad += 1
                print('cp1252_check: %s: python says %s' % (line, want))
            continue
        m = re.match(r'^back \S+ ([0-9A-F]*) -> (refused after )?([0-9A-F]*)$', line)
        if m:
            n += 1
            try:
                text = bytes.fromhex(m.group(1)).decode('utf-8')
            except UnicodeDecodeError as e:
                text = None
                good = bytes.fromhex(m.group(1))[:e.start].decode('utf-8')
            if text is None:
                want, refused = good, True
            else:
                want, refused = text, False
            out = bytearray()
            for ch in want:
                if ord(ch) in UNDEFINED:
                    out.append(ord(ch))
                    continue
                try:
                    out += ch.encode('cp1252')
                except UnicodeEncodeError:
                    refused = True
                    break
            want_hex = out.hex().upper()
            if (refused != bool(m.group(2))) or want_hex != m.group(3):
                bad += 1
                print('cp1252_check: %s: python says %s%s' % (line, 'refused after ' if refused else '', want_hex))
            continue
        m = re.match(r'^utf8 ([0-9A-F]*) -> (ok|bad (\d+))$', line)
        if m:
            n += 1
            data = bytes.fromhex(m.group(1))
            try:
                data.decode('utf-8')
                want = 'ok'
            except UnicodeDecodeError as e:
                want = 'bad %d' % (e.start + 1)
            if want != m.group(2):
                bad += 1
                print('cp1252_check: %s: python says %s' % (line, want))
    if n < 280:
        print('cp1252_check: only %d lines checked' % n)
        sys.exit(1)
    if bad:
        sys.exit(1)
    print('cp1252_check: %d lines agree with codecs' % n)


if __name__ == '__main__':
    main()
