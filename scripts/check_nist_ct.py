#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Conservative secret-flow check over the production parser's actual ASTs.

The curve order C and announced lengths are public. Scalar operands, output
values and carry inputs are secret. This checks control, addressing, division
and variable shift counts, rather than matching a particular mask spelling.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[1]
compiler = Path(sys.argv[1]).resolve()
build = Path(sys.argv[2]).resolve()
root = Path(tempfile.mkdtemp(prefix='nist-ct-', dir=build))
parser = build / 'stage'
helpers = {'p_f.7_pasnist11_orderreduce', 'p_f.7_pasnist12_ordermontmul',
           'p_f.7_pasnist8_ordermul', 'p_f.7_pasnist8_orderadd', 'p_f.7_pasnist12_orderinverse'}


class Unsafe(Exception):
    pass


def check(functions):
    reports = []
    for function in functions:
        name = function['name']
        state = {p['name'].lower(): p['name'].lower() != 'c' for p in function['params']}
        assert function['params'][0]['name'].lower() == 'c'
        assert function['params'][0]['const'] == 1
        counters = {'controls': 0, 'addresses': 0, 'calls': 0}

        def fail(reason, node):
            raise Unsafe(f'{name}:{node.get("line", 0)}: {reason}')

        def variable(node):
            if node['kind'] == 2:
                return node['name'].lower()
            if node['kind'] in (6, 8, 17):
                return variable(node['l'])
            fail('unsupported output location', node)

        def address(node):
            if node['kind'] == 2:
                return
            if node['kind'] in (6, 17):
                address(node['l'])
                return
            if node['kind'] == 8:
                counters['addresses'] += 1
                if expr(node['r']):
                    fail('secret-dependent memory index', node)
                address(node['l'])
                return
            fail('unsupported indirect address', node)

        def assign(node, secret):
            address(node)
            key = variable(node)
            if key == 'c':
                fail('public curve order is modified', node)
            state[key] = secret if node['kind'] == 2 else state.get(key, False) or secret

        def call(symbol, args, node):
            counters['calls'] += 1
            if symbol in ('rt_addc', 'rt_subb'):
                if len(args) != 5 or args[3]['kind'] != 17:
                    fail('unexpected carry intrinsic ABI', node)
                secret = any([expr(x) for x in args[:3]])
                if expr(args[4]):
                    fail('secret carry-width selector', node)
                assign(args[3]['l'], secret)
                return secret
            if symbol in helpers:
                if len(args) < 3 or args[1]['kind'] != 17:
                    fail('unexpected order-helper ABI', node)
                if expr(args[0]):
                    fail('secret curve-order parameter', node)
                secret = any([expr(x) for x in args[2:]])
                if symbol == 'p_f.7_pasnist11_orderreduce':
                    secret = state.get(variable(args[1]), False) or secret
                assign(args[1]['l'], secret)
                return secret
            fail('unreviewed call: ' + symbol, node)

        def expr(node):
            if node is None:
                return False
            kind = node['kind']
            if kind == 0:
                return False
            if kind == 2:
                key = node['name'].lower()
                if key not in state:
                    fail('unclassified variable ' + key, node)
                return state[key]
            if kind == 3:
                left, right = expr(node['l']), expr(node['r'])
                if node['bin'] in (3, 4, 20) and (left or right):
                    fail('secret-dependent division/remainder', node)
                if node['bin'] in (18, 19, 21, 22, 23) and right:
                    fail('secret variable shift count', node)
                return left or right
            if kind == 4:
                if node['un'] not in (0, 1, 2):
                    fail('unreviewed unary operation', node)
                return expr(node['l'])
            if kind == 5:
                return call(node['name'].lower(), node['args'], node)
            if kind == 6:
                return expr(node['l'])
            if kind == 8:
                address(node)
                return expr(node['l'])
            if kind == 17:
                address(node['l'])
                return False
            fail('unreviewed expression kind ' + str(kind), node)

        def statement(node):
            if node is None:
                return
            kind = node['kind']
            if kind == 0:
                secret = expr(node['e'])
                assign(node['dest'], secret)
            elif kind == 7:
                for child in node['stmts']:
                    statement(child)
            elif kind == 9:
                call(node['name'].lower(), node['args'], node)
            elif kind == 3:
                counters['controls'] += 1
                if expr(node['e']):
                    fail('secret-dependent conditional', node)
                before = state.copy()
                statement(node['then'])
                left = state.copy()
                state.clear()
                state.update(before)
                statement(node['else'])
                for key in set(left) | set(state):
                    state[key] = left.get(key, False) or state.get(key, False)
            elif kind == 5:
                counters['controls'] += 1
                if expr(node['e']) or expr(node['e2']):
                    fail('secret-dependent loop bound', node)
                induction = node['name'].lower()
                state[induction] = False
                for _ in range(64):
                    before = state.copy()
                    statement(node['body'])
                    if state.get(induction, False):
                        fail('secret induction-variable update', node)
                    merged = {key: state.get(key, False) or before.get(key, False)
                              for key in set(state) | set(before)}
                    state.update(merged)
                    if state == before:
                        break
                else:
                    fail('loop analysis did not converge', node)
            else:
                fail('unreviewed statement kind ' + str(kind), node)

        statement(function['body'])
        reports.append({'function': name, **counters})
    return reports


source = (repo / 'src/lib/pasnist.paslang').read_text()
source_hash = hashlib.sha256(source.encode()).hexdigest()
old = (repo / 'scripts/fixtures/nist_order_variable.inc').read_text()
command = [str(compiler), '-cpu', 'native', '-inline', '0', '-Fu', str(parser),
           '-Fu', str(build), '-o', str(root / 'ctast'),
           str(repo / 'scripts/fixtures/nist_ctast.paslang')]
compiled = subprocess.run(command, capture_output=True, timeout=180)
(root / 'compile.stdout').write_bytes(compiled.stdout)
(root / 'compile.stderr').write_bytes(compiled.stderr)
assert compiled.returncode == 0, compiled.stderr
start, end = 'procedure OrderMontMul(', '\n{ Z = A B mod n }'
original = old[old.index(start):]
current = source[source.index(start):source.index(end, source.index(start))]
variants = {'production': source,
            'old-secret-final-branch': source.replace(current, original, 1),
            'secret-index': source.replace('Mul128(A[i], B[j], hi, lo);',
                'Mul128(A[A[0] and 3], B[j], hi, lo);', 1),
            'secret-loop': source.replace('for i := 0 to L - 1 do',
                'for i := 0 to (A[0] and 3) do', 1),
            'secret-inverse-exponent': source.replace('C.NMinus2[i div 64]', 'A[i div 64]', 1)}
assert len(set(variants.values())) == len(variants)
results = []
for label, text in variants.items():
    path = root / (label + '.paslang')
    path.write_text(text)
    for target in ('amd64', 'arm64'):
        command = [str(root / 'ctast'), str(path), str(build / (
            'a64' if target == 'arm64' else '')), str(parser), target]
        result = subprocess.run(command, cwd=root, capture_output=True, timeout=180)
        prefix = root / (label + '-' + target)
        prefix.with_suffix('.stdout').write_bytes(result.stdout)
        prefix.with_suffix('.stderr').write_bytes(result.stderr)
        assert result.returncode == 0, (label, target, result.stderr)
        assert hashlib.sha256((repo / 'src/lib/pasnist.paslang').read_bytes()).hexdigest() == source_hash
        error = None
        try:
            reports = check(json.loads(result.stdout))
        except Unsafe as rejected:
            reports, error = [], str(rejected)
        assert (error is None) == (label == 'production'), (label, target, error)
        row = {'variant': label, 'target': target, 'parse_exit': result.returncode,
               'source_sha256': hashlib.sha256(text.encode()).hexdigest(),
               'accepted': error is None, 'diagnostic': error, 'functions': reports}
        results.append(row)
        print(label, target, 'accepted' if error is None else error, flush=True)
(root / 'taint-status.json').write_text(json.dumps({'ok': True, 'results': results}, indent=2) + '\n')
