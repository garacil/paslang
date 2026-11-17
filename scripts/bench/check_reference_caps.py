#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned.
# GPL version 3 or later; see COPYING. No warranty.
"""Compiler-free reference identities, ISA and actual FMA selection controls."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

specification = importlib.util.spec_from_file_location("reference_caps", Path(__file__).with_name("reference_caps.py"))
caps = importlib.util.module_from_spec(specification)
specification.loader.exec_module(caps)


class ReferenceCapabilities(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="paslang-reference-caps-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.binary = self.root / "program"
        self.binary.write_bytes(b"fixture program")
        self.marker = self.root / "evidence"
        self.marker.write_text("retained fixture evidence\n")
        self.configuration = {"identity_sha256": "configuration", "provider": "musl",
                              "target": "x86_64-unknown-linux-musl"}
        self.linked = {"binary": caps.file_identity(self.binary), "needed": [],
                       "interpreter": None, "provider_sha256": "provider",
                       "identity_sha256": "linked"}
        self.proof = {"format": "paslang-rust-capability-proof-v2",
                      "configuration_sha256": "configuration", "provider_sha256": "provider",
                      "runtime_environment": {}, "checks": {"correctness": True,
                          "baseline_isa": True, "provider_dispatch": True},
                      "guarded_functions": {"core::core_arch::x86::xsave::_xgetbv": caps._REVIEWED_XGETBV},
                      "guarded_callers": {"std_detect::detect::cache::detect_and_initialize": caps._REVIEWED_XGETBV_CALLER},
                      "rep_bsf_contexts": [], "evidence": [
                          {"kind": kind, "path": str(self.marker),
                           "sha256": caps.file_identity(self.marker)["sha256"]}
                          for kind in ("correctness", "isa", "provider")]}

    def capture(self, body):
        return mock.patch.object(caps, "_capture", return_value={
            "command": ["objdump", "fixture"], "status": 0,
            "stdout": body, "stderr": ""})

    def require(self, body, proof=None):
        with self.capture(body):
            return caps.require_rust_capabilities(self.configuration, "base", self.linked,
                self.proof if proof is None else proof, runtime_environment={})

    def test_baseline_text_is_bound_to_fresh_binary(self):
        result = self.require("0000 <fixture>:\n   0: 31 c0   xor %eax,%eax\n   2: c3 ret\n")
        self.assertEqual(result["status"], "retained-evidence-matches")
        self.assertEqual(result["linked_text"]["binary"]["sha256"], self.linked["binary"]["sha256"])
        self.assertEqual(result["linked_text"]["instruction_count"], 2)

    def test_preparing_a_candidate_never_certifies_it(self):
        body = "0000 <fixture>:\n 0: c3 ret\n"
        with self.capture(body):
            candidate = caps.prepare_rust_proof(self.configuration, self.linked, self.proof["evidence"])
        self.assertFalse(any(candidate["checks"].values()))
        with self.assertRaises(caps.CapabilityError):
            self.require(body, candidate)

    def test_documented_sse2_aliases_keep_legacy_encoding(self):
        self.require("0000 <fixture>:\n 0: f2 0f c2 c1 01 cmpltsd %xmm1,%xmm0\n 5: f2 0f 2a c0 cvtsi2sdl %eax,%xmm0\n 9: c3 ret\n")
        with self.assertRaises(caps.CapabilityError):
            self.require("0000 <fixture>:\n 0: c5 fb c2 c1 01 cmpltsd %xmm1,%xmm0\n")

    def test_optional_and_unsafe_semantic_forms_are_refused(self):
        cases = ["c5 f9 ef c0 vpxor %xmm0,%xmm0,%xmm0",
                 "f3 0f bc c0 tzcnt %eax,%eax", "f3 0f bd c0 lzcnt %eax,%eax",
                 "9f lahf", "9e sahf", "d5 00 01 c0 add %r16,%r16",
                 "f3 c5 f9 ef c0 repz vpxor %xmm0,%xmm0,%xmm0"]
        for instruction in cases:
            with self.subTest(instruction=instruction), self.assertRaises(caps.CapabilityError):
                self.require("0000 <unsafe_use>:\n  0: " + instruction + "\n  8: c3 ret\n")

    def test_unparsed_unknown_and_omitted_executable_bytes_are_refused(self):
        for line in ["  0: 0f ff (bad)", "  0: ff", "  0: .byte 0xff", "  ..."]:
            with self.subTest(line=line), self.assertRaises(caps.CapabilityError):
                self.require("0000 <fixture>:\n" + line + "\n 20: c3 ret\n")

    def test_duplicate_demangled_names_preserve_both_functions(self):
        with self.capture("0000 <same>:\n  0: c3 ret\n0001 <same>:\n  1: 90 nop\n  2: c3 ret\n"):
            value = caps.rust_linked_text(self.configuration, self.binary)
        self.assertEqual(len(value["functions"]["same"]), 2)
        self.assertNotEqual(value["functions"]["same"][0]["sha256"], value["functions"]["same"][1]["sha256"])

    def test_indirect_and_offset_cpu_discovery_references_are_refused(self):
        for form in ["8d 05 00 00 00 00 lea 0x0(%rip),%rax # 20 <core::core_arch::x86::xsave::_xgetbv>",
                     "e8 00 00 00 00 call 20 <core::core_arch::x86::xsave::_xgetbv+0x1>"]:
            with self.subTest(form=form), self.assertRaises(caps.CapabilityError):
                self.require("0000 <unsafe_reference>:\n  0: " + form + "\n")

    def test_arbitrary_function_or_context_exceptions_are_refused(self):
        for key, value in [("guarded_functions", {"any_function": "f" * 64}),
                           ("guarded_callers", []), ("rep_bsf_contexts", ["f" * 64])]:
            proof = copy.deepcopy(self.proof); proof[key] = value
            with self.subTest(key=key), self.assertRaises(caps.CapabilityError):
                self.require("0000 <fixture>:\n 0: c3 ret\n", proof)

    def test_proof_environment_components_and_retained_bytes_are_bound(self):
        for key, value in [("configuration_sha256", "different"),
                           ("provider_sha256", "different"),
                           ("runtime_environment", {"RUST_STD_DETECT_UNSTABLE": "avx2"}),
                           ("format", "paslang-rust-capability-proof-v1"),
                           ("evidence", None), ("evidence", [{"kind": "isa", "path": None}])]:
            proof = copy.deepcopy(self.proof); proof[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(caps.CapabilityError):
                self.require("0000 <fixture>:\n 0: c3 ret\n", proof)
        self.marker.write_text("changed evidence\n")
        with self.assertRaises(caps.CapabilityError):
            self.require("0000 <fixture>:\n 0: c3 ret\n")

    def test_malformed_program_and_elf_metadata_are_refused(self):
        with self.assertRaises(caps.CapabilityError):
            caps.require_rust_capabilities(self.configuration, "base", {}, self.proof,
                                           runtime_environment={})
        with mock.patch.object(caps, "_capture", return_value={"stdout": ""}):
            with self.assertRaises(caps.CapabilityError):
                caps.rust_binary_metadata(self.configuration, self.binary)

    def test_changed_binary_is_refused_after_provider_observation(self):
        self.binary.write_bytes(b"changed program")
        with self.assertRaises(caps.CapabilityError):
            self.require("0000 <fixture>:\n 0: c3 ret\n")

    def test_missing_proof_and_missing_file_fail_as_capability_errors(self):
        with self.assertRaises(caps.CapabilityError):
            caps.require_rust_capabilities(self.configuration, "base", self.linked, None,
                                           runtime_environment={})
        with self.assertRaises(caps.CapabilityError):
            caps.require_rust_capabilities(self.configuration, "base", self.linked,
                                           self.root / "absent.json", runtime_environment={})

    def test_native_is_unmasked_and_base_never_gets_an_implicit_certificate(self):
        inherited = {"GLIBC_TUNABLES": "glibc.cpu.hwcaps=-AVX2",
                     "RUST_STD_DETECT_UNSTABLE": "avx2", "LD_PRELOAD": "example.so"}
        env = caps.rust_runtime_environment("native", inherited)
        self.assertEqual(caps.capability_environment(env), {})
        with self.assertRaises(caps.CapabilityError):
            caps.require_rust_capabilities(self.configuration, "native", runtime_environment=inherited)
        self.assertFalse(caps._base_mnemonic("tzcnt"))
        self.assertFalse(caps._base_mnemonic("lahf"))
        self.assertFalse(caps._base_mnemonic("sahf"))

    def test_library_fingerprint_uses_contents_and_metadata_is_reviewed(self):
        root = self.root / "sysroot"
        library = root / "lib/rustlib/x86_64-unknown-linux-gnu/lib"
        library.mkdir(parents=True)
        marker = library / "libstd.rlib"; marker.write_bytes(b"first")
        compiler = self.root / "rustc"; compiler.write_bytes(b"compiler fixture"); compiler.chmod(0o700)
        metadata = "release: " + caps.REVIEWED_RELEASE + "\ncommit-hash: " + caps.REVIEWED_COMMIT + "\nhost: x86_64-unknown-linux-gnu\n"
        with mock.patch.object(caps, "_capture", return_value={"stdout": metadata}):
            first = caps.rust_configuration(compiler, sysroot=root)
            marker.write_bytes(b"second")
            second = caps.rust_configuration(compiler, sysroot=root)
        self.assertNotEqual(first["identity_sha256"], second["identity_sha256"])
        self.assertFalse(second["base_capability"]["certified"])
        with mock.patch.object(caps, "_capture", return_value={"stdout": "release: unknown\n"}):
            with self.assertRaises(caps.CapabilityError):
                caps.rust_configuration(compiler, sysroot=root)



class FmaReferenceSelection(unittest.TestCase):
    # These are compiler-free wrong-selection/dataflow controls. Actual ELF,
    # provider and workload checks are retained separately by the driver.
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="paslang-fma-reference-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.binary = self.root / "b44fixture"
        self.inspector = self.root / "objdump"
        self.inspector.write_bytes(b"fixture inspector")
        self.nonce = 0

    def metadata(self, reference, text):
        self.nonce += 1
        self.binary.write_bytes(b"fixture binary " + str(self.nonce).encode())
        with mock.patch.object(caps.shutil, "which", return_value=str(self.inspector)), \
                mock.patch.object(caps, "_capture", return_value={
                    "command": [str(self.inspector), "-d", "fixture"], "status": 0,
                    "stdout": text, "stderr": ""}):
            return caps.fma_binary_metadata(reference, self.binary, self.root / "evidence")

    def require(self, reference, cpu, text, has_fma, provider="musl", certified=True):
        metadata = self.metadata(reference, text)
        evidence = {"status": "retained-evidence-matches" if certified else "ordinary-unmasked",
                    "linked_text": {"binary": metadata["binary"]}}
        return caps.require_fma_path(reference, cpu, metadata, effective_has_fma=has_fma,
                                     capability_evidence=evidence, provider=provider)

    GO = """0000 <main.main>:
  0: 0f b6 15 00 00 00 00 movzbl 0x0(%rip),%edx # 100 <runtime.x86HasFMA>
  7: 85 d2 test %edx,%edx
  9: 74 07 je 12 <main.main+0x12>
  b: c4 e2 c9 b9 d1 vfmadd231sd %xmm1,%xmm6,%xmm2
 10: eb 05 jmp 17 <main.main+0x17>
 12: e8 09 00 00 00 call 20 <math.FMA>
 17: c3 ret
0020 <math.FMA>:
 20: f2 0f 59 c1 mulsd %xmm1,%xmm0
 24: c3 ret
"""
    RUST_SOFT = """0000 <b44fma::main>:
 0: 4c 8d 25 19 00 00 00 lea 0x19(%rip),%r12 # 20 <fma>
 7: 41 ff d4 call *%r12
 a: c3 ret
0020 <fma>:
 20: f2 0f 59 c1 mulsd %xmm1,%xmm0
 24: c3 ret
"""
    RUST_HARD = """0000 <b44fma::main>:
 0: c4 e2 d9 a9 ea vfmadd213sd %xmm2,%xmm4,%xmm5
 5: c3 ret
"""

    def test_go_effective_state_selects_the_actual_branch(self):
        self.assertEqual(self.require("go", "base", self.GO, False)["selected"], "pure-go-fma")
        self.assertEqual(self.require("go", "native", self.GO, True)["selected"], "hardware-fma")
        self.assertEqual(self.require("go", "native", self.GO, False)["selected"], "pure-go-fma")

    def test_wrong_feature_and_inverted_go_branch_are_rejected(self):
        for text in (self.GO.replace("runtime.x86HasFMA", "runtime.otherFeature"),
                     self.GO.replace("74 07 je", "75 07 jne")):
            with self.subTest(text=text), self.assertRaises(caps.CapabilityError):
                self.require("go", "base", text, False)

    def test_unproved_optional_go_provider_is_rejected(self):
        outside = "0030 <other>:\n 30: c4 e2 d9 a9 ea vfmadd213sd %xmm2,%xmm4,%xmm5\n 35: c3 ret\n"
        with self.assertRaises(caps.CapabilityError):
            self.require("go", "base", self.GO + outside, False)
        with self.assertRaises(caps.CapabilityError):
            self.require("go", "base", self.GO, True)

    def test_native_software_on_fma_host_cannot_manufacture_a_win(self):
        with self.assertRaises(caps.CapabilityError):
            self.require("rust", "native", self.RUST_SOFT, True)
        self.assertEqual(self.require("rust", "native", self.RUST_HARD, True)["selected"], "hardware-fma")
        self.assertEqual(self.require("rust", "native", self.RUST_SOFT, False)["selected"], "static-software-fma")

    def test_rust_base_needs_actual_static_provider_isa_evidence(self):
        self.assertEqual(self.require("rust", "base", self.RUST_SOFT, False)["selected"], "static-software-fma")
        for options in ({"provider": "gnu"}, {"certified": False}):
            with self.subTest(options=options), self.assertRaises(caps.CapabilityError):
                self.require("rust", "base", self.RUST_SOFT, False, **options)

    def test_unused_or_unreached_provider_pointer_is_not_evidence(self):
        for text in (self.RUST_SOFT.replace("# 20 <fma>", "# 20 <other>"),
                     self.RUST_SOFT.replace("call *%r12", "call *%r13"),
                     self.RUST_SOFT.replace(" 0: 4c", " 0: eb 07 jmp 9 <b44fma::main+0x9>\n 2: 4c").replace(" 7: 41", " 9: 41")):
            with self.subTest(text=text), self.assertRaises(caps.CapabilityError):
                self.require("rust", "base", text, False)

    def test_all_pointer_register_alias_writes_invalidate_the_call(self):
        for reg, opcode in (("%r12", "4d 31 e4"), ("%r12d", "45 31 e4"),
                            ("%r12w", "66 45 31 e4"), ("%r12b", "45 30 e4")):
            changed = self.RUST_SOFT.replace(" 7: 41 ff d4 call *%r12\n a: c3 ret",
                " 7: " + opcode + " xor " + reg + "," + reg + "\n b: 41 ff d4 call *%r12\n e: c3 ret")
            with self.subTest(reg=reg), self.assertRaises(caps.CapabilityError):
                self.require("rust", "base", changed, False)
        for reg, accumulator, opcode in (("%rbx", "%rax", "48 93"), ("%ebx", "%eax", "93"),
                                         ("%bx", "%ax", "66 93"), ("%bl", "%al", "86 d8"),
                                         ("%bh", "%ah", "86 fc")):
            changed = self.RUST_SOFT.replace("%r12", "%rbx").replace(" 7: 41 ff d4 call *%rbx\n a: c3 ret",
                " 7: " + opcode + " xchg " + reg + "," + accumulator + "\n a: ff d3 call *%rbx\n c: c3 ret")
            with self.subTest(reg=reg), self.assertRaises(caps.CapabilityError):
                self.require("rust", "base", changed, False)

    def test_cmpxchg_is_a_possible_pointer_write_not_a_comparison(self):
        changed = self.RUST_SOFT.replace("%r12", "%rbx").replace(
            " 7: 41 ff d4 call *%rbx\n a: c3 ret",
            " 7: 48 0f b1 cb cmpxchg %rcx,%rbx\n b: ff d3 call *%rbx\n d: c3 ret")
        with self.assertRaises(caps.CapabilityError):
            self.require("rust", "base", changed, False)

    def test_epilogue_restore_after_the_last_call_is_legal(self):
        text = self.RUST_SOFT.replace(" a: c3 ret", " a: 41 5c pop %r12\n c: c3 ret")
        self.require("rust", "base", text, False)

    def test_dead_native_hardware_does_not_prove_selection(self):
        dead = self.RUST_HARD.replace(" 0: c4", " 0: eb 06 jmp 8 <b44fma::main+0x8>\n 2: c4").replace(" 5: c3 ret", " 8: c3 ret")
        with self.assertRaises(caps.CapabilityError):
            self.require("rust", "native", dead, True)

    def test_paslang_linked_gate_rejects_historical_base_dispatch(self):
        current = "0000 <pas_main>:\n 0: e8 0b 00 00 00 call 10 <p_f.0_6_horner>\n 5: c3 ret\n0010 <p_f.0_6_horner>:\n 10: c3 ret\n"
        self.require("paslang", "base", current, False)
        native = current.replace(" 10: c3 ret", " 10: c4 e2 d9 a9 ea vfmadd213sd %xmm2,%xmm4,%xmm5\n 15: c3 ret")
        self.require("paslang", "native", native, True)
        old = current + "0020 <p_f.6_pasnum6_pasfma>:\n 20: c4 e2 d9 a9 ea vfmadd213sd %xmm2,%xmm4,%xmm5\n 25: c3 ret\n"
        with self.assertRaises(caps.CapabilityError):
            self.require("paslang", "base", old, False)
        with self.assertRaises(caps.CapabilityError):
            self.require("paslang", "native", current, True)

    def test_only_unreached_lone_zero_text_data_is_accepted(self):
        text = self.RUST_HARD + "0020 <cpu_name_data>:\n 20: 00 .byte 0\n"
        self.require("rust", "native", text, True)
        with self.assertRaises(caps.CapabilityError):
            self.require("rust", "native", text.replace(" 5: c3 ret", " 5: 00 .byte 0"), True)
        with self.assertRaises(caps.CapabilityError):
            self.require("rust", "native", text.replace("20: 00 .byte 0", "20: c4 .byte 0xc4"), True)

    def test_changed_binary_dump_and_duplicate_roots_fail_closed(self):
        metadata = self.metadata("rust", self.RUST_HARD)
        self.binary.write_bytes(b"changed")
        with self.assertRaises(caps.CapabilityError):
            caps.require_fma_path("rust", "native", metadata, effective_has_fma=True)
        with self.assertRaises(caps.CapabilityError):
            self.metadata("rust", self.RUST_HARD + self.RUST_HARD)
        for text in ("0000 <b44fma::main>:\n ...\n", "0000 <b44fma::main>:\n 0: ff .byte 0xff\n"):
            with self.subTest(text=text), self.assertRaises(caps.CapabilityError):
                self.metadata("rust", text)


if __name__ == "__main__":
    unittest.main()
