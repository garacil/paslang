#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see COPYING.
"""P457: mixed property accessors pass the complete backing block.

Usage: check_propfield.py COMPILER BUILDDIR QEMU [--baseline COMPILER]

The normal golden loops exercise optimized native/base and arm64 code.
This bounded check also runs the same source at inline 0 on both targets
and inspects the one-word record's address passed to a const parameter.
An optional compiler with the current compiled-unit format must fail the amd64 regression; its scalar,
fat, field/field and getter control routines must emit the same code as
the candidate on both targets. No FPC executable supplies the answers.
"""
from pathlib import Path
import re
import resource
import subprocess
import sys
import tempfile
import runpy

_symbols = runpy.run_path(str(Path(__file__).with_name('asm_symbols.py')))
procedure_symbol = _symbols['procedure_symbol']



CONTROLS = ('controlinteger', 'controlbyte', 'controlstring', 'controlslice',
            'controlface', 'controlquad', 'controlfieldfield', 'controlgetter')


def command(args):
    result = subprocess.run([str(a) for a in args], text=True,
                            capture_output=True, timeout=120)
    if result.returncode:
        raise SystemExit('propfield: command failed: ' + ' '.join(map(str, args)) +
                         '\n' + result.stdout + result.stderr)
    return result


def routine(assembly, name):
    match = re.search(r'^' + re.escape(procedure_symbol('', name)) +
                      r'(?:_o(?:_[vr][0-9]+)*)?:\n(.*?)^\s*\.cfi_endproc',
                      assembly, re.M | re.S)
    if not match:
        raise SystemExit('propfield: no emitted routine ' + name)
    return match[1]


def instructions(body):
    """Ignore debug locations and renumber local labels, preserving branches."""
    labels = {}

    def label(match):
        value = match[0]
        if value not in labels:
            labels[value] = '.local' + str(len(labels))
        return labels[value]

    lines = []
    for line in body.splitlines():
        line = line.strip()
        if not line or re.match(r'^\.(?:loc\b|cfi(?:_|$)|file\b|p2align\b|balign\b|align\b)', line):
            continue
        if line.startswith('.LL'):
            continue
        lines.append(re.sub(r'\.L[A-Za-z0-9_]+', label, line))
    return '\n'.join(lines)


def compile_fixture(compiler, source, folder, target, units):
    folder.mkdir(parents=True)
    program = folder / 'propfield.paslang'
    program.write_text(source)
    executable = folder / 'propfield'
    command([compiler, '-target', target, '-cpu', 'base', '-inline', '0',
             '-Fu', units, '-o', executable, program])
    return executable, executable.with_suffix('.s').read_text()


def no_core():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def main():
    args = sys.argv[1:]
    baseline = None
    if len(args) == 5 and args[3] == '--baseline':
        baseline = Path(args[4]).resolve()
        args = args[:3]
    if len(args) != 3:
        raise SystemExit(__doc__)
    compiler, build, qemu = map(lambda p: Path(p).resolve(), args)
    tree = Path(__file__).resolve().parents[1]
    source = (tree / 'testdata/propfield.paslang').read_text()
    expected = (tree / 'testdata/propfield.out').read_text()
    if expected != 'propfield ok\n':
        raise SystemExit('propfield: review the assertion fixture and its oracle')
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='propfield-', dir=build) as tmp:
        work = Path(tmp)
        for target, units, launch in [('amd64', build, []),
                                      ('arm64', build / 'a64', [qemu])]:
            executable, assembly = compile_fixture(compiler, source,
                work / target / 'candidate', target, units)
            got = command([*launch, executable])
            if got.stdout != expected:
                raise SystemExit(target + ': propfield golden differs: ' + got.stdout)
            probe = routine(assembly, 'probeone')
            # VMT at 0, Pad at 8, FOne at 16. The const call must receive
            # that address, never the first word stored in FOne.
            pattern = (r'^\s*leaq 16\(%rax\), %r(?:ax|di)$' if target == 'amd64'
                       else r'^\s*add x0, x0, #16$')
            if not re.search(pattern, probe, re.M):
                raise SystemExit(target + ': one-word const argument has no backing-field address:\n' + probe)
            for name in CONTROLS:
                routine(assembly, name)
            if baseline:
                oldexe, oldasm = compile_fixture(baseline, source,
                    work / target / 'baseline', target, units)
                if target == 'amd64':
                    focused = command([executable, 'repro'])
                    if focused.stdout != 'propfield repro ok\n':
                        raise SystemExit('propfield: candidate focused reproduction differs')
                    old = subprocess.run([str(oldexe), 'repro'], text=True,
                        capture_output=True, timeout=30, cwd=oldexe.parent,
                        preexec_fn=no_core)
                    if old.returncode == 0 and old.stdout == 'propfield repro ok\n':
                        raise SystemExit('propfield: the baseline compiler did not reproduce P457')
                for name in CONTROLS:
                    previous = instructions(routine(oldasm, name))
                    current = instructions(routine(assembly, name))
                    if previous != current:
                        raise SystemExit(target + ': unrelated emitted code changed in ' + name +
                                         '\nBASELINE:\n' + previous + '\nCANDIDATE:\n' + current)
    print('propfield: complete mixed-accessor values and const address at inline 0 on both targets' +
          ('; baseline amd64 failure and eight unchanged controls per target' if baseline else ''))


if __name__ == '__main__':
    main()
