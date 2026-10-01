#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Currency language/interface, place binding and debug contracts on both targets."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

compiler = str(Path(sys.argv[1]).resolve())
build = Path(sys.argv[2]).resolve()
qemu = sys.argv[3:]
work = Path(tempfile.mkdtemp(prefix='currency-language-', dir=build))
environment = dict(os.environ, PASLANG_GCVERIFY='1', PASLANG_GCSTRESS='1', PASLANG_GCPOISON='1')
compile_environment = {key: value for key, value in os.environ.items()
                       if not key.startswith('PASLANG_GC')}


def run(command, input_data=None):
    selected_environment = compile_environment if command[0] == compiler else environment
    result = subprocess.run(command, input=input_data, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, env=selected_environment, timeout=120)
    if result.returncode:
        raise RuntimeError(f'{command!r}: exit {result.returncode}\n'
                           + result.stdout.decode(errors='replace'))
    return result.stdout


rejects = {
    'implicit-binary': ('c := d', 'a real becomes Currency only through Currency(x)'),
    'implicit-decimal': ('d := c', 'a Currency needs an explicit conversion'),
    'integer-cast': ('n := Integer(c)', 'Trunc or Round'),
    'mixed-double': ('c := c + d', 'mixed Currency arithmetic'),
    'mixed-quad': ('c := q + c', 'mixed Currency arithmetic'),
    'mixed-min': ('c := Min(c, d)', 'mixed Currency arithmetic'),
    'mixed-max': ('c := Max(q, c)', 'mixed Currency arithmetic'),
    'ordinal-div': ('c := c div 1', 'Currency takes'),
    'ordinal-mod': ('c := c mod 1', 'Currency takes'),
    'condition': ('if c then n := 1', 'does not go into Boolean'),
    'ordinal': ('n := Ord(c)', 'Ord of a Currency'),
    'odd': ('if Odd(c) then n := 1', 'Currency does not go into Odd'),
    'sin': ('d := Sin(c)', 'has no Currency form'),
    'nan': ('if IsNan(c) then n := 1', 'has no Currency form'),
    'step': ('Inc(n, c)', 'Currency does not go into Integer'),
    'index': ('n := items[c]', 'Currency does not go into Integer'),
    'literal-overflow': ('c := 922337203685477.58075', 'constant does not fit Currency'),
    'folded-overflow': ('c := High(Currency) + 0.0001', 'Currency overflow in a constant'),
    'anonymous-array-name': ('items := items and d', 'and of array[0..1] of Integer'),
    'named-array-name': ('pair := pair and d', 'and of TCurrencyQuadWords'),
}
for target in ('amd64', 'arm64'):
    core = build / 'a64' if target == 'arm64' else build
    directory = work / target
    directory.mkdir()
    for level in (0, 40):
        for unit in ('currencyu', 'currencywrap', 'corekindsu'):
            run([compiler, '-target', target, '-inline', str(level), '-c', '-Fu', str(directory),
                 '-Fu', str(core), '-o', str(directory / unit), f'testdata/units/{unit}.paslang'])
        for fixture in ('currency1', 'syscurrency', 'corekinds', 'placeonce', 'dwarfcurrency',
                        'selectflow', 'realincplace', 'quadincplace', 'intcompplace', 'arrayidentity',
                        'units/currencyuse', 'units/corekindsuse'):
            binary = directory / (Path(fixture).name + '-' + str(level))
            run([compiler, '-target', target, '-inline', str(level), '-Fu', str(directory),
                 '-Fu', str(core), '-o', str(binary), f'testdata/{fixture}.paslang'])
            for affinity in ([], ['taskset', '-c', str(min(os.sched_getaffinity(0)))]):
                command = affinity + (qemu if target == 'arm64' else []) + [str(binary)]
                output = run(command)
                if output != Path(f'testdata/{fixture}.out').read_bytes():
                    raise RuntimeError(f'{fixture}/{target}/{level}: {output!r}')
    for name, (statement, diagnostic) in rejects.items():
        source = directory / (name + '.paslang')
        source.write_text('program rejected; uses sysutils; '
                          'var c: Currency; d: Double; q: Quad; n: Integer; '
                          'items: array[0..1] of Integer; pair: TCurrencyQuadWords; begin '
                          + statement + ' end.\n')
        result = subprocess.run([compiler, '-target', target, '-Fu', str(core), '-o', str(directory / name),
                                 str(source)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        if not result.returncode or diagnostic.encode() not in result.stdout:
            raise RuntimeError(f'wrong rejection {name}/{target}: {result.stdout!r}')
    for name in ('TClass', 'TVarRec', 'vtCurrency'):
        source = directory / ('reserved-' + name + '.paslang')
        source.write_text(f'program rejected; uses sysutils; var {name}: Integer; begin end.\n')
        result = subprocess.run([compiler, '-target', target, '-Fu', str(core), '-o', str(directory / 'reserved'),
                                 str(source)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        if not result.returncode or b'is a reserved word, not a name' not in result.stdout:
            raise RuntimeError(f'wrong reserved core rejection {name}/{target}: {result.stdout!r}')
    # The internal debugger's decimal code is not an integer or float code.
    binary = directory / 'debug-currency'
    run([compiler, '-target', target, '-debug', '-inline', '0', '-Fu', str(core),
         '-o', str(binary), 'testdata/dwarfcurrency.paslang'])
    output = run((qemu if target == 'arm64' else []) + [str(binary), '--debug-mode'],
                 b'b 9\nc\np amount\np upper\np lower\nd 1\nc\n')
    for expected in (b'amount = 2.675', b'upper = 922337203685477.5807',
                     b'lower = -922337203685477.5808'):
        if expected not in output:
            raise RuntimeError(f'missing debug value {target}: {output!r}')
    dwarf = run(['readelf', '--debug-dump=info', str(binary)])
    for expected in (b'DW_AT_decimal_scale: -4', b'DW_AT_digit_count : 19', b'(signed_fixed)'):
        if expected not in dwarf:
            raise RuntimeError(f'missing fixed-point DWARF {expected!r}: {target}')
    if target == 'amd64':
        gdb_output = run(['gdb', '-batch', '-nx', '-ex', 'set debuginfod enabled off',
                          '-ex', 'break dwarfcurrency.paslang:9', '-ex', 'run > /dev/null',
                          '-ex', 'print amount', '-ex', 'ptype amount',
                          '-ex', 'python import struct; assert struct.unpack("<q", '
                          'gdb.selected_inferior().read_memory(int(gdb.parse_and_eval("&upper")), 8))[0] == 9223372036854775807',
                          '-ex', 'python assert struct.unpack("<q", '
                          'gdb.selected_inferior().read_memory(int(gdb.parse_and_eval("&lower")), 8))[0] == -9223372036854775808',
                          '-ex', 'kill', str(binary)])
        if b'= 2.675' not in gdb_output or b'small = 1/10000' not in gdb_output:
            raise RuntimeError(f'GDB Currency type/value: {gdb_output!r}')
    print(f'ok Currency language {target}: inline0/40, affinity, GC stress, interfaces, rejects and debug')
