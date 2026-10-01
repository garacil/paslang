#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P178: saturated blocking calls preserve G/M/P, GC and stack roots.

Unique build directories, dynamically selected affinity and a private
Unix GDB socket avoid shared output files, CPU assumptions and port races.
The QEMU user-mode socket endpoint is documented at
https://www.qemu.org/docs/master/user/main.html#linux-user-space-emulator
"""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


compiler = str(Path(sys.argv[1]).resolve())
build = Path(sys.argv[2]).resolve()
qemu = sys.argv[3:]
inject_only = "--inject-only" in qemu
if inject_only:
    qemu.remove("--inject-only")
if not qemu:
    raise SystemExit("usage: check_syscalls.py compiler build qemu [options]")
work = Path(tempfile.mkdtemp(prefix="syscalls-", dir=build))
base_env = {key: value for key, value in os.environ.items() if not key.startswith("PASLANG_GC")}
stress = dict(base_env, PASLANG_GCVERIFY="1", PASLANG_GCSTRESS="1", PASLANG_GCPOISON="1")
off = dict(base_env, PASLANG_GC="off")
cpu = str(min(os.sched_getaffinity(0)))


def run(command, env=base_env, timeout=120):
    process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, start_new_session=True)
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        output, _ = process.communicate()
        raise RuntimeError(f"timeout: {command}\n{output.decode(errors='replace')}")
    if process.returncode:
        raise RuntimeError(f"exit {process.returncode}: {command}\n{output.decode(errors='replace')}")
    return output


for target in ("amd64", "arm64"):
    core = build if target == "amd64" else build / "a64"
    runner = [] if target == "amd64" else qemu
    for level in ((40,) if inject_only else (0, 40)):
        for name in (("syscallretry", "syscallroots") if inject_only else
                     ("syscallprogress", "syscallroots", "syscallwait", "syscallretry", "forksignals")):
            binary = work / f"{name}-{target}-{level}"
            run([compiler, "-target", target, "-inline", str(level), "-Fu", str(core),
                 "-o", str(binary), f"testdata/{name}.paslang"])
            expected = Path(f"testdata/{name}.out").read_bytes()
            for environment in (stress, off):
                for affinity in (["taskset", "-c", cpu], []):
                    output = run([*affinity, *runner, str(binary)], environment)
                    if output != expected:
                        raise RuntimeError(f"unexpected output from {binary}: {output!r}")
    for name, script, marker in (
            ("syscallretry", "eintr", b"EINTR retry, short read and EOF passed"),
            ("syscallroots", "handoff", b"pending syscall handoff and genuine deadlock passed")):
        binary = work / f"{name}-{target}-40"
        commands = ["gdb", "-batch", "-nx", "-q", "-ex", "set debuginfod enabled off",
                    "-ex", "set pagination off", "-ex", "set language c", str(binary)]
        source = f"source scripts/inject_syscall_{script}.py"
        if target == "amd64":
            output = run(["taskset", "-c", cpu, *commands, "-ex", source], stress)
        else:
            # Short isolated path: AF_UNIX paths are limited to 108 bytes.
            with tempfile.TemporaryDirectory(prefix="pl-gdb-") as socket_dir:
                endpoint = Path(socket_dir) / "gdb.sock"
                process = subprocess.Popen(["taskset", "-c", cpu, *qemu, "-g", str(endpoint),
                                            str(binary)], env=stress, stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    deadline = time.monotonic() + 10
                    while not endpoint.exists():
                        if process.poll() is not None or time.monotonic() >= deadline:
                            raise RuntimeError("QEMU did not open its private GDB socket")
                        time.sleep(0.01)
                    output = run([*commands, "-ex", f"target remote {endpoint}", "-ex", source], stress)
                    guest_output, _ = process.communicate(timeout=10)
                    if process.returncode or guest_output != Path(f"testdata/{name}.out").read_bytes():
                        raise RuntimeError(f"{script} fixture failed: {guest_output!r}")
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.communicate()
        if marker not in output:
            raise RuntimeError(f"{script} fault injection failed: {output.decode(errors='replace')}")
    print(f"ok syscalls {target} (inline 0/40, single/all CPUs, GC stress/off, EINTR/short/EOF/handoff)", flush=True)
