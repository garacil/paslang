#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""Mutation testing of one unit against the golden programs that use it.

A mutant is the unit's source with one small change (a comparison turned
around, an operator swapped, a constant off by one, a condition negated,
a statement deleted, a loop bound shortened, a not dropped, a Boolean
flipped; the zero assignments of Result and of locals that open a body
are left alone, since the language clears them already; those of an out
or var parameter stay, the caller sees them). Each mutant is compiled as a unit of its own, the units that
use it and that the chosen programs need are compiled against it, and
the programs are compiled against them and run; the first one whose
output differs from its testdata/NAME.out, or that fails to compile,
or that does not end in time, catches the mutant. A mutant no program
catches survives, and is written out with its lines for the eye: it is
either a hole in the tests or an equivalent change, and live.txt says
which, with the reason, mutant by mutant.

Run in the tree, as the owner of the tree:
  python3 -I scripts/mutunit.py UNIT [options]
  --tree DIR          the tree (default .), with bin/paslangc and build/
  --sample N          this many mutants, chosen by --seed (default all)
  --seed S            the seed of the sample (default 1)
  --ops LIST          only these operators: rel,arith,not,const,bool,neg,del,bound
  --routine NAMES     only the lines of these routines (comma-separated; a header to its end)
  --lines A-B         only these lines
  --tests A,B,...     these programs of testdata (default: the ones that use the unit)
  --all-golden        every golden program, not only the ones that use the unit
  --max-tests N       at most N programs, the direct users first (default 40)
  --arm64             each mutant on arm64 too, under build/qemu-aarch64
  --arm64-survivors   the mutants that survive amd64 are tried on arm64
  --jobs K            this many mutants at once (default 2)
  --timeout SECS      the time one program may run (default 120)
  --live FILE         mutants listed here (id reason) are equivalents, not survivors
  --list              print the mutants and stop
  --only ID,ID        only these mutants (ids as --list prints them)
  --out DIR           where the mutants are built (default build/mut/UNIT)
Every compile runs under ulimit -v 4 GB and timeout 120 s. The report
ends with the score: caught / (caught + survived); build failures and
equivalents do not count.
"""

import concurrent.futures
import os
import random
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from unit_audit import TOK, makefile_lists, uses_of  # noqa: E402

KEYWORDS = {'and', 'array', 'as', 'asm', 'begin', 'case', 'class', 'const', 'constructor', 'destructor', 'div', 'do', 'downto',
            'else', 'end', 'except', 'exit', 'false', 'file', 'finalization', 'finally', 'for', 'function', 'goto', 'if',
            'implementation', 'in', 'inherited', 'initialization', 'inline', 'interface', 'is', 'label', 'library', 'mod',
            'nil', 'not', 'object', 'of', 'on', 'operator', 'or', 'out', 'packed', 'procedure', 'program', 'property',
            'raise', 'record', 'repeat', 'resourcestring', 'set', 'shl', 'shr', 'string', 'then', 'threadvar', 'to', 'true',
            'try', 'type', 'unit', 'until', 'uses', 'var', 'while', 'with', 'xor', 'pas', 'select', 'lock', 'once', 'chan', 'map'}
REL = {'<': '<=', '<=': '<', '>': '>=', '>=': '>', '<>': '=', '=': '<>'}
ARITH = {'+': '-', '-': '+', '*': '+', 'div': 'mod', 'mod': 'div', 'shl': 'shr', 'shr': 'shl', 'and': 'or', 'or': 'and', 'xor': 'or'}
STMT_LINE = re.compile(r'^(\s+)([A-Za-z_][\w.]*(?:\[[^\]]*\])?\^?(?:\.[A-Za-z_]\w*)*)\s*(:=.*|\(.*\)|)\s*;\s*$')
COND_LINE = re.compile(r'^(\s*)(if|while)\s+(.*\S)\s+(then|do)\b(.*)$')
UNTIL_LINE = re.compile(r'^(\s*)until\s+(.*\S)\s*;\s*$')
FOR_LINE = re.compile(r'^(\s*for\s+\w+\s*:=\s*.*?\s+)(to|downto)(\s+)(.*\S)(\s+do\b.*)$')
INIT_LINE = re.compile(r"^\s+([A-Za-z_]\w*)\s*:=\s*(0|False|''|nil)\s*;\s*$", re.I)


def sh(cmd, cwd, timeout):
    """a command inside a shell of the tree's user, memory capped, with a time limit"""
    try:
        r = subprocess.run(['sh', '-c', 'ulimit -v 4194304; exec timeout %d %s' % (timeout, cmd)], cwd=cwd, capture_output=True, text=True, errors='replace')
        return r.returncode, r.stdout, r.stderr
    except OSError as e:
        return 127, '', str(e)


def tokens_with_pos(src):
    out = []
    line = 1
    for m in TOK.finditer(src):
        t = m.group()
        out.append((t, m.start(), m.end(), line))
        line += t.count('\n')
    return out


def code_index(toks):
    """indexes of the tokens that are code (not comments, not blanks), with asm blocks and uses clauses left out"""
    idx = []
    in_asm = False
    in_uses = False
    for i, (t, s, e, ln) in enumerate(toks):
        if t.isspace() or t.startswith('{') or t.startswith('(*') or t.startswith('//'):
            continue
        low = t.lower()
        if in_asm:
            if low == 'end':
                in_asm = False
            continue
        if in_uses:
            if t == ';':
                in_uses = False
            continue
        if low == 'asm':
            in_asm = True
            continue
        if low == 'uses':
            in_uses = True
            continue
        idx.append(i)
    return idx


def routine_span(lines, name):
    """the lines of the routine NAME: from its header to the end; of the implementation"""
    hdr = re.compile(r'^(function|procedure|constructor|destructor|operator)\s+(\w+\.)?%s\b' % re.escape(name), re.I)
    start = None
    for i, l in enumerate(lines):
        if hdr.match(l):
            # the implementation has a body: a begin at column 0 follows before the next header
            j = i + 1
            while j < len(lines) and not re.match(r'^(function|procedure|constructor|destructor|operator|end\.)', lines[j]):
                if lines[j].startswith('begin'):
                    start = i
                    break
                j += 1
            if start is not None:
                break
    if start is None:
        raise SystemExit('mutunit: no routine %s with a body' % name)
    k = start + 1
    while k < len(lines) and not lines[k].startswith('end;') and not lines[k].startswith('end.'):
        k += 1
    return start + 1, k + 1


def mutants_of(src, ops, line_lo, line_hi):
    """every mutant: (id, op, line, old, new, start, end) with start..end the span of src replaced by new"""
    toks = tokens_with_pos(src)
    lines = src.split('\n')
    line_start = [0]
    for l in lines:
        line_start.append(line_start[-1] + len(l) + 1)
    out = []
    idx = code_index(toks)
    code = [toks[i] for i in idx]
    for k, (t, s, e, ln) in enumerate(code):
        if not (line_lo <= ln <= line_hi):
            continue
        low = t.lower()
        col = s - line_start[ln - 1] + 1
        prev = code[k - 1][0] if k else ''
        nxt = code[k + 1][0] if k + 1 < len(code) else ''
        if 'rel' in ops and t in REL:
            if t == '=':
                # a comparison, not a declaration: something other than a name at line start before it, or inside parentheses
                line_text = lines[ln - 1]
                before = line_text[:col - 1]
                if re.match(r'^\s*[A-Za-z_]\w*\s*$', before) or re.match(r'^\s*[A-Za-z_]\w*\s*:\s*[^=]*$', before):
                    continue
            out.append(('rel@%d:%d' % (ln, col), 'rel', ln, t, REL[t], s, e))
        if 'arith' in ops and low in ARITH:
            if low in ('+', '-') and prev in ('(', ',', ':=', '=', '<', '>', '<=', '>=', '<>', '[') and nxt and (nxt[0].isdigit() or nxt[0] == '$'):
                pass  # a sign of a literal: swapping it is a constant mutant, kept
            out.append(('arith@%d:%d' % (ln, col), 'arith', ln, t, ARITH[low], s, e))
        if 'not' in ops and low == 'not':
            out.append(('not@%d:%d' % (ln, col), 'not', ln, t, '', s, e))
        if 'bool' in ops and low in ('true', 'false'):
            out.append(('bool@%d:%d' % (ln, col), 'bool', ln, t, 'False' if low == 'true' else 'True', s, e))
        if 'const' in ops and re.match(r'^(\d+|\$[0-9A-Fa-f]+)$', t) and prev != '..' and nxt != '..':
            if t.startswith('$'):
                v = int(t[1:], 16)
                out.append(('const@%d:%d' % (ln, col), 'const', ln, t, '$%X' % (v + 1), s, e))
                if v > 0:
                    out.append(('const@%d:%d-' % (ln, col), 'const', ln, t, '$%X' % (v - 1), s, e))
            else:
                v = int(t)
                out.append(('const@%d:%d' % (ln, col), 'const', ln, t, str(v + 1), s, e))
                if v > 0:
                    out.append(('const@%d:%d-' % (ln, col), 'const', ln, t, str(v - 1), s, e))
    # line-level mutants: deleted statements, negated conditions, shortened loops
    in_body = False
    # the run of X := 0 / False / '' / nil that opens a body: for Result (which the language clears) and for the
    # routine's own locals it changes nothing; for an out or var parameter it is a store the caller sees, and stays a mutant
    init = False
    init_lines = set()
    refparams = set()
    for ln0, l in enumerate(lines):
        ln = ln0 + 1
        if re.match(r'^(function|procedure|constructor|destructor|operator)\b', l):
            hdr = l
            k = ln0
            while '(' in hdr and ')' not in hdr[hdr.index('('):] and k + 1 < len(lines):
                k += 1
                hdr += ' ' + lines[k]
            refparams = set()
            if '(' in hdr and ')' in hdr:
                for grp in hdr[hdr.index('(') + 1:hdr.rindex(')')].split(';'):
                    g = grp.strip()
                    if re.match(r'^(out|var)\s', g, re.I):
                        names = g.split(':')[0]
                        refparams |= set(n.strip().lower() for n in re.sub(r'^(out|var)\s', '', names, flags=re.I).split(','))
        if l.startswith('begin'):
            in_body = True
            init = True
        elif l.startswith('end;') or l.startswith('end.') or re.match(r'^(function|procedure|constructor|destructor|operator|var|const|type|implementation|interface|initialization|finalization)\b', l):
            in_body = False
            init = False
        elif init and l.strip():
            m = INIT_LINE.match(l)
            if m:
                if m.group(1).lower() not in refparams:
                    init_lines.add(ln)
            else:
                init = False
        if not (line_lo <= ln <= line_hi):
            continue
        s, e = line_start[ln0], line_start[ln0] + len(l)
        if 'del' in ops and in_body and ln not in init_lines:
            m = STMT_LINE.match(l)
            if m and m.group(2).split('.')[0].split('[')[0].lower() not in KEYWORDS - {'exit', 'inherited'}:
                out.append(('del@%d' % ln, 'del', ln, l.strip(), '', s, e))
        if 'neg' in ops and in_body:
            m = COND_LINE.match(l)
            if m:
                new = '%s%s not (%s) %s%s' % (m.group(1), m.group(2), m.group(3), m.group(4), m.group(5))
                out.append(('neg@%d' % ln, 'neg', ln, l.strip(), new.strip(), s, e))
            m = UNTIL_LINE.match(l)
            if m:
                new = '%suntil not (%s);' % (m.group(1), m.group(2))
                out.append(('neg@%d' % ln, 'neg', ln, l.strip(), new.strip(), s, e))
        if 'bound' in ops and in_body:
            m = FOR_LINE.match(l)
            if m:
                sign = '- 1' if m.group(2) == 'to' else '+ 1'
                new = '%s%s%s(%s) %s%s' % (m.group(1), m.group(2), m.group(3), m.group(4), sign, m.group(5))
                out.append(('bound@%d' % ln, 'bound', ln, l.strip(), new.strip(), s, e))
            for fn, sign in (('High', ' - 1'), ('Low', ' + 1')):
                for mm in re.finditer(r'\b%s\(' % fn, l):
                    depth = 0
                    j = mm.end() - 1
                    while j < len(l):
                        if l[j] == '(':
                            depth += 1
                        elif l[j] == ')':
                            depth -= 1
                            if depth == 0:
                                break
                        j += 1
                    if j < len(l):
                        a, b = s + mm.start(), s + j + 1
                        out.append(('bound@%d:%d' % (ln, mm.start() + 1), 'bound', ln, l[mm.start():j + 1], '(' + l[mm.start():j + 1] + sign + ')', a, b))
    # one mutant per id (the line-level ones and the token ones never share an id); none on the opening zero assignments
    seen = {}
    for m in out:
        if m[2] in init_lines and m[1] in ('const', 'bool', 'del'):
            continue
        seen.setdefault(m[0], m)
    return [seen[k] for k in seen]


def main():
    args = sys.argv[1:]
    if not args or args[0].startswith('-'):
        raise SystemExit(__doc__)
    unit = args[0]
    tree = '.'
    sample = seed = None
    seed = 1
    ops = {'rel', 'arith', 'not', 'const', 'bool', 'neg', 'del', 'bound'}
    routine = lines_opt = tests_opt = live = out_dir = None
    all_golden = arm64 = arm64_surv = list_only = False
    max_tests, jobs, timeout = 40, 2, 120
    only = None
    i = 1
    while i < len(args):
        a = args[i]
        nxt = args[i + 1] if i + 1 < len(args) else None
        if a == '--tree':
            tree = nxt
            i += 1
        elif a == '--sample':
            sample = int(nxt)
            i += 1
        elif a == '--seed':
            seed = int(nxt)
            i += 1
        elif a == '--ops':
            ops = set(nxt.split(','))
            i += 1
        elif a == '--routine':
            routine = nxt
            i += 1
        elif a == '--lines':
            lines_opt = nxt
            i += 1
        elif a == '--tests':
            tests_opt = nxt.split(',')
            i += 1
        elif a == '--all-golden':
            all_golden = True
        elif a == '--max-tests':
            max_tests = int(nxt)
            i += 1
        elif a == '--arm64':
            arm64 = True
        elif a == '--arm64-survivors':
            arm64_surv = True
        elif a == '--jobs':
            jobs = int(nxt)
            i += 1
        elif a == '--timeout':
            timeout = int(nxt)
            i += 1
        elif a == '--live':
            live = nxt
            i += 1
        elif a == '--list':
            list_only = True
        elif a == '--only':
            only = set(nxt.split(','))
            i += 1
        elif a == '--out':
            out_dir = nxt
            i += 1
        else:
            raise SystemExit('mutunit: unknown option ' + a)
        i += 1
    tree = os.path.abspath(tree)
    mk = open(os.path.join(tree, 'Makefile'), errors='replace').read()
    core, lib, golden, golden_a64 = makefile_lists(mk)
    order = [os.path.basename(p)[:-8] for p in core + lib]
    paths = {os.path.basename(p)[:-8]: p for p in core + lib}
    if unit not in paths:
        raise SystemExit('mutunit: %s is not in CORE_UNITS or LIB_UNITS' % unit)
    src = open(os.path.join(tree, paths[unit]), errors='replace').read()
    lines = src.split('\n')
    lo, hi = 1, len(lines)
    spans = None
    if routine:
        spans = [routine_span(lines, r) for r in routine.split(',')]
        lo, hi = min(a for a, b in spans), max(b for a, b in spans)
    if lines_opt:
        a, b = lines_opt.split('-')
        lo, hi = int(a), int(b)
    muts = mutants_of(src, ops, lo, hi)
    if spans:
        muts = [m for m in muts if any(a <= m[2] <= b for a, b in spans)]
    if only:
        muts = [m for m in muts if m[0] in only]
    elif sample is not None and sample < len(muts):
        # the same number from each operator as far as it has them: constants are legion (tables), the others few
        rnd = random.Random(seed)
        by_op = {}
        for m in muts:
            by_op.setdefault(m[1], []).append(m)
        for op in by_op:
            rnd.shuffle(by_op[op])
        picked = []
        while len(picked) < sample and any(by_op.values()):
            for op in sorted(by_op):
                if by_op[op] and len(picked) < sample:
                    picked.append(by_op[op].pop())
        muts = sorted(picked, key=lambda m: (m[2], m[0]))
    if list_only:
        for m in muts:
            print('%-16s %-5s line %-5d %s  ->  %s' % (m[0], m[1], m[2], m[3][:50], m[4][:50]))
        print('%d mutants of %s (lines %d-%d)' % (len(muts), unit, lo, hi))
        return

    # the units' uses closures, from their sources
    def code_of(path):
        text = open(os.path.join(tree, path), errors='replace').read()
        return [t for t in TOK.findall(text) if not t.isspace() and not t.startswith('{') and not t.startswith('(*') and not t.startswith('//')]
    deps = {u: set(d for d in uses_of(code_of(paths[u])) if d in paths) for u in order}

    def closure(ds):
        out, todo = set(), list(ds)
        while todo:
            d = todo.pop()
            if d in out:
                continue
            out.add(d)
            todo += list(deps[d])
        return out
    uclos = {u: closure(deps[u]) for u in order}

    # the programs: their direct uses and closure; the ones with a .out that make check runs
    tdir = os.path.join(tree, 'testdata')
    runnable = set(golden) | set(golden_a64) | set(re.findall(r'testdata/([A-Za-z0-9_]+)\.paslang', mk))
    progs = {}
    for f in sorted(os.listdir(tdir)):
        if f.endswith('.paslang') and os.path.exists(os.path.join(tdir, f[:-8] + '.out')) and (f[:-8] in runnable or (tests_opt and f[:-8] in tests_opt)):
            code = code_of('testdata/' + f)
            if code and code[0].lower() == 'unit':
                continue
            d = set(x for x in uses_of(code) if x in paths)
            progs[f[:-8]] = (d, closure(d))
    if tests_opt:
        tests = [t for t in tests_opt if t in progs]
        missing = [t for t in tests_opt if t not in progs]
        if missing:
            print('mutunit: not runnable or no .out: %s' % ' '.join(missing))
    elif all_golden:
        tests = sorted(progs)
    else:
        direct = sorted(t for t, (d, c) in progs.items() if unit in d)
        via = sorted(t for t, (d, c) in progs.items() if unit in c and unit not in d)
        tests = (direct + via)[:max_tests]
        if not tests:
            raise SystemExit('mutunit: no golden program uses %s; name them with --tests or --all-golden' % unit)
    if not tests:
        raise SystemExit('mutunit: no tests')
    needed = set()
    for t in tests:
        needed |= progs[t][1]
    pos = order.index(unit)
    recompile = [v for v in order[pos + 1:] if unit in uclos[v] and v in needed]
    print('mutunit: %s: %d mutants, %d programs (%s%s), units rebuilt per mutant: %s' % (
        unit, len(muts), len(tests), ' '.join(tests[:12]), ' ...' if len(tests) > 12 else '', ' '.join(recompile) or 'none'), flush=True)

    out_dir = os.path.abspath(out_dir or os.path.join(tree, 'build', 'mut', unit))
    os.makedirs(out_dir, exist_ok=True)
    cc = os.path.join(tree, 'bin', 'paslangc')
    qemu = os.path.join(tree, 'build', 'qemu-aarch64')
    gold = {t: open(os.path.join(tdir, t + '.out'), errors='replace').read() for t in tests}

    def build_and_run(mid, text, machines):
        """build the mutant and run the programs: ('caught', why) | ('survives', '') | ('build', why)"""
        d = os.path.join(out_dir, mid.replace(':', '_').replace('@', '_'))
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, unit + '.paslang'), 'w') as f:
            f.write(text)
        for mach in machines:
            sub = os.path.join(d, 'x' if mach == 'amd64' else 'a')
            os.makedirs(sub, exist_ok=True)
            if mach == 'amd64':
                flags, fu = '', '-Fu %s -Fu %s/build' % (sub, tree)
            else:
                flags, fu = '-target arm64', '-Fu %s -Fu %s/build/a64' % (sub, tree)
            rc, so, se = sh('%s %s -cpu base -c %s -o %s/%s %s/%s.paslang' % (cc, flags, fu, sub, unit, d, unit), tree, 120)
            if rc:
                return 'build', '%s: %s' % (mach, (se + so).strip().split('\n')[-1][:120])
            for v in recompile:
                rc, so, se = sh('%s %s -cpu base -c %s -o %s/%s %s' % (cc, flags, fu, sub, v, paths[v]), tree, 120)
                if rc:
                    return 'build', '%s %s: %s' % (mach, v, (se + so).strip().split('\n')[-1][:120])
            for t in tests:
                exe = os.path.join(sub, 't_' + t)
                rc, so, se = sh('%s %s %s -o %s testdata/%s.paslang' % (cc, flags, fu, exe, t), tree, 120)
                if rc:
                    return 'caught', '%s %s does not compile: %s' % (mach, t, (se + so).strip().split('\n')[-1][:100])
                run = exe if mach == 'amd64' else qemu + ' ' + exe
                rc, so, se = sh(run, tree, timeout)
                if rc == 124:
                    return 'caught', '%s %s: no end in %d s' % (mach, t, timeout)
                if so != gold[t] or rc != 0:
                    gl, ol = gold[t].split('\n'), so.split('\n')
                    k = next((j for j in range(min(len(gl), len(ol))) if gl[j] != ol[j]), min(len(gl), len(ol)))
                    why = '%s %s line %d: %s' % (mach, t, k + 1, (ol[k] if k < len(ol) else '(ends)')[:60])
                    if rc:
                        why += ' [exit %d%s]' % (rc, (' ' + se.strip().split('\n')[-1][:80]) if se.strip() else '')
                    return 'caught', why
        return 'survives', ''

    machines = ['amd64', 'arm64'] if arm64 else ['amd64']
    t0 = time.time()
    verdict, why = build_and_run('m0', src, machines)
    if verdict != 'survives':
        raise SystemExit('mutunit: the unmutated unit fails: %s %s (a program with another output, or one that does not build here)' % (verdict, why))
    print('mutunit: baseline ok (%d s)' % int(time.time() - t0), flush=True)

    equiv = {}
    if live and os.path.exists(live):
        for l in open(live):
            p = l.split(None, 1)
            if p:
                equiv[p[0]] = p[1].strip() if len(p) > 1 else ''

    results = {}

    def work(m):
        mid, op, ln, old, new, s, e = m
        text = src[:s] + new + src[e:]
        v, w = build_and_run(mid, text, machines)
        if v == 'survives' and arm64_surv and not arm64:
            v, w = build_and_run(mid, text, ['arm64'])
            if v == 'survives':
                w = 'amd64 and arm64'
        return mid, v, w

    report = open(os.path.join(out_dir, 'report.txt'), 'w')
    report.write('mutunit %s: %d mutants, programs %s\n' % (unit, len(muts), ' '.join(tests)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        for mid, v, w in ex.map(work, muts):
            m = next(mm for mm in muts if mm[0] == mid)
            results[mid] = (v, w)
            tag = 'SURVIVES listed' if (v == 'survives' and mid in equiv) else v.upper()
            line = '%-16s %-5s line %-5d %s -> %s : %s %s' % (mid, m[1], m[2], m[3][:40], m[4][:40], tag, w)
            print(line, flush=True)
            report.write(line + '\n')
    caught = sum(1 for v, w in results.values() if v == 'caught')
    build_failed = sum(1 for v, w in results.values() if v == 'build')
    surv = [m for m in muts if results[m[0]][0] == 'survives' and m[0] not in equiv]
    eq = [m for m in muts if results[m[0]][0] == 'survives' and m[0] in equiv]
    summary = 'score %d/%d caught; %d survive, %d equivalent, %d do not build; %d s' % (
        caught, caught + len(surv), len(surv), len(eq), build_failed, int(time.time() - t0))
    print(summary)
    report.write(summary + '\n')
    report.close()
    with open(os.path.join(out_dir, 'survivors.txt'), 'w') as f:
        for m in surv:
            mid, op, ln, old, new, s, e = m
            f.write('%s %s line %d: %s -> %s\n' % (mid, op, ln, old, new))
            for k in range(max(1, ln - 3), min(len(lines), ln + 3) + 1):
                f.write('%s%5d  %s\n' % ('>' if k == ln else ' ', k, lines[k - 1]))
            f.write('\n')
    if surv:
        print('%d survivors with their lines in %s' % (len(surv), os.path.join(out_dir, 'survivors.txt')))


if __name__ == '__main__':
    main()
