#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
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
"""Writes testdata/cipherkat.txt, the known answers of P428's unit pascipher,
from Go's own tests (Go 1.27's crypto/aes, crypto/cipher and crypto/hkdf,
golang.org/x/crypto v0.58.0's chacha20poly1305 and poly1305): each table is
copied into a Go program that prints it, so Go itself reads its literals.
The TLS 1.2 PRF answers come from RFC 5246 5's P_hash written with Python's
hmac. Go's GCM entries with a tag shorter than 16 bytes (NewGCMWithTagSize)
are left out: pascipher seals with TLS's 16-byte tag only. usage:

    python3 scripts/cipher_kat.py GOROOT XCRYPTO testdata/cipherkat.txt

GOROOT is Go's tree (/usr/lib/go), XCRYPTO golang.org/x/crypto@v0.58.0 in
Go's module cache.
"""
import hashlib
import hmac
import os
import re
import subprocess
import sys
import tempfile

goroot, xcrypto, out = sys.argv[1:4]


def block(src, name):
    """the text of 'var name = ...{...}' in src"""
    i = src.index('var ' + name)
    e = src.index('=', i)
    j = src.index('{', e)
    if 'struct' in src[e:j]:
        j = src.index('{', src.index('}', j) + 1)
    depth = 0
    k = j
    while True:
        c = src[k]
        if c == '"':
            k = src.index('"', k + 1)
        elif c == '`':
            k = src.index('`', k + 1)
        elif c == '/' and src[k + 1] == '/':
            k = src.index('\n', k)
            continue
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[i:k + 1]
        k += 1


def run(body):
    d = tempfile.mkdtemp()
    open(os.path.join(d, 'main.go'), 'w').write(body)
    open(os.path.join(d, 'go.mod'), 'w').write('module kat\n\ngo 1.24\n')
    r = subprocess.run(['go', 'run', '.'], cwd=d, capture_output=True, text=True,
                       env=dict(os.environ, GOFLAGS='-mod=mod', GOTOOLCHAIN='local'))
    if r.returncode:
        sys.exit(r.stderr)
    return r.stdout


lines = []
src = open(goroot + '/src/crypto/aes/aes_test.go').read()
lines += run('''package main
import ("encoding/hex"; "fmt")
type CryptTest struct { key, in, out []byte }
''' + block(src, 'encryptTests') + '''
func main() { for _, t := range encryptTests { fmt.Println("aes", hex.EncodeToString(t.key), hex.EncodeToString(t.in), hex.EncodeToString(t.out)) } }
''').splitlines()
src = open(goroot + '/src/crypto/cipher/gcm_test.go').read()
lines += run('''package main
import ("fmt")
''' + block(src, 'aesGCMTests') + '''
func h(s string) string { if s == "" { return "-" }; return s }
func main() { for _, t := range aesGCMTests { if len(t.result)-len(t.plaintext) == 32 { fmt.Println("gcm", t.key, h(t.nonce), h(t.plaintext), h(t.ad), t.result) } } }
''').splitlines()
src = open(xcrypto + '/chacha20poly1305/chacha20poly1305_vectors_test.go').read()
lines += run('''package main
import ("fmt")
''' + block(src, 'chacha20Poly1305Tests') + '''
func h(s string) string { if s == "" { return "-" }; return s }
func main() { for _, t := range chacha20Poly1305Tests { if len(t.nonce) == 24 { fmt.Println("ccp", t.key, t.nonce, h(t.plaintext), h(t.aad), t.out) } } }
''').splitlines()
src = open(xcrypto + '/internal/poly1305/vectors_test.go').read()
lines += run('''package main
import ("fmt")
type test struct { in, key, tag, state string }
''' + block(src, 'testData') + '''
func h(s string) string { if s == "" { return "-" }; return s }
func main() { for _, t := range testData { if t.state == "" { fmt.Println("poly", t.key, h(t.in), t.tag) } } }
''').splitlines()
src = open(goroot + '/src/crypto/hkdf/hkdf_test.go').read()
lines += run('''package main
import ("crypto/md5"; "crypto/sha1"; "crypto/sha256"; "crypto/sha512"; "encoding/hex"; "fmt"; "hash")
var _ = md5.New
var _ = sha1.New
var _ = sha512.New
type hkdfTest struct { hash func() hash.Hash; master, salt, prk, info, out []byte }
''' + block(src, 'hkdfTests') + '''
func h(b []byte) string { if len(b) == 0 { return "-" }; return hex.EncodeToString(b) }
func main() { for _, t := range hkdfTests { n := map[int]string{32: "0", 48: "1", 64: "2"}[t.hash().Size()]; if t.hash().Size() == 32 && t.hash().BlockSize() != 64 { n = "" }; if n != "" { fmt.Println("hkdf", n, h(t.salt), h(t.master), h(t.info), len(t.out), h(t.out)) } } }
''').splitlines()


def prf(hname, secret, label, seed, n):
    s = label + seed
    a = s
    o = b''
    while len(o) < n:
        a = hmac.new(secret, a, hname).digest()
        o += hmac.new(secret, a + s, hname).digest()
    return o[:n]


rng = hashlib.sha256(b'pascipher tls12 prf').digest()
for i, (hid, hname) in enumerate([(0, 'sha256'), (1, 'sha384'), (0, 'sha256'), (1, 'sha384')]):
    secret = hashlib.sha512(rng + bytes([i, 1])).digest()[:48]
    seed = hashlib.sha512(rng + bytes([i, 2])).digest()
    label = [b'master secret', b'key expansion', b'client finished', b'extended master secret'][i]
    n = [48, 104, 12, 48][i]
    lines.append('prf %d %s %s %s %d %s' % (hid, secret.hex(), label.hex(), seed.hex(), n,
                                           prf(hname, secret, label, seed, n).hex()))
open(out, 'w').write('\n'.join(lines) + '\n')
print(len(lines), 'answers')
