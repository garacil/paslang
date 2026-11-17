#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P615: real RFC6979 retry state, independent HMAC/group oracle and mutant.

Only the first nonce result is forced; subsequent HMAC results remain real.
The scalar, signing and key-generation algorithms retain their production
bodies apart from counters and first-attempt primitive fault injection.
Python affine arithmetic follows SEC1v2 section2.2.1, with the domain
parameters of Standards for Efficient Cryptography2 (SEC2), sections2.4.2
and2.5.1. No Go executable or additional Python package is required.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo / 'scripts/bench'))
import metadata_scope as scope

compiler, build, qemu = (Path(x).resolve() for x in sys.argv[1:])
source_path = repo / 'src/lib/pasnist.paslang'
fixture = repo / 'testdata/nistretry.paslang'
root = Path(tempfile.mkdtemp(prefix='nist-retry-', dir=build))
env = {k: v for k, v in os.environ.items()
       if k not in scope.CONTROL_KEYS and not k.startswith('PASLANG_')}
env.update(LC_ALL='C', LANG='C', PYTHONDONTWRITEBYTECODE='1')


def identity(path):
    st = path.stat()
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'bytes': st.st_size, 'mode': st.st_mode & 0o7777, 'mtime_ns': st.st_mtime_ns}


inputs = [compiler, qemu, source_path, fixture, Path(__file__).resolve(),
          Path(scope.__file__).resolve(), Path(sys.executable).resolve()]
for directory in (build, build / 'a64'):
    inputs.extend(p for p in directory.iterdir() if p.is_file() and p.suffix in ('.o', '.pi'))
for name in ('as', 'ld', 'aarch64-linux-gnu-as', 'aarch64-linux-gnu-ld'):
    resolved = shutil.which(name, path=env['PATH'])
    if resolved is None:
        raise RuntimeError('required assembler/linker unavailable: ' + name)
    inputs.append(Path(resolved).resolve())
frozen = {str(p): identity(p) for p in inputs}
state = {'ok': False, 'complete': False, 'milestone': 'P615', 'inputs': frozen,
         'commands': [], 'variants': [], 'mutants': [], 'errors': [], 'evidence': str(root)}


def save():
    scope.save(root / 'status.json', state)


def guard():
    for name, wanted in frozen.items():
        if identity(Path(name)) != wanted:
            raise RuntimeError('input changed during retry test: ' + name)


def run(label, arguments):
    guard()
    folder = root / label
    args = [str(x) for x in arguments]
    row = {'label': label, 'argv': args, 'cwd': str(root), 'timeout_s': 240,
           'scope': str(folder)}
    state['commands'].append(row)
    save()
    result = scope.invoke(args, folder, root, env, 240)
    scope.validate_receipt(folder, args, root, env, require_success=True)
    row.update(status=result['status'], elapsed_s=result['elapsed_s'],
               cleanup=result['cleanup'], stdout=result['stdout'], stderr=result['stderr'])
    save()
    if (result['status'] != 0 or not result['cleanup']['ok'] or result['reason'] is not None
            or result['signals'] or result['received_signals'] or result['leftovers_before_cleanup']):
        raise RuntimeError('unsuccessful retry-test process scope: ' + label)
    if (folder / 'stderr').read_bytes():
        raise RuntimeError('unexpected retry-test diagnostics: ' + label)
    if label.endswith(('-unit', '-compile')) and (folder / 'stdout').read_bytes():
        raise RuntimeError('unexpected retry-test build output: ' + label)
    guard()
    return (folder / 'stdout').read_bytes()


# SEC2v2 domain parameters; affine Python is independent of Montgomery/window
# arithmetic in pasnist. Test inputs are public and need no constant-time math.
CURVES = (
    (32,
     int('FFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF', 16),
     int('5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B', 16),
     int('FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551', 16),
     (int('6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296', 16),
      int('4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5', 16)),
     hashlib.sha256),
    (48,
     int('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFFFF0000000000000000FFFFFFFF', 16),
     int('B3312FA7E23EE7E4988E056BE3F82D19181D9C6EFE8141120314088F5013875AC656398D8A2ED19D2A85C8EDD3EC2AEF', 16),
     int('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFC7634D81F4372DDF581A0DB248B0A77AECEC196ACCC52973', 16),
     (int('AA87CA22BE8B05378EB1C71EF320AD746E1D3B628BA79B9859F741E082542A385502F25DBF55296C3A545E3872760AB7', 16),
      int('3617DE4A96262C6F5D9E98BF9292DC29F8F41DBD289A147CE9DA3113B5F0B8C00A60B1CE1D7E819D7A431D7C90EA0E5F', 16)),
     hashlib.sha384),
)


def add(point, other, prime):
    if point is None:
        return other
    if other is None:
        return point
    x1, y1 = point
    x2, y2 = other
    if x1 == x2 and (y1 + y2) % prime == 0:
        return None
    if point == other:
        slope = (3 * x1 * x1 - 3) * pow(2 * y1, -1, prime) % prime
    else:
        slope = (y2 - y1) * pow(x2 - x1, -1, prime) % prime
    x3 = (slope * slope - x1 - x2) % prime
    return x3, (slope * (x1 - x3) - y1) % prime


def multiply(scalar, point, prime):
    result = None
    while scalar:
        if scalar & 1:
            result = add(result, point, prime)
        point = add(point, point, prime)
        scalar >>= 1
    return result


def oracle(separator):
    answers = {}
    for curve, (size, prime, coefficient, order, generator, digest) in enumerate(CURVES):
        x, y = generator
        if (y * y - x * x * x + 3 * x - coefficient) % prime:
            raise RuntimeError('invalid SEC2 generator')
        if multiply(order, generator, prime) is not None:
            raise RuntimeError('invalid SEC2 group order')
        key, value = bytes(size), bytes([1]) * size
        seed = (1).to_bytes(size, 'big') + (2).to_bytes(size, 'big')
        mac = lambda k, d: hmac.new(k, d, digest).digest()
        key = mac(key, value + b'\x00' + seed)
        value = mac(key, value)
        key = mac(key, value + b'\x01' + seed)
        value = mac(key, value)
        for mode in range(1, 8):
            rejected = {1: 0, 2: order, 3: order + 1,
                        4: (1 << (8 * size)) - 1}.get(mode, 1).to_bytes(size, 'big')
            retry_key = mac(key, rejected + bytes([separator]))
            retry_value = mac(retry_key, rejected)
            candidate = mac(retry_key, retry_value)
            nonce = int.from_bytes(candidate, 'big')
            if not 0 < nonce < order:
                raise RuntimeError('test vector unexpectedly requires more than one retry')
            rx, _ = multiply(nonce, generator, prime)
            r = rx % order
            s = (2 + r) * pow(nonce, -1, order) % order
            if not r or not s:
                raise RuntimeError('test vector unexpectedly has degenerate signature')
            answers[curve, mode] = (candidate.hex(), r.to_bytes(size, 'big').hex(),
                                   s.to_bytes(size, 'big').hex())
    return answers


def inspect(output, expected):
    records = output.decode('ascii').splitlines()
    if len(records) != 14:
        raise RuntimeError('retry fixture did not produce exactly14 signatures')
    mismatches = []
    for index, line in enumerate(records):
        parts = line.split()
        curve, mode = divmod(index, 7)
        mode += 1
        if len(parts) != 7 or parts[:3] != ['retry', str(curve), str(mode)] or parts[6] != 'verified':
            raise RuntimeError('retry fixture output structure changed')
        size, prime, _, order, generator, _ = CURVES[curve]
        nonce_text, r_text, s_text = parts[3:6]
        if any(len(x) != 2 * size or any(c not in '0123456789abcdef' for c in x)
               for x in (nonce_text, r_text, s_text)):
            raise RuntimeError('retry fixture lost exact scalar/signature width')
        nonce, r, s = (int(x, 16) for x in (nonce_text, r_text, s_text))
        if not all(0 < x < order for x in (nonce, r, s)):
            raise RuntimeError('retry fixture emitted an invalid scalar')
        # An independent ECDSA verification, public key = [1]G and digest =2.
        inverse = pow(s, -1, order)
        public_point = add(multiply(2 * inverse % order, generator, prime),
                           multiply(r * inverse % order, generator, prime), prime)
        if public_point is None or public_point[0] % order != r:
            raise RuntimeError('independent signature verification failed')
        if tuple(parts[3:6]) != expected[curve, mode]:
            mismatches.append({'curve': curve, 'mode': mode,
                               'actual': parts[3:6], 'expected': expected[curve, mode]})
    return mismatches


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise RuntimeError('production primitive hook changed: ' + before)
    return text.replace(before, after, 1)


exports = """
{ Private P615 test view only; no production unit export changes. }
var TestMode, TestCurve, TestCalls, TestPoints, TestInverses: Integer;
    TestNonce: string;
function TestBytes(Value: Integer): string;
"""
backend = """
function TestBytes(Value: Integer): string;
var Size: Integer;
begin
  if TestCurve = NistP256 then Size := 32 else Size := 48;
  SetLength(Result, Size);
  FillChar(Result[1], Size, 0);
  case Value of
    0: ;
    1, 2: Result[Size] := Chr(Value);
    3: if TestCurve = NistP256 then Result := OrderBytes(Ord256, Ord256.N)
       else Result := OrderBytes(Ord384, Ord384.N);
    4: begin Result := TestBytes(3); Result[Size] := Chr(Ord(Result[Size]) + 1); end;
    5: FillChar(Result[1], Size, 255);
  end;
end;
"""
hook = """
function NistSignHmac(Curve: Integer; const Key, Data: string): string;
begin
  Inc(TestCalls);
  if TestCalls > 8 then Halt(95);
  if TestCalls = 5 then
  begin
    case TestMode of
      1: Exit(TestBytes(0));
      2: Exit(TestBytes(3));
      3: Exit(TestBytes(4));
      4: Exit(TestBytes(5));
    else Exit(TestBytes(1));
    end;
  end;
  Result := NistRealHmac(Curve, Key, Data);
  if TestCalls = 8 then TestNonce := Result;
end;
"""

save()
try:
    expected = oracle(0)
    wrong_expected = oracle(1)
    if len(expected) != 14 or any(expected[k] == wrong_expected[k] for k in expected):
        raise RuntimeError('wrong-separator control does not distinguish every test vector')
    scope.save(root / 'oracle.json', {'algorithm': 'RFC6979 plus SEC1 affine ECDSA',
        'cases': [{'curve': c, 'mode': m, 'nonce_r_s': list(v)}
                  for (c, m), v in expected.items()]})
    scope.save(root / 'wrong-separator-oracle.json', {'cases': [
        {'curve': c, 'mode': m, 'nonce_r_s': list(v)} for (c, m), v in wrong_expected.items()]})
    source = source_path.read_text(encoding='utf-8')
    view = replace_once(source, '\nimplementation\n', exports + '\nimplementation\n')
    hmac_start = 'function NistSignHmac(Curve: Integer; const Key, Data: string): string;'
    view = replace_once(view, hmac_start,
                        backend + '\nfunction NistRealHmac(Curve: Integer; const Key, Data: string): string;')
    marker = '\nfunction NistEcdsaSign(Curve: Integer; const Priv, Hash: string; out R, S: string): Boolean;\nvar'
    view = replace_once(view, marker, hook + marker)
    for curve in ('256', '384'):
        before = f'          P{curve}ScalarBaseMult(p{curve}, value);\n          ok := P{curve}PointBytesX(p{curve}, x);'
        view = replace_once(view, before, before + """
          Inc(TestPoints);
          if TestPoints = 1 then
          begin
            if TestMode = 5 then x := TestBytes(0);
            if TestMode = 7 then ok := False;
          end;""")
    view = replace_once(view, '            OrderInverse(c, inverse, nonce);',
                        '            Inc(TestInverses);\n            OrderInverse(c, inverse, nonce);')
    view = replace_once(view, '            OrderMul(c, sn, product, inverse);',
                        """            OrderMul(c, sn, product, inverse);
            if (TestMode = 6) and (TestPoints = 1) then
              for i := 0 to 5 do sn[i] := 0;""")
    view_path = root / 'pasnist.paslang'
    view_path.write_text(view, encoding='utf-8')
    anchor = 'key := NistSignHmac(Curve, key, value + #0);'
    mutant_path = root / 'wrong-retry-separator.paslang'
    mutant_path.write_text(replace_once(view, anchor,
        'key := NistSignHmac(Curve, key, value + #1);'), encoding='utf-8')
    state['view_sha256'] = identity(view_path)['sha256']
    state['mutant_sha256'] = identity(mutant_path)['sha256']
    save()
    for target in ('amd64', 'arm64'):
        core = build / ('a64' if target == 'arm64' else '')
        launch = [qemu, '-cpu', 'max'] if target == 'arm64' else []
        for inline in (0, 40):
            label = f'{target}-{inline}'
            folder = root / ('view-' + label)
            folder.mkdir()
            flags = ['-target', target, '-cpu', 'base', '-inline', str(inline)]
            run(label + '-unit', [compiler, *flags, '-c', '-Fu', core,
                                 '-o', folder / 'pasnist', view_path])
            binary = folder / 'nistretry'
            run(label + '-compile', [compiler, *flags, '-Fu', folder, '-Fu', core,
                                    '-o', binary, fixture])
            if str(folder / 'pasnist.o') not in binary.with_suffix('.link').read_text(encoding='utf-8'):
                raise RuntimeError('retry fixture did not link its own production-library view')
            output = run(label + '-run', [*launch, binary])
            mismatches = inspect(output, expected)
            scope.save(root / (label + '-comparison.json'), {'mismatches': mismatches})
            if mismatches:
                raise RuntimeError('actual retry signature differs from RFC oracle: ' + label)
            state['variants'].append({'variant': label, 'signatures': 14,
                                      'pascal_verified': 14, 'python_verified': 14,
                                      'exact_rfc_matches': 14})
            save()
            print('check_nist_retry:', label, '14 real retry signatures verified', flush=True)
        label = 'wrong-separator-' + target
        folder = root / label
        folder.mkdir()
        flags = ['-target', target, '-cpu', 'base', '-inline', '40']
        run(label + '-unit', [compiler, *flags, '-c', '-Fu', core,
                             '-o', folder / 'pasnist', mutant_path])
        binary = folder / 'nistretry'
        run(label + '-compile', [compiler, *flags, '-Fu', folder, '-Fu', core,
                                '-o', binary, fixture])
        if str(folder / 'pasnist.o') not in binary.with_suffix('.link').read_text(encoding='utf-8'):
            raise RuntimeError('mutant fixture did not link the actual changed library')
        output = run(label + '-run', [*launch, binary])
        mismatches = inspect(output, expected)
        wrong_mismatches = inspect(output, wrong_expected)
        scope.save(root / (label + '-comparison.json'),
                   {'rfc_mismatches': mismatches, 'wrong_separator_mismatches': wrong_mismatches})
        if len(mismatches) != 14 or wrong_mismatches:
            raise RuntimeError('wrong-separator mutant did not fail for its exact RFC state error')
        state['mutants'].append({'target': target, 'successfully_built': True, 'run_exit': 0,
            'signatures': 14, 'pascal_verified': 14, 'python_verified': 14,
            'exact_rfc_mismatches': 14, 'exact_wrong_separator_matches': 14})
        save()
        print('check_nist_retry:', target, 'valid-signature wrong-separator mutant detected', flush=True)
    guard()
    state['ok'] = True
except BaseException as error:
    state['errors'].append(type(error).__name__ + ': ' + str(error))
    raise
finally:
    state['complete'] = True
    save()
print('check_nist_retry: 56 RFC matches and28 valid mutant mismatches passed; ' + str(root), flush=True)
