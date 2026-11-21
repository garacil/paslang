#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacil@tucall.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Check error GOAWAY and bounded transport teardown against a local peer."""
import argparse
from contextlib import ExitStack
from pathlib import Path
import socket
import ssl
import subprocess
import time

CERTS = Path(__file__).resolve().parents[1] / 'testdata/tls'
PREFACE = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'
PROTOCOL_ERROR = b'\x00' * 7 + b'\x01'
CASES = ('trailing', 'late-body', 'silent')


def exact(stream, length):
    result = bytearray()
    while len(result) < length:
        buf = stream.recv(length - len(result))
        if not buf:
            raise EOFError(f'EOF after {len(result)} of {length} bytes')
        result.extend(buf)
    return bytes(result)


def header(kind, flags, stream, length):
    return length.to_bytes(3, 'big') + bytes([kind, flags]) + stream.to_bytes(4, 'big')


def receive(stream):
    buf = exact(stream, 9)
    return (buf[3], buf[4], int.from_bytes(buf[5:], 'big'),
            exact(stream, int.from_bytes(buf[:3], 'big')))


def until(stream, kind):
    for _ in range(8):
        frame = receive(stream)
        if frame[0] == kind:
            return frame
    raise AssertionError(f'missing frame of type {kind}')


def tls_server(stream):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERTS / 'ec.pem', CERTS / 'ec.key')
    ctx.set_alpn_protocols(['h2'])
    ctx.num_tickets = 0
    return ctx.wrap_socket(stream, server_side=True, suppress_ragged_eofs=False)


def use_peer(stream, transport, case, process):
    if exact(stream, len(PREFACE)) != PREFACE:
        raise AssertionError('wrong connection preface')
    stream.sendall(header(4, 0, 0, 0))
    if until(stream, 1)[2] != 1:
        raise AssertionError('missing request on stream 1')
    if case == 'late-body':
        stream.sendall(header(0, 0, 3, 32768))
    else:
        fault = header(6, 0, 1, 8) + b'bad ping'
        if case == 'trailing':
            fault += b'x' * 49152
        stream.sendall(fault)
    began = time.monotonic()
    if until(stream, 7) != (7, 0, 0, PROTOCOL_ERROR):
        raise AssertionError('wrong error GOAWAY')
    if stream.recv(1):
        raise AssertionError('bytes after GOAWAY')
    if case == 'late-body':
        stream.sendall(b'y' * 32768)
    if case == 'budget':
        stream.sendall(b'z' * (65536 + 4096))
        if process.wait(timeout=2.8) != 0:
            raise AssertionError('client failed on the byte limit')
    elif case == 'silent':
        if process.wait(timeout=2.8) != 0:
            raise AssertionError('client failed during the bounded wait')
        if time.monotonic() - began < 0.65:
            raise AssertionError('connection closed before the peer had time to finish')
    elif transport == 'tls':
        with stream.unwrap() as raw:
            raw.shutdown(socket.SHUT_WR)
    else:
        stream.shutdown(socket.SHUT_WR)


def run_case(client, transport, case):
    with ExitStack() as close:
        args = [*client, transport]
        passed = ()
        if transport == 'pair':
            stream, child = socket.socketpair()
            close.enter_context(stream)
            close.enter_context(child)
            child.setblocking(False)
            passed = (child.fileno(),)
            endpoint = child.fileno()
        else:
            listener = close.enter_context(socket.socket())
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            listener.settimeout(10)
            endpoint = listener.getsockname()[1]
        args.extend([str(endpoint), str(CERTS / 'ca.pem'), case])
        process = close.enter_context(subprocess.Popen(args, pass_fds=passed,
                                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        error = None
        try:
            if transport == 'pair':
                child.close()
            else:
                stream, _ = listener.accept()
                close.enter_context(stream)
            stream.settimeout(3.5)
            if transport == 'tls':
                stream = close.enter_context(tls_server(stream))
            use_peer(stream, transport, case, process)
        except (OSError, EOFError, AssertionError, subprocess.TimeoutExpired) as exc:
            error = repr(exc)
        try:
            stdout, stderr = process.communicate(timeout=4)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            error = f'{error or ""} client did not return after close'
        if error or process.returncode or stderr or stdout != b'request failed\nconnection closed\n':
            raise AssertionError(f'{transport} {case}: {error or "client output"} '
                                 f'{process.returncode}, {stdout!r}, {stderr!r}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('client', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.client:
        parser.error('supply a client command')
    failures = []
    for transport in ('pair', 'tcp', 'tls'):
        cases = CASES if transport == 'tls' else (*CASES, 'budget')
        for case in cases:
            try:
                run_case(args.client, transport, case)
            except AssertionError as exc:
                failures.append(str(exc))
    if failures:
        parser.exit(1, '\n'.join(failures) + '\n')
    print('ok HTTP/2 error GOAWAY and bounded teardown')


if __name__ == '__main__':
    main()
