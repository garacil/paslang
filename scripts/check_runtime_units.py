#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P588: runtime-unit exclusion, its frame consequence and cooperative progress.

Usage: check_runtime_units.py COMPILER BUILDDIR QEMU

Read the actual built runtime units at both processor levels of both targets.
Compile isolated units bearing the three runtime names, and an ordinary positive
control, with identical Pascal bodies. Only the fake pasdebug is linked, against
real core objects; the fake core units never enter a program. All generated
files, compiler working directories and executables stay under a TemporaryDirectory.
No source of the compiler or runtime is rewritten by this checker.
"""
import importlib.util
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

# Loading the checker below must not leave caches beside project sources.
sys.dont_write_bytecode = True


RUNTIME_UNITS = ('pasheap', 'pasroutines', 'pasdebug')
ASYNC_SECTION = re.compile(r'^\s*\.section\s+pasasync(?:\.|[,\s])', re.M)


def fail(message):
    raise SystemExit('runtime-units: ' + message)


def command(arguments, directory, *, env=None, timeout=120):
    try:
        return subprocess.run(arguments, cwd=directory, env=env, text=True,
                              capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        fail('timeout: ' + ' '.join(map(str, arguments)))


def successful(arguments, directory):
    result = command(arguments, directory)
    if result.returncode:
        fail('command failed: ' + ' '.join(map(str, arguments)) +
             '\n' + result.stdout + result.stderr)
    return result


def no_async(assembly, label):
    if ASYNC_SECTION.search(assembly):
        fail(label + ': runtime unit has an async section')


def has_async(assembly, label):
    if not ASYNC_SECTION.search(assembly):
        fail(label + ': ordinary code has no async section')


def built_units(build):
    """These are Makefile's base and P143 level directories, not installed units."""
    variants = (
        ('amd64/base', build),
        ('amd64/v3', build / 'v3'),
        ('arm64/base', build / 'a64'),
        ('arm64/v8.2+crypto', build / 'a64' / 'v8.2+crypto'),
    )
    for variant, directory in variants:
        for unit in RUNTIME_UNITS:
            path = directory / (unit + '.s')
            if not path.is_file():
                fail(str(path) + ': actual built unit assembly is missing')
            assembly = path.read_text()
            if not re.search(r'^p_' + unit + r'_[\w.]+:', assembly, re.M):
                fail(str(path) + ': no routine of the expected unit')
            no_async(assembly, variant + ' production ' + unit)
        path = directory / 'passtr.s'
        if not path.is_file():
            fail(str(path) + ': production positive control is missing')
        has_async(path.read_text(), variant + ' production passtr')


def unit_source(name):
    return """unit %s;
interface
type PProbe = ^Integer;
function IdentityLeaf(X: Integer): Integer;
function SumTicks(N: Integer): Integer;
function SpinUntil(Flag: PProbe): Integer;
function CheckedAt(I: Integer): Integer;
function PeekValue(P: PProbe): Integer;
implementation
var Cells: array[0..1] of Integer;
function IdentityLeaf(X: Integer): Integer;
begin
  Result := X + 1;
end;
function SumTicks(N: Integer): Integer;
var I, S: Integer;
begin
  S := 0;
  for I := 1 to N do
    S := S + I * I;
  Result := S;
end;
function SpinUntil(Flag: PProbe): Integer;
var Steps: Integer;
begin
  Steps := 0;
  while Flag^ = 0 do
    Steps := Steps + 1;
  Result := Steps;
end;
function CheckedAt(I: Integer): Integer;
begin
  Result := Cells[I];
end;
function PeekValue(P: PProbe): Integer;
begin
  Result := P^;
end;
end.
""" % name


def program_source(name):
    return """program unitprobe;
uses sysutils, %s;
var
  DoneFlag, Steps, CyclesDone: Integer;
  P: PProbe;
  Spare: waitgroup;
  M: map[Integer] of Integer;
function UserPlus(X: Integer): Integer;
begin
  Result := X + 1;
end;
procedure Allocate;
var
  I: Integer;
  Junk: array of Integer;
begin
  Sleep(5);
  for I := 1 to 12 do
  begin
    SetLength(Junk, 0);
    SetLength(Junk, 400);
    Junk[7] := I;
    CyclesDone := CyclesDone + GcCollect;
  end;
  AtomicStore(DoneFlag, 1);
end;
begin
  try
    if ParamStr(1) = 'index' then
      WriteLn(CheckedAt(ParamCount + 2))
    else if ParamStr(1) = 'nil' then
      WriteLn(PeekValue(P))
    else if ParamStr(1) = 'api-wg' then
      Spare.Done
    else if ParamStr(1) = 'api-map' then
      M[1] := 1
    else if ParamStr(1) = 'progress' then
    begin
      pas Allocate;
      Steps := SpinUntil(@DoneFlag);
      WriteLn('progress ', AtomicLoad(DoneFlag), ' cycles ', AtomicLoad(CyclesDone));
    end
    else
      WriteLn('sum ', SumTicks(10), ' leaf ', IdentityLeaf(UserPlus(40)));
  except
    on E: Exception do
      WriteLn('caught ', E.ClassName);
  end;
end.
""" % name


def body(assembly, symbol):
    match = re.search(r'^' + re.escape(symbol) +
                      r':\n(.*?^\s*\.cfi_endproc\s*$)', assembly, re.M | re.S)
    if match is None:
        fail(symbol + ': no complete emitted body')
    return match[1]


def frame_policy(assembly, unit, arm, runtime):
    prefix = 'p_' + unit + '_'
    frame = re.compile(r'\bstp x29, x30\b|\bmov x29, sp\b' if arm
                       else r'pushq %rbp|movq %rsp, %rbp')
    guard = re.compile(r'\[x28, #16\]' if arm else r'16\(%r14\)')
    leaf = body(assembly, prefix + 'identityleaf')
    if frame.search(leaf) or 'rt_morestack' in leaf:
        fail(unit + ': the separate straight-line LeafProc control gained a frame/check')
    loop = body(assembly, prefix + 'sumticks')
    if runtime:
        no_async(assembly, unit + ' fixture')
        if not frame.search(loop) or len(guard.findall(loop)) < 2:
            fail(unit + ': runtime loop lacks its frame or cooperative guard check')
        spin = body(assembly, prefix + 'spinuntil')
        if not frame.search(spin) or len(guard.findall(spin)) < 2 or 'rt_morestack' not in spin:
            fail(unit + ': waiting runtime loop lacks a cooperative slow path')
    else:
        has_async(assembly, unit + ' fixture')
        if frame.search(loop) or guard.search(loop) or 'rt_morestack' in loop:
            fail(unit + ': ordinary FlatProc loop gained a frame/check')


def require_run(arguments, directory, stdout, *, env, timeout):
    result = command(arguments, directory, env=env, timeout=timeout)
    if result.returncode or result.stdout != stdout or result.stderr:
        fail('unexpected execution: ' + ' '.join(map(str, arguments)) +
             '\nexit=' + str(result.returncode) + '\n' +
             result.stdout + result.stderr)


def rejected_elf_owners(executable, folder, checker, arm):
    """Forge ranges within real code whose decoded unit is exactly a runtime unit.

    Ownership comes from the existing paslines records, never symbol spelling.
    Only a pasasync pair changes; matching unit metadata remains untouched.
    Each data-mutated ELF fixture is never executed.
    """
    spec = importlib.util.spec_from_file_location('pasasync_owner_check', checker)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = executable.read_bytes()
    sections, heads = module.sections(data)
    owners = {}
    width = 4 if arm else 1
    for start, end, unit in module.unit_code(data, str(executable)):
        if unit in RUNTIME_UNITS and end - start >= width:
            owners.setdefault(unit, start)
    table = sections['pasasync']
    if table[4] < 16:
        fail('ELF owner control has no table entry to replace')
    for unit in RUNTIME_UNITS:
        if unit not in owners:
            fail('ELF owner control has no code with actual unit metadata for ' + unit)
        forged = bytearray(data)
        start = owners[unit]
        struct.pack_into('<QQ', forged, table[3], start, start + width)
        path = folder / ('forbidden-' + unit)
        path.write_bytes(forged)
        result = command([sys.executable, '-I', str(checker), str(path)], folder)
        diagnostic = result.stdout + result.stderr
        if not result.returncode or 'overlaps runtime unit ' + unit not in diagnostic:
            fail(unit + ': ELF checker did not reject exact runtime-unit ownership:\n' + diagnostic)


def prefix_program_source():
    return """program prefixprobe;
function PasHeap_Probe(X: Integer): Integer;
begin
  Result := X + 1;
end;
function PasRoutines_Probe(X: Integer): Integer;
begin
  Result := X + 1;
end;
function PasDebug_Probe(X: Integer): Integer;
begin
  Result := X + 1;
end;
begin
  WriteLn(PasHeap_Probe(ParamCount) + PasRoutines_Probe(ParamCount + 1) +
    PasDebug_Probe(ParamCount + 2));
end.
"""


def prefix_program(compiler, machine, target, units, launch, checker):
    folder = machine / 'program-prefixes'
    folder.mkdir()
    source = folder / 'prefixprobe.paslang'
    source.write_text(prefix_program_source())
    executable = folder / 'prefixprobe'
    successful([compiler, '-target', target, '-cpu', 'base', '-inline', '0',
                '-Fu', str(units), '-o', str(executable), str(source)], folder)
    assembly = (folder / 'prefixprobe.s').read_text()
    for prefix in RUNTIME_UNITS:
        if '.section pasasync.p_' + prefix + '_probe,' not in assembly:
            fail(target + ': legitimate program name ' + prefix + '_probe lost eligibility')
    successful([sys.executable, '-I', str(checker), str(executable)], folder)
    require_run([*launch, str(executable)], folder, '6\n',
                env=dict(os.environ, PASLANG_ASYNCPREEMPTOFF='0'),
                timeout=180 if target == 'arm64' else 60)


def main():
    if len(sys.argv) != 4:
        fail(__doc__)
    compiler = str(Path(sys.argv[1]).resolve())
    build = Path(sys.argv[2]).resolve()
    qemu = str(Path(sys.argv[3]).resolve())
    root = Path(__file__).resolve().parents[1]
    built_units(build)
    build.mkdir(parents=True, exist_ok=True)
    cpu = str(min(os.sched_getaffinity(0)))
    with tempfile.TemporaryDirectory(prefix='runtime-units-', dir=build) as tmp:
        work = Path(tmp)
        for target, units, launch in (
                ('amd64', build, []),
                ('arm64', build / 'a64', [qemu])):
            machine = work / target
            machine.mkdir()
            prefix_program(compiler, machine, target, units, launch,
                           root / 'scripts/check_pasasync.py')
            folders = {}
            # Separate directories matter: a fake pasheap or pasroutines must
            # never shadow the actual core while compiling/linking pasdebug.
            for unit in (*RUNTIME_UNITS, 'rtuser', 'pasheap_probe'):
                folder = machine / unit
                folder.mkdir()
                folders[unit] = folder
                source = folder / (unit + '.paslang')
                source.write_text(unit_source(unit))
                successful([compiler, '-target', target, '-cpu', 'base',
                            '-inline', '0', '-c', '-Fu', str(folder),
                            '-Fu', str(units), '-o', str(folder / unit),
                            str(source)], folder)
                assembly = (folder / (unit + '.s')).read_text()
                frame_policy(assembly, unit, target == 'arm64',
                             unit in RUNTIME_UNITS)
            for unit in ('pasdebug', 'rtuser', 'pasheap_probe'):
                folder = folders[unit]
                source = folder / 'unitprobe.paslang'
                source.write_text(program_source(unit))
                executable = folder / 'unitprobe'
                successful([compiler, '-target', target, '-cpu', 'base',
                            '-inline', '0', '-Fu', str(folder),
                            '-Fu', str(units), '-o', str(executable),
                            str(source)], folder)
                assembly = (folder / 'unitprobe.s').read_text()
                if '.section pasasync.p_userplus,' not in assembly:
                    fail(target + ' ' + unit + ': user-routine positive control is missing')
                if '.section pasasync..text,' not in assembly:
                    fail(target + ' ' + unit + ': main positive control is missing')
                successful([sys.executable, '-I',
                            str(root / 'scripts/check_pasasync.py'),
                            str(executable)], folder)
                if unit == 'pasdebug':
                    rejected_elf_owners(executable, folder,
                                        root / 'scripts/check_pasasync.py',
                                        target == 'arm64')
                env = dict(os.environ, PASLANG_ASYNCPREEMPTOFF='0')
                timeout = 180 if target == 'arm64' else 60
                args = [*launch, str(executable)]
                require_run(args, folder, 'sum 385 leaf 42\n',
                            env=env, timeout=timeout)
                for mode, expected in (('api-wg', 'ERangeError'),
                                       ('api-map', 'EAccessViolation')):
                    require_run([*args, mode], folder, 'caught ' + expected + '\n',
                                env=env, timeout=timeout)
                for mode, expected, statement in (
                        ('index', 'ERangeError', '  Result := Cells[I];'),
                        ('nil', 'EAccessViolation', '  Result := P^;')):
                    result = command([*args, mode], folder,
                                     env=env, timeout=timeout)
                    if unit != 'pasdebug':
                        if (result.returncode or result.stderr or
                                result.stdout != 'caught ' + expected + '\n'):
                            fail(target + ': ordinary ' + mode +
                                 ' did not reach its handler:\n' +
                                 result.stdout + result.stderr)
                    else:
                        line = unit_source(unit).splitlines().index(statement) + 1
                        reason = ('index 3 out of range [0..1]' if mode == 'index'
                                  else 'nil pointer dereference')
                        expected_line = ('paslang: ' + reason + ' at line ' +
                                         str(line) + ' of unit pasdebug\n')
                        if (result.returncode != 1 or result.stdout or
                                result.stderr != expected_line):
                            fail(target + ': internal ' + mode +
                                 ' must remain fatal at its own line:\nexit=' +
                                 str(result.returncode) + '\n' +
                                 result.stdout + result.stderr)
                # The fake runtime's loop has no async entry: collection must
                # finish through its cooperative check, even with signals off.
                # The ordinary unit supplies the complementary async control.
                progress_env = dict(env, PASLANG_GCVERIFY='1', PASLANG_GCSTRESS='1',
                                    PASLANG_GCPOISON='1',
                                    PASLANG_ASYNCPREEMPTOFF=('1' if unit == 'pasdebug' else '0'))
                require_run(['taskset', '-c', cpu, *args, 'progress'], folder,
                            'progress 1 cycles 12\n', env=progress_env, timeout=timeout)
    print('runtime-units: 12 built runtime variants excluded, 4 production controls; '
          'both targets retain runtime cooperative frames, user async/FlatProc, '
          'straight-line leaves, fatal internal faults and catchable API failures; '
          '6 forged ELF runtime entries rejected by actual unit metadata; '
          'program and ordinary-unit prefix-name controls remain eligible')


if __name__ == '__main__':
    main()
