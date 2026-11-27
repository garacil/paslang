#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.
"""Verify routing fallbacks, partial request hooks, and response aborts."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import select
import socket
import subprocess


HOST = b'Host: localhost\r\n'
GET_OK = b'GET /ok HTTP/1.1\r\n' + HOST + b'\r\n'
GET_DROP = b'GET /drop HTTP/1.1\r\n' + HOST + b'\r\n'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def line(process):
    if not select.select([process.stdout], [], [], 15)[0]:
        raise AssertionError('server did not report readiness or shutdown')
    result = process.stdout.readline()
    require(result, 'server closed its control stream')
    return result


def exchange(port, payload):
    with socket.create_connection(('127.0.0.1', port), timeout=10) as peer:
        peer.sendall(payload)
        with peer.makefile('rb') as stream:
            return stream.read()


def reply(port, request, status, body, header=None):
    wire = exchange(port, request)
    head, _, got = wire.partition(b'\r\n\r\n')
    require(head.startswith(f'HTTP/1.1 {status} '.encode()) and got == body, wire)
    if header is not None:
        require(header in head.split(b'\r\n'), head)


def routes(port, custom):
    close = b'Connection: close\r\n\r\n'
    reply(port, b'GET /missing HTTP/1.1\r\n' + HOST + close, 404,
          b'GET /missing' if custom else b'404 page not found\n')
    reply(port, b'PUT /ok HTTP/1.1\r\n' + HOST + close, 405,
          b'PUT /ok GET, HEAD' if custom else b'Method Not Allowed\n', b'Allow: GET, HEAD')
    malformed = b'GET /bad HTTP/1.1\r\n' + HOST + b'X-Probe: valid\r\nBroken Header\r\n\r\n'
    reply(port, malformed, 400, b'GET /bad valid 0' if custom else b'400 Bad Request: invalid header name\n')
    if not custom:
        return
    reply(port, b'GET /bad-version HTTP/1.x\r\n' + HOST + close, 400, b'GET /bad-version  0')
    reply(port, b'GET /moved HTTP/1.1\r\n' + HOST + close, 307, b'', b'Location: /ok')
    prefix = b'GET /slow HTTP/1.1\r\n' + HOST + b'X-Probe: partial\r\n'
    reply(port, prefix + b'X-Unfinished:', 408, b'GET /slow partial 0')
    reply(port, prefix + b'A: 1\r\nB: 1\r\nC: 1\r\n\r\n', 431, b'GET /slow partial 0')
    reply(port, prefix + b'X-Wide: ' + b'x' * 300 + b'\r\n\r\n', 431, b'GET /slow partial 0')
    upload = b'POST /upload HTTP/1.1\r\n' + HOST + b'X-Probe: upload\r\nContent-Length: 3\r\n'
    reply(port, upload + b'Expect: 100-continue\r\n\r\n', 413, b'POST /upload upload 3')
    require(exchange(port, malformed.replace(b'X-Probe: valid', b'X-Probe: drop')) == b'',
            'the rejection hook sent a response after aborting')
    absent = b'GET /drop-missing HTTP/1.1\r\n' + HOST + close
    require(exchange(port, absent) == b'', 'the not-found hook sent a response after aborting')


def aborts(port):
    with socket.create_connection(('127.0.0.1', port), timeout=10) as peer:
        with peer.makefile('rb') as stream:
            peer.sendall(GET_OK)
            require(stream.readline() == b'HTTP/1.1 200 OK\r\n', 'initial keep-alive request failed')
            while (header := stream.readline()) != b'\r\n':
                require(header, 'incomplete first response')
            require(stream.read(2) == b'ok', 'wrong first response body')
            peer.sendall(GET_DROP)
            require(stream.read() == b'', 'aborted keep-alive request returned a response')
    chunk = exchange(port, b'GET /chunk HTTP/1.1\r\n' + HOST + b'\r\n')
    head, _, body = chunk.partition(b'\r\n\r\n')
    require(b'Transfer-Encoding: chunked' in head and body == b'6\r\nprefix\r\n', chunk)
    with ThreadPoolExecutor(max_workers=8) as pool:
        require(all(wire == b'' for wire in pool.map(lambda _: exchange(port, GET_DROP), range(32))),
                'an aborted request returned a response')


def run(command, mode):
    env = {**os.environ, 'PASLANG_MAXPROCS': '1', 'PASLANG_GCSTRESS': '3', 'PASLANG_GCPOISON': '1'}
    with subprocess.Popen([*command, mode], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, bufsize=0) as process:
        try:
            port = int(line(process))
            if mode == 'text':
                require(exchange(port, GET_DROP) == b'', 'abort returned a response')
            else:
                routes(port, mode == 'hooks')
                if mode == 'hooks':
                    aborts(port)
            process.stdin.write(b'stop\n')
            seen = []
            while not (entry := line(process)).startswith(b'connections '):
                seen.append(entry.rstrip(b'\n'))
            require(entry == b'connections 0\n' and line(process) == b'routines 0\n',
                    'an aborted connection or its routine remained open')
            for fd in Path(f'/proc/{process.pid}/fd').iterdir():
                require(not str(fd.readlink()).startswith('socket:['), f'socket {fd} remained open')
            if mode == 'hooks':
                require(seen.count(b'abort /drop 0 0') == 33 and seen.count(b'abort  0 0') == 2
                        and seen.count(b'abort /chunk 200 6') == 1 and len(seen) == 36, seen)
            elif mode == 'text':
                require(len(seen) == 1 and seen[0].startswith(b'127.0.0.1 GET /drop 0 0 ')
                        and seen[0].endswith(b'ms aborted'), seen)
            else:
                require(not seen, seen)
            process.stdin.write(b'exit\n')
            out, err = process.communicate(timeout=10)
            require(process.returncode == 0 and not out and not err, (process.returncode, out, err))
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('server', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.server:
        parser.error('supply the server command, including its emulator if needed')
    for mode in ('defaults', 'hooks', 'text'):
        run(args.server, mode)
    print('ok HTTP fallbacks, partial requests, aborts and cleanup')


if __name__ == '__main__':
    main()
