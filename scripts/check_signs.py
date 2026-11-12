#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""The assembly of testdata/signs (P542): Abs and the negation of a Double
are one andpd or xorpd on the register (fabs and fneg on arm64), not a shift
pair or a bit flip through rax; the Horner chains and the products with a
constant on the left take no push, no pop and no trip through rax however
deep they are; and the routine that returns its result from rax (the first of
a unit has the label .L1, which the test of the epilogue took for a prefix of
.L10 to .L19 and never merged the tail) ends with no move out of an xmm
register. Reads the amd64 assembly of signs, the arm64 assembly and the
assembly of the unit pasmath, whose first routine is PasSin."""

import re
import sys
from pathlib import Path
import runpy

_symbols = runpy.run_path(str(Path(__file__).with_name('asm_symbols.py')))
procedure_symbol = _symbols['procedure_symbol']



def routine(text, name, unit=''):
    m = re.search(r'^%s:\n(.*?)^\s+\.cfi_endproc' % re.escape(procedure_symbol(unit, name)), text, re.M | re.S)
    if not m:
        sys.exit('check_signs: no routine p_%s' % name)
    return m.group(1)


def code(body):
    return [l for l in body.split('\n') if l.startswith('  ') and not l.startswith('  .')]


def last_before_ret(body):
    lines = code(body)
    for i, l in enumerate(lines):
        if l.strip() == 'ret':
            return lines[i - 1].strip()
    sys.exit('check_signs: no ret')


def need(cond, msg):
    if not cond:
        sys.exit('check_signs: ' + msg)


amd = open(sys.argv[1]).read()
arm = open(sys.argv[2]).read()
pm = open(sys.argv[3]).read()
ab = routine(amd, 'ab')
need(ab.count('andpd .Lrabs') >= 2, 'Abs is not andpd in ab')
need('shlq $1' not in ab and 'shrq $1' not in ab, 'ab shifts the sign out through rax')
ng = routine(amd, 'ng')
need(ng.count('xorpd .Lrneg') >= 2, 'the negation is not xorpd in ng')
need('btcq' not in ng, 'ng flips the sign bit through rax')
lp = routine(amd, 'lp')
need('andpd .Lrabs' in lp and 'shlq $1' not in lp, 'the loop of lp does not keep Abs in the register')
cm = routine(amd, 'cm')
need('andpd .Lrabs' in cm, 'Abs in a comparison is not andpd in cm')
for r in ('hr', 'hl', 'hs', 'hx', 'cm'):
    b = routine(amd, r)
    need('pushq' not in b and 'popq' not in b, '%s pushes: its expression left the registers' % r)
    need('movq %xmm0, %rax' not in b and 'movq %rax, %xmm0' not in b, '%s crosses to rax inside its expression' % r)
need('xmm' not in last_before_ret(routine(amd, 'sg')), 'sg ends with a move out of an xmm register: %s' % last_before_ret(routine(amd, 'sg')))
need('xmm' not in last_before_ret(routine(pm, 'passin', 'pasmath')),
     'PasSin ends with a move out of an xmm register: %s' % last_before_ret(routine(pm, 'passin', 'pasmath')))
need(re.search(r'fabs d\d+, d\d+', routine(arm, 'ab')) is not None, 'Abs is not fabs on arm64')
need(re.search(r'fneg d\d+, d\d+', routine(arm, 'ng')) is not None, 'the negation is not fneg on arm64')
print('check_signs: ok')
