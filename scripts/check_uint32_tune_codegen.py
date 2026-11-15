#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Pure width/tune selector checks for a retained uint32tune ELF disassembly.

The caller binds this module's observations to the selected compiler,
executable, objdump and complete stdout. This module never runs a command.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

# Each function is emitted in this order in one translation unit. The N1 X/W
# transitions exercise separate width banks; N2 and N1-again exercise tune keys.
FUNCTIONS = (
    ("n1xfirst99", 64, 64, 99, "n1-x99"),
    ("n1wfirst99", 32, 32, 99, "w99"),
    ("n1xafterw99", 64, 64, 99, "n1-x99"),
    ("n1wafterx99", 32, 32, 99, "w99"),
    ("n2x99", 64, 64, 99, "n2-x99"),
    ("n2w99", 32, 32, 99, "w99"),
    ("n1xagain99", 64, 64, 99, "n1-x99"),
    ("n1wagain99", 32, 32, 99, "w99"),
    ("n1wbit31", 32, 32, 2147483648, "shift31"),
    ("n1wminus1", 32, 32, 4294967295, "neg"),
    ("n1xbit31", 64, 64, 2147483648, "shift31"),
    ("n1xpositiveffffffff", 64, 64, 4294967295, "wide"),
    ("defaultx99", 64, 64, 99, "wide"),
    ("defaultwidefromu32", 32, 64, 99, "wide"),
    ("defaultxbit32", 64, 64, 4294967296, "shift32"),
)
INPUT_WIDE = (0, 1, -1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF, 1 << 32,
              0x1234567881234567, (1 << 63) - 1, -(1 << 63))
INPUT_NARROW = (0, 1, 2, 0x7FFFFFFF, 0x80000000, 0x81234567, 0xFFFFFFFE, 0xFFFFFFFF)
ENTRY = re.compile(r"^\s*([0-9a-f]+) <([^>]+)>:$")
INS = re.compile(r"^\s*([0-9a-f]+):\s+([A-Za-z.][A-Za-z0-9.]*)\s*(.*)$")
REG32 = r"%(?:e[abcd]x|e[sd]i|e[bs]p|r[0-9]+d)"
REG64 = r"%(?:r[abcd]x|r[sd]i|r[bs]p|r[0-9]+)"


def expected_output():
    """Independent arbitrary-precision product followed by the language width."""
    result = []
    for name, argument_width, result_width, factor, selection in FUNCTIONS:
        for value in INPUT_NARROW if argument_width == 32 else INPUT_WIDE:
            product = (value * factor) & ((1 << result_width) - 1)
            if result_width == 64 and product & (1 << 63):
                product -= 1 << 64
            result.append(str(product))
    return ("\n".join(result) + "\n").encode()


def functions(text):
    result, current = {}, None
    for line in text.splitlines():
        match = ENTRY.match(line)
        if match:
            name = match[2].lower()
            if current and name.startswith(current + "+"):
                continue
            current = name
            result.setdefault(current, {"entry": match[1], "instructions": []})
            continue
        match = INS.match(line)
        if current and match:
            result[current]["instructions"].append({"address": match[1], "op": match[2].lower(), "args": match[3], "text": line})
    return result


def immediate(text):
    match = re.fullmatch(r"[#\$]?(0x[0-9a-f]+|[0-9]+)", text.strip(), re.I)
    return int(match[1], 0) if match else None


def arithmetic(instructions, arch):
    """Select scalar result arithmetic, leaving stack-frame and move traffic out."""
    result = []
    for instruction in instructions:
        op = instruction["op"]
        args = instruction["args"].split("//", 1)[0].strip()
        if arch == "arm64":
            parts = [part.strip() for part in args.split(",")]
            if not parts or not re.fullmatch(r"[wx][0-9]+", parts[0]):
                continue
            if parts[0] == "x29" or any(part == "sp" for part in parts[1:]):
                continue
            width = 32 if parts[0][0] == "w" else 64
            kind, shift = None, None
            if op == "mul" or (op == "madd" and len(parts) == 4 and parts[-1] == ("wzr" if width == 32 else "xzr")):
                kind = "mul"
            elif op in ("neg", "negs") or (op in ("sub", "subs") and len(parts) >= 3 and parts[1] == ("wzr" if width == 32 else "xzr")):
                kind = "neg"
            elif op == "lsl" and len(parts) == 3:
                kind, shift = "shift", immediate(parts[2])
            elif op == "ubfm" and len(parts) == 4:
                rotation, top = immediate(parts[2]), immediate(parts[3])
                if rotation is not None and top == rotation - 1:
                    kind, shift = "shift", (width - rotation) % width
            elif op in ("add", "adds", "sub", "subs"):
                kind = "combine"
            if kind in ("combine", "neg"):
                match = re.search(r"\blsl\s+([#]?(?:0x[0-9a-f]+|[0-9]+))", args, re.I)
                shift = immediate(match[1]) if match else 0
        else:
            args = args.split("#", 1)[0].strip()
            destination = args.rsplit(",", 1)[-1].strip()
            width = 32 if re.fullmatch(REG32, destination) else 64 if re.fullmatch(REG64, destination) else None
            if width is None or destination in ("%rsp", "%rbp"):
                continue
            if op.startswith("lea") and re.search(r"\(%r(?:sp|bp)\)", args):
                continue
            kind, shift = None, None
            if op in ("imul", "imull", "imulq", "mul", "mull", "mulq"):
                kind = "mul"
            elif op in ("neg", "negl", "negq"):
                kind, shift = "neg", 0
            elif op in ("shl", "shll", "shlq", "sal", "sall", "salq"):
                kind, shift = "shift", immediate(args.split(",", 1)[0])
            elif op in ("add", "addl", "addq", "sub", "subl", "subq", "lea", "leal", "leaq"):
                kind = "combine"
        if kind:
            result.append({"kind": kind, "width": width, "shift": shift, "instruction": instruction})
    return result


def check(text, arch):
    bodies = functions(text)
    issues, observations = [], {}
    for name, argument_width, result_width, factor, selection in FUNCTIONS:
        matches = [(symbol, body) for symbol, body in bodies.items() if re.fullmatch(r"p_f\.0_[0-9]+_" + name, symbol)]
        if len(matches) != 1:
            issues.append({"kind": "missing-or-duplicate-width-tune-body", "function": name, "count": len(matches)})
            continue
        symbol, body = matches[0]
        operations = arithmetic(body["instructions"], arch)
        observations[symbol] = {"entry": body["entry"], "selection": selection, "operations": operations}
        valid = bool(operations) and all(item["width"] == result_width for item in operations)
        if selection.startswith("shift"):
            shift = int(selection[len("shift"):])
            valid = valid and len(operations) == 1 and operations[0]["kind"] == "shift" and operations[0]["shift"] == shift
        elif selection == "neg":
            valid = valid and len(operations) == 1 and operations[0]["kind"] == "neg" and operations[0]["shift"] == 0
        elif arch == "arm64" and selection in ("n2-x99", "w99"):
            valid = valid and len(operations) == 1 and operations[0]["kind"] == "mul"
        elif arch == "arm64" and selection == "n1-x99":
            valid = valid and len(operations) == 2 and all(item["kind"] == "combine" for item in operations) and sorted(item["shift"] for item in operations) == [1, 5]
        if not valid:
            issues.append({"kind": "wrong-width-or-tune-selection", "function": symbol, "expected_width": result_width, "selection": selection, "operations": operations})
    return {"ok": not issues, "issues": issues, "functions": observations}


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("disassembly")
    parser.add_argument("--arch", choices=("amd64", "arm64"), required=True)
    parser.add_argument("--out", help="fresh optional observation path")
    options = parser.parse_args()
    if options.out and Path(options.out).exists():
        parser.error("fresh output path required")
    path = Path(options.disassembly)
    content = path.read_bytes()
    result = check(content.decode("utf-8", "strict"), options.arch)
    result.update(disassembly=str(path.resolve()), sha256=hashlib.sha256(content).hexdigest())
    rendered = json.dumps(result, indent=2) + "\n"
    if options.out:
        Path(options.out).write_text(rendered)
    else:
        print(rendered, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
