#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
#
# paslang is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# paslang is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with paslang.  If not, see <https://www.gnu.org/licenses/>.

"""The benchmark pairs in alternating rounds.

The median of a few runs of each program moves by up to ten per cent from
one batch to the next on a machine that runs anything else (a desktop, a
clock the governor scales), more than the gaps it has to judge. This runs
each pair in rounds, the two programs alternating which runs first, and
takes the ratio of each round (paslang's time over Go's): the median of
those ratios and the middle half of them. It uses the programs run.py has
built in build/bench, so `make bench` (or run.py) comes first.

  scripts/bench/rounds.py [-n rounds] [--json path] [--cpu native,base] [pair ...]

Each pair runs for every processor run.py built it for: NAME.pl (-cpu
native) and NAME.base.pl (-cpu base), both against the same Go binary,
which runs with GODEBUG=cpu.all=off against the base build (run.py says
why).

A pair passes when the median of its rounds' ratios is within its budget
in run.py (all below 1.00, Regla 12) and the middle half of them lies
below 1.00: paslang faster than Go in three rounds of four at least. The
exit status is 1 when a pair does not pass or does not print the same.
"""
import json
import os
import statistics
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run import BUDGET  # noqa: E402
OUT = os.path.join(ROOT, "build", "bench")
PAIRS = ["b1loop", "b2str", "b3spawn", "b4chan", "b5map", "b6smap", "b7narrow", "b8ptr",
         "b9hash", "b10rot", "b11tree"]


def timed(path, env=None):
    start = time.perf_counter()
    p = subprocess.run([path], capture_output=True, env=env)
    return time.perf_counter() - start, p.stdout


def main():
    # One line as each pair is measured, also into a file (make bench > log).
    sys.stdout.reconfigure(line_buffering=True)
    rounds = 40
    out = None
    pairs = []
    cpus = ["native", "base"]
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "-n":
            rounds = int(args[i + 1])
            i += 2
        elif args[i] == "--json":
            out = args[i + 1]
            i += 2
        elif args[i] == "--cpu":
            cpus = args[i + 1].split(",")
            i += 2
        else:
            pairs.append(args[i])
            i += 1
    if not pairs:
        pairs = PAIRS
    record = {"method": "%d rounds a pair, the two programs alternating which runs first; "
                        "the ratio of each round (paslang over Go), its median and quartiles" % rounds,
              "pairs": {}}
    bad = 0
    print("pair      cpu     ratio  budget  middle half      paslang s   go s  same output")
    for cpu, name in [(c, n) for c in cpus for n in pairs]:
        pl = os.path.join(OUT, name + ("" if cpu == "native" else "." + cpu) + ".pl")
        go = os.path.join(OUT, name + ".go.bin")
        if not (os.path.exists(pl) and os.path.exists(go)):
            print("%-9s %-6s not built: run make bench first" % (name, cpu))
            continue
        genv = dict(os.environ, GODEBUG="cpu.all=off") if cpu == "base" else None
        ratios, tp, tg, same = [], [], [], True
        for r in range(rounds):
            if r % 2 == 0:
                a, oa = timed(pl)
                b, ob = timed(go, genv)
            else:
                b, ob = timed(go, genv)
                a, oa = timed(pl)
            same = same and oa == ob
            tp.append(a)
            tg.append(b)
            ratios.append(a / b)
        q = statistics.quantiles(ratios, n=4)
        row = {"ratio_median": round(statistics.median(ratios), 3), "q1": round(q[0], 3),
               "q3": round(q[2], 3), "paslang_s": round(statistics.median(tp), 4),
               "go_s": round(statistics.median(tg), 4), "same_output": same}
        flag = ""
        if statistics.median(ratios) > BUDGET[name]:
            flag += "  OVER BUDGET"
        if q[2] >= 1.0:
            flag += "  NOT FASTER"
        bad += bool(flag) or not same
        row["budget"] = BUDGET[name]
        row["over"] = flag.strip()
        record["pairs"][name if cpu == "native" else name + "." + cpu] = row
        print("%-9s %-6s  %.3f  %6.2f  %.3f to %.3f   %.4f   %.4f  %s%s" % (
            name, cpu, row["ratio_median"], BUDGET[name], row["q1"], row["q3"], row["paslang_s"],
            row["go_s"], "yes" if same else "NO", flag))
    if out:
        with open(out, "w") as f:
            json.dump(record, f, indent=1)
        print("record written to " + out)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
