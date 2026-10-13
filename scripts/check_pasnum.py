#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""pasnum (P200) on both machines against its model: Go's table of powers
of ten checked word by word (scripts/pow10gen.py); a million cases from
scripts/nummodel.py, the inputs of Go's own tests first
(testdata/numgo.txt) and then seeded ones, whose answers are worked out
exactly in Python's integers, checked against Go's strconv when go is
there (testdata/numtext.go) and against testdata/numtext built for amd64
with -cpu native and base and -inline 40 and 0; the first 200,000 on
arm64 under qemu with -cpu max and base; and the first 4,000 answered
by eight routines at once with the collector's verify, stress and
poison modes on, on both machines (Regla 11)."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

compiler = str(Path(sys.argv[1]).resolve())
build = Path(sys.argv[2]).resolve()
qemu = sys.argv[3:]
# One directory, emptied on each run and removed when the check passes:
# a failure stays for inspection, nothing accumulates in build/.
work = build / 'check-pasnum'
if work.exists():
    shutil.rmtree(work)
work.mkdir()
compile_environment = {key: value for key, value in os.environ.items()
                       if not key.startswith('PASLANG_GC')}
gc_environment = dict(compile_environment, PASLANG_GCVERIFY='1', PASLANG_GCSTRESS='1',
                      PASLANG_GCPOISON='1')


def run(command, stdin=None, env=None, timeout=900):
    source = open(stdin, 'rb') if stdin else subprocess.DEVNULL
    try:
        result = subprocess.run(command, stdin=source, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, env=env or compile_environment,
                                timeout=timeout)
    finally:
        if stdin:
            source.close()
    if result.returncode:
        raise RuntimeError(f'{command!r}: exit {result.returncode}\n'
                           + result.stdout.decode(errors='replace')[-4000:])
    return result.stdout


def head(source, lines, dest, end):
    """the first lines of source into dest, an empty line after them
    when end"""
    with open(source) as f, open(dest, 'w') as g:
        for _ in range(lines):
            g.write(f.readline())
        if end:
            g.write('\n')


def compare(name, expect, got):
    want = Path(expect).read_bytes()
    if got != want:
        a = want.split(b'\n')
        b = got.split(b'\n')
        for i in range(min(len(a), len(b))):
            if a[i] != b[i]:
                raise RuntimeError(f'{name}: answer {i + 1} differs: model {a[i]!r}, got {b[i]!r}')
        raise RuntimeError(f'{name}: {len(b)} answers for {len(a)}')


run([sys.executable, 'scripts/pow10gen.py', '--check'])
cases, expect = work / 'cases.txt', work / 'expect.txt'
run([sys.executable, 'scripts/nummodel.py', '--seed', '20026', '--count', '1000000',
     str(cases), str(expect)], timeout=1800)
if shutil.which('go'):
    oracle = work / 'oracle'
    oracle.mkdir()
    shutil.copy('testdata/numtext.go', oracle / 'main.go')
    go_environment = dict(compile_environment, GOCACHE=str(build / 'gocache'), GOFLAGS='-mod=mod')
    subprocess.run(['go', 'mod', 'init', 'numtext'], cwd=oracle, env=go_environment,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    result = subprocess.run(['go', 'run', '.', str(cases), str(expect)], cwd=oracle, env=go_environment,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
    if result.returncode or not result.stdout.endswith(b' 0 differ from Go\n'):
        raise RuntimeError('the model against Go: ' + result.stdout.decode(errors='replace'))
    against = 'Go and the model'
else:
    against = 'the model (no go: Go is not asked)'
few, few_expect = work / 'few.txt', work / 'few-expect.txt'
head(cases, 200000, few, True)
head(expect, 200000, few_expect, False)
small, small_expect = work / 'small.txt', work / 'small-expect.txt'
head(cases, 4000, small, True)
head(expect, 4000, small_expect, False)
for target, cpus in (('amd64', ('native', 'base')), ('arm64', ('max', 'base'))):
    core = build / 'a64' if target == 'arm64' else build
    wrap = qemu if target == 'arm64' else []
    for cpu in cpus:
        for level in (40, 0):
            binary = work / f'numtext-{target}-{cpu}-{level}'
            run([compiler, '-target', target, '-cpu', cpu, '-inline', str(level), '-Fu', str(core),
                 '-o', str(binary), 'testdata/numtext.paslang'])
            if target == 'amd64':
                compare(binary.name, expect, run([str(binary)], cases))
            else:
                compare(binary.name, few_expect, run(wrap + [str(binary)], few))
            compare(binary.name + ' par', small_expect,
                    run(wrap + [str(binary), 'par'], small, gc_environment))
    print(f'ok pasnum {target} ({" and ".join(cpus)}, inline 40/0, eight routines under the '
          f'collector\'s verify/stress/poison) against {against}')
shutil.rmtree(work)
