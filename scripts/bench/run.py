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

"""Measure paslang against Go and Rust.

  scripts/bench/run.py            build and run the pairs, print the table, then the probes
  scripts/bench/run.py probes     run the robustness probes only, print status and message
  scripts/bench/run.py -n 5       five alternating rounds per pair (default 3)
  scripts/bench/run.py --scale F  every budget times F (F < 1 shows a failing run)
  scripts/bench/run.py --json P   write every number and the machine's details to P
  scripts/bench/run.py --cpu base build the paslang side for these processors only
                                  (comma-separated; default native,base: Regla 12)
  scripts/bench/run.py --reference go,rust --pairs b1loop,b6smap --go-native-level v3
                                  select the audited twins and separate reference series

The selected-reference mode builds Go separately for base/native and Rust
with opt-level=3. Native Go needs the highest host/OS ISA level reviewed
explicitly. Missing requested tools fail; ordinary project checks use stubs.
Its --json record retains every full timed/memory output and failure. Use
--reference go,rust --help for all selected-mode options. The default command
retains the legacy full Go suite and the CPU policy documented below.

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
binary with a source-bound capability probe and a silent, reviewed CPU
policy. Baseline refuses unsupported REP preferences or uncontrolled
optional ISA fields (reference_policy.py).
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
import math
import select
import signal
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from peak import peak_kib  # noqa: E402
from reference_policy import (go_runtime_environment, go_build_environment,
                              prepare_go_capabilities, go_binary_metadata,
                              require_go_artifact_capabilities)  # noqa: E402
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
         # P211: each operation on each file of Go's corpus, against v2 and v1
         "b37json",
         # P426: XML read token by token (TXmlReader.Next against Decoder.Token)
         "b38xml",
         # P427, P449: DEFLATE at level 6, inflate and many small gzip files against compress/flate
         "b39flate",
         # P433: mail (messages read into a tree, address lists, the composer, encoded words)
         "b40mail",
         # P451: base64 encode and decode of 3 MB against encoding/base64
         "b41base64",
         # P479: HTTP requests read (pashttp's reader against net/http's ReadRequest)
         "b42http",
         # P486: real arithmetic (Doubles in a Mandelbrot loop)
         "b43real",
         # P425: the fused multiply-add (Fma against math.FMA)
         "b44fma",
         # P471: first NIST public-key derivation in a fresh process.
         "b45nist"]
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
    "b20hash": ["md5", "sha1", "sha512", "sha3", "hmac", "hmacp", "sha3p", "crc32", "adler32", "fnv"],
    "b21text": ["hex", "runes"],
    "b22rand": ["own", "below", "real", "global", "globalpar"],
    "b23date": ["stamp", "date", "full"],
    "b24math": ["sin", "exp", "ln", "sqrt", "pow", "atan", "tan", "sinh", "tanh", "asinh", "log1p"],
    "b25exec": ["serial", "par"],
    "b26slice": ["ints", "strings"],
    "b27call": ["iface", "closure", "proc"],
    "b28stack": ["deep", "many"],
    "b29exc": ["raise"],
    "b30gc": ["trees"],
    "b31map": ["iter", "delete", "update", "sums", "bits"],
    "b32fs": ["stat", "list"],
    "b33utf8": ["ascii", "mixed"],
    "b34json": ["parse", "parse1", "compact", "compact1", "pretty", "pretty1", "canonical"],
    "b35bind": ["marshal", "marshal1", "indent", "indent1"],
    "b36unbind": ["unmarshal", "unmarshal1"],
    "b37json": [op + "-" + f
                for op in ["parse", "parse1", "valid", "valid1", "decode", "decode1", "encode", "encode1",
                           "compact", "compact1", "pretty", "pretty1", "canonical", "build"]
                for f in ["canada_geometry", "citm_catalog", "golang_source", "string_escaped",
                          "string_unicode", "synthea_fhir", "twitter_status"]],
    "b38xml": ["tokens"],
    "b39flate": ["deflate", "inflate", "small"],
    "b40mail": ["message", "addr", "build", "words"],
    "b41base64": ["roundtrip"],
    "b42http": ["requests"],
    "b43real": ["mandel"],
    "b44fma": ["horner"],
    "b45nist": ["p256", "p384"],
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
# P211 (1.1.280): b37json, each operation on each file of Go's corpus
# against v2 and v1, fifteen alternating rounds (rounds.py), native and
# base; each section keeps what it won, the larger of its two medians
# plus 0.075 rounded up to 0.05, at most 0.99, then raised to the larger of
# that and the same rule on five rounds of the installed 1.1.280 on a machine
# with other jobs running (every section still below Go's time). The medians,
# native/base,
# the files in _B37F's order:
#   parse     0.61/0.66 0.31/0.36 0.36/0.41 0.49/0.52 0.59/0.66 0.28/0.30 0.40/0.45
#   parse1    0.30/0.33 0.16/0.21 0.18/0.22 0.39/0.35 0.49/0.41 0.15/0.17 0.23/0.26
#   valid     0.89/0.92 0.68/0.77 0.54/0.61 0.73/0.79 0.63/0.67 0.58/0.66 0.50/0.62
#   valid1    0.85/0.93 0.87/0.93 0.85/0.94 0.78/0.85 0.66/0.72 0.74/0.84 0.68/0.85
#   decode    0.69/0.73 0.66/0.69 0.69/0.71 0.52/0.53 0.63/0.65 0.86/0.88 0.74/0.81
#   decode1   0.60/0.68 0.55/0.57 0.62/0.63 0.42/0.42 0.47/0.53 0.73/0.74 0.57/0.64
#   encode    0.89/0.90 0.58/0.57 0.51/0.52 0.53/0.57 0.56/0.63 0.72/0.72 0.60/0.66
#   encode1   0.87/0.89 0.55/0.54 0.49/0.53 0.54/0.56 0.54/0.59 0.72/0.72 0.58/0.65
#   compact   0.32/0.33 0.29/0.32 0.24/0.24 0.49/0.51 0.50/0.54 0.24/0.25 0.28/0.29
#   compact1  0.31/0.32 0.25/0.25 0.20/0.21 0.51/0.53 0.48/0.50 0.20/0.21 0.20/0.23
#   pretty    0.42/0.41 0.35/0.36 0.24/0.30 0.50/0.53 0.51/0.49 0.31/0.34 0.37/0.39
#   pretty1   0.36/0.37 0.30/0.29 0.21/0.24 0.44/0.43 0.44/0.40 0.23/0.24 0.23/0.23
#   canonical 0.82/0.79 0.81/0.88 0.62/0.62 0.46/0.44 0.54/0.56 0.78/0.81 0.69/0.69
#   build     0.86/0.89 0.94/0.93 0.82/0.82 0.54/0.57 0.49/0.51 0.84/0.81 0.79/0.80
_B37F = ["canada_geometry", "citm_catalog", "golang_source", "string_escaped",
         "string_unicode", "synthea_fhir", "twitter_status"]
_B37 = {
    "parse": [0.75, 0.50, 0.70, 0.60, 0.75, 0.50, 0.55],
    "parse1": [0.45, 0.35, 0.40, 0.50, 0.60, 0.35, 0.40],
    "valid": [0.99, 0.90, 0.75, 0.90, 0.75, 0.85, 0.75],
    "valid1": [0.99, 0.99, 0.99, 0.95, 0.80, 0.99, 0.99],
    "decode": [0.85, 0.80, 0.80, 0.65, 0.75, 0.99, 0.90],
    "decode1": [0.80, 0.70, 0.75, 0.50, 0.60, 0.85, 0.75],
    "encode": [0.99, 0.80, 0.75, 0.65, 0.75, 0.95, 0.80],
    "encode1": [0.99, 0.75, 0.75, 0.65, 0.70, 0.99, 0.75],
    "compact": [0.55, 0.45, 0.45, 0.60, 0.65, 0.40, 0.45],
    "compact1": [0.55, 0.40, 0.40, 0.65, 0.60, 0.35, 0.40],
    "pretty": [0.55, 0.45, 0.55, 0.65, 0.60, 0.55, 0.55],
    "pretty1": [0.55, 0.45, 0.50, 0.55, 0.55, 0.45, 0.35],
    "canonical": [0.90, 0.99, 0.80, 0.55, 0.65, 0.99, 0.95],
    "build": [0.99, 0.99, 0.99, 0.80, 0.60, 0.99, 0.90],
}
for _op in _B37:
    for _f, _v in zip(_B37F, _B37[_op]):
        BUDGET["b37json:" + _op + "-" + _f] = _v
# P479 (1.2.304): b42http, 200,000 requests read, nine alternating rounds: 0.69
# native and 0.66 base of net/http's ReadRequest (it was 1.80 and 1.75); the
# larger plus 0.075 rounded up to 0.05.
BUDGET["b42http:requests"] = 0.80
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
        env = go_build_environment(OUT, "base", None)
        env.setdefault("HOME", OUT)
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


GO_CAPABILITIES = None


def go_env(cpu):
    """Legacy runtime selector; capability preparation stays outside samples."""
    global GO_CAPABILITIES
    if cpu == "base" and GO_CAPABILITIES is None:
        import shutil
        compiler = shutil.which("go")
        if compiler is None:
            raise RuntimeError("Go capability preparation requires go on PATH")
        GO_CAPABILITIES = prepare_go_capabilities(compiler, os.path.join(OUT, "go-capabilities"))
    return go_runtime_environment(cpu, capabilities=GO_CAPABILITIES)


def go_artifact_evidence(executable, cpu, record):
    """Retain actual linkage and fail closed before legacy baseline timing."""
    artifacts = record.setdefault("go_artifacts", {})
    if executable not in artifacts:
        artifacts[executable] = go_binary_metadata(executable)
    observation = {"executable": executable, "cpu": cpu, "ok": False}
    record.setdefault("go_artifact_evidence", []).append(observation)
    try:
        observation["capability_evidence"] = require_go_artifact_capabilities(cpu, artifacts[executable])
    except ValueError as error:
        observation["refusal"] = str(error)
        raise
    observation["ok"] = True
    return observation


def fail_legacy_record(record, destination, error):
    """A refused old-style invocation must replace any prior success JSON."""
    record.update(ok=False, error=str(error))
    if destination:
        import json
        os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
        with open(destination, "w") as target:
            json.dump(json_values(record), target, indent=1, allow_nan=False)
    raise SystemExit(str(error))


def peak_mb(exe, env=None, runs=MEM_RUNS, args=()):
    """Compatibility API; retain and validate every complete memory output."""
    rows = []
    expected = None
    for index in range(runs):
        row = memory_once(exe, env, args, expected)
        row["round"] = index + 1
        rows.append(row)
        if expected is None:
            expected = row["stdout"]
    LAST_MEMORY[(exe, tuple(args))] = rows
    if not all(row["ok"] for row in rows):
        raise RuntimeError(f"memory run failed: {exe} {args}; see LAST_MEMORY")
    peaks = sorted(row["peak_kib"] / 1024 for row in rows)
    return median(peaks), peaks


def memory_once(exe, env=None, args=(), expected=None):
    with tempfile.TemporaryFile() as so, tempfile.TemporaryFile() as se:
        kib, status, problem = -1, "measurement-error", None
        try:
            kib, status = peak_kib([exe, *args], env=env, stdout=so.fileno(),
                                   stderr=se.fileno(), timeout=TIMEOUT)
        except (OSError, RuntimeError) as error:
            problem = str(error)
        so.seek(0)
        se.seek(0)
        answer = so.read().decode("utf-8", "surrogateescape")
        error = se.read().decode("utf-8", "surrogateescape")
    return {"peak_kib": kib, "status": status, "stdout": answer, "stderr": error,
            "measurement_error": problem,
            "ok": status == 0 and kib > 0 and not error and (expected is None or answer == expected)}


def memory_pair(a, b, n, env_a, env_b, args, expected_a, expected_b, *, rows_a=None, rows_b=None):
    """Independent traced samples, alternating order as in timed rounds."""
    if n < 1:
        raise ValueError("memory rounds must be positive")
    rows_a = [] if rows_a is None else rows_a
    rows_b = [] if rows_b is None else rows_b
    LAST_MEMORY[(a, tuple(args))] = rows_a
    LAST_MEMORY[(b, tuple(args))] = rows_b
    def observe(exe, env, expected, rows, index):
        row = {"round": index + 1, "first": "a" if index % 2 == 0 else "b",
               "status": "interrupted", "ok": False}
        rows.append(row)
        try:
            row.update(memory_once(exe, env, args, expected))
        except BaseException as error:
            row["measurement_error"] = type(error).__name__ + ": " + str(error)
            raise
        return row
    for index in range(n):
        if index % 2 == 0:
            ra = observe(a, env_a, expected_a, rows_a, index)
            rb = observe(b, env_b, expected_b, rows_b, index)
        else:
            rb = observe(b, env_b, expected_b, rows_b, index)
            ra = observe(a, env_a, expected_a, rows_a, index)
        if ra["status"] == "timeout" or rb["status"] == "timeout":
            break
    valid = len(rows_a) == n and all(row["ok"] for row in rows_a + rows_b)
    ma = median([row["peak_kib"] / 1024 for row in rows_a]) if valid else None
    mb = median([row["peak_kib"] / 1024 for row in rows_b]) if valid else None
    return ma, mb, rows_a, rows_b


def units(names=None):
    """The (program, section) pairs to measure, section None for a program
    without sections."""
    return [(b, sec) for b in (names or PAIRS) for sec in SECTIONS.get(b, [None])]


def unit_name(b, sec):
    return b if sec is None else b + ":" + sec


def once(exe, env=None, args=()):
    """Wall seconds, exit status and complete stdout, including final newlines.

    Decode with surrogateescape so comparison preserves even non-UTF-8 bytes.
    stderr is retained separately in LAST_ONCE, not merged with the answer.
    """
    with tempfile.TemporaryFile() as so, tempfile.TemporaryFile() as se:
        t = time.perf_counter()
        p = subprocess.Popen([exe, *args], stdout=so, stderr=se, env=env,
                             start_new_session=True)
        fd = None
        try:
            # pidfd polling avoids Popen.wait(timeout)'s sleep granularity.
            fd = os.pidfd_open(p.pid)
            poller = select.poll()
            poller.register(fd, select.POLLIN)
            deadline = time.monotonic() + TIMEOUT
            ended = []
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                # poll(2) accepts signed-int milliseconds. Keep the absolute
                # deadline while bounding each individual kernel wait.
                ended = poller.poll(max(1, math.ceil(min(remaining, 2_147_483) * 1000)))
                if ended:
                    break
            if not ended or time.monotonic() >= deadline:
                wall, status = float("inf"), "timeout"
            else:
                _, st = os.waitpid(p.pid, 0)
                wall = time.perf_counter() - t
                p.returncode = status = os.waitstatus_to_exitcode(st)
        finally:
            if fd is not None:
                os.close(fd)
            if p.returncode is None:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                p.wait()
        so.seek(0); se.seek(0)
        out = so.read().decode("utf-8", "surrogateescape")
        err = se.read().decode("utf-8", "surrogateescape")
    LAST_ONCE[(exe, tuple(args))] = {"wall_s": wall, "status": status,
                                    "stdout": out, "stderr": err}
    return wall, status, out


def alternate(a, b, n, env_a=None, env_b=None, args=(), *, rows=None):
    """n rounds of the programs a and b, alternating which runs first.
    Gives each side's median wall seconds, accumulated status and complete
    stdout, and the median of the rounds' ratios, b's
    time over a's. On a machine that runs anything else a median of
    separate runs moved by up to 30 % from one batch to the next; a
    round's two programs share the machine's state of that moment."""
    if n < 1:
        raise ValueError("timed rounds must be positive")
    wa, wb, ratios = [], [], []
    rows = [] if rows is None else rows
    LAST_ROUNDS[(a, b, tuple(args))] = rows
    LAST_RATIOS[(a, b, tuple(args))] = ratios
    LAST_WALLS[(a, tuple(args))] = wa
    LAST_WALLS[(b, tuple(args))] = wb
    sa, oa, sb, ob = 0, None, 0, None
    def observe(exe, env, side, row):
        row[side] = {"status": "interrupted"}
        try:
            result = once(exe, env, args)
        except BaseException as error:
            row["errors"].append(type(error).__name__ + ": " + str(error))
            raise
        row[side] = dict(LAST_ONCE[(exe, tuple(args))])
        return result
    for r in range(n):
        row = {"round": r + 1, "first": "a" if r % 2 == 0 else "b",
               "completed": False, "errors": []}
        rows.append(row)
        if r % 2 == 0:
            ta, xa, ya = observe(a, env_a, "a", row)
            tb, xb, yb = observe(b, env_b, "b", row)
        else:
            tb, xb, yb = observe(b, env_b, "b", row)
            ta, xa, ya = observe(a, env_a, "a", row)
        wa.append(ta)
        wb.append(tb)
        ratios.append(tb / ta if ta > 0 and xa != "timeout" and xb != "timeout" else float("inf"))
        sa = sa or xa
        sb = sb or xb
        reasons = row["errors"]
        if xa != 0 or xb != 0:
            reasons.append("nonzero status or timeout")
        if row["a"]["stderr"] or row["b"]["stderr"]:
            reasons.append("unexpected stderr")
        if ya != yb:
            reasons.append("complete stdout differs")
        if oa is not None and ya != oa:
            reasons.append("first program stdout changed between rounds")
        if ob is not None and yb != ob:
            reasons.append("second program stdout changed between rounds")
        row["completed"] = True
        if oa is None:
            oa = ya
        if ob is None:
            ob = yb
        if xa == "timeout" or xb == "timeout":
            break
    LAST_WALLS[(a, tuple(args))] = sorted(wa)
    LAST_WALLS[(b, tuple(args))] = sorted(wb)
    LAST_RATIOS[(a, b, tuple(args))] = list(ratios)
    LAST_ROUNDS[(a, b, tuple(args))] = rows
    return (median(wa), sa, oa), (median(wb), sb, ob), median(ratios)


def median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2


def json_values(value):
    """Keep missing/non-finite measurements valid JSON, with status evidence."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: json_values(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_values(item) for item in value]
    return value


LAST_RATIOS = {}
LAST_WALLS = {}
LAST_PEAKS = {}
LAST_MEMORY = {}
LAST_ONCE = {}
LAST_ROUNDS = {}
LAST_CHECKPTR = []


def machine():
    """The hardware, kernel and toolchain a run happened on, for the record."""
    def out(cmd, env=None):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, errors='surrogateescape', timeout=15, env=env).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
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
                         "go": out(["go", "version"], env=go_build_environment(OUT, "base", None)), "as": out(["as", "--version"]).splitlines()[:1],
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
        rounds = LAST_ROUNDS[(pl_path(b, cpu), pl_path(b, cpu, ".cp"), ())]
        same = "yes" if (len(rounds) == n and not any(r["errors"] for r in rounds)
                         and cp_out == pl_out and cs == 0 and ps == 0) else "NO (see round errors)"
        flag = "  OVER BUDGET" if ratio > budget else ""
        bad += bool(flag) or same != "yes"
        LAST_CHECKPTR.append({"pair": b, "cpu": cpu, "ratio": ratio,
                              "budget": budget, "same_output": same == "yes",
                              "rounds": rounds, "over": flag.strip()})
        print(f"{b:10s} {cpu:6s} -checkptr {cw:7.3f} s, {ratio:5.1f} times the plain build (budget {budget:.1f})  same output: {same}{flag}")
    return bad


def probes():
    print(f"{'probe':12s} {'status':>7s}  message")
    for p in PROBES:
        build(p, go=False)
        exe = os.path.join(OUT, p + ".pl")
        w, st, output = once(exe)
        message = output or LAST_ONCE[(exe, ())]["stderr"]
        first = message.splitlines()[0] if message else ""
        print(f"{p:12s} {str(st):>7s}  {first}")


def stages(cpus):
    """JSON's stages one at a time (P211): k12json built for each
    processor, on the corpus prepare() writes, its lines as it prints them."""
    prepare()
    for cpu in cpus:
        build("k12json", go=False, cpu=cpu)
        print(f"-cpu {cpu}")
        p = subprocess.run([pl_path("k12json", cpu)], capture_output=True, text=True, cwd=ROOT)
        print(p.stdout, end="")
        if p.returncode != 0:
            sys.exit(p.stderr)


def main():
    if sys.argv[1:] in (["--help"], ["-h"]):
        print(__doc__)
        return 0
    if any(option.split("=", 1)[0] in
           ("--reference", "--pairs", "--memory-runs", "--go-native-level", "--no-build", "--timeout",
            "--rust-target", "--rust-sysroot", "--rust-provider", "--rust-capability-proof")
           for option in sys.argv[1:]):
        from run_refs import main as reference_main
        return reference_main(sys.argv[1:])
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
    if not math.isfinite(scale) or not 0 < scale <= 1:
        raise SystemExit("--scale must be positive and at most 1; budgets cannot be relaxed")
    if n < 1 or not cpus or set(cpus) - {"native", "base"}:
        raise SystemExit("positive rounds and --cpu native,base are required")
    if args not in ([], ["probes"], ["stages"]):
        raise SystemExit("unknown arguments: " + " ".join(args))
    record = {"machine": machine(), "runs_per_program": n, "scale": scale, "cpus": cpus, "pairs": [], "checkptr": []}
    if args == ["probes"]:
        probes()
        return
    if args == ["stages"]:
        stages(cpus)
        return
    bad = 0
    if "base" in cpus:
        go_env("base")
        record["go_capabilities"] = GO_CAPABILITIES
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
            try:
                go_artifact_evidence(gexe, cpu, record)
            except ValueError as error:
                fail_legacy_record(record, json_path, error)
            (gw, gs, go_out), (pw, ps, pl_out), ratio = alternate(gexe, pexe, n, go_env(cpu), None, args)
            round_rows = LAST_ROUNDS[(gexe, pexe, args)]
            # Failed/incomplete timed rounds have no memory verdict. Keep
            # their full diagnostics instead of rerunning them as valid peaks.
            ended = (gs == 0 and ps == 0 and len(round_rows) == n
                     and not any(r["errors"] for r in round_rows))
            if ended:
                gr, pr, gm, pm = memory_pair(gexe, pexe, MEM_RUNS, go_env(cpu), None,
                                             args, go_out, pl_out)
                memory_ok = gr is not None and pr is not None
                gpeaks = [r["peak_kib"] / 1024 for r in gm]
                ppeaks = [r["peak_kib"] / 1024 for r in pm]
                mem = pr / gr if memory_ok and gr > 0 else float("inf")
                gr, pr = gr or 0.0, pr or 0.0
            else:
                gr, gpeaks, pr, ppeaks, mem = 0.0, [], 0.0, [], 0.0
                gm, pm, memory_ok = [], [], False
            budget = BUDGET[name] * scale
            same = "yes" if (len(round_rows) == n and not any(r["errors"] for r in round_rows)
                             and memory_ok and go_out == pl_out and gs == 0 and ps == 0) else "NO (see round errors)"
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
                                    "rounds": round_rows,
                                    "go_memory": gm, "paslang_memory": pm,
                                    "ratio_time": ratio, "ratio_mem": mem, "budget": budget, "same_output": same == "yes",
                                    "over": flag.strip()})
    print()
    for cpu in cpus:
        bad += checkptr(n, scale, cpu)
    record["checkptr"] = list(LAST_CHECKPTR)
    print()
    probes()
    if json_path:
        import json
        record["machine"]["load_after"] = open("/proc/loadavg").read().strip()
        with open(json_path, "w") as f:
            json.dump(json_values(record), f, indent=1, allow_nan=False)
        print(f"record written to {json_path}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    # The shared reference driver imports this module for the same state.
    sys.modules.setdefault("run", sys.modules[__name__])
    sys.exit(main())
