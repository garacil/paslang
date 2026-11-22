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
    label = '.wi_ctl:' if native else '.awi_ctl:'
    failed = '.wi_failed' if native else '.awi_failed'
    load_fd = '  movq %rbx, %rdx\n' if native else '  mov x2, x19\n'
    bad_fd = '  movq $-1, %rdx\n' if native else '  mov x2, #-1\n'
    force_mod = '  movl $3, %esi\n' if native else '  mov w1, #3\n'
    test_add = '  cmpl $1, %esi\n  je 99f\n' if native else '  cmp w1, #1\n  b.eq 99f\n'
    unexpected = (f'  movq $-22, %rax\n  jmp {failed}\n99:\n' if native else
                  f'  mov x0, #-22\n  b {failed}\n99:\n')
    retried = ('  testl %r12d, %r12d\n  jnz 98f\n' if native else '  cbnz w20, 98f\n')
    resume = '  jmp 97f\n' if native else '  b 97f\n'
    # Force real EBADF on the first ADD and on a MOD. The third case
    # lets the kernel reject a missing entry before forcing EBADF on
    # the retried ADD.
    if wait.count(label) != 1 or wait.count(load_fd) != 1:
        raise SystemExit(f'{target}: accept registration fixture no longer matches')
    variants = {
        'first-add': test_add + unexpected + bad_fd,
        'mod-error': force_mod + bad_fd,
        'retry-add': retried + force_mod + load_fd + resume + '98:\n'
                     + test_add + unexpected + bad_fd + '97:\n',
    }
    cases = {name: wait.replace(load_fd, code, 1) for name, code in variants.items()}
    # Add the listener before the original ADD so the real kernel
    # returns EEXIST. After the retry selects MOD, force EBADF there.
    syscall = '  syscall\n' if native else '  svc #0\n'
    reset = '  movl $233, %eax\n' if native else '  mov x0, x25\n'
    test_result = ('  testq %rax, %rax\n' if native else '  cmp x0, #0\n')
    check_result = (f'  jne {failed}\n' if native else f'  b.ne {failed}\n')
    test_mod = '  cmpl $3, %esi\n  je 99f\n' if native else '  cmp w1, #3\n  b.eq 99f\n'
    if wait.count(syscall) != 1:
        raise SystemExit(f'{target}: expected one epoll_ctl instruction')
    inject = (retried + syscall + test_result + check_result + reset + resume + '98:\n'
              + test_mod + unexpected + bad_fd + '97:\n' + syscall)
    cases['retry-mod'] = wait.replace(syscall, inject, 1)
    for operation, altered in cases.items():
        variant = work / f'{target}-{operation}'
        link_variant(binary, variant, prefix, assembly[:start] + altered + assembly[finish:])
        try:
            got = subprocess.run([*launch, variant], capture_output=True, timeout=10)
        except subprocess.TimeoutExpired:
            raise SystemExit(f'{target}: accept parked after {operation} failed') from None
        if (got.returncode, got.stdout, got.stderr) != (0, b'-9\n', b''):
            raise SystemExit(f'{target}: {operation} expected -EBADF, '
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
