#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Which processor an amd64 executable is built for (P264), read in its
disassembly (objdump -d): the instructions past the base processor
(SSE2) are those of BMI1 and BMI2, LZCNT, POPCNT, MOVBE, SSE4.2's
CRC32, and every VEX or EVEX instruction (a ymm or zmm register, or a
v mnemonic).

  check_cpubin.py base   EXE   none outside the kernel bodies named *Cpu
  check_cpubin.py native EXE   some outside those kernels, when
                               /proc/cpuinfo has BMI1, POPCNT or AVX2

The kernel bodies named *Cpu are left out for base until P268: passtr's
PosOf takes its kernels by a parameter, so a base program links
PasIndexByteCpu and PasMemEqCpu and never runs them."""
import re
import subprocess
import sys

PAST = re.compile(r'\b(lzcnt|tzcnt|popcnt|andn|blsr|blsi|blsmsk|bzhi|shlx|shrx|sarx|rorx|mulx|pdep|pext|movbe'
                  r'|crc32[bwlq]?)\b|%[yz]mm|^v[a-z0-9]+\b')


def scan(exe):
    out = subprocess.run(['objdump', '-d', '--no-show-raw-insn', exe], capture_output=True, text=True,
                         check=True).stdout
    cur = '?'
    hits = {}
    for line in out.split('\n'):
        m = re.match(r'^[0-9a-f]+ <([^>]+)>:', line)
        if m:
            if not m.group(1).startswith('.'):
                cur = m.group(1)
            continue
        ins = line.split('\t')[-1].strip()
        if '\t' in line and PAST.search(ins):
            hits.setdefault(cur, []).append(ins)
    return hits


def main():
    mode, exe = sys.argv[1], sys.argv[2]
    hits = scan(exe)
    if mode == 'base':
        bad = {k: v for k, v in hits.items() if not k.endswith('cpu')}
        if bad:
            for k, v in sorted(bad.items()):
                print('%s: %s has %d instructions past the base processor: %s' % (exe, k, len(v), ', '.join(v[:4])))
            sys.exit(1)
        print('%s: no instruction past the base processor outside the *Cpu kernels (%d routines with them)'
              % (exe, len(hits)))
    elif mode == 'native':
        flags = open('/proc/cpuinfo').read().split()
        if not any(f in flags for f in ('bmi1', 'popcnt', 'avx2')):
            print('%s: this processor has nothing past the base to look for' % exe)
            return
        own = {k: v for k, v in hits.items() if not k.endswith('cpu')}
        if not own:
            sys.exit('%s: no instruction past the base processor outside the *Cpu kernels: not built for this one'
                     % exe)
        print('%s: %d routines on this processor\'s instructions' % (exe, len(own)))
    else:
        sys.exit('check_cpubin.py base|native EXE')


main()
