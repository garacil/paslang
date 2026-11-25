#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Exercise a Paslang HTTPS server with OpenSSL, curl and Go on loopback."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import http.client
import os
from pathlib import Path
import select
import socket
import ssl
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

ROOT = Path(__file__).resolve().parent.parent
KEYS = ROOT / 'testdata/tls'
HELLO = b'hello over TLS\n'
REQUEST = b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n'
FILE = bytes(range(256)) * 200
CIPHERS = (
    ('TLS_AES_128_GCM_SHA256', 'X25519', False),
    ('TLS_AES_256_GCM_SHA384', 'P-384', False),
    ('TLS_CHACHA20_POLY1305_SHA256', 'X448:P-256', True),
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(command, timeout=45, **options):
    return subprocess.run(command, check=True, capture_output=True, timeout=timeout, **options)


@contextmanager
def server(command, cert, key, file, raw=False, tls12=False):
    env = dict(os.environ, PASLANG_MAXPROCS='1')
    args = [*command, cert, key, file, 'raw' if raw else '', 'tls12' if tls12 else '']
    with subprocess.Popen(args, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=env) as process:
        try:
            require(select.select([process.stdout], [], [], 20)[0], 'server readiness timeout')
            ready = process.stdout.readline()
            require(ready.strip().isdigit(), f'invalid readiness line {ready!r}')
            yield int(ready)
        finally:
            if not raw:
                process.terminate()
            try:
                out, err = process.communicate(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                raise
        require((process.returncode, out, err) == (0, b'', b''),
                f'server exit {process.returncode}: {out!r} {err!r}')


def client_context(root, protocols=('http/1.1',), version=ssl.TLSVersion.TLSv1_3):
    context = ssl.create_default_context(cafile=root)
    context.minimum_version = context.maximum_version = version
    context.set_alpn_protocols(list(protocols))
    return context


def get_hello(port, context, protocol='http/1.1', version='TLSv1.3'):
    with socket.create_connection(('127.0.0.1', port), timeout=8) as connection:
        with context.wrap_socket(connection, server_hostname='localhost', suppress_ragged_eofs=False) as stream:
            require(stream.version() == version, 'TLS version')
            require(stream.selected_alpn_protocol() == protocol, 'ALPN')
            stream.sendall(REQUEST)
            response = http.client.HTTPResponse(stream, method='GET')
            response.begin()
            require((response.status, response.read()) == (200, HELLO), 'HTTPS response')
            require(stream.recv(1) == b'', 'expected TLS close_notify')


def reject(port, context, reason, server_name='localhost'):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=8) as connection:
            with context.wrap_socket(connection, server_hostname=server_name):
                raise RuntimeError(f'handshake accepted, expected {reason}')
    except ssl.SSLError as error:
        require(error.reason == reason, f'expected {reason}, got {error}')


def check_openssl(port, root, folder):
    for suite, groups, retry in CIPHERS:
        trace = folder / 'openssl-trace.txt'
        result = run(['openssl', 's_client', '-connect', f'127.0.0.1:{port}', '-tls1_3',
                      '-CAfile', root, '-verify_return_error', '-verify_hostname', 'localhost',
                      '-servername', 'localhost', '-alpn', 'http/1.1', '-ciphersuites', suite,
                      '-groups', groups, '-quiet', '-msg', '-msgfile', trace], input=REQUEST)
        require(result.stdout.startswith(b'HTTP/1.1 200 ') and result.stdout.endswith(HELLO), suite)
        handshake = trace.read_text()
        require(handshake.count('], ServerHello\n') == 1 + retry,
                f'{groups}: wrong number of ServerHello messages')
        require('], Finished\n' in handshake, 'OpenSSL did not see a Finished message')


def check_key_limits(compile_command, runner, folder, identity, file):
    # Keep the real record layer and shorten only the limits. TLS 1.3
    # must rekey in place. TLS 1.2 must close before exhausting its keys.
    source = (ROOT / 'src/lib/pastls.paslang').read_text()
    for limit, reduced in (('Tls13MaxEpochRecords', 3), ('Tls12MaxRecords', 4)):
        declaration = f'  {limit} = 16777216;'
        require(source.count(declaration) == 1, f'missing {limit}')
        source = source.replace(declaration, f'  {limit} = {reduced};')
    folder.mkdir()
    local_tls = folder / 'pastls.paslang'
    local_tls.write_text(source)
    run([*compile_command, '-c', '-o', folder / 'pastls', local_tls])
    binary = folder / 'server'
    run([compile_command[0], '-Fu', folder, *compile_command[1:], '-o', binary,
         ROOT / 'testdata/tlsserver13.paslang'])
    cert, key, root = identity
    trace = folder / 'openssl-trace.txt'
    request = b'POST /echo HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n'
    request += f'Content-Length: {len(FILE)}\r\n\r\n'.encode() + FILE
    with server([*runner, binary], cert, key, file) as port:
        result = run(['openssl', 's_client', '-connect', f'127.0.0.1:{port}', '-tls1_3',
                      '-CAfile', root, '-verify_return_error', '-verify_hostname', 'localhost',
                      '-servername', 'localhost', '-alpn', 'http/1.1', '-quiet', '-msg',
                      '-msgfile', trace], input=request)
        status, body = result.stdout.split(b'\r\n\r\n', 1)
        require(status.startswith(b'HTTP/1.1 200 ') and body == FILE, 'data across KeyUpdate')
        require('], KeyUpdate\n' in trace.read_text(), 'missing server KeyUpdate')


    with server([*runner, binary], cert, key, file, tls12=True) as port:
        context = client_context(root, version=ssl.TLSVersion.TLSv1_2)
        with socket.create_connection(('127.0.0.1', port), timeout=8) as connection:
            with context.wrap_socket(connection, server_hostname='localhost', suppress_ragged_eofs=False) as stream:
                stream.sendall(b'GET /file HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
                response = stream.makefile('rb').read()
                header, body = response.split(b'\r\n\r\n', 1)
                require(header.startswith(b'HTTP/1.1 200 ') and 0 < len(body) < len(FILE) and FILE.startswith(body),
                        'TLS 1.2 write key limit must end the stream with close_notify')
        with socket.create_connection(('127.0.0.1', port), timeout=8) as connection:
            with context.wrap_socket(connection, server_hostname='localhost') as stream:
                for byte in REQUEST[:4]:
                    stream.sendall(bytes((byte,)))
                try:
                    stream.recv(1)
                except ssl.SSLError as error:
                    require(error.reason == 'TLSV1_ALERT_INTERNAL_ERROR', str(error))
                else:
                    raise RuntimeError('TLS 1.2 read key limit did not alert')


def save_early_ticket(cert, key, root, path):
    oracle_command = ['openssl', 's_server', '-accept', '127.0.0.1:0', '-cert', cert,
                      '-key', key, '-early_data', '-max_early_data', '16384', '-num_tickets', '1']
    with subprocess.Popen(oracle_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, bufsize=0) as oracle:
        try:
            for _ in range(5):
                require(select.select([oracle.stdout], [], [], 5)[0], 'ticket oracle readiness timeout')
                line = oracle.stdout.readline().strip()
                if line.startswith(b'ACCEPT '):
                    address = line.split()[1].decode()
                    break
            else:
                raise RuntimeError('missing ticket oracle address')
            command = ['openssl', 's_client', '-connect', address, '-CAfile', root,
                       '-verify_return_error', '-servername', 'localhost', '-sess_out', path, '-quiet']
            with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL) as client:
                try:
                    for _ in range(100):
                        if path.exists() and path.read_bytes().endswith(b'-----END SSL SESSION PARAMETERS-----\n'):
                            return
                        require(client.poll() is None, 'ticket client exited before getting a session')
                        time.sleep(0.05)
                    raise RuntimeError('ticket was not saved')
                finally:
                    client.terminate()
        finally:
            oracle.terminate()


def check_early_data(port, root, folder, ticket):
    early = folder / 'early-request'
    early.write_bytes(b'GET /early-data HTTP/1.1\r\nHost: localhost\r\n\r\n')
    for groups, server_hellos in (('X25519', 1), ('X448:P-256', 2)):
        trace = folder / 'openssl-trace.txt'
        result = run(['openssl', 's_client', '-connect', f'127.0.0.1:{port}', '-tls1_3',
                      '-CAfile', root, '-verify_return_error', '-verify_hostname', 'localhost',
                      '-servername', 'localhost', '-alpn', 'http/1.1', '-groups', groups,
                      '-sess_in', ticket, '-early_data', early, '-quiet', '-msg', '-msgfile', trace],
                     input=REQUEST)
        status_line = b'HTTP/1.1 200 '
        require(result.stdout.startswith(status_line) and result.stdout.endswith(HELLO) and
                result.stdout.count(b'HTTP/1.1 ') == 1, 'expected just the HTTP exchange after Finished')
        handshake = trace.read_text()
        first_flight = handshake.split('<<<', 1)[0]
        require('InnerContent' in first_flight and handshake.count('], ServerHello\n') == server_hellos,
                'missing early data or unexpected retry path')


def check_http(port, context):
    connection = http.client.HTTPSConnection('127.0.0.1', port, timeout=8, context=context)
    raw = socket.create_connection(('127.0.0.1', port), timeout=8)
    try:
        connection.sock = context.wrap_socket(raw, server_hostname='localhost')
        for method, path, body, expected in (
            ('POST', '/echo', FILE, FILE), ('GET', '/file', None, FILE),
            ('HEAD', '/file', None, b''), ('GET', '/', None, HELLO),
        ):
            connection.request(method, path, body)
            response = connection.getresponse()
            require((response.status, response.read()) == (200, expected), f'{method} {path}')
            if method == 'HEAD':
                require(response.getheader('Content-Length') == str(len(FILE)), 'HEAD length')
    finally:
        raw.close()
        connection.close()


def make_cert(folder, name, option, value):
    key = folder / (name + '.key')
    cert = folder / (name + '.pem')
    command = ['openssl', 'req', '-x509', '-newkey', option, '-nodes',
               '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost', '-days', '2',
               '-keyout', key, '-out', cert]
    if value:
        command.extend(['-pkeyopt', value])
    run(command)
    return cert, key, cert


def check_profile(label, command, identities, file, folder, go_client, ticket, wrong_key, weak_rsa):
    mismatched = subprocess.run([*command, KEYS / 'ec.pem', wrong_key, file],
                                capture_output=True, timeout=10)
    require(mismatched.returncode == 3 and b'does not match' in mismatched.stdout,
            'mismatched identity must fail before listening')
    weak_cert, weak_key, _ = weak_rsa
    weak = subprocess.run([*command, weak_cert, weak_key, file], capture_output=True, timeout=10)
    require(weak.returncode == 3 and b'RSA key needs at least 2048 bits' in weak.stdout,
            'weak RSA identity must fail before listening')
    for name, (cert, key, root) in identities.items():
        context = client_context(root)
        with server(command, cert, key, file) as port:
            get_hello(port, context)
            run([go_client, '-client', f'127.0.0.1:{port}', '-root', root])
            if name != 'p256':
                continue
            check_openssl(port, root, folder)
            check_early_data(port, root, folder, ticket)
            run_result = run(['curl', '--noproxy', '*', '--fail', '--silent', '--show-error',
                              '--tlsv1.3', '--http1.1', '--cacert', root,
                              '--resolve', f'localhost:{port}:127.0.0.1', f'https://localhost:{port}/file'])
            require(run_result.stdout == FILE, 'curl file body')
            check_http(port, context)
            get_hello(port, client_context(root, ()), protocol=None)
            with socket.create_connection(('127.0.0.1', port), timeout=8) as clear:
                clear.sendall(REQUEST)
                try:
                    require(not clear.recv(64).startswith(b'HTTP/'), 'clear HTTP answered by TLS listener')
                except ConnectionResetError:
                    pass
            reject(port, client_context(root, ('h2',)), 'TLSV1_ALERT_NO_APPLICATION_PROTOCOL')
            reject(port, context, 'CERTIFICATE_VERIFY_FAILED', 'wrong.example')
            old = ssl.create_default_context(cafile=root)
            old.maximum_version = ssl.TLSVersion.TLSv1_2
            reject(port, old, 'TLSV1_ALERT_PROTOCOL_VERSION')
            with socket.create_connection(('127.0.0.1', port), timeout=8) as idle:
                with ThreadPoolExecutor(max_workers=8) as pool:
                    list(pool.map(lambda _: get_hello(port, context), range(16)))
                require(idle.recv(1) == b'', 'idle TLS handshake did not expire')
            get_hello(port, context)
    cert, key, root = identities['p256']
    with server(command, cert, key, file, raw=True) as port:
        context = client_context(root, ('http/1.1', 'pas-test'))
        with socket.create_connection(('127.0.0.1', port), timeout=8) as connection:
            with context.wrap_socket(connection, server_hostname='localhost') as stream:
                require(stream.selected_alpn_protocol() == 'pas-test', 'standalone ALPN preference')
                require(stream.makefile('rb').read() == b'localhost pas-test', 'standalone SNI and ALPN')
    print(f'TLS 1.3 server {label}: verified five PEM identities, three suites, HRR, HTTPS and standalone TLS')


def tls12_client_hello(*, extensions=(), ems=b'', fallback=False):
    def vector(value, size=2):
        return len(value).to_bytes(size, 'big') + value

    suites = bytes.fromhex('c02b00ff' + ('5600' if fallback else ''))
    params = [(10, vector(bytes.fromhex('001d0017'))), (13, vector(bytes.fromhex('0403')))]
    if ems is not None:
        params.append((23, ems))
    params.extend(extensions)
    extensions = b''.join(code.to_bytes(2, 'big') + vector(value) for code, value in params)
    body = b'\x03\x03' + bytes(32) + b'\0' + vector(suites) + b'\x01\0' + vector(extensions)
    return b'\x16\x03\x01' + vector(b'\x01' + vector(body, 3))


def check_tls12_alerts(port):
    for options, expected in (
        ({'ems': None}, 40),
        ({'ems': b'\0'}, 50),
        ({'fallback': True}, 86),
        ({'extensions': [(43, bytes.fromhex('020302'))]}, 70),
        ({'extensions': [(0xff01, b'\x01\xaa')]}, 40),
    ):
        with socket.create_connection(('127.0.0.1', port), timeout=8) as connection:
            connection.sendall(tls12_client_hello(**options))
            with connection.makefile('rb') as stream:
                alert = stream.read(7)
                require(len(alert) == 7 and alert[0] == 21 and alert[3:] == bytes((0, 2, 2, expected)),
                        f'expected fatal alert {expected}, got {alert.hex()}')

    with socket.create_connection(('127.0.0.1', port), timeout=8) as connection:
        # The explicit versions vector selects TLS 1.2. ServerHello
        # must carry the downgrade sentinel, including on the TLS 1.2 wire.
        connection.sendall(tls12_client_hello(extensions=[(43, bytes.fromhex('020303'))]))
        with connection.makefile('rb') as stream:
            header = stream.read(5)
            require(header[:3] == b'\x16\x03\x03', 'expected a TLS 1.2 handshake record')
            response = stream.read(int.from_bytes(header[3:], 'big'))
            require(response[:1] == b'\x02' and response[30:38] == b'DOWNGRD\x01',
                    'missing TLS 1.2 downgrade sentinel')
            require(b'\x0e\0\0\0' == response[-4:], 'incomplete TLS 1.2 server flight')
            # A ChangeCipherSpec cannot replace the client's key exchange.
            connection.sendall(b'\x14\x03\x03\x00\x01\x01')
            require(stream.read(7) == b'\x15\x03\x03\x00\x02\x02\x0a', 'early change cipher spec')


def check_tls12_profile(label, command, identities, file, go_client):
    version = ssl.TLSVersion.TLSv1_2
    for name, (cert, key, root) in identities.items():
        with server(command, cert, key, file, tls12=True) as port:
            if name != 'ed25519':
                get_hello(port, client_context(root, version=version), version='TLSv1.2')
            run([go_client, '-client', f'127.0.0.1:{port}', '-root', root, '-client-version', '1.2'])
            if name not in ('p256', 'rsa'):
                continue
            for suffix, groups in (('AES128-GCM-SHA256', 'X25519:P-256'),
                                   ('AES256-GCM-SHA384', 'P-384:P-256'),
                                   ('CHACHA20-POLY1305', 'P-256')):
                auth = 'RSA' if name == 'rsa' else 'ECDSA'
                suite = f'ECDHE-{auth}-{suffix}'
                args = ['openssl', 's_client', '-connect', f'127.0.0.1:{port}', '-tls1_2',
                        '-CAfile', root, '-verify_return_error', '-verify_hostname', 'localhost',
                        '-servername', 'localhost', '-alpn', 'http/1.1', '-cipher', suite,
                        '-groups', groups, '-quiet']
                if name == 'rsa':
                    args += ['-sigalgs', 'rsa_pkcs1_sha256']
                result = run(args, input=REQUEST)
                require(result.stdout.startswith(b'HTTP/1.1 200 ') and result.stdout.endswith(HELLO), suite)
            if name != 'p256':
                continue
            # This client offers both versions. The server must choose TLS 1.3.
            both = client_context(root, version=version)
            both.maximum_version = ssl.TLSVersion.TLSv1_3
            get_hello(port, both)
            check_http(port, client_context(root, version=version))
            reject(port, client_context(root, ('h2',), version), 'TLSV1_ALERT_NO_APPLICATION_PROTOCOL')
            check_tls12_alerts(port)
            result = run(['curl', '--noproxy', '*', '--fail', '--silent', '--show-error',
                          '--tls-max', '1.2', '--tlsv1.2', '--http1.1', '--cacert', root,
                          '--resolve', f'localhost:{port}:127.0.0.1', f'https://localhost:{port}/file'])
            require(result.stdout == FILE, 'curl TLS 1.2 file body')
    cert, key, root = identities['p256']
    with server(command, cert, key, file, raw=True, tls12=True) as port:
        context = client_context(root, ('http/1.1', 'pas-test'), version)
        with socket.create_connection(('127.0.0.1', port), timeout=8) as connection:
            with context.wrap_socket(connection, server_hostname='localhost') as stream:
                require(stream.selected_alpn_protocol() == 'pas-test', 'TLS 1.2 standalone ALPN')
                require(stream.makefile('rb').read() == b'localhost pas-test', 'TLS 1.2 standalone SNI')
    print(f'TLS 1.2 server {label}: verified HTTPS, SNI, ALPN, six suites, and protocol alerts')


def main():
    compiler, build, qemu = (Path(arg).resolve() for arg in sys.argv[1:])
    go_client = build / 'tlsoracle-server-check'
    run(['go', 'build', '-o', go_client, '.'], timeout=180, cwd=ROOT / 'scripts/tlsoracle',
        env=dict(os.environ, GOCACHE=str(build / 'gocache')))
    with TemporaryDirectory(prefix='paslang-tls-server-') as tmp:
        folder = Path(tmp)
        file = folder / 'file'
        file.write_bytes(FILE)
        root = KEYS / 'ca.pem'
        sec1 = folder / 'ec-sec1.key'
        rsa_pkcs1 = folder / 'rsa-pkcs1.key'
        run(['openssl', 'pkey', '-in', KEYS / 'ec.key', '-traditional', '-out', sec1])
        run(['openssl', 'pkey', '-in', KEYS / 'rsa.key', '-traditional', '-out', rsa_pkcs1])
        wrong_key = folder / 'wrong.key'
        run(['openssl', 'genpkey', '-algorithm', 'EC', '-pkeyopt', 'ec_paramgen_curve:prime256v1',
             '-out', wrong_key])
        identities = {
            'p256': (KEYS / 'ec.pem', KEYS / 'ec.key', root),
            'p256-sec1': (KEYS / 'ec.pem', sec1, root),
            'rsa': (KEYS / 'rsa.pem', rsa_pkcs1, root),
            'ed25519': make_cert(folder, 'ed25519', 'ed25519', ''),
            'p384': make_cert(folder, 'p384', 'ec', 'ec_paramgen_curve:secp384r1'),
        }
        weak_rsa = make_cert(folder, 'weak-rsa', 'rsa:1024', '')
        ticket = folder / 'session.pem'
        save_early_ticket(*identities['p256'], ticket)
        for arch, cpu in (('amd64', 'base'), ('amd64', 'native'), ('arm64', 'base'), ('arm64', 'max')):
            units = build if arch == 'amd64' else build / 'a64'
            label = f'{arch}/{cpu}'
            binary = folder / f'tlsserver-{arch}-{cpu}'
            compile_command = [compiler, '-target', arch, '-cpu', cpu, '-Fu', units]
            run([*compile_command, '-o', binary, ROOT / 'testdata/tlsserver13.paslang'])
            runner = [] if arch == 'amd64' else [qemu]
            check_profile(label, [*runner, binary], identities, file, folder, go_client, ticket,
                          wrong_key, weak_rsa)
            check_tls12_profile(label, [*runner, binary], identities, file, go_client)
            check_key_limits(compile_command, runner, folder / (binary.name + '-short-epoch'),
                             identities['p256'], file)
            print(f'TLS server {label}: TLS 1.3 KeyUpdate and TLS 1.2 read/write key limits')


if __name__ == '__main__':
    main()
