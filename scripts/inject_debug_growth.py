# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""GDB: move the debugged G after saving a frame but before parking.

No product test switch: request growth through the actual stack guard,
then inspect the relocated frame before the ordinary debugger reads it.
"""
from pathlib import Path
import struct
import gdb

arm = gdb.selected_inferior().architecture().name() == 'aarch64'
gdb.write('debug injection architecture: ' + gdb.selected_inferior().architecture().name() + '\n')


def value(expression):
    return int(gdb.parse_and_eval(expression))


def word(address):
    return struct.unpack('<Q', gdb.selected_inferior().read_memory(address, 8))[0]


lines = Path('src/lib/pasdebug.paslang').read_text().splitlines()
first = next(i for i, text in enumerate(lines) if text.startswith('procedure PasDebugLine(')
             and i > 100)
unlock = next(i + 1 for i in range(first, len(lines)) if lines[i].strip() == 'Guard.Unlock;')
entry = gdb.Breakpoint('p_pasdebug_pasdebugline', internal=True)
entry.condition = f'{"$x0" if arm else "$rdi"} == {value("$debug_line")}'
gdb.execute('continue' if arm else 'run --debug-mode < ' + gdb.convenience_variable('debug_input').string())
if entry.hit_count != 1:
    raise gdb.GdbError('debug hook did not reach the forced-growth stop')
victim = value('$x28' if arm else '$r14')
entry.delete()
saved = gdb.Breakpoint(f'src/lib/pasdebug.paslang:{unlock}', internal=True)
saved.condition = f'{"$x28" if arm else "$r14"} == {victim}'
gdb.execute('continue')
if saved.hit_count != 1:
    raise gdb.GdbError('debug hook did not publish its frame before growth')
old_hi = word(victim + 8)
gdb.selected_inferior().write_memory(victim + 16, struct.pack('<Q', old_hi))
saved.delete()
inspection = gdb.Breakpoint('p_pasdebug_frames', internal=True)
gdb.execute('continue')
if inspection.hit_count != 1:
    raise gdb.GdbError('debugger did not inspect a stopped frame')
state = value('$x1' if arm else '$rsi')
lo, hi, offset = word(victim), word(victim + 8), word(state + 24)
if hi == old_hi or word(state + 32) != victim or not (0 < offset < hi - lo):
    raise gdb.GdbError(f'stale debug frame: old={old_hi:x}, new={hi:x}, distance={offset:x}')
bp = hi - offset
amount = struct.unpack('<q', gdb.selected_inferior().read_memory(bp - 8, 8))[0]
if amount != 26750:
    raise gdb.GdbError(f'relocated Currency frame was not preserved: {amount}')
inspection.delete()
gdb.execute('detach')
gdb.write('forced debugger stack growth and relocated Currency frame passed\n')
