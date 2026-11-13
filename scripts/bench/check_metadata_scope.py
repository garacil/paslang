#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Compiler-free bounded metadata scope controls and actual-source mutants."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent


def load(path):
    spec=importlib.util.spec_from_file_location('scope_under_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def require(condition,message):
    if not condition:raise AssertionError('metadata scope control: '+message)


def control(name,target,work):
    scope=load(target)
    if name in ('ready-stream','child-stream','no-children'):
        original=(scope.time.monotonic,scope.os.waitpid,scope._children,scope._signal_owned_child)
        ticks=[0];calls=[0]
        def clock():
            ticks[0]+=1
            if ticks[0]>1000:raise AssertionError('metadata scope control: unbounded ready stream')
            return ticks[0]*.001
        def waiting(pid,flags):
            calls[0]+=1
            clock()
            return (123,0)
        def children():
            for i in range(10000):
                if i>1000:raise AssertionError('metadata scope control: unbounded child stream')
                yield 123
        try:
            scope.time.monotonic=clock
            if name=='no-children':
                def empty(pid,flags):raise ChildProcessError
                scope.os.waitpid=empty;scope._children=lambda:[]
            elif name=='ready-stream':
                scope.os.waitpid=waiting;scope._children=lambda:[]
            else:
                scope._children=children
                scope._signal_owned_child=lambda pid,sig: bool(clock())
            result=scope._drain_owned(.01)
        finally:
            scope.time.monotonic,scope.os.waitpid,scope._children,scope._signal_owned_child=original
        require(result['ok']==(name=='no-children'),'ECHILD/deadline verdict differs')
        require(ticks[0]<100,'notification stream exceeded absolute deadline')
        return {'name':name,'ticks':ticks[0],'ok':True}

    environment=dict(os.environ)
    if name=='root-gone':
        child=subprocess.Popen([sys.executable,'-c','pass'])
        descriptor=os.pidfd_open(child.pid,0)
        try:
            child.wait(timeout=2)
            result=scope._force_scope(child,descriptor,.3)
            require(not result['discovery_complete'] and result['supervisor_reaped'],
                    'exited root authorized numeric ancestry discovery')
            require(not result['descendants'],'exited root acquired unrelated descendants')
        finally:os.close(descriptor)
        return {'name':name,'ok':True}

    if name=='cache-env':
        args=[sys.executable,'-c',"print('metadata')"]
        result=scope.cached_metadata(args,work/'cached',work,environment)
        require(result['status']==0,'initial metadata cache failed')
        for key in ('GOARCH','GOOS','GOFLAGS','GOWORK','GO111MODULE','GOCACHE','GOFMAHASH'):
            changed=dict(environment);changed[key]='changed-control'
            try:scope.validate_receipt(work/'cached',args,work,changed,require_success=True)
            except RuntimeError:pass
            else:require(False,'cached metadata accepted changed '+key)
        return {'name':name,'ok':True}

    if name=='finite-cleanup':
        child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
        descriptor=os.pidfd_open(child.pid,0)
        try:
            try:result=scope._force_scope(child,descriptor,sys.float_info.max)
            except OverflowError:require(False,'finite cleanup interval overflow')
            require(result['ok'] and result['supervisor_reaped'],'large finite deadline failed scoped cleanup')
        finally:
            os.close(descriptor)
            if child.poll() is None:child.kill()
            child.wait(timeout=2)
        return {'name':name,'ok':True}

    marker=work/'processes.json'
    descendant=("import os,time,json;from pathlib import Path;"
        "Path("+repr(str(marker))+").write_text(json.dumps([os.getpid()]));time.sleep(60)")
    spawn=("import subprocess,sys,time;from pathlib import Path;"
        "p=subprocess.Popen([sys.executable,'-c',"+repr(descendant)+"],start_new_session=True);"
        "limit=time.monotonic()+2\n"
        "while not Path("+repr(str(marker))+").exists() and time.monotonic()<limit:time.sleep(.001)\n"
        "print('ready',flush=True)\n")
    sender=None;old=None
    if name in ('success','shutdown-signals'):
        program="import sys;sys.stdout.buffer.write(b'complete\\n\\xff\\n')"
    elif name=='nonzero':
        program="import sys;sys.stderr.write('diagnostic\\n');raise SystemExit(7)"
    elif name in ('timeout','signals'):
        program=spawn+"time.sleep(60)"
    elif name in ('unresponsive','failed-cleanup','raised-cleanup'):
        program=spawn
    else:raise ValueError(name)
    module=target
    if name=='shutdown-signals':
        content=Path(target).read_text()
        anchor=' return 0\n\n\ndef unfinished_scope(folder):'
        injected=(' os.kill(os.getpid(),signal.SIGINT)\n'
                  ' os.kill(os.getpid(),signal.SIGTERM)\n'
                  ' assert {signal.SIGINT,signal.SIGTERM} <= signal.sigpending()\n'
                  +anchor)
        require(content.count(anchor)==1,'actual worker return anchor changed')
        module=work/'worker_shutdown_control.py';module.write_text(content.replace(anchor,injected))
        scope=load(module)
    if name in ('unresponsive','failed-cleanup','raised-cleanup'):
        content=Path(target).read_text()
        anchor="    cleanup=_drain_owned(request['cleanup_timeout'])"
        if name=='unresponsive':
            replacement="    time.sleep(60)\n"+anchor
        elif name=='raised-cleanup':
            replacement="    raise RuntimeError('injected cleanup exception')"
        else:
            replacement="    cleanup={'ok':False,'remaining':[],'reaped':[],'reason':'injected cleanup failure'}"
        require(content.count(anchor)==1,'actual worker defect anchor changed')
        module=work/'worker_control.py';module.write_text(content.replace(anchor,replacement))
        compile(module.read_text(),str(module),'exec')
        scope=load(module)
        scope._SUPERVISOR_SLACK=.2
    if name=='signals':
        old=signal.signal(signal.SIGINT,lambda sig,frame:None)
        sender_code=("import os,time,signal;time.sleep(.1)\n"
                     "for i in range(20):\n"
                     " os.kill("+str(os.getpid())+",signal.SIGINT);time.sleep(.005)\n")
        sender=subprocess.Popen([sys.executable,'-c',sender_code])
    unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
    caller_mask=signal.pthread_sigmask(signal.SIG_BLOCK,[])
    caller_handlers={sig:signal.getsignal(sig) for sig in (signal.SIGINT,signal.SIGTERM)}
    started=time.monotonic()
    try:
        result=scope.invoke([sys.executable,'-c',program],work/'invocation',work,environment,
                            .25 if name not in ('success','nonzero','shutdown-signals') else 3,
                            grace=.1,cleanup_timeout=1)
        if sender is not None:sender.wait(timeout=3)
        require(signal.pthread_sigmask(signal.SIG_BLOCK,[])==caller_mask
                and all(signal.getsignal(sig)==handler for sig,handler in caller_handlers.items()),
                'invocation changed caller signal mask or handlers')
        require(unrelated.poll() is None,'unrelated caller child was consumed or killed')
        require(time.monotonic()-started<8,'real metadata command exceeded cleanup bound')
        require(not (work/'invocation'/'supervisor-stderr').read_bytes(),
                'scope supervisor emitted unexpected diagnostics')
        if name in ('success','shutdown-signals'):
            require(result['status']==0 and result['cleanup']['ok'],'successful command failed')
            require((work/'invocation'/'stdout').read_bytes()==b'complete\n\xff\n',
                    'full byte output was not preserved')
        elif name=='nonzero':
            require(result['status']==7 and result['cleanup']['ok'],'nonzero status was lost')
            require((work/'invocation'/'stderr').read_bytes()==b'diagnostic\n','stderr was discarded')
        elif name in ('timeout','signals'):
            require(result['status']=='timeout' if name=='timeout' else str(result['status']).startswith('signal-'),
                    'timeout or caller signal became success')
            require(result['cleanup']['ok'],'ordinary cancellation did not prove ECHILD')
        else:
            forced=result.get('forced_cleanup',{})
            require(result['status']!=0 and result['cleanup']['ok'] is False,
                    'forced cleanup became successful evidence')
            require(forced.get('ok') and forced.get('supervisor_reaped'),
                    'forced cleanup did not prove scoped exits and supervisor reap')
            require(len(forced.get('descendants',[]))>=1,'forced cleanup missed detached descendant')
        if marker.exists():
            for pid in json.loads(marker.read_text()):
                proc=Path('/proc',str(pid),'stat')
                if name in ('unresponsive','failed-cleanup','raised-cleanup') and proc.exists():
                    require(proc.read_text().rsplit(')',1)[1].split()[0] in ('Z','X'),
                            'detached descendant is still executing after forced cleanup')
                else:
                    require(not proc.exists(),'detached descendant survived or was not reaped')
        return {'name':name,'ok':True,'status':result['status']}
    finally:
        if sender is not None and sender.poll() is None:
            sender.kill();sender.wait(timeout=2)
        if old is not None:signal.signal(signal.SIGINT,old)
        unrelated.kill();unrelated.wait(timeout=2)


def main():
    if len(sys.argv)==5 and sys.argv[1]=='--control':
        result=control(sys.argv[2],Path(sys.argv[3]),Path(sys.argv[4]))
        print(json.dumps(result));return
    guard=load(HERE/'metadata_scope.py')
    source=(HERE/'metadata_scope.py').read_text()
    modes=('ready-stream','child-stream','no-children','success','nonzero','timeout','signals','shutdown-signals',
           'unresponsive','failed-cleanup','raised-cleanup','root-gone','cache-env','finite-cleanup')
    with tempfile.TemporaryDirectory(prefix='paslang-metadata-scope-') as scratch:
        root=Path(scratch)
        def invoke(name,target,tag):
            work=root/tag;work.mkdir()
            result=guard.invoke([sys.executable,str(Path(__file__).resolve()),'--control',name,str(target),str(work)],
                                root/(tag+'-scope'),root,dict(os.environ),12,grace=.2,cleanup_timeout=2)
            require(result.get('cleanup',{}).get('ok'),'test observer failed to reap owned children')
            marker=work/'processes.json'
            if marker.exists():
                for pid in json.loads(marker.read_text()):
                    require(not Path('/proc',str(pid)).exists(),'test observer left an unreaped descendant')
            return result,(root/(tag+'-scope')/'stderr').read_text()
        for name in modes:
            result,error=invoke(name,HERE/'metadata_scope.py','positive-'+name)
            require(result['program_status']==0,'positive '+name+' failed: '+json.dumps(result)+' '+error)
        mutations=(
            ('shutdown-mask','shutdown-signals',
             "  signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGINT,signal.SIGTERM})\n",
             ""),
            ('ready-deadline','ready-stream',
             "  while True:\n   if expired():return incomplete()\n   try:pid,status=os.waitpid(-1,os.WNOHANG)",
             "  while True:\n   try:pid,status=os.waitpid(-1,os.WNOHANG)"),
            ('child-deadline','child-stream',
             "  for pid in _children():\n   if expired():return incomplete()\n",
             "  for pid in _children():\n"),
            ('forced-kill','unresponsive',
             "   for fd in [*(row['fd'] for row in bound.values()),descriptor]:",
             "   for fd in []:"),
            ('raised-cleanup-handoff','raised-cleanup',
             "   except BaseException as caught:\n    cleanup={'ok':False,'remaining':None,'reaped':[],\n             'error':type(caught).__name__+': '+str(caught)}",
             "   except BaseException as caught:\n    raise"),
            ('forced-success','unresponsive',
             "   result['cleanup']={'ok':False,'reason':'forced cleanup; invocation remains failed'}",
             "   result['cleanup']={'ok':True,'reason':'forced cleanup; invocation remains failed'}"),
            ('finite-wait','finite-cleanup',
             "    events=poller.poll(max(1,math.ceil(min(1.0,max(0.0,deadline-time.monotonic()))*1000)))",
             "    events=poller.poll(max(1,math.ceil((deadline-time.monotonic())*1000)))"),
            ('cache-controls','cache-env',
             "CONTROL_KEYS=('GOARCH','GOOS','GOFLAGS','GOWORK','GO111MODULE','GOCACHE','GOFMAHASH',\n 'GOROOT','GOENV'",
             "CONTROL_KEYS=('GOROOT','GOENV'"),
        )
        for name,mode,anchor,replacement in mutations:
            require(source.count(anchor)==1,'mutant anchor changed: '+name)
            path=root/(name+'.py');path.write_text(source.replace(anchor,replacement))
            compile(path.read_text(),str(path),'exec')
            result,error=invoke(mode,path,'mutant-'+name)
            require(result['program_status']!=0 and 'metadata scope control:' in error,
                    'actual-source mutant was not caught by its intended oracle: '+name+' '+json.dumps(result)+' '+error)
    print('check_metadata_scope: fourteen compiler-free groups; eight actual-source mutants; '
          'full byte output/status; bounded ready streams; detached timeout/signal/forced cleanup; '
          'supervisor reap, caller signals and unrelated children')


if __name__=='__main__':main()
