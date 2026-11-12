#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Check declaration ownership, opt-in warnings and private-name hints."""
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shlex
import subprocess
import sys
import tempfile
import time

compiler = Path(sys.argv[1]).resolve()
build = Path(sys.argv[2]).resolve()
qemu = Path(sys.argv[3]).resolve()
host_arm = len(sys.argv) > 4 and sys.argv[4] == '--host-arm64'
root = Path(__file__).resolve().parents[1]
work = Path(tempfile.mkdtemp(prefix='import-diagnostics-', dir=build))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
state = {'ok':False, 'complete':False, 'compiler':str(compiler),
         'compiler_sha256':hashlib.sha256(compiler.read_bytes()).hexdigest(),
         'host_arm64':host_arm, 'commands':[], 'profiles':[]}
base_env = {k:v for k,v in os.environ.items() if not k.startswith('PASLANG_GC') and k != 'PASLANG_DEBUG'}
def save():
    (work/'status.json').write_text(json.dumps(state,indent=2)+'\n')
def run(label, command, cwd, expected_exit=0, expected=None, warnings=(), stress=False, sdk=None):
    env = dict(base_env)
    if sdk:
        env['PASLANG_LIB'] = str(sdk)
    if stress:
        env.update(PASLANG_GCVERIFY='1',PASLANG_GCSTRESS='1',PASLANG_GCPOISON='1')
    command = list(map(str,command))
    start = time.monotonic()
    result = subprocess.run(command,cwd=cwd,env=env,capture_output=True,timeout=180)
    (work/(label+'.stdout')).write_bytes(result.stdout)
    (work/(label+'.stderr')).write_bytes(result.stderr)
    state['commands'].append({'label':label,'argv':command,'cwd':str(cwd),
        'exit':result.returncode,'expected_exit':expected_exit,'wall_s':time.monotonic()-start})
    save()
    assert result.returncode == expected_exit,(label,result.returncode,result.stderr)
    if expected is not None:
        assert result.stdout == expected,(label,result.stdout,expected)
    if expected_exit == 0:
        if warnings:
            assert result.stderr.count(b'paslangc: warning: import shadow for ') == 1,(label,result.stderr)
            for text in warnings:
                assert text.encode() in result.stderr,(label,text,result.stderr)
        else:
            assert not result.stderr,(label,result.stderr)
    return result

save()
try:
    profiles = [('arm64','base'),('arm64','max')] if host_arm else [
        ('amd64','base'),('amd64','native'),('arm64','base'),('arm64','max')]
    for target,cpu in profiles:
        sdk = build/'a64' if target == 'arm64' else build
        compile_launch = [qemu,'-cpu','cortex-a53'] if host_arm else []
        launch = [qemu,'-cpu','cortex-a53' if cpu == 'base' else 'max'] if target == 'arm64' else []
        for inline in (0,40):
            tag = target+'-'+cpu+'-'+str(inline)
            folder = work/tag
            folder.mkdir()
            flags = ['-target',target,'-cpu',cpu,'-inline',str(inline),'-Fu',folder,'-Fu',sdk]
            cc = [*compile_launch,compiler,*flags]
            for unit in ('di_a','di_b','di_secret','di_other','di_clock','di_priv','di_multi',
                         'di_pub','di_wrap','di_own','di_api'):
                run(tag+'-unit-'+unit,[*cc,'-c','-o',folder/unit,root/'testdata/importdiag'/(unit+'.paslang')],folder,sdk=sdk)

            def program(name, text, expected, *, warn=False, through=None, same=None):
                source = folder/((same or name)+'.paslang')
                if same:
                    assert source.read_text() == text+'\n'
                else:
                    source.write_text(text+'\n')
                exe = folder/(same or name)
                previous = exe.read_bytes() if same else None
                warning = ('Value','selected di_b.Value','through '+through,
                           'directly imported di_a.Value','qualify the call') if through else ()
                run(tag+'-'+name+'-compile',[*cc,*( ['-warn-import-shadow'] if warn else []),
                    '-o',exe,source],folder,warnings=warning,sdk=sdk)
                if same:
                    assert exe.read_bytes() == previous,(tag,name,'warning changed executable')
                linked = [Path(p).resolve() for p in shlex.split(exe.with_suffix('.link').read_text()) if p.endswith('.o')]
                for obj in linked:
                    if obj.stem.startswith('di_'):
                        assert obj.parent == folder,(tag,name,obj)
                for mode in ('normal','gc'):
                    run(tag+'-'+name+'-'+mode,[*launch,exe],folder,
                        expected=expected.encode(),stress=mode=='gc')
                return exe

            shadow = 'program p; uses di_a,di_pub; begin WriteLn(Value(5)); end.'
            program('plain',shadow,'205\n')
            program('warning',shadow,'205\n',warn=True,through='di_pub',same='plain')
            program('deep','program p; uses di_a,di_wrap; begin WriteLn(Value(5)); end.','205\n',warn=True,through='di_wrap')
            program('cached','program p; uses di_a,di_pub,di_wrap; begin WriteLn(Value(5)); end.','205\n',warn=True,through='di_pub')
            program('upgrade','program p; uses di_a,di_priv,di_pub; begin WriteLn(Value(5)); end.','205\n',warn=True,through='di_pub')
            program('reverse','program p; uses di_pub,di_a; begin WriteLn(Value(5)); end.','105\n',warn=True)
            program('direct','program p; uses di_a,di_b; begin WriteLn(Value(5)); end.','205\n',warn=True)
            program('qualified','program p; uses di_a,di_pub; begin WriteLn(di_a.Value(5)); WriteLn(di_b.Value(5)); end.','105\n205\n',warn=True)
            program('local','program p; uses di_a,di_pub; function Value(N: Integer): Integer; begin Result := 400+N; end; begin WriteLn(Value(5)); end.','405\n',warn=True)
            program('facade-own','program p; uses di_a,di_own; begin WriteLn(Value(5)); end.','305\n',warn=True)
            program('public-type','program p; uses di_api; var S: SecretType; begin S := GetSecret; WriteLn(S.N); end.','73\n',warn=True)
            program('direct-fix','program p; uses di_priv,di_secret; begin WriteLn(SecretValue(1)); end.','72\n',warn=True)
            program('x509','program p; uses sysutils,pasx509; begin WriteLn(IntToStr(5)); WriteLn(FileExists(\'.\',False)); WriteLn(StrToInt64(\'7\')); end.','5\n0\n7\n',warn=True)
            program('tls','program p; uses sysutils,pastls; begin WriteLn(IntToStr(5)); end.','5\n',warn=True)

            negatives = [
                ('private-call','program p; uses di_priv; begin WriteLn(SecretValue(1)); end.',
                    ('unit di_secret declares SecretValue','add di_secret to uses')),
                ('private-const','program p; uses di_priv; begin WriteLn(HiddenToken); end.',
                    ('unit di_secret declares HiddenToken','add di_secret to uses')),
                ('private-var','program p; uses di_priv; begin HiddenVar := 2; end.',
                    ('unit di_secret declares HiddenVar','add di_secret to uses')),
                ('private-type','program p; uses di_priv; var S: SecretType; begin end.',
                    ('unit di_secret declares SecretType','add di_secret to uses')),
                ('clock','program p; uses di_priv; begin WriteLn(NowUnix); end.',
                    ('unit pastime declares NowUnix','add pastime to uses')),
                ('lower-case','program p; uses di_priv; begin WriteLn(secretvalue(1)); end.',
                    ('unit di_secret declares secretvalue','add di_secret to uses')),
                ('ambiguous','program p; uses di_multi; begin WriteLn(HiddenToken); end.',
                    ('units ','di_secret','di_other','export HiddenToken','add the intended unit to uses')),
                ('wrong-arity','program p; uses di_a,di_wrap; begin WriteLn(Wrong(5,False)); end.',
                    ('wrong number of arguments for Wrong','selected di_b.Wrong (through di_wrap)',
                     'directly imported di_a.Wrong','qualify the call')),
                ('unknown','program p; begin WriteLn(NoSuchName); end.',('unknown identifier NoSuchName',)),
            ]
            for name,text,hints in negatives:
                source = folder/(name+'.paslang')
                source.write_text(text+'\n')
                result = run(tag+'-'+name,[*cc,'-o',folder/name,source],folder,
                    expected_exit=1,expected=b'',sdk=sdk)
                for hint in hints:
                    assert hint.encode() in result.stderr,(tag,name,hint,result.stderr)
                assert re.search(rb' at [0-9]+:[0-9]+',result.stderr),(tag,name,result.stderr)
                assert str(source).encode() in result.stderr,(tag,name,result.stderr)
                assert not (folder/name).exists(),(tag,name,'error produced executable')
                if name == 'unknown':
                    assert b'; unit ' not in result.stderr and b' to uses' not in result.stderr
            state['profiles'].append(tag)
            save()
            print('ok import-diagnostics',tag,flush=True)
    assert hashlib.sha256(compiler.read_bytes()).hexdigest() == state['compiler_sha256']
    state['ok'] = True
finally:
    state['complete'] = True
    save()
assert state['ok']
print('ok import-diagnostics',len(state['commands']),'commands; evidence:',work)
