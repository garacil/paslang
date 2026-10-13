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
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run import BUDGET, PAIRS, units, unit_name, once, go_env, pl_path  # noqa: E402
OUT = os.path.join(ROOT, "build", "bench")


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
    chosen = [(b, sec) for b, sec in units() if not pairs or b in pairs or unit_name(b, sec) in pairs]
    record = {"method": "%d rounds a pair, the two programs alternating which runs first; "
                        "the ratio of each round (paslang over Go), its median and quartiles" % rounds,
              "pairs": {}}
    bad = 0
    print("pair           cpu     ratio  budget  middle half      paslang s   go s  same output")
    for cpu, (prog, sec) in [(c, u) for c in cpus for u in chosen]:
        name, args = unit_name(prog, sec), (() if sec is None else (sec,))
        pl = pl_path(prog, cpu)
        go = os.path.join(OUT, prog + ".go.bin")
        if not (os.path.exists(pl) and os.path.exists(go)):
            print("%-14s %-6s not built: run make bench first" % (name, cpu))
            continue
        genv = go_env(cpu)
        ratios, tp, tg, same = [], [], [], True
        started = time.perf_counter()
        for r in range(rounds):
            # A unit whose rounds are long (a pair Go wins by a hundred
            # times) stops after 60 s once it has five.
            if r >= 5 and time.perf_counter() - started > 60:
                break
            if r % 2 == 0:
                a, sa, oa = once(pl, None, args)
                b, sb, ob = once(go, genv, args)
            else:
                b, sb, ob = once(go, genv, args)
                a, sa, oa = once(pl, None, args)
            same = same and oa == ob and sa == 0 and sb == 0
            if sa == "timeout" or sb == "timeout":
                tp.append(a)
                tg.append(b)
                ratios = [a / b] * 4
                break
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
        print("%-14s %-6s  %.3f  %6.2f  %.3f to %.3f   %.4f   %.4f  %s%s" % (
            name, cpu, row["ratio_median"], BUDGET[name], row["q1"], row["q3"], row["paslang_s"],
            row["go_s"], "yes" if same else "NO", flag))
    if out:
        with open(out, "w") as f:
            json.dump(record, f, indent=1)
        print("record written to " + out)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
