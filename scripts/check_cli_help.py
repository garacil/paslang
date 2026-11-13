#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Check public CLI help, errors and executable usage on an actual compiler."""
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import subprocess
import sys
import tempfile
import time

compiler = Path(sys.argv[1]).resolve()
build = Path(sys.argv[2]).resolve()
qemu = [str(Path(sys.argv[3]).resolve()), '-cpu', 'cortex-a53'] if len(sys.argv) > 3 else []
target = 'arm64' if qemu else 'amd64'
units = build / 'a64' if qemu else build
work = Path(tempfile.mkdtemp(prefix='cli-help-' + target + '-', dir=build))
base = {k:v for k,v in os.environ.items() if not k.startswith('PASLANG_GC') and k != 'PASLANG_DEBUG'}
base['PASLANG_LIB'] = str(units)
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
state = {'ok':False, 'complete':False, 'target':target, 'compiler':str(compiler),
         'compiler_sha256':hashlib.sha256(compiler.read_bytes()).hexdigest(), 'commands':[]}
def save():
    (work/'status.json').write_text(json.dumps(state,indent=2)+'\n')
def run(label, args, code=0, expected=None, env=base, compiler_call=True, readonly=True):
    command = [*qemu, str(compiler), *map(str,args)] if compiler_call else list(map(str,args))
    before = set(work.iterdir())
    start = time.monotonic()
    r = subprocess.run(command,cwd=work,env=env,capture_output=True,timeout=180 if qemu else 60)
    if readonly:
        assert set(work.iterdir()) == before, label + ': help changed the working directory'
    (work/(label+'.stdout')).write_bytes(r.stdout)
    (work/(label+'.stderr')).write_bytes(r.stderr)
    state['commands'].append({'label':label,'argv':command,'exit':r.returncode,
        'expected_exit':code,'elapsed_s':time.monotonic()-start})
    save()
    assert r.returncode == code, (label,r.returncode,r.stderr)
    if code == 0:
        assert not r.stderr,(label,r.stderr)
    if expected is not None:
        assert r.stdout == expected,(label,r.stdout,expected)
    return r

save()
try:
    short = run('default',[]).stdout
    assert short.isascii() and b'\x1b' not in short
    short_version = re.fullmatch(rb'paslangc ([0-9]+\.[0-9]+\.[0-9]+) - modern Pascal compiler', short.splitlines()[0])
    assert short_version and len(short.splitlines()) <= 35
    for line in (b'Usage:',b'  paslangc [options] source.paslang',b'Build and run:',
                 b'  paslangc -o app source.paslang',b'  ./app',b'Common options:',b'Help:',b'Documentation:'):
        assert line in short.splitlines(),line
    assert ('Default target: linux/'+target).encode() in short
    assert b'(default: a.out)' in short and b'--help <topic>' in short
    for label,args in [('short',['-h']),('index',['--help','index']),('short-topic',['--help','short'])]:
        run(label,args,expected=short)
    run('plain-terminal',[],expected=short,env=dict(base,TERM='dumb',COLUMNS='20',NO_COLOR='1'))

    version = run('version',['-v']).stdout
    match = re.fullmatch(rb'paslangc ([0-9]+\.[0-9]+\.[0-9]+)',version.splitlines()[0])
    assert match and ('target: linux/'+target).encode() in version.splitlines()
    assert any(line.startswith(b'processor: ') for line in version.splitlines())
    assert 'Copyright (C) 2026 Germán Luis Aracil Boned'.encode() in version
    assert b'License GPLv3+' in version and b'NO WARRANTY' in version
    assert b'\x1b' not in version
    assert short_version[1] == match[1], 'default help and -v release differ'
    state['version'] = match[1].decode()
    run('long-version',['--version'],expected=version)

    topics = ['flags','types','lang','runtime','lib','limits','examples']
    all_text = run('all',['--help']).stdout
    assert all_text.startswith(short + b'\n'), 'full help lost the release overview'
    assert re.findall(rb'^## ([a-z]+)$',all_text,re.M) == [t.encode() for t in topics]
    run('all-topic',['--help','all'],expected=all_text)
    for topic in topics:
        output = run('topic-'+topic,['--help',topic]).stdout
        assert output.startswith(('## '+topic+'\n').encode()),topic
        assert re.findall(rb'^## ([a-z]+)$',output,re.M) == [topic.encode()],topic
    assert run('mixed-case',['--help','LiB']).stdout == (work/'topic-lib.stdout').read_bytes()
    bad = run('unknown-topic',['--help','not-a-topic'],code=1,expected=b'')
    assert bad.stderr == b'paslangc: unknown help topic: not-a-topic; use paslangc --help index\n'

    for label,args in [('missing-output-source',['-o','unused']),('missing-object-source',['-c'])]:
        bad = run(label,args,code=1,expected=b'')
        assert bad.stderr == b'paslangc: no source file; use paslangc -h\n'

    hello = work/'source.paslang'
    hello.write_text("program hello; begin WriteLn('hello'); end.\n")
    run('compile-example',['-o','app','source.paslang'],expected=b'',readonly=False)
    run('run-example',[*qemu,work/'app'],expected=b'hello\n',compiler_call=False)
    run('compile-default',['source.paslang'],expected=b'',readonly=False)
    run('run-default',[*qemu,work/'a.out'],expected=b'hello\n',compiler_call=False)
    object_base = work/'object/hello'
    run('compile-object',['-c','-o',object_base,'source.paslang'],expected=b'',readonly=False)
    obj = object_base.with_suffix('.o')
    assert obj.is_file() and not object_base.exists()
    data = obj.read_bytes()
    assert data[:6] == b'\x7fELF\x02\x01' and int.from_bytes(data[16:18],'little') == 1
    assert int.from_bytes(data[18:20],'little') == (183 if qemu else 62)

    (work/'greet.paslang').write_text("unit greet; interface function Greeting: string; implementation function Greeting: string; begin Result := 'hello from unit'; end; end.\n")
    run('compile-unit',['-c','greet.paslang'],expected=b'',readonly=False)
    local_units = work/('build/a64' if qemu else 'build')
    assert (local_units/'greet.pi').is_file() and (local_units/'greet.o').is_file()
    (work/'usegreet.paslang').write_text('program usegreet; uses greet; begin WriteLn(Greeting); end.\n')
    run('compile-unit-client',['-Fu',local_units,'-o','unit-app','usegreet.paslang'],expected=b'',readonly=False)
    run('run-unit-client',[*qemu,work/'unit-app'],expected=b'hello from unit\n',compiler_call=False)
    assert hashlib.sha256(compiler.read_bytes()).hexdigest() == state['compiler_sha256']
    state['ok'] = True
finally:
    state['complete'] = True
    save()
assert state['ok']
print('ok compiler-help',target,'('+str(len(state['commands']))+' commands; usage/topics/version/errors and real compile/run/unit examples)')
