#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""The QEMU the arm64 tests run under (P226): qemu-aarch64, user mode.

Built from the signed QEMU release, kept in docs/ref/qemu (fetched from
download.qemu.org the first time and checked against its SHA-256 every
time; the signature was checked with the release key, Michael Roth's,
CEAC C9E1 5534 EBAB B82D 3FA0 3353 C9CE F108 B584), with the patches of
scripts/qemu applied in order: QEMU 11.1.1 deadlocks a guest that forks
while another of its threads makes a system call with a pointer,
answers EINVAL to MADV_GUARD_INSTALL, starts a thread with every host
signal blocked (P302), and changes gdb's breakpoints while the other
threads walk them, dying of its own SIGSEGV (P349). Only the tests need
it; it needs a C compiler, Python, meson, ninja and glib's headers, as
QEMU does.
usage: build_qemu.py BUILDDIR TARBALL
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

VERSION = "11.1.1"
URL = f"https://download.qemu.org/qemu-{VERSION}.tar.xz"
SHA256 = "079ffbff8a7111bbc89022107cbabf3bbfd614d5fc9d7cc675991196aca12482"

build = Path(sys.argv[1]).resolve()
tarball = Path(sys.argv[2]).resolve()
patches = sorted(Path(__file__).resolve().parent.joinpath("qemu").glob("*.patch"))
source = build / f"qemu-{VERSION}"
objects = build / "qemu-build"
log = build / "qemu-build.log"


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def run(command, cwd):
    with open(log, "a") as out:
        out.write(f"$ {' '.join(map(str, command))}\n")
        out.flush()
        result = subprocess.run(list(map(str, command)), cwd=cwd, stdout=out, stderr=subprocess.STDOUT)
    if result.returncode:
        raise SystemExit(f"build_qemu: {command[0]} failed, see {log}")


if not tarball.exists():
    tarball.parent.mkdir(parents=True, exist_ok=True)
    part = tarball.with_name(tarball.name + ".part")
    print(f"qemu: fetching {URL}", flush=True)
    with urllib.request.urlopen(URL, timeout=60) as response, open(part, "wb") as out:
        shutil.copyfileobj(response, out, 1 << 20)
    if digest(part) != SHA256:
        part.unlink()
        raise SystemExit(f"build_qemu: {URL} does not have the SHA-256 it should")
    part.rename(tarball)
if digest(tarball) != SHA256:
    raise SystemExit(f"build_qemu: {tarball} does not have the SHA-256 of QEMU {VERSION}")

log.write_text("")
for d in (source, objects):
    if d.exists():
        shutil.rmtree(d)
run(["tar", "-xJf", tarball, "-C", build], build)
for patch in patches:
    run(["patch", "-p1", "--forward", "--batch", "-i", patch], source)
objects.mkdir()
run([source / "configure", "--target-list=aarch64-linux-user", "--disable-system", "--disable-tools",
     "--disable-docs", "--disable-werror", "--disable-plugins", "--disable-capstone"], objects)
run(["ninja", "qemu-aarch64"], objects)
made = build / "qemu-aarch64.new"
shutil.copy2(objects / "qemu-aarch64", made)
os.replace(made, build / "qemu-aarch64")
shutil.rmtree(source)
shutil.rmtree(objects)
print(f"qemu: qemu-aarch64 {VERSION} with {len(patches)} patches ({', '.join(p.name for p in patches)})",
      flush=True)
