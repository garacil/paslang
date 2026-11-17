#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""check_twoservers.py OUT PROGRAM [RUNNER...] (P639): examples/twoservers,
run under RUNNER (qemu for arm64) on two free ports, answers on both,
then a SIGTERM ends the whole program within ten seconds, with status 0
and its standard output equal to OUT. Its admin server's accept loop is a
background routine; before P639 such a program stayed alive."""
import signal
import subprocess
import sys
import time
import urllib.request

out, prog, runner = sys.argv[1], sys.argv[2], sys.argv[3:]
p = subprocess.Popen(runner + [prog, '0', '0'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
ports = p.stderr.readline().split()
if len(ports) != 3 or ports[0] != 'ports':
    p.kill()
    sys.exit('twoservers: no ports line: %r' % ports)
first = p.stdout.readline()
for port, path, want in ((ports[1], '/', 'public\n'), (ports[2], '/health', 'ok\n')):
    body = urllib.request.urlopen('http://127.0.0.1:%s%s' % (port, path), timeout=10).read().decode()
    if body != want:
        p.kill()
        sys.exit('twoservers: %s answered %r' % (path, body))
t0 = time.monotonic()
p.send_signal(signal.SIGTERM)
try:
    rest, _ = p.communicate(timeout=10)
except subprocess.TimeoutExpired:
    p.kill()
    sys.exit('twoservers: still alive 10 s after SIGTERM')
if p.returncode != 0:
    sys.exit('twoservers: status %d' % p.returncode)
got = first + rest
if got != open(out).read():
    sys.exit('twoservers: printed %r' % got)
print('check_twoservers: both servers answered and SIGTERM ended the program in %.1f s' % (time.monotonic() - t0))
