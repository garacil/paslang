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

"""The compiler against go build (P223, Regla 12: the compiler itself
is one of the things that must be faster than Go's).

  PATH=bin:$PATH scripts/bench/build.py [-n rounds] [--json path]

It writes the same program in both languages: N functions, each a loop
of ten steps of shifts, xors and a multiplication, a test, a call of
IntToStr (strconv.Itoa) and a constant of its own, and a main that calls
them all and prints the sum. Each round builds both, alternating which
goes first, and takes the ratio of the wall times (paslangc -o against
go build -o, both to a linked executable). Go's standard library stays
in its cache (build/bench/gocache), as it is for anyone who has built
before; a constant of main changes every round on both sides, so go
build compiles the program again rather than taking it from its cache.
The constants are random: the cache outlives the run, and with the same
constants in every run (1000 + the round, until 2026-10-13) the second
run's go build found its first rounds there and took 0.16 s for 1.1 s.
Both executables run once and must print the same. The exit status is 1
when the median ratio passes BUDGET or the middle half reaches 1.00.
"""
import json
import os
import random
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "build", "bench", "compile")
N = 3000
BUDGET = 0.99


def paslang_source(nonce):
    out = ["program gen;", "", "uses", "  sysutils;", ""]
    for k in range(N):
        out += ["function F%d(X: Integer): Integer;" % k,
                "var",
                "  i, s: Integer;",
                "begin",
                "  s := X;",
                "  for i := 1 to 10 do",
                "    s := ((s * 3 + i) xor (s shr 2)) and $FFFFFFFF;",
                "  if s mod 7 = 0 then",
                "    s := s + Length(IntToStr(s));",
                "  Result := s + %d;" % k,
                "end;", ""]
    out += ["var", "  t: Integer;", "", "begin", "  t := %d;" % nonce]
    out += ["  t := t + F%d(%d);" % (k, k + 1) for k in range(N)]
    out += ["  WriteLn(t);", "end."]
    return "\n".join(out) + "\n"


def go_source(nonce):
    out = ["package main", "", 'import (', '\t"fmt"', '\t"strconv"', ')', ""]
    for k in range(N):
        out += ["func f%d(x int) int {" % k,
                "\ts := x",
                "\tfor i := 1; i <= 10; i++ {",
                "\t\ts = ((s*3 + i) ^ (s >> 2)) & 0xFFFFFFFF",
                "\t}",
                "\tif s%7 == 0 {",
                "\t\ts += len(strconv.Itoa(s))",
                "\t}",
                "\treturn s + %d" % k,
                "}", ""]
    out += ["func main() {", "\tt := %d" % nonce]
    out += ["\tt += f%d(%d)" % (k, k + 1) for k in range(N)]
    out += ["\tfmt.Println(t)", "}"]
    return "\n".join(out) + "\n"


def timed(cmd, cwd, env=None):
    t = time.perf_counter()
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit("%s\n%s" % (" ".join(cmd), p.stderr[-2000:]))
    return time.perf_counter() - t


def main():
    sys.stdout.reconfigure(line_buffering=True)
    rounds, out = 8, None
    a = sys.argv[1:]
    while a:
        if a[0] == "-n":
            rounds = int(a[1]); a = a[2:]
        elif a[0] == "--json":
            out = a[1]; a = a[2:]
        else:
            sys.exit("build.py: unknown argument " + a[0])
    pdir, gdir = os.path.join(OUT, "pl"), os.path.join(OUT, "go")
    os.makedirs(pdir, exist_ok=True)
    os.makedirs(gdir, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("HOME", OUT)
    env["GOCACHE"] = os.path.join(ROOT, "build", "bench", "gocache")
    env["GOFLAGS"] = "-mod=mod"
    if not os.path.exists(os.path.join(gdir, "go.mod")):
        subprocess.run(["go", "mod", "init", "gen"], cwd=gdir, env=env, check=True, capture_output=True)
    psrc, gsrc = os.path.join(pdir, "gen.paslang"), os.path.join(gdir, "main.go")
    pexe, gexe = os.path.join(pdir, "gen"), os.path.join(gdir, "gen")
    # The standard library into Go's cache first, as for anyone who has built before.
    with open(gsrc, "w") as f:
        f.write(go_source(0))
    timed(["go", "build", "-o", gexe, "."], gdir, env)
    tp, tg, ratios = [], [], []
    base = random.SystemRandom().randrange(1 << 40) * 1000
    for r in range(rounds):
        nonce = base + r
        with open(psrc, "w") as f:
            f.write(paslang_source(nonce))
        with open(gsrc, "w") as f:
            f.write(go_source(nonce))
        if r % 2 == 0:
            a1 = timed(["paslangc", "-o", pexe, psrc], ROOT)
            b1 = timed(["go", "build", "-o", gexe, "."], gdir, env)
        else:
            b1 = timed(["go", "build", "-o", gexe, "."], gdir, env)
            a1 = timed(["paslangc", "-o", pexe, psrc], ROOT)
        tp.append(a1)
        tg.append(b1)
        ratios.append(a1 / b1)
    po = subprocess.run([pexe], capture_output=True, text=True).stdout.strip()
    go = subprocess.run([gexe], capture_output=True, text=True).stdout.strip()
    q = statistics.quantiles(ratios, n=4) if len(ratios) > 1 else [ratios[0]] * 3
    med = statistics.median(ratios)
    flag = ""
    if med > BUDGET:
        flag += "  OVER BUDGET"
    if q[2] >= 1.0:
        flag += "  NOT FASTER"
    same = po == go and po != ""
    print("compile %d functions: paslangc %.3f s, go build %.3f s, ratio %.3f (middle half %.3f to %.3f), "
          "budget %.2f, same output %s%s" % (N, statistics.median(tp), statistics.median(tg), med, q[0], q[2],
                                             BUDGET, "yes" if same else "NO (%r vs %r)" % (po, go), flag))
    if out:
        with open(out, "w") as f:
            json.dump({"functions": N, "rounds": rounds, "paslang_s": tp, "go_s": tg, "ratios": ratios,
                       "ratio_median": med, "q1": q[0], "q3": q[2], "budget": BUDGET, "same_output": same,
                       "over": flag.strip()}, f, indent=1)
        print("record written to " + out)
    sys.exit(1 if flag or not same else 0)


if __name__ == "__main__":
    main()
