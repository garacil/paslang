#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Check the fused literal prefix and integer output on both targets."""

import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import mkdtemp

VALUES = sorted({
    -(1 << 63), (1 << 63) - 1, 0,
    *(sign * (10**width + delta)
      for width in range(19) for delta in (-1, 0, 1) for sign in (-1, 1)),
})

PROGRAM = """program intprefix;
uses paslib;
var calls: Integer;

function Next(N: Int64): Int64;
begin
  Inc(calls);
  Result := N;
end;

function IntToStr(N: Int64): string;
begin
  Result := 'shadow';
end;

function Joined(N: Int64): string;
begin
  Result := 'item-' + paslib.IntToStr(Next(N));
end;

procedure Check(N: Int64);
begin
  WriteLn(Joined(N));
  WriteLn('x' + paslib.IntToStr(N));
  WriteLn('other-' + IntToStr(N));
  WriteLn(IntToStrWithPrefix('a' + #0 + 'ñ-', N));
  WriteLn(IntToStrWithPrefix('', N));
end;

procedure BigPrefix;
var
  prefix, value: string;
begin
  SetLength(prefix, 270000);
  FillChar(prefix[1], Length(prefix), Ord('a'));
  value := IntToStrWithPrefix(prefix, Low(Int64));
  value[1] := 'b';
  WriteLn(Length(value), ' ', prefix[1], ' ', value[1], ' ',
    Copy(value, 270001, 20));
end;

begin
"""
PROGRAM += ''.join(f'  Check({value});\n' for value in VALUES)
PROGRAM += "  BigPrefix;\n  WriteLn(calls);\nend.\n"
EXPECTED = ''.join(f'item-{n}\nx{n}\nother-shadow\na\x00ñ-{n}\n{n}\n'
                   for n in VALUES)
EXPECTED += f'270020 a b -9223372036854775808\n{len(VALUES)}\n'


def run(args, cwd, env=None):
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, timeout=120)
    assert result.returncode == 0, (args, result.returncode, result.stderr)
    assert not result.stderr, (args, result.stderr)
    return result.stdout


def main():
    compiler, build, qemu = (Path(arg).resolve() for arg in sys.argv[1:])
    work = Path(mkdtemp(prefix='int-prefix-', dir=build))
    source = work / 'intprefix.paslang'
    source.write_text(PROGRAM, encoding='utf-8')
    stress = dict(os.environ, PASLANG_GCVERIFY='1', PASLANG_GCSTRESS='1',
                  PASLANG_GCPOISON='1', PASLANG_MAXPROCS='1')
    for target, units in [('amd64', build), ('arm64', build / 'a64')]:
        launcher = [] if target == 'amd64' else [qemu, '-cpu', 'cortex-a53']
        instruction = 'call' if target == 'amd64' else 'bl'
        for limit in (0, 40):
            app = work / f'{target}-{limit}'
            run([compiler, '-target', target, '-cpu', 'base', '-inline', str(limit),
                 '-Fu', units, '-o', app, source], work)
            assembly = app.with_suffix('.s').read_text()
            match = re.search(r'^p_f\.0_6_joined:\n(.*?)^\s*\.cfi_endproc',
                              assembly, re.M | re.S)
            assert match, f'{app}: missing Joined routine'
            joined = match[1]
            original = f'{instruction} p_f.6_paslib8_inttostr\n'
            combined = f'{instruction} p_f.6_paslib18_inttostrwithprefix\n'
            assert (combined in joined) == (limit > 0), (app, joined)
            assert (original in joined) == (limit == 0), (app, joined)
            assert (f'{instruction} rt_concat\n' in joined) == (limit == 0), (app, joined)
            assert run([*launcher, app], work) == EXPECTED.encode(), app
            assert run([*launcher, app], work, stress) == EXPECTED.encode(), app
        print(f'ok literal integer prefix {target}, inline 0 and 40')


if __name__ == '__main__':
    main()
