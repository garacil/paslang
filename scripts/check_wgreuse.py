#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""check_wgreuse.py PASLANGC BUILDDIR QEMU: a waitgroup used again wakes nobody early (P585).

The call that brings a waitgroup's count to zero (PasWaitGroupAdd, src/lib/pasroutines.paslang) takes the
lock and wakes the routines parked in Wait, and it can be stopped between the add and the lock. A routine
that found the count at zero without parking has gone on by then; when it used the waitgroup again and was
parked in the next Wait, the late call woke it with routines still to come. Seen 2026-11-06 in a stress of
channels closed under their senders, one run in three, and never in a test written for it: the place where
the call must be stopped is two instructions wide.

So the place is made wide here. testdata/wgagain is compiled against a copy of the unit whose call that
reaches zero sleeps a millisecond before it takes the lock, on both machines, and no Wait may come back with
a routine still to come. Then the same copy without the question the call asks under the lock (is the count
still zero), which is the unit as it was: every round must come back early there, or this check would not
see the failure it is here for."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

if len(sys.argv) != 4:
    sys.exit(__doc__)
compiler = str(Path(sys.argv[1]).resolve())
build = Path(sys.argv[2]).resolve()
qemu = str(Path(sys.argv[3]).resolve())
root = Path(__file__).resolve().parent.parent
source = (root / 'src/lib/pasroutines.paslang').read_text()
program = root / 'testdata/wgagain.paslang'
good = (root / 'testdata/wgagain.out').read_text()

asked = """  if n <> 0 then
    Exit;
  SpinLock(@W.Spin);
  if AtomicAdd(@W.Count, 0) = 0 then
  begin
    g := QWake1(@W.Head);
    while g <> 0 do
    begin
      ReadyG(g);
      g := QWake1(@W.Head);
    end;
  end;
  SpinUnlock(@W.Spin);
"""
if source.count(asked) != 1:
    sys.exit('check_wgreuse: PasWaitGroupAdd is not the text this check widens; read it and bring the check up to date')
wide = asked.replace("  SpinLock(@W.Spin);\n", "  Sleep(1);\n  SpinLock(@W.Spin);\n")
unasked = """  if n <> 0 then
    Exit;
  Sleep(1);
  SpinLock(@W.Spin);
  g := QWake1(@W.Head);
  while g <> 0 do
  begin
    ReadyG(g);
    g := QWake1(@W.Head);
  end;
  SpinUnlock(@W.Spin);
"""
work = build / 'check-wgreuse'
if work.exists():
    shutil.rmtree(work)


def run(command, timeout=120):
    r = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    return r.returncode, r.stdout.decode(errors='replace')


for name, text in (('asked', source.replace(asked, wide)), ('unasked', source.replace(asked, unasked))):
    for machine, flags, units, launch in (('amd64', [], build, []), ('arm64', ['-target', 'arm64'], build / 'a64', [qemu])):
        d = work / name / machine
        d.mkdir(parents=True)
        (d / 'pasroutines.paslang').write_text(text)
        fu = ['-Fu', str(d), '-Fu', str(units)]
        for command in ([compiler, *flags, '-cpu', 'base', '-c', *fu, '-o', str(d / 'pasroutines'), str(d / 'pasroutines.paslang')],
                        [compiler, *flags, *fu, '-o', str(d / 'wgagain'), str(program)]):
            rc, out = run(command)
            if rc:
                sys.exit('check_wgreuse: %s %s: %s' % (name, machine, out.strip()[-300:]))
        rc, out = run([*launch, str(d / 'wgagain')])
        if name == 'asked':
            if rc != 0 or out != good:
                sys.exit('check_wgreuse: %s, the call that reaches zero stopped a millisecond before its lock: %s'
                         % (machine, out.strip()[-200:] or 'exit %d' % rc))
        elif rc != 0 or 'waits came back with a routine still to come' not in out:
            sys.exit('check_wgreuse: %s, the unit as it was (no question under the lock) passed: this check does not '
                     'see the failure any more: %s' % (machine, out.strip()[-200:] or 'exit %d' % rc))
shutil.rmtree(work)
print('check_wgreuse: with the call that reaches zero stopped a millisecond before its lock, no Wait of testdata/wgagain '
      'comes back early on either machine; without its question under the lock, they do')
