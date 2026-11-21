#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Check complete uncaught reports from 48 foreground pasroutines."""

from collections import Counter
import os
import selectors
import subprocess
import sys


def expected_reports():
    prefix = b'paslang: uncaught raise in a routine, which ends alone'
    reports = Counter()
    for worker in range(1, 49):
        if worker % 6 == 0:
            line = prefix + b', raised at line 35'
        elif worker == 1:
            line = prefix + b': EFormatFailure, raised at line 37'
        else:
            body = b'x' * (8192 if worker == 2 else 96)
            line = prefix + f': EWorker: worker-{worker}-'.encode() + body + b', raised at line 41'
        reports[line] += 1
    return reports


def check(command):
    expected = expected_reports()
    for stress in (False, True):
        env = os.environ.copy()
        if stress:
            env.update(PASLANG_GCSTRESS='1', PASLANG_GCVERIFY='1', PASLANG_GCPOISON='1')
        for round_number in range(1, 9):
            run = subprocess.run(command, capture_output=True, env=env, timeout=60)
            if not run.stderr.endswith(b'\n'):
                raise SystemExit(f'uncaught reports missing final newline: {run.stderr[-300:]!r}')
            found = Counter(run.stderr[:-1].split(b'\n'))
            if run.returncode or run.stdout or found != expected:
                first_missing = next(iter(expected - found), b'')[:240]
                first_unexpected = next(iter(found - expected), b'')[:240]
                raise SystemExit(
                    f'uncaught reports: status {run.returncode}, stdout {run.stdout[:240]!r}, '
                    f'GC stress {stress}, round {round_number}, {found.total()} lines\n'
                    f'missing: {first_missing!r}\nunexpected: {first_unexpected!r}'
                )
    check_blocked_writer(command)
    check_helpers(command)
    print('ok uncaught reports, blocked worker, and direct reporting calls')


def check_helpers(command):
    run = subprocess.run(command + ['helpers'], capture_output=True, timeout=10)
    expected = (b'paslang: uncaught raise in the main routine: EWorker: first\n'
                b'paslang: uncaught raise in a routine, which ends alone: EWorker: second\n'
                b'paslang: third\n')
    if run.returncode or run.stdout or run.stderr != expected:
        raise SystemExit(f'direct reporting calls: {run.returncode}, {run.stdout!r}, {run.stderr!r}')


def read_ready(pipe):
    with selectors.DefaultSelector() as selector:
        selector.register(pipe, selectors.EVENT_READ)
        if not selector.select(30):
            raise SystemExit('timed out waiting for the report handshake')
        return os.read(pipe.fileno(), 4096)


def check_blocked_writer(command):
    # Hold the worker midway through a message too large for the pipe.
    # Release the main raise, then wait for its formatter before draining.
    with subprocess.Popen(command + ['pipe'], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        try:
            prefix = read_ready(proc.stderr)
            proc.stdin.write(b'raise\n')
            proc.stdin.flush()
            ready = read_ready(proc.stdout)
            out, err = proc.communicate(timeout=60)
        finally:
            if proc.poll() is None:
                proc.kill()

    worker = (b'paslang: uncaught raise in a routine, which ends alone: EWorker: '
              + b'x' * (1 << 20) + b', raised at line 57\n')
    main = (b'paslang: uncaught raise in the main routine: EMainFailure: main, raised at line 62\n'
            b'  called at line 76\n')
    if proc.returncode != 1 or ready + out != b'main formatting\n' or prefix + err != worker + main:
        raise SystemExit(
            f'blocked report: status {proc.returncode}, stdout {ready + out!r}, '
            f'stderr {len(prefix) + len(err)} bytes, tail {err[-240:]!r}'
        )


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('usage: check_uncaught_reports.py command [args ...]')
    check(sys.argv[1:])
