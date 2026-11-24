#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Check hardware DIT across concurrent pasroutines and measure scoped call cost."""
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
from tempfile import mkdtemp

ROOT = Path(__file__).resolve().parents[1]


def run(command, procs=4):
    result = subprocess.run(command, env=os.environ | {'PASLANG_MAXPROCS': str(procs)},
                            capture_output=True, check=True, text=True, timeout=120)
    assert not result.stderr, result.stderr
    return result.stdout.strip()



def observe_rsa(compiler, sdk, qemu, work, source):
    """Read hardware DIT inside the real private operation, after entry."""
    hook = '  if not NatSetBytes(cn, C, Key.Pub.N) then'
    probe = """
  asm arm64 (ditProbe: out x0)
    mrs x0, s3_3_c4_c2_5
    ubfx x0, x0, #24, #1
  end;
  WriteLn('RSA DIT ', ditProbe);
"""
    assert source.count(hook) == 1
    source = source.replace(hook, probe + hook)
    locals_line = '  cn, m1, m2, t0, check: TNat;'
    assert source.count(locals_line) == 1
    (work / 'pasrsa.paslang').write_text(
        source.replace(locals_line, locals_line + '\n  ditProbe: Integer;'))
    run([compiler, '-target', 'arm64', '-cpu', 'base', '-Fu', sdk, '-c',
         '-o', work / 'pasrsa', work / 'pasrsa.paslang'])
    vectors = (ROOT / 'testdata/rsasign/cavp.txt').read_text().splitlines()
    key = next(line.split()[2:7] for line in vectors if line.startswith('key '))
    observed = {}
    for cpu in ('base', 'base+dit'):
        binary = work / ('rsa-' + cpu)
        run([compiler, '-target', 'arm64', '-cpu', cpu, '-Fu', work, '-Fu', sdk,
             '-o', binary, ROOT / 'scripts/fixtures/rsa_fault.paslang'])
        result = run([qemu, '-cpu', 'max', binary, *key])
        assert 'verifies True' in result, result
        observed[cpu] = re.findall(r'^RSA DIT ([01])$', result, re.M)
    return observed


def main():
    compiler, build, qemu = (Path(arg).resolve() for arg in sys.argv[1:])
    work = Path(mkdtemp(prefix='dit-scope-', dir=build))
    source = ROOT / 'scripts/fixtures/dit_scope.paslang'

    def compile_case(target, cpu, name):
        output = work / name
        sdk = build / 'a64' if target == 'arm64' else build
        subprocess.run([compiler, '-target', target, '-cpu', cpu, '-inline', '0',
                        '-Fu', sdk, '-o', output, source], timeout=120, check=True)
        listing = output.with_suffix('.s').read_text()
        entry = listing.split('\nrt_execute:\n', 1)[1].split('\nrt_gstart:\n', 1)[0]
        has_dit = 'msr s3_3_c4_c2_5, x9' in entry
        assert has_dit == (name == 'arm-dit'), name
        return output

    native = compile_case('amd64', 'base', 'amd64')
    base = compile_case('arm64', 'base', 'arm-base')
    dit = compile_case('arm64', 'base+dit', 'arm-dit')
    assert re.fullmatch(r'ok DIT False migrations [0-9]+', run([native]))
    assert re.fullmatch(r'ok DIT False migrations [0-9]+', run([qemu, '-cpu', 'cortex-a53', base]))
    assert re.fullmatch(r'ok DIT False migrations [0-9]+', run([qemu, '-cpu', 'max', base]))
    for procs in (1, 4):
        result = run([qemu, '-cpu', 'max', dit], procs)
        match = re.fullmatch(r'ok DIT True migrations ([0-9]+)', result)
        assert match and (procs == 1 or int(match[1]) > 0), (procs, result)
        print(f'arm64 DIT ({procs} Ps): {result}')

    observed = observe_rsa(compiler, build / 'a64', qemu, work,
                           (ROOT / 'src/lib/pasrsa.paslang').read_text())
    assert observed == {'base': ['0'] * 3, 'base+dit': ['1'] * 3}, observed
    print('ok DIT inside all three RSA signatures')

    samples = {'base': [], 'dit': []}
    cases = [('base', base), ('dit', dit)]
    for i in range(7):
        for name, binary in (cases if i % 2 == 0 else reversed(cases)):
            samples[name].append(int(run([qemu, '-cpu', 'max', binary, 'cost'], 1)))
    report = {'platform': 'qemu arm64 max', 'scope_pairs': 200000,
              'nanoseconds': samples, 'median_ns_per_pair':
              {name: statistics.median(times) / 200000 for name, times in samples.items()}}
    (work / 'cost.json').write_text(json.dumps(report, indent=2) + '\n')
    print('ok DIT base paths, nested scopes, exception cleanup, parking and migration', work)


if __name__ == '__main__':
    main()
