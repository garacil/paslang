#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacil@tucall.com>
#
# paslang is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# paslang is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with paslang.  If not, see <https://www.gnu.org/licenses/>.

"""The exact model of testdata/hash1.paslang (P111): Python's hashlib,
hmac and zlib for the standards, and the reference definitions of
CRC-32C, FNV-1a, MurmurHash3 (x86, 32 bits) and SipHash-2-4, run over
the same inputs, printing what the program must print. A 64-bit word
prints as the signed Integer it is in paslang."""
import hashlib
import hmac
import zlib

MASK32 = 0xffffffff
MASK64 = 0xffffffffffffffff


def signed64(x):
    x &= MASK64
    return x - (1 << 64) if x >> 63 else x


def pattern(n):
    return bytes(((i * 7 + 3) & 255) for i in range(1, n + 1))


CRC32C_TAB = []
for i in range(256):
    c = i
    for _ in range(8):
        c = (c >> 1) ^ 0x82f63b78 if c & 1 else c >> 1
    CRC32C_TAB.append(c)


def crc32c(data, crc=0):
    c = (~crc) & MASK32
    for b in data:
        c = CRC32C_TAB[(c ^ b) & 255] ^ (c >> 8)
    return (~c) & MASK32


def crc32(data, crc=0):
    return zlib.crc32(data, crc) & MASK32


def adler32(data, adler=1):
    return zlib.adler32(data, adler) & MASK32


def fnv1a32(data):
    h = 0x811c9dc5
    for b in data:
        h = ((h ^ b) * 0x01000193) & MASK32
    return h


def fnv1a64(data):
    h = 0xcbf29ce484222325
    for b in data:
        h = ((h ^ b) * 0x100000001b3) & MASK64
    return signed64(h)


def rotl32(x, r):
    return ((x << r) | (x >> (32 - r))) & MASK32


def murmur3(data, seed=0):
    h = seed & MASK32
    n = len(data)
    blocks = n // 4
    for i in range(blocks):
        k = int.from_bytes(data[i * 4:i * 4 + 4], 'little')
        k = (k * 0xcc9e2d51) & MASK32
        k = rotl32(k, 15)
        k = (k * 0x1b873593) & MASK32
        h ^= k
        h = rotl32(h, 13)
        h = (h * 5 + 0xe6546b64) & MASK32
    k = 0
    tail = data[blocks * 4:]
    if len(tail) >= 3:
        k ^= tail[2] << 16
    if len(tail) >= 2:
        k ^= tail[1] << 8
    if len(tail) >= 1:
        k ^= tail[0]
        k = (k * 0xcc9e2d51) & MASK32
        k = rotl32(k, 15)
        k = (k * 0x1b873593) & MASK32
        h ^= k
    h ^= n
    h ^= h >> 16
    h = (h * 0x85ebca6b) & MASK32
    h ^= h >> 13
    h = (h * 0xc2b2ae35) & MASK32
    h ^= h >> 16
    return h


def rotl64(x, r):
    return ((x << r) | (x >> (64 - r))) & MASK64


def siphash(data, k0, k1):
    k0 &= MASK64
    k1 &= MASK64
    v0 = k0 ^ 0x736f6d6570736575
    v1 = k1 ^ 0x646f72616e646f6d
    v2 = k0 ^ 0x6c7967656e657261
    v3 = k1 ^ 0x7465646279746573

    def rnd():
        nonlocal v0, v1, v2, v3
        v0 = (v0 + v1) & MASK64
        v1 = rotl64(v1, 13)
        v1 ^= v0
        v0 = rotl64(v0, 32)
        v2 = (v2 + v3) & MASK64
        v3 = rotl64(v3, 16)
        v3 ^= v2
        v0 = (v0 + v3) & MASK64
        v3 = rotl64(v3, 21)
        v3 ^= v0
        v2 = (v2 + v1) & MASK64
        v1 = rotl64(v1, 17)
        v1 ^= v2
        v2 = rotl64(v2, 32)
    n = len(data)
    blocks = n // 8
    for i in range(blocks):
        m = int.from_bytes(data[i * 8:i * 8 + 8], 'little')
        v3 ^= m
        rnd()
        rnd()
        v0 ^= m
    b = (n << 56) & MASK64
    for j, byte in enumerate(data[blocks * 8:]):
        b |= byte << (8 * j)
    v3 ^= b
    rnd()
    rnd()
    v0 ^= b
    v2 ^= 0xff
    for _ in range(4):
        rnd()
    return signed64(v0 ^ v1 ^ v2 ^ v3)


def H(name, data):
    return hashlib.new(name, data).digest()


def main():
    out = []
    w = out.append
    w(b''.hex() + b'paslang'.hex() + ' ' + bytes([0, 255, 16]).hex())
    s = b'abc'
    for name in ('md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512',
                 'sha3_224', 'sha3_256', 'sha3_384', 'sha3_512'):
        w(H(name, b'').hex() + ' ' + H(name, s).hex())
    s = b'abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq'
    w(H('sha256', s).hex() + ' ' + H('sha1', s).hex())
    s = b'The quick brown fox jumps over the lazy dog'
    w(f"{crc32(s)} {crc32c(s)} {adler32(s)} {fnv1a32(s)} {fnv1a64(s)} {murmur3(s)} {murmur3(s, 42)}")
    key = b'Jefe'
    msg = b'what do ya want for nothing?'
    w(hmac.new(key, msg, 'sha256').hexdigest())
    w(hmac.new(key, msg, 'sha224').hexdigest())
    w(hmac.new(key, msg, 'sha384').hexdigest())
    w(hmac.new(key, msg, 'sha512').hexdigest())
    w(hmac.new(key, msg, 'sha1').hexdigest() + ' ' + hmac.new(key, msg, 'md5').hexdigest())
    key = bytes([0xaa] * 131)
    msg = b'Test Using Larger Than Block-Size Key - Hash Key First'
    w(hmac.new(key, msg, 'sha256').hexdigest())
    w(hmac.new(key, msg, 'sha512').hexdigest())
    msg = bytes(range(15))
    w(f"{siphash(msg, 0x0706050403020100, 0x0f0e0d0c0b0a0908)} {siphash(b'', 0, 0)}")

    def fold(fn, label):
        acc = b''
        for i in range(301):
            acc = hashlib.sha256(acc + fn(i)).digest()
        w(label + ' ' + acc.hex())
    fold(lambda i: H('md5', pattern(i)), 'md5')
    fold(lambda i: H('sha1', pattern(i)), 'sha1')
    fold(lambda i: H('sha224', pattern(i)), 'sha224')
    fold(lambda i: H('sha256', pattern(i)), 'sha256')
    fold(lambda i: H('sha384', pattern(i)), 'sha384')
    fold(lambda i: H('sha512', pattern(i)), 'sha512')
    fold(lambda i: H('sha3_256', pattern(i)), 'sha3_256')
    fold(lambda i: H('sha3_512', pattern(i)), 'sha3_512')
    fold(lambda i: H('sha3_224', pattern(i)) + H('sha3_384', pattern(i)), 'sha3_224_384')
    fold(lambda i: f"{crc32(pattern(i))} {crc32c(pattern(i))} {adler32(pattern(i))}".encode(), 'crc')
    fold(lambda i: f"{fnv1a32(pattern(i))} {fnv1a64(pattern(i))} {murmur3(pattern(i), i)} {siphash(pattern(i), i, -i)}".encode(), 'fnv_murmur_sip')
    fold(lambda i: hmac.new(pattern(i), pattern(300 - i), 'sha256').digest() +
         hmac.new(pattern(i), pattern(i), 'md5').digest(), 'hmac')
    for n in (63, 64, 65, 127, 128, 129, 191, 192, 193, 255, 256, 257, 1000, 4096, 4097, 100000):
        s = pattern(n)
        w(f"{n} {H('sha256', s).hex()} {H('sha512', s).hex()} {crc32(s)} {crc32c(s)}")
        w(f"{H('sha1', s).hex()} {H('md5', s).hex()} {H('sha3_256', s).hex()} {adler32(s)}")
    s = pattern(1000)
    ok1 = crc32(s) == crc32(s[300:], crc32(s[:300]))
    ok2 = crc32c(s) == crc32c(s[300:], crc32c(s[:300]))
    ok3 = adler32(s) == adler32(s[300:], adler32(s[:300]))
    w(f"{int(ok1)} {int(ok2)} {int(ok3)}")
    print('\n'.join(out))


if __name__ == '__main__':
    main()
