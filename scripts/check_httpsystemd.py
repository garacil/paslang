#!/usr/bin/env python3
"""check_httpsystemd.py PROGRAM [LAUNCHER]: httpserver's ListenSystemd
(P434). Sockets made as systemd makes them (sd_listen_fds(3)): a TCP one
on 127.0.0.1 as descriptor 3 and a Unix one as 4, LISTEN_FDS=2 and
LISTEN_PID the program's own pid (a shell that execs it keeps its pid,
and so does qemu). The program, testdata/httpsrv with 'systemd', answers
GET /hello on both, then stops on SIGTERM."""
import os
import signal
import socket
import subprocess
import sys
import tempfile

prog = sys.argv[1]
launcher = sys.argv[2:3]
tmp = tempfile.mkdtemp(prefix='httpsystemd')
path = os.path.join(tmp, 's.sock')
# 3 and 4 taken first, so the sockets get others and dup2 puts them there
pad = [os.open('/dev/null', os.O_RDONLY) for _ in range(3)]
tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcp.bind(('127.0.0.1', 0))
tcp.listen(16)
port = tcp.getsockname()[1]
uni = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
uni.bind(path)
uni.listen(16)
os.dup2(tcp.fileno(), 3, inheritable=True)
os.dup2(uni.fileno(), 4, inheritable=True)
for fd in pad:
    if fd > 4:
        os.close(fd)
p = subprocess.Popen(['sh', '-c', 'LISTEN_PID=$$ LISTEN_FDS=2 exec "$@"', 'sh'] + launcher + [prog, 'systemd'],
                     pass_fds=(3, 4), stdout=subprocess.PIPE, text=True)
os.close(3)
os.close(4)
tcp.close()
uni.close()
lines = [p.stdout.readline().strip(), p.stdout.readline().strip()]


def ask(sock):
    sock.settimeout(60)
    sock.sendall(b'GET /hello HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n')
    data = b''
    while True:
        b = sock.recv(4096)
        if not b:
            break
        data += b
    sock.close()
    return data


a = ask(socket.create_connection(('127.0.0.1', port), timeout=60))
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect(path)
b = ask(s)
os.kill(p.pid, signal.SIGTERM)
lines.append(p.stdout.readline().strip())
code = p.wait(timeout=60)
ok = (lines == ['systemd sockets: 1', 'ready', 'stopped on SIGTERM'] and code == 0 and
      a.startswith(b'HTTP/1.1 200 OK\r\n') and a.endswith(b'\r\n\r\nhello\n') and
      b.startswith(b'HTTP/1.1 200 OK\r\n') and b.endswith(b'\r\n\r\nhello\n'))
if os.path.exists(path):
    os.remove(path)
os.rmdir(tmp)
if not ok:
    print('check_httpsystemd: wrong:', lines, code, a[:80], b[:80])
    sys.exit(1)
print('check_httpsystemd: TCP and Unix sockets from systemd, answered, stopped on SIGTERM')
