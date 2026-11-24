#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Check Mul128's emitted product and both outputs."""

from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory


def main():
    if len(sys.argv) != 4:
        raise SystemExit('usage: check_mulwide.py compiler builddir qemu')
    compiler, build, qemu = (Path(arg).resolve() for arg in sys.argv[1:])
    tests = Path(__file__).resolve().parent.parent / 'testdata'
    expected = (tests / 'wide.out').read_bytes()
    profiles = [
        ('amd64', 'base', [], ['mulq']),
        ('amd64', 'bmi2', None, ['mulxq']),
        ('arm64', 'base', [qemu, '-cpu', 'cortex-a53'], ['umulh', 'mul']),
    ]
    with TemporaryDirectory(prefix='mulwide-', dir=build) as temp:
        for target, cpu, launch, product in profiles:
            binary = Path(temp) / (target + '-' + cpu)
            units = build if target == 'amd64' else build / 'a64'
            subprocess.run([compiler, '-target', target, '-cpu', cpu, '-inline', '0',
                            '-Fu', units, '-o', binary, tests / 'wide.paslang'],
                           check=True, timeout=60)
            assembly = binary.with_suffix('.s').read_text()
            body = re.search(r'^p_f\.0_15_readwideproduct:\n(.*?)^  \.cfi_endproc$',
                             assembly, re.MULTILINE | re.DOTALL)
            if body is None:
                raise SystemExit(f'{target}/{cpu}: no complete product body')
            emitted = re.findall(r'^  (mulq|mulxq|imulq|mul|umulh)\b', body[1], re.MULTILINE)
            if emitted != product:
                raise SystemExit(f'{target}/{cpu}: expected {product!r}, emitted {emitted!r}')
            if launch is not None:
                got = subprocess.run([*launch, binary], capture_output=True, timeout=60)
                if (got.returncode, got.stdout, got.stderr) != (0, expected, b''):
                    raise SystemExit(f'{target}/{cpu}: wide output changed: {got}')
    print('Mul128 emits one amd64 product and one arm64 instruction per half')


if __name__ == '__main__':
    main()
