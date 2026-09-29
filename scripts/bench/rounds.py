#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacil@tucall.com>
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

  scripts/bench/rounds.py [-n rounds] [--json path] [pair ...]
"""
import json
import os
import statistics
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "build", "bench")
PAIRS = ["b1loop", "b2str", "b3spawn", "b4chan", "b5map", "b6smap", "b7narrow", "b8ptr",
         "b9hash", "b10rot", "b11tree"]


def timed(path):
    start = time.perf_counter()
    p = subprocess.run([path], capture_output=True)
    return time.perf_counter() - start, p.stdout


def main():
    rounds = 40
    out = None
    pairs = []
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "-n":
            rounds = int(args[i + 1])
            i += 2
        elif args[i] == "--json":
            out = args[i + 1]
            i += 2
        else:
            pairs.append(args[i])
            i += 1
    if not pairs:
        pairs = PAIRS
    record = {"method": "%d rounds a pair, the two programs alternating which runs first; "
                        "the ratio of each round (paslang over Go), its median and quartiles" % rounds,
              "pairs": {}}
    print("pair       ratio  middle half      paslang s   go s  same output")
    for name in pairs:
        pl = os.path.join(OUT, name + ".pl")
        go = os.path.join(OUT, name + ".go.bin")
        if not (os.path.exists(pl) and os.path.exists(go)):
            print("%-9s not built: run make bench first" % name)
            continue
        ratios, tp, tg, same = [], [], [], True
        for r in range(rounds):
            if r % 2 == 0:
                a, oa = timed(pl)
                b, ob = timed(go)
            else:
                b, ob = timed(go)
                a, oa = timed(pl)
            same = same and oa == ob
            tp.append(a)
            tg.append(b)
            ratios.append(a / b)
        q = statistics.quantiles(ratios, n=4)
        row = {"ratio_median": round(statistics.median(ratios), 3), "q1": round(q[0], 3),
               "q3": round(q[2], 3), "paslang_s": round(statistics.median(tp), 4),
               "go_s": round(statistics.median(tg), 4), "same_output": same}
        record["pairs"][name] = row
        print("%-9s  %.3f  %.3f to %.3f   %.4f   %.4f  %s" % (
            name, row["ratio_median"], row["q1"], row["q3"], row["paslang_s"], row["go_s"],
            "yes" if same else "NO"))
    if out:
        with open(out, "w") as f:
            json.dump(record, f, indent=1)
        print("record written to " + out)


if __name__ == "__main__":
    main()
