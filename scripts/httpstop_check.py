#!/usr/bin/env python3
"""httpstop_check.py BINARY [RUNNER ...]: stops testdata/httpstop's server with SIGTERM as a service manager does,
and looks at what is left of its sockets (P573).

  unix, the file there      the program listens on a Unix socket itself; SIGTERM: it ends and says so
  unix, the file removed    the same with the socket's file removed first (it did not end before P573)
  systemd, tcp              a listening TCP socket is passed as sd_listen_fds(3) says, and this script keeps its own
                            descriptor of it, as a socket unit does: after the program stops, the socket still
                            listens (a connection is taken), and a second run of the program serves on it
  systemd, unix             the same with a Unix socket
  systemd, unix, removed    with the socket's file removed the program still stops
  idle                      a server nobody talks to sleeps: its acceptor is parked on the poller and neither tries
                            again every few milliseconds nor spins (the cost of a second of it is looked at)
  out of descriptors        with more connections than it may hold open (EMFILE from accept4) the server waits a
                            little and tries again, as Go's Serve backs off: it does not spin, and when the
                            connections go it serves again and stops on SIGTERM
  systemd, not listening    a socket that is bound and does not listen (EINVAL from accept4): nothing will ever
                            come, the acceptor ends and the program with it, at once
  systemd, not a socket     the same with a descriptor that is no socket (ENOTSOCK)
  systemd, a datagram one   and with a socket that takes no connections (EOPNOTSUPP)
  no poller                 started with one descriptor less than an idle server holds, the last it opens, its
                            acceptor's poller, cannot be made; the limit is then lifted (prlimit(2)), so that
                            accept4 answers EAGAIN again: the acceptor tries every few milliseconds, takes a
                            connection, does not spin, and the server stops on SIGTERM
  one after another         a connection is taken as soon as it comes: two hundred, each asked and answered, in
                            well under the second that a pause of 5 ms before each would make (not under an
                            emulator)

RUNNER is what runs the binary when it is not this machine's (an emulator and its options).
Exit status 1 at the first that fails."""
import os
import resource
import select
import signal
import socket
import subprocess
import sys
import tempfile
import time

if len(sys.argv) < 2:
    sys.exit(__doc__)
BIN = os.path.abspath(sys.argv[1])
RUN = sys.argv[2:]
WAIT = 20
# One idle second of the server (idle below): the runtime's monitor thread wakes a hundred times and nothing else
# runs, here and under the emulator alike (99 or 100 context switches, 0 or 1 ticks of CPU). An acceptor that slept
# 5 ms between tries cost 590 switches a second, and one that tried again at once 85 ticks of the 100 a second has.
SWITCHES = 250
TICKS = 20
# the descriptors the program may have open when it is made to run out of them
FILES = 40
# Connections one after another, each taken by an acceptor that waited for it: 200 take 0.01 s here; with a pause
# of 5 ms before each they would take a second and more.
QUICK = 200
QUICKTIME = 0.5


def fail(what, why):
    print('httpstop_check: %s: %s' % (what, why))
    sys.exit(1)


def start(args, sock=None, files=0):
    """the program with args; sock, when given (a socket or a file), becomes descriptor 3 with LISTEN_FDS and
    LISTEN_PID set; files, when given, is the most descriptors the program may have open"""
    limit = None
    if files:
        # the soft limit alone, so that it can be lifted again from here
        limit = lambda: resource.setrlimit(resource.RLIMIT_NOFILE, (files, resource.getrlimit(resource.RLIMIT_NOFILE)[1]))
    if sock is None:
        return subprocess.Popen(RUN + [BIN] + args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, preexec_fn=limit, bufsize=0)
    # the shell puts the socket at 3 and names its own pid, which exec keeps
    sh = 'exec 3<&%d; LISTEN_FDS=1 LISTEN_PID=$$ exec "$@"' % sock.fileno()
    return subprocess.Popen(['sh', '-c', sh, 'sh'] + RUN + [BIN] + args, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, pass_fds=(sock.fileno(),), bufsize=0)


def kill_and_collect(p):
    """Kill and reap within one cleanup deadline; retain available pipe bytes."""
    deadline = time.monotonic() + WAIT
    p.kill()
    try:
        return p.communicate(timeout=max(0, deadline - time.monotonic()))[0], ''
    except subprocess.TimeoutExpired as error:
        output = error.output or b''
        p.stdout.close()
        try:
            p.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            return output, '; could not reap within cleanup deadline'
        return output, '; pipe did not close within cleanup deadline'


def abort(p, what, why, received=b''):
    remaining, cleanup = kill_and_collect(p)
    fail(what, why + cleanup + '; said %r' % (received + remaining).decode(errors='backslashreplace'))


def until_listening(p, what):
    # One owner reads the raw pipe. Buffered readline can read ahead into
    # the final line, which timed POSIX communicate reads through os.read.
    deadline = time.monotonic() + WAIT
    line = bytearray()
    while not line.endswith(b'\n'):
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([p.stdout], [], [], remaining)[0]:
            abort(p, what, 'not listening after %d seconds' % WAIT, bytes(line))
        byte = os.read(p.stdout.fileno(), 1)
        if not byte:
            break
        line.extend(byte)
    if line != b'listening\n':
        abort(p, what, 'it said %r, not listening' % bytes(line).decode(errors='backslashreplace'), bytes(line))


def stop(p, what):
    p.send_signal(signal.SIGTERM)
    try:
        rest = p.communicate(timeout=WAIT)[0].decode()
    except subprocess.TimeoutExpired:
        abort(p, what, 'still alive %d seconds after SIGTERM' % WAIT)
    if p.returncode != 0 or rest != 'stopped by SIGTERM\n':
        fail(what, 'exit status %d, said %r' % (p.returncode, rest))


def ask(p, family, addr, what):
    """GET /hola answered: the server is up, its watch of the signals too (ServeUntilSignal sets it before it
    serves), so a SIGTERM from here on is the server's to take"""
    c = socket.socket(family, socket.SOCK_STREAM)
    c.settimeout(WAIT)
    try:
        c.connect(addr)
    except OSError as e:
        abort(p, what, 'a connection: %s' % e)
    r = get(c)
    if not r.startswith(b'HTTP/1.1 200') or b'hola' not in r:
        abort(p, what, 'it answered %r' % r[:60])


def get(c):
    c.settimeout(WAIT)
    c.sendall(b'GET /hola HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n')
    data = b''
    while True:
        part = c.recv(4096)
        if not part:
            break
        data += part
    c.close()
    return data


def by_path(remove, what):
    d = tempfile.mkdtemp()
    path = d + '/s.sock'
    p = start(['unix', path])
    until_listening(p, what)
    ask(p, socket.AF_UNIX, path, what)
    if remove:
        os.unlink(path)
    stop(p, what)
    if os.path.exists(path):
        fail(what, 'the socket file is still there')
    os.rmdir(d)
    print('ok', what)


def passed(family, remove, what):
    d = tempfile.mkdtemp()
    path = d + '/s.sock'
    s = socket.socket(family, socket.SOCK_STREAM)
    if family == socket.AF_UNIX:
        s.bind(path)
        addr = path
    else:
        s.bind(('127.0.0.1', 0))
        addr = s.getsockname()
    s.listen(16)
    p = start(['systemd'], s)
    until_listening(p, what)
    ask(p, family, addr, what)
    if remove:
        os.unlink(path)
    stop(p, what)
    if not remove:
        # the socket is the unit's: it still listens, and the next run serves on it
        if s.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN) != 1:
            fail(what, 'the socket no longer listens after the program stopped')
        c = socket.socket(family, socket.SOCK_STREAM)
        c.settimeout(WAIT)
        try:
            c.connect(addr)
        except OSError as e:
            fail(what, 'a connection after the stop: %s' % e)
        p = start(['systemd'], s)
        until_listening(p, what)
        r = get(c)
        if not r.startswith(b'HTTP/1.1 200') or b'hola' not in r:
            abort(p, what, 'the second run answered %r' % r[:60])
        stop(p, what)
        if family == socket.AF_UNIX:
            os.unlink(path)
    s.close()
    os.rmdir(d)
    print('ok', what)


def cost(pid):
    """the context switches of every thread of pid and the process's ticks of CPU so far"""
    cs = 0
    for t in os.listdir('/proc/%d/task' % pid):
        try:
            for l in open('/proc/%d/task/%s/status' % (pid, t)):
                if 'ctxt_switches' in l:
                    cs += int(l.split()[1])
        except OSError:
            pass
    f = open('/proc/%d/stat' % pid).read().rsplit(')', 1)[1].split()
    return cs, int(f[11]) + int(f[12])


def quiet(p, what, switches):
    """a second of p costs at most switches context switches (None: any number) and TICKS of CPU; the best of
    three seconds counts, so that a busy machine does not fail it"""
    seen = []
    for k in range(3):
        a = cost(p.pid)
        time.sleep(1)
        b = cost(p.pid)
        seen.append((b[0] - a[0], b[1] - a[1]))
        if (switches is None or seen[-1][0] <= switches) and seen[-1][1] <= TICKS:
            return
    abort(p, what, 'a second cost %s (context switches, ticks of CPU); at most %s and %d'
         % (' '.join('%d,%d' % x for x in seen), 'any number' if switches is None else switches, TICKS))


def idle(what):
    d = tempfile.mkdtemp()
    path = d + '/s.sock'
    p = start(['unix', path])
    until_listening(p, what)
    # one connection served: the acceptor has been round its loop and waits again
    ask(p, socket.AF_UNIX, path, what)
    time.sleep(0.3)
    quiet(p, what, SWITCHES)
    stop(p, what)
    os.rmdir(d)
    print('ok', what)


def exhausted(what):
    d = tempfile.mkdtemp()
    path = d + '/s.sock'
    p = start(['unix', path], files=FILES)
    until_listening(p, what)
    ask(p, socket.AF_UNIX, path, what)
    # connections that ask nothing, more than the program may hold open: the rest wait in the listener's queue
    held = []
    for k in range(2 * FILES):
        c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        c.setblocking(False)
        try:
            c.connect(path)
        except OSError:
            c.close()
            break
        held.append(c)
    if len(held) < FILES:
        abort(p, what, 'only %d connections were taken into the queue' % len(held))
    time.sleep(0.5)
    # it tries again every few milliseconds (any number of switches) and must not spin
    quiet(p, what, None)
    if p.poll() is not None:
        fail(what, 'the program ended, status %d' % p.returncode)
    for c in held:
        c.close()
    time.sleep(0.5)
    ask(p, socket.AF_UNIX, path, what)
    stop(p, what)
    os.rmdir(d)
    print('ok', what)


def nopoller(what):
    d = tempfile.mkdtemp()
    path = d + '/s.sock'
    p = start(['unix', path])
    until_listening(p, what)
    ask(p, socket.AF_UNIX, path, what)
    time.sleep(0.3)
    # the highest descriptor of an idle server is the last it opened, its acceptor's poller: with that number
    # as the limit every descriptor before it can be made and that one cannot
    top = max(int(x) for x in os.listdir('/proc/%d/fd' % p.pid))
    stop(p, what)
    p = start(['unix', path], files=top)
    until_listening(p, what)
    time.sleep(0.5)
    # accept4 takes its descriptor before it looks for a connection, so at the limit it answers EMFILE and never
    # EAGAIN: with the limit lifted the acceptor is the one that waits with no poller
    hard = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
    resource.prlimit(p.pid, resource.RLIMIT_NOFILE, (hard, hard))
    ask(p, socket.AF_UNIX, path, what)
    time.sleep(0.3)
    if max(int(x) for x in os.listdir('/proc/%d/fd' % p.pid)) >= top:
        abort(p, what, 'the server has its descriptor %d all the same' % top)
    quiet(p, what, None)
    stop(p, what)
    os.rmdir(d)
    print('ok', what)


def quick(what):
    if RUN:
        print('--', what, '(not under an emulator)')
        return
    d = tempfile.mkdtemp()
    path = d + '/s.sock'
    p = start(['unix', path])
    until_listening(p, what)
    ask(p, socket.AF_UNIX, path, what)
    t = time.monotonic()
    for k in range(QUICK):
        ask(p, socket.AF_UNIX, path, what)
    t = time.monotonic() - t
    if t > QUICKTIME:
        abort(p, what, '%d connections took %.2f s; at most %.2f' % (QUICK, t, QUICKTIME))
    stop(p, what)
    os.rmdir(d)
    print('ok', what)


def ends(sock, what):
    """sock is passed as systemd passes a socket and nothing can come from it: the program ends by itself"""
    p = start(['systemd'], sock)
    until_listening(p, what)
    try:
        rest = p.communicate(timeout=WAIT)[0].decode()
    except subprocess.TimeoutExpired:
        abort(p, what, 'still alive after %d seconds' % WAIT)
    if p.returncode != 0 or not rest.startswith('stopped by'):
        fail(what, 'exit status %d, said %r' % (p.returncode, rest))
    print('ok', what)


def main():
    by_path(False, 'unix, the file there')
    by_path(True, 'unix, the file removed')
    passed(socket.AF_INET, False, 'systemd, tcp')
    passed(socket.AF_UNIX, False, 'systemd, unix')
    passed(socket.AF_UNIX, True, 'systemd, unix, the file removed')
    idle('idle')
    exhausted('out of descriptors')
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    ends(s, 'systemd, not listening')
    s.close()
    f = open('/dev/null')
    ends(f, 'systemd, not a socket')
    f.close()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('127.0.0.1', 0))
    ends(s, 'systemd, a datagram one')
    s.close()
    nopoller('no poller')
    quick('one after another')


if __name__ == '__main__':
    main()
