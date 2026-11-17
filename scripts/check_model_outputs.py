#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Reproduce tree, hash and rotation output oracles without changing fixtures."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: check_model_outputs.py build')
    repo = Path(__file__).resolve().parents[1]
    build = Path(sys.argv[1]).resolve()
    models = ('hashmodel.py', 'treemodel.py', 'rotmodel.py')
    fixtures = ('hash1', 'tree2', 'rotwords', 'rotmem')
    inputs = [repo / 'scripts' / name for name in models]
    inputs += [repo / 'testdata' / (name + '.out') for name in fixtures]
    frozen = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}

    def compare(label, actual, expected):
        if actual != expected.read_bytes():
            raise SystemExit(label + ': model differs from ' + str(expected))

    with tempfile.TemporaryDirectory(prefix='model-oracles-', dir=build) as tmp:
        work = Path(tmp)
        (work / 'scripts').mkdir()
        (work / 'testdata').mkdir()
        for name in models:
            copied = work / 'scripts' / name
            shutil.copyfile(repo / 'scripts' / name, copied)
            result = subprocess.run([sys.executable, '-I', str(copied)], cwd=work,
                                    stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
            if result.returncode or result.stderr:
                raise SystemExit(name + ': failed or wrote diagnostics: ' + repr(result.stderr[:400]))
            if name == 'rotmodel.py':
                if result.stdout:
                    raise SystemExit(name + ': unexpected standard output')
                for stem in ('rotwords', 'rotmem'):
                    compare(stem, (work / 'testdata' / (stem + '.out')).read_bytes(),
                            repo / 'testdata' / (stem + '.out'))
            else:
                stem = 'hash1' if name == 'hashmodel.py' else 'tree2'
                compare(stem, result.stdout, repo / 'testdata' / (stem + '.out'))
    for path, digest in frozen.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise SystemExit('model input changed: ' + str(path))
    print('model outputs: hash1, tree2, rotwords and rotmem exactly reproduced')


if __name__ == '__main__':
    main()
