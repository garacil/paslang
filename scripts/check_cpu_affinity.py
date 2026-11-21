#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Check scheduler startup with real and synthetic Linux CPU affinity masks."""

import os
from pathlib import Path
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
    expect(launch + [str(program)], min(32, max(2, len(allowed))), f'{cpu} current mask')
    expect(['taskset', '-c', str(min(allowed))] + launch + [str(program)], 2, f'{cpu} single CPU')

    assembly = program.with_suffix('.s').read_text()
    link = program.with_suffix('.link').read_text().splitlines()
    syscall = '  syscall\n' if native else '  svc #0\n'
    start = assembly.index('rt_ncpu:\n')
    end = assembly.index('\nrt_', start)
    if assembly[start:end].count(syscall) != 1:
        raise SystemExit(f'affinity {cpu}: expected one syscall in the startup counter')
    raw = assembly.index(syscall, start)
    for name, words, result, expected in (
        ('upper-word', [1, 15], 16, 5),
        ('clamp', [-1], 8, 32),
        ('short-mask', [7, -1], 8, 3),
        ('failed', [-1], -1, 2),
        ('empty', [-1], 0, 2),
    ):
        candidate = working / f'{cpu}-{name}'
        asm = candidate.with_suffix('.s')
        obj = candidate.with_suffix('.o')
        asm.write_text(assembly[:raw] + masked_syscall(cpu, words, result) + assembly[raw + len(syscall):])
        run([cc_prefix + 'as', '-o', str(obj), str(asm)])
        replacements = {str(program): str(candidate), str(program.with_suffix('.o')): str(obj)}
        run([cc_prefix + 'ld', *(replacements.get(arg, arg) for arg in link)])
        expect(launch + [str(candidate)], expected, f'{cpu} {name}')


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit('usage: check_cpu_affinity.py compiler builddir qemu')
    compiler, build, qemu = (Path(arg).resolve() for arg in sys.argv[1:])
    with TemporaryDirectory(prefix='affinity-check-', dir=build) as temporary:
        for target, run_under in (('amd64', []), ('arm64', [str(qemu)])):
            check_target(str(compiler), build, Path(temporary), target, run_under)
    print('CPU affinity masks and errors checked on amd64 and arm64')
