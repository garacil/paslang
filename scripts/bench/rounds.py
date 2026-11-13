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

  scripts/bench/rounds.py --reference go,rust --pairs b1loop,b6smap --go-native-level v3

Selected references share run.py's driver, retain the quartile requirement
and reuse only executables whose source, tool, flags and identity match.
Use the same selectors/CPU settings as the selected run.py build. The
default command retains the legacy Go-suite behavior documented below.

Each pair runs for every processor run.py built it for: NAME.pl (-cpu
native) and NAME.base.pl (-cpu base), both against the same Go binary,
which uses a source-bound capability probe and reviewed CPU controls for
the base build, refusing unsupported REP or optional-ISA states
(reference_policy.py).

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
import run as bench  # noqa: E402
from run import BUDGET, PAIRS, LAST_ONCE, units, unit_name, once, go_env, pl_path, json_values, go_artifact_evidence, fail_legacy_record  # noqa: E402
OUT = os.path.join(ROOT, "build", "bench")


def main():
    if sys.argv[1:] in (["--help"], ["-h"]):
        print(__doc__)
        return 0
    if any(option.split("=", 1)[0] in
           ("--reference", "--pairs", "--memory-runs", "--go-native-level", "--no-build", "--timeout",
            "--rust-target", "--rust-sysroot", "--rust-provider", "--rust-capability-proof")
           for option in sys.argv[1:]):
        from run_refs import main as reference_main
        return reference_main(sys.argv[1:], rounds_only=True)
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
    if rounds < 1 or not cpus or set(cpus) - {"native", "base"}:
        sys.exit("rounds.py: positive rounds and --cpu native,base are required")
    known = set(PAIRS) | {unit_name(b, sec) for b, sec in units()}
    unknown = set(pairs) - known
    if unknown:
        sys.exit("rounds.py: unknown pairs: " + ", ".join(sorted(unknown)))
    record = {"method": "%d rounds a pair, the two programs alternating which runs first; "
                        "the ratio of each round (paslang over Go), its median and quartiles" % rounds,
              "pairs": {}}
    bad = 0
    if "base" in cpus:
        go_env("base")
        record["go_capabilities"] = bench.GO_CAPABILITIES
    print("pair           cpu     ratio  budget  middle half      paslang s   go s  same output")
    for cpu, (prog, sec) in [(c, u) for c in cpus for u in chosen]:
        name, args = unit_name(prog, sec), (() if sec is None else (sec,))
        pl = pl_path(prog, cpu)
        go = os.path.join(OUT, prog + ".go.bin")
        if not (os.path.exists(pl) and os.path.exists(go)):
            print("%-14s %-6s not built: run make bench first" % (name, cpu))
            bad += 1
            record["pairs"][name if cpu == "native" else name + "." + cpu] = {
                "ratio_median": float("inf"), "q1": float("inf"), "q3": float("inf"),
                "paslang_s": float("inf"), "go_s": float("inf"), "same_output": False,
                "budget": BUDGET[name], "over": "NOT BUILT", "rounds": [],
                "requested_rounds": rounds, "completed_rounds": 0}
            continue
        genv = go_env(cpu)
        try:
            go_artifact_evidence(go, cpu, record)
        except ValueError as error:
            fail_legacy_record(record, out, error)
        ratios, tp, tg, same = [], [], [], True
        round_rows, first_a, first_b = [], None, None
        for r in range(rounds):
            if r % 2 == 0:
                a, sa, oa = once(pl, None, args)
                b, sb, ob = once(go, genv, args)
            else:
                b, sb, ob = once(go, genv, args)
                a, sa, oa = once(pl, None, args)
            same = same and oa == ob and sa == 0 and sb == 0
            errors = []
            if oa != ob:
                errors.append("complete stdout differs")
            if sa != 0 or sb != 0:
                errors.append("nonzero status or timeout")
            if LAST_ONCE[(pl, args)]["stderr"] or LAST_ONCE[(go, args)]["stderr"]:
                errors.append("unexpected stderr")
            if first_a is not None and oa != first_a:
                errors.append("paslang stdout changed between rounds")
            if first_b is not None and ob != first_b:
                errors.append("Go stdout changed between rounds")
            first_a = oa if first_a is None else first_a
            first_b = ob if first_b is None else first_b
            same = same and not errors
            round_rows.append({"round": r + 1, "first": "paslang" if r % 2 == 0 else "go",
                               "paslang": dict(LAST_ONCE[(pl, args)]),
                               "go": dict(LAST_ONCE[(go, args)]), "errors": errors})
            if sa == "timeout" or sb == "timeout":
                tp.append(a)
                tg.append(b)
                ratios.append(float("inf"))
                break
            tp.append(a)
            tg.append(b)
            ratios.append(a / b)
        same = same and len(round_rows) == rounds
        q = statistics.quantiles(ratios, n=4) if len(ratios) > 1 else [ratios[0]] * 3
        row = {"ratio_median": round(statistics.median(ratios), 3), "q1": round(q[0], 3),
               "q3": round(q[2], 3), "paslang_s": round(statistics.median(tp), 4),
               "go_s": round(statistics.median(tg), 4), "same_output": same,
               "requested_rounds": rounds, "completed_rounds": len(round_rows),
               "rounds": round_rows}
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
            json.dump(json_values(record), f, indent=1, allow_nan=False)
        print("record written to " + out)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    sys.exit(main())
