#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Validate every release format and run both relocated packaged compilers."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

repo = Path(__file__).resolve().parents[1]
assets = repo / 'build/pkg/release'
base = {key: value for key, value in os.environ.items() if not key.startswith('PASLANG_GC')}
stress = dict(base, PASLANG_GCVERIFY='1', PASLANG_GCSTRESS='1', PASLANG_GCPOISON='1')
work = Path(tempfile.mkdtemp(prefix='paslang-release-check-'))
qemu = repo / 'build/qemu-aarch64-static'


def run(command, cwd=work, env=base):
    result = subprocess.run(list(map(str, command)), cwd=cwd, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    if result.returncode:
        raise RuntimeError(f'{command}: {result.returncode}\n{result.stdout.decode(errors="replace")}')
    return result.stdout


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


version = re.search(rb'paslangc\s+([0-9.]+)', run([repo / 'bin/paslangc', '-v']))[1].decode()
# Independently compile the distributed tools for the baseline, rather than
# accepting a package that merely copies a host-native build of pasdbg.
debugger_hashes = {}
for target in ('amd64', 'arm64'):
    # GAS records the object basename as an ELF FILE symbol. Match the real
    # tool's basename so the comparison includes every byte, without stripping
    # symbols or normalizing a difference away.
    reference = work / f'baseline-{target}' / 'pasdbg'
    reference.parent.mkdir()
    core = repo / ('build/a64' if target == 'arm64' else 'build')
    run([repo / 'bin/paslangc', '-target', target, '-cpu', 'base', '-Fu', core,
         '-o', reference, 'cmd/pasdbg/pasdbg.paslang'], cwd=repo)
    debugger_hashes[target] = digest(reference)
records = (assets / 'SHA256SUMS').read_text().splitlines()
if len(records) != 10:
    raise RuntimeError('release must contain ten packages and SHA256SUMS')
for record in records:
    expected, name = record.split()
    if Path(name).name != name or version not in name or digest(assets / name) != expected:
        raise RuntimeError(f'invalid asset or checksum: {name}')
    directory = work / (name + '.extracted')
    directory.mkdir()
    if name.endswith('.deb'):
        run(['dpkg-deb', '--extract', assets / name, directory])
    elif name.endswith('.rpm'):
        process = subprocess.Popen(['rpm2cpio', str(assets / name)], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        try:
            result = subprocess.run(['bsdtar', '-xf', '-', '-C', str(directory)],
                                    stdin=process.stdout, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, timeout=120)
            process.stdout.close()
            error = process.stderr.read()
            if result.returncode or process.wait(timeout=10):
                raise RuntimeError(f'RPM extraction failed: {result.stdout!r} {error!r}')
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    else:
        run(['bsdtar', '-xf', assets / name, '-C', directory])
    packaged = list(directory.rglob('bin/paslangc'))
    if len(packaged) != 1:
        raise RuntimeError(f'package has no unique compiler: {name}')
    compiler = packaged[0]
    target = 'arm64' if ('arm64' in name or 'aarch64' in name) else 'amd64'
    reference = repo / ('bin/paslangc-arm64' if target == 'arm64' else 'bin/paslangc')
    if digest(compiler) != digest(reference):
        raise RuntimeError(f'package compiler differs from verified binary: {name}')
    debugger = compiler.with_name('pasdbg')
    if not debugger.is_file() or digest(debugger) != debugger_hashes[target]:
        raise RuntimeError(f'package debugger is not the baseline build: {name}')
    header = run(['readelf', '-h', compiler])
    if (b'AArch64' if target == 'arm64' else b'X86-64') not in header:
        raise RuntimeError(f'wrong package architecture: {name}')
    if b'INTERP' in run(['readelf', '-l', compiler]):
        raise RuntimeError(f'compiler unexpectedly requires a dynamic loader: {name}')
    manual = list(directory.rglob('manual/index.html'))
    if len(manual) != 1 or digest(manual[0]) != digest(repo / 'docs/manual/index.html'):
        raise RuntimeError(f'package manual is not current: {name}')
    documentation = compiler.parents[1] / 'share/doc/paslang'
    for source in ('README.md', 'docs/MANUAL.md', 'docs/HELP.md', 'docs/TYPES.md',
                   'docs/GC.md', 'docs/QUAD.md', 'docs/KERNELS.md',
                   'docs/VISION.md', 'docs/CONSTRAINTS.md'):
        if digest(documentation / Path(source).name) != digest(repo / source):
            raise RuntimeError(f'package documentation is not current: {name}/{source}')
    print(f'ok package format and contents {name}', flush=True)

fixtures = ('systemerrors', 'blockedio', 'boundedfiles', 'filemetadata', 'directories',
            'paths', 'environments', 'processes', 'temporaryresources', 'systempaths',
            'textbuilding', 'textencoding', 'textbuffers', 'valuehelpers', 'identifiers',
            'money', 'scopedtypes')
for target in ('amd64', 'arm64'):
    package = work / f'paslang-{version}-linux-{target}.tar.gz.extracted' / f'paslang-{version}-linux-{target}'
    launch = [qemu, '-cpu', 'max'] if target == 'arm64' else []
    compiler = package / 'bin/paslangc'
    if version.encode() not in run([*launch, compiler, '-v']):
        raise RuntimeError('wrong packaged compiler version')
    for name in fixtures:
        source = package / f'share/paslang/examples/{name}.paslang'
        binary = work / f'{name}-{target}'
        # Deliberately no -Fu: the relocated compiler must find its own units.
        run([*launch, compiler, '-cpu', 'base', '-o', binary, source])
        output = run([*launch, binary], env=stress)
        if output != source.with_suffix('.out').read_bytes():
            raise RuntimeError(f'packaged example {name}/{target}: {output!r}')
        print(f'ok relocated packaged compiler {target}: {name}', flush=True)
    # Exercise the actual packaged debugger against an instrumented program,
    # including parsing replies through its string/network units. AArch64's
    # compiler, program and debugger also run on a model without LSE.
    baseline = [qemu, '-cpu', 'cortex-a53'] if target == 'arm64' else []
    binary = work / f'debug-package-{target}'
    socket = work / f'debug-package-{target}.sock'
    run([*baseline, compiler, '-cpu', 'base', '-debug', '-o', binary,
         package / 'share/paslang/examples/money.paslang'])
    program = subprocess.Popen([*baseline, str(binary), '--debug-listen', str(socket)],
                               cwd=work, env=stress, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 30
        while not socket.exists():
            if program.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError(f'packaged debug program did not listen: {target}')
            time.sleep(0.01)
        reply = run([*baseline, package / 'bin/pasdbg', socket, 'help'], env=stress)
        if not reply.endswith(b'ok\n') or b'next' not in reply:
            raise RuntimeError(f'packaged debugger protocol failed: {target}: {reply!r}')
    finally:
        if program.poll() is None:
            program.terminate()
        try:
            program.wait(timeout=10)
        except subprocess.TimeoutExpired:
            program.kill()
            program.wait(timeout=10)
    print(f'ok relocated baseline compiler/program/debugger protocol {target}', flush=True)
print('ok all ten release packages, current manuals and both relocated compilers', flush=True)
