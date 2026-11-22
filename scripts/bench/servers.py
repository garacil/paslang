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

"""Compare the servers against Go with the same number of self-test clients.

    PATH=bin:$PATH python3 scripts/bench/servers.py [-n runs] [--json out] [--cpu native,base]

Each round alternates which side runs first. The timed run and the separate
traced VmHWM sample must both exit successfully with the complete expected
output. Timed samples use metadata_scope's wall clock and child cleanup.
The JSON record retains every result, including diagnostics and invalid samples.
Each run starts with the connection tracking table of the firewall at
most a quarter full (settle): a run of 10,000 clients leaves 10,000
entries for 120 s (nf_conntrack_tcp_timeout_time_wait), the runs of one
pair fill the 262,144 of this machine, and the kernel then drops every
new packet ("nf_conntrack: table full, dropping packet"): both sides'
dnsd lost datagrams and waited two seconds, an httpd run took 19 s.
"""
import argparse
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import metadata_scope  # noqa: E402
from run import memory_once  # noqa: E402

ROOT = HERE.parent.parent
SRV = HERE / "servers"
OUT = ROOT / "build" / "bench" / "servers"
FORMAT = "paslang-server-bench-v2"
# dnsd stops at 5000: at 10,000 queries in one burst both sides lose
# datagrams to the kernel's receive buffer (rmem_max, 4 MB) and take the
# two-second retry, some runs and not others.
PAIRS = [("httpd", [2000, 10000]), ("dnsd", [2000, 5000]),
         ("termd", [2000, 10000]), ("apisrv", [2000, 10000])]
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
        metadata_scope.check_stop()
        if time.perf_counter() - t > 600:
            raise RuntimeError("the connection tracking table stayed over a quarter full for 600 s")
        time.sleep(1)
    WAITED[0] += time.perf_counter() - t


def expected_output(name, clients):
    if name == "dnsd":
        return f"{clients} clients, {clients} answered, 0 missed, 0 bad\n"
    if name == "termd":
        return f"{clients} sessions, {clients} quit, 0 bad\n"
    requests = clients * 3
    summary = f"{clients} clients, {requests} requests, {requests} served, 0 bad\n"
    if name == "httpd":
        summary += f"stats.json: {clients + 1} connections, {requests + 1} requests, 0 bad\n"
    return summary


def run_one(cmd, env=None, *, timeout=600, memory_timeout=60, row=None, publish=None):
    """Retain the timed outcome and any separate traced sample."""
    row = {} if row is None else row
    command = list(map(str, cmd))
    row.update(command=command, timed=None, memory=None)
    settle()
    with tempfile.TemporaryDirectory(prefix="paslang-server-sample-") as folder:
        scope = Path(folder) / "timed"
        result = metadata_scope.invoke(command, scope, Path.cwd(),
                                       dict(os.environ) if env is None else env, timeout)
        worker_path = scope / "worker-result.json"
        worker = json.loads(worker_path.read_text()) if worker_path.is_file() else {}
        row["timed"] = {"status": result["status"], "wall_s": worker.get("elapsed_s"),
                        "stdout": (scope / "stdout").read_bytes().decode("utf-8", "surrogateescape"),
                        "stderr": (scope / "stderr").read_bytes().decode("utf-8", "surrogateescape"),
                        "cleanup": result["cleanup"], "reason": result.get("reason"),
                        "error": result.get("error")}
    if publish:
        publish()
    if not row["timed"]["cleanup"].get("ok"):
        raise RuntimeError("server sample did not finish cleanup")
    if row["timed"]["status"] == 0:
        settle()
        row["memory"] = memory_once(command[0], env, command[1:],
                                    expected=row["timed"]["stdout"], timeout=memory_timeout)
        if publish:
            publish()
    return row


def positive(value):
    return type(value) in (float, int) and math.isfinite(value) and value > 0


def valid_output(sample, expected):
    return (isinstance(sample, dict) and type(sample.get("status")) is int
            and sample["status"] == 0 and sample.get("stdout") == expected and sample.get("stderr") == "")


def summarize(pair, count):
    """Derive the verdict from the individual timed and traced outcomes."""
    expected = expected_output(pair["pair"], pair["n"])
    rounds = pair["rounds"]
    runtimes = {"go": [], "paslang": []}
    peaks = {"go": [], "paslang": []}
    ratios = []
    exact = type(count) is int and count > 0 and len(rounds) == count
    for number, round_ in enumerate(rounds, 1):
        first = "go" if number % 2 else "paslang"
        complete = round_.get("round") == number and round_.get("first") == first
        for side in runtimes:
            row = round_.get(side) or {}
            timed, memory = row.get("timed"), row.get("memory")
            time_ok = (valid_output(timed, expected) and (timed.get("cleanup") or {}).get("ok") is True
                       and not timed.get("reason") and not timed.get("error"))
            mem_ok = (valid_output(memory, expected) and memory.get("ok") is True
                      and not memory.get("measurement_error"))
            complete = complete and time_ok and mem_ok
            runtimes[side].append(timed["wall_s"] if time_ok and positive(timed.get("wall_s")) else None)
            peaks[side].append(memory["peak_kib"] / 1024 if mem_ok and positive(memory.get("peak_kib")) else None)
        exact = exact and complete
        go, paslang = runtimes["go"][-1], runtimes["paslang"][-1]
        ratios.append(paslang / go if go is not None and paslang is not None else None)
    valid = exact and all(positive(value) for values in (*peaks.values(), ratios) for value in values)
    ratio = statistics.median(ratios) if valid else None
    memory_ratio = statistics.median(peaks["paslang"]) / statistics.median(peaks["go"]) if valid else None
    budget = BUDGET[pair["pair"]]
    if not valid:
        verdict = "INVALID"
    elif ratio > budget or memory_ratio > MEM_BUDGET:
        verdict = "OVER BUDGET"
    else:
        verdict = "PASS"
    return {"go_s": runtimes["go"], "paslang_s": runtimes["paslang"],
            "go_mb": peaks["go"], "paslang_mb": peaks["paslang"], "ratios": ratios,
            "ratio": ratio, "ratio_mem": memory_ratio, "budget": budget,
            "memory_budget": MEM_BUDGET, "same_output": exact, "verdict": verdict}


def median_text(values, places):
    if isinstance(values, list) and values and all(positive(value) for value in values):
        return f"{statistics.median(values):.{places}f}"
    return "-"


def main():
    sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-n", type=int, default=3)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--cpu", default="native,base")
    options = parser.parse_args()
    cpus = options.cpu.split(",")
    if options.n < 1 or not all(cpus) or len(cpus) != len(set(cpus)):
        parser.error("pass a positive round count and distinct CPU names")
    paslangc = shutil.which("paslangc") or ROOT / "bin" / "paslangc"
    record = {"format": FORMAT, "date": time.strftime("%Y-%m-%d %H:%M:%S"),
              "machine": platform.platform(), "runs": options.n, "cpus": cpus, "pairs": [],
              "requested_pairs": len(cpus) * sum(len(loads) for _, loads in PAIRS),
              "completed_pairs": 0, "ok": False}

    def publish():
        record["conntrack_wait_s"] = round(WAITED[0], 1)
        if options.json:
            metadata_scope.save(options.json, record)

    publish()
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        record["cpu"] = next(line.split(":", 1)[1].strip()
                             for line in Path("/proc/cpuinfo").read_text().splitlines()
                             if line.startswith(("model name", "Processor")))
        record["paslangc"] = subprocess.run([paslangc, "-v"], check=True, capture_output=True,
                                           text=True, timeout=60).stdout.splitlines()[0]
        record["go"] = subprocess.run(["go", "version"], check=True, capture_output=True,
                                      text=True, timeout=60).stdout.strip()
        print("pair     cpu        n    go s  paslang s  ratio  go MB  pl MB   mem  verdict")
        with metadata_scope.signal_scope():
            for cpu in cpus:
                for name, loads in PAIRS:
                    metadata_scope.check_stop()
                    paslang = OUT / (name + ("" if cpu == "native" else "." + cpu) + ".pl")
                    go = OUT / (name + ".go.bin")
                    subprocess.run([paslangc, "-cpu", cpu, "-Fu", ROOT / "build", "-o", paslang,
                                    ROOT / "examples" / (name + ".paslang")], check=True, timeout=600)
                    if cpu == cpus[0]:
                        subprocess.run(["go", "build", "-o", go, SRV / (name + ".go")],
                                       check=True, cwd=SRV, timeout=600)
                    genv = dict(os.environ, GODEBUG="cpu.all=off") if cpu == "base" else None
                    for clients in loads:
                        pair = {"pair": name, "cpu": cpu, "n": clients, "rounds": []}
                        record["pairs"].append(pair)
                        commands = {"go": (go, genv), "paslang": (paslang, None)}
                        for number in range(1, options.n + 1):
                            order = ("go", "paslang") if number % 2 else ("paslang", "go")
                            round_ = {"round": number, "first": order[0]}
                            pair["rounds"].append(round_)
                            for side in order:
                                metadata_scope.check_stop()
                                round_[side] = {}
                                publish()
                                exe, env = commands[side]
                                run_one([exe, "-selftest", str(clients)], env,
                                        row=round_[side], publish=publish)
                        pair.update(summarize(pair, options.n))
                        record["completed_pairs"] += 1
                        print(f"{name:8s} {cpu:6s} {clients:6d}  "
                              f"{median_text(pair['go_s'], 3):>6s}  {median_text(pair['paslang_s'], 3):>9s}  "
                              f"{median_text([pair['ratio']], 2):>5s}  {median_text(pair['go_mb'], 1):>5s}  "
                              f"{median_text(pair['paslang_mb'], 1):>5s}  "
                              f"{median_text([pair['ratio_mem']], 2):>5s}  {pair['verdict']}")
                        publish()
        record["ok"] = (record["completed_pairs"] == record["requested_pairs"]
                        and all(pair["verdict"] == "PASS" for pair in record["pairs"]))
    except (Exception, KeyboardInterrupt) as error:
        record["error"] = f"{type(error).__name__}: {error}"
        print(record["error"], file=sys.stderr)
    finally:
        publish()
    print("waited %.0f s for the connection tracking table" % WAITED[0])
    if options.json:
        print("record written to %s" % options.json)
    return 0 if record["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
