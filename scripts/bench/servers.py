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
is paslang over Go. Writes a JSON record with --json, and fails when a
pair passes its budget.

    PATH=bin:$PATH python3 scripts/bench/servers.py [-n runs] [--json out]
"""
import json, os, platform, re, resource, shutil, statistics, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRV = os.path.join(ROOT, "scripts", "bench", "servers")
OUT = os.path.join(ROOT, "build", "bench", "servers")
# dnsd stops at 5000: at 10,000 queries in one burst both sides lose
# datagrams to the kernel's receive buffer (rmem_max, 4 MB) and take the
# two-second retry, some runs and not others.
PAIRS = [("httpd", [2000, 10000], "2000 clients, 6000 requests, 6000 served, 0 bad"),
         ("dnsd", [2000, 5000], "2000 clients, 2000 answered, 0 missed, 0 bad"),
         ("termd", [2000, 10000], "2000 sessions, 2000 quit, 0 bad")]
BUDGET = 1.10

def run_one(cmd):
    """Wall seconds, peak RSS in MB and the first line printed, the
    process a child of a fresh Python so ru_maxrss is its own."""
    helper = ("import resource,subprocess,sys,json,time\n"
              "t=time.time(); p=subprocess.run(sys.argv[1:], capture_output=True, text=True)\n"
              "r=resource.getrusage(resource.RUSAGE_CHILDREN)\n"
              "print(json.dumps({'rc':p.returncode,'s':time.time()-t,'mb':r.ru_maxrss/1024,'out':p.stdout.strip().split('\\n')[0] if p.stdout else ''}))")
    p = subprocess.run([sys.executable, "-c", helper] + cmd, capture_output=True, text=True, timeout=600)
    return json.loads(p.stdout.strip().split("\n")[-1])

def version_of(paslangc):
    """The version line of the banner, without the box."""
    out = subprocess.run([paslangc, "-v"], capture_output=True, text=True).stdout
    for line in out.split("\n"):
        if "paslangc" in line and re.search(r"\d+\.\d+\.\d+", line):
            return re.sub(r"[│╭╮╰╯─]", "", line).strip()
    return out.strip().split("\n")[0]

def main():
    runs = 3
    out = None
    a = sys.argv[1:]
    while a:
        if a[0] == "-n":
            runs = int(a[1]); a = a[2:]
        elif a[0] == "--json":
            out = a[1]; a = a[2:]
        else:
            print("servers.py: unknown argument", a[0]); sys.exit(2)
    os.makedirs(OUT, exist_ok=True)
    paslangc = shutil.which("paslangc") or os.path.join(ROOT, "bin", "paslangc")
    rec = {"date": time.strftime("%Y-%m-%d %H:%M:%S"), "machine": platform.platform(),
           "cpu": open("/proc/cpuinfo").read().split("model name")[1].split(":")[1].split("\n")[0].strip(),
           "go": subprocess.run(["go", "version"], capture_output=True, text=True).stdout.strip(),
           "paslangc": version_of(paslangc),
           "runs": runs, "pairs": []}
    fail = False
    print("pair             n    go s  paslang s  ratio  go MB  pl MB   mem  same output")
    for name, ns, _ in PAIRS:
        pl = os.path.join(OUT, name + ".pl")
        gb = os.path.join(OUT, name + ".go.bin")
        subprocess.run([paslangc, "-Fu", os.path.join(ROOT, "build"), "-o", pl,
                        os.path.join(ROOT, "examples", name + ".paslang")], check=True)
        subprocess.run(["go", "build", "-o", gb, os.path.join(SRV, name + ".go")], check=True, cwd=SRV)
        for n in ns:
            gs, ps, gm, pm, same = [], [], [], [], True
            for _ in range(runs):
                g = run_one([gb, "-selftest", str(n)])
                p = run_one([pl, "-selftest", str(n)])
                gs.append(g["s"]); ps.append(p["s"]); gm.append(g["mb"]); pm.append(p["mb"])
                if g["rc"] != 0 or p["rc"] != 0 or g["out"] != p["out"]:
                    same = False
            gt, pt = statistics.median(gs), statistics.median(ps)
            gmm, pmm = statistics.median(gm), statistics.median(pm)
            ratio = pt / gt if gt else 0
            over = ratio > BUDGET or not same
            fail = fail or over
            print("%-12s %6d  %6.3f  %9.3f  %5.2f  %5.0f  %5.0f  %4.2f  %s%s" % (
                name, n, gt, pt, ratio, gmm, pmm, pmm / gmm if gmm else 0, "yes" if same else "NO",
                "  OVER BUDGET" if over else ""))
            rec["pairs"].append({"pair": name, "n": n, "go_s": gs, "paslang_s": ps, "go_mb": gm,
                                 "paslang_mb": pm, "ratio": ratio, "same_output": same})
    if out:
        with open(out, "w") as f:
            json.dump(rec, f, indent=1)
        print("record written to", out)
    sys.exit(1 if fail else 0)

if __name__ == "__main__":
    main()
