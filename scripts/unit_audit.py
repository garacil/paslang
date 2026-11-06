#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""What each unit of src/lib and src/rtl stands on.

For every unit of CORE_UNITS and LIB_UNITS the report gives: the golden
programs that use it, directly or through a unit that uses it, and on
which machines make check runs them; the recipes of make check that
exercise it; the oracles, corpora, models and checkers of scripts/
written for it; its bench pairs against Go (Regla 12); whether a golden
program runs it from several routines at once (Regla 11); whether a
fuzzer feeds it; how many words of its interface the manual names, and
which it does not; and, when the registry is at hand, what remains open
for it. It reads the tree, never a memory of it (Regla 2).

usage: unit_audit.py [--tree DIR] [--registry FILE] [--mutants DIR]
                     [--gaps] [--missing] [--gate] [UNIT...]
  --registry FILE  docs/seed_milestones.py or a copy: its pending rows
                   that name the unit are counted
  --mutants DIR    the reports of mutunit.py (DIR/UNIT/report.txt): the
                   score of each unit's last run is shown
  --gaps           print the gaps, worst unit first, after the table
  --missing        print the words of each interface the manual lacks
  --gate           exit 1 when a library unit has no golden program on
                   one of the machines, or no section in the manual
"""

import os
import re
import sys

TOK = re.compile(r"\{[^}]*\}|\(\*.*?\*\)|//[^\n]*|'(?:[^'\n]|'')*'|#\$[0-9A-Fa-f]+|#\d+|\$[0-9A-Fa-f]+"
                 r"|\d+(?:\.\d+)?(?:[eE][-+]?\d+)?|[A-Za-z_]\w*|:=|<>|<=|>=|\.\.|[^\sA-Za-z_0-9]|\s+", re.S)

# words that name a unit in a script's file name or in the registry, besides the unit's own name
ALIAS = {
    'pasflate': ['flate', 'deflate', 'gzip', 'zlib'], 'paszip': ['zip'], 'pasxml': ['xml'], 'pasjson': ['json'],
    'pasurl': ['url'], 'pasmime': ['mime', 'mail'], 'passmtp': ['smtp', 'mail'], 'pasimap': ['imap', 'mail'],
    'pashttp': ['http'], 'httpclient': ['http_client', 'httpcli'], 'httpserver': ['http_gosrv', 'httpsystemd', 'servers', 'apisrv'],
    'pastls': ['tls'], 'pasx509': ['x509'], 'pascipher': ['cipher', 'wyche', 'aes', 'chacha', 'gcm'],
    'pascodec': ['codec', 'base64'], 'sqlite': ['sql', 'sqlite', 'sqlite3'], 'paspdf': ['pdf'], 'paspdfenc': ['pdfenc', 'pdf'],
    'paspdfafm': ['pdfafm', 'pdf'], 'paspdfform': ['pdf_forms', 'pdfform', 'pdf'], 'paspdfcrypt': ['pdfcrypt', 'pdf'],
    'pasfontcff': ['fontcff', 'cff'], 'pasfonttt': ['fonttt', 'truetype'], 'pasfontnames': ['fontnames'],
    'pasnum': ['num', 'pasnum', 'pow10'], 'pastree': ['tree'], 'pashash': ['hash', 'md5lens', 'sha3lens', 'sha512lens', 'crclens', 'adler', 'sha', 'md5', 'crc'],
    'pastime': ['time', 'zone', 'civil'], 'pasxlsx': ['xlsx'], 'argon2': ['argon2', 'blake2'],
    'pasnist': ['fiat', 'nist', 'wyche', 'p-256', 'p-384', 'ecdsa'], 'pasrsa': ['rsa', 'wyche'], 'pasx25519': ['x25519', 'wyche'],
    'passignal': ['signal', 'signals'], 'paslinux': ['syscalls', 'syscall_connect', 'syscall_eintr', 'syscall_handoff', 'linux'],
    'pasnet': ['net', 'nonblocking', 'poller', 'socket'], 'pasroutines': ['pasasync', 'parkleft', 'routinemem', 'routine', 'routines', 'mutex', 'waitgroup'],
    'pasdebug': ['debug', 'debug_growth'], 'pasfmt': ['currency', 'fmt', 'format'], 'pasmath': ['math', 'mathacc', 'mathgo', 'fma'],
    'passtr': ['longslice', 'utf8kern', 'strings', 'string'], 'pasmap': ['map', 'maps'], 'pasheap': ['heap', 'collector', 'gc'],
    'pasquad': ['quad'], 'pasrand': ['rand', 'random'], 'passort': ['sort'], 'pasx11': ['x11'], 'pasconn': ['conn'],
    'pastextproto': ['textproto'], 'sysutils': ['sysutils'], 'paslib': ['paslib'], 'pasobject': ['object', 'tobject'],
    'passystemd': ['systemd', 'sd_notify', 'notify'],
}
# stems too common to name a unit in the registry (they stay for file names)
NOT_IN_REGISTRY = {'net', 'time', 'map', 'maps', 'heap', 'gc', 'tree', 'hash', 'sort', 'rand', 'string', 'strings', 'format',
                   'object', 'conn', 'num', 'math', 'routine', 'routines', 'collector', 'mutex', 'waitgroup', 'random',
                   'socket', 'poller', 'linux', 'notify', 'sha', 'md5', 'crc', 'sql', 'mail', 'http', 'url', 'zip', 'aes'}


def tokens(text):
    return TOK.findall(text)


def sig(toks):
    """the tokens that are code: no comments, no white space; strings kept as one token"""
    return [t for t in toks if not (t[0] in '{(/' and (t.startswith('{') or t.startswith('(*') or t.startswith('//'))) and not t.isspace()]


def uses_of(code):
    """every name in the uses clauses of a code token list, lower case"""
    names = []
    i = 0
    while i < len(code):
        if code[i].lower() == 'uses':
            i += 1
            while i < len(code) and code[i] != ';':
                if re.match(r'[A-Za-z_]\w*$', code[i]) and code[i].lower() != 'in' and code[i - 1] != '.':
                    names.append(code[i].lower())
                i += 1
        i += 1
    return names


def interface_words(code):
    """the names a unit's interface declares: routines, methods, properties, types, constants, variables"""
    try:
        a = next(i for i, t in enumerate(code) if t.lower() == 'interface')
        b = next(i for i, t in enumerate(code) if t.lower() == 'implementation')
    except StopIteration:
        return []
    words = []
    sect = None
    i = a + 1
    while i < b:
        t = code[i]
        low = t.lower()
        if low in ('function', 'procedure', 'constructor', 'destructor', 'operator', 'property'):
            if i + 1 < b and re.match(r'[A-Za-z_]\w*$', code[i + 1]) and (i + 2 >= b or code[i + 2] != '.'):
                words.append(code[i + 1])
            i += 2
            continue
        if low in ('type', 'const', 'var', 'threadvar', 'resourcestring'):
            sect = low
            i += 1
            continue
        if low == 'uses':
            while i < b and code[i] != ';':
                i += 1
        if sect in ('type', 'const', 'var') and re.match(r'[A-Za-z_]\w*$', t) and i + 1 < b and code[i + 1] in ('=', ':', ','):
            # the name of a declaration: it follows a semicolon, the section word, or a comma of a name list
            prev = code[i - 1]
            if prev in (';', ',', ')') or prev.lower() in ('type', 'const', 'var', 'threadvar', 'public', 'private', 'protected', 'published', 'end', 'begin'):
                if low not in ('end', 'class', 'record', 'object', 'interface', 'packed', 'of', 'array', 'set', 'string', 'strict'):
                    words.append(t)
        i += 1
    seen = set()
    out = []
    for w in words:
        if w.lower() not in seen:
            seen.add(w.lower())
            out.append(w)
    return out


def read(path):
    with open(path, errors='replace') as f:
        return f.read()


def makefile_lists(mk):
    """CORE_UNITS, LIB_UNITS (paths), GOLDEN, GOLDEN_A64 (names)"""
    def var_lines(name):
        out = []
        for m in re.finditer(r'^%s\s*(?::=|\+=|=)\s*(.*?)(?<!\\)$' % re.escape(name), mk, re.M | re.S):
            out += m.group(1).replace('\\\n', ' ').split()
        return out
    return var_lines('CORE_UNITS'), var_lines('LIB_UNITS'), var_lines('GOLDEN'), var_lines('GOLDEN_A64')


def recipe_blocks(mk):
    """the blocks of the check recipes: (name, programs compiled, scripts run, text)"""
    blocks = []
    cur_prog, cur_scr, cur_txt = set(), set(), []
    for line in mk.split('\n'):
        if not line.startswith('\t'):
            continue
        cur_txt.append(line)
        for m in re.finditer(r'testdata/([A-Za-z0-9_]+)\.paslang', line):
            cur_prog.add(m.group(1))
        for m in re.finditer(r'scripts/([A-Za-z0-9_./-]+)', line):
            cur_scr.add(m.group(1))
        m = re.search(r'echo\s+"?ok\s+([A-Za-z0-9_.-]+)', line)
        if m:
            blocks.append((m.group(1), cur_prog, cur_scr, '\n'.join(cur_txt)))
            cur_prog, cur_scr, cur_txt = set(), set(), []
    return blocks


def main():
    args = sys.argv[1:]
    tree = '.'
    registry = None
    mutants = None
    gaps = missing = gate = False
    only = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--tree':
            tree = args[i + 1]
            i += 1
        elif a == '--registry':
            registry = args[i + 1]
            i += 1
        elif a == '--mutants':
            mutants = args[i + 1]
            i += 1
        elif a == '--gaps':
            gaps = True
        elif a == '--missing':
            missing = True
        elif a == '--gate':
            gate = True
        elif a.startswith('-'):
            raise SystemExit(__doc__)
        else:
            only.append(a.lower())
        i += 1

    mk = read(os.path.join(tree, 'Makefile'))
    core, lib, golden, golden_a64 = makefile_lists(mk)
    golden, golden_a64 = set(golden), set(golden_a64)
    units = []  # (name, kind, path)
    for p in core:
        units.append((os.path.basename(p)[:-8], 'core', p))
    for p in lib:
        units.append((os.path.basename(p)[:-8], 'lib', p))
    names = {u[0].lower(): u for u in units}

    # each unit: its code tokens, its uses, its interface words, its lines
    ucode, udeps, uwords, ulines = {}, {}, {}, {}
    for name, kind, p in units:
        text = read(os.path.join(tree, p))
        ulines[name] = text.count('\n') + 1
        code = sig(tokens(text))
        ucode[name] = code
        udeps[name] = set(d for d in uses_of(code) if d in names)
        uwords[name] = interface_words(code)

    def closure(deps):
        out = set()
        todo = list(deps)
        while todo:
            d = todo.pop()
            if d in out or d not in names:
                continue
            out.add(d)
            todo += list(udeps.get(d, ()))
        return out

    uclos = {u: closure(udeps[u]) for u in udeps}

    # every program of testdata: its uses closure, whether it starts routines
    tdir = os.path.join(tree, 'testdata')
    progs = {}
    for f in sorted(os.listdir(tdir)):
        if not f.endswith('.paslang'):
            continue
        code = sig(tokens(read(os.path.join(tdir, f))))
        if code and code[0].lower() == 'unit':
            continue
        direct = set(d for d in uses_of(code) if d in names)
        conc = any(code[k].lower() == 'pas' and k + 1 < len(code) and re.match(r'[A-Za-z_]\w*$', code[k + 1]) for k in range(len(code)))
        progs[f[:-8]] = (direct, closure(direct), conc)

    blocks = recipe_blocks(mk)
    recipe_progs = set()
    for b in blocks:
        recipe_progs |= b[1]

    # scripts and their stems
    sdir = os.path.join(tree, 'scripts')
    scripts = sorted(s for s in os.listdir(sdir) if s not in ('__pycache__', 'bench', 'qemu') and not s.startswith('check_') or s.startswith('check_'))
    scripts = [s for s in scripts if s not in ('__pycache__', 'bench', 'qemu')]
    assigned = set()

    def script_matches(unit):
        stems = [unit.lower()] + ALIAS.get(unit.lower(), [])
        out = []
        for s in scripts:
            base = s.lower()
            for st in stems:
                if re.search(r'(^|[_.-])%s([_.-]|$|\d)' % re.escape(st.replace('-', '')), base.replace('check_', '').replace('gen_', '').replace('inject_', '')):
                    out.append(s)
                    assigned.add(s)
                    break
        return out

    # bench pairs
    bdir = os.path.join(tree, 'scripts', 'bench')
    pairs = {}
    if os.path.isdir(bdir):
        for f in sorted(os.listdir(bdir)):
            if f.endswith('.paslang') and f[0] == 'b':
                code = sig(tokens(read(os.path.join(bdir, f))))
                pairs[f[:-8]] = closure(set(d for d in uses_of(code) if d in names))

    manual = read(os.path.join(tree, 'docs', 'MANUAL.md')) if os.path.exists(os.path.join(tree, 'docs', 'MANUAL.md')) else ''
    manual_low = manual.lower()
    manual_words = set(re.findall(r'[a-z_]\w*', manual_low))

    reg_rows = []
    if registry and os.path.exists(registry):
        text = read(registry)
        for m in re.finditer(r'^m\((\d+),\s*\d+,\s*"(P\d+)",\s*(.*?)^\s*"(\w+)",\s*\d+\)', text, re.S | re.M):
            reg_rows.append((m.group(2), m.group(3), m.group(4)))

    def pending_for(unit):
        words = [unit.lower()] + [a for a in ALIAS.get(unit.lower(), []) if a not in NOT_IN_REGISTRY]
        out = []
        for pid, body, status in reg_rows:
            if status != 'pending':
                continue
            low = body.lower()
            if any(re.search(r'(?<![a-z0-9_])%s(?![a-z0-9_])' % re.escape(w), low) for w in words):
                out.append(pid)
        return out

    def mutant_score(unit):
        if not mutants:
            return ''
        p = os.path.join(mutants, unit, 'report.txt')
        if not os.path.exists(p):
            return '-'
        m = re.search(r'score\s+(\d+)/(\d+)', read(p))
        return '%s/%s' % (m.group(1), m.group(2)) if m else '?'

    rows = []
    worst = []
    failed_gate = []
    for name, kind, p in units:
        if only and name.lower() not in only:
            continue
        direct = sorted(t for t, (d, c, _) in progs.items() if name in d)
        through = sorted(t for t, (d, c, _) in progs.items() if name in c and name not in d)
        users = set(direct) | set(through)
        g_amd = sorted(users & golden)
        g_arm = sorted(users & golden_a64)
        g_rec = sorted(users & recipe_progs)
        conc = sorted(t for t in users if progs[t][2])
        recs = sorted(b[0] for b in blocks if (b[1] & users) or re.search(r'(?<![a-z0-9_])%s(?![a-z0-9_])' % re.escape(name.lower()), b[3].lower()))
        scr = script_matches(name)
        fuzz = sorted(s for s in scr if 'fuzz' in s.lower()) + sorted(t for t in progs if 'fuzz' in t and name in progs[t][1])
        oracles = [s for s in scr if 'fuzz' not in s.lower()]
        bp = sorted(b for b, c in pairs.items() if name in c) if kind == 'lib' else ['(core)']
        words = uwords[name]
        miss = [w for w in words if w.lower() not in manual_words]
        cov = (100 * (len(words) - len(miss)) // len(words)) if words else 100
        in_manual = ('uses %s' % name.lower()) in manual_low or ('`%s`' % name.lower()) in manual_low
        pend = pending_for(name)
        rows.append((name, kind, ulines[name], len(words), cov, len(miss), len(direct), len(through), len(g_amd), len(g_arm), len(g_rec), len(recs), len(oracles), len(bp), len(conc), len(fuzz), len(pend), mutant_score(name), in_manual))
        score = 0
        why = []
        if kind == 'lib' and not g_amd:
            score += 5
            why.append('no golden program on amd64')
        if kind == 'lib' and not g_arm:
            score += 5
            why.append('no golden program on arm64')
        if kind == 'lib' and not in_manual:
            score += 4
            why.append('no uses section in the manual')
        if not oracles:
            score += 3
            why.append('no oracle, corpus or checker script')
        if not fuzz:
            score += 2
            why.append('no fuzzer')
        if kind == 'lib' and not bp:
            score += 2
            why.append('no bench pair')
        if not conc:
            score += 2
            why.append('no golden program runs it from several routines')
        if miss:
            score += 1
            why.append('%d interface words the manual lacks' % len(miss))
        if pend:
            why.append('open: ' + ' '.join(pend))
        worst.append((score, name, why, miss, direct, through, recs, oracles, bp, conc, fuzz, pend))
        if gate and kind == 'lib' and (not g_amd or not g_arm or not in_manual):
            failed_gate.append((name, why))

    hdr = ('unit', 'kind', 'lines', 'words', 'man%', 'miss', 'direct', 'via', 'amd64', 'arm64', 'recipe', 'blocks', 'oracle', 'bench', 'conc', 'fuzz', 'open', 'mutants')
    fmt = '%-13s %-4s %6s %5s %4s %4s %6s %4s %5s %5s %6s %6s %6s %5s %4s %4s %4s %7s'
    print(fmt % hdr)
    for r in rows:
        print(fmt % (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11], r[12], r[13], r[14], r[15], r[16], r[17]))
    unassigned = [s for s in scripts if s not in assigned]
    print('\n%d units, %d golden programs (%d amd64, %d arm64), %d recipe blocks, %d scripts (%d not matched to a unit: %s)' % (
        len(rows), len(progs), len(golden), len(golden_a64), len(blocks), len(scripts), len(unassigned), ' '.join(unassigned)))
    orphans = sorted(t for t in progs if t not in golden and t not in golden_a64 and t not in recipe_progs)
    if orphans:
        print('%d programs of testdata no recipe compiles: %s' % (len(orphans), ' '.join(orphans)))
    if gaps:
        print('\nGAPS, worst first')
        for score, name, why, miss, direct, through, recs, oracles, bp, conc, fuzz, pend in sorted(worst, key=lambda w: (-w[0], w[1])):
            print('%2d %-13s %s' % (score, name, '; '.join(why)))
            print('   direct: %s' % (' '.join(direct) or '-'))
            if through:
                print('   via units: %s' % ' '.join(through))
            print('   blocks: %s' % (' '.join(recs) or '-'))
            print('   scripts: %s' % (' '.join(oracles + fuzz) or '-'))
            if bp and bp != ['(core)']:
                print('   bench: %s' % ' '.join(bp))
            if conc:
                print('   routines: %s' % ' '.join(conc))
    if missing:
        print('\nWORDS OF EACH INTERFACE THE MANUAL LACKS')
        for score, name, why, miss, *_ in sorted(worst, key=lambda w: w[1]):
            if miss:
                print('%-13s %s' % (name, ' '.join(miss)))
    if gate and failed_gate:
        for name, why in failed_gate:
            print('unit_audit: %s: %s' % (name, '; '.join(why)), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
