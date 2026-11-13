#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned.
# GPL version 3 or later; see COPYING. No warranty.
"""Compiler-free regressions for Rust component identities and ISA refusal."""
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


if __name__ == "__main__":
    unittest.main()
