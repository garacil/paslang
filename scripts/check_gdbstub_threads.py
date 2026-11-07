#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""check_gdbstub_threads.py BUILDDIR QEMU [SESSIONS]: QEMU's gdb stub keeps a breakpoint while the guest makes
threads (P582).

The checks that run a program under QEMU's stub (check_debug_growth, check_syscalls) set breakpoints that are
false at most stops, so gdb removes the breakpoint, steps and inserts it again each time, while the program's
runtime starts its threads. QEMU 11.1.1 lost the breakpoint when a removal came while a thread was being made
(scripts/qemu/0005: the new thread's CPU is in the list before it has its creator's breakpoints, the removal
stopped at it with an error, and gdb never inserts again a breakpoint it could not remove): once in a make
check on a busy machine, the debugged program ran to its end past the stop it was to make.

This is the case alone. The guest (scripts/qemu/gdbthreads.s, assembled and linked here) calls probe 2000
times on one thread, with a loop between two calls, while another makes threads that end at once; gdb
(scripts/qemu/gdbthreads_gdb.py) has a breakpoint at probe that is true at the last call. Each of SESSIONS
sessions (20 when not said) must stop there, with at least five hundred threads made meanwhile (about two
thousand are, on a machine with nothing else to do). Without the patch the breakpoint is lost in every
session; with part of it, the emulator dies in some.

The patch makes a thread's making and its exit exclusive sections, and QEMU's fork is one that then takes the
lock of a thread's making (fork_start(), linux-user/main.c): the two must be taken in fork's order everywhere.
The first form of the patch took them the other way round, and a guest that forked while one of its threads
was being made stood for ever (testdata/sysprocesses under make check, one run in three). So a second guest
(scripts/qemu/forkthreads.s) runs with no gdb: one thread forks 300 times, its children ending by exit and by
exit_group in turn, while another makes threads that end at once. Each of five runs must end within a minute
with status 0 and a hundred threads or more made meanwhile (about three hundred are)."""
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

if len(sys.argv) < 3:
    sys.exit(__doc__)
build = Path(sys.argv[1]).resolve()
qemu = str(Path(sys.argv[2]).resolve())
sessions = int(sys.argv[3]) if len(sys.argv) > 3 else 20
here = Path(__file__).resolve().parent / 'qemu'
COUNT = 2000
SPIN = 1000
FORKS = 300
FORK_RUNS = 5
work = build / 'check-gdbstub-threads'
if work.exists():
    shutil.rmtree(work)
work.mkdir()
guest = work / 'gdbthreads'
forker = work / 'forkthreads'
for command in (['aarch64-linux-gnu-as', '--defsym', 'COUNT=%d' % COUNT, '--defsym', 'SPIN=%d' % SPIN, '-o', str(work / 'gdbthreads.o'), str(here / 'gdbthreads.s')],
                ['aarch64-linux-gnu-ld', '-o', str(guest), str(work / 'gdbthreads.o')],
                ['aarch64-linux-gnu-as', '--defsym', 'FORKS=%d' % FORKS, '-o', str(work / 'forkthreads.o'), str(here / 'forkthreads.s')],
                ['aarch64-linux-gnu-ld', '-o', str(forker), str(work / 'forkthreads.o')]):
    r = subprocess.run(command, capture_output=True, text=True)
    if r.returncode:
        sys.exit('check_gdbstub_threads: %s: %s' % (command[0], (r.stdout + r.stderr).strip()))
# no gdb: a fork while a thread is made or ends
fewest = None
for n in range(FORK_RUNS):
    process = subprocess.Popen([qemu, str(forker)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, start_new_session=True)
    try:
        out, _ = process.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        sys.exit('check_gdbstub_threads: run %d of %d: the guest that forks %d times while another thread makes threads '
                 'did not end in 60 seconds (QEMU: a section and clone_lock taken in two orders)' % (n + 1, FORK_RUNS, FORKS))
    if process.returncode != 0 or len(out) != 8:
        sys.exit('check_gdbstub_threads: run %d of %d: the guest that forks ended with status %d and said %r'
                 % (n + 1, FORK_RUNS, process.returncode, out[-200:]))
    threads = int.from_bytes(out, 'little')
    if threads < 100:
        sys.exit('check_gdbstub_threads: run %d: only %d threads were made beside the %d forks' % (n + 1, threads, FORKS))
    fewest = threads if fewest is None else min(fewest, threads)
least = None
for n in range(sessions):
    with tempfile.TemporaryDirectory(prefix='pl-gdbt-') as directory:
        endpoint = Path(directory) / 'gdb.sock'
        process = subprocess.Popen([qemu, '-g', str(endpoint), str(guest)], stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + 20
            while not endpoint.exists():
                if process.poll() is not None or time.monotonic() >= deadline:
                    sys.exit('check_gdbstub_threads: QEMU did not open its gdb socket')
                time.sleep(.01)
            try:
                g = subprocess.run(['gdb', '-batch', '-nx', '-q', str(guest), '-ex', 'set debuginfod enabled off',
                                    '-ex', 'set pagination off', '-ex', 'set $probe_count = %d' % COUNT,
                                    '-ex', 'target remote %s' % endpoint, '-ex', 'source %s' % (here / 'gdbthreads_gdb.py')],
                                   env=dict(os.environ, DEBUGINFOD_URLS=''), stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, timeout=300)
                out = g.stdout.decode(errors='replace')
            except subprocess.TimeoutExpired:
                out = 'gdb did not end in 300 seconds'
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
    m = re.search(r'the last of %d calls of probe stopped at its breakpoint, (\d+) threads made meanwhile' % COUNT, out)
    if not m:
        said = [l for l in out.split('\n') if l and not l.startswith('[New Thread') and 'exited]' not in l]
        sys.exit('check_gdbstub_threads: session %d of %d: %s' % (n + 1, sessions, ' | '.join(said[-4:])[:400]))
    made = int(m.group(1))
    if made < 500:
        sys.exit('check_gdbstub_threads: session %d: only %d threads were made beside the %d stops' % (n + 1, made, COUNT))
    least = made if least is None else min(least, made)
shutil.rmtree(work)
print('check_gdbstub_threads: %d sessions, in each the last of %d calls stopped at its breakpoint after %d that gdb '
      'stepped over, with %d threads or more made meanwhile; with no gdb, %d runs of %d forks each ended, with %d '
      'threads or more made meanwhile' % (sessions, COUNT, COUNT - 1, least, FORK_RUNS, FORKS, fewest))
