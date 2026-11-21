#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Force the Argon2d lane schedule from P455 on both architectures."""

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise SystemExit(f'Argon2 barrier test needs updating for {old!r}')
    return text.replace(old, new)


def delayed_wake(source):
    interface, implementation = source.split('\nimplementation\n', 1)
    first = implementation.index('procedure PasWaitGroupAdd(')
    last = implementation.index('procedure PasWaitGroupDone(', first)
    wake = implementation[first:last]
    wake = replace_once(wake, '  g, n: Integer;', '  g, n: Integer;\n  firstZero: Boolean;')
    wake = replace_once(wake, '  SpinLock(@W.Spin);', '''  firstZero := AtomicCas(@Argon2Barrier, 0, 1);
  if firstZero then
    while AtomicAdd(@W.Head, 0) = 0 do
      Yield;
  SpinLock(@W.Spin);''')
    wake = replace_once(wake, '    g := QWake1(@W.Head);\n    while', '''    g := QWake1(@W.Head);
    if firstZero and (g <> 0) and (AtomicAdd(@W.Count, 0) <> 0) then
      Halt(47);
    while''')
    wake = replace_once(wake, '  SpinUnlock(@W.Spin);', '''  SpinUnlock(@W.Spin);
  if firstZero then
    AtomicExchange(Argon2Barrier, 2);''')
    probe = '''var Argon2Barrier: Integer;

function Argon2BarrierObserved: Boolean;
begin
  Result := AtomicAdd(@Argon2Barrier, 0) = 2;
end;

'''
    prefix = interface + '\nimplementation\n' + implementation[:first] + probe
    suffix = implementation[last:]
    broken = replace_once(wake, '  if AtomicAdd(@W.Count, 0) = 0 then', '  if True then')
    return prefix + wake + suffix, prefix + broken + suffix


def held_lane(source):
    segment = 'procedure Segment(A: TArgon; N, Slice, Lane: Integer);'
    # Keep the private instrumentation out of pasroutines.pi so the
    # already-built library units can still use the original interface.
    probe = '''function Argon2BarrierObserved: Boolean;
begin
  asm amd64 (Result: out rax)
    call p_f.11_pasroutines21_argon2barrierobserved
  end;
  asm arm64 (Result: out x0)
    bl p_f.11_pasroutines21_argon2barrierobserved
  end;
end;

'''
    source = replace_once(source, segment, probe + segment)
    source = replace_once(source, '  indep: Boolean;\nbegin\n  for i := 0 to 127 do', '''  indep: Boolean;
begin
  if (N = 0) and (Slice = 1) and (Lane = 0) then
    while not Argon2BarrierObserved do
      Yield;
  for i := 0 to 127 do''')
    return replace_once(source, '      a.Wg.Wait;', '''      if (n = 0) and (slice = 0) then
        while AtomicAdd(PInt64(@a.Wg), 0) <> 0 do
          Yield;
      a.Wg.Wait;''')


PROGRAM = """program argon2barrier;
uses argon2;
begin
  WriteLn(Hex(Argon2Raw(Argon2d, StringOfChar(#1, 32), StringOfChar(#2, 16),
    StringOfChar(#3, 8), StringOfChar(#4, 12), 3, 32, 4, 32)));
end.
"""


def check(compiler, build, qemu):
    root = Path(__file__).resolve().parent.parent
    waitgroup = (root / 'src/lib/pasroutines.paslang').read_text()
    guarded, unguarded = delayed_wake(waitgroup)
    argon2 = held_lane((root / 'src/lib/argon2.paslang').read_text())
    golden = (root / 'testdata/argon2kat.out').read_text().splitlines()
    expected, = (row.split(': ', 1)[1].strip().encode() + b'\n'
                 for row in golden if row.startswith('argon2d kat:'))
    with TemporaryDirectory(prefix='argon2-barrier-', dir=build) as tmp:
        for target, units, launch in (('amd64', build, []), ('arm64', build / 'a64', [qemu])):
            for name, source, status, output in (('guarded', guarded, 0, expected),
                                                 ('unguarded', unguarded, 47, b'')):
                stage = Path(tmp) / target / name
                stage.mkdir(parents=True)
                (stage / 'pasroutines.paslang').write_text(source)
                (stage / 'argon2.paslang').write_text(argon2)
                (stage / 'probe.paslang').write_text(PROGRAM)
                flags = [compiler, '-target', target, '-cpu', 'base',
                         '-Fu', str(stage), '-Fu', str(units)]
                for build_name in ('pasroutines', 'argon2', 'probe'):
                    compile_unit = ['-c'] if build_name != 'probe' else []
                    command = flags + compile_unit + ['-o', str(stage / build_name),
                                                      str(stage / (build_name + '.paslang'))]
                    subprocess.run(command, check=True, timeout=120)
                env = dict(os.environ, PASLANG_GCSTRESS='1', PASLANG_GCVERIFY='1', PASLANG_GCPOISON='1')
                run = subprocess.run(launch + [str(stage / 'probe')], capture_output=True, env=env, timeout=60)
                if (run.returncode, run.stdout, run.stderr) != (status, output, b''):
                    raise SystemExit(f'Argon2 barrier {target} {name}: {run.returncode}, '
                                     f'{run.stdout!r}, {run.stderr!r}')
    print('Argon2d KAT matches on both targets and the old waitgroup wakes before a lane finishes')


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit('usage: check_argon2_barrier.py compiler builddir qemu')
    check(str(Path(sys.argv[1]).resolve()), Path(sys.argv[2]).resolve(), str(Path(sys.argv[3]).resolve()))
