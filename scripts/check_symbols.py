#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P590: separate scoped declarations, opaque imports and ABI transitions.

Usage: check_symbols.py COMPILER BUILDDIR QEMU

Fixtures compile as separate units. Both CPU profiles of both targets run
at inline 0/40, normally and with GC stress. The actual pasast constructors
also execute on each target; a framed reader checks their components.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import signal
import subprocess
import sys
import tempfile
import time

repo = Path(__file__).resolve().parents[1]
compiler, build, qemu = (Path(s).resolve() for s in sys.argv[1:])
fixtures = repo / 'testdata/symbols'
work = Path(tempfile.mkdtemp(prefix='symbols-', dir=build))
api = runpy.run_path(str(Path(__file__).with_name('asm_symbols.py')))
decode = api['decode']
base = {k: v for k, v in os.environ.items() if not k.startswith('PASLANG_GC')}
stress = dict(base, PASLANG_GCVERIFY='1', PASLANG_GCSTRESS='1', PASLANG_GCPOISON='1')
inputs = [compiler, Path(__file__), Path(__file__).with_name('asm_symbols.py'),
          repo / 'src/compiler/pasast.paslang', repo / 'testdata/fatal/nilasmtop.paslang',
          *sorted(fixtures.iterdir())]
frozen = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
state = {'ok': False, 'complete': False, 'commands': [], 'inputs': frozen}


def save():
    (work / 'status.json').write_text(json.dumps(state, indent=2) + '\n')


def run(label, args, directory, *, code=0, want=None, env=base):
    for name, digest in frozen.items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest, name
    args = list(map(str, args))
    started = time.monotonic()
    row = {'label': label, 'argv': args, 'cwd': str(directory), 'exit': None,
           'expected_exit': code, 'timeout': False,
           'environment': {k: v for k, v in env.items() if k.startswith('PASLANG_GC')}}
    state['commands'].append(row)
    save()
    process = subprocess.Popen(args, cwd=directory, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        out, err = process.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        row['timeout'] = True
        os.killpg(process.pid, signal.SIGKILL)
        out, err = process.communicate(timeout=20)
    row.update(exit=process.returncode, seconds=time.monotonic() - started)
    (work / (label + '.stdout')).write_bytes(out)
    (work / (label + '.stderr')).write_bytes(err)
    save()
    if row['timeout'] or process.returncode != code or (want is not None and out != want):
        raise RuntimeError(label + ' failed; evidence: ' + str(work))
    return out, err


def constructors(output):
    names = ('', 'a', 'a', '_', 'a_', '_a', 'a_b', 'a__b', 'a.b', '12_x')
    lines = output.decode('ascii').splitlines()
    assert len(lines) == 702, len(lines)
    seen = {}
    at = 0
    for i, owner in enumerate(names):
        for j, name in enumerate(names):
            parent, stem, member, nested, anonymous, operator, local = lines[at:at + 7]
            expected = [
                ('p_f', (owner, name), ''), ('t_u', (owner, name), ''),
                ('p_m', (stem, 'm_a'), ''), ('p_n', (parent, 'b_c'), ''),
                ('p_a', (parent, str(i * 10 + j)), ''),
                ('p_o', (owner, '', 'add', name, 'rhs'), ''),
                ('t_n', (parent, 't_a'), ''),
            ]
            for physical, identity in zip(lines[at:at + 7], expected):
                assert decode(physical) == identity, (physical, identity)
                assert physical not in seen or seen[physical] == identity, physical
                seen[physical] = identity
            at += 7
    assert lines[-2:] == ['_v3', '_r3'], lines[-2:]


save()
try:
    out, _ = run('help-format', [compiler, '--help', 'lang'], work)
    assert b'only PASLANGI36 loads' in out and b'only PASLANGI13' not in out
    for target, cpu in [('amd64', 'base'), ('amd64', 'native'),
                        ('arm64', 'base'), ('arm64', 'max')]:
        core = build / ('a64' if target == 'arm64' else '')
        launch = [qemu, '-cpu', 'cortex-a53' if cpu == 'base' else 'max'] if target == 'arm64' else []
        for inline in (0, 40):
            tag = f'{target}-{cpu}-{inline}'
            folder = work / tag
            folder.mkdir()
            flags = ['-target', target, '-cpu', cpu, '-inline', str(inline), '-Fu', folder, '-Fu', core]
            for unit in ('a', 'a_b', 'types_a', 'types_a_b', 'bridge', 'p_owner', 'classns'):
                run(tag + '-' + unit, [compiler, *flags, '-c', '-o', folder / unit,
                                      fixtures / (unit + '.paslang')], folder)
            assert (folder / 'a.pi').read_bytes().startswith(b'PASLANGI36\n')
            # A raw assembler reference is a consumer of the generated ABI.
            # This fixture forges a source PC while faulting inside assembly.
            raw = folder / 'raw-asm'
            run(tag + '-raw-asm-compile', [compiler, *flags, '-o', raw,
                repo / 'testdata/fatal/nilasmtop.paslang'], folder)
            _, err = run(tag + '-raw-asm-run', [*launch, raw], folder, code=1, want=b'before\n')
            assert err == b'paslang: nil pointer dereference at line 28\n', err
            for expected in sorted(fixtures.glob('*.out')):
                name = expected.stem
                binary = folder / name
                run(tag + '-' + name + '-compile', [compiler, *flags, '-o', binary,
                                                   fixtures / (name + '.paslang')], folder)
                for mode, env in [('normal', base), ('stress', stress)]:
                    run(tag + '-' + name + '-' + mode, [*launch, binary], folder,
                        want=expected.read_bytes(), env=env)
            for name in ('unitsplit', 'typeuse', 'bridgeuse'):
                source = (fixtures / (name + '.paslang')).read_text()
                source = re.sub(r'uses ([^;]+);', lambda m: 'uses ' +
                                ', '.join(reversed([v.strip() for v in m[1].split(',')])) + ';', source)
                path = folder / (name + '-reverse.paslang')
                path.write_text(source)
                binary = folder / (name + '-reverse')
                run(tag + '-' + name + '-reverse-compile', [compiler, *flags, '-o', binary, path], folder)
                run(tag + '-' + name + '-reverse-run', [*launch, binary], folder,
                    want=(fixtures / (name + '.out')).read_bytes(), env=stress)
            for name, message in [('duplicate', b'duplicate'), ('duplicatemember', b'duplicate'),
                                  ('typebad', b'does not descend')]:
                _, err = run(tag + '-' + name + '-reject', [compiler, *flags, '-c', '-o', folder / name,
                                                           fixtures / (name + '.paslang')], folder, code=1)
                assert message in err.lower(), (name, err)
            for generation, message in [(34, b'older than 1.2.400'), (35, b'older than 1.2.402'),
                                        (37, b'newer paslang (PASLANGI37)')]:
                stale = folder / ('format-' + str(generation))
                stale.mkdir()
                data = (folder / 'a.pi').read_bytes()
                (stale / 'a.pi').write_bytes(data.replace(b'PASLANGI36\n', f'PASLANGI{generation}\n'.encode(), 1))
                (stale / 'a.o').write_bytes((folder / 'a.o').read_bytes())
                _, err = run(tag + '-format-' + str(generation), [compiler, '-target', target, '-cpu', cpu,
                    '-Fu', stale, '-Fu', core, '-o', stale / 'probe', fixtures / 'programsplit.paslang'],
                    stale, code=1)
                assert message in err and b'compile a again' in err, err
            # Implementation-only changes keep the interface identical while
            # rebuilding its object and observing the changed return value.
            changed = folder / 'implementation'
            changed.mkdir()
            source = (fixtures / 'a.paslang').read_text()
            assert source.count('Result := 3;') == 1
            path = changed / 'a.paslang'
            path.write_text(source.replace('Result := 3;', 'Result := 4;'))
            run(tag + '-implementation', [compiler, '-target', target, '-cpu', cpu, '-inline', str(inline),
                '-Fu', core, '-c', '-o', changed / 'a', path], changed)
            assert (changed / 'a.pi').read_bytes() == (folder / 'a.pi').read_bytes()
            assert (changed / 'a.o').read_bytes() != (folder / 'a.o').read_bytes()
            binary = changed / 'client'
            run(tag + '-implementation-client', [compiler, '-target', target, '-cpu', cpu,
                '-Fu', changed, '-Fu', core, '-o', binary, fixtures / 'programsplit.paslang'], changed)
            run(tag + '-implementation-run', [*launch, binary], changed, want=b'4 7\n', env=stress)
            # Execute the actual constructors, including mixed case, repeated
            # underscores, empty owners and qualified-type dots.
            run(tag + '-ast-unit', [compiler, *flags, '-c', '-o', folder / 'pasast',
                                   repo / 'src/compiler/pasast.paslang'], folder)
            binary = folder / 'constructors'
            run(tag + '-constructors-compile', [compiler, *flags, '-o', binary,
                                               fixtures / 'constructors.paslang'], folder)
            out, _ = run(tag + '-constructors-run', [*launch, binary], folder, env=stress)
            constructors(out)
            print('symbols:', tag, 'passed', flush=True)
    state['ok'] = True
finally:
    state['complete'] = True
    save()
assert state['ok']
print('symbols:', len(state['commands']), 'commands passed; evidence:', work)
