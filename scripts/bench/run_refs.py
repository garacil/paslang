#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Selected benchmark pairs against Go and Rust, shared by run.py/rounds.py.

Example: run.py --pairs b1loop,b6smap --reference go,rust
    --cpu native,base --go-native-level v3 -n 40 --json build/bench/selected-refs.json
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import signal
import statistics
import subprocess
import sys
import time

import run as bench
from reference_policy import (go_level, go_build_environment, go_runtime_environment,
                              go_policy_description, validate_go_version,
                              prepare_go_capabilities, validate_go_capabilities,
                              go_binary_metadata, require_go_artifact_capabilities)


# The eleven std-only twins cover every current section of these programs.
# Unsupported pairs and sections still fail explicitly.
RUST_SECTIONS = {
    "b1loop": (None,), "b2str": (None,), "b5map": (None,),
    "b6smap": (None,), "b7narrow": (None,), "b8ptr": (None,),
    "b10rot": (None,), "b14sort": ("ints", "strings", "reals"),
    "b24math": ("sin", "exp", "ln", "sqrt", "pow", "atan", "tan", "sinh", "tanh", "asinh", "log1p"),
    "b26slice": ("ints", "strings"), "b31map": ("iter", "delete", "update", "sums", "bits"),
}


def csv(value):
    return list(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))


def json_values(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: json_values(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_values(item) for item in value]
    return value


def selected_units(selectors, references):
    all_units = bench.units()
    if selectors is None:
        # Go retains every current pair; Rust's default covers all audited
        # twins. An explicitly requested unsupported Rust pair is an error.
        selectors = list(RUST_SECTIONS) if "rust" in references else list(bench.PAIRS)
    known = set(bench.PAIRS) | {bench.unit_name(*unit) for unit in all_units}
    unknown = set(selectors) - known
    if unknown:
        raise ValueError("unknown pairs: " + ", ".join(sorted(unknown)))
    units = [unit for unit in all_units if unit[0] in selectors or bench.unit_name(*unit) in selectors]
    if not units:
        raise ValueError("--pairs must select at least one pair or section")
    if "rust" in references:
        missing = [bench.unit_name(*unit) for unit in units
                   if unit[1] not in RUST_SECTIONS.get(unit[0], ())]
        if missing:
            raise ValueError("requested Rust sections have no audited twin yet: " + ", ".join(missing))
    return units


def capture(arguments, *, env=None, cwd=None):
    command = [str(a) for a in arguments]
    child = subprocess.Popen(command, env=env, cwd=cwd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
    try:
        try:
            stdout, stderr = child.communicate(timeout=120)
            status = child.returncode
        except subprocess.TimeoutExpired:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = child.communicate()
            status = 'timeout'
    finally:
        if child.returncode is None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
        if child.stdout:
            child.stdout.close()
        if child.stderr:
            child.stderr.close()
    return {"command": command, "status": status,
            "stdout": stdout.decode('utf-8', 'surrogateescape'),
            "stderr": stderr.decode('utf-8', 'surrogateescape')}


def metadata(arguments, **kwargs):
    result = capture(arguments, **kwargs)
    if (result["status"] or not (result["stdout"] or result["stderr"]) or
            (Path(arguments[0]).name == "go" and result["stderr"])):
        raise RuntimeError("reference metadata command failed: " + " ".join(map(str, arguments)))
    return result



def paslang_inputs(arguments, executable, env=None, cwd=None):
    """Exact external unit inputs from the compiler's retained link line.

    cmd/paslangc adds -Fu, PASLANG_LIB, compiler-relative installed units,
    build[/a64], cwd and the source directory in that order. FindPi reads
    the first matching interface; UnitObj may select its newer CPU object.
    The program's generated object and linker script are outputs, not inputs.
    """
    root = Path(bench.ROOT if cwd is None else cwd).resolve()
    source = Path(arguments[-1])
    if not source.is_absolute():
        source = root / source
    environment = os.environ if env is None else env
    arm = any(arguments[index:index + 2] == ["-target", "arm64"]
              for index in range(len(arguments) - 1))
    directories = [arguments[index + 1] for index, argument in enumerate(arguments[:-1])
                   if argument == "-Fu"]
    if environment.get("PASLANG_LIB"):
        directories.append(environment["PASLANG_LIB"])
    compiler = Path(arguments[0])
    if not compiler.is_absolute():
        compiler = root / compiler
    installed = compiler.resolve().parent.parent / "lib/paslang"
    directories.append(installed / "aarch64" if arm else installed)
    if arm:
        directories.append(root / "build/a64")
    directories.extend((root / "build", root, source.parent))
    paths = [(Path(path) if Path(path).is_absolute() else root / path).resolve()
             for path in directories]
    executable = Path(executable)
    if not executable.is_absolute():
        executable = root / executable
    link = executable.with_suffix(".link")
    lines = link.read_text().splitlines()
    if len(lines) < 6 or lines[0] != "-o" or lines[2:4] != ["--gc-sections", "-T"]:
        raise RuntimeError("malformed Paslang link-input record: " + str(link))
    def identity(path):
        content = path.read_bytes()
        return {"path": str(path), "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
    units = []
    cpu = arguments[arguments.index("-cpu") + 1] if "-cpu" in arguments else "native"
    for entry in lines[6:]:
        obj = (Path(entry) if Path(entry).is_absolute() else root / entry).resolve()
        name = obj.stem.lower()
        interface = next((directory / (name + ".pi") for directory in paths
                          if (directory / (name + ".pi")).is_file()), None)
        if interface is None:
            raise RuntimeError("stale executable: Paslang unit interface is absent: " + name)
        base = interface.with_suffix(".o")
        variant = interface.parent / ("v8.2+crypto" if arm else "v3") / (name + ".o")
        if obj not in (base.resolve(), variant.resolve()):
            raise RuntimeError("stale executable: Paslang unit resolution changed: " + name)
        selection = None
        if cpu != "base":
            # Availability and relative age affect UnitObj selection. Keep
            # their decision stable without fingerprinting unrelated outputs
            # or absolute mtimes that change when identical units rebuild.
            selection = {"variant": str(variant), "available": variant.is_file(),
                         "not_older_than_base": (variant.is_file() and base.is_file() and
                                                 variant.stat().st_mtime_ns >= base.stat().st_mtime_ns)}
        units.append({"name": name, "interface": identity(interface),
                      "object": identity(obj), "cpu_object_selection": selection})
    return {"search_paths": list(map(str, paths)), "units": units}


def build(arguments, executable, record, *, env=None, reuse=False):
    arguments = [str(argument) for argument in arguments]
    source = Path(arguments[-1])
    tool_version = record[{"rustc": "rustc", "go": "go_version", "paslangc": "paslangc"}
                          [Path(arguments[0]).name]]
    identity = {"command": arguments, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "compiler_version": tool_version["stdout"] + tool_version["stderr"],
                "compiler_sha256": hashlib.sha256(Path(arguments[0]).read_bytes()).hexdigest(),
                "native_host": record['native_host'] if any('native' in a for a in arguments[1:-1]) else None,
                "rust_configuration": record.get("rust_configuration") if Path(arguments[0]).name == "rustc" else None,
                "go_capability_identity": record["go_capabilities"]["identity_sha256"]
                    if Path(arguments[0]).name == "go" else None,
                "environment": {key: env[key] for key in
                    ("GODEBUG", "GOAMD64", "GOARCH", "GOOS", "GOFLAGS", "GOTOOLCHAIN", "GOEXPERIMENT", "GOENV",
                     "GLIBC_TUNABLES", "LD_HWCAP_MASK", "RUST_STD_DETECT_UNSTABLE")
                    if env and key in env}}
    manifest = executable.with_name(executable.name + ".build.json")
    if reuse:
        if not executable.is_file() or not manifest.is_file():
            raise RuntimeError("not built with matching recorded flags: " + str(executable))
        previous = json.loads(manifest.read_text())
        if not isinstance(previous, dict) or not isinstance(previous.get("identity"), dict):
            raise RuntimeError("malformed build manifest: " + str(manifest))
        if Path(arguments[0]).name == "paslangc":
            identity["paslang_inputs"] = paslang_inputs(arguments, executable, env)
        if (previous.get("identity") != identity or
                previous.get("executable_sha256") != hashlib.sha256(executable.read_bytes()).hexdigest()):
            raise RuntimeError("stale executable/source/tool/flags: " + str(executable))
        record["build_observations"].append({"reused": True, **previous})
        return
    started = time.perf_counter()
    result = capture(arguments, env=env, cwd=bench.ROOT)
    result["wall_s"] = time.perf_counter() - started
    result["environment"] = {key: env[key] for key in
        ("GODEBUG", "GOAMD64", "GOARCH", "GOOS", "GOFLAGS", "GOCACHE", "GOTOOLCHAIN", "GOEXPERIMENT", "GOENV",
         "GLIBC_TUNABLES", "LD_HWCAP_MASK", "RUST_STD_DETECT_UNSTABLE")
        if env and key in env}
    record["build_observations"].append(result)
    if result["status"] or (Path(arguments[0]).name == "go" and result["stderr"]):
        raise RuntimeError("build failed or emitted unexpected Go stderr: " + " ".join(map(str, arguments)) + "\n" + result["stderr"])
    result["executable_bytes"] = executable.stat().st_size
    # Keep static-link messages too: differing linkage is part of the record.
    result["linkage"] = capture(["ldd", executable]) if shutil.which("ldd") else None
    if Path(arguments[0]).name == "paslangc":
        identity["paslang_inputs"] = paslang_inputs(arguments, executable, env)
    result["identity"] = identity
    result["executable_sha256"] = hashlib.sha256(executable.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(result, indent=1) + "\n")


# Export only known runtime controls. GO* includes unrelated settings such as
# GOPROXY, whose URL may carry credentials and must never enter this report.
RUNTIME_ENV_KEYS = (
    "GODEBUG", "GOGC", "GOMEMLIMIT", "GOMAXPROCS", "GOAMD64",
    "GLIBC_TUNABLES",
    "RUST_STD_DETECT_UNSTABLE", "MALLOC_CHECK_", "MALLOC_TOP_PAD_", "MALLOC_PERTURB_",
    "MALLOC_MMAP_THRESHOLD_", "MALLOC_TRIM_THRESHOLD_", "MALLOC_MMAP_MAX_",
    "MALLOC_ARENA_MAX", "MALLOC_ARENA_TEST",
    "PASLANG_CPU", "PASLANG_GC", "PASLANG_GCSTRESS", "PASLANG_GCPOISON",
    "PASLANG_GCVERIFY", "PASLANG_GCWORKERS", "PASLANG_ASYNCPREEMPTOFF",
)


def exported_runtime_environment(env):
    return {key: env[key] for key in RUNTIME_ENV_KEYS if key in env}


def native_host_identity():
    fields = {'vendor_id', 'cpu family', 'model', 'model name', 'stepping', 'microcode',
              'flags', 'Features', 'CPU implementer', 'CPU architecture', 'CPU variant',
              'CPU part', 'CPU revision'}
    values = set()
    for line in Path('/proc/cpuinfo').read_text().splitlines():
        if ':' in line:
            name, value = (part.strip() for part in line.split(':', 1))
            if name in fields:
                values.add((name, value))
    if not values:
        raise RuntimeError('native reuse requires readable CPU identification/features')
    return {'architecture': platform.machine(), 'cpu_fields': [list(item) for item in sorted(values)]}


def reference_environment(reference, cpu, native_level=None, capabilities=None):
    if reference == "go":
        return go_runtime_environment(cpu, native_level, capabilities=capabilities)
    from reference_caps import rust_runtime_environment
    return rust_runtime_environment(cpu)


def main(argv=None, *, rounds_only=False):
    argv = list(sys.argv[1:] if argv is None else argv)
    destination = None
    for index, argument in enumerate(argv):
        if argument == '--json' and index + 1 < len(argv):
            destination = argv[index + 1]
        elif argument.startswith('--json='):
            destination = argument.split('=', 1)[1]
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            # Includes type/choice/unknown-option failures during parse_args.
            if destination and not destination.startswith('--'):
                path = Path(destination)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"format": "paslang-bench-refs-v1", "ok": False,
                    "error": message, "pairs": [], "completed_comparisons": 0}, indent=1) + "\n")
            super().error(message)
    parser = Parser(description=__doc__)
    parser.add_argument("--pairs", help="comma-separated programs/sections; default all Go pairs or audited Rust twins")
    parser.add_argument("--reference", default="go", help="go, rust or go,rust")
    parser.add_argument("--cpu", default="native,base")
    parser.add_argument("--rust-target", help="explicit Rust target triple; defaults to compiler host")
    parser.add_argument("--rust-sysroot", help="matching Rust standard-library sysroot")
    parser.add_argument("--rust-provider", choices=("gnu", "musl"), help="identify the Rust target C provider")
    parser.add_argument("--rust-capability-proof", help="retained artifact-bound baseline ISA evidence JSON")
    parser.add_argument("--go-native-level", choices=("v1", "v2", "v3", "v4"),
                        help="highest supported Go ISA level after host/OS capability review; required for native Go")
    parser.add_argument("-n", type=int, default=40 if rounds_only else 3)
    parser.add_argument("--memory-runs", type=int, default=bench.MEM_RUNS)
    parser.add_argument("--json")
    parser.add_argument("--no-build", action="store_true", default=rounds_only,
                        help="reuse binaries only when source, tool version, flags and executable hash match")
    parser.add_argument("--timeout", type=float, default=bench.TIMEOUT)
    options = parser.parse_args(argv)
    report_file = Path(options.json) if options.json else None
    if report_file:
        report_file.parent.mkdir(parents=True, exist_ok=True)
    def reject(message):
        parser.error(message)
    references, cpus = csv(options.reference), csv(options.cpu)
    if not references or set(references) - {"go", "rust"}:
        reject("--reference accepts go and rust only")
    if not cpus or set(cpus) - {"native", "base"}:
        reject("--cpu accepts native and base only")
    if options.n < 1 or options.memory_runs < 1:
        reject("round counts must be positive")
    if not math.isfinite(options.timeout) or options.timeout <= 0:
        reject("timeout must be finite and positive")
    bench.TIMEOUT = options.timeout
    if platform.machine().lower() not in ("x86_64", "amd64"):
        reject("measurement runs on amd64 only; arm64 uses the separate correctness driver")
    if "go" in references and "native" in cpus and options.go_native_level is None:
        reject("native Go requires --go-native-level after reviewing the highest supported host/OS ISA level")
    try:
        units = selected_units(csv(options.pairs) if options.pairs is not None else None, references)
    except ValueError as error:
        reject(str(error))
    tools = {}
    for name in ["paslangc", *["rustc" if ref == "rust" else "go" for ref in references]]:
        tools[name] = shutil.which(name)
        if tools[name] is None:
            reject("explicitly requested reference/tool is unavailable on PATH: " + name)
    for name, section in units:
        if not 0 < bench.BUDGET[bench.unit_name(name, section)] < 1 or not 0 < bench.MEM_BUDGET < 1:
            reject("comparison budgets must remain strictly below 1")
    if "rust" not in references and any((options.rust_target, options.rust_sysroot,
                                         options.rust_provider, options.rust_capability_proof)):
        reject("Rust configuration options require --reference rust or go,rust")
    out = Path(bench.OUT)
    out.mkdir(parents=True, exist_ok=True)
    record = {"format": "paslang-bench-refs-v1",
              "method": "per-reference full-process series; alternating time and memory order within each series; complete stdout every round",
              "machine": bench.machine(), "references": references, "cpus": cpus,
              "native_host": native_host_identity() if 'native' in cpus else None,
              "requested_rounds": options.n, "memory_runs": options.memory_runs, "timeout_s": options.timeout,
              "go_levels": {cpu: go_level(cpu, options.go_native_level) for cpu in cpus} if "go" in references else {},
              "capability_review": "explicit Go ISA policy and Rust per-binary capability gate",
              "go_policy": go_policy_description() if "go" in references else None,
              "source_sha256": {}, "build_observations": [], "pairs": [],
              "coverage": {"requested_sections": len(units), "go_programs": len(bench.PAIRS),
                           "audited_rust_programs": len(RUST_SECTIONS),
                           "audited_rust_sections": sum(map(len, RUST_SECTIONS.values()))},
              "contracts": [
                  "Equal stdout is workload agreement, not proof of equal memory-safety or HashDoS guarantees.",
                  "Rust uses std/default HashMap hashing and normal drops; Go/paslang use their own maps and GC.",
                  "Full-process time includes setup, allocation, GC and teardown; Rust destruction work is retained.",
                  "b6smap borrows stable prebuilt key strings; there is no per-insert String clone.",
                  "Build observations are not an alternating compiler-build benchmark or a cold-cache claim.",
                  "Rust target-cpu affects this crate; the installed standard library remains precompiled.",
                  "Rust base timings require retained binary-bound capability evidence for prebuilt std/provider paths.",
                  "Go base is built separately at v1; native uses an explicitly selected reviewed level, not the base binary."]}
    expected_by_unit, built, failed = {}, set(), False
    try:
        record["paslangc"] = metadata([tools["paslangc"], "-v"])
        if "rust" in references:
            record["rustc"] = metadata([tools["rustc"], "-Vv"])
            from reference_caps import (rust_configuration, rust_build_args, rust_binary_metadata,
                                        require_rust_capabilities)
            record["rust_configuration"] = rust_configuration(
                tools["rustc"], target=options.rust_target, sysroot=options.rust_sysroot,
                provider=options.rust_provider)
            record["rust_capability_proof"] = (json.loads(Path(options.rust_capability_proof).read_text())
                                                if options.rust_capability_proof else None)
            record["rust_capability_proof_path"] = (str(Path(options.rust_capability_proof).resolve())
                                                    if options.rust_capability_proof else None)
        if "go" in references:
            record["go_version"] = metadata([tools["go"], "version"],
                env=go_build_environment(out, "base", options.go_native_level))
            validate_go_version(record["go_version"]["stdout"])
            record["go_capabilities"] = prepare_go_capabilities(tools["go"], out / "go-capabilities")
            validate_go_capabilities(record["go_capabilities"], tools["go"])
            record["go_environment"] = {
                cpu: metadata([tools["go"], "env", "-json", "GOAMD64", "GOARCH", "GOOS", "GOEXPERIMENT", "GOENV", "CGO_ENABLED"],
                              env=go_build_environment(out, cpu, options.go_native_level))
                for cpu in cpus}
        record["libc"] = metadata(["ldd", "--version"]) if shutil.which("ldd") else None
        if any(name in ("b34json", "b37json") for name, _ in units):
            bench.prepare()
        for cpu in cpus:
            for name, section in units:
                pl = out / (name + ".refs." + cpu + ".paslang")
                key = ("paslang", name, cpu)
                if key not in built:
                    source = Path(bench.HERE) / (name + ".paslang")
                    record["source_sha256"][str(source)] = hashlib.sha256(source.read_bytes()).hexdigest()
                    build([tools["paslangc"], "-cpu", cpu, "-o", pl, source], pl, record, reuse=options.no_build)
                    built.add(key)
                for reference in references:
                    ref_cpu = (cpu + "." + go_level(cpu, options.go_native_level) if reference == "go"
                               else cpu + "." + record["rust_configuration"]["target"])
                    ref = out / (name + ".refs." + ref_cpu + "." + reference)
                    key = (reference, name, ref_cpu)
                    if key not in built:
                        source = Path(bench.HERE) / ((name + ".go") if reference == "go" else ("rust/" + name + ".rs"))
                        record["source_sha256"][str(source)] = hashlib.sha256(source.read_bytes()).hexdigest()
                        if reference == "go":
                            env = go_build_environment(out, cpu, options.go_native_level)
                            build([tools["go"], "build", "-o", ref, source], ref, record, env=env, reuse=options.no_build)
                        else:
                            flags = rust_build_args(record["rust_configuration"], cpu)
                            env = reference_environment(reference, cpu)
                            build([tools["rustc"], "--edition=2024", *flags, "-o", ref, source], ref, record,
                                  env=env, reuse=options.no_build)
                            record.setdefault("rust_cfg", {})[cpu] = metadata([tools["rustc"], "--print", "cfg", *flags], env=env)
                        built.add(key)
                    args = () if section is None else (section,)
                    capability = record.get("go_capabilities") if reference == "go" else None
                    env = reference_environment(reference, cpu, options.go_native_level, capability)
                    if reference == "rust":
                        artifacts = record.setdefault("rust_artifacts", {})
                        artifact_key = str(ref)
                        if artifact_key not in artifacts:
                            artifacts[artifact_key] = rust_binary_metadata(record["rust_configuration"], ref)
                    else:
                        artifacts = record.setdefault("go_artifacts", {})
                        artifact_key = str(ref)
                        if artifact_key not in artifacts:
                            artifacts[artifact_key] = go_binary_metadata(ref)
                    budget = bench.BUDGET[bench.unit_name(name, section)]
                    rounds = []
                    row = {"pair": bench.unit_name(name, section), "cpu": cpu, "reference": reference,
                           "reference_target": record["rust_configuration"]["target"] if reference == "rust" else "amd64",
                           "capability_evidence": capability,
                           "time_budget": budget, "memory_budget": bench.MEM_BUDGET,
                           "ratio_time": None, "ratio_memory": None, "same_output": False, "ok": False, "completed": False,
                           "q1": None, "q3": None, "requires_q3_below_one": rounds_only,
                           "reference_s": None, "paslang_s": None,
                           "requested_rounds": options.n, "completed_rounds": 0,
                           "rounds": rounds, "reference_memory": [], "paslang_memory": [],
                           "runtime_environment": exported_runtime_environment(env),
                           "paslang_runtime_environment": exported_runtime_environment(os.environ)}
                    # Publish before timing or memory can be interrupted.
                    record["pairs"].append(row)
                    if reference == "rust":
                        row["capability_evidence"] = require_rust_capabilities(
                            record["rust_configuration"], cpu, artifacts[artifact_key],
                            proof=options.rust_capability_proof, runtime_environment=env)
                    else:
                        row["artifact_metadata"] = artifacts[artifact_key]
                        try:
                            row["artifact_capability_evidence"] = require_go_artifact_capabilities(cpu, artifacts[artifact_key])
                        except ValueError as error:
                            row["capability_refusal"] = str(error)
                            raise
                    try:
                        (rw, rs, ro), (pw, ps, po), ratio = bench.alternate(
                            str(ref), str(pl), options.n, env, None, args, rows=rounds)
                    finally:
                        row['completed_rounds'] = sum(part.get('completed', False) for part in rounds)
                    same = (row['completed_rounds'] == options.n and not any(part["errors"] for part in rounds)
                            and rs == 0 and ps == 0)
                    identity = (cpu, name, section)
                    if identity in expected_by_unit and expected_by_unit[identity] != po:
                        same = False
                    expected_by_unit.setdefault(identity, po)
                    ratios = bench.LAST_RATIOS[(str(ref), str(pl), args)]
                    quartiles = statistics.quantiles(ratios, n=4) if len(ratios) > 1 else [ratios[0]] * 3
                    row.update(ratio_time=ratio, same_output=same, q1=quartiles[0], q3=quartiles[2],
                               reference_s=rw, paslang_s=pw)
                    rm = pm = None
                    reference_memory, paslang_memory = row['reference_memory'], row['paslang_memory']
                    if same:
                        rm, pm, reference_memory, paslang_memory = bench.memory_pair(
                            str(ref), str(pl), options.memory_runs, env, None, args, ro, po,
                            rows_a=reference_memory, rows_b=paslang_memory)
                        same = all(row["ok"] for row in reference_memory + paslang_memory)
                    memory_ratio = pm / rm if pm is not None and rm else None
                    good = (same and ratio <= budget and (not rounds_only or quartiles[2] < 1)
                            and memory_ratio is not None and memory_ratio <= bench.MEM_BUDGET)
                    failed = failed or not good
                    row.update(ratio_memory=memory_ratio, same_output=same, ok=good, completed=True)
                    print(f"{row['pair']:20s} {cpu:6s} {reference:4s} ratio {ratio:.3f}/{budget:.2f} "
                          f"memory {memory_ratio!s}/{bench.MEM_BUDGET:.2f} stdout {same} {'PASS' if good else 'FAIL'}", flush=True)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        record["error"] = str(error)
        failed = True
    except BaseException as error:
        record["error"] = type(error).__name__ + ": " + str(error)
        failed = True
        raise
    finally:
        record["requested_comparisons"] = len(units) * len(cpus) * len(references)
        record["attempted_comparisons"] = len(record["pairs"])
        record["completed_comparisons"] = sum(row['completed'] for row in record['pairs'])
        record["ok"] = (not failed and record["completed_comparisons"] == record["requested_comparisons"]
                        and all(row['ok'] for row in record['pairs']))
        if report_file:
            report_file.write_text(json.dumps(json_values(record), indent=1, allow_nan=False) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
