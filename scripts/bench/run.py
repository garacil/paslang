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

"""Measure paslang against Go, the reference for what is good.

  scripts/bench/run.py            build and run the pairs, print the table, then the probes
  scripts/bench/run.py probes     run the robustness probes only, print status and message
  scripts/bench/run.py -n 5       five runs per program (default 3), median reported
  scripts/bench/run.py --scale F  every budget times F (F < 1 shows a failing run)
  scripts/bench/run.py --json P   write every number and the machine's details to P

After the table, the pairs in CHECKPTR run again built with paslangc -checkptr
(P104): the line gives that build's time as a multiple of the plain one, held
to CHECKPTR_BUDGET, and its output must be the same.

make bench runs it with this tree's bin/paslangc first on the PATH (P89).

Each pair is one .paslang and one .go with the same work. The .paslang is compiled
with the paslangc on the PATH, the .go with go (its cache under build/gocache).
The table prints median wall time, resident memory (ru_maxrss of that process)
and the ratio paslang / Go. Exit status is 1 when a time ratio passes its budget
in BUDGET, when paslang's peak resident memory passes MEM_BUDGET times Go's, or
when the outputs differ. Budgets are today's numbers rounded up; they go down as
milestones close. The numbers come from a run, never from memory.
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "build", "bench")
PAIRS = ["b1loop", "b2str", "b3spawn", "b4chan", "b5map", "b6smap", "b7narrow", "b8ptr",
         "b9hash", "b10rot", "b11tree"]
CHECKPTR = ["b8ptr"]
PROBES = ["p1alloccap", "p2deeprec", "p3divzero", "p4nil", "p5bounds", "p6strbounds", "p7parked"]
# paslang / Go wall-time ratio allowed, per pair: today's numbers rounded up,
# lowered as milestones close (P90 took b4chan to 0.4; P93, P94, P96 and P98 took
# b1loop to 1.0, b2str to 0.9, b5map and b3spawn to 0.8 and b4chan to 0.2 on
# 2026-09-26, 1.0.52). The margin above 1.0 is the noise of a shared machine.
# P89 (1.0.72): with P90 to P98 closed every pair is at parity or better, so the
# budgets are 1.0 and the noise of a shared machine (runs vary by 10 to 30%
# here): 1.1, medians of seven runs under make bench. b4chan stays at 0.5 to
# keep what it won (0.3 today); b6smap, 0.8 to 1.0 today, is held at 1.1.
BUDGET = {"b1loop": 1.1, "b2str": 1.1, "b3spawn": 1.1, "b4chan": 0.5, "b5map": 1.1, "b6smap": 1.1,
          # P100 (1.0.96): narrow code, at 1.1 since P100 closed (1.0.105:
          # 0.82 of Go's cycles, the instructions Go runs and its loops aligned).
          "b7narrow": 1.1,
          # P104 (1.0.111): pointer walks and a linked list, 0.93 of Go's
          # cycles (Go walks the block as a slice).
          "b8ptr": 1.1,
          # 1.1.1 (2026-09-29, docs/BENCH-2026-09-29.md): the hash kernels
          # at Go's time after the const parameters stopped being copied;
          # the rotations of a xoshiro256** stream at 1.47 (the loop keeps
          # six variables in registers and has eight) and the ordered
          # tree at 1.31 of the same B+ tree in Go (the leaf's key layout,
          # the calls P112 removes): today's numbers rounded up, to go
          # down with P113.
          "b9hash": 1.1, "b10rot": 1.5, "b11tree": 1.4}
# paslangc -checkptr / the plain build, per pair in CHECKPTR (P104).
CHECKPTR_BUDGET = {"b8ptr": 10.0}
# Peak resident memory, paslang / Go: at most Go's and the same margin (every
# pair is at or under Go's today: 12/12, 12/12, 12/26, 12/12, 48/52, 115/121 MB).
MEM_BUDGET = 1.1


def sh(cmd, env=None, cwd=ROOT):
    p = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=cwd)
    if p.returncode != 0:
        sys.exit(f"{' '.join(cmd)}\n{p.stderr}")


def build(name, go=True):
    os.makedirs(OUT, exist_ok=True)
    # paslangc makes a build/ under its cwd, so it runs from the root, where one belongs.
    sh(["paslangc", "-o", os.path.join(OUT, name + ".pl"), os.path.join(HERE, name + ".paslang")])
    if go:
        env = dict(os.environ)
        env.setdefault("HOME", OUT)
        env["GOCACHE"] = os.path.join(OUT, "gocache")
        env["GOFLAGS"] = "-mod=mod"
        d = os.path.join(OUT, "go_" + name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "main.go"), "w") as f, open(os.path.join(HERE, name + ".go")) as g:
            f.write(g.read())
        if not os.path.exists(os.path.join(d, "go.mod")):
            sh(["go", "mod", "init", name], env=env, cwd=d)
        p = subprocess.run(["go", "build", "-o", os.path.join(OUT, name + ".go.bin"), "."],
                           capture_output=True, text=True, env=env, cwd=d)
        if p.returncode != 0:
            sys.exit(p.stderr)


def run(exe, n):
    """Median wall seconds, peak resident MB, exit status, first output line."""
    walls, rss, status, first = [], 0, 0, ""
    for _ in range(n):
        so = open(os.path.join(OUT, "stdout"), "w+")
        se = open(os.path.join(OUT, "stderr"), "w+")
        t = time.perf_counter()
        p = subprocess.Popen([exe], stdout=so, stderr=se)
        _, st, ru = os.wait4(p.pid, 0)
        walls.append(time.perf_counter() - t)
        rss = max(rss, ru.ru_maxrss / 1024)
        status = st >> 8 if st & 0xff == 0 else -(st & 0x7f)
        so.seek(0); se.seek(0)
        out = so.read().strip().splitlines()
        err = se.read().strip().splitlines()
        first = (out[0] if out else "") + ((" | " + err[0]) if err else "")
        so.close(); se.close()
    walls.sort()
    LAST_WALLS[exe] = list(walls)
    return walls[len(walls) // 2], rss, status, first


LAST_WALLS = {}


def machine():
    """The hardware, kernel and toolchain a run happened on, for the record."""
    def out(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
        except OSError:
            return ""
    def read(path):
        try:
            return open(path).read().strip()
        except OSError:
            return ""
    info = {"date": time.strftime("%Y-%m-%d %H:%M:%S %z"), "hostname": out(["hostname"]),
            "kernel": out(["uname", "-r"]), "os": "", "cpu": {}, "memory": {}, "toolchain": {},
            "load_before": read("/proc/loadavg")}
    for line in read("/etc/os-release").splitlines():
        if line.startswith("PRETTY_NAME="):
            info["os"] = line.split("=", 1)[1].strip('"')
    cpu = {}
    for line in out(["lscpu"]).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            cpu[k.strip()] = v.strip()
    flags = cpu.get("Flags", cpu.get("Indicadores", "")).split()
    info["cpu"] = {"model": cpu.get("Model name", cpu.get("Nombre del modelo", "")),
                   "logical_cpus": os.cpu_count(),
                   "l1d": cpu.get("L1d cache", cpu.get("Caché L1d", "")),
                   "l2": cpu.get("L2 cache", cpu.get("Caché L2", "")),
                   "l3": cpu.get("L3 cache", cpu.get("Caché L3", "")),
                   "max_mhz": cpu.get("CPU max MHz", cpu.get("CPU MHz máx.", "")),
                   "governor": read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"),
                   "boost": read("/sys/devices/system/cpu/cpufreq/boost"),
                   "features_used": [f for f in ("sse4_2", "popcnt", "pclmulqdq", "avx2", "bmi2", "sha_ni", "avx512f") if f in flags]}
    for line in read("/proc/meminfo").splitlines():
        if line.startswith(("MemTotal", "MemAvailable")):
            k, v = line.split(":", 1)
            info["memory"][k] = v.strip()
    info["toolchain"] = {"paslangc": [l.strip(" │") for l in out(["paslangc", "-v"]).splitlines() if "paslangc" in l][:1],
                         "go": out(["go", "version"]), "as": out(["as", "--version"]).splitlines()[:1],
                         "ld": out(["ld", "--version"]).splitlines()[:1]}
    return info


def checkptr(n, scale):
    """The pairs in CHECKPTR built with -checkptr: time over the plain build's."""
    bad = 0
    for b in CHECKPTR:
        sh(["paslangc", "-checkptr", "-o", os.path.join(OUT, b + ".cp"), os.path.join(HERE, b + ".paslang")])
        pw, _, ps, pl_out = run(os.path.join(OUT, b + ".pl"), n)
        cw, _, cs, cp_out = run(os.path.join(OUT, b + ".cp"), n)
        ratio = cw / pw if pw > 0 else float("inf")
        budget = CHECKPTR_BUDGET[b] * scale
        same = "yes" if (cp_out == pl_out and cs == 0 and ps == 0) else f"NO ({cp_out!r} vs {pl_out!r})"
        flag = "  OVER BUDGET" if ratio > budget else ""
        bad += bool(flag) or same != "yes"
        print(f"{b:10s} -checkptr {cw:7.3f} s, {ratio:5.1f} times the plain build (budget {budget:.1f})  same output: {same}{flag}")
    return bad


def probes():
    print(f"{'probe':12s} {'status':>7s}  message")
    for p in PROBES:
        build(p, go=False)
        w, r, st, first = run(os.path.join(OUT, p + ".pl"), 1)
        print(f"{p:12s} {st:7d}  {first}")


def main():
    n = 3
    scale = 1.0
    args = sys.argv[1:]
    json_path = ""
    while args[:1] in (["-n"], ["--scale"], ["--json"]):
        if args[0] == "-n":
            n = int(args[1])
        elif args[0] == "--json":
            json_path = args[1]
        else:
            scale = float(args[1])
        args = args[2:]
    record = {"machine": machine(), "runs_per_program": n, "scale": scale, "pairs": [], "checkptr": []}
    if args == ["probes"]:
        probes()
        return
    bad = 0
    print(f"{'pair':10s} {'go s':>7s} {'paslang s':>10s} {'ratio':>6s} {'budget':>7s} "
          f"{'go MB':>6s} {'pl MB':>6s} {'mem':>5s}  same output")
    for b in PAIRS:
        build(b)
        gw, gr, gs, go_out = run(os.path.join(OUT, b + ".go.bin"), n)
        pw, pr, ps, pl_out = run(os.path.join(OUT, b + ".pl"), n)
        ratio = pw / gw if gw > 0 else float("inf")
        mem = pr / gr if gr > 0 else float("inf")
        budget = BUDGET[b] * scale
        same = "yes" if (go_out == pl_out and gs == 0 and ps == 0) else f"NO ({pl_out!r} vs {go_out!r})"
        flag = ""
        if ratio > budget:
            flag += "  OVER BUDGET"
        if mem > MEM_BUDGET * scale:
            flag += "  OVER MEMORY"
        bad += bool(flag) or same != "yes"
        print(f"{b:10s} {gw:7.3f} {pw:10.3f} {ratio:6.2f} {budget:7.2f} {gr:6.0f} {pr:6.0f} {mem:5.2f}  {same}{flag}")
        record["pairs"].append({"pair": b, "go": {"median_s": gw, "walls_s": LAST_WALLS.get(os.path.join(OUT, b + ".go.bin"), []),
                                                  "peak_rss_mb": gr, "status": gs, "output": go_out},
                                "paslang": {"median_s": pw, "walls_s": LAST_WALLS.get(os.path.join(OUT, b + ".pl"), []),
                                            "peak_rss_mb": pr, "status": ps, "output": pl_out},
                                "ratio_time": ratio, "ratio_mem": mem, "budget": budget, "same_output": same == "yes",
                                "over": flag.strip()})
    print()
    bad += checkptr(n, scale)
    print()
    probes()
    if json_path:
        import json
        record["machine"]["load_after"] = open("/proc/loadavg").read().strip()
        with open(json_path, "w") as f:
            json.dump(record, f, indent=1)
        print(f"record written to {json_path}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
