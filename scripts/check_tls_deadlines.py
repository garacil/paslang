#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacil@tucall.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Check timeout and EOF handling with independently encrypted TLS records."""
import argparse
from pathlib import Path
import socket
import ssl
import struct
import subprocess

CERTS = Path(__file__).resolve().parents[1] / 'testdata/tls'
PAYLOAD = bytes((offset * 131 + 17) & 255 for offset in range(16384))


class Peer:
    def __init__(self, stream, version):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = context.maximum_version = version
        context.set_ciphers('ECDHE-ECDSA-AES128-GCM-SHA256')
        context.load_cert_chain(CERTS / 'ec.pem', CERTS / 'ec.key')
        context.num_tickets = 0
        self.stream = stream
        self.incoming = ssl.MemoryBIO()
        self.outgoing = ssl.MemoryBIO()
        self.tls = context.wrap_bio(self.incoming, self.outgoing, server_side=True)

    def receive(self):
        data = self.stream.recv(65536)
        if not data:
            raise EOFError('client closed before acknowledging the fragment')
        self.incoming.write(data)

    def flush(self):
        data = self.outgoing.read()
        if data:
            self.stream.sendall(data)

    def handshake(self, truncate):
        while True:
            try:
                self.tls.do_handshake()
                self.flush()
                return
            except ssl.SSLWantReadError:
                if truncate and self.outgoing.pending:
                    self.stream.sendall(self.outgoing.read()[:7])
                    if self.stream.recv(1):
                        raise AssertionError('client wrote before completing the handshake')
                    return
                self.flush()
                self.receive()

    def expect(self, expected):
        while True:
            try:
                data = self.tls.read(1)
            except ssl.SSLWantReadError:
                self.flush()
                self.receive()
            else:
                if data != expected:
                    raise AssertionError(f'expected client message {expected!r}, got {data!r}')
                return

    def record(self, plaintext):
        if self.tls.write(plaintext) != len(plaintext):
            raise AssertionError('short application write to TLS BIO')
        wire = self.outgoing.read()
        if len(wire) != 5 + int.from_bytes(wire[3:5], 'big'):
            raise AssertionError('oracle did not produce exactly one wire record')
        return wire

    def exercise(self, mode):
        self.handshake(truncate=mode == 'handshake')
        if mode == 'handshake':
            return
        self.expect(b's')
        wire = self.record(PAYLOAD)
        if len(wire) <= len(PAYLOAD):
            raise AssertionError('oracle record is missing its authenticated framing')
        cuts = {'recover': (2, 22, 22, 4096), 'body-eof': (22,),
                'header-eof': (2,), 'reset': (22,), 'bad-mac': (22,)}
        previous = 0
        for end in cuts[mode]:
            self.stream.sendall(wire[previous:end])
            # The peer sends nothing further until the application's deadline
            # expired. An encrypted acknowledgement proves the retry point.
            self.expect(b'a')
            previous = end
        if mode == 'recover':
            self.stream.sendall(wire[previous:] + self.record(b'next'))
        if mode == 'bad-mac':
            self.stream.sendall(wire[previous:-1] + bytes([wire[-1] ^ 1]))
        if mode == 'reset':
            self.stream.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
        else:
            self.stream.shutdown(socket.SHUT_WR)


def run_case(client, version, number, mode):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.settimeout(20)
        port = listener.getsockname()[1]
        with subprocess.Popen([*client, str(port), number, mode, str(CERTS / 'ca.pem')],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
            peer_error = None
            try:
                stream, _ = listener.accept()
                with stream:
                    stream.settimeout(15)
                    Peer(stream, version).exercise(mode)
            except (OSError, EOFError, AssertionError) as error:
                peer_error = error
            try:
                stdout, stderr = process.communicate(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                raise RuntimeError(f'client timed out: {stdout!r} {stderr!r}') from None
    expected = {'recover': b'ok resumed record\n', 'handshake': b'ok handshake timeout\n'}
    if (process.returncode != 0 or stderr or peer_error is not None
            or stdout != expected.get(mode, b'ok terminal read\n')):
        raise AssertionError(f'TLS 1.{number[-1]} {mode}: client exit {process.returncode}, '
                             f'stdout {stdout!r}, stderr {stderr!r}, peer {peer_error!r}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('client', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.client:
        parser.error('supply a client command, including its emulator if needed')
    errors = []
    for number, version in (('12', ssl.TLSVersion.TLSv1_2), ('13', ssl.TLSVersion.TLSv1_3)):
        for mode in ('recover', 'body-eof', 'header-eof', 'reset', 'bad-mac', 'handshake'):
            try:
                run_case(args.client, version, number, mode)
            except AssertionError as error:
                errors.append(str(error))
    if errors:
        parser.exit(1, '\n'.join(errors) + '\n')
    print('ok TLS 1.2/1.3 record deadlines')


if __name__ == '__main__':
    main()
