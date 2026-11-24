#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Check the Curve25519 field and Ed25519 scalar paths against Python."""

import base64
from pathlib import Path
import random
import subprocess
import sys
from tempfile import TemporaryDirectory


FIELD_PROGRAM = """
program field25519check;
uses sysutils, passtr, pasfield25519;
var
  a, b, c: TFe;
  op, rounds, i, rows: Integer;
function ReadIntegerLine: Integer;
var text: string;
begin
  ReadLn(text);
  Result := StrToInt(text);
end;

begin
  rows := ReadIntegerLine;
  while rows > 0 do
  begin
    op := ReadIntegerLine;
    rounds := ReadIntegerLine;
    for i := 0 to 4 do a[i] := ReadIntegerLine;
    for i := 0 to 4 do b[i] := ReadIntegerLine;
    case op of
      0: FeMul(c, a, b);
      1: begin FeMul(a, a, b); c := a; end;
      2: begin FeMul(b, a, b); c := b; end;
      3: FeSquareN(c, a, rounds);
      4: begin FeSquareN(a, a, rounds); c := a; end;
    end;
    for i := 0 to 4 do
      if (c[i] < 0) or (c[i] >= (1 shl 52)) then Halt(2);
    WriteLn(LowerCase(Hex(FeBytes(c))));
    Dec(rows);
  end;
end.
"""


SCALAR_INTERFACE = """
function TestScalarReduce(const Text: string): string;
function TestScalarMultiplyAdd(const A, B, C: string): string;
"""

SCALAR_IMPLEMENTATION = """
function TestScalarReduce(const Text: string): string;
var s: TScalar;
begin
  ScalarFromBytes(Text, s);
  Result := ScalarBytes(s);
end;

function TestScalarMultiplyAdd(const A, B, C: string): string;
var left, right, addend, s: TScalar;
    i: Integer;
begin
  for i := 0 to 31 do
  begin
    left[i] := Ord(A[i + 1]);
    right[i] := Ord(B[i + 1]);
    addend[i] := Ord(C[i + 1]);
  end;
  ScalarMultiplyAdd(left, right, addend, s);
  Result := ScalarBytes(s);
end;

"""

SCALAR_PROGRAM = """
program scalar25519check;
uses sysutils, pascodec, passtr, pased25519;
var
  a, b, c, resultBytes: string;
  op, rows: Integer;

function ReadBytes: string;
var line: string;
begin
  ReadLn(line);
  if not Base64Decode(line, False, True, Result) then Halt(1);
end;

function ReadIntegerLine: Integer;
var text: string;
begin
  ReadLn(text);
  Result := StrToInt(text);
end;

begin
  rows := ReadIntegerLine;
  while rows > 0 do
  begin
    op := ReadIntegerLine;
    a := ReadBytes;
    if op = 0 then
      resultBytes := TestScalarReduce(a)
    else
    begin
      b := ReadBytes;
      c := ReadBytes;
      resultBytes := TestScalarMultiplyAdd(a, b, c);
    end;
    WriteLn(LowerCase(Hex(resultBytes)));
    Dec(rows);
  end;
end.
"""


def field_fixtures():
    modulus = (1 << 255) - 19
    highest = (1 << 52) - 1
    mask = (1 << 51) - 1
    rng = random.Random(25519)
    limbs = [(0,) * 5, (1, 0, 0, 0, 0), (mask - 18, mask, mask, mask, mask),
             (mask,) * 5, (highest,) * 5, (highest, 0, highest, 0, highest)]
    limbs += [tuple(rng.randrange(1 << 52) for _ in range(5)) for _ in range(72)]
    rows = []
    expected = []

    def field_value(words):
        return sum(word << (51 * i) for i, word in enumerate(words))

    for i, a in enumerate(limbs):
        b = limbs[-i - 1]
        x, y = field_value(a), field_value(b)
        for operation in range(3):
            rows.append((operation, 0, *a, *b))
            expected.append((x * y % modulus).to_bytes(32, 'little').hex())
        for rounds in (-1, 0, 1, 2, 127, 128, 129, 256):
            result = pow(x, 1 << max(0, rounds), modulus).to_bytes(32, 'little').hex()
            for operation in (3, 4):
                rows.append((operation, rounds, *a, *b))
                expected.append(result)
    data = '\n'.join(str(value) for row in rows for value in row)
    return f'{len(rows)}\n{data}\n'.encode(), expected


def scalar_fixtures():
    order = (1 << 252) + 27742317777372353535851937790883648493
    limit = 1 << 512
    rng = random.Random(2 * 25519)
    edges = [0, 1, order - 1, order, order + 1, 2 * order - 1, 2 * order,
             (1 << 256) - 1, (1 << 256), (limit // order) * order, limit - 1]
    values = edges + [rng.randrange(limit) for _ in range(256)]
    rows = []
    expected = []

    def wire(n, length):
        return base64.b64encode(n.to_bytes(length, 'little')).decode()

    for n in values:
        rows.append(f'0\n{wire(n, 32 if n < 1 << 256 else 64)}')
        expected.append((n % order).to_bytes(32, 'little').hex())
    max_word = (1 << 256) - 1
    for a, b, c in [(0, 0, 0), (max_word, max_word, max_word)] + [
            tuple(rng.getrandbits(256) for _ in range(3)) for _ in range(128)]:
        rows.append('1\n' + '\n'.join(wire(n, 32) for n in (a, b, c)))
        expected.append(((a * b + c) % order).to_bytes(32, 'little').hex())
    return ('\n'.join([str(len(rows)), *rows]) + '\n').encode(), expected


def check(binary, runner, fixtures):
    data, expected = fixtures
    got = subprocess.run([*runner, binary], input=data, capture_output=True, timeout=90)
    if got.returncode or got.stderr:
        raise SystemExit(f'{binary.name}: comparison failed: {got.stderr!r}')
    actual = got.stdout.decode().splitlines()
    if len(actual) != len(expected):
        raise SystemExit(f'{binary.name}: got {len(actual)} results, wanted {len(expected)}')
    for i, (result, want) in enumerate(zip(actual, expected)):
        if result != want:
            raise SystemExit(f'{binary.name}: case {i}: got {result}, wanted {want}')
    print(f'{binary.name}: {len(actual)} results match Python')


def check_field_dispatch(compiler, build, work, source):
    kernels = {
        'base': {'femulbase', 'fesquarenbase'},
        'bmi2': {'femulcpu', 'fesquareblockcpu'},
    }
    names = kernels['base'] | kernels['bmi2']
    for cpu, expected in kernels.items():
        output = work / f'field-dispatch-{cpu}'
        subprocess.run([compiler, '-target', 'amd64', '-cpu', cpu, '-c',
                        '-Fu', build, '-o', output, source], timeout=60, check=True)
        assembly = output.with_suffix('.s').read_text()
        emitted = {name for name in names if f'_{name}:\n' in assembly}
        if emitted != expected or 'rt_cpuhas' in assembly or 'rt_cpufeat' in assembly:
            raise SystemExit(f'{cpu}: expected only {sorted(expected)}, found {sorted(emitted)}')
        if ('  mulxq ' in assembly) != (cpu == 'bmi2'):
            raise SystemExit(f'{cpu}: wrong multiply instruction')
    print('Curve25519 base and BMI2 kernels selected at compile time')


def main():
    if len(sys.argv) != 4:
        raise SystemExit('usage: check_curve25519.py compiler builddir qemu')
    compiler, build, qemu = (Path(arg).resolve() for arg in sys.argv[1:])
    field = field_fixtures()
    scalars = scalar_fixtures()
    root = Path(__file__).resolve().parent.parent
    original = (root / 'src/lib/pased25519.paslang').read_text()
    assert original.endswith('end.\n')
    scalar_unit = original.removesuffix('end.\n').replace(
        '\nimplementation\n', SCALAR_INTERFACE + '\nimplementation\n', 1)
    scalar_unit += SCALAR_IMPLEMENTATION + 'end.\n'
    profiles = [
        ('amd64', 'native', build, []),
        ('amd64', 'base', build, []),
        ('arm64', 'max', build / 'a64', [qemu, '-cpu', 'max']),
        ('arm64', 'base', build / 'a64', [qemu, '-cpu', 'cortex-a53']),
    ]
    with TemporaryDirectory(prefix='field25519-', dir=build) as temp:
        work = Path(temp)
        check_field_dispatch(compiler, build, work, root / 'src/lib/pasfield25519.paslang')
        field_source = work / 'field25519check.paslang'
        field_source.write_text(FIELD_PROGRAM)
        scalar_source = work / 'scalar25519check.paslang'
        scalar_source.write_text(SCALAR_PROGRAM)
        for target, cpu, units, runner in profiles:
            name = f'{target}-{cpu}'
            binary = work / f'{name}-field'
            command = [compiler, '-target', target, '-cpu', cpu]
            subprocess.run([*command, '-Fu', units, '-o', binary, field_source],
                           timeout=60, check=True)
            check(binary, runner, field)

            variant = work / name
            variant.mkdir()
            unit = variant / 'pased25519.paslang'
            unit.write_text(scalar_unit)
            subprocess.run([*command, '-c', '-Fu', units, '-o', unit.with_suffix(''), unit],
                           timeout=60, check=True)
            binary = work / f'{name}-scalar'
            subprocess.run([*command, '-Fu', variant, '-Fu', units, '-o', binary, scalar_source],
                           timeout=60, check=True)
            if str(unit.with_suffix('.o')) not in binary.with_suffix('.link').read_text().splitlines():
                raise SystemExit(f'{binary.name}: did not link the scalar test unit')
            check(binary, runner, scalars)


if __name__ == '__main__':
    main()
