#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Nonce rejection, degenerate components and kernel entropy fault regressions.

Only private test views intercept primitives; installed library exports and all
scalar/signing/keygen algorithm bodies are kept intact. The linker receipt must
select each generated view. Expected signatures use independent Python modular
arithmetic and the checked-in Go public-point corpus.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import sys
import tempfile

tree = Path(__file__).resolve().parents[1]
compiler = Path(sys.argv[1]).resolve()
build = Path(sys.argv[2]).resolve()
qemu = Path(sys.argv[3]).resolve()
root = Path(tempfile.mkdtemp(prefix='nist-faults-', dir=build))
source = (tree / 'src/lib/pasnist.paslang').read_text()
source_hash = hashlib.sha256(source.encode()).hexdigest()
records = []
state = {'ok': False, 'complete': False, 'source_sha256': source_hash, 'commands': records}


def save():
    (root / 'status.json').write_text(json.dumps(state, indent=2) + '\n')


def run(label, args, expected_exit=0):
    directory = root / label
    directory.mkdir()
    args = list(map(str, args))
    row = {'argv': args, 'exit': None, 'label': label}
    records.append(row)
    save()
    start = time.monotonic()
    process = subprocess.Popen(args, cwd=root, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        out, err = process.communicate(timeout=240)
    except subprocess.TimeoutExpired:
        row['timeout'] = True
        os.killpg(process.pid, signal.SIGKILL)
        out, err = process.communicate(timeout=20)
    row.update(exit=process.returncode, elapsed_s=time.monotonic() - start)
    (directory / 'stdout').write_bytes(out)
    (directory / 'stderr').write_bytes(err)
    save()
    assert not row.get('timeout') and row['exit'] == expected_exit, (label, err, out)
    assert hashlib.sha256((tree / 'src/lib/pasnist.paslang').read_bytes()).hexdigest() == source_hash
    return out


exports = '''
{ Test view only: no hooks are exported by the production unit. }
var TestMode, TestCurve, TestCalls, TestPoints, TestInverses: Integer;
    TestBuffer: Pointer;
function TestBytes(Value: Integer): string;
function TestBufferZero: Boolean;
'''
backend = '''
function TestBytes(Value: Integer): string;
var Size: Integer;
begin
  if TestCurve=NistP256 then Size:=32 else Size:=48;
  SetLength(Result,Size); FillChar(Result[1],Size,0);
  case Value of
    0: ;
    1,2: Result[Size]:=Chr(Value);
    3: if TestCurve=NistP256 then Result:=OrderBytes(Ord256,Ord256.N)
       else Result:=OrderBytes(Ord384,Ord384.N);
    4: begin
       Result:=TestBytes(3);
       Result[Size]:=Chr(Ord(Result[Size])+1);
       end;
    5: FillChar(Result[1],Size,255);
  end;
end;

function TestBufferZero: Boolean;
var I,Size:Integer; P:^Byte;
begin
  if TestCurve=NistP256 then Size:=32 else Size:=48;
  Result:=TestBuffer<>nil;
  for I:=0 to Size-1 do begin
    P:=Pointer(Integer(TestBuffer)+I);
    if P^<>0 then Result:=False;
  end;
end;

function TestEntropy(Nr,Address,Count,Flags:Integer):Integer;
var Size,Offset,Take,I:Integer; P:^Byte; Candidate:string;
begin
  Inc(TestCalls);
  if TestCalls>8 then Halt(90);
  if Amd64=0 then begin if Nr<>278 then Halt(91); end
  else if Nr<>318 then Halt(92);
  if Flags<>0 then Halt(93);
  if TestCurve=NistP256 then Size:=32 else Size:=48;
  if TestCalls=1 then TestBuffer:=Pointer(Address);
  Offset:=Address-Integer(TestBuffer);
  if (Offset<0) or (Count<>Size-Offset) then Halt(94);
  if (TestMode=101) and (TestCalls=1) then Exit(-4);
  if (TestMode=110) then Exit(-38);
  if (TestMode=111) and (TestCalls=2) then Exit(-4);
  if TestMode=105 then Exit(Count+1);
  if TestCalls=2 then begin
    if TestMode=103 then Exit(-5);
    if TestMode=104 then Exit(0);
  end;
  Take:=Count;
  if (TestCalls=1) and ((TestMode=102) or (TestMode=103) or
      (TestMode=104) or (TestMode=111)) then Take:=Size div 2;
  Candidate:=TestBytes(1);
  if TestCalls=1 then case TestMode of
    106: Candidate:=TestBytes(0);
    107: Candidate:=TestBytes(3);
    108: Candidate:=TestBytes(4);
    109: Candidate:=TestBytes(5);
  end;
  for I:=0 to Take-1 do begin
    P:=Pointer(Address+I); P^:=Byte(Ord(Candidate[Offset+I+1]));
  end;
  Result:=Take;
end;
'''
hmac = '''
function NistSignHmac(Curve: Integer; const Key, Data: string): string;
begin
  Inc(TestCalls);
  if TestCalls>8 then Halt(95);
  if TestCalls=5 then begin
    case TestMode of
      1: Exit(TestBytes(0));
      2: Exit(TestBytes(3));
      3: Exit(TestBytes(4));
      4: Exit(TestBytes(5));
    else Exit(TestBytes(1));
    end;
  end;
  if TestCalls=8 then begin
    if TestMode<=4 then Exit(TestBytes(1)) else Exit(TestBytes(2));
  end;
  Result:=NistRealHmac(Curve,Key,Data);
end;
'''


def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new, 1)


view = replace_once(source, '\nimplementation\n', exports + '\nimplementation\n')
view = replace_once(view, '\nfunction NistGenerateKey(Curve: Integer): string;\nvar',
                    backend + '\nfunction NistGenerateKey(Curve: Integer): string;\nvar')
view = replace_once(view, 'count := Syscall(nr, Integer(@Result[used + 1]), size - used, 0);',
                    'count := TestEntropy(nr, Integer(@Result[used + 1]), size - used, 0);')
view = replace_once(view, 'function NistSignHmac(Curve: Integer; const Key, Data: string): string;',
                    'function NistRealHmac(Curve: Integer; const Key, Data: string): string;')
marker = '\nfunction NistEcdsaSign(Curve: Integer; const Priv, Hash: string; out R, S: string): Boolean;\nvar'
view = replace_once(view, marker, hmac + marker)
for curve in ('256', '384'):
    old = f'          P{curve}ScalarBaseMult(p{curve}, value);\n          ok := P{curve}PointBytesX(p{curve}, x);'
    new = old + '''
          Inc(TestPoints);
          if TestPoints=1 then begin
            if TestMode=5 then x:=TestBytes(0);
            if TestMode=7 then ok:=False;
          end;'''
    view = replace_once(view, old, new)
view = replace_once(view, '            OrderInverse(c, inverse, nonce);',
                    '            Inc(TestInverses);\n            OrderInverse(c, inverse, nonce);')
view = replace_once(view, '            OrderMul(c, sn, product, inverse);',
                    '''            OrderMul(c, sn, product, inverse);
            if (TestMode=6) and (TestPoints=1) then
              for i:=0 to 5 do sn[i]:=0;''')
(root / 'pasnist.paslang').write_text(view)
driver = '''program nistfaults;
uses pasnist,paslib;
procedure Require(OK:Boolean; const Name:string);
begin if not OK then begin WriteLn('FAIL ',Name,' curve=',TestCurve,' mode=',TestMode,
 ' calls=',TestCalls,' points=',TestPoints,' inverse=',TestInverses); Halt(1); end; end;
procedure Reset(Mode,Curve:Integer);
begin TestMode:=Mode; TestCurve:=Curve; TestCalls:=0; TestPoints:=0;
 TestInverses:=0; TestBuffer:=nil; end;
var C,M,WantCalls,WantPoints,WantInverse:Integer; R,S,P,H,K:string;
begin
 for C:=0 to 1 do begin
  for M:=1 to 7 do begin
   Reset(M,C); P:=TestBytes(1); H:=TestBytes(2);
   Require(NistEcdsaSign(C,P,H,R,S),'sign');
   Require(TestCalls=8,'RFC retry calls');
   if M<=4 then WantPoints:=1 else WantPoints:=2;
   if M=6 then WantInverse:=2 else WantInverse:=1;
   Require(TestPoints=WantPoints,'point count');
   Require(TestInverses=WantInverse,'inverse count');
   Require(NistEcdsaVerify(C,NistPublicKey(C,P),H,R,S),'verify');
   WriteLn('nonce ',C,' ',M,' ',Hex(R),' ',Hex(S));
  end;
  for M:=101 to 111 do begin
   Reset(M,C); K:=NistGenerateKey(C);
   if (M=103) or (M=104) or (M=105) or (M=110) then begin
    Require(K='','entropy failure');
    Require(TestBufferZero,'failed key erased');
   end else begin
    Require(K=TestBytes(1),'accepted scalar');
    Require(NistPublicKey(C,K)<>'','valid public key');
   end;
   if (M=105) or (M=110) then WantCalls:=1
   else if M=111 then WantCalls:=3 else WantCalls:=2;
   Require(TestCalls=WantCalls,'entropy calls');
   WriteLn('entropy ',C,' ',M,' ok');
  end;
  Reset(101,C); Require(NistGenerateKey(-1)='','curve rejection');
  Require(TestCalls=0,'invalid curve entropy call');
 end;
end.
'''
(root / 'nistfaults.paslang').write_text(driver)
corpus = json.loads((tree / 'testdata/nistsign-vectors.json').read_text())['vectors']
orders = [int('FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551',16),
          int('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFC7634D81F4372DDF581A0DB248B0A77AECEC196ACCC52973',16)]
expected = []
for curve, n in enumerate(orders):
    size = 32 if curve == 0 else 48
    for mode in range(1,8):
        nonce = 1 if mode <= 4 else 2
        row = next(v for v in corpus if v['curve'] == curve and int(v['private'],16) == nonce)
        r = int(row['public'][2:2+size*2],16) % n
        s = (2+r)*pow(nonce,-1,n)%n
        expected.append(f'nonce {curve} {mode} {r:0{size*2}x} {s:0{size*2}x}\n')
    expected.extend(f'entropy {curve} {mode} ok\n' for mode in range(101,112))
expected = ''.join(expected).encode()
(root / 'expected.stdout').write_bytes(expected)
save()
try:
    for target in ('amd64','arm64'):
        core = build / ('a64' if target=='arm64' else '')
        launch = [qemu,'-cpu','max'] if target=='arm64' else []
        for inline in (0,40):
            label = f'{target}-{inline}'
            directory = root / ('view-'+label)
            directory.mkdir()
            flags = ['-target',target,'-cpu','base','-inline',str(inline)]
            run(label+'-unit',[compiler,*flags,'-c','-Fu',core,'-o',directory/'pasnist',root/'pasnist.paslang'])
            binary = directory/'nistfaults'
            run(label+'-compile',[compiler,*flags,'-Fu',directory,'-Fu',core,'-o',binary,root/'nistfaults.paslang'])
            assert str(directory/'pasnist.o') in binary.with_suffix('.link').read_text()
            output = run(label+'-run',[*launch,binary])
            assert output == expected, (label,output,expected)
            print(label,'36 nonce/entropy fault cases passed',flush=True)
    mutants = {
        'biased-nonce': ('if OrderSetBytes(c, nonce, value) then',
                         'if OrderSetOverflowingBytes(c, nonce, value) then',
                         b'FAIL RFC retry calls'),
        'lost-eintr': ('until count <> -4;', 'until True;', b'FAIL accepted scalar'),
    }
    state['mutants'] = []
    for name, (before, after, diagnostic) in mutants.items():
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
            binary = directory / 'nistfaults'
            run(label + '-compile', [compiler, *flags, '-Fu', directory, '-Fu', core,
                '-o', binary, root / 'nistfaults.paslang'])
            assert str(directory / 'pasnist.o') in binary.with_suffix('.link').read_text()
            output = run(label + '-run', [*launch, binary], expected_exit=1)
            assert diagnostic in output, (label, output)
            state['mutants'].append({'name': label, 'compiled': True, 'detected': True})
            save()
            print(label, 'fault detected', flush=True)
    state['ok'] = True
finally:
    state['complete'] = True
    save()
