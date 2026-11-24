#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Follow PrivateOp and its callees in the production parser's tree.

Limb counts, string lengths, valid key parity, and the public key
are public. Track the data behind an address independently of the address.
Reject unreviewed operations and calls, including indirect control flow.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
from tempfile import mkdtemp

ROOT = Path(__file__).resolve().parents[1]
DIT_ENTER = 'p_f.11_pasroutines11_pasditenter'
DIT_LEAVE = 'p_f.11_pasroutines11_pasditleave'


class Unsafe(Exception):
    pass


@dataclass(frozen=True)
class Value:
    # An empty path denotes scalar data or all contents of an aggregate.
    secret: frozenset = frozenset()
    addresses: frozenset = frozenset()

    def __or__(self, other):
        return Value(self.secret | other.secret, self.addresses | other.addresses)

    def field(self, name):
        if () in self.secret:
            return SECRET
        return Value(frozenset(p[1:] for p in self.secret if p[0] == name))


PUBLIC = Value()
SECRET = Value(frozenset({()}))
KEY = Value(frozenset({('d',), ('dp',), ('dq',), ('qinv',)}
                      | {(prime, field) for prime in ('p', 'q')
                         for field in ('nat', 'm0inv', 'rr')}))


def merge(left, right):
    return {name: left.get(name, PUBLIC) | right.get(name, PUBLIC)
            for name in left.keys() | right.keys()}


def combine(values):
    total = PUBLIC
    for value in values:
        total |= value
    return total


class Check:
    def __init__(self, functions):
        self.functions = {fn['sym'].lower(): fn for fn in functions}
        self.reached = set()
        self.active = set()
        self.cache = {}

    def routine(self, sym, inputs, pointed):
        key = (sym, inputs, pointed)
        if key in self.cache:
            return self.cache[key]
        fn = self.functions[sym]
        if sym in self.active:
            raise Unsafe(f"recursive call in {fn['name']}")
        self.active.add(sym)
        self.reached.add(fn['name'])
        frame = Frame(self, fn, inputs, pointed)
        frame.statement(fn['body'])
        answer = frame.outputs()
        self.active.remove(sym)
        self.cache[key] = answer
        return answer


class Frame:
    def __init__(self, check, fn, inputs, pointed):
        self.check = check
        self.function = fn
        self.parameters = [param['name'].lower() for param in fn['params']]
        self.pointed = pointed
        self.known = {*self.parameters, 'result', *(name.lower() for name in fn['locals'])}
        self.state = dict(zip(self.parameters, inputs, strict=True))
        self.exits = PUBLIC
        self.outputs_seen = self.state.copy()
        for number, value in enumerate(pointed):
            if value is not None:
                memory = f'@{number}'
                self.state[memory] = value
                self.state[self.parameters[number]] = Value(addresses=frozenset({(memory,)}))

    def outputs(self):
        state = merge(self.state, self.outputs_seen)
        return (self.state.get('result', PUBLIC) | self.exits,
                tuple(state.get(p, PUBLIC) for p in self.parameters),
                tuple(None if p is None else state[f'@{i}'] for i, p in enumerate(self.pointed)))

    def fail(self, node, message):
        raise Unsafe(f"{self.function['name']}:{node['line']}: {message}")

    def require_public(self, value, node, message):
        if value.secret:
            self.fail(node, message)

    def read(self, locations):
        values = []
        for base, *path in locations:
            value = self.state.get(base, PUBLIC)
            for field in path:
                value = value.field(field)
            values.append(value)
        return combine(values)

    def write(self, locations, value):
        for base, *path in locations:
            if path:
                assert not value.addresses
                secrets = frozenset(tuple(path) + field for field in value.secret)
                self.state[base] = self.state.get(base, PUBLIC) | Value(secrets)
            else:
                self.state[base] = value

    def address(self, node):
        kind = node['kind']
        if kind == 2:
            name = node['name'].lower()
            if name not in self.known:
                self.fail(node, f'unreviewed variable {name}')
            return frozenset({(name,)})
        if kind == 6:
            return frozenset(place + (node['name'].lower(),) for place in self.address(node['l']))
        if kind == 7:
            pointer = self.expr(node['l'])
            self.require_public(pointer, node, 'secret-dependent indirect address')
            if not pointer.addresses:
                self.fail(node, 'unreviewed pointer dereference')
            return pointer.addresses
        if kind == 8:
            index = self.expr(node['r'])
            self.require_public(index, node, 'secret-dependent memory index')
            base = self.expr(node['l'])
            if node['l']['typekind'] == 5 or base.addresses:
                self.require_public(base, node, 'secret-dependent pointer index')
                if not base.addresses:
                    self.fail(node, 'unreviewed pointer index')
                return base.addresses
            return frozenset(place + ('*',) for place in self.address(node['l']))
        self.fail(node, 'unreviewed address')

    @staticmethod
    def zero(node):
        return node['kind'] == 0 and node['num'] == 0

    @staticmethod
    def empty_string(node):
        return node['kind'] == 1 and node['bytes'] == 0

    def expr(self, node):
        if node is None:
            return PUBLIC
        kind = node['kind']
        if kind in (0, 1, 9):
            return PUBLIC
        if kind in (2, 6, 7, 8):
            return self.read(self.address(node))
        if kind == 17:
            return Value(addresses=self.address(node['l']))
        if kind == 4:
            if node['un'] not in (0, 1, 2, 7):
                self.fail(node, 'unreviewed unary operation')
            return self.expr(node['l'])
        if kind == 5:
            return self.call(node)
        if kind == 3:
            left, right = self.expr(node['l']), self.expr(node['r'])
            op = node['bin']
            if op in (5, 6) and (self.empty_string(node['l']) or self.empty_string(node['r'])):
                return PUBLIC  # The compiler compares only the string length.
            if (node['l']['typekind'] == 3 or node['r']['typekind'] == 3):
                self.require_public(left | right, node, 'secret-dependent string operation')
            if left.addresses or right.addresses:
                self.require_public(left | right, node, 'secret-dependent address arithmetic')
                if op not in (0, 1) or not left.addresses or right.addresses:
                    self.fail(node, 'unreviewed pointer arithmetic')
                return left
            value = SECRET if (left | right).secret else PUBLIC
            if op in (3, 4, 20):
                self.require_public(value, node, 'secret-dependent division')
            if op in (18, 19, 21, 22, 23):
                self.require_public(right, node, 'secret-dependent shift count')
            if op in (11, 12) and node['typekind'] == 2:
                self.require_public(value, node, 'secret-dependent Boolean evaluation')
            return value
        self.fail(node, f'unreviewed expression kind {kind}')

    def call(self, node):
        sym = node['name'].lower()
        args = node['args']
        values = [self.expr(arg) for arg in args]
        if sym in ('rt_addc', 'rt_subb'):
            if len(values) != 5 or not values[3].addresses:
                self.fail(node, 'unexpected carry intrinsic ABI')
            self.require_public(values[4], node, 'secret carry-width selector')
            value = SECRET if combine(values[:3]).secret else PUBLIC
            self.write(values[3].addresses, value)
            return value
        if sym == 'rt_length' and len(values) == 1:
            return PUBLIC
        if sym in ('rt_setlength', 'rt_fillchar'):
            if not values or not values[0].addresses:
                self.fail(node, 'unexpected memory intrinsic ABI')
            self.require_public(combine(values[1:]), node, 'secret memory size or fill')
            return PUBLIC
        if sym == DIT_ENTER and not values:
            return PUBLIC
        if sym == DIT_LEAVE and len(values) == 1:
            self.require_public(values[0], node, 'secret-dependent DIT setting')
            return PUBLIC
        if sym not in self.check.functions:
            self.fail(node, f'unreviewed call {sym}')
        params = self.check.functions[sym]['params']
        if len(params) != len(values):
            self.fail(node, 'unexpected argument count')
        inputs, pointed, locations = [], [], []
        for param, value, arg in zip(params, values, args, strict=True):
            place = value.addresses
            if param['byref']:
                if not place:
                    self.fail(node, 'unreviewed reference parameter')
                inputs.append(self.read(place))
                pointed.append(None)
            else:
                inputs.append(value if not place else PUBLIC)
                pointed.append(self.read(place) if place else None)
                if not place and param['const'] and arg['typekind'] in (3, 4, 6):
                    if arg['kind'] in (2, 6, 7, 8):
                        place = self.address(arg)
            locations.append(place)
        # By-ref and const arguments can name the same storage. Feed any
        # new secrets written through one alias back to the other aliases
        # until the call's input/output taint settles.
        result = PUBLIC
        for _ in range(64):
            answer, outputs, memory = self.check.routine(sym, tuple(inputs), tuple(pointed))
            result |= answer
            for i, param in enumerate(params):
                if param['byref']:
                    self.write(locations[i], self.read(locations[i]) | outputs[i])
                elif memory[i] is not None:
                    self.write(locations[i], self.read(locations[i]) | memory[i])
            revised, revised_points = list(inputs), list(pointed)
            for i, place in enumerate(locations):
                if not place or not any(
                    self.overlap(place, locations[j])
                    for j, param in enumerate(params)
                    if i != j and (param['byref'] or memory[j] is not None)
                ):
                    continue
                if pointed[i] is None:
                    revised[i] |= self.read(place)
                else:
                    revised_points[i] |= self.read(place)
            if (inputs, pointed) == (revised, revised_points):
                return result
            inputs, pointed = revised, revised_points
        self.fail(node, 'call alias analysis did not converge')

    @staticmethod
    def overlap(left, right):
        return any(a[:min(len(a), len(b))] == b[:min(len(a), len(b))]
                   for a in left for b in right)

    def releases_status(self, node):
        """The two observable rejection decisions, at their exact sites."""
        cond, yes = node['e'], node['then']
        if node['else'] is not None or cond['kind'] != 3 or cond['bin'] != 6:
            return False
        left, right = cond['l'], cond['r']
        if self.function['name'] == 'privateop':
            return (left['kind'] == 5 and left['name'].lower() == 'p_f.6_pasrsa8_natequal'
                    and [a['name'].lower() for a in left['args']] == ['check', 'cn']
                    and right['kind'] == 0 and right['num'] == 1
                    and yes['kind'] == 21 and yes['e'] is None)
        if self.function['name'] == 'natbytes':
            return (left['kind'] == 2 and left['name'].lower() == 'overflow'
                    and self.zero(right) and yes['kind'] == 0
                    and yes['dest']['kind'] == 2 and yes['dest']['name'].lower() == 'result'
                    and self.empty_string(yes['e']))
        return False

    def statement(self, node):
        if node is None:
            return
        if node['arms'] or node['sels']:
            self.fail(node, 'unreviewed multi-branch statement')
        kind = node['kind']
        if kind == 0:
            value = self.expr(node['e'])
            self.write(self.address(node['dest']), value)
        elif kind == 7:
            for child in node['stmts']:
                self.statement(child)
        elif kind == 9:
            self.call(node)
        elif kind == 3:
            condition = self.expr(node['e'])
            if not self.releases_status(node):
                self.require_public(condition, node, 'secret-dependent conditional')
            before = self.state.copy()
            self.statement(node['then'])
            yes = self.state
            self.state = before
            self.statement(node['else'])
            self.state = merge(yes, self.state)
        elif kind in (4, 5):
            self.require_public(self.expr(node['e']) | self.expr(node['e2']), node,
                                'secret-dependent loop bound')
            if kind == 5:
                self.state[node['name'].lower()] = PUBLIC
            for _ in range(64):
                before = self.state.copy()
                self.statement(node['body'])
                if kind == 4:
                    self.require_public(self.expr(node['e']), node, 'secret-dependent loop bound')
                if kind == 5:
                    self.require_public(self.state[node['name'].lower()], node, 'secret induction variable')
                self.state = merge(before, self.state)
                if self.state == before:
                    break
            else:
                self.fail(node, 'loop analysis did not converge')
        elif kind == 17:
            # PrivateOp's try/finally around the runtime DIT scope.
            after = node['else']
            if (self.function['name'] != 'privateop' or node['body'] or node['stmts']
                    or not node['then'] or not after or after['kind'] != 7
                    or len(after['stmts']) != 1 or after['stmts'][0]['kind'] != 9
                    or after['stmts'][0]['name'].lower() != DIT_LEAVE):
                self.fail(node, 'unreviewed exception handler')
            self.statement(node['then'])
            self.statement(after)
        elif kind == 21:
            self.exits |= self.expr(node['e'])
            self.outputs_seen = merge(self.outputs_seen, self.state)
        elif kind in (23, 24):
            dest = self.address(node['dest'])
            self.write(dest, combine((self.read(dest), self.expr(node['e']))))
        elif kind not in (25, 26):
            self.fail(node, f'unreviewed statement kind {kind}')


def audit(functions):
    check = Check(functions)
    entry, = (symbol for symbol, fn in check.functions.items() if fn['name'] == 'privateop')
    check.routine(entry, (KEY, PUBLIC, PUBLIC), (None, None, None))
    return sorted(check.reached)


def run(argv):
    result = subprocess.run(argv, capture_output=True, check=True, timeout=180)
    if result.stderr:
        raise RuntimeError(result.stderr.decode(errors='replace'))
    return result.stdout


def main():
    compiler, build = (Path(arg).resolve() for arg in sys.argv[1:])
    stage = build / 'stage'
    work = Path(mkdtemp(prefix='rsa-ct-', dir=build))
    parser = work / 'ctast'
    run([compiler, '-cpu', 'base', '-Fu', stage, '-Fu', build, '-o', parser,
         ROOT / 'scripts/fixtures/nist_ctast.paslang'])
    source = (ROOT / 'src/lib/pasrsa.paslang').read_text()
    body = source.index('\nprocedure NatMontgomeryMul(', source.index('\nimplementation\n'))
    before, core = source[:body], source[body:]
    limb = '    d := B.Limbs[i];'
    bound = '  for i := 0 to n - 1 do'
    assert core.count(limb) == 1 and bound in core
    variants = {
        'production': (source, ''),
        'secret-branch': (before + core.replace(limb, limb + '\n    if d <> 0 then d := d + 1;', 1),
                          'secret-dependent conditional'),
        'secret-index': (before + core.replace(limb, '    d := B.Limbs[i+(B.Limbs[0] and 1)];', 1),
                         'secret-dependent memory index'),
        'secret-bound': (before + core.replace(bound, '  for i := 0 to (B.Limbs[0] and 1) do', 1),
                         'secret-dependent loop bound'),
    }
    for target, sdk in (('amd64', build), ('arm64', build / 'a64')):
        for label, (text, expected) in variants.items():
            path = work / f'{target}-{label}.paslang'
            path.write_text(text)
            tree = run([parser, path, sdk, stage, target, 'rsa'])
            path.with_suffix('.json').write_bytes(tree)
            functions = json.loads(tree)
            try:
                reached = audit(functions)
            except Unsafe as error:
                assert expected and expected in str(error), (target, label, error)
                print(target, label, error, flush=True)
            else:
                assert not expected, (target, label)
                print(f'{target} audited PrivateOp and {len(reached) - 1} callees',
                      ', '.join(reached), flush=True)
            for inline in ('0', '40'):
                output = work / f'{target}-{label}-{inline}'
                run([compiler, '-target', target, '-cpu', 'base', '-inline', inline,
                     '-Fu', sdk, '-c', '-o', output, path])


if __name__ == '__main__':
    main()
