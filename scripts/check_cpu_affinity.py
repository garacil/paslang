#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Check Linux CPU affinity and one-processor scheduler wakeups."""

import os
from pathlib import Path
import runpy
import subprocess
import sys
from tempfile import TemporaryDirectory

PROGRAM = """program affinitycount;
function Ps: Integer;
begin
  asm amd64 (Result: out rax)
    movq rt_nproc(%rip), %rax
  end;
  asm arm64 (Result: out x0)
    adrp x0, rt_nproc
    ldr x0, [x0, :lo12:rt_nproc]
  end;
end;
begin
  WriteLn(Ps);
end.
"""


def run(command):
    result = subprocess.run(command, capture_output=True, timeout=60)
    if result.returncode:
        raise SystemExit(f'{command!r} exited {result.returncode}\n'
                         + result.stderr.decode(errors='replace'))
    return result.stdout


def expect(command, number, case):
    output = run(command)
    if output != f'{number}\n'.encode():
        raise SystemExit(f'affinity {case}: expected {number}, got {output!r}')


def masked_syscall(cpu, words, result):
    # Replace only the raw syscall. Memory contents and the result
    # register model the Linux ABI, leaving startup and counting intact.
    if cpu == 'amd64':
        return ''.join(f'  movabsq ${word}, %rax\n  movq %rax, {i * 8}(%rsp)\n'
                       for i, word in enumerate(words)) + f'  movq ${result}, %rax\n'
    return ''.join(f'  mov x9, #{word}\n  str x9, [sp, #{i * 8}]\n'
                   for i, word in enumerate(words)) + f'  mov x0, #{result}\n'


def link_variant(program, candidate, cc_prefix, assembly):
    asm = candidate.with_suffix('.s')
    obj = candidate.with_suffix('.o')
    asm.write_text(assembly)
    run([cc_prefix + 'as', '-o', str(obj), str(asm)])
    link = program.with_suffix('.link').read_text().splitlines()
    replacements = {str(program): str(candidate), str(program.with_suffix('.o')): str(obj)}
    run([cc_prefix + 'ld', *(replacements.get(arg, arg) for arg in link)])


def check_one_p(compiler, units, working, cpu, launch, allowed):
    root = Path(__file__).resolve().parent.parent
    check_blocked_writer = runpy.run_path(str(root / 'scripts/check_uncaught_reports.py'))['check_blocked_writer']
    command = ['taskset', '-c', str(min(allowed)), *launch]
    for name in ('reportparallel', 'dlrecv'):
        program = working / f'{cpu}-{name}'
        source = root / 'testdata' / 'fatal' / (name + '.paslang')
        run([compiler, '-target', cpu, '-cpu', 'base', '-Fu', str(units),
             '-o', str(program), str(source)])
        if name == 'reportparallel':
            for _ in range(8):
                check_blocked_writer(command + [str(program)])
        else:
            deadlock = subprocess.run(command + [str(program)], capture_output=True, timeout=30)
            expected = (root / 'testdata' / 'fatal' / 'expected.out').read_bytes()
            if (deadlock.returncode, deadlock.stdout, deadlock.stderr) != (
                1, expected, b'paslang: all routines are asleep: deadlock\n'
            ):
                raise SystemExit(f'one-P {cpu} deadlock: {deadlock.returncode}, '
                                 f'{deadlock.stdout!r}, {deadlock.stderr!r}')


def check_target(compiler, build, working, cpu, launch):
    native = cpu == 'amd64'
    cc_prefix = '' if native else 'aarch64-linux-gnu-'
    units = build if native else build / 'a64'
    program = working / cpu
    source = program.with_suffix('.paslang')
    source.write_text(PROGRAM)
    run([compiler, '-target', cpu, '-cpu', 'base', '-Fu', str(units),
         '-o', str(program), str(source)])

    allowed = os.sched_getaffinity(0)
    pin = ['taskset', '-c', str(min(allowed))]
    for value, expected in (('4', 4), ('+00065', 65), ('', 1), ('0', 1),
                            ('-1', 1), (' 4', 1), ('4x', 1), ('10001', 1),
                            ('999999999999999999999', 1)):
        expect(pin + ['env', f'PASLANG_MAXPROCS={value}'] + launch + [str(program)],
               expected, f'{cpu} PASLANG_MAXPROCS={value!r}')

    # Tests of the mask must reach the syscall independently of the caller's environment.
    launch = ['env', '-u', 'PASLANG_MAXPROCS'] + launch
    expect(launch + [str(program)], min(10000, max(1, len(allowed))), f'{cpu} current mask')
    expect(pin + launch + [str(program)], 1, f'{cpu} single CPU')

    assembly = program.with_suffix('.s').read_text()
    syscall = '  syscall\n' if native else '  svc #0\n'
    start = assembly.index('rt_ncpu:\n')
    end = assembly.index('\nrt_', start)
    if assembly[start:end].count(syscall) != 1:
        raise SystemExit(f'affinity {cpu}: expected one syscall in the startup counter')
    raw = assembly.index(syscall, start)
    for name, words, result, expected in (
        ('upper-word', [1, 15], 16, 5),
        ('single-high-cpu', [0, 1], 16, 1),
        ('wide-mask', [-1, 1], 16, 65),
        ('short-mask', [7, -1], 8, 3),
        ('failed', [-1], -1, 1),
        ('empty', [-1], 0, 1),
    ):
        candidate = working / f'{cpu}-{name}'
        changed = assembly[:raw] + masked_syscall(cpu, words, result) + assembly[raw + len(syscall):]
        link_variant(program, candidate, cc_prefix, changed)
        expect(launch + [str(candidate)], expected, f'{cpu} {name}')
    check_one_p(compiler, units, working, cpu, launch, allowed)


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit('usage: check_cpu_affinity.py compiler builddir qemu')
    compiler, build, qemu = (Path(arg).resolve() for arg in sys.argv[1:])
    with TemporaryDirectory(prefix='affinity-check-', dir=build) as temporary:
        for target, run_under in (('amd64', []), ('arm64', [str(qemu)])):
            check_target(str(compiler), build, Path(temporary), target, run_under)
    print('CPU affinity, pending wakes and real deadlocks checked on amd64 and arm64')
