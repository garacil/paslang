#!/usr/bin/env python3
"""P427: the archives paszip writes, read by zipfile and by Go's archive/zip.

    ./zip dump | zip_verify.py

testdata/zip.paslang with the argument dump writes `NAME CRC32 HEX` for
each archive its writer made (CRC32 is the one of the listing of the
entries). zipfile must pass testzip() and give that listing, and so must
Go (scripts/zip_oracle.go). Exit 1 if either does not.
"""
import io
import os
import subprocess
import sys
import zipfile
import zlib

here = os.path.dirname(os.path.abspath(__file__))
rows = [ln.split() for ln in sys.stdin if ln.strip()]
bad = 0
for name, crc, hx in rows:
    blob = bytes.fromhex(hx)
    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
        assert zf.testzip() is None
        lst = b""
        for zi in zf.infolist():
            data = zf.read(zi)
            raw = zi.orig_filename.encode("utf-8" if zi.flag_bits & 0x800 else "cp437")
            lst += raw + b"\t" + str(len(data)).encode() + b"\t" + str(zlib.crc32(data) & 0xffffffff).encode() + b"\n"
        assert zlib.crc32(lst) & 0xffffffff == int(crc)
        print("zipfile reads", name, "ok:", len(zf.infolist()), "entries")
    except Exception as e:
        bad += 1
        print("zipfile BAD", name, e)
inp = "".join("%d %s\n" % (i, r[2]) for i, r in enumerate(rows))
out = subprocess.run(["go", "run", os.path.join(here, "zip_oracle.go")], input=inp, capture_output=True, text=True).stdout
for i, ln in enumerate(out.splitlines()):
    v = ln.split()[1]
    want = "ok:"
    if not v.startswith(want) or v.split(":")[2] != str(int(rows[i][1])):
        bad += 1
        print("Go BAD", rows[i][0], v)
    else:
        print("Go reads", rows[i][0], v)
sys.exit(1 if bad else 0)
