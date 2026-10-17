#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""An exec and a new thread do not race (P333), read in the runtime
paslangc writes into a program, amd64 or with --arm arm64: rt_newm
takes the exec lock for reading before its clone (rt_execrl), tries the
clone again on EAGAIN (-11) and gives the lock back once the thread is
made; rt_syscall's execve of the process takes the lock for writing
(rt_execwl) and gives it back after (rt_execwu), on its two paths.
"""

import re
import sys


def body(lines, name):
    out, on = [], False
    for l in lines:
        if l == name + ":":
            on = True
            continue
        if on and re.match(r"^[A-Za-z_][A-Za-z0-9_.]*:$", l) and not l.startswith("."):
            break
        if on:
            out.append(l)
    return out


def main():
    arm = "--arm" in sys.argv[1:]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        raise SystemExit("usage: check_execlock.py file.s [--arm]")
    lines = open(args[0]).read().splitlines()
    nm = "\n".join(body(lines, "rt_newm"))
    sy = "\n".join(body(lines, "rt_syscall"))
    bad = []
    if arm:
        want_nm = [r"bl rt_execrl\n(.*\n)*?.*mov x8, #220", r"cmn x0, #11", r"mov x8, #101", r"ldaxr x17, \[x16\]\n  sub x17, x17, #1"]
        want_sy = [r"cmp x8, #221\n  b\.eq \.asy_exec", r"\.asy_exec:\n  bl rt_execwl\n  svc #0\n  bl rt_execwu",
                   r"\.asy_rawexec:\n(.*\n)*?  bl rt_execwl\n  svc #0\n  bl rt_execwu"]
    else:
        # the clone's and the nanosleep's numbers by a movl of 32 bits (P321)
        want_nm = [r"call rt_execrl\n(.*\n)*?  movl \$56, %eax", r"cmpq \$-11, %rax", r"movl \$35, %eax", r"lock decq rt_execlk\(%rip\)"]
        want_sy = [r"cmpq \$59, %rax\n  je \.sy_exec", r"\.sy_exec:\n  call rt_execwl\n  syscall\n  call rt_execwu",
                   r"\.sy_raw_exec:\n  call rt_execwl\n  syscall\n  call rt_execwu"]
    for w in want_nm:
        if not re.search(w, nm):
            bad.append(f"rt_newm has no {w}")
    for w in want_sy:
        if not re.search(w, sy):
            bad.append(f"rt_syscall has no {w}")
    if bad:
        print("\n".join(bad))
        raise SystemExit(f"check_execlock: {len(bad)} forms missing in {args[0]}")
    print(f"check_execlock: rt_newm under the exec lock with clone again on EAGAIN, execve under it, in {args[0]}")


if __name__ == "__main__":
    main()
