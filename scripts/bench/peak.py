#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
#
# paslang is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# paslang is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with paslang.  If not, see <https://www.gnu.org/licenses/>.

"""Trace an executable's own VmHWM with immediate, deadline-bounded waits.

A fresh, single-threaded sampler owns SIGCHLD/signalfd and a child subreaper.
The caller's handlers, mask, interval timers, wakeup fd and unrelated children
are never used for notification. Only a short fork/pidfd setup blocks caller
signals, restoring the exact original mask before execution is observed.

The tracee receives exec-equivalent original dispositions and the original
mask; every delivery-stop signal is forwarded unchanged. PTRACE_EVENT_EXEC
and PTRACE_EVENT_EXIT are notifications, not signals to inject. VmHWM is read
at exit, with THP disabled as before. No polling delay slows Go preemption.

Linux only; multithreaded callers and SIGCHLD auto-reaping are rejected.
A caller SIGCHLD handler may observe/reap our worker; its complete receipt
binds the target result and cleanup independently of that notification. Setup
and execution share timeout; owned-child cleanup has a separate five-second
bound. Exceptions/SIGINT cancel the worker and wait for cleanup before escape.
See Linux signalfd(2), ptrace(2), pidfd_open(2), PR_SET_CHILD_SUBREAPER and
PR_SET_PDEATHSIG. The helper, not the caller, consumes SIGCHLD notifications.
"""
import ctypes
import errno
import json
import math
import os
from pathlib import Path
import select
import signal
import struct
import sys
import time

PTRACE_TRACEME = 0
PTRACE_CONT = 7
PTRACE_SETOPTIONS = 0x4200
PTRACE_EVENT_EXEC = 4
PTRACE_EVENT_EXIT = 6
PTRACE_O_TRACEEXEC = 1 << PTRACE_EVENT_EXEC
PTRACE_O_TRACEEXIT = 1 << PTRACE_EVENT_EXIT
PTRACE_O_EXITKILL = 1 << 20
PR_SET_THP_DISABLE = 41
_CLEANUP_SECONDS = 5.0
_NOTICE = None
_CLEANUP_DEADLINE = None
_BLOCKABLE = signal.valid_signals() - {signal.SIGKILL, signal.SIGSTOP}

_libc = ctypes.CDLL(None, use_errno=True)
_libc.ptrace.restype = ctypes.c_long
_libc.ptrace.argtypes = [ctypes.c_long, ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p]
_libc.prctl.restype = ctypes.c_int
_libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
_libc.sigemptyset.argtypes = [ctypes.c_void_p]
_libc.sigaddset.argtypes = [ctypes.c_void_p, ctypes.c_int]
_libc.signalfd.restype = ctypes.c_int
_libc.signalfd.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
_libc.sigaction.restype = ctypes.c_int
_libc.sigaction.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]


def _ptrace(req, pid, data):
    if _libc.ptrace(req, pid, None, ctypes.c_void_p(data)) == -1:
        error = ctypes.get_errno()
        raise OSError(error, 'ptrace %d: %s' % (req, os.strerror(error)))


def _prctl(option, value):
    if _libc.prctl(option, value, 0, 0, 0):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _hwm_kib(pid):
    with open('/proc/%d/status' % pid) as source:
        for line in source:
            if line.startswith('VmHWM:'):
                return int(line.split()[1])
    return -1


class _Deadline(Exception):
    pass


class _Cancelled(Exception):
    pass


def _poll(fds, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise _Deadline
    poller = select.poll()
    for fd in fds:
        poller.register(fd, select.POLLIN | select.POLLHUP | select.POLLERR)
    # poll(2) takes a signed-int millisecond timeout. Cap each kernel wait
    # before multiplication; the absolute deadline remains authoritative.
    ready = poller.poll(max(1, math.ceil(min(remaining, 2_147_483) * 1000)))
    if time.monotonic() >= deadline:
        raise _Deadline
    return {fd for fd, event in ready}


class _Notifications:
    def __init__(self, cancel):
        self.cancel = cancel
        self.cancelled = False
        selected = {signal.SIGCHLD, signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT}
        # libc's Linux sigset_t has 1024 bits; sigemptyset/sigaddset own its
        # representation. No raw kernel sigset layout or syscall number.
        mask = ctypes.create_string_buffer(128)
        if _libc.sigemptyset(mask):
            raise OSError(ctypes.get_errno(), 'sigemptyset')
        for sig in selected:
            if _libc.sigaddset(mask, sig):
                raise OSError(ctypes.get_errno(), 'sigaddset')
        self.fd = _libc.signalfd(-1, mask, os.O_CLOEXEC | os.O_NONBLOCK)
        if self.fd < 0:
            raise OSError(ctypes.get_errno(), 'signalfd')
        os.set_blocking(cancel, False)

    def wait(self, deadline, cancellable=True, starting=False):
        if cancellable and self.cancelled:
            raise _Cancelled
        selected = [self.fd] + ([self.cancel] if cancellable else [])
        ready = _poll(selected, deadline)
        if self.cancel in ready:
            try:
                message = os.read(self.cancel, 4096)
            except BlockingIOError:
                message = None
            if starting and message == b'G':
                return True
            if message is not None:
                self.cancelled = True
        if self.fd in ready:
            while True:
                if time.monotonic() >= deadline:
                    raise _Deadline
                try:
                    data = os.read(self.fd, 128 * 16)
                except BlockingIOError:
                    break
                if not data or len(data) % 128:
                    raise RuntimeError('invalid signalfd notification')
                for offset in range(0, len(data), 128):
                    if time.monotonic() >= deadline:
                        raise _Deadline
                    if struct.unpack_from('=I', data, offset)[0] != signal.SIGCHLD:
                        self.cancelled = True
        if cancellable and self.cancelled:
            raise _Cancelled


def _wait_until(pid, deadline, *, cancellable=True):
    """Consume only this tracee's wait status, never a ready expired result."""
    while True:
        if time.monotonic() >= deadline:
            raise _Deadline
        got, status = os.waitpid(pid, os.WNOHANG)
        if time.monotonic() >= deadline:
            raise _Deadline
        if got:
            return status
        if _NOTICE is None:
            raise RuntimeError('event wait requires the isolated sampler worker')
        _NOTICE.wait(deadline, cancellable)


def _cleanup_deadline():
    global _CLEANUP_DEADLINE
    if _CLEANUP_DEADLINE is None:
        _CLEANUP_DEADLINE = time.monotonic() + _CLEANUP_SECONDS
    return _CLEANUP_DEADLINE


def _kill_reap(pid):
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    # A consumed exit stop needs CONT before the SIGKILL exit can finish.
    try:
        _ptrace(PTRACE_CONT, pid, 0)
    except ProcessLookupError:
        pass
    deadline = _cleanup_deadline()
    while True:
        try:
            status = _wait_until(pid, deadline, cancellable=False)
        except ChildProcessError:
            return
        except _Deadline as error:
            raise TimeoutError('traced memory sample did not reap after SIGKILL') from error
        if os.WIFEXITED(status) or os.WIFSIGNALED(status):
            return
        if os.WIFSTOPPED(status):
            try:
                _ptrace(PTRACE_CONT, pid, 0)
            except ProcessLookupError:
                pass


def _children():
    return [int(pid) for pid in Path('/proc/self/task', str(os.getpid()), 'children').read_text().split()]


def _drain_owned(deadline):
    """The fresh sampler has only sample descendants. ECHILD proves closure."""
    killed = []
    while True:
        if time.monotonic() >= deadline:
            raise TimeoutError('sampler descendants did not reap after SIGKILL')
        for pid in _children():
            if time.monotonic() >= deadline:
                raise TimeoutError('sampler descendant scan exceeded cleanup deadline')
            try:
                descriptor = os.pidfd_open(pid)
            except ProcessLookupError:
                continue
            try:
                signal.pidfd_send_signal(descriptor, signal.SIGKILL, None, 0)
                killed.append(pid)
            except ProcessLookupError:
                pass
            finally:
                os.close(descriptor)
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('sampler descendant wait stream exceeded cleanup deadline')
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return killed
            if not pid:
                break
        try:
            _NOTICE.wait(deadline, cancellable=False)
        except _Deadline as error:
            raise TimeoutError('sampler descendants did not reap after SIGKILL') from error


def _exec_dispositions(ignored):
    for sig in _BLOCKABLE:
        try:
            signal.signal(sig, signal.SIG_IGN if int(sig) in ignored else signal.SIG_DFL)
        except OSError as error:
            if error.errno != errno.EINVAL:
                raise


def _sample(argv, env, stdout, stderr, deadline, original_mask, ignored):
    if time.monotonic() >= deadline:
        raise _Deadline
    sampler = os.getpid()
    pid = os.fork()
    if pid == 0:
        try:
            _prctl(1, signal.SIGKILL)
            if os.getppid() != sampler:
                os._exit(125)
            os.setsid()
            if stdout is not None:
                os.dup2(stdout, 1)
            if stderr is not None:
                os.dup2(stderr, 2)
            _exec_dispositions(ignored)
            signal.pthread_sigmask(signal.SIG_SETMASK, original_mask)
            _prctl(PR_SET_THP_DISABLE, 1)
            _ptrace(PTRACE_TRACEME, 0, 0)
            if env is None:
                os.execv(argv[0], argv)
            os.execve(argv[0], argv, env)
        finally:
            os._exit(127)
    reaped = False
    try:
        status = _wait_until(pid, deadline)
        if os.WIFEXITED(status) or os.WIFSIGNALED(status):
            reaped = True
            return -1, os.waitstatus_to_exitcode(status)
        if not os.WIFSTOPPED(status) or os.WSTOPSIG(status) != signal.SIGTRAP:
            raise RuntimeError('memory sample did not reach its initial exec stop')
        _ptrace(PTRACE_SETOPTIONS, pid, PTRACE_O_TRACEEXIT | PTRACE_O_TRACEEXEC | PTRACE_O_EXITKILL)
        _ptrace(PTRACE_CONT, pid, 0)
        peak = -1
        while True:
            status = _wait_until(pid, deadline)
            if os.WIFEXITED(status) or os.WIFSIGNALED(status):
                reaped = True
                return peak, os.waitstatus_to_exitcode(status)
            sig = os.WSTOPSIG(status)
            if sig == signal.SIGTRAP and (status >> 16) == PTRACE_EVENT_EXIT:
                peak = _hwm_kib(pid)
                sig = 0
            elif sig == signal.SIGTRAP and (status >> 16) == PTRACE_EVENT_EXEC:
                sig = 0
            _ptrace(PTRACE_CONT, pid, sig)
    except _Deadline:
        return -1, 'timeout'
    finally:
        if not reaped:
            _kill_reap(pid)


def _error_record(error):
    return {'type': type(error).__name__, 'message': str(error),
            'errno': error.errno if isinstance(error, OSError) else None}


def _worker(argv, env, stdout, stderr, deadline, original_mask, ignored, cancel, answer, parent):
    global _NOTICE
    result = None
    cleanup_ok = True
    try:
        os.setsid()
        signal.set_wakeup_fd(-1)
        # All state changes are private to this fresh worker. Reset inherited
        # SIGCHLD auto-reap/no-stop flags and never invoke caller callbacks.
        _exec_dispositions(set())
        signal.signal(signal.SIGPIPE, signal.SIG_IGN)
        signal.pthread_sigmask(signal.SIG_SETMASK, _BLOCKABLE)
        _prctl(36, 1)
        _prctl(1, signal.SIGTERM)
        _NOTICE = _Notifications(cancel)
        if os.getppid() != parent:
            raise _Cancelled
        while not _NOTICE.wait(deadline, starting=True):
            pass
        result = {'result': _sample(argv, env, stdout, stderr, deadline, original_mask, ignored)}
    except _Deadline:
        result = {'result': [-1, 'timeout']}
    except BaseException as error:
        result = {'error': _error_record(error)}
    finally:
        try:
            if _NOTICE is not None:
                killed = _drain_owned(_cleanup_deadline())
                if killed and result is not None and result.get('result', [None, None])[1] == 0:
                    result = {'error': _error_record(RuntimeError('memory sample left running descendants'))}
        except BaseException as error:
            cleanup_ok = False
            result = {'error': _error_record(error)}
        result['cleanup_ok'] = cleanup_ok
        payload = json.dumps(result, ensure_ascii=True).encode()
        try:
            while payload:
                count = os.write(answer, payload)
                payload = payload[count:]
        except BrokenPipeError:
            pass
        finally:
            os.close(answer)
        if cleanup_ok:
            os._exit(0)
        # Keep ownership after publishing failed cleanup. EOF lets the
        # caller detect the failure before pidfd exit and take over using
        # verified descendant identities. Never exit0 without ECHILD proof.
        until = time.monotonic() + 3 * _CLEANUP_SECONDS + 2
        while time.monotonic() < until and os.getppid() == parent:
            try:
                _NOTICE.wait(until,cancellable=False)
            except BaseException:
                break
        # Parent loss/failure: a final bounded kill/CONT/reap attempt. This
        # path cannot produce successful cleanup evidence for the caller.
        try:
            for pid in _children():
                try:
                    os.kill(pid,signal.SIGKILL)
                    _ptrace(PTRACE_CONT,pid,0)
                except ProcessLookupError:
                    pass
            _drain_owned(time.monotonic()+_CLEANUP_SECONDS)
        except BaseException:
            pass
        os._exit(1)


def _read_result(fd, data):
    while True:
        try:
            piece = os.read(fd, 65536)
        except BlockingIOError:
            return data, False
        if not piece:
            return data, True
        data += piece
        if len(data) > 65536:
            raise RuntimeError('invalid oversized sampler result')


def _channel_result(channel):
    try:
        result = json.loads(channel['data'])
    except (ValueError,UnicodeError) as error:
        raise RuntimeError('sampler worker did not retain a valid result') from error
    if not isinstance(result,dict):
        raise RuntimeError('invalid sampler result')
    return result


def _receive_worker(pid, descriptor, answer, deadline, channel):
    while True:
        ready = _poll([descriptor] + ([] if channel['closed'] else [answer]), deadline)
        if answer in ready or descriptor in ready:
            channel['data'],channel['closed'] = _read_result(answer,channel['data'])
        if channel['closed']:
            result = _channel_result(channel)
            if result.get('cleanup_ok') is not True:
                channel['forced_attempted']=True
                _force_worker(pid,descriptor,'worker reported failed cleanup: '+str(result.get('error')))
        if descriptor in ready:
            try:
                got,status = os.waitpid(pid,os.WNOHANG)
            except ChildProcessError:
                # A caller SIGCHLD handler may have reaped the worker. Its
                # complete receipt still binds the target result and cleanup.
                got,status = pid,None
            if not got:
                continue
            channel['reaped']=True
            channel['status']=None if status is None else os.waitstatus_to_exitcode(status)
            result = _channel_result(channel)
            if result.get('cleanup_ok') is not True:
                raise RuntimeError('sampler worker exited without owned-child cleanup proof')
            if channel['status'] not in (None,0):
                raise RuntimeError('sampler worker exited after an internal failure')
            if 'error' in result:
                error=result['error']
                kind={'RuntimeError':RuntimeError,'TimeoutError':TimeoutError,
                      'KeyboardInterrupt':KeyboardInterrupt,'ValueError':ValueError}.get(error['type'],RuntimeError)
                if error['type'] in ('OSError','ProcessLookupError','PermissionError'):
                    raise OSError(error['errno'],error['message'])
                raise kind(error['message'])
            value=result.get('result')
            if not isinstance(value,list) or len(value)!=2:
                raise RuntimeError('invalid sampler observation')
            return tuple(value)


def _force_worker(pid, descriptor, reason="worker did not finish cancellation"):
    saved_mask = signal.pthread_sigmask(signal.SIG_BLOCK,_BLOCKABLE)
    try:
        return _force_worker_impl(pid,descriptor,reason)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK,saved_mask)


def _force_worker_impl(pid, descriptor, reason):
    """Error-only scoped escalation; forced cleanup is always a failure.

    Bind descendants through the worker's actual ancestry before losing its
    subreaper. Every delivery uses a pidfd, never a recycled PID or a name.
    Worker exit is waited/reaped even if a descendant refuses to terminate.
    """
    bound = {}
    problems = []
    worker_may_wait = False
    try:
        try:
            signal.pidfd_send_signal(descriptor, signal.SIGSTOP, None, 0)
            worker_may_wait = True
        except ProcessLookupError:
            # The numeric PID may already have been reaped/recycled by a
            # caller handler. Never walk or wait that number after pidfd loss.
            problems.append('worker exited before descendant binding; cleanup unproved')
        until = time.monotonic() + _CLEANUP_SECONDS
        try:
            while worker_may_wait and time.monotonic() < until:
                pending, scanned, added = [pid], set(), False
                while pending:
                    if time.monotonic() >= until:
                        raise _Deadline
                    parent = pending.pop()
                    if parent in scanned:
                        continue
                    scanned.add(parent)
                    try:
                        tasks = list(Path('/proc',str(parent),'task').iterdir())
                    except FileNotFoundError:
                        continue
                    for task in tasks:
                        if time.monotonic() >= until:
                            raise _Deadline
                        try:
                            children = [int(value) for value in (task/'children').read_text().split()]
                        except FileNotFoundError:
                            continue
                        for child in children:
                            if time.monotonic() >= until:
                                raise _Deadline
                            if child not in bound:
                                child_fd = None
                                try:
                                    before = Path('/proc',str(child),'stat').read_text().rsplit(')',1)[1].split()
                                    child_fd = os.pidfd_open(child)
                                    after = Path('/proc',str(child),'stat').read_text().rsplit(')',1)[1].split()
                                    if before[19]!=after[19] or int(after[1])!=parent:
                                        continue
                                    bound[child]=child_fd;child_fd=None;added=True
                                except (FileNotFoundError,ProcessLookupError):
                                    continue
                                finally:
                                    if child_fd is not None:os.close(child_fd)
                            pending.append(child)
                            try:signal.pidfd_send_signal(bound[child],signal.SIGKILL,None,0)
                            except ProcessLookupError:pass
                if not added:
                    break
            else:
                raise _Deadline
        except BaseException as error:
            problems.append('descendant discovery incomplete: '+type(error).__name__)
    finally:
        # A failure while walking /proc cannot leave our stopped worker
        # behind. Post-kill proof has its own absolute bounded deadline.
        for fd in [*bound.values(),descriptor]:
            try:signal.pidfd_send_signal(fd,signal.SIGKILL,None,0)
            except ProcessLookupError:pass
        remaining = {descriptor,*bound.values()}
        reaped = False
        until = time.monotonic() + _CLEANUP_SECONDS
        try:
            while remaining and time.monotonic() < until:
                try:
                    ready = _poll(remaining,until)
                except BaseException:
                    continue
                if descriptor in ready and worker_may_wait:
                    try:
                        got,status=os.waitpid(pid,os.WNOHANG)
                    except ChildProcessError:
                        got=pid
                    reaped=bool(got)
                remaining.difference_update(ready)
            if not reaped and worker_may_wait:
                try:
                    got,status=os.waitpid(pid,os.WNOHANG)
                except ChildProcessError:
                    got=pid
                reaped=bool(got)
            if remaining:problems.append('owned-process exit not proven')
            if not reaped:problems.append('worker reap not proven')
        finally:
            for fd in bound.values():os.close(fd)
    raise TimeoutError('sampler required forced cleanup; worker_reaped='+str(reaped)+'; reason='+reason+
                       '; verified descendants='+','.join(map(str,sorted(bound)))+
                       ('; '+'; '.join(problems) if problems else '; verified processes exited'))


def _abort_worker(pid, descriptor, answer, channel):
    # Exit0 is emitted only after the isolated worker reached ECHILD. Keep
    # this proof even when the original exception interrupts JSON decoding.
    if channel['reaped'] and channel['status']==0:
        return
    deadline=time.monotonic()+_CLEANUP_SECONDS+1
    while time.monotonic()<deadline:
        try:
            ready=_poll([descriptor]+([] if channel['closed'] else [answer]),deadline)
            if answer in ready or descriptor in ready:
                channel['data'],channel['closed']=_read_result(answer,channel['data'])
            if channel['closed']:
                result=_channel_result(channel)
                if result.get('cleanup_ok') is not True:
                    break
            if descriptor in ready:
                try:
                    got,status=os.waitpid(pid,os.WNOHANG)
                except ChildProcessError:
                    got,status=pid,None
                if not got:
                    continue
                channel['reaped']=True
                channel['status']=None if status is None else os.waitstatus_to_exitcode(status)
                if channel['status']==0:
                    return
                result=_channel_result(channel)
                if channel['status'] is None and result.get('cleanup_ok') is True:
                    return
                break
        except BaseException:
            # Repeated caller signals may not abandon an owned sample.
            continue
    _force_worker(pid,descriptor,'cancellation did not retain successful cleanup proof')


class _SignalAction(ctypes.Structure):
    # Linux/glibc generic bits/sigaction.h for the supported 64-bit targets.
    _fields_ = [('handler', ctypes.c_void_p), ('mask', ctypes.c_ulong * 16),
                ('flags', ctypes.c_int), ('restorer', ctypes.c_void_p)]


def _caller_allows_wait():
    if (sys.platform!='linux' or os.uname().machine not in ('x86_64','aarch64')
            or not hasattr(_libc,'gnu_get_libc_version')
            or ctypes.sizeof(ctypes.c_ulong)!=8 or ctypes.sizeof(ctypes.c_void_p)!=8):
        raise RuntimeError('peak_kib supports reviewed glibc LP64 amd64/aarch64 hosts only')
    if (ctypes.sizeof(_SignalAction)!=152 or _SignalAction.handler.offset!=0
            or _SignalAction.mask.offset!=8 or _SignalAction.flags.offset!=136
            or _SignalAction.restorer.offset!=144):
        raise RuntimeError('unreviewed userspace glibc sigaction layout')
    action = _SignalAction()
    if _libc.sigaction(signal.SIGCHLD, None, ctypes.byref(action)):
        error = ctypes.get_errno()
        raise OSError(error, 'query SIGCHLD action')
    if action.handler == 1 or action.flags & 2:  # SIG_IGN / SA_NOCLDWAIT
        raise RuntimeError('peak_kib requires waitable children; SIGCHLD auto-reaping is enabled')


def peak_kib(argv, env=None, stdout=None, stderr=None, timeout=60):
    """Return (own peak KiB, status), or (-1, 'timeout'); never reuse failures.

    Requires a single-threaded Linux caller with waitable children. Timers,
    signal handlers/masks and wakeup fd belong to the caller and stay intact.
    A SIGCHLD handler may reap the private worker; its complete cleanup receipt
    remains authoritative. Unrelated child wait statuses are never consumed. Setup+execution share the requested timeout.
    """
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('memory timeout must be finite and positive')
    deadline = time.monotonic() + timeout
    if len(list(Path('/proc/self/task').iterdir())) != 1:
        raise RuntimeError('peak_kib requires a single-threaded caller')
    _caller_allows_wait()
    status = Path('/proc/self/status').read_text()
    ignored_bits = int(next(line.split()[1] for line in status.splitlines() if line.startswith('SigIgn:')), 16)
    if ignored_bits & (1 << (signal.SIGCHLD - 1)):
        raise RuntimeError('peak_kib requires waitable children; SIGCHLD is ignored')
    ignored = {int(sig) for sig in signal.valid_signals() if ignored_bits & (1 << (int(sig) - 1))}
    owned = set()
    pid = descriptor = None
    original_mask = None
    cleanup_mask = None
    parent = os.getpid()
    channel = {'data':b'', 'closed':False, 'reaped':False, 'status':None}
    try:
        cancel_read, cancel_write = os.pipe2(os.O_CLOEXEC)
        owned.update((cancel_read,cancel_write))
        answer_read, answer_write = os.pipe2(os.O_CLOEXEC)
        owned.update((answer_read,answer_write))
        # No Python handler may escape between fork and binding the worker's
        # PID. Pending caller signals stay in the caller, never in the child.
        original_mask = signal.pthread_sigmask(signal.SIG_BLOCK, _BLOCKABLE)
        try:
            if len(list(Path('/proc/self/task').iterdir())) != 1:
                raise RuntimeError('peak_kib requires a single-threaded caller')
            _caller_allows_wait()
            pid = os.fork()
            if pid == 0:
                os.close(cancel_write)
                os.close(answer_read)
                _worker(argv, env, stdout, stderr, deadline, original_mask, ignored, cancel_read, answer_write, parent)
            os.close(cancel_read); owned.remove(cancel_read)
            os.close(answer_write); owned.remove(answer_write)
            descriptor = os.pidfd_open(pid)
            owned.add(descriptor)
            os.set_blocking(answer_read, False)
            os.set_blocking(cancel_write, False)
            os.write(cancel_write, b'G')
        finally:
            saved_mask, original_mask = original_mask, None
            signal.pthread_sigmask(signal.SIG_SETMASK, saved_mask)
        return _receive_worker(pid, descriptor, answer_read, deadline + _CLEANUP_SECONDS + 1, channel)
    except BaseException as error:
        cleanup_mask=signal.pthread_sigmask(signal.SIG_BLOCK,_BLOCKABLE)
        if pid is not None:
            # Closing the pipe is a reliable cancellation even if a caller
            # signal interrupted a write. The worker watches EOF as well.
            close_until = time.monotonic() + _CLEANUP_SECONDS
            while cancel_write in owned:
                if time.monotonic() >= close_until:
                    raise TimeoutError('sampler cancellation pipe did not close')
                try:
                    os.close(cancel_write)
                except OSError as close_error:
                    if close_error.errno != errno.EBADF:
                        raise
                except BaseException:
                    continue
                owned.remove(cancel_write)
        if pid is not None and descriptor is not None:
            if not channel.get('forced_attempted'):
                _abort_worker(pid, descriptor, answer_read, channel)
        elif pid is not None:
            until = time.monotonic() + _CLEANUP_SECONDS
            while True:
                if time.monotonic() >= until:
                    raise TimeoutError('sampler startup did not finish after closed control pipe')
                try:
                    got, status = os.waitpid(pid, os.WNOHANG)
                except ChildProcessError:
                    break
                except BaseException:
                    continue
                if got:
                    break
                if time.monotonic() >= until:
                    raise TimeoutError('sampler startup did not finish after closed control pipe')
                # Error-only startup fallback: no tracee exists and no G was
                # sent. Normal tracing and normal cleanup never poll/sleep.
                try:
                    time.sleep(0.001)
                except BaseException:
                    continue
        if isinstance(error,_Deadline):
            raise TimeoutError('sampler worker exceeded setup/execution/cleanup deadline') from error
        raise
    finally:
        finish_mask = (signal.pthread_sigmask(signal.SIG_BLOCK,_BLOCKABLE)
                       if cleanup_mask is None else cleanup_mask)
        close_errors=[]
        try:
            for fd in owned:
                try:
                    os.close(fd)
                except OSError as close_error:
                    if close_error.errno!=errno.EBADF:close_errors.append(close_error)
        finally:
            # Pending caller handlers run only after every owned descriptor
            # has been released. Their dispositions/wakeup fd are unchanged.
            signal.pthread_sigmask(signal.SIG_SETMASK,
                                   original_mask if original_mask is not None else finish_mask)
        if close_errors:raise close_errors[0]


def main():
    kib, code = peak_kib(sys.argv[1:])
    print('peak %d KiB, exit status %s' % (kib, code), file=sys.stderr)
    return code if isinstance(code, int) and code >= 0 else 1


if __name__ == '__main__':
    sys.exit(main())
