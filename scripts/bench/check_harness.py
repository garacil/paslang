#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Deterministic benchmark-harness checks; no language compiler is required.

Tool stubs produce explicitly synthetic workloads. Their observations test
command construction, complete output and failure accounting, never speed.
"""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import run as bench
import rounds
import reference_policy as policy
import run_refs


def require(value, message):
    if not value:
        raise AssertionError(message)


def executable(path, body):
    path.write_text('#!' + sys.executable + '\n' + body)
    path.chmod(0o755)
    return str(path)


def invoke(function, arguments):
    # StringIO has no reconfigure; production CLI does, and the stub needs
    # only that harmless method while preserving readable captured output.
    class Output(io.StringIO):
        def reconfigure(self, **kwargs):
            pass
    with patch.object(sys, 'argv', ['checker', *arguments]), contextlib.redirect_stdout(Output()):
        try:
            result = function()
        except SystemExit as error:
            return error.code
    return result or 0



def policy_checks():
    inherited = {"GODEBUG": "cpu.all=off,cpu.erms=off,cpu.fsrm=on,cpu.avx2=on,gctrace=0",
                 "GOAMD64": "v4", "OTHER": "retained"}
    try:
        policy.go_runtime_environment("base", environment=inherited)
    except ValueError:
        pass
    else:
        require(False, "Go base accepted missing capability evidence")
    native = policy.go_runtime_environment("native", "v3", inherited)
    require(native["GODEBUG"] == "gctrace=0" and native["GOAMD64"] == "v3" and
            inherited["GOAMD64"] == "v4" and "cpu.erms=off" in inherited["GODEBUG"],
            "native CPU overrides survived or input environment was mutated")
    policy.validate_go_version("go version go1.27.3-X:nodwarf5 linux/amd64")
    with patch.dict(os.environ, {"GOEXPERIMENT": "none", "GOENV": "/synthetic/user-overrides"}):
        build_env = policy.go_build_environment("/synthetic/output", "native", "v3")
    require(build_env["GOEXPERIMENT"] == "" and build_env["GOENV"] == "off",
            "inherited Go experiments or user environment altered the ordinary reference")
    for version in ("go version go1.27.3 linux/amd64", "go version go1.27.4 linux/amd64", "go version go1.27.30 linux/amd64",
                    "go version go1.27.3-X:unknownexperiment linux/amd64"):
        try:
            policy.validate_go_version(version)
        except ValueError:
            pass
        else:
            require(False, "unreviewed Go version accepted the pinned policy")
    require(len(bench.PAIRS) == 45 and len(bench.units()) == 218 and "b45nist" in bench.PAIRS and
            run_refs.selected_units(None, ["go"]) == bench.units() and
            run_refs.selected_units(["b45nist"], ["go"]) == [("b45nist", "p256"), ("b45nist", "p384")],
            "selected Go mode lost the current full suite or NIST pair")
    require(len(run_refs.selected_units(None, ["rust"])) == 28,
            "Rust default no longer includes every audited section")
    for selectors in (["b45nist"], ["b3spawn"], ["b45nist:p256"], []):
        try:
            run_refs.selected_units(selectors, ["rust"])
        except ValueError:
            pass
        else:
            require(False, "unsupported or empty Rust selection was silently accepted")



def input_resolution_checks(folder):
    work = folder / "compile-cwd"
    unit_directory = work / "build"
    unit_directory.mkdir(parents=True)
    compiler = folder / "compiler/bin/paslangc"
    compiler.parent.mkdir(parents=True)
    compiler.touch()
    interface, unit_object = unit_directory / "unit.pi", unit_directory / "unit.o"
    interface.write_text("controlled compiled interface")
    unit_object.write_text("controlled linked unit")
    program = work / "program"
    generated = work / "program.o"
    generated.write_text("generated program object version one")
    program.with_suffix(".link").write_text("\n".join(
        ["-o", "program", "--gc-sections", "-T", "program.ld", "program.o", "build/unit.o"]) + "\n")
    arguments = [str(compiler), "-cpu", "base", "-o", "program", "main.paslang"]
    original = run_refs.paslang_inputs(arguments, "program", env={}, cwd=work)
    unit = original["units"][0]
    require(len(original["units"]) == 1 and unit["interface"]["path"] == str(interface) and
            unit["object"]["path"] == str(unit_object),
            "relative link/unit paths did not follow the actual compiler cwd")
    generated.write_text("changed generated program object")
    (unit_directory / "unrelated-benchmark.o").write_text("another benchmark's output")
    require(run_refs.paslang_inputs(arguments, "program", env={}, cwd=work) == original,
            "generated/unrelated benchmark objects invalidated library reuse")
    shadow = work / "earlier-unit-directory"
    shadow.mkdir()
    (shadow / "unit.pi").write_text("different earlier interface")
    (shadow / "unit.o").write_text("different earlier object")
    try:
        run_refs.paslang_inputs([*arguments[:-1], "-Fu", str(shadow), arguments[-1]],
                               "program", env={}, cwd=work)
    except RuntimeError as error:
        require("stale executable" in str(error), "changed unit resolution lost its diagnostic")
    else:
        require(False, "an earlier interface shadowing the recorded unit was reused")


def timed_checks(folder):
    a = executable(folder / 'a', "import os\nos.write(1,b'first\\nsecond\\n\\xff')\nos.write(2,b'diagnostic\\n')\n")
    b = executable(folder / 'b', "import os\nos.write(1,b'first\\nother\\n\\xff')\n")
    wall, status, output = bench.once(a)
    require(status == 0 and wall > 0 and output.encode('utf-8', 'surrogateescape') == b'first\nsecond\n\xff',
            'complete multiline/non-UTF8 stdout was lost')
    require(bench.LAST_ONCE[(a, ())]['stderr'] == 'diagnostic\n', 'stderr merged or lost')
    bench.alternate(a, b, 1)
    require(bench.LAST_ROUNDS[(a, b, ())][0]['errors'], 'same-first-line mismatch accepted')
    c = executable(folder / 'c', "print('first',end='')\n")
    d = executable(folder / 'd', "print('first')\n")
    bench.alternate(c, d, 1)
    require(bench.LAST_ROUNDS[(c, d, ())][0]['errors'], 'trailing newline difference accepted')

    def counter(path, bad):
        return executable(path, 'from pathlib import Path\nimport sys\n'
            f'p=Path({str(path) + ".count"!r})\n'
            'n=int(p.read_text())+1 if p.exists() else 1\np.write_text(str(n))\n'
            f"print('wrong' if n=={bad} else 'correct')\nsys.exit(7 if n=={bad} else 0)\n")
    stable = executable(folder / 'stable', "print('correct')\n")
    with patch.object(bench, 'TIMEOUT', 1e100):
        wall, status, answer = bench.once(stable)
    require(status == 0 and answer == 'correct\n' and wall > 0,
            'large finite timed deadline overflowed kernel wait')
    for bad in (1, 2):
        transient = counter(folder / ('transient' + str(bad)), bad)
        (_, sa, _), _, _ = bench.alternate(transient, stable, 3)
        rows = bench.LAST_ROUNDS[(transient, stable, ())]
        require(sa == 7 and len(rows) == 3 and rows[bad-1]['errors'] and
                rows[bad-1]['a']['stdout'] == 'wrong\n', 'early/middle failure was overwritten')
        require([r['first'] for r in rows] == ['a', 'b', 'a'], 'timing order did not alternate')
    # Equal stdout/status is insufficient when a sample emits diagnostics.
    for bad in (1, 2):
        path = folder / ('diagnostic' + str(bad))
        diagnostic = executable(path, 'from pathlib import Path\nimport os\n'
            f'p=Path({str(path) + ".count"!r})\n'
            'n=int(p.read_text())+1 if p.exists() else 1\np.write_text(str(n))\n'
            f"print('correct')\nif n=={bad}:os.write(2,b'GODEBUG warning\\n\\xff')\n")
        bench.alternate(diagnostic, stable, 3)
        rows = bench.LAST_ROUNDS[(diagnostic, stable, ())]
        require(len(rows) == 3 and rows[bad-1]['a']['status'] == 0 and
                rows[bad-1]['a']['stdout'] == 'correct\n' and
                rows[bad-1]['a']['stderr'].encode('utf-8', 'surrogateescape') == b'GODEBUG warning\n\xff' and
                'unexpected stderr' in rows[bad-1]['errors'],
                'early/middle diagnostics were accepted or lost')
    changing = []
    for name in ('changing-a', 'changing-b'):
        path = folder / name
        changing.append(executable(path, 'from pathlib import Path\n'
            f'p=Path({str(path) + ".count"!r})\n'
            'n=int(p.read_text())+1 if p.exists() else 1\np.write_text(str(n))\nprint(n)\n'))
    bench.alternate(*changing, 3)
    rows = bench.LAST_ROUNDS[(*changing, ())]
    require(not rows[0]['errors'] and rows[1]['errors'] and rows[2]['errors'],
            'corresponding but changing outputs accepted')
    slow = executable(folder / 'slow', 'import time\ntime.sleep(5)\n')
    with patch.object(bench, 'TIMEOUT', 0.05):
        bench.alternate(slow, stable, 3)
    rows = bench.LAST_ROUNDS[(slow, stable, ())]
    require(len(rows) == 1 and rows[0]['a']['status'] == 'timeout' and rows[0]['errors'],
            'timeout became a complete successful sample')

    # Both mutants are executable versions of the actual production source.
    # The same external output/status oracles must reject their behavior.
    source = Path(bench.__file__).read_text()
    needle = 'min(remaining, 2_147_483) * 1000'
    require(source.count(needle) == 1, 'large-finite timed mutant anchor changed')
    mutant = types.ModuleType('timed_large_deadline_mutant')
    mutant.__file__ = bench.__file__
    exec(compile(source.replace(needle, 'remaining * 1000'), '<timed-large-deadline-mutant>', 'exec'), mutant.__dict__)
    mutant.TIMEOUT = 1e100
    try:
        mutant.once(stable)
    except OverflowError:
        pass
    else:
        require(False, 'uncapped timed poll mutant escaped large-finite oracle')
    diagnostic = executable(folder / 'stderr-only', "import os\nprint('correct')\nos.write(2,b'warning\\n')\n")
    needle = '        if row["a"]["stderr"] or row["b"]["stderr"]:\n            reasons.append("unexpected stderr")\n'
    require(source.count(needle) == 1, 'timed-stderr mutant anchor changed')
    mutant = types.ModuleType('timed_stderr_mutant')
    mutant.__file__ = bench.__file__
    exec(compile(source.replace(needle, ''), '<timed-stderr-mutant>', 'exec'), mutant.__dict__)
    mutant.alternate(diagnostic, stable, 1)
    require(not mutant.LAST_ROUNDS[(diagnostic, stable, ())][0]['errors'],
            'timed-stderr mutant did not exercise the rejected diagnostic')
    mutant = types.ModuleType('reader_mutant')
    mutant.__file__ = bench.__file__
    needle = 'out = so.read().decode("utf-8", "surrogateescape")'
    require(source.count(needle) == 1, 'reader mutant anchor changed')
    exec(compile(source.replace(needle, needle + '.splitlines()[0]'), '<reader-mutant>', 'exec'), mutant.__dict__)
    require(mutant.once(a)[2] != output, 'first-line-reader mutant escaped full-output oracle')
    mutant = types.ModuleType('status_mutant')
    mutant.__file__ = bench.__file__
    exec(compile(source.replace('sa = sa or xa', 'sa = xa').replace('sb = sb or xb', 'sb = xb'),
                 '<status-mutant>', 'exec'), mutant.__dict__)
    transient = counter(folder / 'mutant-transient', 1)
    require(mutant.alternate(transient, stable, 3)[0][1] != 7,
            'last-status-only mutant escaped accumulated-status oracle')


def memory_checks():
    calls = []
    def sample(exe, env, args, expected):
        calls.append(exe)
        return {'peak_kib': 1024 if exe == 'p' else 2048, 'status': 0,
                'stdout': expected, 'stderr': '', 'ok': True}
    with patch.object(bench, 'memory_once', sample):
        ma, mb, a, b = bench.memory_pair('r', 'p', 4, None, None, (), 'all\n', 'all\n')
    require(calls == ['r', 'p', 'p', 'r', 'r', 'p', 'p', 'r'] and ma == 2 and mb == 1,
            'memory samples did not alternate or median was wrong')
    require(len(a) == len(b) == 4 and all(row['stdout'] == 'all\n' for row in a+b),
            'memory observations missing')
    for failure in ({'status': 7}, {'status': 'timeout'}, {'peak_kib': 0},
                    {'stdout': 'wrong\n'}, {'stderr': 'GODEBUG warning\n'}):
        def fake_peak(argv, **kwargs):
            os.write(kwargs['stdout'], failure.get('stdout', 'all\n').encode())
            os.write(kwargs['stderr'], failure.get('stderr', '').encode())
            return failure.get('peak_kib', 1024), failure.get('status', 0)
        with patch.object(bench, 'peak_kib', fake_peak):
            row = bench.memory_once('synthetic', expected='all\n')
        require(not row['ok'], 'invalid traced memory result accepted: ' + repr(failure))

    source = Path(bench.__file__).read_text()
    needle = 'status == 0 and kib > 0 and not error and'
    require(source.count(needle) == 1, 'memory-stderr mutant anchor changed')
    mutant = types.ModuleType('memory_stderr_mutant')
    mutant.__file__ = bench.__file__
    exec(compile(source.replace(needle, 'status == 0 and kib > 0 and'),
                 '<memory-stderr-mutant>', 'exec'), mutant.__dict__)
    def warning_peak(argv, **kwargs):
        os.write(kwargs['stdout'], b'all\n')
        os.write(kwargs['stderr'], b'GODEBUG warning\n')
        return 1024, 0
    with patch.object(mutant, 'peak_kib', warning_peak):
        require(mutant.memory_once('synthetic', expected='all\n')['ok'],
                'memory-stderr mutant did not exercise the rejected diagnostic')


def rounds_checks(folder):
    calls = []
    diagnostics = [False]
    def fake_once(exe, env=None, args=()):
        calls.append(exe)
        wall = 1 if exe.endswith('.pl') else 2
        bench.LAST_ONCE[(exe, tuple(args))] = {'wall_s': wall, 'status': 0,
                                               'stdout': 'complete\n', 'stderr': 'warning\n' if diagnostics[0] and exe.endswith('.go.bin') else ''}
        return wall, 0, 'complete\n'
    (folder / 'b1loop.pl').touch()
    (folder / 'b1loop.go.bin').write_text('explicit synthetic ELF-discovery fixture\n' * 4)
    def synthetic_linkage(path, dynamic=False):
        path = Path(path)
        metadata = {'format': 'paslang-go-linked-program-v1',
                    'binary': {'path': str(path.resolve()), 'bytes': path.stat().st_size,
                               'sha256': __import__('hashlib').sha256(path.read_bytes()).hexdigest()},
                    'elf': {'class': 64, 'machine': 62, 'type': 2},
                    'needed': ['libc.so.6'] if dynamic else [],
                    'interpreter': '/synthetic/loader' if dynamic else None,
                    'has_dynamic_segment': dynamic}
        metadata['identity_sha256'] = policy._digest(metadata)
        return metadata
    report = folder / 'rounds.json'
    with patch.object(rounds, 'OUT', str(folder)), patch.object(bench, 'OUT', str(folder)), \
         patch.object(rounds, 'once', fake_once), patch.object(bench, 'go_binary_metadata', synthetic_linkage):
        code = invoke(rounds.main, ['-n', '8', '--cpu', 'native', '--json', str(report), 'b1loop'])
        row = json.loads(report.read_text())['pairs']['b1loop']
        require(code == 0 and len(calls) == 16 and row['completed_rounds'] == 8,
                'requested rounds were shortened')
        code = invoke(rounds.main, ['-n', '1', '--cpu', 'native', 'b1loop'])
        require(code == 0, 'one-round quantile case failed')
        diagnostics[0] = True
        code = invoke(rounds.main, ['-n', '2', '--cpu', 'native', '--json', str(report), 'b1loop'])
        row = json.loads(report.read_text())['pairs']['b1loop']
        require(code == 1 and not row['same_output'] and
                all('unexpected stderr' in part['errors'] and part['go']['status'] == 0 and
                    part['go']['stdout'] == 'complete\n' and part['go']['stderr'] == 'warning\n'
                    for part in row['rounds']),
                'legacy rounds accepted or discarded a successful-status diagnostic')
        diagnostics[0] = False
        (folder / 'b1loop.pl').unlink()
        require(invoke(rounds.main, ['--cpu', 'native', 'b1loop']) == 1, 'missing binary passed')
    # Old-style CPU selectors cannot bypass the same provider refusal.
    (folder / 'b1loop.base.pl').touch()
    report.write_text(json.dumps({'ok': True, 'pairs': ['prior success']}))
    before_calls = len(calls)
    with patch.object(rounds, 'OUT', str(folder)), patch.object(bench, 'OUT', str(folder)), \
         patch.object(rounds, 'once', fake_once), patch.object(rounds, 'go_env', return_value={'GODEBUG': 'cpu.all=off'}), \
         patch.object(bench, 'go_binary_metadata', lambda path: synthetic_linkage(path, True)):
        require(invoke(rounds.main, ['-n', '1', '--cpu', 'base', '--json', str(report), 'b1loop']) != 0,
                'legacy baseline bypassed the dynamic-provider gate')
    refused = json.loads(report.read_text())
    require(not refused['ok'] and 'provider ISA unproved' in refused['error'] and
            refused['go_artifacts'] and not refused['go_artifact_evidence'][0]['ok'] and len(calls) == before_calls,
            'legacy provider refusal timed a sample, lost linkage, or left prior successful JSON')
    source = Path(rounds.__file__).read_text()
    needle = '        for r in range(rounds):\n'
    require(source.count(needle) == 1, 'short-round mutant anchor changed')
    mutant = types.ModuleType('short_rounds_mutant')
    mutant.__file__ = rounds.__file__
    exec(compile(source.replace(needle, needle + '            if r >= 5:\n                break\n'),
                 '<short-round-mutant>', 'exec'), mutant.__dict__)
    (folder / 'b1loop.pl').touch()
    with patch.object(mutant, 'OUT', str(folder)), patch.object(bench, 'OUT', str(folder)), \
         patch.object(mutant, 'once', fake_once), patch.object(bench, 'go_binary_metadata', synthetic_linkage):
        require(invoke(mutant.main, ['-n', '8', '--cpu', 'native', '--json', str(report), 'b1loop']) == 1,
                'short-round mutant passed incomplete-round oracle')
        require(json.loads(report.read_text())['pairs']['b1loop']['completed_rounds'] == 5,
                'short-round mutant was not exercised')


STUB = r'''import json, os, sys
from pathlib import Path
kind=Path(sys.argv[0]).name
args=sys.argv[1:]
log=Path(os.environ['BENCH_STUB_LOG'])
with log.open('a') as f:
    f.write(json.dumps({'tool':kind,'args':args,'env':{k:os.environ.get(k) for k in ('GOAMD64','GOARCH','GOOS','GODEBUG')}})+'\n')
if kind=='paslangc' and args==['-v']: print('paslangc stub');sys.exit()
if kind=='go' and args==['version']: print('go version go1.27.3-X:nodwarf5 linux/amd64');sys.exit()
if kind=='go' and args[:2]==['env','-json']: print(json.dumps({'GOAMD64':os.environ.get('GOAMD64'),'GOARCH':'amd64','GOOS':'linux'}));sys.exit()
if kind=='rustc' and args==['-Vv']: print('rustc stub\nrelease: stub');sys.exit()
if kind=='rustc' and args[:2]==['--print','sysroot']: print('/synthetic/sysroot');sys.exit()
if kind=='rustc' and args[:2]==['--print','cfg']: print('target_arch="x86_64"');sys.exit()
out=Path(args[args.index('-o')+1])
body='import os\n# Explicit synthetic benchmark workload.\n'
answer=b'first\ncomplete\n'
if kind=='rustc' and os.environ.get('BENCH_STUB_MODE')=='wrong-rust': answer=b'first\nWRONG\n'
body+='os.write(1,'+repr(answer)+')\n'
mode=os.environ.get('BENCH_STUB_MODE','')
if mode.endswith('-go') and kind=='go' or mode.endswith('-paslang') and kind=='paslangc':
    if mode.startswith('timed-stderr'):
        body+="os.write(2,b'GODEBUG synthetic warning\\n\\xff')\n"
    if mode.startswith('memory-stderr'):
        body+="from pathlib import Path\ntraced=next(line.split()[1] for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('TracerPid:'))\nif traced!='0':os.write(2,b'GODEBUG traced warning\\n\\xff')\n"
out.write_text('#!'+sys.executable+'\n'+body)
out.chmod(0o755)
if kind=='paslangc':
    unit=Path(os.environ['PASLANG_LIB'])/'fixture.o'
    out.with_suffix('.link').write_text('\n'.join(['-o',str(out),'--gc-sections','-T',str(out.with_suffix('.ld')),str(out.with_suffix('.o')),str(unit)])+'\n')
'''


# The test launcher supplies wall/peak numbers and external tool metadata.
# Each stub process
# still executes through production once()/peak_kib(), with its real full
# stdout, stderr, status and command flags. Aggregate verdicts consequently
# depend on explicit synthetic observations rather than desktop load/RSS.
CLI_LAUNCHER = r"""import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import run as bench
import rounds
import run_refs
import reference_caps as caps
import reference_policy as policy
import hashlib

# Only external toolchain/library discovery and capability evidence are
# synthetic. Production flag construction, manifest checks and gates still
# run, and no installed Rust compiler or sysroot is needed by make check.
def synthetic_configuration(rustc, target=None, sysroot=None, provider=None):
    selected = target or 'x86_64-unknown-linux-gnu'
    actual_provider = 'musl' if selected.endswith('-musl') else 'gnu'
    if provider is not None and provider != actual_provider:
        raise ValueError('synthetic provider/target mismatch')
    root = Path(sysroot or os.environ['BENCH_STUB_SYSROOT'])
    marker = root / 'stdlib.marker'
    fingerprint = hashlib.sha256(marker.read_bytes()).hexdigest()
    return {'target': selected, 'host': 'x86_64-unknown-linux-gnu', 'provider': actual_provider,
            'sysroot': str(root), 'identity_sha256': fingerprint,
            'standard_library': {'sha256': fingerprint}, 'bundled_provider': None,
            'base_capability': {'certified': False}}

def synthetic_binary(configuration, path):
    fingerprint = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return {'binary': {'sha256': fingerprint}, 'identity_sha256': fingerprint,
            'isa_certified': False}

def synthetic_capabilities(configuration, cpu, binary=None, proof=None, runtime_environment=None):
    if cpu == 'base' and os.environ.get('BENCH_STUB_MODE') == 'capability-refusal':
        raise ValueError('synthetic baseline capability evidence is unavailable')
    return {'certified': True, 'synthetic_fixture': True, 'cpu': cpu}

def synthetic_go_capabilities(go_executable, outdir, environment=None):
    marker = Path(os.environ['BENCH_STUB_SYSROOT']) / 'go-source.marker'
    fingerprint = hashlib.sha256(marker.read_bytes()).hexdigest()
    return {'format': 'paslang-go-cpu-capabilities-v1', 'policy_id': policy.GO_POLICY,
            'identity_sha256': fingerprint, 'base_supported': os.environ.get('BENCH_STUB_MODE') != 'go-capability-refusal',
            'runtime_cpu_options': ['cpu.all=off', 'cpu.erms=on'],
            'baseline_reason': 'synthetic FSRM/ISA refusal',
            'native_state': {'ERMS': True, 'FSRM': False}, 'base_state': {},
            'compiler': {'synthetic_fixture': True}, 'sources': {}, 'go_environment': {},
            'observations': []}

def synthetic_validate_go(capabilities, go_executable=None):
    return capabilities

def synthetic_go_binary(path):
    path = Path(path)
    dynamic = os.environ.get('BENCH_STUB_MODE') == 'dynamic-go'
    metadata = {'format': 'paslang-go-linked-program-v1',
                'binary': {'path': str(path.resolve()), 'bytes': path.stat().st_size,
                           'sha256': hashlib.sha256(path.read_bytes()).hexdigest()},
                'elf': {'class': 64, 'machine': 62, 'type': 2},
                'needed': ['libc.so.6'] if dynamic else [],
                'interpreter': '/synthetic/ld-linux-x86-64.so.2' if dynamic else None,
                'has_dynamic_segment': dynamic}
    metadata['identity_sha256'] = policy._digest(metadata)
    return metadata

run_refs.go_binary_metadata = synthetic_go_binary
policy.prepare_go_capabilities = synthetic_go_capabilities
policy.validate_go_capabilities = synthetic_validate_go
run_refs.prepare_go_capabilities = synthetic_go_capabilities
run_refs.validate_go_capabilities = synthetic_validate_go
bench.prepare_go_capabilities = synthetic_go_capabilities
caps.rust_configuration = synthetic_configuration
caps.rust_binary_metadata = synthetic_binary
caps.require_rust_capabilities = synthetic_capabilities
# Exercise amd64 command construction with Python stubs on either host.
run_refs.platform.machine = lambda: 'x86_64'
mode = os.environ.get('BENCH_STUB_MODE', '')
original_once, original_peak = bench.once, bench.peak_kib
counts, memory_calls, timing_calls = {}, 0, 0

def synthetic_once(executable, env=None, args=()):
    global timing_calls
    timing_calls += 1
    if mode == 'interrupt-timing' and timing_calls == 4:
        raise KeyboardInterrupt('synthetic interrupted timed sample')
    wall, status, answer = original_once(executable, env, args)
    if status == 0:
        pascal = executable.endswith('.paslang')
        counts[executable] = counts.get(executable, 0) + 1
        wall = ((0.2, 0.2, 1.2, 1.2)[(counts[executable] - 1) % 4]
                if pascal and mode == 'quartile' else (0.5 if pascal else 1.0))
        bench.LAST_ONCE[(executable, tuple(args))]['wall_s'] = wall
    return wall, status, answer

def synthetic_peak(argv, **kwargs):
    global memory_calls
    kib, status = original_peak(argv, **kwargs)
    memory_calls += 1
    if mode == 'memory-error':
        raise OSError('synthetic ptrace refusal after real sample')
    if mode == 'interrupt-memory' and memory_calls == 2:
        raise KeyboardInterrupt('synthetic interrupted memory sample')
    if status == 0 and kib > 0:
        kib = 1024 if argv[0].endswith('.paslang') else 2048
    return kib, status

bench.once, bench.peak_kib = synthetic_once, synthetic_peak
rounds.once = synthetic_once
sys.argv = [sys.argv[2], *sys.argv[3:]]
raise SystemExit(bench.main() if sys.argv[0] == 'run.py' else rounds.main())
"""


def strict_json(path):
    def reject_constant(value):
        raise AssertionError('non-finite token in exported JSON: ' + value)
    return json.loads(path.read_text(), parse_constant=reject_constant)


def cli_checks(folder):
    root = folder / 'cli'
    here = root / 'scripts/bench'
    here.mkdir(parents=True)
    for name in ('run.py', 'rounds.py', 'run_refs.py', 'peak.py', 'reference_policy.py', 'reference_caps.py',
                 'metadata_scope.py', 'check_metadata_scope.py', 'go_cpu_probe.go', 'go_cpu_probe.s'):
        shutil.copy(Path(bench.HERE) / name, here / name)
    (here / 'rust').mkdir()
    for suffix in ('paslang', 'go', 'rs'):
        source = here / ('rust/b1loop.rs' if suffix == 'rs' else 'b1loop.' + suffix)
        source.write_text('synthetic compiler-stub input\n')
    bindir = root / 'tools'
    bindir.mkdir()
    for tool in ('paslangc', 'go', 'rustc'):
        executable(bindir / tool, STUB)
    log = root / 'commands.jsonl'
    sysroot = root / 'sysroot'
    sysroot.mkdir()
    marker = sysroot / 'stdlib.marker'
    marker.write_text('synthetic standard library version one')
    go_marker = sysroot / 'go-source.marker'
    go_marker.write_text('synthetic Go source/tool inputs version one')
    paslang_units = root / 'paslang-units'
    paslang_units.mkdir()
    for extension in ('pi', 'o'):
        (paslang_units / ('fixture.' + extension)).write_text('synthetic Paslang library ' + extension)
    env = dict(os.environ, PATH=str(bindir), BENCH_STUB_LOG=str(log),
               BENCH_STUB_SYSROOT=str(sysroot), PASLANG_LIB=str(paslang_units), GOAMD64='v4',
               GODEBUG='cpu.all=off,cpu.avx2=off,gctrace=0', GOPROXY='secret-proxy-marker',
               GOAUTH='secret-auth-marker', PASLANG_PRIVATE='secret-pascal-marker')
    report = root / 'result.json'
    common = ['--pairs', 'b1loop', '--reference', 'go,rust', '--cpu', 'native,base',
              '--go-native-level', 'v3', '-n', '2', '--memory-runs', '2', '--json', str(report)]
    def launch(script, arguments, extra=None):
        return subprocess.run([sys.executable, '-c', CLI_LAUNCHER, str(here), script, *arguments],
                              env=dict(env, **(extra or {})), capture_output=True, text=True, timeout=30)
    result = launch('run.py', common)
    require(result.returncode == 0, 'normal CLI synthetic run failed: ' + result.stderr + result.stdout)
    data = strict_json(report)
    require(data['format'] == 'paslang-bench-refs-v1' and data['ok'] and len(data['pairs']) == 4,
            'normal CLI did not retain all references/CPUs')
    for row in data['pairs']:
        require(row['completed_rounds'] == 2 and len(row['reference_memory']) == 2 and
                row['time_budget'] == bench.BUDGET['b1loop'] and row['memory_budget'] == bench.MEM_BUDGET,
                'round count or reference budget changed')
        if row['reference'] == 'go':
            expected = 'gctrace=0' + (',cpu.all=off,cpu.erms=on' if row['cpu'] == 'base' else '')
            require(not row['artifact_metadata']['has_dynamic_segment'] and
                    row['artifact_capability_evidence']['binary_sha256'] == row['artifact_metadata']['binary']['sha256'],
                    'normal static Go artifact evidence was lost or refused')
            require(row['runtime_environment']['GODEBUG'] == expected and
                    row['capability_evidence']['identity_sha256'] == data['go_capabilities']['identity_sha256'],
                    'Go CPU overrides leaked or capability identity was lost')
    exported = json.dumps(data)
    require(not any(secret in exported for secret in ('secret-proxy-marker','secret-auth-marker','secret-pascal-marker')),
            'unrelated environment secret exported')
    commands = [json.loads(line) for line in log.read_text().splitlines()]
    go_builds = [r for r in commands if r['tool']=='go' and r['args'][:1]==['build']]
    require({r['env']['GOAMD64'] for r in go_builds} == {'v1','v3'} and len(go_builds) == 2 and
            all(r['env']['GODEBUG'] == 'gctrace=0' for r in go_builds),
            'native/base Go targets were not distinct or compiler hosts inherited CPU masks')
    rust_builds = [r for r in commands if r['tool']=='rustc' and '-o' in r['args']]
    require(len(rust_builds) == 2 and all('opt-level=3' in r['args'] for r in rust_builds) and
            {arg for r in rust_builds for arg in r['args'] if arg.startswith('target-cpu=')} ==
            {'target-cpu=x86-64','target-cpu=native'}, 'Rust optimization/CPU flags wrong')
    before = len([r for r in commands if '-o' in r['args']])
    result = launch('rounds.py', common)
    require(result.returncode == 0, 'normal rounds reuse failed: ' + result.stderr)
    commands = [json.loads(line) for line in log.read_text().splitlines()]
    require(len([r for r in commands if '-o' in r['args']]) == before, 'rounds rebuilt executables')
    # A valid JSON scalar or list is still an invalid build manifest. It
    # must produce a failed current result, never a finally-written success.
    manifest = root / 'build/bench/b1loop.refs.native.paslang.build.json'
    saved_manifest = manifest.read_text()
    for value in (None, [], 42, {'identity': []}):
        try:
            manifest.write_text(json.dumps(value))
            result = launch('rounds.py', common)
            refused = strict_json(report)
            require(result.returncode == 1 and refused['ok'] is False and
                    refused['completed_comparisons'] == 0 and
                    'malformed build manifest' in refused['error'],
                    'malformed manifest was reused or produced successful JSON')
        finally:
            manifest.write_text(saved_manifest)

    # Native reuse must reject a foreign CPU identity and changed compiler
    # bytes, even though executable/source/flags and printed version agree.
    try:
        changed_manifest = json.loads(saved_manifest)
        changed_manifest['identity']['native_host'] = {'foreign_cpu': True}
        manifest.write_text(json.dumps(changed_manifest))
        result = launch('rounds.py', common)
        require(result.returncode == 1 and 'stale executable' in strict_json(report)['error'],
                'foreign native-host identity was reused')
    finally:
        manifest.write_text(saved_manifest)
    compiler = bindir / 'paslangc'
    saved_compiler = compiler.read_text()
    try:
        compiler.write_text(saved_compiler + '\n# different bytes, same printed version\n')
        result = launch('rounds.py', common)
        require(result.returncode == 1 and 'stale executable' in strict_json(report)['error'],
                'changed compiler bytes with unchanged version were reused')
    finally:
        compiler.write_text(saved_compiler)

    for extension in ('pi', 'o'):
        library = paslang_units / ('fixture.' + extension)
        saved_library = library.read_text()
        try:
            library.write_text('changed unit bytes with unchanged compiler/source/flags')
            result = launch('rounds.py', common)
            require(result.returncode == 1 and 'stale executable' in strict_json(report)['error'],
                    'changed Paslang unit ' + extension + ' reused an old executable')
        finally:
            library.write_text(saved_library)

    saved_go_marker = go_marker.read_text()
    try:
        go_marker.write_text('changed Go source/tool bytes, same printed compiler version')
        result = launch('rounds.py', common)
        require(result.returncode == 1 and 'stale executable' in strict_json(report)['error'],
                'changed Go capability/source identity reused an old executable')
    finally:
        go_marker.write_text(saved_go_marker)

    saved_marker = marker.read_text()
    try:
        marker.write_text('changed library bytes, same compiler and source')
        result = launch('rounds.py', common)
        require(result.returncode == 1 and 'stale executable' in strict_json(report)['error'],
                'changed Rust standard-library contents reused an old executable')
    finally:
        marker.write_text(saved_marker)

    result = launch('run.py', common, {'BENCH_STUB_MODE': 'capability-refusal'})
    data = strict_json(report)
    require(result.returncode == 1 and not data['ok'] and
            'baseline capability evidence' in data['error'] and
            all(not row['rounds'] for row in data['pairs']
                if row['reference'] == 'rust' and row['cpu'] == 'base'),
            'uncertified Rust baseline was timed or reported successful')
    result = launch('run.py', common, {'BENCH_STUB_MODE': 'go-capability-refusal'})
    data = strict_json(report)
    require(result.returncode == 1 and not data['ok'] and not data['go_capabilities']['base_supported'] and
            all(not row['rounds'] for row in data['pairs'] if row['reference'] == 'go' and row['cpu'] == 'base'),
            'uncertified Go baseline was timed or reported successful')
    # External provider discovery is synthetic; the production ELF/provider
    # gate must still accept static base and ordinary dynamic native only.
    result = launch('run.py', common, {'BENCH_STUB_MODE': 'dynamic-go'})
    data = strict_json(report)
    native_go = next(row for row in data['pairs'] if row['reference'] == 'go' and row['cpu'] == 'native')
    base_go = next(row for row in data['pairs'] if row['reference'] == 'go' and row['cpu'] == 'base')
    require(result.returncode == 1 and not data['ok'] and native_go['ok'] and
            native_go['artifact_metadata']['needed'] == ['libc.so.6'] and
            not base_go['rounds'] and not base_go['reference_memory'] and not base_go['completed'] and
            base_go['artifact_metadata']['has_dynamic_segment'] and
            'provider ISA unproved' in base_go['capability_refusal'],
            'dynamic Go base was timed, silently changed, or ordinary native was refused')
    path = here / 'run_refs.py'
    original = path.read_text()
    needle = 'row["artifact_capability_evidence"] = require_go_artifact_capabilities(cpu, artifacts[artifact_key])'
    require(original.count(needle) == 1, 'Go artifact gate mutant anchor changed')
    try:
        path.write_text(original.replace(needle, 'row["artifact_capability_evidence"] = {"gate_omitted": True}'))
        result = launch('run.py', common, {'BENCH_STUB_MODE': 'dynamic-go'})
        changed = strict_json(report)
        require(result.returncode == 0 and changed['ok'] and
                all(row['completed'] and row['rounds'] for row in changed['pairs']),
                'omitted provider gate mutant did not reach the intended dynamic-base violation')
    finally:
        path.write_text(original)

    # An unsupported Rust request must fail before even compiler metadata.
    for pair in ('b45nist:p256', 'b3spawn'):
        log.write_text('')
        result = launch('run.py', ['--pairs', pair, '--reference', 'rust', '--cpu', 'native', '--json', str(report)])
        require(result.returncode == 2 and 'no audited twin' in result.stderr and not log.read_text(),
                'unsupported Rust pair silently fell back or invoked a compiler')

    # Median below budget is insufficient for the stronger rounds CLI:
    # these exact synthetic ratios have median .7 but upper quartile 1.2.
    four_rounds = list(common)
    four_rounds[four_rounds.index('-n') + 1] = '4'
    result = launch('run.py', four_rounds, {'BENCH_STUB_MODE': 'quartile'})
    data = strict_json(report)
    require(result.returncode == 0 and data['ok'] and
            all(row['ratio_time'] < row['time_budget'] and row['q3'] > 1
                and not row['requires_q3_below_one'] for row in data['pairs']),
            'synthetic quartile control did not isolate the median-only run contract')
    result = launch('rounds.py', four_rounds, {'BENCH_STUB_MODE': 'quartile'})
    data = strict_json(report)
    require(result.returncode == 1 and data['ok'] is False and
            all(row['ratio_time'] < row['time_budget'] and row['q3'] > 1
                and row['requires_q3_below_one'] and not row['ok'] for row in data['pairs']),
            'selected-reference rounds dropped the upper-quartile rule')

    # A tracer failure must preserve all completed timing evidence and the
    # bytes/status/error of each failed memory observation.
    result = launch('run.py', common, {'BENCH_STUB_MODE': 'memory-error'})
    data = strict_json(report)
    require(result.returncode == 1 and not data['ok'] and len(data['pairs']) == 4,
            'memory failure disappeared from the comparison record')
    for row in data['pairs']:
        memories = row['reference_memory'] + row['paslang_memory']
        require(len(row['rounds']) == 2 and all(not r['errors'] for r in row['rounds']) and
                len(memories) == 4 and all(not m['ok'] and m['status'] == 'measurement-error' and
                m['stdout'] == 'first\ncomplete\n' and
                'synthetic ptrace refusal' in m['measurement_error'] for m in memories),
                'memory failure discarded timing rounds, full output or its measurement error')

    for kind in ('timed', 'memory'):
        for side in ('go', 'paslang'):
            result = launch('run.py', common, {'BENCH_STUB_MODE': kind + '-stderr-' + side})
            data = strict_json(report)
            affected = [row for row in data['pairs'] if side == 'paslang' or row['reference'] == side]
            require(result.returncode == 1 and not data['ok'] and affected and all(not row['ok'] for row in affected),
                    kind + ': unexpected ' + side + ' stderr passed')
            for row in affected:
                if kind == 'timed':
                    samples = [part[key] for part in row['rounds'] for key in ('a', 'b')]
                    require(all('unexpected stderr' in part['errors'] for part in row['rounds']) and
                            not row['reference_memory'] and not row['paslang_memory'],
                            'diagnostic timed sample proceeded to memory or lost sticky failure')
                else:
                    samples = row['reference_memory'] + row['paslang_memory']
                    require(all(not part['errors'] for part in row['rounds']) and
                            any(not sample['ok'] for sample in samples),
                            'traced-only diagnostic was not isolated from clean timing')
                warnings = [sample for sample in samples if sample['stderr']]
                require(warnings and all(sample['status'] == 0 and sample['stdout'] == 'first\ncomplete\n' and
                        sample['stderr'].encode('utf-8','surrogateescape').endswith(b'\xff') for sample in warnings),
                        'diagnostic status/full stdout/non-UTF8 stderr were discarded')

    result = launch('run.py', common, {'BENCH_STUB_MODE': 'interrupt-memory'})
    data = strict_json(report)
    require(result.returncode != 0 and data['ok'] is False and
            'KeyboardInterrupt' in data['error'] and data['completed_comparisons'] == 0 and
            data['attempted_comparisons'] == 1 and
            data['requested_comparisons'] == 4, 'interrupted partial series was reported successful')
    row = data['pairs'][0]
    require(not row['ok'] and not row['completed'] and len(row['rounds']) == 2 and
            len(row['reference_memory']) == len(row['paslang_memory']) == 1 and
            row['reference_memory'][0]['ok'] and
            row['reference_memory'][0]['stdout'] == 'first\ncomplete\n' and
            row['paslang_memory'][0]['status'] == 'interrupted' and
            'KeyboardInterrupt' in row['paslang_memory'][0]['measurement_error'],
            'interruption lost completed time/memory evidence or the incomplete sample')

    # Round one completes; in round two the first (Pascal) side completes
    # and the later reference side is interrupted. The current comparison
    # and every completed stdout must already be attached to the report.
    for script in ('run.py', 'rounds.py'):
        result = launch(script, common, {'BENCH_STUB_MODE': 'interrupt-timing'})
        data = strict_json(report)
        require(result.returncode != 0 and data['ok'] is False and
                'KeyboardInterrupt' in data['error'] and data['completed_comparisons'] == 0 and
            data['attempted_comparisons'] == 1 and
                data['requested_comparisons'] == 4 and len(data['pairs']) == 1,
                script + ': timed interruption hid the active comparison or reported success')
        row = data['pairs'][0]
        require(not row['ok'] and not row['completed'] and row['completed_rounds'] == 1 and row['requested_rounds'] == 2 and
                row['ratio_time'] is None and not row['reference_memory'] and not row['paslang_memory'] and
                len(row['rounds']) == 2, script + ': timed interruption lost completed-count/incomplete evidence')
        first, partial = row['rounds']
        require(first['completed'] and not first['errors'] and
                all(first[side]['status'] == 0 and first[side]['stdout'] == 'first\ncomplete\n'
                    for side in ('a', 'b')) and
                not partial['completed'] and partial['first'] == 'b' and
                partial['b']['status'] == 0 and partial['b']['stdout'] == 'first\ncomplete\n' and
                partial['a']['status'] == 'interrupted' and
                any('KeyboardInterrupt' in error for error in partial['errors']),
                script + ': timed interruption discarded prior/partial full output or the failing side')

    (here / 'b1loop.paslang').write_text('changed synthetic input\n')
    require(launch('rounds.py', common).returncode == 1 and
            'stale executable' in json.loads(report.read_text())['error'], 'stale source reused')
    result = launch('run.py', common, {'BENCH_STUB_MODE':'wrong-rust'})
    data = strict_json(report)
    require(result.returncode == 1 and not data['ok'] and len(data['pairs']) == 4 and
            all(r['same_output'] for r in data['pairs'] if r['reference']=='go') and
            all(not r['same_output'] for r in data['pairs'] if r['reference']=='rust'),
            'failed reference disappeared behind successful reference')
    (bindir / 'rustc').unlink()
    log.write_text('')
    result = launch('run.py', common)
    require(result.returncode == 2 and 'unavailable' in result.stderr and not log.read_text(),
            'missing explicitly requested Rust did not fail before build')
    require(json.loads(report.read_text())['ok'] is False and
            json.loads(report.read_text())['completed_comparisons'] == 0,
            'refused invocation left an earlier successful record')
    # Parser type/choice failures occur before normal option validation.
    # Both destination syntaxes must replace an earlier successful report.
    for arguments in (['--pairs', 'b1loop', '-n', 'bad', '--json', str(report)],
                      ['--pairs', 'b1loop', '--go-native-level', 'v5', '--json=' + str(report)],
                      ['--pairs', 'b1loop', '--unknown', '--json', str(report)]):
        report.write_text(json.dumps({'ok': True, 'pairs': ['old successful result']}))
        result = launch('run.py', arguments)
        refused = strict_json(report)
        require(result.returncode == 2 and refused['ok'] is False and
                refused['completed_comparisons'] == 0 and refused['pairs'] == [] and refused['error'],
                'parse-argument refusal left earlier successful JSON untouched')

    go_only = ['--pairs','b1loop','--reference','go','--cpu','base','-n','1','--memory-runs','1']
    require(launch('run.py', go_only).returncode == 0, 'Go-only mode required Rust')
    for arguments in (['--pairs','unknown','--reference','go','--cpu','base'],
                      ['--pairs','b1loop','--reference','go','--cpu','native'],
                      ['--pairs','b1loop','--reference','go','--cpu','base','-n','0']):
        require(launch('run.py', arguments).returncode != 0, 'invalid selection/CPU/count accepted')


def main():
    with tempfile.TemporaryDirectory(prefix='bench-harness-') as directory:
        folder = Path(directory)
        policy_checks()
        input_resolution_checks(folder)
        timed_checks(folder)
        memory_checks()
        rounds_checks(folder)
        cli_checks(folder)
    print('benchmark harness: source-bound Go capability wiring, full Go/Rust selection, complete output, all rounds, failures, deterministic CLI observations, strict JSON, manifest/CPU/tool reuse, quartiles, memory errors/interruption and source mutants pass')


if __name__ == '__main__':
    main()
