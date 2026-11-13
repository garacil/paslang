#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned.
# GPL version 3 or later; see COPYING. No warranty.
"""Rust reference identities and evidence for the selected linked programs.

Rust's rustc book, codegen-options and targets/known-issues, documents that
crate CPU flags do not rebuild std. linux_musl.rs selects bundled CRT inputs;
compiler-builtins/libm has feature detection independent of std_detect.
Consequently neither a musl target name nor target-cpu certifies a process.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


REVIEWED_RELEASE = "1.99.1"
REVIEWED_COMMIT = "58cf8f9c35b355199727627d07ae34a4e2846d67"
TARGET_PROVIDERS = {
    "x86_64-unknown-linux-gnu": "gnu",
    "x86_64-unknown-linux-musl": "musl",
    "aarch64-unknown-linux-musl": "musl",
}
CAPABILITY_ENVIRONMENT = (
    "GLIBC_TUNABLES", "LD_HWCAP_MASK", "RUST_STD_DETECT_UNSTABLE",
    "LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT",
)


class CapabilityError(ValueError):
    """A required identity or retained capability check is unavailable."""


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def file_identity(path):
    """Hash bytes, including a symlink's actual file, and reject a racing write."""
    try:
        path = Path(path)
        before = path.stat()
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for part in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(part)
        after = path.stat()
    except (OSError, TypeError, ValueError) as error:
        raise CapabilityError("cannot fingerprint reference file: " + str(path)) from error
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise CapabilityError("file changed while fingerprinting: " + str(path))
    return {"path": str(path.absolute()), "resolved_path": str(path.resolve()),
            "bytes": after.st_size, "sha256": digest.hexdigest()}


def library_fingerprint(directory):
    """A reusable content identity; changing a library invalidates artifact reuse."""
    directory = Path(directory)
    if not directory.is_dir():
        raise CapabilityError("Rust library directory is absent: " + str(directory))
    entries = []
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            item = file_identity(path)
            entries.append({"name": str(path.relative_to(directory)),
                            "bytes": item["bytes"], "sha256": item["sha256"]})
    if not entries:
        raise CapabilityError("Rust library directory is empty: " + str(directory))
    return {"directory": str(directory.resolve()), "sha256": _digest(entries),
            "files": entries, "file_count": len(entries)}


def rust_runtime_environment(cpu, environment=None):
    if cpu not in ("native", "base"):
        raise CapabilityError("unknown Rust CPU mode: " + str(cpu))
    env = dict(os.environ if environment is None else environment)
    # Use normal provider lookup; injected libraries are a different reference.
    for name in ("LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT"):
        env.pop(name, None)
    if cpu == "native":
        for name in CAPABILITY_ENVIRONMENT:
            env.pop(name, None)
    return env


def capability_environment(environment):
    return {name: environment[name] for name in CAPABILITY_ENVIRONMENT
            if environment.get(name)}


def _capture(arguments, environment=None):
    environment = dict(os.environ if environment is None else environment)
    environment["LC_ALL"] = "C"
    try:
        result = subprocess.run(list(map(str, arguments)), capture_output=True,
                                text=True, timeout=60, env=environment)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CapabilityError("reference metadata failed: " + str(error)) from error
    if result.returncode:
        raise CapabilityError("reference metadata failed: " + " ".join(map(str, arguments))
                              + "\n" + result.stderr[-2000:])
    return {"command": list(map(str, arguments)), "status": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def rust_configuration(rustc, target=None, sysroot=None, provider=None):
    """Resolve one compiler/provider series and fingerprint the selected std.

    This captures metadata, not a compatibility probe or an ISA certificate.
    GNU and musl configurations deliberately have different series/identities.
    """
    executable = shutil.which(str(rustc))
    if executable is None:
        raise CapabilityError("requested Rust compiler is unavailable: " + str(rustc))
    executable = str(Path(executable).absolute())
    metadata = _capture([executable, "-Vv"], rust_runtime_environment("native"))
    if not isinstance(metadata.get("stdout"), str):
        raise CapabilityError("Rust compiler metadata is malformed")
    version = {}
    for line in metadata["stdout"].splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            version[key] = value
    if version.get("release") != REVIEWED_RELEASE or version.get("commit-hash") != REVIEWED_COMMIT:
        raise CapabilityError("Rust source review covers " + REVIEWED_RELEASE + " commit "
                              + REVIEWED_COMMIT + "; review the selected compiler first")
    host = version.get("host")
    if not host:
        raise CapabilityError("Rust compiler did not report its host target")
    target = target or host
    selected_provider = TARGET_PROVIDERS.get(target)
    if selected_provider is None:
        raise CapabilityError("Rust reference target is not reviewed: " + str(target))
    if provider is not None and provider != selected_provider:
        raise CapabilityError("Rust provider does not match target: " + str(provider)
                              + " / " + target)
    sysroot_metadata = None
    if sysroot is None:
        sysroot_metadata = _capture([executable, "--print", "sysroot"],
                                   rust_runtime_environment("native"))
        sysroot = sysroot_metadata["stdout"].strip()
    root = Path(sysroot).resolve()
    std = library_fingerprint(root / "lib" / "rustlib" / target / "lib")
    compiler = file_identity(executable)
    actual_compiler = root / "bin" / "rustc"
    if actual_compiler.is_file():
        compiler["sysroot_binary"] = file_identity(actual_compiler)
    # rustc is a small launcher on some toolchains. Include the code it loads.
    support_entries = []
    for path in sorted((root / "lib").glob("*")):
        if path.is_file() and ("rustc_driver" in path.name or "LLVM" in path.name):
            item = file_identity(path)
            support_entries.append({"name": path.name, "bytes": item["bytes"],
                                    "sha256": item["sha256"]})
    support = {"files": support_entries, "sha256": _digest(support_entries)}
    bundled = root / "lib" / "rustlib" / target / "lib" / "self-contained"
    bundled_provider = (library_fingerprint(bundled) if bundled.is_dir() and
                        any(path.is_file() for path in bundled.rglob("*")) else None)
    if selected_provider == "musl" and (bundled_provider is None or not (bundled / "libc.a").is_file()):
        raise CapabilityError("musl reference requires bundled libc/CRT inputs in its sysroot")
    identity = {"compiler_sha256": compiler["sha256"],
                "compiler_support_sha256": support["sha256"],
                "compiler_version": version, "target": target,
                "provider": selected_provider, "std_sha256": std["sha256"],
                "bundled_provider_sha256": bundled_provider["sha256"] if bundled_provider else None}
    return {"format": "paslang-rust-configuration-v1", "rustc": executable,
            "compiler": compiler, "compiler_metadata": metadata,
            "compiler_support": support, "version": version, "host": host,
            "target": target, "provider": selected_provider,
            "series": "rust-" + target, "sysroot": str(root),
            "sysroot_metadata": sysroot_metadata, "standard_library": std,
            "bundled_provider": bundled_provider, "identity_sha256": _digest(identity),
            "base_capability": {"certified": False,
                "reason": "crate CPU flags do not certify precompiled std, compiler-builtins, libm, unwind or libc/CRT dispatch",
                "required": "binary-bound correctness, ISA and provider evidence for the measured environment"}}


def rust_configuration_metadata(configuration):
    return configuration


def rust_build_args(configuration, cpu):
    if cpu not in ("native", "base"):
        raise CapabilityError("unknown Rust CPU mode: " + str(cpu))
    target = configuration["target"]
    if cpu == "native" and target.split("-", 1)[0] != configuration["host"].split("-", 1)[0]:
        raise CapabilityError("target-cpu=native cannot describe a cross-architecture reference")
    processor = "native" if cpu == "native" else ("x86-64" if target.startswith("x86_64-") else "generic")
    arguments = ["--target", target, "--sysroot", configuration["sysroot"],
                 "-C", "opt-level=3", "-C", "target-cpu=" + processor]
    if configuration["provider"] == "musl":
        arguments += ["-C", "link-self-contained=yes"]
        if target.startswith("aarch64-"):
            linker = shutil.which("ld.lld")
            if linker is None:
                raise CapabilityError("AArch64 musl reference requires ld.lld")
            arguments += ["-C", "linker=" + linker, "-C", "linker-flavor=ld.lld",
                          "-C", "link-arg=--fix-cortex-a53-843419"]
    return arguments


def rust_binary_metadata(configuration, path):
    """Observe ELF linkage and hash the actual dynamic provider closure.

    ldd is used only on the trusted, locally compiled benchmark executable.
    A static musl executable instead records the bundled provider fingerprint.
    Neither observation alone proves its effective instruction set.
    """
    binary = file_identity(path)
    inspector = shutil.which("readelf")
    if inspector is None:
        raise CapabilityError("readelf is required to identify Rust linked providers")
    elf = _capture([inspector, "-W", "-h", "-l", "-d", "-n", path],
                   rust_runtime_environment("native"))
    text = elf["stdout"]
    machine = "Advanced Micro Devices X86-64" if configuration["target"].startswith("x86_64-") else "AArch64"
    if ("ELF Header:" not in text or not re.search(r"Class:\s+ELF64\b", text) or
            not re.search(r"Machine:\s+" + re.escape(machine), text)):
        raise CapabilityError("Rust linked-program ELF metadata is malformed or has the wrong architecture")
    needed = re.findall(r"\(NEEDED\).*?Shared library: \[(.*?)\]", text)
    interpreter_match = re.search(r"Requesting program interpreter:\s*(.*?)\]", text)
    interpreter = interpreter_match.group(1) if interpreter_match else None
    providers, loader = [], None
    if needed or interpreter:
        ldd = shutil.which("ldd")
        if ldd is None:
            raise CapabilityError("ldd is required to fingerprint the GNU dynamic provider closure")
        loader = _capture([ldd, str(Path(path).absolute())], rust_runtime_environment("native"))
        for line in loader["stdout"].splitlines():
            if "not found" in line:
                raise CapabilityError("unresolved Rust provider: " + line.strip())
            match = re.match(r"\s*(\S+)\s+=>\s+(/\S+)\s+\(", line)
            direct = re.match(r"\s*(/\S+)\s+\(", line)
            if match:
                soname, location = match.groups()
                soname = Path(soname).name
            elif direct:
                location = direct.group(1)
                soname = Path(location).name
            else:
                continue
            item = file_identity(location)
            providers.append({"soname": soname, **item})
        observed = {item["soname"] for item in providers}
        if set(needed) - observed:
            raise CapabilityError("dynamic provider closure is incomplete: " + repr(sorted(set(needed) - observed)))
    if configuration["provider"] == "musl" and (needed or interpreter):
        raise CapabilityError("musl series requires the selected self-contained static provider")
    if configuration["provider"] == "gnu" and (not interpreter or not any(
            item["soname"].startswith("libc.so") for item in providers)):
        raise CapabilityError("GNU series requires ordinary dynamic GNU libc linkage")
    provider_identity = [{"soname": item["soname"], "sha256": item["sha256"],
                          "bytes": item["bytes"]} for item in providers]
    provider_identity.sort(key=lambda item: item["soname"])
    provider_sha256 = _digest({"dynamic": provider_identity,
                              "bundled": configuration["bundled_provider"]["sha256"]
                              if configuration["bundled_provider"] else None})
    identity = {"configuration_sha256": configuration["identity_sha256"],
                "binary_sha256": binary["sha256"], "provider_sha256": provider_sha256}
    return {"format": "paslang-rust-linked-program-v1", "binary": binary,
            "configuration_sha256": configuration["identity_sha256"],
            "needed": needed, "interpreter": interpreter, "readelf": elf,
            "loader": loader, "providers": providers,
            "provider_sha256": provider_sha256, "identity_sha256": _digest(identity),
            "isa_certified": False}


# Only instructions available in the x86-64/SSE2 base are accepted here.
# REP-BSF/TZCNT is excluded here: its zero/flags semantics require an exact
# reviewed context, even though the encoding executes on baseline machines.
# ENDBR64 is backward-compatible when CET is disabled; it grants no ISA use.
_BASE_SCALAR = set("""adc add and bsf bsr bswap bt btc btr bts call cbw cdq cdqe
clc cld cltq cmc cmp cmpxchg cmpxchg8b cpuid cqo cqto cs cwtl cwtd cwtq cwd
cwde data16 dec div endbr64 enter hlt idiv imul in inc int int3 iret jmp
lea leave lock lods lodsb lodsl lodsq lodsw loop loope loopne mov movabs movs
movsb movsbl movsbq movsd movsl movslq movsq movss movsw movswl movswq movsxd
movsx movzbl movzbq movzwl movzwq movzx mul neg nop not or out pause pop popf
popfq push pushf pushfq rcl rcr rdtsc rep repe repz repne repnz ret retq rol ror
sal sar sbb scas scasb scasl scasq scasw shl shld shr shrd stc std stos
stosb stosl stosq stosw sub syscall sysret test ud2 wait xadd xchg xlat
xor""".split())
_BASE_SSE = set("""addpd addps addsd addss andnpd andnps andpd andps cmppd cmpps
cmpsd cmpss comisd comiss cvtdq2pd cvtdq2ps cvtpd2dq cvtpd2pi cvtpd2ps
cvtpi2pd cvtpi2ps cvtps2dq cvtps2pd cvtps2pi cvtsd2si cvtsd2ss cvtsi2sd
cvtsi2ss cvtss2sd cvtss2si cvttpd2dq cvttpd2pi cvttps2dq cvttps2pi cvttsd2si
cvttss2si divpd divps divsd divss emms fxrstor fxsave ldmxcsr lfence maskmovdqu
maskmovq maxpd maxps maxsd maxss mfence minpd minps minsd minss movapd movaps
movd movdqa movdqu movhlps movhpd movhps movlhps movlpd movlps movmskpd movmskps
movntdq movnti movntpd movntps movntq movq movsd movss movupd movups mulpd
mulps mulsd mulss orpd orps packssdw packsswb packuswb paddb paddd paddq paddsb
paddsw paddusb paddusw paddw pand pandn pavgb pavgw pcmpeqb pcmpeqd pcmpeqw
pcmpgtb pcmpgtd pcmpgtw pextrw pinsrw pmaddwd pmaxsw pmaxub pminsw pminub
pmovmskb pmulhuw pmulhw pmullw pmuludq por prefetchnta prefetcht0 prefetcht1
prefetcht2 psadbw pshufd pshufhw pshuflw pshufw pslld pslldq psllq psllw
psrad psraw psrld psrldq psrlq psrlw psubb psubd psubq psubsb psubsw psubusb
psubusw psubw punpckhbw punpckhdq punpckhqdq punpckhwd punpcklbw punpckldq
punpcklqdq punpcklwd pxor rcpps rcpss rsqrtps rsqrtss sfence shufpd shufps
sqrtpd sqrtps sqrtsd sqrtss stmxcsr subpd subps subsd subss ucomisd ucomiss
unpckhpd unpckhps unpcklpd unpcklps xorpd xorps""".split())
_BASE_X87 = set("""f2xm1 fabs fadd faddp fbld fbstp fchs fclex fcmovb fcmovbe
fcmove fcmovnb fcmovnbe fcmovne fcmovnu fcmovu fcom fcomi fcomip fcomp fcompp
fcos fdecstp fdiv fdivp fdivr fdivrp ffree fiadd ficom ficomp fidiv fidivr fild
fimul fincstp finit fist fistp fisub fisubr fld fld1 fldcw fldenv fldl2e fldl2t
fldlg2 fldln2 fldpi fldz fmul fmulp fnclex fninit fnop fnsave fnstcw fnstenv
fnstsw fpatan fprem fprem1 fptan frndint frstor fsave fscale fsin fsincos fsqrt
fst fstp fstsw fsub fsubp fsubr fsubrp ftst fucom fucomi fucomip fucomp fucompp
fxam fxch fxtract fyl2x fyl2xp1""".split())
_CONDITIONS = set("a ae b be c e g ge l le na nae nb nbe nc ne ng nge nl nle no np ns nz o p pe po s z".split())


def _base_mnemonic(name):
    # Intel SDM Vol2A table1-7 and CVTSI2SD: GNU spellings of SSE2 forms.
    if name in ("cmpltsd", "cvtsi2sdl", "cvtsi2sdq"):
        return True
    if name in _BASE_SCALAR or name in _BASE_SSE or name in _BASE_X87:
        return True
    if name.startswith("j") and name[1:] in _CONDITIONS:
        return True
    if name.startswith("cmov") and name[4:] in _CONDITIONS:
        return True
    if name.startswith("set") and name[3:] in _CONDITIONS:
        return True
    # GNU objdump prints operand sizes for many scalar and x87 instructions.
    return name[-1:] in ("b", "w", "l", "q", "s", "t") and (
        name[:-1] in _BASE_SCALAR or name[:-1] in _BASE_X87 or
        (name.endswith("ll") and name[:-2] in _BASE_X87))


def _base_instruction(mnemonic, operands, encoding):
    # VEX/EVEX/APX encodings remain optional even for familiar scalar names.
    octets = list(bytes.fromhex(encoding))
    while octets and (octets[0] in (0xf0, 0xf2, 0xf3, 0x26, 0x2e, 0x36, 0x3e,
                                    0x64, 0x65, 0x66, 0x67) or
                      0x40 <= octets[0] <= 0x4f):
        octets.pop(0)
    if not octets or octets[0] in (0xc4, 0xc5, 0x62, 0xd5):
        return False
    machine_operands = operands.split("#", 1)[0].split("<", 1)[0]
    if re.search(r"%[yz]mm[0-9]|%k[0-7]|%r(?:1[6-9]|2[0-9]|3[01])(?:[bdw])?\b|[{}]", machine_operands):
        return False
    prefixes = {"lock", "rep", "repe", "repz", "repne", "repnz", "data16",
                "cs", "ds", "es", "fs", "gs", "ss", "addr16", "addr32"}
    while mnemonic in prefixes:
        parts = operands.split(None, 1)
        if not parts:
            return False
        mnemonic, operands = parts[0], (parts[1] if len(parts) == 2 else "")
    return _base_mnemonic(mnemonic)


def rust_linked_text(configuration, binary):
    """Disassemble every text byte; keep distinct records for duplicate names."""
    if configuration["target"] != "x86_64-unknown-linux-musl":
        raise CapabilityError("shared linked-text policy currently covers static x86_64 musl only")
    inspector = shutil.which("objdump")
    if inspector is None:
        raise CapabilityError("objdump is required for fresh linked-text ISA validation")
    before = file_identity(binary)
    disassembly = _capture([inspector, "-d", "-C", "--insn-width=16", "--disassemble-zeroes", binary],
                           rust_runtime_environment("native"))
    functions, instructions, references, unknown = {}, 0, [], []
    symbol, current, function_address, addresses = None, [], None, set()

    def finish_function():
        if symbol is not None:
            functions.setdefault(symbol, []).append({"address": function_address,
                                                     "sha256": _digest(current)})

    for line in disassembly["stdout"].splitlines():
        match = re.match(r"^([0-9a-f]+) <(.*)>:$", line)
        if match:
            finish_function()
            function_address, symbol = match.groups()
            current = []
            continue
        if not re.match(r"^\s*[0-9a-f]+:", line):
            if line.strip() == "...":
                raise CapabilityError("disassembler omitted executable bytes")
            continue
        match = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+)+)(\S+)\s*(.*)", line)
        if not match:
            raise CapabilityError("undecoded executable bytes: " + line.strip())
        address, encoding, mnemonic, operands = match.groups()
        if symbol is None or "(bad)" in line or address in addresses:
            raise CapabilityError("cannot classify linked executable text: " + line)
        addresses.add(address)
        instructions += 1
        normalized = re.sub(r"\b[0-9a-f]+ <", "<", operands.split("#", 1)[0])
        normalized = re.sub(r"-?0x[0-9a-f]+\(%rip\)", "@rip", normalized)
        current.append(mnemonic + " " + normalized.strip())
        if not _base_instruction(mnemonic, operands, encoding):
            unknown.append({"symbol": symbol, "function_address": function_address,
                            "address": address, "instruction": mnemonic})
        called = re.search(r"<(.*)>", operands)
        if called:
            references.append({"caller": symbol, "function_address": function_address,
                               "callee": called.group(1), "instruction": mnemonic})
    finish_function()
    if not instructions:
        raise CapabilityError("no linked executable instructions were inspected")
    after = file_identity(binary)
    if before["sha256"] != after["sha256"]:
        raise CapabilityError("linked binary changed during instruction inspection")
    return {"binary": after, "instruction_count": instructions,
            "functions": functions, "references": references, "unclassified": unknown,
            "disassembly_sha256": hashlib.sha256(disassembly["stdout"].encode()).hexdigest(),
            "command": disassembly["command"]}


# Reviewed official std/provider and smoke contexts. These are exact function
# bodies, not a user-extensible instruction whitelist. LLVM's BSF lowering is
# X86MCInstLower.cpp516-532 and X86InstrCompiler.td2333-2337. New bodies fail
# closed until their source, zero-value path and flag uses are reviewed.
_REVIEWED_REP_BSF_CONTEXTS = frozenset("""
05fbe02fbcc988f65bc9e8ba75aa18278a24196cb60413e005aed8932bd1e0df
091150d23f4e6ef0da0b2b0ca3a220c3b86cf726b00d0c9eff7e36477d2f70eb
19de8ecc8db9f56ce80bd9520ed15f6b4907f7a404f2956048246a11488ecaed
211ffdebd7d389eb51f9ea5726d3015307bd0f7a5011bb7ffb126c8223443f38
3473b0d26b95556106ca2d31b45ea0896b002a5bc3c06ef560322a98d71892d2
392dc056f3ad8301976b63bf235e9bde1634efca47447d814f2a24cb0da36ecf
426c520c5ebbd0bb4d7263ef771828a6e0865cc61a9fadf84e7c9e8fc2fe5664
690858ee0108f5be26c00a0fb644ad2620bc2cdc764459030acd49e95161fb08
697f30a1a330338460752b8df49332d2f88d86a0173d92c3b8576b62a4ffd53b
6e991b18f4875166dc7266959e0b51e4d52d71d330028d6a624930f9474a3fb7
72af714e5dfffa5bea40b56bca019bc1d541092d9d3dff203469cf98c675634f
7a66a67d7be4e2bdc238e65aff5c56b56f575e8301de9eaf27061ac7059d18aa
824e18d6900766cfbed94e3dd964db9da012eebf62b151374e578a523cf343c3
96cdddf54176ba792fbb16b3dcbcf356b4678ddf0f1dd042d6179a33487209d7
96de95f3713f8d38046e2de2ed575cabadd0789dd9935a2819112d3ad1435b94
9f6b7eecc685d27bc3801c3d1fe2dc6c97a316cc01d3451859651c7458b45e32
a0af3e4fa32889d7a4c2502fab48dad58a43aa822425b92eb5d763176d4dbac2
a4ede24a499047fc4c839417c5227ea60646f403fe196131dc685487dcd2aac7
c264983cbef33f36380bbbc76394c8e81c8e7c6aecd27eee9491103c48305af4
cbfcf029c5f10e13ad0197a0c2ce3a88ecc84920e7cf49085819f8d06e0e1cd4
cfa8baa514331c39eccdca0c0f2fd99485c3114baa00bf01436c6f321c0378e0
d583b2955be55e19e058017094d7ed16057e6bfd56315a74b52460b16d897600
f3e84c98f17e6c4f7296deeccdea56722118e2d52951ed5ad7f0804acba65dd9
ffa3eed30a6861935337c6feba4a6d5c138ea5fd986c8c00f8643b0f92cb7cb7
""".split())
_REVIEWED_XGETBV = "47f6abd5f8a5575c2173647b8ab0b70065625bfb857ce8ab2a0e812468a344d2"
_REVIEWED_XGETBV_CALLER = "be65af10a72ca0874e71b59bc82137f32a5eb3e99ad40450ba889f4444f619e0"


def _function_hash(scan, symbol, address):
    matches = [row["sha256"] for row in scan["functions"].get(symbol, [])
               if row["address"] == address]
    if len(matches) != 1:
        raise CapabilityError("ambiguous linked function identity: " + symbol)
    return matches[0]


def _validate_scoped_text(scan, proof):
    guarded = proof.get("guarded_functions", {})
    callers = proof.get("guarded_callers", {})
    contexts = proof.get("rep_bsf_contexts", [])
    if not isinstance(guarded, dict) or not isinstance(callers, dict) or not isinstance(contexts, list):
        raise CapabilityError("malformed scoped instruction evidence")
    function = "core::core_arch::x86::xsave::_xgetbv"
    caller = "std_detect::detect::cache::detect_and_initialize"
    if guarded != {function: _REVIEWED_XGETBV} or callers != {caller: _REVIEWED_XGETBV_CALLER}:
        raise CapabilityError("unsupported guarded CPU-discovery exception")
    if any(not isinstance(value, str) for value in contexts) or set(contexts) - _REVIEWED_REP_BSF_CONTEXTS:
        raise CapabilityError("unreviewed REP-BSF semantic context")
    for item in scan["unclassified"]:
        name = item["symbol"]
        digest = _function_hash(scan, name, item["function_address"])
        if item["instruction"] == "tzcnt":
            context = _digest({"symbol": name, "sha256": digest})
            if context in contexts and context in _REVIEWED_REP_BSF_CONTEXTS:
                continue
        elif item["instruction"] == "xgetbv" and name == function:
            if digest == _REVIEWED_XGETBV and len(scan["functions"].get(name, [])) == 1:
                continue
        raise CapabilityError("unproved linked baseline instruction: " + repr(item))
    if any(item["instruction"] == "xgetbv" for item in scan["unclassified"]):
        caller_rows = scan["functions"].get(caller, [])
        if len(caller_rows) != 1 or caller_rows[0]["sha256"] != _REVIEWED_XGETBV_CALLER:
            raise CapabilityError("guarded CPU discovery caller is absent or changed")
    for reference in scan["references"]:
        if function not in reference["callee"]:
            continue
        if reference["callee"] != function or reference["instruction"] not in ("call", "callq"):
            raise CapabilityError("indirect/offset CPU-discovery reference is unproved")
        if (reference["caller"] != caller or len(scan["functions"].get(caller, [])) != 1 or
                _function_hash(scan, caller, reference["function_address"]) != _REVIEWED_XGETBV_CALLER):
            raise CapabilityError("unproved CPU-discovery caller")


def _retained_evidence(entries, base):
    evidence, kinds = [], set()
    if not isinstance(entries, list):
        raise CapabilityError("Rust capability evidence must be a list")
    for item in entries:
        if not isinstance(item, dict) or item.get("kind") not in ("correctness", "isa", "provider"):
            raise CapabilityError("unsupported Rust capability evidence entry")
        if not isinstance(item.get("path"), str) or not item["path"]:
            raise CapabilityError("Rust capability evidence path is missing")
        path = Path(item["path"])
        if not path.is_absolute():
            path = base / path
        retained = file_identity(path)
        if retained["sha256"] != item.get("sha256"):
            raise CapabilityError("Rust capability evidence changed: " + str(path))
        evidence.append({"kind": item["kind"], **retained})
        kinds.add(item["kind"])
    if kinds != {"correctness", "isa", "provider"}:
        raise CapabilityError("Rust capability proof needs retained correctness, ISA and provider evidence")
    return evidence


def require_rust_capabilities(configuration, cpu, binary=None, proof=None,
                              runtime_environment=None):
    """Validate retained scoped evidence and bind it to the actual executable.

    V2 covers a fingerprinted static musl toolchain/provider and scans every
    fresh linked program, including new
    generated nonces. V2 never extends an exception to new provider code.
    It does not grant a standalone whole-library ISA certificate.
    """
    if cpu not in ("native", "base"):
        raise CapabilityError("unknown Rust CPU mode: " + str(cpu))
    environment = rust_runtime_environment(cpu) if runtime_environment is None else runtime_environment
    controls = capability_environment(environment)
    if cpu == "native":
        if controls:
            raise CapabilityError("native Rust reference must remain ordinary and unmasked")
        return {"cpu": cpu, "status": "ordinary-unmasked",
                "scope": "native compiler selection; no baseline ISA claim"}
    if binary is None or proof is None:
        raise CapabilityError("Rust base performance requires linked-program correctness, ISA and provider evidence; target-cpu alone is insufficient")
    linked = binary if isinstance(binary, dict) else rust_binary_metadata(configuration, binary)
    if (not isinstance(linked, dict) or not isinstance(linked.get("binary"), dict) or
            not isinstance(linked["binary"].get("path"), str) or
            not isinstance(linked["binary"].get("sha256"), str) or
            not isinstance(linked.get("needed"), list) or
            not isinstance(linked.get("provider_sha256"), str) or
            not isinstance(linked.get("identity_sha256"), str)):
        raise CapabilityError("linked Rust program metadata is malformed")
    base, proof_identity = Path.cwd(), None
    if isinstance(proof, (str, os.PathLike)):
        proof_path = Path(proof).resolve()
        proof_identity = file_identity(proof_path)
        base = proof_path.parent
        try:
            proof = json.loads(proof_path.read_text())
        except (OSError, ValueError) as error:
            raise CapabilityError("cannot read Rust capability proof: " + str(error)) from error
    if not isinstance(proof, dict) or proof.get("configuration_sha256") != configuration["identity_sha256"]:
        raise CapabilityError("Rust capability proof belongs to a different compiler/std/provider configuration")
    format_name = proof.get("format")
    scan = None
    if format_name != "paslang-rust-capability-proof-v2":
        raise CapabilityError("unsupported Rust capability proof format; linked-text validation is required")
    entry = proof
    if configuration["provider"] != "musl" or linked["needed"] or linked["interpreter"]:
        raise CapabilityError("shared Rust capability evidence requires the reviewed static musl provider")
    if proof.get("provider_sha256") != linked["provider_sha256"]:
        raise CapabilityError("shared Rust capability evidence belongs to another linked provider")
    scan = rust_linked_text(configuration, linked["binary"]["path"])
    if scan["binary"]["sha256"] != linked["binary"]["sha256"]:
        raise CapabilityError("linked program changed after provider inspection")
    _validate_scoped_text(scan, proof)
    scan = {key: value for key, value in scan.items() if key not in ("functions", "references")}
    if entry.get("runtime_environment") != controls:
        raise CapabilityError("Rust capability proof runtime controls do not match the measured environment")
    checks = entry.get("checks", {})
    if not isinstance(checks, dict) or any(checks.get(name) is not True for name in
                                         ("correctness", "baseline_isa", "provider_dispatch")):
        raise CapabilityError("Rust capability proof has incomplete or failing checks")
    evidence = _retained_evidence(entry.get("evidence", []), base)
    return {"cpu": cpu, "status": "retained-evidence-matches",
            "identity_sha256": linked["identity_sha256"], "proof": proof_identity,
            "evidence": evidence, "runtime_environment": controls, "linked_text": scan,
            "scope": "this linked program and runtime controls only"}


def prepare_rust_proof(configuration, binary, evidence):
    """Prepare a portable candidate; retained review checks remain false."""
    linked = binary if isinstance(binary, dict) else rust_binary_metadata(configuration, binary)
    if configuration["provider"] != "musl" or linked["needed"] or linked["interpreter"]:
        raise CapabilityError("candidate linked-text evidence requires static musl")
    scan = rust_linked_text(configuration, linked["binary"]["path"])
    if scan["binary"]["sha256"] != linked["binary"]["sha256"]:
        raise CapabilityError("linked program changed during candidate preparation")
    proof = {"format": "paslang-rust-capability-proof-v2",
             "configuration_sha256": configuration["identity_sha256"],
             "provider_sha256": linked["provider_sha256"], "runtime_environment": {},
             "checks": {"correctness": False, "baseline_isa": False, "provider_dispatch": False},
             "guarded_functions": {"core::core_arch::x86::xsave::_xgetbv": _REVIEWED_XGETBV},
             "guarded_callers": {"std_detect::detect::cache::detect_and_initialize": _REVIEWED_XGETBV_CALLER},
             "rep_bsf_contexts": sorted(_REVIEWED_REP_BSF_CONTEXTS), "evidence": evidence,
             "observed_program": {"binary_sha256": linked["binary"]["sha256"],
                                  "instruction_count": scan["instruction_count"],
                                  "disassembly_sha256": scan["disassembly_sha256"]},
             "scope": "listed static provider contents plus strict fresh linked-text checks; outputs remain driver-checked",
             "review": "Candidate only. Set a check true only after reviewing its retained correctness, ISA or provider evidence. Preparation does not certify every library routine."}
    _validate_scoped_text(scan, proof)
    _retained_evidence(evidence, Path.cwd())
    return proof


def main():
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Prepare scoped Rust baseline evidence; no benchmark or program is run.")
    parser.add_argument("--rustc", default="rustc")
    parser.add_argument("--rust-target", default="x86_64-unknown-linux-musl")
    parser.add_argument("--rust-sysroot")
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--evidence", action="append", default=[], metavar="KIND=PATH",
                        help="retained correctness/isa/provider evidence; repeat for all three kinds")
    parser.add_argument("--prepare-proof", required=True, type=Path,
                        help="candidate JSON output; review checks remain false")
    options = parser.parse_args()
    try:
        configuration = rust_configuration(options.rustc, options.rust_target, options.rust_sysroot)
        entries = []
        for specification in options.evidence:
            kind, separator, name = specification.partition("=")
            if not separator or kind not in ("correctness", "isa", "provider") or not name:
                raise CapabilityError("--evidence must be correctness=PATH, isa=PATH or provider=PATH")
            identity = file_identity(name)
            entries.append({"kind": kind, "path": identity["path"], "sha256": identity["sha256"]})
        candidate = prepare_rust_proof(configuration, options.binary, entries)
        options.prepare_proof.write_text(json.dumps(candidate, indent=2) + "\n")
    except (CapabilityError, OSError) as error:
        print("reference_caps: " + str(error), file=sys.stderr)
        return 2
    print("Candidate written to " + str(options.prepare_proof) + "; retained review checks remain false.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
