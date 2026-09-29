# Quad: IEEE binary128 in software (P103)

`Quad` is the widest real of paslang: IEEE 754 binary128, 16 bytes, a
113-bit significand (about 34 decimal digits) and a 15-bit exponent
(from about 6.5e-4966 for the smallest subnormal to 1.19e4932). Neither
amd64 nor arm64 has binary128 arithmetic in hardware, so paslang works
it out in software with integer instructions only. That gives the same
bits on both machines, which is the point: a program that computes in
`Quad` prints the same digits wherever it runs.

P103 closed with 1.0.115; later milestones touched `Quad` where the table
says. What exists, by version:

| Version | What |
|---|---|
| 1.0.113 | The core unit `pasquad` (the arithmetic) and the exact text of a binary128 in `pasfmt`, both checked against GCC's `__float128` |
| 1.0.114 | The type `Quad` in the compiler: variables, parameters, results, arrays, fields, maps, channels, arithmetic, comparisons, conversions, the functions that have a `Quad` form, `WriteLn`, literals, `Pi` |
| 1.0.115 | Constants folded in `Quad`, typed constants and defaults, DWARF, 16-byte alignment in records, a faster divide and root, the measured cost against `Double` and GCC; P103 closes |
| 1.0.118 | The bit words (`PopCount`, `IsBitSet`, `SetBit`, `GetBits`...) take a `Quad` as its 16 bytes (P105) |
| 1.0.122 | `pasquad` on the wide words (`MulHi`, `AddCarry`...): fast paths for two normal operands, `+` 253 → 69 cycles, `*` 468 → 61, `/` 626 → 201 (P106; below) |
| 1.0.130 | The rotation, shift and funnel words take a `Quad` whole, 128 bits (P108) |

## The value

A binary128 is two 64-bit words, exactly as it lies in memory on both
machines (little endian):

| Word | Bits |
|---|---|
| `Lo` (offset 0) | the low 64 bits of the 112-bit fraction |
| `Hi` (offset 8) | bit 63 the sign, bits 62–48 the exponent (bias 16383), bits 47–0 the top 48 bits of the fraction |

An exponent field of 0 is zero or a subnormal (no hidden bit, the
exponent of 1); 32767 is an infinity (fraction 0) or a NaN (bit 47 of
`Hi` set for a quiet one).

## The core unit `pasquad` (`src/lib/pasquad.paslang`)

Every routine takes the words of its operands by value and gives the
result's words through `out` parameters: `PasQAdd(ALo, AHi, BLo, BHi,
RLo, RHi)` is six integer registers, the most amd64 passes in registers.
The unit has no `Quad` type of its own, so any paslang compiles it, and
so does FPC (the bootstrap compiles the compiler, which folds `Quad`
constants with it, 1.0.115).

| Routine | What |
|---|---|
| `PasQAdd`, `PasQSub`, `PasQMul`, `PasQDiv` | the four operations |
| `PasQSqrt` | the square root (a negative operand gives the default NaN; the compiler stops the program before, as for `Double`) |
| `PasQCmp` | -1, 0, 1, or 2 when either is a NaN; -0 equals 0 |
| `PasQFromInt`, `PasQFromDouble` | exact |
| `PasQToDouble`, `PasQToSingle` | rounded once, straight from 113 bits (no double rounding through `Double`) |
| `PasQToInt(A, Mode, Ok)` | mode 0 `Trunc`, 1 `Round` (a tie to even), 2 `Floor`, 3 `Ceil`; `Ok` false for a NaN, an infinity or a value no `Integer` holds |
| `PasQInt` | toward zero, as a binary128 |

How it works:

- **128-bit integers in pairs of `Int64`.** paslang has no unsigned
  64-bit type (`QWord` is `Integer`), so an unsigned compare flips the
  sign bits (`ULt`), and `shr` is logical on `Integer`, as FPC's is.
  `Add128`, `Sub128`, `Shl128`, `Shr128` (the bits that fall off set a
  sticky flag), `Clz64`, and `Mul64`, a 64 × 64 → 128-bit product from
  four products of 32-bit halves.
- **`Unpack`** gives a class (zero, finite, infinite, NaN), the sign and
  a finite value as a 128-bit integer times a power of two, its top bit
  always at 112: a subnormal is normalized here, so every operation
  after it sees one shape.
- **`RoundPack`** is the only rounding: it takes any non-zero 128-bit
  integer, a power of two and a sticky flag, normalizes the integer to
  its top bit, keeps 113 bits (more shifted out below the smallest
  normal, for a subnormal result), rounds to the nearest with a tie to
  even, and packs by adding: the significand's hidden bit carries into
  the exponent field, so a rounding that carries to the next power of
  two, or from the largest subnormal to the smallest normal, needs no
  case of its own, and one past the largest finite value is the
  infinity's bits.
- **Add and subtract:** the larger magnitude first, both significands
  shifted up 14 bits, the smaller aligned down with the bits it loses
  jammed into its lowest bit, then one add or subtract and `RoundPack`.
  Fourteen bits below the rounding place keep a jammed sum or
  difference rounding exactly; an exact cancellation is +0.
- **Multiply:** the 226-bit product of two 113-bit significands from
  four `Mul64`, its top 128 bits to `RoundPack`, the rest sticky.
- **Divide:** Knuth's algorithm D in base 2^30 (1.0.115), so every
  product and every two-digit numerator stays below 2^63 in a signed
  `Int64`: the divisor in four digits, the top one normalized, the
  dividend in nine, five quotient digits (120 or 121 bits, enough to
  round), each one estimated from the top two digits and corrected at
  most twice, the remainder sticky. It replaced a restoring division, one
  bit a pass, that took 7,700 cycles.
- **Square root:** digit by digit, two bits of the radicand a pass, the
  exponent made even first; 114 or 115 root bits, the remainder sticky.
  The radicand is aligned at the top of two words once, so each pass
  takes its two bits with shifts by constants, and the 128-bit steps are
  written out in the loop (1.0.115: 11,250 cycles before, 1,690 now).
- **NaN:** an operation with a NaN operand gives that NaN made quiet (the
  first operand's when both are); an invalid one (∞ − ∞, 0 × ∞, 0 / 0,
  ∞ / ∞, the root of a negative) gives the default NaN, `Hi` =
  `$7FFF800000000000`, positive on both machines (x86's libgcc gives a
  negative one, arm64 a positive one: paslang picks one).

## The exact text (`src/lib/pasfmt.paslang`)

`PasParseQuad(S, Lo, Hi)` reads a decimal number as the nearest binary128,
rounded once from its digits: the digits as one big integer (`TBig`,
32-bit limbs), multiplied or divided by the power of ten exactly, 115
quotient bits and a sticky remainder, `RoundToQuad` (113 bits in two
words, subnormals, infinity past the largest). `PasFmtQuad(Lo, Hi, W, D)`
writes one with `D` decimals, the exact value rounded once, a tie to
even, as `PasFmtReal` does a `Double`: `ScanReal` (the reading of the
digits) and `FmtExact` (the writing) are shared by `Double`, `Single` and
`Quad`.

## The type (1.0.114)

`Quad` is builtin type id 14 (`TyQuad`), a kind of its own (`tykQuad`),
so no path written for `Double` or `Single` takes it by mistake: a rule
that does not know it refuses it at compile time. The `.pi` format went
to `PASLANGI10`, since every type after the builtins moved by one
(`PASLANGI13` since 1.0.137).

**Typing (pasparse).** `QuadOf(E)` is the one entry for a place that
wants a `Quad`, as `RStamp` is for the other reals: it takes an
operation of reals down to its leaves (so `q := d * d` multiplies two
Quads), reads a constant with no type from its digits with
`PasParseQuad` (a literal keeps its text; `Pi` carries 50 digits), and
widens an `Integer` (`rtq_i2q`), a `Double` (`rtq_d2q`) or a `Single`
(through `rt_s2d`). An operation of integers stays an `Integer`
operation and is widened after, as for a `Double`. `ValArg` calls it for
every context (an assignment, a value argument, `Result`, `Exit`,
`Send`) and refuses a `Quad` where a narrower real, an integer, a
`Boolean` or an enumeration goes. `ApplyOp` sends any operation with a
`Quad` side to `QuadBin` before the string and real rules: `+ - * /`
become `rtq_add`, `rtq_sub`, `rtq_mul`, `rtq_div`, and a comparison is
`rtq_cmp` (PasQCmp's -1, 0, 1 or 2) compared with a constant: `=` is
`cmp = 0`, `<>` `cmp <> 0`, `<` `cmp = -1`, `>` `cmp = 1`, `<=`
`cmp <= 0`, and `a >= b` is `cmp(b, a) <= 0`, so a NaN (2) answers
false to all but `<>`. Unary minus of a literal flips its sign at
compile time, else `rtq_neg`. `Inc` and `Dec` become an assignment of
`QuadBin`. `QuadGuard` refuses a `Quad` handed straight to any other
`rt_` routine (`sin has no Quad form: write Double(x) for it`): the
calculation set has no `Quad` forms beyond those above. It lets
`rt_rotm` and `rt_funnelm` through, the rotation words on any value
(1.0.130), and the bit words (`PopCount`, `IsBitSet`, `SetBit` and the
rest, 1.0.118) never meet it, since they see a `Quad` as its 16 bytes
of memory.

**The emitter.** Every Quad operation is a call node, so the register
pool and the loop registers never hold a value across it, as for any
call. `IsFat` includes `Quad`: a value is two words in `rax:rdx`
(`x0:x2`), stored and loaded as a string's two words are, passed by
address, returned in the two registers; neither word holds a pointer
(`GcMark` sets no bit), so a `Quad` costs the collector nothing.
`EmitQuadFn` emits each `rtq_` call: the operands' words in the first
four argument registers, the result's words through a 16-byte scratch
slot whose two addresses are the fifth and sixth argument, then back
into `rax:rdx`. `rtq_neg` and `rtq_abs` are one instruction on the sign
bit (`btcq`/`btrq`, `eor`/`and`). `rtq_sqrt` asks `PasQCmp` first and
calls `rt_sqrtneg` below 0; `rtq_toint` reads `PasQToInt`'s `Ok` and
calls `rt_realrange`: both stop at the caller's line. `rtq_min` and
`rtq_max` compare once and pick. `rtq_fmt` calls `PasFmtQuad`. The core
unit `pasquad` is given to the linker with every program, so a unit
that works in `Quad` inside needs nothing of the program that uses it;
since 1.1.1 only the routines a program reaches stay (26 KB of code
when all do, with the fast paths of 1.0.122).

**Tests.** `testdata/quad` covers every place a value goes and every
operation, and its `.out` is what the same program in C with
`__float128` prints; `quadmore` adds `Inc`, `Dec`, a map, a channel, a
class field and a unit whose interface has `Quad` (`units/quadu`);
`quadbad/` holds ten refusals with their messages; `fatal/qtrunc` and
`fatal/qsqrt` stop at their lines; the manual's `examples/quad`. All on
both machines.

## Constants, layout and debugging (1.0.115)

- **Constants folded in binary128.** The compiler links `pasquad` (FPC's
  build of it gives the same bits). `QFold` works an expression of
  constants out in binary128 with the routines the program runs: a
  literal from its digits, an integer exactly, a named constant from its
  own binary128 value, `+ - * /` and unary minus. `ParseConstValue` keeps
  that value beside the `Double` one for every real constant, a node
  carries it (`Flags` bit 1, `QLo` and `Hi`), and `QuadOf` takes it, so a
  `Quad` gets `1 / 3` to 113 bits while a `Double` still gets 53. A
  unit's `.pi` writes `CONST name bits r lo hi`; an older reader stops at
  `r`, so the format stays `PASLANGI10`.
- **Typed constants and defaults.** `ParseTypedInit` folds a `Quad`
  constant into the variable's 16 bytes. A `Quad` default is kept as its
  16 bytes in the parameter's default text, which the `.pi` writes in
  hex as it does a string's. (A `Single` constant and default now round
  once from their digits too; they rounded the `Double`.)
- **Layout.** `AlignOf(Quad)` is 16, as C's `_Float128`: a record's `Quad`
  field lies on 16 and the record rounds to it. A global that holds a
  `Quad` gets `.align 16`. A frame slot or a heap block with a header may
  hold one on 8, which only a hardware binary128 load would mind.
- **Debugging.** DWARF gives a `Quad` local a 16-byte float named
  `_Float128`: gdb takes a 16-byte float as x87's 80-bit long double on
  amd64 unless it has that name. `make check` stops gdb in
  `testdata/dwarfquad` and reads 1/3 to 36 digits.
- **Linking.** Every compilation links `pasquad` without importing its
  names; a `uses pasquad` after that reads them (`units/quadimpl`).

## Fast paths (1.0.122)

With the words of P106 (`MulHi`, `AddCarry`, `SubBorrow`,
`LeadingZeros`, `DivMod128`), taken behind `{$ifdef PASLANG}` so FPC
still builds the unit its old way, `pasquad` works two normal operands
with no call: the significands 10 bits up, the bits that fall off one
jammed into its lowest bit (an inexact result is odd there, so it is
never a false tie), one step of normalization, round to nearest even at
bit 10, pack. A sum or a difference goes so unless the exponents are one
apart or less with opposite signs (the result may cancel) or the result
may be subnormal; a product is four `MulHi` and a chain of carries; a
quotient on amd64 is Knuth's algorithm D in base 2^64, each digit
estimated by `divq` and corrected by `MulHi` (arm64 keeps the base-2^30
one: it has no 128-by-64 division). Zeros, subnormals, infinities and
NaNs go the general way, whose helpers use the same words. Checked on
120,000 random pairs of every kind against an exact oracle (Python
fractions rounded to nearest even) with no bit different, the same bits
on both machines; `testdata/quadfast` keeps 2,000 of them.

## What it costs

Measured with the processor's cycle counters (`perf_event_open`) on the
development machine (amd64), cycles per
operation from the difference of two pass counts, the loop included,
against GCC 15's `__float128` (libgcc's soft-fp, `-O2`); 1.0.122 is the
least of three runs on a machine that was running stress chains too:

| Operation | 1.0.115 | 1.0.122 | GCC `__float128` | 1.0.122 / GCC |
|---|---|---|---|---|
| `+` | 253 | 69 | 42 | 1.6 |
| `*` | 468 | 61 | 48 | 1.3 |
| `/` | 626 | 201 | 77 | 2.6 |
| `Sqrt` | 1,690 | 1,327 | 331 | 4 |

A `Double` operation in the same loop costs a few cycles, so a `Quad`
one is 20 to 60 times a `Double`'s for `+ - * /` and about 150 for
`Sqrt`. A loop of a million quotients and sums plus 200,000 roots took
13.8 million cycles in `Double`, 2,018 million in `Quad` and 384 million
with GCC's `__float128`, with the same digits in the last two. GCC's
soft-fp is C compiled with 128-bit integers, a 64 × 64 → 128-bit multiply
and add-with-carry; 1.0.115's `pasquad` was Pascal without them, where
each 128-bit step was two or four words and the calls passed their
results through memory. P106 gave the language those words (1.0.121)
and `pasquad` its fast paths on them (1.0.122). The square root still
goes digit by digit through the general helpers.

## How it is checked

Against GCC's `__float128` (libgcc's soft-fp, IEEE binary128, nearest
even) and libquadmath (`quadmath_snprintf`, `strtoflt128`), which are
correctly rounded. A program in C and the same program in paslang draw
the same operands from the same splitmix64 and print every result in
hex; `testdata/quadcore.out` and `testdata/quadfmt.out` are what the C
program printed, and `make check` compares the paslang program's output
with them on both machines. During the build of 1.0.113 the comparison
ran on 200,000 random cases × 17 results each (every operation,
comparison, rounding and conversion), 30,000 of them under qemu on
arm64, the unit compiled by FPC too, and on 3,000 values written with
five precisions and 3,000 decimal strings read: no bit differed.

The drawing covers every exponent, the neighbourhood of 1, subnormals,
the top of the range, the smallest normals, integers, and pairs of
nearly equal values (cancellation); 18 fixed cases cover the ties to
even, overflow, the smallest subnormal halved, 2^63 and -2^63 into an
`Integer`, 2.5 and 3.5 rounded, exact cancellation, the invalid
operations and NaN operands.

---

Copyright (C) 2026 Germán Luis Aracil Boned.

Permission is granted to copy, distribute and/or modify this document
under the terms of the GNU Free Documentation License, Version 1.3 or
any later version published by the Free Software Foundation; with no
Invariant Sections, no Front-Cover Texts, and no Back-Cover Texts. A
copy of the license is included in the file COPYING.DOC.
