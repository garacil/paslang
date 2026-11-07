#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""sigsent_check.py BINARY [RUNNER ...]: sends SIGSEGV and SIGBUS to testdata/sigsent while it turns in its loop (P568).

The program has a handler for EAccessViolation around the loop. A fault of its own code there would be raised
and taken (a bus error too: EBusError is its child); a signal that someone sent is no fault, and the program
must end as it always did: status 1, a line of the runtime on the error output, and not one word from the
handler. Two runs for each signal: sent with kill(2), which the kernel gives to whichever thread it chooses
(code SI_USER), and with tgkill(2) at the thread the program says its loop runs on (code SI_TKILL), where the
pc is the loop's own code.

RUNNER is what runs the binary when it is not this machine's (an emulator and its options): its threads are
the program's, with the same numbers.
Exit status 1 when the program does anything else."""
import ctypes
import os
import platform
import signal
import subprocess
import sys

if len(sys.argv) < 2:
    sys.exit(__doc__)
# tgkill by its number on the machine this script runs on (asm/unistd_64.h; asm-generic/unistd.h)
TGKILL = {'x86_64': 234, 'aarch64': 131}.get(platform.machine())
libc = ctypes.CDLL(None, use_errno=True)


def one(how, sig):
    p = subprocess.Popen(sys.argv[2:] + [os.path.abspath(sys.argv[1])], stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        line = p.stdout.readline().split()
        if len(line) != 2 or line[0] != b'ready' or not line[1].isdigit():
            sys.exit('sigsent_check: the program said %r, not ready and its thread' % line)
        if how == 'kill':
            os.kill(p.pid, sig)
        elif libc.syscall(TGKILL, p.pid, int(line[1]), int(sig)) != 0:
            sys.exit('sigsent_check: tgkill(%d, %d): %s' % (p.pid, int(line[1]), os.strerror(ctypes.get_errno())))
        try:
            out, err = p.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            sys.exit('sigsent_check: the program did not end in 30 seconds after %s (%s)' % (sig.name, how))
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()
    if b'taken' in out or b'not reached' in out:
        sys.exit('sigsent_check: the handler ran for a %s sent with %s: %r' % (sig.name, how, out[:120]))
    if p.returncode != 1 or not err.startswith(b'paslang: '):
        sys.exit('sigsent_check: %s with %s: status %d and %r on the error output, not 1 and a line of the runtime'
                 % (sig.name, how, p.returncode, err[:120]))
    return err.decode().strip()


if TGKILL is None:
    sys.exit('sigsent_check: no number of tgkill for a machine %s' % platform.machine())
for sig in (signal.SIGSEGV, signal.SIGBUS):
    a = one('kill', sig)
    b = one('tgkill', sig)
    print('sigsent_check: a %s that was sent ends the program with status 1 and no handler runs: with kill %r, '
          'with tgkill at the loop\'s thread %r' % (sig.name, a, b))
