# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""GDB, for scripts/check_gdbstub_threads.py (P582): a breakpoint at probe that is true at the last call alone.

Every call before it is a stop QEMU's stub reports, a breakpoint gdb removes, a step, and a breakpoint gdb
inserts again, while the guest's other thread makes threads. A removal that the stub answers with an error
leaves gdb with a breakpoint it believes inserted and never inserts again (gdb/breakpoint.c,
remove_breakpoint_1), and the guest runs past the last call to its end."""
import struct
import gdb

count = int(gdb.parse_and_eval('$probe_count'))
bp = gdb.Breakpoint('probe', internal=True)
bp.condition = '$x0 == %d' % count
gdb.execute('continue')
if bp.hit_count != 1:
    raise gdb.GdbError('the breakpoint at probe was lost: the guest went on past it')
made = int(gdb.parse_and_eval('(unsigned long)&made'))
made = struct.unpack('<Q', gdb.selected_inferior().read_memory(made, 8))[0]
gdb.write('the last of %d calls of probe stopped at its breakpoint, %d threads made meanwhile\n' % (count, made))
gdb.execute('kill')
