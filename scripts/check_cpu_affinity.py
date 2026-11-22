#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Check Linux scheduler sizing and one-processor wakeups."""

import json
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


def with_cgroup_files(assembly, membership, mountinfo):
    for path, fixture in (('/proc/self/cgroup', membership), ('/proc/self/mountinfo', mountinfo)):
        original = f'.asciz "{path}"'
        if assembly.count(original) != 1:
            raise SystemExit(f'expected one startup path for {path}')
        assembly = assembly.replace(original, '.asciz ' + json.dumps(str(fixture), ensure_ascii=False))
    return assembly


def check_cgroups(command, membership, mountinfo, working):
    default = ['env', '-u', 'PASLANG_MAXPROCS', *command]
    mount = working / 'cpu quotas'
    group = mount / 'child'
    group.mkdir(parents=True)
    escaped = str(mount).replace(chr(92), r'\134').replace(' ', r'\040')
    quota = group / 'cpu.max'
    parent = mount / 'cpu.max'
    membership.write_text('0::/team space/child\n')
    identical_prefix = f'42 21 0:42 /team {escaped} rw - cgroup2 cgroup rw\n'
    long_mount = '43 21 0:43 / /misc rw - overlay overlay ' + 'x' * 65536 + '\n'
    v2 = f'44 21 0:44 /team\\040space {escaped} rw nsdelegate - cgroup2 cgroup rw\n'
    mountinfo.write_text(long_mount + identical_prefix + v2)
    for child, inherited, expected in (
        ('125000 100000\n', 'max 100000\n', 2),
        ('30000 100000\n', 'max 100000\n', 1),
        ('max 100000\n', '175000 100000\n', 2),
        ('900000 100000\n', '300000 100000\n', 3),
        ('10 0\n', '200000 100000\n', 2),
        ('100000 100000 extra\n', '200000 100000\n', 2),
        ('100000 100000', '200000 100000\n', 2),
        ('9223372036854775808 100000\n', '300000 100000\n', 3),
        ('9223372036854775807 1\n', 'max 100000\n', 65),
        ('max 100000\n', 'max 100000\n', 65),
    ):
        quota.write_text(child)
        parent.write_text(inherited)
        expect(default, expected, f'cgroup v2 {child!r}, parent {inherited!r}')

    quota.write_text('100000 100000\n')
    mountinfo.write_text(identical_prefix)
    expect(default, 65, 'cgroup mount root must match at a path boundary')
    membership.write_text('0::/team space/../team space/child\n')
    mountinfo.write_text(v2)
    expect(default, 65, 'cgroup outside the visible mount')

    membership.write_text('0::/team space/child\n7:cpuacct,cpu:/legacy/child\n')
    v1 = f'45 21 0:45 /legacy {escaped} rw - cgroup cgroup rw,cpuacct,cpu\n'
    mountinfo.write_text(v2 + v1)
    (group / 'cpu.cfs_quota_us').write_text('-1\n')
    (mount / 'cpu.cfs_quota_us').write_text('225000\n')
    (mount / 'cpu.cfs_period_us').write_text('100000\n')
    expect(default, 3, 'cgroup v1 controller in a hybrid hierarchy and inherited limit')
    (group / 'cpu.cfs_quota_us').write_text('75000\n')
    (group / 'cpu.cfs_period_us').write_text('100000\n')
    expect(default, 1, 'cgroup v1 local quota')
    expect(['env', 'PASLANG_MAXPROCS=4', *command], 4, 'explicit override in a limited cgroup')


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
    clean_launch = ['env', '-u', 'PASLANG_MAXPROCS'] + launch
    expect(pin + clean_launch + [str(program)], 1, f'{cpu} single CPU')

    fixtures = working / f'{cpu}-cgroups'
    fixtures.mkdir()
    membership = fixtures / 'cgroup'
    mountinfo = fixtures / 'mountinfo'
    assembly = with_cgroup_files(program.with_suffix('.s').read_text(), membership, mountinfo)
    affinity_only = working / f'{cpu}-current-mask'
    link_variant(program, affinity_only, cc_prefix, assembly)
    expect(clean_launch + [str(affinity_only)], min(10000, max(1, len(allowed))), f'{cpu} current mask')
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
        expect(clean_launch + [str(candidate)], expected, f'{cpu} {name}')
    check_cgroups(launch + [str(working / f'{cpu}-wide-mask')], membership, mountinfo, fixtures)
    check_one_p(compiler, units, working, cpu, clean_launch, allowed)


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit('usage: check_cpu_affinity.py compiler builddir qemu')
    compiler, build, qemu = (Path(arg).resolve() for arg in sys.argv[1:])
    with TemporaryDirectory(prefix='affinity-check-', dir=build) as temporary:
        for target, run_under in (('amd64', []), ('arm64', [str(qemu)])):
            check_target(str(compiler), build, Path(temporary), target, run_under)
    print('CPU affinity, cgroups, pending wakes and real deadlocks checked on amd64 and arm64')
