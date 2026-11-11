#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P577: program/unit failures, source tables and debugger stops on both targets."""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

repo = Path(__file__).resolve().parents[1]
compiler, build, qemu = (Path(s).resolve() for s in sys.argv[1:])
work = Path(tempfile.mkdtemp(prefix='inline-place-', dir=build))
base = {k: v for k, v in os.environ.items() if not k.startswith('PASLANG_GC')}
stress = dict(base, PASLANG_GCVERIFY='1', PASLANG_GCSTRESS='1', PASLANG_GCPOISON='1')
off = dict(base, PASLANG_GC='off')
expected = (repo / 'testdata/inlineplace.out').read_bytes()
inputs = [compiler, repo / 'testdata/inlineplace.paslang', repo / 'testdata/inlineplace.out',
          repo / 'testdata/units/inlineplaceu.paslang', repo / 'testdata/inlinebreak.paslang',
          repo / 'scripts/fixtures/inline_place_fatal.paslang',
          repo / 'scripts/fixtures/inline_place_gdb.py']
frozen = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
state = {'ok': False, 'complete': False, 'commands': [], 'inputs': frozen}


def save():
    (work / 'status.json').write_text(json.dumps(state, indent=2) + '\n')


def run(label, args, env=base, data=None, want=None, code=0):
    for name, digest in frozen.items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest, name
    directory = work / label
    directory.mkdir()
    args = list(map(str, args))
    record = {'label': label, 'argv': args, 'cwd': str(repo), 'exit': None,
              'environment': {k: v for k, v in env.items() if k.startswith('PASLANG_')},
              'timeout_s': 120, 'timed_out': False, 'expected_exit': code}
    state['commands'].append(record)
    save()
    started = time.monotonic()
    process = subprocess.Popen(args, cwd=repo, env=env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        out, err = process.communicate(data, timeout=120)
    except subprocess.TimeoutExpired:
        record['timed_out'] = True
        os.killpg(process.pid, signal.SIGKILL)
        out, err = process.communicate(timeout=20)
    record.update(exit=process.returncode, elapsed_s=time.monotonic() - started)
    (directory / 'stdout').write_bytes(out)
    (directory / 'stderr').write_bytes(err)
    if data is not None:
        (directory / 'stdin').write_bytes(data)
    save()
    if record['timed_out'] or process.returncode != code or (want is not None and out != want):
        raise RuntimeError(f'{label} failed; evidence: {directory}')
    return out


save()
try:
    for target, cpu in (('amd64', 'base'), ('amd64', 'native'), ('arm64', 'base'), ('arm64', 'max')):
        core = build / ('a64' if target == 'arm64' else '')
        runner = [qemu, '-cpu', 'cortex-a53' if cpu == 'base' else 'max'] if target == 'arm64' else []
        for inline in (0, 40):
            tag = f'{target}-{cpu}-{inline}'
            directory = work / tag
            directory.mkdir()
            flags = ['-target', target, '-cpu', cpu, '-inline', str(inline)]
            run(tag + '-unit', [compiler, *flags, '-c', '-Fu', core, '-o', directory / 'inlineplaceu',
                               repo / 'testdata/units/inlineplaceu.paslang'])
            assembly = (directory / 'inlineplaceu.s').read_text()
            for helper in ('cell', 'half', 'load', 'letter'):
                calls = re.search(r'\b(?:callq?|bl)\s+p_inlineplaceu_' + helper + r'\b', assembly)
                assert bool(calls) == (inline == 0), (tag, helper, 'inlining control failed')
            binary = directory / 'inlineplace'
            run(tag + '-compile', [compiler, *flags, '-Fu', directory, '-Fu', core,
                                  '-o', binary, repo / 'testdata/inlineplace.paslang'])
            assert str(directory / 'inlineplaceu.o') in binary.with_suffix('.link').read_text()
            for mode, env in (('normal', base), ('stress', stress), ('off', off)):
                run(tag + '-' + mode, [*runner, binary], env, want=expected)
            fatal = directory / 'inlinefatal'
            run(tag + '-fatal-compile', [compiler, *flags, '-Fu', core, '-o', fatal,
                                        repo / 'scripts/fixtures/inline_place_fatal.paslang'])
            assert 'sysutils.o' not in fatal.with_suffix('.link').read_text()
            for kind, line, error in (
                    ('index', 7, 'index 6 out of range [0..3]'),
                    ('divide', 12, 'integer divide by zero'),
                    ('range', 17, 'real out of integer range'),
                    ('nil', 22, 'nil pointer dereference')):
                run(tag + '-fatal-' + kind, [*runner, fatal, kind], stress, want=b'before\n', code=1)
                observed = (work / (tag + '-fatal-' + kind) / 'stderr').read_bytes()
                assert observed == f'paslang: {error} at line {line}\n'.encode(), (tag, kind, observed)
            debugged = directory / 'inlinebreak'
            run(tag + '-debug-compile', [compiler, *flags, '-Fu', core, '-o', debugged,
                                        repo / 'testdata/inlinebreak.paslang'])
            run(tag + '-debug-plain', [*runner, debugged], want=b'13\n')
            run(tag + '-tables', [sys.executable, '-I', repo / 'scripts/check_paslines.py', binary, debugged])
            traced = dict(off, PASLANG_ASYNCPREEMPTOFF='1', DEBUGINFOD_URLS='')
            command = ['gdb', '-batch', '-nx', '-q', debugged, '-ex', 'set debuginfod enabled off',
                       '-ex', 'set pagination off']
            if target == 'amd64':
                out = run(tag + '-gdb', [*command, '-ex', 'source scripts/fixtures/inline_place_gdb.py'], traced)
            else:
                # Keep Unix socket paths short regardless of the build directory.
                with tempfile.TemporaryDirectory(prefix='pl-inl-') as sockdir:
                    endpoint = Path(sockdir) / 'gdb.sock'
                    guest = subprocess.Popen([*map(str, runner), '-g', str(endpoint), str(debugged)],
                                             cwd=repo, env=traced, stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE, start_new_session=True)
                    try:
                        deadline = time.monotonic() + 10
                        while not endpoint.exists():
                            if guest.poll() is not None or time.monotonic() >= deadline:
                                raise RuntimeError('QEMU did not open the debugger socket')
                            time.sleep(.01)
                        out = run(tag + '-gdb', [*command, '-ex', f'target remote {endpoint}',
                                  '-ex', 'source scripts/fixtures/inline_place_gdb.py'], traced)
                    finally:
                        if guest.poll() is None:
                            os.killpg(guest.pid, signal.SIGKILL)
                        so, se = guest.communicate(timeout=20)
                        (directory / 'guest.stdout').write_bytes(so)
                        (directory / 'guest.stderr').write_bytes(se)
                        (directory / 'guest.status').write_text(str(guest.returncode) + '\n')
            assert b'inline-place: call-site breaks and next passed\n' in out
            if cpu == 'base':
                console = directory / 'console'
                run(tag + '-console-compile', [compiler, *flags, '-debug', '-Fu', core, '-o', console,
                                              repo / 'testdata/inlinebreak.paslang'])
                commands = b'b 17\nc\np total\nn\np total\nn\np total\nd 1\nc\n'
                out = run(tag + '-console', [*runner, console, '--debug-mode'], stress, commands)
                for message in (b'inlinebreak.paslang:17', b'inlinebreak.paslang:18',
                                b'inlinebreak.paslang:19', b'total = 0\n', b'total = 5\n',
                                b'total = 13\n', b'the program ended\n'):
                    assert message in out, (tag, message)
            print(f'ok inline-place {tag}: faults, arguments, tables, breaks and next', flush=True)
    state['ok'] = True
finally:
    state['complete'] = True
    save()
print(f'inline-place evidence: {work}', flush=True)
