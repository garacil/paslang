#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version3 or later; see COPYING. No warranty.
"""Bounded metadata-command supervision; only this invocation owns children.

Each invocation gets a fresh single-threaded subreaper process. Its only
children come from that invocation. After the harness dies, separately
sessioned descendants are adopted here, then pidfd-killed and wait-reaped.
/proc children is an enumeration hint; only waitpid ECHILD proves completion.
Linux man-pages pidfd_open, pidfd_send_signal, wait, CHILD_SUBREAPER and
PDEATHSIG references are retained in coordinator-reference/.
"""
import contextlib
import ctypes
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import select
import shutil
import subprocess
import sys
import time

_SIGNALS=[]
_DEPTH=0
CONTROL_KEYS=('GOARCH','GOOS','GOFLAGS','GOWORK','GO111MODULE','GOCACHE','GOFMAHASH',
 'GOROOT','GOENV','GOEXPERIMENT','CGO_ENABLED','GODEBUG','GOGC','GOMEMLIMIT',
 'GOMAXPROCS','GOAMD64','GOTOOLCHAIN','GLIBC_TUNABLES','LD_HWCAP_MASK','RUST_STD_DETECT_UNSTABLE',
 'PASLANG_LIB','PASLANG_CPU','PASLANG_GC','PASLANG_GCSTRESS','PASLANG_GCPOISON','PASLANG_GCVERIFY',
 'PASLANG_GCWORKERS','PASLANG_ASYNCPREEMPTOFF','GCC_EXEC_PREFIX','COMPILER_PATH','LIBRARY_PATH',
 'LD_RUN_PATH','LD_LIBRARY_PATH','LD_PRELOAD','LD_AUDIT')


def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 temporary=path.with_name('.'+path.name+'.tmp')
 temporary.write_text(json.dumps(value,indent=2,ensure_ascii=True,allow_nan=False)+'\n')
 temporary.replace(path)


def process_identity(pid):
 try:
  fields=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()
  return {'pid':pid,'ppid':int(fields[1]),'start_time':int(fields[19]),
          'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
 except (FileNotFoundError,ProcessLookupError):return None


@contextlib.contextmanager
def signal_scope():
 global _DEPTH
 if _DEPTH:
  _DEPTH+=1
  try:yield
  finally:_DEPTH-=1
  return
 previous={sig:signal.getsignal(sig) for sig in (signal.SIGINT,signal.SIGTERM)}
 _SIGNALS.clear();_DEPTH=1
 def note(sig,frame):_SIGNALS.append(int(sig))
 for sig in previous:signal.signal(sig,note)
 try:yield
 finally:
  for sig,handler in previous.items():signal.signal(sig,handler)
  _DEPTH=0


def received_signals():return list(_SIGNALS)


def check_stop():
 if _SIGNALS:raise RuntimeError('coordinator signal requested stop: '+str(_SIGNALS))


def _prctl(option,value):
 libc=ctypes.CDLL(None,use_errno=True)
 libc.prctl.restype=ctypes.c_int
 if libc.prctl(ctypes.c_int(option),ctypes.c_ulong(value),ctypes.c_ulong(0),ctypes.c_ulong(0),ctypes.c_ulong(0)):
  error=ctypes.get_errno();raise OSError(error,os.strerror(error))


def _children():
 return [int(value) for value in Path('/proc/self/task',str(os.getpid()),'children').read_text().split()]


def _signal_owned_child(pid,sig):
 # In this fresh supervisor, unreaped children cannot recycle their PIDs.
 # SIGCHLD is DFL and no other thread/handler waits. The pidfd also binds
 # delivery to the exact kernel process, never a subsequently recycled PID.
 before=process_identity(pid)
 if before is None or before['ppid']!=os.getpid():return False
 fd=os.pidfd_open(pid,0)
 try:
  after=process_identity(pid)
  if after is None or after!=before:return False
  try:signal.pidfd_send_signal(fd,sig,None,0)
  except ProcessLookupError:return False
  return True
 finally:os.close(fd)


def _drain_owned(timeout):
 deadline=time.monotonic()+timeout;reaped=[];killed=[]
 def expired():
  return time.monotonic()>=deadline
 def incomplete():
  # Never enumerate an unbounded ready stream after its deadline. The lack
  # of ECHILD is itself sufficient to refuse a successful cleanup claim.
  return {'ok':False,'killed':sorted(set(killed)),'reaped':reaped,
          'remaining':None,'reason':'owned-child cleanup deadline expired before ECHILD'}
 while True:
  if expired():return incomplete()
  for pid in _children():
   if expired():return incomplete()
   try:
    if _signal_owned_child(pid,signal.SIGKILL):killed.append(pid)
   except ProcessLookupError:pass
  while True:
   if expired():return incomplete()
   try:pid,status=os.waitpid(-1,os.WNOHANG)
   except ChildProcessError:return {'ok':True,'killed':sorted(set(killed)),'reaped':reaped,'remaining':[]}
   if not pid:break
   reaped.append({'pid':pid,'status':status})
  if expired():return incomplete()
  time.sleep(min(0.005,max(0,deadline-time.monotonic())))


def _worker(request_path):
 request_path=Path(request_path);request=json.loads(request_path.read_text());folder=request_path.parent
 signal.signal(signal.SIGCHLD,signal.SIG_DFL)
 with signal_scope():
  _prctl(36,1) # PR_SET_CHILD_SUBREAPER; scoped to this fresh process.
  _prctl(1,signal.SIGTERM) # PR_SET_PDEATHSIG, followed by race check.
  if os.getppid()!=request['parent_pid']:_SIGNALS.append(int(signal.SIGTERM))
  scope=process_identity(os.getpid());save(folder/'scope.json',scope)
  started=time.monotonic();child=None;reason=None;error=None;program_status=None;leftovers=[]
  try:
   if _SIGNALS:reason='parent-or-signal-before-launch'
   else:
    with (folder/'stdout').open('wb') as stdout,(folder/'stderr').open('wb') as stderr:
     child=subprocess.Popen(request['command'],cwd=request['cwd'],env=os.environ,
                            stdout=stdout,stderr=stderr,start_new_session=True)
     save(folder/'harness.json',process_identity(child.pid))
     deadline=started+request['timeout']
     while child.poll() is None and not _SIGNALS and time.monotonic()<deadline:time.sleep(0.01)
     if child.returncode is None:
      reason='signal' if _SIGNALS else 'timeout'
      wanted=_SIGNALS[0] if _SIGNALS else int(signal.SIGINT)
      _signal_owned_child(child.pid,signal.SIGCONT)
      _signal_owned_child(child.pid,wanted)
      grace=time.monotonic()+request['grace']
      while child.poll() is None and time.monotonic()<grace:time.sleep(0.01)
      if child.returncode is None:_signal_owned_child(child.pid,signal.SIGKILL)
     # Do not block on wait here. Adopted descendants and a still-terminating
     # leader are killed/reaped together under one bounded kernel wait loop.
     program_status=child.poll()
     leftovers=_children()
  except BaseException as caught:
   error=type(caught).__name__+': '+str(caught);reason='supervisor-error'
  finally:
   try:
    cleanup=_drain_owned(request['cleanup_timeout'])
   except BaseException as caught:
    cleanup={'ok':False,'remaining':None,'reaped':[],
             'error':type(caught).__name__+': '+str(caught)}
   if child is not None and program_status is None:
    leader=next((row for row in cleanup['reaped'] if row['pid']==child.pid),None)
    if leader is not None:
     program_status=os.waitstatus_to_exitcode(leader['status']);child.returncode=program_status
   status=program_status if reason is None else ('signal-'+str(_SIGNALS[0]) if _SIGNALS else reason)
   if reason is None and leftovers:status='descendants-left-after-exit'
   if not cleanup['ok']:status='cleanup-failed'
   result={'status':status,'program_status':program_status,'reason':reason,'signals':list(_SIGNALS),
           'supervisor':scope,'cleanup':cleanup,'leftovers_before_cleanup':leftovers,
           'elapsed_s':time.monotonic()-started,'finished_utc':utc(),'error':error}
   save(folder/'worker-result.json',result)
   if not cleanup['ok']:
    # Retain ancestry until the controller can bind and kill this exact
    # scope. Exiting now would orphan the processes whose cleanup failed.
    hold=time.monotonic()+max(30,4*request['cleanup_timeout'])
    while time.monotonic()<hold and os.getppid()==request['parent_pid']:
     time.sleep(0.01)
  # The private worker is exiting after its receipt and cleanup. Block
  # cancellation before restoring handlers, through interpreter shutdown;
  # the separate caller still restores its own signal state normally.
  signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGINT,signal.SIGTERM})
 return 0


def unfinished_scope(folder):
 folder=Path(folder)
 identity_path=folder/'scope.json'
 if not identity_path.exists():identity_path=folder/'launched-supervisor.json'
 if not identity_path.exists():
  result=folder/'result.json'
  if result.exists() and json.loads(result.read_text()).get('supervisor_started') is False:return None
  return 'unfinished scope has no verifiable supervisor identity'
 retained=json.loads(identity_path.read_text());current=process_identity(retained['pid'])
 if current is not None and current['start_time']==retained['start_time'] and current['boot_id']==retained['boot_id']:
  return 'prior supervisor is still alive: '+str(retained['pid'])
 worker=folder/'worker-result.json'
 if not worker.exists():return 'prior scope did not retain a cleanup receipt'
 result=json.loads(worker.read_text())
 if not result.get('cleanup',{}).get('ok'):return 'prior scope did not prove complete kill/reap'
 return None


def tool_identity(command,env):
 executable=shutil.which(str(command),path=env['PATH'])
 if executable is None:return None
 path=Path(executable)
 return {'invocation_path':str(path.absolute()),'resolved_path':str(path.resolve()),
         'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def validate_receipt(folder,command,cwd,env,*,require_success=False):
 folder=Path(folder)
 request=json.loads((folder/'invocation.json').read_text())
 result=json.loads((folder/'result.json').read_text())
 if request.get('command')!=list(map(str,command)) or request.get('cwd')!=str(cwd):
  raise RuntimeError('cached metadata/receipt command or cwd changed: '+str(folder))
 if request.get('path')!=env['PATH'] or request.get('environment_controls')!={key:env[key] for key in CONTROL_KEYS if key in env}:
  raise RuntimeError('cached metadata/receipt environment changed: '+str(folder))
 if request.get('tool_identity')!=tool_identity(command[0],env):raise RuntimeError('cached metadata/receipt tool changed: '+str(folder))
 if require_success and result.get('status')!=0:raise RuntimeError('cached metadata did not succeed: '+str(folder))
 pending=unfinished_scope(folder)
 if pending:raise RuntimeError(pending)
 for name in ('stdout','stderr'):
  path=folder/name;retained=result.get(name,{})
  if retained.get('bytes')!=path.stat().st_size or retained.get('sha256')!=hashlib.sha256(path.read_bytes()).hexdigest():
   raise RuntimeError('cached metadata/receipt bytes changed: '+str(path))
 return result


def cached_metadata(command,folder,cwd,env,timeout=60):
 folder=Path(folder)
 if folder.exists():return validate_receipt(folder,command,cwd,env,require_success=True)
 result=invoke(command,folder,cwd,env,timeout)
 if result.get('status')!=0:raise RuntimeError('metadata discovery failed: '+str(folder))
 return result


_SUPERVISOR_SLACK=15.0


def _force_scope(supervisor,descriptor,timeout):
 """Bind an owned stopped ancestry, kill it, and reap only our supervisor.

 Forced cleanup always leaves the invocation failed. PID descriptors bind
 every signal; numeric /proc discovery is allowed only while the bound
 supervisor still exists. Stopping all discovered tasks before another
 scan prevents a descendant from forking after the closure was observed.
 """
 original_mask=signal.pthread_sigmask(signal.SIG_BLOCK,signal.valid_signals()-{signal.SIGKILL,signal.SIGSTOP})
 bound={};issues=[];root=None;complete=False;reaped=False
 deadline=time.monotonic()+timeout
 def ready(fd):
  poller=select.poll();poller.register(fd,select.POLLIN)
  return bool(poller.poll(0))
 def check():
  if time.monotonic()>=deadline:raise TimeoutError('forced scope discovery deadline')
 def stopped(pid):
  for task in Path('/proc',str(pid),'task').iterdir():
   check()
   state=(task/'stat').read_text().rsplit(')',1)[1].split()[0]
   if state not in ('T','t','Z','X'):return False
  return True
 try:
  try:
   # A successful pidfd signal alone is insufficient if poll() already
   # reaped the old root. Refuse numeric discovery after root exit.
   if supervisor.poll() is not None or ready(descriptor):
    raise ProcessLookupError('bound supervisor already exited; ancestry unproved')
   root=process_identity(supervisor.pid)
   if root is None:raise ProcessLookupError('missing bound supervisor identity')
   signal.pidfd_send_signal(descriptor,signal.SIGSTOP,None,0)
   while True:
    check()
    if ready(descriptor):raise ProcessLookupError('bound supervisor exited during discovery')
    current=process_identity(supervisor.pid)
    if current is None or current!=root:raise ProcessLookupError('bound supervisor identity changed')
    pending=[supervisor.pid];seen=set();added=False;all_stopped=True
    while pending:
     check();parent=pending.pop()
     if parent in seen:continue
     seen.add(parent)
     fd=descriptor if parent==supervisor.pid else bound[parent]['fd']
     if ready(fd):continue
     if not stopped(parent):
      all_stopped=False
      continue
     for task in Path('/proc',str(parent),'task').iterdir():
      check()
      try:children=[int(value) for value in (task/'children').read_text().split()]
      except FileNotFoundError:continue
      for child in children:
       check()
       if child not in bound:
        child_fd=None
        try:
         before=process_identity(child)
         if before is None or before['ppid']!=parent:continue
         child_fd=os.pidfd_open(child,0)
         after=process_identity(child)
         if before!=after:continue
         signal.pidfd_send_signal(child_fd,signal.SIGSTOP,None,0)
         bound[child]={'fd':child_fd,'identity':after};child_fd=None;added=True
        except (ProcessLookupError,FileNotFoundError):continue
        finally:
         if child_fd is not None:os.close(child_fd)
       pending.append(child)
    if all_stopped and not added:
     complete=True
     break
    time.sleep(min(0.001,max(0,deadline-time.monotonic())))
  except BaseException as error:
   issues.append(type(error).__name__+': '+str(error))
  finally:
   # No user handler can interrupt these loops; restore the exact caller
   # mask after killing/reaping and closing every owned descriptor.
   for fd in [*(row['fd'] for row in bound.values()),descriptor]:
    try:signal.pidfd_send_signal(fd,signal.SIGKILL,None,0)
    except ProcessLookupError:pass
   remaining={descriptor,*(row['fd'] for row in bound.values())}
   deadline=time.monotonic()+timeout
   while remaining and time.monotonic()<deadline:
    poller=select.poll()
    for fd in remaining:poller.register(fd,select.POLLIN)
    events=poller.poll(max(1,math.ceil(min(1.0,max(0.0,deadline-time.monotonic()))*1000)))
    remaining.difference_update(fd for fd,event in events if event & select.POLLIN)
   try:supervisor.wait(timeout=max(0.001,deadline-time.monotonic()));reaped=True
   except subprocess.TimeoutExpired:issues.append('supervisor reap deadline')
   if remaining:issues.append('bound process exit unproved')
   for row in bound.values():os.close(row['fd'])
  return {'ok':complete and reaped and not remaining and not issues,'forced':True,
          'discovery_complete':complete,'supervisor':root,'supervisor_reaped':reaped,
          'descendants':[row['identity'] for row in bound.values()],
          'unproved_exit_descriptors':len(remaining),'issues':issues}
 finally:
  signal.pthread_sigmask(signal.SIG_SETMASK,original_mask)


def invoke(command,folder,cwd,env,timeout,*,grace=2.0,cleanup_timeout=5.0):
 if not all(isinstance(value,(int,float)) and math.isfinite(value) and value>0 for value in (timeout,grace,cleanup_timeout)):
  raise ValueError('invocation/grace/cleanup deadlines must be positive and finite')
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
 request={'command':list(map(str,command)),'cwd':str(cwd),'started_utc':utc(),
          'environment_controls':{key:env[key] for key in CONTROL_KEYS if key in env},
          'path':env['PATH'],'timeout':timeout,'grace':grace,'cleanup_timeout':cleanup_timeout,
          'parent_pid':os.getpid(),'tool_identity':tool_identity(command[0],env)}
 save(folder/'invocation.json',request)
 started=time.monotonic();supervisor=None;fd=None;failure=None;forced=None
 with signal_scope():
  try:
   if _SIGNALS:failure='signal-before-launch'
   else:
    launcher=[sys.executable,str(Path(__file__).resolve()),'--supervise',str(folder/'invocation.json')]
    save(folder/'supervisor-command.json',launcher)
    with (folder/'supervisor-stdout').open('wb') as stdout,(folder/'supervisor-stderr').open('wb') as stderr:
     supervisor=subprocess.Popen(launcher,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
     save(folder/'launched-supervisor.json',process_identity(supervisor.pid))
     fd=os.pidfd_open(supervisor.pid,0);forwarded=0
     outer_deadline=started+timeout+grace+cleanup_timeout+_SUPERVISOR_SLACK
     while supervisor.poll() is None:
      if len(_SIGNALS)>forwarded:
       try:
        signal.pidfd_send_signal(fd,signal.SIGCONT,None,0)
        signal.pidfd_send_signal(fd,_SIGNALS[-1],None,0)
       except ProcessLookupError:pass
       forwarded=len(_SIGNALS)
      receipt=folder/'worker-result.json'
      if receipt.exists() and json.loads(receipt.read_text()).get('cleanup',{}).get('ok') is False:
       failure='supervisor-cleanup-failed'
       break
      if time.monotonic()>=outer_deadline:
       failure='supervisor-unresponsive'
       break
      time.sleep(0.01)
  except BaseException as error:
   failure=type(error).__name__+': '+str(error)
  finally:
   if supervisor is not None and supervisor.poll() is None:
    if fd is None:fd=os.pidfd_open(supervisor.pid,0)
    forced=_force_scope(supervisor,fd,cleanup_timeout)
    save(folder/'forced-cleanup.json',forced)
    failure=failure or 'forced-supervisor-cleanup'
   if fd is not None:os.close(fd)
  result_path=folder/'worker-result.json'
  if result_path.exists():result=json.loads(result_path.read_text())
  else:result={'status':failure or 'supervisor-failed','cleanup':{'ok':False},'error':failure}
  if supervisor is not None and supervisor.poll() is None:
   result.update(status='supervisor-unresponsive',error='scoped supervisor still running; resume refused')
  elif supervisor is not None and supervisor.returncode!=0 and forced is None:
   result.update(status='supervisor-failed',error='scoped supervisor exit '+str(supervisor.returncode))
  if failure:result.update(status=failure,error=failure)
  if forced is not None:
   result['forced_cleanup']=forced
   result['cleanup']={'ok':False,'reason':'forced cleanup; invocation remains failed'}
  if _SIGNALS:result['status']='signal-'+str(_SIGNALS[0])
  result.update(supervisor_started=supervisor is not None,
                command=request['command'],cwd=request['cwd'],started_utc=request['started_utc'],
                elapsed_s=time.monotonic()-started,finished_utc=utc(),received_signals=list(_SIGNALS))
  for name in ('stdout','stderr'):
   path=folder/name
   if not path.exists():path.write_bytes(b'')
   result[name]={'path':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
  save(folder/'result.json',result)
  return result


if __name__=='__main__':
 if len(sys.argv)==3 and sys.argv[1]=='--supervise':raise SystemExit(_worker(sys.argv[2]))
 raise SystemExit('metadata_scope is imported by the CPU capability metadata probe')
