#!/usr/bin/env python3
# This file is part of paslang's benchmarks.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacil@tucall.com>
# GPL version 3 or later. See COPYING.

"""Measure verified full HTTPS connections/s and warmed HTTPS payload bytes/s."""

import argparse
from hashlib import sha256
from itertools import product
import json
import math
import os
from pathlib import Path
import platform
import statistics
from subprocess import CalledProcessError
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from check_tls_server import HELLO, KEYS, ROOT, require, run, server  # noqa: E402
from bench.metadata_scope import save  # noqa: E402

PAYLOAD = bytes(range(256)) * (4 * 1024 * 1024 // 256)


def sample(command, load, version, cpu, mode, workers, iterations, file):
    with server(command, KEYS / 'ec.pem', KEYS / 'ec.key', file, tls12=version == '1.2') as port:
        result = run([*load, 'load', f'127.0.0.1:{port}', KEYS / 'ca.pem', file,
                      mode, version, cpu, str(workers), str(iterations)], timeout=180)
        require(not result.stderr, f'client diagnostics {result.stderr!r}')
        row = json.loads(result.stdout)
        size = len(PAYLOAD) if mode == 'transfer' else len(HELLO)
        require(row['requests'] == workers * iterations and row['bytes'] == size * row['requests']
                and math.isfinite(row['seconds']) and row['seconds'] > 0,
                f'invalid workload counts or elapsed time: {row}')
        row['rate'] = row['bytes' if mode == 'transfer' else 'requests'] / row['seconds']
        return row


def benchmark(args, folder, proof):
    compiler = args.compiler.resolve()
    proof['toolchains'] = {
        'paslang': run([compiler, '-v']).stdout.decode().splitlines()[0],
        'go': run(['go', 'version']).stdout.decode().strip(),
        'go_amd64': {},
    }
    file = folder / 'file'
    file.write_bytes(PAYLOAD)
    proof['fixture_sha256'] = {
        name: sha256(path.read_bytes()).hexdigest() for name, path in (
            ('paslang', ROOT / 'testdata/tlsserver13.paslang'), ('go', HERE / 'servers/tls.go'),
            ('runner', Path(__file__)), ('payload', file),
        )
    }
    proof['binaries'] = {}
    for cpu in args.cpu:
        go_env = dict(os.environ)
        if cpu == 'base':
            go_env['GOAMD64'] = 'v1'
        elif args.go_amd64:
            go_env['GOAMD64'] = args.go_amd64
        go = folder / ('go-' + cpu)
        run(['go', 'build', '-o', go, HERE / 'servers/tls.go'], timeout=180, env=go_env)
        proof['toolchains']['go_amd64'][cpu] = (
            run(['go', 'env', 'GOAMD64'], env=go_env).stdout.decode().strip())
        binary = folder / ('paslang-' + cpu)
        units = ['-Fu', args.units.resolve()] if args.units else []
        run([compiler, '-cpu', cpu, *units, '-o', binary, ROOT / 'testdata/tlsserver13.paslang'])
        linked = binary.with_suffix('.link').read_text().splitlines()
        objects = [Path(line) for line in linked if line.endswith(('pastls.o', 'pascipher.o'))]
        require(sorted(obj.name for obj in objects) == ['pascipher.o', 'pastls.o'],
                'missing linked TLS or cipher object')
        proof['binaries'][cpu] = {
            'paslang_sha256': sha256(binary.read_bytes()).hexdigest(),
            'go_sha256': sha256(go.read_bytes()).hexdigest(),
            'linked_units': {str(obj): sha256(obj.read_bytes()).hexdigest() for obj in objects},
        }
        pinned_server = ['taskset', '-c', str(args.server_cpu)]
        pinned_client = ['taskset', '-c', ','.join(map(str, args.client_cpus))]
        debug = 'cpu.all=off' if cpu == 'base' else ''
        commands = {
            'go': ['env', 'GOMAXPROCS=1', f'GODEBUG={debug}', *pinned_server, go],
            'paslang': [*pinned_server, binary],
        }
        load = ['env', f'GOMAXPROCS={len(args.client_cpus)}', f'GODEBUG={debug}', *pinned_client, go]
        for version, mode in product(args.version, ('handshake', 'transfer')):
            iterations = args.handshakes if mode == 'handshake' else args.transfers
            pair = {'cpu': cpu, 'tls': version, 'mode': mode, 'rounds': []}
            proof['pairs'].append(pair)
            for index in range(args.rounds):
                order = ('go', 'paslang') if index % 2 == 0 else ('paslang', 'go')
                row = {'order': order}
                pair['rounds'].append(row)
                for side in order:
                    row[side] = sample(commands[side], load, version, cpu, mode,
                                       args.workers, iterations, file)
                require(row['go']['cipher'] == row['paslang']['cipher'], 'different ciphers')
                row['paslang_over_go'] = row['paslang']['rate'] / row['go']['rate']
            ratios = [row['paslang_over_go'] for row in pair['rounds']]
            pair['median_ratio'] = statistics.median(ratios)
            pair['paslang_faster'] = pair['median_ratio'] > 1
            median = {side: statistics.median(row[side]['rate'] for row in pair['rounds'])
                      for side in commands}
            print(f'{cpu:6} TLS {version} {mode:9} Go {median["go"]:12.1f} '
                  f'Paslang {median["paslang"]:12.1f} ratio {pair["median_ratio"]:.3f}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--units', type=Path)
    parser.add_argument('--go-amd64', choices=('v1', 'v2', 'v3', 'v4'))
    parser.add_argument('--json', type=Path, required=True)
    parser.add_argument('--cpu', action='append', choices=('base', 'native'))
    parser.add_argument('--version', action='append', choices=('1.2', '1.3'))
    parser.add_argument('--server-cpu', type=int, required=True)
    parser.add_argument('--client-cpus', type=int, nargs='+', required=True)
    parser.add_argument('--rounds', type=int, default=7)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--handshakes', type=int, default=96, help='connections per worker per round')
    parser.add_argument('--transfers', type=int, default=4, help='4 MiB responses per worker per round')
    args = parser.parse_args()
    args.cpu = args.cpu or ['native', 'base']
    args.version = args.version or ['1.3', '1.2']
    cpus = [args.server_cpu, *args.client_cpus]
    if len(set(cpus)) != len(cpus) or not set(cpus) <= os.sched_getaffinity(0):
        parser.error('server and client CPUs must be distinct and available')
    if (min(args.rounds, args.workers, args.handshakes, args.transfers) <= 0
            or len(set(args.cpu)) != len(args.cpu) or len(set(args.version)) != len(args.version)):
        parser.error('provide positive workload sizes and distinct CPU profiles and versions')
    proof = {
        'format': 'paslang-tls-server-bench-v1', 'machine': platform.platform(),
        'settings': {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
        'pairs': [], 'valid': False, 'goal_met': False,
    }
    try:
        with TemporaryDirectory(prefix='paslang-tls-bench-') as tmp:
            benchmark(args, Path(tmp), proof)
        proof['valid'] = True
        proof['goal_met'] = all(pair['paslang_faster'] for pair in proof['pairs'])
    except Exception as error:
        proof['error'] = f'{type(error).__name__}: {error}'
        if isinstance(error, CalledProcessError):
            proof['diagnostics'] = error.stderr.decode(errors='replace')
            print(proof['diagnostics'], file=sys.stderr, end='')
        print(proof['error'], file=sys.stderr)
    finally:
        save(args.json, proof)
    return 0 if proof['goal_met'] else 1 if proof['valid'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
