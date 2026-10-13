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

"""The bootstrap seed of paslangc (P262, Regla 15): the assembly that
paslangc writes for itself, for one machine, and the line that links it,
so a machine without any paslangc builds one with GNU as and ld alone,
the tools paslang needs anyway. No other compiler is involved, as Go
builds itself with an earlier Go (golang/src/cmd/dist/README).

    scripts/bootstrap_seed.py make --compiler bin/paslangc --arch amd64 \\
        --out bootstrap/seed-amd64.tar.xz -- UNIT.paslang ... cmd/paslangc/paslangc.paslang
    scripts/bootstrap_seed.py build --seed bootstrap/seed-amd64.tar.xz --out DIR \
        [--as AS --ld LD --run WRAPPER]

make compiles every unit given (the core units first, then the
compiler's), for -cpu base, then the program, the last file, and packs
each .s, the link script and the link line paslangc used (its .link
file, one argument a line) with a manifest: the version, the machine,
the files in order and the SHA-256 of each. build unpacks a seed into
DIR, checks every SHA-256, assembles each .s as paslangc does (as --64
-g on amd64, as -g on arm64) and links them with that line, giving
DIR/paslangc, and runs it with -v to show the version it is. --as and
--ld name other tools (the arm64 seed on an amd64 machine takes
aarch64-linux-gnu-as and -ld) and --run a wrapper to run the result
with (qemu-aarch64).
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit("bootstrap_seed: %s failed\n%s%s" % (" ".join(cmd), p.stdout, p.stderr))
    return p.stdout


def make(compiler, arch, out, sources):
    if not sources:
        sys.exit("bootstrap_seed: make needs the units and the program after --")
    target = ["-target", "arm64"] if arch == "arm64" else []
    version = run([compiler, "-v"])
    with tempfile.TemporaryDirectory(prefix="paslang-seed-") as tmp:
        work = Path(tmp)
        for src in sources[:-1]:
            name = Path(src).stem
            run([compiler] + target + ["-cpu", "base", "-c", "-Fu", str(work), "-o", str(work / name), src])
        prog = Path(sources[-1]).stem
        run([compiler] + target + ["-cpu", "base", "-Fu", str(work), "-o", str(work / prog), sources[-1]])
        link = (work / (prog + ".link")).read_text().split("\n")
        link = [a for a in link if a != ""]
        objs, args = [], []
        for a in link:
            if a.endswith(".o"):
                base = Path(a).name
                objs.append(base[:-2])
                args.append(base)
            elif a.endswith(".ld"):
                args.append("link.ld")
            elif a == str(work / prog):
                args.append("paslangc")
            else:
                args.append(a)
        files = {}
        for o in objs:
            files[o + ".s"] = (work / (o + ".s")).read_bytes()
        files["link.ld"] = (work / (prog + ".ld")).read_bytes()
        found = re.search(r"\d+\.\d+\.\d+", version)
        manifest = {"version": found.group(0) if found else "",
                    "arch": arch, "assemble": [o + ".s" for o in objs], "link": args,
                    "sha256": {n: sha(d) for n, d in sorted(files.items())}}
        files["manifest.json"] = (json.dumps(manifest, indent=1) + "\n").encode()
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(out, "w:xz", preset=9) as tar:
            for name in sorted(files):
                info = tarfile.TarInfo(name)
                info.size = len(files[name])
                info.mode = 0o644
                info.mtime = 0
                tar.addfile(info, io.BytesIO(files[name]))
    print("bootstrap_seed: %s, %d units, %d bytes" % (out, len(objs), os.path.getsize(out)))


def build(seed, out, as_bin="as", ld_bin="ld", wrapper=None):
    dest = Path(out)
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(seed, "r:xz") as tar:
        names = tar.getnames()
        for n in names:
            if "/" in n or n.startswith(".") or n == "":
                sys.exit("bootstrap_seed: %s holds a path that is not a plain name: %r" % (seed, n))
        tar.extractall(dest, filter="data")
    manifest = json.loads((dest / "manifest.json").read_text())
    for n, h in manifest["sha256"].items():
        if sha((dest / n).read_bytes()) != h:
            sys.exit("bootstrap_seed: %s does not match its SHA-256" % n)
    arm = manifest["arch"] == "arm64"
    for s in manifest["assemble"]:
        o = s[:-2] + ".o"
        if arm:
            run([as_bin, "-g", "-o", o, s], cwd=dest)
        else:
            run([as_bin, "--64", "-g", "-o", o, s], cwd=dest)
    run([ld_bin] + manifest["link"], cwd=dest)
    cmd = ([wrapper] if wrapper else []) + [str(dest / "paslangc"), "-v"]
    got = re.search(r"\d+\.\d+\.\d+", run(cmd))
    if not got or got.group(0) != manifest["version"]:
        sys.exit("bootstrap_seed: the compiler built from %s says %s, the seed %s" % (
            seed, got.group(0) if got else "nothing", manifest["version"]))
    print("bootstrap_seed: %s from %s with %s and %s" % (got.group(0), seed, as_bin, ld_bin))


def main(argv):
    if not argv or argv[0] not in ("make", "build"):
        sys.exit(__doc__)
    opts, rest = {}, []
    i = 1
    while i < len(argv):
        if argv[i] == "--":
            rest = argv[i + 1:]
            break
        if argv[i].startswith("--") and i + 1 < len(argv):
            opts[argv[i][2:]] = argv[i + 1]
            i += 2
            continue
        sys.exit("bootstrap_seed: unknown argument " + argv[i])
    if argv[0] == "make":
        make(opts["compiler"], opts.get("arch", "amd64"), opts["out"], rest)
    else:
        build(opts["seed"], opts["out"], opts.get("as", "as"), opts.get("ld", "ld"), opts.get("run"))


if __name__ == "__main__":
    main(sys.argv[1:])
