# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""gdb's half of scripts/check_nopre.py (P363): at rt_gocall's call of
its Pascal routine, where the routine holds a runtime lock (G+184), the
guard is set to the stop's value, so the next stack check enters
rt_morestack, which finds the lock and returns by .ms_nopre; at that
return every word rt_morestack saved in the record must be 0 again.
Prints 'nopre: N stops, words left: [...]'."""

import gdb

gdb.execute("set pagination off")
gdb.execute("set confirm off")
arm = "aarch64" in gdb.execute("show architecture", to_string=True)
greg = "$x28" if arm else "$r14"
words = (72, 80, 88, 96, 104, 112, 128, 160, 168, 248) if arm else (72, 80, 88, 96, 104, 112, 120, 248)


def first(sym, parts, count):
    text = gdb.execute("x/%di '%s'" % (count, sym), to_string=True)
    for line in text.splitlines():
        if all(p in line for p in parts):
            return int(line.replace("=>", " ").split()[0].rstrip(":"), 16)
    raise gdb.GdbError("no %s in %s" % (parts, sym))


state = {"stops": 0, "left": None}


class Poison(gdb.Breakpoint):
    def stop(self):
        g = int(gdb.parse_and_eval(greg))
        gdb.execute("set *(long*)%d = 0xfffffffffffffade" % (g + 16))
        return False


class Back(gdb.Breakpoint):
    def stop(self):
        g = int(gdb.parse_and_eval(greg))
        state["stops"] += 1
        state["left"] = [o for o in words if int(gdb.parse_and_eval("*(long*)%d" % (g + o))) != 0]
        # one stop is the test; the rest runs at full speed (rt_gocall is
        # called thousands of times under the stress, each hit a round trip
        # through QEMU's stub on arm64)
        poison.enabled = False
        self.enabled = False
        return False


poison = Poison("*%d" % first("rt_gocall", ["blr", "x17"] if arm else ["call", "*%rax"], 200), internal=True)
Back("*%d" % first(".ms_nopre", ["ret"], 40), internal=True)
gdb.execute("continue" if arm else "run")
print("nopre: %d stops, words left: %s" % (state["stops"], state["left"]))
