#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
#
# paslang is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# paslang is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with paslang.  If not, see <https://www.gnu.org/licenses/>.

"""The table of powers of ten of pasnum (P200), Go's pow10Tab
(golang/src/internal/strconv/pow10tab.go), made the way Go's
pow10gen.go makes it: for each e from -348 to 347, 10^e scaled by a
power of two into [2^127, 2^128), its floor as hi * 2^64 + lo, one more
when 10^e was not an integer, and then hi * 2^64 - lo with lo taken
from 2^64 when it is not 0. Each word is written as paslangc writes a
64-bit constant past High(Int64), in hexadecimal, the high word first,
two words a line.

    scripts/pow10gen.py              print the table's lines
    scripts/pow10gen.py --check      compare Go's pow10tab.go and the
                                     table in src/lib/pasnum.paslang
                                     with this computation, word by word
"""
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_EXP, MAX_EXP = -348, 347


def words():
    """(hi, lo) of each e, unsigned, as pow10gen.go computes them."""
    out = []
    two128 = 1 << 128
    for e in range(MIN_EXP, MAX_EXP + 1):
        r = Fraction(10) ** e
        while r < two128:
            r *= 2
        while r >= two128:
            r /= 2
        d = r.numerator // r.denominator
        hi, lo = divmod(d, 1 << 64)
        if r.denominator != 1:
            lo += 1
            if lo == 1 << 64:
                lo = 0
                hi += 1
        if lo != 0:
            hi += 1
            lo = (1 << 64) - lo
        out.append((hi, lo))
    return out


def lines():
    ws = words()
    out = []
    for i, (hi, lo) in enumerate(ws):
        sep = "," if i < len(ws) - 1 else ");"
        out.append("    $%016X, $%016X%s" % (hi, lo, sep))
    return out


def go_words():
    src = subprocess.run(["git", "-C", str(ROOT / "golang"), "show",
                          "HEAD:src/internal/strconv/pow10tab.go"],
                         capture_output=True, text=True, check=True).stdout
    return [(int(a, 16), int(b, 16)) for a, b in
            re.findall(r"\{(0x[0-9a-f]+), (0x[0-9a-f]+)\}", src)]


def pasnum_words():
    src = (ROOT / "src" / "lib" / "pasnum.paslang").read_text()
    body = src[src.index("Pow10Tab: array[0..1391] of Int64 = ("):]
    body = body[body.index("(") + 1:body.index(");") + 1]
    nums = [int(x, 16) for x in re.findall(r"\$([0-9A-F]{16})", body)]
    return list(zip(nums[0::2], nums[1::2]))


def main():
    if sys.argv[1:] == ["--check"]:
        mine = words()
        go = go_words()
        pas = pasnum_words()
        bad = 0
        if len(mine) != 696 or len(go) != 696 or len(pas) != 696:
            sys.exit("pow10gen: %d computed, %d in Go's pow10tab.go, %d in pasnum" % (len(mine), len(go), len(pas)))
        for i in range(696):
            if mine[i] != go[i] or mine[i] != pas[i]:
                bad += 1
                print("1e%d: computed %x %x, Go %x %x, pasnum %x %x" % (
                    MIN_EXP + i, mine[i][0], mine[i][1], go[i][0], go[i][1], pas[i][0], pas[i][1]))
        if bad:
            sys.exit("pow10gen: %d of 696 differ" % bad)
        print("pow10gen: 696 powers of ten, the same in Go's pow10tab.go, pasnum and here")
        return
    print("\n".join(lines()))


if __name__ == "__main__":
    main()
