#!/usr/bin/env python3
"""P427: what pasflate's writer makes, read by zlib and gzip (the real
ones), and its size against zlib's on the same data.

    ./flatec dump | flate_verify.py

testdata/flatec.paslang with the argument dump writes each stream as
`KIND NAME LEVEL CRC32 LENGTH HEX`. Each must read back, with Python's
zlib (raw, zlib, gzip), to a text of that length and CRC-32. The sizes are
printed beside the ones zlib makes of the same text at the same level.
Exit 1 if a stream does not read or reads wrong.
"""
import gzip
import os
import subprocess
import sys
import zlib

bad = 0
n = 0
ratios = {}
rows = [ln.split() if len(ln.split()) == 6 else ln.split() + [""] for ln in sys.stdin]
for kind, name, level, crc, length, hx in rows:
    level, crc, length = int(level), int(crc), int(length)
    blob = bytes.fromhex(hx)
    try:
        if kind == "raw":
            d = zlib.decompressobj(-15)
            data = d.decompress(blob)
            assert d.eof and not d.unused_data
        elif kind == "zlib":
            d = zlib.decompressobj(15)
            data = d.decompress(blob)
            assert d.eof and not d.unused_data
        else:
            data = gzip.decompress(blob)
        assert len(data) == length and zlib.crc32(data) == crc
    except Exception as e:
        bad += 1
        print("BAD", kind, name, level, e)
        continue
    n += 1
    if kind == "raw":
        c = zlib.compressobj(level, zlib.DEFLATED, -15)
        ref = len(c.compress(data) + c.flush())
        if ref:
            ratios.setdefault(level, []).append((len(blob) / ref, name, len(blob), ref))
# and Go's compress packages
here = os.path.dirname(os.path.abspath(__file__))
inp = "".join("%s %d %s\n" % (r[0], i, r[5] or "-") for i, r in enumerate(rows))
out = subprocess.run(["go", "run", os.path.join(here, "flate_oracle.go")], input=inp, capture_output=True, text=True).stdout
gobad = 0
for i, ln in enumerate(out.splitlines()):
    v = ln.split()[1]
    if v != "ok:%d:%08x" % (int(rows[i][4]), int(rows[i][3])):
        gobad += 1
        print("Go BAD", rows[i][:3], v)
print("streams read by Go:", len(rows) - gobad, "bad:", gobad)
bad += gobad
print("streams read by zlib/gzip:", n, "bad:", bad - gobad)
for lv in sorted(ratios):
    r = ratios[lv]
    worst = max(r)
    avg = sum(x[0] for x in r) / len(r)
    print("level %d: size / zlib's: mean %.3f, worst %.3f (%s %d vs %d)" % (lv, avg, worst[0], worst[1], worst[2], worst[3]))
sys.exit(1 if bad else 0)
