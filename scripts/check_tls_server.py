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
def server(command, cert, key, file, raw=False, tls12=False, tickets=False):
    env = dict(os.environ, PASLANG_MAXPROCS='1')
    args = [*command, cert, key, file, 'raw' if raw else '', 'tls12' if tls12 else '',
            'tickets' if tickets else '']
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


def get_hello(port, context, protocol='http/1.1', version='TLSv1.3', session=None):
    with socket.create_connection(('127.0.0.1', port), timeout=8) as connection:
        with context.wrap_socket(connection, server_hostname='localhost', suppress_ragged_eofs=False,
                                 session=session) as stream:
            require(stream.version() == version, 'TLS version')
            require(stream.selected_alpn_protocol() == protocol, 'ALPN')
            stream.sendall(REQUEST)
            response = http.client.HTTPResponse(stream, method='GET')
            response.begin()
            require((response.status, response.read()) == (200, HELLO), 'HTTPS response')
            require(stream.recv(1) == b'', 'expected TLS close_notify')
            return stream.session, stream.session_reused


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
            session, reused = get_hello(port, context)
            require(not reused and not session.has_ticket, 'session tickets are opt-in')
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
            check_tls13_alerts(port)
            get_hello(port, client_context(root, ()), protocol=None)
            with socket.create_connection(('127.0.0.1', port), timeout=8) as clear:
                clear.sendall(REQUEST)
                try:
                    require(clear.recv(1) == b'', 'clear HTTP answered by TLS listener')
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
    print(f'TLS 1.3 server {label}: verified five PEM identities, three suites, HRR, HTTPS, standalone TLS, and protocol alerts')


def check_tls13_resumption(label, command, identity, file, folder, go_client):
    cert, key, root = identity
    with server(command, cert, key, file, tickets=True) as port:
        context = client_context(root)
        session, resumed = get_hello(port, context)
        require(session.has_ticket and not resumed and session.ticket_lifetime_hint == 3600,
                'full handshake must issue an hour-long ticket')

        outgoing = ssl.MemoryBIO()
        client = context.wrap_bio(ssl.MemoryBIO(), outgoing, server_hostname='localhost', session=session)
        try:
            client.do_handshake()
        except ssl.SSLWantReadError:
            pass
        hello = outgoing.read()
        require(len(hello) > 5 and hello[0] == 22 and int.from_bytes(hello[3:5], 'big') == len(hello) - 5,
                'expected a single ClientHello record')
        # The binder is the final field of the PSK extension, which is last.
        with socket.create_connection(('127.0.0.1', port), timeout=8) as connection:
            connection.sendall(hello[:-1] + bytes((hello[-1] ^ 1,)))
            with connection.makefile('rb') as stream:
                alert = stream.read(7)
                require(alert == b'\x15\x03\x03\x00\x02\x02\x33', f'bad binder alert {alert.hex()}')

        with ThreadPoolExecutor(max_workers=2) as pool:
            reuse = [used for _, used in pool.map(lambda _: get_hello(port, context, session=session), range(2))]
        require(sorted(reuse) == [False, True], 'a valid ticket must work once, even across concurrent handshakes')
        _, reused = get_hello(port, context, session=session)
        require(not reused, 'a consumed ticket must fall back to certificate authentication')
        run([go_client, '-client', f'127.0.0.1:{port}', '-root', root, '-client-resume'])

        saved = folder / 'resume.pem'
        trace = folder / 'resume-trace.txt'
        args = ['openssl', 's_client', '-connect', f'127.0.0.1:{port}', '-tls1_3',
                '-CAfile', root, '-verify_return_error', '-verify_hostname', 'localhost',
                '-servername', 'localhost', '-alpn', 'http/1.1', '-ciphersuites', 'TLS_AES_256_GCM_SHA384', '-quiet']
        run([*args, '-groups', 'X25519', '-sess_out', saved], input=REQUEST)
        result = run([*args, '-groups', 'X448:P-256', '-sess_in', saved, '-msg', '-msgfile', trace], input=REQUEST)
        handshake = trace.read_text()
        require(result.stdout.startswith(b'HTTP/1.1 200 ') and result.stdout.endswith(HELLO),
                'resumed HTTPS after HelloRetryRequest')
        require(handshake.count('], ServerHello\n') == 2 and '], Certificate\n' not in handshake,
                'expected retry and PSK instead of another certificate exchange')
    print(f'TLS 1.3 resumption {label}: OpenSSL and Go, retry, binder alert, and single-use tickets')


def check_tls12_resumption(label, command, identities, file, folder, go_client):
    version = ssl.TLSVersion.TLSv1_2
    for name in ('p256', 'rsa'):
        cert, key, root = identities[name]
        context = client_context(root, version=version)
        with server(command, cert, key, file, tls12=True, tickets=True) as port:
            session, reused = get_hello(port, context, version='TLSv1.2')
            require(session.has_ticket and not reused and session.ticket_lifetime_hint == 3600,
                    'TLS 1.2 full handshake must issue an hour-long ticket')
            for _ in range(2):
                _, reused = get_hello(port, context, version='TLSv1.2', session=session)
                require(reused, 'TLS 1.2 must reuse a valid ticket')
            context.set_alpn_protocols([])
            _, reused = get_hello(port, context, protocol=None, version='TLSv1.2', session=session)
            require(not reused, 'TLS 1.2 must use a full handshake when ALPN changes')
            context.set_alpn_protocols(['http/1.1'])
            _, reused = get_hello(port, context, version='TLSv1.2', session=session)
            require(reused, 'TLS 1.2 ticket remains usable with the original ALPN')

            id_context = client_context(root, version=version)
            id_context.options |= ssl.OP_NO_TICKET
            id_session, reused = get_hello(port, id_context, version='TLSv1.2')
            require(len(id_session.id) == 32 and not id_session.has_ticket and not reused,
                    'TLS 1.2 must issue a session ID to a client without tickets')
            _, reused = get_hello(port, id_context, version='TLSv1.2', session=id_session)
            require(reused, 'TLS 1.2 must resume a valid session ID')

            run([go_client, '-client', f'127.0.0.1:{port}', '-root', root,
                 '-client-version', '1.2', '-client-resume'])
            saved, trace = folder / 'resume12.pem', folder / 'resume12-trace.txt'
            args = ['openssl', 's_client', '-connect', f'127.0.0.1:{port}', '-tls1_2',
                    '-CAfile', root, '-verify_return_error', '-verify_hostname', 'localhost',
                    '-servername', 'localhost', '-alpn', 'http/1.1', '-quiet']
            run([*args, '-sess_out', saved], input=REQUEST)
            result = run([*args, '-sess_in', saved, '-msg', '-msgfile', trace], input=REQUEST)
            handshake = trace.read_text()
            require(result.stdout.startswith(b'HTTP/1.1 200 ') and result.stdout.endswith(HELLO),
                    'TLS 1.2 abbreviated handshake must carry HTTPS')
            require('], ServerHello\n' in handshake and '], Finished\n' in handshake and
                    '], Certificate\n' not in handshake and '], NewSessionTicket\n' not in handshake,
                    'TLS 1.2 abbreviated flight must reuse the original ticket')

        with server(command, cert, key, file, tls12=True, tickets=True) as other:
            _, reused = get_hello(other, context, version='TLSv1.2', session=session)
            require(not reused, 'TLS 1.2 ticket belongs to the configuration that issued it')
    print(f'TLS 1.2 resumption {label}: OpenSSL and Go, ECDSA and RSA, tickets, session IDs and full fallback')


def vector(value, size=2):
    return len(value).to_bytes(size, 'big') + value


def record(content, value, version=b'\x03\x03'):
    return bytes((content,)) + version + vector(value)


def client_hello(extensions, *, legacy=b'\x03\x03', session=b'',
                 suites=b'\x13\x01', compression=b'\0'):
    params = b''.join(code.to_bytes(2, 'big') + vector(value) for code, value in extensions)
    body = legacy + bytes(32) + vector(session, 1) + vector(suites) + vector(compression, 1)
    return b'\x01' + vector(body + vector(params), 3)


def tls12_client_hello(*, extensions=(), ems=b'', fallback=False):
    suites = bytes.fromhex('c02b00ff' + ('5600' if fallback else ''))
    params = [(10, vector(bytes.fromhex('001d0017'))), (13, vector(bytes.fromhex('0403')))]
    if ems is not None:
        params.append((23, ems))
    params.extend(extensions)
    return record(22, client_hello(params, suites=suites), b'\x03\x01')


def expect_fatal_alert(stream, name, expected):
    alert = stream.read(7)
    require(alert == record(21, bytes((2, expected))),
            f'{name}: expected fatal alert {expected}, got {alert.hex() or "EOF"}')


def check_tls13_alerts(port):
    # BoGo runner.go at 7e529d2b3971c10d63c6a980f3744f580321ff40:
    # ExtraCompressionMethods, DuplicateExtensionServer, MissingKeyShare-Server
    # and SecondClientHelloMissingKeyShare. RFC 9846 defines the alert bytes.
    extensions = (
        (43, vector(b'\x03\x04', 1)),  # supported_versions
        (10, vector(b'\x00\x1d')),     # supported_groups (X25519)
        (13, vector(b'\x04\x03')),     # signature_algorithms (ECDSA P-256)
        (51, vector(b'')),             # key_share (request a retry)
    )
    hello = client_hello(extensions)
    without_key_share = client_hello(extensions[:-1])
    for name, request, expected in (
        ('extra compression methods', record(22, client_hello(extensions, compression=b'\x01\x00')), 47),
        ('duplicate extensions', record(22, client_hello(extensions + extensions[:1])), 50),
        ('missing key_share', record(22, without_key_share), 109),
        ('missing supported_groups', record(22, client_hello(extensions[:1] + extensions[2:])), 109),
        ('missing signature_algorithms', record(22, client_hello(extensions[:2] + extensions[3:])), 109),
        ('legacy session ID too long', record(22, client_hello(extensions, session=bytes(33))), 50),
        ('odd cipher suite vector', record(22, client_hello(extensions, suites=b'\x13\x01\x00')), 50),
        ('truncated extension vector', record(22, b'\x01' + vector(hello[4:-1], 3)), 50),
        ('wrong legacy version', record(22, client_hello(extensions, legacy=b'\x03\x04')), 70),
        ('wrong first handshake message', record(22, b'\x14\x00\x00\x00'), 10),
        ('empty handshake record', record(22, b''), 10),
        ('oversized plaintext record', record(22, bytes(16385)), 22),
        ('premature change_cipher_spec', record(20, b'\x01'), 10),
        ('premature application_data', record(23, b'\x00'), 10),
        ('unrecognized record type', record(255, b''), 10),
    ):
        with socket.create_connection(('127.0.0.1', port), timeout=8) as connection:
            connection.sendall(request)
            with connection.makefile('rb') as stream:
                expect_fatal_alert(stream, name, expected)

    retry_random = bytes.fromhex('cf21ad74e59a6111be1d8c021e65b891c2a211167abb8c5e079e09e2c8a8339c')
    for name, request, expected in (
        ('second ClientHello missing key_share', record(22, without_key_share), 109),
        ('second ClientHello after dummy CCS',
         record(20, b'\x01') + record(22, without_key_share), 109),
        ('second ClientHello wrong legacy version',
         record(22, client_hello(extensions, legacy=b'\x03\x04')), 70),
        ('invalid change_cipher_spec value', record(20, b'\x02'), 10),
        ('invalid change_cipher_spec length', record(20, b'\x01\x01'), 10),
        ('interleaved change_cipher_spec', record(22, hello[:8]) + record(20, b'\x01'), 10),
    ):
        with socket.create_connection(('127.0.0.1', port), timeout=8) as connection:
            connection.sendall(record(22, hello, b'\x03\x01'))
            with connection.makefile('rb') as stream:
                header = stream.read(5)
                require(header[:3] == b'\x16\x03\x03', f'{name}: expected HelloRetryRequest')
                retry = stream.read(int.from_bytes(header[3:], 'big'))
                require(retry[:1] == b'\x02' and retry[6:38] == retry_random,
                        f'{name}: missing HelloRetryRequest random')
                connection.sendall(request)
                expect_fatal_alert(stream, name, expected)


def check_tls12_alerts(port):
    for name, options, expected in (
        ('missing EMS', {'ems': None}, 40),
        ('nonempty EMS', {'ems': b'\0'}, 50),
        ('inappropriate fallback', {'fallback': True}, 86),
        ('unsupported version', {'extensions': [(43, bytes.fromhex('020302'))]}, 70),
        ('nonempty renegotiation', {'extensions': [(0xff01, b'\x01\xaa')]}, 40),
        ('duplicate extensions', {'extensions': [(23, b'')]}, 50),
    ):
        with socket.create_connection(('127.0.0.1', port), timeout=8) as connection:
            connection.sendall(tls12_client_hello(**options))
            with connection.makefile('rb') as stream:
                expect_fatal_alert(stream, name, expected)

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
            expect_fatal_alert(stream, 'early TLS 1.2 change_cipher_spec', 10)


def check_tls12_profile(label, command, identities, file, go_client):
    version = ssl.TLSVersion.TLSv1_2
    for name, (cert, key, root) in identities.items():
        with server(command, cert, key, file, tls12=True) as port:
            if name != 'ed25519':
                session, reused = get_hello(port, client_context(root, version=version), version='TLSv1.2')
                require(not reused and not session.has_ticket, 'TLS 1.2 tickets are opt-in')
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
            check_tls12_resumption(label, [*runner, binary], identities, file, folder, go_client)
            check_tls13_resumption(label, [*runner, binary], identities['p256'], file, folder, go_client)
            check_key_limits(compile_command, runner, folder / (binary.name + '-short-epoch'),
                             identities['p256'], file)
            print(f'TLS server {label}: TLS 1.3 KeyUpdate and TLS 1.2 read/write key limits')


if __name__ == '__main__':
    main()
