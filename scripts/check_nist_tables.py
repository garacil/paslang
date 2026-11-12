#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P471: generated constants, independently recomputed points and selectors.

Private views append the reference probe to the production unit. Four actual
unit defects must fail after an independent valid-point control passes.
Production source and exported interfaces are never modified by this check.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time

repo = Path(__file__).resolve().parents[1]
compiler, build, qemu = (Path(v).resolve() for v in sys.argv[1:])
root = Path(tempfile.mkdtemp(prefix="nist-tables-", dir=build))
source_path = repo / "src/lib/pasnist.paslang"
source = source_path.read_text()
fixture = repo / "scripts/fixtures/nist_tables_reference.paslang"
frozen = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in (compiler, source_path, fixture, Path(__file__),
                    repo / "scripts/nist_tables.py")}
base = {k: v for k, v in os.environ.items() if not k.startswith("PASLANG_GC")}
stress = dict(base, PASLANG_GCVERIFY="1", PASLANG_GCSTRESS="1", PASLANG_GCPOISON="1")
state = {"ok": False, "complete": False, "inputs": frozen, "commands": []}
expected = b"control\nP256 1376 entries\nP384 1440 entries; 1536 selections\n"


def save():
    (root / "status.json").write_text(json.dumps(state, indent=2) + "\n")


def guard():
    for name, digest in frozen.items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest, name


def run(label, args, cwd, *, code=0, want=None, env=base):
    guard()
    args = list(map(str, args))
    row = {"label": label, "argv": args, "cwd": str(cwd), "exit": None,
           "expected_exit": code,
           "environment": {k: v for k, v in env.items() if k.startswith("PASLANG_GC")}}
    state["commands"].append(row)
    save()
    start = time.monotonic()
    process = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=env, start_new_session=True)
    try:
        out, err = process.communicate(timeout=240)
    except subprocess.TimeoutExpired:
        row["timeout"] = True
        os.killpg(process.pid, signal.SIGKILL)
        out, err = process.communicate(timeout=20)
    row.update(exit=process.returncode, wall_s=time.monotonic() - start)
    (root / (label + ".stdout")).write_bytes(out)
    (root / (label + ".stderr")).write_bytes(err)
    save()
    assert not row.get("timeout") and row["exit"] == code, (label, out, err)
    assert want is None or out == want, (label, out, want)
    guard()
    return out


def corrupt_table(text, bits):
    at = text.index("  P" + str(bits) + "GenTables:")
    literal = re.search(r"\$[0-9A-F]{16}", text[at:])
    assert literal
    first, last = at + literal.start(), at + literal.end()
    value = int(text[first + 1:last], 16) ^ 1
    return text[:first] + "$%016X" % value + text[last:]


def view(text):
    assert text.count("unit pasnist;") == text.count("\ninterface\n") == 1
    text = text.replace("unit pasnist;", "unit nisttableview;", 1)
    text = text.replace("\ninterface\n",
                        "\ninterface\nprocedure ProbeControl;\nprocedure ProbeTables;\n", 1)
    assert text.count("\ninitialization\n") == 1
    return text.replace("\ninitialization\n", "\n" + fixture.read_text() + "\ninitialization\n")


save()
try:
    run("regenerate-check", ["python3", "-I", repo / "scripts/nist_tables.py", "--check"], repo)
    assert "GenTablesInit" not in source and "TablesOnce" not in source
    variants = {
        "production": (source, None),
        "p256-limb": (corrupt_table(source, 256), b"P256 table X\n"),
        "p384-limb": (corrupt_table(source, 384), b"P384 table X\n"),
        "zero-z": (source.replace("mask := CtByteEq(N, 0) - 1;", "mask := -1;"),
                   b"P384 infinity Z\n"),
    }
    # Confine the selector defect to the new base table, preserving the
    # variable-point implementation and the independent point control.
    start = source.index("procedure P384GenTableSelect(")
    stop = source.index("\nend;", start) + len("\nend;")
    block = source[start:stop]
    assert block.count("choice := CtByteEq(i, N);") == 1
    variants["selector"] = (
        source[:start] + block.replace("choice := CtByteEq(i, N);",
                                      "choice := CtByteEq(i + 1, N);") + source[stop:],
        b"P384 selection X\n")
    assert len({hashlib.sha256(v[0].encode()).hexdigest() for v in variants.values()}) == 5
    for target, cpu in (("amd64", "base"), ("amd64", "native"),
                        ("arm64", "base"), ("arm64", "max")):
        launch = [qemu, "-cpu", "cortex-a53" if cpu == "base" else "max"] if target == "arm64" else []
        core = build / ("a64" if target == "arm64" else "")
        for inline in (0, 40):
            tag = f"{target}-{cpu}-{inline}"
            for name, (text, failure) in variants.items():
                folder = root / (tag + "-" + name)
                folder.mkdir()
                path = folder / "nisttableview.paslang"
                path.write_text(view(text))
                program = folder / "probe.paslang"
                program.write_text("program Probe; uses nisttableview; begin\n"
                                   "ProbeControl; if ParamCount = 0 then ProbeTables end.\n")
                flags = ["-target", target, "-cpu", cpu, "-inline", str(inline),
                         "-Fu", folder, "-Fu", core]
                run(tag + "-" + name + "-unit", [compiler, *flags, "-c",
                    "-o", folder / "nisttableview", path], folder)
                binary = folder / "probe"
                run(tag + "-" + name + "-compile", [compiler, *flags, "-o", binary, program], folder)
                objects = [Path(p).resolve() for p in shlex.split(binary.with_suffix(".link").read_text())
                           if p.endswith(".o")]
                assert objects.count(folder / "nisttableview.o") == 1
                assert not any(p.name == "pasnist.o" for p in objects)
                run(tag + "-" + name + "-control", [*launch, binary, "control"], folder,
                    want=b"control\n", env=stress)
                if failure is None:
                    for mode, env in (("normal", base), ("stress", stress)):
                        run(tag + "-" + name + "-" + mode, [*launch, binary], folder,
                            want=expected, env=env)
                else:
                    out = run(tag + "-" + name + "-reject", [*launch, binary], folder,
                              code=1, env=stress)
                    assert failure in out, (tag, name, out)
            print("nist-tables:", tag, "all entries/selections and four defects checked", flush=True)
    state["ok"] = True
finally:
    state["complete"] = True
    save()
print("nist-tables:", len(state["commands"]), "commands; evidence", root)
