#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Exact const/capture refusals for select channels, values, bodies and destinations."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('compiler', type=Path)
    parser.add_argument('build', type=Path)
    parser.add_argument('qemu', type=Path, nargs='?')
    parser.add_argument('--host-arm64', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    compiler, build = args.compiler.resolve(), args.build.resolve()
    prefix = [str(compiler)]
    if args.host_arm64:
        if args.qemu is None:
            parser.error('--host-arm64 requires qemu')
        prefix = [str(args.qemu.resolve()), '-cpu', 'max', *prefix]
    cases = json.loads((root / 'testdata/selectwalkbad/expected.json').read_text())
    if len(cases) != 9:
        raise SystemExit('select diagnostics: expected nine refusal fixtures')
    output = build / 'select-diagnostics'
    output.mkdir(exist_ok=True)
    checked = 0
    for target in (('arm64',) if args.host_arm64 else ('amd64', 'arm64')):
        sdk = build / 'a64' if target == 'arm64' else build
        environment = dict(os.environ, PASLANG_LIB=str(sdk))
        for inline in (0, 40):
            for name, message in cases.items():
                source = root / 'testdata/selectwalkbad' / (name + '.paslang')
                destination = output / (name + '-' + target + '-i' + str(inline))
                result = subprocess.run([*prefix, '-target', target, '-cpu', 'base',
                    '-inline', str(inline), '-Fu', str(sdk), '-o', str(destination), str(source)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment, timeout=60)
                expected = ('paslangc: ' + message + ' in ' + str(source) + '\n').encode()
                if result.returncode != 1 or result.stdout or result.stderr != expected:
                    raise SystemExit('select diagnostics: unexpected refusal for ' + name +
                        ' ' + target + ' inline ' + str(inline) + ': status ' + str(result.returncode) +
                        ', stdout ' + repr(result.stdout) + ', stderr ' + repr(result.stderr))
                checked += 1
    print('select diagnostics: ' + str(checked) + ' exact const/capture refusals')


if __name__ == '__main__':
    main()
