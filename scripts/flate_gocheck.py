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

def run_output(args, *, input=None):
    result = subprocess.run(args, input=None if input is None else input.encode("utf-8"),
                            capture_output=True, check=False)
    if result.returncode != 0 or result.stderr:
        print("flate_gocheck: child status %d, stderr %d bytes: %r" %
              (result.returncode, len(result.stderr), args), file=sys.stderr, flush=True)
        sys.stderr.buffer.write(result.stdout)
        sys.stderr.buffer.write(result.stderr)
        sys.stderr.buffer.flush()
        sys.exit(1)
    return result.stdout.decode("utf-8")


here = os.path.dirname(os.path.abspath(__file__))
flatec = sys.argv[1]
if shutil.which("go") is None:
    print("no go: flate_gocheck skipped")
    sys.exit(2)
shapes = run_output([flatec, "data"])
mine = run_output([flatec]).splitlines()
names = set(l.split()[0] for l in shapes.splitlines()) - {"text400k", "soup200k"}
mine = [ln for ln in mine if ln.split()[0] in names or ln.startswith("sweep ")]
go = run_output(["go", "run", os.path.join(here, "flate_gocheck.go")], input=shapes).splitlines()
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
