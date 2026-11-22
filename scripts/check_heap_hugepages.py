#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Check the Linux VM policy for full and partial paslang heap chunks."""

from pathlib import Path
import re
import select
import subprocess
import sys
from tempfile import TemporaryDirectory

PROGRAM = """program heapusage;
var b, stop: string; bytes, i: Integer;
begin
  bytes := 16384;
  if ParamCount > 0 then
    bytes := PMD_BYTES * 3 + 16384;
  SetLength(b, bytes);
  i := 1;
  while i <= bytes do
  begin
    b[i] := 'x';
    i := i + 4096;
  end;
  WriteLn(Integer(@b[1]), ' ', Integer(@b[bytes]));
  ReadLn(stop);
  if b[1] <> 'x' then
    Halt(1);
end.
"""

MAPPING = re.compile(r'^([0-9a-f]+)-([0-9a-f]+) ', re.MULTILINE)


def vm_flags(pid, addresses):
    smaps = Path(f'/proc/{pid}/smaps').read_text()
    mappings = list(MAPPING.finditer(smaps))
    result = []
    for address in addresses:
        for i, m in enumerate(mappings):
            if int(m[1], 16) <= address < int(m[2], 16):
                end = mappings[i + 1].start() if i + 1 < len(mappings) else len(smaps)
                flags = re.search(r'^VmFlags: (.*)$', smaps[m.end():end], re.MULTILINE)
                result.append(set(flags[1].split()) if flags else set())
                break
        else:
            raise RuntimeError(f'no heap mapping for {address:#x}')
    return result


def check_image(argv, large):
    args = ['large'] if large else []
    with subprocess.Popen(argv + args, stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) as p:
        try:
            ready, _, _ = select.select([p.stdout], [], [], 30)
            if not ready:
                raise RuntimeError(f'no heap address from {argv!r}')
            first, last = map(int, p.stdout.readline().split())
            head, tail = vm_flags(p.pid, (first, last))
            if ('hg' if large else 'nh') not in head or 'nh' not in tail:
                raise RuntimeError(f'{argv!r} large={large}: heap VM flags {head}, {tail}')
            out, err = p.communicate(b'\n', timeout=30)
            if p.returncode or out or err:
                raise RuntimeError(f'{argv!r}: exit={p.returncode}, output={out!r}, error={err!r}')
        finally:
            if p.poll() is None:
                p.kill()
                p.communicate(timeout=5)


def check(compiler, sdk, work, qemu, pmd):
    source = work / 'heapusage.paslang'
    source.write_text(PROGRAM.replace('PMD_BYTES', str(pmd)))
    for target, units, launch in (('amd64', sdk, []), ('arm64', sdk / 'a64', [str(qemu)])):
        image = work / target
        subprocess.run([compiler, '-target', target, '-cpu', 'base', '-Fu', units,
                        '-o', image, source], check=True, timeout=90)
        for large in (False, True):
            check_image(launch + [str(image)], large)


def main():
    if len(sys.argv) != 4:
        raise SystemExit('usage: check_heap_hugepages.py compiler builddir qemu')
    compiler, sdk, qemu = (Path(arg).resolve() for arg in sys.argv[1:])
    pmd_file = Path('/sys/kernel/mm/transparent_hugepage/hpage_pmd_size')
    if not pmd_file.exists():
        print('heap huge-page policy: skipped, Linux THP unavailable')
        return
    pmd = int(pmd_file.read_text())
    with TemporaryDirectory(prefix='heap-hugepages-', dir=sdk) as folder:
        check(compiler, sdk, Path(folder), qemu, pmd)
    print('THP eligibility of complete and partial heap chunks checked on amd64 and arm64')


if __name__ == '__main__':
    main()
