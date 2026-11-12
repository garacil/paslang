#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P595: implicit class values widen; narrowing requires an explicit cast.

Usage: check_class_values.py COMPILER BUILDDIR QEMU

The expected conversions follow the class/var-parameter contract, Go's
go/types/operand.go assignableTo and the Pascal reference. Invalid programs
only compile: no unsafe accepted program is run. Valid imported and forward
classes run normally, under GC stress, and on a single scheduler CPU.
"""
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
compiler, build, qemu = (Path(v).resolve() for v in sys.argv[1:])
fixtures = repo / 'testdata/classvalues'
work = Path(tempfile.mkdtemp(prefix='class-values-', dir=build))
inputs = [compiler, Path(__file__), *sorted(fixtures.iterdir())]
frozen = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
base = {k: v for k, v in os.environ.items() if not k.startswith('PASLANG_GC')}
stress = dict(base, PASLANG_GCVERIFY='1', PASLANG_GCSTRESS='1', PASLANG_GCPOISON='1')
single = ['taskset', '-c', str(min(os.sched_getaffinity(0)))]
state = {'ok': False, 'complete': False, 'inputs': frozen, 'commands': []}


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
    return err


prefix = '''program ClassReject;
type
  TBase = class N: Integer; end;
  TChild = class(TBase) Extra: Integer; end;
  TOther = class M: Integer; end;
  TAlias = TBase;
  THolder = record Item: TBase; end;
  TBox = class
    Item: TBase;
    procedure Take(V: TBase);
    procedure Put(V: TBase);
    property Prop: TBase write Put;
  end;
procedure TBox.Take(V: TBase); begin end;
procedure TBox.Put(V: TBase); begin Item := V end;
procedure Take(V: TBase); begin end;
procedure TakeConst(const V: TBase); begin end;
procedure TakeVar(var V: TBase); begin end;
procedure TakeOut(out V: TBase); begin V := nil end;
var B: TBase; C: TChild; O: TOther; Alias: TAlias;
  I: Integer; R: Double; F: Single; P: Pointer; Typed: ^TBase;
  H: THolder; Box: TBox; A: array[0..1] of TBase;
  D: array of TBase; M: map[Integer] of TBase; Ch: chan of TBase;
'''

# Each case fixes one invalid source/target conversion and a context.
bad = {
    'unrelated': ('B := O', 'does not go into'),
    'narrow': ('C := B', 'checked class cast'),
    'alias': ('Alias := O', 'does not go into'),
    'classinteger': ('I := B', 'does not go into'),
    'classdouble': ('R := B', 'does not go into'),
    'classsingle': ('F := B', 'does not go into'),
    'integerclass': ('B := I', 'does not go into'),
    'pointerclass': ('B := P', 'does not go into'),
    'typedpointerclass': ('B := Typed', 'does not go into'),
    'classtypedpointer': ('Typed := B', 'does not go into'),
    'classzero': ('B := 0', 'does not go into'),
    'valuearg': ('Take(O)', 'does not go into'),
    'constarg': ('TakeConst(O)', 'does not go into'),
    'narrowarg': ('TakeVar(C)', 'var parameter of type'),
    'outarg': ('TakeOut(C)', 'var parameter of type'),
    'field': ('H.Item := O', 'does not go into'),
    'objectfield': ('Box.Item := O', 'does not go into'),
    'method': ('Box.Take(O)', 'does not go into'),
    'property': ('Box.Prop := O', 'does not go into'),
    'array': ('A[0] := O', 'does not go into'),
    'slice': ('D[0] := O', 'does not go into'),
    'map': ('M[1] := O', 'does not go into'),
    'send': ('Send(Ch, O)', 'does not go into'),
}
extra = {
    'result': (prefix + 'function Bad: TBase;\nbegin Result := O end;\nbegin end.\n', 'does not go into'),
    'exitresult': (prefix + 'function Bad: TBase;\nbegin Exit(O) end;\nbegin end.\n', 'does not go into'),
    'forwardunrelated': ('''program ForwardReject;
type TBase = class N: Integer; end; TChild = class;
function Bad(C: TChild): TBase;
begin Result := C end;
type TChild = class M: Integer; end;
begin end.
''', 'does not go into'),
    'localforward': ('''program LocalForwardReject;
procedure Local;
type TBase = class N: Integer; end; TChild = class;
function Bad(C: TChild): TBase;
begin Result := C end;
type TChild = class M: Integer; end;
begin end;
begin end.
''', 'does not go into'),
}

save()
try:
    run('help-class-values', [compiler, '--help', 'types'], work)
    # Help goes to stdout; retain it alongside every other command's evidence.
    assert b'Implicit class values accept nil' in (work / 'help-class-values.stdout').read_bytes()
    for target, cpu in [('amd64', 'base'), ('amd64', 'native'),
                        ('arm64', 'base'), ('arm64', 'max')]:
        for inline in (0, 40):
            tag = f'{target}-{cpu}-{inline}'
            folder = work / tag
            folder.mkdir()
            core = build / ('a64' if target == 'arm64' else '')
            flags = ['-target', target, '-cpu', cpu, '-inline', str(inline),
                     '-Fu', folder, '-Fu', core]
            launch = [qemu, '-cpu', 'cortex-a53' if cpu == 'base' else 'max'] if target == 'arm64' else []
            for name in ('classbase', 'classderived'):
                run(tag + '-' + name, [compiler, *flags, '-c', '-o', folder / name,
                                       fixtures / (name + '.paslang')], folder)
            for name in ('values', 'forward'):
                binary = folder / name
                run(tag + '-' + name + '-compile', [compiler, *flags, '-o', binary,
                                                   fixtures / (name + '.paslang')], folder)
                for mode, env, affinity in [('normal', base, []), ('stress', stress, []),
                                             ('single', stress, single)]:
                    run(tag + '-' + name + '-' + mode, [*affinity, *launch, binary], folder,
                        env=env, want=(fixtures / (name + '.out')).read_bytes())
            sources = {name: (prefix + 'begin\n  ' + expr + ';\nend.\n', message)
                       for name, (expr, message) in bad.items()}
            sources.update(extra)
            for name, (source, message) in sources.items():
                path = folder / (name + '.paslang')
                path.write_text(source)
                err = run(tag + '-reject-' + name, [compiler, *flags, '-c', '-o', folder / name, path],
                          folder, code=1)
                assert message.encode() in err and b' at ' in err, (name, err)
                failing = ('Result := O' if name == 'result' else 'Exit(O)' if name == 'exitresult'
                           else 'Result := C' if name in ('forwardunrelated', 'localforward')
                           else bad[name][0])
                expected_line = next(i for i, line in enumerate(source.splitlines(), 1) if failing in line)
                position = re.search(rb' at ([0-9]+):([0-9]+)', err)
                assert position and int(position[1]) == expected_line, (name, expected_line, err)
            print('ok class-values', tag, flush=True)
    state['ok'] = True
finally:
    state['complete'] = True
    save()
print('class-values:', len(state['commands']), 'commands; evidence', work)
