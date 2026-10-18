# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Run inside GDB: inject one -EINTR without consuming a pipe byte.

This is deterministic fault injection, not a signal delivery test. Stop
before a read(8), substitute an invalid syscall, and replace its result
with -EINTR before rt_syscall's return/GC/handoff logic sees it. The
fixture must retry the real read, validate its short result and EOF.
GDB's documented Python API is used outside Breakpoint.stop callbacks:
https://sourceware.org/gdb/current/onlinedocs/gdb.html/Breakpoints-In-Python.html
"""
import gdb


arm = gdb.selected_inferior().architecture().name() == "aarch64"
number, length, result = ("x8", "x2", "x19") if arm else ("rax", "rdx", "rbx")
read_number = 63 if arm else 0
entry = gdb.Breakpoint("rt_syscall", internal=True)
entry.condition = f"${number} == {read_number} && ${length} == 8"
gdb.execute("continue" if arm else "run")
if entry.hit_count != 1:
    raise gdb.GdbError("read entry breakpoint was not reached")
gdb.execute(f"set ${number} = -1")
entry.delete()
label = ".asy_parent" if arm else ".sy_parent"
address = int(gdb.parse_and_eval(f"(void *) &'{label}'"))
returned = gdb.Breakpoint(f"*{address}", internal=True)
returned.thread = gdb.selected_thread().global_num
gdb.execute("continue")
if returned.hit_count != 1:
    raise gdb.GdbError("syscall return breakpoint was not reached")
gdb.execute(f"set ${result} = -4")
returned.delete()
gdb.write("injected EINTR before syscall return\n")
# Under QEMU the program's exit ends the run, not a breakpoint at rt_exit
# (P348): QEMU's user-mode stub stops only the thread that stops
# (gdbstub/user.c, gdb_handlesig), the others run on, and a last stop in
# rt_exit, in whichever thread reached it, made gdb 18.1 crash or lose
# QEMU as the process ended under it, 3 runs of 1800 with four busy loops
# on one processor; gdb keeps the exit's status in $_exitcode. A native
# gdb stops every thread at a breakpoint (all-stop), so amd64 stops there.
if arm:
    gdb.execute("continue")
    code = gdb.parse_and_eval("$_exitcode")
    if code.type.code == gdb.TYPE_CODE_VOID or int(code) != 0:
        raise gdb.GdbError(f"fixture did not reach successful exit: {code}")
else:
    exiting = gdb.Breakpoint("rt_exit", internal=True)
    gdb.execute("continue")
    code = int(gdb.parse_and_eval("$rdi"))
    if exiting.hit_count != 1 or code != 0:
        raise gdb.GdbError(f"fixture did not reach successful exit: {code}")
    exiting.delete()
    gdb.execute("detach")
gdb.write("EINTR retry, short read and EOF passed\n")
