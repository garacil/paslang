#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P218: an alignment the emitter writes means bytes on both machines.

GNU as reads .align N as N bytes on x86 but as 2**N on AArch64 (as.info
of binutils 2.47, 7.3), so the emitter's .align 8 put arm64's data at
256 bytes and the heap's .align 16 at 65536: an arm64 program's .bss
was aligned to 64 KiB and up to that much larger than amd64's, and
each string constant and descriptor in .rodata took 256 bytes (sysutils'
.rodata was 166,880 bytes on arm64, 38,944 on amd64). The emitter
writes .balign (bytes on both, 7.8) or .p2align (a power of two, 7.75),
never .align:
- no .s it writes for a program, a unit or a core unit holds .align;
- .data, .rodata and .bss are aligned alike on both machines in the
  objects of a program, of a unit and of every core unit, and in the
  executable (readelf);
- the executable's .bss is the same size on both machines;
- the program, linked with its unit, gives its output on both.
Usage: check_align.py compiler build qemu core-unit-sources...
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path


compiler = str(Path(sys.argv[1]).resolve())
build = Path(sys.argv[2]).resolve()
qemu = sys.argv[3:4]
core_units = [Path(source).stem for source in sys.argv[4:]]
if not qemu or not core_units:
    raise SystemExit("usage: check_align.py compiler build qemu core-unit-sources...")
work = build / "check-align"
if work.exists():
    shutil.rmtree(work)
work.mkdir()
SECTIONS = (".data", ".rodata", ".bss")
ALIGN = re.compile(r"^\s*\.align\b", re.M)


def sections(path):
    """The size and the alignment of .data, .rodata and .bss, from the
    section headers readelf prints: [Nr] Name Type Address Off Size ES
    Flg Lk Inf Al."""
    out = subprocess.run(["readelf", "-SW", str(path)], check=True, capture_output=True,
                         text=True).stdout
    found = {}
    for line in out.splitlines():
        words = line.replace("[ ", "[").split()
        for at, word in enumerate(words):
            if word in SECTIONS and at + 4 < len(words):
                found[word] = (int(words[at + 4], 16), int(words[-1]))
    missing = [name for name in SECTIONS if name not in found]
    if missing:
        raise RuntimeError(f"{path}: no {', '.join(missing)}")
    return found


def no_align(path):
    lines = [str(n) for n, text in enumerate(path.read_text().splitlines(), 1)
             if ALIGN.match(text)]
    if lines:
        raise RuntimeError(f"{path}: .align at line {', '.join(lines[:5])}")


def same_alignment(what, amd, arm):
    for name in SECTIONS:
        if amd[name][1] != arm[name][1]:
            raise RuntimeError(f"{what}: {name} aligned to {amd[name][1]} on amd64 "
                               f"and {arm[name][1]} on arm64")


built = {}
for target in ("amd64", "arm64"):
    core = build if target == "amd64" else build / "a64"
    out = work / target
    out.mkdir()
    unit = out / "clsu"
    program = out / "clsuse"
    subprocess.run([compiler, "-target", target, "-cpu", "base", "-c", "-Fu", str(core),
                    "-o", str(unit), "testdata/units/clsu.paslang"], check=True)
    subprocess.run([compiler, "-target", target, "-cpu", "base", "-Fu", str(out), "-Fu", str(core),
                    "-o", str(program), "testdata/units/clsuse.paslang"], check=True)
    runner = [] if target == "amd64" else qemu
    got = subprocess.run([*runner, str(program)], check=True, capture_output=True,
                         timeout=60).stdout
    want = Path("testdata/units/clsuse.out").read_bytes()
    if got != want:
        raise RuntimeError(f"clsuse {target}: the output differs from testdata/units/clsuse.out")
    for source in (unit, program, *(core / name for name in core_units)):
        no_align(source.with_suffix(".s"))
    built[target] = {"the unit clsu": sections(unit.with_suffix(".o")),
                     "the program clsuse": sections(program.with_suffix(".o")),
                     "the executable clsuse": sections(program),
                     **{f"the core unit {name}": sections(core / f"{name}.o") for name in core_units}}
for what, amd in built["amd64"].items():
    same_alignment(what, amd, built["arm64"][what])
amd, arm = built["amd64"]["the executable clsuse"][".bss"], built["arm64"]["the executable clsuse"][".bss"]
if amd[0] != arm[0]:
    raise RuntimeError(f"the executable clsuse: .bss of {arm[0]} bytes on arm64, {amd[0]} on amd64")
print(f"ok align (no .align in {2 * (2 + len(core_units))} .s files; .data, .rodata and .bss "
      f"aligned alike in {len(built['amd64'])} objects and executables; .bss {amd[0]} bytes on both)",
      flush=True)
shutil.rmtree(work)
