#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING.
"""Check HTTPS progress and cleanup with 2,048 established TLS connections."""
import argparse
import asyncio
import os
from pathlib import Path
import resource
import ssl

CERTS = Path(__file__).resolve().parents[1] / 'testdata/tls'
CONNECTIONS = 2048
STALLED = 64
IN_FLIGHT = 64
TIMEOUT = 240


def tls_context(version):
    ctx = ssl.create_default_context(cafile=str(CERTS / 'ca.pem'))
    ctx.minimum_version = ctx.maximum_version = version
    return ctx


def socket_count(pid):
    count = 0
    for fd in Path(f'/proc/{pid}/fd').iterdir():
        try:
            target = fd.readlink()
        except FileNotFoundError:
            continue
        if str(target).startswith('socket:['):
            count += 1
    return count


async def get(reader, writer, path):
    writer.write(b'GET ' + path + b' HTTP/1.1\r\nHost: localhost\r\n\r\n')
    await writer.drain()
    status, *headers = (await reader.readuntil(b'\r\n\r\n')).split(b'\r\n')
    if status != b'HTTP/1.1 200 OK':
        raise AssertionError(f'{path!r}: unexpected status {status!r}')
    length, = (int(h.split(b':', 1)[1]) for h in headers
               if h.lower().startswith(b'content-length:'))
    return await reader.readexactly(length)


async def exercise(server):
    port = int(await asyncio.wait_for(server.stdout.readline(), 20))
    if socket_count(server.pid) != 1:
        raise AssertionError('expected exactly one listening socket at startup')
    contexts = [tls_context(ssl.TLSVersion.TLSv1_2), tls_context(ssl.TLSVersion.TLSv1_3)]
    writers = []
    slots = asyncio.Semaphore(IN_FLIGHT)

    async def connect(ctx=None):
        reader, writer = await asyncio.open_connection('127.0.0.1', port, ssl=ctx,
                                                       server_hostname='localhost' if ctx else None)
        writers.append(writer)
        return reader, writer

    async def hello(stream):
        if await get(*stream, b'/') != b'hello':
            raise AssertionError('wrong HTTPS response body')

    async def open_and_serve(index):
        async with slots:
            stream = await connect(contexts[index % len(contexts)])
            await hello(stream)
            return stream

    async def check_active(probe, expected):
        active = routines = sockets = None
        try:
            async with asyncio.timeout(20):
                while True:
                    active, routines = map(int, (await get(*probe, b'/status')).split())
                    sockets = socket_count(server.pid)
                    if active == expected and routines > active and sockets == active + 1:
                        return
                    await asyncio.sleep(0.02)
        except TimeoutError:
            raise AssertionError(f'expected {expected} active connections and {expected + 1} sockets; '
                                 f'got active={active}, routines={routines}, sockets={sockets}') from None

    try:
        clients = await asyncio.gather(*(open_and_serve(i) for i in range(CONNECTIONS)))
        # Accepted TCP clients that withhold the ClientHello park in the handshake.
        stalled = [await connect() for _ in range(STALLED)]
        probe = await connect(contexts[1])
        peak = CONNECTIONS + STALLED + 1
        await check_active(probe, peak)
        if await get(*probe, b'/collect') != b'collected':
            raise AssertionError('the HTTPS probe did not finish collection')
        await asyncio.gather(*(hello(client) for client in clients))
        print(f'ok HTTPS progress with {peak} active connections on one P', flush=True)

        for _, writer in clients[:32] + stalled[:32]:
            writer.transport.abort()
        await check_active(probe, peak - 64)
        await hello(probe)

        server.stdin.write(b'stop\n')
        await server.stdin.drain()
        active, routines, idle_routines = map(int, (await server.stdout.readline()).split())
        sockets = socket_count(server.pid)
        if active or routines != idle_routines or sockets:
            raise AssertionError(f'after shutdown: active={active}, routines={routines}, '
                                 f'idle baseline={idle_routines}, sockets={sockets}')
        # Verify all remaining peers see EOF while the server process is still alive.
        survivors = clients[32:] + stalled[32:] + [probe]
        if any(await asyncio.gather(*(reader.read(1) for reader, _ in survivors))):
            raise AssertionError('unexpected bytes after HTTPS shutdown')
        server.stdin.write(b'exit\n')
        await server.stdin.drain()
        if await server.wait():
            raise AssertionError(f'server exit {server.returncode}')
        print(f'ok HTTPS cleanup of {peak - 64} live connections', flush=True)
    finally:
        for writer in writers:
            writer.transport.abort()


async def run(command):
    server = await asyncio.create_subprocess_exec(
        *command, CERTS / 'ec.pem', CERTS / 'ec.key', stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, env={**os.environ, 'PASLANG_MAXPROCS': '1'})
    try:
        await asyncio.wait_for(exercise(server), TIMEOUT)
    finally:
        if server.returncode is None:
            server.kill()
            await server.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('server', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.server:
        parser.error('supply the server command, including its emulator if needed')
    wanted = CONNECTIONS + STALLED + 32
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if hard != resource.RLIM_INFINITY and hard < wanted:
        parser.error(f'the TLS concurrency check needs an open-file limit of at least {wanted}')
    if soft != resource.RLIM_INFINITY and soft < wanted:
        resource.setrlimit(resource.RLIMIT_NOFILE, (wanted, hard))
    asyncio.run(run(args.server))


if __name__ == '__main__':
    main()
