#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Check inotify setup failures and deadline arithmetic on both targets."""

from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'src/lib/pasinotify.paslang'
TEST = ROOT / 'testdata/inotifyerrors.paslang'
ZERO_WAKE = ('  FWake := Syscall(Nr(290, 19)',
             '  Syscall(Nr(3, 57), 0);\n  FWake := Syscall(Nr(290, 19)')
SETUP_CASES = (
    # inotify_init1 alone fails (an unknown flag: EINVAL), with room for
    # the eventfd and the set, which must not be made after it.
    ('reject-init', 'reject-init', (
        ('Nr(294, 26), InNonblock or InCloexec', 'Nr(294, 26), InNonblock or InCloexec or 1'),)),
    ('reject-watch', 'reject', (
        ('Nr(233, 21), FEp, 1, FFd', 'Nr(233, 21), -1, 1, FFd'),)),
    ('reject-wake', 'reject', (
        ('Nr(233, 21), FEp, 1, FWake', 'Nr(233, 21), -1, 1, FWake'),)),
    ('zero-wake', 'zero-wake', (ZERO_WAKE,)),
    ('zero-poll', 'zero-poll', (
        ('  FEp := Syscall(Nr(291, 20)', '  Syscall(Nr(3, 57), 0);\n  FEp := Syscall(Nr(291, 20)'),)),
    ('reject-zero-wake', 'reject-zero-wake', (
        ZERO_WAKE, ('Nr(291, 20), InCloexec', 'Nr(291, 20), InCloexec or 1'))),
)

MAX_TIME = (1 << 63) - 1
MAX_WAIT = 1 << 40
MS = 1_000_000
START = 90 * MS
LATEST_REQUEST = (MAX_TIME - START) // MS
DEADLINE_CASES = (
    ('zero', 0, START, START),
    ('untimed', -1, START, START),
    ('minimum-timeout', -(1 << 63), START, START),
    ('one-millisecond-left', 1, START, START),
    ('one-millisecond-minus-one', 1, START, START + 1),
    ('elapsed', 1, START, START + MS),
    ('one-nanosecond-left', 1, START, START + MS - 1),
    ('exact-wait-limit', MAX_WAIT - 1, START, START),
    ('above-wait-limit', MAX_WAIT, START, START),
    ('maximum-request', MAX_TIME, START, START),
    ('latest-request-elapsed', LATEST_REQUEST, START, START + LATEST_REQUEST * MS),
    ('overflow-at-expiry', LATEST_REQUEST + 1, START, MAX_TIME),
    ('near-limit-elapsed', 1, MAX_TIME - MS - 1, MAX_TIME - 1),
    ('near-limit-saturated', 2, MAX_TIME - MS - 1, MAX_TIME - 1),
    ('near-limit-last-nanosecond', 1, MAX_TIME - 1, MAX_TIME - 1),
    ('saturated-elapsed', MAX_TIME, START, MAX_TIME),
)
CLOCK_PROBE = """implementation

uses paslib;

var
  ProbeClockCalls: Integer;

function ProbeClock: Integer;
var
  argument: Integer;
begin
  Inc(ProbeClockCalls);
  argument := 4;
  if ProbeClockCalls = 1 then
    argument := 3;
  if not StrToInt64(ParamStr(argument), Result) then Halt(10);
end;

function ProbeTimed(Fd, Interests, Milliseconds: Integer): Integer;
begin
  WriteLn('timed ', Milliseconds);
  Result := -125;
end;

function ProbeUntimed(Fd, Interests: Integer): Integer;
begin
  WriteLn('untimed');
  Result := -125;
end;
"""


def build_probe(command, units, folder, source):
    folder.mkdir()
    variant = folder / SOURCE.name
    variant.write_text(source)
    subprocess.run([*command, '-c', '-Fu', units, '-o', folder / 'pasinotify', variant],
                   check=True, timeout=60)
    binary = folder / 'inotifyerrors'
    subprocess.run([*command, '-Fu', folder, '-Fu', units, '-o', binary, TEST],
                   check=True, timeout=60)
    return binary


def require_output(label, command, expected):
    result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, timeout=20)
    if (result.returncode, result.stdout, result.stderr) != (0, expected, b''):
        raise SystemExit(f'{label}: expected {expected!r}, got {result.returncode}, '
                         f'{result.stdout!r}, {result.stderr!r}')


def deadline_probe_source(source):
    # Run the real empty inotify read and Next loop. Supply the two clock
    # readings and record the poll boundary without waiting on future dates.
    start = source.index('\nfunction TInotify.Next(')
    end = source.index('\nprocedure TInotify.Dispose;', start)
    body = source[start:end]
    if (body.count('Nanotime') != 2 or body.count('WaitMs(FEp') != 1
            or body.count('WaitIo(FEp') != 1 or source.count('implementation\n') != 1):
        raise SystemExit('inotify deadline fixture does not match')
    body = body.replace('Nanotime', 'ProbeClock').replace('WaitMs(FEp', 'ProbeTimed(FEp')
    body = body.replace('WaitIo(FEp', 'ProbeUntimed(FEp')
    return (source[:start] + body + source[end:]).replace('implementation\n', CLOCK_PROBE)


def deadline_output(milliseconds, start, now):
    if milliseconds < 0:
        return b'untimed\nerror 125\n'
    left = min(MAX_TIME, start + milliseconds * MS) - now
    if left <= 0:
        return b'error 0\n'
    return f'timed {min(MAX_WAIT, left // MS + 1)}\nerror 125\n'.encode()


def check(compiler, build, work, target, launch, source):
    units = build if target == 'amd64' else build / 'a64'
    command = [compiler, '-target', target, '-cpu', 'base']
    for case, argument, replacements in SETUP_CASES:
        altered = source
        for original, replacement in replacements:
            if altered.count(original) != 1:
                raise SystemExit(f'{case}: inotify constructor fixture does not match')
            altered = altered.replace(original, replacement)
        binary = build_probe(command, units, work / f'{target}-{case}', altered)
        require_output(f'{target} {case}', [*launch, binary, argument], b'inotify setup path ok\n')

    binary = build_probe(command, units, work / f'{target}-deadline', deadline_probe_source(source))
    for case, milliseconds, start, now in DEADLINE_CASES:
        require_output(f'{target} {case}', [*launch, binary, 'deadline', str(milliseconds),
                                         str(start), str(now)], deadline_output(milliseconds, start, now))


def main():
    if len(sys.argv) != 4:
        raise SystemExit('usage: check_inotify_failures.py compiler builddir qemu')
    compiler, build, qemu = (Path(arg).resolve() for arg in sys.argv[1:])
    source = SOURCE.read_text()
    with TemporaryDirectory(prefix='inotify-failures-', dir=build) as temp:
        check(compiler, build, Path(temp), 'amd64', [], source)
        check(compiler, build, Path(temp), 'arm64', [qemu, '-cpu', 'cortex-a53'], source)
    print('Inotify setup failures and deadline boundaries checked on amd64 and arm64')


if __name__ == '__main__':
    main()
