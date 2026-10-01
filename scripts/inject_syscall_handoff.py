# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""GDB: force the last-sleeper check during a syscall P handoff.

Stop before a reused M is published, step only the publishing thread,
and exercise the real leaf detector with a last-sleeper snapshot. Pending
capacity must suppress deadlock; removing that capacity must still detect
deadlock. Restore the entire snapshot before letting the fixture finish.
No runtime branch or test-mode switch is added to the product.
"""
import gdb

arm = gdb.selected_inferior().architecture().name() == "aarch64"
pc, sp = ("pc", "sp") if arm else ("rip", "rsp")
replacement = "x23" if arm else "r12"
fresh = "x24" if arm else "rbp"


def value(expression):
    return int(gdb.parse_and_eval(expression))


def word(name):
    return value("*(unsigned long long*)&" + name)


def setword(name, number):
    gdb.execute(f"set *(unsigned long long*)&{name} = {number}")


def setregister(name, number):
    # Changing SP/FP invalidates unwinding. Always write the hardware
    # frame, never a cached caller's saved register on the runtime stack.
    gdb.invalidate_cached_frames()
    gdb.newest_frame().select()
    gdb.execute(f"set ${name} = {number}")


entry = gdb.Breakpoint(".rk_attach", internal=True)
entry.condition = f"${fresh} == 0"
gdb.execute("continue" if arm else "run")
if entry.hit_count != 1:
    raise gdb.GdbError("reused-M handoff was not reached")
entry.delete()
if not arm:
    gdb.execute("set scheduler-locking on")
# Advance through ownership transfer and publication, not through unlock.
for _ in range(40):
    instruction = gdb.selected_frame().architecture().disassemble(value("$" + pc), count=1)[0]
    if "rt_unlock" in instruction["asm"]:
        break
    gdb.execute("stepi", to_string=True)
else:
    raise gdb.GdbError("handoff publication did not reach unlock")
pending = word("rt_nspinning")
mark = value(f"*(long*)(${replacement} + 56)")
if pending < 1 or mark != 1:
    raise gdb.GdbError(f"published replacement is not counted: count={pending}, mark={mark}")

names = ("rt_msleep", "rt_nspinning", "rt_sleeph", "rt_npollwait", "rt_maindone", "rt_nlive")
snapshot = {name: word(name) for name in names}
register_names = ([f"x{index}" for index in range(31)] + ["sp", "pc", "cpsr"] if arm else
                  ["rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp",
                   *[f"r{index}" for index in range(8, 16)], "rip", "eflags"])
registers = {name: value("$" + name) for name in register_names}
resume = registers[pc]
saved_stack = None
if not arm:
    saved_stack = bytes(gdb.selected_inferior().read_memory(registers[sp] - 8, 8))

for has_capacity in (True, False):
    setword("rt_msleep", (snapshot["rt_msleep"] & ~0xffffffff) | (word("rt_mstarted") - 1))
    setword("rt_nspinning", pending if has_capacity else 0)
    for name in ("rt_sleeph", "rt_npollwait", "rt_maindone"):
        setword(name, 0)
    setword("rt_nlive", 2)
    if arm:
        setregister("x30", resume)
    else:
        setregister("rsp", registers[sp] - 8)
        gdb.execute(f"set *(unsigned long long*)$rsp = {resume}")
    setregister(pc, value("(unsigned long)&rt_msleepin"))
    returning = gdb.Breakpoint(f"*{resume}", internal=True)
    dying = gdb.Breakpoint("rt_diedeadlock", internal=True)
    returning.thread = dying.thread = gdb.selected_thread().global_num
    gdb.execute("continue")
    expected = returning if has_capacity else dying
    if expected.hit_count != 1:
        raise gdb.GdbError("detector did not distinguish pending capacity from deadlock")
    returning.delete()
    dying.delete()
    for name, number in registers.items():
        setregister(name, number)

for name, number in snapshot.items():
    setword(name, number)
if saved_stack is not None:
    gdb.selected_inferior().write_memory(registers[sp] - 8, saved_stack)
if not arm:
    gdb.execute("set scheduler-locking off")
exiting = gdb.Breakpoint("rt_exit", internal=True)
gdb.execute("continue")
code = value("$x0" if arm else "$rdi")
if exiting.hit_count != 1 or code != 0:
    raise gdb.GdbError(f"handoff fixture did not finish successfully: {code}")
exiting.delete()
gdb.execute("detach")
gdb.write("pending syscall handoff and genuine deadlock passed\n")
