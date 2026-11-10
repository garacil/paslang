#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P584: probe the production string-view range guard without reading addresses.

Usage: check_strview_range.py COMPILER BUILDDIR QEMU

The private inline predicate is copied verbatim from passtr into a probe;
PasStrView must use that predicate for its real wrap guard. Python's
arbitrary-precision unsigned sum supplies the independent answers. No
synthetic address is dereferenced, and no helper is exported to programs.
Probe arguments depend on ParamCount (zero when launched without arguments),
so ordinary inlining cannot turn the boundary cases into constants.
"""
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile


SPACE = 1 << 64
MAX_LENGTH = (1 << 63) - 1


def cases():
    starts = [0, 1, 2, (1 << 63) - 2, (1 << 63) - 1, 1 << 63,
              (1 << 63) + 1, (1 << 63) + 2, SPACE - 65536,
              SPACE - 4096, SPACE - 8, SPACE - 2, SPACE - 1]
    lengths = [1, 2, 3, 7, 8, 9, 4095, 4096, 4097, 65535, 65536,
               65537, MAX_LENGTH - 1, MAX_LENGTH]
    result = [(start, length) for start in starts for length in lengths]
    rng = random.Random(584)
    result += [(rng.getrandbits(64), rng.randrange(1, MAX_LENGTH + 1))
               for _ in range(128)]
    return result


def signed(value):
    return value if value < (1 << 63) else value - SPACE


def literal(value):
    return 'Low(Int64)' if value == -(1 << 63) else str(value)


def probe_source(helper, rows):
    calls = ''.join('  Probe(%s + Adjustment, %s + Adjustment);\n' %
                    (literal(signed(start)), length)
                    for start, length in rows)
    return ('program rangeprobe;\nvar Adjustment: Int64;\n\n' + helper +
            '\nprocedure Probe(Address, Count: Int64);\nbegin\n'
            "  WriteLn(Address, ' ', Count, ' ', "
            'Ord(StrViewPastEnd(Pointer(Address), Count)));\nend;\n\nbegin\n'
            '  Adjustment := ParamCount;\n' +
            calls + 'end.\n')


def command(args, expect_success=True):
    result = subprocess.run(args, text=True, capture_output=True, timeout=90)
    if expect_success and result.returncode:
        raise SystemExit('strview-range command failed: ' + ' '.join(args) +
                         '\n' + result.stdout + result.stderr)
    return result


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    compiler = str(Path(sys.argv[1]).resolve())
    build = Path(sys.argv[2]).resolve()
    qemu = str(Path(sys.argv[3]).resolve())
    tree = Path(__file__).resolve().parents[1]
    source = (tree / 'src/lib/passtr.paslang').read_text()
    interface, implementation = source.split('\nimplementation\n', 1)
    if re.search(r'\bStrViewPastEnd\b', interface):
        raise SystemExit('the range predicate must remain private to passtr')
    body = implementation[implementation.index('function PasStrView(P: Pointer; N: Int64): string;'):]
    if body.count('if StrViewPastEnd(P, N) then') != 1:
        raise SystemExit('PasStrView no longer uses the production range predicate once; review this checker')
    found = re.findall(r'(?ms)^function StrViewPastEnd\(P: Pointer; N: Int64\): Boolean; inline;\n'
                       r'begin\n.*?^end;\n', source)
    if len(found) != 1:
        raise SystemExit('the private range predicate changed; review this checker')
    helper = found[0]
    old = '(Int64(P) + N > 0)'
    if helper.count(old) != 1:
        raise SystemExit('the endpoint comparison changed; review its original-boundary mutant')
    mutant = helper.replace(old, '(Int64(P) + N >= 0)')
    rows = cases()
    expected = ''.join('%d %d %d\n' % (signed(start), length,
                                      int(start + length > SPACE))
                       for start, length in rows)
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='strview-range-', dir=build) as tmp:
        work = Path(tmp)
        for target, units, launch in [('amd64', build, []),
                                      ('arm64', build / 'a64', [qemu])]:
            assembly = (units / 'passtr.s').read_text()
            if not re.search(r'^p_passtr_passtrview:', assembly, re.M):
                raise SystemExit(target + ': production PasStrView is absent from its assembly')
            if re.search(r'^\s*(?:call|bl)\s+p_passtr_strviewpastend\b', assembly, re.M):
                raise SystemExit(target + ': the optimized production guard calls its inline predicate')
            for inline in ('0', '40'):
                for label, code in [('guard', helper), ('old-endpoint', mutant)]:
                    folder = work / target / inline / label
                    folder.mkdir(parents=True)
                    program = folder / 'rangeprobe.paslang'
                    program.write_text(probe_source(code, rows))
                    output = folder / 'rangeprobe'
                    command([compiler, '-target', target, '-cpu', 'base',
                             '-inline', inline, '-Fu', str(units),
                             '-o', str(output), str(program)])
                    got = command([*launch, str(output)])
                    if label == 'guard' and got.stdout != expected:
                        raise SystemExit(target + '/' + inline + ': production range predicate disagrees with the unsigned oracle')
                    if label == 'old-endpoint' and got.stdout == expected:
                        raise SystemExit(target + '/' + inline + ': original endpoint mutant escaped')
            program = work / target / 'removedmapput.paslang'
            program.write_text('program removedmapput;\nuses pasmap;\n'
                               'var p: Pointer;\nbegin p := PasMapPut(nil, nil, nil); end.\n')
            refused = command([compiler, '-target', target, '-cpu', 'base',
                               '-c', '-Fu', str(units), '-o', str(program.with_suffix('')),
                               str(program)], expect_success=False)
            diagnostic = refused.stdout + refused.stderr
            if (refused.returncode == 0 or 'PasMapPut' not in diagnostic
                    or 'unknown' not in diagnostic.lower()):
                raise SystemExit(target + ': removed generic map put remained callable or failed for another reason: ' + diagnostic)
    print('strview-range: %d unsigned boundary/random cases on both targets, inline 0/40; '
          'original endpoint mutant caught; no optimized helper call; generic map put refused' % len(rows))


if __name__ == '__main__':
    main()
