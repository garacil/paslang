#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""What pashttp2 does at limits its own constants keep out of reach (P617).

  scripts/check_http2_variants.py PASLANGC BUILDDIR QEMU_A64 [UNIT]

UNIT is another text of the unit to try instead of
src/lib/pashttp2.paslang (a mutant, to see that this check catches it).

A connection has 2^30 stream numbers, takes a GiB before it gives the
connection's window back, and gives a stream's back before a frame can
overrun it: the code for the last stream number, for the connection's
window and for a peer that overruns a window is never reached by a test
of the unit as it is. Copies of the unit with those constants changed
are compiled as the unit, for amd64 and arm64, and testdata/http2fake
runs its cases for each:

- numbers: the first stream is 2^31 - 3. Two requests go, on the last
  two numbers; a third is refused unwritten and can go on another
  connection; the connection ends with the last of the two (RFC 9113
  5.1.1).
- windows: a connection window of 65536, a stream window of 20000 and
  frames of 16384. The windows are given back at half, the connection's
  too; a frame within the largest but past what the stream's window has
  left is FLOW_CONTROL_ERROR; a frame past the largest is
  FRAME_SIZE_ERROR at the new size (6.9.1, 4.2).
- connwindow: a connection window of 16 over the 65535 it begins with.
  A frame of the whole window is taken and given back; one octet more
  is FLOW_CONTROL_ERROR.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

tree = Path(__file__).resolve().parents[1]
compiler = Path(sys.argv[1]).resolve()
build = Path(sys.argv[2]).resolve()
qemu = Path(sys.argv[3]).resolve()
root = Path(tempfile.mkdtemp(prefix='http2-variants-', dir=build))
unit = Path(sys.argv[4]).resolve() if len(sys.argv) > 4 else tree / 'src/lib/pashttp2.paslang'
source = unit.read_text()

FIRST = '  FNextId := 1;\n'
CONN = '  H2ConnWindow = 1073741824;\n'
STREAM = '  H2StreamWindow = 4194304;\n'
FRAME = '  H2ReadFrame = 1048576;\n'
for piece in (FIRST, CONN, STREAM, FRAME):
    assert source.count(piece) == 1, piece

variants = {
    'numbers': (source.replace(FIRST, '  FNextId := 2147483645;\n'),
                'the stream numbers run out: 5 of 5\n'),
    'windows': (source.replace(CONN, '  H2ConnWindow = 65536;\n').replace(STREAM, '  H2StreamWindow = 20000;\n')
                .replace(FRAME, '  H2ReadFrame = 16384;\n'),
                'windows of another size: 9 of 9\n'),
    'connwindow': (source.replace(CONN, '  H2ConnWindow = 16;\n'),
                   'a connection window of 16: 3 of 3\n'),
}


def run(args, timeout=120):
    done = subprocess.run(list(map(str, args)), cwd=root, capture_output=True, timeout=timeout)
    assert done.returncode == 0, (args, done.stderr[-400:], done.stdout[-400:])
    return done.stdout.decode()


for target in ('amd64', 'arm64'):
    flags = ['-cpu', 'base'] + (['-target', 'arm64'] if target == 'arm64' else [])
    core = build / ('a64' if target == 'arm64' else '')
    launch = [qemu, '-cpu', 'max'] if target == 'arm64' else []
    for label, (text, want) in variants.items():
        directory = root / (label + '-' + target)
        directory.mkdir()
        (directory / 'pashttp2.paslang').write_text(text)
        run([compiler, *flags, '-c', '-Fu', core, '-o', directory / 'pashttp2', directory / 'pashttp2.paslang'])
        binary = directory / 'http2fake'
        run([compiler, *flags, '-Fu', directory, '-Fu', core, '-o', binary, tree / 'testdata/http2fake.paslang'])
        got = run([*launch, binary, label])
        assert got == want, (label, target, got)
        print(label, target, 'as expected', flush=True)
assert unit.read_text() == source
print('ok http2 variants: %d builds on two machines' % len(variants))
