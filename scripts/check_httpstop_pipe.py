#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Exercise the real HTTP-stop pipe/start functions with controlled children."""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
sys.dont_write_bytecode = True


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def load(path):
    argv = sys.argv
    try:
        sys.argv = [str(path), '/unused']
        spec = importlib.util.spec_from_file_location('httpstop_under_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.argv = argv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-parent', type=Path)
    args = parser.parse_args()
    folder = Path(tempfile.mkdtemp(prefix='httpstop-pipe-', dir=args.evidence_parent))
    source = Path(__file__).resolve().with_name('httpstop_check.py')
    text = source.read_text()
    stub = folder / 'child.py'
    stub.write_text('#!' + sys.executable + '\n' + r'''import os, signal, stat, sys, time
mode = sys.argv[1]
if 'LISTEN_FDS' in os.environ:
    assert os.environ['LISTEN_FDS'] == '1'
    assert int(os.environ['LISTEN_PID']) == os.getpid()
    assert stat.S_ISSOCK(os.fstat(3).st_mode)
if mode == 'signal':
    def stopped(sig, frame):
        os.write(1, b'stopped by SIGTERM\n')
        sys.exit(0)
    signal.signal(signal.SIGTERM, stopped)
    os.write(1, b'listening\n')
    while True: signal.pause()
elif mode == 'stop-timeout':
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    os.write(1, b'listening\nwaiting for signal\n')
    while True: signal.pause()
elif mode == 'readiness-timeout':
    os.write(1, b'listen')
    while True: signal.pause()
elif mode == 'termination-timeout':
    os.write(1, b'listening\npending final bytes\n')
    while True: signal.pause()
elif mode == 'wrong-ready':
    os.write(1, b'wrong\nstopped by none\n')
elif mode == 'missing-ready':
    pass
elif mode == 'missing-final':
    os.write(1, b'listening\n')
elif mode == 'wrong-final':
    os.write(1, b'listening\nwrong\n')
elif mode == 'nonzero':
    os.write(1, b'listening\nstopped by none\n')
    sys.exit(7)
elif mode == 'split':
    os.write(1, b'list')
    time.sleep(0.025)
    os.write(1, b'ening\nstopped ')
    time.sleep(0.025)
    os.write(1, b'by none\n')
else:
    os.write(1, b'listening\nstopped by none\n')
''')
    stub.chmod(0o755)
    mutant_text = text.replace(', bufsize=0', '')
    begin = mutant_text.index('def until_listening(')
    end = mutant_text.index('\n\ndef stop(', begin)
    mutant_text = mutant_text[:begin] + """def until_listening(p, what):
    line = p.stdout.readline().decode()
    if line != 'listening\\n':
        p.kill()
        fail(what, 'it said %r, not listening' % line)
""" + mutant_text[end:]
    mutant = folder / 'httpstop-original-reader.py'
    mutant.write_text(mutant_text)
    rows = []
    result = {'ok': False, 'source': str(source),
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'mutant_sha256': hashlib.sha256(mutant.read_bytes()).hexdigest(),
        'python': sys.version, 'rows': rows}
    def save():
        (folder / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    try:
        for old, module in [(False, load(source)), (True, load(mutant))]:
            module.BIN, module.RUN = str(stub), []
            original_start = module.start
            for passed in (False, True):
                scenarios = [('immediate', False, '')] if old else [
                    ('immediate', True, ''), ('split', True, ''), ('signal', True, ''),
                    ('wrong-ready', False, 'not listening'), ('missing-ready', False, 'not listening'),
                    ('readiness-timeout', False, 'listen'),
                    ('termination-timeout', False, 'pending final bytes'),
                    ('stop-timeout', False, 'waiting for signal'),
                    ('nonzero', False, 'exit status 7'), ('wrong-final', False, "said 'wrong"),
                    ('missing-final', False, "said ''")]
                for mode, success, diagnostic in scenarios:
                    children = []
                    module.WAIT = 0.2 if 'timeout' in mode else 2
                    def start(actual_args, sock=None, files=0):
                        child = original_start([mode], sock=sock, files=files)
                        children.append(child)
                        # Both lines are committed before the real readiness
                        # read in the deterministic immediate-exit regression.
                        if mode not in ('split', 'signal') and 'timeout' not in mode:
                            child.wait(timeout=2)
                        return child
                    module.start = start
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) if passed else None
                    output = io.StringIO()
                    status = 0
                    started = time.monotonic()
                    try:
                        with contextlib.redirect_stdout(output):
                            if mode in ('signal', 'stop-timeout'):
                                child = module.start([] , sock)
                                module.until_listening(child, mode)
                                module.stop(child, mode)
                            else:
                                module.ends(sock, mode)
                    except SystemExit as error:
                        status = error.code
                    finally:
                        production_reaped = all(child.returncode is not None for child in children)
                        if sock is not None:
                            sock.close()
                        for child in children:
                            if child.poll() is None:
                                child.kill()
                                child.communicate(timeout=2)
                    elapsed = time.monotonic() - started
                    row = {'original_reader_mutant': old, 'descriptor_branch': passed,
                           'scenario': mode, 'status': status, 'stdout': output.getvalue(),
                           'wall_s': elapsed, 'children': []}
                    rows.append(row)
                    row['production_reaped'] = production_reaped
                    require(production_reaped, 'production failure path left its child unreaped: ' + repr(row))
                    for child in children:
                        try:
                            waited = os.waitpid(child.pid, os.WNOHANG)
                        except ChildProcessError:
                            waited = 'already reaped'
                        row['children'].append({'pid': child.pid, 'status': child.returncode,
                                                'waitpid': waited, 'command': child.args})
                        require(waited == 'already reaped', 'child not reaped by production harness')
                        child.stdout.close()
                    save()
                    require((status == 0) == success, repr(row))
                    require(diagnostic in row['stdout'], 'missing diagnostic: ' + repr(row))
                    require(elapsed < 4, 'readiness/termination/cleanup deadline exceeded')
                    if old:
                        require("exit status 0, said ''" in row['stdout'], 'old buffering mutant was not caught by lost-output assertion')
        result['ok'] = True
    except BaseException as error:
        result['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        save()
    print('httpstop pipe: 22 real-plumbing controls passed; old reader caught on both start branches; evidence ' + str(folder))


if __name__ == '__main__':
    main()
