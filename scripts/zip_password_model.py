#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacil@tucall.com>
# GPL version 3 or later; see COPYING. No warranty.
"""UNRUN source proposal. Fresh private output only; never regenerate canonicals.
Future development oracle: hashlib/HMAC, cryptography AES-ECB, zlib, struct.
Fixed synthetic salts/header bytes are test inputs, never an encryption API.
"""
import argparse, binascii, hashlib, hmac, io, json, shutil, struct, sys, zlib, zipfile
from pathlib import Path
import cryptography
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.bindings import _rust as crypto_binding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MASK = 0xffffffff
STAGE = dict(structure=0, unsupported=1, required=2, password=3, auth=4,
             inflate=5, size=6, crc=7, limit=8, writer=9, internal=10)


def crc(data):
    return binascii.crc32(data) & MASK


def rawcrc(state, byte):
    # Adapt the independent public complemented IEEE CRC, not a new CRC table.
    return (binascii.crc32(bytes((byte,)), state ^ MASK) ^ MASK) & MASK


class Legacy:
    def __init__(self, password):
        self.k = [0x12345678, 0x23456789, 0x34567890]
        for b in password:
            self.update(b)

    def update(self, b):
        self.k[0] = rawcrc(self.k[0], b)
        self.k[1] = ((self.k[1] + (self.k[0] & 255)) * 134775813 + 1) & MASK
        self.k[2] = rawcrc(self.k[2], self.k[1] >> 24)

    def code(self, data, decrypt=False):
        out = bytearray()
        for b in data:
            t = (self.k[2] | 2) & 65535
            coded = b ^ ((t * (t ^ 1) >> 8) & 255)
            self.update(coded if decrypt else b)
            out.append(coded)
        return bytes(out)


def aes_xor(key, data):
    blocks = (len(data) + 15) // 16
    counters = b''.join(i.to_bytes(16, 'little') for i in range(1, blocks + 1))
    context = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    stream = context.update(counters) + context.finalize()
    return bytes(a ^ b for a, b in zip(data, stream))


def pack(body, method, flags, checksum, size, extra=b'', local_extra=None,
         descriptor=0, comp_size=None):
    name = b'a.txt'
    local_extra = extra if local_extra is None else local_extra
    comp_size = len(body) if comp_size is None else comp_size
    dt, dd = 0x4200, 33
    filled = (0, 0, 0) if descriptor else (checksum, comp_size, size)
    local = struct.pack('<IHHHHHIIIHH', 0x04034b50, 20, flags, method,
                        dt, dd, *filled, len(name), len(local_extra)) + name + local_extra
    tail = b'' if not descriptor else ((struct.pack('<I', 0x08074b50) if descriptor == 2 else b'') +
                                     struct.pack('<III', checksum, comp_size, size))
    directory = struct.pack('<IHHHHHHIIIHHHHHII', 0x02014b50, 20, 20, flags, method,
                            dt, dd, checksum, comp_size, size, len(name), len(extra),
                            0, 0, 0, 0, 0) + name + extra
    end = struct.pack('<IHHHHIIH', 0x06054b50, 0, 0, 1, 1, len(directory), len(local + body + tail), 0)
    return local + body + tail + directory + end


def make(kind='aes', password=b'123', plain=b'ABCDEFGH', method=0,
         descriptor=0, version=1, strength=3, no_data=False, compressed=None,
         size=None, checksum=None, extension=b''):
    size = len(plain) if size is None else size
    checksum = (0 if kind == 'aes' and version == 2 else crc(plain)) if checksum is None else checksum
    if compressed is None:
        if method == 8 and not no_data:
            co = zlib.compressobj(6, zlib.DEFLATED, -15)
            compressed = co.compress(plain) + co.flush()
            de = zlib.decompressobj(-15)
            assert de.decompress(compressed) + de.flush() == plain and de.eof and not de.unused_data
        else:
            compressed = plain
    flags = (8 if descriptor else 0) | (0 if kind == 'plain' else 1)
    extra, wire_method = b'', method
    meta = dict(kind=kind, password=password, plain=plain, method=method,
                descriptor=descriptor, checksum=checksum, size=size, flags=flags)
    if kind == 'aes':
        keylen = {1:16, 2:24, 3:32}[strength]
        salt = bytes(range(keylen // 2))
        key = hashlib.pbkdf2_hmac('sha1', password, salt, 1000, 2 * keylen + 2)
        ciphertext = aes_xor(key[:keylen], compressed)
        tag = hmac.digest(key[keylen:2 * keylen], ciphertext, 'sha1')[:10]
        body = salt + key[-2:] + ciphertext + tag
        extra = struct.pack('<HHH2sBH', 0x9901, 7 + len(extension), version, b'AE', strength, method) + extension
        wire_method = 99
        meta.update(salt=salt, verifier=key[-2:], ciphertext=ciphertext, tag=tag,
                    version=version, strength=strength, body=body, extra=extra)
    elif kind == 'legacy':
        check = 0x42 if descriptor else checksum >> 24
        header = bytes(range(11)) + bytes((check,))
        body = Legacy(password).code(header + compressed)
        meta.update(body=body, check=check)
    else:
        body = compressed
        meta.update(body=body)
    meta.update(extra=extra, wire_method=wire_method)
    blob = pack(body, wire_method, flags, checksum, size, extra, descriptor=descriptor)
    if kind == 'plain' or (kind == 'legacy' and password and compressed):
        assert zipfile.ZipFile(io.BytesIO(blob)).read('a.txt', pwd=password) == plain
    return blob, meta


def crc_signature_payload():
    # Solve four suffix bytes using independent binascii CRC linearity.
    prefix = b'descriptor CRC equals signature:'
    base = crc(prefix + bytes(4))
    basis = {}
    for i in range(32):
        value, mask = crc(prefix + (1 << i).to_bytes(4, 'little')) ^ base, 1 << i
        while value:
            pivot = value.bit_length() - 1
            if pivot not in basis:
                basis[pivot] = (value, mask)
                break
            row, bits = basis[pivot]
            value ^= row
            mask ^= bits
    target, solution = 0x08074b50 ^ base, 0
    while target:
        row, bits = basis[target.bit_length() - 1]
        target ^= row
        solution ^= bits
    payload = prefix + solution.to_bytes(4, 'little')
    assert crc(payload) == 0x08074b50
    return payload


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--canonicals', required=True, type=Path)
    ap.add_argument('--fixture-pins', required=True, type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    rows, evidence = [], []

    def add(label, blob, password=b'123', have=True, stage=-1, plain=b'', limit=0):
        assert all(c.isalnum() or c in '-_' for c in label)
        filename = label + '.zip'
        (args.out / filename).write_bytes(blob)
        digest = hashlib.sha256(blob).hexdigest()
        rows.append('\t'.join([label, filename, password.hex() or '-', str(int(have)),
                               str(stage), hashlib.sha256(plain).hexdigest(), str(limit), digest]))
        evidence.append(dict(id=label, archive_sha256=digest, bytes=len(blob), stage=stage,
                             password_hex=password.hex(), have_password=have,
                             plaintext_sha256=hashlib.sha256(plain).hexdigest(), limit=limit))

    # Copy exact historic originals. They have already been independently decoded.
    pins = json.loads(args.fixture_pins.read_text())
    for rec in pins['historical_expected_outputs']:
        file = args.canonicals / rec['archive']
        assert hashlib.sha256(file.read_bytes()).hexdigest() == rec['archive_sha256']
        filename = 'canonical-' + rec['archive']
        shutil.copyfile(file, args.out / filename)
        password = b'Ab.9' if rec.get('zipcrypto') else b'123'
        rows.append('\t'.join([filename[:-4], filename, password.hex(), '1', '-1',
                               rec['plaintext_sha256'], '0', rec['archive_sha256']]))
    for version in (1, 2):
        for strength in (1, 2, 3):
            for method in (0, 8):
                for descriptor in (0, 1, 2):
                    label = f'a{version}-{strength}-m{method}-d{descriptor}'
                    blob, meta = make(version=version, strength=strength, method=method, descriptor=descriptor)
                    add(label, blob, plain=meta['plain'])
            for method in (0, 8):
                blob, meta = make(version=version, strength=strength, method=method, plain=b'', no_data=True)
                add(f'empty-a{version}-{strength}-m{method}', blob, plain=b'')
            blob, meta = make(version=version, strength=strength, method=8, plain=b'')
            add(f'empty-deflate-a{version}-{strength}', blob, plain=b'')
    for method in (0, 8):
        for descriptor in (0, 1, 2):
            blob, meta = make(kind='legacy', method=method, descriptor=descriptor)
            assert 0x42 != meta['checksum'] >> 24
            add(f'legacy-m{method}-d{descriptor}', blob, plain=meta['plain'])
        blob, meta = make(kind='legacy', method=method, plain=b'', no_data=True)
        add(f'legacy-empty-m{method}', blob, plain=b'')
    for n in (1, 15, 16, 17, 4095, 4096, 4097, 65535, 65536, 65537):
        plain = bytes((i * 131 + 17) & 255 for i in range(n))
        blob, meta = make(plain=plain, version=2)
        add(f'counter-{n}', blob, plain=plain)
    for name, password in [('empty', b''), ('nul', b'p\x00w'), ('raw', b'\xff\x80\x00'), ('long', bytes(range(129)))]:
        for kind in ('aes', 'legacy'):
            blob, meta = make(kind=kind, password=password)
            add(f'password-{kind}-{name}', blob, password=password, plain=meta['plain'])
            add(f'omitted-{kind}-{name}', blob, have=False, stage=STAGE['required'])
    blob, meta = make()
    add('password-required', blob, have=False, stage=STAGE['required'])
    wrong = b'wrong'
    assert hashlib.pbkdf2_hmac('sha1', wrong, meta['salt'], 1000, 66)[-2:] != meta['verifier']
    add('wrong-password', blob, password=wrong, stage=STAGE['password'])
    add('declared-limit-before-password', blob, password=wrong, stage=STAGE['limit'], limit=7)
    for i in range(10):
        body = bytearray(meta['body']); body[-10 + i] ^= 1
        add(f'tag-byte-{i}', pack(body, 99, 1, meta['checksum'], meta['size'], meta['extra']), stage=STAGE['auth'])
    for i in (16, 17):
        changed = bytearray(meta['body']); changed[i] ^= 1
        add(f'verifier-byte-{i - 16}', pack(changed, 99, 1, meta['checksum'], meta['size'], meta['extra']), stage=STAGE['password'])
    changed = bytearray(meta['body']); changed[0] ^= 1
    assert hashlib.pbkdf2_hmac('sha1', b'123', bytes(changed[:16]), 1000, 66)[-2:] != bytes(changed[16:18])
    add('salt-tamper', pack(changed, 99, 1, meta['checksum'], meta['size'], meta['extra']), stage=STAGE['password'])
    for field, at in [('flags', 6), ('method', 8), ('time', 10), ('name', 30), ('aes-prefix', 43)]:
        changed = bytearray(blob); changed[at] ^= 1
        add('local-directory-' + field, changed, stage=STAGE['structure'])
    # Same known AES prefix, unrelated extension tails may differ between headers.
    ext = meta['extra'][:2] + struct.pack('<H', 8) + meta['extra'][4:] + b'X'
    add('different-extra-tails', pack(meta['body'], 99, 1, meta['checksum'], meta['size'], ext,
                                    local_extra=ext[:-1] + b'Y'), plain=meta['plain'])
    body = bytearray(meta['body']); body[18] ^= 1
    add('ciphertext-tamper', pack(body, 99, 1, meta['checksum'], meta['size'], meta['extra']), stage=STAGE['auth'])
    # Correct MAC but wrong authoritative CRC reaches the final AE1 CRC check.
    bad, _ = make(checksum=meta['checksum'] ^ 1)
    add('ae1-crc', bad, stage=STAGE['crc'])
    bad, _ = make(version=2, checksum=1)
    add('ae2-nonzero-crc', bad, stage=STAGE['structure'])
    bad, _ = make(size=9)
    add('stored-size', bad, stage=STAGE['size'])
    bad, bm = make(method=8, compressed=b'\x07')
    add('authenticated-invalid-deflate', bad, stage=STAGE['inflate'])
    body = bm['body'][:-1] + bytes((bm['body'][-1] ^ 1,))
    add('bad-mac-invalid-deflate', pack(body, 99, 1, bm['checksum'], bm['size'], bm['extra']), stage=STAGE['auth'])
    bad, _ = make(method=8, compressed=bytes.fromhex('73747276717573f70000'), size=7)
    add('literal-budget', bad, stage=STAGE['limit'])
    for label, extra, flags, method, expected in [
        ('missing-aes', b'', 1, 99, 'structure'),
        ('duplicate-aes', meta['extra'] * 2, 1, 99, 'structure'),
        ('short-tlv', b'\x01\x99\x07', 1, 99, 'structure'),
        ('bad-vendor', struct.pack('<HHH2sBH', 0x9901, 7, 1, b'ZZ', 3, 0), 1, 99, 'unsupported'),
        ('bad-version', struct.pack('<HHH2sBH', 0x9901, 7, 3, b'AE', 3, 0), 1, 99, 'unsupported'),
        ('bad-strength', struct.pack('<HHH2sBH', 0x9901, 7, 1, b'AE', 4, 0), 1, 99, 'unsupported'),
        ('bad-real-method', struct.pack('<HHH2sBH', 0x9901, 7, 1, b'AE', 3, 6), 1, 99, 'unsupported'),
        ('zip64-extra', bytes((1,0,0,0)) + meta['extra'], 1, 99, 'unsupported'),
        ('strong', meta['extra'], 65, 99, 'unsupported'),
        ('masked', meta['extra'], 8193, 99, 'unsupported'),
        ('aes-not-encrypted', meta['extra'], 0, 99, 'structure'),
        ('aes-wrong-method', meta['extra'], 1, 8, 'structure')]:
        add(label, pack(meta['body'], method, flags, meta['checksum'], meta['size'], extra), stage=STAGE[expected])
    for n in range(1, 11):
        add(f'truncated-aes-tlv-{n}', pack(meta['body'], 99, 1, meta['checksum'], meta['size'], meta['extra'][:n]), stage=STAGE['structure'])
    # Prefix beyond the known7 bytes is permitted and preserved independently.
    extended, em = make(extension=b'future-tail')
    add('aes-extension-tail', extended, plain=em['plain'])
    for n in (0, 1, 7, 15, 16, 17, 27):
        add(f'truncated-overhead-{n}', pack(meta['body'][:n], 99, 1, meta['checksum'], meta['size'], meta['extra']), stage=STAGE['structure'])
    for desc in (1, 2):
        good, gm = make(descriptor=desc, plain=crc_signature_payload())
        add(f'descriptor-crc-signature-{desc}', good, plain=gm['plain'])
        at = 30 + len(b'a.txt') + len(gm['extra']) + len(gm['body'])
        changed = bytearray(good); changed[at + (4 if desc == 2 else 0) + 4] ^= 1
        add(f'descriptor-compsize-{desc}', changed, stage=STAGE['structure'])
    # True verifier collision: two passwords, same salt and verifier, different keys.
    seen = {}
    for i in range(4096):
        password = b'collision-' + str(i).encode()
        verifier = hashlib.pbkdf2_hmac('sha1', password, bytes(range(8)), 1000, 34)[-2:]
        if verifier in seen:
            correct, wrong = seen[verifier], password
            good, gm = make(password=correct, version=2, strength=1)
            wrong_key = hashlib.pbkdf2_hmac('sha1', wrong, gm['salt'], 1000, 34)
            assert wrong_key[-2:] == gm['verifier']
            assert hmac.digest(wrong_key[16:32], gm['ciphertext'], 'sha1')[:10] != gm['tag']
            add('verifier-collision-correct', good, password=correct, plain=gm['plain'])
            add('verifier-collision-wrong', good, password=wrong, stage=STAGE['auth'])
            break
        seen[verifier] = password
    else:
        raise RuntimeError('bounded verifier collision search exhausted')
    # Real ZipCrypto header collisions; stored data distinguishes CRC from password stage.
    for plain in (b'ABCDEFGH', b''):
        good, gm = make(kind='legacy', plain=plain)
        for i in range(4096):
            wrong = b'legacy-collision-' + str(i).encode()
            decoded = Legacy(wrong).code(gm['body'], decrypt=True)
            if decoded[11] == gm['check'] and (not plain or crc(decoded[12:]) != gm['checksum']):
                add('legacy-collision-' + ('empty' if not plain else 'crc'), good,
                    password=wrong, stage=-1 if not plain else STAGE['crc'], plain=b'')
                break
        else:
            raise RuntimeError('bounded legacy header collision search exhausted')
    good, gm = make(kind='legacy', method=8, plain=b'')
    add('legacy-empty-real-deflate', good, plain=b'')
    # Missing descriptor must not borrow bytes from the central directory.
    good, gm = make(descriptor=1)
    missing = pack(gm['body'], 99, 9, gm['checksum'], gm['size'], gm['extra'])
    add('missing-descriptor', missing, stage=STAGE['structure'])
    # Plain entries ignore explicit passwords, including raw bytes.
    good, gm = make(kind='plain')
    add('plain-omitted', good, have=False, plain=gm['plain'])
    add('plain-password', good, password=b'\xff\x00', plain=gm['plain'])
    (args.out / 'cases.tsv').write_text('\n'.join(rows) + '\n')
    (args.out / 'MODEL.json').write_text(json.dumps(dict(executed=True, python=sys.version,
        zlib_runtime=zlib.ZLIB_RUNTIME_VERSION, cryptography_version=cryptography.__version__,
        aes_openssl_runtime=default_backend().openssl_version_text(),
        aes_binding=dict(path=crypto_binding.__file__, sha256=hashlib.sha256(Path(crypto_binding.__file__).read_bytes()).hexdigest()),
        provider_isa_reviewed=False, new_cases=evidence,
        canonical_source_revision='f791e69', canonical_reused_without_decoding=True), indent=2) + '\n')
    print('prepared', len(rows), 'ZIP password contracts')


if __name__ == '__main__':
    main()
