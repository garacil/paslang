#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P602: exact FMA semantics and linked CPU selection through the ordinary SDK.

Usage: check_fma_target.py COMPILER BUILDDIR [QEMU] [options].
The runner never rebuilds or changes SDK objects. Every command is bounded,
owned, retained and checked, including compiler diagnostics and cleanup.
--role baseline records the old selector's violations without accepting them
as candidate correctness. --role mutant enforces the full candidate policy.
`selection(text, arch, cpu, variant, native_has_fma=None)` is a pure oracle
for complete ELF symbols/disassembly. Native requires the actual base probe.
Both inline policies retain address-observable arithmetic bodies. Unsupported
hardware executions are reported separately from compiled-code evidence.

References: Go f043823a ssagen/intrinsics.go:782-817 and installed Go1.27.4
math/fma.go; Rust58cf8f9c num/f32.rs and num/f64.rs mul_add, intrinsic.rs:110;
Intel SDM Vol2C5-226/5-232; AMD APM Vol4 VFMADD213SD/SS; ARM M.c C7.2.120.
The Fraction oracle uses one nearest-even rounding; it neither calls a FMA
provider nor trusts one implementation as the oracle for another. NaN payload
bits are unspecified, matching fmafused's existing any-NaN contract.
"""
import argparse
from fractions import Fraction
import hashlib
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts/bench"))
import metadata_scope as scope

WAYS = ("default", "public", "soft", "pointer", "localbase", "localfast", "after", "ordered")
VIA = ("default", "public", "soft", "localbase", "localfast", "after", "ordered")
PROFILES = {"amd64": ("base", "v3", "v3+aes+pclmul", "native"), "arm64": ("base", "max")}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def item(path):
    path = Path(path)
    st = path.stat()
    return {"sha256": sha(path), "bytes": st.st_size, "mode": st.st_mode & 0o777,
            "mtime_ns": st.st_mtime_ns, "resolved": str(path.resolve())}


def snapshot(paths):
    return {str(p): item(p) for p in sorted(set(map(Path, paths)))}


def after(paths):
    return {name: item(name) if Path(name).is_file() else None for name in paths}


def power2(exponent):
    return Fraction(1 << exponent) if exponent >= 0 else Fraction(1, 1 << -exponent)


def fma_bits(a, b, c, width):
    """IEEE nearest-even result from integer input bits and exact rationals."""
    frac, ebits, bias = (52, 11, 1023) if width == 64 else (23, 8, 127)
    signbit = 1 << (width - 1)
    exponent_mask = (1 << ebits) - 1
    fraction_mask = (1 << frac) - 1
    infinity = exponent_mask << frac

    def decode(bits):
        exponent, mantissa = (bits >> frac) & exponent_mask, bits & fraction_mask
        negative = bool(bits & signbit)
        if exponent == exponent_mask:
            return ("nan" if mantissa else "inf"), negative, None
        if exponent:
            mantissa |= 1 << frac
        value = Fraction(mantissa) * power2((exponent or 1) - bias - frac)
        return "finite", negative, -value if negative else value

    x, y, z = (decode(bits) for bits in (a, b, c))
    if any(value[0] == "nan" for value in (x, y, z)):
        return None
    negative_product = x[1] != y[1]
    if x[0] == "inf" or y[0] == "inf":
        if (x[0] == "finite" and x[2] == 0) or (y[0] == "finite" and y[2] == 0):
            return None
        if z[0] == "inf" and z[1] != negative_product:
            return None
        return infinity | (signbit if negative_product else 0)
    if z[0] == "inf":
        return c
    exact = x[2] * y[2] + z[2]
    if exact == 0:
        negative_zero = (x[2] == 0 or y[2] == 0) and z[2] == 0 and negative_product and z[1]
        return signbit if negative_zero else 0
    negative = exact < 0
    magnitude = abs(exact)
    exponent = magnitude.numerator.bit_length() - magnitude.denominator.bit_length()
    if power2(exponent) > magnitude:
        exponent -= 1
    minimum = 1 - bias
    quantum = max(exponent - frac, minimum - frac)
    scaled = magnitude / power2(quantum)
    rounded, remainder = divmod(scaled.numerator, scaled.denominator)
    if 2 * remainder > scaled.denominator or (2 * remainder == scaled.denominator and rounded & 1):
        rounded += 1
    sign = signbit if negative else 0
    if rounded == 0:
        return sign
    exponent = rounded.bit_length() - 1 + quantum
    if exponent > bias:
        return infinity | sign
    if exponent < minimum:
        return sign | rounded
    shift = exponent - frac - quantum
    mantissa = rounded >> shift if shift >= 0 else rounded << -shift
    return sign | ((exponent + bias) << frac) | (mantissa - (1 << frac))


def vectors(source):
    result = {}
    for name, width in (("DInput", 64), ("SInput", 32)):
        match = re.search(r"\b" + name + r": array\[0\.\.([0-9]+)\] of Integer = \((.*?)\);", source, re.S)
        if match is None:
            raise RuntimeError("fixture input table changed: " + name)
        words = [int(word, 16) for word in re.findall(r"\$([0-9A-Fa-f]+)", match[2])]
        if (int(match[1]) + 1 != len(words) or len(words) != (48 if width == 64 else 51)
                or any(word >= 1 << width for word in words)):
            raise RuntimeError("fixture input table malformed: " + name)
        result[width] = [tuple(words[i:i + 3]) for i in range(0, len(words), 3)]
    critical = (0x39800001, 0x397FFFFE, 0x3F800001)
    if result[32][-1] != critical or fma_bits(*critical, 32) != 0x3F800001:
        raise RuntimeError("Single double-rounding oracle changed")
    return result


def expected_output(source):
    rows = []
    for width, kind in ((64, "D"), (32, "S")):
        for i, operands in enumerate(vectors(source)[width]):
            bits = fma_bits(*operands, width)
            text = "nan" if bits is None else str(bits - (1 << 64) if width == 64 and bits & (1 << 63) else bits)
            for name in WAYS:
                rows.append(f"{kind} {name} {i} {text}")
                if name == "ordered":
                    rows.append(f"order {kind} {i} 123")
            for name in VIA:
                rows.append(f"{kind} via-{name} {i} {text}")
                if name == "ordered":
                    rows.append(f"order-via {kind} {i} 123")
    # Mixed Single/Double, integer conversion and a loop-held Double are
    # separate contracts; these are exact representable bit patterns.
    rows += ["D mixed 0 " + str(0x3E90000010000000),
             "D integer 0 " + str(0x4024000000000000),
             "D loop 0 " + str(0x402C040000000000)]
    return ("\n".join(rows) + "\n").encode()


# Linked-address decoding below follows the reviewed emitter's actual
# addressing and two-word function-value ABI. Only exact rt_morestack is
# an arithmetic runtime boundary; no unresolved arithmetic transfer passes.
# See pasemit LeaS/LdS3195+, CpuHas27224+, ekProcPtr29008+/30012+ and
# EmitStackCheck41320+; GNU objdump(1) --syms defines the symbol rows.
# Width/clobber review: Intel SDM1 3.4.1.1/Table3-2, 7.3.7.1/Table7-3,
# SDM2A3-194..197 CMPXCHG; ARM M.c C7.2.157 FMOV and C6.2.214/216/220,
# C6.2.414/415 LDP/LDR/LDRB/STP/STR, B1.2.3 zero register; SDM1 7.3.1.4 PUSH.
# GNU AS9.16.3.1/9.16.7: AMD immediates need $, bare absolute operands read memory.
# No subword memory value or unmodeled extension instruction proves a pointer.
from bisect import bisect_right
import re

_ENTRY = re.compile(r"^\s*([0-9a-fA-F]+) <([^>]+)>:$")
_INSTRUCTION = re.compile(r"^\s*([0-9a-fA-F]+):\s+(\S+)(?:\s+(.*))?$")
_HEX = re.compile(r"[0-9a-fA-F]+")
_RUNTIME_BOUNDARY = frozenset(("rt_morestack",))


def functions(text):
    """Parse GNU columns and section-bound emitted routine ranges, without I/O."""
    symbols, sections, bodies, errors = {}, {}, {}, []
    in_symbols, saw_symbols, section = False, False, None
    for line in text.splitlines():
        if line.strip() == "SYMBOL TABLE:":
            in_symbols, saw_symbols = True, True
            continue
        if line.startswith("Disassembly of section "):
            in_symbols = False
            section = line[len("Disassembly of section "):].removesuffix(":")
            if section in sections:
                errors.append("duplicate disassembly section: " + section)
            sections.setdefault(section, {"labels": [], "instructions": [], "omitted": []})
            continue
        if in_symbols:
            if not line.strip(): continue
            # GNU objdump --syms: value, seven flag groups, arbitrary section,
            # size, optional visibility, name. Section names need no prefix.
            fields = line.split()
            if len(fields) >= 2 and fields[-2] in (".hidden", ".protected", ".internal"):
                del fields[-2]
            if (len(fields) < 4 or not _HEX.fullmatch(fields[0])
                    or not _HEX.fullmatch(fields[-2])
                    or any(char not in "lgu!wCWIidDFfO" for char in "".join(fields[1:-3]))):
                errors.append("unparsed ELF symbol row: " + line)
                continue
            name = fields[-1].lower()
            row = {"address": int(fields[0], 16), "section": fields[-3],
                   "size": int(fields[-2], 16), "flags": fields[1:-3]}
            if row not in symbols.setdefault(name, []): symbols[name].append(row)
            continue
        match = _ENTRY.match(line)
        if match and section is not None:
            sections[section]["labels"].append((int(match[1], 16), match[2].lower()))
            continue
        match = _INSTRUCTION.match(line)
        if match and section is not None:
            sections[section]["instructions"].append({"address": int(match[1], 16),
                "op": match[2].lower(), "args": match[3] or "", "text": line})
        elif section is not None and line.strip() == "...":
            sections[section]["omitted"].append(sections[section]["instructions"][-1]["address"]
                                                if sections[section]["instructions"] else None)
    instructions, owners, next_address = {}, {}, {}
    for section, decoded in sections.items():
        roots = {}
        for name, rows in symbols.items():
            for row in rows:
                if row["section"] != section: continue
                flags = "".join(row["flags"])
                # The current emitter writes NOTYPE/size-zero routines:
                # EmitProcAt 43979+ exports entries; pas_main 55708 is local.
                # Nested p_f entries can also be local. Dot/$ local labels are
                # interior labels, except an explicit ELF function symbol.
                emitted = (name in ("pas_main", "_start") or name.startswith(("p_f.", "rt_"))
                           or re.fullmatch(r"u_[a-z0-9_]+_(?:init|fini)", name))
                entry = ("F" in flags or (not any(flag in flags for flag in "dfO")
                         and emitted))
                if entry:
                    root = roots.setdefault(row["address"], {"names": [], "sizes": set()})
                    root["names"].append(name)
                    if row["size"]: root["sizes"].add(row["size"])
                elif (not name.startswith((".", "$")) and not any(flag in flags for flag in "dfO")):
                    errors.append("unreviewed local code symbol: " + name)
        starts = sorted(roots)
        addresses = [row["address"] for row in decoded["instructions"]]
        if addresses != sorted(set(addresses)):
            errors.append("duplicate or unordered decoded addresses in " + section)
        section_end = max(addresses, default=-1) + 1
        for index, start in enumerate(starts):
            root = roots[start]
            if len([name for name in set(root["names"]) if name == "pas_main" or name.startswith("p_f.")]) > 1:
                errors.append("ambiguous emitted routine aliases at " + hex(start))
            limit = starts[index + 1] if index + 1 < len(starts) else section_end
            if len(root["sizes"]) > 1:
                errors.append("conflicting ELF function alias sizes at " + hex(start))
            size = next(iter(root["sizes"]), 0)
            end = start + size if size else limit
            if end > limit:
                errors.append("overlapping ELF function ranges at " + hex(start))
            if end <= start or start in bodies:
                errors.append("empty or ambiguous code range at " + hex(start))
            body = {"entry": start, "end": end, "section": section,
                    "range_basis": "ELF-symbol-size" if size else "next-emitted-entry-or-last-decoded-address",
                    "names": sorted(set(root["names"])), "interior_labels": [],
                    "instructions": [], "parse_errors": []}
            bodies[start] = body
        def owner(address):
            index = bisect_right(starts, address) - 1
            if index < 0: return None
            body = bodies[starts[index]]
            return body if body["section"] == section and address < body["end"] else None
        for address, name in decoded["labels"]:
            body = owner(address)
            exact = [row for row in symbols.get(name, [])
                     if row["address"] == address and row["section"] == section]
            # An objdump <entry+offset> heading may lack its own ELF symbol;
            # only the exact enclosing entry and offset may supply it.
            offset = re.fullmatch(r"(.+)\+0x([0-9a-f]+)", name)
            relative = (body is not None and offset is not None
                        and offset[1] in body["names"]
                        and body["entry"] + int(offset[2], 16) == address)
            if body is None or (not exact and not relative):
                errors.append("unbound disassembly label at " + hex(address) + ": " + name)
            elif address != body["entry"]:
                if exact and any(row["size"] or any(flag in "".join(row["flags"]) for flag in "Fguw")
                                 for row in exact):
                    errors.append("ambiguous interior code symbol: " + name)
                body["interior_labels"].append({"address": address, "name": name})
        for row in decoded["instructions"]:
            address, body = row["address"], owner(row["address"])
            if address in instructions:
                errors.append("overlapping decoded sections at " + hex(address))
            instructions[address] = row
            if body is None:
                errors.append("instruction outside emitted routine ranges: " + hex(address))
            else:
                body["instructions"].append(row)
                owners[address] = body["entry"]
        for start in starts:
            if start not in owners or owners[start] != start:
                errors.append("emitted entry has no decoded first instruction: " + hex(start))
        for address in decoded["omitted"]:
            body = owner(address) if address is not None else None
            if body is None:
                errors.append("omitted bytes outside a decoded routine in " + section)
            else:
                body["parse_errors"].append("omitted disassembly bytes in body at " + hex(body["entry"]))
        next_address.update(zip(addresses, addresses[1:]))
    if not saw_symbols:
        errors.append("actual ELF symbol table absent: objdump -t is required")
    if not sections: errors.append("actual code disassembly absent")
    return {"symbols": symbols, "bodies": bodies, "starts": sorted(bodies),
            "code_sections": set(sections), "instructions": instructions, "owners": owners,
            "next_address": next_address, "errors": errors}


def _unique_symbol(image, name, code=False):
    rows = [row for row in image["symbols"].get(name, [])
            if row["section"] != "*UND*" and (not code or row["section"] in image["code_sections"])]
    identities = {(row["address"], row["section"]) for row in rows}
    if len(identities) != 1:
        raise ValueError("missing or ambiguous actual ELF symbol: " + name)
    return next(iter(identities))[0]


def _body_at(image, address):
    entry = image["owners"].get(address)
    if entry is None:
        raise ValueError("transfer/address is not inside a decoded routine range: " + hex(address))
    body = image["bodies"][entry]
    if not body["entry"] <= address < body["end"]:
        raise ValueError("transfer/address exceeds its routine range: " + hex(address))
    return body


def _parts(args, arch):
    text = args.split("//", 1)[0]
    if arch == "amd64":
        text = text.split("#", 1)[0]
    text = re.sub(r"<[^>]+>", "", text)
    values, start, depth = [], 0, 0
    for index, char in enumerate(text):
        if char in "([": depth += 1
        elif char in ")]": depth -= 1
        elif char == "," and depth == 0:
            values.append(text[start:index].strip()); start = index + 1
    values.append(text[start:].strip())
    return values


def _integer(token, address=False):
    token = token.strip().lstrip("#$")
    if token.startswith(("0x", "-0x", "+0x")):
        return int(token, 16)
    return int(token, 16 if address else 10)


def _reg(token, arch):
    token = token.strip().lstrip("%").lower()
    if arch == "arm64":
        if token in ("xzr", "wzr"): return "zero"
        return "x" + token[1:] if re.fullmatch(r"[xw][0-9]+", token) else None
    aliases = {}
    for full, names in (("rax", ("rax", "eax", "ax", "al", "ah")),
                        ("rbx", ("rbx", "ebx", "bx", "bl", "bh")),
                        ("rcx", ("rcx", "ecx", "cx", "cl", "ch")),
                        ("rdx", ("rdx", "edx", "dx", "dl", "dh")),
                        ("rsi", ("rsi", "esi", "si", "sil")),
                        ("rdi", ("rdi", "edi", "di", "dil")),
                        ("rbp", ("rbp", "ebp", "bp", "bpl")),
                        ("rsp", ("rsp", "esp", "sp", "spl"))):
        aliases.update((name, full) for name in names)
    if token in aliases: return aliases[token]
    match = re.fullmatch(r"(r(?:1[0-5]|[89]))[bwd]?", token)
    return match[1] if match else None


def _reg_width(token, arch):
    token = token.strip().lstrip("%").lower()
    if _reg(token, arch) is None: return None
    if arch == "arm64": return 32 if token.startswith("w") else 64
    if token in ("al", "ah", "bl", "bh", "cl", "ch", "dl", "dh", "sil", "dil", "bpl", "spl") or re.fullmatch(r"r(?:1[0-5]|[89])b", token): return 8
    if token in ("ax", "bx", "cx", "dx", "si", "di", "bp", "sp") or re.fullmatch(r"r(?:1[0-5]|[89])w", token): return 16
    if token.startswith("e") or re.fullmatch(r"r(?:1[0-5]|[89])d", token): return 32
    return 64


def _transfer(row, arch):
    op, args = row["op"], row["args"]
    if op in ("ret", "retq"):
        if args.strip() not in (("",) if arch == "amd64" else ("", "x30")):
            return {"kind":"unsupported", "reason":"unreviewed return operand"}
        return {"kind":"return"}
    if arch == "amd64":
        control = op.startswith("j") or op in ("call", "callq", "loop", "loope", "loopne", "jrcxz", "jecxz")
        indirect = control and "*" in args
    else:
        control = op in ("b", "bl", "br", "blr", "cbz", "cbnz", "tbz", "tbnz") or op.startswith("b.")
        indirect = op in ("br", "blr")
    if not control:
        if op in ("syscall", "sysenter", "int", "svc", "hvc", "smc", "eret", "brk", "hlt", "ud2", "bnd", "notrack", "lcall", "ljmp", "iret", "iretq", "retf", "sysret"):
            return {"kind":"unsupported", "reason":"unreviewed control instruction"}
        return None
    if indirect:
        return {"kind":"indirect"}
    token = _parts(args, arch)[-1].strip().split()[0] if _parts(args, arch)[-1].strip() else ""
    try:
        return {"kind":"direct", "target":_integer(token, address=True),
                "call":op in ("call", "callq", "bl")}
    except ValueError:
        return {"kind":"unsupported", "reason":"unresolved direct transfer"}


def direct_targets(body, image, arch):
    """Every direct call/branch, including conditional out-of-body edges."""
    targets = []
    for row in body["instructions"]:
        transfer = _transfer(row, arch)
        if transfer and transfer["kind"] == "direct":
            targets.append(transfer["target"])
    return sorted(set(targets))


def _range_fallthrough(body, image, arch):
    """Reject a reachable implicit successor outside a derived routine range.

    Intel SDM1 6.4.1/7.3.8 and ARM M.c C6.2.33/34/43: calls have a
    return successor, conditional branches have two, returns/unconditional
    branches have none. This bounded walk ignores unreachable alignment
    padding after RET. Explicit foreign targets remain closure's obligation.
    """
    rows = {row["address"]: row for row in body["instructions"]}
    # Main owns cold bounds-failure calls. Both runtime paths die or raise
    # (pasemit49871+/61135+, SysFault1327+); neither resumes after the call.
    # This does not admit another boundary in an arithmetic closure.
    nonreturn = ({_unique_symbol(image, "rt_boundsfail", code=True)}
                 if "pas_main" in body["names"] else set())
    pending, seen, errors = [body["entry"]], set(), []
    while pending:
        address = pending.pop()
        if address in seen: continue
        seen.add(address)
        if address not in rows:
            errors.append("missing decoded successor in " + body["names"][0])
            continue
        row = rows[address]
        transfer = _transfer(row, arch)
        if transfer and transfer["kind"] == "return": continue
        call = row["op"] in ("call", "callq", "bl", "blr")
        if transfer and transfer["kind"] == "direct":
            if call and transfer["target"] in nonreturn: continue
            if not call and transfer["target"] in rows: pending.append(transfer["target"])
            if row["op"] in ("jmp", "jmpq", "b"): continue
        elif transfer and not call:
            continue  # Closure rejects unresolved/unsupported transfers.
        following = image["next_address"].get(address)
        if following not in rows:
            errors.append("reachable fallthrough crosses routine range in " + body["names"][0]
                          + " at " + hex(address))
        else:
            pending.append(following)
    return errors


def _addresses(body, image, arch, feature_address):
    """Conservative straight-block constants, memory references and getter ABI.

    ADRP+ADD(+LDR), ADR, AMD64 RIP-relative LEA/load and immediate MOV are
    resolved numerically. Frame slots preserve known pointer/zero values.
    Other writes invalidate constants; calls and block joins clear them.
    This is deliberately a restricted decoder, not a general disassembler.
    """
    regs, slots, references, feature_reads, returns = {"zero":0}, {}, [], [], []
    joins = set(direct_targets(body, image, arch)) - {body["entry"]}
    def store_slot(frame, known, width):
        # Cache only a complete, known 64-bit word. Partial, unknown or
        # unbound writes may overlap any saved pointer, so discard the
        # cache. Exact full-word writes preserve proven disjoint slots.
        if frame is None or width != 64 or known is None:
            slots.clear()
            return
        for key in list(slots):
            if key[0] == frame[0] and key[1] < frame[1] + 8 and frame[1] < key[1] + 8:
                del slots[key]
        slots[frame] = known & ((1 << 64) - 1)

    def value(token):
        register = _reg(token, arch)
        if register is not None:
            if register == "zero": return 0
            width = _reg_width(token, arch)
            # A partial source is deliberately unknown: no byte/word write
            # or extension can establish a whole code-pointer value here.
            if width is not None and width < 32: return None
            known = regs.get(register)
            return known & 0xffffffff if width == 32 and known is not None else known
        if arch == "amd64" and not token.strip().startswith("$"):
            return None  # Bare AT&T numbers are memory, never immediates.
        try: return _integer(token)
        except ValueError: return None
    def memory(token, row):
        if arch == "amd64":
            if re.fullmatch(r"(?:0x)?[0-9a-f]+", token):
                return _integer(token, address=True), None
            match = re.fullmatch(r"([^()]*)\(%(r[a-z0-9]+)\)", token)
            if not match: return None, None
            try:
                displacement = _integer(match[1]) if match[1] else 0
            except ValueError:
                return None, None  # Segment/unknown addressing proves no constant.
            base = match[2]
            if base == "rip":
                following = image["next_address"].get(row["address"])
                if following is None: return None, None
                return following + displacement, None
            if base == "rbp": return None, (base, displacement)
            return (regs[base] + displacement if base in regs else None), None
        match = re.fullmatch(r"\[([xw][0-9]+|sp)(?:,\s*#?(-?(?:0x[0-9a-f]+|[0-9]+)))?\]", token)
        if not match: return None, None
        base, displacement = match[1], _integer(match[2]) if match[2] else 0
        if base == "x29": return None, (base, displacement)
        return (regs[base] + displacement if base in regs else None), None
    for row in body["instructions"]:
        if row["address"] in joins:
            regs, slots = {"zero":0}, {}
        op, parts = row["op"], _parts(row["args"], arch)
        # All explicit memory operands matter, including BT/TEST and writes.
        for operand in parts:
            address, frame = memory(operand, row)
            if address is not None and feature_address <= address < feature_address + 8:
                if row not in feature_reads: feature_reads.append(row)
        transfer = _transfer(row, arch)
        if transfer and transfer["kind"] == "return":
            returns.append({"instruction":row["address"],
                "code":regs.get("rax" if arch == "amd64" else "x0"),
                "environment":regs.get("rdx" if arch == "amd64" else "x2")})
        if transfer:
            regs, slots = {"zero":0}, {}
            continue
        destination = _reg(parts[-1] if arch == "amd64" else parts[0], arch)
        written, handled = None, False
        if arch == "arm64" and op in ("adrp", "adr") and len(parts) == 2:
            try: written, handled = _integer(parts[1], address=True), True
            except ValueError: pass
        elif arch == "arm64" and op in ("add", "sub") and len(parts) in (3,4):
            base, offset = value(parts[1]), value(parts[2])
            if len(parts) == 4:
                shift = re.fullmatch(r"lsl\s+#?(12|0)", parts[3])
                offset = offset << int(shift[1]) if shift and offset is not None else None
            written = (base + (offset if op == "add" else -offset)) if base is not None and offset is not None else None
            handled = True
        elif arch == "amd64" and op.startswith("lea") and len(parts) == 2:
            written, unused = memory(parts[0], row); handled = True
        elif (op in ("mov", "movq", "movl", "movabs", "movabsq")
              if arch == "amd64" else op == "mov") and len(parts) == 2:
            source, dest = (parts[0], parts[1]) if arch == "amd64" else (parts[1], parts[0])
            if _reg(dest, arch) is None:
                address, frame = memory(dest, row)
                source_width = _reg_width(source, arch)
                whole = (arch == "amd64" and op in ("mov", "movq") and
                         (source_width == 64 or (op == "movq" and _reg(source, arch) is None)))
                store_slot(frame, value(source), 64 if whole else None)
                handled = True
            else:
                address, frame = memory(source, row)
                if address is not None and feature_address <= address < feature_address + 8:
                    feature_reads.append(row)
                whole = arch == "amd64" and op in ("mov", "movq") and _reg_width(dest, arch) == 64
                written = (slots.get(frame) if whole else None) if frame is not None else value(source)
                handled = True
        elif arch == "arm64" and op in ("ldr", "ldur", "ldrb", "ldrh", "ldrsw") and len(parts) == 2:
            address, frame = memory(parts[1], row)
            if address is not None and feature_address <= address < feature_address + 8:
                feature_reads.append(row)
            whole = op in ("ldr", "ldur") and _reg_width(parts[0], arch) == 64
            written, handled = slots.get(frame) if whole and frame is not None else None, True
        elif arch == "arm64" and op in ("stp", "ldp") and len(parts) == 3:
            address, frame = memory(parts[2], row)
            widths = [_reg_width(operand, arch) for operand in parts[:2]]
            stride = 8 if widths == [64, 64] else 4 if widths == [32, 32] else None
            if address is not None and stride is not None and address < feature_address + 8 and address + 2 * stride > feature_address:
                if row not in feature_reads: feature_reads.append(row)
            whole = widths == [64, 64] and len({_reg(operand, arch) for operand in parts[:2]}) == 2
            if op == "stp":
                if whole and frame is not None:
                    for index, operand in enumerate(parts[:2]):
                        store_slot((frame[0], frame[1] + 8 * index), value(operand), 64)
                else:
                    slots.clear()
            else:
                loaded = [slots.get((frame[0], frame[1] + 8 * index)) if whole and frame is not None else None for index in (0, 1)]
                for operand, known in zip(parts[:2], loaded):
                    register = _reg(operand, arch)
                    if register is not None and register != "zero":
                        regs.pop(register, None)
                        if register == "x29": slots.clear()
                        if known is not None:
                            regs[register] = known
                            references.append({"instruction":row["address"], "register":register, "address":known})
            handled, destination = True, None
        elif arch == "arm64" and op in ("stp", "ldp") and len(parts) == 4:
            # Post-index frame epilogues write both destinations, not just
            # the first one. Their memory values are not proven constants.
            if op == "ldp":
                for operand in parts[:2]:
                    register = _reg(operand, arch)
                    if register is not None and register != "zero": regs.pop(register, None)
            slots.clear()
            handled, destination = True, None
        elif arch == "arm64" and op == "fmov" and len(parts) == 2:
            # An FP destination preserves code/env GPRs. The reverse form
            # writes a GPR and invalidates its previous constant value.
            handled, written = True, None
        elif arch == "amd64" and op in ("push", "pushq", "pushw"):
            # PUSH writes memory at an unproved RSP-relative address.
            regs.pop("rsp", None); slots.clear()
            handled, destination = True, None
        elif arch == "amd64" and op in ("leave", "leaveq"):
            regs.pop("rbp", None); regs.pop("rsp", None); slots.clear()
            handled, destination = True, None
        elif arch == "amd64" and op.startswith("pop") and len(parts) == 1:
            regs.pop("rsp", None); slots.clear()
            handled, written = True, None
        elif arch == "arm64" and op in ("str", "stur") and len(parts) == 2:
            address, frame = memory(parts[1], row)
            store_slot(frame, value(parts[0]), _reg_width(parts[0], arch))
            handled, destination = True, None
        elif ((arch == "amd64" and op.startswith(("xor", "sub")) and len(parts) == 2 and parts[0] == parts[1])
              or (arch == "arm64" and op in ("eor", "sub") and len(parts) == 3 and parts[1] == parts[2])):
            written, handled = 0, True
        elif (op in ("cmp", "cmpb", "cmpw", "cmpl", "cmpq", "test", "testb", "testw", "testl", "testq",
                     "bt", "btw", "btl", "btq", "nop", "nopl", "nopw") if arch == "amd64"
              else op in ("cmp", "cmn", "tst", "nop", "fcmp")):
            # These source-reviewed getter forms do not write a code/env GPR.
            destination, handled = None, True
        if arch == "arm64":
            # Pre/post-index addressing writes its base even for a store.
            # Such writes cannot leave a stale known code pointer behind.
            for index, operand in enumerate(parts):
                post_pair = op in ("ldp", "stp") and len(parts) == 4 and index == 2
                if operand.endswith("!") or post_pair:
                    base = re.match(r"\[(x[0-9]+|sp)", operand)
                    if base:
                        register = _reg(base[1], arch)
                        if register is not None: regs.pop(register, None)
                        slots.clear()
        if not handled:
            # Unknown instructions can have implicit or multiple GPR
            # destinations (MUL/XCHG, for example). No old getter constant
            # survives one merely because its final operand names another
            # register. Reviewed complete writes can establish it again.
            regs, slots, destination = {"zero": 0}, {}, None
        if destination == "zero":
            destination = None  # XZR/WZR writes are discarded (ARM B1.2.3).
        if destination is not None:
            regs.pop(destination, None)
            if destination == ("rbp" if arch == "amd64" else "x29"):
                slots.clear()  # A new frame base invalidates old relative slots.
            width = _reg_width(parts[-1] if arch == "amd64" else parts[0], arch)
            if handled and written is not None and (width is None or width >= 32):
                if width == 32:
                    written &= 0xffffffff
                regs[destination] = written
                if op != "adrp":
                    references.append({"instruction":row["address"], "register":destination, "address":written})
        if re.search(r"\brt_cpuhas\b", row["args"]):
            feature_reads.append(row)
    return {"materialized":references, "feature_reads":feature_reads, "returns":returns}


def selection(text, arch, cpu, variant, native_has_fma=None):
    issues, observations = [], {}
    try:
        if arch not in ("amd64", "arm64"):
            raise ValueError("unsupported architecture")
        if cpu == "native" and type(native_has_fma) is not bool:
            raise ValueError("native requires actual ordinary base-probe FMA capability")
        if cpu not in ("base", "v3", "v3+aes+pclmul", "native", "max"):
            raise ValueError("unreviewed target profile")
        global_hardware = arch == "arm64" or (native_has_fma if cpu == "native" else cpu != "base")
        public_hardware = arch == "arm64" or variant == "v3"
        if variant not in (("base", "v3") if arch == "amd64" else ("base", "v8.2+crypto")):
            raise ValueError("unreviewed actual pasnum object variant")
        image = functions(text)
        issues.extend(image["errors"])
        feature_address = _unique_symbol(image, "rt_cpufeat")
        runtime = {_unique_symbol(image, name, code=True):name for name in _RUNTIME_BOUNDARY}
        code_addresses = {row["address"] for name, rows in image["symbols"].items()
                          if name.startswith("p_f.") for row in rows if row["section"] in image["code_sections"]}

        checked_ranges = set()
        def check_range(body):
            if body["entry"] not in checked_ranges:
                checked_ranges.add(body["entry"])
                issues.extend(_range_fallthrough(body, image, arch))

        def find(name, core=False):
            prefix = r"p_f\.6_pasnum[0-9]+_" if core else r"p_f\.0_[0-9]+_"
            names = [symbol for symbol in image["symbols"] if re.fullmatch(prefix + name, symbol)]
            if len(names) != 1:
                raise ValueError("missing or duplicate actual linked routine: " + name)
            address = _unique_symbol(image, names[0], code=True)
            body = _body_at(image, address)
            if body["entry"] != address:
                raise ValueError("routine has no exact disassembled body: " + name)
            check_range(body)
            return names[0], body

        def closure(root):
            pending, seen, boundaries = [root["entry"]], set(), []
            while pending:
                entry = pending.pop()
                if entry in seen: continue
                seen.add(entry)
                body = image["bodies"][entry]
                check_range(body)
                issues.extend(body["parse_errors"])
                for row in body["instructions"]:
                    if row["op"].startswith(("(", ".")) or row["op"] in ("undefined", "bad"):
                        issues.append("unparsed executable bytes in " + body["names"][0])
                    transfer = _transfer(row, arch)
                    if not transfer or transfer["kind"] == "return": continue
                    if transfer["kind"] != "direct":
                        issues.append("unresolved arithmetic transfer in " + body["names"][0] + ": " + row["text"])
                        continue
                    target = transfer["target"]
                    if target in runtime:
                        boundaries.append({"instruction":row["address"], "name":runtime[target]})
                        continue
                    other = _body_at(image, target)
                    if other["entry"] == entry: continue
                    if target != other["entry"] or not any(name.startswith("p_f.") for name in other["names"]):
                        issues.append("unreviewed arithmetic edge to " + hex(target))
                        continue
                    pending.append(other["entry"])
            return sorted(seen), boundaries

        def fmas(body):
            return [row for row in body["instructions"] if
                    (row["op"].startswith(("vfmadd", "vfmsub", "vfnmadd", "vfnmsub")) if arch == "amd64"
                     else row["op"] in ("fmadd", "fmsub", "fnmadd", "fnmsub", "fmla", "fmls"))]

        def inspect(name, width, hardware, portable=False, core=False):
            symbol, body = find(name, core)
            reachable, boundaries = closure(body)
            own, all_fma, feature_reads = fmas(body), [], []
            for entry in reachable:
                child = image["bodies"][entry]
                all_fma += [{"body":child["names"], "instruction":row} for row in fmas(child)]
                feature_reads += _addresses(child, image, arch, feature_address)["feature_reads"]
            targets = direct_targets(body, image, arch)
            observations[name] = {"symbol":symbol, "entry":body["entry"], "expected_hardware":hardware,
                "direct_targets":targets, "reachable":reachable, "runtime_boundaries":boundaries,
                "own_fma":own, "reachable_fma":all_fma, "feature_tests":feature_reads}
            if feature_reads:
                issues.append(name + ": hot runtime CPU feature access remains")
            if hardware is True:
                if any(re.fullmatch(r"p_f\.6_pasnum[0-9]+_pasfmasofts?", candidate)
                       for entry in reachable for candidate in image["bodies"][entry]["names"]):
                    issues.append(name + ": hardware path also reaches a portable FMA kernel")
                if len(own) != 1:
                    issues.append(name + ": expected exactly one own scalar FMA")
                for row in own:
                    correct = (row["op"] == "vfmadd213" + ("sd" if width == 64 else "ss") if arch == "amd64"
                               else row["op"] == "fmadd" and re.match(("d" if width == 64 else "s") + r"[0-9]+,", row["args"]))
                    if not correct: issues.append(name + ": wrong scalar FMA precision/operation")
            elif hardware is False and all_fma:
                issues.append(name + ": portable closure reaches FMA")
            if portable:
                unused, soft = find("pasfmasoft" + ("s" if width == 32 else ""), core=True)
                if soft["entry"] not in targets:
                    issues.append(name + ": explicit shared portable kernel not selected")
            return body

        for suffix, width in (("d",64), ("s",32)):
            for name in ("default", "after", "ordered"):
                inspect(name + suffix, width, global_hardware, portable=not global_hardware)
            inspect("localbase" + suffix, width, arch == "arm64", portable=arch == "amd64")
            inspect("localfast" + suffix, width, True)
            inspect("soft" + suffix, width, False, portable=True)
            public = inspect("public" + suffix, width, False if not public_hardware else None)
            core_name = "pasfma" + ("s" if width == 32 else "")
            core = inspect(core_name, width, public_hardware, portable=not public_hardware, core=True)
            if core["entry"] not in direct_targets(public, image, arch):
                issues.append("public" + suffix + ": public API call disappeared")
            unused, pointer = find("pointer" + suffix)
            indirect = [row for row in pointer["instructions"]
                        if (_transfer(row, arch) or {}).get("kind") == "indirect"]
            if len(indirect) != 1:
                issues.append("pointer" + suffix + ": expected exactly one function-value transfer")
            unused, getter = find("publicvalue" + suffix)
            reachable, boundaries = closure(getter)
            if reachable != [getter["entry"]]:
                issues.append("publicvalue" + suffix + ": unexpected Pascal getter call")
            addresses = _addresses(getter, image, arch, feature_address)
            materialized_code = sorted({row["address"] for row in addresses["materialized"] if row["address"] in code_addresses})
            if materialized_code != [core["entry"]]:
                issues.append("publicvalue" + suffix + ": wrong materialized public code address")
            if not addresses["returns"] or any(row["code"] != core["entry"] or row["environment"] != 0
                                                for row in addresses["returns"]):
                issues.append("publicvalue" + suffix + ": public function-value return ABI unproved")
            observations["publicvalue" + suffix] = {"symbol":getter["names"], "addresses":addresses,
                "expected_code":core["entry"], "materialized_code":materialized_code,
                "runtime_boundaries":boundaries}
        inspect("mixedd",64,global_hardware,portable=not global_hardware)
        inspect("loopd",64,global_hardware,portable=not global_hardware)
        main = _body_at(image, _unique_symbol(image, "pas_main", code=True))
        if main["entry"] != _unique_symbol(image, "pas_main", code=True):
            raise ValueError("Main has no exact linked body")
        check_range(main)
        main_targets = direct_targets(main, image, arch)
        main_fma = fmas(main)
        if arch == "amd64":
            if not global_hardware and main_fma:
                issues.append("base-capability Main contains optional FMA")
            cross = "localbase" if global_hardware else "localfast"
            for suffix in ("d", "s"):
                unused, callee = find(cross + suffix)
                if callee["entry"] not in main_targets:
                    issues.append("Main lost cross-capability direct call to " + cross + suffix)
        observations["pas_main"] = {"entry":main["entry"], "direct_targets":main_targets, "own_fma":main_fma}
    except (ValueError, KeyError, IndexError) as error:
        issues.append(type(error).__name__ + ": " + str(error))
    return {"ok":not issues, "issues":issues, "arch":arch, "cpu":cpu,
            "pasnum_variant":variant, "native_has_fma":native_has_fma,
            "functions":observations}


def sdk_units():
    lines = (ROOT / "Makefile").read_text().splitlines()
    result = set()
    for index, line in enumerate(lines):
        if re.match(r"^(?:CORE_UNITS|LIB_UNITS)\s*:?=", line):
            block = line
            while line.endswith("\\"):
                index += 1
                line = lines[index]
                block += " " + line
            result.update(re.findall(r"src/(?:lib|rtl)/(\w+)\.paslang", block))
    if "pasnum" not in result:
        raise RuntimeError("actual SDK unit list missing")
    return sorted(result)


def sdk_paths(sdk, arch):
    level = "v3" if arch == "amd64" else "v8.2+crypto"
    paths = []
    for unit in sdk_units():
        interface, base, variant = sdk / (unit + ".pi"), sdk / (unit + ".o"), sdk / level / (unit + ".o")
        if not all(path.is_file() for path in (interface, base, variant)):
            raise RuntimeError("ordinary SDK profile incomplete: " + unit + " in " + str(sdk))
        if variant.stat().st_mtime_ns < base.stat().st_mtime_ns:
            raise RuntimeError("ordinary SDK variant is stale: " + str(variant))
        paths += [interface, base, variant]
    return paths


def linked_inputs(program, sdk, arch, cpu):
    lines = program.with_suffix(".link").read_text().splitlines()
    if len(lines) < 6 or lines[0] != "-o" or lines[2:4] != ["--gc-sections", "-T"]:
        raise RuntimeError("malformed actual linker command: " + str(program))
    if Path(lines[1]).resolve() != program.resolve():
        raise RuntimeError("link receipt names another executable")
    level = "v3" if arch == "amd64" else "v8.2+crypto"
    inputs, selected = {}, {}
    for entry in lines[6:]:
        path = Path(entry)
        path = (path if path.is_absolute() else ROOT / path).resolve()
        interface = sdk / (path.stem.lower() + ".pi")
        base = interface.with_suffix(".o")
        variant = sdk / level / path.name
        if not interface.is_file() or path not in (base.resolve(), variant.resolve()):
            raise RuntimeError("linked unit escaped explicit ordinary SDK: " + str(path))
        selected[path.stem.lower()] = "base" if path == base.resolve() else level
        inputs.update(snapshot((path, interface)))
    if "pasnum" not in selected:
        raise RuntimeError("actual linked pasnum.o missing")
    wanted = ("base" if cpu in ("base", "v3") else level if cpu in ("v3+aes+pclmul", "max") else None)
    if wanted is not None and selected["pasnum"] != wanted:
        raise RuntimeError("actual pasnum variant contradicts target/freshness selection")
    return {"files": inputs, "selected": selected, "pasnum_variant": selected["pasnum"]}


def artifacts(program, arch):
    paths = [program, *(program.with_suffix(ext) for ext in (".s", ".o", ".link", ".ld"))]
    if not all(path.is_file() for path in paths):
        raise RuntimeError("required compiler artifacts absent: " + str(program))
    header = program.read_bytes()[:20]
    if (len(header) != 20 or header[:6] != b"\x7fELF\x02\x01"
            or int.from_bytes(header[16:18], "little") != 2
            or int.from_bytes(header[18:20], "little") != {"amd64": 62, "arm64": 183}[arch]):
        raise RuntimeError("wrong actual executable ELF target: " + str(program))
    return snapshot(paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("compiler")
    parser.add_argument("builddir")
    parser.add_argument("qemu", nargs="?")
    parser.add_argument("--units-amd64")
    parser.add_argument("--units-arm64")
    parser.add_argument("--out", help="fresh retained output directory")
    parser.add_argument("--target", choices=("all", "amd64", "arm64"), default="all")
    parser.add_argument("--profile", action="append", choices=tuple(dict.fromkeys(sum(PROFILES.values(), ()))))
    parser.add_argument("--inline", action="append", type=int, choices=(0, 40))
    parser.add_argument("--role", choices=("baseline", "candidate", "mutant"), default="candidate")
    parser.add_argument("--expected-version")
    parser.add_argument("--objdump-amd64", default="objdump")
    parser.add_argument("--objdump-arm64", default="aarch64-linux-gnu-objdump")
    options = parser.parse_args()

    def executable(value):
        path = Path(shutil.which(str(value)) or value).resolve()
        if not path.is_file():
            raise RuntimeError("executable absent: " + str(value))
        return path

    builddir, compiler = Path(options.builddir).resolve(), executable(options.compiler)
    if options.out:
        out = Path(options.out).resolve()
        if out.exists():
            parser.error("fresh --out required; previous failures remain retained")
        out.mkdir(parents=True)
    else:
        builddir.mkdir(parents=True, exist_ok=True)
        out = Path(tempfile.mkdtemp(prefix="check-fma-target-", dir=builddir))
    arches = [arch for arch in PROFILES if options.target in ("all", arch)]
    profiles = [(arch, cpu, inline) for arch in arches for cpu in PROFILES[arch]
                if options.profile is None or cpu in options.profile for inline in (options.inline or (0, 40))]
    if not profiles:
        parser.error("no profiles selected for target")
    sdks = {arch: Path((options.units_amd64 if arch == "amd64" else options.units_arm64)
                       or (builddir if arch == "amd64" else builddir / "a64")).resolve() for arch in arches}
    qemu = executable(options.qemu or builddir / "qemu-aarch64") if "arm64" in arches else None
    dumps = {arch: executable(options.objdump_amd64 if arch == "amd64" else options.objdump_arm64) for arch in arches}
    env = {key: value for key, value in os.environ.items()
           if key not in scope.CONTROL_KEYS and not key.startswith("PASLANG_")}
    env.setdefault("PATH", os.defpath)
    env.update(LC_ALL="C", PYTHONDONTWRITEBYTECODE="1")
    source = ROOT / "testdata/fmatarget.paslang"
    expected = ROOT / "testdata/fmatarget.out"
    probe_source = ROOT / "testdata/fmacaps.paslang"
    record = {"kind": "fma-target-v1", "role": options.role, "ok": False, "complete": False,
              "performance_verdict": None, "compiler": str(compiler), "profiles": profiles,
              "python_version": sys.version,
              "expected_builds": len(profiles), "expected_executions": 3 * len(profiles),
              "expected_metadata_executions": 2 if "amd64" in arches else 0,
              "expected_codegen": len(profiles),
              "inputs_before": {}, "commands": [], "builds": [], "executions": [], "codegen": [], "errors": [],
              "metadata_executions": [], "skipped_executions": [], "local_fast_exclusions": []}

    def save():
        signals = scope.received_signals()
        if signals:
            message = "cancellation received: " + str(signals)
            if message not in record["errors"]:
                record["errors"].append(message)
            record["ok"] = False
        record["received_signals"] = signals
        scope.save(out / "results.json", record)

    def fail(message):
        record["errors"].append(message)
        save()

    def command(argv, label, timeout=180, environment=None):
        scope.check_stop()
        argv = list(map(str, argv))
        environment = env if environment is None else environment
        folder = out / (label + ".scope")
        row = {"label": label, "command": argv, "cwd": str(ROOT), "scope": str(folder),
               "environment_controls": {key: value for key, value in environment.items()
                                        if key in scope.CONTROL_KEYS or key in ("LC_ALL", "PYTHONDONTWRITEBYTECODE")},
               "status": "pending"}
        record["commands"].append(row)
        save()
        result = scope.invoke(argv, folder, ROOT, environment, timeout, grace=2, cleanup_timeout=5)
        row.update(status=result["status"], receipt_sha256=sha(folder / "result.json"),
                   cleanup=result["cleanup"], signals=result["received_signals"])
        save()
        if (not result["cleanup"].get("ok") or result.get("received_signals")
                or result.get("signals") or result.get("reason") is not None):
            raise RuntimeError("owned cleanup/cancellation/deadline failure: " + label)
        scope.validate_receipt(folder, argv, ROOT, environment)
        row["validated"] = True
        save()
        scope.check_stop()
        return result, (folder / "stdout").read_bytes(), (folder / "stderr").read_bytes()

    try:
        # cmd/paslangc names these assembler/linker paths explicitly.
        build_tools = [Path("/usr/bin/as"), Path("/usr/bin/ld")]
        if "arm64" in arches:
            build_tools += [Path("/usr/bin/aarch64-linux-gnu-as"), Path("/usr/bin/aarch64-linux-gnu-ld")]
        inputs = [Path(__file__), Path(sys.executable).resolve(), ROOT / "scripts/bench/metadata_scope.py", ROOT / "Makefile",
                  source, expected, probe_source, compiler, *build_tools, *dumps.values(), *([qemu] if qemu else [])]
        inputs += list((ROOT / "src").rglob("*.paslang"))
        for arch in arches:
            inputs += sdk_paths(sdks[arch], arch)
        record["inputs_before"] = snapshot(inputs)
        save()
        want = expected_output(source.read_text())
        if want != expected.read_bytes():
            raise RuntimeError("independent Fraction oracle differs from retained fmatarget.out")
        result, stdout, stderr = command([compiler, "-v"], "compiler-version", 60)
        record["observed_version"] = stdout.decode("utf-8", "replace")
        if (result["status"] != 0 or stderr or not stdout.startswith(b"paslangc ")
                or (options.expected_version and options.expected_version not in stdout.decode().split())):
            raise RuntimeError("compiler version or diagnostics differ")
        native_has_fma, native_features = None, None
        if "amd64" in arches:
            probe = out / "fma-host-capabilities"
            result, stdout, stderr = command([compiler, "-target", "amd64", "-cpu", "base", "-inline", 0,
                                              "-Fu", sdks["amd64"], "-o", probe, probe_source], "host-capabilities-build")
            row = {"clean_diagnostics": result["status"] == 0 and stdout == b"" and stderr == b""}
            record["probe_build"] = row
            save()
            if not row["clean_diagnostics"]:
                raise RuntimeError("base host-capability probe compilation differs")
            row["artifacts"] = artifacts(probe, "amd64")
            row["linked_inputs"] = linked_inputs(probe, sdks["amd64"], "amd64", "base")
            save()
            for mode, environment in (("normal", env), ("masked", dict(env, PASLANG_CPU="base"))):
                result, stdout, stderr = command([probe], "host-capabilities-" + mode, 60, environment)
                match = re.fullmatch(rb"runtime-fma ([01])\nruntime-features ([0-9]+)\n", stdout)
                matches = result["status"] == 0 and not stderr and match is not None
                if matches:
                    flag, features = bool(int(match[1])), int(match[2])
                    matches = flag == bool(features & (1 << 9)) and bool(features & 1)
                    if mode == "masked":
                        matches = matches and not flag and features == 1
                    else:
                        native_has_fma, native_features = flag, features
                record["metadata_executions"].append({"mode": mode, "exact_oracle_match": matches,
                    "status": result["status"], "stdout_sha256": hashlib.sha256(stdout).hexdigest()})
                save()
                if not matches:
                    raise RuntimeError("actual base-compiled host capability or runtime mask differs")
            record["native_capabilities"] = {"has_fma": native_has_fma, "feature_word": native_features,
                "source": "actual base-compiled fmacaps; rt_cpuinit uses CPUID and enabled AVX state"}
            save()
        # Exact CpuFeatBit/CpuSetOf source mapping: V2 followed by V3;
        # AES/PCLMUL additionally select the ordinary production v3 object.
        v3_features = {"sse3": 1, "ssse3": 2, "sse41": 3, "sse42": 4, "popcnt": 5, "cx16": 30,
                       "avx": 8, "avx2": 13, "bmi1": 14, "bmi2": 15, "fma": 9, "f16c": 10,
                       "movbe": 11, "lzcnt": 27}
        for arch, cpu, inline in profiles:
            tag = "-".join(map(str, ("fmatarget", arch, cpu, inline)))
            program, sdk = out / tag, sdks[arch]
            result, stdout, stderr = command([compiler, "-target", arch, "-cpu", cpu, "-inline", inline,
                                               "-Fu", sdk, "-o", program, source], tag + "-build")
            build = {"tag": tag, "profile": [arch, cpu, inline], "sdk": str(sdk),
                     "clean_diagnostics": result["status"] == 0 and stdout == b"" and stderr == b""}
            record["builds"].append(build)
            save()
            if not build["clean_diagnostics"]:
                fail(tag + ": compile status or diagnostics differ")
                continue
            build["artifacts"] = artifacts(program, arch)
            build["linked_inputs"] = linked_inputs(program, sdk, arch, cpu)
            save()
            result, text, stderr = command([dumps[arch], "-t", "-dw", "--no-show-raw-insn", "--disassembler-color=off", program], tag + "-elf", 60)
            if result["status"] != 0 or stderr:
                fail(tag + ": actual ELF inspection differs")
            else:
                observed = selection(text.decode("utf-8", "strict"), arch, cpu,
                                     build["linked_inputs"]["pasnum_variant"], native_has_fma=native_has_fma)
                record["codegen"].append({"tag": tag, "observation": observed,
                    "disassembly_sha256": hashlib.sha256(text).hexdigest()})
                if options.role != "baseline" and not observed["ok"]:
                    fail(tag + ": actual ELF FMA selection differs")
                save()
            prefix = [] if arch == "amd64" else [qemu, "-cpu", "cortex-a53" if cpu == "base" else "max"]
            masked = dict(env, PASLANG_CPU="base")
            required = dict(v3_features) if arch == "amd64" and cpu.startswith("v3") else {}
            if cpu == "v3+aes+pclmul":
                required.update(aes=6, pclmul=7)
            missing = [name for name, bit in required.items() if not native_features & (1 << bit)]
            build["execution_capability"] = {"required_features": required, "missing_host_features": missing}
            if missing:
                for mode in ("normal", "masked", "stress"):
                    record["skipped_executions"].append({"tag": tag, "mode": mode,
                        "reason": "actual host lacks compiled target features", "missing_features": missing})
                save()
                print(tag, "compiled and inspected; execution unavailable:", ",".join(missing), flush=True)
                continue
            can_fast = arch == "arm64" or native_has_fma is True
            if not can_fast:
                record["local_fast_exclusions"].append({"tag": tag,
                    "paths": ["localfastd", "localfasts"], "reason": "actual host lacks FMA; fixture prints portable counterpart"})
            force = ["--force-localfast"] if can_fast else []
            modes = (("normal", env), ("masked", masked),
                     ("stress", dict(env, PASLANG_GCSTRESS="1", PASLANG_GCVERIFY="1", PASLANG_GCPOISON="1")))
            for label, environment in modes:
                result, stdout, stderr = command([*prefix, program, *force], tag + "-" + label,
                                                600 if arch == "arm64" else 180, environment)
                matches = result["status"] == 0 and stdout == want and not stderr
                record["executions"].append({"tag": tag, "mode": label, "status": result["status"],
                    "exact_oracle_match": matches, "local_fast_executed": can_fast,
                    "expected_stdout_sha256": hashlib.sha256(want).hexdigest()})
                if not matches:
                    fail(tag + "/" + label + ": exact semantic output/status differs")
                save()
            print(tag, "retained", flush=True)
    except BaseException as error:
        fail(type(error).__name__ + ": " + str(error))
    finally:
        record["inputs_after"] = after(record["inputs_before"])
        record["inputs_unchanged"] = record["inputs_before"] == record["inputs_after"]
        all_builds = record["builds"] + ([record["probe_build"]] if "probe_build" in record else [])
        linked = {path: value for build in all_builds
                  for path, value in build.get("linked_inputs", {}).get("files", {}).items()}
        built = {path: value for build in all_builds for path, value in build.get("artifacts", {}).items()}
        record["linked_after"] = after(linked)
        record["linked_unchanged"] = linked == record["linked_after"]
        record["artifacts_after"] = after(built)
        record["artifacts_unchanged"] = built == record["artifacts_after"]
        record["compiled_all"] = len(record["builds"]) == record["expected_builds"] and all(b["clean_diagnostics"] for b in record["builds"])
        record["executed_all"] = len(record["executions"]) == record["expected_executions"] and all(r["exact_oracle_match"] for r in record["executions"])
        record["metadata_complete"] = (len(record["metadata_executions"]) == record["expected_metadata_executions"]
            and all(row["exact_oracle_match"] for row in record["metadata_executions"])
            and ("amd64" not in arches or record.get("probe_build", {}).get("clean_diagnostics") is True))
        record["execution_coverage_complete"] = (len(record["executions"]) + len(record["skipped_executions"])
            == record["expected_executions"] and all(row["exact_oracle_match"] for row in record["executions"]))
        record["hardware_execution_available"] = not record["skipped_executions"] and not record["local_fast_exclusions"]
        record["codegen_complete"] = len(record["codegen"]) == record["expected_codegen"]
        record["selection_ok"] = record["codegen_complete"] and all(r["observation"]["ok"] for r in record["codegen"])
        record["complete"] = True
        record["ok"] = (not record["errors"] and record["inputs_unchanged"] and record["linked_unchanged"]
                        and record["artifacts_unchanged"] and record["compiled_all"] and record["metadata_complete"]
                        and record["execution_coverage_complete"]
                        and record["codegen_complete"] and (options.role == "baseline" or record["selection_ok"]))
        record["verdict"] = ("baseline-controls-with-observed-selection-defects"
            if record["ok"] and options.role == "baseline" and not record["selection_ok"]
            else "baseline-controls-selection-matches" if record["ok"] and options.role == "baseline"
            else "pass-with-unavailable-hardware-executions" if record["ok"] and not record["hardware_execution_available"]
            else "pass" if record["ok"] else "failed")
        save()
    print("FMA target " + record["verdict"] + ": " + str(out / "results.json"), flush=True)
    return 0 if record["ok"] else 1


if __name__ == "__main__":
    with scope.signal_scope():
        status = main()
        scope.check_stop()
        raise SystemExit(status)
