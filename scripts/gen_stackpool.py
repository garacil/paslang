#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""Writes testdata/stackpool.paslang and testdata/stackpool.out (P256): waves
of routines that each grow a stack to a different depth, some of which park
holding it, so that stacks are kept for the next growth and given back by
the routines that finish, and the records of finished routines are taken by
the next wave with their first stack again. A string in every sixteenth
frame keeps pointers on the stack for the stack maps, and every routine
makes garbage after the growth for the collector to run. The expected
output is worked out in Python: the sum Down(N, T) returns is
T + sum over i = 1..N of ((i + T) and 3).

usage: gen_stackpool.py [--check]    --check writes nothing and fails when the
two files in testdata are not what this script writes"""
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata', 'stackpool')
CHECK = sys.argv[1:] == ['--check']
WAVES = 3
WORKERS = 60


def depth(i):
    return 200 + (i * 7919) % 30000


def down(n, t):
    return t + sum(((i + t) & 3) for i in range(1, n + 1))


SRC = """program stackpool;

uses
  sysutils;

var
  wg: waitgroup;
  gate: chan of Integer;
  res: array[0..%(total)d] of Integer;
  junk: array[0..%(total)d] of Integer;
  deepres: Integer;

function Down(N, T: Integer): Integer;
var
  s: string;
begin
  if N = 0 then
    Result := T
  else if (N and 15) = 0 then
  begin
    s := IntToStr(N);
    Result := Down(N - 1, T) + ((N + T) and 3) + Ord(s[Length(s)]) - 48 - (N mod 10);
  end
  else
    Result := Down(N - 1, T) + ((N + T) and 3);
end;

procedure Deep;
begin
  deepres := Down(900000, 5);
  wg.Done;
end;

procedure Worker(Id: Integer);
var
  i, r, k: Integer;
  t: string;
begin
  r := Down(200 + (Id * 7919) mod 30000, Id mod 7);
  { the garbage a cycle of the collector runs for, with the stack grown }
  t := '';
  for i := 1 to 400 do
    t := IntToStr(i) + Copy(t, 1, 100);
  k := Length(t);
  if Id mod 5 = 0 then
    k := k + Recv(gate) - 1;
  res[Id] := r;
  junk[Id] := k;
  wg.Done;
end;

var
  w, i, id, s, parked: Integer;
begin
  { a stack that grows past what the cache keeps (8 MiB), in a routine of its own }
  wg.Add(1);
  pas Deep;
  wg.Wait;
  WriteLn('deep ', deepres);
  gate := MakeChan();
  for w := 0 to %(waves)d - 1 do
  begin
    wg.Add(%(workers)d);
    parked := 0;
    for i := 0 to %(workers)d - 1 do
    begin
      id := w * %(workers)d + i;
      if id mod 5 = 0 then
        parked := parked + 1;
      pas Worker(id);
    end;
    for i := 1 to parked do
      Send(gate, 1);
    wg.Wait;
    s := 0;
    for i := 0 to %(workers)d - 1 do
      s := s + res[w * %(workers)d + i];
    WriteLn('wave ', w, ' ', s);
  end;
  s := 0;
  for i := 0 to %(total)d do
    s := s + junk[i];
  WriteLn('garbage ', s);
end.
"""


def build():
    total = WAVES * WORKERS - 1
    prog = SRC % {'total': total, 'waves': WAVES, 'workers': WORKERS}
    out = ['deep %d' % down(900000, 5)]
    for w in range(WAVES):
        out.append('wave %d %d' % (w, sum(down(depth(w * WORKERS + i), (w * WORKERS + i) % 7) for i in range(WORKERS))))
    # the string a worker builds: t := IntToStr(i) + Copy(t, 1, 100) for i in 1..400
    t = ''
    for i in range(1, 401):
        t = str(i) + t[:100]
    g = 0
    for i in range(WAVES * WORKERS):
        k = len(t)
        if i % 5 == 0:
            k = k + 1 - 1
        g += k
    out.append('garbage %d' % g)
    return prog, '\n'.join(out) + '\n'


def emit(path, text):
    if CHECK:
        if open(path).read() != text:
            sys.exit(path + ' is not what scripts/gen_stackpool.py writes')
    else:
        open(path, 'w').write(text)


prog, exp = build()
emit(OUT + '.paslang', prog)
emit(OUT + '.out', exp)
