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

"""The peak resident memory of a program, read as it exits (P223).

  scripts/bench/peak.py PROGRAM [ARG...]   print its peak in KiB on stderr

peak_kib(argv) runs the program traced (PTRACE_TRACEME, then
PTRACE_O_TRACEEXIT) and, when its main thread stops at its exit, reads
VmHWM from /proc/PID/status: the high-water mark of its own address
space, with the resident size of that moment summed exactly over the
CPUs (fs/proc/task_mmu.c task_mem, get_mm_counter_sum). Nothing else is
stopped: signals are given back to the program as they come.

The program runs with transparent huge pages off (prctl
PR_SET_THP_DISABLE, kept across fork and execve), so the peak is the
4 KiB pages it touched. With them always on, as on this machine, a small
program's peak moves by 2 MiB from one run to the next as its regions
fall with ASLR: a 276 KiB paslang program read 276, 2316 or 4360 KiB,
Go's smallest 2196, 3676 or 5728. What huge pages cost each side is a
measure of its own.

The getrusage maximum that run.py used before is not this. A child's
ru_maxrss starts at the high-water mark of the address space it had
before exec, its parent's copy (fs/exec.c exec_mm_put_old), so every
small program launched from Python read Python's 13 MB. And it is read
with get_mm_counter (include/linux/mm.h), the global count without what
each CPU has not yet folded in, up to percpu_counter_batch pages a CPU
(lib/percpu_counter.c, max(32, 2 * CPUs)): about 2 MB on 16 CPUs, more
than a small program's whole size. VmHWM keeps one approximation: a
peak the program had already given back is recorded at the moment it
gave it back with that same global count (mm->hiwater_rss).
"""
import ctypes
import os
import signal
import sys

PTRACE_TRACEME = 0
PTRACE_CONT = 7
PTRACE_SETOPTIONS = 0x4200
PTRACE_EVENT_EXIT = 6
PTRACE_O_TRACEEXIT = 1 << PTRACE_EVENT_EXIT
PR_SET_THP_DISABLE = 41   # include/uapi/linux/prctl.h

_libc = ctypes.CDLL(None, use_errno=True)
_libc.ptrace.restype = ctypes.c_long
_libc.ptrace.argtypes = [ctypes.c_long, ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p]
_libc.prctl.restype = ctypes.c_int
_libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]


def _ptrace(req, pid, data):
    if _libc.ptrace(req, pid, None, ctypes.c_void_p(data)) == -1:
        e = ctypes.get_errno()
        raise OSError(e, "ptrace %d: %s" % (req, os.strerror(e)))


def _hwm_kib(pid):
    with open("/proc/%d/status" % pid) as f:
        for line in f:
            if line.startswith("VmHWM:"):
                return int(line.split()[1])
    return -1


def peak_kib(argv, env=None, stdout=None, stderr=None):
    """(peak KiB, exit status) of argv run to its end; stdout and stderr
    are file descriptors for the program, or None to keep this process's."""
    pid = os.fork()
    if pid == 0:
        try:
            if stdout is not None:
                os.dup2(stdout, 1)
            if stderr is not None:
                os.dup2(stderr, 2)
            if _libc.prctl(PR_SET_THP_DISABLE, 1, 0, 0, 0) != 0:
                os._exit(126)
            _ptrace(PTRACE_TRACEME, 0, 0)
            if env is None:
                os.execv(argv[0], argv)
            os.execve(argv[0], argv, env)
        finally:
            os._exit(127)
    # The first stop is the SIGTRAP of the exec.
    _, st = os.waitpid(pid, 0)
    if not os.WIFSTOPPED(st):
        return -1, os.waitstatus_to_exitcode(st)
    _ptrace(PTRACE_SETOPTIONS, pid, PTRACE_O_TRACEEXIT)
    _ptrace(PTRACE_CONT, pid, 0)
    peak = -1
    while True:
        _, st = os.waitpid(pid, 0)
        if os.WIFEXITED(st) or os.WIFSIGNALED(st):
            return peak, os.waitstatus_to_exitcode(st)
        sig = os.WSTOPSIG(st)
        if sig == signal.SIGTRAP and (st >> 16) == PTRACE_EVENT_EXIT:
            peak = _hwm_kib(pid)
            sig = 0
        _ptrace(PTRACE_CONT, pid, sig)


if __name__ == "__main__":
    kib, code = peak_kib(sys.argv[1:])
    print("peak %d KiB, exit status %d" % (kib, code), file=sys.stderr)
    sys.exit(code if code >= 0 else 1)
