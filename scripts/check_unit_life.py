#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P576: ordinary lifecycle failures, eligibility, lines and stop room.

Usage: check_unit_life.py COMPILER BUILDDIR QEMU
Every generated source, object, interface, executable and checker-only
assembly mutation stays in a TemporaryDirectory. Fake pasheap/pasroutines
units are compiled only; only fake pasdebug can be linked with real cores.
The room mutations are never assembled or executed. No project source is
rewritten. Both targets and inline 0/40 use the candidate's own built units.
"""
import importlib.util
import os
from pathlib import Path
import re
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
RUNTIME_UNITS = ('pasheap', 'pasroutines', 'pasdebug')
ASYNC_SECTION = re.compile(r'^\s*\.section\s+pasasync(?:\.|[,\s])', re.M)
EMPTY_ASM = '  asm amd64\n  end;\n  asm arm64\n  end;\n'


def fail(message):
    raise SystemExit('unit-life: ' + message)


def run(arguments, folder, *, env=None, timeout=120):
    try:
        return subprocess.run(list(map(str, arguments)), cwd=folder, env=env,
                              text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        fail('timeout: ' + ' '.join(map(str, arguments)))


def good(arguments, folder):
    result = run(arguments, folder)
    if result.returncode:
        fail('command failed: ' + ' '.join(map(str, arguments)) + '\n' + result.stdout + result.stderr)
    return result


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def asm_ranges(text):
    """Actual range labels and containing global function, independent of suffix."""
    labels, owner = {}, None
    for i, line in enumerate(text.splitlines()):
        label = re.fullmatch(r'([.\w]+):', line.strip())
        if not label:
            continue
        name = label.group(1)
        if not name.startswith('.'):
            owner = name
        labels[name] = (i, owner)
    result, table = {}, False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('.section '):
            table = re.match(r'^\.section pasasync(?:[.,\s])', line) is not None
        if table and line.startswith('.quad '):
            words = [word.strip() for word in line[6:].split(',')]
            if len(words) % 2:
                fail('assembly async range is not a pair')
            for start, end in zip(words[::2], words[1::2]):
                if start not in labels or end not in labels:
                    fail('assembly async label is missing')
                lo, own = labels[start]
                hi, end_own = labels[end]
                if lo >= hi or own != end_own:
                    fail('async range crosses a function boundary')
                result.setdefault(own, []).append((start, end, lo, hi))
    return result


def policy(text, unit, init, fini, arm):
    ranges = asm_ranges(text)
    for phase, eligible in (('init', init), ('fini', fini)):
        owner = 'u_' + unit.casefold() + '_' + phase
        entries = ranges.get(owner, [])
        if len(entries) != int(eligible):
            fail(owner + ': wrong lifecycle eligibility (' + str(len(entries)) + ')')
        if not entries:
            continue
        _, _, lo, hi = entries[0]
        lines = text.splitlines()
        begin = lines.index(owner + ':')
        if lo <= begin or not any('rt_morestack' in line for line in lines[begin:lo]):
            fail(owner + ': range does not start past its own prologue check')
        if any('rt_morestack' in line for line in lines[lo:hi]):
            fail(owner + ': eligible body retains a cooperative loop/prologue slow path')
        if arm:
            pools = [i for i in range(begin, len(lines)) if lines[i].strip() == '.ltorg']
            if not pools or hi >= pools[0]:
                fail(owner + ': range includes the arm64 literal pool')


def source(unit, init, fini=None, *, sysutils=True):
    text = 'unit ' + unit + ';\ninterface\nimplementation\n'
    if sysutils:
        text += 'uses sysutils;\n'
    text += 'type PCell = ^Integer;\nvar\n  A: array[0..1] of Integer;\n  I, V, Z: Integer;\n  P: PCell;\n'
    if init is not None:
        text += 'initialization\n' + init
    if fini is not None:
        text += 'finalization\n' + fini
    return text + 'end.\n'


def program(unit):
    return "program lifeuse;\nuses " + unit + ";\nbegin\n  WriteLn('main');\nend.\n"


def compile_unit(compiler, flags, units, folder, unit, text):
    path = folder / (unit.casefold() + '.paslang')
    path.write_text(text)
    prefix = folder / unit.casefold()
    good([compiler, *flags, '-c', '-Fu', folder, '-Fu', units, '-o', prefix, path], folder)
    return prefix.with_suffix('.s').read_text()


def compile_program(compiler, flags, units, folder, text):
    path = folder / 'lifeuse.paslang'
    path.write_text(text)
    executable = folder / 'lifeuse'
    good([compiler, *flags, '-Fu', folder, '-Fu', units, '-o', executable, path], folder)
    return executable


def tables(executable, folder, checker_dir):
    for checker in ('check_pasasync.py', 'check_paslines.py', 'check_maporder.py'):
        good([sys.executable, '-I', checker_dir / checker, executable], folder)


def expect(executable, launch, folder, stdout, env, *, timeout=120):
    result = run([*launch, executable], folder, env=env, timeout=timeout)
    if result.returncode or result.stdout != stdout or result.stderr:
        fail(str(executable) + ': unexpected run\nexit=' + str(result.returncode) + '\n' + result.stdout + result.stderr)


def fatal_cases(compiler, flags, units, root, launch, env, arm):
    failures = (('bounds', 'V := A[I];', 'index 5 out of range [0..1]'),
                ('division', 'V := 70 div Z;', 'integer divide by zero'),
                ('nil', 'V := P^;', 'nil pointer dereference'))
    for phase in ('init', 'fini'):
        for kind, operation, message in failures:
            for mode in ('bare', 'nohandler', 'asm', 'runtime'):
                folder = root / ('fatal-' + phase + '-' + kind + '-' + mode)
                folder.mkdir()
                unit = 'pasdebug' if mode == 'runtime' else 'LifeBad'
                body = '  I := ParamCount + 5;\n  Z := ParamCount;\n'
                if mode == 'asm':
                    body += EMPTY_ASM
                if mode == 'nohandler':
                    body += '  ' + operation + ' { failure }\n'
                else:
                    body += '  try\n    ' + operation + " { failure }\n  except\n    WriteLn('caught');\n  end;\n"
                text = source(unit, body if phase == 'init' else "  WriteLn('init ok');\n",
                              body if phase == 'fini' else None, sysutils=mode != 'bare')
                assembly = compile_unit(compiler, flags, units, folder, unit, text)
                policy(assembly, unit, mode != 'runtime' and (phase != 'init' or mode != 'asm'),
                       phase == 'fini' and mode not in ('asm', 'runtime'), arm)
                # Runtime units exclude both blocks, including a harmless init.
                if mode == 'runtime' and ASYNC_SECTION.search(assembly):
                    fail('runtime lifecycle acquired an async range')
                executable = compile_program(compiler, flags, units, folder, program(unit))
                line = next(i for i, textline in enumerate(text.splitlines(), 1) if '{ failure }' in textline)
                result = run([*launch, executable], folder, env=env)
                stdout = '' if phase == 'init' else 'init ok\nmain\n'
                want = 'paslang: ' + message + ' at line ' + str(line) + ' of unit ' + unit + '\n'
                if result.returncode != 1 or result.stdout != stdout or result.stderr != want:
                    fail(phase + '/' + kind + '/' + mode + ': failure was not fatal at its own unit line\n' + result.stdout + result.stderr)


def mixed_cases(compiler, flags, units, root, launch, env, arm, checker_dir):
    for asm_phase in ('init', 'fini'):
        folder = root / ('mixed-' + asm_phase)
        folder.mkdir()
        bodies = []
        output = []
        for phase in ('init', 'fini'):
            if phase == asm_phase:
                bodies.append(EMPTY_ASM + "  WriteLn('" + phase + " asm');\n")
                output.append(phase + ' asm')
            else:
                bodies.append("  I := ParamCount + 5;\n  try\n    V := A[I];\n  except\n    on E: ERangeError do WriteLn('" + phase + " caught');\n  end;\n")
                output.append(phase + ' caught')
        assembly = compile_unit(compiler, flags, units, folder, 'LifeMixed', source('LifeMixed', *bodies))
        policy(assembly, 'LifeMixed', asm_phase != 'init', asm_phase != 'fini', arm)
        executable = compile_program(compiler, flags, units, folder, program('LifeMixed'))
        tables(executable, folder, checker_dir)
        expect(executable, launch, folder, output[0] + '\nmain\n' + output[1] + '\n', env)
    # No finalization body must not create a stale or empty async range.
    folder = root / 'empty-fini'
    folder.mkdir()
    assembly = compile_unit(compiler, flags, units, folder, 'LifeEmpty', source('LifeEmpty', "  WriteLn('init only');\n"))
    policy(assembly, 'LifeEmpty', True, False, arm)
    executable = compile_program(compiler, flags, units, folder, program('LifeEmpty'))
    tables(executable, folder, checker_dir)
    expect(executable, launch, folder, 'init only\nmain\n', env)
    # FPC permits finalization without a user initialization body.
    folder = root / 'fini-only'
    folder.mkdir()
    assembly = compile_unit(compiler, flags, units, folder, 'LifeOnly', source('LifeOnly', None, "  WriteLn('fini only');\n"))
    policy(assembly, 'LifeOnly', True, True, arm)
    executable = compile_program(compiler, flags, units, folder, program('LifeOnly'))
    tables(executable, folder, checker_dir)
    expect(executable, launch, folder, 'main\nfini only\n', env)


def progress_source(unit='LifeProgress', phase=None):
    body = '''  Done := 0;
  Cycles := 0;
  Keep := 'life roots ' + IntToStr(ParamCount + 1);
  pas Collect;
  while AtomicLoad(Done) = 0 do
    Spins := Spins + 1;
  if Keep <> 'life roots 1' then Halt(81);
'''
    prefix = 'unit ' + unit + ';\n' + '''interface
implementation
uses sysutils;
var Done, Cycles, Spins: Integer;
  Keep: string;
procedure Collect;
var I: Integer;
  Junk: array of Integer;
begin
  Sleep(5);
  for I := 1 to 12 do
  begin
    SetLength(Junk, 0);
    SetLength(Junk, 400);
    Junk[7] := I;
    Cycles := Cycles + GcCollect;
  end;
  AtomicStore(Done, 1);
end;
'''
    if phase is None:
        return prefix + 'initialization\n' + body + "  WriteLn('init progress ', AtomicLoad(Done), ' cycles ', Cycles);\nfinalization\n" + body + "  WriteLn('fini progress ', AtomicLoad(Done), ' cycles ', Cycles);\nend.\n"
    if phase not in ('init', 'fini'):
        fail('unknown async progress phase ' + str(phase))
    marker = phase + ' async loop entered'
    body = body.replace('  while AtomicLoad(Done) = 0 do\n',
                        "  WriteLn('" + marker + "');\n  while AtomicLoad(Done) = 0 do\n")
    keyword = 'initialization' if phase == 'init' else 'finalization'
    return prefix + keyword + '\n' + body + "  WriteLn('" + phase + " progress ', AtomicLoad(Done), ' cycles ', Cycles);\nend.\n"


def async_off(executable, one_cpu, folder, env, phase):
    """Observe this phase's entry first, then require no async-GC progress.

    taskset limits CPU affinity, not the runtime's P count (minimum two).
    The oracle is completion of twelve GC cycles, not single-P fairness.
    Raw byte reads and unbuffered pipes preserve timed communicate output.
    """
    prefix = (('main\n' if phase == 'fini' else '') +
              phase + ' async loop entered\n').encode()
    command = [*map(str, one_cpu), str(executable)]
    process = subprocess.Popen(command, cwd=folder,
        env=dict(env, PASLANG_ASYNCPREEMPTOFF='1'), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, bufsize=0)
    received = bytearray()
    stdout, stderr = b'', b''
    observation_timed_out = False
    problem = ''
    try:
        deadline = time.monotonic() + 20
        while bytes(received) != prefix:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([process.stdout], [], [], remaining)[0]:
                raise RuntimeError('no phase-entry marker within readiness deadline')
            byte = os.read(process.stdout.fileno(), 1)
            if not byte:
                raise RuntimeError('process ended before phase-entry marker')
            received.extend(byte)
            if not prefix.startswith(received):
                raise RuntimeError('unexpected output before phase-entry marker')
        # Startup and QEMU translation do not consume this observation.
        try:
            stdout, stderr = process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            observation_timed_out = True
        else:
            problem = 'disabled async preemption completed instead of waiting'
    except (OSError, RuntimeError) as error:
        problem = str(error)
    finally:
        if process.returncode is None:
            deadline = time.monotonic() + 20
            process.kill()
            try:
                stdout, stderr = process.communicate(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired as error:
                stdout, stderr = error.output or b'', error.stderr or b''
                process.stdout.close()
                process.stderr.close()
                try:
                    process.wait(timeout=max(0, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    problem += '; child was not reaped within cleanup deadline'
                problem += '; pipe did not drain within cleanup deadline'
        process.stdout.close()
        process.stderr.close()
    if (problem or not observation_timed_out or bytes(received) != prefix or
            stdout or stderr or process.returncode != -signal.SIGKILL):
        fail(phase + ' async-off control: ' + (problem or 'unexpected completion/diagnostic output') +
             '\nexit=' + str(process.returncode) + '\nstdout=' +
             repr((bytes(received) + stdout).decode(errors='backslashreplace')) +
             '\nstderr=' + repr(stderr.decode(errors='backslashreplace')))


def progress(compiler, flags, units, root, launch, env, arm, checker_dir, inline):
    folder = root / 'progress'
    folder.mkdir()
    assembly = compile_unit(compiler, flags, units, folder, 'LifeProgress', progress_source())
    policy(assembly, 'LifeProgress', True, True, arm)
    executable = compile_program(compiler, flags, units, folder, program('LifeProgress'))
    tables(executable, folder, checker_dir)
    cpu = min(os.sched_getaffinity(0))
    one_cpu = [shutil.which('taskset') or 'taskset', '-c', str(cpu), *launch]
    expect(executable, one_cpu, folder, 'init progress 1 cycles 12\nmain\nfini progress 1 cycles 12\n', env)
    if inline == 40:
        for phase in ('init', 'fini'):
            unit = 'LifeAsync' + phase.title()
            separate = root / ('progress-' + phase + '-only')
            separate.mkdir()
            assembly = compile_unit(compiler, flags, units, separate, unit, progress_source(unit, phase))
            policy(assembly, unit, True, phase == 'fini', arm)
            executable = compile_program(compiler, flags, units, separate, program(unit))
            tables(executable, separate, checker_dir)
            marker = phase + ' async loop entered\n'
            completion = phase + ' progress 1 cycles 12\n'
            expected = marker + completion + 'main\n' if phase == 'init' else 'main\n' + marker + completion
            expect(executable, one_cpu, separate, expected, env)
            async_off(executable, one_cpu, separate, env, phase)



def growth(compiler, flags, units, root, launch, env, arm, checker_dir):
    folder = root / 'growth'
    folder.mkdir()
    # Independent closed form: 1 + d*(d+1)//2 + 7*d, d=320/640.
    # Validate each retained Pad contribution before the deliberate fault.
    text = '''unit LifeGrow;
interface
implementation
uses sysutils;
var
  A: array[0..1] of Integer;
  I, V, Before: Integer;
function Grow(N: Integer): Integer;
var Pad: array[0..511] of Integer;
begin
  Pad[N and 511] := N + 7;
  if N = 0 then
  begin
    Result := GcCollect;
    if Result <> 1 then Halt(84);
  end
  else Result := Grow(N - 1) + Pad[N and 511];
end;
initialization
  I := ParamCount + 5;
  Before := HeapStat(13);
  try
    V := Grow(320);
    if V <> 53601 then Halt(85);
    V := A[I];
  except
    on E: ERangeError do WriteLn('init grew and caught');
  end;
  if HeapStat(13) <= Before then Halt(82);
finalization
  Before := HeapStat(13);
  try
    V := Grow(640);
    if V <> 209601 then Halt(86);
    V := A[I];
  except
    on E: ERangeError do WriteLn('fini grew and caught');
  end;
  if HeapStat(13) <= Before then Halt(83);
end.
'''
    assembly = compile_unit(compiler, flags, units, folder, 'LifeGrow', text)
    policy(assembly, 'LifeGrow', True, True, arm)
    executable = compile_program(compiler, flags, units, folder, program('LifeGrow'))
    tables(executable, folder, checker_dir)
    expect(executable, launch, folder, 'init grew and caught\nmain\nfini grew and caught\n', env)


def room_controls(compiler, flags, units, root, arm, checker_dir, stack):
    folder = root / 'room'
    folder.mkdir()
    assembly = compile_unit(compiler, flags, units, folder, 'LifeRoom', source('LifeRoom', '  V := ParamCount;\n', '  V := ParamCount;\n', sysutils=False))
    # Keep the stop-room boundary independent of I/O's unchecked call chain.
    executable = compile_program(compiler, flags, units, folder,
                                 'program lifeuse; uses LifeRoom; begin end.\n')
    main_assembly = executable.with_suffix('.s').read_text()
    stop = 368 if arm else 144  # pasemit AsyncRoom, verified against runtime stop layouts
    for text, owner in ((main_assembly, 'pas_main'), (assembly, 'u_liferoom_init'), (assembly, 'u_liferoom_fini')):
        ranges = asm_ranges(text)
        if len(ranges.get(owner, [])) != 1:
            fail(owner + ': missing real async range for stop-room control')
        lines = text.splitlines()
        symbols = stack.sets(lines)
        body = stack.routines(lines).get(owner)
        if body is None:
            fail(owner + ': no real emitted body')
        walk = stack.Walk(body, arm, symbols)
        if walk.budget is None:
            fail(owner + ': no recognized entry check')
        # The measured frame depth is unchanged. Only the check's room is
        # varied, exactly enough for a stop or one byte short. An old
        # section-suffix lookup misses main/init/fini and accepts the short one.
        need = walk.peak + stop
        if need > 4095:
            fail(owner + ': room fixture unexpectedly needs a shifted SUB')
        a = lines.index(owner + ':') + 1
        check = next((i for i in range(a, len(lines)) if (lines[i].startswith('  sub x9, sp, #') if arm else lines[i].startswith('  leaq -') and lines[i].endswith('(%rsp), %r11'))), None)
        if check is None:
            fail(owner + ': no guard-address instruction')
        if arm and lines[check + 1].startswith('  sub x9, x9, #'):
            fail(owner + ': unexpected two-instruction guard-address fixture')
        for short in (False, True):
            changed = lines.copy()
            room = need - int(short)
            # Intel SDM LEA effective address; ARM ARM C6.2.457 SUB immediate.
            # These are text inputs for Python only, never assembled/executed.
            changed[check] = ('  sub x9, sp, #' + str(room)) if arm else ('  leaq -' + str(room) + '(%rsp), %r11')
            path = folder / (owner + ('-short.s' if short else '-exact.s'))
            path.write_text('\n'.join(changed) + '\n')
            result = run([sys.executable, '-I', checker_dir / 'check_stack.py', path, *(['--arm'] if arm else []), '--async=' + str(stop), '--room=rt_yieldpoint:16,rt_asyncpreempt' if arm else '--room=rt_yieldpoint,rt_asyncpreempt'], folder)
            if short:
                if result.returncode != 1 or owner not in result.stdout or 'by a stop' not in result.stdout:
                    fail(owner + ': one-byte-short stop room was not rejected for a stop\n' + result.stdout + result.stderr)
            elif result.returncode:
                fail(owner + ': exact stop room was rejected\n' + result.stdout + result.stderr)


def main():
    if len(sys.argv) != 4:
        fail('usage: check_unit_life.py COMPILER BUILDDIR QEMU')
    compiler, build, qemu = (Path(arg).resolve() for arg in sys.argv[1:])
    project = Path(__file__).resolve().parents[1]
    checker_dir = project / 'scripts'
    stack = module(checker_dir / 'check_stack.py', 'p576_stack')
    env = dict(os.environ, PASLANG_ASYNCPREEMPTOFF='0', PASLANG_GCVERIFY='1',
               PASLANG_GCSTRESS='1', PASLANG_GCPOISON='1')
    # Exhaust actual runtime-unit code, even routines with no paslines record.
    for subdir in ('', 'v3', 'a64', 'a64/v8.2+crypto'):
        for unit in RUNTIME_UNITS:
            path = build / subdir / (unit + '.s')
            if not path.is_file() or ASYNC_SECTION.search(path.read_text()):
                fail(str(path) + ': actual runtime unit is missing or has async code')
    with tempfile.TemporaryDirectory(prefix='paslang-unit-life-', dir=build) as temp:
        root = Path(temp)
        for target in ('amd64', 'arm64'):
            arm = target == 'arm64'
            units = build / 'a64' if arm else build
            launch = [qemu] if arm else []
            for inline in (0, 40):
                work = root / (target + '-' + str(inline))
                work.mkdir()
                flags = ['-target', target, '-cpu', 'base', '-inline', str(inline)]
                # Same body, exact runtime unit identity: fake heap/scheduler
                # are compile-only; no fake interface leaks to another folder.
                for unit in RUNTIME_UNITS:
                    folder = work / ('runtime-' + unit)
                    folder.mkdir()
                    text = source(unit, '  I := ParamCount + 1;\n  while I < 5 do I := I + 1;\n', '  I := ParamCount + 1;\n  while I < 5 do I := I + 1;\n', sysutils=False)
                    assembly = compile_unit(compiler, flags, units, folder, unit, text)
                    if ASYNC_SECTION.search(assembly):
                        fail(unit + ': compile-only runtime lifecycle became eligible')
                    for phase in ('init', 'fini'):
                        own = 'u_' + unit + '_' + phase
                        lines = assembly.splitlines()
                        start = lines.index(own + ':')
                        end = lines.index('u_' + unit + '_fini:') if phase == 'init' else len(lines)
                        if sum('rt_morestack' in line for line in lines[start:end]) < 2:
                            fail(own + ': runtime lifecycle lost its cooperative loop check')
                folder = work / 'golden'
                folder.mkdir()
                golden = project / 'testdata/units'
                assembly = compile_unit(compiler, flags, units, folder, 'LifeCaught', (golden / 'lifecaught.paslang').read_text())
                policy(assembly, 'LifeCaught', True, True, arm)
                executable = compile_program(compiler, flags, units, folder, (golden / 'lifecaughtuse.paslang').read_text())
                tables(executable, folder, checker_dir)
                expect(executable, launch, folder, (golden / 'lifecaughtuse.out').read_text(), env)
                fatal_cases(compiler, flags, units, work, launch, env, arm)
                mixed_cases(compiler, flags, units, work, launch, env, arm, checker_dir)
                progress(compiler, flags, units, work, launch, env, arm, checker_dir, inline)
                growth(compiler, flags, units, work, launch, env, arm, checker_dir)
                room_controls(compiler, flags, units, work, arm, checker_dir, stack)
    print('unit-life: both targets inline0/40; own handlers/classes/lines/cleanup and later success; independent ASM/runtime exclusions; ordered line/async metadata; one-CPU GC progress; main/init/fini exact and one-byte-short stop room')


if __name__ == '__main__':
    main()
