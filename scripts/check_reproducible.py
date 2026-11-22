#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Check byte-identical programs and units and verify their inputs with sha256sum."""

import os
from pathlib import Path
import subprocess
import sys
from tempfile import mkdtemp

UNIT = """unit pathunit;
interface
function Answer: Integer;
implementation
function Answer: Integer;
begin
  Result := 42;
end;
end.
"""

PROGRAM = r"""program repropath;
uses pathunit;
procedure PrintAnswer;
var
  value: Integer;
begin
  value := Answer;
  asm amd64
    .include "asm\\ inputs/part #$.inc"
  end;
  asm arm64
    .include "asm\\ inputs/part #$.inc"
  end;
  WriteLn(value);
end;
begin
  PrintAnswer;
end.
"""

STANDALONE = """program standalonedemo;
begin
  WriteLn('paslang');
end.
"""

ASSEMBLY = r"""  .warning "reproducibility fixture warning"
  .pushsection .rodata.repropath
  .incbin "asm\\ inputs/payload #$.bin"
  .popsection
"""
INCLUDE = Path(r'asm\ inputs/part #$.inc')
PAYLOAD = INCLUDE.with_name('payload #$.bin')
STANDALONE_SOURCE = Path('src/standalone\\part\r\n.paslang')


def run(args, cwd, env=None, *, check=True):
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, timeout=120)
    if check and result.returncode != 0:
        raise SystemExit(f'{args!r} failed in {cwd}:\n{result.stderr.decode(errors="replace")}')
    return result


def checksum_path(path):
    return (os.fsencode(path).replace(b'\\', b'\\\\')
            .replace(b'\r', b'\\r').replace(b'\n', b'\\n'))


def verify_inputs(tree, name, output, included, excluded):
    manifest = tree / name
    manifest.write_bytes(output)
    run(['sha256sum', '--check', '--strict', manifest], tree.parent)
    for path in included:
        escaped = checksum_path(path)
        assert b'  ' + escaped + b'\n' in output, (name, 'missing', path)
    for path in excluded:
        escaped = checksum_path(path)
        assert b'  ' + escaped + b'\n' not in output, (name, 'unexpected', path)


def build_tree(compiler, units, tree, target, debug, variant):
    tree.mkdir()
    (tree / 'src').mkdir()
    (tree / INCLUDE.parent).mkdir()
    for path, data in {'src/main.paslang': PROGRAM.encode(),
                       'src/pathunit.paslang': UNIT.encode(),
                       STANDALONE_SOURCE: STANDALONE.encode(),
                       INCLUDE: ASSEMBLY.encode(),
                       PAYLOAD: b'\x00\x12\xff'}.items():
        (tree / path).write_bytes(data)
        stamp = 946684800 + variant * 400000000
        os.utime(tree / path, (stamp, stamp))
    root = tree.with_name(tree.name + ' alias')
    root.symlink_to(tree, target_is_directory=True)
    if variant == 0:
        root = '.'
    destination = tree / f'out {variant}: $\\ units'
    unit = destination / 'pathunit.paslang'
    app = destination / f'program-{variant}'
    independent = [compiler, '-target', target, '-cpu', 'base', '-tune', 'generic',
                   '-Fu', units]
    if debug:
        independent.append('-debug')
    flags = [*independent, '-trimpath', root, '-build-inputs', '-Fu', destination]
    env = dict(os.environ, TZ='UTC' if variant == 0 else 'Pacific/Kiritimati',
               LANG='C' if variant == 0 else 'C.UTF-8',
               SOURCE_DATE_EPOCH=str(stamp))
    source = tree / 'src/pathunit.paslang'
    unit_result = run([*flags, '-c', '-o', unit, source], tree, env)
    assert not unit_result.stderr, unit_result.stderr
    program = tree / 'src/main.paslang'
    app_result = run([*flags, '-o', app, program], tree, env)
    assert b'reproducibility fixture warning' in app_result.stderr, app_result.stderr
    prefix = '/usr/bin/' if target == 'amd64' else '/usr/bin/aarch64-linux-gnu-'
    assembler, linker = prefix + 'as', prefix + 'ld'
    verify_inputs(tree, 'unit.sha256', unit_result.stdout,
                  [compiler, assembler, source, units / 'pasnum.pi'],
                  [unit.with_suffix('.o'), unit.with_suffix('.s'), linker])
    verify_inputs(tree, 'program.sha256', app_result.stdout,
                  [compiler, assembler, linker, program, tree / INCLUDE, tree / PAYLOAD,
                   units / 'pasnum.o', unit.with_suffix('.pi'), unit.with_suffix('.o')],
                  [app.with_suffix('.o'), app.with_suffix('.s'), app])
    if variant == 1:
        # Check path-component boundaries and symlink resolution.
        outside = tree.with_name(tree.name + '-outside')
        outside.mkdir()
        (outside / program.name).write_bytes(program.read_bytes())
        alias = tree / 'outside.paslang'
        alias.symlink_to(outside / program.name)
        failure = run([*flags, '-o', destination / 'outside', alias], tree, env, check=False)
        assert failure.returncode == 1 and not failure.stdout, failure
        assert b'source is outside -trimpath root' in failure.stderr, failure.stderr

    for path, source_name in [(unit, b'src/pathunit.paslang'), (app, b'src/main.paslang')]:
        dwarf = run(['readelf', '--debug-dump=info,rawline', path.with_suffix('.o')], tree)
        assert not dwarf.stderr, dwarf.stderr
        assert source_name in dwarf.stdout, (path, source_name)
        assert b'DW_AT_comp_dir' not in dwarf.stdout, path
        assert os.fsencode(tree) not in path.with_suffix('.o').read_bytes(), path
    standalone = destination / f'standalone-{variant}'
    raw_path = destination / f'untrimmed-{variant}'
    source = tree / STANDALONE_SOURCE
    # Build from outside the root. GAS must not turn the logical DWARF
    # source name into an input relative to the compiler's directory.
    result = run([*independent, '-trimpath', tree.name, '-build-inputs',
                  '-o', standalone, source.relative_to(tree.parent)], tree.parent, env)
    verify_inputs(tree, 'standalone.sha256', result.stdout, [source],
                  [standalone.with_suffix('.s'), tree.parent / STANDALONE_SOURCE])
    run([*independent, '-o', raw_path, source], tree, env)
    artifacts = [app, app.with_suffix('.s'), app.with_suffix('.o'),
                 unit.with_suffix('.s'), unit.with_suffix('.o'), unit.with_suffix('.pi'),
                 standalone, standalone.with_suffix('.s'), standalone.with_suffix('.o')]
    return (app, standalone), artifacts, raw_path


def main():
    compiler, build, qemu = (Path(argument).resolve() for argument in sys.argv[1:])
    work = Path(mkdtemp(prefix='reproducible-', dir=build))
    print(f'Reproducibility evidence in {work}', flush=True)
    for target, units in [('amd64', build), ('arm64', build / 'a64')]:
        for debug in (False, True):
            label = f'{target}-{"debug" if debug else "plain"}'
            parent = work / label
            parent.mkdir()
            first_apps, first, first_raw = build_tree(
                compiler, units, parent / 'tree =one', target, debug, 0)
            second_apps, second, second_raw = build_tree(
                compiler, units, parent / 'second tree', target, debug, 1)
            for left, right in zip(first, second, strict=True):
                assert left.read_bytes() == right.read_bytes(), (left, right)
            assert first_raw.read_bytes() != second_raw.read_bytes(), label
            for apps, cpu in [(first_apps, 'cortex-a53'), (second_apps, 'max')]:
                launcher = [] if target == 'amd64' else [qemu, '-cpu', cpu]
                for app, output in zip(apps, [b'42\n', b'paslang\n'], strict=True):
                    assert run([*launcher, app], app.parent).stdout == output, app
            print(f'ok reproducible {label}')


if __name__ == '__main__':
    main()
