#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P217: a program keeps the flags of the standard streams it was given.

It shares the open file descriptions of its standard input, output and
error with its shell and the programs around it. Before 1.1.96 the
runtime set O_NONBLOCK on 0, 1 and 2 for good, so a cat writing to the
same pipe after a paslang program stopped with EAGAIN. Go never sets it
on them (src/os/file_unix.go newFileFromNewFile): a stream found
blocking blocks in its system call with its P handed over, one found
nonblocking parks on the poller.

testdata/stdflags runs on pipes made blocking or nonblocking, on one CPU
under the collector's stress, poison and verify modes and on all CPUs:
- the flags it finds and the flags after it are the ones it was given;
- a head writing 1 MiB to the same standard output after it writes all;
- a line a second late on standard input, and a standard output nobody
  reads for a second, let main tick and collect meanwhile;
- a fatal error whose standard error is nonblocking and full waits for
  room in poll, spending no CPU, where it spun on EAGAIN.
"""
import fcntl
import os
from pathlib import Path
import resource
import select
import shutil
import signal
import subprocess
import sys
import time


compiler = str(Path(sys.argv[1]).resolve())
build = Path(sys.argv[2]).resolve()
qemu = sys.argv[3:]
if not qemu:
    raise SystemExit("usage: check_stdstreams.py compiler build qemu [options]")
work = build / "check-stdstreams"
if work.exists():
    shutil.rmtree(work)
work.mkdir()
base_env = {key: value for key, value in os.environ.items() if not key.startswith("PASLANG_GC")}
stress = dict(base_env, PASLANG_GCVERIFY="1", PASLANG_GCSTRESS="1", PASLANG_GCPOISON="1")
cpu = str(min(os.sched_getaffinity(0)))
LATE = 1.0
LINES, WIDTH = 200, 1000
MIB = 1 << 20
source = Path("testdata/stdflags.paslang").read_text().splitlines()
fault_line = next(number for number, text in enumerate(source, 1) if text.strip() == "p^ := 7;")


def mode(fd):
    return "nonblocking" if fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_NONBLOCK else "blocking"


def flags_line(given):
    return ("standard input %s, standard output %s, standard error %s\n" % tuple(
        "nonblocking" if nonblocking else "blocking" for nonblocking in given)).encode()


def read_exact(fd, count, what):
    data = b""
    deadline = time.monotonic() + 60
    while len(data) < count:
        left = deadline - time.monotonic()
        if left <= 0 or not select.select([fd], [], [], left)[0]:
            break
        chunk = os.read(fd, min(count - len(data), 1 << 16))
        if not chunk:
            break
        data += chunk
    if len(data) != count:
        raise RuntimeError(f"{what}: {len(data)} bytes of {count}")
    return data


def read_all(fd):
    data = b""
    while chunk := os.read(fd, 1 << 16):
        data += chunk
    return data


class Child:
    """The program on three new pipes: given[i] makes the child's end of
    stream i nonblocking. This process keeps its own copy of each of the
    child's ends, the same open file descriptions, to read their flags
    after the child is gone."""

    def __init__(self, command, given, env, affinity, fill_error=False):
        self.given = given
        self.command = command
        self.ends = []
        mine = []
        for stream in range(3):
            read_end, write_end = os.pipe()
            child_end, my_end = (read_end, write_end) if stream == 0 else (write_end, read_end)
            os.set_blocking(child_end, not given[stream])
            self.ends.append(child_end)
            mine.append(my_end)
        self.stdin_w, self.stdout_r, self.stderr_r = mine
        self.filled = 0
        if fill_error:
            # The pipe full to its last byte: 4096 a write while a page
            # is free, then single bytes into the last page.
            for size in (4096, 1):
                try:
                    while True:
                        self.filled += os.write(self.ends[2], b"f" * size)
                except BlockingIOError:
                    pass
        self.cpu_before = resource.getrusage(resource.RUSAGE_CHILDREN)
        self.process = subprocess.Popen([*affinity, *command], env=env, stdin=self.ends[0],
                                        stdout=self.ends[1], stderr=self.ends[2],
                                        start_new_session=True)

    def finish(self):
        """Waits for the child, checks the flags it leaves behind and
        returns its exit code, its output and the CPU it spent."""
        try:
            self.process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait()
            raise RuntimeError(f"timeout: {self.command}")
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        spent = (after.ru_utime - self.cpu_before.ru_utime) + (after.ru_stime - self.cpu_before.ru_stime)
        left = tuple(mode(end) == "nonblocking" for end in self.ends)
        if left != self.given:
            raise RuntimeError(f"{self.command}: flags {self.given} became {left}")
        for end in (*self.ends, self.stdin_w):
            os.close(end)
        output = read_all(self.stdout_r), read_all(self.stderr_r)
        os.close(self.stdout_r)
        os.close(self.stderr_r)
        return self.process.returncode, output[0], output[1], spent


def expect(what, got, want):
    if got != want:
        raise RuntimeError(f"{what}: {got!r} where {want!r}")


for target in ("amd64", "arm64"):
    core = build if target == "amd64" else build / "a64"
    runner = [] if target == "amd64" else qemu
    binary = work / f"stdflags-{target}"
    subprocess.run([compiler, "-target", target, "-Fu", str(core), "-o", str(binary),
                    "testdata/stdflags.paslang"], check=True)
    program = [*runner, str(binary)]
    for environment, affinity in ((stress, ["taskset", "-c", cpu]), (base_env, [])):
        where = f"{target}, {'one CPU' if affinity else 'all CPUs'}"
        for given in ((False, False, False), (True, True, True)):
            name = f"{where}, {'nonblocking' if given[0] else 'blocking'}"
            # The flags main finds are the ones it was given, and stay.
            child = Child([*program, "flags"], given, environment, affinity)
            code, out, err, _ = child.finish()
            expect(f"flags ({name})", (code, out, err), (0, flags_line(given), b""))
            # ReadLn waits for a line a second late; main goes on.
            child = Child([*program, "read"], given, environment, affinity)
            time.sleep(LATE)
            os.write(child.stdin_w, b"late\n")
            code, out, err, _ = child.finish()
            expect(f"read ({name})", (code, out, err), (0, flags_line(given) +
                   b"read late, 10 ticks and a collection before it came 1\n", b""))
            # WriteLn waits for a reader a second late; main goes on.
            child = Child([*program, "write"], given, environment, affinity)
            time.sleep(LATE)
            lines = read_exact(child.stdout_r, LINES * (WIDTH + 1), f"write ({name})")
            code, out, err, _ = child.finish()
            expect(f"write ({name})", (code, lines + out, err),
                   (0, (b"w" * WIDTH + b"\n") * LINES, flags_line(given) +
                    b"10 ticks and a collection while the writer was stuck 1, 200 lines written\n"))
        # A head after the program on the same standard output writes all
        # of its MiB, though nobody reads it for a second.
        given = (False, False, False)
        child = Child(["sh", "-c", '"$@" flags && exec head -c %d /dev/zero' % MIB, "sh", *program],
                      given, environment, affinity)
        time.sleep(LATE)
        line = flags_line(given)
        out = read_exact(child.stdout_r, len(line) + MIB, f"a head after the program ({where})")
        code, rest, err, _ = child.finish()
        expect(f"a head after the program ({where})", (code, out + rest, err), (0, line + bytes(MIB), b""))
        # A fatal error on a full nonblocking standard error waits for
        # room without spinning: the CPU it spends is its start, not the
        # second it waits.
        given = (False, False, True)
        child = Child([*program, "fatal"], given, environment, affinity, fill_error=True)
        time.sleep(LATE)
        filler = read_exact(child.stderr_r, child.filled, f"fatal ({where})")
        code, out, err, spent = child.finish()
        expect(f"fatal ({where})", (code, out, filler + err),
               (1, flags_line(given), b"f" * child.filled +
                b"paslang: nil pointer dereference at line %d\n" % fault_line))
        if spent >= LATE / 2:
            raise RuntimeError(f"fatal ({where}): {spent:.3f} s of CPU while standard error was full")
    print(f"ok stdstreams {target} (flags kept, blocking and nonblocking, one CPU and all, "
          "a head after the program, a fatal error on a full standard error)", flush=True)
shutil.rmtree(work)
