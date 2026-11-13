#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Equivalent compiler build-time/executable-size probe (P223/P525).

build.py [-n rounds] [--json path] retains the legacy Go/paslang default.
Opt in with --reference go,rust --cpu native,base --go-native-level v3.
Native Go's level must be explicitly reviewed; base uses v1. Rust uses
opt-level=3, target-cpu=native/x86-64 and its ordinary default linkage/drop.
Modern compiler hosts remain unmasked; base runtime masks affect only the
generated program. Both environments are recorded per observation.
Every generated round (including warmups) executes both new binaries and
checks full stdout, status and stderr against an independent nonce oracle.
Per-reference paslang series stay distinct. No third-party crates/modules.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import shutil
import signal
import statistics
import subprocess
import tempfile
import sys
import time

from reference_policy import (go_build_environment, go_runtime_environment,
                              go_policy_description, validate_go_version, prepare_go_capabilities, validate_go_capabilities, go_binary_metadata, require_go_artifact_capabilities)
from reference_caps import (rust_configuration, rust_build_args, rust_binary_metadata,
                            require_rust_capabilities, rust_runtime_environment)
from run_refs import paslang_inputs

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / 'build/bench/compile'
N = 3000
BUDGET = 0.99
FORMAT = 'paslang-compiler-build-refs-v1'
ENV_KEYS = ('GOENV', 'GOAMD64', 'GOARCH', 'GOOS', 'GOFLAGS', 'GOCACHE', 'GOTOOLCHAIN', 'GOWORK',
            'GOEXPERIMENT', 'CGO_ENABLED', 'GODEBUG', 'GOGC', 'GOMEMLIMIT', 'GOMAXPROCS',
            'GLIBC_TUNABLES', 'LD_HWCAP_MASK',
            'RUST_STD_DETECT_UNSTABLE', 'MALLOC_CHECK_', 'MALLOC_TOP_PAD_', 'MALLOC_PERTURB_',
            'MALLOC_MMAP_THRESHOLD_', 'MALLOC_TRIM_THRESHOLD_', 'MALLOC_MMAP_MAX_',
            'MALLOC_ARENA_MAX', 'MALLOC_ARENA_TEST',
            'PASLANG_LIB', 'PASLANG_CPU', 'PASLANG_GC', 'PASLANG_GCSTRESS', 'PASLANG_GCPOISON',
            'PASLANG_GCVERIFY', 'PASLANG_GCWORKERS', 'PASLANG_ASYNCPREEMPTOFF')


def count(functions):
    return N if functions is None else functions


def paslang_source(nonce, functions=None):
    out = ['program gen;', '', 'uses', '  sysutils;', '']
    for k in range(count(functions)):
        out += [f'function F{k}(X: Integer): Integer;', 'var', '  i, s: Integer;', 'begin',
                '  s := X;', '  for i := 1 to 10 do',
                '    s := ((s * 3 + i) xor (s shr 2)) and $FFFFFFFF;',
                '  if s mod 7 = 0 then', '    s := s + Length(IntToStr(s));', f'  Result := s + {k};', 'end;', '']
    out += ['var', '  t: Integer;', '', 'begin', f'  t := {nonce};']
    out += [f'  t := t + F{k}({k + 1});' for k in range(count(functions))]
    return '\n'.join(out + ['  WriteLn(t);', 'end.', ''])


def go_source(nonce, functions=None):
    # Explicit int64 gives the same width as paslang on both 64-bit targets.
    # Go's official strconv docs define Itoa(i) == FormatInt(int64(i),10).
    out = ['package main', '', 'import (', '\t"fmt"', '\t"strconv"', ')', '']
    for k in range(count(functions)):
        out += [f'func f{k}(x int64) int64 {{', '\ts := x', '\tfor i := int64(1); i <= 10; i++ {',
                '\t\ts = ((s*3 + i) ^ (s >> 2)) & 0xFFFFFFFF', '\t}', '\tif s%7 == 0 {',
                '\t\ts += int64(len(strconv.FormatInt(s, 10)))', '\t}', f'\treturn s + {k}', '}', '']
    out += ['func main() {', f'\tt := int64({nonce})']
    out += [f'\tt += f{k}({k + 1})' for k in range(count(functions))]
    return '\n'.join(out + ['\tfmt.Println(t)', '}', ''])


def rust_source(nonce, functions=None):
    out = []
    for k in range(count(functions)):
        out += [f'fn f{k}(x: i64) -> i64 {{', '    let mut s = x;', '    for i in 1..=10i64 {',
                '        s = ((s * 3 + i) ^ (s >> 2)) & 0xffff_ffff;', '    }', '    if s % 7 == 0 {',
                '        s += s.to_string().len() as i64;', '    }', f'    s + {k}', '}', '']
    out += ['fn main() {', f'    let mut t: i64 = {nonce};']
    out += [f'    t += f{k}({k + 1});' for k in range(count(functions))]
    return '\n'.join(out + ['    println!("{}", t);', '}', ''])


def expected_total(functions):
    """Integer/digit-count oracle; no compiler or generated binary supplies it."""
    total = 0
    for k in range(functions):
        value = k + 1
        for step in range(1, 11):
            value = ((value * 3 + step) ^ (value >> 2)) & 0xffffffff
        if value % 7 == 0:
            value += len(str(value))
        total += value + k
    return total


def write_record(path, record):
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name + '.', delete=False) as output:
            temporary = Path(output.name)
            json.dump(record, output, indent=1, ensure_ascii=True, allow_nan=False)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def requested_json(arguments):
    path = None
    for i, argument in enumerate(arguments):
        if argument.startswith('--json=') and argument[7:]:
            path = Path(argument[7:])
        elif argument == '--json' and i + 1 < len(arguments) and arguments[i + 1] and not arguments[i + 1].startswith('-'):
            path = Path(arguments[i + 1])
    return path


class RecordingParser(argparse.ArgumentParser):
    def __init__(self, record, publish, **kwargs):
        super().__init__(**kwargs)
        self.record, self.publish = record, publish

    def error(self, message):
        self.record.update(ok=False, phase='refused', error=message)
        self.publish()
        super().error(message)


def stop_child(child):
    # The child has a private session; terminal SIGINT reaches the parent,
    # not necessarily it. subprocess.communicate only waits briefly on
    # KeyboardInterrupt (Python subprocess.py), so cleanup is ours.
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
    try:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            return child.communicate()
        finally:
            child.wait()
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def command(arguments, cwd, env=None, timeout=600, *, result=None, publish=None):
    started, child = None, None
    row = {} if result is None else result
    row.update(command=[str(item) for item in arguments], cwd=str(cwd), status='pending',
               stdout='', stderr='', wall_s=None,
               environment=environment_record(env))
    try:
        if publish:
            publish()
        # Persist the pending command before starting the measurement. JSON
        # serialization/fsync belongs to evidence collection, not compiler time.
        started = time.perf_counter()
        child = subprocess.Popen(row['command'], cwd=cwd, env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, start_new_session=True)
        row['status'] = 'running'
        try:
            stdout, stderr = child.communicate(timeout=timeout)
            status = child.returncode
        except subprocess.TimeoutExpired:
            stdout, stderr = stop_child(child)
            status = 'timeout'
        row.update(status=status, stdout=stdout.decode('utf-8', 'surrogateescape'),
                   stderr=stderr.decode('utf-8', 'surrogateescape'), wall_s=time.perf_counter() - started)
        if publish:
            publish()
        return row
    except BaseException as error:
        # This covers KeyboardInterrupt, SystemExit and exceptions from the
        # parent/publisher as well as timeouts. Never abandon its process group.
        if child is not None:
            stdout, stderr = stop_child(child)
            row.update(stdout=stdout.decode('utf-8', 'surrogateescape'), stderr=stderr.decode('utf-8', 'surrogateescape'))
        row.update(status='error' if isinstance(error, OSError) else 'interrupted',
                   exception=type(error).__name__ + ': ' + str(error),
                   wall_s=time.perf_counter() - started if started is not None else None)
        if publish:
            publish()
        if isinstance(error, OSError):
            row['stderr'] = row['stderr'] or str(error)
            return row
        raise


def environment_record(environment):
    values = os.environ if environment is None else environment
    return {key: value for key, value in values.items() if key in ENV_KEYS}


def compiler_environment(language, cpu, native_level, legacy=False, capabilities=None):
    """Target flags select output; installed compiler hosts stay unmasked."""
    if language == 'rust':
        return rust_runtime_environment('native')
    if language != 'go':
        return cpu_environment(language, cpu, native_level, legacy, capabilities)
    if legacy:
        return go_runtime_environment('native', None, cpu_environment(language,cpu,native_level,legacy,capabilities))
    env = go_build_environment(OUT / cpu, cpu, native_level)
    env['GOWORK'] = 'off'
    # Preserve the target GOAMD64 from go_build_environment. Passing no
    # native level strips inherited cpu.* overrides without changing it.
    return go_runtime_environment('native', None, env)


def cpu_environment(language, cpu, native_level, legacy=False, capabilities=None):
    env = dict(os.environ)
    if language == 'rust':
        return rust_runtime_environment(cpu, env)
    if language != 'go':
        return env
    if legacy:
        env['GOCACHE'] = str(ROOT / 'build/bench/gocache')
        env['GOFLAGS'] = '-mod=mod'
        return env
    env = go_build_environment(OUT / cpu, cpu, native_level)
    env['GOWORK'] = 'off'
    return go_runtime_environment(cpu, native_level, env, capabilities)


def invocation(language, tool, source, executable, cpu, legacy, configuration=None):
    if language == 'paslang':
        return [tool, *([] if legacy else ['-cpu', cpu]), '-o', executable, source]
    if language == 'go':
        return [tool, 'build', '-o', executable, '.'] if legacy else [tool, 'build', '-o', executable, source]
    if configuration is None:
        raise ValueError('Rust compilation requires an explicit resolved provider configuration')
    return [tool, '--edition=2024', *rust_build_args(configuration, cpu), '-o', executable, source]


def pending_observation():
    return {'build': None, 'source_sha256': None, 'executable_bytes': None, 'executable_sha256': None,
            'execution': None, 'linkage': None, 'paslang_inputs': None,
            'build_environment': None, 'runtime_environment': None,
            'rust_artifact': None, 'go_artifact': None, 'capability_evidence': None,
            'ok': False, 'phase': 'pending'}


def observation(language, tool, source, executable, cpu, legacy, env, expected, timeout, *, result=None, publish=None, configuration=None, capability_proof=None, execution_env=None, go_capabilities=None):
    execution_env = env if execution_env is None else execution_env
    result = pending_observation() if result is None else result
    def update():
        if publish:
            publish()
    result.update(ok=False, language=language, cpu=cpu, phase='building',
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), build={}, execution=None,
                  linkage=None, executable_bytes=None, executable_sha256=None, rust_artifact=None, go_artifact=None,
                  capability_evidence=None, paslang_inputs=None,
                  build_environment=environment_record(env),
                  runtime_environment=environment_record(execution_env))
    update()
    executable.unlink(missing_ok=True)  # Never execute a previous round's artifact.
    # Keep Pascal's established tree-root cwd so the candidate compiler finds
    # the already-built core under ROOT/build. No cold unit rebuild is added.
    build_cwd = ROOT if language == 'paslang' else source.parent
    built = command(invocation(language, tool, source, executable, cpu, legacy, configuration), build_cwd, env, timeout,
                    result=result['build'], publish=update)
    result['build'] = built
    update()  # The completed build is durable before execution can interrupt.
    if built['status'] != 0 or built['stderr'] != '' or not executable.is_file():
        result.update(phase='complete', error='build failed or emitted unexpected stderr' if built['status'] != 0 or built['stderr'] else 'compiler produced no executable')
        update()
        return result
    result.update(executable_bytes=executable.stat().st_size,
                  executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest())
    if language == 'paslang':
        # Provenance collection is outside the timed compiler/linker interval.
        # Resolve the actual .pi and selected base/v3 .o bytes from .link using
        # the same cwd and environment as the command which produced it.
        result['phase'] = 'unit-inputs'
        update()
        result['paslang_inputs'] = paslang_inputs(built['command'], executable, env, cwd=build_cwd)
        update()
    if language == 'rust':
        result['phase'] = 'capability'
        update()
        result['rust_artifact'] = rust_binary_metadata(configuration, executable)
        update()
        result['capability_evidence'] = require_rust_capabilities(
            configuration, cpu, result['rust_artifact'], proof=capability_proof,
            runtime_environment=execution_env)
    if language == 'go' and not legacy:
        result['phase'] = 'capability'
        update()
        validate_go_capabilities(go_capabilities)
        result['go_artifact'] = go_binary_metadata(executable)
        update()
        provider = require_go_artifact_capabilities(cpu,result['go_artifact'])
        result['capability_evidence'] = {'configuration_sha256':go_capabilities['identity_sha256'],
            'cpu':cpu,'executable_sha256':result['executable_sha256'],'provider':provider,
            'runtime_environment':environment_record(execution_env)}
    result.update(phase='executing', execution={})
    update()
    executed = command([executable], source.parent, execution_env, timeout, result=result['execution'], publish=update)
    result['execution'] = executed
    result['ok'] = executed['status'] == 0 and executed['stdout'] == expected and executed['stderr'] == ''
    if not result['ok']:
        result['error'] = 'generated nonce output/status/stderr differs from the independent oracle'
    result['phase'] = 'linkage'
    update()  # Execution evidence survives a later linkage/publisher exception.
    if shutil.which('ldd'):
        result['linkage'] = {}
        command(['ldd', executable], source.parent, env=execution_env if language == 'rust' else None,
                timeout=timeout, result=result['linkage'], publish=update)
    result['phase'] = 'complete'
    update()
    return result


def quantiles(values):
    if not values or not all(isinstance(item, (int, float)) and math.isfinite(item) for item in values):
        return None, None, None
    quartiles = statistics.quantiles(values, n=4) if len(values) > 1 else [values[0]] * 3
    return statistics.median(values), quartiles[0], quartiles[2]


def summary(rows, cpu, reference, requested):
    def observed(row, side, field):
        observation = row[side]
        build = observation.get('build') or {}
        return build.get('wall_s') if field == 'time' and build.get('status') == 0 else observation.get('executable_bytes') if field == 'bytes' else None
    pl = [observed(row, 'paslang', 'time') for row in rows]
    ref = [observed(row, 'reference', 'time') for row in rows]
    ratios = [p / r if p is not None and r is not None and r > 0 else None for p, r in zip(pl, ref)]
    median, q1, q3 = quantiles(ratios)
    completed = sum(bool(row.get('complete')) for row in rows)
    same = len(rows) == completed == requested and all(row['paslang']['ok'] and row['reference']['ok'] for row in rows)
    over = []
    if median is None or median > BUDGET:
        over.append('OVER BUDGET' if median is not None else 'INCOMPLETE BUILD TIMES')
    if q3 is None or q3 >= 1:
        over.append('NOT FASTER')
    if not same:
        over.append('OUTPUT/STATUS FAILURE')
    return {'cpu': cpu, 'reference': reference, 'requested_rounds': requested, 'completed_rounds': completed,
            'attempted_rounds': len(rows), 'paslang_s': pl, 'reference_s': ref, 'ratios': ratios,
            'ratio_median': median, 'q1': q1, 'q3': q3, 'requires_q3_below_one': True,
            'budget': BUDGET, 'same_output': same, 'ok': not over, 'over': '; '.join(over),
            'paslang_bytes': [observed(row, 'paslang', 'bytes') for row in rows],
            'reference_bytes': [observed(row, 'reference', 'bytes') for row in rows], 'rounds': rows}


def main(arguments=None):
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    report_file = requested_json(arguments)
    record = {'format': FORMAT, 'ok': False, 'phase': 'arguments', 'pairs': [], 'warmups': [], 'tools': {}}
    def publish():
        write_record(report_file, record)
    publish()  # Invalidate an older good record even if argument parsing fails.
    finished = False
    parser = RecordingParser(record, publish, description=__doc__, allow_abbrev=False)
    try:
        parser.add_argument('-n', type=int, default=8)
        parser.add_argument('--json')
        parser.add_argument('--reference', help='explicit references: go, rust or go,rust; omitted retains legacy Go policy')
        parser.add_argument('--cpu', help='native, base or native,base for the explicit comparison mode')
        parser.add_argument('--go-native-level', choices=('v1', 'v2', 'v3', 'v4'))
        parser.add_argument('--rust-target', help='explicit Rust target; defaults to compiler host')
        parser.add_argument('--rust-sysroot', help='matching Rust compiler/standard-library sysroot')
        parser.add_argument('--rust-provider', choices=('gnu', 'musl'))
        parser.add_argument('--rust-capability-proof', help='retained base-ISA/provider certificate for this Rust configuration')
        parser.add_argument('--functions', type=int, default=N)
        parser.add_argument('--timeout', type=float, default=600)
        options = parser.parse_args(arguments)
        legacy = options.reference is None and options.cpu is None and options.go_native_level is None
        references = list(dict.fromkeys(part.strip() for part in (options.reference if options.reference is not None else 'go').split(',')))
        cpus = ['native'] if legacy else list(dict.fromkeys(part.strip() for part in (options.cpu if options.cpu is not None else 'native,base').split(',')))
        if not references or set(references) - {'go', 'rust'}:
            parser.error('--reference accepts go and rust only')
        if 'rust' not in references and any((options.rust_target, options.rust_sysroot,
                                            options.rust_provider, options.rust_capability_proof)):
            parser.error('Rust configuration options require --reference rust or go,rust')
        if not cpus or set(cpus) - {'native', 'base'}:
            parser.error('--cpu accepts native and base only')
        if options.n < 1 or options.functions < 1 or not math.isfinite(options.timeout) or options.timeout <= 0:
            parser.error('rounds, functions and timeout must be positive')
        if not legacy and platform.machine().lower() not in ('x86_64', 'amd64'):
            parser.error('explicit base/native compiler timings currently require amd64 hardware')
        if not legacy and 'go' in references and 'native' in cpus and options.go_native_level is None:
            parser.error('native Go requires an explicitly reviewed --go-native-level')
        tools = {}
        for language in ['paslang', *references]:
            tool = {'paslang': 'paslangc', 'go': 'go', 'rust': 'rustc'}[language]
            tools[language] = shutil.which(tool)
            if tools[language] is None:
                parser.error('explicitly requested compiler/tool is unavailable on PATH: ' + tool)
        OUT.mkdir(parents=True, exist_ok=True)
        constant = expected_total(options.functions)
        base = random.SystemRandom().randrange(1 << 40) * 1000
        if base + len(cpus) * len(references) * options.n + constant >= (1 << 63):
            parser.error('generated nonce and checksum must fit the common signed 64-bit width')
        record.update({'format': FORMAT, 'functions': options.functions, 'rounds': options.n,
                  'references': references, 'cpus': cpus, 'legacy_cpu_policy': legacy, 'budget': BUDGET,
                  'machine': {'system': platform.platform(), 'host': platform.node(), 'architecture': platform.machine()},
                  'method': 'separate alternating compiler/linker series for each reference; every nonce checked; default linked executable file sizes',
                  'cache_policy': {'legacy': 'Go-only warmup retained' if legacy else 'each compiler warmed once per reference/CPU series',
                                   'go': 'installed standard library warmed in recorded GOCACHE; fresh random main constant every measured round',
                                   'rust': 'installed precompiled standard library; direct rustc, no Cargo/incremental cache requested',
                                   'paslang': 'installed compiler/core interfaces; generated source recompiled every round',
                                   'os': 'OS filesystem/page caches are not flushed; no cold-cache claim'},
                  'contracts': ['No stripped binary-size or equal runtime-library ISA guarantee is inferred from default-linked file sizes.',
                                'Rust target-cpu selects this generated crate; installed std/libc remain their selected provider libraries.',
                                'Modern Go compiler/linker hosts use ordinary CPU detection; GOAMD64 selects only the generated target.',
                                'The reviewed Go base runtime mask applies only when executing the generated program; build and runtime environments are recorded separately.',
                                'Rust base programs require configuration/provider certification plus freshly checked artifact evidence before execution.',
                                'Each reference has its own paslang timings and nonces; no cross-reference paslang average.',
                                'All function arithmetic is signed 64-bit and nonnegative before shifts, masked to 32 bits after each loop step.'],
                  'go_policy': None if legacy else go_policy_description(),
                  'tools': {}, 'warmups': [], 'pairs': [], 'ok': False, 'requested_comparisons': len(cpus) * len(references), 'completed_comparisons': 0, 'phase': 'metadata', 'requires_q3_below_one': True})
        for language, flags in (('paslang', ['-v']), ('go', ['version']), ('rust', ['-Vv'])):
            if language not in tools:
                continue
            info = record['tools'][language] = {}
            metadata_env = (compiler_environment(language, cpus[0], options.go_native_level, legacy)
                            if language in ('rust','go') else None)
            command([tools[language], *flags], ROOT, env=metadata_env, timeout=options.timeout, result=info, publish=publish)
            if info['status'] != 0 or info['stderr'] != '' or not info['stdout']:
                raise RuntimeError('compiler version capture failed: ' + language)
            info['executable_sha256'] = hashlib.sha256(Path(tools[language]).read_bytes()).hexdigest()
            if language == 'go' and not legacy:
                validate_go_version(info['stdout'])
        for tool in ('as', 'ld', 'ldd'):
            if shutil.which(tool):
                record['tools'][tool] = {}
                command([tool, '--version'], ROOT, timeout=options.timeout, result=record['tools'][tool], publish=publish)
        go_capabilities = None
        if 'go' in tools and not legacy:
            record['phase'] = 'go-capabilities'
            publish()
            go_capabilities = prepare_go_capabilities(tools['go'],OUT / 'go-capabilities')
            record['go_capabilities'] = go_capabilities
            # Fail an unsupported baseline before compiler warmups/timing.
            if 'base' in cpus:
                go_runtime_environment('base',capabilities=go_capabilities)
            validate_go_capabilities(go_capabilities,tools['go'])
        configuration = None
        capability_proof = Path(options.rust_capability_proof).resolve() if options.rust_capability_proof else None
        if 'rust' in tools:
            configuration = rust_configuration(tools['rust'], target=options.rust_target,
                                               sysroot=options.rust_sysroot, provider=options.rust_provider)
            record['rust_configuration'] = configuration
            record['rust_capability_proof'] = str(capability_proof) if capability_proof else None
            record['rust_sysroot'] = {}
            command([tools['rust'], '--sysroot', configuration['sysroot'], '--print', 'sysroot'], ROOT, env=cpu_environment('rust', 'native', None), timeout=options.timeout, result=record['rust_sysroot'], publish=publish)
            if record['rust_sysroot']['status'] != 0 or not record['rust_sysroot']['stdout']:
                raise RuntimeError('Rust standard-library sysroot capture failed')
        generators = {'paslang': paslang_source, 'go': go_source, 'rust': rust_source}
        series = 0
        for cpu in cpus:
            for reference in references:
                series += 1
                folder = OUT if legacy else OUT / cpu / reference
                locations = {}
                for language in ('paslang', reference):
                    tag = 'pl' if language == 'paslang' else language
                    directory = folder / tag
                    directory.mkdir(parents=True, exist_ok=True)
                    source = directory / {'paslang': 'gen.paslang', 'go': 'main.go', 'rust': 'gen.rs'}[language]
                    locations[language] = (source, directory / 'gen')
                    if language == 'go' and legacy and not (directory / 'go.mod').exists():
                        (directory / 'go.mod').write_text('module gen\n')
                if reference == 'go':
                    env = compiler_environment('go', cpu, options.go_native_level, legacy, go_capabilities)
                    record.setdefault('go_runtime_environment', {})[cpu] = environment_record(
                        cpu_environment('go', cpu, options.go_native_level, legacy, go_capabilities))
                    info = command([tools['go'], 'env', '-json', 'GOOS', 'GOARCH', 'GOAMD64', 'GOROOT',
                                    'GOVERSION', 'GOEXPERIMENT', 'CGO_ENABLED', 'GOFLAGS', 'GOTOOLCHAIN'],
                                   locations['go'][0].parent, env, options.timeout)
                    record.setdefault('go_environment', {})[cpu] = info
                    if info['status'] != 0 or info['stderr'] != '' or not info['stdout']:
                        raise RuntimeError('effective Go build environment capture failed')
                if reference == 'rust':
                    flags = rust_build_args(configuration, cpu)
                    info = command([tools['rust'], '--print', 'cfg', *flags], ROOT, env=compiler_environment('rust', cpu, options.go_native_level), timeout=options.timeout)
                    record.setdefault('rust_cfg', {})[cpu] = info
                    if info['status'] != 0 or not info['stdout']:
                        raise RuntimeError('effective Rust target configuration capture failed')
                warm_languages = (reference,) if legacy else ('paslang', reference)
                for language in warm_languages:
                    source, executable = locations[language]
                    source.write_text(generators[language](0, options.functions))
                    env = compiler_environment(language, cpu, options.go_native_level, legacy, go_capabilities)
                    execution_env = cpu_environment(language, cpu, options.go_native_level, legacy, go_capabilities)
                    row = pending_observation()
                    row.update(cpu=cpu, reference_series=reference, language=language, nonce=0, expected_stdout=str(constant) + '\n')
                    record['warmups'].append(row)
                    publish()
                    observation(language, tools[language], source, executable, cpu, legacy, env, str(constant) + '\n', options.timeout, result=row, publish=publish, configuration=configuration,
                                capability_proof=capability_proof, execution_env=execution_env, go_capabilities=go_capabilities)
                    if not row['ok']:
                        raise RuntimeError('compiler warmup build/output failed: ' + language)
                rows = []
                pair = summary(rows, cpu, reference, options.n)
                if reference == 'rust':
                    pair.update(reference_target=configuration['target'], reference_provider=configuration['provider'],
                                configuration_sha256=configuration['identity_sha256'])
                record['pairs'].append(pair)
                def progress():
                    pair.update(summary(rows, cpu, reference, options.n))
                    record['completed_comparisons'] = sum(item['completed_rounds'] == options.n for item in record['pairs'])
                    publish()
                progress()
                for index in range(options.n):
                    nonce = base + (series - 1) * options.n + index
                    expected = str(nonce + constant) + '\n'
                    values = {'round': index + 1, 'nonce': nonce, 'expected_stdout': expected,
                              'first': 'paslang' if index % 2 == 0 else reference,
                              'paslang': pending_observation(), 'reference': pending_observation(), 'complete': False}
                    rows.append(values)
                    progress()
                    for language in ('paslang', reference):
                        source, _ = locations[language]
                        source.write_text(generators[language](nonce, options.functions))
                    order = ('paslang', reference) if index % 2 == 0 else (reference, 'paslang')
                    for language in order:
                        source, executable = locations[language]
                        env = compiler_environment(language, cpu, options.go_native_level, legacy, go_capabilities)
                        execution_env = cpu_environment(language, cpu, options.go_native_level, legacy, go_capabilities)
                        observation(language, tools[language], source, executable, cpu, legacy, env, expected, options.timeout,
                                    result=values['paslang' if language == 'paslang' else 'reference'], publish=progress,
                                    configuration=configuration, capability_proof=capability_proof, execution_env=execution_env, go_capabilities=go_capabilities)
                    values['complete'] = True
                    progress()
                print('compile %d functions %s/%s: paslangc %s s, reference %s s, ratio %s, budget %.2f, every output %s, %s' %
                      (options.functions, cpu, reference, statistics.median(pair['paslang_s']) if all(value is not None for value in pair['paslang_s']) else '-',
                       statistics.median(pair['reference_s']) if all(value is not None for value in pair['reference_s']) else '-', pair['ratio_median'], BUDGET,
                       'yes' if pair['same_output'] else 'NO', 'PASS' if pair['ok'] else pair['over']), flush=True)
        record['requested_comparisons'] = len(cpus) * len(references)
        record['completed_comparisons'] = len(record['pairs'])
        record['ok'] = len(record['pairs']) == record['requested_comparisons'] and all(pair['ok'] for pair in record['pairs'])
        record['phase'] = 'complete'
        finished = True
    except SystemExit as error:
        record['ok'] = False
        record.setdefault('error', 'argument processing ended with status ' + str(error.code))
        raise
    except KeyboardInterrupt:
        record.update(ok=False, phase='interrupted', error='KeyboardInterrupt')
        return 130
    except BaseException as error:
        record.update(ok=False, phase='failed', error=type(error).__name__ + ': ' + str(error))
        if not isinstance(error, Exception):
            raise
    finally:
        if not finished:
            record['ok'] = False
        if record.get('legacy_cpu_policy') and record['pairs']:
            pair = record['pairs'][0]
            for key in ('paslang_s', 'ratios', 'ratio_median', 'q1', 'q3', 'same_output', 'over'):
                record[key] = pair[key]
            record['go_s'] = pair['reference_s']
        publish()
    return 0 if record['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
