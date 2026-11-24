#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Check both RemoveAll APIs when the parent disappears after unlink."""

from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


PROGRAM = """program rmallparent;
uses sysutils;
var
  error: TSysError;
  ok: Boolean;
begin
  ok := TryRemoveAllAt(CurrentDirectoryHandle, 'parent/child', error);
  WriteLn(ok, ' ', error.Code, ' ', error.Operation, ' ', error.Path);
  SetLastOSError(13);
  ok := RemoveAll('parent/child');
  WriteLn(ok, ' ', GetLastOSError);
end.
"""


def check(compiler, units, target, launch, work, source):
    work.mkdir()
    child = work / 'parent/child'
    child.mkdir(parents=True)
    unit = work / 'sysutils'
    variant = unit.with_suffix('.paslang')
    variant.write_text(source)
    program = work / 'rmallparent.paslang'
    program.write_text(PROGRAM)
    binary = program.with_suffix('')
    command = [compiler, '-target', target, '-cpu', 'base']
    subprocess.run([*command, '-c', '-Fu', units, '-o', unit, variant],
                   check=True, timeout=120)
    subprocess.run([*command, '-Fu', work, '-Fu', units, '-o', binary, program],
                   check=True, timeout=60)
    if str(unit.with_suffix('.o')) not in binary.with_suffix('.link').read_text().splitlines():
        raise SystemExit(f'{target}: the test did not link the private sysutils variant')
    got = subprocess.run([*launch, binary], cwd=work, capture_output=True, timeout=20)
    expected = b'True 0 remove parent/child\nTrue 0\n'
    if (got.returncode, got.stdout, got.stderr) != (0, expected, b'') or not child.is_dir():
        raise SystemExit(f'{target}: parent open expected {expected!r}, got '
                         f'{got.returncode}, {got.stdout!r}, {got.stderr!r}')


def main():
    if len(sys.argv) != 4:
        raise SystemExit('usage: check_rmall_parent.py compiler builddir qemu')
    compiler, build, qemu = (Path(arg).resolve() for arg in sys.argv[1:])
    root = Path(__file__).resolve().parent.parent
    source = (root / 'src/rtl/sysutils.paslang').read_text()
    opening = 'TryOpenFileAt(DirectoryHandle, parentPath, ODirectory, 0, parent, Error)'
    if source.count(opening) != 1:
        raise SystemExit('RemoveAll parent open fixture does not match')
    # The initial unlink returns EISDIR on the real child. Only the
    # subsequent parent open sees a missing directory and returns ENOENT.
    source = source.replace(opening, opening.replace('parentPath', "parentPath + 'missing/'"))
    with TemporaryDirectory(prefix='rmall-parent-', dir=build) as temporary:
        work = Path(temporary)
        check(compiler, build, 'amd64', [], work / 'amd64', source)
        check(compiler, build / 'a64', 'arm64', [qemu, '-cpu', 'cortex-a53'], work / 'arm64', source)
    print('RemoveAll parent disappearance checked on amd64 and arm64')


if __name__ == '__main__':
    main()
