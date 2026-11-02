#!/usr/bin/env python3
"""P449: pasflate's writer makes the bytes of Go's compress/flate.

    flate_gocheck.py FLATEC

FLATEC is the compiled testdata/flatec. It writes the twelve shapes of data
(`flatec data`); scripts/flate_gocheck.go writes, with Go's compress/flate and
gzip, the lines flatec writes for them (the size and hash of the raw stream
and of the gzip file at each level -2 and 0 to 9, and of the raw stream of
the data written in pieces with flushes between, and of the streams of many cuts
of a text, of random bytes and of a long text); the two lists of lines must be
the same. Exit 1 if they are not, 2 if there is no go to ask.
"""
import os
import shutil
import subprocess
import sys

here = os.path.dirname(os.path.abspath(__file__))
flatec = sys.argv[1]
if shutil.which("go") is None:
    print("no go: flate_gocheck skipped")
    sys.exit(2)
shapes = subprocess.run([flatec, "data"], capture_output=True, text=True, check=True).stdout
mine = subprocess.run([flatec], capture_output=True, text=True, check=True).stdout.splitlines()
names = set(l.split()[0] for l in shapes.splitlines()) - {"text400k", "soup200k"}
mine = [ln for ln in mine if ln.split()[0] in names or ln.startswith("sweep ")]
go = subprocess.run(["go", "run", os.path.join(here, "flate_gocheck.go")], input=shapes, capture_output=True, text=True, check=True).stdout.splitlines()
bad = 0
for a, b in zip(mine, go):
    if a != b:
        bad += 1
        print("DIFFERENT")
        print("  pasflate:", a)
        print("  Go:      ", b)
if len(mine) != len(go):
    bad += 1
    print("pasflate wrote %d lines, Go %d" % (len(mine), len(go)))
print("lines the same as Go's: %d, different: %d" % (len(mine) - bad, bad))
sys.exit(1 if bad else 0)
