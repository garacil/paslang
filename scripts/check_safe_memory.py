#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P523: raw memory words are refused at their place in every safe scope.

The same source with its safe declaration removed must compile, so a
syntax error or an unavailable builtin cannot masquerade as a refusal.
Both compiler targets are checked; typed allocation is the safenew golden.
Usage: check_safe_memory.py COMPILER BUILDDIR
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path


OPERATIONS = {
    'expr': 'p := GetMem(1);',
    'exprscan': 'p := gEtMeM(SizeOf(p^), 0);',
    'stmt': 'GetMem(p, 1);',
    'stmtscan': 'gEtMeM(p, SizeOf(p^), 0);',
    'free': 'New(p);\n  FreeMem(p);\n  p^ := 42;',
    'doublefree': 'New(p);\n  FreeMem(p);\n  FreeMem(p);',
    'barefree': 'FreeMem;',
}


def source(scope, operation):
    body = 'var p: PInteger;\nbegin\n  ' + operation + '\nend;\n'
    if scope == 'program':
        return 'safe program smtest;\n' + body[:-2] + '.\n'
    if scope == 'unit':
        return ('safe unit smtest;\ninterface\nprocedure Run;\n'
                'implementation\nprocedure Run;\n' + body + 'end.\n')
    if scope in ('initialization', 'finalization'):
        return ('safe unit smtest;\ninterface\nimplementation\n'
                'var p: PInteger;\n' + scope + '\n  ' + operation + '\nend.\n')
    if scope == 'routine':
        return ('program smtest;\nsafe procedure Run;\n' + body +
                'begin Run; end.\n')
    if scope == 'function':
        return ('program smtest;\nsafe function Run: PInteger;\n' + body +
                'begin WriteLn(Run = nil); end.\n')
    if scope == 'nested':
        return ('program smtest;\nsafe procedure Outer;\nprocedure Run;\n' +
                body + 'begin Run; end;\nbegin Outer; end.\n')
    if scope == 'method':
        return ('program smtest;\ntype TBox = class\n'
                '  safe procedure Run;\nend;\nprocedure TBox.Run;\n' +
                body + 'begin TBox.Create.Run; end.\n')
    if scope == 'constructor':
        return ('program smtest;\ntype TBox = class\n'
                '  safe constructor Build;\nend;\nconstructor TBox.Build;\n' +
                body + 'var box: TBox;\nbegin box := TBox.Build; end.\n')
    if scope == 'destructor':
        return ('program smtest;\ntype TBox = class\n'
                '  safe destructor Clean;\nend;\ndestructor TBox.Clean;\n' +
                body + 'var box: TBox;\nbegin box := TBox.Create; box.Clean; end.\n')
    raise AssertionError(scope)


def compile_source(compiler, path, output, target):
    return subprocess.run(
        [str(compiler), '-target', target, '-cpu', 'base', '-c',
         '-o', str(output), str(path)], text=True, capture_output=True,
        timeout=30)


def main():
    compiler = Path(sys.argv[1]).resolve()
    build = Path(sys.argv[2]).resolve()
    build.mkdir(parents=True, exist_ok=True)
    checked = 0
    with tempfile.TemporaryDirectory(prefix='safe-memory-', dir=build) as tmp:
        root = Path(tmp)
        for target in ('amd64', 'arm64'):
            for scope in ('program', 'unit', 'initialization', 'finalization',
                          'routine', 'function', 'nested', 'method', 'constructor', 'destructor'):
                for name, operation in OPERATIONS.items():
                    text = source(scope, operation)
                    builtin = re.search(r'GetMem|FreeMem', text, re.I)
                    assert builtin is not None
                    line = text.count('\n', 0, builtin.start()) + 1
                    col = builtin.start() - text.rfind('\n', 0, builtin.start())
                    word = builtin.group().lower()
                    reason = ('call GetMem; use typed New instead' if word == 'getmem'
                              else 'call FreeMem; the collector owns memory')
                    expected = f'safe code does not {reason} at {line}:{col}'
                    directory = root / target / scope / name
                    directory.mkdir(parents=True)
                    path = directory / 'smtest.paslang'
                    path.write_text(text)
                    result = compile_source(compiler, path, directory / 'safe', target)
                    diagnostic = result.stdout + result.stderr
                    if result.returncode == 0 or expected not in diagnostic:
                        raise SystemExit(f'{target} {scope} {name}: expected refusal '
                                         f'{expected!r}, got {result.returncode}: {diagnostic}')
                    path.write_text(text.replace('safe ', ''))
                    result = compile_source(compiler, path, directory / 'raw', target)
                    if result.returncode != 0:
                        raise SystemExit(f'{target} {scope} {name}: raw equivalent failed: '
                                         f'{result.stdout}{result.stderr}')
                    checked += 1
    print(f'safe-memory: {checked} refusals at the builtin and {checked} raw equivalents, both targets')


if __name__ == '__main__':
    main()
