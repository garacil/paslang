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

"""Write the Markdown report of a benchmark record (run.py --json):
the machine, the toolchain, the method, the table of every pair on each
processor with all its rounds, and the memory; then, when their records
are given, the forty rounds of rounds.py, the compiler against go build
(build.py) and the servers (servers.py). The notes on each pair are
added by hand below the tables, from a reading of the code, never from
memory.

    scripts/bench/report.py docs/bench/2026-10-13b.json \
        [--rounds docs/bench/rounds-2026-10-13b.json] \
        [--build docs/bench/build-2026-10-13.json] \
        [--servers docs/bench/servers-2026-10-13.json] > docs/BENCH-2026-10-13.md
"""
import json
import statistics
import sys


def machine(w, r, path):
    m = r["machine"]
    cpu = m["cpu"]
    t = m["toolchain"]
    w(f"# Benchmark against Go, {m['date'][:10]}")
    w("")
    w(f"Record: `{path}` (every run, every number, written by `scripts/bench/run.py --json`).")
    w("Go is the reference for what is good, and paslang has to be faster and")
    w("use less memory than Go in everything Go also does (REGLAS_DE_ORO, Reglas 3")
    w("and 12); the numbers come from a run, never from memory (Regla 2).")
    w("")
    w("## The machine")
    w("")
    w("| | |")
    w("|---|---|")
    w(f"| Processor | {cpu['model']}, {cpu['logical_cpus']} logical CPUs |")
    w(f"| Caches | L1d {cpu['l1d']}, L2 {cpu['l2']}, L3 {cpu['l3']} |")
    w(f"| Clock | up to {cpu['max_mhz']} MHz, governor `{cpu['governor']}`, boost {cpu['boost'] or '?'} |")
    w(f"| Extensions -cpu native uses | {', '.join(cpu['features_used'])} |")
    w(f"| Memory | {m['memory'].get('MemTotal', '?')} total, {m['memory'].get('MemAvailable', '?')} available |")
    w(f"| System | {m['os']}, kernel {m['kernel']}, host `{m['hostname']}` |")
    w(f"| Load average before, after | {m['load_before'].split()[0]}, {m.get('load_after', '?').split()[0]} (1 min) |")
    w("")
    w("## The toolchain")
    w("")
    w("| | |")
    w("|---|---|")
    w(f"| paslangc | {' '.join(t['paslangc']).strip() if t['paslangc'] else '?'} |")
    w(f"| Go | {t['go']} |")
    w(f"| Assembler, linker | {(t['as'] or ['?'])[0]}; {(t['ld'] or ['?'])[0]} |")
    w("")


def method(w, r):
    w("## The method")
    w("")
    w("Each pair is one `.paslang` and one `.go` with the same work and the same output")
    w("(`scripts/bench/`); a program that measures several things takes the name of one")
    w("as its argument, and each `NAME:SECTION` is a pair of its own. The paslang side is")
    w(f"built for each processor in {', '.join('`-cpu ' + c + '`' for c in r['cpus'])}; the native build runs")
    w("against Go as it ships (its libraries choose the processor's extensions as they")
    w("run), the base build against the same Go binary with `GODEBUG=cpu.all=off`, so both")
    w(f"run on the base processor. The two programs run in {r['runs_per_program']} rounds, alternating which")
    w("runs first; the time ratio is the median of the rounds' ratios, paslang's time over")
    w("Go's: below 1 paslang is faster. The memory is the peak resident set (`VmHWM`) as")
    w("each program exits, read by `scripts/bench/peak.py` from a traced run with huge pages")
    w("off, the median of five such runs apart from the timed ones. Every budget is below")
    w("1.00: a pair Go wins or ties fails `make bench` and has its hito; a pair that wins")
    w("keeps what it won, rounded up. A run past 60 s is killed and its pair fails.")
    w("")


def results(w, r):
    w("## Results")
    w("")
    w("| Pair | cpu | Go s | paslang s | time ratio | budget | Go MB | paslang MB | memory ratio | same output |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for p in r["pairs"]:
        g, l = p["go"], p["paslang"]
        flag = f" **{p['over']}**" if p.get("over") else ""
        if "timeout" in (g["status"], l["status"]):
            # Killed after 60 s: no time to divide, no memory measured.
            w(f"| {p['pair']} | {p['cpu']} | {g['median_s']:.3f} | did not end | -{flag} | {p['budget']:.2f} | - | - | - | "
              f"NO: {l['output'] if l['status'] == 'timeout' else g['output']} |")
            continue
        w(f"| {p['pair']} | {p['cpu']} | {g['median_s']:.3f} | {l['median_s']:.3f} | {p['ratio_time']:.2f}{flag} | "
          f"{p['budget']:.2f} | {g['peak_rss_mb']:.1f} | {l['peak_rss_mb']:.1f} | {p['ratio_mem']:.2f} | "
          f"{'yes' if p['same_output'] else 'NO: ' + str(l['output'])} |")
    w("")
    w("Every round, in seconds, sorted:")
    w("")
    w("| Pair | cpu | Go | paslang |")
    w("|---|---|---|---|")
    for p in r["pairs"]:
        gw = ", ".join("did not end" if x == float("inf") else f"{x:.3f}" for x in p["go"]["walls_s"])
        lw = ", ".join("did not end" if x == float("inf") else f"{x:.3f}" for x in p["paslang"]["walls_s"])
        w(f"| {p['pair']} | {p['cpu']} | {gw} | {lw} |")
    w("")
    if r.get("checkptr"):
        w("`-checkptr` (P104), its time as a multiple of the plain build's:")
        w("")
        for c in r["checkptr"]:
            w(f"- {json.dumps(c)}")
        w("")


def rounds(w, path):
    r = json.load(open(path))
    w("## Forty alternating rounds")
    w("")
    w(f"Record: `{path}` (`scripts/bench/rounds.py`): {r['method']}. A pair fails when")
    w("its median passes the budget or the middle half of its rounds reaches 1.00.")
    w("")
    w("| Pair | cpu | round ratio, median | middle half | paslang s | Go s | budget | same output |")
    w("|---|---|---|---|---|---|---|---|")
    for name, row in r["pairs"].items():
        pair, _, cpu = name.partition(".")
        flag = f" **{row['over']}**" if row.get("over") else ""
        med = "did not end" if row["ratio_median"] == float("inf") else f"{row['ratio_median']:.3f}"
        half = "-" if row["q1"] == float("inf") else f"{row['q1']:.3f} to {row['q3']:.3f}"
        pl = "-" if row["paslang_s"] == float("inf") else f"{row['paslang_s']:.4f}"
        w(f"| {pair} | {cpu or 'native'} | {med}{flag} | {half} | {pl} | {row['go_s']:.4f} | {row['budget']:.2f} | "
          f"{'yes' if row['same_output'] else 'NO'} |")
    w("")


def build(w, path):
    b = json.load(open(path))
    w("## The compiler against go build")
    w("")
    w(f"Record: `{path}` (`scripts/bench/build.py`): one generated program of {b['functions']} functions")
    w("built by both compilers to a linked executable, in alternating rounds, Go's standard")
    w("library in its cache and the program recompiled every round.")
    w("")
    w("| Rounds | paslangc s, median | go build s, median | ratio, median | middle half | budget | same output |")
    w("|---|---|---|---|---|---|---|")
    flag = f" **{b['over']}**" if b.get("over") else ""
    w(f"| {b['rounds']} | {statistics.median(b['paslang_s']):.3f} | {statistics.median(b['go_s']):.3f} | "
      f"{b['ratio_median']:.3f}{flag} | {b['q1']:.3f} to {b['q3']:.3f} | {b['budget']:.2f} | "
      f"{'yes' if b['same_output'] else 'NO'} |")
    w("")


def servers(w, path):
    s = json.load(open(path))
    w("## The servers")
    w("")
    w(f"Record: `{path}` (`scripts/bench/servers.py`, {s['paslangc']}): each server and its Go twin")
    w(f"run as `-selftest n`, {s['runs']} alternating runs; the conntrack wait was {s.get('conntrack_wait_s', '?')} s.")
    w("")
    w("| Pair | cpu | n | Go s | paslang s | time ratio | budget | Go MB | paslang MB | memory ratio | same output |")
    w("|---|---|---|---|---|---|---|---|---|---|---|")
    for p in s["pairs"]:
        flag = f" **{p['over']}**" if p.get("over") else ""
        w(f"| {p['pair']} | {p['cpu']} | {p['n']} | {statistics.median(p['go_s']):.3f} | "
          f"{statistics.median(p['paslang_s']):.3f} | {p['ratio']:.2f}{flag} | {p['budget']:.2f} | "
          f"{statistics.median(p['go_mb']):.1f} | {statistics.median(p['paslang_mb']):.1f} | {p['ratio_mem']:.2f} | "
          f"{'yes' if p['same_output'] else 'NO'} |")
    w("")


def main(a):
    if not a:
        a = ["build/bench/last.json"]
    path, extra = a[0], dict(zip(a[1::2], a[2::2]))
    for k in extra:
        if k not in ("--rounds", "--build", "--servers"):
            sys.exit("report.py: unknown argument " + k)
    r = json.load(open(path))
    out = []
    w = out.append
    machine(w, r, path)
    method(w, r)
    results(w, r)
    if "--rounds" in extra:
        rounds(w, extra["--rounds"])
    if "--build" in extra:
        build(w, extra["--build"])
    if "--servers" in extra:
        servers(w, extra["--servers"])
    w("## What each pair does")
    w("")
    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1:])
