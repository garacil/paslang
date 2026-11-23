#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Exercise startup diagnostics on real Linux guard and uname errors."""

import errno
import os
from pathlib import Path
import runpy
import subprocess
import sys
from tempfile import mkdtemp

ROOT = Path(__file__).resolve().parents[1]


def expect(command, status, stdout, stderr):
    result = subprocess.run(command, capture_output=True, timeout=30)
    if (result.returncode, result.stdout, result.stderr) != (status, stdout, stderr):
        raise SystemExit(
            f'{command}: expected {(status, stdout, stderr)!r}, got '
            f'{(result.returncode, result.stdout, result.stderr)!r}')


def check_target(compiler, units, work, target, launch, release, link_variant):
    program = work / target
    subprocess.run([compiler, '-target', target, '-cpu', 'base', '-Fu', units,
                    '-o', program, ROOT / 'testdata/hello.paslang'], check=True, timeout=30)
    expect([*launch, program], 0, b'hello world\n', b'')
    assembly = program.with_suffix('.s').read_text()
    marker = '\nrt_guard:\n'
    assert assembly.count(marker) == 1
    if target == 'amd64':
        tool_prefix = ''
        misalign = '  leaq 1(%rdi), %rdi\n'
        uname_arg = '  movq %rsp, %rdi\n'
        null_uname_arg = '  xorl %edi, %edi\n'
    else:
        tool_prefix = 'aarch64-linux-gnu-'
        misalign = '  add x0, x0, #1\n'
        uname_arg = '  mov x0, sp\n'
        null_uname_arg = '  mov x0, xzr\n'
    # Pass an unaligned address to the real madvise, leaving the error path intact.
    broken = assembly.replace(marker, marker + misalign)
    candidate = work / f'{target}-guard'
    link_variant(program, candidate, tool_prefix, broken)
    message = (f'paslang: madvise(MADV_GUARD_INSTALL) failed (errno {errno.EINVAL}): '
               'requires Linux 6.13 or later (running kernel: ')
    expect([*launch, candidate], 2, b'', f'{message}{release})\n'.encode())
    # Force a separate real error from uname to check that the original errno survives.
    before, guard_failure = broken.split('\nrt_guardfail:\n', 1)
    handler, after = guard_failure.split('\nrt_gconstack:\n', 1)
    assert handler.count(uname_arg) == 1
    handler = handler.replace(uname_arg, null_uname_arg)
    without_release = work / f'{target}-guard-no-release'
    link_variant(program, without_release, tool_prefix,
                 before + '\nrt_guardfail:\n' + handler + '\nrt_gconstack:\n' + after)
    expect([*launch, without_release], 2, b'', f'{message}unknown)\n'.encode())
    print(f'ok guard diagnostics {target}, normal start, EINVAL and unavailable uname')


def main():
    if len(sys.argv) != 4:
        raise SystemExit('usage: check_guard_diagnostics.py compiler builddir qemu')
    compiler, build, qemu = (Path(arg).resolve() for arg in sys.argv[1:])
    work = Path(mkdtemp(prefix='guard-diagnostics-', dir=build))
    link_variant = runpy.run_path(str(ROOT / 'scripts/check_cpu_affinity.py'))['link_variant']
    check_target(compiler, build, work, 'amd64', [], os.uname().release, link_variant)
    release = '6.12.113-paslang-test'
    check_target(compiler, build / 'a64', work, 'arm64',
                 [qemu, '-cpu', 'cortex-a53', '-r', release], release, link_variant)


if __name__ == '__main__':
    main()
