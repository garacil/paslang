#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""sigsent_check.py BINARY [RUNNER ...]: sends SIGSEGV, SIGBUS and SIGFPE to testdata/sigsent while it turns in its
loop (P568, P581).

The program has a handler for EAccessViolation around the loop. A fault of its own code there would be raised
and taken (a bus error too: EBusError is its child); a signal that someone sent is no fault, and the program
must end as it always did, with status 1 and not one word from the handler, and with a line that says what
happened: the signal, that it was sent, the process that sent it when the signal's code tells one, and where
the program was.

  paslang: SIGSEGV sent by process 12345 at line 31

Four ways for each signal: kill(2), which the kernel gives to whichever thread it chooses (code SI_USER);
tgkill(2) at the thread the program says its loop runs on (SI_TKILL), where the pc is the loop's own code;
sigqueue(3) (SI_QUEUE); and rt_sigqueueinfo(2) with a code that tells no process (SI_ASYNCIO), whose line
names none.

RUNNER is what runs the binary when it is not this machine's (an emulator and its options): its threads are
the program's, with the same numbers.
Exit status 1 when the program does anything else."""
import ctypes
import os
import platform
import signal
import struct
import subprocess
import sys

if len(sys.argv) < 2:
    sys.exit(__doc__)
# tgkill and rt_sigqueueinfo by their numbers on the machine this script runs on (asm/unistd_64.h;
# asm-generic/unistd.h)
NUMBERS = {'x86_64': (234, 129), 'aarch64': (131, 138)}.get(platform.machine())
if NUMBERS is None:
    sys.exit('sigsent_check: no system call numbers for a machine %s' % platform.machine())
TGKILL, SIGQUEUEINFO = NUMBERS
SI_ASYNCIO = -4
libc = ctypes.CDLL(None, use_errno=True)
me = os.getpid()


def one(how, sig):
    p = subprocess.Popen(sys.argv[2:] + [os.path.abspath(sys.argv[1])], stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        line = p.stdout.readline().split()
        if len(line) != 2 or line[0] != b'ready' or not line[1].isdigit():
            sys.exit('sigsent_check: the program said %r, not ready and its thread' % line)
        if how == 'kill':
            rc = 0
            os.kill(p.pid, sig)
        elif how == 'tgkill':
            rc = libc.syscall(TGKILL, p.pid, int(line[1]), int(sig))
        elif how == 'sigqueue':
            rc = libc.sigqueue(p.pid, int(sig), ctypes.c_void_p(0))
        else:
            # a siginfo of 128 bytes: the signal, no error, the code, and nothing after them
            info = ctypes.create_string_buffer(struct.pack('iii', int(sig), 0, SI_ASYNCIO).ljust(128, b'\0'), 128)
            rc = libc.syscall(SIGQUEUEINFO, p.pid, int(sig), info)
        if rc != 0:
            sys.exit('sigsent_check: %s(%d, %s): %s' % (how, p.pid, sig.name, os.strerror(ctypes.get_errno())))
        try:
            out, err = p.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            sys.exit('sigsent_check: the program did not end in 30 seconds after %s (%s)' % (sig.name, how))
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()
    err = err.decode('utf-8', 'replace')
    if b'taken' in out or b'not reached' in out:
        sys.exit('sigsent_check: the handler ran for a %s sent with %s: %r' % (sig.name, how, out[:120]))
    want = 'paslang: %s sent%s at ' % (sig.name, '' if how == 'raw' else ' by process %d' % me)
    if p.returncode != 1 or not err.startswith(want) or err.count('\n') != 1:
        sys.exit('sigsent_check: %s with %s: status %d and %r on the error output, not 1 and a line that starts %r'
                 % (sig.name, how, p.returncode, err[:160], want))
    return err.strip()


n = 0
for sig in (signal.SIGSEGV, signal.SIGBUS, signal.SIGFPE):
    said = [one(how, sig) for how in ('kill', 'tgkill', 'sigqueue', 'raw')]
    n += len(said)
    print('sigsent_check: %s sent with kill, tgkill at the loop\'s thread, sigqueue and a code that tells no '
          'process: %r, %r' % (sig.name, said[1], said[3]))
print('sigsent_check: %d signals that were sent end the program with status 1, each with its line, and no '
      'handler runs' % n)
