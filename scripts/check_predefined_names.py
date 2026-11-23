#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Exercise declaration diagnostics for the compiler's reserved-name inventory."""

from pathlib import Path
import re
import subprocess
import sys
from tempfile import mkdtemp

ROOT = Path(__file__).resolve().parents[1]
PREDEFINED = 'is a predefined name of the language'
SYNTAX = 'is a reserved word, not a name'
IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z_0-9]*')


def inventory(sdk):
    parser = (ROOT / 'src/compiler/pasparse.paslang').read_text()
    lexer = (ROOT / 'src/compiler/paslex.paslang').read_text()
    keyword = lexer.split('function Keyword(', 1)[1].split('\nend;', 1)[0]
    keywords = set(re.findall(r"if u = '(\w+)' then", keyword))
    init = parser.split('procedure TParser.InitReserved;', 1)[1].split('\nend;', 1)[0]
    names = {}
    for words, kind in re.findall(r"AddReserved\('([^']+)'(?:,\s*(rnk\w+))?\);", init):
        for name in words.split():
            assert name not in names, name
            names[name] = ('', SYNTAX if kind == 'rnkSyntax' else PREDEFINED)

    vector = parser.split('function TParser.VecShape(', 1)[1].split('\nend;', 1)[0]
    operations = re.findall(r"Op = '(\w+)'", vector)
    assert operations
    for operation in operations:
        names.setdefault('v' + operation, ('', PREDEFINED))

    load = parser.split('procedure TParser.LoadCore;', 1)[1].split('\nend;', 1)[0]
    core_types = re.findall(r"AddCoreName\('(\w+)'\)", load)
    variants = parser.split('  VtNames:', 1)[1].split('  VtValues:', 1)[0]
    core_types.extend(re.findall(r"'(\w+)'", variants))
    for name in core_types:
        names.setdefault(name.lower(), ('', PREDEFINED))

    units = re.findall(r"LoadUnit\('(\w+)', (True|False)\);", load)
    assert keywords and names.get('low') == ('', PREDEFINED) and units
    for unit, link_only in sorted(units, key=lambda item: item[1]):
        uses = f'uses {unit};\n' if link_only == 'True' else ''
        for line in (sdk / f'{unit}.pi').read_text().splitlines():
            parts = line.split()
            if len(parts) < 2 or parts[0] not in {'FUNC', 'CONST', 'VAR', 'TYPE', 'ALIAS'}:
                continue
            kind, name = parts[:2]
            if name == '_' or not IDENTIFIER.fullmatch(name):
                continue
            lower = name.lower()
            if lower in keywords or (lower == 'exception' and kind in {'TYPE', 'ALIAS'}):
                continue
            names.setdefault(lower, (uses, PREDEFINED))
    return names


def invoke(compiler, sdk, target, program, source):
    program.write_text(source, encoding='utf-8')
    return subprocess.run([compiler, '-target', target, '-cpu', 'base', '-Fu', sdk,
                           '-o', program.with_suffix('.bin'), program],
                          capture_output=True, timeout=30)


def reject(compiler, sdk, target, program, source, expected):
    result = invoke(compiler, sdk, target, program, source)
    assert result.returncode == 1 and not result.stdout and expected.encode() in result.stderr, (
        target, expected, result.returncode, result.stdout, result.stderr)
    assert not program.with_suffix('.bin').exists(), (target, program)


def main():
    compiler, build = (Path(arg).resolve() for arg in sys.argv[1:])
    work = Path(mkdtemp(prefix='predefined-names-', dir=build))
    for target, sdk in [('amd64', build), ('arm64', build / 'a64')]:
        names = inventory(sdk)
        for name, (uses, diagnostic) in sorted(names.items()):
            # Change the spelling to check case-insensitive lookup and diagnostic spelling.
            spelling = name[0].upper() + name[1:]
            source = f'program rejected;\n{uses}var {spelling}: Integer;\nbegin\nend.\n'
            line = 3 if uses else 2
            reject(compiler, sdk, target, work / f'{target}-{name}.paslang', source,
                   f'{spelling} {diagnostic} at {line}:5')
        reject(compiler, sdk, target, work / f'{target}-send.paslang',
               'program rejected;\nprocedure Send;\nbegin\nend;\nbegin\nend.\n',
               "Send is a reserved word, not a routine's name at 2:11")
        reject(compiler, sdk, target, work / f'{target}-single-parameter.paslang',
               'program rejected;\nprocedure Example(Single: Integer);\nbegin\nend;\nbegin\nend.\n',
               f'Single {PREDEFINED} at 2:19')
        positive = invoke(compiler, sdk, target, work / f'{target}-accepted.paslang',
                          'program accepted;\nvar LowerBound: Integer;\nbegin\n'
                          '  LowerBound := Low(Byte);\n  WriteLn(LowerBound);\nend.\n')
        assert positive.returncode == 0 and not positive.stderr, (target, positive.stderr)
        count = sum(diagnostic == PREDEFINED for _, diagnostic in names.values())
        print(f'ok predefined names {target}, {count} predefined identifiers and '
              f'{len(names) - count} context words')


if __name__ == '__main__':
    main()
