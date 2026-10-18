#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""What a sleeping routine costs (P342): testdata/sleepers run with 0
routines and with 20,000, all alive together behind its gate, and the
difference of the two peaks (scripts/bench/peak.py: VmHWM at the exit,
transparent huge pages off) a routine, held to --limit bytes. Under
QEMU (--qemu PATH) the guest's pages are QEMU's own, so the difference
is the guest's too. amd64's record and first stack are 1360 bytes,
arm64's 2048; Go's goroutine took 1690 on b17conc:sleep.

usage: check_routinemem.py BINARY --limit=BYTES [--qemu=PATH]
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "bench"))
import peak  # noqa: E402

N = 20000


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    limit = None
    qemu = []
    for a in sys.argv[1:]:
        if a.startswith("--limit="):
            limit = int(a[8:])
        elif a.startswith("--qemu="):
            qemu = [a[7:]]
    if len(args) != 1 or limit is None:
        raise SystemExit("usage: check_routinemem.py BINARY --limit=BYTES [--qemu=PATH]")
    devnull = os.open(os.devnull, os.O_WRONLY)
    kib = {}
    for n in (0, N):
        k, status = peak.peak_kib(qemu + [args[0], str(n)], stdout=devnull)
        if status != 0:
            raise SystemExit(f"check_routinemem: {args[0]} {n} ended with {status}")
        kib[n] = k
    per = (kib[N] - kib[0]) * 1024 // N
    if per > limit:
        raise SystemExit(f"check_routinemem: a sleeping routine takes {per} bytes, more than {limit} "
                         f"({kib[0]} KiB with none, {kib[N]} with {N})")
    print(f"check_routinemem: a sleeping routine takes {per} bytes, {limit} at most "
          f"({kib[0]} KiB with none, {kib[N]} KiB with {N})")


if __name__ == "__main__":
    main()
