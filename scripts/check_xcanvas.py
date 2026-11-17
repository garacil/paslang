#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacil@tucall.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Own one Xvfb for the two already-built Xcanvas clients, then reap it.

One thread, ordinary Popen methods only: no external waitpid, PID files or
signals to numeric PIDs. A dead direct child is never signalled after reaping.
"""
import argparse
import os
from pathlib import Path
import select
import shutil
import signal
import subprocess
import sys
import time


def require(value, message):
    if not value:
        raise RuntimeError(message)


def reap(child):
    if child.poll() is not None:
        child.wait()
        return False
    child.terminate()
    try:
        child.wait(timeout=2)
        return False
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=5)
        return True


def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('expected', type=Path)
    parser.add_argument('build', type=Path)
    parser.add_argument('qemu', nargs=argparse.REMAINDER)
    a = parser.parse_args()
    if a.qemu[:1] == ['--']:
        a.qemu = a.qemu[1:]
    require(a.qemu, 'an ARM emulator command is required')
    expected, build = a.expected.read_bytes(), a.build.resolve(strict=True)
    stopped, errors = [], []
    old_chld = signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    previous = {s: signal.getsignal(s) for s in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)}
    for s in previous:
        signal.signal(s, lambda number, frame: stopped.append(number))
    server, reader, writer = None, None, None
    env = os.environ.copy()

    def check():
        require(not stopped, 'Xcanvas interrupted by signal ' + str(stopped[0] if stopped else ''))
        require(server is None or server.poll() is None, 'Xvfb exited before both clients completed')

    def client(label, argv):
        check()
        child, cleanup_failed = None, False
        try:
            with (build / (label + '.got')).open('wb') as output, (build / (label + '.err')).open('wb') as diagnostics:
                child = subprocess.Popen(argv, stdout=output, stderr=diagnostics, env=env)
                deadline = time.monotonic() + 120
                while child.poll() is None:
                    check()
                    require(time.monotonic() < deadline, label + ' exceeded 120 seconds')
                    time.sleep(0.02)
                require(child.returncode == 0, label + ' returned ' + str(child.returncode))
            check()
            require((build / (label + '.err')).read_bytes() == b'', label + ' wrote diagnostics')
            require((build / (label + '.got')).read_bytes() == expected, label + ' output differs')
            print('ok ' + label, flush=True)
        finally:
            if child is not None:
                try:
                    require(not reap(child), label + ' required SIGKILL during cleanup')
                except BaseException as error:
                    cleanup_failed = True
                    errors.append(label + ' cleanup: ' + type(error).__name__ + ': ' + str(error))
        require(not cleanup_failed, label + ' cleanup failed')

    try:
        check()
        executable = shutil.which('Xvfb')
        if executable is not None:
            reader, writer = os.pipe()
            with (build / 'xvfb.log').open('wb') as log:
                server = subprocess.Popen([executable, '-displayfd', str(writer), '-screen', '0',
                    '1024x768x24', '-ac'], pass_fds=(writer,), stdout=log, stderr=log)
            os.close(writer)
            writer = None
            deadline, display = time.monotonic() + 10, bytearray()
            while b'\n' not in display:
                check()
                require(time.monotonic() < deadline, 'Xvfb did not report a display within 10 seconds')
                ready, _, _ = select.select([reader], [], [], 0.05)
                if ready:
                    data = os.read(reader, 64)
                    require(data, 'Xvfb closed displayfd before reporting a display')
                    display.extend(data)
                    require(len(display) <= 64, 'invalid Xvfb display number')
            require(display.endswith(b'\n') and display[:-1].isdigit(), 'invalid Xvfb display number')
            env['DISPLAY'] = ':' + display[:-1].decode('ascii')
            (build / 'xvfb.display').write_bytes(display)
            os.close(reader)
            reader = None
        client('xcanvas', [str(build / 'xcanvas')])
        client('xcanvas-arm', [*a.qemu, str(build / 'xcanvas-arm')])
    except BaseException as error:
        errors.append(type(error).__name__ + ': ' + str(error))
    finally:
        for fd in (reader, writer):
            if fd is not None:
                os.close(fd)
        if server is not None:
            try:
                require(not reap(server), 'Xvfb required SIGKILL during cleanup')
            except BaseException as error:
                errors.append(type(error).__name__ + ': ' + str(error))
        for number, handler in previous.items():
            signal.signal(number, handler)
        signal.signal(signal.SIGCHLD, old_chld)
        if stopped:
            errors.append('received signals: ' + str(stopped))
    for error in errors:
        print('Xcanvas: ' + error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
