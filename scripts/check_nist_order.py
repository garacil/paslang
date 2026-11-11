#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Actual scalar arithmetic against Python integer oracles, including aliases."""
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import signal
import subprocess
import time
import sys
import tempfile

tree = Path(__file__).resolve().parents[1]
compiler = Path(sys.argv[1]).resolve()
build = Path(sys.argv[2]).resolve()
qemu = Path(sys.argv[3]).resolve()
root = Path(tempfile.mkdtemp(prefix='nist-order-', dir=build))
source = (tree / 'src/lib/pasnist.paslang').read_text()
source_hash = hashlib.sha256(source.encode()).hexdigest()
orders = [int('FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551', 16),
          int('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFC7634D81F4372DDF581A0DB248B0A77AECEC196ACCC52973', 16)]
rows = []
state = {'ok': False, 'complete': False, 'source_sha256': source_hash, 'commands': rows}


def save():
    (root / 'status.json').write_text(json.dumps(state, indent=2) + '\n')


def run(label, command):
    directory = root / label
    directory.mkdir()
    args = list(map(str, command))
    record = {'label': label, 'argv': args, 'cwd': str(root), 'exit': None}
    rows.append(record)
    save()
    started = time.monotonic()
    process = subprocess.Popen(args, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=True)
    try:
        out, err = process.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        record['timeout'] = True
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, err = process.communicate(timeout=20)
    record.update(exit=process.returncode, elapsed_s=time.monotonic() - started)
    (directory / 'stdout').write_bytes(out)
    (directory / 'stderr').write_bytes(err)
    (directory / 'command.json').write_text(json.dumps(record, indent=2) + '\n')
    save()
    assert not record.get('timeout') and process.returncode == 0, (label, err)
    assert hashlib.sha256((tree / 'src/lib/pasnist.paslang').read_bytes()).hexdigest() == source_hash
    return out


declaration = '''
{ Test view only: the production arithmetic bodies are unchanged. }
function NistOrderProbe(Curve, Operation, Overflow: Integer; const A, B: string): string;
'''
wrapper = '''
function NistOrderProbe(Curve, Operation, Overflow: Integer; const A, B: string): string;
var c: TOrder; ax,bx,zx: TNat; ok:Boolean;
begin
  if Curve = NistP256 then c:=Ord256 else c:=Ord384;
  ok:=OrderSetRaw(c,ax,A); if not ok then Halt(71);
  ok:=OrderSetRaw(c,bx,B); if not ok then Halt(72);
  zx:=ax;
  case Operation of
    0: OrderReduce(c,zx,Overflow);
    1: OrderAdd(c,zx,ax,bx);
    2: OrderMul(c,zx,ax,bx);
    3: OrderMontMul(c,zx,ax,bx);
    4: OrderInverse(c,zx,ax);
    5: begin OrderAdd(c,ax,ax,bx); zx:=ax; end;
    6: begin OrderAdd(c,bx,ax,bx); zx:=bx; end;
    7: begin OrderMul(c,ax,ax,bx); zx:=ax; end;
    8: begin OrderMontMul(c,bx,ax,bx); zx:=bx; end;
    9: begin OrderInverse(c,ax,ax); zx:=ax; end;
  else Halt(73);
  end;
  Result:=OrderBytes(c,zx);
end;
'''
assert source.count('\nimplementation\n') == 1 and source.count('\ninitialization\n') == 1
view = source.replace('\nimplementation\n', declaration + '\nimplementation\n', 1)
view = view.replace('\ninitialization\n', wrapper + '\ninitialization\n', 1)
(root / 'pasnist.paslang').write_text(view)
driver = '''program ordermodel;
uses pasnist,paslib;
function UnHex(const Text:string):string;
var i,n,v:Integer;c:Char;
begin
 SetLength(Result,Length(Text) div 2); v:=0;
 for i:=1 to Length(Text) do begin
  c:=Text[i]; if c<='9' then n:=Ord(c)-48 else n:=Ord(c)-87;
  if Odd(i) then v:=n shl 4 else Result[i div 2]:=Chr(v or n);
 end;
end;
var text,answer:string;doc,row:json;
begin
 if not ReadFile(ParamStr(1),text) then Halt(74);
 doc:=JsonParse(text);
 for row in doc do begin
  answer:=NistOrderProbe(row['curve'].AsInteger,row['op'].AsInteger,
   row['high'].AsInteger,UnHex(row['a'].AsString),UnHex(row['b'].AsString));
  WriteLn(Hex(answer));
 end;
end.
'''
(root / 'ordermodel.paslang').write_text(driver)
cases, expected = [], []
random_source = random.Random(59401)


def add(curve, op, a, b, high, wanted):
    size = 32 if curve == 0 else 48
    cases.append({'curve': curve, 'op': op, 'a': a.to_bytes(size, 'big').hex(),
                  'b': b.to_bytes(size, 'big').hex(), 'high': high})
    expected.append(wanted.to_bytes(size, 'big'))


for curve, n in enumerate(orders):
    width = 256 if curve == 0 else 384
    radix = 1 << width
    rinverse = pow(radix, -1, n)
    edges = sorted({0, 1, 2, n - 2, n - 1, *(
        (1 << bit) + delta for bit in range(64, width, 64) for delta in (-1, 0, 1))})
    for a in sorted({0, 1, n - 1, n, n + 1, radix - 1}):
        add(curve, 0, a, 0, 0, a % n)
    for low in (0, 1, 2 * n - radix - 1):
        add(curve, 0, low, 0, 1, (radix + low) % n)
    pairs = [(a, b) for a in edges for b in edges]
    pairs += [(random_source.randrange(n), random_source.randrange(n)) for _ in range(48)]
    for a, b in pairs:
        for op in (1, 5, 6):
            add(curve, op, a, b, 0, (a + b) % n)
        for op in (2, 7):
            add(curve, op, a, b, 0, a * b % n)
        for op in (3, 8):
            add(curve, op, a, b, 0, a * b * rinverse % n)
    for a in [*edges, *(random_source.randrange(1, n) for _ in range(12))]:
        for op in (4, 9):
            add(curve, op, a, 0, 0, 0 if a == 0 else pow(a, -1, n))
(root / 'cases.json').write_text(json.dumps(cases, separators=(',', ':')) + '\n')
(root / 'expected.hex').write_text(''.join(value.hex() + '\n' for value in expected))
state['cases_per_variant'] = len(cases)
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
save()
try:
    for target in ('amd64', 'arm64'):
        core = build / ('a64' if target == 'arm64' else '')
        launch = [qemu, '-cpu', 'max'] if target == 'arm64' else []
        for inline in (0, 40):
            label = target + '-' + str(inline)
            directory = root / ('view-' + label)
            directory.mkdir()
            flags = ['-target', target, '-cpu', 'base', '-inline', str(inline)]
            run(label + '-unit', [compiler, *flags, '-c', '-Fu', core, '-o',
                directory / 'pasnist', root / 'pasnist.paslang'])
            binary = directory / 'ordermodel'
            run(label + '-compile', [compiler, *flags, '-Fu', directory, '-Fu', core,
                '-o', binary, root / 'ordermodel.paslang'])
            assert str(directory / 'pasnist.o') in binary.with_suffix('.link').read_text()
            output = run(label + '-run', [*launch, binary, root / 'cases.json'])
            actual = [bytes.fromhex(line.decode()) for line in output.splitlines()]
            assert actual == expected, (label, next((i for i, (a, b) in enumerate(
                zip(actual, expected)) if a != b), 'wrong row count'))
            print(label, len(cases), 'arithmetic-model cases passed', flush=True)
    mutants = {
        'drop-overflow': ('mask := -(((Overflow or (-Overflow)) shr 63) or (borrow xor 1));',
                          'mask := -(borrow xor 1);'),
        'reverse-borrow': ('mask := -(((Overflow or (-Overflow)) shr 63) or (borrow xor 1));',
                           'mask := -(((Overflow or (-Overflow)) shr 63) or borrow);'),
    }
    state['mutants'] = []
    for name, (before, after) in mutants.items():
        assert view.count(before) == 1
        changed = root / (name + '.paslang')
        changed.write_text(view.replace(before, after, 1))
        for target in ('amd64', 'arm64'):
            label = name + '-' + target
            directory = root / label
            directory.mkdir()
            core = build / ('a64' if target == 'arm64' else '')
            launch = [qemu, '-cpu', 'max'] if target == 'arm64' else []
            flags = ['-target', target, '-cpu', 'base', '-inline', '40']
            run(label + '-unit', [compiler, *flags, '-c', '-Fu', core,
                '-o', directory / 'pasnist', changed])
            binary = directory / 'ordermodel'
            run(label + '-compile', [compiler, *flags, '-Fu', directory, '-Fu', core,
                '-o', binary, root / 'ordermodel.paslang'])
            assert str(directory / 'pasnist.o') in binary.with_suffix('.link').read_text()
            actual = run(label + '-run', [*launch, binary, root / 'cases.json'])
            wanted = (root / 'expected.hex').read_bytes()
            assert actual != wanted, 'arithmetic mutant survived: ' + label
            state['mutants'].append({'name': label, 'compiled': True, 'detected': True})
            save()
            print(label, 'arithmetic defect detected', flush=True)
    state['ok'] = True
finally:
    state['complete'] = True
    save()
print('All actual arithmetic/model and alias variants passed.', flush=True)
