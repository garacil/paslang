#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Check lexical shadowing of routines by local variables and parameters."""

from pathlib import Path
import subprocess
import sys
from tempfile import mkdtemp

UNIT = """unit localnames;
interface
type TTransform = function(N: Integer): Integer;
function Total(N: Integer): Integer;
function Twice(const Total: Integer): Integer;
function Apply(Total: TTransform): Integer;
implementation
function Total(N: Integer): Integer;
begin
  Result := N + 7;
end;

function Twice(const Total: Integer): Integer;
  function Captured: Integer;
  begin
    Result := Total * 2;
  end;
begin
  Result := Captured;
end;

function Apply(Total: TTransform): Integer;
begin
  Result := Total(10);
end;
end.
"""

PROGRAM = """program scopeclient;
uses localnames;
function Bump(N: Integer): Integer;
begin
  Result := N + 1;
end;
begin
  WriteLn(Twice(21), ' ', Total(5), ' ', localnames.Total(6), ' ', Apply(@Bump));
end.
"""

RESULT_CONFLICT = """program resultconflict;
function Count(Count: Integer): Integer;
begin
  Result := Count;
end;
begin
end.
"""


def run(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, timeout=90)


def main():
    compiler, build, qemu = (Path(arg).resolve() for arg in sys.argv[1:])
    fixtures = Path(__file__).resolve().parents[1] / 'testdata'
    root = Path(mkdtemp(prefix='routine-shadow-', dir=build))
    for target, units in [('amd64', build), ('arm64', build / 'a64')]:
        work = root / target
        work.mkdir()
        unit = work / 'localnames.paslang'
        program = work / 'scopeclient.paslang'
        conflict = work / 'resultconflict.paslang'
        noncallable = work / 'noncallable.paslang'
        unit.write_text(UNIT, encoding='utf-8')
        program.write_text(PROGRAM, encoding='utf-8')
        conflict.write_text(RESULT_CONFLICT, encoding='utf-8')
        noncallable.write_text(UNIT.replace('unit localnames;', 'unit noncallable;')
                               .replace('Result := Total * 2;', 'Result := Total(10);'),
                               encoding='utf-8')
        cli = [compiler, '-target', target, '-cpu', 'base', '-Fu', units, '-Fu', work]
        if target == 'amd64':
            launch = []
        else:
            launch = [qemu, '-cpu', 'cortex-a53']

        built = run([*cli, '-c', '-o', work / 'localnames', unit], work)
        assert built.returncode == 0, (target, built.stdout, built.stderr)
        for source, expected in [(program, b'42 12 13 11\n'),
                                 (fixtures / 'dupwhere/paramproc.paslang', b'4x\n'),
                                 (fixtures / 'dupwhere/nestprocvar.paslang', b'2\n1\n')]:
            app = work / source.stem
            built = run([*cli, '-o', app, source], work)
            assert built.returncode == 0, (target, source, built.stdout, built.stderr)
            result = run([*launch, app], work)
            assert (result.returncode, result.stdout, result.stderr) == (0, expected, b''), (
                target, source, result.returncode, result.stdout, result.stderr)
        for source, expected in [
            (conflict, b'duplicate identifier Count (it is the function)'),
            (noncallable, b'unknown procedure Total'),
            (fixtures / 'dupwhere/varproc.paslang', b'duplicate identifier Show (a routine of the name)'),
            (fixtures / 'scopebad/varproc.paslang',
             b'duplicate identifier Part (the routine has a variable or a parameter of the name)'),
        ]:
            flags = ['-c'] if source == noncallable else []
            refused = run([*cli, *flags, '-o', work / 'rejected', source], work)
            diagnostics = refused.stdout + refused.stderr
            assert refused.returncode == 1 and expected in diagnostics, (target, source, diagnostics)
        print(f'ok routine shadowing {target}')


if __name__ == '__main__':
    main()
