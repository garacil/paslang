#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Check proxy trust for direct and activated Unix listeners alongside TCP."""

from collections import Counter
from contextlib import ExitStack
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory, mkdtemp

PROGRAM = """program httpunixproxy;
uses sysutils, httpserver;

procedure Report(Req: THttpRequest; Resp: THttpResponse);
begin
  Resp.ReplyText(200, Req.RealIP + '|' + Req.RemoteAddr);
end;

var
  router: THttpRouter;
  server: THttpServer;
begin
  router := THttpRouter.Create;
  router.Handle('GET', '/ip', @Report);
  server := THttpServer.Create(router);
  server.TrustProxy := ParamStr(2) = 'on';
  server.TrustedProxies := ['unix:' + ParamStr(3), 'unix:' + ParamStr(5),
    'unix:', '127.0.0.1'];
  if ParamStr(1) = 'activated' then
  begin
    if not server.ListenSystemd then
      Halt(1);
  end
  else if not (server.ListenUnix(ParamStr(3), 432, '') and
               server.ListenUnix(ParamStr(4), 432, '') and
               server.ListenUnix(ParamStr(5), 0, '') and
               server.ListenTcp('127.0.0.1', 0)) then
    Halt(2);
  WriteLn('ready ', server.Port);
  server.ServeUntilSignal;
end.
"""

# Model sd_listen_fds: sockets are consecutive from fd 3. Duplicate all
# sources out of the destination range before moving any of them.
ACTIVATE = """import fcntl, os, sys
sources, *command = sys.argv[1:]
fds = [int(fd) for fd in sources.split(',')]
copies = [fcntl.fcntl(fd, fcntl.F_DUPFD_CLOEXEC, 3 + len(fds)) for fd in fds]
for target, source in enumerate(copies, 3):
    os.dup2(source, target, inheritable=True)
os.environ.update(LISTEN_PID=str(os.getpid()), LISTEN_FDS=str(len(fds)))
os.execv(command[0], command)
"""
IP = '203.0.113.9'
CLAIM = f'X-Real-IP: {IP}\r\n'.encode()


def ask(address, headers, source=None):
    family = socket.AF_INET if isinstance(address, tuple) else socket.AF_UNIX
    with socket.socket(family, socket.SOCK_STREAM) as client:
        client.settimeout(30)
        if source:
            client.bind((source, 0))
        client.connect(address)
        peer = '{}:{}'.format(*client.getsockname()) if source else ''
        client.sendall(b'GET /ip HTTP/1.1\r\nHost: x\r\nConnection: close\r\n'
                       + headers + b'\r\n')
        with client.makefile('rb') as stream:
            head, body = stream.read().split(b'\r\n\r\n', 1)
        assert head.startswith(b'HTTP/1.1 200 OK\r\n'), head
        return body.decode(), peer


def check(command, log, mode, enabled):
    with TemporaryDirectory(prefix='paslang-realip-', dir='/tmp') as directory, ExitStack() as stack:
        paths = [f'{directory}/proxy', f'{directory}/other']
        abstract = f'@{Path(directory).name}'
        addresses = [*paths, '\0' + abstract[1:]]
        args = [*command, mode, 'on' if enabled else 'off', *paths, abstract]
        fds = []
        if mode == 'activated':
            for address in [*addresses, ('127.0.0.1', 0)]:
                family = socket.AF_INET if isinstance(address, tuple) else socket.AF_UNIX
                listener = stack.enter_context(socket.socket(family, socket.SOCK_STREAM))
                listener.bind(address)
                listener.listen(16)
                fds.append(listener.fileno())
            args = [sys.executable, '-I', '-c', ACTIVATE, ','.join(map(str, fds)), *args]

        with subprocess.Popen(args, pass_fds=fds, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True) as server:
            try:
                ready, _, _ = select.select([server.stdout], [], [], 30)
                assert ready, (mode, 'waited for listeners')
                first = server.stdout.readline()
                assert first.startswith('ready '), (mode, first)
                tcp = ('127.0.0.1', int(first.split()[1]))
                expected_logs = Counter()

                def require(address, headers, expected_ip, source=None):
                    body, peer = ask(address, headers, source)
                    assert body == f'{expected_ip}|{peer}', (mode, address, body, expected_ip, peer)
                    expected_logs[expected_ip or source or '-'] += 1

                require(addresses[0], CLAIM, IP if enabled else '')
                require(addresses[0], b'', '')
                require(addresses[0], b'X-Real-IP: unknown\r\n', '')
                require(addresses[0], CLAIM * 2, '')
                require(addresses[1], CLAIM, '')
                require(addresses[2], CLAIM, '')
                require(tcp, CLAIM, IP if enabled else '', '127.0.0.1')
                require(tcp, CLAIM, '', '127.0.0.2')
            finally:
                if server.poll() is None:
                    server.terminate()
                try:
                    output, _ = server.communicate(timeout=30)
                except subprocess.TimeoutExpired:
                    server.kill()
                    output, _ = server.communicate()
                log.write_text(output, encoding='utf-8')

        assert server.returncode == 0, (mode, server.returncode, output)
        entries = [line.split() for line in output.splitlines()]
        assert all(len(entry) == 6 and entry[1:4] == ['GET', '/ip', '200']
                   for entry in entries), (mode, entries)
        assert Counter(entry[0] for entry in entries) == expected_logs, (mode, output)
        assert [Path(path).exists() for path in paths] == [mode == 'activated'] * 2


def main():
    compiler, build, qemu = (Path(arg).resolve() for arg in sys.argv[1:])
    work = Path(mkdtemp(prefix='httpunixproxy-', dir=build))
    source = work / 'httpunixproxy.paslang'
    source.write_text(PROGRAM, encoding='utf-8')
    for target, units in [('amd64', build), ('arm64', build / 'a64')]:
        app = work / target
        subprocess.run([compiler, '-target', target, '-cpu', 'base', '-Fu', units,
                        '-o', app, source], check=True, cwd=work, timeout=120)
        command = [str(app)] if target == 'amd64' else [str(qemu), '-cpu', 'cortex-a53', str(app)]
        for mode in ('direct', 'activated'):
            for enabled in (True, False):
                check(command, work / f'{target}-{mode}-{enabled}.log', mode, enabled)
        print(f'ok Unix proxy trust {target}, direct and systemd listeners')


if __name__ == '__main__':
    main()
