#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Check that NetAccept returns Linux epoll registration errors on both targets."""

from pathlib import Path
import runpy
import subprocess
import sys
from tempfile import TemporaryDirectory

PROGRAM = """program acceptregistration;
var
  listener, answer: Integer;
begin
  listener := NetListen(0);
  if listener < 0 then
    Halt(8);
  answer := NetAccept(listener);
  NetClose(listener);
  WriteLn(answer);
end.
"""


def check_target(compiler, build, work, target, prefix, launch, link_variant):
    native = target == 'amd64'
    source = work / f'{target}.paslang'
    binary = source.with_suffix('')
    source.write_text(PROGRAM)
    units = build if native else build / 'a64'
    subprocess.run([compiler, '-target', target, '-cpu', 'base', '-Fu', units,
                    '-o', binary, source], check=True, timeout=60)
    assembly = source.with_suffix('.s').read_text()
    # NetAccept waits as every routine does (P441): the park of every
    # wait, from its label to the next routine's.
    start = assembly.index('\nrt_pollpark:\n')
    finish = assembly.index('\nrt_tcplisten:\n', start)
    wait = assembly[start:finish]
    load_fd = '  movq %rbx, %rdx\n' if native else '  mov x2, x19\n'
    bad_fd = '  movq $-1, %rdx\n' if native else '  mov x2, #-1\n'
    # Ask the real kernel for EBADF at either registration call. In
    # the second case MOD is genuine and sees an absent entry (ENOENT).
    if wait.count(load_fd) != 2:
        raise SystemExit(f'{target}: accept registration fixture no longer matches')
    for index, operation in enumerate(('MOD', 'ADD')):
        offset = wait.index(load_fd) if index == 0 else wait.rindex(load_fd)
        altered = wait[:offset] + bad_fd + wait[offset + len(load_fd):]
        variant = work / f'{target}-{operation.lower()}-error'
        link_variant(binary, variant, prefix, assembly[:start] + altered + assembly[finish:])
        try:
            got = subprocess.run([*launch, variant], capture_output=True, timeout=10)
        except subprocess.TimeoutExpired:
            raise SystemExit(f'{target}: accept parked after EPOLL_CTL_{operation} failed') from None
        if (got.returncode, got.stdout, got.stderr) != (0, b'-9\n', b''):
            raise SystemExit(f'{target}: EPOLL_CTL_{operation} expected -EBADF, '
                             f'got {got.returncode}, {got.stdout!r}, {got.stderr!r}')


def main():
    if len(sys.argv) != 4:
        raise SystemExit('usage: check_accept_registration.py compiler builddir qemu')
    compiler, build, qemu = map(lambda value: Path(value).resolve(), sys.argv[1:])
    link_variant = runpy.run_path(str(Path(__file__).with_name('check_cpu_affinity.py')))['link_variant']
    with TemporaryDirectory(prefix='accept-registration-', dir=build) as temp:
        check_target(compiler, build, Path(temp), 'amd64', '', [], link_variant)
        check_target(compiler, build, Path(temp), 'arm64',
                     'aarch64-linux-gnu-', [qemu, '-cpu', 'cortex-a53'], link_variant)
    print('Accept reports epoll registration errors on amd64 and arm64')


if __name__ == '__main__':
    main()
