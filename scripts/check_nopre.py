#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""A stop asked for while a routine holds a runtime lock leaves no saved
register in its record (P363). testdata/nopre allocates under the
collector's stress, so its heap's slow paths run through rt_gocall with
the lock count up; scripts/inject_nopre.py, under gdb (QEMU's stub on
arm64, as scripts/check_syscalls.py does), sets the guard there to the
stop's value, rt_morestack returns by .ms_nopre, and every word it saved
in the record must be 0 at that return. The program's output must not
change.

usage: check_nopre.py compiler build qemu
"""

import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

compiler, build = sys.argv[1], Path(sys.argv[2])
qemu = sys.argv[3:]
if not qemu:
    raise SystemExit(__doc__)
expected = Path("testdata/nopre.out").read_bytes()
env = dict(os.environ, PASLANG_GCSTRESS="1", PASLANG_ASYNCPREEMPTOFF="1")
gdb = ["gdb", "-batch", "-nx", "-q", "-ex", "set debuginfod enabled off",
       "-ex", "set pagination off", "-ex", "set language c"]
for target in ("amd64", "arm64"):
    binary = build / f"nopre-{target}"
    subprocess.run([compiler, "-target", target, "-Fu", str(build if target == "amd64" else build / "a64"),
                    "-o", str(binary), "testdata/nopre.paslang"], check=True, timeout=300)
    if target == "amd64":
        r = subprocess.run([*gdb, str(binary), "-ex", "source scripts/inject_nopre.py"],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=600)
        out, guest = r.stdout, r.stdout
    else:
        with tempfile.TemporaryDirectory(prefix="pl-gdb-") as socket_dir:
            endpoint = Path(socket_dir) / "gdb.sock"
            process = subprocess.Popen([*qemu, "-g", str(endpoint), str(binary)], env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            try:
                deadline = time.monotonic() + 10
                while not endpoint.exists():
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise SystemExit("check_nopre: QEMU did not open its GDB socket")
                    time.sleep(0.01)
                r = subprocess.run([*gdb, str(binary), "-ex", f"target remote {endpoint}",
                                    "-ex", "source scripts/inject_nopre.py"],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=600)
                out = r.stdout
                guest, _ = process.communicate(timeout=60)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
    text = out.decode(errors="replace")
    line = next((l for l in text.splitlines() if l.startswith("nopre: ")), None)
    if line is None or line.startswith("nopre: 0 stops") or not line.endswith("words left: []"):
        raise SystemExit(f"check_nopre {target}: {line or text[-2000:]}")
    if expected not in guest:
        raise SystemExit(f"check_nopre {target}: the program said {guest[-400:]!r}")
    print(f"ok nopre {target} ({line[len('nopre: '):]})", flush=True)
