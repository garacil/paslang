#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""Generate shared manual defaults from source and check the compiled help.

  scripts/check_helpdoc.py --sync TREE
  scripts/check_helpdoc.py PASLANGC MANUAL [RUNNER ...]

The compiler and runtime define the values. Their help prints the same
constants and the generator updates the cited places in MANUAL.md.
"""
import re
import subprocess
import sys
from pathlib import Path

COMPILER = 'src/compiler/pasast.paslang'
HEAP = 'src/lib/pasheap.paslang'
FORMAT = 'src/lib/pasfmt.paslang'

# Fact name, source file and constant, then help and manual capture patterns.
# Each capture is the exact text of the value.
FACTS = [
    ('routine parameters', COMPILER, 'MaxParams',
     [r'At most (\d+) parameters', r'up to (\d+) parameters'],
     [r'takes up to (\d+) parameters', r'takes at most (\d+) parameters']),
    ('select arms', COMPILER, 'MaxSelectArms',
     [r'A select has at most (\d+) arms'],
     [r'A select has at most (\d+) arms']),
    ('minimum kernel', COMPILER, 'MinLinuxKernel',
     [r'kernel (\d+\.\d+) or newer'],
     [r'kernel (\d+\.\d+) or newer']),
    ('default output', COMPILER, 'DefaultProgramOutput',
     [r'program with no -o is named ([\w.]+) in the current directory',
      r'Output executable \(default: ([\w.]+)\)'],
     [r'a program defaults to `([\w.]+)`']),
    ('default -inline', COMPILER, 'DefaultInlineLimit',
     [r'-inline 0 keeps one copy of every routine\. (\d+) by default'],
     [r'`-inline 0` keeps one copy of every routine and every loop; (\d+) by default']),
    ('default PASLANG_GC', HEAP, 'PasDefaultGcPercent',
     [r'PASLANG_GC=(\d+) \(the default\)'],
     [r'`PASLANG_GC=(\d+)` is the default']),
    ('default GC workers', HEAP, 'PasDefaultGcWorkers',
     [r'By default at most (\d+) workers mark'],
     [r'By default at most (\d+) workers mark']),
    ('default real decimals', FORMAT, 'PasDefaultRealDecimals',
     [r'up to (\d+) fractional digits'],
     [r'real prints up to (\d+) decimals', r"`WriteLn`'s own form, up to (\d+) decimals"]),
]


def matches(text, pattern):
    """Match across a wrapped paragraph while preserving the source spans."""
    return list(re.finditer(pattern.replace(' ', r'\s+'), text))


def source_values(root):
    sources = {}
    for _, file, constant, _, _ in FACTS:
        if file not in sources:
            sources[file] = (root / file).read_text(encoding='utf-8')
        values = re.findall(
            rf"^  {constant} = ('[^'\n]+'|\d+);", sources[file], re.MULTILINE)
        if len(values) != 1:
            raise ValueError(f'{file}: expected one definition of {constant}')
        yield values[0].strip("'")


def update_manual(root, values):
    path = root / 'docs/MANUAL.md'
    manual = path.read_text(encoding='utf-8')
    edits = {}
    for (name, _, _, _, patterns), value in zip(FACTS, values, strict=True):
        for pattern in patterns:
            found = matches(manual, pattern)
            if not found:
                raise ValueError(f'{name}: missing manual entry for {pattern!r}')
            for match in found:
                if match[1] != value:
                    edits[match.span(1)] = value
    if edits:
        for (start, end), value in sorted(edits.items(), reverse=True):
            manual = manual[:start] + value + manual[end:]
        path.write_text(manual, encoding='utf-8')
        print(f'check_helpdoc: updated {len(edits)} manual values')


def check(compiler, manual_path, runner):
    root = Path(__file__).resolve().parent.parent
    versions = []
    for flag in ('--help', '-h'):
        result = subprocess.run(
            [*runner, compiler, flag], capture_output=True, text=True, check=True)
        versions.append(result.stdout)
    help_text = '\n'.join(versions)
    manual = Path(manual_path).read_text(encoding='utf-8')
    errors = []
    for (name, _, _, help_patterns, manual_patterns), value in zip(
            FACTS, source_values(root), strict=True):
        for text, label, patterns in (
                (help_text, 'help', help_patterns), (manual, 'manual', manual_patterns)):
            for pattern in patterns:
                found = matches(text, pattern)
                if not found:
                    errors.append(f'{name}: missing {label} entry for {pattern!r}')
                for match in found:
                    if match[1] != value:
                        errors.append(f'{name}: {label} has {match[1]}, source has {value}')
    if (not matches(help_text, r'take defaults as a routine does') or
            matches(help_text, r'[Aa] method has no default|default value on a method')):
        errors.append('the help must describe method default arguments')

    for error in errors:
        print(f'check_helpdoc: {error}')
    if errors:
        return 1
    print(f'check_helpdoc: {len(FACTS)} source settings and method defaults checked')
    return 0


def main():
    args = sys.argv[1:]
    if len(args) < 2 or (args[0] == '--sync' and len(args) != 2):
        raise SystemExit(__doc__)
    try:
        if args[0] == '--sync':
            root = Path(args[1])
            update_manual(root, source_values(root))
            return 0
        compiler, manual, *runner = args
        return check(compiler, manual, runner)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(f'check_helpdoc: {error}') from error


if __name__ == '__main__':
    sys.exit(main())
