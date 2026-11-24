#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned.
# GPL version 3 or later. See COPYING.

"""Close and reuse a descriptor at two explicit poller scheduling boundaries."""

import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import mkdtemp

ROOT = Path(__file__).resolve().parents[1]


def insert(source, marker, replacement):
    if source.count(marker) != 1:
        raise RuntimeError(f"poll fixture checkpoint missing or ambiguous: {marker!r}")
    return source.replace(marker, replacement, 1)


def instrument(source):
    source = insert(source, "\nimplementation\n", """
var
  PollTestFd, PollTestLeader, PollTestQueued, PollTestPromoted, PollTestResume: Integer;
  PollTestSetup, PollTestResumeSetup: Integer;

implementation
""")
    lead = "      Result := PollPark(Fd, Ev, Deadline, nil, 0, @r^.Spin);"
    source = insert(source, lead,
                    "      if Fd = PollTestFd then AtomicStore(PollTestLeader, 1);\n" + lead)
    queue = "    Result := PollPark(-1, 0, Deadline, nil, 0, @r^.Spin);"
    source = insert(source, queue,
                    "    if Fd = PollTestFd then AtomicStore(PollTestQueued, 1);\n" + queue)
    handoff = "    PollUnlink(r^.Head[d], node);\n    SpinUnlock(@r^.Spin);"
    source = insert(source, handoff, handoff + """
    if turn and (Fd = PollTestFd) then
    begin
      AtomicStore(PollTestPromoted, 1);
      while AtomicLoad(PollTestResume) = 0 do Sleep(1);
    end;""")
    setup = "        SpinUnlock(@r^.Spin);\n        if not linked then"
    return insert(source, setup, """        SpinUnlock(@r^.Spin);
        if linked and (Fds[i] = PollTestFd) then
        begin
          AtomicStore(PollTestSetup, 1);
          while AtomicLoad(PollTestResumeSetup) = 0 do Sleep(1);
        end;
        if not linked then""")


def main():
    compiler, build, qemu = map(lambda arg: Path(arg).resolve(), sys.argv[1:])
    work = Path(mkdtemp(prefix="poll-generations-", dir=build))
    core = re.search(r"^CORE_UNITS :=.*?\n\n", (ROOT / "Makefile").read_text(), re.M | re.S)
    units = re.findall(r"src/lib/\w+\.paslang", core.group())
    units += ["src/lib/paslinux.paslang", "src/lib/paslib.paslang", "src/lib/pasnet.paslang"]
    source = work / "pasroutines.paslang"
    source.write_text(instrument((ROOT / "src/lib/pasroutines.paslang").read_text()))

    for arch in ("amd64", "arm64"):
        out = work / arch
        out.mkdir()
        sdk = build if arch == "amd64" else build / "a64"
        options = [compiler, "-target", arch, "-cpu", "base", "-Fu", out, "-Fu", sdk]
        for unit in units:
            name = Path(unit).stem
            path = source if name == "pasroutines" else ROOT / unit
            subprocess.run(options + ["-c", "-o", out / name, path], check=True, timeout=120)
        executable = out / "pollgenerations"
        subprocess.run(options + ["-o", executable, ROOT / "scripts/fixtures/poll_generations.paslang"],
                       check=True, timeout=120)
        linked = executable.with_suffix(".link").read_text().splitlines()
        if str(out / "pasroutines.o") not in linked:
            raise RuntimeError("poll probe did not link the instrumented unit")
        argv = [executable] if arch == "amd64" else [qemu, "-cpu", "cortex-a53", executable]
        outcome = subprocess.run(argv, env=os.environ | {"PASLANG_MAXPROCS": "2"},
                                 capture_output=True, text=True, timeout=30)
        if (outcome.returncode, outcome.stdout, outcome.stderr) != (0, "ok poll generations\n", ""):
            raise RuntimeError(f"{arch} poll generations: {outcome}")
        print(f"{arch} poll generations: queued wait and WaitAny setup both rejected a reused number")


if __name__ == "__main__":
    main()
