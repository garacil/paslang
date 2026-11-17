#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""A fault in RSA's private operation never leaves as a signature (P616).

  scripts/check_rsa_faults.py PASLANGC BUILDDIR QEMU_A64 [UNIT]

UNIT is another text of the unit to try instead of src/lib/pasrsa.paslang
(a mutant, to see that this check catches it).

Copies of src/lib/pasrsa.paslang with a fault written into the Chinese
remainder computation are compiled as the unit, for amd64 and arm64, and a
driver signs with each (scripts/fixtures/rsa_fault.paslang, the first key
of testdata/rsasign/cavp.txt):

- the unit as it is: signs, and the signature is the one worked out here
  with Python's pow;
- a bit flipped in the half modulo p, in the half modulo q, and the
  product by qInv left out: no signature at all, PKCS #1 v1.5 or PSS;
- the same fault in the half modulo p with the final comparison taken out:
  a signature leaves, it does not verify, and gcd(sig^e - em, n) is a prime
  factor of n. That is the attack the comparison stops (Boneh, DeMillo and
  Lipton), shown on this code and not assumed;
- the comparison taken out alone: the right signature, so the comparison
  changes nothing when there is no fault.

The key's making is kept from the faults: they are written after it.

The salt of a PSS signature comes from getrandom. In five more copies the
system call is replaced by a routine that answers as the kernel can: an
interrupted call twice and then the bytes, one byte a call, an error, zero
bytes, and more bytes than were asked. The first two must sign and verify,
as Go's sysrand goes on after EINTR and a short read; the other three must
give no signature.
"""
import hashlib
import math
from pathlib import Path
import subprocess
import sys
import tempfile

tree = Path(__file__).resolve().parents[1]
compiler = Path(sys.argv[1]).resolve()
build = Path(sys.argv[2]).resolve()
qemu = Path(sys.argv[3]).resolve()
root = Path(tempfile.mkdtemp(prefix='rsa-faults-', dir=build))
unit = Path(sys.argv[4]).resolve() if len(sys.argv) > 4 else tree / 'src/lib/pasrsa.paslang'
source = unit.read_text()

P_HALF = '  NatExp(m1, t0, Key.DP, Key.P);\n'
Q_HALF = '  NatExp(m2, t0, Key.DQ, Key.Q);\n'
QINV = '  NatMul(m1, Key.QInv, Key.P);\n'
CHECK = '  if NatEqual(check, cn) <> 1 then\n    Exit;\n'
for piece in (P_HALF, Q_HALF, QINV, CHECK):
    assert source.count(piece) == 1, piece

variants = {
    'production': source,
    'fault-p-half': source.replace(P_HALF, P_HALF + '  m1.Limbs[0] := m1.Limbs[0] xor 1;\n'),
    'fault-q-half': source.replace(Q_HALF, Q_HALF + '  m2.Limbs[0] := m2.Limbs[0] xor 1;\n'),
    'no-qinv': source.replace(QINV, ''),
    'fault-p-half-unchecked': source.replace(P_HALF, P_HALF + '  m1.Limbs[0] := m1.Limbs[0] xor 1;\n')
                                    .replace(CHECK, ''),
    'unchecked': source.replace(CHECK, ''),
}
RANDOM = 'Syscall(nr, Integer(@Result[used + 1]), N - used, 0)'
BEFORE = '\nfunction KernelRandom(N: Integer): string;\n'
assert source.count(RANDOM) == 1 and source.count(BEFORE) == 1
FAKES = {
    'entropy-interrupted': '''  if FakeCalls <= 2 then
    Exit(-4);
  FillChar(b^, Want, 165);
  Result := Want;''',
    'entropy-short': '''  { a byte a call, and the call must ask for what is left of 32 }
  if Want <> 32 - (FakeCalls - 1) then
    Exit(-5);
  b^ := 90;
  Result := 1;''',
    'entropy-error': '''  Result := -5;''',
    'entropy-zero': '''  Result := 0;''',
    'entropy-over': '''  { one byte, then one more than was asked }
  if FakeCalls = 1 then
  begin
    b^ := 90;
    Exit(1);
  end;
  FillChar(b^, Want, 165);
  Result := Want + 1;''',
}
for label, body in FAKES.items():
    fake = '''
var
  FakeCalls: Integer;

{ test view only: the kernel's answer to getrandom, chosen by the check }
function FakeRandom(P, Want: Integer): Integer;
var
  b: PByte;
begin
  Inc(FakeCalls);
  b := PByte(Pointer(P));
%s
end;
''' % body
    variants[label] = source.replace(BEFORE, fake + BEFORE) \
                            .replace(RANDOM, 'FakeRandom(Integer(@Result[used + 1]), N - used)')
assert len(set(variants.values())) == len(variants)

key = None
for line in (tree / 'testdata/rsasign/cavp.txt').read_text().splitlines():
    if line.startswith('key '):
        key = line.split()[2:7]
        break
n, e, d, p, q = (int(x, 16) for x in key)
assert p * q == n
digest = hashlib.sha256(b'a fault must not leave as a signature').digest()
size = (n.bit_length() + 7) // 8
t = bytes.fromhex('3031300d060960864801650304020105000420') + digest
em = int.from_bytes(b'\x00\x01' + b'\xff' * (size - len(t) - 3) + b'\x00' + t, 'big')
right = pow(em, d, n).to_bytes(size, 'big').hex()


def run(args, timeout=60, *, quiet=False):
    done = subprocess.run(list(map(str, args)), cwd=root, capture_output=True, timeout=timeout)
    assert done.returncode == 0, (args, done.stderr[-400:], done.stdout[-400:])
    assert done.stderr == b'', (args, done.stderr[-400:], done.stdout[-400:])
    if quiet:
        assert done.stdout == b'', (args, done.stdout[-400:])
    return done.stdout.decode()


for target in ('amd64', 'arm64'):
    flags = ['-cpu', 'base'] + (['-target', 'arm64'] if target == 'arm64' else [])
    core = build / ('a64' if target == 'arm64' else '')
    launch = [qemu, '-cpu', 'max'] if target == 'arm64' else []
    for label, text in variants.items():
        directory = root / (label + '-' + target)
        directory.mkdir()
        (directory / 'pasrsa.paslang').write_text(text)
        run([compiler, *flags, '-c', '-Fu', core, '-o', directory / 'pasrsa', directory / 'pasrsa.paslang'], quiet=True)
        binary = directory / 'rsafault'
        run([compiler, *flags, '-Fu', directory, '-Fu', core, '-o', binary,
             tree / 'scripts/fixtures/rsa_fault.paslang'], quiet=True)
        out = dict(line.split(' ', 1) for line in run([*launch, binary, *key]).splitlines())
        assert out['made'] == 'True ', (label, target, out)
        sig = out['sig'].strip()
        if label in ('production', 'unchecked', 'entropy-interrupted', 'entropy-short'):
            assert out['signed'] == 'True' and sig == right and out['verifies'] == 'True', (label, target, out)
            assert out['pss'] == 'True %d' % size, (label, target, out)
            assert out['rnd'] == 'True %d True' % size, (label, target, out)
        elif label.startswith('entropy-'):
            # the kernel gave no salt: the other two signatures need none
            assert out['signed'] == 'True' and sig == right and out['pss'] == 'True %d' % size, (label, target, out)
            assert out['rnd'] == 'False 0 False', (label, target, out)
        elif label == 'fault-p-half-unchecked':
            assert out['signed'] == 'True' and sig != right and out['verifies'] == 'False', (label, target, out)
            factor = math.gcd(pow(int(sig, 16), e, n) - em, n)
            assert factor in (p, q), (label, target, 'the faulted signature does not give a factor')
        else:
            assert out['signed'] == 'False' and sig == '' and out['verifies'] == 'False', (label, target, out)
            assert out['pss'] == 'False 0' and out['rnd'] == 'False 0 False', (label, target, out)
        print(label, target, 'as expected', flush=True)
assert hashlib.sha256(unit.read_bytes()).hexdigest() == hashlib.sha256(source.encode()).hexdigest()
print('ok rsa faults: %d variants on two machines' % len(variants))
