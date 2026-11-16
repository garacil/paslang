#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""The data of testdata/rsasign.paslang (P616): keys, signatures, bad keys.

  scripts/rsasign_vectors.py --check   every vector of testdata/rsasign
                                        worked out again from its key
  scripts/rsasign_vectors.py --write   new keys and vectors (needs the
                                        Python package cryptography)
  scripts/rsasign_vectors.py --cavp D  cavp.txt from NIST's SigGen15_186-3.txt
                                        and SigGenPSS_186-3.txt in directory D

The oracle is this file's own arithmetic: EMSA-PKCS1-v1_5 and EMSA-PSS
(RFC 8017 9.2 and 9.1.1) built with hashlib and raised to d with pow().
--write also asks OpenSSL, through cryptography, for every PKCS #1 v1.5
signature and to verify every PSS one, and stops when they disagree.

Files, all under testdata/rsasign:
  k2048.pem k3072.pem k4096.pem   PKCS #8 test keys (never to be used);
  k2049.pem k2050.pem             two more whose moduli are not whole octets
  k2048.pkcs1.pem                 the first one again as PKCS #1
  vectors.txt                     v15 KEY HASH MSGHEX SIGHEX
                                  pss KEY HASH SALTHEX MSGHEX SIGHEX
  keys.txt                        NAME FILE ok|own|bad WORDS: a key file and
                                  whether it loads: ok is the first key in
                                  another form (it signs as the first does),
                                  own another key (its signature verifies
                                  with its own public half), bad a key that
                                  is refused with these words
  good-*, bad-*                   those key files
  cavp.txt                        NIST CAVP's signature generation vectors
                                  (186-3rsatestvectors.zip, FIPS 186-4): key
                                  NAME N E D P Q, then v15 and pss lines as
                                  above. NIST gives n, e and d; p and q are
                                  worked out from them here.
"""
import base64
import hashlib
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / 'testdata' / 'rsasign'
HASHES = {'SHA-224': ('sha224', '302d300d06096086480165030402040500041c'),
          'SHA-256': ('sha256', '3031300d060960864801650304020105000420'),
          'SHA-384': ('sha384', '3041300d060960864801650304020205000430'),
          'SHA-512': ('sha512', '3051300d060960864801650304020305000440')}
WRITTEN = ('SHA-256', 'SHA-384', 'SHA-512')
OID_RSA = bytes.fromhex('2a864886f70d010101')
OID_EC = bytes.fromhex('2a8648ce3d0201')


# ---- DER, as much as a key file needs ----

def der_len(n):
    if n < 128:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, 'big')
    return bytes([0x80 | len(b)]) + b


def tlv(tag, body):
    return bytes([tag]) + der_len(len(body)) + body


def der_int(v):
    n = max(1, (v.bit_length() + 8) // 8) if v >= 0 else (((-v - 1).bit_length() + 8) // 8)
    return tlv(2, v.to_bytes(n, 'big', signed=True))


def der_seq(*parts):
    return tlv(0x30, b''.join(parts))


def read_tlv(b, at):
    tag = b[at]
    n = b[at + 1]
    at += 2
    if n & 0x80:
        k = n & 0x7f
        n = int.from_bytes(b[at:at + k], 'big')
        at += k
    return tag, b[at:at + n], at + n


def read_ints(body):
    out, at = [], 0
    while at < len(body):
        tag, v, at = read_tlv(body, at)
        assert tag == 2
        out.append(int.from_bytes(v, 'big', signed=True))
    return out


def pem(kind, der, headers=''):
    b = base64.b64encode(der).decode()
    lines = [b[i:i + 64] for i in range(0, len(b), 64)]
    return ('-----BEGIN %s-----\n%s%s\n-----END %s-----\n' % (kind, headers, '\n'.join(lines), kind)).encode()


def unpem(text):
    lines = [l for l in text.decode().splitlines() if l and not l.startswith('-----') and ':' not in l]
    return base64.b64decode(''.join(lines))


class Key:
    """n, e, d, p, q, dp, dq, qi of a two-prime key."""

    def __init__(self, n, e, d, p, q, dp=None, dq=None, qi=None):
        self.n, self.e, self.d, self.p, self.q = n, e, d, p, q
        self.dp = d % (p - 1) if dp is None else dp
        self.dq = d % (q - 1) if dq is None else dq
        self.qi = pow(q, -1, p) if qi is None else qi

    @classmethod
    def from_pkcs8(cls, der):
        tag, body, _ = read_tlv(der, 0)
        _, _, at = read_tlv(body, 0)
        _, _, at = read_tlv(body, at)
        _, inner, _ = read_tlv(body, at)
        return cls.from_pkcs1(inner)

    @classmethod
    def from_pkcs1(cls, der):
        _, body, _ = read_tlv(der, 0)
        v = read_ints(body)
        return cls(*v[1:9])

    def ints(self):
        return [0, self.n, self.e, self.d, self.p, self.q, self.dp, self.dq, self.qi]

    def pkcs1(self, ints=None):
        return der_seq(*[der_int(x) for x in (self.ints() if ints is None else ints)])

    def pkcs8(self, inner=None, version=0, alg=None, extra=b''):
        if alg is None:
            alg = der_seq(tlv(6, OID_RSA), tlv(5, b''))
        return der_seq(der_int(version), alg, tlv(4, self.pkcs1() if inner is None else inner), extra)

    @property
    def size(self):
        return (self.n.bit_length() + 7) // 8


# ---- the oracle: RFC 8017 with hashlib and pow ----

def sign_v15(k, hname, msg):
    h, prefix = HASHES[hname]
    t = bytes.fromhex(prefix) + hashlib.new(h, msg).digest()
    em = b'\x00\x01' + b'\xff' * (k.size - len(t) - 3) + b'\x00' + t
    return pow(int.from_bytes(em, 'big'), k.d, k.n).to_bytes(k.size, 'big')


def mgf1(h, seed, n):
    out, c = b'', 0
    while len(out) < n:
        out += hashlib.new(h, seed + c.to_bytes(4, 'big')).digest()
        c += 1
    return out[:n]


def sign_pss(k, hname, msg, salt):
    h = HASHES[hname][0]
    mhash = hashlib.new(h, msg).digest()
    hlen = len(mhash)
    embits = k.n.bit_length() - 1
    emlen = (embits + 7) // 8
    assert emlen >= hlen + len(salt) + 2
    hh = hashlib.new(h, b'\x00' * 8 + mhash + salt).digest()
    db = b'\x00' * (emlen - len(salt) - hlen - 2) + b'\x01' + salt
    masked = bytearray(a ^ b for a, b in zip(db, mgf1(h, hh, len(db))))
    masked[0] &= 0xff >> (8 * emlen - embits)
    em = bytes(masked) + hh + b'\xbc'
    return pow(int.from_bytes(em, 'big'), k.d, k.n).to_bytes(k.size, 'big')


def load_keys():
    keys = {}
    for name in ('k2048', 'k3072', 'k4096', 'k2049', 'k2050'):
        keys[name] = Key.from_pkcs8(unpem((HERE / (name + '.pem')).read_bytes()))
    return keys


def check():
    keys = load_keys()
    for name, k in keys.items():
        assert k.p * k.q == k.n and (k.e * k.dp) % (k.p - 1) == 1 and (k.qi * k.q) % k.p == 1, name
    assert Key.from_pkcs1(unpem((HERE / 'k2048.pkcs1.pem').read_bytes())).ints() == keys['k2048'].ints()
    n = 0
    for line in (HERE / 'vectors.txt').read_text().splitlines():
        f = line.split()
        if not f or f[0].startswith('#'):
            continue
        if f[0] == 'v15':
            want = sign_v15(keys[f[1]], f[2], bytes.fromhex(f[3] if f[3] != '-' else ''))
            assert want.hex() == f[4], line[:60]
        elif f[0] == 'pss':
            salt = bytes.fromhex(f[3] if f[3] != '-' else '')
            want = sign_pss(keys[f[1]], f[2], bytes.fromhex(f[4] if f[4] != '-' else ''), salt)
            assert want.hex() == f[5], line[:60]
        else:
            raise SystemExit('unknown line ' + line[:40])
        n += 1
    cavp = 0
    for line in (HERE / 'cavp.txt').read_text().splitlines():
        f = line.split()
        if not f or f[0].startswith('#'):
            continue
        if f[0] == 'key':
            v = [int(x, 16) for x in f[2:7]]
            assert v[3] * v[4] == v[0] and is_prime(v[3]) and is_prime(v[4]), f[1]
            keys[f[1]] = Key(*v)
        elif f[0] == 'v15':
            assert sign_v15(keys[f[1]], f[2], bytes.fromhex(f[3])).hex() == f[4], line[:60]
            cavp += 1
        else:
            assert sign_pss(keys[f[1]], f[2], bytes.fromhex(f[4]), bytes.fromhex(f[3])).hex() == f[5], line[:60]
            cavp += 1
    listed = 0
    for line in (HERE / 'keys.txt').read_text().splitlines():
        f = line.split(None, 3)
        if not f or f[0].startswith('#'):
            continue
        assert (HERE / f[1]).exists(), f[1]
        assert f[2] in ('ok', 'own', 'bad')
        listed += 1
    print('rsasign vectors: %d signatures and %d of NIST agree with their keys, %d key files listed'
          % (n, cavp, listed))


# ---- --write ----

def is_prime(n, rounds=40):
    if n < 4:
        return n in (2, 3)
    if n % 2 == 0:
        return False
    for sp in (3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % sp == 0:
            return n == sp
    d, s = n - 1, 0
    while d % 2 == 0:
        d, s = d // 2, s + 1
    rng = random.Random(n & 0xffffffff)
    for _ in range(rounds):
        x = pow(rng.randrange(2, n - 1), d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def next_prime(n, e):
    n |= 1
    while not (is_prime(n) and (n - 1) % e != 0):
        n += 2
    return n


def write():
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    HERE.mkdir(parents=True, exist_ok=True)
    ch = {'SHA-256': hashes.SHA256(), 'SHA-384': hashes.SHA384(), 'SHA-512': hashes.SHA512()}
    keys, ckeys = {}, {}
    rng = random.Random(616)
    for bits in (2048, 3072, 4096, 2049, 2050):
        name = 'k%d' % bits
        path = HERE / (name + '.pem')
        if path.exists():
            der = unpem(path.read_bytes())
        elif bits % 8 == 0:
            ck = rsa.generate_private_key(public_exponent=65537, key_size=bits)
            der = ck.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                   serialization.NoEncryption())
        else:
            # a modulus whose bit length is not a multiple of 8: EMSA-PSS's
            # encoded message is then shorter than the modulus or masks
            # other bits of its first octet (RFC 8017 9.1.1 and 8.1.1)
            while True:
                pp = next_prime(rng.getrandbits(bits - bits // 2) | (3 << (bits - bits // 2 - 2)), 65537)
                qq = next_prime(rng.getrandbits(bits // 2) | (1 << (bits // 2 - 1)), 65537)
                if (pp * qq).bit_length() == bits:
                    break
            lam0 = (pp - 1) * (qq - 1) // math.gcd(pp - 1, qq - 1)
            der = Key(pp * qq, 65537, pow(65537, -1, lam0), pp, qq).pkcs8()
        path.write_bytes(pem('PRIVATE KEY', der))
        keys[name] = Key.from_pkcs8(der)
        ckeys[name] = serialization.load_der_private_key(der, None)
    k = keys['k2048']
    (HERE / 'k2048.pkcs1.pem').write_bytes(pem('RSA PRIVATE KEY', k.pkcs1()))

    rng = random.Random(616)
    msgs = [b'', b'a', b'paslang signs with RSA', bytes(rng.randrange(256) for _ in range(257))]
    out = ['# P616. v15 KEY HASH MSG SIG: RSASSA-PKCS1-v1_5, equal to OpenSSL 3 byte for byte.',
           '# pss KEY HASH SALT MSG SIG: RSASSA-PSS with MGF1 on the same hash and the salt given;',
           '# every signature also verifies in OpenSSL. - is the empty string.']
    for name, key in keys.items():
        for hname in WRITTEN:
            if name in ('k2049', 'k2050') and hname != 'SHA-256':
                continue
            for m in msgs:
                sig = sign_v15(key, hname, m)
                assert ckeys[name].sign(m, padding.PKCS1v15(), ch[hname]) == sig
                out.append('v15 %s %s %s %s' % (name, hname, m.hex() or '-', sig.hex()))
            hlen = hashlib.new(HASHES[hname][0]).digest_size
            longest = (key.n.bit_length() - 1 + 7) // 8 - 2 - hlen
            for slen in (0, 1, hlen, longest):
                salt = bytes(rng.randrange(256) for _ in range(slen))
                m = msgs[2]
                sig = sign_pss(key, hname, m, salt)
                ckeys[name].public_key().verify(
                    sig, m, padding.PSS(mgf=padding.MGF1(ch[hname]), salt_length=slen), ch[hname])
                out.append('pss %s %s %s %s %s' % (name, hname, salt.hex() or '-', m.hex(), sig.hex()))
    (HERE / 'vectors.txt').write_text('\n'.join(out) + '\n')

    # key files: the ones that load, then each defect with the words of its refusal
    rows = ['# P616. NAME FILE ok|own|bad WORDS: a key file; ok signs as the first key, own is another',
            '# key whose signature its own public half verifies, bad is refused with these words.']

    def put(name, fname, data, verdict, words=''):
        (HERE / fname).write_bytes(data)
        rows.append(('%s %s %s %s' % (name, fname, verdict, words)).rstrip())

    lam = (k.p - 1) * (k.q - 1) // __import__('math').gcd(k.p - 1, k.q - 1)
    sw = Key(k.n, k.e, k.d, k.q, k.p)
    put('pkcs8', 'k2048.pem', (HERE / 'k2048.pem').read_bytes(), 'ok')
    put('pkcs1', 'k2048.pkcs1.pem', (HERE / 'k2048.pkcs1.pem').read_bytes(), 'ok')
    put('pkcs8-der', 'good-pkcs8.der', k.pkcs8(), 'ok')
    put('pkcs1-der', 'good-pkcs1.der', k.pkcs1(), 'ok')
    put('no-crt-values', 'good-nocrt.der', k.pkcs1(k.ints()[:6]), 'ok')
    put('primes-swapped', 'good-swapped.der', sw.pkcs1(), 'ok')
    put('d-plus-lambda', 'good-dlambda.der', Key(k.n, k.e, k.d + lam, k.p, k.q, k.dp, k.dq, k.qi).pkcs1(), 'ok')
    put('pkcs8-no-params', 'good-noparams.der', k.pkcs8(alg=der_seq(tlv(6, OID_RSA))), 'ok')
    put('pkcs8-v2-public', 'good-v2.der', k.pkcs8(version=1, extra=tlv(0x81, b'\x00\x01')), 'ok')
    put('cert-then-key', 'good-after-cert.pem',
        pem('CERTIFICATE', b'\x30\x00') + (HERE / 'k2048.pem').read_bytes(), 'ok')

    i = k.ints()

    def swap(pos, val):
        j = list(i)
        j[pos] = val
        return k.pkcs1(j)

    put('n-plus-2', 'bad-n.der', swap(1, k.n + 2), 'bad', 'p * q != n')
    put('e-other', 'bad-e.der', swap(2, 65539), 'bad', 'invalid CRT exponent')
    put('e-even', 'bad-eeven.der', swap(2, 65536), 'bad', 'public exponent is even')
    put('e-one', 'bad-eone.der', swap(2, 1), 'bad', 'public exponent too small')
    put('e-large', 'bad-elarge.der', swap(2, 2 ** 31 + 1), 'bad', 'public exponent too large')
    put('e-negative', 'bad-eneg.der', swap(2, -65537), 'bad', 'public exponent too small')
    put('d-plus-2', 'bad-d.der', swap(3, k.d + 2), 'bad', 'd does not match dP')
    put('d-above-n', 'bad-dbig.der', swap(3, k.n + 1), 'bad', 'invalid private exponent')
    put('p-even', 'bad-peven.der', swap(4, k.p + 1), 'bad', 'invalid prime')
    put('p-one', 'bad-pone.der', swap(4, 1), 'bad', 'invalid prime')
    put('q-other', 'bad-q.der', swap(5, k.q + 2), 'bad', 'p * q != n')
    put('dp-plus-1', 'bad-dp.der', swap(6, k.dp + 1), 'bad', 'invalid CRT exponent')
    put('dp-above-p', 'bad-dpbig.der', swap(6, k.dp + k.p - 1), 'bad', 'invalid CRT exponent')
    put('dq-plus-2', 'bad-dq.der', swap(7, k.dq + 2), 'bad', 'invalid CRT exponent')
    put('qinv-plus-1', 'bad-qi.der', swap(8, k.qi + 1), 'bad', 'invalid CRT coefficient')
    put('qinv-above-p', 'bad-qibig.der', swap(8, k.qi + k.p), 'bad', 'invalid CRT coefficient')
    put('primes-swapped-only', 'bad-swaponly.der', k.pkcs1([0, k.n, k.e, k.d, k.q, k.p, k.dp, k.dq, k.qi]),
        'bad', 'invalid CRT exponent')
    put('d-zero', 'bad-dzero.der', swap(3, 0), 'bad', 'zero or negative')
    put('d-negative', 'bad-dneg.der', swap(3, -k.d), 'bad', 'zero or negative')
    put('n-negative', 'bad-nneg.der', swap(1, -k.n), 'bad', 'zero or negative')
    put('qinv-zero', 'bad-qizero.der', swap(8, 0), 'bad', 'zero or negative')
    # p = q: n is a square
    sq = Key(k.p * k.p, k.e, pow(k.e, -1, k.p * (k.p - 1)), k.p, k.p, qi=1)
    put('p-equals-q', 'bad-square.der', sq.pkcs1(), 'bad', 'invalid CRT coefficient')
    # primes next to each other: Fermat's method factors n at once
    q2 = next_prime(k.p + 2, k.e)
    n2 = k.p * q2
    lam2 = (k.p - 1) * (q2 - 1) // __import__('math').gcd(k.p - 1, q2 - 1)
    close = Key(n2, k.e, pow(k.e, -1, lam2), k.p, q2)
    put('primes-close', 'bad-close.der', close.pkcs1(), 'bad', '|p - q| too small')
    # a modulus under 1024 bits
    ps = next_prime(rng.getrandbits(511) | (1 << 510), k.e)
    qs = next_prime(rng.getrandbits(512) | (1 << 511), k.e)
    lams = (ps - 1) * (qs - 1) // __import__('math').gcd(ps - 1, qs - 1)
    small = Key(ps * qs, k.e, pow(k.e, -1, lams), ps, qs)
    assert small.n.bit_length() < 1024
    put('modulus-short', 'bad-short.der', small.pkcs1(), 'bad', '%d-bit keys are insecure' % small.n.bit_length())

    # --- boundaries ---
    E = k.e
    # the largest exponent taken, 2^31 - 1 (a prime), and 2, even before it is small
    big_e = 2 ** 31 - 1
    assert math.gcd(big_e, (k.p - 1) * (k.q - 1)) == 1
    put('e-largest', 'good-emax.der', Key(k.n, big_e, pow(big_e, -1, lam), k.p, k.q).pkcs1(), 'own')
    put('e-two', 'bad-etwo.der', swap(2, 2), 'bad', 'public exponent is even')
    # a prime of one limb, either way round: the product's rows and the short modulus
    p1 = next_prime(rng.getrandbits(61) | (1 << 60), E)
    q1 = next_prime(rng.getrandbits(1987) | (3 << 1985), E)
    assert (p1 * q1).bit_length() == 2048
    lam1 = (p1 - 1) * (q1 - 1) // math.gcd(p1 - 1, q1 - 1)
    put('prime-one-limb', 'good-limb.der', Key(p1 * q1, E, pow(E, -1, lam1), p1, q1).pkcs1(), 'own')
    put('prime-one-limb-second', 'good-limb2.der', Key(p1 * q1, E, pow(E, -1, lam1), q1, p1).pkcs1(), 'own')
    # n with a third prime: longer than p * q can be
    r3 = next_prime(rng.getrandbits(127) | (1 << 126), E)
    put('modulus-third-prime', 'bad-nthree.der', swap(1, k.n * r3), 'bad', 'p * q != n')
    # n that differs from p * q in its last limb alone
    put('modulus-top-limb', 'bad-ntop.der', swap(1, k.n ^ (1 << (64 * 31))), 'bad', 'p * q != n')
    # p * q of 33 limbs and n its low 32: the limbs above n's must be looked at
    p2 = next_prime(rng.getrandbits(65) | (3 << 63), E)
    q2 = next_prime(rng.getrandbits(1984) | (3 << 1982), E)
    full = p2 * q2
    assert full.bit_length() > 2048
    n2 = full % (1 << 2048)
    assert n2 % 2 == 1 and n2.bit_length() > 1984
    lam2b = (p2 - 1) * (q2 - 1) // math.gcd(p2 - 1, q2 - 1)
    d2 = pow(E, -1, lam2b)
    put('modulus-low-limbs', 'bad-nlow.der',
        der_seq(*[der_int(x) for x in (0, n2, E, d2 % n2, p2, q2, d2 % (p2 - 1), d2 % (q2 - 1), pow(q2, -1, p2))]),
        'bad', 'p * q != n')
    # |p - q| just at and just past 2^(nlen/2 - 100)
    for nm, fn, verdict, words in (('primes-gap-at-limit', 'bad-gap.der', 'bad', '|p - q| too small'),
                                   ('primes-gap-past-limit', 'good-gap.der', 'own', '')):
        nbits = (k.p * k.p).bit_length()
        t = nbits // 2 - 100
        qg = next_prime(k.p + (1 << (t - 1 if verdict == 'bad' else t)), E)
        ng = k.p * qg
        assert ng.bit_length() == nbits and (qg - k.p).bit_length() == (t if verdict == 'bad' else t + 1)
        lamg = (k.p - 1) * (qg - 1) // math.gcd(k.p - 1, qg - 1)
        put(nm, fn, Key(ng, E, pow(E, -1, lamg), k.p, qg).pkcs1(), verdict, words)
    # d just at and just past 2^(nlen/2): p - 1 = 3 (q - 1), so that the
    # least common multiple of p - 1 and q - 1 is p - 1 and d is below it
    found = {}
    x = rng.getrandbits(1023) | (1 << 1022) | 1
    small = [3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97]
    while len(found) < 2:
        x += 2
        y = 3 * x - 2
        if any(x % sp == 0 or y % sp == 0 for sp in small):
            continue
        if not (is_prime(x, 2) and is_prime(y, 2) and is_prime(x) and is_prime(y)):
            continue
        lamd = y - 1
        if math.gcd(E, lamd) != 1:
            continue
        dd = pow(E, -1, lamd)
        nd = x * y
        which = 'at' if dd.bit_length() == nd.bit_length() // 2 else \
            'past' if dd.bit_length() == nd.bit_length() // 2 + 1 else None
        if which and which not in found:
            found[which] = Key(nd, E, dd, y, x)
    put('d-at-limit', 'bad-dsmall.der', found['at'].pkcs1(), 'bad', 'd too small')
    put('d-past-limit', 'good-dedge.der', found['past'].pkcs1(), 'own')

    # more refusals, each for its own reason
    put('n-one', 'bad-none.der', swap(1, 1), 'bad', 'invalid modulus')
    put('n-even', 'bad-neven.der', swap(1, k.n + 1), 'bad', 'public modulus is even')
    put('d-plus-p-less-1', 'bad-ddq.der', swap(3, k.d + k.p - 1), 'bad', 'd does not match dQ')
    put('no-crt-n-plus-2', 'bad-nocrtn.der', k.pkcs1([0, k.n + 2, k.e, k.d, k.p, k.q]), 'bad', 'p * q != n')
    put('no-crt-p-even', 'bad-nocrtp.der', k.pkcs1([0, k.n, k.e, k.d, k.p + 1, k.q]), 'bad', 'invalid prime')
    # a key whose d mod (p - 1) has a zero first octet: the exponent is kept at its full size
    while True:
        cand = rsa.generate_private_key(public_exponent=65537, key_size=1024).private_numbers()
        if cand.dmp1.bit_length() <= cand.p.bit_length() - 8:
            break
    put('dp-short', 'good-dpshort.der',
        Key(cand.public_numbers.n, 65537, cand.d, cand.p, cand.q, cand.dmp1, cand.dmq1, cand.iqmp).pkcs1(), 'own')
    while True:
        cand = rsa.generate_private_key(public_exponent=65537, key_size=1024).private_numbers()
        if cand.dmq1.bit_length() <= cand.q.bit_length() - 8:
            break
    put('dq-short', 'good-dqshort.der',
        Key(cand.public_numbers.n, 65537, cand.d, cand.p, cand.q, cand.dmp1, cand.dmq1, cand.iqmp).pkcs1(), 'own')

    good = k.pkcs1()
    put('trailing-after', 'bad-trail.der', good + b'\x00', 'bad', 'trailing data after RSA private key')
    put('trailing-inside', 'bad-trailin.der', k.pkcs1(i + [7]), 'bad', 'trailing data in RSA private key')
    put('two-crt-values', 'bad-partial.der', k.pkcs1(i[:8]), 'bad', 'failed to parse RSA private key')
    put('version-1', 'bad-v1.der', swap(0, 1), 'bad', 'more than two primes')
    put('version-2', 'bad-v2.der', swap(0, 2), 'bad', 'unsupported private key version')
    put('truncated', 'bad-cut.der', good[:-5], 'bad', 'failed to parse RSA private key')
    put('empty', 'bad-empty.der', b'', 'bad', 'failed to parse')
    padded = der_seq(der_int(0), tlv(2, b'\x00' + k.n.to_bytes(k.size + 1, 'big')),
                     *[der_int(x) for x in i[2:]])
    put('integer-not-minimal', 'bad-minimal.der', padded, 'bad', 'failed to parse RSA private key')
    put('pkcs8-ec-oid', 'bad-p8ec.der', k.pkcs8(alg=der_seq(tlv(6, OID_EC), tlv(5, b''))), 'bad',
        'is not an RSA key')
    put('pkcs8-params', 'bad-p8params.der', k.pkcs8(alg=der_seq(tlv(6, OID_RSA), tlv(6, OID_EC))), 'bad',
        'invalid RSA private key parameters')
    put('pkcs8-version-2', 'bad-p8v.der', k.pkcs8(version=2), 'bad', 'unsupported PKCS #8 version')
    put('pkcs8-trailing', 'bad-p8trail.der', k.pkcs8() + b'\x05\x00', 'bad', 'trailing data after PKCS #8')
    put('pkcs8-extra-field', 'bad-p8extra.der', k.pkcs8(extra=der_int(1)), 'bad', 'trailing data in PKCS #8')
    put('pkcs8-bad-inner', 'bad-p8inner.der', k.pkcs8(inner=swap(8, k.qi + 1)), 'bad',
        'embedded in PKCS#8: crypto/rsa: invalid CRT coefficient')
    put('pem-encrypted-headers', 'bad-enc.pem',
        pem('RSA PRIVATE KEY', good, 'Proc-Type: 4,ENCRYPTED\nDEK-Info: AES-128-CBC,00\n\n'), 'bad',
        'encrypted private keys are not read')
    put('pem-encrypted-pkcs8', 'bad-enc8.pem', pem('ENCRYPTED PRIVATE KEY', k.pkcs8()), 'bad',
        'encrypted private keys are not read')
    put('pem-ec-key', 'bad-ec.pem', pem('EC PRIVATE KEY', b'\x30\x00'), 'bad', 'is not an RSA private key')
    put('pem-no-key', 'bad-nokey.pem', pem('CERTIFICATE', b'\x30\x00'), 'bad', 'no private key PEM block')
    put('pem-wrong-form', 'bad-form.pem', pem('PRIVATE KEY', good), 'bad', 'failed to parse PKCS #8')
    (HERE / 'keys.txt').write_text('\n'.join(rows) + '\n')
    check()


def factor(n, e, d):
    """p and q of n from a pair of exponents: a square root of 1 that is
    not 1 or n - 1 shares a factor with n (the proof of RSA's own paper)."""
    k = d * e - 1
    r, t = k, 0
    while r % 2 == 0:
        r, t = r // 2, t + 1
    rng = random.Random(n & 0xffffffff)
    while True:
        x = pow(rng.randrange(2, n - 1), r, n)
        for _ in range(t):
            y = x * x % n
            if y == 1 and x not in (1, n - 1):
                p = __import__('math').gcd(x - 1, n)
                return max(p, n // p), min(p, n // p)
            x = y


def cavp(directory):
    out = ['# P616. NIST CAVP, 186-3rsatestvectors.zip (SHA-256 8405aeb3572a4f98ed4b1a3ccb3f2f49',
           '# e725462dd28ec4759d6a15d88855d19c): SigGen15_186-3.txt and SigGenPSS_186-3.txt.',
           '# key NAME N E D P Q; v15 KEY HASH MSG SIG; pss KEY HASH SALT MSG SIG.']
    for fname, kind in (('SigGen15_186-3.txt', 'v15'), ('SigGenPSS_186-3.txt', 'pss')):
        cur, name, count = {}, None, 0
        for line in (Path(directory) / fname).read_text().splitlines():
            f = [x.strip() for x in line.split('=', 1)]
            if len(f) != 2 or line.startswith('#'):
                continue
            if f[0] == '[mod':
                continue
            cur[f[0]] = f[1]
            if f[0] == 'd':
                n, e, d = int(cur['n'], 16), int(cur['e'], 16), int(cur['d'], 16)
                p, q = factor(n, e, d)
                name = 'c%d%s' % (n.bit_length(), kind)
                out.append('key %s %x %x %x %x %x' % (name, n, e, d, p, q))
            last = 'S' if kind == 'v15' else 'SaltVal'
            if f[0] == last:
                h = cur['SHAAlg'].replace('SHA', 'SHA-')
                if kind == 'v15':
                    out.append('v15 %s %s %s %s' % (name, h, cur['Msg'], cur['S']))
                else:
                    out.append('pss %s %s %s %s %s' % (name, h, cur['SaltVal'], cur['Msg'], cur['S']))
                count += 1
        assert count == 80, (fname, count)
    (HERE / 'cavp.txt').write_text('\n'.join(out) + '\n')
    check()


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--cavp':
        cavp(sys.argv[2])
    elif sys.argv[1:] == ['--write']:
        write()
    elif sys.argv[1:] == ['--check']:
        check()
    else:
        raise SystemExit(__doc__)
