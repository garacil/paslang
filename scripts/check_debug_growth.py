#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Stack-relative debugger frames/next on both targets, with forced growth."""
import os
import re
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

compiler = str(Path(sys.argv[1]).resolve())
build = Path(sys.argv[2]).resolve()
qemu = sys.argv[3:]
work = Path(tempfile.mkdtemp(prefix='debug-growth-', dir=build))
base = {key: value for key, value in os.environ.items() if not key.startswith('PASLANG_GC')}
stress = dict(base, PASLANG_GCVERIFY='1', PASLANG_GCSTRESS='1', PASLANG_GCPOISON='1',
              DEBUGINFOD_URLS='')
lines = Path('testdata/debuggrow.paslang').read_text().splitlines()
grow_line = next(i + 1 for i, text in enumerate(lines) if 'Grow(40);' in text)
commands = (f'b {grow_line}\nc\np amount\np upper\np lower\nbt\nn\np amount\n'
            f'n\np amount\nd 1\nc\n').encode()
input_path = work / 'console-input'
input_path.write_bytes(commands)


def run(command, env=base, data=None):
    result = subprocess.run(command, env=env, input=data, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=120)
    if result.returncode:
        raise RuntimeError(f'{command!r}: {result.returncode}\n{result.stdout.decode(errors="replace")}')
    return result.stdout


def check(output, target):
    for expected in (b'amount = 2.675\n', b'amount = 2.6751\n',
                     b'upper = 922337203685477.5807', b'lower = -922337203685477.5808',
                     f'Show debuggrow.paslang:{grow_line + 1}'.encode(),
                     f'Show debuggrow.paslang:{grow_line + 2}'.encode(),
                     Path('testdata/debuggrow.out').read_bytes()):
        if expected not in output:
            raise RuntimeError(f'missing {expected!r}/{target}: {output!r}')


for target, cpu_level in (('amd64', 'base'), ('arm64', 'base'), ('arm64', 'max')):
    core = build if target == 'amd64' else build / 'a64'
    binary = work / (target + '-' + cpu_level)
    run([compiler, '-target', target, '-cpu', cpu_level, '-debug', '-Fu', str(core), '-o', str(binary),
         'testdata/debuggrow.paslang'])
    runner = qemu if target == 'arm64' else []
    if target == 'arm64':
        # QEMU on x86 cannot serve as a weak-memory ordering oracle.
        # Verify actual ISA bytes through the cross-disassembler, too.
        machine = run(['aarch64-linux-gnu-objdump', '-d', '--no-show-raw-insn', str(binary)]).decode()
        for label in ('.rd_a', '.rd_c', '.pk_cas', '.rpu_cas', '.awi_spin'):
            block = re.search(r'<' + re.escape(label) + r'>:\n(.*?)(?=\n[0-9a-f]+ <)',
                              machine, re.S)
            if not block:
                raise RuntimeError(f'missing G transition {label}')
            if cpu_level == 'base':
                if not re.search(r'ldaxr\s+w3,\s*\[x9\]', block[1]) or not re.search(
                        r'stlxr\s+w4,\s*w2,\s*\[x9\]', block[1]) or 'casal' in block[1]:
                    raise RuntimeError(f'{label} does not acquire/release the base G transition')
            elif not re.search(r'casal\s+w3,\s*w2,\s*\[x9\]', block[1]) or 'ldaxr' in block[1]:
                raise RuntimeError(f'{label} does not use the statically selected LSE G transition')
    for env in (stress, dict(base, PASLANG_GC='off')):
        for affinity in ([], ['taskset', '-c', str(min(os.sched_getaffinity(0)))]):
            check(run([*affinity, *runner, str(binary), '--debug-mode'], env, commands), target)
    gdb_commands = ['gdb', '-batch', '-nx', '-q', str(binary),
                    '-ex', 'set debuginfod enabled off', '-ex', 'set pagination off',
                    '-ex', 'set language c', '-ex', 'set args --debug-mode',
                    '-ex', f'set $debug_line = {grow_line}',
                    '-ex', f'set $debug_input = "{input_path}"']
    source = 'source scripts/inject_debug_growth.py'
    if target == 'amd64':
        # Isolate the injected growth request from concurrent GC guard
        # requests; ordinary console runs above retain full GC stress.
        gdb_output = run([*gdb_commands, '-ex', source], dict(base, PASLANG_GC='off'))
        check(gdb_output, target)
    else:
        with tempfile.TemporaryDirectory(prefix='pl-dbg-') as directory:
            endpoint = Path(directory) / 'gdb.sock'
            process = subprocess.Popen(['taskset', '-c', str(min(os.sched_getaffinity(0))),
                                        *qemu, '-g', str(endpoint), str(binary), '--debug-mode'],
                                       env=dict(base, PASLANG_GC='off'), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                process.stdin.write(commands)
                process.stdin.flush()
                deadline = time.monotonic() + 10
                while not endpoint.exists():
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError('QEMU did not open its private GDB socket')
                    time.sleep(.01)
                try:
                    gdb_output = run([*gdb_commands, '-ex', f'target remote {endpoint}', '-ex', source], stress)
                except RuntimeError as error:
                    output, _ = process.communicate(timeout=10)
                    raise RuntimeError(f'{error}\nguest exit {process.returncode}: {output!r}') from error
                output, _ = process.communicate(timeout=120)
                if process.returncode:
                    raise RuntimeError(f'forced-growth guest failed: {output!r}')
                check(output, target)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
    if b'forced debugger stack growth and relocated Currency frame passed' not in gdb_output:
        raise RuntimeError(gdb_output.decode(errors='replace'))
    print(f'ok debugger growth {target}/{cpu_level}: frames, next, GC stress/off, single/all CPUs and forced relocation',
          flush=True)
