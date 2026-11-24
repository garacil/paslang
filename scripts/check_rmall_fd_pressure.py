#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Exercise RemoveAll when Linux refuses another directory descriptor."""

import os
from pathlib import Path
import resource
import subprocess
import sys
from tempfile import TemporaryDirectory


def limit_descriptors():
    _, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, hard))


def check(compiler, units, source, temp, target, launcher):
    work = temp / target
    work.mkdir()
    binary = work / 'remove-tree'
    subprocess.run([compiler, '-target', target, '-cpu', 'base', '-Fu', units,
                    '-o', binary, source], check=True, timeout=60)

    marker = work / 'outside'
    marker.write_text('untouched\n')
    tree = work / 'tree'
    tree.mkdir()
    fd = os.open(tree, os.O_DIRECTORY)
    try:
        for _ in range(200):
            os.mkdir('d', dir_fd=fd)
            child = os.open('d', os.O_DIRECTORY, dir_fd=fd)
            os.close(fd)
            fd = child
        os.symlink(marker, 'external', dir_fd=fd)
    finally:
        os.close(fd)

    result = subprocess.run([*launcher, binary, tree],
                            env=dict(os.environ, PASLANG_MAXPROCS='1'),
                            preexec_fn=limit_descriptors, capture_output=True, timeout=30)
    if ((result.returncode, result.stdout, result.stderr) != (0, b'', b'')
            or tree.exists() or marker.read_text() != 'untouched\n'):
        raise SystemExit(f'{target}: removal under RLIMIT_NOFILE=32 failed: {result}')


def main():
    if len(sys.argv) != 4:
        raise SystemExit('usage: check_rmall_fd_pressure.py compiler builddir qemu')
    compiler, build, qemu = (Path(arg).resolve() for arg in sys.argv[1:])
    source = Path(__file__).resolve().parent / 'bench_rmall' / 'rm.paslang'
    with TemporaryDirectory(prefix='rmall-fd-pressure-', dir=build) as directory:
        temp = Path(directory)
        check(compiler, build, source, temp, 'amd64', [])
        check(compiler, build / 'a64', source, temp, 'arm64', [qemu, '-cpu', 'cortex-a53'])
    print('RemoveAll passed real descriptor pressure and preserved the external symlink target')


if __name__ == '__main__':
    main()
