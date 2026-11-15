#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Check UInt32 semantics, memory widths and actual ELF code on both targets.

Usage: check_uint32.py COMPILER BUILDDIR [QEMU] [options]. Every execution
is compared with an independent integer model, with and without GC stress.
A fresh retained receipt binds the compiler, SDK, sources and disassembly.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
import uint32_model
import check_uint32_codegen
sys.path.insert(0, str(ROOT / "scripts/bench"))
import metadata_scope
MASK = (1 << 32) - 1


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def literal(value):
    if value == -(1 << 63):
        return "(-9223372036854775807 - 1)"
    return "(" + str(value) + ")" if value < 0 else str(value)


def extension():
    """Explicit UInt32 operations; Python arbitrary integers provide the oracle."""
    operations = [
        ("Add", "a + b", lambda a, b: (a + b) & MASK),
        ("AddK1", "a + 1", lambda a, b: (a + 1) & MASK),
        ("Sub", "a - b", lambda a, b: (a - b) & MASK),
        ("Mul", "a * b", lambda a, b: (a * b) & MASK),
        ("Not", "not a", lambda a, b: (~a) & MASK),
        ("Neg", "-a", lambda a, b: (-a) & MASK),
        ("AndNot", "a and not b", lambda a, b: a & (~b & MASK)),
        ("OrNot", "a or not b", lambda a, b: a | (~b & MASK)),
        ("XorNot", "a xor not b", lambda a, b: a ^ (~b & MASK)),
        ("NotXor", "not (a xor b)", lambda a, b: (~(a ^ b)) & MASK),
        ("Mix", "(a + b) xor (a * b)", lambda a, b: ((a + b) ^ (a * b)) & MASK),
    ]
    for value in (0, 1, 3, 5, 9, 16, 128, 65536, 0x80000000, 0xFFFFFFFD, MASK):
        operations.append(("MulK" + str(value), "a * " + str(value),
                           lambda a, b, k=value: (a * k) & MASK))
    for count in (0, 31, 32, 33, 63):
        operations.append(("Shift" + str(count), "a shl " + str(count),
                           lambda a, b, n=count: (a << n) & MASK))
    for value in (0x80000000, 0xF2345678, MASK):
        operations.append(("Imm" + str(value), "a + " + str(value),
                           lambda a, b, k=value: (a + k) & MASK))
    source = ["program uint32extensions;", "var Calls, Trace: Integer;", "",
              "function Pass(a: UInt32): UInt32;",
              "begin Calls += 1; Result := a; end;", ""]
    for name, expression, _ in operations:
        for raw in (False, True):
            body = re.sub(r"\b([ab])\b", lambda m: "Pass(" + m[1] + ")", expression) if raw else expression
            source += ["function " + ("Raw" if raw else "Step") + name + "(a, b: UInt32): UInt32;",
                       "begin Result := " + body + "; end;", ""]
    source += [
        "function Tagged(a: UInt32; tag: Integer): UInt32; begin Trace := Trace * 10 + tag; Result := a; end;",
        "function Ordered(a, b: UInt32): UInt32; begin Result := Tagged(a, 1) - Tagged(b, 2); end;",
        "function Wide(a, b: UInt32): Integer; begin Result := a + b; end;",
        "function Wrapped(a, b: UInt32): Integer; begin Result := Integer(UInt32(a + b)); end;",
        "function CanonAdd(a, b: UInt32): Boolean; begin Result := (a + b) = UInt32(0); end;",
        "function CanonRaw(a, b: UInt32): Boolean; begin Result := (Pass(a) + Pass(b)) = UInt32(0); end;",
        "function CanonImm(a: UInt32): Boolean; begin Result := (a + 1) = UInt32(0); end;",
        "function CanonNot(a, b: UInt32): Boolean; begin Result := (not Pass(a)) = b; end;",
        "function CanonMul3(a: UInt32): Boolean; begin Result := (a * 3) = a; end;",
        "function Inplace(a: UInt32): UInt32;",
        "var x: UInt32; i: Integer;",
        "begin x := a; for i := 0 to 15 do x := x + 1; Result := x; end;",
        "function InplaceZeros(a: UInt32): Integer;",
        "var x: UInt32; i, count: Integer;",
        "begin x := a; count := 0; for i := 0 to 15 do begin x := x + 1; if x = 0 then count += 1; end; Result := count; end;",
        "begin",
    ]
    values = (0, 1, 2, 255, 65535, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFE, MASK)
    pairs = [(a, b) for a in values for b in values]
    rnd = random.Random(548405)
    pairs += [(rnd.getrandbits(32), rnd.getrandbits(32)) for _ in range(64)]
    expected = []
    for a, b in pairs:
        for name, expression, model in operations:
            for prefix in ("Step", "Raw"):
                if prefix == "Raw":
                    source.append("  Calls := 0;")
                source.append("  WriteLn(" + prefix + name + "(" + str(a) + ", " + str(b) + "));")
                expected.append(str(model(a, b)))
                if prefix == "Raw":
                    source.append("  WriteLn(Calls);")
                    expected.append(str(len(re.findall(r"\b[ab]\b", expression))))
        source += ["  Trace := 0;", "  WriteLn(Ordered(" + str(a) + ", " + str(b) + "));", "  WriteLn(Trace);"]
        expected += [str((a - b) & MASK), "12"]
        for name, value in (("Wide", a + b), ("Wrapped", (a + b) & MASK)):
            source.append("  WriteLn(" + name + "(" + str(a) + ", " + str(b) + "));")
            expected.append(str(value))
        for name, value in (("CanonAdd", ((a + b) & MASK) == 0),
                            ("CanonRaw", ((a + b) & MASK) == 0),
                            ("CanonNot", ((~a) & MASK) == b)):
            source.append("  WriteLn(Ord(" + name + "(" + str(a) + ", " + str(b) + ")));")
            expected.append(str(int(value)))
        source.append("  WriteLn(Ord(CanonMul3(" + str(a) + ")));")
        expected.append(str(int(((a * 3) & MASK) == a)))
        source.append("  WriteLn(Inplace(" + str(a) + "));")
        expected.append(str((a + 16) & MASK))
        source.append("  WriteLn(InplaceZeros(" + str(a) + "));")
        expected.append(str(sum(((a + offset) & MASK) == 0 for offset in range(1, 17))))
        source.append("  WriteLn(Ord(CanonImm(" + str(a) + ")));")
        expected.append(str(int(((a + 1) & MASK) == 0)))
    source += ["end.", ""]
    return "\n".join(source).encode(), ("\n".join(expected) + "\n").encode()


def expected_fault_line(source):
    """The generated eight-byte read is on its function's single source line."""
    called = re.search(rb"WriteLn\((ReadWide(?:Extract)?)\(", source)
    if called is None:
        raise RuntimeError("fault case has no designated eight-byte read")
    prefix = b"function " + called[1] + b"("
    matches = [number for number, line in enumerate(source.splitlines(), 1)
               if line.startswith(prefix) and b"p^" in line]
    if len(matches) != 1:
        raise RuntimeError("fault case has no unique source read line")
    return matches[0]


def matches_memory_fault(source, status, stdout, stderr):
    # P568 prints MsgBadAddr, an unpadded lowercase address and rt_fatalline;
    # the read must remain at its source line, including through inlining.
    pattern = (rb"paslang: invalid memory address 0x([1-9a-f][0-9a-f]{0,15}) at line "
               + str(expected_fault_line(source)).encode("ascii") + b"\n")
    observed = re.fullmatch(pattern, stderr)
    return status == 1 and stdout == b"" and observed is not None and int(observed[1], 16) >= 4096


def guard(fault=False):
    """Use the existing utf8kern guard-page syscall convention, unchanged."""
    lines = [
        "program uint32guard;", "type PU32 = ^UInt32; PS8 = ^Int8; PS16 = ^Int16; PS32 = ^Int32;",
        "var page, st: Integer;",
        "function AddByte(a: UInt32; p: PByte): UInt32; begin Result := a + p^; end;",
        "function AddWord(a: UInt32; p: PWord): UInt32; begin Result := a + p^; end;",
        "function AddU32(a: UInt32; p: PU32): UInt32; begin Result := a + p^; end;",
        "function ReadWide(p: PInteger): UInt32; begin Result := UInt32(p^); end;",
        "function ReadWideExtract(p: PInteger): Integer; begin Result := (p^ shr 8) and 255; end;",
        "function ExtractByte(p: PByte): Integer; begin Result := (p^ shr 1) and 127; end;",
        "function ExtractWord(p: PWord): Integer; begin Result := (p^ shr 8) and 255; end;",
        "function ExtractU32(p: PU32): Integer; begin Result := (p^ shr 24) and 255; end;",
        "function ExtractTypedByte(p: PByte): Byte; begin Result := (p^ shr 1) and 127; end;",
        "function ExtractTypedWord(p: PWord): Word; begin Result := (p^ shr 8) and 255; end;",
        "function ExtractInt8(p: PS8): Int8; begin Result := (p^ shr 1) and 127; end;",
        "function ExtractInt16(p: PS16): Int16; begin Result := (p^ shr 8) and 255; end;",
        "function ExtractInt32(p: PS32): Int32; begin Result := (p^ shr 24) and 255; end;",
        "begin",
        "  if Amd64 = 1 then page := Syscall(9, 0, 8192, 3, 34, -1, 0)",
        "  else page := Syscall(222, 0, 8192, 3, 34, -1, 0);",
        "  if page < 0 then Halt(90);",
        "  if Amd64 = 1 then st := Syscall(10, page + 4096, 4096, 0)",
        "  else st := Syscall(226, page + 4096, 4096, 0);",
        "  if st <> 0 then Halt(91);",
        "  PByte(Pointer(page + 4095))^ := 255;",
    ]
    if fault:
        name = "ReadWideExtract" if fault == "extract" else "ReadWide"
        lines += ["  WriteLn(" + name + "(PInteger(Pointer(page + 4092))));"]
        expected = None
    else:
        lines += [
            "  WriteLn(AddByte(4294967295, PByte(Pointer(page + 4095))));",
            "  WriteLn(ExtractByte(PByte(Pointer(page + 4095))));",
            "  PWord(Pointer(page + 4094))^ := 65535;",
            "  WriteLn(AddWord(4294967295, PWord(Pointer(page + 4094))));",
            "  WriteLn(ExtractWord(PWord(Pointer(page + 4094))));",
            "  PU32(Pointer(page + 4092))^ := 4294967295;",
            "  WriteLn(AddU32(1, PU32(Pointer(page + 4092))));",
            "  WriteLn(ExtractU32(PU32(Pointer(page + 4092))));",
            "  WriteLn(PByte(Pointer(page + 4091))^);",
            "  WriteLn(ExtractTypedByte(PByte(Pointer(page + 4095))));",
            "  WriteLn(ExtractTypedWord(PWord(Pointer(page + 4094))));",
            "  WriteLn(ExtractInt8(PS8(Pointer(page + 4095))));",
            "  WriteLn(ExtractInt16(PS16(Pointer(page + 4094))));",
            "  WriteLn(ExtractInt32(PS32(Pointer(page + 4092))));",
        ]
        expected = b"254\n127\n65534\n255\n0\n255\n0\n127\n255\n127\n255\n255\n"
    lines += ["end.", ""]
    return "\n".join(lines).encode(), expected


def unit_inputs(program, units):
    """Bind every external object and its interface in the explicitly selected SDK."""
    lines = program.with_suffix(".link").read_text().splitlines()
    if len(lines) < 6 or lines[0] != "-o" or lines[2:4] != ["--gc-sections", "-T"]:
        raise RuntimeError("malformed retained link inputs: " + str(program))
    result = []
    for entry in lines[6:]:
        obj = Path(entry)
        obj = (obj if obj.is_absolute() else ROOT / obj).resolve()
        if not obj.is_relative_to(units):
            raise RuntimeError("linked object escaped selected SDK: " + str(obj))
        interface = units / (obj.stem.lower() + ".pi")
        if not interface.is_file():
            raise RuntimeError("linked unit has no interface in selected SDK: " + str(obj))
        result.append({kind: {"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size}
                       for kind, path in (("interface", interface), ("object", obj))})
    return {"units": result}


def extraction():
    """Logical shifts keep their 64-bit count contract; conversions bound context."""
    m64 = (1 << 64) - 1
    forms = (
        ("Wide", "Integer", "Integer", "a", lambda a: a & m64),
        ("Narrow", "UInt32", "UInt32", "a", lambda a: a & MASK),
        ("CastBefore", "Integer", "Integer", "UInt32(a)", lambda a: a & MASK),
        ("Signed", "Int32", "Integer", "a", lambda a: uint32_model.wrap_t("Int32", a) & m64),
        ("Raw", "Integer", "Integer", "Pass(a)", lambda a: a & m64),
    )
    counts = (-65, -64, -63, -33, -32, -31, -1, 0, 1, 7, 15, 31, 32, 33, 63, 64, 65)
    masks = (0, 1, 255, 65535, MASK)
    lines = ["program uint32extract;", "var Calls: Integer;",
             "function Pass(a: Integer): Integer; begin Calls += 1; Result := a; end;"]
    functions = []
    for name, argtype, restype, arg, model in forms:
        for mask in masks:
            suffix = name + "M" + str(mask)
            lines += ["function Dynamic" + suffix + "(a: " + argtype + "; n: Integer): " + restype + ";",
                      "begin Result := (" + arg + " shr n) and " + str(mask) + "; end;"]
            for index, count in enumerate(counts):
                fname = "Const" + suffix + "C" + str(index)
                lines += ["function " + fname + "(a: " + argtype + "): " + restype + ";",
                          "begin Result := (" + arg + " shr " + literal(count) + ") and " + str(mask) + "; end;"]
                functions.append((fname, name, argtype, model, count, mask))
    lines += ["function CastAfter(a, n: Integer): UInt32; begin Result := UInt32((a shr n) and 4294967295); end;", "begin"]
    answer = []
    values = (0, 0x81234567, -1, -(1 << 63), 0x1234567881234567)
    def value_for(value, argtype):
        return uint32_model.wrap_t(argtype, value)
    def emit(call, expected, raw=False):
        if raw:
            lines.append("  Calls := 0;")
        lines.append("  WriteLn(" + call + ");")
        answer.append(str(expected))
        if raw:
            lines.append("  WriteLn(Calls);")
            answer.append("1")
    for fname, name, argtype, model, count, mask in functions:
        for value in values:
            a = value_for(value, argtype)
            emit(fname + "(" + literal(a) + ")", (model(a) >> (count & 63)) & mask, name == "Raw")
    for name, argtype, restype, arg, model in forms:
        for mask in masks:
            for count in range(-65, 66):
                for value in (0x81234567, -1, 0x1234567881234567):
                    a = value_for(value, argtype)
                    emit("Dynamic" + name + "M" + str(mask) + "(" + literal(a) + ", " + literal(count) + ")",
                         (model(a) >> (count & 63)) & mask, name == "Raw")
    for value in values:
        for count in range(-65, 66):
            emit("CastAfter(" + literal(value) + ", " + literal(count) + ")", ((value & m64) >> (count & 63)) & MASK)
    lines += ["end.", ""]
    return "\n".join(lines).encode(), ("\n".join(answer) + "\n").encode()


def narrow_extraction():
    """Fitting masks also permit extraction in byte, word and signed contexts."""
    types = (("Byte", 255), ("Word", 65535), ("Int8", 127), ("Int16", 32767), ("Int32", 2147483647))
    counts = (-65, -1, 0, 1, 7, 15, 31, 32, 65)
    dynamic = (-65, -64, -33, -32, -1, 0, 1, 7, 15, 31, 32, 33, 63, 64, 65)
    source = ["program uint32narrowextract;", "var Calls: Integer;"]
    functions = []
    for typ, maximum in types:
        source += ["function Pass" + typ + "(a: " + typ + "): " + typ + "; begin Calls += 1; Result := a; end;"]
        for raw in (False, True):
            arg = "Pass" + typ + "(a)" if raw else "a"
            suffix = typ + ("Raw" if raw else "Stored")
            source += ["function Dynamic" + suffix + "(a: " + typ + "; n: Integer): " + typ + ";",
                       "begin Result := (" + arg + " shr n) and " + str(maximum) + "; end;"]
            for mask in (1, maximum):
                for index, count in enumerate(counts):
                    name = "Const" + suffix + "M" + str(mask) + "C" + str(index)
                    source += ["function " + name + "(a: " + typ + "): " + typ + ";",
                               "begin Result := (" + arg + " shr " + literal(count) + ") and " + str(mask) + "; end;"]
                    functions.append((name, typ, mask, raw, count))
    source.append("begin")
    expected = []
    def values(typ):
        return sorted({uint32_model.wrap_t(typ, value) for value in (0, -1, 0x81234567)})
    def emit(name, typ, mask, raw, count, dynamic=False):
        for value in values(typ):
            if raw:
                source.append("  Calls := 0;")
            args = literal(value) + (", " + literal(count) if dynamic else "")
            source.append("  WriteLn(" + name + "(" + args + "));")
            expected.append(str(uint32_model.shift_right(typ, value, count) & mask))
            if raw:
                source.append("  WriteLn(Calls);")
                expected.append("1")
    for args in functions:
        emit(*args)
    for typ, maximum in types:
        for raw in (False, True):
            for count in dynamic:
                emit("Dynamic" + typ + ("Raw" if raw else "Stored"), typ, maximum, raw, count, True)
    source += ["end.", ""]
    return "\n".join(source).encode(), ("\n".join(expected) + "\n").encode()


def multiplication_storage():
    """Compare before narrowing a result: retyped storage can have dirty high bits."""
    lines = ["program uint32mulstorage;", "var Calls: Integer;"]
    types = ("Int8", "Int16", "Int32", "Integer", "UInt32")
    for typ in types:
        lines += ["function Pass" + typ + "(a: " + typ + "): " + typ + "; begin Calls += 1; Result := a; end;"]
        for factor in (0, 1):
            for raw in (False, True):
                name = ("Raw" if raw else "Stored") + typ + "K" + str(factor)
                arg = "Pass" + typ + "(a)" if raw else "a"
                lines += ["function " + name + "(a: " + typ + "; b: UInt32): Boolean;",
                          "begin Result := (UInt32(" + arg + ") * " + str(factor) + ") = b; end;"]
    lines += ["begin"]
    answer = []
    for typ in types:
        values = {uint32_model.wrap_t(typ, value) for value in (0, 1, -1, -2, 0x80000000, 0x81234567, 0x1234567881234567, -(1 << 63))}
        for value in sorted(values):
            for factor in (0, 1):
                product = ((value & MASK) * factor) & MASK
                for other in (product, (product + 1) & MASK):
                    for raw in (False, True):
                        name = ("Raw" if raw else "Stored") + typ + "K" + str(factor)
                        lines += ["  Calls := 0;", "  WriteLn(Ord(" + name + "(" + literal(value) + ", " + str(other) + ")));", "  WriteLn(Calls);"]
                        answer += [str(int(product == other)), str(int(raw))]
    lines += ["end.", ""]
    return "\n".join(lines).encode(), ("\n".join(answer) + "\n").encode()


def corpus(seeds):
    for name, stem in (("historical-690", "uint32legacy"), ("dirty-rotates", "uint32rotate")):
        yield name, (ROOT / "testdata" / (stem + ".paslang")).read_bytes(), (ROOT / "testdata" / (stem + ".out")).read_bytes(), False
    for name, generate in (("extensions", extension), ("extract-context", extraction), ("extract-narrow", narrow_extraction), ("mul-storage", multiplication_storage)):
        source, answer = generate()
        yield name, source, answer, False
    for name, fault in (("guard-widths", False), ("guard-read8-fault", True), ("guard-extract8-fault", "extract")):
        source, answer = guard(fault)
        yield name, source, answer, bool(fault)
    for seed in seeds:
        source, answer = uint32_model.build(seed)
        yield "fuzz-" + str(seed), source.encode(), answer.encode(), False


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("compiler")
    parser.add_argument("builddir")
    parser.add_argument("qemu", nargs="?")
    parser.add_argument("--units-amd64")
    parser.add_argument("--units-arm64")
    parser.add_argument("--expected-version", help="optional exact version required by a private comparison")
    parser.add_argument("--role", choices=("baseline", "candidate", "mutant"), default="candidate")
    parser.add_argument("--out", help="fresh retained output directory; otherwise created under BUILDDIR")
    parser.add_argument("--target", choices=("all", "amd64", "arm64"), default="all")
    parser.add_argument("--seed-first", type=int, default=54800)
    parser.add_argument("--seed-count", type=int, default=8)
    parser.add_argument("--objdump-amd64", default="objdump")
    parser.add_argument("--objdump-arm64", default="aarch64-linux-gnu-objdump")
    options = parser.parse_args()
    builddir = Path(options.builddir).resolve()
    if options.seed_count < 0:
        parser.error("seed-count must be nonnegative")
    if options.out:
        out = Path(options.out).resolve()
        if out.exists():
            parser.error("fresh output directory required; retain previous failures")
        out.mkdir(parents=True)
    else:
        builddir.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="check-uint32-", dir=builddir))
    def executable(value):
        resolved = shutil.which(str(value))
        path = Path(resolved if resolved else value).resolve()
        if not path.is_file():
            raise RuntimeError("executable absent: " + str(value))
        return str(path)
    compiler = Path(executable(options.compiler))
    source_root = ROOT
    options.units_amd64 = str(Path(options.units_amd64).resolve() if options.units_amd64 else builddir)
    options.units_arm64 = str(Path(options.units_arm64).resolve() if options.units_arm64 else builddir / "a64")
    options.qemu = executable(options.qemu or builddir / "qemu-aarch64") if options.target != "amd64" else None
    options.objdump_amd64 = executable(options.objdump_amd64) if options.target != "arm64" else None
    options.objdump_arm64 = executable(options.objdump_arm64) if options.target != "amd64" else None
    record = {"format": "uint32-correctness-v1", "role": options.role,
              "ok": False, "phase": "setup", "performance_verdict": None,
              "compiler": str(compiler), "compiler_before": sha(compiler),
              "expected_version": options.expected_version,
              "inputs_before": {}, "builds": [], "runs": [], "errors": []}
    tools = [item for item in (options.qemu, options.objdump_amd64, options.objdump_arm64) if item]
    record["tools_before"] = {item: sha(item) for item in tools}

    def save():
        signals = metadata_scope.received_signals()
        if signals:
            message = "cancellation received: " + str(signals)
            if message not in record["errors"]:
                record["errors"].append(message)
            record["ok"] = False
            if record["phase"] == "complete":
                record["phase"] = "failed"
        record["received_signals"] = signals
        tmp = out / "results.json.tmp"
        tmp.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
        tmp.replace(out / "results.json")

    base_env = {key: value for key, value in os.environ.items()
                if not key.startswith("PASLANG_GC") and key not in ("PASLANG_CPU", "PASLANG_LIB")}
    base_env.setdefault("PATH", os.defpath)

    def command(argv, label, phase, env=None, timeout=180, **extra):
        metadata_scope.check_stop()
        environment = base_env if env is None else env
        row = {"argv": list(map(str, argv)), "cwd": str(source_root), "label": label,
               "phase": phase, "status": "pending", **extra}
        record["builds" if phase == "build" else "runs"].append(row)
        save()
        scope_dir = out / (label + ".scope")
        scoped = metadata_scope.invoke(row["argv"], scope_dir, source_root, environment, timeout)
        row.update(status=scoped["status"], elapsed_s=scoped["elapsed_s"],
                   scope_receipt=str(scope_dir / "result.json"), cleanup=scoped["cleanup"],
                   signals=scoped["received_signals"], tool_identity=metadata_scope.tool_identity(row["argv"][0], environment))
        stdout = (scope_dir / "stdout").read_bytes()
        stderr = (scope_dir / "stderr").read_bytes()
        (out / (label + ".stdout")).write_bytes(stdout)
        (out / (label + ".stderr")).write_bytes(stderr)
        row.update(stdout_sha256=hashlib.sha256(stdout).hexdigest(),
                   stderr_sha256=hashlib.sha256(stderr).hexdigest())
        if not scoped["cleanup"].get("ok"):
            record["errors"].append(label + ": owned process cleanup did not complete")
        else:
            try:
                metadata_scope.validate_receipt(scope_dir, row["argv"], source_root, environment)
                row["scope_validated"] = True
            except Exception as error:
                row["scope_validated"] = False
                record["errors"].append(label + ": scope receipt invalid: " + str(error))
        save()
        metadata_scope.check_stop()
        return row, stdout, stderr

    try:
        for path in [Path(__file__), ROOT / "scripts/uint32_model.py", ROOT / "scripts/check_uint32_codegen.py", ROOT / "scripts/bench/metadata_scope.py",
                     *sorted((ROOT / "testdata").glob("uint32*")),
                     *sorted((source_root / "src").rglob("*.paslang"))]:
            record["inputs_before"][str(path)] = sha(path)
        save()
        row, stdout, stderr = command([compiler, "-v"], "compiler-version", "metadata")
        record["observed_version"] = stdout.decode("utf-8", "replace").strip()
        row["clean_diagnostics"] = row["status"] == 0 and stderr == b""
        if not row["clean_diagnostics"] or (options.expected_version and options.expected_version not in stdout.decode().split()):
            raise RuntimeError("compiler version or diagnostics do not match the selected compiler")
        record["sdk_inputs_before"] = {}
        for directory in {Path(options.units_amd64 if arch == "amd64" else options.units_arm64).resolve()
                          for arch in ("amd64", "arm64") if options.target in ("all", arch)}:
            for path in sorted(directory.rglob("*")):
                if path.is_file() and path.suffix in (".pi", ".o"):
                    record["sdk_inputs_before"][str(path)] = sha(path)
        if options.target != "amd64":
            record["qemu_before"] = sha(options.qemu)
        cases = list(corpus(range(options.seed_first, options.seed_first + options.seed_count)))
        record["cases"] = []
        for name, source, expected, fault in cases:
            path = out / (name + ".paslang")
            path.write_bytes(source)
            record["inputs_before"][str(path)] = sha(path)
            if expected is not None:
                path = out / (name + ".expected")
                path.write_bytes(expected)
                record["inputs_before"][str(path)] = sha(path)
            record["cases"].append({"name": name, "source_sha256": hashlib.sha256(source).hexdigest(),
                "expected_sha256": hashlib.sha256(expected).hexdigest() if expected is not None else None,
                "expected_fault": fault, "expected_fault_line": expected_fault_line(source) if fault else None})
        profiles = [(arch, cpu, inline) for arch, cpus in
                    (("amd64", ("base", "native")), ("arm64", ("base", "max")))
                    if options.target in ("all", arch) for cpu in cpus for inline in (0, 40)]
        record["profiles"] = profiles
        record["expected_builds"] = len(cases) * len(profiles)
        record["expected_executions"] = 2 * record["expected_builds"]
        environments = (("normal", base_env), ("stress", dict(base_env,
            PASLANG_GCSTRESS="1", PASLANG_GCVERIFY="1", PASLANG_GCPOISON="1")))
        for arch, cpu, inline in profiles:
            units = Path(options.units_amd64 if arch == "amd64" else options.units_arm64).resolve()
            for name, source, expected, fault in cases:
                tag = "-".join(map(str, (name, arch, cpu, inline)))
                program = out / tag
                argv = [compiler, "-target", arch, "-cpu", cpu, "-inline", str(inline),
                        "-Fu", units, "-o", program, out / (name + ".paslang")]
                row, build_stdout, build_stderr = command(argv, tag + "-build", "build", env=base_env)
                row["clean_diagnostics"] = row["status"] == 0 and build_stdout == b"" and build_stderr == b""
                if row["status"] != 0:
                    record["errors"].append(tag + ": build failed")
                    continue
                if not row["clean_diagnostics"]:
                    record["errors"].append(tag + ": successful compile emitted diagnostics")
                row["binary_sha256"] = sha(program)
                row["unit_inputs"] = unit_inputs(program, units)
                row["artifacts"] = {str(path): sha(path) for path in
                    [program, *[program.with_suffix(suffix) for suffix in (".s", ".o", ".link", ".ld")]] if path.is_file()}
                dump = options.objdump_amd64 if arch == "amd64" else options.objdump_arm64
                dump_row, _, _ = command([dump, "-drw", "--no-show-raw-insn", program], tag + "-elf", "inspection")
                if dump_row["status"] != 0:
                    record["errors"].append(tag + ": ELF disassembly unavailable")
                launch = [] if arch == "amd64" else [options.qemu, "-cpu", "cortex-a53" if cpu == "base" else "max"]
                for mode, environment in environments:
                    obs, actual, error = command([*launch, program], tag + "-" + mode, "execution", env=environment,
                                                timeout=600 if arch == "arm64" else 180, case=name, profile=[arch, cpu, inline])
                    if fault:
                        ok = matches_memory_fault(source, obs["status"], actual, error)
                    else:
                        ok = obs["status"] == 0 and actual == expected and error == b""
                    obs["matches_independent_oracle"] = ok
                    if not ok:
                        record["errors"].append(tag + "/" + mode + ": exact output/status differs")
                    save()
                print(tag, "recorded", flush=True)
    except BaseException as error:
        record["errors"].append(type(error).__name__ + ": " + str(error))
        if not isinstance(error, Exception):
            raise
    finally:
        record["tools_after"] = {path: sha(path) if Path(path).is_file() else None for path in record["tools_before"]}
        record["tools_unchanged"] = record["tools_before"] == record["tools_after"]
        record["inputs_after"] = {path: sha(path) if Path(path).is_file() else None for path in record["inputs_before"]}
        record["inputs_unchanged"] = record["inputs_before"] == record["inputs_after"]
        record["compiler_after"] = sha(compiler)
        record["compiler_unchanged"] = record["compiler_before"] == record["compiler_after"]
        units = {}
        consistent = True
        for build in record["builds"]:
            for unit in build.get("unit_inputs", {}).get("units", []):
                for kind in ("interface", "object"):
                    item = unit[kind]
                    if item["path"] in units and units[item["path"]] != item["sha256"]:
                        consistent = False
                    units[item["path"]] = item["sha256"]
        record["unit_inputs_before"] = units
        record["unit_inputs_after"] = {path: sha(path) if Path(path).is_file() else None for path in units}
        record["sdk_inputs_after"] = {path: sha(path) if Path(path).is_file() else None
            for path in record.get("sdk_inputs_before", {})}
        record["units_unchanged"] = consistent and units == record["unit_inputs_after"] and record.get("sdk_inputs_before") == record["sdk_inputs_after"]
        record["qemu_after"] = sha(options.qemu) if "qemu_before" in record else None
        record["qemu_unchanged"] = record.get("qemu_before") == record["qemu_after"]
        artifacts = {path: value for build in record["builds"] for path, value in build.get("artifacts", {}).items()}
        record["artifacts_after"] = {path: sha(path) if Path(path).is_file() else None for path in artifacts}
        record["artifacts_unchanged"] = artifacts == record["artifacts_after"]
        record["compiled_all"] = len(record["builds"]) == record.get("expected_builds") and all(row["status"] == 0 and row.get("clean_diagnostics") for row in record["builds"])
        executions = [row for row in record["runs"] if row["phase"] == "execution"]
        record["executed_all"] = len(executions) == record.get("expected_executions")
        record["ok"] = not record["errors"] and record["compiled_all"] and record["executed_all"] and record["inputs_unchanged"] and record["compiler_unchanged"] and record["units_unchanged"] and record["qemu_unchanged"] and record["artifacts_unchanged"] and record["tools_unchanged"]
        save()
        try:
            record["codegen"] = check_uint32_codegen.check_receipt(out / "results.json")
        except Exception as error:
            record["codegen"] = {"ok": False, "error": type(error).__name__ + ": " + str(error)}
        if options.role != "baseline" and not record["codegen"]["ok"]:
            record["ok"] = False
            record["errors"].append("UInt32 ELF codegen requirement failed")
        record["phase"] = "complete" if record["ok"] else "failed"
        save()
    print("UInt32 " + ("ok" if record["ok"] else "FAILED") + ": " + str(out / "results.json"), flush=True)
    return 0 if record["ok"] else 1


if __name__ == "__main__":
    with metadata_scope.signal_scope():
        status = main()
        metadata_scope.check_stop()
        raise SystemExit(status)
