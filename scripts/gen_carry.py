#!/usr/bin/env python3
"""Writes testdata/carry.paslang and testdata/carry.out (P508): AddCarry and
SubBorrow over four words (a 256-bit sum and difference) in every form the
emitter works out in registers and the ones it leaves to the general path:
the carry in a word variable of 1, 2 or 8 bytes (a local or a global), the
operands variables, elements, fields, constants and expressions, the carry in
a constant, a variable or an expression, the sum in a variable that is also an
operand, a carry out that is not a variable (an element, a field, a variable
parameter), a call inside a condition, a call whose value is dropped and a
call inside a call. The expected output is worked out here with Python
integers (the sum and difference of 256-bit numbers), not by the compiler;
the program also checks every sum against a plain-arithmetic reference of its
own and says how many differ.

usage: gen_carry.py [--check]    --check writes nothing and fails when the two
files in testdata are not what this script writes
"""
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'testdata', 'carry')
CHECK = sys.argv[1:] == ['--check']
MASK = (1 << 64) - 1


def emit(path, text):
    if CHECK:
        if open(path).read() != text:
            sys.exit(path + ' is not what scripts/gen_carry.py writes')
    else:
        open(path, 'w').write(text)


def s64(x):
    x &= MASK
    return x - (1 << 64) if x >> 63 else x


# the values of a and b, as the program spells them
V = [("0", 0), ("1", 1), ("2", 2), ("$7FFFFFFFFFFFFFFF", (1 << 63) - 1), ("$8000000000000000", 1 << 63),
     ("$8000000000000001", (1 << 63) + 1), ("-2", MASK - 1), ("-1", MASK), ("$FFFFFFFF", 0xFFFFFFFF),
     ("$100000000", 1 << 32), ("$FFFFFFFF00000000", 0xFFFFFFFF00000000), ("$0123456789ABCDEF", 0x0123456789ABCDEF)]
CI = [0, 1, 2, -1, 5]
KC = [0xFFFFFFFF00000000, MASK, 5, 1 << 63]


def limbs_x(a, b):
    return [a, a ^ b, b, (a + b + 1) & MASK]


def limbs_y(a, b):
    return [b, a, b ^ 12345, (a - 3) & MASK]


def wide(ls):
    return sum(v << (64 * i) for i, v in enumerate(ls))


def chain(op, x, y, ci):
    """the four words and the carry out of x + y + (ci <> 0), or x - y - (ci <> 0)"""
    cin = 1 if ci != 0 else 0
    if op == 0:
        t = wide(x) + wide(y) + cin
        carry = t >> 256
    else:
        t = wide(x) - wide(y) - cin
        carry = 1 if t < 0 else 0
    t &= (1 << 256) - 1
    return [(t >> (64 * i)) & MASK for i in range(4)], carry


def step(op, a, b, ci):
    """one word and its carry out"""
    cin = 1 if ci != 0 else 0
    if op == 0:
        t = a + b + cin
        return t & MASK, t >> 64
    t = a - b - cin
    return t & MASK, 1 if t < 0 else 0


def fold(h, v):
    return ((h ^ (v & MASK)) * 1099511628211) & MASK


SEED = 0xCBF29CE484222325

# (name, locals, body, y of the reference: Y, K (the constants) or X, carry in of the reference)
# FN is AddCarry or SubBorrow. The globals X, Y (words), R (the sum) and Rc (the carry out).
FORMS = [
    ('local', 'a0, a1, a2, a3, b0, b1, b2, b3, r0, r1, r2, r3, c: Int64',
     """  a0 := X[0]; a1 := X[1]; a2 := X[2]; a3 := X[3];
  b0 := Y[0]; b1 := Y[1]; b2 := Y[2]; b3 := Y[3];
  r0 := FN(a0, b0, ci, c);
  r1 := FN(a1, b1, c, c);
  r2 := FN(a2, b2, c, c);
  r3 := FN(a3, b3, c, c);
  R[0] := r0; R[1] := r1; R[2] := r2; R[3] := r3; Rc := c;""", 'Y', 'ci'),
    ('elems', 'r0, r1, r2, r3, c: Int64',
     """  r0 := FN(X[0], Y[0], ci, c);
  r1 := FN(X[1], Y[1], c, c);
  r2 := FN(X[2], Y[2], c, c);
  r3 := FN(X[3], Y[3], c, c);
  R[0] := r0; R[1] := r1; R[2] := r2; R[3] := r3; Rc := c;""", 'Y', 'ci'),
    ('destarr', 'c: Int64',
     """  R[0] := FN(X[0], Y[0], ci, c);
  R[1] := FN(X[1], Y[1], c, c);
  R[2] := FN(X[2], Y[2], c, c);
  R[3] := FN(X[3], Y[3], c, c);
  Rc := c;""", 'Y', 'ci'),
    ('byte', 'c: Byte',
     """  R[0] := FN(X[0], Y[0], ci, c);
  R[1] := FN(X[1], Y[1], c, c);
  R[2] := FN(X[2], Y[2], c, c);
  R[3] := FN(X[3], Y[3], c, c);
  Rc := c;""", 'Y', 'ci'),
    ('word', 'c: Word',
     """  R[0] := FN(X[0], Y[0], ci, c);
  R[1] := FN(X[1], Y[1], c, c);
  R[2] := FN(X[2], Y[2], c, c);
  R[3] := FN(X[3], Y[3], c, c);
  Rc := c;""", 'Y', 'ci'),
    ('glob', '',
     """  R[0] := FN(X[0], Y[0], ci, GC);
  R[1] := FN(X[1], Y[1], GC, GC);
  R[2] := FN(X[2], Y[2], GC, GC);
  R[3] := FN(X[3], Y[3], GC, GC);
  Rc := GC;""", 'Y', 'ci'),
    ('loop', 'i, c: Int64',
     """  c := ci;
  for i := 0 to 3 do
    R[i] := FN(X[i], Y[i], c, c);
  Rc := c;""", 'Y', 'ci'),
    ('rec', 'P, Q, S: P4; c: Int64',
     """  P.a0 := X[0]; P.a1 := X[1]; P.a2 := X[2]; P.a3 := X[3];
  Q.a0 := Y[0]; Q.a1 := Y[1]; Q.a2 := Y[2]; Q.a3 := Y[3];
  S.a0 := FN(P.a0, Q.a0, ci, c);
  S.a1 := FN(P.a1, Q.a1, c, c);
  S.a2 := FN(P.a2, Q.a2, c, c);
  S.a3 := FN(P.a3, Q.a3, c, c);
  R[0] := S.a0; R[1] := S.a1; R[2] := S.a2; R[3] := S.a3; Rc := c;""", 'Y', 'ci'),
    ('expr', 'c: Int64',
     """  R[0] := FN(X[0] and (-1), Y[0] or 0, ci, c);
  R[1] := FN(X[1] xor 0, Y[1] + 0, c, c);
  R[2] := FN(X[2] - 0, Y[2] * 1, c, c);
  R[3] := FN(0 + X[3], Y[3] and $FFFFFFFFFFFFFFFF, c, c);
  Rc := c;""", 'Y', 'ci'),
    ('consts', 'c: Int64',
     """  R[0] := FN(X[0], $FFFFFFFF00000000, ci, c);
  R[1] := FN(X[1], -1, c, c);
  R[2] := FN(X[2], 5, c, c);
  R[3] := FN(X[3], $8000000000000000, c, c);
  Rc := c;""", 'K', 'ci'),
    ('same', 'a0, a1, a2, a3, c: Int64',
     """  a0 := X[0]; a1 := X[1]; a2 := X[2]; a3 := X[3];
  a0 := FN(a0, Y[0], ci, c);
  a1 := FN(a1, Y[1], c, c);
  a2 := FN(a2, Y[2], c, c);
  a3 := FN(a3, Y[3], c, c);
  R[0] := a0; R[1] := a1; R[2] := a2; R[3] := a3; Rc := c;""", 'Y', 'ci'),
    ('twice', 'a0, a1, a2, a3, c: Int64',
     """  a0 := X[0]; a1 := X[1]; a2 := X[2]; a3 := X[3];
  a0 := FN(a0, a0, ci, c);
  a1 := FN(a1, a1, c, c);
  a2 := FN(a2, a2, c, c);
  a3 := FN(a3, a3, c, c);
  R[0] := a0; R[1] := a1; R[2] := a2; R[3] := a3; Rc := c;""", 'X', 'ci'),
    ('cineq', 'c: Int64',
     """  R[0] := FN(X[0], Y[0], Ord(X[0] = Y[0]), c);
  R[1] := FN(X[1], Y[1], c, c);
  R[2] := FN(X[2], Y[2], c, c);
  R[3] := FN(X[3], Y[3], c, c);
  Rc := c;""", 'Y', 'eq'),
    ('cinone', 'c: Int64',
     """  R[0] := FN(X[0], Y[0], 1, c);
  R[1] := FN(X[1], Y[1], c, c);
  R[2] := FN(X[2], Y[2], c, c);
  R[3] := FN(X[3], Y[3], c, c);
  Rc := c;""", 'Y', 'one'),
    ('cinfive', 'c: Int64',
     """  R[0] := FN(X[0], Y[0], 5, c);
  R[1] := FN(X[1], Y[1], c, c);
  R[2] := FN(X[2], Y[2], c, c);
  R[3] := FN(X[3], Y[3], c, c);
  Rc := c;""", 'Y', 'five'),
    ('cinzero', 'c: Int64',
     """  R[0] := FN(X[0], Y[0], 0, c);
  R[1] := FN(X[1], Y[1], c, c);
  R[2] := FN(X[2], Y[2], c, c);
  R[3] := FN(X[3], Y[3], c, c);
  Rc := c;""", 'Y', 'zero'),
    ('cinglob', 'c: Int64',
     """  G2 := ci;
  R[0] := FN(X[0], Y[0], G2, c);
  R[1] := FN(X[1], Y[1], c, c);
  R[2] := FN(X[2], Y[2], c, c);
  R[3] := FN(X[3], Y[3], c, c);
  Rc := c;""", 'Y', 'ci'),
    ('cinbyte', 'c: Int64; cb: Byte',
     """  cb := Byte(ci and 255);
  R[0] := FN(X[0], Y[0], cb, c);
  R[1] := FN(X[1], Y[1], c, c);
  R[2] := FN(X[2], Y[2], c, c);
  R[3] := FN(X[3], Y[3], c, c);
  Rc := c;""", 'Y', 'ci'),
    ('cinexpr', 'c: Int64',
     """  R[0] := FN(X[0], Y[0], ci and 6, c);
  R[1] := FN(X[1], Y[1], c, c);
  R[2] := FN(X[2], Y[2], c, c);
  R[3] := FN(X[3], Y[3], c, c);
  Rc := c;""", 'Y', 'and6'),
    ('varpar', 'c: Int64',
     """  c := ci;
  Step(FN0, R[0], c, X[0], Y[0]);
  Step(FN0, R[1], c, X[1], Y[1]);
  Step(FN0, R[2], c, X[2], Y[2]);
  Step(FN0, R[3], c, X[3], Y[3]);
  Rc := c;""", 'Y', 'ci'),
    ('gdest', 'c: Int64',
     """  Gq0 := FN(X[0], Y[0], ci, c);
  Gq1 := FN(X[1], Y[1], c, c);
  Gq2 := FN(X[2], Y[2], c, c);
  Gq3 := FN(X[3], Y[3], c, c);
  R[0] := Gq0; R[1] := Gq1; R[2] := Gq2; R[3] := Gq3; Rc := c;""", 'Y', 'ci'),
    ('upvar', 'RAW:var\n  r0, r1, r2, r3, c: Int64;\n\n  procedure Go;\n  begin\n    r0 := FN(X[0], Y[0], ci, c);\n    r1 := FN(X[1], Y[1], c, c);\n    r2 := FN(X[2], Y[2], c, c);\n    r3 := FN(X[3], Y[3], c, c);\n  end;\n',
     """  Go;
  R[0] := r0; R[1] := r1; R[2] := r2; R[3] := r3; Rc := c;""", 'Y', 'ci'),
    ('narrow', 'wa: Word; bb: Byte; sx, si: SmallInt; c: Int64',
     """  wa := Word(X[0] and $FFFF);
  bb := Byte(Y[0] and $FF);
  if X[1] < 0 then
    sx := -5
  else
    sx := 7;
  if Y[1] < 0 then
    si := -100
  else
    si := 100;
  EX[0] := wa; EX[1] := sx; EX[2] := X[2]; EX[3] := wa;
  EY[0] := bb; EY[1] := si; EY[2] := bb; EY[3] := Y[3];
  R[0] := FN(wa, bb, ci, c);
  R[1] := FN(sx, si, c, c);
  R[2] := FN(X[2], bb, c, c);
  R[3] := FN(wa, Y[3], c, c);
  Rc := c;""", 'N', 'ci'),
    ('elemcarry', 'c: array[0..1] of Int64',
     """  R[0] := FN(X[0], Y[0], ci, c[1]);
  R[1] := FN(X[1], Y[1], c[1], c[1]);
  R[2] := FN(X[2], Y[2], c[1], c[1]);
  R[3] := FN(X[3], Y[3], c[1], c[1]);
  Rc := c[1];""", 'Y', 'ci'),
    ('fieldcarry', 'c: P4',
     """  R[0] := FN(X[0], Y[0], ci, c.a1);
  R[1] := FN(X[1], Y[1], c.a1, c.a1);
  R[2] := FN(X[2], Y[2], c.a1, c.a1);
  R[3] := FN(X[3], Y[3], c.a1, c.a1);
  Rc := c.a1;""", 'Y', 'ci'),
]

REFY = {'Y': 0, 'K': 1, 'X': 2, 'N': 3}
REFCI = {'ci': 'ci', 'eq': 'Ord(X[0] = Y[0])', 'one': '1', 'five': '5', 'zero': '0', 'and6': '(ci and 6)'}


def ref_ci(kind, ci, x, y):
    return {'ci': ci, 'eq': 1 if x[0] == y[0] else 0, 'one': 1, 'five': 5, 'zero': 0, 'and6': ci & 6}[kind]


POISON = ['Pz := AddCarry(-1, -1, 0, Pc);', 'Pz := SubBorrow(0, 1, 0, Pc);']

P = []


def w(s):
    P.append(s)


w("""program carry;

{ AddCarry and SubBorrow over four words (P508): every form of the carry
  variable, of the operands and of the carry in, with the boundary values
  of a and b and five carries in. The sums are checked against plain
  arithmetic here and their hash is the one scripts/gen_carry.py works
  out. }

type
  W4 = array[0..3] of Int64;
  P4 = record
    a0, a1, a2, a3: Int64;
  end;

const
  NV = %d;
  NC = %d;

var
  X, Y, R, KC, EX, EY: W4;
  Rc, Hh, Bad, Cases, GC, G2, Gq0, Gq1, Gq2, Gq3, Pz, Pc: Int64;
  VA: array[0..%d] of Int64;
  CIS: array[0..%d] of Int64;

function ULt(A, B: Int64): Boolean;
begin
  Result := (A xor Low(Int64)) < (B xor Low(Int64));
end;

procedure Fold(v: Int64);
begin
  Hh := (Hh xor v) * 1099511628211;
end;

{ the sum or the difference of two words and a carry, in plain arithmetic }
procedure RefStep(Op, a, b, c: Int64; var s, k: Int64);
var
  t: Int64;
begin
  c := Ord(c <> 0);
  if Op = 0 then
  begin
    s := a + b;
    t := Ord(ULt(s, a));
    s := s + c;
    k := t or Ord(ULt(s, c));
  end
  else
  begin
    s := a - b;
    t := Ord(ULt(a, b));
    k := t or Ord(ULt(s, c));
    s := s - c;
  end;
end;

procedure Judge(Op, WhichY, Cie: Int64);
var
  i, s, k: Int64;
  Z: W4;
  bad1: Boolean;
begin
  k := Cie;
  for i := 0 to 3 do
  begin
    case WhichY of
      0: RefStep(Op, X[i], Y[i], k, s, k);
      1: RefStep(Op, X[i], KC[i], k, s, k);
      3: RefStep(Op, EX[i], EY[i], k, s, k);
    else
      RefStep(Op, X[i], X[i], k, s, k);
    end;
    Z[i] := s;
  end;
  bad1 := (Rc <> k);
  for i := 0 to 3 do
    if R[i] <> Z[i] then
      bad1 := True;
  if bad1 then
    Inc(Bad);
  Inc(Cases);
  for i := 0 to 3 do
    Fold(R[i]);
  Fold(Rc);
end;

procedure Step(Op: Int64; var r, c: Int64; a, b: Int64);
begin
  if Op = 0 then
    r := AddCarry(a, b, c, c)
  else
    r := SubBorrow(a, b, c, c);
end;
""" % (len(V), len(CI), len(V) - 1, len(CI) - 1))

# the forms, one procedure for the sum and one for the difference
for name, loc, body, refy, refci in FORMS:
    for op, fn in ((0, 'AddCarry'), (1, 'SubBorrow')):
        text = body.replace('FN0', str(op)).replace('FN', fn)
        # a call that leaves the carry flag set (a borrow on amd64, no carry on arm64 for
        # the difference) before the first word, so a carry in of 0 that
        # takes the flag as it finds it gives a wrong answer
        text = '  ' + POISON[op] + '\n' + text
        w("procedure F_%s_%d(ci: Int64);" % (name, op))
        if loc.startswith('RAW:'):
            w(loc[4:].replace('FN', fn))
        elif loc:
            w("var")
            for d in loc.split(';'):
                w("  %s;" % d.strip())
        w("begin")
        w(text)
        w("end;")
        w("")

# the other calls: a value in a condition, a value dropped, a call in a call,
# a constant first operand, a large second operand, a sum of one operand twice
w("""{ the calls whose value is used or dropped; each returns what it computed
  in R[0] and Rc, and a third word in R[1] }
procedure M_cond(Op, a, b, ci: Int64);
var
  c: Int64;
begin
  R[1] := 0;
  if Op = 0 then
  begin
    if AddCarry(a, b, ci, c) < 0 then
      R[1] := 1;
  end
  else if SubBorrow(a, b, ci, c) < 0 then
    R[1] := 1;
  R[0] := 0;
  Rc := c;
end;

procedure M_drop(Op, a, b, ci: Int64);
var
  c: Int64;
begin
  if Op = 0 then
    AddCarry(a, b, ci, c)
  else
    SubBorrow(a, b, ci, c);
  R[0] := 0;
  R[1] := 0;
  Rc := c;
end;

procedure M_nest(Op, a, b, ci: Int64);
var
  c1, c2: Int64;
begin
  if Op = 0 then
    R[0] := AddCarry(AddCarry(a, b, ci, c1), b, c1, c2)
  else
    R[0] := SubBorrow(SubBorrow(a, b, ci, c1), b, c1, c2);
  R[1] := c1;
  Rc := c2;
end;

procedure M_consta(Op, a, b, ci: Int64);
var
  c: Int64;
begin
  if Op = 0 then
    R[0] := AddCarry(-1, b, ci, c)
  else
    R[0] := SubBorrow(-1, b, ci, c);
  R[1] := 0;
  Rc := c;
end;

procedure M_bigb(Op, a, b, ci: Int64);
var
  c: Int64;
begin
  if Op = 0 then
    R[0] := AddCarry(a, $8000000000000000, ci, c)
  else
    R[0] := SubBorrow(a, $8000000000000000, ci, c);
  R[1] := 0;
  Rc := c;
end;

procedure M_big(Op, a, b, ci: Int64);
var
  c: Int64;
begin
  if Op = 0 then
    R[0] := AddCarry($FFFFFFFF00000000, $0123456789ABCDEF, ci, c)
  else
    R[0] := SubBorrow($FFFFFFFF00000000, $0123456789ABCDEF, ci, c);
  R[1] := 0;
  Rc := c;
end;

procedure M_mulhi(Op, a, b, ci: Int64);
var
  c: Int64;
begin
  if Op = 0 then
    R[0] := AddCarry(MulHi(a, b), a * b, ci, c)
  else
    R[0] := SubBorrow(MulHi(a, b), a * b, ci, c);
  R[1] := 0;
  Rc := c;
end;

procedure M_zero(Op, a, b, ci: Int64);
var
  c: Int64;
begin
  if Op = 0 then
  begin
    Pz := AddCarry(-1, -1, 0, Pc);
    R[0] := AddCarry(a, b, 0, c);
  end
  else
  begin
    Pz := SubBorrow(0, 1, 0, Pc);
    R[0] := SubBorrow(a, b, 0, c);
  end;
  R[1] := 0;
  Rc := c;
end;

procedure M_sumvar(Op, a, b, ci: Int64);
var
  c: Int64;
begin
  c := ci;
  if Op = 0 then
    R[0] := AddCarry(a, b, c, c)
  else
    R[0] := SubBorrow(a, b, c, c);
  R[1] := 0;
  Rc := c;
end;
""")
MISC = ['cond', 'drop', 'nest', 'consta', 'bigb', 'big', 'mulhi', 'sumvar', 'zero']

w("procedure RunOne(Idx, ci: Int64);")
w("begin")
w("  case Idx of")
idx = 0
names = []
for name, loc, body, refy, refci in FORMS:
    for op in (0, 1):
        names.append('%s %s' % (name, 'add' if op == 0 else 'sub'))
        w("    %d:" % idx)
        w("      begin")
        w("        F_%s_%d(ci);" % (name, op))
        w("        Judge(%d, %d, %s);" % (op, REFY[refy], REFCI[refci]))
        w("      end;")
        idx += 1
w("  end;")
w("end;")
w("")
w("""procedure Setup(a, b: Int64);
begin
  X[0] := a;
  X[1] := a xor b;
  X[2] := b;
  X[3] := a + b + 1;
  Y[0] := b;
  Y[1] := a;
  Y[2] := b xor 12345;
  Y[3] := a - 3;
end;

procedure Sweep(Idx: Int64; const Name: string);
var
  i, j, k: Int64;
begin
  Hh := $CBF29CE484222325;
  Bad := 0;
  Cases := 0;
  for i := 0 to NV - 1 do
    for j := 0 to NV - 1 do
      for k := 0 to NC - 1 do
      begin
        Setup(VA[i], VA[j]);
        RunOne(Idx, CIS[k]);
      end;
  WriteLn(Name, ' cases ', Cases, ' bad ', Bad, ' hash ', Hh);
end;

procedure MiscOne(Idx, Op, a, b, ci: Int64);
begin
  case Idx of""")
for i, m in enumerate(MISC):
    w("    %d: M_%s(Op, a, b, ci);" % (i, m))
w("""  end;
end;

procedure SweepMisc(Idx, Op: Int64; const Name: string);
var
  i, j, k: Int64;
begin
  Hh := $CBF29CE484222325;
  Cases := 0;
  for i := 0 to NV - 1 do
    for j := 0 to NV - 1 do
      for k := 0 to NC - 1 do
      begin
        MiscOne(Idx, Op, VA[i], VA[j], CIS[k]);
        Fold(R[0]);
        Fold(R[1]);
        Fold(Rc);
        Inc(Cases);
      end;
  WriteLn(Name, ' cases ', Cases, ' hash ', Hh);
end;

var
  f: Int64;
begin""")
for i, k in enumerate(KC):
    w("  KC[%d] := $%X;" % (i, k))
for i, (t, v) in enumerate(V):
    w("  VA[%d] := %s;" % (i, t))
for i, v in enumerate(CI):
    w("  CIS[%d] := %d;" % (i, v))
w("  for f := 0 to %d do" % (len(names) - 1))
w("    case f of")
for i, n in enumerate(names):
    w("      %d: Sweep(f, '%s');" % (i, n))
w("    end;")
for i, m in enumerate(MISC):
    for op in (0, 1):
        w("  SweepMisc(%d, %d, 'misc %s %s');" % (i, op, m, 'add' if op == 0 else 'sub'))
w("""end.

{ This file is part of paslang's tests.
  Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
  paslang is free software under the GNU General Public License,
  version 3 or (at your option) any later version; see the file
  COPYING. It comes with ABSOLUTELY NO WARRANTY. }
""")

# ----- the expected output
o = []
vals = [v for t, v in V]
for name, loc, body, refy, refci in FORMS:
    for op in (0, 1):
        h = SEED
        cases = 0
        for a in vals:
            for b in vals:
                x = limbs_x(a, b)
                y = limbs_y(a, b)
                for ci in CI:
                    yy = {'Y': y, 'K': KC, 'X': x}.get(refy)
                    xx = x
                    if refy == 'N':
                        xx = [x[0] & 0xFFFF, (-5 if x[1] >> 63 else 7) & MASK, x[2], x[0] & 0xFFFF]
                        yy = [y[0] & 0xFF, (-100 if y[1] >> 63 else 100) & MASK, y[0] & 0xFF, y[3]]
                    r, k = chain(op, xx, yy, ref_ci(refci, ci, x, y))
                    for v in r:
                        h = fold(h, v)
                    h = fold(h, k)
                    cases += 1
        o.append('%s %s cases %d bad 0 hash %d' % (name, 'add' if op == 0 else 'sub', cases, s64(h)))


def misc(name, op, a, b, ci):
    if name == 'cond':
        s, c = step(op, a, b, ci)
        return 0, 1 if s >> 63 else 0, c
    if name == 'drop':
        s, c = step(op, a, b, ci)
        return 0, 0, c
    if name == 'nest':
        s1, c1 = step(op, a, b, ci)
        s2, c2 = step(op, s1, b, c1)
        return s2, c1, c2
    if name == 'consta':
        s, c = step(op, MASK, b, ci)
        return s, 0, c
    if name == 'bigb':
        s, c = step(op, a, 1 << 63, ci)
        return s, 0, c
    if name == 'big':
        s, c = step(op, 0xFFFFFFFF00000000, 0x0123456789ABCDEF, ci)
        return s, 0, c
    if name == 'mulhi':
        hi = (a * b) >> 64
        s, c = step(op, hi, (a * b) & MASK, ci)
        return s, 0, c
    if name == 'sumvar':
        s, c = step(op, a, b, ci)
        return s, 0, c
    if name == 'zero':
        s, c = step(op, a, b, 0)
        return s, 0, c
    raise SystemExit(name)


for m in MISC:
    for op in (0, 1):
        h = SEED
        cases = 0
        for a in vals:
            for b in vals:
                for ci in CI:
                    r0, r1, c = misc(m, op, a, b, ci)
                    h = fold(fold(fold(h, r0), r1), c)
                    cases += 1
        o.append('misc %s %s cases %d hash %d' % (m, 'add' if op == 0 else 'sub', cases, s64(h)))

emit(OUT + '.paslang', "\n".join(P))
emit(OUT + '.out', "\n".join(o) + "\n")
