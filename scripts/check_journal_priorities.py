#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Check the journald stderr contract with private sockets and pipes."""

import os
from pathlib import Path
import runpy
import socket
import subprocess
import sys
from tempfile import mkdtemp

ROOT = Path(__file__).resolve().parents[1]

EXCEPTION = """program journalexception;
uses sysutils;

procedure Fail;
begin
  raise Exception.Create('first' + #10 + 'second');
end;

procedure Caller;
begin
  Fail;
end;

begin
  Caller;
end.
"""
CONVERTED = """program journalconverted;
uses sysutils;
var
  Denominator: Integer;
begin
  Denominator := ParamCount;
  try
    WriteLn(10 div Denominator);
  finally
    WriteLn('unwound');
  end;
end.
"""
API = """program journalapi;
uses passystemd, paslinux;
begin
  WriteLn(SD_EMERG, SD_ALERT, SD_CRIT, SD_ERR, SD_WARNING, SD_NOTICE, SD_INFO, SD_DEBUG);
  WriteLn(SdJournalStderr);
  if ParamCount > 0 then
  begin
    if OsDup2(1, 2) <> 2 then Halt(3);
    WriteLn(SdJournalStderr);
  end;
end.
"""


def env_with(descriptor, variant):
    env = os.environ.copy()
    env.pop('JOURNAL_STREAM', None)
    stat = os.fstat(descriptor)
    value = {
        'match': f'{stat.st_dev}:{stat.st_ino}',
        'wrong-device': f'{stat.st_dev + 1}:{stat.st_ino}',
        'wrong-inode': f'{stat.st_dev}:{stat.st_ino + 1}',
        'overflow-device': f'{stat.st_dev + 2**64}:{stat.st_ino}',
        'overflow-inode': f'{stat.st_dev}:{stat.st_ino + 2**64}',
        'trailing': f'{stat.st_dev}:{stat.st_ino}:0',
        'signed': f'+{stat.st_dev}:{stat.st_ino}',
        'empty': f':{stat.st_ino}',
    }.get(variant)
    if value is not None:
        env['JOURNAL_STREAM'] = value
    return env


def invoke(command, destination, variant='match', *, cwd=None):
    if destination == 'socket':
        receiver, writer = socket.socketpair()
        with receiver, writer:
            env = env_with(writer.fileno(), variant)
            result = subprocess.run(command, env=env, stdout=subprocess.PIPE,
                                    stderr=writer, cwd=cwd, timeout=90)
            writer.close()
            stderr = b''.join(iter(lambda: receiver.recv(4096), b''))
    else:
        read_fd, write_fd = os.pipe()
        with os.fdopen(read_fd, 'rb') as reader, os.fdopen(write_fd, 'wb') as writer:
            env = env_with(writer.fileno(), variant)
            result = subprocess.run(command, env=env, stdout=subprocess.PIPE,
                                    stderr=writer, cwd=cwd, timeout=90)
            writer.close()
            stderr = reader.read()
    return result.returncode, result.stdout, stderr


def check_report(command, status, priority, marker, *, cwd):
    baseline_status, _, terminal_style = invoke(command, 'pipe', cwd=cwd)
    assert baseline_status == status and marker in terminal_style, (command, terminal_style)
    plain = invoke(command, 'socket', 'wrong-inode', cwd=cwd)
    assert plain[0] == status and plain[2] == terminal_style, (command, plain)
    active = invoke(command, 'socket', cwd=cwd)
    expected = b''.join(priority + line for line in terminal_style.splitlines(keepends=True))
    assert active[0] == status and active[2] == expected, (command, expected, active)


def check_target(compiler, sdk, runner, work, target, link_variant):
    fixtures = [('api', API), ('object', EXCEPTION), ('converted', CONVERTED)]
    sources = {}
    for name, contents in fixtures:
        source = work / f'{name}.paslang'
        source.write_text(contents)
        sources[name] = source
    sources.update({
        'raw': ROOT / 'testdata/fatal/divzero.paslang',
        'raise': ROOT / 'testdata/fatal/mainraise.paslang',
        'http': ROOT / 'testdata/httpsrv.paslang',
        'hello': ROOT / 'testdata/hello.paslang',
    })
    for name, source in sources.items():
        subprocess.run([compiler, '-target', target, '-cpu', 'base', '-inline', '0',
                        '-Fu', sdk, '-o', work / name, source], check=True, timeout=40)

    levels = b'<0><1><2><3><4><5><6><7>\n'
    api = [*runner, work / 'api']
    assert invoke(api, 'socket') == (0, levels + b'True\n', b'')
    assert invoke([*api, 'replace'], 'socket') == (0, levels + b'True\nFalse\n', b'')
    assert invoke(api, 'pipe') == (0, levels + b'False\n', b'')
    for variant in ('unset', 'wrong-device', 'wrong-inode', 'overflow-device',
                    'overflow-inode', 'trailing', 'signed', 'empty'):
        assert invoke(api, 'socket', variant) == (0, levels + b'False\n', b''), variant

    calls = [
        ('raw', [], 1, b'<2>', b'integer divide by zero'),
        ('converted', [], 1, b'<2>', b'integer divide by zero'),
        ('raise', [], 1, b'<3>', b'in the main routine'),
        ('raise', ['worker'], 0, b'<3>', b'which ends alone'),
        ('object', [], 1, b'<3>', b'first\nsecond'),
        ('http', [], 0, b'<3>', b'httpserver: GET /fail: Exception'),
    ]
    # httpsrv names its Unix socket from ParamStr(0). A relative name
    # keeps the socket within sun_path in a deeply nested build.
    for name, args, status, priority, marker in calls:
        check_report([*runner, f'./{name}', *args], status, priority, marker, cwd=work)
    hello = work / 'hello'
    guard = work / 'guard'
    assembly = hello.with_suffix('.s').read_text()
    marker = '\nrt_guard:\n'
    assert assembly.count(marker) == 1
    misalign = '  leaq 1(%rdi), %rdi\n' if target == 'amd64' else '  add x0, x0, #1\n'
    link_variant(hello, guard, '' if target == 'amd64' else 'aarch64-linux-gnu-',
                 assembly.replace(marker, marker + misalign))
    check_report([*runner, './guard'], 2, b'<2>', b'madvise(MADV_GUARD_INSTALL)', cwd=work)
    print(f'ok journal priorities {target}, socket identity and exact fallback output')


def main():
    if len(sys.argv) != 4:
        raise SystemExit('usage: check_journal_priorities.py compiler builddir qemu')
    compiler, build, qemu = (Path(arg).resolve() for arg in sys.argv[1:])
    work = Path(mkdtemp(prefix='journal-priorities-', dir=build))
    link_variant = runpy.run_path(str(ROOT / 'scripts/check_cpu_affinity.py'))['link_variant']
    for target, sdk, runner in [('amd64', build, []),
                                ('arm64', build / 'a64', [qemu, '-cpu', 'cortex-a53'])]:
        case = work / target
        case.mkdir()
        check_target(compiler, sdk, runner, case, target, link_variant)


if __name__ == '__main__':
    main()
