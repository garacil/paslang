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
  scripts/bench/run.py -n 5       five alternating rounds per pair (default 3)
  scripts/bench/run.py --scale F  every budget times F (F < 1 shows a failing run)
  scripts/bench/run.py --json P   write every number and the machine's details to P
  scripts/bench/run.py --cpu base build the paslang side for these processors only
                                  (comma-separated; default native,base: Regla 12)

After the table, the pairs in CHECKPTR run again built with paslangc -checkptr
(P104): the line gives that build's time as a multiple of the plain one, held
to CHECKPTR_BUDGET, and its output must be the same.

make bench runs it with this tree's bin/paslangc first on the PATH (P89).

Each pair is one .paslang and one .go with the same work. The .paslang is compiled
with the paslangc on the PATH, once with -cpu native and once with -cpu base
(build/bench/NAME.pl and NAME.base.pl), the .go with go (its cache under
build/gocache); each build is held to the same budgets. The native build
runs against Go as it ships (GOAMD64=v1, its libraries choosing the
processor's extensions when they run); the base build against the same Go
binary run with GODEBUG=cpu.all=off, which turns every optional extension
off (internal/cpu processOptions), so both run on the base processor.
The two programs of a pair run in rounds, alternating which runs first. The
table prints each side's median wall time, the median of the rounds' ratios
paslang / Go (the time verdict), the median peak resident memory (VmHWM as
the program exits, scripts/bench/peak.py, over MEM_RUNS runs apart from the
timed ones) and its ratio. A program that measures several things (SECTIONS)
takes the name of one as its argument, and each NAME:SECTION is judged as a
pair of its own; a run past TIMEOUT seconds is killed and its unit fails.
Exit status is 1 when a time ratio passes its budget in BUDGET, when
paslang's peak resident memory passes MEM_BUDGET times Go's, or when the
outputs differ. Every budget is below 1.00 (P223, Regla 12): a pair Go wins
or ties fails, and has its hito; a pair that wins keeps what it won,
rounded up. The numbers come from a run, never from memory.
"""
import os
import select
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from peak import peak_kib  # noqa: E402
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "build", "bench")
PAIRS = ["b1loop", "b2str", "b3spawn", "b4chan", "b5map", "b6smap", "b7narrow", "b8ptr",
         "b9hash", "b10rot", "b11tree",
         # P223: everything else paslang does that Go does too.
         "b12num", "b13strw", "b14sort", "b15io", "b16net", "b17conc", "b18sync", "b19heap",
         "b20hash", "b21text", "b22rand", "b23date", "b24math", "b25exec", "b26slice", "b27call",
         "b28stack", "b29exc", "b30gc", "b31map", "b32fs",
         # P201: UTF-8 validation (PasUtf8Valid against unicode/utf8.Valid)
         "b33utf8",
         # P203: JSON (the json type against encoding/json v2 and v1) on Go's corpus
         "b34json",
         # P205: typed JSON written (JsonEncode of a record against Marshal)
         "b35bind",
         # P206: typed JSON read (JsonDecode into records against Unmarshal)
         "b36unbind",
         # P426: XML read token by token (TXmlReader.Next against Decoder.Token)
         "b38xml"]
# The longest one run may take, in seconds: a run past it is killed, its
# unit stops being measured and fails (Go's side of every pair takes
# under 1 s; paslang's append of a character, quadratic until its hito,
# took over ten minutes for twenty million).
TIMEOUT = 60
# A program that measures several things takes the name of one as its
# argument; each NAME:SECTION is judged as a pair of its own.
SECTIONS = {
    "b12num": ["itoa", "ftoa", "fmt", "atoi", "atof"],
    "b13strw": ["index", "upper", "lower", "replace", "trim", "compare", "equalfold", "concat"],
    "b14sort": ["ints", "strings", "reals"],
    "b15io": ["small", "smallread"],
    "b16net": ["tcp", "unix"],
    "b17conc": ["sleep", "timeout", "pipe", "fanin"],
    "b18sync": ["mutex", "rwread", "once", "cond", "atomic"],
    "b19heap": ["ints", "strings"],
    "b20hash": ["md5", "sha1", "sha512", "sha3", "hmac", "crc32", "adler32", "fnv"],
    "b21text": ["hex", "runes"],
    "b22rand": ["own", "below", "real", "global", "globalpar"],
    "b23date": ["stamp", "date"],
    "b24math": ["sin", "exp", "ln", "sqrt", "pow", "atan"],
    "b25exec": ["serial", "par"],
    "b26slice": ["ints", "strings"],
    "b27call": ["iface", "closure", "proc"],
    "b28stack": ["deep", "many"],
    "b29exc": ["raise"],
    "b30gc": ["trees"],
    "b31map": ["iter", "delete", "update"],
    "b32fs": ["stat", "list"],
    "b33utf8": ["ascii", "mixed"],
    "b34json": ["parse", "parse1", "compact", "compact1", "pretty", "pretty1", "canonical"],
    "b35bind": ["marshal", "marshal1", "indent", "indent1"],
    "b36unbind": ["unmarshal", "unmarshal1"],
    "b38xml": ["tokens"],
}
CHECKPTR = ["b8ptr"]
PROBES = ["p1alloccap", "p2deeprec", "p3divzero", "p4nil", "p5bounds", "p6strbounds", "p7parked"]
# paslang / Go time allowed, per pair: the median of the rounds' ratios (P223,
# Regla 12: faster than Go in everything, so every budget is below 1.00 and a
# pair Go wins or ties fails make bench). The history: 1.1 for most pairs from
# P89 (1.0.72) to P223, the noise of medians of separate runs on a shared
# machine; 1.5 for b10rot and 1.4 for b11tree from 1.1.1. A pair that wins
# keeps what it won: today's ratio rounded up (2026-10-12, 1.1.106, forty
# alternating rounds, native and base: b3spawn 0.67/0.65, b4chan 0.22/0.23,
# b7narrow 0.85/0.86, b11tree 0.85/0.83). A pair at parity or behind is held
# at 0.99, and its hito takes it under (b1loop 0.98/0.995, b2str 1.29/1.24,
# b5map 1.00/0.95, b6smap 0.99/0.99, b8ptr 1.08/1.07, b9hash 1.01/2.44,
# b10rot 1.43/1.43).
BUDGET = {"b1loop": 0.99, "b2str": 0.99, "b3spawn": 0.90, "b4chan": 0.30, "b5map": 0.99,
          "b6smap": 0.99, "b7narrow": 0.90, "b8ptr": 0.99, "b9hash": 0.99, "b10rot": 0.99,
          "b11tree": 0.95}
# The pairs P223 added (2026-10-13, 1.1.106, forty alternating rounds,
# native and base): every one that loses or ties on either processor is
# held at 0.99 and has its hito; the ones that win on both keep what they
# won, the larger of the two rounded up (upper 0.040/0.048, lower
# 0.032/0.039, equalfold 0.058/0.114, small 0.935/0.939, smallread
# 0.941/0.942, pipe 0.574/0.710, fanin 0.436/0.426, mutex 0.666/0.618,
# cond 0.497/0.472, pow 0.946/0.897, b26slice:strings 0.787/0.858, deep
# 0.862/0.857, raise 0.069/0.071, trees 0.919/0.906).
for _b in PAIRS[11:]:
    for _sec in SECTIONS[_b]:
        BUDGET.setdefault(_b + ":" + _sec, 0.99)
BUDGET.update({"b13strw:upper": 0.10, "b13strw:lower": 0.10, "b13strw:equalfold": 0.15,
               "b15io:small": 0.97, "b15io:smallread": 0.98,
               "b17conc:pipe": 0.80, "b17conc:fanin": 0.55,
               "b18sync:mutex": 0.80, "b18sync:cond": 0.65,
               "b24math:pow": 0.98, "b26slice:strings": 0.90, "b28stack:deep": 0.90,
               "b29exc:raise": 0.15, "b30gc:trees": 0.97})
# P242 (1.1.107): s := s + c grows s in its own block and a block past 32
# KiB grows where it is; twenty million appends did not end in ten
# minutes and take 0.861 of Go's strings.Builder with -cpu native and
# 0.767 with -cpu base (twenty alternating rounds), 19.7 MB at the peak
# against Go's 51.4.
BUDGET["b13strw:concat"] = 0.90
# P203 (1.1.124): the json type on Go's corpus, seven alternating rounds,
# native and base, against encoding/json v2 (and v1 for the sections that
# end in 1): parse 0.560/0.613, parse1 0.279/0.306, compact 0.380/0.396,
# compact1 0.304/0.316, pretty 0.372/0.374, pretty1 0.269/0.262,
# canonical 0.946/0.957 (Go's jsontext.Value.Canonicalize); the peak
# memory 0.93, 0.92, 0.63, 0.61, 0.58, 0.50 and 0.85 of Go's.
BUDGET.update({"b34json:parse": 0.70, "b34json:parse1": 0.40, "b34json:compact": 0.50,
               "b34json:compact1": 0.40, "b34json:pretty": 0.45, "b34json:pretty1": 0.35,
               "b34json:canonical": 0.98})
# P205: typed JSON written; measured 0.79/0.80 (native/base) of Go's v2
# compact, 0.80 of v1, 0.74/0.72 of v2 a value a line, 0.70/0.68 of v1
BUDGET.update({"b35bind:marshal": 0.88, "b35bind:marshal1": 0.88, "b35bind:indent": 0.82,
               "b35bind:indent1": 0.78})
# P206: typed JSON read; measured 0.74/0.78 (native/base) of Go's v2, 0.66/0.69
# of v1, its peak 2.6 times Go's (the document the text was parsed into).
# P280 reads the text a token at a time with no document: 0.77/0.80 of v2,
# 0.70/0.73 of v1, the peak 55 MB against Go's 40, now the data's own size
# (P285 to P287).
BUDGET.update({"b36unbind:unmarshal": 0.88, "b36unbind:unmarshal1": 0.81})
# paslangc -checkptr / the plain build, per pair in CHECKPTR (P104).
CHECKPTR_BUDGET = {"b8ptr": 10.0}
# Peak resident memory, paslang / Go, the medians of MEM_RUNS traced runs:
# below Go's in every pair (P223). Before P223 it read 1.1, and the small
# pairs' numbers were Python's own size (peak.py says why).
MEM_BUDGET = 0.99
# Runs of each program for its memory, traced to read VmHWM as it exits:
# a small program's peak moves by 2 MiB from one run to the next on a
# system with transparent huge pages always on (0, 1 or 2 of them under
# a 276 KiB paslang program, as its regions fall with ASLR; Go's alike).
MEM_RUNS = 5


def sh(cmd, env=None, cwd=ROOT):
    p = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=cwd)
    if p.returncode != 0:
        sys.exit(f"{' '.join(cmd)}\n{p.stderr}")


def pl_path(name, cpu, ext=".pl"):
    """The paslang build of a pair for a processor: NAME.pl for native, NAME.base.pl for base."""
    return os.path.join(OUT, name + ("" if cpu == "native" else "." + cpu) + ext)


def prepare():
    """What a pair reads besides itself: b34json, Go's JSON corpus
    (testdata/json/corpus, zstd) as plain files in build/bench/json, read
    with Python's compression.zstd (a test tool)."""
    import compression.zstd
    d = os.path.join(OUT, "json")
    os.makedirs(d, exist_ok=True)
    for f in sorted(os.listdir(os.path.join(ROOT, "testdata", "json", "corpus"))):
        if f.endswith(".json.zst"):
            with open(os.path.join(ROOT, "testdata", "json", "corpus", f), "rb") as g:
                data = compression.zstd.decompress(g.read())
            with open(os.path.join(d, f[:-4]), "wb") as h:
                h.write(data)


def build(name, go=True, cpu="native"):
    os.makedirs(OUT, exist_ok=True)
    # paslangc makes a build/ under its cwd, so it runs from the root, where one belongs.
    sh(["paslangc", "-cpu", cpu, "-o", pl_path(name, cpu), os.path.join(HERE, name + ".paslang")])
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


def go_env(cpu):
    """The environment Go runs in for a paslang build of cpu: the base
    processor turns off every extension Go would choose when it runs."""
    if cpu == "base":
        return dict(os.environ, GODEBUG="cpu.all=off")
    return None


def peak_mb(exe, env=None, runs=MEM_RUNS, args=()):
    """Median peak resident MB of runs traced runs (peak.py), and all of them."""
    peaks = []
    with open(os.devnull, "w") as null:
        for _ in range(runs):
            kib, _ = peak_kib([exe, *args], env=env, stdout=null.fileno(), stderr=null.fileno())
            peaks.append(kib / 1024)
    peaks.sort()
    return peaks[len(peaks) // 2], peaks


def units(names=None):
    """The (program, section) pairs to measure, section None for a program
    without sections."""
    return [(b, sec) for b in (names or PAIRS) for sec in SECTIONS.get(b, [None])]


def unit_name(b, sec):
    return b if sec is None else b + ":" + sec


def once(exe, env=None, args=()):
    """Wall seconds, exit status and first output line of one run."""
    so = open(os.path.join(OUT, "stdout"), "w+")
    se = open(os.path.join(OUT, "stderr"), "w+")
    t = time.perf_counter()
    p = subprocess.Popen([exe, *args], stdout=so, stderr=se, env=env)
    # The end is waited for on a pidfd: poll wakes when the program ends.
    # Popen.wait(timeout) sleeps in steps of up to 50 ms and rounded every
    # time up to them.
    fd = os.pidfd_open(p.pid)
    poller = select.poll()
    poller.register(fd, select.POLLIN)
    ended = poller.poll(TIMEOUT * 1000)
    os.close(fd)
    if not ended:
        p.kill()
        p.wait()
        so.close(); se.close()
        return float("inf"), "timeout", "did not end in %d s" % TIMEOUT
    _, st = os.waitpid(p.pid, 0)
    wall = time.perf_counter() - t
    p.returncode = status = os.waitstatus_to_exitcode(st)
    so.seek(0); se.seek(0)
    out = so.read().strip().splitlines()
    err = se.read().strip().splitlines()
    so.close(); se.close()
    return wall, status, (out[0] if out else "") + ((" | " + err[0]) if err else "")


def alternate(a, b, n, env_a=None, env_b=None, args=()):
    """n rounds of the programs a and b, alternating which runs first.
    Gives each side's median wall seconds, exit status and first line
    (the first line that differs from the first run's, or a status that
    is not 0, when one does), and the median of the rounds' ratios, b's
    time over a's. On a machine that runs anything else a median of
    separate runs moved by up to 30 % from one batch to the next; a
    round's two programs share the machine's state of that moment."""
    wa, wb, ratios = [], [], []
    sa, oa, sb, ob = 0, None, 0, None
    for r in range(n):
        if r % 2 == 0:
            ta, xa, ya = once(a, env_a, args)
            tb, xb, yb = once(b, env_b, args)
        else:
            tb, xb, yb = once(b, env_b, args)
            ta, xa, ya = once(a, env_a, args)
        wa.append(ta)
        wb.append(tb)
        ratios.append(tb / ta if ta > 0 else float("inf"))
        sa = sa or xa
        sb = sb or xb
        if xa == "timeout" or xb == "timeout":
            oa, ob = ya, yb
            break
        oa = ya if oa is None or ya != oa else oa
        ob = yb if ob is None or yb != ob else ob
    LAST_WALLS[(a, tuple(args))] = sorted(wa)
    LAST_WALLS[(b, tuple(args))] = sorted(wb)
    LAST_RATIOS[(a, b, tuple(args))] = list(ratios)
    return (median(wa), sa, oa), (median(wb), sb, ob), median(ratios)


def median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2


LAST_RATIOS = {}
LAST_WALLS = {}
LAST_PEAKS = {}


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


def checkptr(n, scale, cpu):
    """The pairs in CHECKPTR built with -checkptr: time over the plain build's."""
    bad = 0
    for b in CHECKPTR:
        sh(["paslangc", "-cpu", cpu, "-checkptr", "-o", pl_path(b, cpu, ".cp"), os.path.join(HERE, b + ".paslang")])
        (pw, ps, pl_out), (cw, cs, cp_out), ratio = alternate(pl_path(b, cpu), pl_path(b, cpu, ".cp"), n)
        LAST_RATIOS.pop((pl_path(b, cpu), pl_path(b, cpu, ".cp"), ()), None)
        budget = CHECKPTR_BUDGET[b] * scale
        same = "yes" if (cp_out == pl_out and cs == 0 and ps == 0) else f"NO ({cp_out!r} vs {pl_out!r})"
        flag = "  OVER BUDGET" if ratio > budget else ""
        bad += bool(flag) or same != "yes"
        print(f"{b:10s} {cpu:6s} -checkptr {cw:7.3f} s, {ratio:5.1f} times the plain build (budget {budget:.1f})  same output: {same}{flag}")
    return bad


def probes():
    print(f"{'probe':12s} {'status':>7s}  message")
    for p in PROBES:
        build(p, go=False)
        w, st, first = once(os.path.join(OUT, p + ".pl"))
        print(f"{p:12s} {st:7d}  {first}")


def main():
    # One line as each pair is measured, also into a file (make bench > log).
    sys.stdout.reconfigure(line_buffering=True)
    n = 3
    scale = 1.0
    args = sys.argv[1:]
    json_path = ""
    cpus = ["native", "base"]
    while args[:1] in (["-n"], ["--scale"], ["--json"], ["--cpu"]):
        if args[0] == "-n":
            n = int(args[1])
        elif args[0] == "--json":
            json_path = args[1]
        elif args[0] == "--cpu":
            cpus = args[1].split(",")
        else:
            scale = float(args[1])
        args = args[2:]
    record = {"machine": machine(), "runs_per_program": n, "scale": scale, "cpus": cpus, "pairs": [], "checkptr": []}
    if args == ["probes"]:
        probes()
        return
    bad = 0
    prepare()
    print(f"{'pair':14s} {'cpu':6s} {'go s':>7s} {'paslang s':>10s} {'ratio':>6s} {'budget':>7s} "
          f"{'go MB':>6s} {'pl MB':>6s} {'mem':>5s}  same output")
    for cpu in cpus:
        built = set()
        for b, sec in units():
            if b not in built:
                build(b, go=(cpu == cpus[0]), cpu=cpu)
                built.add(b)
            name, args = unit_name(b, sec), (() if sec is None else (sec,))
            gexe, pexe = os.path.join(OUT, b + ".go.bin"), pl_path(b, cpu)
            (gw, gs, go_out), (pw, ps, pl_out), ratio = alternate(gexe, pexe, n, go_env(cpu), None, args)
            # A unit that did not end has no memory to compare: none is
            # measured (0 in the record), and its time fails it.
            ended = gs != "timeout" and ps != "timeout"
            if ended:
                gr, gpeaks = peak_mb(gexe, go_env(cpu), args=args)
                pr, ppeaks = peak_mb(pexe, args=args)
                mem = pr / gr if gr > 0 else float("inf")
            else:
                gr, gpeaks, pr, ppeaks, mem = 0.0, [], 0.0, [], 0.0
            budget = BUDGET[name] * scale
            same = "yes" if (go_out == pl_out and gs == 0 and ps == 0) else f"NO ({pl_out!r} vs {go_out!r})"
            flag = ""
            if ratio > budget:
                flag += "  OVER BUDGET"
            if ended and mem > MEM_BUDGET * scale:
                flag += "  OVER MEMORY"
            bad += bool(flag) or same != "yes"
            print(f"{name:14s} {cpu:6s} {gw:7.3f} {pw:10.3f} {ratio:6.2f} {budget:7.2f} {gr:6.1f} {pr:6.1f} {mem:5.2f}  {same}{flag}")
            record["pairs"].append({"pair": name, "cpu": cpu, "go_godebug": (go_env(cpu) or {}).get("GODEBUG", ""),
                                    "go": {"median_s": gw, "walls_s": LAST_WALLS.get((gexe, args), []),
                                           "peak_rss_mb": gr, "peaks_mb": gpeaks, "status": gs, "output": go_out},
                                    "paslang": {"median_s": pw, "walls_s": LAST_WALLS.get((pexe, args), []),
                                                "peak_rss_mb": pr, "peaks_mb": ppeaks, "status": ps, "output": pl_out},
                                    "round_ratios": LAST_RATIOS.get((gexe, pexe, args), []),
                                    "ratio_time": ratio, "ratio_mem": mem, "budget": budget, "same_output": same == "yes",
                                    "over": flag.strip()})
    print()
    for cpu in cpus:
        bad += checkptr(n, scale, cpu)
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
