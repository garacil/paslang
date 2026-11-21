#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacil@tucall.com>
# GPL version 3 or later. See COPYING.
"""Run the golden programs with GC stress and diagnose a timed-out child."""

import argparse
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


# Source 1.3.39, Ryzen 7 4800H with concurrent work. The longest ordinary
# runs were about 44 s on amd64 and 95 s under QEMU. The same run measured
# store1 at about 79 s and 323 s, and mapsmall at 156 s under QEMU.
LIMITS = {"amd64": 120, "arm64": 300}
LONG_CASES = {
    "amd64": {"store1": 300},
    "arm64": {"mapsmall": 600, "store1": 1200},
}
TAIL_BYTES = 16 * 1024


def thread_waits(pid):
    proc = Path("/proc") / str(pid) / "task"
    try:
        threads = sorted(proc.iterdir(), key=lambda path: int(path.name))
    except OSError as error:
        print(f"cannot read thread waits for process {pid}: {error}", file=sys.stderr)
        return
    for thread in threads:
        try:
            status = (thread / "status").read_text()
            state = next(line.split(":", 1)[1].strip()
                         for line in status.splitlines() if line.startswith("State:"))
            wait = (thread / "wchan").read_text().strip()
        except (OSError, StopIteration):
            print(f"thread {thread.name}: state and wchan unavailable", file=sys.stderr)
            continue
        print(f"thread {thread.name}: state {state}, wchan {wait}", file=sys.stderr)


def output_tail(path):
    with path.open("rb") as output:
        size = output.seek(0, os.SEEK_END)
        output.seek(max(0, size - TAIL_BYTES))
        tail = output.read(TAIL_BYTES).decode("utf-8", "backslashreplace")
    if tail:
        print(f"stdout tail from {path}", file=sys.stderr)
        print(tail, end="" if tail.endswith("\n") else "\n", file=sys.stderr)


def wait(child, deadline, interrupted):
    while not interrupted:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return child.poll()
        try:
            return child.wait(timeout=min(remaining, 0.25))
        except subprocess.TimeoutExpired:
            continue
    return None


def run_case(argv, output, limit, interrupted, label):
    started = time.monotonic()
    status = None
    with output.open("wb") as stream:
        child = subprocess.Popen(argv, stdout=stream, start_new_session=True)
        try:
            status = wait(child, started + limit, interrupted)
            if status is None and not interrupted:
                print(f"{label} timed out after {limit:g} seconds", file=sys.stderr)
                thread_waits(child.pid)
        finally:
            if child.returncode is None:
                # The unreaped leader keeps this process group ID reserved.
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
    if interrupted:
        return 128 + interrupted[0], time.monotonic() - started
    if status != 0:
        if status is not None:
            print(f"{label} exited with status {status}", file=sys.stderr)
        output_tail(output)
        status = 124 if status is None else (128 - status if status < 0 else status)
    return status, time.monotonic() - started


def main():
    parser = argparse.ArgumentParser(allow_abbrev=False, description=__doc__)
    parser.add_argument("--arch", choices=LIMITS, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--qemu", type=Path)
    parser.add_argument("--limit", type=float)
    parser.add_argument("cases", nargs="+")
    args = parser.parse_args()
    if (args.arch == "arm64") != (args.qemu is not None):
        parser.error("--qemu is required only for arm64")
    if args.limit is not None and (not math.isfinite(args.limit) or args.limit <= 0):
        parser.error("--limit must be finite and positive")
    interrupted = []
    for signum in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda number, frame: interrupted.append(number))
    os.environ.update(PASLANG_GCVERIFY="1", PASLANG_GCSTRESS="3", PASLANG_GCPOISON="1")
    prefix = [args.qemu] if args.qemu else []
    suffix = "-arm" if args.qemu else ""
    slowest = (0, "")
    for case in args.cases:
        if interrupted:
            return 128 + interrupted[0]
        name = case + suffix
        output = args.build / (name + ".vgot")
        expected = Path("testdata") / (case + ".out")
        limit = args.limit or LONG_CASES[args.arch].get(case, LIMITS[args.arch])
        status, elapsed = run_case([*prefix, os.path.join(args.build, name)],
                                   output, limit, interrupted, f"{args.arch}/{case}")
        if status:
            return status
        if output.read_bytes() != expected.read_bytes():
            return subprocess.run(["diff", "-u", expected, output]).returncode
        slowest = max(slowest, (elapsed, case))
    print(f"GC stress {args.arch}: slowest {slowest[1]} in {slowest[0]:.2f} seconds", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
