#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P462: compiled unit cycles, public checksums and private dependencies.

Usage: check_unit_cycles.py COMPILER BUILDDIR QEMU

The Pascal Reference16.4 permits a cycle with an implementation edge.
Literal output fixes initialization/finalization order. Invalid interfaces
and stale objects only compile; accepted invalid programs are never run.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time

repo = Path(__file__).resolve().parents[1]
compiler, build, qemu = (Path(v).resolve() for v in sys.argv[1:])
fixtures = repo / 'testdata/unitcycles'
work = Path(tempfile.mkdtemp(prefix='unit-cycles-', dir=build))
inputs = [compiler, Path(__file__), repo / 'testdata/units/pisum.paslang',
          *sorted(fixtures.iterdir())]
frozen = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
base = {k: v for k, v in os.environ.items() if not k.startswith('PASLANG_GC')}
stress = dict(base, PASLANG_GCVERIFY='1', PASLANG_GCSTRESS='1', PASLANG_GCPOISON='1')
state = {'ok': False, 'complete': False, 'inputs': frozen, 'commands': [], 'interfaces': []}


def save():
    (work / 'status.json').write_text(json.dumps(state, indent=2) + '\n')


def run(label, args, folder, *, code=0, want=None, env=base):
    for name, digest in frozen.items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest, name
    row = {'label': label, 'argv': list(map(str, args)), 'cwd': str(folder),
           'exit': None, 'expected_exit': code, 'timeout': False,
           'environment': {k: v for k, v in env.items() if k.startswith('PASLANG_GC')}}
    state['commands'].append(row)
    save()
    started = time.monotonic()
    p = subprocess.Popen(row['argv'], cwd=folder, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, start_new_session=True)
    try:
        out, err = p.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        row['timeout'] = True
        os.killpg(p.pid, signal.SIGKILL)
        out, err = p.communicate(timeout=20)
    row.update(exit=p.returncode, seconds=time.monotonic() - started)
    (work / (label + '.stdout')).write_bytes(out)
    (work / (label + '.stderr')).write_bytes(err)
    save()
    assert not row['timeout'] and p.returncode == code, (label, str(work), err.decode(errors='replace'))
    assert want is None or out == want, (label, out, want)
    return out, err


def public(data):
    assert data.startswith(b'PASLANGI36\n')
    rows = data.splitlines(keepends=True)
    at = next((i for i, row in enumerate(rows) if row.startswith((b'DEP ', b'LINK '))), len(rows))
    return rows[1], b''.join(rows[2:at])


def unique_objects(binary, names):
    objects = [Path(v).name for v in shlex.split(binary.with_suffix('.link').read_text())
               if v.endswith('.o')]
    for name in names:
        assert objects.count(name + '.o') == 1, (binary, name, objects)


def copy_units(folder, destination, names):
    destination.mkdir()
    for name in names:
        for suffix in ('.pi', '.o'):
            shutil.copy2(folder / (name + suffix), destination / (name + suffix))


save()
try:
    for target, cpu in [('amd64', 'base'), ('amd64', 'native'),
                        ('arm64', 'base'), ('arm64', 'max')]:
        core = build / ('a64' if target == 'arm64' else '')
        launch = [qemu, '-cpu', 'cortex-a53' if cpu == 'base' else 'max'] if target == 'arm64' else []
        for inline in (0, 40):
            tag = f'{target}-{cpu}-{inline}'
            folder = work / tag
            folder.mkdir()

            def flags(directory):
                return ['-target', target, '-cpu', cpu, '-inline', str(inline),
                        '-Fu', directory, '-Fu', core]

            def unit(name, source, directory=folder, label=None):
                run(tag + '-' + (label or name), [compiler, *flags(directory), '-c',
                    '-o', directory / name, source], directory)

            unit('cyclestate', fixtures / 'cyclestate.paslang')
            unit('ca', fixtures / 'castub.paslang', label='ca-stub')
            ca_stub = (folder / 'ca.pi').read_bytes()
            unit('cb', fixtures / 'cb.paslang')
            control = folder / 'control'
            run(tag + '-control-compile', [compiler, *flags(folder), '-o', control,
                fixtures / 'both.paslang'], folder)
            run(tag + '-control-run', [*launch, control], folder,
                want=b'7 7 AB\nfinal ABba\n', env=stress)
            unit('ca', fixtures / 'ca.paslang', label='ca-implementation')
            ca_complete = (folder / 'ca.pi').read_bytes()
            assert public(ca_stub) == public(ca_complete), 'private uses changed the public interface'
            assert b'USE cb\n' not in ca_complete and b'LINK cb\n' in ca_complete
            assert b'LINK cyclestate\n' in ca_complete
            unit('cb', fixtures / 'cb.paslang', label='cb-recompiled')
            unit('wrapper', fixtures / 'wrapper.paslang')
            # A compatible old CA.pi must not conceal a new source
            # interface CA -> CB -> CA cycle.
            source_cycle = folder / 'source-public-ca.paslang'
            source_cycle.write_text('unit CA; interface uses CB; implementation end.\n')
            _, err = run(tag + '-source-public-cycle', [compiler, *flags(folder), '-c',
                '-o', folder / 'source-public-ca', source_cycle], folder, code=1)
            assert b'circular uses in interface' in err, err
            state['interfaces'].append({'profile': tag, 'stub_bytes': len(ca_stub),
                'complete_bytes': len(ca_complete), 'public_bytes': len(public(ca_complete)[1]),
                'same_public_body_and_checksum': True})
            save()
            for name in ('both', 'reverse', 'onlya', 'onlyb', 'wrapped'):
                binary = folder / name
                run(tag + '-' + name + '-compile', [compiler, *flags(folder), '-o', binary,
                    fixtures / (name + '.paslang')], folder)
                unique_objects(binary, ('ca', 'cb', 'cyclestate'))
                for mode, env in [('normal', base), ('stress', stress)]:
                    run(tag + '-' + name + '-' + mode, [*launch, binary], folder,
                        want=(fixtures / (name + '.out')).read_bytes(), env=env)

            # The private edge is in the middle of the public import walk:
            # UA USE UB, UB LINK UC, UC USE UA. Complete the entire public
            # stack before following UB's private edge, from all three roots.
            unit('ub', fixtures / 'ubstub.paslang', label='ub-stub')
            ub_stub = (folder / 'ub.pi').read_bytes()
            unit('ua', fixtures / 'ua.paslang')
            unit('uc', fixtures / 'uc.paslang')
            unit('ub', fixtures / 'ub.paslang', label='ub-implementation')
            assert public(ub_stub) == public((folder / 'ub.pi').read_bytes())
            unit('ua', fixtures / 'ua.paslang', label='ua-recompiled')
            for name in ('chaina', 'chainb', 'chainc'):
                binary = folder / name
                run(tag + '-' + name + '-compile', [compiler, *flags(folder), '-o', binary,
                    fixtures / (name + '.paslang')], folder)
                unique_objects(binary, ('ua', 'ub', 'uc', 'cyclestate'))
                for mode, env in [('normal', base), ('stress', stress)]:
                    run(tag + '-' + name + '-' + mode, [*launch, binary], folder,
                        want=(fixtures / (name + '.out')).read_bytes(), env=env)

            # Private units and their public dependencies add no names.
            for name, expression in [('function', 'FromA'), ('qualified', 'CB.FromA'),
                                     ('global', 'Events')]:
                path = folder / ('privacy-' + name + '.paslang')
                path.write_text('program Privacy; uses CA; begin WriteLn(' + expression + ') end.\n')
                _, err = run(tag + '-privacy-' + name, [compiler, *flags(folder), '-c',
                    '-o', folder / ('privacy-' + name), path], folder, code=1)
                assert b'unknown' in err.lower(), err

            # A new private unit, type and function still keep CA's public
            # metadata byte-identical, and its initialization is linked.
            unit('cyclehidden', fixtures / 'cyclehidden.paslang')
            hidden = folder / 'ca-hidden.paslang'
            text = (fixtures / 'ca.paslang').read_text()
            text = text.replace('uses CB, CycleState;', 'uses CB, CycleState, CycleHidden;')
            text = text.replace('CB.Plus(MakeValue) end', 'CB.Plus(MakeValue) + SecretValue - 11 end')
            hidden.write_text(text)
            unit('ca', hidden, label='ca-private-unit')
            assert public(ca_complete) == public((folder / 'ca.pi').read_bytes())
            assert b'TSecret' not in public((folder / 'ca.pi').read_bytes())[1]
            binary = folder / 'private-unit'
            run(tag + '-private-unit-compile', [compiler, *flags(folder), '-o', binary,
                fixtures / 'both.paslang'], folder)
            unique_objects(binary, ('ca', 'cb', 'cyclestate', 'cyclehidden'))
            run(tag + '-private-unit-run', [*launch, binary], folder,
                want=b'7 7 BHA\nfinal BHAahb\n', env=stress)
            for name, declaration, statement in [
                ('type', 'var Secret: TSecret; ', ''),
                ('function', '', 'WriteLn(SecretValue)'),
                ('qualified', '', 'WriteLn(CycleHidden.SecretValue)'),
                ('helper', 'var Number: Integer; ', 'Number := 1; WriteLn(Number.HiddenValue)')]:
                path = folder / ('private-unit-' + name + '.paslang')
                path.write_text('program Privacy; uses CA; ' + declaration + 'begin ' + statement + ' end.\n')
                _, err = run(tag + '-private-unit-reject-' + name, [compiler, *flags(folder), '-c',
                    '-o', folder / ('private-unit-reject-' + name), path], folder, code=1)
                expected = b'has no members: hiddenvalue' if name == 'helper' else b'unknown'
                assert expected in err.lower(), err
            private_stale = folder / 'stale-private'
            copy_units(folder, private_stale, ('ca', 'cb', 'cyclestate', 'cyclehidden', 'wrapper'))
            source = private_stale / 'hidden-changed.paslang'
            source.write_text((fixtures / 'cyclehidden.paslang').read_text().replace(
                'TSecret = record Hidden: Integer; end;',
                'TSecret = record Hidden, Extra: Integer; end;'))
            unit('cyclehidden', source, private_stale, 'private-interface-changed')
            _, err = run(tag + '-stale-private', [compiler, *flags(private_stale), '-o',
                private_stale / 'client', fixtures / 'onlya.paslang'], private_stale, code=1)
            assert b'was compiled against another cyclehidden.pi; compile ca again' in err.lower(), err
            unit('ca', fixtures / 'ca.paslang', label='ca-restored')
            assert (folder / 'ca.pi').read_bytes() == ca_complete

            # CA records its direct CB edge. CB must still reject a stale
            # private dependency reached through that edge.
            transitive = folder / 'stale-transitive'
            copy_units(folder, transitive, ('ca', 'cb', 'cyclestate', 'cyclehidden', 'wrapper'))
            source = transitive / 'cb-hidden.paslang'
            text = (fixtures / 'cb.paslang').read_text()
            assert text.count('uses CycleState;') == 1
            source.write_text(text.replace('uses CycleState;', 'uses CycleState, CycleHidden;'))
            unit('cb', source, transitive, 'cb-private-unit')
            assert public((transitive / 'cb.pi').read_bytes()) == public((folder / 'cb.pi').read_bytes())
            binary = transitive / 'client'
            run(tag + '-transitive-valid-compile', [compiler, *flags(transitive), '-o', binary,
                fixtures / 'both.paslang'], transitive)
            unique_objects(binary, ('ca', 'cb', 'cyclestate', 'cyclehidden'))
            run(tag + '-transitive-valid-run', [*launch, binary], transitive,
                want=b'7 7 HBA\nfinal HBAabh\n', env=stress)
            source = transitive / 'hidden-changed.paslang'
            source.write_text((fixtures / 'cyclehidden.paslang').read_text().replace(
                'TSecret = record Hidden: Integer; end;',
                'TSecret = record Hidden, Extra: Integer; end;'))
            unit('cyclehidden', source, transitive, 'transitive-interface-changed')
            _, err = run(tag + '-stale-transitive', [compiler, *flags(transitive), '-o',
                transitive / 'stale', fixtures / 'both.paslang'], transitive, code=1)
            assert b'was compiled against another cyclehidden.pi; compile cb again' in err.lower(), err

            # Reclassify the private CA -> CB edge as public, preserving a
            # valid checksum with the existing independent pisum utility.
            pisum = folder / 'pisum'
            run(tag + '-pisum-compile', [compiler, *flags(folder), '-o', pisum,
                repo / 'testdata/units/pisum.paslang'], folder)
            cycle = folder / 'public-cycle'
            copy_units(folder, cycle, ('ca', 'cb', 'cyclestate', 'wrapper'))
            data = (cycle / 'ca.pi').read_bytes()
            assert data.count(b'UNIT ca\n') == data.count(b'LINK cb\n') == 1
            data = data.replace(b'UNIT ca\n', b'UNIT ca\nUSE cb\n').replace(b'LINK cb\n', b'')
            (cycle / 'ca.pi').write_bytes(data)
            run(tag + '-public-cycle-checksum', [*launch, pisum, cycle / 'ca.pi'], cycle)
            # Keep every dependency checksum consistent too: cycle
            # rejection must not rely on a stale-import error.
            old_sum = public(ca_complete)[0].split()[1]
            new_sum = public((cycle / 'ca.pi').read_bytes())[0].split()[1]
            for dependent in ('cb', 'wrapper'):
                path = cycle / (dependent + '.pi')
                data = path.read_bytes()
                before_public = public(data)
                old_dep = b'DEP ca ' + old_sum + b'\n'
                assert data.count(old_dep) == 1
                path.write_bytes(data.replace(old_dep, b'DEP ca ' + new_sum + b'\n'))
                assert public(path.read_bytes()) == before_public
            cases = {
                'program-a': 'program P; uses CA; begin end.\n',
                'program-b': 'program P; uses CB; begin end.\n',
                'interface': 'unit Mode; interface uses CA; implementation end.\n',
                'implementation': 'unit Mode; interface implementation uses CA; end.\n',
                'link-only': 'program P; uses Wrapper; begin end.\n',
            }
            for name, text in cases.items():
                path = cycle / (name + '.paslang')
                path.write_text(text)
                _, err = run(tag + '-public-cycle-' + name, [compiler, *flags(cycle), '-c',
                    '-o', cycle / name, path], cycle, code=1)
                assert b'circular uses in interface' in err, err

            # Missing private units and stale public metadata fail before a
            # client can link or execute code against the wrong record ABI.
            missing = folder / 'missing-private'
            copy_units(folder, missing, ('ca', 'cyclestate'))
            source = missing / 'probe.paslang'
            source.write_text('program P; uses CA; begin WriteLn(Value) end.\n')
            _, err = run(tag + '-missing-private', [compiler, *flags(missing), '-o', missing / 'probe',
                source], missing, code=1)
            assert b'unit not compiled: cb' in err.lower(), err
            stale = folder / 'stale-public'
            copy_units(folder, stale, ('ca', 'cb', 'cyclestate', 'wrapper'))
            source = stale / 'ca-changed.paslang'
            source.write_text((fixtures / 'castub.paslang').read_text().replace(
                'TPair = record N: Integer; function Number: Integer; end;',
                'TPair = record N, Extra: Integer; function Number: Integer; end;'))
            unit('ca', source, stale, 'ca-interface-changed')
            assert public((stale / 'ca.pi').read_bytes()) != public(ca_complete)
            _, err = run(tag + '-stale-public', [compiler, *flags(stale), '-o', stale / 'client',
                fixtures / 'both.paslang'], stale, code=1)
            assert b'was compiled against another ca.pi; compile cb again' in err.lower(), err
            print('ok unit-cycles', tag, flush=True)
    state['ok'] = True
finally:
    state['complete'] = True
    save()
print('unit-cycles:', len(state['commands']), 'commands; evidence', work)
