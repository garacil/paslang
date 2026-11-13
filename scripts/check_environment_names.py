#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Check the selected base SDK with long environment names and private controls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
LOOKUP = '.rela.text.p_f.8_paslinux24_lookupprocessenvironment'
BASE = 'p_f.6_passtr14_pasposcharbase'
CPU = 'p_f.6_passtr13_pasposcharcpu'
LIMITED = 'qemu64,sse3=off,cx16=off,lahf-lm=off,avx=off,avx2=off'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def identity(path):
    path = Path(path).resolve(strict=True)
    blob = path.read_bytes()
    return {'path': str(path), 'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest()}


def machine(path):
    with Path(path).open('rb') as stream:
        head = stream.read(20)
    require(head[:6] == b'\x7fELF\x02\x01', 'expected a little-endian ELF64 file: ' + str(path))
    return int.from_bytes(head[18:20], 'little')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', required=True, type=Path)
    parser.add_argument('--library', required=True, type=Path)
    parser.add_argument('--target', required=True, choices=('amd64', 'arm64'))
    parser.add_argument('--qemu', type=Path)
    parser.add_argument('--installed', action='store_true')
    parser.add_argument('--mutation-controls', action='store_true')
    parser.add_argument('--qemu-amd64', type=Path)
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    compiler, library = args.compiler.resolve(strict=True), args.library.resolve(strict=True)
    qemu = args.qemu.resolve(strict=True) if args.qemu else None
    qemu_amd64 = args.qemu_amd64.resolve(strict=True) if args.qemu_amd64 else None
    require(library.is_dir(), 'library must name the actual target SDK directory')
    host_arm = platform.machine().lower() in ('aarch64', 'arm64')
    compiler_machine = machine(compiler)
    require(compiler_machine in (62, 183), 'unsupported compiler ELF machine')
    require(compiler_machine != 183 or host_arm or qemu, 'an ARM compiler needs --qemu on this host')
    require(compiler_machine != 62 or not host_arm or qemu_amd64, 'an AMD64 compiler needs --qemu-amd64 on this host')
    require(args.target != 'amd64' or not host_arm or qemu_amd64, 'AMD64 programs need --qemu-amd64 on this host')
    require(args.target != 'arm64' or host_arm or qemu, 'ARM programs need --qemu on this host')
    require(not args.mutation_controls or args.target == 'amd64', 'the native-profile leak mutant is AMD64-specific')
    work = Path(tempfile.mkdtemp(prefix='paslang-environment-names-'))
    result_path = args.json.resolve() if args.json else work / 'result.json'
    require(not result_path.exists(), 'refuse to replace an earlier result receipt')
    result_path.parent.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('PASLANG_', 'QEMU_')) and not k.upper().startswith('P612_')}
    env.update(LANG='C.UTF-8', LC_ALL='C.UTF-8')
    for size in (32, 33, 64, 65):
        env['P612_P' + 'x' * (size - 6)] = 'present' + str(size)
        env['P612_E' + 'x' * (size - 6)] = ''
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    state = {'format': 'paslang-environment-names-check-v1', 'ok': False, 'complete': False,
             'target': args.target, 'installed': args.installed, 'work': str(work),
             'compiler': identity(compiler), 'compiler_elf_machine': compiler_machine,
             'library': str(library), 'source': identity(ROOT / 'testdata/environmentnames.paslang'),
             'commands': [], 'inherited_paslang_lib_removed': 'PASLANG_LIB' not in env,
             'qemu': identity(qemu) if qemu else None,
             'qemu_amd64': identity(qemu_amd64) if qemu_amd64 else None}

    def save():
        temporary = result_path.with_name(result_path.name + '.tmp-' + str(os.getpid()))
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=1, allow_nan=False) + '\n')
        temporary.replace(result_path)

    def run(label, command, expected=None, code=0, allow_stderr=False):
        command = list(map(str, command)); start = time.monotonic()
        item = {'label': label, 'argv': command, 'cwd': str(work), 'paslang_lib_present': False}
        state['commands'].append(item); save()
        child = None
        try:
            child = subprocess.Popen(command, cwd=work, env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, start_new_session=True)
            stdout, stderr = child.communicate(timeout=180)
        except BaseException as error:
            if child is not None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                stdout, stderr = child.communicate()
            else:
                stdout = stderr = b''
            item.update(error={'type': type(error).__name__, 'message': str(error)},
                        timeout=isinstance(error, subprocess.TimeoutExpired),
                        status=child.returncode if child else None, elapsed_s=time.monotonic() - start)
            for name, data in (('stdout', stdout), ('stderr', stderr)):
                path = work / (str(len(state['commands'])) + '-' + label + '.' + name)
                path.write_bytes(data); item[name] = identity(path)
            save()
            raise
        process = subprocess.CompletedProcess(command, child.returncode, stdout, stderr)
        item.update(status=process.returncode, elapsed_s=time.monotonic() - start)
        for name, data in (('stdout', process.stdout), ('stderr', process.stderr)):
            path = work / (str(len(state['commands'])) + '-' + label + '.' + name)
            path.write_bytes(data); item[name] = identity(path)
        save()
        require(code is None or process.returncode == code, label + ': unexpected status ' + str(process.returncode))
        require(allow_stderr or not process.stderr, label + ': unexpected stderr')
        require(expected is None or process.stdout == expected, label + ': unexpected stdout')
        return process

    compiler_runner = ([qemu, '-cpu', 'cortex-a53'] if compiler_machine == 183 and not host_arm else
                       [qemu_amd64, '-cpu', 'max'] if compiler_machine == 62 and host_arm else [])

    def compile_client(label, output, selected_library, installed=False, source=None):
        flags = [] if installed else ['-Fu', str(selected_library)]
        run(label, [*compiler_runner, compiler, '-target', args.target, '-cpu', 'base', *flags,
                    '-o', output, source or ROOT / 'testdata/environmentnames.paslang'], expected=b'')
        require(machine(output) == (183 if args.target == 'arm64' else 62), label + ': wrong target ELF')
        link = output.with_suffix('.link').read_text().splitlines()
        require(link[:6] == ['-o', str(output), '--gc-sections', '-T', str(output.with_suffix('.ld')),
                             str(output.with_suffix('.o'))], label + ': unexpected link argument layout')
        objects = [Path(value).resolve(strict=True) for value in link[6:]]
        require(objects and len(set(objects)) == len(objects), label + ': missing/duplicate SDK objects')
        require(all(path.suffix == '.o' and path.parent == selected_library.resolve()
                    for path in objects), label + ': selected object escaped the direct base SDK directory')
        require({'paslinux.o', 'paslib.o'} <= {path.name for path in objects}, label + ': environment SDK objects missing')
        binding = {'binary': identity(output), 'link': identity(output.with_suffix('.link')),
                   'objects': [identity(path) for path in objects]}
        state.setdefault('applications', {})[label] = binding; save()
        return objects

    def relocations(label, obj):
        require(machine(obj) == (183 if args.target == 'arm64' else 62), 'wrong SDK object target')
        text = run(label, ['readelf', '-rW', obj]).stdout.decode()
        current = None; entries = []; found = False
        for line in text.splitlines():
            section = re.match(r"Relocation section '([^']+)'", line)
            if section:
                current = section[1]; found |= current == LOOKUP
            elif current == LOOKUP and re.match(r'^\s*[0-9a-fA-F]+\s', line):
                entries.append(line.split())
        require(found and entries, 'missing LookupProcessEnvironment relocation section')
        call_type = 'R_AARCH64_CALL26' if args.target == 'arm64' else 'R_X86_64_PLT32'
        require(all(len(entry) >= 5 for entry in entries), 'malformed LookupProcessEnvironment relocation entry')
        calls = [entry[4] for entry in entries if entry[2] == call_type]
        counts = {'base': calls.count(BASE), 'cpu': sum(entry[4] == CPU for entry in entries),
                  'cpu_calls': calls.count(CPU), 'object': identity(obj), 'call_type': call_type}
        state.setdefault('relocations', {})[label] = counts; save()
        return counts

    def expected(size=None):
        if size is None:
            return (ROOT / 'testdata/environmentnames.out').read_bytes()
        return ('environment names ' + str(size) + ': present/empty/missing/invalid OK\n').encode()

    def library_manifest():
        return {str(path): identity(path) for path in library.iterdir()
                if path.is_file() and path.suffix in ('.o', '.pi')}

    library_before = library_manifest()
    state['library_inputs_before'] = library_before
    save()
    try:
        binary = work / 'environmentnames'
        compile_client('compile-base', binary, library, args.installed)
        counts = relocations('base-relocations', library / 'paslinux.o')
        require(counts['base'] == 2 and counts['cpu'] == 0, 'base SDK selected CPU-only environment search')
        if args.target == 'amd64':
            run('base-instructions', [sys.executable, '-I', ROOT / 'scripts/check_cpubin.py', 'base', binary])
            runner = [qemu_amd64, '-cpu', LIMITED] if host_arm else []
            run('base-amd64', [*runner, binary], expected=expected())
        elif host_arm:
            run('base-native-arm', [binary], expected=expected())
        else:
            for model in ('cortex-a53', 'max'):
                run('base-arm-' + model, [qemu, '-cpu', model, binary], expected=expected())
        state['positive_base_complete'] = True; save()
        if args.mutation_controls:
            sdk = work / 'mutant-sdk'; sdk.mkdir()
            for path in library.iterdir():
                if path.is_file() and path.suffix in ('.o', '.pi'):
                    shutil.copy2(path, sdk / path.name)
            run('build-private-profile-mutant', [*compiler_runner, compiler, '-target', 'amd64', '-cpu', 'v3',
                '-c', '-Fu', sdk, '-o', sdk / 'paslinux', ROOT / 'src/lib/paslinux.paslang'], expected=b'')
            bad = work / 'mutant-environmentnames'
            compile_client('compile-mutant-client', bad, sdk)
            counts = relocations('mutant-relocations', sdk / 'paslinux.o')
            require(counts['cpu'] == counts['cpu_calls'] == 2 and counts['base'] == 0, 'mutation did not reproduce the CPU-only calls')
            rejected = run('mutant-instructions', [sys.executable, '-I', ROOT / 'scripts/check_cpubin.py', 'base', bad], code=1)
            require(b'pasindexbytecpu' in rejected.stdout.lower(), 'instruction oracle rejected an unrelated defect')
            state['mutant_static_oracles_rejected'] = True
            flags = Path('/proc/cpuinfo').read_text().split() if Path('/proc/cpuinfo').exists() else []
            if not host_arm and 'avx2' in flags:
                run('mutant-native-avx2', [bad], expected=expected())
                state['mutant_native_control'] = 'passed on AVX2 host'
            else:
                state['mutant_native_control'] = 'not run: host AVX2 unavailable'
            if qemu_amd64:
                run('qemu-amd64-version', [qemu_amd64, '--version'])
                run('masked-capabilities', [qemu_amd64, '-cpu', LIMITED, binary, 'capabilities'], expected=b'0 0 0 0\n')
                canary_source = work / 'avx2-canary.paslang'
                canary_source.write_text("program avx2canary; uses passtr; var s: string; begin s := StringOfChar('x',33); if PasIndexByteCpu(@s[1],33,Ord('z')) <> -1 then Halt(1); WriteLn('AVX2 canary'); end.\n")
                canary = work / 'avx2-canary'
                run('compile-avx2-canary', [*compiler_runner, compiler, '-target', 'amd64', '-cpu', 'base', '-Fu', library,
                    '-o', canary, canary_source], expected=b'')
                run('canary-max', [qemu_amd64, '-cpu', 'max', canary], expected=b'AVX2 canary\n')
                calibrated = run('canary-masked', [qemu_amd64, '-cpu', LIMITED, canary], code=None, expected=b'', allow_stderr=True)
                require(calibrated.returncode in (-signal.SIGILL, 128 + signal.SIGILL), 'masked AVX2 canary did not fail with SIGILL')
                run('base-masked', [qemu_amd64, '-cpu', LIMITED, binary], expected=expected())
                run('mutant-max-32', [qemu_amd64, '-cpu', 'max', bad, '32'], expected=expected(32))
                run('mutant-max-33', [qemu_amd64, '-cpu', 'max', bad, '33'], expected=expected(33))
                # The CPU function's common AVX cleanup also requires AVX for32-byte inputs.
                short_failure = run('mutant-masked-32', [qemu_amd64, '-cpu', LIMITED, bad, '32'], code=None, expected=b'', allow_stderr=True)
                require(short_failure.returncode == calibrated.returncode, 'short-name mutant differs from calibrated SIGILL')
                failure = run('mutant-masked-33', [qemu_amd64, '-cpu', LIMITED, bad, '33'], code=None, expected=b'', allow_stderr=True)
                require(failure.returncode == calibrated.returncode, 'long-name mutant differs from calibrated SIGILL')
                state['mutant_masked_control'] = {'verified': True, 'model': LIMITED, 'calibrated_status': calibrated.returncode}
            else:
                state['mutant_masked_control'] = {'verified': False, 'reason': '--qemu-amd64 was not supplied; static oracles remain mandatory'}
        state['ok'] = True
    except BaseException as error:
        state['error'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        state['complete'] = True
        for label, read_now, before in (
                ('compiler', lambda: identity(compiler), state['compiler']),
                ('library_inputs', library_manifest, library_before)):
            try:
                state[label + '_unchanged'] = read_now() == before
            except BaseException as error:
                state[label + '_unchanged'] = False
                state.setdefault('final_validation_errors', []).append(
                    {'input': label, 'type': type(error).__name__, 'message': str(error)})
        state['ok'] = state['ok'] and state['compiler_unchanged'] and state['library_inputs_unchanged']
        save()
    require(state['ok'], 'compiler or shared SDK changed during the check')
    print('ok environment names ' + args.target + '; selected base SDK; receipt ' + str(result_path))


if __name__ == '__main__':
    main()
