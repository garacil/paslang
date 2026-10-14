#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P203: paslang's JSON parser and writer held to Go's encoding/json/v2.

The documents: the hand cases below, JSONTestSuite's test_parsing
(testdata/json/suite), Go's corpus (testdata/json/corpus, zstd, read
with Python's compression.zstd) and documents made from the first two by
mutation, from fixed seeds. For each, build/jsoncheck (testdata/
jsoncheck.paslang) writes in modes p, i and c what Go writes
(testdata/json/oracle.go): the document compact, a value a line, in RFC
8785's form, or the error's offset, pointer and reason; mode P parses
it with the index and a byte at a time and must give the same.

Python's json, made strict (no NaN, no name twice, no lone surrogate),
must take and refuse the same documents, but for a noncharacter.

paslang's output must be testdata/json/expect.txt, which holds the hand
cases' and the suite's lines as they are and a SHA-256 of the corpus'
and the mutations' (so the file stays small). With Go there (the
oracle's binary as the second argument), Go's output must be the same
but for one difference, paslang's on purpose: a noncharacter (U+FDD0 to
U+FDEF and the last two of every plane, RFC 7493 2.1) is refused, where
Go takes it; there paslang's error must be at the place of the first
noncharacter, raw or escaped, as this script finds it, and Go must take
the text or fail at that byte or after it.
--update writes expect.txt from Go's output so checked.

usage: check_json.py [--qemu=QEMU] build/jsoncheck [build/json/oracle | -] [--update]
(--qemu runs an arm64 jsoncheck under that QEMU.)"""
import glob
import hashlib
import os
import random
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TD = os.path.join(ROOT, 'testdata', 'json')

CASES = [
    b'[1,]', b'{"a":1,}', b'{"a":1 "b":2}', b'[1 2]', b'[1x]', b'1 2', b'{"a":[1,{"b":tru}]}',
    b'{"a":1,"a":2}', b'["\\ud800"]', b'{"x":"a\\u0001\x01"}', b'[[[["a\\q"]]]]', b'{1:2}',
    b'{"a" 1}', b'[-]', b'[01]', b'["\xff"]', b'[1', b'{"a":{"b":[1,2', b'', b'  ',
    b'{"a\\q":1}', b'[1,', b'{"a":', b'{"a"', b'{"a', b'["ab', b'{"a":["x","y\\u12',
    b'[{}, {"k": [1, 2, 3, x]}]', b'[{}, {"k": [1, 2, 3], }]', b'{"a~/b":[nul]}', b'[1.]', b'[1e]',
    b'[1.5e+]', b'[-01]', b'["a" : 1]', b'["\\uDFFF"]', b'["\\uD800\\u0041"]', b'["\\u00G0"]',
    b'"\\uD83D\\uDE00"', b'[true false]', b'{"a":1}}', b'[1]]', b']', b'{"":1,"":2}',
    b'["a\\u0000"]', b'{"a":[1,2,{"b":null,"c":[true,false,"x\\"y"]}],"d":-0.5e-3}', b'0', b'-0',
    b'1e400', b'"\\u00e9\\n\\t\\/"', b'[[[[[[[[[[]]]]]]]]]]', b' {"a" : [ 1 , 2 ] } ', b'"abc',
    b'"\\', b'"\\u', b'"\\u00', b'"\\ud800', b'"\\ud800\\', b'"\\ud800\\u', b'"\\ud800\\udc',
    b'"\\ud800\\ud', b'"\\ud800\\ux', b'tr', b'nul', b'fals', b'-', b'1.', b'1e+',
    b'{"a":1,"b":2,"c":3,"d":4,"e":5,"f":6,"g":7,"h":8,"i":9,"j":10,"k":11,"l":12,"m":13,'
    b'"n":14,"o":15,"p":16,"q":17,"r":18,"a":19}',
    b'{' + b','.join(b'"k%d":%d' % (i, i) for i in range(200)) + b',"k150":0}',
    b'{' + b','.join(b'"k%d":%d' % (i, i) for i in range(200)) + b'}',
    b'"\xef\xbf\xbe"', b'"\\uFFFE"', b'"\\uFDD0"', b'"\\uD83F\\uDFFF"', b'["\xed\xa0\x80"]',
    b'"\xc3"', b'\xef\xbb\xbf1', b'[1]\x00', b'//c\n1', b'NaN', b'[Infinity]', b'+1', b'.5',
    b'0x10', b'1E2', b'1e-2', b'123456789012345678901234567890',
    b'{"a" :1 ,"b":[ ] , "c" : { } }', b'"\t"', b'["\x7f"]', b'"\xf4\x8f\xbf\xbd"',
    b'[' * 10000 + b']' * 10000, b'[' * 10001 + b']' * 10001,
    b'{"<&>":"\xe2\x80\xa8\xe2\x80\xa9","\\u2028":"\\u003c"}',
    b'[1e-7,1e21,1e20,-1.5e-7,0.000001,123e-2,5e-324,1.7976931348623157e308,1e309]',
]


def mutations(seeds, n, seed):
    rnd = random.Random(seed)
    pool = [s for s in seeds if len(s) < 4000]
    alpha = (b'{}[]:,"\\ \t\n\r0123456789-+.eEtrufalsn\x00\x1f\x7f\xc3\xa9\xe2\x82\xac'
             b'\xf0\x9f\x98\x80\xff\xed\xa0\x80uU/bfnrt')
    out = []
    for _ in range(n):
        s = bytearray(rnd.choice(pool))
        for _ in range(rnd.randint(1, 4)):
            op = rnd.randint(0, 5)
            if op == 0 and s:
                s[rnd.randrange(len(s))] = rnd.choice(alpha)
            elif op == 1:
                s.insert(rnd.randint(0, len(s)), rnd.choice(alpha))
            elif op == 2 and s:
                del s[rnd.randrange(len(s))]
            elif op == 3 and s:
                s = s[:rnd.randint(0, len(s))]
            elif op == 4:
                t = rnd.choice(pool)
                i = rnd.randint(0, len(t))
                j = rnd.randint(i, len(t))
                k = rnd.randint(0, len(s))
                s[k:k] = t[i:j]
            elif op == 5:
                s = bytearray(b'[' * rnd.randint(1, 5)) + s + bytearray(b']' * rnd.randint(0, 5))
        out.append(bytes(s))
    return out


def documents():
    suite = [open(f, 'rb').read() for f in sorted(glob.glob(os.path.join(TD, 'suite', '*.json')))]
    import compression.zstd
    corpus = [compression.zstd.decompress(open(f, 'rb').read())
              for f in sorted(glob.glob(os.path.join(TD, 'corpus', '*.json.zst')))]
    muts = mutations(CASES + suite, 20000, 1)
    return [('case', CASES), ('suite', suite), ('corpus', corpus), ('mutation', muts)]


def run(prog, mode, docs):
    data = ''.join((d.hex() if d else '-') + '\n' for d in docs).encode()
    r = subprocess.run(prog + [mode], input=data, capture_output=True, timeout=1800)
    if r.returncode != 0:
        sys.exit('%s %s exited %d: %s' % (prog[0], mode, r.returncode, r.stderr.decode()[-2000:]))
    lines = r.stdout.decode('utf-8', 'surrogateescape').split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    if len(lines) != len(docs):
        sys.exit('%s %s wrote %d lines for %d documents' % (prog[0], mode, len(lines), len(docs)))
    return lines


def nonchar_at(d):
    """The place of the first noncharacter of the text, raw or escaped
    (\\uXXXX, or a surrogate pair), or -1."""
    i = 0
    while i < len(d):
        b = d[i]
        if b == 0x5c and d[i + 1:i + 2] == b'u':
            h = d[i + 2:i + 6]
            try:
                v = int(h, 16)
            except ValueError:
                i += 1
                continue
            if 0xD800 <= v <= 0xDBFF and d[i + 6:i + 8] == b'\\u':
                try:
                    w = int(d[i + 8:i + 12], 16)
                    v = 0x10000 + ((v - 0xD800) << 10) + (w - 0xDC00)
                except ValueError:
                    pass
            if 0xFDD0 <= v <= 0xFDEF or (v & 0xFFFE) == 0xFFFE:
                return i
            i += 2
            continue
        if b >= 0x80:
            for n in (4, 3, 2):
                try:
                    c = d[i:i + n].decode('utf-8')
                except UnicodeDecodeError:
                    continue
                if len(c) == 1:
                    v = ord(c)
                    if 0xFDD0 <= v <= 0xFDEF or (v & 0xFFFE) == 0xFFFE:
                        return i
                    i += n - 1
                    break
        i += 1
    return -1


def py_verdict(d):
    """Python's json made strict, the second oracle: True when it takes
    the text as I-JSON, False when not, None when it cannot say (a
    nesting past its recursion). Its decoder takes NaN, a name twice and
    a lone surrogate escape; here they are refused, as UTF-8 that is not
    and a byte order mark. It takes a noncharacter, as Go. A nesting past
    10000, the limit of Go and of paslang, it may take: no verdict."""
    import json as pyjson
    try:
        text = d.decode('utf-8')
    except UnicodeDecodeError:
        return False
    if text.startswith('\ufeff'):
        return False

    def pairs(ps):
        if len({k for k, _ in ps}) != len(ps):
            raise ValueError('a name twice')
        return dict(ps)

    def constant(c):
        raise ValueError(c)

    try:
        v = pyjson.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except RecursionError:
        return None
    except ValueError:
        return False
    work = [(v, 0)]
    while work:
        x, depth = work.pop()
        if isinstance(x, str):
            if any(0xD800 <= ord(c) <= 0xDFFF for c in x):
                return False
        elif isinstance(x, dict):
            if depth >= 10000:
                return None
            for k, y in x.items():
                work.append((k, depth + 1))
                work.append((y, depth + 1))
        elif isinstance(x, list):
            if depth >= 10000:
                return None
            work.extend((y, depth + 1) for y in x)
    return True


def squeeze(groups, lines):
    """The lines of the cases and the suite as they are; of the corpus and
    the mutations, a SHA-256 of each group's."""
    out = []
    k = 0
    for name, docs in groups:
        part = lines[k:k + len(docs)]
        k += len(docs)
        if name in ('case', 'suite'):
            out += ['%s %s' % (name, l) for l in part]
        else:
            out.append('%s sha256 %s' % (name, hashlib.sha256('\n'.join(part).encode(
                'utf-8', 'surrogateescape')).hexdigest()))
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    update = '--update' in sys.argv
    pas = [args[0]]
    for a in sys.argv[1:]:
        if a.startswith('--qemu='):
            pas = [a[len('--qemu='):], args[0]]
    gobin = args[1] if len(args) > 1 and args[1] != '-' else None
    groups = documents()
    docs = [d for _, ds in groups for d in ds]
    bad = 0
    same = run(pas, 'P', docs)
    for d, l in zip(docs, same):
        if l != 'same':
            bad += 1
            if bad < 10:
                print('index and plain differ on %r: %s' % (d[:80], l))
    got = {}
    for mode in 'pic':
        got[mode] = run(pas, mode, docs)
    for d, g in zip(docs, got['p']):
        pv = py_verdict(d)
        if pv is None or pv == g.startswith('ok '):
            continue
        if pv and 'noncharacter' in g and nonchar_at(d) >= 0:
            continue
        bad += 1
        if bad < 20:
            print('Python (strict) %s %r, paslang: %s' % ('takes' if pv else 'refuses', d[:120],
                                                       g[:200]))
    if gobin:
        for mode in 'pic':
            want = run([gobin], mode, docs)
            for i, (d, g, w) in enumerate(zip(docs, got[mode], want)):
                if g == w:
                    continue
                at = nonchar_at(d)
                if at >= 0 and g.startswith('err %d ' % at) and 'noncharacter' in g and \
                        (w.startswith('ok ') or int(w.split()[1]) >= at):
                    continue
                bad += 1
                if bad < 20:
                    print('%s: Go and paslang differ on %r\n  go:      %s\n  paslang: %s' %
                          (mode, d[:120], w[:300], g[:300]))
    exp = []
    for mode in 'pic':
        exp += ['%s %s' % (mode, l) for l in squeeze(groups, got[mode])]
    path = os.path.join(TD, 'expect.txt')
    if update:
        if not gobin:
            sys.exit('--update needs Go\'s oracle')
        if bad:
            sys.exit('%d differences: expect.txt not written' % bad)
        open(path, 'w', encoding='utf-8', errors='surrogateescape').write('\n'.join(exp) + '\n')
        print('wrote', path)
        return
    old = open(path, encoding='utf-8', errors='surrogateescape').read().split('\n')[:-1]
    if old != exp:
        for i, (a, b) in enumerate(zip(old, exp)):
            if a != b:
                bad += 1
                if bad < 30:
                    print('expect.txt line %d:\n  want: %s\n  got:  %s' % (i + 1, a[:300], b[:300]))
        if len(old) != len(exp):
            bad += 1
            print('expect.txt has %d lines, paslang wrote %d' % (len(old), len(exp)))
    if bad:
        sys.exit('%d differences' % bad)
    print('ok json oracle (%d documents%s)' % (len(docs), ', Go v2 too' if gobin else ''))


main()
