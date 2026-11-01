#!/usr/bin/env python3
"""Writes testdata/civil.paslang and testdata/civil.out (P534): UnixToDate, UnixToYMD,
DateStr, TimeStr, StampStr and the DateOf, TimeOf and StampOf of hand-made dates, over
the edges of every kind of year (leap by 4, not by 100, leap by 400), the ends of the
Int64 range and five sweeps of 40000 moments each, whole days to 2^64 seconds. The
expected output is worked out here with Python integers by the days-from-civil
algorithm of Howard Hinnant (not the one the library uses), which the script checks
against Python's datetime for the years 1 to 9999 before it writes anything.

usage: gen_civil.py [--check]    --check writes nothing and fails when the two files in
testdata are not what this script writes
"""
import datetime
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata', 'civil')
CHECK = sys.argv[1:] == ['--check']
M64 = (1 << 64) - 1
MIN64 = -(1 << 63)
MAX64 = (1 << 63) - 1


def emit(path, text):
    if CHECK:
        if open(path).read() != text:
            sys.exit(path + ' is not what scripts/gen_civil.py writes')
    else:
        open(path, 'w').write(text)


def days_from_civil(y, m, d):
    y -= m <= 2
    era = y // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(z):
    z += 719468
    era = z // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    return y + (m <= 2), m, d


def fields(t):
    days, secs = divmod(t, 86400)
    y, m, d = civil_from_days(days)
    return (y, m, d, secs // 3600, secs % 3600 // 60, secs % 60, (days + 4) % 7,
            days - days_from_civil(y, 1, 1) + 1)


def digits(v, n):
    return str(max(v, 0)).zfill(n)


def stamp(f):
    return '%s-%s-%s %s:%s:%s' % (digits(f[0], 4), digits(f[1], 2), digits(f[2], 2),
                                   digits(f[3], 2), digits(f[4], 2), digits(f[5], 2))


def check_oracle():
    """the oracle against datetime: days and seconds across the years 1 to 9999"""
    base = datetime.datetime(1970, 1, 1)
    lo = int((datetime.datetime(1, 1, 1) - base).total_seconds())
    hi = int((datetime.datetime(9999, 12, 31, 23, 59, 59) - base).total_seconds())
    n = 6007
    for i in range(n + 1):
        t = lo + (hi - lo) * i // n + i * 12345
        t = min(max(t, lo), hi)
        d = base + datetime.timedelta(seconds=t)
        f = fields(t)
        want = (d.year, d.month, d.day, d.hour, d.minute, d.second, (d.weekday() + 1) % 7,
                d.timetuple().tm_yday)
        if f != want:
            sys.exit('the oracle differs from datetime at %d: %r %r' % (t, f, want))


def lit(t):
    return '-9223372036854775807 - 1' if t == MIN64 else str(t)


def signed(x):
    x &= M64
    return x - (1 << 64) if x >> 63 else x


YEARS = [-400, -100, -4, -1, 0, 1, 4, 100, 399, 400, 1582, 1600, 1899, 1900, 1969, 1970, 1971,
         1999, 2000, 2001, 2023, 2024, 2026, 2038, 2100, 2399, 2400, 9999, 10000, 12345, 100000,
         -100000, 292277026595, -292277022657]
TS = [MIN64, MIN64 + 1, MAX64, MAX64 - 1, -86401, -86400, -86399, -1, 0, 1, 86399, 86400, 86401]
for y in YEARS:
    for (m, d) in ((1, 1), (2, 28), (2, 29), (3, 1), (12, 31)):
        if m == 2 and d == 29 and not ((y % 4 == 0 and y % 100 != 0) or y % 400 == 0):
            continue
        z = days_from_civil(y, m, d)
        for s in (0, 43200 + 61, 86399):
            t = z * 86400 + s
            if MIN64 <= t <= MAX64:
                TS.append(t)
SWEEPS = [(-3000000000000, 150000000007, 40000), (-4000000000, 200003, 40000),
          (0, 86400, 40000), (-(1 << 62), (1 << 63) // 40000, 40000),
          (MIN64, (1 << 64) // 40001, 40000)]
HAND = [(12345, 1, 1, 0, 0, 0), (-5, 3, 4, 5, 6, 7), (2026, 123, 4, 5, 6, 7),
        (2026, 12, 31, 100, 0, 0), (0, 0, 0, 0, 0, 0), (9999, 99, 99, 99, 99, 99),
        (10000, 100, 100, 100, 100, 100), (2026, 5, 6, -1, 2, 3), (2026, 5, 6, 7, 8, 9),
        (99, 1, 2, 3, 4, 5), (7, 8, 9, 10, 11, 12)]

PROGRAM = '''program civil;

{ P534: UnixToDate, UnixToYMD, DateStr, TimeStr, StampStr and the written forms of hand-made dates }

uses
  pastime;

var
  bad: Integer;

procedure One(T: Int64);
var
  d: TDate;
  y, m, dd: Integer;
begin
  d := UnixToDate(T);
  UnixToYMD(T, y, m, dd);
  if (y <> d.Year) or (m <> d.Month) or (dd <> d.Day) then
    bad := bad + 1;
  WriteLn(T, ' ', d.Year, ' ', d.Month, ' ', d.Day, ' ', d.Hour, ' ', d.Minute, ' ', d.Second, ' ', d.Wday, ' ', d.Yday, ' ', d.Nano);
  WriteLn(DateStr(T), ' ', TimeStr(T), ' ', StampStr(T));
end;

procedure Sweep(Start, Step, Count: Int64);
var
  k, t, h: Int64;
  d: TDate;
  y, m, dd: Integer;
begin
  h := 0;
  for k := 0 to Count - 1 do
  begin
    t := Start + k * Step;
    d := UnixToDate(t);
    UnixToYMD(t, y, m, dd);
    if (y <> d.Year) or (m <> d.Month) or (dd <> d.Day) then
      bad := bad + 1;
    h := h * 31 + d.Year;
    h := h * 31 + d.Month;
    h := h * 31 + d.Day;
    h := h * 31 + d.Hour;
    h := h * 31 + d.Minute;
    h := h * 31 + d.Second;
    h := h * 31 + d.Wday;
    h := h * 31 + d.Yday;
  end;
  WriteLn('sweep ', Start, ' ', Step, ' ', Count, ' ', h);
end;

procedure Hand(Y, Mo, D, H, Mi, S: Integer);
var
  x: TDate;
begin
  x.Year := Y;
  x.Month := Mo;
  x.Day := D;
  x.Hour := H;
  x.Minute := Mi;
  x.Second := S;
  x.Nano := 0;
  x.Wday := 0;
  x.Yday := 0;
  WriteLn(DateOf(x), ' ', TimeOf(x), ' ', StampOf(x));
end;

begin
  bad := 0;
%s  WriteLn('mismatches ', bad);
end.
'''


def build():
    body = []
    exp = []
    for t in TS:
        body.append('  One(%s);\n' % lit(t))
        f = fields(t)
        exp.append('%d %d %d %d %d %d %d %d %d 0\n' % ((t,) + f))
        exp.append('%s %s %s\n' % (stamp(f).split(' ')[0], stamp(f).split(' ')[1], stamp(f)))
    for (a, b, c) in SWEEPS:
        body.append('  Sweep(%s, %d, %d);\n' % (lit(a), b, c))
        h = 0
        for k in range(c):
            f = fields(a + k * b)
            for v in f:
                h = signed(h * 31 + v)
        exp.append('sweep %d %d %d %d\n' % (a, b, c, h))
    for hnd in HAND:
        body.append('  Hand(%d, %d, %d, %d, %d, %d);\n' % hnd)
        f = hnd
        exp.append('%s-%s-%s %s:%s:%s %s\n' % (digits(f[0], 4), digits(f[1], 2), digits(f[2], 2),
                                              digits(f[3], 2), digits(f[4], 2), digits(f[5], 2), stamp(f)))
    exp.append('mismatches 0\n')
    return PROGRAM % ''.join(body), ''.join(exp)


check_oracle()
prog, out = build()
emit(OUT + '.paslang', prog)
emit(OUT + '.out', out)
