#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P591: deferred calls keep complete stack maps in actual code order.

Usage: check_loopmaps.py COMPILER BUILDDIR QEMU [--baseline COMPILER]

Both targets, inline 0 and 40, must pass independent call/map coverage,
object ownership, raw ELF ordering, and the GC/stack-growth fixture.
The optional older compiler must reproduce inversions while preserving
identical instructions and exact descriptors paired with every return PC.
Artifacts and command logs remain under BUILDDIR/loopmaps-* on failure too.
Metadata is checked before executing candidate code; forged metadata is
never executed, and a compiler/linker failure is never a caught mutant.
"""

import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
from typing import NamedTuple
import runpy

_symbols = runpy.run_path(str(Path(__file__).with_name('asm_symbols.py')))
procedure_symbol = _symbols['procedure_symbol']



ROUTINES = tuple(procedure_symbol('', name) for name in
                 ('workrepeat', 'workpost', 'worknested', 'workregions',
                  'workislands', 'coldread'))
EXPECTED = 'loopmaporder ok\n'


class CheckError(Exception):
    pass


def require(ok, message):
    if not ok:
        raise CheckError(message)


class Section(NamedTuple):
    index: int
    name: str
    typ: int
    flags: int
    address: int
    offset: int
    size: int
    link: int
    info: int
    alignment: int
    entsize: int


class Symbol(NamedTuple):
    name: str
    info: int
    other: int
    section: int
    value: int
    size: int


class Relocation(NamedTuple):
    offset: int
    typ: int
    symbol: Symbol
    addend: int


class ELF:
    """Bounded ELF64 reader; all VA reads stay in one allocated file section.

    gABI chapter 4, docs/ref/elf/gabi-ch4.sheader.html: section headers,
    SHT_RELA explicit addends, sh_link/sh_info, and SHF_LINK_ORDER.
    Read final PCs rather than repeat the emitter's queue algorithm, as
    Go obj/pcln.go funcpctab traverses the final Prog/Pc instruction order.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        require(self.data[:6] == b'\x7fELF\x02\x01' and len(self.data) >= 64,
                str(path) + ': expected little-endian ELF64')
        self.typ, self.machine = self.unpack('<HH', 16)
        require(self.typ in (1, 2) and self.machine in (62, 183),
                str(path) + ': expected amd64/arm64 object or executable')
        shoff, = self.unpack('<Q', 40)
        shsize, count, names = self.unpack('<HHH', 58)
        require(shsize == 64 and count > 0 and names < count,
                str(path) + ': unsupported section-header layout')
        self.bytes(shoff, count * shsize)
        heads = [self.unpack('<IIQQQQIIQQ', shoff + i * shsize)
                 for i in range(count)]
        strings = heads[names]
        names_data = self.bytes(strings[4], strings[5])
        self.sections = [Section(i, self.string(names_data, h[0]), *h[1:])
                         for i, h in enumerate(heads)]
        self.by_name = {s.name: s for s in self.sections if s.name}
        require(len(self.by_name) == sum(bool(s.name) for s in self.sections),
                str(path) + ': duplicate section names')
        for section in self.sections:
            if section.typ != 8:
                self.bytes(section.offset, section.size)
        self._symbols = {}

    def bytes(self, offset, size):
        require(0 <= offset <= len(self.data) and 0 <= size <= len(self.data) - offset,
                str(self.path) + ': read outside file')
        return self.data[offset:offset + size]

    def unpack(self, fmt, offset):
        return struct.unpack(fmt, self.bytes(offset, struct.calcsize(fmt)))

    def string(self, data, offset):
        require(0 <= offset < len(data), str(self.path) + ': bad string offset')
        end = data.find(b'\0', offset)
        require(end >= 0, str(self.path) + ': unterminated ELF string')
        return data[offset:end].decode('utf-8')

    def section(self, name):
        require(name in self.by_name, str(self.path) + ': missing section ' + name)
        return self.by_name[name]

    def section_bytes(self, section):
        require(section.typ != 8, str(self.path) + ': file read from NOBITS')
        return self.bytes(section.offset, section.size)

    def words(self, section, offset, count):
        require(section.flags & 2 and section.typ != 8 and
                0 <= offset <= section.size and 0 <= count <= (section.size - offset) // 8,
                str(self.path) + ': descriptor exceeds allocated file section ' + section.name)
        return self.unpack('<' + 'Q' * count, section.offset + offset)

    def descriptor(self, section, offset):
        require(section.flags & 3 == 2,
                str(self.path) + ': descriptor is not allocated read-only data')
        header, = self.words(section, offset, 1)
        kind, n = header & 255, header >> 8
        require((kind == 1 and header == 1) or (kind == 0 and n > 0),
                str(self.path) + ': invalid descriptor kind/header')
        count = 1 if kind == 1 else 1 + 2 * ((n + 63) // 64)
        return self.words(section, offset, count)

    def allocated(self, address, size):
        matches = [s for s in self.sections if s.flags & 2 and s.typ != 8 and
                   s.address <= address and size <= s.size and
                   address - s.address <= s.size - size]
        require(len(matches) == 1,
                str(self.path) + ': VA read has no unique allocated file section at ' + hex(address))
        return matches[0], address - matches[0].address

    def symbols(self, table):
        if table.index not in self._symbols:
            require(table.typ == 2 and table.entsize == 24 and table.size % 24 == 0 and
                    table.link < len(self.sections), str(self.path) + ': bad symbol table')
            strings = self.section_bytes(self.sections[table.link])
            result = []
            for offset in range(0, table.size, 24):
                name, info, other, section, value, size = self.unpack('<IBBHQQ', table.offset + offset)
                result.append(Symbol(self.string(strings, name), info, other, section, value, size))
            self._symbols[table.index] = result
        return self._symbols[table.index]

    def named_symbol(self, name):
        found = [symbol for table in self.sections if table.typ == 2
                 for symbol in self.symbols(table) if symbol.name == name and
                 0 < symbol.section < len(self.sections)]
        require(len(found) == 1, str(self.path) + ': no unique defined symbol ' + name)
        return found[0]

    def relocations(self, target):
        result = []
        for section in self.sections:
            if section.typ != 4 or section.info != target.index:
                continue
            require(section.entsize == 24 and section.size % 24 == 0 and
                    section.link < len(self.sections), str(self.path) + ': bad RELA section')
            symbols = self.symbols(self.sections[section.link])
            for offset in range(0, section.size, 24):
                at, info, addend = self.unpack('<QQq', section.offset + offset)
                require(info >> 32 < len(symbols), str(self.path) + ': bad relocation symbol')
                result.append(Relocation(at, info & 0xffffffff, symbols[info >> 32], addend))
        return result

    def resolve(self, relocation):
        require(relocation.typ == (1 if self.machine == 62 else 257) and
                0 < relocation.symbol.section < len(self.sections),
                str(self.path) + ': map needs a defined absolute64 relocation')
        return self.sections[relocation.symbol.section], relocation.symbol.value + relocation.addend


def strict_order(pcs, label):
    for previous, current in zip(pcs, pcs[1:]):
        require(previous < current,
                label + ': raw map order: ' + hex(current) + ' follows ' + hex(previous))


def coverage(expected, actual, label):
    missing, extra = set(expected) - set(actual), set(actual) - set(expected)
    require(not missing and not extra,
            label + ': PC coverage missing=' + str(sorted(missing)) + ' extra=' + str(sorted(extra)))


def pairing(expected, actual, label):
    coverage(expected, actual, label)
    for pc in expected:
        require(expected[pc] == actual[pc],
                label + ': descriptor mismatch at ' + hex(pc) +
                ': expected ' + repr(expected[pc]) + ', got ' + repr(actual[pc]))


def linked_maps(elf, ordered):
    section = elf.section('pasgcmaps')
    require(section.size > 0 and section.size % 16 == 0,
            str(elf.path) + ': invalid raw map table size')
    rows, descriptors = [], {}
    for offset in range(0, section.size, 16):
        pc, pointer = elf.unpack('<QQ', section.offset + offset)
        require(pc not in descriptors, str(elf.path) + ': duplicate map PC ' + hex(pc))
        owner, _ = elf.allocated(pc - 1, 1)
        require(owner.flags & 4, str(elf.path) + ': return PC is outside executable code')
        desc_section, desc_offset = elf.allocated(pointer, 8)
        descriptors[pc] = elf.descriptor(desc_section, desc_offset)
        rows.append(pc)
    if ordered:
        strict_order(rows, str(elf.path))
    return rows, descriptors


def command(arguments, folder, name, *, env=None, timeout=180):
    arguments = [str(argument) for argument in arguments]
    (folder / (name + '.command.json')).write_text(json.dumps(arguments) + '\n')
    try:
        result = subprocess.run(arguments, cwd=folder, env=env, text=True,
                                capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise CheckError(name + ': command timed out; artifacts in ' + str(folder)) from error
    (folder / (name + '.stdout')).write_text(result.stdout)
    (folder / (name + '.stderr')).write_text(result.stderr)
    require(result.returncode == 0,
            name + ': command failed with exit ' + str(result.returncode) +
            '; this is not a caught metadata mutant; logs in ' + str(folder))
    return result


def disassembled_calls(elf, folder):
    tool = 'objdump' if elf.machine == 62 else 'aarch64-linux-gnu-objdump'
    text = command([tool, '-drw', elf.path], folder, 'objdump').stdout
    calls, current = {name: [] for name in ROUTINES}, None
    for line in text.splitlines():
        match = re.match(r'^Disassembly of section \.text\.(\S+):$', line)
        if match:
            current = match[1] if match[1] in calls else None
            continue
        if current is None:
            continue
        fields = line.split('\t')
        address = re.match(r'^\s*([0-9a-fA-F]+):\s*$', fields[0])
        if not address or len(fields) < 3 or not fields[2].strip():
            continue
        mnemonic = fields[2].split()[0]
        if mnemonic not in (('call', 'callq') if elf.machine == 62 else ('bl', 'blr')):
            continue
        raw = fields[1].strip().split()
        require(bool(raw) and all(re.fullmatch(r'[0-9a-fA-F]{2}', byte) for byte in raw)
                if elf.machine == 62 else len(raw) == 1 and bool(re.fullmatch(r'[0-9a-fA-F]{8}', raw[0])),
                current + ': cannot decode call width from objdump')
        width = len(raw) if elf.machine == 62 else 4
        target = re.search(r'R_(?:X86_64|AARCH64)_\w+\s+([^\s+-]+)', line)
        calls[current].append((int(address[1], 16) + width, target[1] if target else None))
    return calls


def object_maps(elf, calls, ordered, inline):
    require(elf.typ == 1, str(elf.path) + ': expected relocatable object')
    result = {}
    for name in ROUTINES:
        code = elf.section('.text.' + name)
        table = elf.section('pasgcmaps.' + name)
        require(code.flags & 6 == 6 and table.flags & 0x83 == 0x83 and table.link == code.index,
                name + ': map section ownership/link-order flags are wrong')
        require(table.size > 0 and table.size % 16 == 0, name + ': invalid object map size')
        relocations = elf.relocations(table)
        by_offset = {relocation.offset: relocation for relocation in relocations}
        require(len(by_offset) == len(relocations) and
                set(by_offset) == set(range(0, table.size, 8)),
                name + ': map PC/descriptor relocation coverage differs')
        rows, descriptors = [], {}
        for offset in range(0, table.size, 16):
            owner, pc = elf.resolve(by_offset[offset])
            require(owner.index == code.index and 0 < pc <= code.size,
                    name + ': map PC belongs to the wrong code section')
            require(pc not in descriptors, name + ': duplicate object map PC ' + hex(pc))
            section, at = elf.resolve(by_offset[offset + 8])
            descriptors[pc] = elf.descriptor(section, at)
            rows.append(pc)
        expected = calls[name]
        require(len(expected) >= 3 and expected[0][1] == 'rt_morestack',
                name + ': missing prologue/body/cooperative call mechanism')
        require(sum(target == 'rt_morestack' for _, target in expected) >= 2,
                name + ': no body cooperative call remains')
        pcs = [pc for pc, _ in expected]
        require(len(set(pcs)) == len(pcs), name + ': duplicate disassembled call end')
        coverage(pcs, descriptors, name)
        if ordered:
            strict_order(rows, name)
        for pc in pcs:
            kind = 1 if pc == pcs[0] else 0
            require(descriptors[pc][0] & 255 == kind,
                    name + ': descriptor kind mismatch at ' + hex(pc) + '; expected ' + str(kind))
        result[name] = descriptors
    island_calls = [target for _, target in calls['p_f.0_11_workislands']]
    require(('p_f.0_12_addisland591' in island_calls) == (inline == 0),
            'p_f.0_11_workislands: AddIsland591 must remain at inline 0 and actually inline at 40')
    return result


def object_link_pairing(obj, executable, object_descriptors, descriptors):
    for name, expected in object_descriptors.items():
        symbol = executable.named_symbol(name)
        owner = executable.sections[symbol.section]
        code = obj.section('.text.' + name)
        require(owner.flags & 6 == 6 and owner.address <= symbol.value and
                symbol.value + code.size <= owner.address + owner.size,
                name + ': linked routine is outside its executable section')
        actual = {pc - symbol.value: words for pc, words in descriptors.items()
                  if symbol.value < pc <= symbol.value + code.size}
        pairing(expected, actual, name + ' object/linked')


def negative_controls(descriptors):
    """Mutate decoded metadata only; no forged binary is written or executed."""
    expected = dict(descriptors['p_f.0_10_workrepeat'])
    pcs = sorted(expected)

    def rejected(action, diagnostic):
        try:
            action()
        except CheckError as error:
            require(diagnostic in str(error), 'negative control failed for the wrong reason: ' + str(error))
        else:
            raise CheckError('negative control accepted ' + diagnostic)

    changed = dict(expected)
    del changed[pcs[1]]
    rejected(lambda: coverage(pcs, changed, 'dropped-record control'), 'PC coverage missing=')
    changed = dict(expected)
    changed[pcs[1]] = (1,)
    rejected(lambda: pairing(expected, changed, 'changed-kind control'), 'descriptor mismatch')
    rooted = next((pc for pc in pcs if len(expected[pc]) >= 3), None)
    require(rooted is not None, 'negative controls need a body descriptor with bitmap words')
    changed = dict(expected)
    words = list(changed[rooted])
    words[1] ^= 1
    changed[rooted] = tuple(words)
    rejected(lambda: pairing(expected, changed, 'changed-rootmask control'), 'descriptor mismatch')
    rejected(lambda: strict_order(list(reversed(pcs)), 'reversed-order control'), 'raw map order')


def compile_fixture(compiler, folder, source, units, target, inline):
    folder.mkdir(parents=True)
    # Baseline and candidate use the same source pathname. A differing path
    # can change interned source strings and absolute data addresses even
    # when the emitted instructions and metadata semantics are identical.
    program = folder.parent / 'loopmaporder.paslang'
    program.write_text(source)
    executable = folder / 'program'
    command([compiler, '-target', target, '-cpu', 'base', '-inline', str(inline),
             '-Fu', units, '-o', executable, program], folder, 'compile')
    require(executable.is_file() and executable.with_suffix('.o').is_file(),
            str(folder) + ': compilation did not produce executable and object')
    return ELF(executable.with_suffix('.o')), ELF(executable)


def inspect(obj, executable, folder, inline, ordered):
    calls = disassembled_calls(obj, folder)
    object_descriptors = object_maps(obj, calls, ordered, inline)
    rows, descriptors = linked_maps(executable, ordered)
    object_link_pairing(obj, executable, object_descriptors, descriptors)
    report = {'raw_pcs': rows, 'object_descriptors': object_descriptors,
              'linked_descriptors': descriptors, 'calls': calls}
    (folder / 'metadata.json').write_text(json.dumps(report, indent=2) + '\n')
    return rows, descriptors, object_descriptors


def compare_baseline(old_obj, old, new_obj, new, old_rows, old_maps, new_maps):
    require(any(a >= b for a, b in zip(old_rows, old_rows[1:])),
            str(old.path) + ': baseline did not reproduce raw map inversion')
    require(old.section_bytes(old.section('.text')) == new.section_bytes(new.section('.text')),
            'baseline comparison: emitted .text bytes changed')
    for name in ROUTINES:
        old_code, new_code = old_obj.section('.text.' + name), new_obj.section('.text.' + name)
        require(old_code.flags == new_code.flags and
                old_obj.section_bytes(old_code) == new_obj.section_bytes(new_code),
                name + ': baseline comparison changed object instructions/section ownership')
        require(old.named_symbol(name) == new.named_symbol(name),
                name + ': baseline comparison changed linked symbol ownership/address')
    pairing(old_maps, new_maps, 'baseline per-PC descriptor pairing')


def main():
    arguments = sys.argv[1:]
    baseline = None
    if len(arguments) == 5 and arguments[3] == '--baseline':
        baseline = Path(arguments[4]).resolve()
        arguments = arguments[:3]
    require(len(arguments) == 3, __doc__)
    compiler, build, qemu = (Path(argument).resolve() for argument in arguments)
    root = Path(__file__).resolve().parents[1]
    source = (root / 'testdata/loopmaporder.paslang').read_text()
    require((root / 'testdata/loopmaporder.out').read_text() == EXPECTED,
            'review the fixture oracle: expected loopmaporder ok')
    build.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='loopmaps-', dir=build))
    print('loopmaps artifacts: ' + str(work), flush=True)
    # Go runtime/symtab.go moduledataverify1 checks PC ordering before lookup.
    # Keep this a raw-file check; startup's defensive sort cannot satisfy it.
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('PASLANG_GC')}
    env['PASLANG_ASYNCPREEMPTOFF'] = '0'
    for target, units, launch in [('amd64', build, []),
                                  ('arm64', build / 'a64', [qemu])]:
        for inline in (0, 40):
            folder = work / (target + '-inline' + str(inline))
            obj, executable = compile_fixture(compiler, folder / 'candidate', source,
                                               units, target, inline)
            rows, descriptors, object_descriptors = inspect(
                obj, executable, folder / 'candidate', inline, True)
            negative_controls(object_descriptors)
            if baseline:
                old_obj, old = compile_fixture(baseline, folder / 'baseline', source,
                                                units, target, inline)
                old_rows, old_maps, _ = inspect(old_obj, old, folder / 'baseline', inline, False)
                compare_baseline(old_obj, old, obj, executable, old_rows, old_maps, descriptors)
                (folder / 'baseline-pairing.txt').write_text(
                    'baseline inversion; identical text and complete per-PC descriptor pairing\n')
            for name, settings in [('run', {}),
                                   ('gc-stacks', {'PASLANG_GCVERIFY': '1',
                                                  'PASLANG_GCSTRESS': '3',
                                                  'PASLANG_GCPOISON': '1'})]:
                result = command([*launch, executable.path], folder / 'candidate', name,
                                 env=dict(env, **settings), timeout=600 if target == 'arm64' else 300)
                require(result.stdout == EXPECTED and not result.stderr,
                        target + ' inline ' + str(inline) + ': fixture output differs in ' + name)
            print(target + ' inline ' + str(inline) + ': complete maps, descriptors, GC and stacks', flush=True)
    print('loopmaps: both targets, inline 0/40, raw object/ELF order, call coverage and metadata controls' +
          ('; baseline inversions with identical per-PC descriptors' if baseline else ''))


if __name__ == '__main__':
    try:
        main()
    except (CheckError, OSError, UnicodeError, struct.error) as error:
        raise SystemExit('loopmaps: ' + str(error))
