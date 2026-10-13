#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""What testdata/rtlong.paslang must print (P271): its counts of
mismatches are 0, and its hashes of the texts about the edges of the
runtime's pieces are those of xxhsum (0.8: -H3 is XXH3_64 with seed 0,
-H64 XXH64, -H32 XXH32), run here on the same bytes, byte k of the text
being (131 (k + 1) + 7) mod 256. It needs xxhsum: make check runs it
when xxhsum is there, and the expected output in testdata holds what it
gave. The lengths are read from the test itself."""
import os
import re
import subprocess
import sys
import tempfile

src = open(sys.argv[1] if len(sys.argv) > 1 else 'testdata/rtlong.paslang').read()
m = re.search(r'HLens: array\[0\.\.\d+\] of Integer = \((.*?)\);', src, re.S)
lens = [int(x) for x in m.group(1).split(',')]
text = bytes(((k + 1) * 131 + 7) & 255 for k in range(max(lens)))


def xxh(flag, data):
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(data)
        name = f.name
    try:
        out = subprocess.run(['xxhsum', flag, name], capture_output=True, text=True, check=True).stdout
    finally:
        os.unlink(name)
    word = out.split()[0]
    if word.startswith('XXH3_'):
        word = word[5:]
    return word.upper()


print('move and fill 0')
print('zero values 0')
print('comparisons 0')
for n in lens:
    t = text[:n]
    print(n, xxh('-H3', t), xxh('-H64', t), xxh('-H32', t))
print('bad 0')
