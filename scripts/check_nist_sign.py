#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Both-target ECDSA API, oracle, CPU, inline and GC regressions (P594)."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

repo = Path(__file__).resolve().parents[1]
compiler = Path(sys.argv[1]).resolve()
build = Path(sys.argv[2]).resolve()
qemu = Path(sys.argv[3]).resolve()
root = Path(tempfile.mkdtemp(prefix='nist-sign-', dir=build))
base = {k: v for k, v in os.environ.items() if not k.startswith('PASLANG_GC')}
stress = dict(base, PASLANG_GCVERIFY='1', PASLANG_GCSTRESS='1', PASLANG_GCPOISON='1')
off = dict(base, PASLANG_GC='off')
expected = (repo / 'testdata/nistsign.out').read_bytes()
corpus = repo / 'testdata/nistsign-vectors.json'
assert len(json.loads(corpus.read_text())['vectors']) == 90
frozen = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (
    compiler, repo / 'src/lib/pasnist.paslang', repo / 'testdata/nistsign.paslang', corpus)}
records = []
state = {'ok': False, 'complete': False, 'commands': records, 'evidence': str(root)}


def save():
    (root / 'status.json').write_text(json.dumps(state, indent=2) + '\n')


def guard():
    for name, digest in frozen.items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest, name


def run(label, arguments, env=base, want=None):
    guard()
    directory = root / label
    directory.mkdir()
    args = list(map(str, arguments))
    row = {'label': label, 'argv': args, 'cwd': str(repo), 'timeout_s': 240,
           'environment': {k: v for k, v in env.items() if k.startswith('PASLANG_GC')},
           'exit': None, 'timed_out': False}
    records.append(row)
    (directory / 'command.json').write_text(json.dumps(row, indent=2) + '\n')
    save()
    start = time.monotonic()
    process = subprocess.Popen(args, cwd=repo, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        out, err = process.communicate(timeout=240)
    except subprocess.TimeoutExpired:
        row['timed_out'] = True
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, err = process.communicate(timeout=20)
    row.update(exit=process.returncode, elapsed_s=time.monotonic() - start)
    (directory / 'stdout').write_bytes(out)
    (directory / 'stderr').write_bytes(err)
    (directory / 'status.json').write_text(json.dumps(row, indent=2) + '\n')
    save()
    guard()
    if row['timed_out'] or process.returncode != 0:
        raise RuntimeError(f'{label} failed; process evidence: {directory}')
    if want is not None and out != want:
        raise RuntimeError(f'{label} output mismatch; process evidence: {directory}')
    return out


save()
try:
    for target in ('amd64', 'arm64'):
        core = build / ('a64' if target == 'arm64' else '')
        launch = [qemu, '-cpu', 'max'] if target == 'arm64' else []
        interface = None
        for cpu in ('base', 'native' if target == 'amd64' else 'max'):
            for inline in (0, 40):
                tag = f'{target}-{cpu}-{inline}'
                directory = root / tag
                directory.mkdir()
                flags = ['-target', target, '-cpu', cpu, '-inline', str(inline)]
                run(tag + '-unit', [compiler, *flags, '-c', '-Fu', core, '-o',
                    directory / 'pasnist', repo / 'src/lib/pasnist.paslang'])
                observed = (directory / 'pasnist.pi').read_bytes()
                if interface is None:
                    interface = observed
                elif interface != observed:
                    raise RuntimeError(f'public interface changes with CPU/inline: {tag}')
                binary = directory / 'nistsign'
                run(tag + '-compile', [compiler, *flags, '-Fu', directory, '-Fu', core,
                    '-o', binary, repo / 'testdata/nistsign.paslang'])
                if str(directory / 'pasnist.o') not in binary.with_suffix('.link').read_text():
                    raise RuntimeError(f'test did not link its own library variant: {tag}')
                run(tag + '-normal', [*launch, binary], want=expected)
                run(tag + '-stress', [*launch, binary], env=stress, want=expected)
                run(tag + '-cold', [*launch, binary, 'cold'], env=stress,
                    want=b'cold concurrent ok\n')
                run(tag + '-oracle', [*launch, binary, 'oracle', corpus],
                    want=b'oracle signatures: 90\n')
                run(tag + '-off-oracle', [*launch, binary, 'oracle', corpus], env=off,
                    want=b'oracle signatures: 90\n')
                run(tag + '-off-keys', [*launch, binary, 'keys'], env=off,
                    want=b'generated keys ok\n')
                if cpu == 'base' and target == 'amd64':
                    run(tag + '-baseline-code', ['python3', '-I',
                        repo / 'scripts/check_cpubin.py', 'base', binary])
                if target == 'arm64' and cpu == 'base':
                    run(tag + '-arm-baseline', [qemu, '-cpu', 'cortex-a53', binary],
                        env=stress, want=expected)
                print('check_nist_sign:', tag, 'passed', flush=True)
    state['ok'] = True
finally:
    state['complete'] = True
    save()
print('check_nist_sign: RFC/API/90-oracle/GC/concurrency matrix passed; ' + str(root), flush=True)
