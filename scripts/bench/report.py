#!/usr/bin/env python3
"""Write the Markdown report of a benchmark record (run.py --json):
the machine, the toolchain, the method, the table of every pair with
all its runs, and the memory. The notes on each pair are added by hand
below the table, from a reading of the code, never from memory.

    scripts/bench/report.py docs/bench/2026-09-29.json > docs/BENCH-2026-09-29.md
"""
import json
import sys


def main(path):
    r = json.load(open(path))
    m = r["machine"]
    cpu = m["cpu"]
    t = m["toolchain"]
    out = []
    w = out.append
    date = m["date"][:10]
    w(f"# Benchmark against Go, {date}")
    w("")
    w(f"Record: `{path}` (every run, every number, written by `scripts/bench/run.py --json`).")
    w("Go is the reference for what is good; the numbers come from a run, never")
    w("from memory.")
    w("")
    w("## The machine")
    w("")
    w("| | |")
    w("|---|---|")
    w(f"| Processor | {cpu['model']}, {cpu['logical_cpus']} logical CPUs |")
    w(f"| Caches | L1d {cpu['l1d']}, L2 {cpu['l2']}, L3 {cpu['l3']} |")
    w(f"| Clock | up to {cpu['max_mhz']} MHz, governor `{cpu['governor']}`, boost {cpu['boost'] or '?'} |")
    w(f"| Extensions the compiler uses | {', '.join(cpu['features_used'])} |")
    w(f"| Memory | {m['memory'].get('MemTotal', '?')} total, {m['memory'].get('MemAvailable', '?')} available |")
    w(f"| System | {m['os']}, kernel {m['kernel']}, host `{m['hostname']}` |")
    w(f"| Load average before, after | {m['load_before'].split()[0]}, {m.get('load_after', '?').split()[0]} (1 min) |")
    w("")
    w("## The toolchain")
    w("")
    w("| | |")
    w("|---|---|")
    w(f"| paslangc | {' '.join(t['paslangc']) if t['paslangc'] else '?'} (`-cpu native` by default: the processor above) |")
    w(f"| Go | {t['go']} |")
    w(f"| Assembler, linker | {(t['as'] or ['?'])[0]}; {(t['ld'] or ['?'])[0]} |")
    w("")
    w("## The method")
    w("")
    w(f"Each pair is one `.paslang` and one `.go` with the same work (`scripts/bench/`). Each program ran")
    w(f"{r['runs_per_program']} times; the table gives the median wall time and the peak resident memory of")
    w("the process (`ru_maxrss`). The ratio is paslang over Go: below 1 paslang is faster. A budget")
    w("is today's number rounded up, and `run.py` fails when a pair passes it, so a slowdown is a")
    w("failed run. Both binaries print the same, or the pair fails.")
    w("")
    w("## Results")
    w("")
    w("| Pair | Go s | paslang s | time ratio | budget | Go MB | paslang MB | memory ratio | same output |")
    w("|---|---|---|---|---|---|---|---|---|")
    for p in r["pairs"]:
        g, l = p["go"], p["paslang"]
        flag = f" **{p['over']}**" if p.get("over") else ""
        w(f"| {p['pair']} | {g['median_s']:.3f} | {l['median_s']:.3f} | {p['ratio_time']:.2f}{flag} | {p['budget']:.2f} | "
          f"{g['peak_rss_mb']:.0f} | {l['peak_rss_mb']:.0f} | {p['ratio_mem']:.2f} | {'yes' if p['same_output'] else 'NO'} |")
    w("")
    w("Every run, in seconds, sorted:")
    w("")
    w("| Pair | Go | paslang |")
    w("|---|---|---|")
    for p in r["pairs"]:
        gw = ", ".join(f"{x:.3f}" for x in p["go"]["walls_s"])
        lw = ", ".join(f"{x:.3f}" for x in p["paslang"]["walls_s"])
        w(f"| {p['pair']} | {gw} | {lw} |")
    w("")
    w("## What each pair does")
    w("")
    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "build/bench/last.json")
