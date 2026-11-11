# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""GDB checks the real call-site breakpoints and next, without debugger hooks."""
import gdb


def total():
    # Ordinary optimized builds expose globals as ELF symbols; -debug
    # supplies the separate source-variable tables for the console.
    address = int(gdb.parse_and_eval('(unsigned long)&v_total'))
    return int.from_bytes(gdb.selected_inferior().read_memory(address, 8), 'little')


arm = gdb.selected_inferior().architecture().name() == 'aarch64'
gdb.execute('set language c')
gdb.execute('set confirm off')
gdb.execute('handle SIGURG nostop noprint pass')
for line in (17, 18, 19):
    gdb.Breakpoint(f'inlinebreak.paslang:{line}')
gdb.execute('continue' if arm else 'run')
assert gdb.find_pc_line(int(gdb.parse_and_eval('$pc'))).line == 17
assert total() == 0
gdb.execute('next')
assert total() == 5
# The second breakpoint is before the load, including when its first
# instruction now names the inlined Load's source line. No extra call
# or debugger hook is needed to preserve the call-site breakpoint.
assert gdb.breakpoints()[1].hit_count == 1
for _ in range(4):
    if gdb.find_pc_line(int(gdb.parse_and_eval('$pc'))).line == 19:
        break
    gdb.execute('next')
else:
    raise gdb.GdbError('next did not leave the inlined call')
assert total() == 13
assert gdb.breakpoints()[2].hit_count == 1
gdb.write('inline-place: call-site breaks and next passed\n')
gdb.execute('kill')
