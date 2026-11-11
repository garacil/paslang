#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P589 value snapshots and declaration ownership.

Usage: check_call_provenance.py COMPILER BUILDDIR QEMU [PARSER_UNITS]

PARSER_UNITS defaults to BUILDDIR/stage, the existing native compiler units
left by Makefile's stage recipe. They must match the candidate compiler;
this checker never rebuilds production compiler sources. The original runtime matrix
uses exactly four isolated units and one program per target/inline variant
(amd64/arm64, inline 0/40): twenty compilation invocations in total. One
additional native program calls the production ParseSource and FormatIface
APIs. Its parse-only cases run in both target modes, using that target's
actual core interfaces. A forged interface is never linked or executed.
The runtime matrix uses an amd64 host and QEMU for arm64; the parser
harness itself derives its native target from platform.machine().

The golden is standalone. Temporary variants import four ordinary units
with identical exported names and core-looking unit prefixes, through their
compiled .pi interfaces. Generated variants create heap strings and collect
after old global headers are replaced, before and during a recursive stack
growth probe (320 frames of 4 KiB), then read the retained values. The
stack-move counter must increase inside one of these post-overwrite calls.
Shared pointees and slice elements deliberately remain shared; inline values and copied descriptors keep their snapshots.
Const and var parameters provide complementary alias controls.

The parser controls inspect the final AST's public parameter names: v.in
means parameter materialization; v means borrowing. They require the actual
expected call node too. Real exports of the four trusted units must retain
borrowing; ordinary, unknown, conflicting and mismatched owners must copy.
Eleven additional parse-only load-order cases per target use production
serialization of dependency-free interfaces: unknown/approved order, distinct
approved owners, approved reappearance on a real link-only promotion, and a
cross-owner symbol conflict observable before promotion. The latter would
lose materialization if registration moved after LinkOnly's early return;
its distinct-symbol control must retain borrowing. Actual public UsesNames,
DepNames and imported-export visibility enforce the intended order.
The independent class-field object_matrix adds four real ordinary units and
one program per target/inline variant: twenty additional compilations and
36 exact-output rows per run. It checks shallow aggregate snapshots versus
shared object contents after the only explicit global reference is replaced,
then collection and observed stack relocation.
It does not claim the copied value is the only physical GC root.
All generated sources, interfaces, objects and executables stay temporary.
"""
import os
import platform
from pathlib import Path
import re
import subprocess
import sys
import tempfile

CORES = ('pasmap', 'pasfmt', 'pasheap', 'pasquad')
MODES = ('value', 'expr', 'const', 'var')
ROWS = {
    'value': '7 8 61 9 seed managed 41 2 51 2',
    'expr': '7 8 61 9 seed managed 41 2 51 2',
    'const': '97 98 62 99 changed changed 49 1 59 1',
    'var': '97 98 62 99 changed changed 49 1 59 1',
}
ARG_NAMES = ('GRecord', 'GStatic', 'GString', 'GManaged', 'GSlice')
PARAMS = 'R: TRecord; A: TStatic; S: string; M: TManaged; D: TSlice'
FIELDS = ("R.N, ' ', R.Pad[1], ' ', R.Target^, ' ', A[1], ' ', S, ' ', "
          "M.LabelText, ' ', M.Items[0], ' ', Length(M.Items), ' ', "
          "D[0], ' ', Length(D)")


ROOT_STRESS = r'''function RootStress(N: Integer): Integer;
var Frame: array[0..511] of Integer;
begin
  Frame[N mod 512] := N;
  if N = 0 then
  begin
    if GcCollect <> 1 then Halt(81);
    Result := Frame[0];
  end
  else
    Result := RootStress(N - 1) + Frame[N mod 512] - N;
end;

procedure PreserveRoots;
var BeforeGrowth: Integer;
begin
  BeforeGrowth := HeapStat(13);
  if GcCollect <> 1 then Halt(82);
  if RootStress(320) <> 0 then Halt(83);
  if HeapStat(13) > BeforeGrowth then RootGrowthObserved := 1;
  if GcCollect <> 1 then Halt(84);
end;
'''


def rooted_variant(golden):
    changes = (
        ('  GPointed, GOther: Integer;\n', '  GPointed, GOther: Integer;\n  RootGrowthObserved: Integer;\n'),
        ("  GString := 'seed';", "  GString := StringOfChar('s', ParamCount + 1) + 'eed';"),
        ("  GManaged.LabelText := 'managed';", "  GManaged.LabelText := StringOfChar('m', ParamCount + 1) + 'anaged';"),
        ('procedure ApplyChange;', ROOT_STRESS + '\nprocedure ApplyChange;'),
        ('  GPointed := 61;\nend;', '  GPointed := 61;\n  PreserveRoots;\nend;'),
        ('  { P589_IMPORTED_RUNS }\nend.', '  { P589_IMPORTED_RUNS }\n  if RootGrowthObserved = 0 then Halt(85);\nend.'),
    )
    for before, after in changes:
        if golden.count(before) != 1:
            fail('rooted fixture anchor is not unique: ' + before)
        golden = golden.replace(before, after)
    return golden


HARNESS = r'''{ P589: public production parser/compiled-interface APIs only.
  Copyright (C) 2026 Germán Luis Aracil Boned.
  GPL version 3 or later; see COPYING. No warranty. }
program callownerast;
uses pasast, pasparse, pasiface, paslib;

function ExprCalls(E: PExpr; const Sym: string): Boolean;
var I: Integer;
begin
  Result := False;
  if E = nil then Exit;
  if (E^.Kind = ekCall) and (E^.Name = Sym) then
  begin Result := True; Exit; end;
  if ExprCalls(E^.L, Sym) or ExprCalls(E^.R, Sym) then
  begin Result := True; Exit; end;
  for I := 0 to High(E^.Args) do
    if ExprCalls(E^.Args[I], Sym) then
    begin Result := True; Exit; end;
end;

function StmtCalls(S: PStmt; const Sym: string): Boolean;
var I: Integer;
begin
  Result := False;
  if S = nil then Exit;
  if (S^.Kind = skCall) and (S^.Name = Sym) then
  begin Result := True; Exit; end;
  if ExprCalls(S^.E, Sym) or ExprCalls(S^.E2, Sym) or
     ExprCalls(S^.Dest, Sym) then
  begin Result := True; Exit; end;
  for I := 0 to High(S^.Args) do
    if ExprCalls(S^.Args[I], Sym) then
    begin Result := True; Exit; end;
  if StmtCalls(S^.ThenSt, Sym) or StmtCalls(S^.ElseSt, Sym) or
     StmtCalls(S^.Body, Sym) then
  begin Result := True; Exit; end;
  for I := 0 to High(S^.Stmts) do
    if StmtCalls(S^.Stmts[I], Sym) then
    begin Result := True; Exit; end;
end;

var
  Source, CallSym, Joined: string;
  Paths: array of string;
  Model: TProgram;
  I, Seen: Integer;
  Arm: Boolean;
begin
  if (ParamStr(1) = 'forge') or (ParamStr(1) = 'forge-bare') then
  begin
    if (ParamStr(1) = 'forge') and (ParamCount <> 7) then Halt(2);
    if (ParamStr(1) = 'forge-bare') and (ParamCount <> 8) then Halt(2);
    if not ReadFile(ParamStr(2), Source) then Halt(3);
    Paths := [ParamStr(3)];
    Arm := ParamStr(4) = 'arm64';
    Model := ParseSource(Source, Paths, Arm, 0, 0);
    if ParamStr(1) = 'forge-bare' then
    begin
      { A real core-named source skips automatic LoadCore. Check that
        no implicit dependency can move the controlled import order. }
      if (not Model.IsUnit) or (Model.Name <> 'passtr') then Halt(9);
      if (Length(Model.UsesNames) <> 0) or (Length(Model.DepNames) <> 0) or
         (Length(Model.LinkObjs) <> 0) then Halt(10);
    end;
    Seen := 0;
    for I := 0 to High(Model.Procs) do
      if (not Model.Procs[I].IsExt) and
         (Model.Procs[I].Name = 'foreignchange') then
      begin
        Model.Procs[I].Sym := ParamStr(5);
        if ParamStr(1) = 'forge-bare' then
          Model.Procs[I].Name := ParamStr(8);
        Seen := Seen + 1;
      end;
    if Seen <> 1 then Halt(4);
    Model.Name := ParamStr(6);
    if not WriteFile(ParamStr(7), FormatIface(Model)) then Halt(5);
    WriteLn('forged interface');
  end
  else
  begin
    if ((ParamStr(1) <> 'ast') and (ParamStr(1) <> 'ast-order')) or
       (ParamCount <> 6) then Halt(2);
    if not ReadFile(ParamStr(2), Source) then Halt(3);
    Paths := [ParamStr(3), ParamStr(4)];
    Arm := ParamStr(5) = 'arm64';
    CallSym := ParamStr(6);
    Model := ParseSource(Source, Paths, Arm, 0, 0);
    Seen := 0;
    for I := 0 to High(Model.Procs) do
      if (not Model.Procs[I].IsExt) and (Model.Procs[I].Name = 'probe') then
      begin
        if Length(Model.Procs[I].Params) = 0 then Halt(6);
        if (CallSym <> '') and (not StmtCalls(Model.Procs[I].Body, CallSym)) then
          Halt(7);
        WriteLn(Model.Procs[I].Params[0].Name);
        if CallSym <> '' then WriteLn(CallSym);
        Seen := Seen + 1;
      end;
    if Seen <> 1 then Halt(8);
    if ParamStr(1) = 'ast-order' then
    begin
      Joined := '';
      for I := 0 to High(Model.UsesNames) do
      begin
        if I > 0 then Joined := Joined + ',';
        Joined := Joined + Model.UsesNames[I];
      end;
      WriteLn('uses:', Joined);
      Joined := '';
      for I := 0 to High(Model.DepNames) do
      begin
        if I > 0 then Joined := Joined + ',';
        Joined := Joined + Model.DepNames[I];
      end;
      WriteLn('loaded:', Joined);
      Seen := 0;
      for I := 0 to High(Model.Procs) do
        if Model.Procs[I].IsExt and (Model.Procs[I].Name = 'quadcall') then
          Seen := Seen + 1;
      WriteLn('quad-visible:', Seen);
    end;
  end;
end.
'''

RECORD = 'type TR = record N: Integer; Pad: array[0..2] of Integer; end;\n'
FOREIGN = ('unit foreign589;\ninterface\nprocedure foreignchange;\n'
           'implementation\nprocedure foreignchange;\nbegin end;\nend.\n')

BARE_FOREIGN = FOREIGN.replace('unit foreign589;', 'unit passtr;')


def fail(message):
    raise SystemExit('call-provenance: ' + message)


def command(arguments, directory, *, expected=None, env=None, timeout=180):
    try:
        result = subprocess.run(list(map(str, arguments)), cwd=directory,
                                env=env, capture_output=True, text=True,
                                timeout=timeout)
    except subprocess.TimeoutExpired:
        fail('timeout: ' + ' '.join(map(str, arguments)))
    if result.returncode or result.stderr or (expected is not None and result.stdout != expected):
        fail('unexpected result: ' + ' '.join(map(str, arguments)) +
             '\nexit=' + str(result.returncode) + '\n' + result.stdout + result.stderr +
             ('' if expected is None else '\nexpected:\n' + expected))
    return result


def exported_symbol(interface, name):
    rows = [line.split() for line in interface.read_text().splitlines()]
    found = [row[2] for row in rows if len(row) >= 3 and row[0] == 'FUNC' and row[1].casefold() == name.casefold()]
    if len(found) != 1:
        fail(str(interface) + ': expected one export ' + name)
    return found[0]


def helper_source(golden, unit):
    # Reuse the same fixture declarations and mutations as the standalone
    # golden, then export matching names in every ordinary helper unit.
    decl = golden[golden.index('type\n'):golden.index('procedure Reset;')]
    state = golden[golden.index('procedure Reset;'):golden.index('procedure ordinary_change;')]
    out = ['unit ' + unit + ';\ninterface\n', decl, 'procedure Reset;\n']
    for mode in MODES:
        prefix = 'const ' if mode == 'const' else 'var ' if mode == 'var' else ''
        formal = '; '.join(prefix + part for part in PARAMS.split('; '))
        out.append('procedure ordinary_' + mode + '(' + formal + ');\n')
    out += ['implementation\n', state,
            'procedure ordinary_change;\nbegin ApplyChange; end;\n',
            'function ordinary_result: Integer;\nbegin ApplyChange; Result := 0; end;\n']
    for mode in MODES:
        prefix = 'const ' if mode == 'const' else 'var ' if mode == 'var' else ''
        formal = '; '.join(prefix + part for part in PARAMS.split('; '))
        out.append('procedure ordinary_' + mode + '(' + formal + ');\n')
        if mode == 'expr':
            out.append('var K: Integer;\n')
        out.append('begin\n')
        out.append('  K := ordinary_result;\n' if mode == 'expr' else '  ordinary_change;\n')
        out.append("  WriteLn('" + unit + ' ' + mode + " ', " + FIELDS + ');\nend;\n')
    out.append('end.\n')
    return ''.join(out)


def runtime_matrix(compiler, build, qemu, work, golden, expected):
    golden = rooted_variant(golden)
    helpers = tuple(core + '_helpers' for core in CORES)
    for target, core_units, runner in (
            ('amd64', build, []), ('arm64', build / 'a64', [qemu])):
        for inline in (0, 40):
            folder = work / (target + '-inline' + str(inline))
            sources = folder / 'sources'
            units = folder / 'units'
            sources.mkdir(parents=True)
            units.mkdir()
            flags = [compiler, '-target', target, '-cpu', 'base', '-inline', str(inline)]
            symbols = []
            for unit in helpers:
                source = sources / (unit + '.paslang')
                source.write_text(helper_source(golden, unit))
                command([*flags, '-c', '-Fu', units, '-Fu', core_units,
                         '-o', units / unit, source], folder)
                interface = units / (unit + '.pi')
                if not interface.is_file() or not (units / (unit + '.o')).is_file():
                    fail(unit + ': compiled .pi/.o control is missing')
                if not re.search(r'^UNIT ' + unit + r'$', interface.read_text(), re.M):
                    fail(unit + ': interface has a different unit name')
                symbols.extend(exported_symbol(interface, 'ordinary_' + mode) for mode in MODES)
            calls = []
            matrix_expected = expected
            for unit in helpers:
                arguments = ', '.join(unit + '.' + name for name in ARG_NAMES)
                for mode in MODES:
                    calls.append('  ' + unit + '.Reset;\n  ' + unit + '.ordinary_' + mode + '(' + arguments + ');\n')
                    matrix_expected += unit + ' ' + mode + ' ' + ROWS[mode] + '\n'
            source = folder / 'callprovenance.paslang'
            source.write_text(golden.replace('{ P589_IMPORTS }', 'uses ' + ', '.join(helpers) + ';')
                              .replace('  { P589_IMPORTED_RUNS }', ''.join(calls)))
            executable = folder / 'callprovenance'
            command([*flags, '-Fu', units, '-Fu', core_units, '-o', executable, source], folder)
            assembly = executable.with_suffix('.s').read_text()
            for symbol in symbols:
                if not re.search(r'^\s*(?:call|bl)\s+' + re.escape(symbol) + r'\s*$', assembly, re.M):
                    fail(target + ': no actual imported call of ' + symbol)
            env = dict(os.environ, PASLANG_GCVERIFY='1', PASLANG_GCSTRESS='1', PASLANG_GCPOISON='1')
            command([*runner, executable], folder, expected=matrix_expected, env=env)


def probe_source(body, *, uses='', declarations='', extra_params='', result='Integer'):
    return ('program ownerprobe;\n' + ('uses ' + uses + ';\n' if uses else '') + RECORD +
            declarations + '\nfunction probe(v: TR' + extra_params + '): ' + result + ';\nbegin\n' +
            body + '\nend;\nbegin end.\n')


def bare_interface(harness, directory, units, target, owner, export, symbol):
    """Production serialization of a dependency-free parse-only interface."""
    source = directory / (owner + '-source.paslang')
    source.write_text(BARE_FOREIGN)
    interface = directory / (owner + '.pi')
    command([harness, 'forge-bare', source, units, target, symbol, owner,
             interface, export], directory, expected='forged interface\n')
    rows = [line.split() for line in interface.read_text().splitlines()]
    if [row for row in rows if row[:1] == ['UNIT']] != [['UNIT', owner]]:
        fail(owner + ': controlled interface UNIT differs')
    if any(row[:1] in (['USE'], ['DEP']) for row in rows):
        fail(owner + ': controlled interface acquired an implicit dependency')
    exports = [row for row in rows if row[:1] == ['FUNC']]
    if len(exports) != 1 or exports[0][1:3] != [export, symbol]:
        fail(owner + ': controlled interface export differs')
    if interface.with_suffix('.o').exists():
        fail(owner + ': parse-only fixture unexpectedly has an object')


def order_source(before, after, call, *, automatic_core):
    # passtr is core-named but NOT one of CallUnitId's four approved units.
    # It skips LoadCore; owner589 instead exercises the real automatic path.
    owner = 'owner589' if automatic_core else 'passtr'
    return ('unit ' + owner + ';\ninterface\nuses ' + ', '.join(before) + ';\n' + RECORD +
            'function probe(v: TR): Integer;\nimplementation\n' +
            ('uses ' + ', '.join(after) + ';\n' if after else '') +
            'function probe(v: TR): Integer;\nbegin\n  ' + call + ';\n  Result := v.N;\nend;\nend.\n')


def load_order_controls(harness, units, target, folder):
    """Observe actual AST/load metadata; do not reimplement NoteCallUnit."""
    # Each row's oracle is the language's materialization/borrowing outcome.
    # Shared forged symbols are never linked or executed as core routines.
    shared = 'p_pasheap_order_shared589'
    specs = [
        ('heap-only', ('pasheap',), (), 'heapcall', 'v', False, False),
        ('quad-only', ('pasquad',), (), 'quadcall', 'v', False, False),
        ('unknown-only', ('foreign589',), (), 'unknowncall', 'v.in', False, False),
        ('unknown-then-approved', ('foreign589', 'pasheap'), (), 'heapcall', 'v.in', False, False),
        ('approved-then-unknown', ('pasheap', 'foreign589'), (), 'heapcall', 'v.in', False, False),
        ('two-approved-heap-quad', ('pasheap', 'pasquad'), (), 'quadcall', 'v.in', False, False),
        ('two-approved-quad-heap', ('pasquad', 'pasheap'), (), 'heapcall', 'v.in', False, False),
        ('unknown-core-promoted', ('foreign589',), ('pasquad',), 'quadcall', 'v.in', True, False),
        ('approved-conflict-promoted', ('pasheap',), ('pasquad',), 'quadcall', 'v.in', True, False),
        ('linkonly-core-conflict', ('pasheap',), (), 'heapcall', 'v.in', True, False),
        ('linkonly-distinct-control', ('pasheap',), (), 'heapcall', 'v', True, True),
    ]
    for name, before, after, call, parameter, automatic, distinct in specs:
        case = folder / (target + '-order-' + name)
        case.mkdir()
        for owner, export in (('foreign589', 'unknowncall'), ('pasheap', 'heapcall'), ('pasquad', 'quadcall')):
            symbol = shared
            if distinct and owner == 'pasquad':
                symbol = 'p_pasquad_order_distinct589'
            elif automatic and owner == 'pasheap' and owner not in before:
                # LoadCore also links pasheap last. Keep that unrelated load
                # separate from the unknown -> pasquad -> pasquad sequence.
                symbol = 'p_pasheap_order_unrelated589'
            bare_interface(harness, case, units, target, owner, export, symbol)
        source = case / 'probe.paslang'
        text = order_source(before, after, call, automatic_core=automatic)
        source.write_text(text)
        # The serialized interfaces have no USE/DEP edges. Verify the actual
        # consumer's source clauses as well as public ParseSource load metadata.
        clauses = re.findall(r'^uses (.+);$', text, re.M)
        expected_clauses = [', '.join(before)] + ([', '.join(after)] if after else [])
        if clauses != expected_clauses:
            fail(name + ': controlled source USE order differs')
        observed = command([harness, 'ast-order', source, case, units, target, shared], case).stdout.splitlines()
        if observed[:2] != [parameter, shared] or len(observed) != 5:
            fail(name + ': actual AST parameter/call differs: ' + repr(observed))
        if observed[2] != 'uses:' + ','.join((*before, *after)):
            fail(name + ': ParseSource source USE order differs: ' + repr(observed))
        if not observed[3].startswith('loaded:'):
            fail(name + ': no public dependency-load observation')
        loaded = observed[3][len('loaded:'):].split(',')
        if automatic:
            # LoadCore calls pasquad with LinkOnly=True before implementation
            # uses; a later normal load promotes it without a second FLoaded row.
            selected = [unit for unit in loaded if unit in ('foreign589', 'pasheap', 'pasquad')]
            expected_loads = [*before, 'pasquad']
            if 'pasheap' not in before:
                expected_loads.append('pasheap')
            if selected != expected_loads:
                fail(name + ': automatic core load order differs: ' + repr(loaded))
        elif loaded != list(before):
            fail(name + ': bare consumer unexpectedly loaded other units: ' + repr(loaded))
        visible = 1 if 'pasquad' in (*before, *after) else 0
        if observed[4] != 'quad-visible:' + str(visible):
            fail(name + ': link-only/promoted namespace visibility differs: ' + repr(observed))
        if any(case.glob('*.o')):
            fail(name + ': a forged interface was assembled or linked')
    return len(specs)


def parser_controls(compiler, build, parser_units, work):
    for name in ('pasast', 'pasparse', 'pasiface', 'paslib'):
        for suffix in ('.pi', '.o'):
            path = parser_units / (name + suffix)
            if not path.is_file():
                fail(str(path) + ': native compiler-unit prerequisite is missing; pass the matching PARSER_UNITS directory')
    folder = work / 'parser'
    folder.mkdir()
    source = folder / 'callownerast.paslang'
    source.write_text(HARNESS)
    harness = folder / 'callownerast'
    host = platform.machine().casefold()
    native_target = {'x86_64': 'amd64', 'amd64': 'amd64', 'aarch64': 'arm64', 'arm64': 'arm64'}.get(host)
    if native_target is None:
        fail('unsupported native parser-harness machine: ' + host)
    command([compiler, '-target', native_target, '-cpu', 'base', '-inline', '0',
             '-Fu', parser_units, '-Fu', build, '-o', harness, source], folder)
    count = 0
    for target, units in (('amd64', build), ('arm64', build / 'a64')):
        cases = [('pure', probe_source('  Result := v.N;'), 'v', '')]
        for prefix in ('ordinary', *CORES):
            symbol = 'p_' + prefix + '_change'
            declarations = 'procedure ' + prefix + '_change;\nbegin end;\n'
            cases.append(('local-' + prefix,
                          probe_source('  ' + prefix + '_change;\n  Result := v.N;', declarations=declarations),
                          'v.in', symbol))
        production = (
            ('pasmap', 'PasMapClear', '  PasMapClear(nil, nil);\n  Result := v.N;'),
            ('pasfmt', 'PasFmtInt', '  Result := v.N + Length(PasFmtInt(1, 0));'),
            ('pasheap', 'PasHeapCheck', '  Result := v.N + PasHeapCheck(nil);'),
            ('pasquad', 'PasQCmp', '  Result := v.N + PasQCmp(0, 0, 0, 0);'),
        )
        real_symbols = {}
        for unit, export, body in production:
            symbol = exported_symbol(units / (unit + '.pi'), export)
            real_symbols[unit] = symbol
            cases.append(('core-' + unit, probe_source(body, uses=unit), 'v', symbol))
        cases.append(('raw-runtime', probe_source('  Result := v.N + HeapCheck;'), 'v', 'rt_heapcheck'))
        cases.append(('implicit-quad', probe_source('  Result := a + b;', extra_params='; a, b: Quad', result='Quad'),
                      'v', 'rtq_add'))
        for name, text, parameter, symbol in cases:
            case = folder / (target + '-' + name)
            case.mkdir()
            source = case / 'probe.paslang'
            source.write_text(text)
            expected = parameter + '\n' + (symbol + '\n' if symbol else '')
            command([harness, 'ast', source, case, units, target, symbol], case, expected=expected)
            count += 1
        # Production serialization maintains the checksums and type metadata.
        # No object is supplied for these interfaces: only ParseSource reads them.
        for unit in CORES:
            for kind in ('unknown', 'conflict', 'header'):
                case = folder / (target + '-' + kind + '-' + unit)
                case.mkdir()
                source = case / 'foreign589.paslang'
                source.write_text(FOREIGN)
                symbol = real_symbols[unit] if kind == 'conflict' else 'p_' + unit + '_foreign589_' + kind
                header = unit if kind == 'header' else 'foreign589'
                command([harness, 'forge', source, units, target, symbol, header,
                         case / 'foreign589.pi'], case, expected='forged interface\n')
                probe = case / 'probe.paslang'
                probe.write_text(probe_source('  foreign589.foreignchange;\n  Result := v.N;', uses='foreign589'))
                command([harness, 'ast', probe, case, units, target, symbol], case,
                        expected='v.in\n' + symbol + '\n')
                count += 1
        count += load_order_controls(harness, units, target, folder)
    return count



# P589 class fields retain the copied reference and shared object contents.
# Records copy their inline values/descriptors, including the class pointer;
# the object that pointer denotes stays shared (MANUAL section 6, TYPES).
OBJECT_ROWS = {
    'value': '7 carrier 61 mutated 97 changed 62 replacement',
    'expr': '7 carrier 61 mutated 97 changed 62 replacement',
    'const': '97 changed 62 replacement 97 changed 62 replacement',
    'var': '97 changed 62 replacement 97 changed 62 replacement',
}
OBJECT_FIELDS = ("R.N, ' ', R.LabelText, ' ', R.Target.N, ' ', R.Target.LabelText, ' ', "
                 "GObject.N, ' ', GObject.LabelText, ' ', GObject.Target.N, ' ', GObject.Target.LabelText")

OBJECT_DECLS = r"""type
  TProbeObject589 = class
    N: Integer;
    LabelText: string;
  end;
  TObjectArg589 = record
    N: Integer;
    LabelText: string;
    Target: TProbeObject589;
  end;
var
  GObject: TObjectArg589;
  ObjectGrowthObserved: Integer;
"""

OBJECT_STATE = r"""function ObjectRootStress(N: Integer): Integer;
var Frame: array[0..511] of Integer;
begin
  Frame[N mod 512] := N;
  if N = 0 then
  begin
    if GcCollect <> 1 then Halt(181);
    Result := Frame[0];
  end
  else
    Result := ObjectRootStress(N - 1) + Frame[N mod 512] - N;
end;

procedure ObjectPreserveRoots;
var BeforeGrowth: Integer;
begin
  BeforeGrowth := HeapStat(13);
  if GcCollect <> 1 then Halt(182);
  if ObjectRootStress(320) <> 0 then Halt(183);
  if HeapStat(13) > BeforeGrowth then ObjectGrowthObserved := 1;
  if GcCollect <> 1 then Halt(184);
end;

procedure ResetObjects;
begin
  ObjectGrowthObserved := 0;
  GObject.N := 7;
  GObject.LabelText := StringOfChar('c', ParamCount + 1) + 'arrier';
  GObject.Target := TProbeObject589.Create;
  GObject.Target.N := 60;
  GObject.Target.LabelText := StringOfChar('o', ParamCount + 1) + 'ld';
end;

procedure ApplyObjectChange;
begin
  { Mutate through the old class reference before replacing that header.
    No second source variable/global retains the old class reference. }
  GObject.Target.N := 61;
  GObject.Target.LabelText := StringOfChar('m', ParamCount + 1) + 'utated';
  GObject.Target := TProbeObject589.Create;
  GObject.Target.N := 62;
  GObject.Target.LabelText := StringOfChar('r', ParamCount + 1) + 'eplacement';
  GObject.N := 97;
  GObject.LabelText := StringOfChar('c', ParamCount + 1) + 'hanged';
  { The reader's record value and old reference must remain usable across
    collection and actual stack relocation after replacement. }
  ObjectPreserveRoots;
end;
"""

OBJECT_NOTICE = ("{ P589 class-field snapshots and shared object contents.\n"
                 "  Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>\n"
                 "  GPL version 3 or later; see COPYING. No warranty. }\n")


def object_head(prefix, mode):
    modifier = 'const ' if mode == 'const' else 'var ' if mode == 'var' else ''
    return 'procedure ' + prefix + '_object_' + mode + '(' + modifier + 'R: TObjectArg589);\n'


def object_readers(prefix, label):
    out = [
        'procedure ' + prefix + '_object_change;\nbegin ApplyObjectChange; end;\n',
        'function ' + prefix + '_object_result: Integer;\nbegin ApplyObjectChange; Result := 0; end;\n',
    ]
    for mode in MODES:
        out.append(object_head(prefix, mode))
        if mode == 'expr':
            out.append('var K: Integer;\n')
        out.append('begin\n')
        out.append('  K := ' + prefix + '_object_result;\n' if mode == 'expr'
                   else '  ' + prefix + '_object_change;\n')
        out.append('  if ObjectGrowthObserved = 0 then Halt(185);\n')
        out.append("  WriteLn('" + label + ' ' + mode + " ', " + OBJECT_FIELDS + ');\nend;\n')
    return ''.join(out)


def object_unit_source(unit):
    # Real source compiled by the candidate: no forged object or .pi.
    heads = ''.join(object_head('ordinary', mode) for mode in MODES)
    return (OBJECT_NOTICE + 'unit ' + unit + ';\ninterface\n' + OBJECT_DECLS +
            'procedure ResetObjects;\n' + heads + 'implementation\n' +
            OBJECT_STATE + object_readers('ordinary', 'import ' + unit) + 'end.\n')


def object_program_source(helpers):
    out = [OBJECT_NOTICE, 'program objectprovenance589;\n',
           'uses ' + ', '.join(helpers) + ';\n', OBJECT_DECLS, OBJECT_STATE]
    for prefix in ('ordinary', *CORES):
        out.append(object_readers(prefix, 'direct ' + prefix))
    out.append('begin\n')
    for prefix in ('ordinary', *CORES):
        for mode in MODES:
            out.append('  ResetObjects;\n  ' + prefix + '_object_' + mode + '(GObject);\n')
    for unit in helpers:
        for mode in MODES:
            out.append('  ' + unit + '.ResetObjects;\n  ' + unit +
                       '.ordinary_object_' + mode + '(' + unit + '.GObject);\n')
    out.append('end.\n')
    return ''.join(out)


def object_expected(helpers):
    # Complete literal observations. No provenance/cache-join oracle.
    rows = []
    for prefix in ('ordinary', *CORES):
        for mode in MODES:
            rows.append('direct ' + prefix + ' ' + mode + ' ' + OBJECT_ROWS[mode])
    for unit in helpers:
        for mode in MODES:
            rows.append('import ' + unit + ' ' + mode + ' ' + OBJECT_ROWS[mode])
    return '\n'.join(rows) + '\n'


def object_matrix(compiler, build, qemu, work):
    """Separate class-reference value/alias controls; old matrices stay intact."""
    helpers = tuple(core + '_object589' for core in CORES)
    expected = object_expected(helpers)
    for target, core_units, runner in (
            ('amd64', build, []), ('arm64', build / 'a64', [qemu])):
        for inline in (0, 40):
            folder = work / ('objects-' + target + '-inline' + str(inline))
            sources = folder / 'sources'
            units = folder / 'units'
            sources.mkdir(parents=True)
            units.mkdir()
            flags = [compiler, '-target', target, '-cpu', 'base', '-inline', str(inline)]
            symbols = []
            for unit in helpers:
                source = sources / (unit + '.paslang')
                source.write_text(object_unit_source(unit))
                command([*flags, '-c', '-Fu', units, '-Fu', core_units,
                         '-o', units / unit, source], folder)
                interface = units / (unit + '.pi')
                if not interface.is_file() or not (units / (unit + '.o')).is_file():
                    fail(unit + ': object matrix compiled .pi/.o is missing')
                if not re.search(r'^UNIT ' + unit + r'$', interface.read_text(), re.M):
                    fail(unit + ': object matrix interface has another unit identity')
                symbols.extend(exported_symbol(interface, 'ordinary_object_' + mode) for mode in MODES)
            source = folder / 'objectprovenance589.paslang'
            source.write_text(object_program_source(helpers))
            executable = folder / 'objectprovenance589'
            command([*flags, '-Fu', units, '-Fu', core_units, '-o', executable, source], folder)
            assembly = executable.with_suffix('.s').read_text()
            for symbol in symbols:
                if not re.search(r'^\s*(?:call|bl)\s+' + re.escape(symbol) + r'\s*$', assembly, re.M):
                    fail(target + ': object matrix has no real imported call of ' + symbol)
            env = dict(os.environ, PASLANG_GCVERIFY='1', PASLANG_GCSTRESS='1', PASLANG_GCPOISON='1')
            command([*runner, executable], folder, expected=expected, env=env)
    print('call-provenance objects: 36 literal rows per variant, both targets/inline 0+40; '
          'record/string/class-reference snapshots, shared object mutation and const/var aliases '
          'survive post-overwrite collection and observed stack relocation')


def main():
    if len(sys.argv) not in (4, 5):
        fail(__doc__)
    compiler = Path(sys.argv[1]).resolve()
    build = Path(sys.argv[2]).resolve()
    qemu = Path(sys.argv[3]).resolve()
    parser_units = Path(sys.argv[4]).resolve() if len(sys.argv) == 5 else build / 'stage'
    root = Path(__file__).resolve().parents[1]
    golden = (root / 'testdata/callprovenance.paslang').read_text()
    expected = (root / 'testdata/callprovenance.out').read_text()
    if golden.count('{ P589_IMPORTS }') != 1 or golden.count('{ P589_IMPORTED_RUNS }') != 1:
        fail('standalone golden has lost its two fixture insertion sites')
    with tempfile.TemporaryDirectory(prefix='call-provenance-', dir=build) as tmp:
        work = Path(tmp)
        # Diagnose prerequisites before spending the twenty matrix compilations.
        count = parser_controls(compiler, build, parser_units, work)
        runtime_matrix(compiler, build, qemu, work, golden, expected)
        object_matrix(compiler, build, qemu, work)
    print('call-provenance: both targets and inline 0/40 preserve value snapshots, '
          'const/var aliases and pointer/slice sharing; four ordinary prefix units '
          'import through .pi; ' + str(count) + ' production-parser policy controls; '
          'real core AST borrowing policy retained (instruction cost and timing require separate measurement)')


if __name__ == '__main__':
    main()
