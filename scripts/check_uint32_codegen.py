#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Check actual ELF UInt32 operation widths and redundant canonicalization.

The receipt binds each inspected disassembly to its execution, executable,
compiler and SDK. A baseline may retain failures without applying this gate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

ENTRY = re.compile(r"^\s*([0-9a-f]+) <([^>]+)>:$")
INS = re.compile(r"^\s*([0-9a-f]+):\s+([A-Za-z.][A-Za-z0-9.]*)\s*(.*)$")
REG32 = r"%(?:e[abcd]x|e[sd]i|e[bs]p|r[0-9]+d)"
REG64 = r"%(?:r[abcd]x|r[sd]i|r[bs]p|r[0-9]+)"


def functions(text):
    result, current = {}, None
    for line in text.splitlines():
        match = ENTRY.match(line)
        if match:
            name = match[2]
            if current and name.startswith(current + "+"):
                continue
            current = name
            result.setdefault(current, {"entry": match[1], "instructions": []})
            continue
        match = INS.match(line)
        if current and match:
            result[current]["instructions"].append({"address": match[1], "op": match[2], "args": match[3], "text": line})
    return result


def check(text, arch):
    bodies = functions(text)
    issues, observations = [], {}
    wanted = ("stepadd", "stepsub", "stepmul", "stepnot", "stepneg", "stepandnot", "stepornot", "stepxornot", "stepnotxor")
    for name in wanted:
        matches = [(symbol, body) for symbol, body in bodies.items() if re.fullmatch(r"p_f\.0_[0-9]+_" + name, symbol)]
        if len(matches) != 1:
            issues.append({"kind": "missing-or-duplicate-body", "name": name, "count": len(matches)})
            continue
        symbol, body = matches[0]
        observations[symbol] = {"entry": body["entry"], "instruction_count": len(body["instructions"])}
        alu = 0
        canonical = set()
        for instruction in body["instructions"]:
            op, args = instruction["op"], instruction["args"].split("#", 1)[0].strip() if arch == "amd64" else instruction["args"].strip()
            if arch == "amd64":
                destination = args.rsplit(",", 1)[-1].strip()
                aliases = {"%rax": "%eax", "%rbx": "%ebx", "%rcx": "%ecx", "%rdx": "%edx", "%rsi": "%esi", "%rdi": "%edi", "%rbp": "%ebp", "%rsp": "%esp"}
                if re.fullmatch(REG64, destination) and not op.startswith(("cmp", "test", "push")):
                    canonical.discard(aliases.get(destination, destination + "d"))
                if op.startswith(("call", "j")):
                    canonical.clear()
                cleanup = re.fullmatch(r"(" + REG32 + r"),\s*\1", args)
                if op in ("mov", "movl") and cleanup and cleanup[1] in canonical:
                    issues.append({"kind": "redundant-canon", "function": symbol, "instruction": instruction})
                if op.startswith("mov") and re.fullmatch(REG32, destination):
                    canonical.add(destination)
                if re.fullmatch(r"(?:add|sub|imul|and|or|xor|neg|not|lea)[lq]?", op):
                    destination = args.rsplit(",", 1)[-1].strip()
                    if re.fullmatch(REG32, destination):
                        alu += 1
                        canonical.add(destination)
                    elif re.fullmatch(REG64, destination) and destination not in ("%rsp", "%rbp") and not (op.startswith("lea") and re.search(r"\(%r(?:sp|bp)\)", args)):
                        issues.append({"kind": "wide-alu", "function": symbol, "instruction": instruction})
            else:
                destination = args.split(",", 1)[0].strip()
                if re.fullmatch(r"x[0-9]+", destination) and op not in ("cmp", "tst", "str", "stp"):
                    canonical.discard("w" + destination[1:])
                if op in ("b", "bl", "blr") or op.startswith("b."):
                    canonical.clear()
                cleanup = re.fullmatch(r"(w[0-9]+),\s*\1", args)
                if op == "mov" and cleanup and cleanup[1] in canonical:
                    issues.append({"kind": "redundant-canon", "function": symbol, "instruction": instruction})
                if (op == "mov" or op.startswith("ldr")) and re.fullmatch(r"w[0-9]+", destination):
                    canonical.add(destination)
                if op in ("add", "sub", "mul", "madd", "neg", "mvn", "and", "orr", "eor", "bic", "orn", "eon"):
                    destination = args.split(",", 1)[0].strip()
                    if re.fullmatch(r"w[0-9]+", destination):
                        alu += 1
                        canonical.add(destination)
                    elif re.fullmatch(r"x[0-9]+", destination) and destination != "x29":
                        issues.append({"kind": "wide-alu", "function": symbol, "instruction": instruction})
        observations[symbol]["u32_alu_count"] = alu
        if alu == 0:
            issues.append({"kind": "missing-u32-alu", "function": symbol})
    return {"ok": not issues, "issues": issues, "functions": observations}


def check_rotations(text, arch):
    """The seed transfer must directly precede the real 32-bit machine rotate."""
    bodies = functions(text)
    issues, observations = [], {}
    for direction in ("rol", "ror"):
        for suffix in ("0", "7", "13", "32", "64", "dynamic"):
            name = "machine" + direction + suffix
            matches = [(symbol, body) for symbol, body in bodies.items()
                       if re.fullmatch(r"p_f\.0_[0-9]+_" + name, symbol)]
            if len(matches) != 1:
                issues.append({"kind": "missing-machine-rotate", "name": name, "count": len(matches)})
                continue
            symbol, body = matches[0]
            instructions = body["instructions"]
            found = []
            for index, instruction in enumerate(instructions):
                op, args = instruction["op"], instruction["args"].split("//", 1)[0].strip()
                if arch == "amd64":
                    args = args.split("#", 1)[0].strip()
                    match = op in (direction, direction + "l") and args.endswith(",%eax")
                    match = match or (op in (direction, direction + "l") and re.search(r",\s*%eax$", args))
                    seeded = index > 0 and instructions[index-1]["op"] in ("mov", "movq") and re.fullmatch(r"%rdx,\s*%rax", instructions[index-1]["args"].strip())
                else:
                    match = op in ("ror", "rorv", "extr") and re.match(r"w0,\s*w0,", args)
                    previous = instructions[max(0, index-2):index]
                    seeded = bool(previous and previous[-1]["op"] == "mov" and re.fullmatch(r"x0,\s*x2", previous[-1]["args"].strip()))
                    if direction == "rol" and suffix == "dynamic" and len(previous) == 2:
                        seeded = previous[0]["op"] == "mov" and bool(re.fullmatch(r"x0,\s*x2", previous[0]["args"].strip())) and previous[1]["op"] == "neg" and bool(re.fullmatch(r"w1,\s*w1", previous[1]["args"].strip()))
                if match and seeded:
                    found.append(instruction)
            observations[symbol] = {"entry": body["entry"], "seeded_u32_rotates": found}
            if len(found) != 1:
                issues.append({"kind": "unobserved-dirty-upper-rotate", "function": symbol, "count": len(found)})
    return {"ok": not issues, "issues": issues, "functions": observations}


def check_receipt(receipt_path):
    receipt_path = Path(receipt_path).resolve()
    receipt = json.loads(receipt_path.read_text())
    result = {"ok": False, "receipt": str(receipt_path),
        "observations": [], "issues": []}
    for build in receipt.get("builds", []):
        match = re.fullmatch(r"(extensions|dirty-rotates)-(amd64|arm64)-(base|native|max)-0-build", build["label"])
        if not match:
            continue
        name = build["label"][:-len("-build")] + "-elf.stdout"
        path = receipt_path.parent / name
        if build["status"] != 0 or not path.is_file():
            result["issues"].append({"kind": "missing-compiled-ELF", "label": build["label"]})
            continue
        binary = Path(build.get("argv", [""])[-2])
        if not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest() != build.get("binary_sha256"):
            result["issues"].append({"kind": "unbound-executable", "label": build["label"]})
            continue
        expected = next((row for row in receipt["runs"] if row["label"] == name[:-len(".stdout")]), None)
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if expected is None or expected["status"] != 0 or expected["stdout_sha256"] != digest:
            result["issues"].append({"kind": "unbound-ELF-disassembly", "path": str(path)})
            continue
        tool = expected.get("tool_identity", {})
        tool_path = tool.get("resolved_path")
        bound_tool = receipt.get("tools_before", {}).get(tool_path)
        if not expected.get("scope_validated") or not expected.get("cleanup", {}).get("ok") or not tool_path or not Path(tool_path).is_file() or bound_tool != tool.get("sha256") or hashlib.sha256(Path(tool_path).read_bytes()).hexdigest() != bound_tool or expected.get("argv", [])[-1:] != [str(binary)]:
            result["issues"].append({"kind": "unbound-inspection-tool-or-scope", "path": str(path)})
            continue
        observation = (check if match[1] == "extensions" else check_rotations)(content.decode("utf-8", "strict"), match[2])
        observation.update(case=match[1], arch=match[2], cpu=match[3], file=str(path), sha256=digest,
                           executable_sha256=build["binary_sha256"])
        result["observations"].append(observation)
        result["issues"].extend(observation["issues"])
    expected_profiles = {(case, *row[:2]) for row in receipt.get("profiles", []) if row[2] == 0 for case in ("extensions", "dirty-rotates")}
    observed = {(row["case"], row["arch"], row["cpu"]) for row in result["observations"]}
    if observed != expected_profiles:
        result["issues"].append({"kind": "incomplete-profile-coverage", "expected": sorted(expected_profiles), "observed": sorted(observed)})
    result["ok"] = bool(expected_profiles) and not result["issues"]
    return result



def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("receipt")
    parser.add_argument("--out", help="optional fresh JSON output path")
    options = parser.parse_args()
    if options.out and Path(options.out).exists():
        parser.error("fresh output path required")
    result = check_receipt(options.receipt)
    content = json.dumps(result, indent=2) + "\n"
    if options.out:
        Path(options.out).write_text(content)
    else:
        print(content, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
