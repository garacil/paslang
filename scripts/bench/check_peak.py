#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P525: real traced-process outcomes, deadlines and cleanup (no compilers).

Run beside peak.py. These probes observe the child from outside the tracing
algorithm; a failed assertion is an actual harness contract violation.
"""
import contextlib
import ctypes
import io
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
import time
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import peak


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def captured(command, **options):
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        answer = peak.peak_kib(command, stdout=out.fileno(), stderr=err.fileno(), **options)
        out.seek(0)
        err.seek(0)
        return answer, out.read(), err.read()


def reaped(pid):
    try:
        got, _ = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        require(not Path('/proc', str(pid)).exists(), 'sample PID still exists after reap')
        return
    raise AssertionError('sample was not reaped by peak_kib: ' + str((pid, got)))


def main():
    module_path=Path(peak.__file__).resolve()
    require(module_path==Path(__file__).resolve().with_name('peak.py'),'checker imported the wrong sampler source')
    source_hash=hashlib.sha256(module_path.read_bytes()).hexdigest()
    rows = []
    with tempfile.TemporaryDirectory(prefix='peak-check-') as folder:
        work = Path(folder)
        (kib, code), out, err = captured(['/bin/sh', '-c',
            "printf 'first\\nlast\\n'; printf '\\377' >&2"], timeout=3)
        require(code == 0 and kib > 0 and out == b'first\nlast\n' and err == b'\xff',
                'success status, full stdout/stderr or positive VmHWM differs')
        rows.append({'case': 'full-output', 'peak_kib': kib, 'status': code})

        # A later exec produces a ptrace event, whereas an ordinary
        # SIGTRAP remains a signal delivered to the sample. Neither may
        # silently turn into the other.
        (kib, code), out, _ = captured(['/bin/sh', '-c',
            'exec /bin/echo after-exec'], timeout=3)
        require(code == 0 and kib > 0 and out == b'after-exec\n',
                'later exec event was injected as SIGTRAP or lost its output')
        rows.append({'case': 'successful-reexec', 'peak_kib': kib, 'status': code})

        for name, shell, expected in [('nonzero', 'exit 7', 7),
                                       ('signal', 'kill -TERM $$', -signal.SIGTERM),
                                       ('real-trap', 'ulimit -c 0; kill -TRAP $$', -signal.SIGTRAP)]:
            (kib, code), _, _ = captured(['/bin/sh', '-c', shell], timeout=3)
            require(code == expected and kib > 0, name + ' status was lost')
            rows.append({'case': name, 'peak_kib': kib, 'status': code})

        # Keep a real exited child waitable with WNOWAIT. Even its ready
        # status must not be consumed by a wait whose deadline has expired
        # (Linux waitid(2)); this does not depend on scheduler timing.
        pid = os.fork()
        if pid == 0:
            os._exit(17)
        try:
            until = time.monotonic() + 3
            while os.waitid(os.P_PID, pid, os.WEXITED | os.WNOWAIT | os.WNOHANG) is None:
                require(time.monotonic() < until, 'deadline fixture child did not exit')
                time.sleep(0.002)
            try:
                peak._wait_until(pid, time.monotonic() - 1)
            except peak._Deadline:
                pass
            else:
                raise AssertionError('ready child status was accepted after the deadline')
        finally:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass
        rows.append({'case': 'ready-child-expired-deadline'})

        pidfile = work / 'sleeper.pid'
        began = time.monotonic()
        (kib, code), _, _ = captured(['/bin/sh', '-c',
            'echo $$ > "$1"; exec /bin/sleep 60', 'sample', str(pidfile)], timeout=0.15)
        elapsed = time.monotonic() - began
        require((kib, code) == (-1, 'timeout') and elapsed < 3,
                'running tracee timeout was not bounded/invalidated')
        reaped(int(pidfile.read_text()))
        rows.append({'case': 'execution-timeout', 'elapsed_s': elapsed, 'status': code})

        # The deadline must start before exec. An injected exec stall is an
        # ordinary forked child, with no initial ptrace exec-stop yet.
        pidfile = work / 'preexec.pid'
        def stall_exec(*arguments):
            pidfile.write_text(str(os.getpid()))
            time.sleep(60)
        began = time.monotonic()
        with patch.object(peak.os, 'execv', stall_exec):
            (kib, code), _, _ = captured(['/bin/true'], timeout=0.15)
        elapsed = time.monotonic() - began
        require((kib, code) == (-1, 'timeout') and elapsed < 3,
                'pre-exec tracee timeout was not bounded/invalidated')
        reaped(int(pidfile.read_text()))
        rows.append({'case': 'preexec-timeout', 'elapsed_s': elapsed, 'status': code})

        for exception in (RuntimeError, KeyboardInterrupt):
            seen_file = work / ('hwm-' + exception.__name__ + '.pid')
            def fail_hwm(pid):
                seen_file.write_text(str(pid))
                raise exception('injected VmHWM reader failure')
            with patch.object(peak, '_hwm_kib', fail_hwm):
                try:
                    captured(['/bin/true'], timeout=3)
                except exception as error:
                    require(str(error) == 'injected VmHWM reader failure',
                            'parent exception was masked during cleanup')
                else:
                    raise AssertionError('injected RSS failure did not propagate')
            require(seen_file.exists(), 'RSS failure did not reach real exit-stop')
            reaped(int(seen_file.read_text()))
            rows.append({'case': 'rss-failure-cleanup', 'exception': exception.__name__})

        seen_file = work / 'options.pid'
        real_ptrace = peak._ptrace
        def fail_options(request, pid, data):
            if request == peak.PTRACE_SETOPTIONS:
                seen_file.write_text(str(pid))
                raise RuntimeError('injected trace options failure')
            return real_ptrace(request, pid, data)
        with patch.object(peak, '_ptrace', fail_options):
            try:
                captured(['/bin/true'], timeout=3)
            except RuntimeError as error:
                require(str(error) == 'injected trace options failure',
                        'trace setup exception was masked during cleanup')
            else:
                raise AssertionError('injected trace setup failure did not propagate')
        require(seen_file.exists(), 'trace setup failure did not reach real exec stop')
        reaped(int(seen_file.read_text()))
        rows.append({'case': 'trace-setup-failure-cleanup'})

        # A test-only subreaper lets this observer wait for the orphaned
        # grandchild and prove group cleanup, without leaving it for init.
        # Linux PR_SET_CHILD_SUBREAPER(2const): adoption is local to us and
        # this attribute is not inherited across fork.
        saved_subreaper = ctypes.c_int()
        require(peak._libc.prctl(37, ctypes.addressof(saved_subreaper), 0, 0, 0) == 0,
                'cannot read observer subreaper setting')
        require(peak._libc.prctl(36, 1, 0, 0, 0) == 0,
                'cannot enable observer subreaper')
        main_file, child_file = work / 'group-main.pid', work / 'group-child.pid'
        descendant = None
        try:
            program = ("import os,time\nfrom pathlib import Path\n"
                       "child=os.fork()\n"
                       "if child==0:\n"
                       " Path(" + repr(str(child_file)) + ").write_text(str(os.getpid()))\n"
                       "else:\n"
                       " Path(" + repr(str(main_file)) + ").write_text(str(os.getpid()))\n"
                       "time.sleep(60)\n")
            (kib, code), _, _ = captured([sys.executable, '-c', program], timeout=0.5)
            require((kib, code) == (-1, 'timeout'), 'process-group sample did not time out')
            reaped(int(main_file.read_text()))
            descendant = int(child_file.read_text())
            require(not Path('/proc',str(descendant)).exists(), 'timed-out sample left a running descendant')
            try:
                os.waitpid(descendant,os.WNOHANG)
            except ChildProcessError:
                pass
            else:
                raise AssertionError('sampler did not reap its own descendant')
            descendant = None
            rows.append({'case': 'process-group-timeout', 'descendant_status': 'gone and worker-reaped'})
        finally:
            if descendant is not None:
                try:
                    os.kill(descendant, signal.SIGKILL)
                    os.waitpid(descendant, 0)
                except ProcessLookupError:
                    pass
            require(peak._libc.prctl(36, saved_subreaper.value, 0, 0, 0) == 0,
                    'cannot restore observer subreaper setting')

        # Every touched parent page is inherited at fork. A wait4 ru_maxrss
        # result would retain that high-water mark even after exec, whereas
        # the small executable's own /proc VmHWM excludes it.
        parent = bytearray(64 * 1024 * 1024)
        for index in range(0, len(parent), 4096):
            parent[index] = 1
        (kib, code), _, _ = captured(['/bin/true'], timeout=3)
        require(code == 0 and 0 < kib < len(parent) // 4096,
                'launcher memory contaminated small executable VmHWM')
        rows.append({'case': 'launcher-rss-excluded', 'peak_kib': kib,
                     'parent_touched_kib': len(parent) // 1024})
        del parent

        for timeout in (0, -1, math.nan, math.inf):
            with patch.object(peak.os, 'fork', side_effect=AssertionError('invalid timeout forked')):
                try:
                    peak.peak_kib(['/bin/true'], timeout=timeout)
                except ValueError:
                    pass
                else:
                    raise AssertionError('nonpositive/nonfinite timeout accepted')
        rows.append({'case': 'invalid-timeout-rejected', 'values': ['0', '-1', 'nan', 'inf']})

        (kib,code),out,err=captured(['/bin/true'],timeout=1e100)
        require(code==0 and kib>0 and not out and not err,'large finite deadline overflowed kernel wait')
        rows.append({'case':'large-finite-deadline'})

        # A real signal-delivery stop per iteration. A 2 ms polling observer
        # turns this short program into a timeout. The child requires every
        # SIGURG handler invocation before announcing its exact total.
        program = ("import os,signal\ncount=0\n"
                   "def received(*args):\n global count\n count+=1\n"
                   "signal.signal(signal.SIGURG,received)\n"
                   "for index in range(2000):os.kill(os.getpid(),signal.SIGURG)\n"
                   "print(count)\n")
        (kib, code), out, err = captured([sys.executable,'-c',program],timeout=2)
        require(code==0 and kib>0 and out==b'2000\n' and not err,
                'rapid SIGURG forwarding/progress failed')
        rows.append({'case':'rapid-sigurg','signals':2000,'status':code})

        # Caller state is independent of the sampler's signalfd/subreaper.
        # The target must see exec-equivalent ignored dispositions and the
        # original mask, not the worker's private blocked signal set.
        alarm_events=[]
        def alarm(sig,frame):alarm_events.append(sig)
        old_alarm=signal.getsignal(signal.SIGALRM)
        old_usr1=signal.getsignal(signal.SIGUSR1)
        old_mask=signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGUSR2})
        wake_read,wake_write=os.pipe2(os.O_NONBLOCK|os.O_CLOEXEC)
        old_wakeup=signal.set_wakeup_fd(wake_write)
        old_timer=signal.getitimer(signal.ITIMER_REAL)
        try:
            require(old_timer==(0.,0.),'state fixture requires a fresh interval timer')
            signal.signal(signal.SIGUSR1,signal.SIG_IGN)
            signal.signal(signal.SIGALRM,alarm)
            signal.setitimer(signal.ITIMER_REAL,.01,.01)
            expected_mask=signal.pthread_sigmask(signal.SIG_BLOCK,set())
            program=("import signal,time\n"
                     "mask=signal.pthread_sigmask(signal.SIG_BLOCK,set())\n"
                     "print(signal.SIGUSR2 in mask,signal.SIGURG in mask,signal.getsignal(signal.SIGUSR1)==signal.SIG_IGN)\n"
                     "time.sleep(.12)\n")
            (kib,code),out,err=captured([sys.executable,'-c',program],timeout=2)
            require(code==0 and kib>0 and out==b'True False True\n' and not err,
                    'tracee inherited sampler signal state')
            require(signal.getsignal(signal.SIGALRM) is alarm and signal.getsignal(signal.SIGUSR1)==signal.SIG_IGN,
                    'caller signal handlers changed')
            require(signal.pthread_sigmask(signal.SIG_BLOCK,set())==expected_mask,'caller signal mask changed')
            timer=signal.getitimer(signal.ITIMER_REAL)
            require(timer[1]==.01 and 0<timer[0]<=.01 and len(alarm_events)>=3,'caller interval timer was reset or suppressed')
            saved=signal.set_wakeup_fd(-1);signal.set_wakeup_fd(wake_write)
            require(saved==wake_write and bytes([signal.SIGALRM]) in os.read(wake_read,4096),'caller wakeup fd was replaced or disabled')
            rows.append({'case':'caller-state-preserved','timer_events':len(alarm_events)})
        finally:
            signal.setitimer(signal.ITIMER_REAL,0)
            signal.set_wakeup_fd(old_wakeup)
            signal.signal(signal.SIGALRM,old_alarm)
            signal.signal(signal.SIGUSR1,old_usr1)
            signal.pthread_sigmask(signal.SIG_SETMASK,old_mask)
            os.close(wake_read);os.close(wake_write)

        child_events=[]
        def child_signal(sig,frame):child_events.append(sig)
        old_child=signal.signal(signal.SIGCHLD,child_signal)
        unrelated=os.fork()
        if unrelated==0:
            time.sleep(.03);os._exit(41)
        try:
            (kib,code),out,err=captured([sys.executable,'-c','import time;time.sleep(.08);print("own child")'],timeout=2)
            require(code==0 and kib>0 and out==b'own child\n' and not err,'sample with unrelated child failed')
            got,status=os.waitpid(unrelated,0);unrelated=None
            require(os.waitstatus_to_exitcode(status)==41 and child_events and signal.getsignal(signal.SIGCHLD) is child_signal,
                    'sampler stole unrelated child status or replaced SIGCHLD handler')
            rows.append({'case':'unrelated-child-and-sigchld-handler','unrelated_status':41})
        finally:
            if unrelated is not None:
                try:os.kill(unrelated,signal.SIGKILL)
                except ProcessLookupError:pass
                try:os.waitpid(unrelated,0)
                except ChildProcessError:pass
            signal.signal(signal.SIGCHLD,old_child)

        # A caller reaper may consume the helper's wait status. The target
        # status and cleanup still come from its complete sampler receipt.
        helper_reaps=[]
        def reap_helper(sig,frame):
            while True:
                try:got,status=os.waitpid(-1,os.WNOHANG)
                except ChildProcessError:return
                if not got:return
                helper_reaps.append((got,status))
        old_child=signal.signal(signal.SIGCHLD,reap_helper)
        try:
            (kib,code),out,err=captured(['/bin/echo','caller-reaped-helper'],timeout=2)
            require(code==0 and kib>0 and out==b'caller-reaped-helper\n' and not err and helper_reaps,
                    'caller reaper lost sampler target/cleanup evidence')
            require(signal.getsignal(signal.SIGCHLD) is reap_helper,'caller reaper handler changed')
            rows.append({'case':'caller-reaped-worker-receipt'})
        finally:signal.signal(signal.SIGCHLD,old_child)

        # Refuse fork-unsafe contexts before creating any helper or changing
        # masks/handlers. Refuse kernel auto-reaping even when Python's
        # cached getsignal value is still SIG_DFL.
        held=threading.Event();ready=threading.Event()
        def thread_wait():ready.set();held.wait()
        other=threading.Thread(target=thread_wait);other.start();ready.wait()
        try:
            with patch.object(peak.os,'fork',side_effect=AssertionError('unsupported context forked')):
                try:peak.peak_kib(['/bin/true'],timeout=1)
                except RuntimeError as error:require('single-threaded' in str(error),'wrong unsupported-thread error')
                else:raise AssertionError('multithreaded caller accepted')
        finally:held.set();other.join()
        action=peak._SignalAction()
        require(peak._libc.sigaction(signal.SIGCHLD,None,ctypes.byref(action))==0,'cannot inspect SIGCHLD fixture')
        changed=peak._SignalAction();ctypes.memmove(ctypes.byref(changed),ctypes.byref(action),ctypes.sizeof(action));changed.flags|=2
        try:
            require(peak._libc.sigaction(signal.SIGCHLD,ctypes.byref(changed),None)==0,'cannot set no-child-wait fixture')
            with patch.object(peak.os,'fork',side_effect=AssertionError('auto-reap context forked')):
                try:peak.peak_kib(['/bin/true'],timeout=1)
                except RuntimeError as error:require('auto-reaping' in str(error),'wrong auto-reap error')
                else:raise AssertionError('auto-reaping caller accepted')
        finally:require(peak._libc.sigaction(signal.SIGCHLD,ctypes.byref(action),None)==0,'cannot restore SIGCHLD action')
        rows.append({'case':'unsupported-contexts-refused'})

        # The pidfd setup failure occurs before G authorizes tracee creation.
        # Closing the control pipe must still let the known worker exit/reap.
        helpers=[];real_fork=peak.os.fork
        def record_fork():
            pid=real_fork()
            if pid:helpers.append(pid)
            return pid
        with patch.object(peak.os,'fork',record_fork),patch.object(peak.os,'pidfd_open',side_effect=OSError(5,'injected pidfd setup failure')):
            try:captured(['/bin/true'],timeout=1)
            except OSError as error:require('injected pidfd setup failure' in str(error),'pidfd error was masked')
            else:raise AssertionError('pidfd setup failure was accepted')
        require(len(helpers)==1,'setup failure unexpectedly created a tracee')
        reaped(helpers[0]);rows.append({'case':'pidfd-startup-failure-cleanup'})

        before_fds=set(os.listdir('/proc/self/fd'));pipe_calls=[];real_pipe2=peak.os.pipe2
        def fail_second_pipe(flags):
            pipe_calls.append(1)
            if len(pipe_calls)==2:raise OSError(24,'injected second pipe failure')
            return real_pipe2(flags)
        with patch.object(peak.os,'pipe2',fail_second_pipe):
            try:captured(['/bin/true'],timeout=1)
            except OSError as error:require(error.errno==24,'pipe setup error was masked')
            else:raise AssertionError('pipe setup failure was accepted')
        require(set(os.listdir('/proc/self/fd'))==before_fds,'partial pipe setup leaked descriptors')
        rows.append({'case':'pipe-creation-failure-cleanup'})

        # Real SIGINT interrupts the caller while a deliberately slow cleanup
        # receives a second SIGINT. Detached descendants must still disappear.
        main_file,child_file=work/'int-main.pid',work/'int-child.pid'
        program=("import os,signal,time\nfrom pathlib import Path\n"
                 "signal.signal(signal.SIGINT,signal.SIG_IGN)\n"
                 "child=os.fork()\n"
                 "if child==0:\n os.setsid();Path("+repr(str(child_file))+").write_text(str(os.getpid()))\n"
                 "else:\n Path("+repr(str(main_file))+").write_text(str(os.getpid()))\n"
                 "while True:time.sleep(60)\n")
        caller=os.getpid();sender=os.fork()
        if sender==0:
            until=time.monotonic()+3
            while not child_file.exists() and time.monotonic()<until:time.sleep(.002)
            os.kill(caller,signal.SIGINT);time.sleep(.02);os.kill(caller,signal.SIGINT);os._exit(0)
        real_cleanup=peak._kill_reap
        def delayed_cleanup(pid):time.sleep(.1);return real_cleanup(pid)
        try:
            with patch.object(peak,'_kill_reap',delayed_cleanup):
                try:captured([sys.executable,'-c',program],timeout=3)
                except KeyboardInterrupt:pass
                else:raise AssertionError('real SIGINT did not interrupt the caller')
            require(not Path('/proc',main_file.read_text()).exists() and not Path('/proc',child_file.read_text()).exists(),
                    'SIGINT left a detached sample descendant')
            rows.append({'case':'sigint-repeat-detached-descendant-cleanup'})
        finally:
            os.waitpid(sender,0)

        # A permanently readable notification stream cannot evade its
        # absolute deadline. The synthetic stream is bounded by its own
        # assertion so even a missing-deadline mutant cannot hang the check.
        cancel_read,cancel_write=os.pipe2(os.O_CLOEXEC)
        notice=peak._Notifications(cancel_read)
        reads=[]
        def continuous_read(fd,size):
            require(fd==notice.fd,'stream fixture read unrelated descriptor')
            reads.append(1)
            if len(reads)>=1000000:raise AssertionError('stream drain ignored deadline')
            return int(signal.SIGCHLD).to_bytes(4,sys.byteorder)+bytes(124)
        try:
            with patch.object(peak,'_poll',return_value={notice.fd}),patch.object(peak.os,'read',continuous_read):
                try:notice.wait(time.monotonic()+.02)
                except peak._Deadline:pass
                else:raise AssertionError('continuous notification stream evaded deadline')
            require(reads,'continuous notification stream did not run')
            rows.append({'case':'continuous-notification-deadline'})
        finally:os.close(notice.fd);os.close(cancel_read);os.close(cancel_write)

        # Force the error-only supervisor fallback, with a deliberately hung
        # worker cleanup. The caller is a test-only subreaper so it can also
        # wait-reap descendants adopted after that defective worker dies.
        saved_subreaper=ctypes.c_int()
        require(peak._libc.prctl(37,ctypes.addressof(saved_subreaper),0,0,0)==0,'cannot inspect forced fixture subreaper')
        require(peak._libc.prctl(36,1,0,0,0)==0,'cannot set forced fixture subreaper')
        main_file,child_file=work/'forced-main.pid',work/'forced-child.pid'
        program=("import os,time\nfrom pathlib import Path\n"
                 "child=os.fork()\n"
                 "if child==0:\n os.setsid();Path("+repr(str(child_file))+").write_text(str(os.getpid()))\n"
                 "else:\n Path("+repr(str(main_file))+").write_text(str(os.getpid()))\n"
                 "while True:time.sleep(60)\n")
        helpers=[];real_fork=peak.os.fork
        def record_helper():
            pid=real_fork()
            if pid:helpers.append(pid)
            return pid
        def hung_cleanup(pid):time.sleep(60)
        try:
            with patch.object(peak,'_kill_reap',hung_cleanup),patch.object(peak,'_CLEANUP_SECONDS',.2),patch.object(peak.os,'fork',record_helper):
                try:captured([sys.executable,'-c',program],timeout=.1)
                except TimeoutError as error:require('forced cleanup; worker_reaped=True' in str(error),'forced cleanup lacked worker reap proof')
                else:raise AssertionError('hung worker cleanup was accepted')
            require(len(helpers)==1,'forced fixture did not record its worker')
            reaped(helpers[0])
            for path in (main_file,child_file):
                pid=int(path.read_text())
                try:got,status=os.waitpid(pid,os.WNOHANG)
                except ChildProcessError:require(not Path('/proc',str(pid)).exists(),'forced descendant survived')
                else:require(got==pid,'forced descendant was still running')
            rows.append({'case':'forced-worker-kill-reap-proof'})
            for path in (main_file,child_file):path.unlink()
            marker=work/'inside-forced-cleanup'
            signals_done=work/'forced-signals-complete'
            real_force_impl=peak._force_worker_impl
            def held_force_impl(*args):
                marker.write_text('inside force wrapper')
                until=time.monotonic()+2
                while not signals_done.exists():
                    require(time.monotonic()<until,'forced SIGINT stream did not finish')
                    time.sleep(.002)
                return real_force_impl(*args)
            caller=os.getpid();sender=os.fork()
            if sender==0:
                until=time.monotonic()+6
                while not marker.exists() and time.monotonic()<until:time.sleep(.002)
                if not marker.exists():os._exit(1)
                for index in range(20):os.kill(caller,signal.SIGINT);time.sleep(.005)
                signals_done.write_text('done')
                os._exit(0)
            original_mask=signal.pthread_sigmask(signal.SIG_BLOCK,set())
            before_fds=set(os.listdir('/proc/self/fd'));helpers=[]
            int_events=[]
            def first_interrupt(sig,frame):
                int_events.append(sig)
                if len(int_events)==1:raise KeyboardInterrupt
            old_int=signal.signal(signal.SIGINT,first_interrupt)
            def failed_drain(deadline):raise RuntimeError('injected owned cleanup failure')
            normal_exit_program=("import os,time\nfrom pathlib import Path\n"
                 "child=os.fork()\n"
                 "if child==0:\n os.setsid();Path("+repr(str(child_file))+").write_text(str(os.getpid()));time.sleep(60)\n"
                 "else:\n Path("+repr(str(main_file))+").write_text(str(os.getpid()))\n"
                 " while not Path("+repr(str(child_file))+").exists():time.sleep(.002)\n"
                 " os._exit(0)\n")
            try:
                with patch.object(peak,'_drain_owned',failed_drain),patch.object(peak,'_CLEANUP_SECONDS',.2),patch.object(peak.os,'fork',record_helper),patch.object(peak,'_force_worker_impl',held_force_impl):
                    try:captured([sys.executable,'-c',normal_exit_program],timeout=2)
                    except (TimeoutError,KeyboardInterrupt):pass
                    else:raise AssertionError('forced repeated-SIGINT cleanup was accepted')
                require(marker.exists(),'repeated SIGINT did not enter actual forced cleanup')
                require(signal.pthread_sigmask(signal.SIG_BLOCK,set())==original_mask,'forced cleanup changed caller mask')
                require(signal.getsignal(signal.SIGINT) is first_interrupt and int_events,'forced cleanup changed or lost caller handler')
                require(set(os.listdir('/proc/self/fd'))==before_fds,'forced repeated SIGINT leaked descriptors')
                require(len(helpers)==1,'repeated force fixture lost its helper')
                reaped(helpers[0])
                for path in (main_file,child_file):
                    pid=int(path.read_text())
                    try:got,status=os.waitpid(pid,os.WNOHANG)
                    except ChildProcessError:require(not Path('/proc',str(pid)).exists(),'forced SIGINT descendant survived')
                    else:require(got==pid,'forced SIGINT descendant was still running')
                rows.append({'case':'forced-cleanup-repeated-sigint','signals':20})
            finally:
                try:
                    got,status=os.waitpid(sender,0)
                    require(os.waitstatus_to_exitcode(status)==0,'forced SIGINT sender did not execute')
                finally:signal.signal(signal.SIGINT,old_int)

        finally:
            for path in (main_file,child_file):
                if path.exists():
                    pid=int(path.read_text())
                    try:os.kill(pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    try:os.waitpid(pid,0)
                    except ChildProcessError:pass
            require(peak._libc.prctl(36,saved_subreaper.value,0,0,0)==0,'cannot restore forced fixture subreaper')

        # A live pidfd may refer to an exited, already-reaped worker while
        # its old numeric PID denotes another child. Never walk/reap that
        # numeric root after pidfd SIGSTOP says the original process is gone.
        gate_read,gate_write=os.pipe2(os.O_CLOEXEC)
        old_worker=os.fork()
        if old_worker==0:
            os.close(gate_write);os.read(gate_read,1);os._exit(0)
        descriptor=os.pidfd_open(old_worker)
        os.write(gate_write,b'G');os.close(gate_read);os.close(gate_write);os.waitpid(old_worker,0)
        unrelated=os.fork()
        if unrelated==0:os._exit(41)
        walks=[];real_iterdir=Path.iterdir
        def record_root_walk(path):
            if str(path)=='/proc/'+str(unrelated)+'/task':walks.append(str(path))
            return real_iterdir(path)
        try:
            until=time.monotonic()+2
            while os.waitid(os.P_PID,unrelated,os.WEXITED|os.WNOWAIT|os.WNOHANG) is None:
                require(time.monotonic()<until,'unrelated ready fixture did not exit');time.sleep(.002)
            with patch.object(Path,'iterdir',record_root_walk):
                try:peak._force_worker(unrelated,descriptor)
                except TimeoutError as error:require('worker exited before descendant binding' in str(error),'gone-worker cleanup was not marked unproved')
                else:raise AssertionError('gone-worker escalation was accepted')
            require(not walks,'gone-worker pidfd walked a reused numeric root')
            got,status=os.waitpid(unrelated,0);unrelated=None
            require(os.waitstatus_to_exitcode(status)==41,'gone-worker escalation stole unrelated status')
            rows.append({'case':'gone-worker-numeric-root-not-used'})
        finally:
            os.close(descriptor)
            if unrelated is not None:
                try:os.waitpid(unrelated,0)
                except ChildProcessError:pass

        stderr = io.StringIO()
        with patch.object(peak, 'peak_kib', return_value=(-1, 'timeout')):
            with contextlib.redirect_stderr(stderr):
                code = peak.main()
        require(code == 1 and stderr.getvalue() == 'peak -1 KiB, exit status timeout\n',
                'CLI timeout was masked by formatting or status conversion')
        rows.append({'case': 'cli-timeout', 'status': code})
    require(hashlib.sha256(module_path.read_bytes()).hexdigest()==source_hash,'sampler source changed during check')
    print(json.dumps({'ok': True, 'peak_module':str(module_path),'peak_sha256':source_hash,'cases': rows}, indent=2))


if __name__ == '__main__':
    main()
