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

"""The three servers against their Go twins (P115): each pair is
examples/<name>.paslang and scripts/bench/servers/<name>.go, both with
-selftest n (n client routines inside the program, the counts printed).
Wall time and peak resident memory, the median of the runs; the ratio
is paslang over Go. The memory is VmHWM as the program exits, read by a
traced run of its own after each timed one (scripts/bench/peak.py says
why getrusage's maximum is not it). Writes a JSON record with --json, and fails when a
pair passes its budget.

    PATH=bin:$PATH python3 scripts/bench/servers.py [-n runs] [--json out] [--cpu native,base]

The paslang side is built once for each processor (-cpu native and -cpu
base by default, Regla 12), both against the same Go binary, which runs
with GODEBUG=cpu.all=off against the base build (run.py says why). The
record keeps each run's exit status and first line, so a pair that does
not print the same says what each side printed.

Each run starts with the connection tracking table of the firewall at
most a quarter full (settle): a run of 10,000 clients leaves 10,000
entries for 120 s (nf_conntrack_tcp_timeout_time_wait), the runs of one
pair fill the 262,144 of this machine, and the kernel then drops every
new packet ("nf_conntrack: table full, dropping packet"): both sides'
dnsd lost datagrams and waited two seconds, an httpd run took 19 s.
"""
import json, os, platform, re, shutil, statistics, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from peak import peak_kib  # noqa: E402
SRV = os.path.join(ROOT, "scripts", "bench", "servers")
OUT = os.path.join(ROOT, "build", "bench", "servers")
# dnsd stops at 5000: at 10,000 queries in one burst both sides lose
# datagrams to the kernel's receive buffer (rmem_max, 4 MB) and take the
# two-second retry, some runs and not others.
PAIRS = [("httpd", [2000, 10000], "2000 clients, 6000 requests, 6000 served, 0 bad"),
         ("dnsd", [2000, 5000], "2000 clients, 2000 answered, 0 missed, 0 bad"),
         ("termd", [2000, 10000], "2000 sessions, 2000 quit, 0 bad"),
         ("apisrv", [2000, 10000], "2000 clients, 6000 requests, 6000 served, 0 bad")]
# paslang / Go, per pair, the median of the runs' ratios (each run of a
# pair alternates which side goes first): below 1.00 for time and memory
# (P223, Regla 12). From P115 to P223 it was 1.10 for time and nothing for
# memory. All three are held at 0.99. httpd wins (2026-10-12, 1.1.106:
# 0.86 and 0.97 native, 0.92 and 0.99 base), but a burst of 10,000
# connections passes the kernel's SYN backlog on both sides some runs and
# not others, and one such run (a 3 s retry) moves a median of three: a
# budget under 0.99 would fail at random. dnsd (0.93, 1.12; 0.98, 0.96)
# and termd (1.01, 0.30; 1.09, 0.57, its memory 0.98 and 1.01 at 10,000)
# go under with their hitos.
BUDGET = {"httpd": 0.99, "dnsd": 0.99, "termd": 0.99, "apisrv": 0.99}
MEM_BUDGET = 0.99

CONNTRACK = "/proc/sys/net/netfilter/nf_conntrack_"
WAITED = [0.0]


def settle():
    """Wait until the connection tracking table is at most a quarter full
    (no wait without one); the seconds waited are added to WAITED."""
    try:
        cap = int(open(CONNTRACK + "max").read())
    except OSError:
        return
    t = time.perf_counter()
    while int(open(CONNTRACK + "count").read()) > cap // 4:
        if time.perf_counter() - t > 600:
            sys.exit("servers.py: the connection tracking table stayed over a quarter full for 600 s")
        time.sleep(1)
    WAITED[0] += time.perf_counter() - t


def run_one(cmd, env=None):
    """Wall seconds, exit status and the first line printed of a timed
    run, then the peak resident MB of a traced run of its own."""
    settle()
    t = time.perf_counter()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env)
    s = time.perf_counter() - t
    settle()
    with open(os.devnull, "w") as null:
        kib, _ = peak_kib(cmd, env=env, stdout=null.fileno(), stderr=null.fileno())
    return {"rc": p.returncode, "s": s, "mb": kib / 1024,
            "out": p.stdout.strip().split("\n")[0] if p.stdout else ""}

def version_of(paslangc):
    """The version line of the banner, without the box."""
    out = subprocess.run([paslangc, "-v"], capture_output=True, text=True).stdout
    for line in out.split("\n"):
        if "paslangc" in line and re.search(r"\d+\.\d+\.\d+", line):
            return re.sub(r"[│╭╮╰╯─]", "", line).strip()
    return out.strip().split("\n")[0]

def main():
    # One line as each pair is measured, also into a file (make bench > log).
    sys.stdout.reconfigure(line_buffering=True)
    runs = 3
    out = None
    cpus = ["native", "base"]
    a = sys.argv[1:]
    while a:
        if a[0] == "-n":
            runs = int(a[1]); a = a[2:]
        elif a[0] == "--json":
            out = a[1]; a = a[2:]
        elif a[0] == "--cpu":
            cpus = a[1].split(","); a = a[2:]
        else:
            print("servers.py: unknown argument", a[0]); sys.exit(2)
    os.makedirs(OUT, exist_ok=True)
    paslangc = shutil.which("paslangc") or os.path.join(ROOT, "bin", "paslangc")
    rec = {"date": time.strftime("%Y-%m-%d %H:%M:%S"), "machine": platform.platform(),
           "cpu": open("/proc/cpuinfo").read().split("model name")[1].split(":")[1].split("\n")[0].strip(),
           "go": subprocess.run(["go", "version"], capture_output=True, text=True).stdout.strip(),
           "paslangc": version_of(paslangc),
           "runs": runs, "cpus": cpus, "pairs": []}
    fail = False
    print("pair     cpu        n    go s  paslang s  ratio  go MB  pl MB   mem  same output")
    for cpu, (name, ns, _) in [(c, p) for c in cpus for p in PAIRS]:
        pl = os.path.join(OUT, name + ("" if cpu == "native" else "." + cpu) + ".pl")
        gb = os.path.join(OUT, name + ".go.bin")
        subprocess.run([paslangc, "-cpu", cpu, "-Fu", os.path.join(ROOT, "build"), "-o", pl,
                        os.path.join(ROOT, "examples", name + ".paslang")], check=True)
        if cpu == cpus[0]:
            subprocess.run(["go", "build", "-o", gb, os.path.join(SRV, name + ".go")], check=True, cwd=SRV)
        genv = dict(os.environ, GODEBUG="cpu.all=off") if cpu == "base" else None
        for n in ns:
            gs, ps, gm, pm, same, outs, ratios = [], [], [], [], True, [], []
            for r in range(runs):
                if r % 2 == 0:
                    g = run_one([gb, "-selftest", str(n)], genv)
                    p = run_one([pl, "-selftest", str(n)])
                else:
                    p = run_one([pl, "-selftest", str(n)])
                    g = run_one([gb, "-selftest", str(n)], genv)
                ratios.append(p["s"] / g["s"] if g["s"] else float("inf"))
                outs.append({"go": [g["rc"], g["out"]], "paslang": [p["rc"], p["out"]]})
                gs.append(g["s"]); ps.append(p["s"]); gm.append(g["mb"]); pm.append(p["mb"])
                if g["rc"] != 0 or p["rc"] != 0 or g["out"] != p["out"]:
                    same = False
            gt, pt = statistics.median(gs), statistics.median(ps)
            gmm, pmm = statistics.median(gm), statistics.median(pm)
            ratio = statistics.median(ratios)
            mem = pmm / gmm if gmm else float("inf")
            flag = ""
            if ratio > BUDGET[name]:
                flag += "  OVER BUDGET"
            if mem > MEM_BUDGET:
                flag += "  OVER MEMORY"
            fail = fail or bool(flag) or not same
            print("%-8s %-6s %6d  %6.3f  %9.3f  %5.2f  %5.1f  %5.1f  %4.2f  %s%s" % (
                name, cpu, n, gt, pt, ratio, gmm, pmm, mem, "yes" if same else "NO", flag))
            rec["pairs"].append({"pair": name, "cpu": cpu, "n": n, "go_s": gs, "paslang_s": ps, "go_mb": gm,
                                 "paslang_mb": pm, "ratios": ratios, "ratio": ratio, "ratio_mem": mem,
                                 "budget": BUDGET[name], "same_output": same, "outputs": outs,
                                 "over": flag.strip()})
    rec["conntrack_wait_s"] = round(WAITED[0], 1)
    print("waited %.0f s for the connection tracking table" % WAITED[0])
    if out:
        with open(out, "w") as f:
            json.dump(rec, f, indent=1)
        print("record written to", out)
    sys.exit(1 if fail else 0)

if __name__ == "__main__":
    main()
