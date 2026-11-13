#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Deterministic P525 compiler-probe/report checks, using Python tool stubs.

No language compiler is invoked. The stubs interpret only the generated
integer-program subset; actual Go/Rust/Pascal syntax/linking remains a
separate real-compiler validation. Timings here are explicitly synthetic.
Run as python3 -I scripts/bench/check_build_report.py.
"""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import contextlib
import copy
import hashlib
import ctypes
import io
import json
import os
import re
import signal
import subprocess
import tempfile
import time
import types
from unittest.mock import patch
import build as probe
import report
from check_reference_policy import synthetic_capabilities


def require(value, message):
    if not value:
        raise AssertionError(message)


def evaluate_source(language, text):
    """Independent interpreter for the generated arithmetic/source subset."""
    if language == 'paslang':
        blocks = re.findall(r'function F(\d+)\(.*?\n(.*?)\nend;', text, re.S)
        nonce = int(re.search(r'  t := (-?\d+);', text)[1])
        calls = re.findall(r't := t \+ F(\d+)\((\d+)\)', text)
    elif language == 'go':
        blocks = re.findall(r'func f(\d+)\(.*?\n(.*?)\n}', text, re.S)
        nonce = int(re.search(r't := int64\((-?\d+)\)', text)[1])
        calls = re.findall(r't \+= f(\d+)\((\d+)\)', text)
    else:
        blocks = re.findall(r'fn f(\d+)\(.*?\n(.*?)\n}', text, re.S)
        nonce = int(re.search(r'let mut t: i64 = (-?\d+);', text)[1])
        calls = re.findall(r't \+= f(\d+)\((\d+)\)', text)
    functions = dict(blocks)
    require(len(functions) == len(calls) > 0, 'generated function/call counts differ')
    total = nonce
    for name, argument in calls:
        body = functions[name]
        recurrence = re.search(r's\s*(?::=|=)\s*\(\(s\s*\*\s*(\d+)\s*\+\s*i\)\s*(?:xor|\^)\s*\(s\s*(?:shr|>>)\s*(\d+)\)\)\s*(?:and|&)\s*(\$[\dA-Fa-f]+|0x[\da-fA-F_]+)', body)
        require(recurrence is not None, 'unexpected generated recurrence')
        factor, shift, mask = recurrence.groups()
        mask = int(mask.replace('$', '0x').replace('_', ''), 16)
        steps = int(re.search(r'(?:to|<=|\.\.=)\s*(\d+)', body)[1])
        modulus = int(re.search(r's\s*(?:mod|%)\s*(\d+)', body)[1])
        offset = re.search(r'(?:Result\s*:=|return)\s*s\s*\+\s*(\d+)', body) if language != 'rust' else re.search(r'\bs \+ (\d+)\s*$', body)
        require(offset is not None, 'unexpected generated result')
        value = int(argument)
        for step in range(1, steps + 1):
            old = value
            value = ((old * int(factor) + step) ^ (old // (2 ** int(shift)))) % (mask + 1)
        if value % modulus == 0:
            digits, remaining = 1, value
            while remaining >= 10:
                digits += 1
                remaining //= 10
            value += digits
        total += value + int(offset[1])
    return nonce, total


def _stub_tool_main():
    arguments = sys.argv[1:]
    language = {'paslangc': 'paslang', 'go': 'go', 'rustc': 'rust'}[Path(sys.argv[0]).name]
    if arguments in (['-v'], ['-Vv'], ['version']):
        print('go version go1.27.3-X:nodwarf5 linux/amd64' if language == 'go' else language + ' synthetic test tool')
        if language == 'go' and os.environ.get('P525_STUB_METADATA_STDERR') == 'version':
            print('GODEBUG: unknown cpu feature "sha"',file=sys.stderr)
        return
    if arguments[:1] == ['env']:
        print(json.dumps({'GOAMD64': os.environ.get('GOAMD64', 'v1')}))
        if os.environ.get('P525_STUB_METADATA_STDERR') == 'env':
            print('GODEBUG: unknown cpu feature "sha"',file=sys.stderr)
        return
    if '--print' in arguments and arguments[arguments.index('--print') + 1] == 'sysroot':
        print('/synthetic/sysroot'); return
    if arguments[:2] == ['--print', 'cfg']:
        print('target_arch="x86_64"'); return
    executable = Path(arguments[arguments.index('-o') + 1])
    source = next((Path(item) for item in arguments if item.endswith(('.paslang', '.go', '.rs'))), Path.cwd() / 'main.go')
    nonce, value = evaluate_source(language, source.read_text())
    events = Path(os.environ['P525_STUB_EVENTS'])
    previous = [json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []
    number = sum(row['language'] == language for row in previous) + 1
    event = {'language': language, 'nonce': nonce, 'arguments': arguments,
             'GOAMD64': os.environ.get('GOAMD64'), 'GODEBUG': os.environ.get('GODEBUG', '')}
    with events.open('a') as output:
        output.write(json.dumps(event) + '\n')
    wrong = language == os.environ.get('P525_STUB_WRONG_LANGUAGE') and number == int(os.environ.get('P525_STUB_WRONG_BUILD', '-1'))
    status = int(os.environ.get('P525_STUB_EXIT', '0')) if wrong else 0
    answer = value + int(wrong and os.environ.get('P525_STUB_WRONG_OUTPUT', '1') == '1')
    stderr_when = os.environ.get('P525_STUB_STDERR_WHEN') if wrong else None
    if stderr_when == 'build':
        print('GODEBUG sys/cpu: unknown cpu feature "rdtscp"',file=sys.stderr)
    runtime_error = 'GODEBUG sys/cpu: unknown cpu feature "rdtscp"' if stderr_when == 'execution' else ''
    runtime_event = {'language': language, 'nonce': nonce}
    executable.write_text('#!' + sys.executable + '\nimport sys,os,json\nfrom pathlib import Path\n'
        + 'event=' + repr(runtime_event) + '\n'
        + 'event.update(GOAMD64=os.environ.get("GOAMD64"),GODEBUG=os.environ.get("GODEBUG", ""))\n'
        + 'with Path(os.environ["P525_STUB_RUNTIME_EVENTS"]).open("a") as output: output.write(json.dumps(event)+"\\n")\n'
        + 'print(' + repr(answer) + ')\n' + ('print(' + repr(runtime_error) + ',file=sys.stderr)\n' if runtime_error else '') + 'sys.exit(' + str(status) + ')\n')
    executable.chmod(0o755)
    if language == 'paslang':
        # Controlled external-unit inputs; the generated program's own .o/.ld
        # are outputs and must not be included as library provenance.
        unit = Path(os.environ['PASLANG_LIB']) / 'sysutils.o'
        executable.with_suffix('.link').write_text('\n'.join([
            '-o', str(executable), '--gc-sections', '-T', str(executable.with_suffix('.ld')),
            str(executable.with_suffix('.o')), str(unit)]) + '\n')


def invoke(module, arguments):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            return module.main(arguments)
        except SystemExit as error:
            return error.code


@contextlib.contextmanager
def tools(folder, module=probe, *, rust=True, wrong=None, wrong_output=True, exit_status=7, stderr_when=None):
    directory = folder / 'tools'; directory.mkdir()
    core = folder / 'core'; core.mkdir()
    (core / 'sysutils.pi').write_bytes(b'controlled interface one\n')
    (core / 'sysutils.o').write_bytes(b'controlled unit object one\n')
    for name in ('paslangc', 'go', 'rustc'):
        path = directory / name
        path.write_text('#!' + sys.executable + '\nimport sys\nsys.dont_write_bytecode=True\nsys.path.insert(0,' + repr(str(Path(__file__).resolve().parent)) + ')\nfrom check_build_report import _stub_tool_main\n_stub_tool_main()\n')
        path.chmod(0o755)
    def which(name):
        if name in ('paslangc', 'go') or name == 'rustc' and rust:
            return str(directory / name)
        return None
    def rust_configuration(rustc, target=None, sysroot=None, provider=None):
        target = target or 'x86_64-unknown-linux-gnu'
        actual_provider = 'musl' if target.endswith('-musl') else 'gnu'
        if provider is not None and provider != actual_provider:
            raise ValueError('synthetic provider/target mismatch')
        return {'format': 'synthetic-configuration-fixture', 'rustc': str(rustc),
                'host': 'x86_64-unknown-linux-gnu', 'target': target, 'provider': actual_provider,
                'sysroot': sysroot or '/synthetic/sysroot', 'series': 'rust-' + target,
                'identity_sha256': 'configuration-fixture', 'standard_library': {'sha256': 'std-fixture'},
                'bundled_provider': None}
    def rust_binary_metadata(configuration, executable):
        digest = hashlib.sha256(Path(executable).read_bytes()).hexdigest()
        return {'format': 'synthetic-linked-program-fixture',
                'binary': {'sha256': digest, 'bytes': Path(executable).stat().st_size},
                'configuration_sha256': configuration['identity_sha256'],
                'provider_sha256': 'provider-fixture', 'identity_sha256': digest}
    def require_rust_capabilities(configuration, cpu, binary, proof=None, runtime_environment=None):
        # Only external identity/certificate discovery is synthetic. Production
        # rust_build_args/runtime policy, generated programs and observed exits
        # still run through their real source paths in this compiler-free test.
        require(binary['configuration_sha256'] == configuration['identity_sha256'], 'fixture artifact/configuration mismatch')
        return {'cpu': cpu, 'status': 'synthetic-certificate-fixture',
                'identity_sha256': binary['identity_sha256']}
    original = module.command
    def synthetic(arguments, *args, **kwargs):
        row = original(arguments, *args, **kwargs)
        if '-o' in list(map(str, arguments)) and row['status'] == 0:
            row['wall_s'] = 0.01 if Path(str(arguments[0])).name == 'paslangc' else 0.04
            if kwargs.get('publish'):
                kwargs['publish']()
        return row
    env = {'P525_STUB_EVENTS': str(folder / 'events'),
           'P525_STUB_RUNTIME_EVENTS': str(folder / 'runtime-events'), 'PASLANG_LIB': str(core)}
    if stderr_when:
        env['P525_STUB_STDERR_WHEN'] = stderr_when
    if wrong:
        env.update(P525_STUB_WRONG_LANGUAGE='go', P525_STUB_WRONG_BUILD=str(wrong), P525_STUB_EXIT=str(exit_status), P525_STUB_WRONG_OUTPUT='1' if wrong_output else '0')
    with patch.object(module, 'ROOT', folder), patch.object(module, 'OUT', folder / 'out'), \
         patch.object(module.shutil, 'which', which), patch.object(module.platform, 'machine', lambda: 'x86_64'), \
         patch.object(module, 'command', synthetic), \
         patch.object(module, 'prepare_go_capabilities', lambda *a,**k: synthetic_capabilities()), \
         patch.object(module, 'validate_go_capabilities', lambda proof,*a,**k: proof), \
         patch.object(module, 'go_binary_metadata', lambda path: synthetic_go_artifact(path)), \
         patch.object(module, 'rust_configuration', rust_configuration), \
         patch.object(module, 'rust_binary_metadata', rust_binary_metadata), \
         patch.object(module, 'require_rust_capabilities', require_rust_capabilities), patch.dict(os.environ, env):
        yield folder / 'result.json'


def synthetic_go_artifact(path,dynamic=False):
    import reference_policy as policy
    data=Path(path).read_bytes()
    metadata={'format':'paslang-go-linked-program-v1','binary':{'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()},
        'elf':{'class':64,'machine':62,'type':2},'needed':['libc.so.6'] if dynamic else [],
        'interpreter':'/lib/ld-linux.so.2' if dynamic else None,'has_dynamic_segment':dynamic}
    metadata['identity_sha256']=policy._digest(metadata)
    return metadata


def generator_checks():
    for language, generator in (('paslang', probe.paslang_source), ('go', probe.go_source), ('rust', probe.rust_source)):
        # N=1's ten hand-worked steps end at 112027, not a production-oracle value.
        require(evaluate_source(language, generator(17, 1)) == (17, 112044), language + ': independent N1 checksum')
        for nonce in (0, 19, 1234567890123):
            parsed, value = evaluate_source(language, generator(nonce, 5))
            require(parsed == nonce and value == nonce + probe.expected_total(5), language + ': generated nonce/arithmetic differs')


def probe_checks(folder, module=probe):
    folder.mkdir()
    with tools(folder, module, wrong=2) as result:
        code = invoke(module, ['-n', '3', '--functions', '2', '--json', str(result)])
        data = json.loads(result.read_text())
        require(code == 1 and not data['ok'] and not data['pairs'][0]['same_output'], 'early wrong nonce/status was overwritten')
        rows = data['pairs'][0]['rounds']
        require(len(rows) == 3 and rows[0]['reference']['execution']['status'] == 7 and rows[-1]['reference']['ok'], 'every round execution/status was not retained')
        require(all(row['expected_stdout'] == str(row['nonce'] + module.expected_total(2)) + '\n' for row in rows), 'nonce expectation missing')
        require(data['go_s'] == data['pairs'][0]['reference_s'], 'legacy Go fields changed')
        require({row['language'] for row in map(json.loads, (folder / 'events').read_text().splitlines())} == {'paslang', 'go'}, 'default invoked Rust')
    return data



def output_status_checks(folder):
    folder.mkdir()
    for name, wrong_output, status in (('output-only', True, 0), ('status-only', False, 7)):
        work = folder / name; work.mkdir()
        with tools(work, wrong=2, wrong_output=wrong_output, exit_status=status) as result:
            require(invoke(probe, ['-n', '3', '--functions', '2', '--json', str(result)]) == 1, name + ': failure accepted')
            data = json.loads(result.read_text())
            rows = data['pairs'][0]['rounds']
            first = rows[0]['reference']['execution']
            require(not data['ok'] and not data['pairs'][0]['same_output'] and rows[-1]['reference']['ok'], name + ': early failure lost')
            require(first['status'] == status and (first['stdout'] != rows[0]['expected_stdout']) == wrong_output, name + ': stub did not isolate its intended fault')


def diagnostic_checks(folder,module=probe):
    folder.mkdir()
    for phase in ('build','execution'):
        work=folder/phase;work.mkdir()
        with tools(work,module,wrong=2,wrong_output=False,exit_status=0,stderr_when=phase) as result:
            require(invoke(module,['-n','2','--functions','2','--json',str(result)])==1,phase+': unexpected compiler/generated stderr accepted')
            data=json.loads(result.read_text());first=data['pairs'][0]['rounds'][0]['reference']
            require(first[phase]['status']==0 and 'unknown cpu feature' in first[phase]['stderr'] and not first['ok'],phase+': raw successful-status diagnostic lost')


def go_provider_refusals(folder):
    folder.mkdir()
    for cpu in ('native','base'):
        work=folder/cpu;work.mkdir()
        with tools(work) as result,patch.object(probe,'go_binary_metadata',lambda path:synthetic_go_artifact(path,True)):
            code=invoke(probe,['-n','1','--functions','1','--reference','go','--cpu',cpu,'--go-native-level','v3','--json',str(result)])
            data=json.loads(result.read_text())
            if cpu=='native':require(code==0 and data['pairs'][0]['same_output'],'ordinary native dynamic provider refused')
            else:
                require(code==1 and 'provider ISA unproved' in data['error'] and not data['pairs'],'dynamic generated baseline reached measured rounds')
                go=data['warmups'][-1]
                require(go['go_artifact']['needed']==['libc.so.6'] and go['execution'] is None,'dynamic provider evidence lost or unsafe artifact executed')


def go_metadata_diagnostic_refusals(folder):
    folder.mkdir()
    for phase in ('version','env'):
        work=folder/phase;work.mkdir()
        with tools(work) as result,patch.dict(os.environ,{'P525_STUB_METADATA_STDERR':phase}):
            require(invoke(probe,['-n','1','--functions','1','--reference','go','--cpu','native','--go-native-level','v3','--json',str(result)])==1,'Go metadata warning accepted')
            data=json.loads(result.read_text())
            record=data['tools']['go'] if phase=='version' else data['go_environment']['native']
            require(record['status']==0 and 'unknown cpu feature' in record['stderr'] and not data['warmups'] and not (work/'events').exists(),'metadata warning lost or workload reached')


def go_capability_refusals(folder):
    folder.mkdir()
    for name,proof in [('missing',None),('fsrm',synthetic_capabilities(fsrm=True)),('vaes',synthetic_capabilities(active='HasVAES'))]:
        work=folder/name;work.mkdir()
        with tools(work) as result,patch.object(probe,'prepare_go_capabilities',lambda *a,**k:proof):
            require(invoke(probe,['-n','1','--functions','1','--reference','go','--cpu','base','--json',str(result)])==1,'unsafe Go metadata reached measurement')
            data=json.loads(result.read_text())
            require(not data['pairs'] and not data['warmups'] and not (work/'events').exists(),'unsafe Go baseline built/timed a program')


def environment_checks(folder):
    folder.mkdir()
    tunables = 'glibc.malloc.trim_threshold=131072'
    env = dict(os.environ, GLIBC_TUNABLES=tunables, P525_PRIVATE_UNRELATED='not recorded')
    row = probe.command([sys.executable, '-I', '-c', 'print("environment")'], folder, env, timeout=5)
    require(row['status'] == 0 and row['stdout'] == 'environment\n', 'environment capture probe failed')
    require(row['environment'].get('GLIBC_TUNABLES') == tunables and 'P525_PRIVATE_UNRELATED' not in row['environment'], 'runtime tunable allowlist capture differs')
    empty = probe.command([sys.executable, '-I', '-c', 'print("empty environment")'], folder, {}, timeout=5)
    require(empty['status'] == 0 and empty['environment'] == {}, 'empty actual environment was replaced in evidence')
    with patch.dict(os.environ, {'GODEBUG': 'cpu.all=off', 'GOAMD64': 'v4'}):
        legacy_host = probe.compiler_environment('go', 'native', None, True)
        legacy_runtime = probe.cpu_environment('go', 'native', None, True)
        require(legacy_host['GODEBUG'] == '' and legacy_runtime['GODEBUG'] == 'cpu.all=off' and legacy_host['GOAMD64'] == legacy_runtime['GOAMD64'] == 'v4',
                'legacy host CPU mask remained or other legacy targets changed')


def flags_and_refusals(folder, module=probe):
    folder.mkdir()
    with tools(folder, module) as result:
        with patch.dict(os.environ, {'GODEBUG': 'gctrace=1,cpu.all=off,cpu.erms=on,cpu.fsrm=off,cpu.aes=off'}):
            require(invoke(module, ['-n', '1', '--functions', '2', '--reference', 'go,rust', '--cpu', 'native,base', '--go-native-level', 'v3', '--json', str(result)]) == 0, 'synthetic modern probe failed')
        data = json.loads(result.read_text())
        require(len(data['pairs']) == 4 and data['ok'], 'reference/CPU series missing')
        events = list(map(json.loads, (folder / 'events').read_text().splitlines()))
        require({row['GOAMD64'] for row in events if row['language'] == 'go'} == {'v1', 'v3'}, 'Go base/native flags differ')
        require(any('target-cpu=x86-64' in row['arguments'] for row in events if row['language'] == 'rust') and any('target-cpu=native' in row['arguments'] for row in events if row['language'] == 'rust'), 'Rust flags missing')
        require(all('opt-level=3' in row['arguments'] and '--target' in row['arguments']
                    and '--sysroot' in row['arguments'] for row in events if row['language'] == 'rust'),
                'Rust optimization or explicit target/sysroot changed')
        require(data['go_policy']['rep_preferences'] and 'ERMS' in data['go_policy']['rep_preferences'], 'Go REP policy not retained')
        host_events = [row for row in events if row['language'] == 'go']
        require(host_events and all(row['GODEBUG'] == 'gctrace=1' for row in host_events),
                'Go compiler host was ISA-masked or inherited cpu overrides')
        runtime_events = list(map(json.loads, (folder / 'runtime-events').read_text().splitlines()))
        base_events = [row for row in runtime_events if row['language'] == 'go' and row['GOAMD64'] == 'v1']
        require(base_events and all(row['GODEBUG'] == 'gctrace=1,cpu.all=off' for row in base_events),
                'Go generated base runtime lost reviewed ISA mask or REP preferences')
        native_events = [row for row in runtime_events if row['language'] == 'go' and row['GOAMD64'] == 'v3']
        require(native_events and all(row['GODEBUG'] == 'gctrace=1' for row in native_events),
                'Go generated native runtime inherited a CPU override')
        observations = list(data['warmups']) + [row[side] for pair in data['pairs']
                        for row in pair['rounds'] for side in ('paslang', 'reference')]
        for observation in observations:
            require(observation['build_environment'] == observation['build']['environment'] and
                    observation['runtime_environment'] == observation['execution']['environment'],
                    'compiler/runtime environment evidence differs from actual commands')
            if observation['language'] == 'go':
                require(observation['build_environment']['GOAMD64'] == observation['runtime_environment']['GOAMD64'],
                        'host normalization changed the generated Go target level')
        for pair in data['pairs']:
            if pair['reference'] == 'rust':
                artifact = pair['rounds'][0]['reference']['rust_artifact']
                evidence = pair['rounds'][0]['reference']['capability_evidence']
                require(artifact['configuration_sha256'] == data['rust_configuration']['identity_sha256']
                        and evidence['identity_sha256'] == artifact['identity_sha256'], 'Rust per-nonce provider evidence missing')
        for args in (['-n', 'bad'], ['--unknown'], ['--reference', 'bad'], ['--cpu', 'bad'], ['--functions', '-1'], ['--reference', 'go', '--cpu', 'native']):
            result.write_text('{"ok":true}\n')
            require(invoke(module, [*args, '--json', str(result)]) == 2 and json.loads(result.read_text())['ok'] is False, 'refusal left old good JSON')
    missing = folder / 'missing'; missing.mkdir()
    with tools(missing, module, rust=False) as result:
        result.write_text('{"ok":true}\n')
        require(invoke(module, ['--reference', 'rust', '--cpu', 'base', '--json=' + str(result)]) == 2 and not json.loads(result.read_text())['ok'], 'missing Rust left stale success')
        require(not (missing / 'events').exists(), 'missing requested compiler began builds')
    unproved = folder / 'unproved'; unproved.mkdir()
    with tools(unproved, module) as result:
        # The production gate must fail closed for a real missing base proof;
        # the synthetic accepted certificates above never replace this check.
        from reference_caps import require_rust_capabilities
        with patch.object(module, 'require_rust_capabilities', require_rust_capabilities):
            code = invoke(module, ['-n', '1', '--functions', '2', '--reference', 'rust', '--cpu', 'base', '--json', str(result)])
        data = json.loads(result.read_text())
        require(code == 1 and not data['ok'] and data.get('error') and not data['pairs'],
                'missing Rust base proof was accepted')



def provenance_checks(folder, module=probe):
    folder.mkdir()
    with tools(folder, module) as result:
        arguments = ['-n', '1', '--functions', '2', '--reference', 'go', '--cpu', 'base', '--json', str(result)]
        require(invoke(module, arguments) == 0, 'controlled provenance probe failed')
        first = json.loads(result.read_text())['pairs'][0]['rounds'][0]['paslang']
        require(isinstance(first.get('paslang_inputs'), dict) and first['paslang_inputs'].get('units'), 'resolved unit provenance is absent')
        unit = first['paslang_inputs']['units'][0]
        core = folder / 'core'
        require(first['build']['cwd'] == str(folder), 'Pascal build lost established tree-root cwd')
        require(len(first['paslang_inputs']['units']) == 1 and unit['name'] == 'sysutils', 'generated outputs were included as unit inputs')
        require(unit['interface']['path'] == str(core / 'sysutils.pi') and
                unit['interface']['sha256'] == hashlib.sha256(b'controlled interface one\n').hexdigest() and
                unit['object']['path'] == str(core / 'sysutils.o') and
                unit['object']['sha256'] == hashlib.sha256(b'controlled unit object one\n').hexdigest(),
                'resolved interface/object contents missing or incorrect')
        (core / 'sysutils.pi').write_bytes(b'controlled interface two\n')
        (core / 'sysutils.o').write_bytes(b'controlled unit object two\n')
        require(invoke(module, arguments) == 0, 'changed controlled provenance probe failed')
        second = json.loads(result.read_text())['pairs'][0]['rounds'][0]['paslang']['paslang_inputs']['units'][0]
        require(second['interface']['sha256'] != unit['interface']['sha256'] and
                second['object']['sha256'] != unit['object']['sha256'], 'changed library bytes were hidden behind unchanged source/compiler')
        (core / 'sysutils.pi').unlink()
        require(invoke(module, arguments) == 1 and not json.loads(result.read_text())['ok'], 'missing resolved unit provenance was accepted')


def interrupted_evidence(folder):
    folder.mkdir()
    with tools(folder) as result:
        original = probe.command
        def interrupt(arguments, *args, **kwargs):
            if Path(str(arguments[0])).name == 'gen' and Path(str(arguments[0])).parent.name == 'go' and result.exists() and json.loads(result.read_text()).get('pairs'):
                raise KeyboardInterrupt()
            return original(arguments, *args, **kwargs)
        with patch.object(probe, 'command', interrupt):
            require(invoke(probe, ['-n', '2', '--functions', '2', '--json', str(result)]) == 130, 'interrupt exit not preserved')
        data = json.loads(result.read_text())
        row = data['pairs'][0]['rounds'][0]
        require(not data['ok'] and data['phase'] == 'interrupted' and data['pairs'][0]['completed_rounds'] == 0, 'interrupted record became complete')
        require(row['paslang']['execution']['status'] == 0 and row['reference']['build']['status'] == 0 and row['reference']['executable_bytes'] > 0, 'completed build/execution evidence lost before interruption')


@contextlib.contextmanager
def subreaper():
    # Read Linux man-pages6.20 PR_{SET,GET}_CHILD_SUBREAPER and wait(2).
    # Orphans are adopted by this observer; the attribute is not inherited
    # by forked children. This is test-only and the prior setting is restored.
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.restype = ctypes.c_int
    saved = ctypes.c_int()
    zero = ctypes.c_ulong(0)
    require(libc.prctl(ctypes.c_int(37), ctypes.byref(saved), zero, zero, zero) == 0,
            'cannot read observer subreaper setting')
    require(libc.prctl(ctypes.c_int(36), ctypes.c_ulong(1), zero, zero, zero) == 0,
            'cannot enable observer subreaper')
    try:
        yield
    finally:
        require(libc.prctl(ctypes.c_int(36), ctypes.c_ulong(saved.value), zero, zero, zero) == 0,
                'cannot restore observer subreaper setting')


def cleanup_checks(folder):
    folder.mkdir()
    script = folder / 'tree.py'
    script.write_text('import subprocess,sys,time,os\nfrom pathlib import Path\np=subprocess.Popen([sys.executable,"-c","import time;time.sleep(20)"])\nPath(sys.argv[1]).write_text(str(os.getpid())+" "+str(p.pid))\nprint("began",flush=True)\ntime.sleep(20)\n')
    real = subprocess.Popen.communicate
    with subreaper():
        for exception in (KeyboardInterrupt, RuntimeError):
            pidfile = folder / exception.__name__; seen = []
            def interrupt(child, *args, **kwargs):
                if not seen:
                    seen.append(child)
                    until = time.monotonic() + 5
                    while not pidfile.exists() and time.monotonic() < until:
                        time.sleep(0.01)
                    raise exception('synthetic parent exception')
                return real(child, *args, **kwargs)
            try:
                with patch.object(subprocess.Popen, 'communicate', interrupt):
                    try:
                        probe.command([sys.executable, script, pidfile], folder, timeout=5)
                    except exception:
                        pass
                    else:
                        require(False, 'parent exception was swallowed')
                require(pidfile.exists() and seen[0].returncode is not None, 'owned child was not reaped')
                parent, descendant = map(int, pidfile.read_text().split())
                require(not Path('/proc', str(parent)).exists(), 'owned child remains after reap')
                until = time.monotonic() + 2
                while True:
                    got, status = os.waitpid(descendant, os.WNOHANG)
                    if got:
                        require(os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGKILL,
                                'group descendant did not terminate by SIGKILL')
                        break
                    require(time.monotonic() < until, 'process-group descendant still running')
                    time.sleep(0.002)
                require(not Path('/proc', str(descendant)).exists(), 'adopted grandchild remains after reap')
            finally:
                for child in seen:
                    probe.stop_child(child)
                    # Even a failing cleanup oracle must drain its private
                    # group's adopted children before restoring subreaper.
                    while True:
                        try:
                            os.waitpid(-child.pid, 0)
                        except ChildProcessError:
                            break


def sample():
    side = {'status': 0, 'stdout': 'one\ntwo\n', 'stderr': '', 'wall_s': 1.0}
    return {'pair': 'case|<x>', 'cpu': 'base', 'reference': 'rust', 'reference_s': 2.0, 'paslang_s': 1.0,
            'ratio_time': 0.5, 'ratio_memory': 0.5, 'time_budget': 0.99, 'memory_budget': 0.99,
            'same_output': True, 'ok': True, 'requested_rounds': 1, 'completed_rounds': 1,
            'rounds': [{'a': dict(side), 'b': dict(side), 'errors': []}],
            'reference_memory': [{'ok': True, 'status': 0, 'peak_kib': 200, 'stdout': 'one\ntwo\n', 'stderr': ''}],
            'paslang_memory': [{'ok': True, 'status': 0, 'peak_kib': 100, 'stdout': 'one\ntwo\n', 'stderr': ''}]}


def rendered(module, row, memory_runs=1):
    out = []
    module.results(out.append, {'format': 'paslang-bench-refs-v1', 'ok': True, 'pairs': [row], 'requested_comparisons': 1, 'completed_comparisons': 1, 'memory_runs': memory_runs})
    return out, next(line for line in out if line.startswith('| case'))


def report_checks(module=report):
    _, line = rendered(module, sample())
    require(line.endswith('| PASS |'), 'valid reference row rejected')
    for changes in ({'ratio_time': 1.01}, {'ratio_memory': 1.01}, {'completed_rounds': 0}, {'reference_s': None}, {'ratio_time': None}, {'requires_q3_below_one': True, 'q3': 1.0}, {'requested_memory_runs': 3}, {'rounds': None}, {'rounds': [None]}, {'reference_memory': None}, {'reference_memory': [None]}):
        row = sample(); row.update(changes)
        require(rendered(module, row)[1].endswith('| FAIL |'), 'independent budget/count/null failure was trusted as ok')
    require(rendered(module, sample(), 3)[1].endswith('| FAIL |'), 'truncated memory sample count accepted')
    for flag in ('complete', 'completed'):
        row = sample(); row['rounds'][0][flag] = False
        require(rendered(module, row)[1].endswith('| FAIL |'), 'forged completed count hid an incomplete round')
        row = sample(); row[flag] = False
        require(rendered(module, row)[1].endswith('| FAIL |'), 'forged counts hid an incomplete comparison')
    for side in ('reference_memory', 'paslang_memory'):
        row = sample(); row[side][0]['stdout'] = 'one\nwrong second line\n'
        require(rendered(module, row)[1].endswith('| FAIL |'), 'memory ok flag hid full stdout mismatch')
        row = sample(); row[side][0]['status'] = 7
        require(rendered(module, row)[1].endswith('| FAIL |'), 'memory ok flag hid nonzero status')
    row = sample(); row['rounds'][0]['a']['stdout'] = '</pre>|\nsecond\udcff'
    out, line = rendered(module, row)
    text = '\n'.join(out)
    require(line.endswith('| FAIL |') and '&lt;/pre&gt;' in text and '\\udcff' in text and '\\nsecond' in text, 'full escaped diagnostic missing')
    require('</pre>|' not in text, 'diagnostic closed HTML pre')
    text.encode('utf-8', 'strict')
    legacy = {'pair': 'case', 'cpu': 'native', 'same_output': True, 'budget': 0.99, 'ratio_time': 0.5, 'ratio_mem': 0.5,
              'go': {'median_s': 2.0, 'peak_rss_mb': 2.0, 'status': 0, 'walls_s': [2.0]},
              'paslang': {'median_s': 1.0, 'peak_rss_mb': 1.0, 'status': 0, 'walls_s': [1.0]}}
    out = []; module.results(out.append, {'runs_per_program': 1, 'pairs': [legacy]})
    require(next(line for line in out if line.startswith('| case')).endswith('| PASS |'), 'old Go memory-budget compatibility lost')
    legacy['ratio_time'] = None
    out = []; module.results(out.append, {'runs_per_program': 1, 'pairs': [legacy]})
    require(next(line for line in out if line.startswith('| case')).endswith('| FAIL |'), 'legacy null was accepted')



def diagnostic_report_checks(folder, module=report):
    """Raw stderr wins over successful saved flags, on both record formats."""
    folder.mkdir()
    cases = []
    def observe(kind, row, passed, legacy=False):
        if legacy:
            out = []
            module.results(out.append, {'runs_per_program': 1, 'ok': True, 'pairs': [row]})
            line = next(line for line in out if line.startswith('| case'))
        else:
            out, line = rendered(module, row)
        cases.append({'case': kind, 'input': row, 'expected_pass': passed, 'actual_table_row': line})
        (folder / 'cases.json').write_text(json.dumps(cases, indent=1) + '\n')
        require(line.endswith('| PASS |') if passed else line.endswith('| FAIL |'), kind + ' was trusted as ok')
        return '\n'.join(out)
    missing = sample()
    for part in missing['rounds']:
        for side in ('a', 'b'): del part[side]['stderr']
    for field in ('reference_memory', 'paslang_memory'): del missing[field][0]['stderr']
    observe('missing historical stderr fields', missing, True)
    for side in ('a', 'b'):
        for diagnostic in ('GODEBUG warning\n', 'first\nsecond\udcff', None, False, 0):
            row = sample(); row['rounds'][0][side]['stderr'] = diagnostic
            text = observe('timed diagnostic', row, False)
            if diagnostic == 'first\nsecond\udcff':
                require('\\udcff' in text and '\\nsecond' in text, 'timed stderr bytes were not retained')
    for field in ('reference_memory', 'paslang_memory'):
        for diagnostic in ('GODEBUG warning\n', None, False, 0):
            row = sample(); row[field][0]['stderr'] = diagnostic
            observe('memory diagnostic', row, False)
            require(module.memory_mib(row[field], 1) is None, 'diagnostic memory counted as a valid measurement')
    legacy = {'pair': 'case', 'cpu': 'native', 'same_output': True, 'ok': True,
              'budget': .99, 'ratio_time': .5, 'ratio_mem': .5,
              'go': {'median_s': 2., 'peak_rss_mb': 2., 'status': 0, 'walls_s': [2.]},
              'paslang': {'median_s': 1., 'peak_rss_mb': 1., 'status': 0, 'walls_s': [1.]}}
    observe('legacy missing stderr fields', legacy, True, legacy=True)
    for side in ('go', 'paslang'):
        row = copy.deepcopy(legacy); row[side]['stderr'] = 'warning\n'
        observe('legacy summary diagnostic', row, False, legacy=True)
    legacy_round = {'ratio_median': .5, 'q1': .5, 'q3': .5, 'paslang_s': 1., 'go_s': 2.,
                    'same_output': True, 'budget': .99, 'over': '',
                    'requested_rounds': 1, 'completed_rounds': 1,
                    'rounds': [{'go': {'status': 0, 'stdout': 'same\n'},
                                'paslang': {'status': 0, 'stdout': 'same\n'}, 'errors': []}]}
    for side in (None, 'go', 'paslang'):
        row = copy.deepcopy(legacy_round)
        if side: row['rounds'][0][side]['stderr'] = 'warning\n'
        path = folder / ('legacy-round-' + str(side) + '.json')
        path.write_text(json.dumps({'pairs': {'case': row}}))
        out = []; module.rounds(out.append, path)
        line = next(line for line in out if line.startswith('| case'))
        require(line.endswith('| FAIL |') if side else line.endswith('| - |'), 'legacy round diagnostic was trusted as ok')
    out = []
    module.machine(out.append, {'go_capabilities': {'retained': 'cpu-proof'},
        'go_artifacts': {'retained': 'artifact'}, 'go_artifact_evidence': {'retained': 'gate'}}, 'fixture.json')
    text = '\n'.join(out)
    require(all(key in text for key in ('go_capabilities', 'go_artifacts', 'go_artifact_evidence')),
            'Go provenance keys disappeared from rendered evidence')


def compiler_diagnostic_report_checks(folder, module=report):
    folder.mkdir()
    baseline = compiler_record()
    for observation in baseline['warmups'] + [row[side] for row in baseline['pairs'][0]['rounds'] for side in ('paslang', 'reference')]:
        observation['execution'].pop('stderr', None)
    require('Aggregate build-probe verdict: PASS.' in compiler_rendered(module, baseline, folder),
            'compiler historical missing stderr fields were refused')
    cases = []
    for phase in ('build', 'execution'):
        for warmup in (False, True):
            for side in (0, 1):
                record = copy.deepcopy(baseline)
                observation = (record['warmups'][side] if warmup else
                    record['pairs'][0]['rounds'][0][('paslang', 'reference')[side]])
                observation[phase]['stderr'] = 'GODEBUG warning\nsecond\udcff'
                text = compiler_rendered(module, record, folder)
                cases.append({'phase': phase, 'warmup': warmup, 'side': side, 'record': record, 'rendered': text})
                (folder / 'cases.json').write_text(json.dumps(cases, indent=1) + '\n')
                require('Aggregate build-probe verdict: FAIL.' in text, 'compiler ' + phase + ' diagnostic was trusted as ok')
                require('\\udcff' in text, 'compiler diagnostic bytes were not retained')


def compiler_record():
    # N=1 has a hand-worked function result112027. Independent fixture
    # observations intentionally contain enough data to detect forged flags.
    def observed(wall, size, expected):
        return {'ok': True, 'phase': 'complete', 'executable_bytes': size,
                'build': {'status': 0, 'wall_s': wall},
                'execution': {'status': 0, 'stdout': expected, 'stderr': ''}}
    rows = []
    for index, nonce in enumerate((17, 18), 1):
        expected = str(112027 + nonce) + '\n'
        rows.append({'round': index, 'nonce': nonce, 'complete': True, 'expected_stdout': expected,
                     'paslang': observed(1.0, 100, expected), 'reference': observed(2.0, 200, expected)})
    pair = {'reference': 'go', 'cpu': 'native', 'same_output': True, 'ok': True,
            'requested_rounds': 2, 'completed_rounds': 2, 'paslang_s': [1.0, 1.0], 'reference_s': [2.0, 2.0],
            'paslang_bytes': [100, 100], 'reference_bytes': [200, 200], 'ratios': [0.5, 0.5],
            'ratio_median': 0.5, 'q1': 0.5, 'q3': 0.5, 'budget': 0.99, 'rounds': rows}
    warmups = []
    for language in ('paslang', 'go'):
        row = observed(1.0, 100, '112027\n')
        row.update(nonce=0, expected_stdout='112027\n', language=language)
        warmups.append(row)
    return {'format': 'paslang-compiler-build-refs-v1', 'ok': True, 'phase': 'complete',
            'functions': 1, 'rounds': 2, 'requested_comparisons': 1, 'completed_comparisons': 1,
            'pairs': [pair], 'warmups': warmups}


def compiler_rendered(module, record, folder):
    path = folder / 'compiler-report.json'
    path.write_text(json.dumps(record))
    output = []
    module.build(output.append, path)
    return '\n'.join(output)


def compiler_report_checks(folder, module=report):
    folder.mkdir()
    baseline = compiler_record()
    require('Aggregate build-probe verdict: PASS.' in compiler_rendered(module, baseline, folder), 'valid compiler report rejected')
    for side in ('paslang', 'reference'):
        for field, wrong in (('stdout', 'wrong second line\n'), ('status', 7), ('stderr', 'unexpected diagnostic\n')):
            record = copy.deepcopy(baseline)
            record['pairs'][0]['rounds'][0][side]['execution'][field] = wrong
            require('Aggregate build-probe verdict: FAIL.' in compiler_rendered(module, record, folder),
                    'compiler report trusted forged round output/status')
    for alter in ('nonce', 'build-status', 'size-array', 'time-array', 'ratio', 'warmup', 'counts', 'null-round', 'null-warmup'):
        record = copy.deepcopy(baseline)
        row = record['pairs'][0]
        if alter == 'nonce': row['rounds'][0]['nonce'] += 1
        elif alter == 'build-status': row['rounds'][0]['reference']['build']['status'] = 7
        elif alter == 'size-array': row['reference_bytes'][0] += 1
        elif alter == 'time-array': row['reference_s'][0] += 1
        elif alter == 'ratio': row['ratios'][0] = 0.01
        elif alter == 'warmup': record['warmups'][0]['execution']['stdout'] = 'wrong\n'
        elif alter == 'counts': record['requested_comparisons'] = 2
        elif alter == 'null-round': row['rounds'][0] = None
        elif alter == 'null-warmup': record['warmups'][0] = None
        require('Aggregate build-probe verdict: FAIL.' in compiler_rendered(module, record, folder),
                'compiler report trusted forged ' + alter)
    legacy = {'functions': 1, 'rounds': 1, 'paslang_s': [1.0], 'go_s': [2.0], 'ratio_median': 0.5,
              'q1': 0.5, 'q3': 0.5, 'budget': 0.99, 'same_output': True, 'over': ''}
    require('Aggregate build-probe verdict: PASS.' in compiler_rendered(module, legacy, folder), 'legacy compiler report compatibility lost')


def mutant(path, name, old, new):
    source = path.read_text()
    require(source.count(old) == 1, name + ': mutation anchor changed')
    module = types.ModuleType(name); module.__file__ = str(path)
    exec(compile(source.replace(old, new), '<' + name + '>', 'exec'), module.__dict__)
    return module


def mutant_checks(folder):
    last = mutant(Path(probe.__file__), 'last_round_mutant', "all(row['paslang']['ok'] and row['reference']['ok'] for row in rows)", "rows[-1]['paslang']['ok'] and rows[-1]['reference']['ok']")
    try:
        probe_checks(folder / 'last', last)
    except AssertionError as error:
        require('early wrong nonce/status' in str(error), 'last-round mutant failed an unrelated oracle')
    else:
        require(False, 'last-round-only mutant survived')
    omitted = mutant(Path(probe.__file__), 'nonce_mutant', "f'    let mut t: i64 = {nonce};'", "'    let mut t: i64 = 0;'")
    work = folder / 'nonce'; work.mkdir()
    with tools(work, omitted) as result:
        require(invoke(omitted, ['-n', '1', '--functions', '2', '--reference', 'rust', '--cpu', 'base', '--json', str(result)]) == 1 and not json.loads(result.read_text())['pairs'][0]['same_output'], 'nonce-generator mutant survived independent oracle')
    trusted = mutant(Path(report.__file__), 'trusted_flags_mutant', "verdict = same and measured and complete(pair, record, strict='reference' in pair) and limits(pair, record, ratio, budget, memory, mbudget)", "verdict = bool(pair.get('ok'))")
    require(rendered(trusted, dict(sample(), ratio_time=1.5))[1].endswith('| PASS |'), 'trust-flags mutant did not reach the intended violation')
    try:
        report_checks(trusted)
    except AssertionError as error:
        require('independent budget/count/null' in str(error), 'report mutant failed an unrelated oracle')
    else:
        require(False, 'trust-flags report mutant survived')
    aggregate = mutant(Path(report.__file__), 'compiler_flags_mutant', ' and build_round_evidence(row, record)', '')
    try:
        compiler_report_checks(folder / 'compiler-report-mutant', aggregate)
    except AssertionError as error:
        require('compiler report trusted forged round output/status' in str(error), 'compiler report mutant failed an unrelated oracle')
    else:
        require(False, 'aggregate-only compiler report mutant survived')
    masked_host = mutant(Path(probe.__file__), 'masked_compiler_host_mutant',
                         "return go_runtime_environment('native', None, env)",
                         "return go_runtime_environment(cpu, native_level, env, capabilities)")
    try:
        flags_and_refusals(folder / 'masked-host-mutant', masked_host)
    except AssertionError as error:
        require('Go compiler host was ISA-masked' in str(error), 'compiler-host mutant failed an unrelated oracle')
    else:
        require(False, 'masked compiler-host mutant survived')
    unmasked_target = mutant(Path(probe.__file__), 'unmasked_generated_runtime_mutant',
                             "executed = command([executable], source.parent, execution_env, timeout,",
                             "executed = command([executable], source.parent, env, timeout,")
    try:
        flags_and_refusals(folder / 'unmasked-target-mutant', unmasked_target)
    except AssertionError as error:
        require('Go generated base runtime lost reviewed ISA mask' in str(error), 'target-runtime mutant failed an unrelated oracle')
    else:
        require(False, 'unmasked target-runtime mutant survived')
    for name,old,new in (
        ('ignored_build_stderr'," or built['stderr'] != ''",''),
        ('ignored_execution_stderr'," and executed['stderr'] == ''",'')):
        changed=mutant(Path(probe.__file__),name,old,new)
        try:diagnostic_checks(folder/name,changed)
        except AssertionError as error:
            require('unexpected compiler/generated stderr accepted' in str(error),'diagnostic mutant failed unrelated oracle')
        else:require(False,'compiler/generated stderr mutant survived')
    unbound = mutant(Path(probe.__file__), 'unit_provenance_mutant',
                     "result['paslang_inputs'] = paslang_inputs(built['command'], executable, env, cwd=build_cwd)",
                     "result['paslang_inputs'] = {'units': []}")
    try:
        provenance_checks(folder / 'unit-provenance-mutant', unbound)
    except AssertionError as error:
        require('resolved unit provenance is absent' in str(error), 'unit provenance mutant failed an unrelated oracle')
    else:
        require(False, 'omitted unit provenance mutant survived')


def diagnostic_report_mutants(folder):
    folder.mkdir()
    source = Path(report.__file__).read_text()
    variants = (
        ('report_timed_stderr', ((" or not timed_diagnostics_empty(pair)", ''),), 'timed diagnostic', diagnostic_report_checks),
        ('report_memory_stderr', ((" and stderr_empty(row)", ''), (" or not stderr_empty(sample)", '')), 'memory diagnostic', diagnostic_report_checks),
        ('report_legacy_stderr', ((" or not stderr_empty(pair[side])", ''),), 'legacy summary diagnostic', diagnostic_report_checks),
        ('report_legacy_round_stderr', ((" and timed_diagnostics_empty(row)", ''),), 'legacy round diagnostic', diagnostic_report_checks),
        ('report_build_stderr', ((" and stderr_empty(built)", ''),), 'compiler build diagnostic', compiler_diagnostic_report_checks),
        ('report_execution_stderr', ((" and stderr_empty(execution)", ''),), 'compiler execution diagnostic', compiler_diagnostic_report_checks),
    )
    results = []
    for name, replacements, expected, check in variants:
        changed = source
        for old, new in replacements:
            wanted = 2 if name == 'report_legacy_round_stderr' else 1
            require(changed.count(old) == wanted, name + ': source mutation anchor changed')
            changed = changed.replace(old, new)
        directory = folder / name; directory.mkdir()
        (directory / 'report.py').write_text(changed)
        module = types.ModuleType(name); module.__file__ = str(directory / 'report.py')
        exec(compile(changed, module.__file__, 'exec'), module.__dict__)
        try:
            check(directory / 'cases', module)
        except AssertionError as error:
            require(expected in str(error), name + ': mutant failed unrelated oracle: ' + str(error))
            results.append({'name': name, 'source_sha256': hashlib.sha256(changed.encode()).hexdigest(),
                            'caught': True, 'diagnostic': str(error)})
            (folder / 'results.json').write_text(json.dumps(results, indent=1) + '\n')
        else:
            require(False, name + ': diagnostic-report mutant survived')
    require(len(results) == 6, 'diagnostic report mutant count changed')


def main():
    generator_checks()
    report_checks()
    with tempfile.TemporaryDirectory(prefix='paslang-build-report-') as temporary:
        root = Path(temporary)
        probe_checks(root / 'probe')
        output_status_checks(root / 'output-status')
        environment_checks(root / 'environment')
        flags_and_refusals(root / 'flags')
        provenance_checks(root / 'provenance')
        interrupted_evidence(root / 'interrupted')
        cleanup_checks(root / 'cleanup')
        compiler_report_checks(root / 'compiler-report')
        diagnostic_report_checks(root / 'report-diagnostics')
        compiler_diagnostic_report_checks(root / 'compiler-report-diagnostics')
        diagnostic_checks(root / 'diagnostics')
        go_capability_refusals(root / 'go-capability-refusals')
        go_metadata_diagnostic_refusals(root / 'go-metadata-diagnostics')
        go_provider_refusals(root / 'go-provider-refusals')
        mutant_checks(root)
        diagnostic_report_mutants(root / 'diagnostic-report-mutants')
    print('check_build_report: independent generators/nonces; every round and interruption evidence; group cleanup; resolved unit interface/object provenance; runtime environment allowlist; flags/refusals; escaped diagnostics/legacy/null/budgets; fifteen semantic mutants; present stderr overrides saved success flags; compiler-host CPU detection separated from generated-target masks')


if __name__ == '__main__':
    main()
