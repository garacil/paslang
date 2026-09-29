#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
#
# paslang is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# paslang is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with paslang.  If not, see <https://www.gnu.org/licenses/>.

"""The arm64 hash kernels of src/lib/pashash.paslang come from Go 1.23's
crypto/sha1/sha1block_arm64.s, crypto/sha256/sha256block_arm64.s and
crypto/sha512/sha512block_arm64.s (docs/ref/go1.23/crypto, BSD), read
against the Arm ARM (docs/ref/asm). Go writes arm64 assembly in Plan 9
syntax, the destination last and the sources before it in the reverse
of GNU's order; this script turns each line into GNU syntax as
aarch64-linux-gnu-as reads it, expands the SHA-512 macros, and prints
the three kernels, which the unit carries in its asm arm64 blocks.

    python3 scripts/asm_from_go.py sha1|sha256|sha512
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GO = ROOT / 'docs' / 'ref' / 'go1.23' / 'crypto'


def vreg(tok):
    """V4.S4 -> ('v4', '.4s'); V4 -> ('v4', ''); F20 -> ('s20', '')."""
    tok = tok.strip()
    m = re.match(r'^V(\d+)(?:\.([SBD])(\d*))?(?:\[(\d+)\])?$', tok)
    if m:
        n = m.group(1)
        lane = ''
        if m.group(2):
            lane = '.' + m.group(3) + m.group(2).lower()
        if m.group(4) is not None:
            return 'v' + n, '.' + m.group(2).lower() + '[' + m.group(4) + ']'
        return 'v' + n, lane
    m = re.match(r'^F(\d+)$', tok)
    if m:
        return 's' + m.group(1), ''
    raise ValueError(tok)


def xreg(tok):
    m = re.match(r'^R(\d+)$', tok.strip())
    if not m:
        raise ValueError(tok)
    return 'x' + m.group(1)


def conv(line):
    """One Go line to one GNU line, or None for a line to drop."""
    line = line.split('//')[0].strip().rstrip('\\').strip()
    if not line or line.startswith('#') or line.startswith('TEXT') or line == 'RET':
        return None
    if line.endswith(':'):
        return line
    parts = line.split(None, 1)
    op = parts[0]
    args = [a.strip() for a in re.split(r',(?![^\[]*\])', parts[1])] if len(parts) > 1 else []
    if op in ('VLD1.P', 'VLD1'):
        # VLD1.P 16(R1), [V4.B16]
        mem, regs = args[0], args[1]
        m = re.match(r'^(?:(\d+))?\((R\d+)\)$', mem)
        off, base = m.group(1), xreg(m.group(2))
        rl = ', '.join(v + l for v, l in (vreg(t) for t in regs.strip('[]').split(',')))
        s = 'ld1 {' + rl + '}, [' + base + ']'
        if op == 'VLD1.P':
            s += ', #' + off
        return s
    if op in ('VST1.P', 'VST1'):
        regs, mem = args[0], args[1]
        m = re.match(r'^(?:(\d+))?\((R\d+)\)$', mem)
        off, base = m.group(1), xreg(m.group(2))
        rl = ', '.join(v + l for v, l in (vreg(t) for t in regs.strip('[]').split(',')))
        s = 'st1 {' + rl + '}, [' + base + ']'
        if op == 'VST1.P':
            s += ', #' + off
        return s
    if op == 'VMOV':
        a, b = vreg(args[0]), vreg(args[1])
        if '[' in a[1]:
            # VMOV V20.S[0], V1: element to scalar
            return 'mov ' + b[0].replace('v', 's') + ', ' + a[0] + a[1]
        return 'mov ' + b[0] + b[1] + ', ' + a[0] + a[1]
    if op == 'VDUP':
        a, b = vreg(args[0]), vreg(args[1])
        return 'dup ' + b[0] + b[1] + ', ' + a[0] + a[1]
    if op in ('VREV32', 'VREV64'):
        a, b = vreg(args[0]), vreg(args[1])
        return op[1:].lower() + ' ' + b[0] + b[1] + ', ' + a[0] + a[1]
    if op == 'VADD':
        a, b, d = vreg(args[0]), vreg(args[1]), vreg(args[2])
        return 'add ' + d[0] + d[1] + ', ' + b[0] + b[1] + ', ' + a[0] + a[1]
    if op == 'VEXT':
        imm = args[0].lstrip('$')
        a, b, d = vreg(args[1]), vreg(args[2]), vreg(args[3])
        return 'ext ' + d[0] + d[1] + ', ' + b[0] + b[1] + ', ' + a[0] + a[1] + ', #' + imm
    if op in ('SHA1C', 'SHA1P', 'SHA1M'):
        # SHA1C V16.S4, V1, V2 -> sha1c q2, s1, v16.4s
        w, e, d = vreg(args[0]), vreg(args[1]), vreg(args[2])
        return op.lower() + ' ' + d[0].replace('v', 'q') + ', ' + e[0].replace('v', 's') + ', ' + w[0] + w[1]
    if op == 'SHA1H':
        a, d = vreg(args[0]), vreg(args[1])
        return 'sha1h ' + d[0].replace('v', 's') + ', ' + a[0].replace('v', 's')
    if op == 'SHA1SU0':
        m, n, d = vreg(args[0]), vreg(args[1]), vreg(args[2])
        return 'sha1su0 ' + d[0] + d[1] + ', ' + n[0] + n[1] + ', ' + m[0] + m[1]
    if op == 'SHA1SU1':
        n, d = vreg(args[0]), vreg(args[1])
        return 'sha1su1 ' + d[0] + d[1] + ', ' + n[0] + n[1]
    if op in ('SHA256H', 'SHA256H2'):
        # SHA256H V9.S4, V3, V2 -> sha256h q2, q3, v9.4s
        w, n, d = vreg(args[0]), vreg(args[1]), vreg(args[2])
        return op.lower() + ' ' + d[0].replace('v', 'q') + ', ' + n[0].replace('v', 'q') + ', ' + w[0] + w[1]
    if op == 'SHA256SU0':
        n, d = vreg(args[0]), vreg(args[1])
        return 'sha256su0 ' + d[0] + d[1] + ', ' + n[0] + n[1]
    if op == 'SHA256SU1':
        m, n, d = vreg(args[0]), vreg(args[1]), vreg(args[2])
        return 'sha256su1 ' + d[0] + d[1] + ', ' + n[0] + n[1] + ', ' + m[0] + m[1]
    if op in ('SHA512H', 'SHA512H2'):
        w, n, d = vreg(args[0]), vreg(args[1]), vreg(args[2])
        return op.lower() + ' ' + d[0].replace('v', 'q') + ', ' + n[0].replace('v', 'q') + ', ' + w[0] + w[1]
    if op == 'SHA512SU0':
        n, d = vreg(args[0]), vreg(args[1])
        return 'sha512su0 ' + d[0] + d[1] + ', ' + n[0] + n[1]
    if op == 'SHA512SU1':
        m, n, d = vreg(args[0]), vreg(args[1]), vreg(args[2])
        return 'sha512su1 ' + d[0] + d[1] + ', ' + n[0] + n[1] + ', ' + m[0] + m[1]
    if op == 'FMOVS':
        # FMOVS (R0), F20 -> ldr s20, [x0]; FMOVS F20, (R0) -> str s20, [x0]
        if args[0].startswith('('):
            return 'ldr ' + vreg(args[1])[0] + ', [' + xreg(args[0].strip('()')) + ']'
        return 'str ' + vreg(args[0])[0] + ', [' + xreg(args[1].strip('()')) + ']'
    if op == 'SUB':
        imm = args[0].lstrip('$')
        if len(args) == 2:
            return 'sub ' + xreg(args[1]) + ', ' + xreg(args[1]) + ', #' + imm
        return 'sub ' + xreg(args[2]) + ', ' + xreg(args[1]) + ', #' + imm
    if op == 'MOVD':
        if args[0].startswith('R') and args[1].startswith('R'):
            return 'mov ' + xreg(args[1]) + ', ' + xreg(args[0])
        return None
    if op == 'CBNZ':
        return 'cbnz ' + xreg(args[0]) + ', ' + args[1]
    if op == 'PRFM':
        return None
    raise ValueError('unknown op ' + line)


def macros_and_lines(path):
    """Go's #define macros and the lines outside them; a line that is
    the name of a macro without parameters expands to its lines, and a
    macro with parameters is left to the caller (sha512)."""
    macros = {}
    lines = []
    name = None
    for raw in path.read_text().split('\n'):
        t = raw.strip()
        if name is not None:
            macros[name].append(t.rstrip('\\').strip())
            if not t.endswith('\\'):
                name = None
            continue
        m = re.match(r'^#define\s+(\w+)(\([^)]*\))?\s*\\$', t)
        if m:
            name = m.group(1)
            macros[name] = []
            continue
        if t.startswith('#define'):
            continue
        key = t.split('//')[0].strip()
        if key in macros:
            lines += macros[key]
        else:
            lines.append(raw)
    return macros, lines


def body(path):
    out = []
    for line in macros_and_lines(path)[1]:
        g = conv(line)
        if g is not None:
            out.append(g)
    return out


def sha512():
    """Expand Go's SHA512ROUND macros: i0..i4 are the rotating state
    registers, rc0/rc1 round constants, in0..in4 the message words."""
    src = '\n'.join(macros_and_lines(GO / 'sha512' / 'sha512block_arm64.s')[1])
    def trans(i0, i1, i2, i3, i4, rc0, in0):
        return [
            'add v5.2d, %s.2d, %s.2d' % (rc0, in0),
            'ext v6.16b, %s.16b, %s.16b, #8' % (i2, i3),
            'ext v5.16b, v5.16b, v5.16b, #8',
            'ext v7.16b, %s.16b, %s.16b, #8' % (i1, i2),
            'add %s.2d, %s.2d, v5.2d' % (i3, i3),
        ]
    out = []
    for line in src.split('\n'):
        line = line.split('//')[0].strip()
        m = re.match(r'^SHA512ROUND\((.*)\)$', line)
        if m:
            a = [x.strip().lower() for x in m.group(1).split(',')]
            i0, i1, i2, i3, i4, rc0, rc1, in0, in1, in2, in3, in4 = a
            out.append('ld1 {%s.2d}, [x4], #16' % rc1)
            out += trans(i0, i1, i2, i3, i4, rc0, in0)
            out.append('ext v5.16b, %s.16b, %s.16b, #8' % (in3, in4))
            out.append('sha512su0 %s.2d, %s.2d' % (in0, in1))
            out.append('sha512h %s, q6, v7.2d' % i3.replace('v', 'q'))
            out.append('sha512su1 %s.2d, %s.2d, v5.2d' % (in0, in2))
            out.append('add %s.2d, %s.2d, %s.2d' % (i4, i1, i3))
            out.append('sha512h2 %s, %s, %s.2d' % (i3.replace('v', 'q'), i1.replace('v', 'q'), i0))
            continue
        m = re.match(r'^SHA512ROUND_NO_UPDATE\((.*)\)$', line)
        if m:
            a = [x.strip().lower() for x in m.group(1).split(',')]
            i0, i1, i2, i3, i4, rc0, rc1, in0 = a
            out.append('ld1 {%s.2d}, [x4], #16' % rc1)
            out += trans(i0, i1, i2, i3, i4, rc0, in0)
            out.append('sha512h %s, q6, v7.2d' % i3.replace('v', 'q'))
            out.append('add %s.2d, %s.2d, %s.2d' % (i4, i1, i3))
            out.append('sha512h2 %s, %s, %s.2d' % (i3.replace('v', 'q'), i1.replace('v', 'q'), i0))
            continue
        m = re.match(r'^SHA512ROUND_LAST\((.*)\)$', line)
        if m:
            a = [x.strip().lower() for x in m.group(1).split(',')]
            i0, i1, i2, i3, i4, rc0, in0 = a
            out += trans(i0, i1, i2, i3, i4, rc0, in0)
            out.append('sha512h %s, q6, v7.2d' % i3.replace('v', 'q'))
            out.append('add %s.2d, %s.2d, %s.2d' % (i4, i1, i3))
            out.append('sha512h2 %s, %s, %s.2d' % (i3.replace('v', 'q'), i1.replace('v', 'q'), i0))
            continue
        g = conv(line)
        if g is not None:
            out.append(g)
    return out


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else 'sha256'
    if which == 'sha1':
        lines = body(GO / 'sha1' / 'sha1block_arm64.s')
    elif which == 'sha256':
        lines = body(GO / 'sha256' / 'sha256block_arm64.s')
    elif which == 'sha512':
        lines = sha512()
    else:
        sys.exit('sha1, sha256 or sha512')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
