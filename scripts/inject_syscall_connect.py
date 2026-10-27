# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""GDB: an interrupted connect, a spurious wake and a silent nameserver.

P216, on testdata/connwait. The first connect runs and its answer becomes
-EINTR before PasConnect sees it: the kernel has the connection on its
way, and Go's netFD.connect (net/fd_unix.go) takes EINTR for that and
waits. Then the first wait for writing after one with a deadline (the
slow TcpConnectTo, after the fill's TcpConnectToMs) is pointed at
descriptor 100, a UDP socket the fixture keeps writable: the routine
wakes while its connection is still on its way, SO_ERROR says 0, and
getpeername must answer ENOTCONN so it waits again (Go issues 14548 and
19289). Last, with CONNWAIT_DNS=1, the resolver's socket is connected
to port 53 of the nameserver, which is read in the connect's sockaddr,
and the query's sendto on it becomes getpid (P224: a socket connected
to the nameserver, as Go's exchange dials it): nothing leaves the
machine, no answer comes, and TcpConnectToMs must end at its 600 ms
deadline with the resolution (net/dial.go: dialCtx's deadline bounds
resolveAddrList too); the nameserver is the first of /etc/resolv.conf,
so that file must name one.
The fixture exits 0 only when every connection had a peer at once and
carried its bytes and the name gave up in time.

Every stop is in PasConnect or AskWithin, which only connections and
the resolver run: a breakpoint on rt_syscall or rt_waitio stops every
routine's every call, and under QEMU's stub that is not a tool (P220). A line of
the source is found by its text, as inject_debug_growth.py finds one;
the call it makes, by disassembling forward from the line. Breakpoints
are set outside Breakpoint.stop:
https://sourceware.org/gdb/current/onlinedocs/gdb.html/Breakpoints-In-Python.html
"""
from pathlib import Path
import gdb


arm = gdb.selected_inferior().architecture().name() == "aarch64"
if arm:
    number, answer, first, connaddr = "x8", "x0", "x0", "x1"
    getpid = 172
else:
    number, answer, first, connaddr = "rax", "rax", "rdi", "rsi"
    getpid = 39


def line_of(path, header, statement, heads=2):
    """The line of statement in the body that follows header, which the
    unit declares and defines (heads 2) or defines alone (1)."""
    lines = Path(path).read_text().splitlines()
    start = [i for i, text in enumerate(lines) if text == header]
    if len(start) != heads:
        raise gdb.GdbError(f"{header} is not written {heads} times in {path}")
    for i in range(start[-1], len(lines)):
        if lines[i].strip() == statement:
            return f"{path}:{i + 1}"
        if lines[i] == "end;":
            break
    raise gdb.GdbError(f"{statement} is not in {header}")


def stop_at(location, what):
    """Run to location once; the breakpoint is gone afterwards."""
    point = gdb.Breakpoint(location, internal=True)
    gdb.execute("continue")
    if gdb.selected_inferior().pid == 0:
        raise gdb.GdbError(f"fixture exited with {int(gdb.parse_and_eval('$_exitcode'))} before {what}")
    if point.hit_count != 1:
        raise gdb.GdbError(f"{what} was not reached")
    point.delete()


def call_ahead(routine):
    """The first call of routine at or after this pc: its address and the next."""
    pc = int(gdb.parse_and_eval("$pc"))
    for insn in gdb.selected_frame().architecture().disassemble(pc, count=64):
        if f"<{routine}>" in insn["asm"]:
            return insn["addr"], insn["addr"] + insn["length"]
    raise gdb.GdbError(f"no call of {routine} after {pc:#x}")


def value(register):
    return int(gdb.parse_and_eval(f"(long) ${register}"))


connects = "function PasConnect(Fd: Integer; Sa: Pointer; Size, Deadline: Integer): Integer;"
routines = "src/lib/pasroutines.paslang"
connect_line = line_of(routines, connects, "Result := Syscall(nconnect, Fd, Sa, Size);")
timed_line = line_of(routines, connects, "w := WaitMs(Fd, 4, left div 1000000 + 1);")
wait_line = line_of(routines, connects, "w := WaitIo(Fd, 4);")
peer_line = line_of(routines, connects, "if Syscall(ngetpeername, Fd, @peer, @plen) = 0 then")
asks = "function AskWithin(const Host, Server: string; Port, Deadline: Integer): string;"
ask_connect_line = line_of("src/lib/pasnet.paslang", asks,
                           "if (not FillSockaddr(Server, Port, sa, size)) or (Syscall(SnConnect, fd, @sa, size) < 0) then", 1)
send_line = line_of("src/lib/pasnet.paslang", asks,
                    "n := Syscall(SnSendto, fd, Pointer(q), Length(q), 0, 0, 0);", 1)

# The first connect: main's TcpConnectTo, with no other connect running.
point = gdb.Breakpoint(connect_line, internal=True)
gdb.execute("continue" if arm else "run")
if point.hit_count != 1:
    raise gdb.GdbError("the first connect was not reached")
point.delete()
_, back = call_ahead("rt_syscall")
stop_at(f"*{back}", "the first connect's answer")
if value(answer) not in (0, -115):
    raise gdb.GdbError(f"the first connect answered {value(answer)}")
gdb.execute(f"set ${answer} = -4")
gdb.write("injected EINTR into the first connect\n")

# A wait with a deadline is the first fill; the next wait without one
# is the slow TcpConnectTo while the queue is full.
stop_at(timed_line, "a connect's wait with a deadline")
stop_at(wait_line, "the slow connect's wait")
call, _ = call_ahead("rt_waitio")
stop_at(f"*{call}", "the slow connect's call of rt_waitio")
gdb.execute(f"set ${first} = 100")
gdb.write("pointed the slow connect's wait at an always writable socket\n")

# Only the slow connect is connecting: the next getpeername is its own.
stop_at(peer_line, "the check of the wake with getpeername")
_, back = call_ahead("rt_syscall")
stop_at(f"*{back}", "getpeername's answer")
if value(answer) != -107:
    raise gdb.GdbError(f"getpeername after the spurious wake answered {value(answer)}, not ENOTCONN")

# The resolver connects its socket to the nameserver (P224), which sends
# nothing: network byte order, port 53 is bytes 0 and 53 at offset 2 of
# the connect's sockaddr. The fixture sends no datagram of its own: the
# next sendto is the resolver's query on that socket.
stop_at(ask_connect_line, "the resolver's connect (does /etc/resolv.conf name an IPv4 nameserver?)")
call, _ = call_ahead("rt_syscall")
stop_at(f"*{call}", "the connect's call of rt_syscall")
port = gdb.selected_inferior().read_memory(value(connaddr) + 2, 2).tobytes()
if port != b"\x00\x35":
    raise gdb.GdbError(f"the resolver connected to port {int.from_bytes(port, 'big')}, not 53")
stop_at(send_line, "the name's query")
call, _ = call_ahead("rt_syscall")
stop_at(f"*{call}", "the query's call of rt_syscall")
gdb.execute(f"set ${number} = {getpid}")
gdb.write("the name's query became getpid\n")

# A second query would mean the resolver asked again past the deadline.
again = gdb.Breakpoint(send_line, internal=True)
# Under QEMU the program's exit ends the run, not a breakpoint at rt_exit
# (P348): QEMU's user-mode stub stops only the thread that stops
# (gdbstub/user.c, gdb_handlesig), the others run on, and a last stop in
# rt_exit, in whichever thread reached it, made gdb 18.1 crash or lose
# QEMU as the process ended under it, 3 runs of 1800 with four busy loops
# on one processor; gdb keeps the exit's status in $_exitcode. A native
# gdb stops every thread at a breakpoint (all-stop), so amd64 stops there.
if arm:
    gdb.execute("continue")
    if gdb.selected_inferior().pid != 0 or again.hit_count != 0:
        raise gdb.GdbError("the resolver asked again after its deadline")
    code = gdb.parse_and_eval("$_exitcode")
    if code.type.code == gdb.TYPE_CODE_VOID or int(code) != 0:
        raise gdb.GdbError(f"fixture did not reach successful exit: {code}")
else:
    exiting = gdb.Breakpoint("rt_exit", internal=True)
    gdb.execute("continue")
    if gdb.selected_inferior().pid == 0:
        # Halt leaves without rt_exit; gdb keeps the status in $_exitcode.
        raise gdb.GdbError(f"fixture exited with {int(gdb.parse_and_eval('$_exitcode'))}")
    code = int(gdb.parse_and_eval("$rdi"))
    if again.hit_count != 0:
        raise gdb.GdbError("the resolver asked again after its deadline")
    if exiting.hit_count != 1 or code != 0:
        raise gdb.GdbError(f"fixture did not reach successful exit: {code}")
    exiting.delete()
    again.delete()
    gdb.execute("detach")
gdb.write("connect EINTR, spurious wake and name deadline passed\n")
