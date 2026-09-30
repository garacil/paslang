# The paslang programmer's manual

paslang is Pascal with the good parts of Go underneath: 64-bit integers,
UTF-8 strings, routines that park instead of blocking a thread, channels,
a hash map in the language, and the sync types of a modern runtime. The
compiler, `paslangc`, emits native code for GNU/Linux on amd64 and arm64.
A program does not link libc, and a garbage collector gives back the
memory it no longer reaches.

Every program in this manual lives in `examples/` with the output it must
print beside it. `make check` compiles and runs them all, so what you read
here is what the compiler does today. Where a section says "prints", the
text that follows is the exact output.

Contents

1. Getting started
2. Programs and units
3. Values and types
4. Control flow
5. Routines
6. Records, pointers, arrays and slices
7. Classes and interfaces
8. Generics
9. Errors: raise, try, finally
10. Routines that run concurrently: pas, channels, select
11. Maps
12. Sync: mutex, rwmutex, waitgroup, cond, once
13. Strings and hashing
14. Reals and the calculation set
15. The core library and pasnet
16. The clock, chance and order
17. The runtime model
18. Limits and differences from other Pascals
19. Reserved words
20. Command reference

## 1. Getting started

Build the compiler once from the source tree:

```
make            # builds bin/paslangc, bin/pasdbg and the units for both machines
make install    # optional: puts paslangc, pasdbg and lib/paslang under /usr/local
```

The smallest program is a name, a body and one line of output
(`examples/hello.paslang`):

```pascal
{ The smallest program: a name, a body, one line of output.
  Compile and run:  paslangc -o hello examples/hello.paslang && ./hello }
program hello;

begin
  WriteLn('hello world');
end.
```

```
paslangc -o hello examples/hello.paslang
./hello
```

prints

```
hello world
```

A source file ends in `.paslang` and is one program, one unit, or one
package. Comments are `{ braces }` and `// to the end of the line`.
Identifiers and keywords are case-insensitive, as in every Pascal.

## 2. Programs and units

A program is `program Name;` then declarations, then `begin ... end.`.
A unit has an `interface` that programs see, an `implementation`, and
optional `initialization` and `finalization` parts. `uses` names the
units a program or unit needs. The compiler reads the unit's compiled
interface, a `.pi` file, and links its `.o`; it never reparses the unit
source. The constants, types, routines and variables of the interface
are the user's; a variable there is the unit's one copy, which the
program reads and writes. A global of the program with the name of one
in a unit's implementation is another variable.

A unit is how a program of your own is split into parts. What the
language itself provides (strings, maps, trees, heaps, the store, the
hash words, the rotations, the sync types, the calculation set, the
collector, `TObject`) is in the language and needs no `uses`: it is
written as eight core units that every program links without naming
them (§15).
The unit below is a programmer's own:

`examples/units/geometry.paslang`:

```pascal
{ A unit: an interface that programs use, an implementation, and an
  initialization part that runs once before the program body. }
unit geometry;

interface

type
  TPoint = record
    X, Y: Integer;
  end;

function MakePoint(X, Y: Integer): TPoint;
function Manhattan(const A, B: TPoint): Integer;

implementation

function MakePoint(X, Y: Integer): TPoint;
var
  p: TPoint;
begin
  p.X := X;
  p.Y := Y;
  Result := p;
end;

function Manhattan(const A, B: TPoint): Integer;
begin
  Result := Abs(A.X - B.X) + Abs(A.Y - B.Y);
end;

initialization
  WriteLn('geometry ready');
end.
```

`examples/units/usegeom.paslang`:

```pascal
{ Uses the geometry unit. The compiler reads geometry.pi, the compiled
  interface, and links geometry.o; it never reparses the unit source.
  Build: paslangc examples/units/geometry.paslang    (writes build/geometry.pi and .o)
         paslangc -Fu build -o usegeom examples/units/usegeom.paslang }
program usegeom;

uses geometry;

var
  a, b: TPoint;

begin
  a := MakePoint(1, 2);
  b := MakePoint(4, 6);
  WriteLn(Manhattan(a, b));          { 7 }
end.
```

prints

```
geometry ready
7
```

A unit compiled without `-o` goes to `build/<name>.pi` and
`build/<name>.o`, or under `build/a64/` when the target is arm64.
`-Fu <dir>` adds a directory of compiled units. The compiler looks for
a unit's `.pi` in each `-Fu` directory in the order given, then in
`PASLANG_LIB`, in `lib/paslang` beside the directory of the compiler's
`bin` (`/usr/local/lib/paslang` for `/usr/local/bin/paslangc`;
`lib/paslang/aarch64` when the target is arm64), in `build/a64` (arm64
only), in `build`, in
`.`, and beside the source file, and reads the first one it finds.

Eight units are part of the language and need no `uses`; every program
links them. `pasobject` (`TObject`, the root of every class),
`pasroutines` (the sync types), `pasfmt` (what `Write`
prints), `pashash` (the hash words) and `pastree` (the ordered tree,
the heap and the store) also put their names in every program;
`pasmap` (the hash map), `pasheap` (the heap and the collector) and
`pasquad` (`Quad`) are only linked. Of each unit only the routines the
program reaches stay in it (§20). Section 15 describes them.

### Packages

A package compiles several units in one go and installs them. Its file
names the package and the units it contains, and nothing else:

```pascal
package shapes;

contains
  geom, draw;

end.
```

`paslangc -install lib shapes.paslang` compiles each unit listed from
its source beside the package file (`geom.paslang`, `draw.paslang`), in
the order given, into `build/` (`build/a64/` for arm64), copies its `.pi`
and `.o` into `lib`, and writes `lib/shapes.pkg`, a few lines of text
naming the package and its units. A unit may use one listed before it.
A program then uses them as any other units: `paslangc -Fu lib -o app
app.paslang`. A package compiled without `-install` stops with `package
requires -install dir`, and a listed unit without its source with
`missing package unit ...`.

### Conditional compilation

`{$ifdef NAME}`, `{$ifndef NAME}`, `{$else}` and `{$endif}` keep or drop
the code between them, nested as deep as needed, and `{$define NAME}`
and `{$undef NAME}` set a name for the rest of the file. paslang
defines `PASLANG`, `LINUX`, `UNIX` and `CPU64`, and the processor under
the names Free Pascal uses: `CPUX86_64` and `CPUAMD64` on amd64,
`CPUAARCH64` on arm64. So one source builds with either compiler and on
either machine:

```
{$ifdef PASLANG}
  hi := MulHi(a, b);             { one instruction }
{$else}
  hi := MulHiPortable(a, b);     { what FPC builds }
{$endif}
```

Any other directive (`{$mode objfpc}`, `{$H+}`) is read as a comment.

## 3. Values and types

A `const` section names a value of any of these kinds: `N = 3`,
`Ratio = -1.5`, `Name = 'paslang'`, `Nl = #10` (a `Char`), `Yes = True`,
and `Alias = Name` for another constant. A unit exports the constants of
its interface and keeps those of its implementation. A constant is any
expression of constants: `Size = N * 4 + 1`, `Mask = not 0 shr 1`,
`Greeting = Name + '!'`, `Half = 1 / 2`, `Last = Chr(Ord('A') + 25)`,
`Words = SizeOf(Integer) * 8`, with `Ord`, `Chr`, `Succ`, `Pred`, `Abs`,
`Sqr`, `Odd` and the `Length` of a string. The compiler works it out; an
integer that leaves the 64-bit range, a division by zero and a `Chr`
beyond 255 are compile errors. An array bound, a subrange, a `case`
label and a default value take the same expressions:
`array[0..N - 1] of Integer`.

A typed constant, `Limit: Integer = 10`, is a variable that starts with
its value, as in every Pascal: the program may change it. An array
takes `(a, b, c)`, an `array of Char` a string of its length, a record
`(X: 1; Y: 2)` (a field left out is zero), a set `[1, 3..5]`, and a
pointer, class or routine `nil`. One declared in a routine is a static
variable: it keeps its value from call to call.

`examples/values.paslang`:

```pascal
{ The basic values: 64-bit integers, UTF-8 strings, characters,
  booleans and binary64 reals, with the operators that belong to each. }
program values;

var
  i, j: Integer;          { 64-bit, signed; LongInt and Int64 are the same }
  s: string;              { UTF-8 bytes, any length }
  c: Char;                { one byte }
  b: Boolean;
  r: Real;                { IEEE binary64, as Double; Single is binary32 }

begin
  i := 9223372036854775807;         { the largest Integer }
  WriteLn(i);
  j := 7;
  WriteLn(j div 2, ' ', j mod 2);   { integer quotient and remainder: 3 1 }
  WriteLn(j / 2);                   { / is always real division: 3.5 }
  WriteLn(j shl 3, ' ', j shr 1, ' ', j and 3, ' ', j or 8, ' ', j xor 1);
  s := 'año';                       { three characters, four bytes }
  WriteLn(Length(s));               { 4: Length counts bytes }
  c := s[1];                        { s[i] is a byte, 1-based }
  WriteLn(c);                       { a Char prints as the character: a }
  WriteLn(Ord(c));                  { 97, the code of a }
  s := s + ' nuevo';                { + concatenates }
  WriteLn(s);
  WriteLn(Copy(s, 6, 5));           { Copy(s, from, count), 1-based: nuevo }
  b := (j > 3) and (s <> '');       { and, or, not on booleans short-circuit }
  WriteLn(b);                       { booleans print as 1 or 0 }
  r := 1.5 + j;                     { an integer promotes to real }
  WriteLn(r);                       { 8.5 }
  WriteLn(Round(2.5), ' ', Trunc(-2.7), ' ', Sqrt(16));   { 2 -2 4.0 }
end.
```

prints

```
9223372036854775807
3 1
3.5
56 3 3 15 6
4
a
97
año nuevo
nuevo
1
8.5
2 -2 4.0
```

The sizes are fixed and the same on both targets:

| Type | Size | Notes |
|------|------|-------|
| `Integer`, `LongInt`, `Int64`, `SizeInt`, `NativeInt`, `PtrInt`, `Cardinal`, `QWord`, `UInt64`, `Rune` | 8 | one signed 64-bit integer under every name |
| `Byte` `UInt8` · `Int8` `ShortInt` · `Word` `UInt16` · `Int16` `SmallInt` · `UInt32` `LongWord` `DWord` · `Int32` | 1, 1, 2, 2, 4, 4 | six types (the names between dots are one), whose values keep their width: `Byte` 0..255, `Int8` −128..127, `Word` 0..65535, `Int16` −32768..32767, `UInt32` 0..4294967295, `Int32` −2147483648..2147483647; 1, 2 or 4 bytes in memory (a local or a global keeps a word's slot); `High(T)` and `Low(T)` are constants of the type; the names are reserved words (§19) |
| `Boolean` | 8 | `False` is 0, `True` is 1; only a Boolean goes into one, `Boolean(x)` turns a number or a pointer into one (§3) |
| an enumeration, a subrange | 8 | an integer; a subrange's values are its host's: `1..10` integers, `'0'..'9'` characters, `Mon..Fri` the enumeration's members |
| `Char`, `AnsiChar` | 1 | a byte, its own type: `Ord(c)` is its code |
| `string` | 16 | pointer and byte length; no 255 cap, no trailing zero; the characters are copied on the first write after they are shared |
| `Real`, `Double` | 8 | one IEEE binary64 |
| `Single` | 4 | IEEE binary32, worked out in 32 bits; with a Double it widens, and a Double becomes a Single only through `Single(x)` |
| `Quad` | 16 | IEEE binary128 in software, the same bits on both machines; everything widens to it, and it becomes a Double only through `Double(x)` (§14) |
| `^T`, a class, a map, a chan | 8 | one machine word; `nil` is zero |
| `array of T` | 24 | a slice: pointer, length, capacity |
| `array[a..b] of T` | (b-a+1) × SizeOf(T) | fixed, no header |
| `set of T` | 8 or 32 | a bitset: one word for elements 0..63, 32 bytes up to 255 |
| `procedure of object`, `function ... of object` | 16 | code pointer and Self |
| a routine value, `procedure(...)`, `function(...): T` | 16 | code pointer and environment (§5) |
| an interface value | 16 | object and method table |

The type that is asked for decides the width of integer work: the
variable assigned, a value parameter, `Result`, a `for` counter, a
conversion `T(e)`. With `b: Byte = 255`, `i := b + 1` and `Integer(b + 1)`
are 256 while `b := b + 1` is 0. With no such context an integer
expression works in its widest operand's type (a constant with no type
adapts to the other operand), so `WriteLn(b + 1)` prints 0 and
`WriteLn(b + 1 + i)` works in `Integer`. A signed and an unsigned type
join in the signed type that holds both: `Byte` and `Int8` in `Int16`,
`Word` and `Int16` in `Int32`, `UInt32` and `Int32` in `Integer`.
Widening is implicit; narrowing needs a conversion, which keeps the low
bits (`Byte(300)` of a variable is 44), so `b := i` and `b := b + i` do
not compile, and an `Int8` into a `Word` needs `Word(x)`, since -1
is no `Word`. A constant that does not fit is a compile error:
`b := 300`, `Byte(300)`, `Byte(-1)`, a case label, a typed constant, a
default value, an argument, `WriteLn(b + 300)`. `shr` keeps the sign in
`Int8`, `Int16` and `Int32`; `div` and `mod` wrap like the rest; `Inc`
and `Dec` wrap; a `for` with a narrow counter stops on its limit, so
`for b := 0 to 255` ends. A `var` parameter takes its own type.

`examples/narrow.paslang`:

```pascal
{ Integers of every width: the type that is asked for decides the width
  of the work, a narrow value wraps at its width, widening is free and
  narrowing is written. }
program narrow;

type
  TPacked = record
    B: Byte;
    W: Word;
    I: Int32;
  end;

var
  b: Byte;
  s8: Int8;
  w: Word;
  i: Integer;

begin
  b := 255;
  i := b + 1;                       { the target is an Integer: 256 }
  WriteLn(i, ' ', Integer(b + 1));  { 256 256 }
  b := b + 1;                       { the target is a Byte: it wraps to 0 }
  WriteLn(b);                       { 0 }
  b := 200;
  WriteLn(b + 100);                 { no target: Byte work, 44 }
  s8 := -128;
  WriteLn(s8 - 1, ' ', s8 shr 1);   { Int8 wraps to 127; shr keeps the sign: -64 }
  w := Word(s8);                    { an Int8 into a Word needs Word(x) }
  WriteLn(w);                       { 65408 }
  WriteLn(b + s8);                  { a Byte and an Int8 join in Int16: 72 }
  i := 300;
  b := Byte(i);                     { narrowing keeps the low bits: 44 }
  WriteLn(b, ' ', High(Byte), ' ', Low(Int8), ' ', High(Word));
  WriteLn(SizeOf(Byte), ' ', SizeOf(Word), ' ', SizeOf(Int32), ' ', SizeOf(TPacked));
  i := 0;
  for b := 250 to 255 do            { a narrow counter stops on its limit }
    i := i + b;
  WriteLn(i, ' ', b);               { 1515 255 }
end.
```

prints

```
256 256
0
44
127 -64
65408
72
44 255 -128 65535
1 2 4 8
1515 255
```

A string is a value, as an integer is: `t := s` then `s[1] := 'j'`
leaves `t` as it was. Assigning a string, passing it or storing it in a
record, an array or a map shares its characters, and the first write
through any holder copies them (copy on write); writing into a literal
writes into a copy. A pointer taken with `@s[i]` points into characters
of `s` alone.

`WriteLn` and `Write` print integers, reals, strings, booleans (as 1
or 0) and characters. A `Char` prints as the character, its byte;
`Ord(c)` prints the code. A `Rune` is an integer and prints as one.

`/` always divides as reals, even `10 / 4`. `div` and `mod` stay integer.
`+ - *` are real when either side is real, and a comparison promotes an
integer side. An integer where a real is expected becomes that real: in
an assignment, an argument for a real parameter, `Result`, `Exit(n)` and
`Send` on a channel of reals. A `var` parameter takes a variable of its
own type. `Round` is round-to-nearest, ties to even. `WriteLn` of a
real prints up to six decimals, always at least one: `4.0`, `2.5`. It is
the exact value rounded once at the sixth decimal, a tie to the even
digit, at any size: `1e20` is `100000000000000000000.0`, `2/3` is
`0.666667`, `1/0` is `+Inf`, `-1/0` is `-Inf`, `0/0` is `NaN`. A real
literal is the nearest double to what it says, subnormals too.
A real where an integer, a `Boolean` or an enumeration goes is a compile
error that says to write `Trunc` or `Round`, and `Ord` of a real is one
too, as is a conversion like `Int64(d)` or `Byte(d)`; `d as UInt64` sees
its bits (§3, views). `Trunc`, `Round`, `Floor` and `Ceil` of a NaN, an infinity or a
real out of `Integer`'s range stop the program with
`real out of integer range at line N`, the same on both machines
(-2^63 itself converts). `Single` and `Quad` are in §14.

An enumeration and a subrange are integers. A subrange is of a host
type, the type of its bounds, and its values are the host's: `TDigit =
'0'..'9'` is a subrange of `Char`, so a `TDigit` prints as a character,
joins a string, compares with a `Char` and takes a `'7'`; `TWork =
Mon..Fri` is a subrange of the enumeration, whose members it takes and
into which it goes, and `set of TWork` is a set of that enumeration's
kind (`[Red]` of another is refused). A constant out of the subrange is
a compile error (`constant #120 does not fit TDigit`).
`Ord(x)` reads any ordinal;
`Succ(x)` and `Pred(x)` are the next and the previous value, of the same
type. `Chr(n)` is the `Char` whose code is `n`: a constant past 255 is a
compile error, and a value that varies keeps its low byte (`Chr(i)` of
an `i` of 300 is `Chr(44)`). `not` of a Boolean negates it and `not` of
an integer flips its bits: `not 5` is -6.
`Integer(p)` reads a pointer, class, map, chan or ordinal as a number;
`Pointer(n)` is the way back. `@x` is the address of `x`, and `%x` is
the same, a second spelling. Pointers, views over memory and how they
are checked are in §6.
`Default(T)` is the zero value of any type `T`; `Default(Integer)`,
`Default(string)` and `Default(Boolean)` too since 1.0.136 (the compile
stopped on them with `Default type`).
`SizeOf(T)` and `SizeOf(expr)` give sizes.

A set, `set of T`, is a bitset for a `T` whose values lie in 0..255:
`Char`, `Byte`, a `Boolean`, an enumeration or a subrange. Up to
element 63 it is one word; past it, 32 bytes (`set of Char`, `set of
Byte`). `[1, 3..5]` is a set and `[]` the empty one; `+` is the union,
`*` the intersection, `-` the difference, `=` and `<>` compare, `<=`
and `>=` test a subset and a superset, `x in s` tests, `Include(s, x)`
and `Exclude(s, x)` change the variable, and `for x in s do` walks the
members from the lowest:

```pascal
type
  TChars = set of Char;
const
  Blanks: TChars = [' ', #9];
var
  ident: TChars;
  c: Char;
begin
  ident := ['a'..'z', 'A'..'Z', '0'..'9', '_'];
  Include(ident, '$');
  if not ('-' in ident) and (Blanks * ident = []) then
    for c in ident - ['a'..'z', 'A'..'Z'] do
      Write(c);                     { $0123456789_ }
  WriteLn;
end.
```

A list takes its type from its elements and from where it goes; sets
of one kind and other ranges meet in the set that holds both, and a
set goes into another of its kind keeping what that one can hold, as
Free Pascal does. An element out of the set's range is in no set (`x
in s` is false); a list's element known only at run time outside the
set's range stops the program. A list of strings or reals is a list,
not a set: it goes where a slice or an open array goes, and `for s in
['ab', 'cd'] do` walks it in its order. A set goes only where a set
goes: `i := [1, 2]` is a compile error (1.0.136; it stored the
bitmask), and `Write` does not print one. On a processor with AVX2 an
operation on two sets of 32 bytes is one instruction (TYPES.md, Sets).

Every local variable starts as zero: an `Integer` is 0, a `string` is
empty, a slice and a map are `nil`, a record has zero fields.

### Operators, bits and compound assignment

The operators bind in six levels, the tightest first:

| Level | Operators |
|---|---|
| 1 | unary `+`, `-`, `not`, `@` (also written `%`) |
| 2 | `*` `/` `div` `mod` `shl` `shr` `sar` `rol` `ror` |
| 3 | `+` `-` |
| 4 | `=` `<>` `<` `<=` `>` `>=` `in` `is` `as` |
| 5 | `and` `nand` `andnot` |
| 6 | `or` `xor` `nor` `xnor` |

A comparison binds before `and` and `or`, as in C and Go (in other
Pascals it binds after them): `(j > 3) and (s <> '')` needs no
parentheses, and `x and 4 = 4` reads `x and (4 = 4)`. That mixes a
Boolean with an integer, so it is a compile error that says to write
`(x and 4) = 4`.

`and`, `or`, `xor` and `not` work on two Booleans (a Boolean `and` and
`or` short-circuit) or on the bits of two integers. The logic family
adds four words, on Booleans and integers alike:

| Operator | Is | `12 op 10` |
|---|---|---|
| `a nand b` | `not (a and b)` | -9 |
| `a nor b` | `not (a or b)` | -15 |
| `a xnor b` | `not (a xor b)` | -7 |
| `a andnot b` | `a and not b`: the bits of `a` that `b` clears | 4 |

`sar`, `rol` and `ror` complete the shifts:

- `a shl n` moves the bits left; zeros come in.
- `a shr n` moves them right: zeros come in, except in `Int8`, `Int16`
  and `Int32`, where copies of the sign do.
- `a sar n` moves them right with copies of the top bit of `a`'s width
  coming in, whatever its sign: for `b: Byte = $C8`, `b sar 1` is `$E4`
  (228).
- `a rol n` and `a ror n` rotate within the width: for `b = $C8`,
  `b rol 1` is `$91` (145) and `b ror 1` is `$64` (100).

The count is taken as the machines take it, the same on both: `shl`,
`shr` and `sar` count modulo 64, so `b sar 9` of a `Byte` is all sign
(255) and `i sar 64` is `i`; `rol` and `ror` count modulo the width, so
`b rol 9` is `b rol 1` and `i rol -1` is `i ror 1`. The width is the
indicated type's, as for `+` (§3): `i := b rol 1` rotates in `Integer`
(400), `Byte(b rol 1)` rotates the byte (145).

These seven words are reserved (1.0.131): no variable, field or routine
takes their names (§19).
Each instruction is one machine instruction on a register (`rolb`,
`rorw`, `sarq`; `ror`, `asr` on arm64); a byte or a halfword rotation
on arm64 is two shifts and an `orr`.

Every binary operator has a compound assignment, `x op= e`, which is
`x := x op e` with the same rules: `i += 5`, `s += 'lang'`, `d /= 4`,
`q *= 3`, `m xor= k`, `x rol= 3`, `mask andnot= bit`, `i div= 2`. So
`b += i` for a `Byte` `b` and an `Integer` `i` is refused as
`b := b + i` is. The place must be a variable whose address calls no
routine (`a[F] += 1` is refused: F would run twice or its place be
guessed), and the whole is a statement, never an expression.

The rotations are the tool for anything circular: a byte swap (`w rol
8` on a `Word`, `u rol 16` swaps the halves of a `UInt32`), a pattern
that walks round a register, and the mixing step of every hash of the
last twenty years (MurmurHash3, xxHash, SipHash and SHA-2 are built on
`rol`, `ror` and `xor`). `sar` is the division by a power of two that
rounds down, where `div` rounds towards zero: `-41 sar 3` is -6 and
`-41 div 8` is -5.

`examples/rotations.paslang`:

```pascal
{ Rotations in a register: rol, ror and sar on each width, the count
  rules, the width by context, a byte swap, a pattern that walks round,
  and a hash mixed by rotation: MurmurHash3 written by hand equals the
  word Murmur3. }
program rotations;

var
  b: Byte;
  w: Word;
  u, h: UInt32;
  i, k: Integer;
  t: string;

function Bits8(x: Byte): string;   { the byte as eight characters, bit 7 first }
var
  j: Integer;
begin
  Result := '';
  for j := 7 downto 0 do
    if IsBitSet(x, j) then
      Result += '#'
    else
      Result += '.';
end;

begin
  b := $C8;                                                     { 1100 1000 }
  WriteLn(b rol 1, ' ', b ror 1, ' ', b sar 1, ' ', b shr 1);   { 145 100 228 100 }
  WriteLn(b rol 9, ' ', b rol -1, ' ', RotateLeft(b), ' ', RotateRight(b, 12));   { 145 100 145 140 }
  i := b rol 1;                                                 { turned as an Integer }
  WriteLn(i, ' ', Byte(b rol 1), ' ', Integer(b) rol 1);        { 400 145 400 }
  w := $1234;
  WriteLn(w rol 8, ' ', ByteSwap(w), ' ', w rol 8 = ByteSwap(w));   { 13330 13330 1 }
  u := $80000001;
  WriteLn(u rol 1, ' ', u ror 1, ' ', u sar 1, ' ', u shr 1);   { 3 3221225472 3221225472 1073741824 }
  WriteLn(-41 sar 3, ' ', -41 div 8, ' ', -41 shr 61);          { -6 -5 7: sar rounds down, div towards 0 }
  b := 3;                                                       { two lit bits walk round the byte }
  for k := 1 to 8 do
  begin
    WriteLn(Bits8(b));
    b rol= 1;
  end;
  { MurmurHash3 (x86, 32 bits) of a text of whole 4-byte blocks, by hand }
  t := 'The quick brown fox jumps over the lazy dog!';
  h := 0;
  i := 1;
  while i + 3 <= Length(t) do
  begin
    u := UInt32(Ord(t[i])) or (UInt32(Ord(t[i + 1])) shl 8) or
      (UInt32(Ord(t[i + 2])) shl 16) or (UInt32(Ord(t[i + 3])) shl 24);
    u *= $cc9e2d51;
    u rol= 15;
    u *= $1b873593;
    h := h xor u;
    h rol= 13;
    h := h * 5 + $e6546b64;
    i += 4;
  end;
  h := h xor UInt32(Length(t));
  h := h xor (h shr 16);
  h *= $85ebca6b;
  h := h xor (h shr 13);
  h *= $c2b2ae35;
  h := h xor (h shr 16);
  WriteLn(h, ' ', Murmur3(t));                                  { 2991849531 2991849531 }
end.
```

prints

```
145 100 228 100
145 100 145 140
400 145 400
13330 13330 1
3 3221225472 3221225472 1073741824
-6 -5 7
......##
.....##.
....##..
...##...
..##....
.##.....
##......
#......#
2991849531 2991849531
```

Every line of that program gives the same on arm64: a rotation is the
same instruction, or on a byte two shifts and an `orr`, and the count
rules are the language's, not the machine's. The Murmur loop is the
reference algorithm line for line, `k rol= 15` and `h rol= 13` being
its two rotations; `Murmur3` (§13) is the same code in the core unit,
so the two numbers agree.

A `Boolean` in integer arithmetic is its `Ord`, as a `Char` is its
code: `t + 1` is 2 for a true `t`, `-t` is -1. Only a Boolean goes
into a Boolean: `t := i` and `t := t + t` are compile errors.
`Boolean(x)` turns an integer, a `Char`, an enumeration or a pointer
into one: it is `x <> 0` (`x <> nil`), and `Boolean(5)` is a constant
`True`. `if`, `while` and `until` take an integer as that test
directly: `while n do` runs while `n` is not zero. `Ord(b)`,
`Integer(b)` and `Byte(b)` give 0 or 1 for any Boolean expression.

A `string` takes `+`, which joins it with a string or a `Char`, the
comparisons, and the logic words byte by byte with a string of its
length (logic on whole blocks, below). Any other operator on a string,
any arithmetic operator on an array, an object, a map, a channel or a
routine value, or on a record that does not declare it (below), and
any logic operator on a slice, an object, a map, a channel or a
routine value, is a compile error at its line and column: they compiled before and worked
on the hidden address (`s + 1` dropped the 1, `-s` stopped the program,
`a + a` added two addresses).

A record takes the operators declared for it at the top level of a
program or a unit: `+ - * / div mod` and `= <> < <= > >=`, each a
function of two operands with a body:

```
operator + (A, B: TPoint): TPoint;
begin
  Result.X := A.X + B.X;
  Result.Y := A.Y + B.Y;
end;
```

Then `c := a + b` calls it; the operands may be of two types
(`operator * (A: TPoint; K: Integer): TPoint`), and a comparison
returns a Boolean (`testdata/opadd`, `opmore`).

`examples/bits.paslang`:

```pascal
{ The logic family, the shifts and rotations, and compound assignment:
  flags packed in a byte, a hash mixed by rotation, a mask cleared. }
program bits;

const
  FRead = 1;
  FWrite = 2;
  FExec = 4;

var
  flags: Byte;
  h: Integer;
  w: Word;
  i: Integer;
  on: Boolean;

begin
  flags := FRead or FWrite or FExec;
  flags andnot= FWrite;                     { clear one flag }
  WriteLn(flags, ' ', flags and FWrite, ' ', flags nand FRead);   { 5 0 254 }
  on := (flags and FExec) <> 0;             { a test is a comparison }
  WriteLn(on, ' ', Boolean(flags and FRead), ' ', Ord(on) + 1);   { 1 1 2 }
  h := 0;
  for i := 1 to 4 do
  begin
    h := h xor i;
    h rol= 13;                              { mix: a rotation, no loss }
    h *= 31;
  end;
  WriteLn(h);
  w := $8421;
  WriteLn(w rol 4, ' ', w ror 4, ' ', w sar 4, ' ', Integer(w) sar 4);   { 16920 6210 63554 2114 }
  WriteLn(-40 sar 3, ' ', 5 xnor 3, ' ', 12 nor 10);                { -5 -7 -15 }
end.
```

prints

```
5 0 254
1 1 2
8684170628557668569
16920 6210 63554 2114
-5 -7 -15
```

A record type needs no name where a type goes: `var pt: record X, Y:
Int32 end;` declares a variable of a record of its own, and a field,
an array element or a unit's variable can be one too.

### Bit words

The bit words work on any variable. Bit `n` is bit `n mod 8` of byte
`n div 8`, in memory's order, which on both machines is the value's
own: bit 0 of an integer is its lowest, and bit 63 of a `Double` its
sign.

| First argument | Its bits |
|---|---|
| an integer or a `Char` | its width's: 8 for a `Byte`, an `Int8` or a `Char`, then 16, 32 and 64; a signed type's are its two's complement (`PopCount(Int8(-1))` is 8) |
| a `Single`, a `Double`, a `Boolean`, an enumeration, a pointer, a set | its own 32 or 64, in a register: `IsBitSet(d, 63)` is the sign, `SetBit(p, 0, 1)` tags a pointer, `PopCount(st)` counts a set |
| a record, a static array, a `Quad`, an object | its bytes, padding included; an object's instance, its method table too |
| a `string` | its characters, as many as it has now; a write makes them its own first, as `s[i] :=` does |
| a slice (`array of T`) | its elements, as many as it has now |
| `p^` of an untyped `Pointer` | the memory there, with no end the compiler knows (`safe` code refuses it) |

| Word | What it does |
|---|---|
| `IsBitSet(x, n)` | the `Integer` 0 or 1; `if IsBitSet(x, 3) then` works, since `if` takes an integer |
| `SetBit(x, n, v)` | sets bit `n` of the variable `x` when `v` is not 0 (or is `True`), clears it when it is |
| `ToggleBit(x, n)` | flips bit `n` of the variable `x` |
| `GetBits(x, pos, width)` | the `width` bits from `pos` up, an `Integer` from 0; `width` is a constant |
| `SetBits(x, pos, width, v)` | puts the low `width` bits of `v` there in the variable `x` |
| `PopCount(x)` | how many bits are 1 |
| `LeadingZeros(x)`, `TrailingZeros(x)` | the zeros above the highest 1 and below the lowest, the width when `x` is 0 |
| `ReverseBits(x)`, `ByteSwap(x)` | the bits and the bytes in the other order, of `x`'s type |
| `RotateLeft(x, n)`, `RotateRight(x, n)` | `x rol n` and `x ror n` in `x`'s own width, whatever the context; a bigger value, a string or a slice turns whole, `n` is 1 when left out (1.0.130), and a negative `n` turns the other way |

A routine value (16 bytes, §5) is refused by every bit word:
`PopCount(f)` says `PopCount takes an integer`.

`AtomicSetBit(x, n)` and `AtomicClearBit(x, n)` change one bit for
every routine at once, on its byte alone, and give the `Integer` 0 or 1
the bit was, so a test-and-set is one call; they take any variable but
a string, whose characters may be shared.

A constant bit number or field outside the value is a compile error
(`bit 8 out of range [0..7]`, `bits 6..9 out of range [0..7]`); one
that varies is checked with one compare and a jump, against the length
a string or a slice has at that moment, and stops the program with
`bit N out of range [0..M] at line L`. Raw memory is not checked,
unless the unit is compiled with `-checkptr`. `ReverseBits` and
`ByteSwap` take a value of up to 8 bytes (a `Double` comes back a
`Double`), the rotations any value (see Carry, rotations and shifts); `PopCount`, `LeadingZeros` and `TrailingZeros` count a
record, an array, a string or a slice whole, the highest bit being bit
7 of its last byte. `SetBits` takes the
low `width` bits of a value that varies, and a constant must fit the
field. The counts are `Integer`s. The bit words' names are reserved
(1.0.131, §19).

The code is the machine's own: `SetBit(b, 3, 1)` is `orb $8` on `b`'s
byte, or `orq $8` on the register a loop keeps it in; `IsBitSet` a
shift and an `and`; `TrailingZeros` `bsf` over a sentinel bit and
`LeadingZeros` `bsr` (`rbit` + `clz` and `clz` on arm64); `ByteSwap`
`bswap` or `rev`; `ReverseBits` `rbit` on arm64 and a `bswap` with three
swaps on amd64, which has no bit reversal; `PopCount` `popcnt` when the
processor the program is compiled for has it (`-cpu`, §20) and twelve
instructions when it does not, `cnt` on arm64. On memory a constant bit is one instruction
on its byte, and a count over a record or a string a loop in the
runtime, eight bytes a step.

`examples/bitfields.paslang`:

```pascal
{ Bit words: a packed status register decoded with GetBits and changed
  with SetBits and SetBit, a Unix mode printed as ls shows it, a bitmap
  of slots searched with TrailingZeros and counted with PopCount, and
  the next power of two from LeadingZeros. }
program bitfields;

const
  Status = $002A1C85;      { bits 0..3 channel, 4..11 level, 12 enabled, 16..31 count }

var
  reg: UInt32;
  mode, w: Word;
  used: Byte;
  n, slot: Integer;

function Rwx(M: Word): string;      { the nine permission bits, as ls prints them }
const
  Letters = 'rwx';
var
  k: Integer;
begin
  Result := '';
  for k := 8 downto 0 do
    if IsBitSet(M, k) then
      Result := Result + Letters[3 - k mod 3]
    else
      Result := Result + '-';
end;

begin
  reg := Status;
  WriteLn(GetBits(reg, 0, 4), ' ', GetBits(reg, 4, 8), ' ', IsBitSet(reg, 12), ' ',
    GetBits(reg, 16, 16));                                    { 5 200 1 42 }
  SetBits(reg, 4, 8, 15);                                     { level := 15 }
  SetBit(reg, 12, 0);                                         { enabled := off }
  SetBits(reg, 16, 16, GetBits(reg, 16, 16) + 1);             { count += 1 }
  WriteLn(reg, ' ', GetBits(reg, 4, 8), ' ', GetBits(reg, 16, 16));   { 2818293 15 43 }
  mode := $41E8;                                              { a directory, mode 0750 }
  WriteLn(GetBits(mode, 12, 4), ' ', GetBits(mode, 6, 3), GetBits(mode, 3, 3),
    GetBits(mode, 0, 3), ' ', Rwx(mode));                     { 4 750 rwxr-x--- }
  used := $B7;                                                { slots 3 and 6 are free }
  n := 8 - PopCount(used);
  slot := TrailingZeros(Byte(not used));                      { the lowest free slot }
  WriteLn(n, ' ', slot);                                      { 2 3 }
  SetBit(used, slot, 1);                                      { take it }
  WriteLn(TrailingZeros(Byte(not used)), ' ', PopCount(used));   { 6 7 }
  used := $FF;
  WriteLn(TrailingZeros(Byte(not used)));                     { 8: no slot is free }
  n := 100;
  WriteLn(64 - LeadingZeros(n), ' ', 1 shl (64 - LeadingZeros(n - 1)));   { 7 128: bits, next power of two }
  w := $1234;                                                 { a big-endian field }
  WriteLn(ByteSwap(w), ' ', ReverseBits(Byte(1)));            { 13330 128 }
end.
```

prints

```
5 200 1 42
2818293 15 43
4 750 rwxr-x---
2 3
6 7
8
7 128
13330 128
```

`GetBits` and `SetBits` are the way to a field of a packed word, with
no mask or shift written by hand: the count in bits 16..31 is read,
added to and put back in one line, and the level in 4..11 is replaced
whole. `Rwx` takes the permission bits from 8 down to 0 with a bit
number that varies. A bitmap of taken slots is searched through its
complement: `not used` keeps the `Byte`'s eight bits, so
`TrailingZeros` of it is the lowest free slot, and 8, the width, when
none is; `8 - PopCount(used)` is how many are free. `64 -
LeadingZeros(n)` is the number of bits `n` takes, and `1 shl (64 -
LeadingZeros(n - 1))` the power of two at or above `n` (128 for 100, 64
for 64). `ByteSwap` of a `Word` turns a big-endian field into the
machine's order and back.

### Carry, rotations and shifts

Carry is one bit of the running routine, as a processor's carry flag is
one per thread: each routine has its own, 0 when it starts, kept across
the calls it makes, and only the words here change it. The operators
`rol`, `ror`, `shl`, `shr` and `sar` never touch it.

| Word | What it does |
|---|---|
| `Carry` | the routine's Carry, a `Boolean`; `Carry := b` sets it |
| `CarryOn`, `CarryOff`, `CarryFlip` | set it to 1, to 0, flip it |

The rotation and shift words take a value and a count `n`, 1 when it is
left out (`RotateLeftToCarry(x)`). The value is an integer or a `Char`
in its width, or a real, a `Boolean`, an enumeration or a pointer as
its bits; since 1.0.130 anything else too, whole: a record, a static
array, a `Quad`, a `V128` or a `V256` as its bytes, a string as its
characters and a slice as its elements, as many as it has, one number
whose bit i is bit i mod 8 of byte i div 8, as for the bit words. The
word gives a value of the same type (a new string or slice; the
operand is left as it was), turned or shifted in that whole width. Being functions, they work on variables
(`x := RotateLeftThroughCarry(x)`) and on constants: a constant with no
type takes the width of where it goes (`b := RotateLeftToCarry($81)`
turns a `Byte`'s 8 bits and gives 3; alone, 64 bits).

| Word | The bits | Carry | amd64 · Z80 |
|---|---|---|---|
| `RotateLeft`, `RotateRight` | circular | untouched | `rol`, `ror` |
| `RotateLeftToCarry`, `RotateRightToCarry` | circular | gets the last bit that came round | `rol`, `ror` · RLC, RRC |
| `RotateLeftThroughCarry`, `RotateRightThroughCarry` | circular through Carry: a ring of the width + 1 bits | is the ring's extra bit | `rcl`, `rcr` · RL, RR |
| `ShiftLeft`, `ShiftRight` | zeros come in | untouched | `shl`, `shr` |
| `ShiftRightSigned` | copies of the top bit come in | untouched | `sar` |
| `ShiftLeftToCarry`, `ShiftRightToCarry` | zeros come in | gets the last bit out | `shl`, `shr` · SLA, SRL |
| `ShiftRightSignedToCarry` | copies of the top bit come in | gets the last bit out | `sar` · SRA |
| `FunnelLeft(hi, lo, n)` | the top half of `hi:lo` shifted left | untouched | `shld` (arm64 `extr`) |
| `FunnelRight(hi, lo, n)` | the low half of `hi:lo` shifted right | untouched | `shrd` (arm64 `extr`) |

- A count of 0 or less changes nothing, the value or Carry, except in
  `RotateLeft` and `RotateRight`, which are `rol` and `ror`: a negative
  count turns the other way, `RotateLeft(x, -3)` being `RotateRight(x,
  3)`, in a register and on a whole value alike (1.0.147).
- A count past the width is exact, never the processor's count modulo
  32 or 64: a rotation turns `n mod` the width, `n mod` (the width + 1)
  through Carry; a shift of the width or more gives 0, or copies of the
  sign; a `ToCarry` shift past the width leaves 0 in Carry (a signed
  one, the sign), and exactly the width leaves the last bit there.
- A funnel's two values join in one width as the two sides of `hi + lo`
  do (a `Byte` and a `Word` in a `Word`, a constant in the other's); a
  count of twice the width or more gives 0. `hi` comes back for a count
  of 0 or less on the left, `lo` on the right.
- A word as a statement keeps only its Carry: `ShiftRightToCarry(i, 5);`
  puts bit 4 of `i` in Carry and leaves `i` alone.
- `AddCarry` and `SubBorrow` keep their carry in the variables they are
  given, not in Carry: `s := AddCarry(a, b, Ord(Carry), c); Carry := c
  <> 0` chains one through it.
- A record or an array that holds strings, pointers or objects is
  refused, since a turn would make addresses up, and so is an object;
  `p^` of an untyped `Pointer` needs its type first. A funnel's two
  values have one type, and two strings or slices one length, or the
  program stops: `a funnel of 3 and 4 bytes at line L`. An empty string
  or slice has no bits: it comes back empty, and a shift to Carry leaves
  0 there.
- Their names are reserved (1.0.131, §19): no variable, routine, field
  or type takes one.

```
{ a 256-bit number one place to the left, a word at a time }
CarryOff;
for i := 0 to 3 do
  a[i] := RotateLeftThroughCarry(a[i]);

{ a 264-bit number, an array of 33 bytes, turned in one word }
big := RotateLeftThroughCarry(big);

{ CRC-8, polynomial 7 }
crc := crc xor b;
for k := 0 to 7 do
begin
  crc := ShiftLeftToCarry(crc);
  if Carry then
    crc := crc xor $07;
end;
```

The code is the machine's. Carry is a byte in the routine's record,
which a register always holds (r14, x28): `CarryOn` is one `movb`,
`Carry` one `movzbl` (`ldrb`). With a constant count, `x :=
RotateLeftThroughCarry(x)` is `btl` (Carry into the flag), `rclb $1` on
`x`'s byte or on the register a loop keeps it in, and `setc`; a count of
the width is one turn the other way (`rcrq $1`); `ShiftLeftToCarry(x,
3)` is two shifts and a `setc`; `FunnelLeft(hi, lo, 5)` one `shldq` or
one `extr`. A count that varies adds a compare for 0 or less and one for
past the width; through Carry, a division by the width + 1 only when the
count is larger than the width. arm64 has no rotation through a flag: a
ring of up to 33 bits is two shifts and an `orr` in one register, one of
65 bits five instructions. An element, a field or `p^` turns in place
too, its address worked out once (`rclq $1` on `a[i]`). A loop that uses
Carry keeps it in a register, as it keeps a variable, loaded when the
loop starts and stored when it ends: a 256-bit number shifted a word at
a time through Carry is `btl $0, %r10d`, `rclq $1, -32(%rbp,%r9,8)` and
`setc %r10b` a word. A bigger value goes to the runtime (pasheap's
`PasRotMem`) into a block of its own, which an assignment then copies:
inside the value each 8 bytes of the result are two loads and a `shrdq`
(an `ldp` and three shifts on arm64), its ends a word at a time.

Measured on amd64 (ticks of the cycle counter): a CRC-8 about 100 a
byte, bound by the `if Carry` branch the processor mispredicts; a
carry chain over 128 words about 330 a KB (2.6 a word; 2800 with Carry
in memory); a whole 1 KB array turned through Carry about 680 a KB,
the copy back included.

`examples/carry.paslang` shows the Carry words at work: the ring a byte
and Carry make, a 256-bit number doubled a word at a time, ones counted
by turning them into Carry one by one, the CRC-8 of the standard check
text, a 128-bit shift with the funnels, and a word run as a statement
for its Carry alone.

`examples/carry.paslang`:

```pascal
{ Carry: a ring of nine bits through the flag, a 256-bit number
  doubled a word at a time, ones counted by rotating them into Carry,
  CRC-8 with ShiftLeftToCarry, a 128-bit shift with the funnels, and a
  word used as a statement for its Carry alone. }
program carry;

var
  b, crc: Byte;
  k, n, ones, hi, lo: Integer;
  big: array[0..3] of Integer;
  text: string;

function HexInt(x: Integer): string;   { the 16 hex digits of a word }
const
  Digits = '0123456789abcdef';
var
  j: Integer;
begin
  Result := '';
  for j := 15 downto 0 do
    Result += Digits[GetBits(x, j * 4, 4) + 1];
end;

begin
  b := 1;                             { the byte and Carry make a ring of 9 bits }
  CarryOff;
  for k := 1 to 9 do
  begin
    b := RotateLeftThroughCarry(b);
    Write(b, '/', Ord(Carry), ' ');
  end;
  WriteLn;                            { 2/0 4/0 8/0 16/0 32/0 64/0 128/0 0/1 1/0 }
  big[0] := -1;                       { a 256-bit number: all ones, 0, 3, 0 }
  big[1] := 0;
  big[2] := 3;
  big[3] := 0;
  CarryOff;                           { doubled: each word takes the bit the one below it lost }
  for k := 0 to 3 do
    big[k] := RotateLeftThroughCarry(big[k]);
  WriteLn(HexInt(big[3]), ' ', HexInt(big[2]), ' ', HexInt(big[1]), ' ', HexInt(big[0]), ' ', Ord(Carry));
  b := $B5;                           { 1011 0101: five ones, counted through Carry }
  ones := 0;
  for k := 1 to 8 do
  begin
    b := RotateLeftToCarry(b);
    ones += Ord(Carry);
  end;
  WriteLn(ones, ' ', PopCount(b), ' ', b);        { 5 5 181: eight turns bring the byte back }
  text := '123456789';                { CRC-8, polynomial 7: the check value is $F4 }
  crc := 0;
  for n := 1 to Length(text) do
  begin
    crc := crc xor Byte(Ord(text[n]));
    for k := 1 to 8 do
    begin
      crc := ShiftLeftToCarry(crc);
      if Carry then
        crc := crc xor $07;
    end;
  end;
  WriteLn(crc, ' ', Hex(Char(crc)));              { 244 f4 }
  hi := $0123456789ABCDEF;            { hi:lo, a 128-bit value, shifted 4 left, then 4 right }
  lo := $F000000000000001;
  WriteLn(HexInt(FunnelLeft(hi, lo, 4)), ' ', HexInt(lo shl 4));      { the top nibble of lo enters hi }
  WriteLn(HexInt(hi shr 4), ' ', HexInt(FunnelRight(hi, lo, 4)));     { the low nibble of hi enters lo }
  ShiftRightToCarry(hi, 1);           { a statement: only Carry changes }
  WriteLn(Ord(Carry), ' ', hi = $0123456789ABCDEF);   { 1 1 }
end.
```

prints

```
2/0 4/0 8/0 16/0 32/0 64/0 128/0 0/1 1/0 
0000000000000000 0000000000000006 0000000000000001 fffffffffffffffe 0
5 5 181
244 f4
123456789abcdeff 0000000000000010
00123456789abcde ff00000000000000
1 1
```

`HexInt` there is `GetBits` four bits at a time; `$F4` is the check
value every CRC-8 (polynomial 7) implementation must give for
`'123456789'`. The doubling loop is what `RotateLeftThroughCarry` is
for: one instruction a word, and the bit that leaves one word enters
the next through Carry, with no mask and no test.

`examples/bigrot.paslang` turns whole values, where the bits of the
bytes are one number, bit i being bit i mod 8 of byte i div 8: a bitmap
of four bytes, a string, a slice of words and a record.

`examples/bigrot.paslang`:

```pascal
{ Rotations of whole values: a bitmap of 32 bits in four bytes, a string
  turned by whole characters, a slice, a record of four channels, and
  the count rules on them. }
program bigrot;

type
  TColor = record
    R, G, B, A: Byte;
  end;

var
  bits: array[0..3] of Byte;
  s: string;
  ws: array of Word;
  c: TColor;
  i: Integer;

begin
  bits[0] := 1;                       { bit 31 of the four bytes, as one number, comes round to bit 0 }
  bits[1] := 2;
  bits[2] := 4;
  bits[3] := $80;
  bits := RotateLeft(bits, 1);
  WriteLn(bits[0], ' ', bits[1], ' ', bits[2], ' ', bits[3]);   { 3 4 8 0 }
  bits := RotateRight(bits, 1);
  WriteLn(bits[0], ' ', bits[1], ' ', bits[2], ' ', bits[3]);   { 1 2 4 128 }
  bits := ShiftLeft(bits, 8);         { a byte up; the top one is lost }
  WriteLn(bits[0], ' ', bits[1], ' ', bits[2], ' ', bits[3]);   { 0 1 2 4 }
  s := 'paslang';                     { 8 bits move every character up one place, the last to the front }
  WriteLn(RotateLeft(s, 8), ' ', RotateLeft(s, 16), ' ', RotateRight(s, 8), ' ', s);   { gpaslan ngpasla aslangp paslang }
  WriteLn(RotateLeft(s, -8) = RotateRight(s, 8), ' ', RotateLeft(s, 56) = s, ' ', RotateLeft(s, 0) = s);   { 1 1 1 }
  SetLength(ws, 4);                   { a slice of words, one element up }
  for i := 0 to 3 do
    ws[i] := Word(10 * (i + 1));
  ws := RotateLeft(ws, 16);
  WriteLn(ws[0], ' ', ws[1], ' ', ws[2], ' ', ws[3]);   { 40 10 20 30 }
  c.R := 1;                           { a record of four bytes: each field takes the one before it }
  c.G := 2;
  c.B := 3;
  c.A := 4;
  c := RotateLeft(c, 8);
  WriteLn(c.R, ' ', c.G, ' ', c.B, ' ', c.A);     { 4 1 2 3 }
  c := RotateRight(c, 16);
  WriteLn(c.R, ' ', c.G, ' ', c.B, ' ', c.A);     { 2 3 4 1 }
  c.A := $80;                         { a shift to Carry over the whole record: A's top bit leaves }
  c := ShiftLeftToCarry(c, 1);
  WriteLn(Ord(Carry), ' ', c.R, ' ', c.G, ' ', c.B, ' ', c.A);   { 1 4 6 8 0 }
end.
```

prints

```
3 4 8 0
1 2 4 128
0 1 2 4
gpaslan ngpasla aslangp paslang
1 1 1
40 10 20 30
4 1 2 3
2 3 4 1
1 4 6 8 0
```

A string or a slice turned by a multiple of 8 bits (or of its element's
width) moves whole elements: 8 bits move every character up one place
and bring the last to the front, so `RotateRight(s, 8)` is the rotation
of a text by one character to the left. The result is a new string or
slice; `s` is left as it was. A record turns as its bytes, padding
included, so a record of four bytes is a 32-bit ring and its fields
take each other's values in memory order; one that holds a string, a
pointer or an object is refused, since a turn would make an address
up.

### Views: x as T

`x as T` sees the bytes of `x` as a `T`, as they are: nothing is
converted, and the view can be written. `T(x)` stays the conversion of
the value (`Integer(2.5)` is refused, `UInt64(d)` asks for `Trunc`),
and `obj as TClass` stays the checked cast of an object.

```
(d as UInt64) xor= $8000000000000000;     { flips a Double's sign }
(r as TPair).Hi := 7;                     { the second 4 bytes of a record }
(s as array[0..3] of Char)[0] := 'Z';     { a string's first character }
Inc(i as Byte, 10);                       { the low byte of i wraps alone }
```

- A value of one register seen as another (`d as UInt64`, `i as
  Double`, `w as Byte`, `s8 as Byte`) is its bits in the register: no
  code, and `x` keeps its register. A write puts the view's bits into
  the low bytes of `x` and keeps the others, as memory would.
- Anything else is a `T` at `x`'s address: a record, an array, a
  `Quad`, an object's instance, a string's characters (made its own
  first, as any write does), a slice's elements, and `p^` of an untyped
  `Pointer`. The view is a variable: it takes `:=`, compound
  assignment, `Inc`, `SetBit` and a field or an index after it.
- A view bigger than its variable is a compile error (`a view of 2 bytes
  on Byte of 1`); on a string or a slice it is checked at run time
  against the length it has (`bit 31 out of range [0..15]` for four
  bytes of a two-byte string); raw memory has no end the compiler knows,
  and `safe` code refuses it.
- `as` binds as a comparison does: `d as UInt64 xor m` needs no
  parentheses, and a field, an index or `+` after a view does: `(r as
  TPair).Hi`, `(d as UInt64) + 1`. A statement may begin with the
  parenthesis: `(d as UInt64) := 0`.

### Logic on whole blocks

`and`, `or`, `xor`, `not`, `nand`, `nor`, `xnor` and `andnot` take whole
records, static arrays and strings, byte by byte:

```
r3 := r1 xor r2;                 { two records of one size }
key xor= pad;                    { in place }
mask := not mask;                { every bit of an array }
a := a and $FF00FF00;            { one integer over every element }
s := s xor '      ';             { flips the case of six letters }
```

- Two records or static arrays of one size, or a static array of
  integers and one integer, which is repeated over its elements. The
  result goes into a variable (`r := a xor b`, `r xor= b`); in any other
  place it is a compile error, since a record is not a number. Nested
  forms (`(a xor b) and c`) and a record a routine gives back work.
- Two strings of one length give a new string, anywhere a string goes;
  of two lengths they stop the program with `logic on 3 and 4 bytes at
  line L`.
- A record or an array that holds strings, slices, pointers or objects
  is refused: its logic would make addresses up.
- The runtime works eight bytes a step, then one.

A record, a static array, a string and a slice go only where their own
type goes: `i := r`, `s := r` and `r := r2` of another record are compile
errors (they compiled, and moved words that did not belong). `x as T`
(views, above) sees one as another.

`examples/views.paslang`:

```pascal
{ Views and logic on whole blocks: a Double taken apart through its bits
  as a UInt64 and stepped to the next value by Inc of the view, a record
  seen as its bytes, a header put on the wire big-endian with StoreBE
  and read back with LoadBE, two records xor-ed whole, and a string's
  case flipped by a mask. }
program views;

type
  THeader = record
    Magic: UInt32;
    Len: Word;
    Kind, Flags: Byte;
  end;

var
  d: Double;
  bits: UInt64;
  h, k, m: THeader;
  wire: array[0..7] of Byte;
  i, sum: Integer;

begin
  d := -6.5;
  bits := d as UInt64;                                { the same 64 bits }
  WriteLn(bits shr 63, ' ', GetBits(bits, 52, 11) - 1023, ' ', GetBits(bits, 0, 52));
  { 1 2 2814749767106560: sign, exponent, fraction }
  (d as UInt64) xor= $8000000000000000;               { the sign alone }
  WriteLn(d);                                         { 6.5 }
  d := 1.0;
  bits := d as UInt64;
  Inc(d as UInt64);                                   { the next Double above 1.0 }
  WriteLn(d > 1.0, ' ', (d as UInt64) - bits, ' ', (d - 1.0) * 4503599627370496);   { 1 1 1.0 }
  bits := $3FF8000000000000;
  WriteLn(bits as Double);                            { 1.5 }
  i := 250;
  Inc(i as Byte, 10);                                 { the low byte wraps alone }
  WriteLn(i);                                         { 4 }
  h.Magic := $50415321;
  h.Len := 300;
  h.Kind := 7;
  h.Flags := $81;
  sum := 0;
  for i := 0 to SizeOf(h) - 1 do
    sum := sum + (h as array[0..7] of Byte)[i];       { a checksum over its bytes }
  WriteLn(SizeOf(h), ' ', (h as array[0..7] of Byte)[0], ' ', sum);   { 8 33 442 }
  StoreBE32(@wire[0], h.Magic);                       { on the wire, big-endian }
  StoreBE16(@wire[4], h.Len);
  wire[6] := h.Kind;
  wire[7] := h.Flags;
  WriteLn(wire[0], ' ', wire[3], ' ', wire[4], ' ', wire[5]);   { 80 33 1 44 }
  k.Magic := LoadBE32(@wire[0]);                      { and back }
  k.Len := LoadBE16(@wire[4]);
  k.Kind := wire[6];
  k.Flags := wire[7];
  m := h xor k;                                       { the same: every byte 0 }
  WriteLn(m as UInt64, ' ', k.Len, ' ', k.Magic = h.Magic);   { 0 300 1 }
  WriteLn('paslang' xor '       ', ' ', 'Ab' xor '  ');   { PASLANG aB }
end.
```

prints

```
1 2 2814749767106560
6.5
1 1 1.0
1.5
4
8 33 442
80 33 1 44
0 300 1
PASLANG aB
```

`d as UInt64` is the `Double`'s own 64 bits, so `GetBits` on the view
takes it apart: bit 63 the sign, 52..62 the exponent with its bias of
1023, 0..51 the fraction (-6.5 is -1.625 × 2², and 0.625 × 2⁵² is
2814749767106560). `Inc` of the view steps to the next `Double` above,
one unit in the last place, 2⁻⁵² at 1.0, which is why `d - 1.0` is
printed times 2⁵². `bits as Double` goes the other way. A record seen
as `array[0..7] of Byte` walks its bytes in memory's order: `Magic`
lies first and little-endian, so byte 0 is $21, and the checksum is the
sum of all eight. `StoreBE32` and `StoreBE16` (memory words, below)
put the header on the wire big-endian, `LoadBE32` and
`LoadBE16` read it back, and `h xor k` of the two records is 0 in every
byte when they agree, which `m as UInt64` reads as one integer. Two
string constants of one length go through `xor` as well: a mask of
spaces flips the case of the letters under it.

### Wide arithmetic

Words that reach what both machines do on 64-bit words in one or two
instructions (P106):

| Word | Gives | amd64 | arm64 |
|---|---|---|---|
| `MulHi(a, b)`, `MulHiS(a, b)` | the high 64 bits of the 128-bit product, unsigned or signed | `mulq`/`imulq` (rdx) | `umulh`/`smulh` |
| `Mul128(a, b, hi, lo)` | the whole unsigned product into two `Integer`s | the same and `imulq` | the same and `mul` |
| `DivMod128(hi, lo, d, q, r)` | `hi:lo` divided by `d`, unsigned, quotient and remainder | `divq` | 64 shifts and subtractions (it has no such division) |
| `AddCarry(a, b, cin, cout)` | `a + b + cin`, the carry out in `cout` (0 or 1) | `adcq` | `adcs` |
| `SubBorrow(a, b, bin, bout)` | `a - b - bin`, the borrow out in `bout` | `sbbq` | `sbcs` |
| `AddOverflow(a, b, r)`, `SubOverflow`, `MulOverflow` | `r` gets the result in its type; `True` when it did not fit | `seto` | `cset vs`, `smulh` |
| `AddSat(a, b)`, `SubSat(a, b)` | the sum or difference held at the ends of the operands' type | `cmov` | `csel` |

A carry and a borrow are 0 or 1, and any other value in `cin` counts as
1, so a chain of words adds numbers of any length:

```
lo := AddCarry(a0, b0, 0, c);
hi := AddCarry(a1, b1, c, c);            { a1:a0 + b1:b0 }
```

`MulHi` and `MulHiS` are operators the register pool keeps a loop's
values in; the others are a few instructions in line. `DivMod128` stops
the program with `128-bit division overflow at line L` when the
quotient does not fit 64 bits (`hi` not below `d`), and with `integer
divide by zero` for `d = 0`. The operands are `Integer`s: narrower ones
widen, and `cout`, `bout` and `r` may be of any integer width.

`examples/wide.paslang`:

```pascal
{ Wide arithmetic: a 128-bit product printed in decimal through DivMod128,
  a modular multiply that never overflows, MulHi as a division-free range
  reduction, a factorial that stops where MulOverflow says, and pixel
  arithmetic held at the ends by AddSat and SubSat. }
program wide;

var
  hi, lo, h2, l2, c, n, f, t: Integer;
  px: Byte;

function Decimal(Hi, Lo: Integer): string;   { the unsigned hi:lo in decimal }
var
  q, r: Integer;
begin
  Result := '';
  repeat
    DivMod128(0, Hi, 10, q, r);              { hi div 10, and its rest r }
    Hi := q;
    DivMod128(r, Lo, 10, q, r);              { r:lo div 10, and the digit }
    Lo := q;
    Result := Chr(Ord('0') + r) + Result;
  until (Hi = 0) and (Lo = 0);
end;

function MulMod(A, B, M: Integer): Integer;  { a * b mod m, for a, b < m }
var
  h, l, q: Integer;
begin
  Mul128(A, B, h, l);
  DivMod128(h, l, M, q, Result);
end;

begin
  Mul128(10000000000, 10000000000, hi, lo);  { 10^20 does not fit 64 bits }
  WriteLn(hi, ' ', lo, ' ', Decimal(hi, lo));   { 5 7766279631452241920 100000000000000000000 }
  l2 := AddCarry(lo, lo, 0, c);
  h2 := AddCarry(hi, hi, c, c);              { hi:lo + hi:lo }
  WriteLn(Decimal(h2, l2), ' ', c);          { 200000000000000000000 0 }
  n := 9223372036854775783;                  { the largest prime below 2^63 }
  WriteLn(MulMod(n - 1, n - 1, n), ' ', MulMod(n - 2, n - 3, n));   { 1 6: (-1)(-1) and (-2)(-3) }
  WriteLn(MulHi($DEADBEEFCAFEBABE, 100), ' ', MulHi(-1, 100));      { 86 99: x / 2^64 * 100, a bucket of 0..99 }
  f := 1;
  n := 0;
  while not MulOverflow(f, n + 1, t) do      { the last n! that fits }
  begin
    n := n + 1;
    f := t;
  end;
  WriteLn(n, ' ', f);                        { 20 2432902008176640000 }
  WriteLn(AddOverflow(f, 3 * f, t), ' ', t, ' ', AddSat(f, 3 * f));   { 1 -8715136041002991616 9223372036854775807 }
  px := 200;
  WriteLn(AddSat(px, 100), ' ', SubSat(px, 250), ' ', Byte(px + 100), ' ', Byte(px - 250));   { 255 0 44 206 }
end.
```

prints

```
5 7766279631452241920 100000000000000000000
200000000000000000000 0
1 6
86 99
20 2432902008176640000
1 -8715136041002991616 9223372036854775807
255 0 44 206
```

`Decimal` prints a 128-bit number with a quotient that only fits 64
bits: `0:hi` by 10 first, then that remainder over `lo`, and the second
remainder is the digit; the two quotients are the next `hi:lo`. `MulMod`
is `a * b mod m` with no overflow at all: for `a` and `b` below `m` the
product is below `m²`, so its high word is below `m` and `DivMod128`
cannot overflow; `Result` stands where the remainder goes. `MulHi(x, n)`
is `x * n div 2⁶⁴`, which for an `x` spread over its 64 bits (a hash, a
random word) is a number in `0..n-1`: the range reduction that costs
one multiply and no division. The factorial loop keeps in `f` the last
product that fit; `t` takes the one that did not, wrapped, and is
thrown away. `AddSat` and `SubSat` are the one exception to the
widening: they work in the type their two operands join to, so with a
`Byte` `px` the literal joins to `Byte` and the sum holds at 255, where
`Byte(px + 100)` is the same sum done in `Integer` and cut to eight
bits, 44.

### Memory words

| Word | What it does | amd64 | arm64 |
|---|---|---|---|
| `LoadFence`, `StoreFence`, `FullFence` | order the loads, the stores, or both, before against after | `lfence`, `sfence`, `mfence` | `dmb ishld`, `ishst`, `ish` |
| `Prefetch(p)`, `PrefetchWrite(p)` | ask for the cache line at `p` early, to read or to write | `prefetcht0`, `prefetchw` | `prfm pldl1keep`, `pstl1keep` |
| `CacheLine` | the cache line of both machines, 64 bytes, a constant | | |
| `StoreNT(x, v)` | a store past the cache | `movnti` | `str` (it has no single one) |
| `AtomicLoad(x)`, `AtomicStore(x, v)` | a load that acquires, a store that releases | `mov` (x86 orders them) | `ldar`, `stlr` |
| `AtomicExchange(x, v)` | puts `v` and gives what `x` held | `xchg` | `ldaxr`/`stlxr` |
| `AtomicAnd(x, v)`, `AtomicOr`, `AtomicXor` | change `x` for every routine at once and give what it held | `lock cmpxchg` loop | `ldaxr`/`stlxr` loop |
| `LoadBE16(p)`, `LoadBE32`, `LoadBE64`, `LoadLE16`… | the bytes at `p`, aligned or not, in big- or little-endian order | `mov` + `bswap` | `ldr` + `rev` |
| `StoreBE16(p, v)`, …, `StoreLE64(p, v)` | the low bytes of `v` there in that order | `bswap` + `mov` | `rev` + `str` |

The atomic words take an integer variable of any width (`Byte` to
`Integer`) and work at its width; the loads and stores in an order take
any pointer and give a `Word`, a `UInt32` or an `Integer`. A fence, a
prefetch and any word called for its effect end a run of the register
pool, as a call does. `safe` code refuses a load or a store at a
pointer, which sees memory as another type.

`examples/atomics.paslang`:

```pascal
{ Memory words from many routines: a counter kept by AtomicAdd, a flag
  claimed once with AtomicSetBit, a maximum kept by AtomicCas, a bit for
  each routine that finished, and a value published with AtomicStore and
  read with AtomicLoad. Sixteen routines, and a result that is always
  the same, with no lock. }
program atomics;

const
  N = 16;

var
  hits, claimed, best, ready, data, i: Integer;
  flag: Byte;
  done: Word;                              { one bit for each routine }
  wg: waitgroup;

procedure Worker(K: Integer);
var
  j, old, v: Integer;
begin
  for j := 1 to 1000 do
    AtomicAdd(@hits, 1);                   { one instruction, no lock }
  if AtomicSetBit(flag, 0) = 0 then        { the first to get here }
    AtomicAdd(@claimed, 1);
  v := (K * 7919) mod 1000;
  repeat                                   { best := max(best, v) }
    old := AtomicLoad(best);
  until (v <= old) or AtomicCas(@best, old, v);
  AtomicSetBit(done, K);
  wg.Done;
end;

procedure Publish;
begin
  data := 42;                              { written before the flag; }
  AtomicStore(ready, 1);                   { the store releases it }
end;

begin
  wg.Add(N);
  for i := 0 to N - 1 do
    pas Worker(i);
  wg.Wait;
  WriteLn(hits, ' ', claimed, ' ', best);  { 16000 1 947 }
  WriteLn(done, ' ', PopCount(done));      { 65535 16 }
  WriteLn(AtomicExchange(hits, 0), ' ', hits);   { 16000 0: read and reset in one step }
  pas Publish;
  while AtomicLoad(ready) = 0 do           { the load acquires: data is seen after ready }
    Sleep(1);
  WriteLn(data);                           { 42 }
end.
```

prints

```
16000 1 947
65535 16
16000 0
42
```

`AtomicAdd(@v, d)` and `AtomicCas(@v, old, new)` are the runtime's
words (§17): unlike the words above they take the address of an
`Integer`, and a narrower one is refused (`AtomicAdd needs an 8-byte
integer, not a Byte`), as is the variable itself where its address
goes (`AtomicAdd takes the address of an Integer, as AtomicAdd(@v,
...)`, 1.0.147).
`AtomicSetBit(flag, 0)` is the test-and-set: sixteen routines call it
and exactly one gets the 0 back. The `AtomicCas` loop is a maximum
without a lock: read, compare, and put the larger value only when
nobody changed the word meanwhile; a routine that lost the race reads
again. `done` gathers one bit per routine and `PopCount` counts them.
`AtomicStore` and `AtomicLoad` publish a value: what `Publish` wrote
before the store is seen by whoever loaded the 1 (a release and an
acquire), so `data` is 42 once the loop ends, and the loop parks in
`Sleep` rather than spin. `AtomicExchange(hits, 0)` reads a counter and
resets it in one step, so no count is lost between the two. A spin lock
is the same words in a loop:

```
while AtomicExchange(lock, 1) <> 0 do   { a spin lock }
  Pause;
Inc(total);
AtomicStore(lock, 0);
```

### Vectors: V128 and V256

`V128` and `V256` are 16 and 32 bytes that the vector words work on lane
by lane, in the machine's vector registers: lanes of 8, 16, 32 or 64
bits, as the word's name says. Everything a record can do they do: a
variable, a field, an element of an array, a parameter, a function's
result, `p^` through `^V128`; `:=` copies them. A lane is read and
written through a view, and memory is read as vectors through a typed
pointer:

```
type
  PV = ^V128;
var
  v, w: V128;
  p: PV;
...
(v as array[0..15] of Byte)[3] := 200;        { lane 3 of the bytes }
w := VAddSatU8(v, VSplat8(100));              { 16 saturating adds }
p := PV(@buf[0]);
p[i] := VMaxU8(p[i], w);                      { 16 bytes at a time }
```

| Words | Lanes | What each lane gets |
|---|---|---|
| `VAdd8` `VAdd16` `VAdd32` `VAdd64`, `VSub8`…`VSub64` | all | the sum or difference, wrapping |
| `VAddSatU8` `VAddSatS8` `VAddSatU16` `VAddSatS16`, `VSubSatU8`…`VSubSatS16` | 8, 16 | the sum or difference held to the lane's range, unsigned (U) or signed (S) |
| `VMul16`, `VMul32` | 16, 32 | the low half of the product |
| `VAvgU8`, `VAvgU16` | 8, 16 | (a + b + 1) div 2, unsigned |
| `VMinU8` `VMaxU8` `VMinS8` `VMaxS8`, the same for 16 and 32 | 8, 16, 32 | the smaller or larger, unsigned or signed |
| `VCmpEq8`…`VCmpEq64`, `VCmpGtS8`…`VCmpGtS32`, `VCmpGtU8`…`VCmpGtU32` | all; 8, 16, 32 | all ones where the lanes are equal (a is greater), else zero: a mask |
| `VAnd`, `VOr`, `VXor`, `VAndNot(a, b)` (a and not b), `VNot` | bits | the logic of the bits; `and`, `or`, `xor`, `not`, `andnot`, `nand`, `nor`, `xnor` and `x op= y` on vectors are these words |
| `VSelect(m, a, b)` | bits | a where m's bits are 1, b where they are 0 |
| `VShl16` `VShl32` `VShl64`, `VShrU16`…`VShrU64`, `VShrS16` `VShrS32` `VShrS64` | 16, 32, 64 | every lane shifted by one count, a constant or a variable: left, right with zeros (U) or with the sign (S); a count past the lane, or negative, leaves 0 (or the sign). `VShrS64` (1.0.136) is `sshr` (`sshl` for a count that varies) on arm64 and six instructions on amd64, which has no such shift before AVX-512 |
| `VSplat8(x)`…`VSplat64(x)` | all | x's low bits in every lane; a V128 or a V256 as the other operand or the variable it goes into says |
| `VShuffle8(a, idx)` | 8 | a's byte number idx, 0 where idx is past 15: a table of 16 bytes looked up 16 times at once (pshufb, tbl) |
| `VZipLo8`…`VZipLo64`, `VZipHi8`…`VZipHi64` | all | the low (high) lanes of a and b one after the other: a0 b0 a1 b1…; with `VSplat8(0)` as b, bytes widened to words |
| `VPackU16`, `VPackS16`, `VPackS32` | 16, 32 | a's lanes then b's, each held to the half-width lane: Word to Byte unsigned, to Int8, Int32 to Int16 |
| `VAddF32` `VSubF32` `VMulF32` `VDivF32`, the same for `F64` | Single, Double | IEEE arithmetic, rounded to nearest |
| `VMinF32` `VMaxF32` (and `F64`) | Single, Double | a < b ? a : b and a > b ? a : b: b when either is a NaN, as x86 has it, on both machines |
| `VCmpEqF32` `VCmpLtF32` `VCmpLeF32` (and `F64`) | Single, Double | a mask; false where a NaN is |
| `VSqrtF32`, `VSqrtF64`, `VCvtS32F32` | Single, Double | the square root; Int32 lanes to Single |
| `VSplatF32(x)`, `VSplatF64(x)` | Single, Double | x in every lane |
| `VMoveMask8(v)` | 8 | an `Integer`: bit i the top bit of byte i (16 bits, 32 for a V256) |
| `VSumU8(v)`, `VSumS32(v)`, `VSum64(v)` | 8, 32, 64 | an `Integer`: the sum of the lanes, unsigned bytes, signed Int32 (exact), 64 bits (wrapping) |

The two operands of a word are vectors of one width; a V256 is two
halves of 128 bits to every word, as AVX2's instructions are:
`VShuffle8`, the zips and the packs work in each half. A new NaN's
sign and bits are the machine's (amd64 makes a negative one); the rest
is the same on both. A comparison's mask goes on into `VSelect`, `VAnd`,
a view or `VMoveMask8`:

```
m := VCmpGtU8(v, limit);          { 255 where v > limit }
v := VSelect(m, limit, v);        { v held to limit }
k := VMoveMask8(VCmpEq8(p[i], VSplat8(Ord(','))));   { where the commas are }
if k <> 0 then
  pos := 16 * i + TrailingZeros(k);
```

A statement is worked out whole in registers: the vectors are loaded,
the words run, and the result is stored, with no call between; an
operand whose address needs a call (`F(x)[i]`) is computed first, the
others where they are loaded (`p[i]` is one `movdqu (%r10,%rax)`). The
tree may be as deep as the 14 registers allow on its right side; a
left-leaning one (`VAdd8(VAdd8(VAdd8(a, b), c), d)`) costs no more than
one word.

A loop, or any run of statements that calls no routine, keeps its
vector variables in vector registers from one statement to the next, as
it keeps integers (P107): `acc` below is loaded once before the loop,
added to in its register and stored once after it.

```
acc := VSplat32(0);
for i := 0 to n - 1 do
begin
  x := p[i];                           { a load: the copy is x's register }
  acc := VAdd32(acc, VMul32(x, x));    { vpmulld, vpaddd on acc itself }
end;
s := VSumS32(acc);
```

A variable goes into a register when every use of it in the run is an
operand of a vector word, the variable a vector word or a copy assigns,
or a copy's source, and nobody takes its address in its routine (`@v`,
a view `v as T`, which read its memory, keep it there). A local of the
routine or a program's global can; a unit's global, a `var` parameter
and the function's result stay in memory. amd64 gives up to eight
registers (xmm15 down, fewer when a statement's tree is deep: the
tree's registers come first), arm64 v8 to v15; a V256 takes two on
arm64 and in SSE2. On amd64 such a run is compiled once, for the
processor `-cpu` names (§20): for AVX2 when it has AVX2 (a V256 in one
ymm register, every instruction VEX, `vpmulld` and the other SSE4.1
instructions SSE2 lacks), for SSE2 otherwise; nothing is tested at run
time. A constant `VSplat16(255)` is one load of 32 bytes the
object file holds.

On amd64 a V128 is SSE2 and a V256 is AVX2 when the program is
compiled for a processor with it (`-cpu`, §20; the default is the
machine compiling), or two SSE2 halves otherwise; nothing is decided at
run time. `-cpu base` compiles the SSE2 paths, to test them on one
machine. `VShuffle8` is SSSE3's `pshufb` when the set has it and a loop
over the bytes when not. On arm64 a V128 is NEON and a V256 two NEON
halves. The words
SSE2 lacks (`VMul32`, `VMinS8`, `VMinU16`, `VMaxU32`, `VCmpEq64`, the
unsigned compares) are a few of its instructions. `Write` refuses a
vector (and a record or an array): it prints values, and a vector's are
its lanes.

Measured on an AMD Ryzen 9 5950X, the time-stamp counter's ticks per
1000 bytes:

| Loop | 1.0.127 | 1.0.128 |
|---|---|---|
| `c[i] := a[i] + b[i]` over 16 MiB, bytes | 1702 | 1696 |
| the same, `p[i] := VAdd8(q[i], r[i])`, V128 | 503 | 203 |
| the same, V256 (AVX2; SSE2) | 292 | 195; 199 |
| `acc := VAdd32(acc, VMul32(x, x))` and an xor, 1 MiB, V128 (AVX2; SSE2) | 1862; 1895 | 99; 169 |
| `m := VMaxU8(m, q[i])` and an add, 1 MiB, V256 (AVX2; SSE2) | 301; 383 | 50; 95 |

`examples/vectors.paslang`:

```pascal
{ Sixteen or thirty-two lanes at once: a buffer summed a vector at a
  time, its smallest and largest byte, the bytes over a limit found by
  a mask, a saturating add beside a wrapping one, and a V256 doing the
  same on 32 lanes; a lane is read through a view. }
program vectors;

type
  PV = ^V128;
  PW = ^V256;

var
  buf: array[0..63] of Byte;
  i, s, k, least, most: Integer;
  v, lo, hi, m, limit: V128;
  w: V256;
  p: PV;
  q: PW;

function Lane(const x: V128; i: Integer): Integer;
begin
  Result := (x as array[0..15] of Byte)[i];   { a view reads the lane }
end;

begin
  for i := 0 to 63 do
    buf[i] := Byte((i * 37) mod 101);         { 0 37 74 10 47 84 20 57 94 30 ... }
  p := PV(@buf[0]);
  s := 0;
  lo := VSplat8(255);
  hi := VSplat8(0);
  for i := 0 to 3 do                          { the 64 bytes, four vectors }
  begin
    s := s + VSumU8(p[i]);                    { 16 lanes added into an Integer }
    lo := VMinU8(lo, p[i]);                   { 16 running minimums }
    hi := VMaxU8(hi, p[i]);
  end;
  least := 255;
  most := 0;
  for i := 0 to 15 do                         { then the 16 lanes folded to one }
  begin
    if Lane(lo, i) < least then least := Lane(lo, i);
    if Lane(hi, i) > most then most := Lane(hi, i);
  end;
  WriteLn(s, ' ', least, ' ', most);          { 3185 0 100 }
  limit := VSplat8(50);
  m := VCmpGtU8(p[0], limit);                 { 255 in the lanes over 50 }
  k := VMoveMask8(m);                         { those lanes as bits }
  WriteLn(k, ' ', PopCount(k), ' ', TrailingZeros(k));   { 9636 6 2 }
  v := VSelect(m, limit, p[0]);               { the bytes held to 50 }
  WriteLn(Lane(p[0], 2), ' ', Lane(v, 2), ' ', Lane(v, 3));   { 74 50 10 }
  v := VAdd8(p[0], VSplat8(200));
  WriteLn(Lane(v, 8), ' ', Lane(VAddSatU8(p[0], VSplat8(200)), 8));   { 38 255: 94 + 200 wraps, or is held }
  q := PW(@buf[0]);
  w := VMaxU8(q[0], q[1]);                    { 32 lanes: the larger of byte i and byte 32 + i }
  k := VMoveMask8(VCmpGtU8(w, VSplat8(50)));  { 32 bits }
  WriteLn(VSumU8(w), ' ', PopCount(k), ' ', (w as array[0..31] of Byte)[31]);   { 2243 24 36 }
end.
```

prints

```
3185 0 100
9636 6 2
74 50 10
38 255
2243 24 36
```

A typed pointer over a byte array (`PV(@buf[0])`) reads the vectors
where they lie, an unaligned load (`movdqu`), so the array needs no
alignment. A running minimum or maximum is sixteen lanes wide
(`VMinU8`, `VMaxU8`); no word folds them to one, so the last step reads
the lanes through a view. The three sums and the mask are the
reductions there are, and on a V256 each takes every lane: `VSumU8`
adds its 32 bytes, `VMoveMask8` gives 32 bits. A mask goes on to the
integer words: `PopCount` of it counts the lanes that passed,
`TrailingZeros` finds the first. What goes into the buffer is narrowed
as any Integer is (`Byte(...)`).

### The machine's words

| Word | What it gives | amd64 | arm64 |
|---|---|---|---|
| `CycleCount` | the time-stamp counter, an `Integer` that only goes forward | `rdtsc` | `mrs cntvct_el0` |
| `CycleFreq` | the counter's ticks per second | worked out once, against the clock | `mrs cntfrq_el0` |
| `CpuHas('avx2')` | whether the processor has that feature, a `Boolean` | one bit of a word read at start | the same |
| `CpuFeatures` | that whole word, an `Integer` | cpuid and xgetbv | `AT_HWCAP`, `AT_HWCAP2` |

`CycleCount` and `CycleFreq` take no argument; the parentheses may be
written or not. On amd64 the counter runs at a constant rate (the
processor's base frequency), not with the core's clock; on arm64 it is
the generic timer (1 GHz from Armv8.6 on, often 24 MHz to a few hundred
MHz before).
So `(CycleCount - c0) / CycleFreq` is seconds on both. The first
`CycleFreq` of amd64 compares the counter and the monotonic clock with
their values at start: it waits only in a program younger than 10 ms,
and it is kept for every later call.

```
c0 := CycleCount;
Work;
WriteLn('took ', (CycleCount - c0) / CycleFreq:0:6, ' s');
```

`CpuHas` takes the name of a feature in quotes, in any case, and is
decided with the program: a feature the target machine never has is
the constant `False`, one it always has (`sse2` on amd64, `lzcnt` on
arm64) the constant `True`, and the branch that cannot run is not in
the program at all. A name neither machine knows is a compile error, so
a typo does not quietly pick the slow path. The kernel's say counts:
the AVX features are there only when it saves the `ymm` registers, the
AVX-512 ones only when it saves the `zmm` ones.

```
if CpuHas('avx2') then
  SumAvx2(a)            { amd64 with AVX2 }
else if CpuHas('neon') then
  SumNeon(a)            { every arm64 }
else
  SumPlain(a);
```

| Names | amd64 | arm64 |
|---|---|---|
| `simd128` | always (SSE2) | `asimd` |
| `simd256` | `avx2` | never |
| `aes`, `crc32`, `sha1`, `sha2`, `rng` | AES-NI, `sse42`, `sha`, `sha`, `rdrand` | the feature of that name |
| `pclmul` = `pmull` | PCLMULQDQ | PMULL |
| `popcnt`, `fma`, `lzcnt`, `cx16` | the feature | `asimd`, always, always, always |
| `sse2`, `sse3`, `ssse3`, `sse41`, `sse42`, `avx`, `avx2`, `f16c`, `movbe`, `rdrand`, `rdseed`, `bmi1`, `bmi2`, `adx`, `sha`, `erms`, `gfni`, `vaes`, `vpclmulqdq`, `avx512f`, `avx512bw`, `avx512vl`, `avx512dq`, `avx512vbmi`, `avx512vnni` | the feature | never |
| `fp`, `neon` = `asimd`, `atomics` = `lse`, `fphp`, `asimdhp`, `rdm`, `jscvt`, `fcma`, `lrcpc`, `ilrcpc`, `dcpop`, `dcpodp`, `sha3`, `sha512`, `sm3`, `sm4`, `dotprod`, `fhm`, `i8mm`, `bf16`, `frint`, `flagm`, `flagm2`, `sve`, `sve2`, `sveaes`, `svepmull`, `svebitperm`, `svesha3`, `svesm4`, `svei8mm`, `svef32mm`, `svef64mm`, `svebf16`, `dit`, `uscat`, `ssbs`, `sb`, `paca`, `pacg`, `dgh`, `bti`, `mte` | never | the feature (its `HWCAP_` or `HWCAP2_` bit) |

`PASLANG_CPU=base` in the environment makes `CpuHas` and `CpuFeatures`
see the baseline processor, SSE2 on amd64 and NEON on arm64 and nothing
more. The language's own words do not ask them: the vectors, `PopCount`,
the maps' hash and the hash words are chosen when the program is
compiled (`-cpu`, §20), and `-cpu base` compiles their base paths.

`CpuFeatures` holds, on amd64, bit 0 `sse2`, 1 `sse3`, 2 `ssse3`, 3
`sse41`, 4 `sse42`, 5 `popcnt`, 6 `aes`, 7 `pclmul`, 8 `avx`, 9 `fma`, 10
`f16c`, 11 `movbe`, 12 `rdrand`, 13 `avx2`, 14 `bmi1`, 15 `bmi2`, 16
`adx`, 17 `rdseed`, 18 `sha`, 19 `erms`, 20 `avx512f`, 21 `avx512bw`, 22
`avx512vl`, 23 `avx512dq`, 24 `vaes`, 25 `vpclmulqdq`, 26 `gfni`, 27
`lzcnt`, 28 `avx512vbmi`, 29 `avx512vnni` and 30 `cx16`, and, on arm64, `AT_HWCAP`'s low 32 bits with
`AT_HWCAP2`'s low 32 above them: `IsBitSet(CpuFeatures, 22)` is SVE
there.

`examples/machine.paslang`:

```pascal
{ The machine's words, printed so that both machines agree: a feature
  every target has, one that only one has, the features word, the
  cycle counter against its rate, and Amd64 choosing a system call
  number. }
program machine;

var
  c0, c1, n, nr: Integer;
  s: string;

begin
  WriteLn(CpuHas('simd128'), ' ', CpuHas('sse2') <> CpuHas('neon'));   { 1 1: 16-byte vectors everywhere, one machine or the other }
  WriteLn((not CpuHas('simd256')) or CpuHas('avx2'));   { 1: 32-byte vectors are AVX2 }
  if CpuHas('sse2') then
    s := 'sse2'                    { on arm64 this branch is not in the program }
  else if CpuHas('neon') then
    s := 'neon';                   { on amd64 this one is not }
  WriteLn(Length(s));              { 4 }
  WriteLn(IsBitSet(CpuFeatures, 0), ' ', CpuFeatures <> 0);   { 1 1: bit 0 is sse2, or fp on arm64 }
  c0 := CycleCount;
  c1 := CycleCount;
  WriteLn(c1 >= c0, ' ', CycleFreq > 0, ' ', (c1 - c0) / CycleFreq < 1.0);   { 1 1 1 }
  nr := 64;                        { write on arm64 }
  if Amd64 = 1 then
    nr := 1;                       { write on amd64 }
  s := 'written by a system call' + #10;
  n := Syscall(nr, 1, @s[1], Length(s));
  WriteLn(n);                      { 25: the bytes written }
end.
```

prints

```
1 1
1
4
1 1
1 1 1
written by a system call
25
```

`CpuHas` is decided when the program is compiled, so the string `neon`
is nowhere in the amd64 program and `sse2` nowhere in the arm64 one:
what a machine can never run is not in its program. The constant
`Amd64` (§17) says which machine the program is compiled for, as
`CpuHas` says what that machine has; the first picks a system call
number (`write` is 1 on amd64 and 64 on arm64), the second the code for
a feature. Bit 0 of `CpuFeatures` is 1 on both machines because it is
`sse2` on amd64 and `fp` on arm64, each part of the base. Two reads of
`CycleCount` in a row go forward, and their difference divided by
`CycleFreq` (`/`, so a real) is seconds on both.

### Inline assembly

A routine can say what the machine does in its own instructions, one
block for each machine side by side; the one of the machine the program
is compiled for runs, and a block with no partner for that machine is a
compile error:

```
function AddMul(p, q: Integer): Integer;
begin
  asm amd64 (p: in rbx; q: in rcx; Result: out rax)
    movq %rbx, %rax
    imulq %rcx, %rax
    addq %rbx, %rax
  end;
  asm arm64 (p: in x19; q: in x1; Result: out x0)
    mul x0, x19, x1
    add x0, x0, x19
  end;
end;
```

`assembler` is a second spelling of `asm` at the head of a block
(`assembler amd64 (...)`). The partner block is found by the word `asm`
alone, so the block beside it is written `asm arm64 (...)`: two
`assembler` blocks in a row are read as one block with no partner.

The lines go to the assembler as they are written, GNU as syntax (AT&T
on amd64), one instruction or label a line, from the line after the
header to the line that starts with `end`; local labels are numbers
(`1:` and `jnz 1b`). A binding puts a value in a register before the
block (`in`, any expression), a register into a variable after it
(`out`), or both (`inout`):

| Machine | Registers | Take |
|---|---|---|
| amd64 | `rax` `rbx` `rcx` `rdx` `rsi` `rdi` `r8`…`r13` `r15` | an integer, a Boolean, a Char, a pointer, an object, the bits of a real |
| amd64 | `xmm0`…`xmm15`; `ymm0`…`ymm15` | a Single, a Double or a V128; a V256 |
| arm64 | `x0`…`x15`, `x19`…`x27` | as amd64's |
| arm64 | `d0`…`d31`, `s0`…`s31`, `q0`…`q31` (or `v`) | a Double, a Single, a V128 |

`rsp`, `rbp` and `r14` (the running routine) are never bound, nor
`x16`, `x17`, `x18`, `x28`, `x29`, `x30` and `sp`; a block may still use
them if it gives them back. To the rest of the program the block is a
call: nothing stays in a register across it, a narrow variable bound
`out` takes the low bits, and the callee-saved registers the block names
(`rbx`, `r12`-`r15`; `x19`-`x28`, `d8`-`d15`) are saved around it, so it
may use any register. The stack may move by pushes and pops and by
constant adds and subtracts (the collector's maps follow them); a block
that aligns it otherwise is refused. After a block that names a `ymm`
register comes a `vzeroupper`. `safe` code takes no asm.

`examples/assembly.paslang`:

```pascal
{ Inline assembly, one block per machine: the bytes of a word reversed,
  a 128-bit add through the carry into a var parameter, and a loop with
  a local label over the bytes of a string, beside the language's own
  words. }
program assembly;

var
  hi, lo: Integer;

function Swap(x: Integer): Integer;
begin
  asm amd64 (x: in rax; Result: out rax)
    bswapq %rax
  end;
  asm arm64 (x: in x0; Result: out x0)
    rev x0, x0
  end;
end;

function Add128(alo, ahi, blo, bhi: Integer; var sumhi: Integer): Integer;
begin
  asm amd64 (alo: in rax; ahi: in rdx; blo: in rcx; bhi: in rsi; Result: out rax; sumhi: out rdx)
    addq %rcx, %rax
    adcq %rsi, %rdx
  end;
  asm arm64 (alo: in x0; ahi: in x1; blo: in x2; bhi: in x3; Result: out x0; sumhi: out x1)
    adds x0, x0, x2
    adc x1, x1, x3
  end;
end;

function SumBytes(const s: string): Integer;
begin
  asm amd64 (@s[1]: in rsi; Length(s): in rcx; Result: out rax)
    xorl %eax, %eax
  1:
    movzbq (%rsi), %rdx
    addq %rdx, %rax
    incq %rsi
    decq %rcx
    jnz 1b
  end;
  asm arm64 (@s[1]: in x1; Length(s): in x2; Result: out x0)
    mov x0, #0
  1:
    ldrb w3, [x1], #1
    add x0, x0, x3
    subs x2, x2, #1
    b.ne 1b
  end;
end;

begin
  WriteLn(Swap($0102030405060708), ' ', Swap($0102030405060708) = ByteSwap($0102030405060708));   { 578437695752307201 1 }
  lo := Add128(-1, 0, 1, 0, hi);              { all ones plus one: the carry goes up }
  WriteLn(lo, ' ', hi);                       { 0 1 }
  lo := Add128(-1, -1, 1, 0, hi);             { 2^128 - 1 plus one wraps to 0 }
  WriteLn(lo, ' ', hi);                       { 0 0 }
  WriteLn(SumBytes('inline assembly'), ' ', SumBytes('x'));   { 1535 120 }
end.
```

prints

```
578437695752307201 1
0 1
0 0
1535 120
```

An `in` binding is any expression, worked out before the block as any
expression is, its checks included (`@s[1]` of an empty string stops
the program with `index 1 out of range`); an `out` or `inout` binding
is a place: a variable, a field, an element, `p^`, `Result` or a `var`
parameter (`sumhi` above, written back after the block). One register
may serve two bindings, `in` under one name and `out` under another
(`ahi: in rdx; sumhi: out rdx`), and a result comes out of whatever
register the instruction leaves it in. A local label is a number on a
line of its own, `1:`, and a jump names it with a direction, `1b` back
or `2f` forward. The lines between the bindings and `end` go to the
assembler untouched, so an amd64 block is AT&T (`%rax`, `$10`, source
first) and an arm64 block is the Arm syntax (`#0`, destination first).

`examples/bitmap.paslang`:

```pascal
{ The bit words on any variable: a map of 256 slots in 32 bytes, taken
  and given back a bit at a time, and the fields of a Double read from
  its own bits. }
program bitmap;

var
  used: array[0..31] of Byte;       { bit n is slot n }
  i, slot: Integer;
  d: Double;

function Take: Integer;
var
  n: Integer;
begin
  for n := 0 to 255 do
    if IsBitSet(used, n) = 0 then
    begin
      SetBit(used, n, 1);
      Exit(n);
    end;
  Result := -1;
end;

begin
  for i := 1 to 10 do
    slot := Take;
  WriteLn(slot, ' ', PopCount(used));             { 9 10: slots 0 to 9 }
  SetBit(used, 3, 0);                             { give slot 3 back }
  SetBit(used, 7, 0);
  WriteLn(Take, ' ', PopCount(used), ' ', LeadingZeros(used));   { 3 9 246 }
  d := -6.25;
  WriteLn(IsBitSet(d, 63), ' ', GetBits(d, 52, 11) - 1023, ' ', GetBits(d, 0, 52));
  SetBit(d, 63, 0);                               { the sign, as a bit }
  WriteLn(d);
end.
```

prints

```
9 10
3 9 246
1 2 2533274790395904
6.25
```

## 4. Control flow

`examples/control.paslang`:

```pascal
{ Every structured statement: if, case, while, repeat, for, for in,
  break and continue. }
program control;

type
  TDay = (Mon, Tue, Wed, Thu, Fri, Sat, Sun);   { an enumeration }
  TDays = set of TDay;

var
  i, n: Integer;
  d: TDay;
  s: string;
  r: Rune;
  weekend: TDays;

begin
  n := 0;
  for i := 1 to 10 do            { 1..10, inclusive }
    n := n + i;
  WriteLn(n);                    { 55 }
  for i := 3 downto 1 do
    Write(' ', i);               { Write stays on the line }
  WriteLn('');                   {  3 2 1 }
  i := 0;
  while i < 3 do                 { tested before each turn }
    i := i + 1;
  repeat                         { tested after each turn }
    i := i - 1;
  until i = 0;
  WriteLn(i);                    { 0 }
  d := Sat;
  case d of                      { case on an ordinal; else is allowed }
    Mon, Tue, Wed, Thu, Fri: WriteLn('work');
    Sat, Sun: WriteLn('rest');
  end;
  weekend := [Sat, Sun];         { a set of enumeration values }
  if d in weekend then           { in tests a set }
    WriteLn('weekend')
  else
    WriteLn('weekday');
  s := 'año';
  n := 0;
  for r in s do                  { for in over a string walks Unicode scalars }
    n := n + 1;
  WriteLn(n);                    { 3 }
  for i := 1 to 10 do
  begin
    if i = 2 then
      Continue;                  { skip the rest of this turn }
    if i = 5 then
      Break;                     { leave the loop }
    Write(' ', i);
  end;
  WriteLn('');                   {  1 3 4 }
end.
```

prints

```
55
 3 2 1
0
rest
weekend
3
 1 3 4
```

The statements are: assignment, `begin ... end`, `if ... then ... else`,
`case ... of ... else ... end`, `while ... do`, `repeat ... until`,
`for i := a to b do`, `for i := b downto a do`, `for x in s do` over a
string (Unicode scalars, into a `Rune` or an `Integer`), a slice or a
static array (its elements in order, 1.0.134), a set (its members), a
map (its keys, or `for k, v in m do` for keys and values) or a tree
(its keys in order, `for k, v in t do` too; §11), `with r do`, `break`,
`continue`, `exit`, `Halt(n)`, `try`, `raise`, `pas`, `send`, `recv`,
`close`, `select`, `lock` and `once`, and the empty statement
(`if done then ;`). A `for` works out its limit once, before the first
pass: a body that changes the variables of the limit does not change
the loop. The counter stops on the limit and never passes it, so
`for i := 1 to High(Integer)` ends; after a loop that ran to its end
the counter holds the limit, and a loop that does not run leaves it as
it was, as in FPC. The counter may be a `var` parameter or a variable
a closure shares, and so may the variable of `for x in` (1.0.135; the
loop wrote over the address it holds). A `for` whose body calls nothing and holds no other
loop checks for preemption once every 1024 passes, not at each one.
A `for` of a constant count of four passes or fewer with a small body
that neither changes its counter nor takes its address is written out
once per pass with the pass's value in the counter's place, then the
counter is set to the limit as the loop would leave it (1.1.1, §5 on
`-inline`; `-inline 0` keeps the loop).

A `case` label is a constant, a range `'a'..'z'` or a list of them
(`1, 3, 10..19:`); on a string the labels are strings and the whole
string is compared. Two labels that meet are a compile error.

`Write` prints without a newline, `WriteLn` with one, and
`WriteLn(ErrOutput, ...)` writes to standard error. `x:w` pads any value
to `w` columns on the left, and `x:w:d` prints a real with exactly `d`
decimals: `WriteLn(i:5, ' ', x:10:3, ' ', s:8)`; `w` and `d` are any
integer expressions, `x:0:0` rounds to a whole number. `ReadLn(s)` reads a
line into a string. `Inc(v)`, `Inc(v, n)`, `Dec(v)`, `Dec(v, n)` count;
on a real they add or take away the step, `1.0` unless one is given.

`Exit` leaves the current routine, running the `finally` parts on the
way; in a function `Exit(v)` is `Result := v` and then `Exit`. `Halt(n)`
ends the whole program at once with exit status `n`, from any routine,
and plain `Halt` is `Halt(0)`: the other routines are not waited for,
and no `finally` part and no unit's `finalization` runs (what `Write`
printed is already out). A program whose main routine reaches its `end.`
waits for its other routines and exits with 0 (§10).

`ParamCount` is the number of arguments the program was started with,
and `ParamStr(i)` the `i`-th of them as a string, `ParamStr(0)` the
program as it was named on the command line. An `i` outside
`0..ParamCount` gives the empty string (1.0.136; the program stopped
with `nil pointer dereference`).

## 5. Routines

`examples/routines.paslang`:

```pascal
{ Procedures and functions: value, var and out parameters, defaults,
  overloads, forward declarations and nested routines. }
program routines;

function Square(X: Integer): Integer;
begin
  Result := X * X;                      { Result is the function value }
end;

procedure Swap(var A, B: Integer);      { var: the caller's own variables }
var
  t: Integer;
begin
  t := A;
  A := B;
  B := t;
end;

procedure Digits(N: Integer; out Tens, Units: Integer);  { out: results only }
begin
  Tens := N div 10;
  Units := N mod 10;
end;

procedure Greet(const Name: string; Times: Integer = 1);   { a default value }
var
  i: Integer;
begin
  for i := 1 to Times do
    WriteLn('hello ', Name);
end;

procedure Show(N: Integer); overload;   { two routines, one name }
begin
  WriteLn('integer ', N);
end;

procedure Show(S: string); overload;
begin
  WriteLn('string ', S);
end;

procedure Later(N: Integer); forward;   { declared now, written below }

procedure First;
begin
  Later(1);
end;

procedure Later(N: Integer);
begin
  WriteLn('later ', N);
end;

procedure Outer;                        { a nested routine sees the outer locals }
var
  total: Integer;

  procedure Add(K: Integer);
  begin
    total := total + K;
  end;

begin
  total := 0;
  Add(2);
  Add(3);
  WriteLn(total);                       { 5 }
end;

var
  a, b, t, u: Integer;

begin
  WriteLn(Square(7));                   { 49 }
  a := 1;
  b := 2;
  Swap(a, b);
  WriteLn(a, ' ', b);                   { 2 1 }
  Digits(47, t, u);
  WriteLn(t, ' ', u);                   { 4 7 }
  Greet('ana');
  Greet('bo', 2);
  Show(3);
  Show('x');
  First;
  Outer;
end.
```

prints

```
49
2 1
4 7
hello ana
hello bo
hello bo
integer 3
string x
later 1
5
```

A routine's constants, types and nested routines are its own, as in
every Pascal (1.1.12): seen in it and in the routines it nests, gone
after it, so two routines may each have a nested `Sub` or a constant
`K`, and a name declared inside hides the program's of the name. Inside
one routine a variable, a parameter, a constant, a type and a nested
routine may not share a name.

A routine takes up to 32 parameters. `var` passes the caller's variable,
`out` the same but for results only, `const` promises not to change it.
A parameter without them is a copy: a routine that changes its string,
record or array parameter changes its own copy, and the caller's
variable keeps its value (a routine that only reads it pays nothing for
the copy). The elements of a dynamic array are shared, as the array is
a reference. A `const` parameter is the caller's value itself (1.1.1):
nothing is copied or marked on the way in, so a hash of a megabyte
passed as `const` costs the hash alone, and the caller's next write to
that string copies nothing; a routine that assigns to a `const`
parameter, passes it as `var` or `out`, or changes it in any other way
is refused (`S is a const parameter: the routine may not change it or
pass it as var; copy it into a variable first`).
Its address may be taken and it may be viewed (`q as array[0..1] of
Integer`, `Move(S[1], ...)`, a kernel's pointer): the bytes are the
caller's, so a write through that pointer is the caller's too.

**Routines put in place.** A small plain routine of the same unit
costs no call (1.1.1): the compiler copies its body where it is
called. Plain means no nested routine, closure, method or
constructor; parameters, locals and result of an integer, Boolean,
enumeration, subrange or pointer type; a body of assignments, ifs,
cases, `while`, `repeat` and `for` loops (a `for x in` only over a
static array), calls, `Write`, `Inc`, `Dec`, `Halt`, `Sleep`, `Send`,
`Close`, and `Break` or `Continue` in loops of its own, and nothing
else (no `Exit`, `try`, `raise`, `with`, `lock`, `once`, `pas`,
`select`, `ReadLn`, `New`, `asm`, and no `for x in` over a slice, a
string, a set, a map or a tree); a routine
never goes into itself. Small means the body counts `-inline n`
statements and expression nodes or fewer, 40 unless the flag says
otherwise; `inline` after the head puts the routine in whatever its
size, and `-inline 0` is the size level, where every routine exists
once and is called from everywhere. The places taken are a call
statement, an assignment whose right side is the call, and a call
evaluated first in an `if`, a `case`, an assignment's value or place,
the arguments of a call or of `Write`, and the condition of a `while`
or a `repeat`. The routine's parameters become hidden variables of
the caller assigned from the arguments in order (a `var` parameter is
the place given; a value parameter the routine never changes, given a
constant or a variable of the caller's own, is that itself), its
locals hidden variables that start at zero as in the routine, `Result`
the variable the assignment takes; a stop inside reports the routine's
own line, and `DumpLocals` in a routine keeps it a routine. The
output of a program is the same at every level: `testdata/inline1`
runs under `make check` both ways. `-inline-trace` says on the error
output why a routine called in one of those places stays a call; a
routine called only elsewhere stays a call without a line. To debug a routine that goes in
place, compile with `-inline 0`: a debugger then finds the routine and
its variables where the source has them (`-debug`, §17, does so by
itself).

```
$ paslangc -inline-trace prog.paslang
inline: Count stays a call: its body has a statement that stays in its own frame (Exit, try, raise, with, pas, select, ReadLn, New, asm), or names a routine as a value, or calls itself
inline: Big stays a call: measures 88 against -inline 40
```
A default value is a constant expression of the parameter's type (an
integer one converts for a real parameter), `nil` for a pointer, an
object, a class, a routine value, an interface or a slice, and a
constant set in brackets for a set (1.1.6); once a parameter has a
default every later parameter needs one. A method, a constructor, a
class method and an interface's method take defaults as a routine does
(1.1.6); a method's body may repeat its declaration's defaults or leave
them out. A call gives every argument that has no default, and no more. `overload` marks routines that
share a name; the call picks the one whose argument types fit best: the
same types first, then an integer that widens without losing a value
(the nearer width first, the same sign before the other: a `Byte` goes
to `Word` before `Int16`, an `Int8` never to `Word`), then an integer
for a real. A constant with no type of its own is an `Integer`, so
`Put(5)` takes `Put(x: Word)` before `Put(x: Byte)`, and `Int8` before
`Byte`; `Put(300)` takes `Word`. A `var` parameter takes its own type
alone. Two routines that fit equally well are an ambiguous call.
Beyond those, an argument fits every parameter a call converts it into,
priced as Free Pascal ranks it: a subrange for its host, a list in
brackets for an `array of const` or for a set of its kind (the two
tie), then for a slice, `nil` for a reference, a pointer for `Pointer`,
an object for an ancestor (the nearest first), a class reference for
another (they tie), a `Char` for a string, an object for an interface
it implements or for `Pointer` (they tie). `F('x')` takes `F(C: Char)`
before `F(const S: string)`; `F(k)` with a `TGrand` takes `F(X: TKid)`
before `F(X: TBase)`; `F([1, 2])` takes `array of const` before `array of
Int64`. A list of elements of more than one kind, `[n, 'x']`, is a list:
an `array of const` takes it, a set does not (1.1.16, P141; only the
exact types, the integers and the reals matched, so `F(c)` with a Char
for `F(const S: string)` found no overload). `forward` declares a routine before its
body; the later header must repeat the same signature.

A routine is also a value. The type is written the way the header is:

```pascal
type
  TLess = function(A, B: Int64): Boolean;
  TAct = procedure(N: Integer);

var
  f: TLess;
begin
  f := @Up;              { @ takes the routine }
  if f(3, 7) then ...    { the call goes through the value }
  f := nil;              { and nil is a value of it }
```

It is sixteen bytes (1.0.133): the address of the code and an
environment, nil for a routine taken with `@`; a closure keeps its
captured variables there. The signature belongs to the type, so the call
knows what to pass and what comes back. `Assigned(f)` is `f <> nil`, as
for a pointer, an object or a slice. `@` of a nested routine is a
closure (1.0.134): the value carries the link to its parent's
variables. Such a
value can be a parameter, a field of a record, an element of an array,
and what a function gives back, and a call can be written on any of
them, including on what another call returned. At most six arguments
travel through one on amd64 and eight on arm64; beyond that the
compiler refuses rather than pass them wrongly. `passort` takes one as
the order to sort by, which is what Go's `sort.Slice` does.

`procedure(x: Integer) of object` and `function(x: Integer): T of
object` are method values: sixteen bytes, the code and `Self`. The type
keeps its signature, as a routine value's does (1.0.135; it was untyped
and a function of object was refused): a call through one counts its
arguments, converts them as a routine's call does and gives back the
function's answer, in an expression too, and a call can be written on a
field or an element that holds one, `b.OnJoin('x', 1)`. `obj.M` of a
method that takes parameters is its method value, and `@obj.F` that of
a function with none, which `obj.F` alone calls. Any method value still
goes into any other. A call written without `(` through a routine
value, a method value or `obj.M` whose type takes parameters is an
error (1.0.135; it ran on whatever the registers held). A call through one passes a string, a record or a
slice as every other call does (on amd64 it passed a string's first
word alone until 1.0.133).

### array of const

A parameter of type `array of const` takes a list in brackets of values
of any simple kind, as `Format` does (1.1.5):

`examples/varargs.paslang`:

```pascal
{ array of const: a routine that takes a list of values of any simple
  kind, each with its kind, and prints them as a log line. }
program varargs;

procedure Log(const Level: string; const Args: array of const);
var
  i: Int64;
begin
  Write('[', Level, ']');
  for i := 0 to High(Args) do
    case Args[i].VType of
      vtInteger: Write(' ', Args[i].VInteger);
      vtBoolean: Write(' ', Args[i].VBoolean);
      vtChar: Write(' ', Args[i].VChar);
      vtExtended: Write(' ', Args[i].VExtended:0:2);
      vtAnsiString: Write(' ', Args[i].VAnsiString);
      vtObject: Write(' <', Args[i].VObject.ClassName, '>');
      vtClass: Write(' class ', Args[i].VClass.ClassName);
      vtPointer: Write(' pointer');
    else
      Write(' kind ', Args[i].VType);
    end;
  WriteLn;
end;

procedure Warn(const Args: array of const);
begin
  Log('warn', Args);                  { passed on as it came }
end;

type
  TJob = class
  end;

var
  job: TJob;
  n: Int64;

begin
  job := TJob.Create;
  n := 42;
  Log('info', ['started', n, 'jobs,', 0.75, 'load']);
  Log('info', [job, TJob, 'x', True, nil]);
  Warn(['disk at', 91, '%']);
  Log('empty', []);
end.
```

prints

```
[info] started 42 jobs, 0.75 load
[info] <TJob> class TJob x 1 pointer
[warn] disk at 91 %
[empty]
```

The routine sees an array of `TVarRec`, indexed from 0: `VType` says the
kind of each value and the field of that kind holds it.

| Kind | Values | Field |
|---|---|---|
| `vtInteger` | every integer, of any width, an enumeration | `VInteger: Int64` |
| `vtBoolean` | a Boolean | `VBoolean` |
| `vtChar` | a `Char`, a one-character literal | `VChar` |
| `vtExtended` | a `Double`, a `Single` (widened) | `VExtended: Double` |
| `vtQuad` | a `Quad` | `VQuad` |
| `vtAnsiString` | a string | `VAnsiString: string` |
| `vtPChar` | a `PChar` | `VPChar` |
| `vtPointer` | a pointer, `nil`, a routine value (its code) | `VPointer` |
| `vtObject` | an object | `VObject: TObject` |
| `vtClass` | a class, a class reference | `VClass: TClass` |
| `vtInterface` | an interface (its object) | `VInterface: Pointer` |

`TVarRec`, the kinds and their Free Pascal numbers are words of the
language; the kinds paslang does not make (`vtInt64`, `vtWideString`,
…) are there with their numbers for code that names them. The value is
in the record itself, a string's two words and a `Quad` too, where Free
Pascal keeps a pointer to a copy.

The list is built in the caller's frame, not on the heap, and lives for
the call: the routine reads it, indexes it, measures it (`Length`,
`High`), walks it (`for x in`) and passes it on to another `array of
const`, and nothing else. Keeping it (`x := Args`), taking its address,
a closure that holds it, `pas` with one, and a `var` one are compile
errors. A slice of `TVarRec` of the program's goes where an `array of
const` goes too. `array of const` is only a parameter's type.

### Closures

An anonymous routine is a value, in Delphi's syntax (1.0.134):
`function(x: Integer): Integer begin ... end` or `procedure ... begin
... end`, with a `var` section before its `begin` when it needs one. It
keeps the variables of the routines around it by reference: the routine
and its closures share them, and a closure outlives the routine that
made it.

```pascal
type
  TGen = function: Integer;

function Counter(Start: Integer): TGen;
var
  n: Integer;
begin
  n := Start;
  Result := function: Integer
  begin
    n := n + 1;
    Result := n;
  end;
end;

g := Counter(10);
WriteLn(g(), ' ', g());          { 11 12: n lives on after Counter }
```

- A nested routine is a value too, `@Bump`, and `pas Work(a)` runs one
  as a routine of its own; both keep their parent's variables as a
  closure does. `pas procedure begin ... end` runs a closure (§10).
- A counter a closure made in the loop uses is that pass's own, as in
  Go 1.22: `for i := 0 to 3 do fs[i] := function: Integer begin Result
  := i end` gives 0, 1, 2, 3, not four times 3. A change the body makes
  to it still steers the loop. It holds for `for x in` too.
- A routine nested two deep reaches its grandparent's variables (it said
  unknown identifier before 1.0.134).
- A `var` parameter cannot be kept (a closure may outlive the variable
  it points at): copy it to a local. `Result` is not shared with the
  routines inside a routine that has a closure, and a counter a closure
  keeps cannot count another loop inside it.

What it costs: a routine with a closure anywhere inside keeps the
variables its nested routines use in a heap block of its own, made once
per call (one allocation); it reaches them through their field, as a
`var` parameter, and gives the block to its nested routines as their
link. A closure's value is its code and that block. A routine with no
closure inside is compiled as before. A closure made in a loop whose
counter it keeps allocates a small cell each pass.

`examples/closures.paslang` puts them to work: a closure returned, one
passed, two that share a variable, and one run with `pas`:

```pascal
{ Closures: an anonymous routine keeps the variables around it by
  reference, for as long as the value lives. One returned from a
  function, one passed to a routine, two that share a variable, and
  one started with pas. }
program closures;

type
  TFn = function(X: Integer): Integer;
  TAct = procedure(X: Integer);

function Adder(N: Integer): TFn;          { N, a value parameter, is kept }
begin
  Result := function(X: Integer): Integer begin Result := X + N end;
end;

function Compose(F, G: TFn): TFn;         { kept: two routine values }
begin
  Result := function(X: Integer): Integer begin Result := G(F(X)) end;
end;

procedure Each(const A: array of Integer; Act: TAct);
var
  i: Integer;
begin
  for i := 0 to High(A) do
    Act(A[i]);                            { the call goes through the value }
end;

procedure Tally(out Add: TAct; out Total: TFn);
var
  sum: Integer;                           { one variable, two closures }
begin
  sum := 0;
  Add := procedure(X: Integer) begin sum := sum + X end;
  Total := function(X: Integer): Integer begin Result := sum end;
end;

var
  add5, both, total: TFn;
  add: TAct;
  n: Integer;
  wg: waitgroup;

begin
  add5 := Adder(5);
  both := Compose(add5, function(X: Integer): Integer begin Result := X * 2 end);
  WriteLn(add5(1), ' ', both(1));         { 6 12 }
  n := 0;
  Each([1, 2, 3], procedure(X: Integer) begin n := n + X end);
  WriteLn(n);                             { 6 }
  Tally(add, total);                      { Tally returned; sum lives on }
  add(10);
  add(5);
  WriteLn(total(0));                      { 15 }
  wg.Add(1);
  pas procedure begin n := n * 10; wg.Done end;   { a closure as a routine }
  wg.Wait;
  WriteLn(n);                             { 60 }
end.
```

prints

```
6 12
6
15
60
```

What a closure keeps is the variable, not its value at the time:
`Tally`'s `sum` is written through `add` and read through `total` after
`Tally` has returned, and `Adder`'s `N`, a value parameter, is kept the
same way (a `var` or `out` parameter cannot be: `X is a var parameter
of Make, which has a closure inside: a closure may outlive the variable
it points at; copy it to a local`). The variables live as long as a
value that keeps them does: their block is on the heap, and the
collector takes it back when the last closure over it is gone (§17).
One call, one block: the two closures one call of `Tally` makes share
`sum`, and two calls of `Adder` keep two `N`s. An anonymous routine
written where no routine encloses it, as `Each`'s argument is, keeps
nothing of its own: it names the globals as every routine does. A
routine value made of an anonymous routine goes wherever `@Name` goes:
`Compose` keeps two in its closure and calls through them, `Each` takes
one as a parameter, and `Tally` gives two back through `out`
parameters.

## 6. Records, pointers, arrays and slices

`examples/records.paslang`:

```pascal
{ Records, pointers, fixed arrays and slices. }
program records;

type
  TPoint = record
    X, Y: Integer;
  end;
  PNode = ^TNode;                    { a pointer type may name a type later in the same section }
  TNode = record
    Value: Integer;
    Next: PNode;
  end;

var
  p: TPoint;
  head, n: PNode;
  fixed: array[1..3] of Integer;     { fixed bounds, no header }
  xs: array of Integer;              { a slice: pointer, length, capacity }
  i, sum: Integer;

begin
  p.X := 3;
  p.Y := 4;
  with p do                          { fields without the prefix }
    WriteLn(X * X + Y * Y);          { 25 }
  head := nil;
  for i := 1 to 3 do                 { build a list on the heap }
  begin
    New(n);                          { New allocates the pointed-to record }
    n^.Value := i * 10;
    n^.Next := head;
    head := n;
  end;
  sum := 0;
  n := head;
  while n <> nil do
  begin
    sum := sum + n^.Value;
    n := n^.Next;
  end;
  WriteLn(sum);                      { 60 }
  fixed[1] := 1;
  fixed[2] := 2;
  fixed[3] := 3;
  WriteLn(fixed[1] + fixed[2] + fixed[3], ' ', Length(fixed));   { 6 3 }
  SetLength(xs, 2);                  { slices are 0-based and grow with SetLength }
  xs[0] := 5;
  xs[1] := 6;
  SetLength(xs, 3);                  { the old elements stay }
  xs[2] := 7;
  sum := 0;
  for i := 0 to High(xs) do
    sum := sum + xs[i];
  WriteLn(sum, ' ', Length(xs), ' ', High(xs));   { 18 3 2 }
end.
```

prints

```
25
60
6 3
18 3 2
```

Record fields lie in source order, each at its natural alignment (a
`Word` on 2, an `Int32` on 4, an `Integer` on 8; a field that holds a
pointer always on 8, where the collector's maps look for it), and the
record's size rounds up to its most aligned field: `B: Byte; W: Word;
I: Int32` puts `W` at 2 and `I` at 4 and is 8 bytes. A trailing
`case Kind: Integer of` overlays variants. `New(p)` allocates the
pointed-to type and `GetMem(p, n)` allocates `n` bytes (`GetMem(p, n, 0)`
for bytes that hold no pointer). As a function, `GetMem(n)` and
`GetMem(n, 0)` give the new block as a `^Integer`, to be seen through
any view: `q := PByte(GetMem(64, 0))`. `FreeMem(p)` does nothing, the
collector gives back what nothing reaches. `Move(a, b, n)` copies `n` bytes
between two variables; to copy through pointers write `Move(p^, q^, n)`.
`FillChar(x, n, v)` writes the byte (or `Char`) `v` `n` times from `x`
on. `Low`, `High` and `Length` work on static arrays, slices and
strings: a string's `Low` is 1, its first index, and its `High` its
length (1.0.136; `Low` gave 0). `Length` also counts the entries of a
map, a tree or a heap and is 1 for a `Char`, and `Low(h)` of a heap is
its least element (§11). `High(x)` and `Low(x)` of an ordinal value are its
type's bounds, as `High(Byte)` is 255. Anything else is a compile error
(1.0.136; `Length(5)` gave an address, `Length` of a real 1, and `High`
of a map nonsense). A slice grows
with `SetLength` and keeps its old elements; the new ones are zero, even
when the block had room, and growing one slice never shows through
another that shares its block.

The variant part is written as in FPC and closes the record: `case
Kind: TKind of kInt: (I: Integer); kStr: (S: string); kPair: (A, B:
Int32);`. The tag, when it has a name, is a field like the others, and
every variant's fields start right after it, one variant over another:
with `A := 1` and `B := 2`, `I` reads both at once, 8589934593. The
record is as long as its longest variant needs, and nothing checks the
tag: `A` after `I := 5` is 5.

`Append(s, a, b)` is `s` with `a` and `b` after its elements, a slice of
`s`'s type, as Go's `append` (1.0.132); `Append(s, u)` with `u` of `s`'s
type adds `u`'s elements, `s`'s own too. `Cap(s)` is its capacity. A
list in brackets where a slice goes is a new slice of it: `u := [10,
20, 30]`, `Total([1, 2, 3])`, `g := Append(g, [1, 2])`; `[]` is empty.
So `Append(s, [a, b])` adds `a` and `b` (1.0.136; the list went in as
one set bitmask, and the example below printed `1 2 3 9 1049600`), and
to a slice of slices `[a, b]` is one new element, a slice of its own.

```pascal
s := Append(s, 1, 2, 3);      { 3: 1 2 3 }
t := s;
t := Append(t, 4);            { t: 1 2 3 4 }
s := Append(s, 9);            { s: 1 2 3 9, t keeps its 4 }
s := Append(s, [10, 20]);     { a literal, then all its elements }
```

`Append` grows as `SetLength` does: in place only from the end its block
reached, its frontier, with twice the length as capacity, so a loop of
`s := Append(s, x)` costs a copy now and then, not each time; any other
slice of the block keeps what it saw (`t` above), where Go's `append`
would have written over its `t[3]`. The elements are evaluated first, in
order, and stored as `:=` stores them (a string is shared, a record
copied); `Append`'s result is a value like any other, for an argument
or an element too.

`examples/slices.paslang` shows what a slice shares and what it does
not:

```pascal
{ Slices: a function that gives one back, Append in a loop, for in,
  two headers on one block, a slice of a slice, a value parameter and
  a var one, and a copy with a block of its own. }
program slices;

function Range(A, B: Integer): array of Integer;
var
  i: Integer;
begin
  Result := nil;                          { Length 0, High -1 }
  for i := A to B do
    Result := Append(Result, i);
end;

procedure Twice(A: array of Integer);     { a copy of the header }
begin
  A[0] := A[0] * 2;                       { the elements are the caller's }
  A := Append(A, 99);                     { the caller's header does not see it }
end;

procedure Grow(var A: array of Integer; X: Integer);   { var: the header too }
begin
  A := Append(A, X);
end;

var
  s, t, u: array of Integer;
  x, n: Integer;

begin
  s := Range(1, 5);
  WriteLn(Length(s), ' ', High(s), ' ', s[High(s)]);   { 5 4 5 }
  t := s;                                 { one block, two headers }
  t[0] := 10;
  u := s[1..3];
  u := u[1..2];                           { a slice of a slice: s[2..3] }
  u[0] := 30;
  WriteLn(s[0], ' ', s[2], ' ', Length(u), ' ', u[1]);  { 10 30 2 4 }
  Twice(s);
  WriteLn(s[0], ' ', Length(s));          { 20 5 }
  Grow(s, 9);
  WriteLn(Length(s), ' ', s[High(s)]);    { 6 9 }
  n := 0;
  for x in s do
    n := n + x;
  WriteLn(n);                             { 20 + 2 + 30 + 4 + 5 + 9 = 70 }
  t := nil;
  WriteLn(Length(t), ' ', High(t), ' ', t = nil);      { 0 -1 1 }
  t := Append(t, s);                      { a copy: a block of its own }
  t[0] := 0;
  WriteLn(s[0], ' ', Length(t), ' ', High(t));         { 20 6 5 }
end.
```

prints

```
5 4 5
10 30 2 4
20 5
6 9
70
0 -1 1
20 6 5
```

`t := s` copies the header, not the block: `t[0] := 10` shows in `s`.
So does a write through a value parameter (`Twice`), while the `Append`
inside it moves only the callee's own header; a routine that must grow
the caller's slice takes it as `var` (`Grow`). Growth in place keeps
the shared elements shared: after `t := s`, `SetLength(t, 8)` when
`s`'s block had room, then `t[1] := 20`, `s[1]` is 20 too; the length
is `t`'s own, the elements up to `s`'s length are still one. A copy
with a block of its own is `t := nil; t := Append(t, s)`: `Append` to a
nil slice allocates, and so does `Copy(xs, i, n)` (and `Copy(xs, i)`,
to the end), whose elements are a new slice's, as Free Pascal's
(1.1.11): 0-based, a start below 0 shortening the count, a count cut
to what is left. `Insert(x, xs, i)` (an element, a slice or a list in
brackets, before `xs[i]`) and `Delete(xs, i, n)` make a new slice for
`xs`, so one that shared its elements keeps them; `s[i..j]` shares
(below); it can be taken again
of what it gave, so `u := s[1..3]; u := u[1..2]` is `s[2..3]`. A nil
slice is a slice: `Length` 0, `High` -1, `= nil` true, `for x in` over
it does nothing, and `Append` or `SetLength` gives it a block; a
function that builds one starts with `Result := nil` or `Result := []`.

### Pointers and views

A pointer is an address; what it points at has the type of the view it
is seen through where it is used. `Pointer` is untyped: its target has a
type only through a view, and `p^` alone goes only to `Move`,
`FillChar` and the bit words (§3). These pointer types are predefined, each `^` of its type:
`PByte`, `PWord`, `PDWord`, `PInt8`, `PInt16`, `PInt32`, `PUInt8`,
`PUInt16`, `PUInt32`, `PShortInt`, `PSmallInt`, `PLongWord`,
`PInteger`, `PInt64`, `PSingle`, `PDouble`, `PQuad`, `PBoolean`,
`PPointer` and `PChar`; a program that declares one of these names
itself uses its own.

- `PT(q)` sees any pointer (or an address held in an `Integer`) as a
  pointer to `T`; `^T(q)` does the same in line for any type:
  `^TRec(p)^.W`.
- `T(q^)` is the `T` at that address, a variable (`Word(p^) := 7` writes
  two bytes), and `TRec(q)` of a `Pointer` is `TRec(q^)`. Through a
  typed pointer the conversion converts, as in FPC: with `pb: PByte`,
  `Integer(pb^)` is the byte widened, `PInteger(pb)^` the 8 bytes there.
- Arithmetic counts elements of the view: `PDWord(p) + 1` is 4 bytes
  on, `p + 1` of a `Pointer` 1 byte, `p[i]` the element `i` on. As a
  result only (`q := PDWord(p) + 1`) or for good (`Inc(PDWord(p))`,
  `Inc(PWord(p), 3)`, `p := PByte(p) + 1`). `q - r` of two pointers of
  one type is the elements between them (two types need one view);
  `=`, `<>`, `<` and `>` compare addresses.

`examples/pointers.paslang`:

```pascal
{ A pointer is an address, seen as any type where it is used: views,
  arithmetic in elements of the view, View over raw memory, slices that
  share elements, and the object an address is in. }
program pointers;

type
  TPair = record
    B: Byte;
    W: Word;
    I: Int32;
  end;

var
  x: Integer;
  p, q: Pointer;
  pb: PByte;
  d, part: array of Integer;
  v: array of Byte;
  i, n: Integer;

begin
  x := $0807060504030201;
  p := @x;                                    { an untyped address }
  WriteLn(PByte(p)^, ' ', PWord(p)^, ' ', PDWord(p)^);
  WriteLn((PByte(p) + 1)^, ' ', (PWord(p) + 1)^, ' ', PWord(p)[3]);
  WriteLn(TPair(p^).W, ' ', ^TPair(p)^.I);    { a record seen at that address }
  pb := PByte(p);
  WriteLn(Integer(pb^), ' ', PInteger(pb)^ = x);   { the byte converted; 8 bytes seen }
  q := p;
  Inc(PDWord(q));                             { for good: 4 bytes on }
  WriteLn(PByte(q) - PByte(p), ' ', PDWord(q) - PDWord(p));
  v := View(PByte(p), 8);                     { the 8 bytes of x, index checked }
  n := 0;
  for i := 0 to High(v) do
    n := n + v[i];
  WriteLn(Length(v), ' ', n);
  SetLength(d, 6);
  for i := 0 to 5 do
    d[i] := i * 10;
  part := d[2..4];                            { elements 2 to 4, shared }
  part[0] := 99;
  WriteLn(Length(part), ' ', d[2], ' ', part[2]);
  WriteLn(MemSize(@d[0]) >= 48, ' ', MemBase(@d[3]) = MemBase(@d[0]));
end.
```

prints

```
1 513 67305985
2 1027 2055
1027 134678021
1 1
4 1
8 36
3 99 40
1 1
```

`View(p, n)` is the `n` elements `p` points at as a slice (`array of T`,
bytes for a `Pointer`), Go's `unsafe.Slice`; its index is checked like
any slice's, and a length below 0 stops the program. `d[i..j]` is
elements `i` to `j` of a slice or a static array as a slice that shares
them, checked where it is made (`index 9 out of range [0..4]`); it has
capacity 0, so `SetLength` gives it a block of its own. `s[i..j]` of a
string is a copy, `Copy(s, i, j - i + 1)`. `MemBase(p)`, `MemSize(p)`
and `MemEnd(p)` are the object an address is in (a heap block, the
routine's stack, the globals; 0 when none), to check by hand.

A pointer one past the end of a heap block is allowed (a walk may end
there), but it points where the next block starts, so it does not keep
its own block alive: while such a pointer is in use, keep a pointer to
the block itself, as a walk that also holds its start does.

### Checking pointers

By default a pointer step or access is the instruction and nothing more.
Two checks are there when wanted.

Where the code itself names the object and the offset is a constant
(`@x`, a field or a constant element of one, a constant step on from
it), an access outside the object is an error when compiling, with or
without `-checkptr`:

```
paslangc: pointer outside its object: x has 8 bytes and this reaches bytes 8 to 8 at 6:27 in reach.paslang
```

That covers `(PByte(@x) + 8)^` of an 8-byte `x`, `PInteger(@b)^` of a
`Byte`, `^TRec(@x)^` of a smaller `x`, and `FillChar(r, 100, 0)` or
`Move(x, a, 16)` past `r` or `x`. A step alone never is
(`PByte(@x) + 8` is a fine end pointer), and a var parameter is never the
whole object: it may be one element of a bigger array.

`paslangc -checkptr` checks every step and access while the program
runs: `p + n`, `Inc`, `Dec`, `p^`, `p[i]` and every view must stay in
the object the pointer came from (a heap block, the routine's stack, the
globals), or the program stops with `pointer outside its object at line
N`. A step may reach one past the end, as in C, so a walk can end there
and come back; an access there is outside, and `p[i]` and `(p + n)^`
are held to `p`'s own object even when another block follows it. One
case is left to chance: a pointer stepped to the very end of a block and
then read with `p^` is checked against the block that follows, when one
does. The option is chosen per unit (its `.pi` says `CHECKPTR`). The
last object found is kept in the routine's record, so a loop that only
walks a pointer takes about 11 times its time, a list walk about 5 and
code without pointers the same (`make bench` measures it on `b8ptr`);
without the option no check is emitted at all. `safe` code (§19) has no
raw pointer work to check.

## 7. Classes and interfaces

`examples/classes.paslang`:

```pascal
{ Classes: fields, constructors, methods, virtual and override, inherited,
  a property, is and as, and an interface. }
program classes;

type
  IShape = interface
    function Area: Integer;
  end;

  TShape = class(IShape)
    FName: string;
    constructor Create(const AName: string);
    function Area: Integer; virtual;
    function Describe: string;
    property Name: string read FName write FName;
  end;

  TSquare = class(TShape)
    FSide: Integer;
    constructor Create(ASide: Integer);
    function Area: Integer; override;
  end;

constructor TShape.Create(const AName: string);
begin
  FName := AName;
end;

function TShape.Area: Integer;
begin
  Result := 0;
end;

function TShape.Describe: string;
begin
  Result := FName;
end;

constructor TSquare.Create(ASide: Integer);
begin
  inherited Create('square');        { the parent constructor first }
  FSide := ASide;
end;

function TSquare.Area: Integer;
begin
  Result := FSide * FSide;
end;

var
  s: TShape;
  q, back: TSquare;
  a: IShape;

begin
  q := TSquare.Create(5);
  s := q;                            { a descendant fits the parent type }
  WriteLn(s.Describe, ' ', s.Area);  { the override runs: square 25 }
  s.Name := 'box';                   { the property writes the field }
  WriteLn(s.Name);
  if s is TSquare then               { is asks the class at run time }
  begin
    back := s as TSquare;            { as casts, checked }
    WriteLn(back.FSide);             { 5 }
  end;
  a := q;                            { through the interface }
  WriteLn(a.Area);                   { 25 }
end.
```

prints

```
square 25
box
5
25
```

A class value is one pointer to an instance whose first word points to
the method table. `class`, `class(Parent)` and `class(Parent, IFace)`
declare one; a class with no parent may list interfaces directly.
`TName.Create(...)` allocates and runs the constructor chosen by the
argument count and types, most derived first, so a descendant may give
`Create` another signature than its parent. A class without a
constructor still has `Create`. `virtual` and `override` dispatch through
the table; `virtual; abstract;` leaves the body to a descendant, and
creating a class that still has an abstract method is an error.
`inherited Name(args)` calls the parent's version. A `property` reads
and writes a field or a method and may be indexed. `is` tests and `as`
casts. A method value, `procedure of object` or `function ... of
object`, carries the code and `Self` (§5). A call through an interface
takes its arguments as every other call does: a string, a record, a
slice, a real, and more than five of them (1.0.135; it passed one word
an argument, so a string lost its length, and at most five). An
interface's method takes `const`, `var` and `out` parameters as a
class's does (1.0.136; `const` was a syntax error there, and a `var`
argument went as its value).

An object goes wherever its interface goes: into a variable, as an
argument (`Show(sq)` for `procedure Show(S: IShape)`), as a function's
result or `Exit(obj)`, into an element or a field. The interface value
is the object and its class's table for that interface. A call through
it runs the object's own method, and a virtual one is looked up in the
object's table, so a descendant's override runs as it does through the
class. A class goes only into an interface that it or an ancestor
lists; an interface goes where its parent interface goes, but an object
whose class lists `IMore` does not go into an `IBase` variable, as in
Free Pascal (`TA does not implement IBase at 24:17`) (1.1.15, P140; only
an assignment bound an object, an argument went as the object alone
and a call through it died, and the class's method ran, not the
override).

`TFoo = class(TParent);` declares a class with nothing of its own, the
parent's members and nothing else, as Object Pascal does; a family of
exception classes is written so (`EConvertError = class(Exception);`).
`TFoo = class;` and `IFoo = interface;` declare a class or an
interface forward, so that types can name each other: a later type
declaration in the same declarations (a program's, a routine's, or a
unit's interface part) declares it whole, and it is the same type.
Until then it can be named, as a field's, a parameter's or a result's
type, in `class of TFoo` and in `^TFoo`, but it is no parent and no
interface a class implements; declarations that end with one still
forward, a class declared forward and completed as an interface or as
a record, and a class that names itself as its parent are errors
(`forward type TFoo not resolved at 3:3`). The whole declaration may
come after a `var` or a routine, as Free Pascal allows (1.1.14, P139;
the short form was `class member`, and nothing could be declared
forward).

```pascal
type
  TNode = class;                  { forward: TList names it }
  TList = class
    First: TNode;
  end;
  TNode = class                   { the same type, whole }
    Next: TNode;
    Owner: TList;
  end;
  TMark = class(TNode);           { nothing of its own }
```

`is` never stops: of `nil` it is False for every class. `as` stops the
program when the object is not of the class named (`a` holding a `TC`,
`a as TB`), with `paslang: as failed` on standard error and exit
status 1, and no line is named; `nil as T` is `nil` and goes on. So a
cast that may fail asks `is` first, and a bare `as` says the object is
expected to be of that class.

Inside a method, `Self` is the object the method was called on: a field
is `FSide` or `Self.FSide`, and `Result := Self` gives the object back.
It is a hidden local of every method, so a local of that name is a
`duplicate identifier Self`.

`public`, `published`, `protected`, `private`, `strict protected` and
`strict private` begin sections of a class, and the compiler holds to
them (1.0.137; they restricted nothing before). A member before any
section is public. A `private` member is reached anywhere in the unit
(or program) that declares the class; a `strict private` one only
inside the methods of that class. A `protected` member is reached in
the declaring unit and inside the methods of the class's descendants,
in any unit; a `strict protected` one only inside those methods. The
rules hold for fields, methods, constructors, properties and method
values, through `Self` written or left out, through another instance of
the class, in nested routines and closures of a method, and in `with`.
A member out of reach is an error that names it: `FBalance is private
to TAccount at 12:9`. As before, a property declared after `private` or
`protected` has no run-time type information, and every other property
is published (below). A unit's `.pi` carries each member's section, and
a descendant declared in another unit keeps its parent's virtual
methods, interfaces and properties (1.0.137; they were lost, and a
descendant in another unit reused the parent's virtual slots).

A destructor is a method like the others: `destructor Destroy` runs
when it is called, `obj.Destroy`, and never on its own. `obj.Free`
calls `Destroy` when `obj` is not `nil` (1.0.137; it did nothing): the
class's own or an ancestor's, through the table when it is virtual;
`obj` is worked out once, so `List[Next].Free` reads the index once. A
class with no `Destroy` makes `Free` do nothing, and a class that
declares its own method named `Free` calls that. `pas obj.Free` runs the
destructor as a routine. `inherited Destroy`, `inherited Create` or a
bare `inherited` with no ancestor that has the method does nothing
(1.0.137; it was an error). An object's memory goes back when nothing
points to it any more (§17), destructor or not; there is no reference
counting.

### TObject, the root of every class

A class declared with no parent descends from `TObject`, which the
core unit `pasobject` declares (§15): every object has what it has.

| Member | What it does |
|---|---|
| `constructor Create` | makes the object; a class without a constructor of its own still has it |
| `destructor Destroy; virtual` | does nothing; a class overrides it, and `Free` calls it |
| `procedure AfterConstruction; virtual` | called on a new object when its constructor has run, when the class overrides it |
| `procedure BeforeDestruction; virtual` | called before `Destroy` when `Free` or an outermost `x.Destroy` ends the object; an `inherited Destroy` does not call it |
| `function Equals(Obj: TObject): Boolean; virtual` | `Obj` is the same object |
| `function GetHashCode: Int64; virtual` | the object's address |
| `function ToString: string; virtual` | the class's name |
| `ClassName` | the name of the object's class, as declared |
| `ClassNameIs(name)` | the name compared with ASCII letters in either case |
| `InstanceSize` | the bytes an object of the class takes |

The class words (`ClassName`, `ClassNameIs`, `InstanceSize`) read the
object's method table, which carries the class's name, as a string
literal lies (so `ClassName` gives it back without a copy), and the
size of an instance; inside a method they are `Self`'s. `TObject`'s own
`Create` and `AfterConstruction` do nothing, so no call is written for
them: a constructor costs what its own body costs. A method declared
again with the signature of an inherited virtual one overrides it, with
`override` written or not, so `destructor Destroy;` in any class is the
one `Free` runs. The memory of an object goes back to the collector
when nothing points to it, whatever the destructor does. An object of
any class can be raised (§9).

### Class methods, class references and class variables

A class can be worked with before any object exists (1.1.4):

`examples/registry.paslang`:

```pascal
{ Class methods and class references: a registry of shape classes
  that makes an object of whichever class a name picks, through a
  virtual constructor, and counts them in a class variable. }
program registry;

type
  TShape = class
  private
    class var FMade: Int64;           { one for the class and its descendants }
  public
    Size: Int64;
    constructor Create(ASize: Int64); virtual;
    class function Kind: string; virtual;   { Self is the class }
    class function Describe: string;
    class property Made: Int64 read FMade;
    function Area: Int64; virtual;
  end;

  TSquare = class(TShape)
    class function Kind: string; override;
    function Area: Int64; override;
  end;

  TTriangle = class(TShape)
    class function Kind: string; override;
    function Area: Int64; override;
  end;

  TShapeClass = class of TShape;      { holds TShape or a descendant }

constructor TShape.Create(ASize: Int64);
begin
  Size := ASize;
  FMade := FMade + 1;
end;

class function TShape.Kind: string;
begin
  Result := 'shape';
end;

class function TShape.Describe: string;
begin
  Result := ClassName + ' draws a ' + Kind;   { the class it was called for }
end;

function TShape.Area: Int64;
begin
  Result := 0;
end;

class function TSquare.Kind: string;
begin
  Result := 'square';
end;

function TSquare.Area: Int64;
begin
  Result := Size * Size;
end;

class function TTriangle.Kind: string;
begin
  Result := 'triangle';
end;

function TTriangle.Area: Int64;
begin
  Result := Size * Size div 2;
end;

var
  classes: array[0..2] of TShapeClass;

function Find(const Name: string): TShapeClass;
var
  i: Int64;
begin
  Result := nil;
  for i := 0 to 2 do
    if classes[i].Kind = Name then
      Result := classes[i];
end;

var
  c: TShapeClass;
  s: TShape;

begin
  classes[0] := TShape;               { a class is a value }
  classes[1] := TSquare;
  classes[2] := TTriangle;
  WriteLn(TSquare.Describe);
  c := Find('triangle');
  s := c.Create(6);                   { an object of the class c holds }
  WriteLn(s.ClassName, ' ', s.Area);
  s := Find('square').Create(5);
  WriteLn(s.ClassName, ' ', s.Area, ' ', Ord(s.InheritsFrom(TShape)));
  WriteLn(TShape.Made, ' made');
end.
```

prints

```
TSquare draws a square
TTriangle 18
TSquare 25 1
2 made
```

- `class function` and `class procedure` declare a class method; its
  body says `class` too (`class function TShape.Kind`). Inside it `Self`
  is the class, not an object: the class it was called for, so
  `ClassName` and a virtual class method answer for a descendant when a
  descendant's name, a descendant's object or a reference holding a
  descendant calls it. It reaches the class's class variables, class
  properties and other class methods, and makes objects with a
  constructor, of `Self`'s class; a field or an object's method is a
  compile error there. A class method can be `virtual`, overridden and
  `abstract`, and it takes a slot in the method table as an object's
  method does. `static` after one makes a routine in the class's name
  space with no `Self` at all.
- `class of T` is a class reference: one word, the address of a class's
  method table, that holds `T` or a class that descends from it (a
  compile error otherwise). A class's name where a value goes is the
  class; `TClass` is `class of TObject` and holds any class. Through a
  reference: its class methods, `ClassName`, `ClassNameIs`,
  `InstanceSize`, `ClassParent` and `InheritsFrom(C)`, and a
  constructor, which makes an object of the class it holds, of that
  class's size: a `virtual` constructor, overridden, runs the held
  class's own. `x.ClassType` is the class of object `x`; `=` and `<>`
  compare two references.
- `class var` starts class variables, and `x: T; static;` declares one:
  one variable for the class and all its descendants, a global the
  program or unit holds (the debugger shows it as `TShape.FMade`).
- `class property` reads and writes a class variable, or goes through a
  `static` class method.
- `class constructor` and `class destructor` (no parameters, one of
  each per class) run before the unit's `initialization` part, or the
  program's first statement, and after its `finalization`, or its last
  statement, last first.

A class method call costs what a method call costs: `Self` is the table
the class or the object already has, and a virtual one reads one slot.

### Helpers

A helper adds methods to a type that is already declared, a builtin one
too, without a descendant and without touching the type (1.1.9):
`type helper for T` for a simple type (a string, an integer, a real, a
Char, a Boolean, an enumeration, a set), `record helper for R` for a
record and `class helper for C` for a class.

`examples/helpers.paslang`:

```pascal
{ Helpers: methods added to string, to Integer and to a record without
  touching them. Self is the value, and a method may change it. }
program helpers;

type
  TTextHelper = type helper for string
    function Reversed: string;
    function Count(C: Char): Int64;
    procedure Surround(const L, R: string);
    function GetWide: Boolean;
    property Wide: Boolean read GetWide;
  end;

  TNumHelper = type helper for Int64
    function Digits: Int64;
    class function Biggest(A, B: Int64): Int64; static;
  end;

  TSpan = record
    First, Last: Int64;
  end;

  TSpanHelper = record helper for TSpan
    function Len: Int64;
    procedure Widen(By: Int64 = 1);
  end;

function TTextHelper.Reversed: string;
var
  i: Int64;
begin
  Result := '';
  for i := Length(Self) downto 1 do
    Result := Result + Self[i];
end;

function TTextHelper.Count(C: Char): Int64;
var
  i: Int64;
begin
  Result := 0;
  for i := 1 to Length(Self) do
    if Self[i] = C then
      Result := Result + 1;
end;

procedure TTextHelper.Surround(const L, R: string);
begin
  Self := L + Self + R;               { changes the caller's string }
end;

function TTextHelper.GetWide: Boolean;
begin
  Result := Length(Self) > 8;
end;

function TNumHelper.Digits: Int64;
var
  n: Int64;
begin
  Result := 1;
  n := Self;
  while n >= 10 do
  begin
    n := n div 10;
    Result := Result + 1;
  end;
end;

class function TNumHelper.Biggest(A, B: Int64): Int64;
begin
  if A > B then
    Result := A
  else
    Result := B;
end;

function TSpanHelper.Len: Int64;
begin
  Result := Last - First + 1;         { the record's fields, as Self's }
end;

procedure TSpanHelper.Widen(By: Int64);
begin
  First := First - By;
  Last := Last + By;
end;

var
  s: string;
  n: Int64;
  sp: TSpan;

begin
  s := 'paslang';
  WriteLn(s.Reversed, ' ', s.Count('a'), ' ', Ord(s.Wide));
  s.Surround('<', '>');
  WriteLn(s, ' ', Ord(s.Wide), ' ', 'level'.Reversed);
  n := 40961;
  WriteLn(n.Digits, ' ', Int64.Biggest(n, 7), ' ', n.Biggest(3, 9));
  sp.First := 10;
  sp.Last := 14;
  sp.Widen;
  sp.Widen(3);
  WriteLn(sp.First, '..', sp.Last, ' ', sp.Len);
end.
```

prints

```
gnalsap 2 0
<paslang> 1 level
5 40961 9
6..18 13
```

- A helper's methods are called on a value of the type, `s.Reversed`, a
  literal or a constant too (`'level'.Reversed`), and read one another
  and a record's fields without `Self.`. Inside one, `Self` is the
  value, by reference: a method that assigns `Self` or a field changes
  the caller's variable. On a value that is no variable (a literal, a
  result, a `const` parameter) it works on a copy.
- A `class function ... static;` is called through a value or through
  the type's name, `Int64.Biggest`, `string.Join`. A helper's class
  method is always static, and a helper has no fields, no constructor
  and no virtual method.
- `property P: T read GetP write SetP;` reads and writes through the
  helper's methods, with an index in brackets as a class's does.
- `type helper(TBase) for string` descends from another helper for the
  same type and has its methods too. The helper in scope for a type is
  the last one declared or brought by `uses`, as in Free Pascal: a
  second helper for `Int64` hides the first unless it descends from it.
  `private` and `strict private` hold as in a class.
- A helper's method is a routine whose first parameter is `Self`; a call
  costs what a routine's call costs.

### Published properties

A published property that reads or writes a field can be reached by its
name while the program runs. The name is compared without regard to
case, and an object finds its parents' properties too. `o` is an object
and `name` a string:

| Word | What it does |
|---|---|
| `PropKind(o, name)` | the kind of the property, an `Integer`: 0 when `o` has no published property of that name, 1 an integer or another ordinal, 2 a `string`, 3 a method value |
| `GetPropInt(o, name)` | a kind-1 property's value as an `Integer`, read at its field's width and sign; 0 when there is none |
| `SetPropInt(o, name, v)` | writes `v` into a kind-1 property's field at its width (a `Word` keeps the low 16 bits); nothing for another kind |
| `GetPropStr(o, name)` | a kind-2 property's string; `''` when there is none |
| `SetPropStr(o, name, s)` | writes a kind-2 property |
| `SetPropMeth(o, name, m)` | stores the method value `m` in a kind-3 property |
| `CallProp(o, name)` | calls the method value a kind-3 property holds, with no arguments, and gives what it returns as an `Integer` |

```
type
  TBox = class
    FW: Word;
    FName: string;
    FOn: procedure of object;
    procedure Ping;
    property Width: Word read FW write FW;
    property Name: string read FName write FName;
    property OnPing: procedure of object read FOn write FOn;
  end;
...
SetPropInt(b, 'width', 70000);
WriteLn(GetPropInt(b, 'Width'));         { 4464: the Word's 16 bits }
SetPropStr(b, 'Name', 'crate');
SetPropMeth(b, 'OnPing', b.Ping);
CallProp(b, 'OnPing');                   { runs b.Ping }
WriteLn(PropKind(b, 'Name'), PropKind(b, 'Nope'));   { 20 }
```

The table is the class's: one entry per published property with a
field behind it (its name, kind, width and the field's offset), found
through the word before the method table. A property read or written
through methods has no entry.

`examples/properties.paslang` reads settings into an object by name:

```pascal
{ Published properties by name while the program runs: settings
  applied to an object, a method property called, a descendant's
  property found through a parent variable, and what has no entry. }
program properties;

type
  TDevice = class
    FName: string;
    FBaud: Word;
    FHits: Integer;
    FOnPoll: function: Integer of object;
    FSecret: Integer;
    function Poll: Integer;
    property Name: string read FName write FName;
    property Baud: Word read FBaud write FBaud;
    property Sample: Integer read Poll;         { through a method: no entry }
    property OnPoll: function: Integer of object read FOnPoll write FOnPoll;
  private
    property Secret: Integer read FSecret write FSecret;   { no entry either }
  end;

  TLamp = class(TDevice)
    FWatts: Integer;
    property Watts: Integer read FWatts write FWatts;
  end;

function TDevice.Poll: Integer;
begin
  FHits := FHits + 1;
  Result := FHits * 100;
end;

var
  lamp: TLamp;
  dev: TDevice;
  keys: array of string;
  vals: array of Integer;
  i: Integer;

begin
  lamp := TLamp.Create;
  dev := lamp;                            { the object's class is asked, not the variable's }
  keys := ['baud', 'watts', 'secret', 'sample', 'volts'];
  vals := [70000, 60, 7, 9, 12];
  for i := 0 to High(keys) do
    case PropKind(dev, keys[i]) of        { 1 integer, 2 string, 3 method, 0 none }
      1: SetPropInt(dev, keys[i], vals[i]);
      0: WriteLn('no property ', keys[i]);
    end;
  SetPropStr(dev, 'NAME', 'desk');        { the case of the name does not matter }
  WriteLn(GetPropStr(dev, 'name'), ' ', GetPropInt(dev, 'baud'), ' ', lamp.Watts);   { desk 4464 60 }
  SetPropMeth(dev, 'onpoll', @lamp.Poll);
  WriteLn(CallProp(dev, 'OnPoll'), ' ', CallProp(dev, 'OnPoll'), ' ', dev.FHits);   { 100 200 2 }
  WriteLn(PropKind(dev, 'sample'), PropKind(dev, 'secret'), PropKind(dev, 'watts'), PropKind(dev, 'onpoll'));   { 0013 }
end.
```

prints

```
no property secret
no property sample
no property volts
desk 4464 60
100 200 2
0013
```

The words ask the object's class, not the variable's: `dev` is a
`TDevice` that holds a `TLamp`, and `watts` is found. `PropKind` first:
a set word does nothing for a name that has no entry or holds another
kind (`SetPropStr` of a kind-1 property changes nothing), `GetPropInt`
and `GetPropStr` of such a name give 0 and `''`, `CallProp` gives 0,
and `GetPropInt` of a string property is not its string. The value
goes through the field's own width and sign: an `Int8` written -5
reads -5, a `Boolean` written 1 reads 1, and `Baud` above kept the low
16 bits of 70000. A property without a field behind it, `Sample` read
through `Poll`, and one declared after `private` or `protected`,
`Secret`, have no entry: for the words they are not there.

## 8. Generics

`examples/generics.paslang`:

```pascal
{ A generic record and two specializations of it. }
program generics;

type
  generic TPair<T> = record
    First, Second: T;
  end;
  TIntPair = specialize TPair<Integer>;
  TStrPair = specialize TPair<string>;

var
  ip: TIntPair;
  sp: TStrPair;

begin
  ip.First := 1;
  ip.Second := 2;
  sp.First := 'a';
  sp.Second := 'b';
  WriteLn(ip.First + ip.Second);     { 3 }
  WriteLn(sp.First + sp.Second);     { ab }
end.
```

prints

```
3
ab
```

`generic Name<T> = ...` declares a template and `specialize Name<Type>`
makes a concrete type from it. Every specialization is its own type.

A generic is a record with one type parameter (1.0.146): `generic
TStack<T> = class` is refused, `generic record`, and `<K, V>` is a
syntax error at the comma. `T` goes wherever a type goes in the fields,
`Items: array of T` too, and the argument of `specialize` is any type:
`specialize TPair<array of Integer>`, or another specialization,
`specialize TPair<TIntPair>`, whose `First.First` is then a field of a
field.

## 9. Errors: raise, try, finally

`examples/errors.paslang`:

```pascal
{ Errors: raise, try except, try finally. A finally part runs on every
  way out of its block, including exit and an exception on its way up. }
program errors;

procedure Risky(Fail: Boolean);
begin
  try
    WriteLn('start');
    if Fail then
      raise;                      { unwinds to the nearest except }
    WriteLn('no failure');
  finally
    WriteLn('cleanup');           { runs either way }
  end;
  WriteLn('after');
end;

procedure Early;
begin
  try
    Exit;                         { leaves the routine }
  finally
    WriteLn('finally on exit');   { still runs }
  end;
end;

begin
  try
    Risky(True);
  except
    WriteLn('caught');
  end;
  Risky(False);
  Early;
end.
```

prints

```
start
cleanup
caught
start
no failure
cleanup
after
finally on exit
```

`raise` unwinds the current routine to the nearest `except` part, running
every `finally` on the way. A `finally` also runs when its block is left
with `exit`, `break` or `continue`. An exception with no handler ends the
routine that raised it; in the main routine that ends the program.
`raise` alone, as here, raises no object; `raise X` raises an object of
a class, which the handler reads (below).

`examples/cleanup.paslang` releases what each frame holds as a raise
goes up through three frames:

```pascal
{ finally across frames: each frame releases what it holds, innermost
  first, as a raise goes up to its handler; raise; in an except part
  hands the object on to the next handler up; a store the raise cut
  short is not made. }
program cleanup;

type
  ELoad = class                     { what a failed load raises }
    Reason: string;
    constructor Create(const AReason: string);
  end;

var
  open: Integer;                    { resources held right now }
  n: Integer;

constructor ELoad.Create(const AReason: string);
begin
  Reason := AReason;
end;

procedure Track(const What: string; Delta: Integer);
begin
  open := open + Delta;
  WriteLn(What, ', ', open, ' open');
end;

function Parse(const S: string): Integer;
begin
  Track('open parser', 1);
  try
    if S = '' then
      raise ELoad.Create('empty input');   { up through both finally parts }
    Result := Length(S);
  finally
    Track('close parser', -1);      { first }
  end;
end;

function Load(const S: string): Integer;
begin
  Track('open file', 1);
  try
    Result := Parse(S) * 10;        { when Parse raises: no * 10, no store }
  finally
    Track('close file', -1);        { second }
  end;
end;

begin
  try
    n := Load('abc');
    WriteLn('loaded ', n);          { 30 }
    n := Load('');                  { raises two frames down: n is not stored }
  except
    on E: ELoad do
      WriteLn('failed: ', E.Reason, ', n still ', n);   { third: the handler }
  end;
  try
    try
      Load('');
    except
      WriteLn('inner handler');
      raise;                        { the same object: to the next handler up }
    end;
  except
    WriteLn('outer handler');
  end;
end.
```

prints

```
open file, 1 open
open parser, 2 open
close parser, 1 open
close file, 0 open
loaded 30
open file, 1 open
open parser, 2 open
close parser, 1 open
close file, 0 open
failed: empty input, n still 30
open file, 1 open
open parser, 2 open
close parser, 1 open
close file, 0 open
inner handler
outer handler
```

The order is fixed: each `finally` runs as its frame is left, innermost
first, and the `except` part runs last, in the frame that has it; a
`raise` crosses any number of frames without a handler. What the
`raise` cut short stays undone: `Load('')` was to store `Parse(S) * 10`
in `Result` and the main routine `n := Load('')`, and neither store was
made, so `n` keeps its 30; a function that raises gives no value back.
A `raise` in an `except` part is a raise like any other: it leaves that
handler and goes on to the next `except` up, running the `finally`
parts between; `raise;` there hands on the object the handler took. A
`raise` that finds no handler in any frame of its
routine (a `pas` routine, or the main one) still runs the `finally`
parts of the frames it leaves, then ends the routine where it is
(`rt_raise` goes to `rt_goexit`), so a `wg.Done` in plain code after
the call is never reached, and one in a `finally` is. In the main
routine an uncaught `raise` ends the program: `paslang: uncaught raise
in the main routine` on the error output and exit status 1 (1.0.147;
before, the scheduler was left with nothing to run and said
`deadlock`). `testdata/fatal/mainraise` shows both. When the raise
carried an object, the line goes on with what the object's `ToString`
says, its class's name unless the class says more:
`paslang: uncaught raise in the main routine: EOops`
(`testdata/fatal/raiseobj`, 1.1.3).

### Exception objects

`raise X` raises the object `X`, of any class (1.1.3). An `except`
part with `on` handlers runs the first one whose class the object is
or descends from:

`examples/excobjects.paslang`:

```pascal
{ Exception objects: raise carries an object of any class; an except
  part runs the first on handler whose class the object is or descends
  from, with a name for the object in that handler alone; raise; in a
  handler hands the same object on to the next handler out. }
program excobjects;

type
  EParse = class                        { any class can be raised }
    Line: Integer;
    Text: string;
    constructor Create(ALine: Integer; const AText: string);
  end;

  EEmpty = class(EParse)                { a kind of EParse }
  end;

var
  total: Integer;

constructor EParse.Create(ALine: Integer; const AText: string);
begin
  Line := ALine;
  Text := AText;
end;

function Digits(const S: string; Line: Integer): Integer;
var
  i: Integer;
begin
  if S = '' then
    raise EEmpty.Create(Line, 'empty line');
  Result := 0;
  for i := 1 to Length(S) do
  begin
    if (S[i] < '0') or (S[i] > '9') then
      raise EParse.Create(Line, 'not a digit: ' + S[i]);
    Result := Result * 10 + Ord(S[i]) - Ord('0');
  end;
end;

procedure Add(const S: string; Line: Integer);
begin
  try
    total := total + Digits(S, Line);   { no store when Digits raises }
  except
    on E: EEmpty do                     { the first handler that fits runs }
      WriteLn('line ', E.Line, ' skipped: ', E.Text);
    on E: EParse do
    begin
      WriteLn('line ', E.Line, ' refused: ', E.Text);
      if E.Line > 4 then
        raise;                          { the same object, to the handler out }
    end;
  end;
end;

begin
  total := 0;
  try
    Add('12', 1);
    Add('', 2);
    Add('7x', 3);
    Add('30', 4);
    Add('9z', 5);
    Add('100', 6);                      { not reached }
  except
    on E: EParse do
      WriteLn('stopped at line ', E.Line, ' by ', E.ClassName);
  else
    WriteLn('not an EParse');           { any other object, or none }
  end;
  WriteLn('total ', total);
end.
```

prints

```
line 2 skipped: empty line
line 3 refused: not a digit: x
line 5 refused: not a digit: z
stopped at line 5 by EParse
total 42
```

- `on E: T do statement` takes an object of class `T` or of a class
  that descends from it; `E` is a variable of type `T` that holds the
  object, seen by that handler's statement alone (it hides a variable
  of the routine with that name). `on T do statement` takes it without
  a name. Handlers are separated by `;` and tried in order, so a
  descendant's handler goes before its parent's.
- `else` and statements after the last handler run when none takes the
  object, and when the raise carried none. With no `else`, the raise
  goes on to the next `except` out, running the `finally` parts
  between: the handlers of an `except` part choose what they take.
- An `except` part with no `on` takes every raise, object or not.
- `raise;` anywhere inside an `except` part raises the object that
  part took again (outside one, it raises no object). `raise E` raises
  the object itself again too: the object is not freed when a handler
  ends, and a handler may keep it; the collector takes it back when
  nothing points to it.
- `raise X at A` says where the object was raised, `A` a pointer; with
  no `at`, it is the address the raising call returns to.
- The object belongs to the routine that raised it: a routine started
  with `pas` raises and handles its own, whatever the others do. It is
  held in the routine's record while a handler runs; when an `except`
  part ends, by its end, `exit`, `break` or `continue`, the routine
  holds again the object it held before the `try`, so `raise;` in an
  outer handler hands on that handler's object, and a `finally` part
  that handled a raise of its own lets the first one go on.

What it costs: `raise` is two stores and a jump to the handler; a
handler's test is `is`, a walk up the object's parents to the class
named; nothing is copied and nothing is allocated but the object.

### Classes and exceptions together

`examples/bank.paslang` puts both to work: methods that raise an
exception object, a descendant that adds a rule before deferring to
the inherited method,
a class that catches and counts, and a routine whose uncaught raise
ends only itself. In the main routine an uncaught `raise` ends the
program instead, with `paslang: uncaught raise in the main routine` on
the error output and exit status 1 (1.0.147):

```pascal
{ Classes and exceptions: a small bank.

  What the program does, step by step:
  1. Declares EBank, the object a refused operation raises: its Reason
     says why, and the handler that takes it reads it.
  2. Declares TAccount, an owner and a balance, and TSavings, a
     TAccount that must keep a minimum balance. TSavings overrides
     Withdraw and calls the inherited one when the rule holds.
  3. Declares TAudit, which applies operations to any account through
     the parent type and counts them: every attempt in a try/finally,
     every failure in a try/except, whose handler keeps the reason.
  4. Creates one account of each class through their constructors,
     applies six operations (deposits, withdrawals, one bad amount, one
     that breaks the minimum, one with no funds) and prints, for each,
     whether it went through and, if not, why.
  5. Shows is and as: the audit asks whether an account is a TSavings
     to print its minimum.
  6. Starts a routine with pas that raises with no handler: the raise
     runs the routine's finally part and ends only that routine; the
     main routine goes on. The waitgroup shows the finally ran.
  7. Prints the audit totals and the final balances.

  Routines:
  - EBank.Create(AReason): the reason.
  - TAccount.Create(AOwner, Start): sets the owner and the opening
    balance.
  - TAccount.Deposit(Amount): adds Amount; an amount below 1 raises an
    EBank that says bad amount.
  - TAccount.Withdraw(Amount): virtual; takes Amount; more than the
    balance raises an EBank that says insufficient funds.
  - TAccount.Balance: a property that reads the private balance.
  - TSavings.Create(AOwner, Start, AMinimum): the parent constructor,
    then the minimum.
  - TSavings.Withdraw(Amount): override; raises an EBank that says
    below minimum when the balance would drop under the minimum,
    otherwise defers to the inherited Withdraw.
  - TAudit.Apply(Acc, Op, Amount): runs Deposit or Withdraw by Op, d
    or w, inside try/except; returns True when it went through, else
    keeps the EBank's reason in LastReason. The finally part counts
    the attempt whether it raised or not.
  - Risky: raises with no except part; its finally calls wg.Done.
  - The main routine: steps 4 to 7. }
program bank;

type
  EBank = class                      { what a refused operation raises }
    Reason: string;
    constructor Create(const AReason: string);
  end;

  TAccount = class
    FOwner: string;
    FBalance: Integer;
    constructor Create(const AOwner: string; Start: Integer);
    procedure Deposit(Amount: Integer);
    procedure Withdraw(Amount: Integer); virtual;
    property Balance: Integer read FBalance;
  end;

  TSavings = class(TAccount)
    FMinimum: Integer;
    constructor Create(const AOwner: string; Start, AMinimum: Integer);
    procedure Withdraw(Amount: Integer); override;
  end;

  TAudit = class
    Attempts: Integer;
    Failures: Integer;
    LastReason: string;              { why the last refused operation was }
    function Apply(Acc: TAccount; const Op: string; Amount: Integer): Boolean;
  end;

constructor EBank.Create(const AReason: string);
begin
  Reason := AReason;
end;

constructor TAccount.Create(const AOwner: string; Start: Integer);
begin
  FOwner := AOwner;
  FBalance := Start;
end;

procedure TAccount.Deposit(Amount: Integer);
begin
  if Amount < 1 then
    raise EBank.Create('bad amount'); { unwinds to the nearest except }
  FBalance := FBalance + Amount;
end;

procedure TAccount.Withdraw(Amount: Integer);
begin
  if Amount > FBalance then
    raise EBank.Create('insufficient funds');
  FBalance := FBalance - Amount;
end;

constructor TSavings.Create(const AOwner: string; Start, AMinimum: Integer);
begin
  inherited Create(AOwner, Start);   { the parent constructor first }
  FMinimum := AMinimum;
end;

procedure TSavings.Withdraw(Amount: Integer);
begin
  if FBalance - Amount < FMinimum then
    raise EBank.Create('below minimum');
  inherited Withdraw(Amount);        { the parent's checks and the update }
end;

function TAudit.Apply(Acc: TAccount; const Op: string; Amount: Integer): Boolean;
begin
  Result := False;
  try
    try
      if Op = 'd' then
        Acc.Deposit(Amount)
      else
        Acc.Withdraw(Amount);        { the override runs for a TSavings }
      Result := True;
    except
      on E: EBank do                 { the raise from inside the method lands here }
      begin
        Failures := Failures + 1;
        LastReason := E.Reason;
      end;
    end;
  finally
    Attempts := Attempts + 1;        { counted either way }
  end;
end;

var
  wg: waitgroup;

procedure Risky;
begin
  try
    raise EBank.Create('risky');     { no except part in this routine }
  finally
    wg.Done;                         { still runs on the way out }
  end;
  WriteLn('never printed');          { the routine ended at the raise }
end;

var
  plain: TAccount;
  saving: TSavings;
  audit: TAudit;
  acc: TAccount;
  ops: array[0..5] of string;
  amounts: array[0..5] of Integer;
  i: Integer;

begin
  plain := TAccount.Create('ana', 100);
  saving := TSavings.Create('bo', 500, 200);
  audit := TAudit.Create;            { a class with no constructor of its own }
  ops[0] := 'd'; amounts[0] := 50;   { ana: 150 }
  ops[1] := 'w'; amounts[1] := 120;  { ana: 30 }
  ops[2] := 'w'; amounts[2] := 40;   { ana: insufficient funds }
  ops[3] := 'd'; amounts[3] := 0;    { ana: bad amount }
  ops[4] := 'w'; amounts[4] := 250;  { bo: 250 }
  ops[5] := 'w'; amounts[5] := 100;  { bo: below minimum }
  for i := 0 to 5 do
  begin
    if i < 4 then
      acc := plain
    else
      acc := saving;                 { a TSavings fits the parent type }
    if audit.Apply(acc, ops[i], amounts[i]) then
      WriteLn(acc.FOwner, ' ', ops[i], ' ', amounts[i], ' ok, balance ', acc.Balance)
    else
      WriteLn(acc.FOwner, ' ', ops[i], ' ', amounts[i], ' refused: ', audit.LastReason);
  end;
  if saving is TSavings then         { is asks the class at run time }
    WriteLn('minimum of ', saving.FOwner, ' is ', (saving as TSavings).FMinimum);
  wg.Add(1);
  pas Risky;                         { its raise ends only that routine }
  wg.Wait;
  WriteLn('risky ended, main goes on');
  WriteLn(audit.Attempts, ' attempts, ', audit.Failures, ' failures');
  WriteLn(plain.Balance, ' ', saving.Balance);
end.
```

prints

```
ana d 50 ok, balance 150
ana w 120 ok, balance 30
ana w 40 refused: insufficient funds
ana d 0 refused: bad amount
bo w 250 ok, balance 250
bo w 100 refused: below minimum
minimum of bo is 200
risky ended, main goes on
6 attempts, 3 failures
30 250
```

## 10. Routines that run concurrently: pas, channels, select

`examples/concurrent.paslang`:

```pascal
{ Routines: pas starts one, channels carry values between them, select
  waits on several arms, Sleep parks. A routine is a G on the scheduler,
  not an OS thread; waiting parks it and the thread stays free. }
program concurrent;

var
  c, done: chan of Integer;
  total, x, k: Integer;

procedure Producer(N: Integer);
var
  i: Integer;
begin
  for i := 1 to N do
    Send(c, i);                     { parks until the value is taken }
  Send(done, 0);
end;

begin
  c := MakeChan();
  done := MakeChan();
  pas Producer(5);                  { runs concurrently with the main routine }
  total := 0;
  k := 0;
  while k < 5 do
  begin
    x := Recv(c);                   { parks until a value arrives }
    total := total + x;
    k := k + 1;
  end;
  x := Recv(done);
  WriteLn(total);                   { 15 }
  select                            { the ready arm runs, else the else }
    Recv(c, x): WriteLn('value');
  else
    WriteLn('empty');
  end;
  Sleep(1);                         { milliseconds; parks, the thread stays free }
  WriteLn('done');
end.
```

prints

```
15
empty
done
```

`pas` starts a routine: a G, scheduled by the runtime over OS threads,
at most one running Pascal code for each CPU the program may use (§17). What follows `pas` is a call as a
statement writes it (1.0.135): `pas Name(a, b, c)` with any number of
arguments of any type, `pas f` or `pas f(a)` of a routine value or a
closure, `pas obj.M(a)` of a method (a class's or an interface's),
`pas m(a)` of a method value, or `pas procedure begin ... end`. As in
Go, the routine value or the object and every argument are worked out
when `pas` runs, so what the starting routine changes afterwards, or the
next pass of its loop, does not reach the new one; the body of `pas
procedure begin ... end` is a closure and shares the variables it names
(§5). A routine with a `var` parameter is refused, since the new
routine would point into a frame that goes on changing. Up to two
arguments of one word each (an integer, a pointer, an object) go
straight into the new routine's registers; anything else goes through a
closure the compiler makes, one heap cell an argument (a string or a
record went as its first word alone before 1.0.135). A channel, `chan of T` for
any `T` (a string, a record and an array travel as a copy the receiver
owns), is created with `MakeChan()`; `Send(c, v)` parks until a receiver takes the
value and `Recv(c)` parks until one arrives, so the channel is also the
synchronisation. `MakeChan(n)` (with `n` from 0 to 67108864, 2^26;
a constant outside is a compile error and a value outside stops the
program with `channel capacity N out of range`, 1.0.136) makes a
buffered channel, as Go's
`make(chan T, n)`: it keeps up to `n` values, a send parks only when the
buffer is full and a receive takes the oldest value first. `Close(c)`
ends a channel: a receive on a closed channel gives what its buffer
still holds, then the zero value at once. `select` tries its arms, `Recv(c, x):`
or `Send(c, v):`, runs the first one that is ready, and takes the `else`
when none is; without `else` it parks until one is. `Sleep(ms)` parks
the routine for that many milliseconds. `Yield` (also `Gosched`) lets
other routines run. `Goid` (also `GId`) is the number of the current
routine, 1 for the main one, and `NumGoroutine` (also `GCount`) counts
the live ones. When the main routine reaches its `end.`, the program
waits for every other routine to end and then exits with status 0.
When every routine is asleep and nothing can wake any of them, the
program stops instead of waiting for ever (1.0.139, as Go does):

```
paslang: all routines are asleep: deadlock
```

on standard error, exit status 1. That is a `Recv` or a `Send` nobody
will serve, a `wg.Wait` whose count never reaches zero, a mutex locked
twice, a `select` without `else` whose arms can never be ready, two
routines each waiting for the other, or, after the main routine has
ended, the routines left waiting on each other. A routine counts as
able to wake while a `Sleep` timer is pending, while it waits on a
socket, standard input or any descriptor (`WaitFd`, `WaitIo`, `WaitMs`,
pasnet), while it is in a system call, while another routine runs or
is in a queue to run, or while one is parked at a `Breakpoint` and
another still runs; a program whose routines are all at `Breakpoint`s
is dead, since only a routine can call `ContinueBreak`. `Halt(n)` ends
the program at once, whatever the other routines are doing (§4).

Standard output is written line by line under a lock: a `WriteLn` from
one routine never interleaves inside a `WriteLn` from another.

When an operation on a channel parks, in one line each: a `Send` on a
channel made with `MakeChan()` parks until a receiver takes the value,
and on a channel made with `MakeChan(n)` only while its `n` places are
full; a `Recv` parks while there is nothing to take, that is no value
in the buffer, no sender parked on the channel and the channel open. A
send meets a receiver already parked on the channel directly, without
passing through the buffer, and a receive takes the oldest value of
the buffer before it serves a parked sender, so a buffered channel
never reorders what went through it. `Close(c)` wakes every receiver
parked on `c`, each with the zero value; a `Send` on a closed channel,
plain or as an arm of a `select`, stops the program with `paslang:
send on closed channel`, and a second `Close` with `paslang: close of
closed channel` (§17). The zero value is the only sign of a closed
channel a receiver gets, so a stream that ends by a `Close` must not
carry the zero value as data: `pipeline` below sends job numbers from 1.

### Fan-in with select

`examples/fanin.paslang` joins two producers into one select loop over
channels made with `MakeChan()`, which have no buffer, then
shows the non-blocking form, a send arm, and a closed channel:

```pascal
{ Channels and select: two producers, one select loop, a late consumer.

  What the program does, step by step:
  1. Creates four channels with MakeChan. odds and evens carry numbers,
     done carries one signal per finished producer, back carries the
     answer of the consumer. These channels have no buffer: Send parks the
     sender until a receiver takes the value.
  2. Starts Producer(1) and Producer(2) with pas. The first sends the
     odd numbers 1, 3, 5, 7, 9 on odds; the second sends 2, 4, 6, 8, 10
     on evens. Each one sends 1 on done after its last number.
  3. The main routine loops on a select with three receive arms until
     both producers have signalled done. The select parks until one of
     the channels has a value and runs that arm; the sums are the same
     whatever the order in which the values arrive.
  4. Prints the sum of the odd numbers, the sum of the even numbers and
     how many values arrived.
  5. Shows the non-blocking select: with an else branch, a receive on a
     channel nobody sends to, and a send on a channel nobody reads,
     both take the else at once instead of parking.
  6. Starts Consumer with pas and hands it one value through a select
     with a send arm and no else, which parks until the consumer takes
     the value. Then reads the consumer's answer from back.
  7. Closes odds. A receive on a closed channel returns the zero value
     at once, which is how a reader learns that a stream has ended.

  Routines:
  - Producer(First): sends First, First + 2, First + 4, ... up to 10 on
    odds when the number is odd and on evens when it is even, each Send
    parking until the main routine receives, then sends 1 on done.
  - Consumer: receives one number from evens, doubles it and sends the
    result on back.
  - The main routine: steps 1 to 7 above.

  The output is the same on every run: the select loop stops only after
  both done signals, and a producer sends done only after its last
  number was received. }
program fanin;

var
  odds, evens, done, back: chan of Integer;

procedure Producer(First: Integer);
var
  i: Integer;
begin
  i := First;
  while i <= 10 do
  begin
    if Odd(i) then
      Send(odds, i)                { parks until the main routine receives }
    else
      Send(evens, i);
    i := i + 2;
  end;
  Send(done, 1);                   { every number of this producer was taken }
end;

procedure Consumer;
var
  v: Integer;
begin
  v := Recv(evens);                { parks until the main routine sends }
  Send(back, v * 2);
end;

var
  x, sumOdd, sumEven, received, finished: Integer;

begin
  odds := MakeChan();
  evens := MakeChan();
  done := MakeChan();
  back := MakeChan();
  pas Producer(1);
  pas Producer(2);
  sumOdd := 0;
  sumEven := 0;
  received := 0;
  finished := 0;
  while finished < 2 do
    select                         { parks until one arm is ready }
      Recv(odds, x):
        begin
          sumOdd := sumOdd + x;
          received := received + 1;
        end;
      Recv(evens, x):
        begin
          sumEven := sumEven + x;
          received := received + 1;
        end;
      Recv(done, x): finished := finished + 1;
    end;
  WriteLn('odd sum ', sumOdd, ' even sum ', sumEven, ' values ', received);
  select                           { nobody sends on odds now: else runs at once }
    Recv(odds, x): WriteLn('unexpected value ', x);
  else
    WriteLn('nothing to receive');
  end;
  select                           { nobody receives on evens: else runs at once }
    Send(evens, 99): WriteLn('unexpected hand-off');
  else
    WriteLn('nobody receiving');
  end;
  pas Consumer;
  select                           { no else: parks until the consumer takes 21 }
    Send(evens, 21): WriteLn('handed 21');
  end;
  x := Recv(back);
  WriteLn('consumer answered ', x);
  Close(odds);
  x := Recv(odds);                 { a closed channel gives the zero value }
  WriteLn('closed channel gives ', x);
end.
```

prints

```
odd sum 25 even sum 30 values 10
nothing to receive
nobody receiving
handed 21
consumer answered 42
closed channel gives 0
```

A `select` arm is `Recv(c, x): statement` or `Send(c, v): statement`;
the statement may be a `begin ... end` block. With an `else` the select
never parks: it runs the first ready arm or the `else`. Without one it
parks with a waiter on every channel at once and wakes for the first
one that pairs, whichever arm it is; exactly one arm fires. Two
routines may select on the same channels from opposite sides and still
meet. A select has at most 16 arms. A blocking select with a single
send arm is the way to hand a value to a routine that may not be
waiting yet.

### A timeout, and two arms ready at once

There is no timer arm: a timeout is a routine that sleeps and then
sends on a channel of its own, and a `select` with that channel in one
arm and the answer in another takes whichever comes first.
`examples/timeout.paslang`:

```pascal
{ select with a timer: the arm that is ready first runs. Nobody sends
  on never, so the timer arm wins; the server answers when asked, so a
  plain Recv then parks until its answer comes. When two arms are ready
  at once, the first one written runs. }
program timeout;

var
  never, ask, reply, timer, a, b: chan of Integer;
  x: Integer;

procedure Timer(Ms: Integer);
begin
  Sleep(Ms);                       { parks; the thread serves other routines }
  Send(timer, Ms);
end;

procedure Server;
var
  q: Integer;
begin
  q := Recv(ask);                  { parks until somebody asks }
  Send(reply, q * 2);
end;

begin
  never := MakeChan();
  ask := MakeChan();
  reply := MakeChan();
  timer := MakeChan();
  pas Server;
  pas Timer(20);
  select                           { parks with a waiter on both channels }
    Recv(never, x): WriteLn('answer ', x);
    Recv(timer, x): WriteLn('no answer in ', x, ' ms');
  end;
  Send(ask, 21);                   { the server wakes and answers }
  x := Recv(reply);
  WriteLn('answer ', x);           { answer 42 }
  a := MakeChan(1);
  b := MakeChan(1);
  Send(a, 1);                      { both buffers hold a value: both arms are ready }
  Send(b, 2);
  select
    Recv(a, x): WriteLn('a first, took ', x);   { the first arm written runs }
    Recv(b, x): WriteLn('b first, took ', x);
  end;
  Send(a, 1);
  select
    Recv(b, x): WriteLn('b first, took ', x);   { b first, took 2 }
    Recv(a, x): WriteLn('a first, took ', x);
  end;
  x := Recv(a);
  WriteLn('left in a: ', x);       { left in a: 1 }
end.
```

prints

```
no answer in 20 ms
answer 42
a first, took 1
b first, took 2
left in a: 1
```

The runtime tries the arms of a `select` in the order they are written
and runs the first one that is ready, so with `a` and `b` both holding
a value the arm written first fires every time; Go draws one of the
ready arms at random instead. A loop that must not starve its second
arm puts the rarer channel first, or drains the busier one with a
non-blocking select of its own. When no arm is ready and there is no
`else`, the runtime locks every channel of the select in a fixed
order, looks at each arm again under the locks, so a value that
arrived in between is not lost, queues one waiter on each channel and
parks; the first channel to pair claims the select with one compare
and swap, the other waiters are taken off their channels when the
routine wakes, and the arm that paired runs. A receive arm on a closed
channel is ready at once, with the zero value. The timer of the
example sends on a channel nobody else reads: a second `Timer` started
after the answer came would park at its `Send` for ever, and the
program's end would then wait for it (above) and stop with the deadlock
message. A timer whose select may not be there to receive sends on a
channel with a buffer, `MakeChan(1)`, and ends whatever happened.

### A worker pool

`examples/pipeline.paslang` is the shape of most concurrent work: a
channel of jobs, a fixed number of routines taking from it, a channel
of results and a waitgroup (§12) that says when the workers are done.

```pascal
{ A worker pool: three routines take jobs from one channel and put their
  results on another; a waitgroup says when all of them have finished. }
program pipeline;

const
  Workers = 3;
  NJobs = 8;

type
  TResult = record
    Job, Sum: Integer;
  end;

var
  jobs: chan of Integer;
  results: chan of TResult;
  wg: waitgroup;
  sums: array[1..NJobs] of Integer;
  r: TResult;
  i: Integer;

function Work(N: Integer): Integer;   { the job: 1 + 4 + 9 + ... + N * N }
begin
  Result := N * (N + 1) * (2 * N + 1) div 6;
end;

procedure Worker;
var
  n: Integer;
  res: TResult;
begin
  n := Recv(jobs);                 { parks while the channel is empty }
  while n <> 0 do                  { 0: the channel was closed and drained }
  begin
    res.Job := n;
    res.Sum := Work(n);
    Send(results, res);            { a record travels as a copy }
    n := Recv(jobs);
  end;
  wg.Done;                         { one worker less to wait for }
end;

begin
  jobs := MakeChan(NJobs);         { room for every job: no Send below parks }
  results := MakeChan(NJobs);
  wg.Add(Workers);                 { three Done calls are expected }
  for i := 1 to Workers do
    pas Worker;
  for i := 1 to NJobs do
    Send(jobs, i);                 { into the buffer; the workers take them }
  Close(jobs);                     { drained, the channel then gives 0 }
  wg.Wait;                         { parks until the three workers called Done }
  for i := 1 to NJobs do           { every result is in the buffer now }
  begin
    r := Recv(results);
    sums[r.Job] := r.Sum;
  end;
  for i := 1 to NJobs do
    WriteLn(i, ' -> ', sums[i]);   { 1 -> 1, 2 -> 5, ... 8 -> 204 }
end.
```

prints

```
1 -> 1
2 -> 5
3 -> 14
4 -> 30
5 -> 55
6 -> 91
7 -> 140
8 -> 204
```

The jobs channel has room for every job, so the main routine hands out
all of them without parking, and closing it is the signal that there
is no more work: a receive on a closed channel gives what the buffer
still holds and then the zero value, which is why the loop of `Worker`
stops at 0 and why a job is never numbered 0. A worker sends its last
result before it calls `Done`, so when `wg.Wait` returns every result
is in the buffer of `results`, and the main routine takes them out
without parking. They come out in the order the workers finished,
which is not the order of the jobs and differs from run to run; the
array indexed by job number puts them back in order, which is what
makes the output the same on every machine. The buffer of `results`
is not decoration: with `MakeChan()` the first worker to finish a job
would park at `Send` until the main routine received, the main routine
is parked at `wg.Wait`, and the program stops with `paslang: all
routines are asleep: deadlock`. A results channel without a buffer
needs a routine that receives while the workers run.

## 11. Maps

`examples/maps.paslang`:

```pascal
{ map[K] of V: an associative array. The key is an ordinal, a string, a
  pointer or a class; the value is any type. }
program maps;

type
  TPoint = record
    X, Y: Integer;
  end;

var
  age: map[string] of Integer;
  where: map[string] of TPoint;
  name, k: string;
  years, total: Integer;
  p: TPoint;

begin
  New(age);                          { a map starts nil; New creates it }
  age['ana'] := 41;
  age['bo'] := 7;
  age['ana'] := 42;                  { writing again replaces the value }
  WriteLn(Length(age));              { 2 }
  WriteLn(age['ana']);               { 42 }
  WriteLn(age['nadie']);             { a missing key reads as zero }
  if 'bo' in age then                { in tests membership }
    WriteLn('bo is here');
  if TryGet(age, 'ana', years) then  { read and test in one step }
    WriteLn(years);
  Delete(age, 'bo');
  WriteLn(Length(age), ' ', 'bo' in age);   { 1 0 }
  age['cy'] := 30;
  age['di'] := 20;
  total := 0;
  for name, years in age do          { key and value; the order is not specified }
    total := total + years;
  WriteLn(total);                    { 92 }
  for k in age do
    if age[k] < 25 then
      Delete(age, k);                { deleting inside the loop is allowed }
  WriteLn(Length(age));              { 2 }
  age['ana'] += 1;                   { m[k] op= e reads and writes the entry }
  Inc(age['ana']);
  WriteLn(age['ana']);               { 44 }
  Clear(age);
  WriteLn(Length(age));              { 0 }
  New(where);
  p.X := 1;
  p.Y := 2;
  where['home'] := p;                { a record value is copied in }
  p := where['home'];
  WriteLn(p.X, ' ', p.Y);            { 1 2 }
  p := where['office'];              { missing: all zero }
  WriteLn(p.X, ' ', p.Y);            { 0 0 }
  where['work'].X := 5;              { a field of a missing key: the entry is inserted }
  WriteLn(where['work'].X, ' ', where['nowhere'].Y, ' ', Length(where));   { 5 0 2 }
end.
```

prints

```
2
42
0
bo is here
42
1 0
92
2
44
0
1 2
0 0
5 0 2
```

`map[K] of V` is one pointer, `nil` until `New(m)` or `New(m, hint)`
creates the table; the hint is the number of entries to make room for.
The key is an ordinal, a string, a pointer or a class, and the value is
any type, records included. A read of a missing key, or of a `nil` map,
gives the zero value; a write to a `nil` map stops the program with
`paslang: nil map` on standard error and exit status 1, as every
runtime error does. `k in m` tests, `TryGet(m, k, v)` reads with a
Boolean into a `v` of type `V`, `Delete(m, k)` removes, `Clear(m)`
empties, `Length(m)` counts. `for k in m do` and `for k, v in m do` walk
the entries in no particular order; deleting the current key or
inserting during the walk is allowed, and an entry inserted during the
walk may or may not be visited.

The key of `m[k]`, `k in m`, `Delete(m, k)` and `TryGet(m, k, v)` is
converted as an argument of a call is (1.0.140): a `Char` where a
`string` key goes becomes a string, `'x'` where a `Char` key goes a
Char, a constant into a `Byte` key must fit, a wider integer variable
needs a conversion (`m[Byte(i)]`, as `b := i` does), and a key of
another kind is refused (`Integer does not go into string, the key of
map[string] of Integer`). In `for k in m` and `for k, v in m`, `k` is of
type `K`, or an `Integer` when `K` is an ordinal, or a wider integer type
when `K` is one; `v` is of type `V`. The map of a `for` loop is worked
out once, before the first pass, so `for k in Maps() do` calls `Maps`
once.

An entry is written through its place as a variable is: `m[k] += e` and
every `op=` form, `Inc(m[k])`, `Dec(m[k], n)`, `m[k].X := e` and
`m[k][i] := e` for a record or a static array held in the map, `with
m[k] do X := 1`, `SetLength(m[k], n)` for a slice held in the map, and
`m[k]` or `m[k].X` as a `var` argument. The key is inserted with a zero
value when it was missing, so `m[k] += 1` counts from zero and
`where['work'].X := 5` holds a record whose other fields are zero; the
map and the key are worked out once, so `Maps()[Key()] += 1` calls each
once. `m[k].X` of a missing key reads zero, as `m[k]` does. `@m[k]` is
refused: the slot moves when the map grows (a `var` argument holds it
for the call alone, so the routine called must not insert into the same
map). `Delete` and `Clear` zero the slots they empty, so a value or a
key that held a string, a slice or an object is freed by the collector
once nothing else holds it. A map goes only where its own map type goes,
`map[string] of Integer` into `map[string] of Integer` written anywhere,
in another unit too; a `nil` goes into any map.

The map is the Swiss table of Go's runtime: groups of eight slots with
a control byte per slot, quadratic probing and a load of 7/8, in a
directory of tables of at most 1024 slots each (1.0.59). A table doubles
until it has 1024 slots and then splits in two, so a growing map never
holds an old and a new copy of all of itself at once. Keys hash with
XXH3 (1.0.64): a string's bytes as `XxHash3` hashes them, an eight-byte
key through XXH3's path for 4 to 8 bytes, in line. Every map has a seed
of its own, drawn from one `getrandom` per process, so the order differs
between runs and between two maps. A map is not safe for two routines
writing at once; the runtime stops the program with
`paslang: concurrent map writes` when it catches that. Use a mutex.

### Trees: the ordered map and set

`tree[K] of V` is a map whose keys are kept in order, and `tree of K`
a set: a B+ tree in memory (nodes of up to 32 keys, the values in the
leaves, the leaves linked), the core unit `pastree`. `K` is an ordinal,
a `string`, a pointer or a class, in the order `<` gives; `V` is any
type. Every word of the map works (`New`, `t[k]`, `t[k] := v`, `k in t`,
`TryGet`, `Delete`, `Clear`, `Length`, `for k in t`, `for k, v in t`),
and a walk goes in key order: `downto` walks it backwards and
`for k, v in t[a..b] do` walks the keys from `a` to `b`, both included.
The plain walk steps from slot to slot and leaf to leaf without a
call (1.1.1: a million keys walk in 4 ms). A walk that meets another
routine's write in progress stops the program (`paslang: tree walk
during a write`). The walking routine's own writes are not caught: a
walk that inserts or deletes may skip keys or see one twice, so collect
the keys first and change the tree after the walk.

`examples/trees.paslang`:

```pascal
{ An ordered map, a set, a heap, the hash words and the store. }
program trees;

var
  ages: tree[string] of Integer;
  seen: tree of Integer;
  todo: heap of Integer;
  name: string;
  age: Integer;
  db: store;

begin
  New(ages);
  ages['ana'] := 31;
  ages['luis'] := 27;
  ages['maria'] := 44;
  ages['jon'] := 27;
  for name, age in ages do
    WriteLn(name, ' ', age);                 { in key order: ana, jon, luis, maria }
  WriteLn(Low(ages), ' ', High(ages), ' ', Length(ages));   { ana maria 4 }
  WriteLn(Succ(ages, 'jon'), ' ', Pred(ages, 'jon'));       { luis ana }
  WriteLn(Floor(ages, 'k'), ' ', Ceil(ages, 'k'));          { jon luis }
  WriteLn(Rank(ages, 'luis'), ' ', KeyAt(ages, 0));         { 2 ana }
  for name, age in ages['b'..'m'] do
    Write(name, ' ');                        { jon luis }
  WriteLn;
  for name in ages downto do
    Write(name, ' ');                        { maria luis jon ana }
  WriteLn;
  if PopLow(ages, name, age) then
    WriteLn(name, ' ', age, ' ', Length(ages));   { ana 31 3 }

  New(seen);
  Include(seen, 7);
  seen[3] := True;
  Include(seen, 7);
  WriteLn(seen[3], ' ', seen[5], ' ', 7 in seen, ' ', Length(seen));   { 1 0 1 2 }

  New(todo);
  Push(todo, 30);
  Push(todo, 10);
  Push(todo, 20);
  WriteLn(Low(todo), ' ', Pop(todo), ' ', Pop(todo), ' ', Length(todo));   { 10 10 20 1 }

  WriteLn(Hex(Sha256('abc')));
  WriteLn(Hex(Md5('abc')), ' ', Crc32('abc'), ' ', Crc32c('abc'));
  WriteLn(Hex(HmacSha256('key', 'The quick brown fox jumps over the lazy dog')));

  db := StoreOpen('/tmp/paslang-trees-example');
  StorePut(db, 'greeting', 'hello');
  StorePut(db, 'count', '3');
  StoreDelete(db, 'count');
  WriteLn(StoreGet(db, 'greeting'), ' ', 'count' in db, ' ', 'greeting' in db);   { hello 0 1 }
  StoreClose(db);
end.
```

prints

```
ana 31
jon 27
luis 27
maria 44
ana maria 4
luis ana
jon luis
2 ana
jon luis 
maria luis jon ana 
ana 31 3
1 0 1 2
10 10 20 1
ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
900150983cd24fb0d6963f7d28e17f72 891568578 910901175
f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8
hello 0 1
```

The order words: `Low(t)` and `High(t)` are the first and the last
key; `Succ(t, k)` and `Pred(t, k)` the key after and before `k`
(`k` need not be in the tree); `Floor(t, k)` the greatest key not above
`k` and `Ceil(t, k)` the least not below. When there is none the
program stops (`paslang: empty tree`, `paslang: tree succ`, …), so ask
`Length`, `in` or `Rank` first. `Rank(t, k)` is how many keys lie
below `k`, `KeyAt(t, i)` the key of rank `i` (from 0), both counted
from the nodes, not walked. `PopLow(t, k, v)` and `PopHigh(t, k, v)`
take the least or the greatest entry out into `k` and `v` and say
whether there was one; a `tree of K` takes `PopLow(t, k)`.
`u := Split(t, k)` moves the keys from `k` up into a new tree `u`;
`Join(t, u)` moves every entry of `u` into `t`, `u`'s value winning
where both have a key, and leaves `u` empty.

A `tree of K` is a set: `t[k]` reads `True` or `False` (`k in t` too),
`Include(t, k)` and `t[k] := True` put `k` in, `Exclude(t, k)`,
`Delete(t, k)` and `t[k] := False` take it out; `t[k] += 1` and
`TryGet` are refused, since there is no value. `Include` and `Exclude`
on a `set` are refused with the spelling that works there,
`s := s + [x]`. A tree goes only into its own tree type; `nil` reads as
empty and writing to a `nil` tree stops the program. Two routines
writing at once, or a walk during a write, stop it too.

### Heaps

`heap of T` is a binary min-heap (Go's `container/heap` on an array):
`New(h)`, `Push(h, x)`, `Pop(h, x)` takes the least element into `x`
and says whether there was one, `Pop(h)` gives it and `Low(h)` shows it
(an empty heap stops the program with `paslang: empty heap`), and
`Length(h)` counts. `T` is an ordinal, a `string`, a `Double` or a
`Single` (a `Quad` is refused).

The order of the heap is the `<` of `T`: an ordinal as a signed number,
a `string` byte by byte as §13 has it, so `''` comes first and `'B'`
before `'a'`, and a real by value, `-0.0` and `0.0` being equal. A
push or a pop moves one element up or down the tree of the array,
about `Log2(n)` compares; the array starts with room for 16 elements
and doubles when it is full. `Length(h)` of a `nil` heap is 0 and
`Pop(h, x)` of one is `False`, but `Push` on a `nil` heap stops the
program with `paslang: nil heap`: `New(h)` first. A heap kept at `k`
elements, one `Pop` after every `Push` past `k`, holds the `k` largest
seen so far, the least of them at `Low(h)`; `examples/sorting.paslang`
(§16) uses one as a priority queue of strings and one as a top three.

### The store

`store` is a key-value store on disk: `db := StoreOpen(path)` makes or
opens `path` and `path.wal`; `StorePut(db, k, v)`, `StoreGet(db, k)`
(`''` when the key is absent), `k in db`, `StoreDelete(db, k)`,
`StoreSync(db)` (the log written to the disk), `StoreClose(db)` (what
is in memory written as a run of the table, the files closed) and
`StoreAbandon(db)` (the files closed as a crash would leave them: the
log brings the writes back on the next open). Keys and values are
strings of any length. It is a log-structured merge store on the tree,
after LevelDB: every write goes to the log first, in a record with its
CRC32C, and a log torn by a crash is cut at its last whole record; past
a megabyte of log the memory table becomes a run of sorted blocks with
an index the store keeps in memory; past four runs they are merged into
one, written beside the table and renamed over it, so the space of the
old runs comes back. A read looks at memory, then at the runs, newest
first.

`examples/kvstore.paslang`:

```pascal
{ The store: a key-value database in two files, the table and its log.
  A put or a delete goes to the log first; StoreAbandon closes the files
  as a crash would leave them, and the next open replays the log. }
program kvstore;

const
  Path = '/tmp/paslang-kvstore-example';

var
  db: store;
  i: Integer;

{ unlink(2) is 87 on amd64; arm64 has only unlinkat(2), 35. }
procedure Remove(const Name: string);
var
  z: string;
begin
  z := Name + #0;
  if Amd64 = 1 then
    Syscall(87, Integer(@z[1]))
  else
    Syscall(35, -100, Integer(@z[1]), 0);
end;

begin
  Remove(Path);                          { start clean }
  Remove(Path + '.wal');
  db := StoreOpen(Path);                 { makes the table and the log }
  for i := 1 to 5 do
    StorePut(db, 'key' + Chr(Ord('0') + i), 'value ' + Chr(Ord('0') + i));
  StorePut(db, 'key3', 'three');         { the newest value wins }
  StorePut(db, 'empty', '');
  StoreDelete(db, 'key2');
  WriteLn(StoreGet(db, 'key3'), ' ', StoreGet(db, 'key2') = '', ' ', 'key2' in db);   { three 1 0 }
  WriteLn(StoreGet(db, 'empty') = '', ' ', 'empty' in db);   { 1 1: in tells an empty value from a missing key }
  StoreSync(db);                         { the log reaches the disk }
  StoreAbandon(db);                      { a crash: what was in memory is gone }
  db := StoreOpen(Path);                 { the log is replayed }
  WriteLn(StoreGet(db, 'key1'), ' ', StoreGet(db, 'key3'), ' ', 'key2' in db);   { value 1 three 0 }
  StorePut(db, 'key6', 'value 6');
  StoreClose(db);                        { memory becomes a run of the table; the log is emptied }
  db := StoreOpen(Path);
  WriteLn(StoreGet(db, 'key6'), ' ', 'key5' in db, ' ', 'key2' in db);   { value 6 1 0 }
  StoreDelete(db, 'key1');               { a delete of a key that lives in a run }
  StoreClose(db);
  db := StoreOpen(Path);
  WriteLn('key1' in db, ' ', StoreGet(db, 'key4'));   { 0 value 4 }
  StoreClose(db);
  Remove(Path);                          { so the next run starts clean too }
  Remove(Path + '.wal');
end.
```

prints

```
three 1 0
1 1
value 1 three 0
value 6 1 0
0 value 4
```

The two files: `path` is the table, which begins with a header page of
4096 bytes (the magic `PLST`, the version, the bytes in use and the
list of runs, each one's place, length, index and number of keys) and
goes on with the runs; `path.wal` is the log. A new store is a table of
one header page and an empty log. Every `StorePut` and `StoreDelete`
appends one record to the log, eight bytes of head (the length and the
CRC32C) and a body of the operation, the key's and the value's lengths
as four bytes each, the key and the value, so a put of a one-byte key
and a one-byte value adds 19 bytes; the write goes to the kernel at
once and `StoreSync` (`fsync` of the log alone) makes it reach the
disk. So what survives: after the process dies, every put and delete
before it, `StoreSync` or not, since the kernel holds them; after a
power cut, those before the last `StoreSync` for sure and later ones
as far as the disk got. A record cut in the middle fails its length
or its CRC, the replay stops there and the log is cut back to the last
whole record; the runs are never in doubt, since the header that
names a run is written after the run's blocks were synced, and a
merge writes `path.new` whole and renames it over `path`. `StoreClose`
writes the memory table as a run, syncs, and empties the log: after
it, the log is 0 bytes and every entry is in the table, a data block
being 4 bytes of count and the entries, each with its two lengths,
one byte that marks a deleted key, the key and the value. The same
flush happens on its own once the log passes 1048576 bytes, so the
memory table holds at most about a megabyte of writes, and past four
runs the fifth flush merges them into one. Lengths are four bytes in
every record, so a key or a value goes up to 4 GiB; the memory table
is a `tree[string] of string` and holds copies of the strings given.
An empty value is a value: `'empty' in db` is `True` while `StoreGet`
gives `''` for it and for a missing key alike. The store takes no lock
of its own; two routines that use one at once must hold a mutex
(§12). `StorePut` and `StoreDelete` on a `store` that was never
opened stop the program with `paslang: nil store` (a `StoreGet` gives
`''` and `k in db` `False`); a path that cannot be made stops it with
`paslang: store open <path>`, and a file that is not a table with
`paslang: store magic <path>`, leaving it as it was (an empty file is
a new store). `StoreAbandon` is for tests of the
recovery, as in the example; a program that is done with a store
closes it.

## 12. Sync: mutex, rwmutex, waitgroup, cond, once

`examples/sync.paslang`:

```pascal
{ Sync: a mutex with lock, a waitgroup, once, an rwmutex and a cond.
  These types belong to the language and start ready; no uses, no Create. }
program sync;

var
  mu: mutex;
  wg: waitgroup;
  rw: rwmutex;
  init: once;
  ready: cond;
  counter, shared, hits, go, i: Integer;

procedure Worker(K: Integer);
var
  j: Integer;
begin
  for j := 1 to 100 do
    lock mu do                       { held for the statement, then released }
      counter := counter + 1;
  wg.Done;                           { one less routine to wait for }
end;

procedure Setup;
begin
  hits := hits + 1;
end;

procedure Starter(K: Integer);
begin
  once init do                       { one routine runs Setup; the rest wait }
    Setup;
  wg.Done;
end;

procedure Reader(K: Integer);
var
  v: Integer;
begin
  lock rw read do                    { readers share the lock }
    v := shared;
  lock mu do
    counter := counter + v;
  wg.Done;
end;

procedure Waiter(K: Integer);
begin
  mu.Lock;                           { the explicit form of lock }
  while go = 0 do
    ready.Wait(mu);                  { releases mu while parked }
  counter := counter + 1;
  mu.Unlock;
  wg.Done;
end;

begin
  wg.Add(4);
  for i := 1 to 4 do
    pas Worker(i);
  wg.Wait;                           { parks until the four called Done }
  WriteLn(counter);                  { 400 }
  wg.Add(3);
  for i := 1 to 3 do
    pas Starter(i);
  wg.Wait;
  WriteLn(hits, ' ', init.Done);     { 1 1 }
  lock rw do                         { the writer holds it alone }
    shared := 10;
  counter := 0;
  wg.Add(3);
  for i := 1 to 3 do
    pas Reader(i);
  wg.Wait;
  WriteLn(counter);                  { 30 }
  counter := 0;
  wg.Add(2);
  pas Waiter(1);
  pas Waiter(2);
  Sleep(10);
  lock mu do
  begin
    go := 1;
    ready.Broadcast;                 { wake every waiter }
  end;
  wg.Wait;
  WriteLn(counter);                  { 2 }
end.
```

prints

```
400
1 1
30
2
```

The five sync types are reserved words. Their zero value is ready to
use: declare one where you need it, global, local or in a record, and
never create it.

| Type | Size | Methods | Statement |
|------|------|---------|-----------|
| `mutex` | 32 | `Lock`, `Unlock`, `TryLock` | `lock mu do stmt` |
| `rwmutex` | 48 | `Lock`, `Unlock`, `BeginRead`, `EndRead` | `lock rw do stmt`, `lock rw read do stmt` |
| `waitgroup` | 24 | `Add(n)`, `Done`, `Wait` | |
| `cond` | 16 | `Wait(mu)`, `Signal`, `Broadcast` | |
| `once` | 32 | `Done` | `once o do stmt` |

`lock mu do stmt` takes the mutex, runs the statement and releases it on
every way out: the end, `exit`, `break`, `continue` or a `raise`. A
locked routine that must wait parks; the thread goes on running other
routines. `rwmutex` lets any number of readers in together and one
writer alone, and a waiting writer stops new readers. `waitgroup`
counts routines: `Add` before starting them, `Done` in each, `Wait`
parks until the count is zero. A `Done` that takes the count below
zero, or an `Unlock` of a mutex nobody holds, stops the program with a
`paslang:` message and exit status 1. `cond.Wait(mu)` releases the mutex,
parks until `Signal` wakes one waiter or `Broadcast` wakes all, and
takes the mutex again before returning, so always test the condition in
a loop. `once o do stmt` runs the statement the first time and never
again; routines that arrive while it runs wait for it to finish, and
`o.Done` tells whether it has run.

What a `waitgroup` counts is one `Integer`, moved by an atomic add:
`Add(n)` adds `n`, from any routine, before the routines it counts are
started (an `Add` inside the routine could run after the `Wait`);
`Done` is `Add(-1)`; `Wait` returns at once when the count is zero and
parks otherwise. The call that brings the count to zero wakes every
routine parked in `Wait`, so several may wait on one waitgroup, and a
waitgroup whose count came back to zero is reused with a new `Add`.
The count going below zero, one `Done` too many, stops the program
with `paslang: negative waitgroup counter`; the same for a mutex is
`paslang: unlock of an unlocked mutex`. A `mutex` is not reentrant:
`lock mu do` inside `lock mu do` parks the routine on itself, and with
nothing else to run the program stops with the deadlock message
(§10). `TryLock` never parks: it takes the mutex when it is free and
says whether it did. `examples/pipeline.paslang` (§10) counts the
workers of a pool with a waitgroup.

### A map and routines together

`examples/wordcount.paslang` counts the words of a text with four
routines writing into one shared map. The mutex keeps the writers
apart, the waitgroup ends the wait, and the keys are sorted before
printing because a map walk has no fixed order:

```pascal
{ Word frequencies: a map and pasroutines working together.

  What the program does, step by step:
  1. Fills a slice of six lines of text.
  2. Creates the map freq with New(freq, 64): word -> count, with room
     for 64 words before the table first grows.
  3. Tells the waitgroup wg to expect four Done calls, then starts four
     Worker routines with pas. Each worker takes every fourth line
     (worker K takes the lines K, K + 4, K + 8, ...).
  4. Every worker splits its lines into words and adds one to the count
     of each word in the shared map. The mutex mu lets one writer in at
     a time; a map is not safe for two routines writing at once.
  5. wg.Wait parks the main routine until the four workers have called
     Done. The thread is not blocked: it runs the workers meanwhile.
  6. Prints the number of distinct words, copies the keys into a slice,
     sorts them (a map walks its entries in no fixed order) and prints
     each word with its count.
  7. Reads one count with TryGet and tests one missing word with in.

  Routines:
  - Less(A, B): True when A sorts before B, comparing byte by byte and,
    on a common prefix, by length. Used by the sort; it gives the same
    order as < on strings.
  - CountLine(Line): walks the bytes of Line, cuts each run of non-space
    bytes with Copy, and under lock mu adds one to freq[word]. A missing
    key reads as 0, so the first occurrence needs no special case.
  - Worker(K): calls CountLine on the lines K, K + Workers, K + 2 *
    Workers, ... and then calls wg.Done to say it has finished.
  - The main routine: steps 1 to 7 above, including the insertion sort
    over the key slice.

  The output is the same on every run: the sums do not depend on which
  worker counted which line, and the printing order is the sorted one. }
program wordcount;

const
  Workers = 4;

var
  text: array of string;         { the lines to count }
  freq: map[string] of Integer;  { word -> count, shared by every worker }
  mu: mutex;                     { guards freq; ready without Create }
  wg: waitgroup;                 { counts the running workers }

{ True when A sorts before B, byte by byte. }
function Less(const A, B: string): Boolean;
var
  i, n: Integer;
begin
  n := Length(A);
  if Length(B) < n then
    n := Length(B);
  for i := 1 to n do
    if A[i] <> B[i] then
    begin
      Result := A[i] < B[i];
      Exit;
    end;
  Result := Length(A) < Length(B);
end;

{ Splits a line on spaces and counts each word in the shared map. }
procedure CountLine(const Line: string);
var
  i, start: Integer;
  w: string;
begin
  start := 1;
  for i := 1 to Length(Line) + 1 do
    if (i > Length(Line)) or (Line[i] = ' ') then
    begin
      if i > start then
      begin
        w := Copy(Line, start, i - start);
        lock mu do                { one writer at a time; released after the statement }
          freq[w] := freq[w] + 1; { a missing key reads as 0, so no test is needed }
      end;
      start := i + 1;
    end;
end;

{ Worker K takes the lines K, K + Workers, K + 2 * Workers, ... }
procedure Worker(K: Integer);
var
  i: Integer;
begin
  i := K;
  while i <= High(text) do
  begin
    CountLine(text[i]);
    i := i + Workers;
  end;
  wg.Done;                       { one worker less to wait for }
end;

var
  keys: array of string;
  k, tmp: string;
  i, j, n: Integer;

begin
  SetLength(text, 6);
  text[0] := 'the quick brown fox';
  text[1] := 'jumps over the lazy dog';
  text[2] := 'the dog sleeps';
  text[3] := 'the fox runs';
  text[4] := 'quick quick quick';
  text[5] := 'lazy dog lazy fox';
  New(freq, 64);                 { room for 64 words before the table grows }
  wg.Add(Workers);               { four Done calls are expected }
  for i := 0 to Workers - 1 do
    pas Worker(i);               { each worker is a routine on the scheduler }
  wg.Wait;                       { parks until the count is back to zero }
  WriteLn(Length(freq), ' distinct words');
  SetLength(keys, Length(freq)); { collect the keys, then sort them }
  n := 0;
  for k in freq do
  begin
    keys[n] := k;
    n := n + 1;
  end;
  for i := 1 to n - 1 do         { insertion sort on the key array }
  begin
    tmp := keys[i];
    j := i - 1;
    while (j >= 0) and Less(tmp, keys[j]) do
    begin
      keys[j + 1] := keys[j];
      j := j - 1;
    end;
    keys[j + 1] := tmp;
  end;
  for i := 0 to n - 1 do
    WriteLn(keys[i], ' ', freq[keys[i]]);
  if TryGet(freq, 'the', i) then { read and test in one step }
    WriteLn('the appears ', i, ' times');
  if not ('cat' in freq) then    { in tests membership without inserting }
    WriteLn('no cat');
end.
```

prints

```
10 distinct words
brown 1
dog 3
fox 3
jumps 1
lazy 3
over 1
quick 4
runs 1
sleeps 1
the 4
the appears 4 times
no cat
```

The hint in `New(freq, 64)` is the number of entries the map holds
before its first growth, not a raw slot count. A hint of up to 896
makes one table, which starts at 8 slots (7 entries) and doubles until
seven eighths of it hold the hint; a larger one makes as many tables of
1024 slots as hold it at half load. There is no way to fix a size in
the declaration, as in Go; `New` is the only place, and the map never
shrinks. `Less` in this example compares the bytes by hand; since
strings take `<` (§13), `A < B` gives the same order.

## 13. Strings and hashing

`examples/strings.paslang`:

```pascal
{ Strings are UTF-8 bytes with a 64-bit length: index by byte, walk by
  Unicode scalar, cut with Copy, hash with xxHash. }
program strings;

var
  s, t: string;
  i, n: Integer;
  r: Rune;

begin
  s := 'Pascal';
  WriteLn(Length(s), ' ', Ord(s[1]));            { 6 80: s[1] is the byte P }
  t := '';
  for i := Length(s) downto 1 do
    t := t + Copy(s, i, 1);                       { Copy(s, from, count) }
  WriteLn(t);                                     { lacsaP }
  WriteLn(Copy(s, 1, 3) + '-' + Copy(s, 4, 3));   { Pas-cal }
  s := 'niño';
  WriteLn(Length(s));                             { 5 bytes }
  n := 0;
  for r in s do                                   { 4 Unicode scalars }
    n := n + 1;
  WriteLn(n);
  WriteLn(XxHash32('abc'), ' ', XxHash64('abc', 7) <> 0);   { the reference vector, a seeded hash }
  s := '';
  SetLength(s, 3);                                { size a string, then write bytes }
  s[1] := 'a';
  s[2] := 'b';
  s[3] := 'c';
  WriteLn(s, ' ', s = 'abc');                     { abc 1 }
end.
```

prints

```
6 80
lacsaP
Pas-cal
5
4
852579327 1
abc 1
```

A string is a pointer and a 64-bit byte length: no 255 limit, no length
byte in front, no required trailing zero. Assignment copies the pointer
and the length; concatenation allocates a new buffer. `'ab'#10'c'` is one
string with a newline inside. `s[i]` is a byte, 1-based. `Length` counts
bytes and `for r in s do` walks Unicode scalars. `Copy(s, from, count)`
cuts, `SetLength(s, n)` sizes, `=` and `<>` compare bytes, 64 at a
time on AVX2 or SSE2 (or NEON) as Go's `memequal` does. `<`, `<=`,
`>` and `>=` compare them byte by byte as well: the first byte that
differs decides, and when one string is a prefix of the other the
shorter one comes first, so a list of names sorts the way you expect.
`IntToStr` and `StrToInt64` of `uses paslib` convert (§15).

Pascal's string words are there, as Free Pascal has them (1.1.10):
`Pos(sub, s)` and `Pos(sub, s, from)` give the place from 1 of `sub`
in `s`, 0 when it is not there (a `Char` too); `Insert(src, s, i)` puts
`src` before `s[i]`; `Delete(s, i, n)` takes `n` characters out from
`s[i]`; `Copy(s, i)` is the rest from `s[i]`; `Concat(a, b, ...)` is
`a + b + ...`; `UpCase` and `LowerCase` of a `Char` or of a string
change its ASCII letters; `StringOfChar(c, n)` is `n` times `c`;
`Str(x:w:d, s)` puts in `s` what `Write` would write (an
enumeration's member by its name, padded on the right); and `Val(s, v,
code)` reads a number into `v` (decimal, `$` or `0x` hexadecimal, `%`
binary, `&` octal, blanks first), a real or an enumeration's member,
`code` 0 or the place of the first character it could not read. Into
an unsigned type (`Byte`, `Word`, `UInt32`, a subrange from 0) it
reads a decimal number up to 2^64 - 1 and keeps its low bits, as Free
Pascal does: `'300'` into a `Byte` is 44, code 0 (1.1.17, P142; past
2^63 was an error). An
index out of the string does what Free Pascal does: `Insert` at 0
puts in front, `Delete` past the end does nothing, `Copy` from 0
starts at 1. `Pos` searches with the processor's vectors (AVX2, SSE2 or
NEON) for the first byte and compares the rest 64 bytes at a time, as
Go's `strings.Index` does (`docs/KERNELS.md`).

The hash words take a string and give its digest as a string of bytes
(`Hex(s)` writes any string as lowercase hex): `Md5`, `Sha1`, `Sha224`,
`Sha256`, `Sha384`, `Sha512`, `Sha3_224`, `Sha3_256`, `Sha3_384` and
`Sha3_512`, and `HmacMd5(key, msg)`, `HmacSha1`, `HmacSha224`,
`HmacSha256`, `HmacSha384` and `HmacSha512` (RFC 2104). The checksums
give an `Integer`: `Crc32(s)` (Ethernet's and zlib's polynomial),
`Crc32c(s)` (Castagnoli), `Adler32(s)`, each with an optional second
argument, the value so far, to go on from (`Crc32(b, Crc32(a))` is
`Crc32(a + b)`; Adler-32 starts from 1); `Fnv1a32(s)` and `Fnv1a64(s)`;
`Murmur3(s)` and `Murmur3(s, seed)` (MurmurHash3, 32 bits); and
`SipHash(s, k0, k1)` (SipHash-2-4 under a 128-bit key in two words).
The 64-bit words print negative when their top bit is set, as `XxHash64`
does. `MerkleRoot(leaves)`, `MerkleProof(leaves, i)` and
`MerkleCheck(leaf, i, n, proof, root)` are the Merkle tree of RFC 9162
on `Sha256`. Each algorithm is written as its standard writes it, in
the core unit `pashash`, and SHA-1, SHA-256, SHA-512 and the CRCs also
have a body on the processor's own instructions (SHA-NI, SSE4.2's
`crc32`, PCLMULQDQ on amd64; FEAT_SHA1, FEAT_SHA256, FEAT_SHA512,
FEAT_CRC32 on arm64) that the program calls when it is compiled for a
processor that has them (`-cpu`, §20, and `docs/KERNELS.md`).

`examples/hashes.paslang`:

```pascal
{ The hash words on one text: digests as strings of bytes that Hex
  writes out, an HMAC under a key, the checksums in one piece and in
  two, a keyed SipHash, and a Merkle tree of five leaves with an
  inclusion proof that is checked, then refused for a changed leaf. }
program hashes;

var
  text, key, root, proof: string;
  leaves, one: array of string;
  i: Integer;

begin
  text := 'The quick brown fox jumps over the lazy dog';
  WriteLn(Hex(Sha256(text)));
  WriteLn(Hex(Sha1(text)), ' ', Length(Sha1(text)));      { 20 bytes, 40 hex digits }
  WriteLn(Hex(Md5(text)), ' ', Length(Md5(text)));        { 16 }
  WriteLn(Length(Sha512(text)), ' ', Length(Sha3_512(text)), ' ', Length(Hex(Sha384(text))));   { 64 64 96 }
  key := 'secret';
  WriteLn(Hex(HmacSha256(key, text)));
  WriteLn(Crc32(text), ' ', Crc32c(text), ' ', Adler32(text));
  WriteLn(Crc32(Copy(text, 21, 23), Crc32(Copy(text, 1, 20))) = Crc32(text), ' ',
    Adler32(Copy(text, 21, 23), Adler32(Copy(text, 1, 20))) = Adler32(text));   { 1 1: in two pieces }
  WriteLn(SipHash(text, $0706050403020100, $0f0e0d0c0b0a0908));   { under a 128-bit key }
  WriteLn(Fnv1a32(text), ' ', Murmur3(text, 42));
  SetLength(leaves, 5);
  for i := 0 to 4 do
    leaves[i] := 'entry ' + Chr(Ord('0') + i);
  root := MerkleRoot(leaves);
  WriteLn(Hex(root));
  proof := MerkleProof(leaves, 2);                          { the siblings from the leaf up }
  WriteLn(Length(proof) div 32);                            { 3 }
  WriteLn(MerkleCheck(leaves[2], 2, 5, proof, root), ' ',
    MerkleCheck('entry x', 2, 5, proof, root), ' ',
    MerkleCheck(leaves[2], 3, 5, proof, root));             { 1 0 0 }
  SetLength(one, 1);
  one[0] := leaves[0];
  WriteLn(Hex(MerkleRoot(one)) = Hex(Sha256(Char(0) + 'entry 0')));   { 1: a leaf is SHA-256 of 0x00 and the entry }
end.
```

prints

```
d7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592
2fd4e1c67a2d28fced849ee1bb76e7391b93eb12 20
9e107d9d372bb6826bd81d3542a419d6 16
64 64 96
54cd5b827c0ec938fa072a29b177469c843317b095591dc846767aa338bac600
1095738169 576848900 1541148634
1 1
5919806912997584868
76545936 880582914
7caa345dbd892a66454d6c6512ea3c3ea3f0d3ec21be3fc2e2375705fd38f672
3
1 0 0
1
```

A digest is as long as its standard says: `Md5` 16 bytes, `Sha1` 20,
`Sha224` and `Sha3_224` 28, `Sha256` and `Sha3_256` 32, `Sha384` and
`Sha3_384` 48, `Sha512` and `Sha3_512` 64, and an HMAC as long as its
hash. `Hex` gives two lowercase digits per byte, so a `Sha256` prints
as 64 characters, and `Hex('')` is `''`.

Which body a word calls is fixed by `-cpu` through these features:
`Sha1` and `HmacSha1` by `sha1`; `Sha224`, `Sha256`, `HmacSha224`,
`HmacSha256` and the three Merkle words by `sha2` (on amd64 both are
SHA-NI's `sha`); `Sha384`, `Sha512`, `HmacSha384` and `HmacSha512` by
`sha512`, which amd64 never has, so there the Pascal rounds serve;
`Crc32c` by `sse42` on amd64 and `crc32` on arm64; `Crc32` by `pclmul`
and `sse41` together on amd64 (the folding takes a message of 64 bytes
or more, sixteen at a time, and the table finishes the tail) and by
`crc32` on arm64. `Md5`, `HmacMd5`, the SHA-3 words, `Adler32`,
`Fnv1a32`, `Fnv1a64`, `Murmur3`, `SipHash` and `Hex` have one body.
`-cpu base`, and a program compiled across (arm64 from an amd64
machine) with no `-cpu`, call the Pascal bodies everywhere; the bytes are the same
either way (`make check` runs `testdata/hash1` both ways, on both
machines).

`SipHash`'s key is its 16 bytes as two little-endian words, so the
paper's key `00 01 … 0f` is `SipHash(s, $0706050403020100,
$0f0e0d0c0b0a0908)`.

The Merkle words are RFC 9162, 2.1, on `Sha256`: a leaf's hash is
`Sha256` of the byte 0 and the entry, a node's `Sha256` of the byte 1
and its two children, the left child covering the largest power of two
of leaves below the count, and the tree of no leaves is `Sha256('')`.
The leaves are a slice of strings. `MerkleProof(leaves, i)` is the
proof of leaf `i`: the hashes of the siblings from the leaf up, 32
bytes each, in one string (the proof of the only leaf is `''`); an `i`
outside the leaves stops the program with `paslang: merkle index`.
`MerkleCheck(leaf, i, n, proof, root)` walks the proof up from the leaf
(RFC 9162, 2.1.3.2) and is `False` for an `i` outside `0..n-1`, a proof
whose length is not a multiple of 32, or one that does not reach
`root`: the wrong entry and the wrong index both fail.

`XxHash32(s)`, `XxHash64(s)` and `XxHash3(s)` hash the bytes of a
string with xxHash; an optional second argument is the seed.
`XxHash32('abc')` is 852579327, the reference vector of the algorithm.
`XxHash3` is XXH3 with 64 bits, the reference's `XXH3_64bits_withSeed`
and the fastest of the three: a string of up to 16 bytes costs a read
or two and a multiply, a long one goes 64 bytes at a time through vector
registers (AVX2 when the program is compiled for it, SSE2 otherwise;
NEON on arm64), about 2.3 ns for 16 bytes and 75 GB/s for a megabyte on the
machine it was measured on. `XxHash64` and `XxHash3` return all 64 bits
in an `Integer`, so a hash with the top bit set prints negative.

### The algorithms

Every word here takes the bytes of a string and is written as its
standard writes it. A digest
comes back as a string of raw bytes, a checksum or a fast hash as an
`Integer`. The words are reserved (§19): no routine or variable of a
program takes their names.

| Word | Algorithm | Gives | Takes | On the processor (`-cpu`) | Use it for |
|---|---|---|---|---|---|
| `Md5(s)` | MD5, RFC 1321: 64-byte blocks, 64 steps of 32-bit words | 16 bytes | a string | the Pascal rounds | fingerprints in old formats; never for security, collisions are cheap |
| `Sha1(s)` | SHA-1, FIPS 180-4: 64-byte blocks, 80 rounds | 20 bytes | a string | SHA-NI (`sha1`); FEAT_SHA1 | identifiers in the style of git; not for signatures, collisions have been made |
| `Sha224(s)`, `Sha256(s)` | SHA-2, FIPS 180-4: 64-byte blocks, 64 rounds | 28, 32 bytes | a string | SHA-NI (`sha2`); FEAT_SHA256 | the standard choice for integrity and signatures |
| `Sha384(s)`, `Sha512(s)` | SHA-2, FIPS 180-4: 128-byte blocks, 80 rounds of 64-bit words | 48, 64 bytes | a string | FEAT_SHA512 (`sha512`, arm64); Pascal on amd64 | the same, faster on long messages in software |
| `Sha3_224(s)` … `Sha3_512(s)` | SHA-3, FIPS 202: Keccak-f[1600], 24 rounds of a 200-byte sponge | 28 to 64 bytes | a string | the Pascal rounds | when a second family beside SHA-2 is wanted |
| `HmacMd5(key, msg)`, `HmacSha1`, `HmacSha224`, `HmacSha256`, `HmacSha384`, `HmacSha512` | HMAC, RFC 2104, over that hash | as long as its hash | two strings | as its hash | authenticating a message with a shared secret |
| `Crc32(s)`, `Crc32(s, sofar)` | CRC-32 of IEEE 802.3, polynomial `$EDB88320` reflected; zlib, gzip, PNG | 0 to 2³²-1 | a string, the value so far | PCLMULQDQ folding from 64 bytes (`pclmul` and `sse41`); FEAT_CRC32 | detecting errors; the formats that use it |
| `Crc32c(s)`, `Crc32c(s, sofar)` | CRC-32C of Castagnoli, RFC 3720, polynomial `$82F63B78` reflected; iSCSI, ext4, the store's log | 0 to 2³²-1 | the same | SSE4.2 `crc32`, three chains at once (`sse42`); FEAT_CRC32 | detecting errors, fastest of the checksums (33 GB/s on a Ryzen 9 5950X) |
| `Adler32(s)`, `Adler32(s, sofar)` | Adler-32, RFC 1950 | 0 to 2³²-1 | the same, from 1 | the Pascal loop | zlib streams |
| `Fnv1a32(s)`, `Fnv1a64(s)` | FNV-1a, 32 and 64 bits | an `Integer`, all its bits | a string | the Pascal loop | small tables, short keys, no seed |
| `Murmur3(s)`, `Murmur3(s, seed)` | MurmurHash3, x86 variant, 32 bits | 0 to 2³²-1 | a string, a seed | the Pascal rounds | hashing that other systems must reproduce |
| `SipHash(s, k0, k1)` | SipHash-2-4, a 128-bit key in two words | 64 bits in an `Integer` | a string, the key | the Pascal rounds | hash tables that an attacker must not flood |
| `XxHash32(s)`, `XxHash64(s)`, `XxHash3(s)`, each with an optional seed | xxHash: XXH32, XXH64 and XXH3 with 64 bits | 32 or 64 bits in an `Integer` | a string, a seed | XXH3's long path in AVX2 or SSE2, NEON on arm64 (`avx2`) | the map's own hash; the fastest here |
| `MerkleRoot(leaves)`, `MerkleProof(leaves, i)`, `MerkleCheck(leaf, i, n, proof, root)` | the Merkle tree of RFC 9162 on SHA-256 | 32 bytes; the siblings, 32 bytes each; a `Boolean` | a slice of strings; an index | `sha2` | the integrity of a list and a proof that an entry is in it |
| `Hex(s)` | | two lowercase digits per byte | any string | | printing a digest or any bytes |

SHA-2, SHA-3 and an HMAC over them are cryptographic: nobody makes two
texts with one digest. MD5 and SHA-1 were, and are not any more; keep
them for the formats that need them. The checksums and the fast hashes
(CRC, Adler-32, FNV, MurmurHash3, xxHash) are for speed and error
detection alone: a single byte changed changes them, but a text with a
chosen value is easy to make. SipHash sits between: fast, and safe as a
table's hash while its key is secret. A word with a body on the
processor's instructions and one in Pascal gives the same bytes from
both (`make check` runs `testdata/hash1` both ways on both machines);
the choice is made when the program is compiled (`-cpu`, §20).

### Hashing anything

The words take a string because a string is any bytes with a length.
The ways to get one:

- A text is one already, and `Char(65)` where a string goes is the
  one-byte string `'A'`, so `Sha1(Char(65))` is `Sha1('A')`.
- The bytes of a static array: `SetLength(s, n); Move(a, s[1], n)`; of
  a slice of bytes, `Move(sl[0], s[1], Length(sl))`.
- The bytes of a record: `SetLength(s, SizeOf(r))` and a loop over
  `PByte(@r)` into `s[i]`, padding included; the padding is zero, a
  local's as a global's, since every variable starts as zero (§3).
- A file: `ReadFile(path, data)` of `uses paslib` gives its whole
  content, `Sha256(data)` its digest; a file of hundreds of megabytes
  is one string, since a string is only bounded by memory.
- A stream in pieces: `Crc32`, `Crc32c` and `Adler32` go on from the
  value so far (`Crc32(part, crc)`), so a file read a block at a time
  gets the checksum of the whole. The digest words take the whole
  message: read it whole, or hash each block and put the block digests
  in a Merkle tree (`MerkleRoot`), which is what the large-file formats
  do.
- A key: `HmacSha256(key, msg)` for authentication, `SipHash(s, k0,
  k1)` for a table; a seed: `Murmur3(s, seed)`, `XxHash3(s, seed)`.

Compare two digests with `=`, keep one as the string it is, print it
with `Hex`. A digest of the same bytes is the same on both machines,
compiled for any processor.

`examples/digest.paslang`:

```pascal
{ Hashing anything: a text and one character, the bytes of an array
  and of a record, a file, a checksum carried on in pieces, a keyed
  hash, the seeded fast hashes, and digests compared with published
  vectors. }
program digest;

uses paslib;

type
  THeader = record
    Magic: Int32;
    Kind: Byte;
  end;

var
  a: array[0..3] of Byte;
  h: THeader;                        { a global: its padding bytes are zero }
  s, part, data: string;
  i, crc: Integer;
  p: PByte;

begin
  WriteLn(Hex(Sha256('abc')));       { the FIPS 180-4 vector }
  WriteLn(Hex(Md5('')), ' ', Sha1(Char(65)) = Sha1('A'));
  a[0] := 1;
  a[1] := 2;
  a[2] := 3;
  a[3] := 4;
  SetLength(s, 4);
  Move(a, s[1], 4);                  { the array's bytes as a string }
  WriteLn(Hex(s), ' ', Crc32(s) = Crc32(#1#2#3#4));
  h.Magic := $50534C50;
  h.Kind := 6;
  SetLength(s, SizeOf(h));
  p := PByte(@h);
  for i := 1 to SizeOf(h) do
    s[i] := Char(p[i - 1]);          { a record's bytes, padding included }
  WriteLn(SizeOf(h), ' ', Hex(s), ' ', Hex(Sha256(s)));
  WriteFile('/tmp/paslang-digest.txt', 'The quick brown fox jumps over the lazy dog');
  if ReadFile('/tmp/paslang-digest.txt', data) then
    WriteLn(Length(data), ' ', Hex(Sha1(data)));   { the classic SHA-1 vector }
  crc := 0;                          { a stream in pieces: the value so far goes on }
  for i := 1 to 4 do
  begin
    part := Copy(data, (i - 1) * 11 + 1, 11);
    crc := Crc32(part, crc);
  end;
  WriteLn(crc = Crc32(data), ' ', Adler32('dog', Adler32(Copy(data, 1, 40))) = Adler32(data));
  WriteLn(Hex(HmacSha256('key', data)));            { the RFC 2104 example everyone quotes }
  WriteLn(XxHash3(data), ' ', XxHash3(data, 42), ' ', Murmur3(data, 42), ' ', Fnv1a32(data));
  WriteLn(Sha256(data) = Sha256(Copy(data, 1, 20) + Copy(data, 21, 100)), ' ', Length(Sha3_512(data)));
end.
```

prints

```
ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
d41d8cd98f00b204e9800998ecf8427e 1
01020304 1
8 504c535006000000 ac351f88495f7ba75c401072992ff57efcad618790b0a30ac0a0e788bc2fa3af
43 2fd4e1c67a2d28fced849ee1bb76e7391b93eb12
1 1
f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8
-3567667132247329947 -5430228705035387610 880582914 76545936
1 64
```

The numbers printed are the published vectors: `Sha256('abc')` and
`Md5('')` of FIPS 180-4 and RFC 1321, the SHA-1 of the fox and the
HMAC-SHA256 under `key` of RFC 2104's examples.

### How the words are made

The algorithms live in the core unit `pashash` (the xxHash words are
the runtime's own, in assembly, since the map hashes with XXH3), which
every program links without `uses` (§15). `scripts/hashgen.py` writes that unit from
one template: each algorithm in Pascal with its rounds written out (the
only loop is over the blocks), and for SHA-1, SHA-256, SHA-512 and the
CRCs a second body in `asm amd64` and `asm arm64` after Go's assembly
and the processor manuals. A word with a kernel is exported twice,
`XxxCpu` and `XxxBase`; the compiler calls one of them by the processor
the program is compiled for, and the program tests nothing at run time
(`docs/KERNELS.md`). The reserved names are the parser's
(`InitReserved` in `src/compiler/pasparse.paslang`), and
`testdata/hash1` checks every digest, HMAC and checksum word against
Python's `hashlib`, `hmac` and `zlib` and the reference definitions
(`scripts/hashmodel.py`), `testdata/tree1` the Merkle words, and
`testdata/xxh32`, `xxh64` and `xxh3` the xxHash ones.
Adding an algorithm is the recipe in `docs/KERNELS.md`.

## 14. Reals and the calculation set

`examples/maths.paslang`:

```pascal
{ Reals and the calculation set. WriteLn prints a real with up to six
  decimals and always at least one. }
program maths;

var
  x: Real;

begin
  x := 2;
  WriteLn(Sqrt(x));                  { 1.414214 }
  WriteLn(Sin(0), ' ', Cos(0));      { 0.0 1.0 }
  WriteLn(Exp(0), ' ', Ln(1));       { 1.0 0.0 }
  WriteLn(Exp(1));                   { 2.718282 }
  WriteLn(Power(2, 10));             { 1024.0 }
  WriteLn(Floor(2.7), ' ', Ceil(2.1), ' ', Round(2.5), ' ', Trunc(2.7));   { 2 3 2 2 }
  WriteLn(Min(3, 9), ' ', Max(3, 9));   { 3 9 }
  WriteLn(Pi);                       { 3.141593 }
  WriteLn(Hypot(3, 4));              { 5.0 }
  WriteLn(10 / 4, ' ', 10 div 4, ' ', 10 mod 4);   { 2.5 2 2 }
end.
```

prints

```
1.414214
0.0 1.0
1.0 0.0
2.718282
1024.0
2 3 2 2
3 9
3.141593
5.0
2.5 2 2
```

The calculation set is the FPC Math family. Each routine takes an
integer or a real where a real goes (the integer becomes that real) and
gives a `Double`, unless the table says otherwise; angles are radians.
A value outside a routine's domain stops the program with a message and
its line, `paslang: sqrt domain at line 4`, rather than returning NaN;
the last column names the message. A result too big for a `Double` is
an infinity (`Exp(1000)` is `+Inf`), not a stop. There is no `Random`;
`pasrand` has random numbers (§16).

| Routine | Gives | Stops on (message) |
|---|---|---|
| `Abs(x)`, `Sqr(x)` | the absolute value, the square: of an integer an `Integer`, which wraps (`Abs` of the lowest `Integer` is itself), of a real a real of its type | |
| `Sqrt(x)` | the square root; `Sqrt(-0)` is -0, of a NaN a NaN | below 0 (`sqrt domain`) |
| `Sin(x)`, `Cos(x)`, `Tan(x)` | sine, cosine, tangent; of an infinity or a NaN, a NaN (1.0.136; they gave 0.0) | |
| `Cot(x)`, `Sec(x)`, `Csc(x)` | 1/tan, 1/cos, 1/sin; an infinity where the divisor is 0 (`Cot(0)`, `Csc(0)`) | |
| `ArcSin(x)`, `ArcCos(x)` | in -π/2..π/2, in 0..π | outside -1..1 (`arcsin domain`, `arccos domain`) |
| `ArcTan(x)` | in -π/2..π/2 | |
| `ArcTan2(y, x)` | the angle of the point (x, y), in -π..π, in every quadrant; `ArcTan2(0, 0)` is 0 | |
| `ArcCot(x)` | π/2 - `ArcTan(x)` | |
| `ArcSec(x)`, `ArcCsc(x)` | `ArcCos(1/x)`, `ArcSin(1/x)` | \|x\| below 1 (`arcsec domain`, `arccsc domain`) |
| `Sinh(x)`, `Cosh(x)`, `Tanh(x)` | the hyperbolic functions; `Tanh` is ±1 from \|x\| ≥ 20 | |
| `ArcSinh(x)` | the inverse of `Sinh`, odd | |
| `ArcCosh(x)` | the inverse of `Cosh`, 0 or more | below 1 (`arccosh domain`) |
| `ArcTanh(x)` | the inverse of `Tanh` | outside -1 < x < 1 (`arctanh domain`) |
| `Ln(x)`, `Log10(x)`, `Log2(x)` | the logarithm to base e, 10, 2 | 0 or below (`ln domain`, `log domain`) |
| `LogN(base, x)` | the logarithm of `x` to `base` | a base or an `x` of 0 or below, a base of 1 (`log domain`) |
| `LnXP1(x)` | ln(1 + x), accurate for a small `x` | `1 + x` of 0 or below (`lnxp1 domain`) |
| `Exp(x)` | e to the `x` | |
| `Power(base, e)` | `base` to the `e`; `Power(x, 0)` is 1, `Power(0, -1)` +Inf, and a negative base with a whole exponent works (`Power(-2, 3)` is -8) | a negative base with an exponent that is not whole (`power domain`) |
| `Hypot(x, y)` | √(x² + y²) | |
| `Ldexp(x, p)` | x × 2^p; `p` is an `Integer`, a real is a compile error | |
| `Poly(x, a)` | a[0] + a[1]·x + a[2]·x² + …, by Horner; `a` is an `array of Real` | |
| `Int(x)`, `Frac(x)` | the whole part toward zero, and the rest with x's sign: `Int(-2.75)` is -2.0, `Frac(-2.75)` -0.75 | |
| `Trunc(x)`, `Round(x)`, `Floor(x)`, `Ceil(x)` | an `Integer`: toward zero, to the nearest with a tie to even, toward -∞, toward +∞ | a NaN, an infinity or a value no `Integer` holds (`real out of integer range`, §3) |
| `Min(a, b)`, `Max(a, b)` | the smaller, the larger: of two integers an `Integer`, of two reals a real; an integer with a real is a compile error | |
| `Odd(n)` | a `Boolean`, the low bit of an integer; a real is a compile error | |
| `IsNan(x)`, `IsInfinite(x)` | a `Boolean`: x is a NaN; x is +Inf or -Inf | |
| `Pi` | π, written `Pi` or `Pi()`; a constant that takes the real type it meets, all 113 bits in a `Quad` | |

`Single` is IEEE binary32, 4 bytes, worked out in 32 bits like Go's
`float32`. A `Single` with a `Single` stays `Single`; with a `Double` it
widens, exactly, and the work is in `Double`. The type that is asked for
decides, as for integers: a `Single` variable, parameter or result wants
a `Single`. A `Double` becomes a `Single` only through `Single(x)`,
rounded to the nearest (a tie to even); `s := d` does not compile. A
constant rounds once, from its digits, and one out of `Single`'s range
is a compile error. `Abs`, `Sqr`, `Sqrt`, `Min` and `Max` of `Single`s
are `Single`s; the rest of the calculation set works in `Double`.

`examples/single.paslang`:

```pascal
{ Single is IEEE binary32: worked out in 32 bits, widened exactly with a
  Double, and made from a Double only through Single(x). }
program single;

var
  s, t: Single;
  d: Double;

begin
  s := 0.1;                         { the nearest binary32 to 0.1 }
  d := 0.1;                         { the nearest binary64 }
  WriteLn(s:0:10, ' ', d:0:10);
  t := s * 3;                       { Single work, rounded to 32 bits }
  WriteLn(t:0:10);
  d := s;                           { widening is exact }
  WriteLn(d:0:12);
  s := Single(1 / 3);               { a Double becomes a Single only when written }
  WriteLn(s:0:10, ' ', SizeOf(s), ' ', SizeOf(d));
  WriteLn(Sqrt(s):0:8, ' ', Abs(-s):0:8);
end.
```

prints

```
0.1000000015 0.1000000000
0.3000000119
0.100000001490
0.3333333433 4 8
0.57735026 0.33333334
```

`Quad` is IEEE binary128: 16 bytes, a 113-bit significand (about 34
decimal digits) and an exponent from about 6.5e-4966 to 1.19e4932. No
machine paslang runs on has it in hardware, so it is worked out in
software, with integer instructions only: a `Quad` gives the same bits
on amd64 and arm64, and costs a call for each operation. A `Quad` meets
any number: an `Integer`, a `Double` and a `Single` widen to it exactly,
and the work is in `Quad`; a context that wants a `Quad` works its
expression out in `Quad` (`q := d * d` multiplies the two doubles as
Quads). A literal is read from its digits, rounded once, and `Pi` gives
all 113 bits. A `Quad` becomes a `Double` or a `Single` only through
`Double(q)` or `Single(q)`, rounded once, and an `Integer` only through
`Trunc`, `Round`, `Floor` or `Ceil`, which stop the program on a value no
`Integer` holds. `+`, `-`, `*`, `/`, the comparisons (a NaN is ordered
with nothing), `Abs`, `Sqr`, `Sqrt` (below 0 it stops), `Int`, `Frac`,
`Min`, `Max`, `Inc` and `Dec` take a `Quad`; the rest of the calculation
set does not, and says so: write `Double(q)` for it. `WriteLn`
prints a `Quad` exactly, with `q:w:d` for more decimals than six. A
named constant is worked out in `Quad` too, so `const Third = 1 / 3`
has all 113 bits when a `Quad` takes it, in its unit or in another; a
typed constant and a default value can be `Quad`; a `Quad` field lies on
16 bytes, as C's `_Float128` does, and gdb shows a `Quad` local by its
value. An operation is a call into `pasquad`: about 70 cycles for a
sum, 60 for a product, 200 for a quotient and 1,300 for a square root on
the machine they were measured on (1.0.122), where a `Double` takes a
few (docs/QUAD.md).

`examples/quad.paslang`:

```pascal
{ Quad is IEEE binary128: 113 bits of significand, about 34 digits, the
  same bits on every machine. A literal is read from its digits, a
  Double or an integer widens exactly, and a Quad becomes a Double only
  through Double(x). }
program quad;

var
  q, third: Quad;
  d: Double;

begin
  q := 0.1;                          { the nearest binary128 to 0.1 }
  d := 0.1;                          { the nearest binary64 }
  WriteLn(q:0:40);
  WriteLn(d:0:40);
  third := Quad(1) / 3;
  WriteLn(third:0:36);
  WriteLn(Sqrt(Quad(2)):0:34);
  WriteLn(Quad(Pi):0:34);            { Pi to all 113 bits }
  q := 9223372036854775807;
  WriteLn(q + 1:0:0);                { past Integer, still exact }
  d := Double(third);                { rounded once, to 53 bits }
  WriteLn(d:0:20);
  WriteLn(Trunc(third * 100), ' ', Round(Quad(2.5)), ' ', third < 0.34);
  WriteLn(SizeOf(Quad));
end.
```

prints

```
0.1000000000000000000000000000000000048148
0.1000000000000000055511151231257827021182
0.333333333333333333333333333333333317
1.4142135623730950488016887242096980
3.1415926535897932384626433832795028
9223372036854775808
0.33333333333333331483
33 2 1
16
```

## 15. The core library and pasnet

Eight units, the core, are compiled into `build/` (and `build/a64/`
for arm64) by `make`, for the base processor (`-cpu base`, so the
installed toolchain runs on any machine), and installed beside the
compiler by `make install`. Every program links them without `uses`:

- `pasobject` declares `TObject`, the root of every class, and the
  routines the class words call: the name, the parent and the size a
  class's method table carries (§7); `PasUncaught` writes the line of
  an exception object nobody handled (§9).
- `pasroutines` implements `mutex`, `rwmutex`, `waitgroup`, `cond` and
  `once`, the `lock` and `once` statements, `Goid`, `NumGoroutine`,
  `Yield` and `ReadLn`. It is Pascal over the park and wake words of the
  scheduler (§17).
- `pasfmt` writes and reads reals for `Write`, `WriteLn` and `x:w:d`
  (1.0.79): a real printed exactly, a literal read as the nearest double.
- `pasmap` implements `map[K] of V`: a Swiss table in Pascal, a
  directory of tables of at most 1024 slots that split (§11).
- `pashash` is the hash words (§13): every algorithm in Pascal with its
  rounds written out and, for SHA-1, SHA-256, SHA-512 and the CRCs, a
  second body on the processor's instructions; `Hex`; the Merkle words.
- `pastree` implements `tree[K] of V`, `tree of K`, `heap of T` and
  the `store` (§11); it names `pashash` for the log's CRC.
- `pasheap` is the heap's slow paths and the collector (§17).
- `pasquad` is the arithmetic of `Quad`, in software (§14).

The names of `pasobject`, `pasroutines`, `pasfmt`, `pashash` and
`pastree` are every program's, as those of a unit in `uses` are; `pasmap`, `pasheap` and
`pasquad` are only linked (`uses pasquad` brings its names in). Their
routines are there for the compiler, and a program may call them too:

| Unit | Routine | What it does |
|---|---|---|
| `pasroutines` | `PasMutexLock(m)`, `PasMutexUnlock(m)`, `PasMutexTryLock(m): Boolean` | `m.Lock`, `m.Unlock`, `m.TryLock` of a `mutex`, whose record is `TPasMutex` |
| `pasroutines` | `PasRWLock(r)`, `PasRWUnlock(r)`, `PasRWBeginRead(r)`, `PasRWEndRead(r)` | the methods of an `rwmutex` (`TPasRWMutex`) |
| `pasroutines` | `PasWaitGroupAdd(w, n)`, `PasWaitGroupDone(w)`, `PasWaitGroupWait(w)` | those of a `waitgroup` (`TPasWaitGroup`) |
| `pasroutines` | `PasCondWait(c, m)`, `PasCondSignal(c)`, `PasCondBroadcast(c)` | those of a `cond` (`TPasCond`) |
| `pasroutines` | `PasOnceBegin(o): Boolean`, `PasOnceEnd(o)`, `PasOnceDone(o): Boolean` | `once o do stmt` is `if PasOnceBegin(o) then` the statement, then `PasOnceEnd(o)`; `PasOnceDone` is `o.Done` (`TPasOnce`) |
| `pasroutines` | `PasReadLn(Dest: Pointer)` | `ReadLn(s)`: one line of standard input into the string at `Dest` |
| `pasfmt` | `PasFmtReal(x, w, d): string` | `x:w:d` as text, `d` decimals padded to `w` columns; a `d` below 0 is `WriteLn`'s own form, up to six decimals |
| `pasfmt` | `PasFmtInt(v, w): string`, `PasFmtStr(s, w): string` | an integer, a string, padded to `w` columns |
| `pasfmt` | `PasParseReal(s, out bits): Boolean` | the double nearest the text `s`, its 64 bits into the `Int64` `bits`; `False` when `s` is not a number |
| `pasfmt` | `PasParseSingle(s, out bits): Boolean` | the single nearest the text, its bits in the low 32 |
| `pasfmt` | `PasF64ToF32(b)`, `PasF32ToF64(b)` | the bits of a double rounded to the nearest single, of a single widened to a double |
| `pasfmt` | `PasParseQuad(s, out lo, hi): Boolean`, `PasFmtQuad(lo, hi, w, d): string` | a `Quad`'s two words from text, and to text as `PasFmtReal` |
| `pashash` | `PasHex(s)`, `PasMd5(s)`, `PasSha3(s, bits)`, `PasAdler32(s, adler)`, `PasFnv1a32(s)`, `PasFnv1a64(s)`, `PasMurmur3(s, seed)`, `PasSipHash(s, k0, k1)` | the bodies of `Hex`, `Md5`, `Sha3_*`, `Adler32`, `Fnv1a32`, `Fnv1a64`, `Murmur3` and `SipHash`, one each |
| `pashash` | `PasSha1Cpu(s)`, `PasSha1Base(s)`, and the same pairs for `Sha224`, `Sha256`, `Sha384`, `Sha512`; `PasHmacCpu(alg, key, msg)`, `PasHmacBase` (alg 0 MD5, 1 SHA-1, 2 SHA-224, 3 SHA-256, 4 SHA-384, 5 SHA-512); `PasCrc32Cpu(s, crc)`, `PasCrc32Base`, `PasCrc32cCpu`, `PasCrc32cBase`; `PasMerkleRootCpu(leaves)`, `PasMerkleRootBase`, `PasMerkleProofCpu(leaves, i)`, `PasMerkleProofBase`, `PasMerkleCheckCpu(leaf, i, n, proof, root)`, `PasMerkleCheckBase` | the two bodies of each word, the `Cpu` one on the processor's instructions and the `Base` one in Pascal; the compiler calls one by `-cpu` (§20), a program that calls `Cpu` itself answers for the processor it runs on |
| `pastree` | `PasTreeNew`, `PasTreeGet`, `PasTreePut`, `PasTreeDelete`, `PasTreeClear`, `PasTreeStep`, `PasTreeBound`, `PasTreeRank`, `PasTreeKeyAt`, `PasTreePop`, `PasTreeSplit`, `PasTreeJoin`, `PasHeapNew`, `PasHeapPush`, `PasHeapPop`, `PasHeapLow`, `PasHeapEmpty` | the tree and heap words, taking the compiler's descriptor of the type (key kind and sizes) and keys by address: written for the compiler, not for a program, which has `t[k]`, `Push` and the rest |
| `pastree` | `PasStoreOpen(path): Pointer`, `PasStorePut(db, k, v)`, `PasStoreGet(db, k): string`, `PasStoreHas(db, k): Boolean`, `PasStoreDelete(db, k)`, `PasStoreSync(db)`, `PasStoreClose(db)`, `PasStoreAbandon(db)` | the store words; `k in db` is `PasStoreHas` |

```
ok := PasParseReal('0.5', bits);       { True; bits = $3FE0000000000000 }
s := PasFmtReal(3.14159, 8, 2);        { '    3.14' }
```

A missing core unit stops the compile with a message that names it:
`the core unit pasheap is missing (build/pasheap.pi)` for every program,
`map needs the core unit pasmap (build/pasmap.pi)`, `sync types need the
core unit pasroutines (build/pasroutines.pi)` and `Write of a real or a
width needs the core unit pasfmt`.

`uses pasnet` gives sockets, in Pascal over `Syscall` and the epoll
parking of the runtime:

```
TcpListen(port)  TcpPort(fd)  TcpAccept(fd)  TcpConnect(host, port)
TcpRead(fd, max)  TcpWrite(fd, data)  TcpClose(fd)
TcpListen6  TcpConnect6  TcpAccept6  TcpReadDeadline(fd, max, ms)
UdpBind  UdpPort  UdpSend  UdpRecv  UdpClose
```

Port 0 asks the kernel for a free port and `TcpPort` tells which one.
`TcpReadDeadline` returns an empty string when the timer fires first,
and reads at most 512 bytes a call. A
routine that waits on a socket parks; the thread serves other routines.
The bytes `TcpRead` gives are an ordinary string, which the collector
gives back when nothing holds it.

**Servers (1.1.1).** A host is a dotted quad, an IPv6 literal (`::1`,
`fe80::1`, `::ffff:1.2.3.4`, with or without brackets) or a name,
which `Resolve(name)` turns into a dotted quad by /etc/hosts and then
the first nameserver of /etc/resolv.conf over UDP (`localhost` is
`127.0.0.1`; `''` when nothing knows it). `HostToV4(s, ip)`,
`HostToV6(s, a)` (16 bytes), `V4ToStr`, `V6ToStr` (the longest run of
zeros as `::`, a mapped address as `::ffff:a.b.c.d`) and `IsV6Text`
read and write them.

| Word | What it does |
|---|---|
| `TcpListenAt(host, port, backlog)` | a listener at `host` of either family (`''`, `0.0.0.0` or `::` for every address; on `::` IPv4 connections come too), `SO_REUSEADDR` and `TCP_NODELAY` set, the backlog 4096 when 0 or less; `NetAccept` and `TcpAccept` park on it |
| `TcpConnectTo(host, port)` | a connection to a literal of either family or a name, parking while it is made; -1 when it fails |
| `TcpPeer(fd)`, `TcpLocal(fd)` | the two ends as `host:port`, `[host]:port` for IPv6; `''` on an error |
| `TcpShutdown(fd, how)` | no more reading (0), no more writing (1: the peer reads the end of the stream), both (2) |
| `TcpKeepAlive(fd, on)` | the kernel's keep-alive probes |
| `SockBuffers(fd, recv, send)` | the kernel's buffers of a socket, TCP or UDP, 0 leaves one alone; a datagram server under load wants megabytes |
| `TcpReadLine(fd, buf, line)` | a line without its LF and a CR before it, from the string `buf` the caller keeps for the connection, reading more into it as needed; False at the end of the stream with what was left in `line` |
| `TcpReadN(fd, n, buf, data)` | exactly `n` bytes, from `buf` first; False at the end of the stream |
| `UdpBindAt(host, port)` | a datagram socket at `host` of either family |
| `UdpSendTo(fd, host, port, data)` | a datagram of up to 65507 bytes to a literal or a name |
| `UdpRecvFrom(fd, max, host, port)` | a datagram and its sender, parking until one comes; `UdpSend` and `UdpRecv` take datagrams of up to 65536 bytes too |
| `UdpRecvFromMs(fd, max, ms, host, port)` | the same within `ms` milliseconds, else `''` with `host` `''`: a client of a lossy protocol asks again |
| `RaiseFdLimit` | the descriptor limit raised to what the system allows (the hard limit): the new soft limit. A server of tens of thousands of connections calls it first |
| `DnsQueryA(name, id)`, `DnsAnswerA(msg, id)` | a question for an A record and the first A of its answer as a dotted quad (`''` when none or the id differs) |
| `DnsQuestionName(msg)`, `DnsReplyA(query, ip4, ttl)`, `DnsReplyNx(query)` | what a server needs: the name asked, an answer with one A record, no such name |

**Unix-domain sockets (1.1.1).** A path, or an abstract name when it
starts with `@` (no file is made). The runtime's words serve a Unix
stream socket as they serve TCP: `NetAccept`, `NetRead`, `NetWrite`,
`TcpRead`, `TcpWrite`, `TcpReadLine`, `TcpReadN`, `TcpShutdown` and
`TcpClose` take its descriptor.

| Word | What it does |
|---|---|
| `UnixListen(path)` | a listening stream socket at `path`, the file there removed first; `UnixAccept(fd)` (or `TcpAccept`) parks for a connection |
| `UnixConnect(path)` | a connection to the socket at `path`; while the listener's backlog is full the routine parks a moment and tries again |
| `UnixBind(path)`, `UnixSendTo(fd, path, data)`, `UnixRecvFrom(fd, max, from)` | datagrams: a socket at `path` (`''` for one without a name), a datagram to a path, a datagram with its sender's name |
| `UnixPair(a, b)` | two stream sockets joined to each other in this process, a routine at each end |
| `UnixPeer(fd, pid, uid, group)` | the process, user and group at the other end of a stream socket (`SO_PEERCRED`) |
| `UnixSendFd(fd, passed, data)`, `UnixRecvFd(fd, max, passed)` | a descriptor along with a message (`SCM_RIGHTS`): the receiver gets its own descriptor for the same open file |
| `UnixClose(fd)`, `UnixUnlink(path)` | the descriptor off the poller and closed; the socket file removed |
| `WaitAny(fds, ev, ms)` | the first of the slice `fds` ready for `ev` (1 to read, 4 to write) within `ms` milliseconds, as an index, or -1; the routine parks |

`testdata/unixsock` runs every one of them on both machines, and
`termd -unix path` serves the terminal on a Unix socket, its client
connecting with `termd -connect path`.

Eight servers show them, each with a `-selftest n` that runs `n`
client routines in the same process and checks every answer (`make
check` runs them with 2000 on amd64 and 300 under qemu): `examples/httpd`
(HTTP/1.1 with keep-alive, a routine per connection), `examples/dnsd`
(A records from a table over UDP), `examples/termd` (a line
protocol with sessions that talk to each other, and its client), and
after them `examples/ftpd`, `examples/ntpd`, `examples/wsd`,
`examples/chat` and `examples/proxy`. A
routine per connection costs a few kilobytes of stack and nothing
else: ten thousand clients make thirty thousand requests of `httpd`
in about a second, in one process with the clients.

A burst of connections larger than the kernel's SYN backlog
(`net.ipv4.tcp_max_syn_backlog`, 2048 by default) is answered with SYN
cookies, and a connection whose last ACK meets a full accept queue is
dropped with nothing kept to retry it: the client believes it is
connected and the server never heard of it. Where the client speaks
first, as in HTTP, its first bytes bring the connection back. Where the
server speaks first, with a greeting, as `termd`, `ftpd` and `chat` do,
a client reads the greeting with a deadline (`TcpReadDeadline`) and
connects again when it does not come, as their self-tests do; a server
that expects such bursts can also raise the backlog. A write to a peer
that has gone away fails (`TcpWrite` below 0) and the program goes on:
socket writes never raise `SIGPIPE`.

`examples/httpd.paslang`:

```pascal
{ An HTTP/1.1 server on routines (P114): one routine per connection,
  parked on the runtime's poller while it waits, so ten thousand open
  connections are ten thousand small stacks and no threads. Keep-alive
  by default, as the protocol says; GET / is a page, GET /hello a
  greeting, GET /stats the counters, anything else 404.

    httpd [port]            serve (8080 by default) until killed
    httpd -selftest [n]     n client routines (2000 by default), three
                            requests each on one kept-alive connection,
                            in this same process; prints the totals

  make check runs the self-test on both machines. }
program httpd;

uses pasnet, paslib;

const
  Requests = 3;

var
  served, opened, bad: Integer;   { the counters, AtomicAdd from every routine }
  done: WaitGroup;

function Header(Code: Integer; const Text: string; const Body: string; KeepAlive: Boolean): string;
var
  h: string;
begin
  h := 'HTTP/1.1 ' + IntToStr(Code) + ' ' + Text + #13#10 +
    'Content-Type: text/plain; charset=utf-8' + #13#10 +
    'Content-Length: ' + IntToStr(Length(Body)) + #13#10;
  if KeepAlive then
    h := h + 'Connection: keep-alive' + #13#10
  else
    h := h + 'Connection: close' + #13#10;
  Result := h + #13#10 + Body;
end;

{ The word from position I of S up to the next space, I moved past it. }
function Token(const S: string; var I: Integer): string;
var
  j: Integer;
begin
  j := I;
  while (j <= Length(S)) and (S[j] <> ' ') do
    j := j + 1;
  Result := Copy(S, I, j - I);
  I := j;
  while (I <= Length(S)) and (S[I] = ' ') do
    I := I + 1;
end;

function Answer(const Method, Path: string; KeepAlive: Boolean): string;
var
  body: string;
begin
  if Method <> 'GET' then
  begin
    Result := Header(405, 'Method Not Allowed', 'only GET' + #10, KeepAlive);
    Exit;
  end;
  if Path = '/' then
    body := 'paslang httpd: a routine per connection, parked between requests.' + #10 +
      'Try /hello and /stats.' + #10
  else if Path = '/hello' then
    body := 'hello' + #10
  else if Path = '/stats' then
    body := 'connections ' + IntToStr(opened) + #10 + 'requests ' + IntToStr(served) + #10 +
      'bad ' + IntToStr(bad) + #10
  else
  begin
    Result := Header(404, 'Not Found', 'no ' + Path + #10, KeepAlive);
    Exit;
  end;
  Result := Header(200, 'OK', body, KeepAlive);
end;

{ One connection: requests until the peer closes or asks to. }
procedure Serve(C: Integer);
var
  buf, line, method, path, version, key: string;
  i: Integer;
  keep, more: Boolean;
begin
  AtomicAdd(@opened, 1);
  buf := '';
  more := True;
  while more do
  begin
    if not TcpReadLine(C, buf, line) then
      Break;
    if line = '' then
      Continue;                       { a stray empty line between requests }
    i := 1;
    method := Token(line, i);
    path := Token(line, i);
    version := Token(line, i);
    keep := version <> 'HTTP/1.0';
    { the headers up to the empty line; Connection may change keep }
    while TcpReadLine(C, buf, line) and (line <> '') do
    begin
      i := 1;
      key := Token(line, i);
      if (key = 'Connection:') or (key = 'connection:') then
        keep := Token(line, i) <> 'close';
    end;
    if (method = '') or (path = '') then
    begin
      AtomicAdd(@bad, 1);
      Break;
    end;
    AtomicAdd(@served, 1);            { counted before the answer leaves: its client can end, and
                                        the self-test read the count, before this routine runs again }
    if TcpWrite(C, Answer(method, path, keep)) < 0 then
    begin
      AtomicAdd(@served, -1);
      Break;
    end;
    more := keep;
  end;
  TcpClose(C);
end;

procedure Listen(L: Integer);
var
  c: Integer;
begin
  while True do
  begin
    c := TcpAccept(L);
    if c < 0 then
      Break;
    pas Serve(c);
  end;
end;

function StrToIntDef(const S: string; Def: Integer): Integer;
var
  v, i: Integer;
begin
  v := 0;
  if S = '' then
  begin
    Result := Def;
    Exit;
  end;
  for i := 1 to Length(S) do
  begin
    if (S[i] < '0') or (S[i] > '9') then
    begin
      Result := Def;
      Exit;
    end;
    v := v * 10 + Ord(S[i]) - 48;
  end;
  Result := v;
end;

{ A client of the self-test: one connection, Requests requests, each
  answer checked. }
procedure Client(Port, Id: Integer);
var
  c, k, i, n: Integer;
  buf, line, body: string;
  ok: Boolean;
begin
  c := TcpConnectTo('127.0.0.1', Port);
  if c < 0 then
  begin
    AtomicAdd(@bad, 1);
    done.Done;
    Exit;
  end;
  buf := '';
  for k := 1 to Requests do
  begin
    if TcpWrite(c, 'GET /hello HTTP/1.1' + #13#10 + 'Host: self' + #13#10 + #13#10) < 0 then
    begin
      AtomicAdd(@bad, 1);
      Break;
    end;
    ok := TcpReadLine(c, buf, line) and (line = 'HTTP/1.1 200 OK');
    n := -1;
    while ok and TcpReadLine(c, buf, line) and (line <> '') do
    begin
      i := 1;
      if Token(line, i) = 'Content-Length:' then
        n := StrToIntDef(Token(line, i), -1);
    end;
    if ok and (n >= 0) then
      ok := TcpReadN(c, n, buf, body) and (body = 'hello' + #10)
    else
      ok := False;
    if not ok then
    begin
      AtomicAdd(@bad, 1);
      Break;
    end;
  end;
  TcpClose(c);
  done.Done;
end;

procedure SelfTest(N: Integer);
var
  l, i, lim: Integer;
begin
  lim := RaiseFdLimit;
  if lim < 2 * N + 64 then
    N := (lim - 64) div 2;
  l := TcpListen(0);
  if l < 0 then
  begin
    WriteLn('httpd: cannot listen');
    Halt(1);
  end;
  pas Listen(l);
  done.Add(N);
  for i := 1 to N do
    pas Client(TcpPort(l), i);
  done.Wait;
  WriteLn(N, ' clients, ', N * Requests, ' requests, ', served, ' served, ', bad, ' bad');
  if (served <> N * Requests) or (bad <> 0) then
    Halt(1);
  Halt(0);                { the server routine parks for ever: end without waiting for it }
end;

var
  port, l: Integer;
begin
  if (ParamCount >= 1) and (ParamStr(1) = '-selftest') then
  begin
    if ParamCount >= 2 then
      SelfTest(StrToIntDef(ParamStr(2), 2000))
    else
      SelfTest(2000);
    Exit;
  end;
  port := 8080;
  if ParamCount >= 1 then
    port := StrToIntDef(ParamStr(1), 8080);
  RaiseFdLimit;
  l := TcpListenAt('', port, 1024);
  if l < 0 then
  begin
    WriteLn('httpd: cannot listen on port ', port);
    Halt(1);
  end;
  WriteLn('httpd: listening on port ', TcpPort(l), ' (GET /, /hello, /stats)');
  Listen(l);
end.
```

`examples/dnsd.paslang`:

```pascal
{ A DNS server over UDP on routines (P114): a table of names and IPv4
  addresses, an A answer for each, NXDOMAIN for the rest, the question
  echoed as the protocol asks (RFC 1035). One routine reads datagrams
  and answers; the peer's address comes with each datagram.

    dnsd [port]             serve (5353 by default) until killed; try
                            dig @127.0.0.1 -p 5353 one.example
    dnsd -selftest [n]      n client routines (2000 by default) ask a
                            name each and check the answer

  The names served: one.example 10.0.0.1, two.example 10.0.0.2, and
  n.example for any number n up to 65535 as 10.(n div 256).(n mod 256)
  with a leading 10.0. }
program dnsd;

uses pasnet, paslib;

var
  answered, missed, bad: Integer;
  done: WaitGroup;

{ The address of a name, 0 when the table has none. }
function Lookup(const Name: string): Integer;
var
  n: string;
  v, i: Integer;
begin
  Result := 0;
  n := Name;
  if (Length(n) > 0) and (n[Length(n)] = '.') then
    n := Copy(n, 1, Length(n) - 1);
  if n = 'one.example' then
    Result := $0A000001
  else if n = 'two.example' then
    Result := $0A000002
  else if (Length(n) > 8) and (Copy(n, Length(n) - 7, 8) = '.example') then
  begin
    v := 0;
    for i := 1 to Length(n) - 8 do
    begin
      if (n[i] < '0') or (n[i] > '9') then
        Exit;
      v := v * 10 + Ord(n[i]) - 48;
      if v > 65535 then
        Exit;
    end;
    Result := $0A000000 + v;
  end;
end;

procedure Serve(Fd: Integer);
var
  q, host, name, reply: string;
  port, ip: Integer;
begin
  while True do
  begin
    q := UdpRecvFrom(Fd, 512, host, port);
    if q = '' then
      Break;
    name := DnsQuestionName(q);
    if name = '' then
    begin
      AtomicAdd(@bad, 1);
      Continue;
    end;
    ip := Lookup(name);
    if ip = 0 then
    begin
      reply := DnsReplyNx(q);
      AtomicAdd(@missed, 1);
    end
    else
    begin
      reply := DnsReplyA(q, ip, 60);
      AtomicAdd(@answered, 1);
    end;
    UdpSendTo(Fd, host, port, reply);
  end;
end;

{ A client of the self-test: asks for Id.example, expects 10.x.y. }
procedure Client(Port, Id: Integer);
var
  fd, n, p, ip: Integer;
  q, m, host, got, want: string;
begin
  fd := UdpBindAt('', 0);
  if fd < 0 then
  begin
    AtomicAdd(@bad, 1);
    done.Done;
    Exit;
  end;
  q := DnsQueryA(IntToStr(Id) + '.example', Id and 65535);
  got := '';
  { a datagram may be lost: three tries, two seconds each, as a
    resolver does }
  for n := 1 to 3 do
  begin
    if UdpSendTo(fd, '127.0.0.1', Port, q) < 0 then
      Break;
    m := UdpRecvFromMs(fd, 512, 2000, host, p);
    got := DnsAnswerA(m, Id and 65535);
    if got <> '' then
      Break;
  end;
  want := '10.0.' + IntToStr(Id shr 8) + '.' + IntToStr(Id and 255);
  if got <> want then
    AtomicAdd(@bad, 1);
  UdpClose(fd);
  done.Done;
end;

procedure SelfTest(N: Integer);
var
  s, i, port: Integer;
begin
  RaiseFdLimit;
  s := UdpBindAt('', 0);
  if s < 0 then
  begin
    WriteLn('dnsd: cannot bind');
    Halt(1);
  end;
  SockBuffers(s, 8388608, 0);   { the queries of thousands of clients at once }
  port := UdpPort(s);
  pas Serve(s);
  done.Add(N);
  for i := 1 to N do
    pas Client(port, i);
  done.Wait;
  WriteLn(N, ' clients, ', answered, ' answered, ', missed, ' missed, ', bad, ' bad');
  if (answered <> N) or (bad <> 0) then
    Halt(1);
  Halt(0);                { the server routine parks for ever: end without waiting for it }
end;

function StrToIntDef(const S: string; Def: Integer): Integer;
var
  v, i: Integer;
begin
  v := 0;
  if S = '' then
  begin
    Result := Def;
    Exit;
  end;
  for i := 1 to Length(S) do
  begin
    if (S[i] < '0') or (S[i] > '9') then
    begin
      Result := Def;
      Exit;
    end;
    v := v * 10 + Ord(S[i]) - 48;
  end;
  Result := v;
end;

var
  port, s: Integer;
begin
  if (ParamCount >= 1) and (ParamStr(1) = '-selftest') then
  begin
    if ParamCount >= 2 then
      SelfTest(StrToIntDef(ParamStr(2), 2000))
    else
      SelfTest(2000);
    Exit;
  end;
  port := 5353;
  if ParamCount >= 1 then
    port := StrToIntDef(ParamStr(1), 5353);
  s := UdpBindAt('', port);
  if s < 0 then
  begin
    WriteLn('dnsd: cannot bind port ', port);
    Halt(1);
  end;
  SockBuffers(s, 8388608, 0);
  WriteLn('dnsd: serving one.example, two.example and <n>.example on UDP port ', UdpPort(s));
  Serve(s);
end.
```

`examples/termd.paslang`:

```pascal
{ A terminal server and its client (P114): a line protocol over TCP,
  one routine per session, the sessions in a map guarded by a mutex,
  and say broadcasts to every other session through its channel, so a
  session's writer is one routine and no two write at once.

    termd [port]            serve (2323 by default) until killed
    termd -unix path        serve on a Unix-domain socket at path
                            (@name for an abstract one) and the client
                            connects with -connect path
    termd -connect host port   a client: your lines go up, its answers
                            come down, until quit, an empty line or
                            the end of the input
    termd -selftest [n]     n sessions (2000 by default) run the
                            commands and check every answer

  The commands: help, name <yours>, who, echo <text>, say <text>,
  count, quit. }
program termd;

uses pasnet, paslib;

type
  PSession = ^TSession;
  TSession = record
    Fd: Integer;
    Name: string;
    Out: chan of string;      { lines to write, one writer routine; a
                                line of one LF alone tells it to close }
  end;

var
  sessions: map[Integer] of PSession;
  guard: Mutex;
  nextId, quitCount, bad: Integer;
  done: WaitGroup;

{ The writer of a session: what the channel brings goes to the socket. }
procedure Writer(S: PSession);
var
  line: string;
begin
  while True do
  begin
    line := Recv(S^.Out);
    if line = #10 then          { no line holds an LF: the end }
      Break;
    TcpWrite(S^.Fd, line + #10);
  end;
  TcpClose(S^.Fd);
end;

procedure Broadcast(From: PSession; const Text: string);
var
  id: Integer;
  s: PSession;
begin
  guard.Lock;
  for id, s in sessions do
    if s <> From then
      Send(s^.Out, '[' + From^.Name + '] ' + Text);
  guard.Unlock;
end;

function Who: string;
var
  id: Integer;
  s: PSession;
begin
  Result := '';
  guard.Lock;
  for id, s in sessions do
    Result := Result + s^.Name + ' ';
  guard.Unlock;
end;

procedure Session(Fd: Integer);
var
  s: PSession;
  buf, line, cmd, arg: string;
  i, id: Integer;
begin
  New(s);
  s^.Fd := Fd;
  s^.Out := MakeChan(64);
  guard.Lock;
  nextId := nextId + 1;
  id := nextId;
  s^.Name := 'guest' + IntToStr(id);
  sessions[id] := s;
  guard.Unlock;
  pas Writer(s);
  Send(s^.Out, 'welcome ' + s^.Name + ', type help');
  buf := '';
  while TcpReadLine(Fd, buf, line) do
  begin
    i := 1;
    while (i <= Length(line)) and (line[i] <> ' ') do
      i := i + 1;
    cmd := Copy(line, 1, i - 1);
    arg := Copy(line, i + 1, Length(line) - i);
    if cmd = 'help' then
      Send(s^.Out, 'help name who echo say count quit')
    else if cmd = 'name' then
    begin
      if arg <> '' then
      begin
        guard.Lock;
        s^.Name := arg;
        guard.Unlock;
      end;
      Send(s^.Out, 'you are ' + s^.Name);
    end
    else if cmd = 'who' then
      Send(s^.Out, Who)
    else if cmd = 'echo' then
      Send(s^.Out, arg)
    else if cmd = 'say' then
    begin
      Broadcast(s, arg);
      Send(s^.Out, 'said');
    end
    else if cmd = 'count' then
    begin
      guard.Lock;
      Send(s^.Out, IntToStr(Length(sessions)));
      guard.Unlock;
    end
    else if cmd = 'quit' then
    begin
      { the session is over before bye goes out, so a client that has
        read bye finds the count updated }
      guard.Lock;
      Delete(sessions, id);
      quitCount := quitCount + 1;
      guard.Unlock;
      Send(s^.Out, 'bye');
      Send(s^.Out, #10);
      Exit;
    end
    else
      Send(s^.Out, 'what? ' + cmd);
  end;
  { the peer went without quit: not counted as one }
  guard.Lock;
  Delete(sessions, id);
  guard.Unlock;
  Send(s^.Out, #10);        { the writer closes the socket }
end;

procedure Listen(L: Integer);
var
  c: Integer;
begin
  while True do
  begin
    c := TcpAccept(L);
    if c < 0 then
      Break;
    pas Session(c);
  end;
end;

function Expect(C: Integer; var Buf: string; const Cmd, Want: string): Boolean;
var
  line: string;
begin
  Result := False;
  if TcpWrite(C, Cmd + #10) < 0 then
    Exit;
  if not TcpReadLine(C, Buf, line) then
    Exit;
  Result := line = Want;
end;

{ A connection that has said welcome, or -1: the greeting is read with
  a deadline and a new connection tried when it does not come. A burst
  of connections past the kernel's SYN backlog is answered with SYN
  cookies, and one whose last ACK meets a full accept queue is dropped
  with nothing kept to retry it: the client holds a connection the
  server never had, and where the server speaks first both would wait
  for ever. }
function Greeted(Port: Integer; var Buf: string): Integer;
var
  k, c: Integer;
  line: string;
begin
  Result := -1;
  for k := 1 to 5 do
  begin
    c := TcpConnectTo('127.0.0.1', Port);
    if c >= 0 then
    begin
      Buf := TcpReadDeadline(c, 512, 3000);
      if (Buf <> '') and TcpReadLine(c, Buf, line) and (Copy(line, 1, 8) = 'welcome ') then
      begin
        Result := c;
        Exit;
      end;
      TcpClose(c);
    end;
  end;
end;

{ A client of the self-test: the commands, every answer checked. }
procedure Client(Port, Id: Integer);
var
  c: Integer;
  buf: string;
  ok: Boolean;
begin
  buf := '';
  c := Greeted(Port, buf);
  if c < 0 then
  begin
    AtomicAdd(@bad, 1);
    done.Done;
    Exit;
  end;
  ok := Expect(c, buf, 'name user' + IntToStr(Id), 'you are user' + IntToStr(Id));
  ok := ok and Expect(c, buf, 'echo hello ' + IntToStr(Id), 'hello ' + IntToStr(Id));
  ok := ok and Expect(c, buf, 'nothing', 'what? nothing');
  ok := ok and Expect(c, buf, 'quit', 'bye');
  if not ok then
    AtomicAdd(@bad, 1);
  TcpClose(c);
  done.Done;
end;

procedure SelfTest(N: Integer);
var
  l, i: Integer;
begin
  RaiseFdLimit;
  New(sessions);
  l := TcpListen(0);
  if l < 0 then
  begin
    WriteLn('termd: cannot listen');
    Halt(1);
  end;
  pas Listen(l);
  done.Add(N);
  for i := 1 to N do
    pas Client(TcpPort(l), i);
  done.Wait;
  WriteLn(N, ' sessions, ', quitCount, ' quit, ', bad, ' bad');
  if (quitCount <> N) or (bad <> 0) then
    Halt(1);
  Halt(0);                { the server routine parks for ever: end without waiting for it }
end;

{ The client: stdin up, the answers down, in two routines. }
procedure Down(C: Integer);
var
  buf, line: string;
begin
  buf := '';
  while TcpReadLine(C, buf, line) do
    WriteLn(line);
  done.Done;
end;

procedure Connect(const Host: string; Port: Integer);
var
  c: Integer;
  line: string;
begin
  if (Host <> '') and ((Host[1] = '/') or (Host[1] = '@')) then
    c := UnixConnect(Host)          { a Unix-domain socket: the path alone }
  else
    c := TcpConnectTo(Host, Port);
  if c < 0 then
  begin
    WriteLn('termd: cannot connect to ', Host, ':', Port);
    Halt(1);
  end;
  done.Add(1);
  pas Down(c);
  while True do
  begin
    ReadLn(line);
    if line = '' then             { an empty line, or the end of the input }
      line := 'quit';
    if TcpWrite(c, line + #10) < 0 then
      Break;
    if line = 'quit' then
      Break;
  end;
  done.Wait;
  TcpClose(c);
end;

function StrToIntDef(const S: string; Def: Integer): Integer;
var
  v, i: Integer;
begin
  v := 0;
  if S = '' then
  begin
    Result := Def;
    Exit;
  end;
  for i := 1 to Length(S) do
  begin
    if (S[i] < '0') or (S[i] > '9') then
    begin
      Result := Def;
      Exit;
    end;
    v := v * 10 + Ord(S[i]) - 48;
  end;
  Result := v;
end;

var
  port, l: Integer;
begin
  if (ParamCount >= 1) and (ParamStr(1) = '-selftest') then
  begin
    if ParamCount >= 2 then
      SelfTest(StrToIntDef(ParamStr(2), 2000))
    else
      SelfTest(2000);
    Exit;
  end;
  if (ParamCount >= 2) and (ParamStr(1) = '-connect') then
  begin
    if ParamCount >= 3 then
      Connect(ParamStr(2), StrToIntDef(ParamStr(3), 2323))
    else
      Connect(ParamStr(2), 2323);
    Exit;
  end;
  if (ParamCount >= 2) and (ParamStr(1) = '-unix') then
  begin
    New(sessions);
    RaiseFdLimit;
    l := UnixListen(ParamStr(2));
    if l < 0 then
    begin
      WriteLn('termd: cannot listen at ', ParamStr(2));
      Halt(1);
    end;
    WriteLn('termd: listening at ', ParamStr(2), '; termd -connect ', ParamStr(2));
    Listen(l);
    Exit;
  end;
  New(sessions);
  port := 2323;
  if ParamCount >= 1 then
    port := StrToIntDef(ParamStr(1), 2323);
  RaiseFdLimit;
  l := TcpListenAt('', port, 1024);
  if l < 0 then
  begin
    WriteLn('termd: cannot listen on port ', port);
    Halt(1);
  end;
  WriteLn('termd: listening on port ', TcpPort(l), '; termd -connect 127.0.0.1 ', TcpPort(l));
  Listen(l);
end.
```

An FTP server, RFC 959, with its client in the same program: the
control connection is a line protocol, and each listing or transfer
opens a passive data connection (`PASV`, or `EPSV` for either family)
from a listener on a port the kernel picks, accepted by the command
that follows. The files are under the directory the server is given
and a path never leaves it. `ftpd -client host port user pass ls`
lists, `cat name` prints a file, `get name` fetches it, `put name`
sends one; a real client (`lftp`, `curl ftp://...`) works the same.
The self-test's sessions each make a directory of their own, store a
file, list it, fetch it back and remove both.

`examples/ftpd.paslang`:

```pascal
{ An FTP server and its client (P119): RFC 959 over TCP, the control
  connection a line protocol and a passive data connection for each
  listing or transfer, a routine per session, the files under the
  directory it is given. Any user name and password are accepted.

    ftpd [port] [dir]        serve (2121, the current directory) until killed
    ftpd -client host port user pass ls | cat name | get name | put name
                             a client: a listing, a file printed, a
                             file fetched into the current directory,
                             a file sent
    ftpd -selftest [n]       n client sessions (2000 by default) in this
                             process over a temporary directory: each
                             logs in, makes a directory of its own,
                             sends a file there, lists it, fetches it
                             back and checks it, removes both, quits

  The commands: USER, PASS, SYST, TYPE, PWD, CWD, CDUP, MKD, RMD, PASV,
  EPSV, LIST, NLST, RETR, STOR, DELE, SIZE, NOOP, QUIT. make check runs
  the self-test on both machines.

  Passive mode opens a listening port and a connection for every
  listing or transfer, and a closed connection keeps its port for a
  minute (TIME_WAIT): on one address the kernel's ephemeral ports
  (32768 to 60999) hold about five thousand sessions at once, not ten;
  a server for more gives each address its own range. }
program ftpd;

uses pasnet, paslib;

type
  PSession = ^TSession;
  TSession = record
    Fd: Integer;
    Root: string;             { the directory served }
    Cwd: string;              { the current directory under it, '' for the root }
    User: string;
    LoggedIn: Boolean;
    DataL: Integer;           { the listener of PASV, 0 for none }
  end;

var
  stored, fetched, bad: Integer;   { the counters of the self-test }
  done: WaitGroup;

{ ---- small words ---- }

function StrToIntDef(const S: string; Def: Integer): Integer;
var
  v, i: Integer;
begin
  v := 0;
  if S = '' then
  begin
    Result := Def;
    Exit;
  end;
  for i := 1 to Length(S) do
  begin
    if (S[i] < '0') or (S[i] > '9') then
    begin
      Result := Def;
      Exit;
    end;
    v := v * 10 + Ord(S[i]) - 48;
  end;
  Result := v;
end;

function UpperOf(const S: string): string;
var
  i: Integer;
begin
  Result := S;
  for i := 1 to Length(Result) do
    if (Result[i] >= 'a') and (Result[i] <= 'z') then
      Result[i] := Chr(Ord(Result[i]) - 32);
end;

{ The line without its CR: the protocol ends lines in CRLF. }
function Trimmed(const S: string): string;
begin
  Result := S;
  while (Result <> '') and ((Result[Length(Result)] = #13) or (Result[Length(Result)] = ' ')) do
    SetLength(Result, Length(Result) - 1);
end;

{ The first word of S and the rest after the space. }
procedure HeadRest(const S: string; out Head, Rest: string);
var
  i: Integer;
begin
  i := 1;
  while (i <= Length(S)) and (S[i] <> ' ') do
    i := i + 1;
  Head := Copy(S, 1, i - 1);
  while (i <= Length(S)) and (S[i] = ' ') do
    i := i + 1;
  Rest := Copy(S, i, Length(S) - i + 1);
end;

{ Whether Sub occurs in S. }
function Has(const S, Sub: string): Boolean;
var
  i, j: Integer;
begin
  Result := False;
  if (Sub = '') or (Length(Sub) > Length(S)) then
    Exit;
  for i := 1 to Length(S) - Length(Sub) + 1 do
  begin
    j := 1;
    while (j <= Length(Sub)) and (S[i + j - 1] = Sub[j]) do
      j := j + 1;
    if j > Length(Sub) then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

function IsDir(const Path: string): Boolean;
begin
  Result := FileExists(Path + '/.');
end;

{ A path under the root from the client's word: absolute from the root
  or relative to the current directory, . and .. resolved, never above
  the root. '' is the root itself. }
function Under(S: PSession; const Arg: string): string;
var
  parts: array of string;
  p, piece: string;
  i, n: Integer;
begin
  if (Arg <> '') and (Arg[1] = '/') then
    p := Arg
  else if S^.Cwd = '' then
    p := Arg
  else
    p := S^.Cwd + '/' + Arg;
  parts := nil;
  piece := '';
  for i := 1 to Length(p) + 1 do
  begin
    if (i > Length(p)) or (p[i] = '/') then
    begin
      if piece = '..' then
      begin
        if Length(parts) > 0 then
          SetLength(parts, Length(parts) - 1);
      end
      else if (piece <> '') and (piece <> '.') then
      begin
        SetLength(parts, Length(parts) + 1);
        parts[High(parts)] := piece;
      end;
      piece := '';
    end
    else
      piece := piece + p[i];
  end;
  Result := '';
  n := Length(parts);
  for i := 0 to n - 1 do
    if i = 0 then
      Result := parts[i]
    else
      Result := Result + '/' + parts[i];
end;

function RealPath(S: PSession; const Rel: string): string;
begin
  if Rel = '' then
    Result := S^.Root
  else
    Result := S^.Root + '/' + Rel;
end;

procedure RemoveFile(const Path: string);
var
  z: string;
begin
  z := Path + #0;
  if Amd64 = 1 then
    Syscall(87, Integer(@z[1]))
  else
    Syscall(35, -100, Integer(@z[1]), 0);
end;

procedure RemoveDir(const Path: string);
var
  z: string;
begin
  z := Path + #0;
  if Amd64 = 1 then
    Syscall(84, Integer(@z[1]))
  else
    Syscall(35, -100, Integer(@z[1]), 512);
end;

{ Everything a data connection brings until its end. }
function ReadAll(D: Integer): string;
var
  piece: string;
begin
  Result := '';
  while True do
  begin
    piece := TcpRead(D, 65536);
    if piece = '' then
      Break;
    Result := Result + piece;
  end;
end;

{ ---- the server ---- }

procedure Reply(S: PSession; const Text: string);
begin
  TcpWrite(S^.Fd, Text + #13#10);
end;

{ A listing in the form clients expect, one file a line. The lines are
  gathered and joined once: a directory of thousands of files listed by
  thousands of sessions must not copy a growing string for each. }
function Listing(S: PSession; const Rel: string; NamesOnly: Boolean): string;
var
  names, name, full, dir: string;
  lines: array of string;
  i, j, n, total: Integer;
begin
  Result := '';
  dir := RealPath(S, Rel);
  names := ListDir(dir);
  lines := nil;
  total := 0;
  i := 1;
  while i <= Length(names) do
  begin
    j := i;
    while (j <= Length(names)) and (names[j] <> #10) do
      j := j + 1;
    name := Copy(names, i, j - i);
    i := j + 1;
    if name = '' then
      Continue;
    if NamesOnly then
      name := name + #13#10
    else
    begin
      full := dir + '/' + name;
      if IsDir(full) then
        name := 'drwxr-xr-x 1 paslang paslang        0 Jan  1 00:00 ' + name + #13#10
      else
        name := '-rw-r--r-- 1 paslang paslang ' + IntToStr(FileSize(full)) +
          ' Jan  1 00:00 ' + name + #13#10;
    end;
    SetLength(lines, Length(lines) + 1);
    lines[High(lines)] := name;
    total := total + Length(name);
  end;
  SetLength(Result, total);
  n := 1;
  for i := 0 to High(lines) do
  begin
    Move(lines[i][1], Result[n], Length(lines[i]));
    n := n + Length(lines[i]);
  end;
end;

{ The passive data connection: a listener on a port the kernel picks,
  told to the client in the form the command asks for; the transfer
  command that follows accepts the one connection. }
procedure Passive(S: PSession; Extended: Boolean);
var
  host, local: string;
  port, i: Integer;
begin
  if S^.DataL > 0 then
    TcpClose(S^.DataL);
  S^.DataL := TcpListenAt('', 0, 1);
  if S^.DataL < 0 then
  begin
    S^.DataL := 0;
    Reply(S, '425 cannot open a data port');
    Exit;
  end;
  port := TcpPort(S^.DataL);
  if Extended then
  begin
    Reply(S, '229 Entering Extended Passive Mode (|||' + IntToStr(port) + '|)');
    Exit;
  end;
  { the address the client reached us at, in the dotted form }
  local := TcpLocal(S^.Fd);
  i := Length(local);
  while (i > 0) and (local[i] <> ':') do
    i := i - 1;
  host := Copy(local, 1, i - 1);
  if (host = '') or (host[1] = '[') then
    host := '127.0.0.1';
  for i := 1 to Length(host) do
    if host[i] = '.' then
      host[i] := ',';
  Reply(S, '227 Entering Passive Mode (' + host + ',' + IntToStr(port div 256) + ',' +
    IntToStr(port mod 256) + ')');
end;

{ The connection of the transfer, or 0 with the refusal sent. }
function DataConn(S: PSession): Integer;
begin
  if S^.DataL = 0 then
  begin
    Reply(S, '425 use PASV first');
    Result := 0;
    Exit;
  end;
  Reply(S, '150 opening the data connection');
  Result := TcpAccept(S^.DataL);
  TcpClose(S^.DataL);
  S^.DataL := 0;
  if Result < 0 then
  begin
    Reply(S, '425 no data connection');
    Result := 0;
  end;
end;

procedure Session(C: Integer; const Root: string);
var
  s: TSession;
  buf, line, cmd, arg, rel, data: string;
  d: Integer;
begin
  s.Fd := C;
  s.Root := Root;
  s.Cwd := '';
  s.User := '';
  s.LoggedIn := False;
  s.DataL := 0;
  buf := '';
  Reply(@s, '220 paslang ftpd ready');
  while TcpReadLine(C, buf, line) do
  begin
    HeadRest(Trimmed(line), cmd, arg);
    cmd := UpperOf(cmd);
    if cmd = 'USER' then
    begin
      s.User := arg;
      Reply(@s, '331 password, please');
    end
    else if cmd = 'PASS' then
    begin
      s.LoggedIn := True;
      Reply(@s, '230 logged in as ' + s.User);
    end
    else if cmd = 'QUIT' then
    begin
      Reply(@s, '221 bye');
      Break;
    end
    else if cmd = 'NOOP' then
      Reply(@s, '200 ok')
    else if cmd = 'SYST' then
      Reply(@s, '215 UNIX Type: L8')
    else if not s.LoggedIn then
      Reply(@s, '530 log in first')
    else if cmd = 'TYPE' then
      Reply(@s, '200 type ' + arg)
    else if cmd = 'PWD' then
      Reply(@s, '257 "/' + s.Cwd + '" is the current directory')
    else if (cmd = 'CWD') or (cmd = 'CDUP') then
    begin
      if cmd = 'CDUP' then
        rel := Under(@s, '..')
      else
        rel := Under(@s, arg);
      if IsDir(RealPath(@s, rel)) then
      begin
        s.Cwd := rel;
        Reply(@s, '250 now in /' + rel);
      end
      else
        Reply(@s, '550 no such directory');
    end
    else if cmd = 'PASV' then
      Passive(@s, False)
    else if cmd = 'EPSV' then
      Passive(@s, True)
    else if (cmd = 'LIST') or (cmd = 'NLST') then
    begin
      rel := Under(@s, arg);
      if not IsDir(RealPath(@s, rel)) then
        Reply(@s, '550 no such directory')
      else
      begin
        d := DataConn(@s);
        if d > 0 then
        begin
          TcpWrite(d, Listing(@s, rel, cmd = 'NLST'));
          TcpClose(d);
          Reply(@s, '226 listing sent');
        end;
      end;
    end
    else if cmd = 'RETR' then
    begin
      rel := Under(@s, arg);
      if (rel = '') or not ReadFile(RealPath(@s, rel), data) then
        Reply(@s, '550 no such file')
      else
      begin
        d := DataConn(@s);
        if d > 0 then
        begin
          TcpWrite(d, data);
          TcpClose(d);
          Reply(@s, '226 file sent');
        end;
      end;
    end
    else if cmd = 'STOR' then
    begin
      rel := Under(@s, arg);
      if rel = '' then
        Reply(@s, '553 a file name, please')
      else
      begin
        d := DataConn(@s);
        if d > 0 then
        begin
          data := ReadAll(d);
          TcpClose(d);
          if WriteFile(RealPath(@s, rel), data) then
            Reply(@s, '226 file stored')
          else
            Reply(@s, '550 cannot write ' + arg);
        end;
      end;
    end
    else if cmd = 'MKD' then
    begin
      rel := Under(@s, arg);
      if (rel = '') or IsDir(RealPath(@s, rel)) then
        Reply(@s, '550 cannot make ' + arg)
      else if EnsureDir(RealPath(@s, rel)) then
        Reply(@s, '257 "/' + rel + '" made')
      else
        Reply(@s, '550 cannot make ' + arg);
    end
    else if cmd = 'RMD' then
    begin
      rel := Under(@s, arg);
      if (rel = '') or not IsDir(RealPath(@s, rel)) then
        Reply(@s, '550 no such directory')
      else
      begin
        RemoveDir(RealPath(@s, rel));
        if IsDir(RealPath(@s, rel)) then
          Reply(@s, '550 not empty')
        else
          Reply(@s, '250 removed');
      end;
    end
    else if cmd = 'DELE' then
    begin
      rel := Under(@s, arg);
      if (rel = '') or not FileExists(RealPath(@s, rel)) then
        Reply(@s, '550 no such file')
      else
      begin
        RemoveFile(RealPath(@s, rel));
        Reply(@s, '250 deleted');
      end;
    end
    else if cmd = 'SIZE' then
    begin
      rel := Under(@s, arg);
      if (rel = '') or not FileExists(RealPath(@s, rel)) then
        Reply(@s, '550 no such file')
      else
        Reply(@s, '213 ' + IntToStr(FileSize(RealPath(@s, rel))));
    end
    else
      Reply(@s, '502 ' + cmd + ' is not a command here');
  end;
  if s.DataL > 0 then
    TcpClose(s.DataL);
  TcpClose(C);
end;

procedure Listen(L: Integer; const Root: string);
var
  c: Integer;
begin
  while True do
  begin
    c := TcpAccept(L);
    if c < 0 then
      Break;
    pas Session(c, Root);
  end;
end;

{ ---- the client ---- }

{ The reply to a command: its lines up to the last one of the code,
  the code given back; 0 when the connection ends. }
function Answer(C: Integer; var Buf: string; out Text: string): Integer;
var
  line: string;
begin
  Result := 0;
  Text := '';
  while TcpReadLine(C, Buf, line) do
  begin
    line := Trimmed(line);
    Text := Text + line + #10;
    if (Length(line) >= 4) and (line[4] = ' ') then
    begin
      Result := StrToIntDef(Copy(line, 1, 3), 0);
      Exit;
    end;
  end;
end;

function Ask(C: Integer; var Buf: string; const Cmd: string; out Text: string): Integer;
begin
  TcpWrite(C, Cmd + #13#10);
  Result := Answer(C, Buf, Text);
end;

{ PASV, and a connection to the port its reply names: h1,h2,h3,h4,p1,p2. }
function OpenData(C: Integer; var Buf: string; const Host: string): Integer;
var
  text, num: string;
  i, k, port: Integer;
  parts: array[0..5] of Integer;
begin
  Result := -1;
  if Ask(C, Buf, 'PASV', text) <> 227 then
    Exit;
  i := 1;
  while (i <= Length(text)) and (text[i] <> '(') do
    i := i + 1;
  i := i + 1;
  for k := 0 to 5 do
  begin
    num := '';
    while (i <= Length(text)) and (text[i] >= '0') and (text[i] <= '9') do
    begin
      num := num + text[i];
      i := i + 1;
    end;
    parts[k] := StrToIntDef(num, 0);
    i := i + 1;
  end;
  port := parts[4] * 256 + parts[5];
  Result := TcpConnectTo(Host, port);
end;

{ The client of the command line: prints every reply. }
procedure Client(const Host: string; Port: Integer; const User, Pass, Cmd, Name: string);
var
  c, d, code: Integer;
  buf, text, data: string;
begin
  c := TcpConnectTo(Host, Port);
  if c < 0 then
  begin
    WriteLn('ftpd: cannot connect to ', Host, ' port ', Port);
    Halt(1);
  end;
  buf := '';
  Answer(c, buf, text);
  Write(text);
  Ask(c, buf, 'USER ' + User, text);
  Write(text);
  if Ask(c, buf, 'PASS ' + Pass, text) <> 230 then
  begin
    Write(text);
    Halt(1);
  end;
  Write(text);
  if (Cmd = 'ls') or (Cmd = 'cat') or (Cmd = 'get') then
  begin
    d := OpenData(c, buf, Host);
    if d < 0 then
    begin
      WriteLn('ftpd: no data connection');
      Halt(1);
    end;
    if Cmd = 'ls' then
      code := Ask(c, buf, 'LIST', text)
    else
      code := Ask(c, buf, 'RETR ' + Name, text);
    Write(text);
    if code <> 150 then
      Halt(1);
    data := ReadAll(d);
    TcpClose(d);
    if Cmd = 'get' then
    begin
      if WriteFile(BaseName(Name), data) then
        WriteLn(Length(data), ' bytes into ', BaseName(Name))
      else
        WriteLn('ftpd: cannot write ', BaseName(Name));
    end
    else
      Write(data);
    Answer(c, buf, text);
    Write(text);
  end
  else if Cmd = 'put' then
  begin
    if not ReadFile(Name, data) then
    begin
      WriteLn('ftpd: cannot read ', Name);
      Halt(1);
    end;
    d := OpenData(c, buf, Host);
    if d < 0 then
    begin
      WriteLn('ftpd: no data connection');
      Halt(1);
    end;
    code := Ask(c, buf, 'STOR ' + BaseName(Name), text);
    Write(text);
    if code <> 150 then
      Halt(1);
    TcpWrite(d, data);
    TcpClose(d);
    Answer(c, buf, text);
    Write(text);
  end
  else
    WriteLn('ftpd: ls, cat name, get name or put name');
  Ask(c, buf, 'QUIT', text);
  Write(text);
  TcpClose(c);
end;

{ ---- the self-test ---- }

{ A connection that has said its greeting, or -1: the greeting is read
  with a deadline and a new connection tried when it does not come. A
  burst of connections past the kernel's SYN backlog is answered with
  SYN cookies, and one whose last ACK meets a full accept queue is
  dropped with nothing kept to retry it: the client holds a connection
  the server never had, and where the server speaks first both would
  wait for ever (termd has the same). }
function Greeted(Port: Integer; var Buf: string): Integer;
var
  k, c: Integer;
  text: string;
begin
  Result := -1;
  for k := 1 to 5 do
  begin
    c := TcpConnectTo('127.0.0.1', Port);
    if c >= 0 then
    begin
      Buf := TcpReadDeadline(c, 512, 3000);
      if (Buf <> '') and (Answer(c, Buf, text) = 220) then
      begin
        Result := c;
        Exit;
      end;
      TcpClose(c);
    end;
  end;
end;

{ One session: log in, make a directory and go there, store a file,
  list, fetch it back and compare, remove the file and the directory. }
procedure TestClient(Port, Id: Integer);
var
  c, d: Integer;
  buf, text, name, sub, body, back: string;
  ok: Boolean;
begin
  ok := False;
  buf := '';
  c := Greeted(Port, buf);
  if c >= 0 then
  begin
    name := 'f' + IntToStr(Id) + '.txt';
    sub := 'd' + IntToStr(Id);
    body := 'hello from session ' + IntToStr(Id) + #10;
    body := body + body + body + body;
    ok := (Ask(c, buf, 'USER test', text) = 331) and
      (Ask(c, buf, 'PASS x', text) = 230) and (Ask(c, buf, 'MKD ' + sub, text) = 257) and
      (Ask(c, buf, 'CWD ' + sub, text) = 250) and
      (Ask(c, buf, 'PWD', text) = 257) and (Copy(text, 1, 6 + Length(sub)) = '257 "/' + sub);
    if ok then
    begin
      d := OpenData(c, buf, '127.0.0.1');
      ok := (d >= 0) and (Ask(c, buf, 'STOR ' + name, text) = 150);
      if ok then
      begin
        TcpWrite(d, body);
        TcpClose(d);
        ok := Answer(c, buf, text) = 226;
      end;
    end;
    if ok then
      AtomicAdd(@stored, 1);
    if ok then
    begin
      d := OpenData(c, buf, '127.0.0.1');
      ok := (d >= 0) and (Ask(c, buf, 'NLST', text) = 150);
      if ok then
      begin
        back := ReadAll(d);
        TcpClose(d);
        ok := (Answer(c, buf, text) = 226) and Has(back, name + #13#10);
      end;
    end;
    if ok then
    begin
      d := OpenData(c, buf, '127.0.0.1');
      ok := (d >= 0) and (Ask(c, buf, 'RETR ' + name, text) = 150);
      if ok then
      begin
        back := ReadAll(d);
        TcpClose(d);
        ok := (Answer(c, buf, text) = 226) and (back = body);
      end;
    end;
    if ok then
      AtomicAdd(@fetched, 1);
    if ok then
      ok := (Ask(c, buf, 'DELE ' + name, text) = 250) and (Ask(c, buf, 'CDUP', text) = 250) and
        (Ask(c, buf, 'RMD ' + sub, text) = 250);
    Ask(c, buf, 'QUIT', text);
    TcpClose(c);
  end;
  if not ok then
    AtomicAdd(@bad, 1);
  done.Done;
end;

procedure SelfTest(N: Integer);
var
  l, i, lim: Integer;
  dir: string;
begin
  lim := RaiseFdLimit;
  if lim < 8 * N + 64 then
    N := (lim - 64) div 8;
  l := TcpListen(0);
  if l < 0 then
  begin
    WriteLn('ftpd: cannot listen');
    Halt(1);
  end;
  dir := '/tmp/paslang-ftpd-' + IntToStr(TcpPort(l));
  if not EnsureDir(dir) then
  begin
    WriteLn('ftpd: cannot make ', dir);
    Halt(1);
  end;
  pas Listen(l, dir);
  done.Add(N);
  for i := 1 to N do
    pas TestClient(TcpPort(l), i);
  done.Wait;
  RemoveDir(dir);
  WriteLn(N, ' sessions, ', stored, ' stored, ', fetched, ' fetched, ', bad, ' bad');
  if (stored <> N) or (fetched <> N) or (bad <> 0) then
    Halt(1);
  Halt(0);                { the server routine parks for ever: end without waiting for it }
end;

var
  port, l: Integer;
  root: string;
begin
  if (ParamCount >= 1) and (ParamStr(1) = '-selftest') then
  begin
    if ParamCount >= 2 then
      SelfTest(StrToIntDef(ParamStr(2), 2000))
    else
      SelfTest(2000);
    Exit;
  end;
  if (ParamCount >= 6) and (ParamStr(1) = '-client') then
  begin
    if ParamCount >= 7 then
      Client(ParamStr(2), StrToIntDef(ParamStr(3), 21), ParamStr(4), ParamStr(5), ParamStr(6), ParamStr(7))
    else
      Client(ParamStr(2), StrToIntDef(ParamStr(3), 21), ParamStr(4), ParamStr(5), ParamStr(6), '');
    Exit;
  end;
  port := 2121;
  if ParamCount >= 1 then
    port := StrToIntDef(ParamStr(1), 2121);
  root := '.';
  if ParamCount >= 2 then
    root := ParamStr(2);
  RaiseFdLimit;
  l := TcpListenAt('', port, 1024);
  if l < 0 then
  begin
    WriteLn('ftpd: cannot listen on port ', port);
    Halt(1);
  end;
  WriteLn('ftpd: listening on port ', TcpPort(l), ', serving ', root);
  Listen(l, root);
end.
```

An NTP server, SNTP after RFC 4330 over UDP, with its client: a
48-byte packet with timestamps as seconds since 1900 and a binary
fraction of a second; the server gives back the client's transmit time
and adds its own clock at receipt and at answer, and the client works
out the offset of the server's clock from its own and the round trip
from the four times. `ntpd -query host [port]` asks any server, `ntpd
[port]` serves the clock of this machine (port 123 needs root), and
`ntpdate -q` or `chronyc` can ask it.

`examples/ntpd.paslang`:

```pascal
{ An NTP time server and its client (P119): SNTP, RFC 4330, over UDP.
  A request is a 48-byte packet in client mode; the answer carries the
  server's clock as it received the request and as it answers, so the
  client works out its offset from the server and the round trip.

    ntpd [port]              serve (123 needs root; 1123 by default) until killed
    ntpd -query host [port]  ask a server once: the offset and the delay
    ntpd -selftest [n]       n client routines (2000 by default) ask this
                             process's own server and check the answer

  make check runs the self-test on both machines. }
program ntpd;

uses pasnet, paslib, pastime;

const
  Era = 2208988800;         { seconds from 1900 to 1970: NTP time is since 1900 }

var
  answered, missed, bad: Integer;
  done: WaitGroup;

function StrToIntDef(const S: string; Def: Integer): Integer;
var
  v, i: Integer;
begin
  v := 0;
  if S = '' then
  begin
    Result := Def;
    Exit;
  end;
  for i := 1 to Length(S) do
  begin
    if (S[i] < '0') or (S[i] > '9') then
    begin
      Result := Def;
      Exit;
    end;
    v := v * 10 + Ord(S[i]) - 48;
  end;
  Result := v;
end;

{ An NTP timestamp, 64 bits: seconds since 1900 above, the fraction of
  a second in 1/2^32 below; and back to nanoseconds since 1970. }
function NtpOf(Ns: Int64): Int64;
var
  secs, fr: Int64;
begin
  secs := Ns div 1000000000 + Era;
  fr := ((Ns mod 1000000000) shl 32) div 1000000000;
  Result := (secs shl 32) or fr;
end;

function NsOf(T: Int64): Int64;
var
  secs, fr: Int64;
begin
  secs := (T shr 32) - Era;
  fr := T and $FFFFFFFF;
  Result := secs * 1000000000 + (fr * 1000000000) shr 32;
end;

{ The eight bytes of a timestamp at position P of a packet, big-endian. }
procedure PutStamp(var Pk: string; P: Integer; T: Int64);
var
  i: Integer;
begin
  for i := 0 to 7 do
    Pk[P + i] := Chr((T shr (56 - 8 * i)) and 255);
end;

function GetStamp(const Pk: string; P: Integer): Int64;
var
  i: Integer;
begin
  Result := 0;
  for i := 0 to 7 do
    Result := (Result shl 8) or Ord(Pk[P + i]);
end;

{ The answer to a request: the version the client spoke, mode 4 (a
  server), stratum 1 (this clock), the request's transmit time given
  back as its originate time, and our clock at receipt and at answer. }
function Answer(const Req: string; Received: Int64): string;
var
  pk: string;
  i: Integer;
begin
  SetLength(pk, 48);
  for i := 1 to 48 do
    pk[i] := #0;
  pk[1] := Chr((Ord(Req[1]) and $38) or 4);     { LI 0, the version, mode 4 }
  pk[2] := #1;                                  { stratum 1 }
  pk[3] := Req[3];                              { the poll interval, as asked }
  pk[4] := Chr(256 - 20);                       { precision 2^-20 s }
  pk[13] := 'L';                                { the reference: LOCL }
  pk[14] := 'O';
  pk[15] := 'C';
  pk[16] := 'L';
  PutStamp(pk, 17, NtpOf(Received));            { the reference time }
  for i := 0 to 7 do
    pk[25 + i] := Req[41 + i];                  { originate: the client's transmit }
  PutStamp(pk, 33, NtpOf(Received));            { receive }
  PutStamp(pk, 41, NtpOf(NowNanos));            { transmit }
  Result := pk;
end;

procedure Serve(Fd: Integer);
var
  req, host: string;
  port: Integer;
begin
  while True do
  begin
    req := UdpRecvFrom(Fd, 512, host, port);
    if (Length(req) >= 48) and ((Ord(req[1]) and 7) = 3) then
      UdpSendTo(Fd, host, port, Answer(req, NowNanos));
  end;
end;

{ A request: version 4, mode 3, our clock as the transmit time. }
function Request(T1: Int64): string;
var
  i: Integer;
begin
  SetLength(Result, 48);
  for i := 1 to 48 do
    Result[i] := #0;
  Result[1] := Chr((4 shl 3) or 3);
  PutStamp(Result, 41, NtpOf(T1));
end;

{ One exchange: the offset of the server's clock from ours and the
  round trip, both in nanoseconds; False when no answer comes in Ms. }
function Query(const Host: string; Port, Ms: Integer; out Offset, Delay: Int64): Boolean;
var
  fd, p: Integer;
  t1, t2, t3, t4: Int64;
  rep, from: string;
begin
  Result := False;
  fd := UdpBindAt('', 0);
  if fd < 0 then
    Exit;
  t1 := NowNanos;
  if UdpSendTo(fd, Host, Port, Request(t1)) < 0 then
  begin
    UdpClose(fd);
    Exit;
  end;
  rep := UdpRecvFromMs(fd, 512, Ms, from, p);
  t4 := NowNanos;
  UdpClose(fd);
  if (Length(rep) < 48) or ((Ord(rep[1]) and 7) <> 4) then
    Exit;
  if GetStamp(rep, 25) <> NtpOf(t1) then
    Exit;                    { not the answer to this request }
  t2 := NsOf(GetStamp(rep, 33));
  t3 := NsOf(GetStamp(rep, 41));
  Offset := ((t2 - t1) + (t3 - t4)) div 2;
  Delay := (t4 - t1) - (t3 - t2);
  Result := True;
end;

procedure Client(Port, Id: Integer);
var
  off, del: Int64;
begin
  if not Query('127.0.0.1', Port, 5000, off, del) then
    AtomicAdd(@missed, 1)
  else if (off > 1000000000) or (off < -1000000000) or (del < 0) or (del > 5000000000) then
    AtomicAdd(@bad, 1)
  else
    AtomicAdd(@answered, 1);
  done.Done;
end;

procedure SelfTest(N: Integer);
var
  fd, i, lim: Integer;
begin
  lim := RaiseFdLimit;
  if lim < N + 64 then
    N := lim - 64;
  fd := UdpBindAt('127.0.0.1', 0);
  if fd < 0 then
  begin
    WriteLn('ntpd: cannot bind');
    Halt(1);
  end;
  SockBuffers(fd, 4 * 1024 * 1024, 4 * 1024 * 1024);
  pas Serve(fd);
  done.Add(N);
  for i := 1 to N do
    pas Client(UdpPort(fd), i);
  done.Wait;
  WriteLn(N, ' queries, ', answered, ' answered, ', missed, ' missed, ', bad, ' bad');
  if (answered <> N) or (bad <> 0) then
    Halt(1);
  Halt(0);                { the server routine parks for ever: end without waiting for it }
end;

var
  port, fd: Integer;
  off, del: Int64;
begin
  if (ParamCount >= 1) and (ParamStr(1) = '-selftest') then
  begin
    if ParamCount >= 2 then
      SelfTest(StrToIntDef(ParamStr(2), 2000))
    else
      SelfTest(2000);
    Exit;
  end;
  if (ParamCount >= 2) and (ParamStr(1) = '-query') then
  begin
    port := 123;
    if ParamCount >= 3 then
      port := StrToIntDef(ParamStr(3), 123);
    if Query(ParamStr(2), port, 3000, off, del) then
      WriteLn('offset ', off div 1000000, ' ms, delay ', del div 1000000, ' ms, server time ',
        StampStr((NowNanos + off) div 1000000000))
    else
    begin
      WriteLn('ntpd: no answer from ', ParamStr(2));
      Halt(1);
    end;
    Exit;
  end;
  port := 1123;
  if ParamCount >= 1 then
    port := StrToIntDef(ParamStr(1), 1123);
  fd := UdpBindAt('', port);
  if fd < 0 then
  begin
    WriteLn('ntpd: cannot bind port ', port);
    Halt(1);
  end;
  WriteLn('ntpd: serving time on port ', UdpPort(fd));
  Serve(fd);
end.
```

A WebSocket server, RFC 6455: the HTTP handshake with the accept
key from `Sha1` and a base64 written in the program, then frames read
by their header (the length in one of three forms, the mask the client
must send), unmasked; text back to the sender on `/echo`, to every
other connection on `/chat` through a channel per connection and one
writer routine, `ping` answered by `pong`, `close` by `close`. A
browser reaches it with `new WebSocket('ws://host:8081/echo')`; `wsd
-send host port path text` is a client for one frame.

`examples/wsd.paslang`:

```pascal
{ A WebSocket server (P119): RFC 6455 over the HTTP handshake, the
  accept key from Sha1 and base64, frames masked by the client and
  unmasked by the server, ping answered by pong, close by close. A
  connection to /echo gets every text frame back; one to /chat gets
  what every other connection there sends, through a channel per
  connection and one writer routine, as termd does.

    wsd [port]               serve (8081 by default) until killed
    wsd -send host port path text
                             a client: the handshake, one text frame,
                             the frame that comes back, printed
    wsd -selftest [n]        n client routines (2000 by default) on
                             /echo, three frames each, every echo
                             checked, in this same process

  A browser reaches it with new WebSocket('ws://host:8081/echo').
  make check runs the self-test on both machines. }
program wsd;

uses pasnet, paslib;

const
  Guid = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11';
  Frames = 3;

type
  PConn = ^TConn;
  TConn = record
    Fd: Integer;
    Out: chan of string;      { frames to write; '' tells the writer to close }
  end;

var
  echoed, opened, bad: Integer;
  chatters: map[Integer] of PConn;
  guard: Mutex;
  done: WaitGroup;

function StrToIntDef(const S: string; Def: Integer): Integer;
var
  v, i: Integer;
begin
  v := 0;
  if S = '' then
  begin
    Result := Def;
    Exit;
  end;
  for i := 1 to Length(S) do
  begin
    if (S[i] < '0') or (S[i] > '9') then
    begin
      Result := Def;
      Exit;
    end;
    v := v * 10 + Ord(S[i]) - 48;
  end;
  Result := v;
end;

{ The word from position I of S up to the next space, I moved past it. }
function Token(const S: string; var I: Integer): string;
var
  j: Integer;
begin
  j := I;
  while (j <= Length(S)) and (S[j] <> ' ') do
    j := j + 1;
  Result := Copy(S, I, j - I);
  I := j;
  while (I <= Length(S)) and (S[I] = ' ') do
    I := I + 1;
end;

function Trimmed(const S: string): string;
begin
  Result := S;
  while (Result <> '') and ((Result[Length(Result)] = #13) or (Result[Length(Result)] = ' ')) do
    SetLength(Result, Length(Result) - 1);
end;

function ToLowerStr(const S: string): string;
var
  i: Integer;
begin
  Result := S;
  for i := 1 to Length(Result) do
    if (Result[i] >= 'A') and (Result[i] <= 'Z') then
      Result[i] := Chr(Ord(Result[i]) + 32);
end;

{ Base64 of any string, RFC 4648, with the = padding. }
function Base64(const S: string): string;
const
  Alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
var
  i, n, v: Integer;
begin
  Result := '';
  i := 1;
  while i <= Length(S) do
  begin
    n := Length(S) - i + 1;
    if n > 3 then
      n := 3;
    v := Ord(S[i]) shl 16;
    if n >= 2 then
      v := v or (Ord(S[i + 1]) shl 8);
    if n = 3 then
      v := v or Ord(S[i + 2]);
    Result := Result + Alphabet[((v shr 18) and 63) + 1] + Alphabet[((v shr 12) and 63) + 1];
    if n >= 2 then
      Result := Result + Alphabet[((v shr 6) and 63) + 1]
    else
      Result := Result + '=';
    if n = 3 then
      Result := Result + Alphabet[(v and 63) + 1]
    else
      Result := Result + '=';
    i := i + 3;
  end;
end;

{ The accept key of a handshake: base64 of the SHA-1 of the client's
  key and the GUID of the protocol. }
function AcceptKey(const Key: string): string;
begin
  Result := Base64(Sha1(Key + Guid));
end;

{ A frame to write: FIN set, the opcode, the length in its form, the
  payload; masked with the four bytes when the sender is a client. }
function Frame(Opcode: Integer; const Payload: string; Masked: Boolean; Mask: Integer): string;
var
  n, i: Integer;
  m: array[0..3] of Char;
  data: string;
begin
  n := Length(Payload);
  Result := Chr($80 or Opcode);
  if Masked then
    i := $80
  else
    i := 0;
  if n < 126 then
    Result := Result + Chr(i or n)
  else if n < 65536 then
    Result := Result + Chr(i or 126) + Chr(n shr 8) + Chr(n and 255)
  else
    Result := Result + Chr(i or 127) + #0#0#0#0 + Chr((n shr 24) and 255) + Chr((n shr 16) and 255) +
      Chr((n shr 8) and 255) + Chr(n and 255);
  if not Masked then
  begin
    Result := Result + Payload;
    Exit;
  end;
  m[0] := Chr((Mask shr 24) and 255);
  m[1] := Chr((Mask shr 16) and 255);
  m[2] := Chr((Mask shr 8) and 255);
  m[3] := Chr(Mask and 255);
  data := Payload;
  for i := 1 to n do
    data[i] := Chr(Ord(data[i]) xor Ord(m[(i - 1) and 3]));
  Result := Result + m[0] + m[1] + m[2] + m[3] + data;
end;

{ The next frame from a connection: its opcode and payload, unmasked;
  False at the end of the stream or on a malformed frame. }
function ReadFrame(Fd: Integer; var Buf: string; out Opcode: Integer; out Payload: string): Boolean;
var
  head, ext, mask: string;
  n, i: Integer;
  masked: Boolean;
begin
  Result := False;
  Opcode := 0;
  Payload := '';
  if not TcpReadN(Fd, 2, Buf, head) then
    Exit;
  Opcode := Ord(head[1]) and 15;
  masked := (Ord(head[2]) and $80) <> 0;
  n := Ord(head[2]) and 127;
  if n = 126 then
  begin
    if not TcpReadN(Fd, 2, Buf, ext) then
      Exit;
    n := (Ord(ext[1]) shl 8) or Ord(ext[2]);
  end
  else if n = 127 then
  begin
    if not TcpReadN(Fd, 8, Buf, ext) then
      Exit;
    n := 0;
    for i := 1 to 8 do
      n := (n shl 8) or Ord(ext[i]);
    if n > 16 * 1024 * 1024 then
      Exit;
  end;
  if masked then
    if not TcpReadN(Fd, 4, Buf, mask) then
      Exit;
  if n > 0 then
    if not TcpReadN(Fd, n, Buf, Payload) then
      Exit;
  if masked then
    for i := 1 to n do
      Payload[i] := Chr(Ord(Payload[i]) xor Ord(mask[((i - 1) and 3) + 1]));
  Result := True;
end;

{ ---- the server ---- }

{ The writer of a connection: frames from its channel to the socket. }
procedure Writer(C: PConn);
var
  f: string;
begin
  while True do
  begin
    f := Recv(C^.Out);
    if f = '' then
      Break;
    if TcpWrite(C^.Fd, f) < 0 then
      Break;
  end;
  TcpClose(C^.Fd);
end;

procedure Broadcast(From: PConn; const Text: string);
var
  id: Integer;
  c: PConn;
  f: string;
begin
  f := Frame(1, Text, False, 0);
  guard.Lock;
  for id, c in chatters do
    if c <> From then
      Send(c^.Out, f);
  guard.Unlock;
end;

{ The handshake, then the frames: text back on /echo, to the others on
  /chat, pong for ping, close for close. }
procedure Serve(Fd: Integer);
var
  buf, line, method, path, key, name, payload: string;
  i, op: Integer;
  c: PConn;
  chat: Boolean;
begin
  AtomicAdd(@opened, 1);
  buf := '';
  key := '';
  if not TcpReadLine(Fd, buf, line) then
  begin
    TcpClose(Fd);
    Exit;
  end;
  i := 1;
  method := Token(Trimmed(line), i);
  path := Token(Trimmed(line), i);
  while TcpReadLine(Fd, buf, line) and (Trimmed(line) <> '') do
  begin
    i := 1;
    name := ToLowerStr(Token(Trimmed(line), i));
    if name = 'sec-websocket-key:' then
      key := Token(Trimmed(line), i);
  end;
  if (method <> 'GET') or (key = '') then
  begin
    TcpWrite(Fd, 'HTTP/1.1 400 Bad Request' + #13#10 + 'Content-Length: 0' + #13#10 + #13#10);
    TcpClose(Fd);
    AtomicAdd(@bad, 1);
    Exit;
  end;
  TcpWrite(Fd, 'HTTP/1.1 101 Switching Protocols' + #13#10 + 'Upgrade: websocket' + #13#10 +
    'Connection: Upgrade' + #13#10 + 'Sec-WebSocket-Accept: ' + AcceptKey(key) + #13#10 + #13#10);
  chat := path = '/chat';
  New(c);
  c^.Fd := Fd;
  c^.Out := MakeChan(64);
  if chat then
  begin
    guard.Lock;
    chatters[Fd] := c;
    guard.Unlock;
  end;
  pas Writer(c);
  while ReadFrame(Fd, buf, op, payload) do
  begin
    if op = 8 then
    begin
      Send(c^.Out, Frame(8, payload, False, 0));
      Break;
    end
    else if op = 9 then
      Send(c^.Out, Frame(10, payload, False, 0))
    else if (op = 1) or (op = 2) then
    begin
      if chat then
        Broadcast(c, payload)
      else
      begin
        AtomicAdd(@echoed, 1);        { counted before the echo leaves: its client can end first }
        Send(c^.Out, Frame(op, payload, False, 0));
      end;
    end;
  end;
  if chat then
  begin
    guard.Lock;
    chatters[Fd] := nil;
    Delete(chatters, Fd);
    guard.Unlock;
  end;
  Send(c^.Out, '');
end;

procedure Listen(L: Integer);
var
  c: Integer;
begin
  while True do
  begin
    c := TcpAccept(L);
    if c < 0 then
      Break;
    pas Serve(c);
  end;
end;

{ ---- the client ---- }

{ The handshake from the client's side: the key from Seed, the accept
  checked. The connection, or -1. }
function Open(const Host: string; Port: Integer; const Path: string; Seed: Integer;
  var Buf: string): Integer;
var
  key, line, name, accept: string;
  i: Integer;
  raw: string;
begin
  Result := -1;
  SetLength(raw, 16);
  for i := 1 to 16 do
    raw[i] := Chr((Seed * 7919 + i * 104729) and 255);
  key := Base64(raw);
  Result := TcpConnectTo(Host, Port);
  if Result < 0 then
    Exit;
  TcpWrite(Result, 'GET ' + Path + ' HTTP/1.1' + #13#10 + 'Host: ' + Host + #13#10 +
    'Upgrade: websocket' + #13#10 + 'Connection: Upgrade' + #13#10 +
    'Sec-WebSocket-Key: ' + key + #13#10 + 'Sec-WebSocket-Version: 13' + #13#10 + #13#10);
  Buf := '';
  accept := '';
  if not TcpReadLine(Result, Buf, line) or (Copy(line, 1, 12) <> 'HTTP/1.1 101') then
  begin
    TcpClose(Result);
    Result := -1;
    Exit;
  end;
  while TcpReadLine(Result, Buf, line) and (Trimmed(line) <> '') do
  begin
    i := 1;
    name := ToLowerStr(Token(Trimmed(line), i));
    if name = 'sec-websocket-accept:' then
      accept := Token(Trimmed(line), i);
  end;
  if accept <> AcceptKey(key) then
  begin
    TcpClose(Result);
    Result := -1;
  end;
end;

procedure SendText(const Host: string; Port: Integer; const Path, Text: string);
var
  c, op: Integer;
  buf, payload: string;
begin
  c := Open(Host, Port, Path, 1, buf);
  if c < 0 then
  begin
    WriteLn('wsd: no WebSocket at ', Host, ':', Port, Path);
    Halt(1);
  end;
  TcpWrite(c, Frame(1, Text, True, $12345678));
  if ReadFrame(c, buf, op, payload) then
    WriteLn(payload)
  else
    WriteLn('wsd: no frame came back');
  TcpWrite(c, Frame(8, '', True, $12345678));
  TcpClose(c);
end;

{ A client of the self-test: Frames texts, each echo checked. }
procedure Client(Port, Id: Integer);
var
  c, k, op: Integer;
  buf, text, payload: string;
  ok: Boolean;
begin
  ok := False;
  buf := '';
  c := Open('127.0.0.1', Port, '/echo', Id, buf);
  if c >= 0 then
  begin
    ok := True;
    for k := 1 to Frames do
    begin
      text := 'hello ' + IntToStr(Id) + ' ' + IntToStr(k);
      if TcpWrite(c, Frame(1, text, True, Id * 2654435761 + k)) < 0 then
        ok := False
      else
        ok := ReadFrame(c, buf, op, payload) and (op = 1) and (payload = text);
      if not ok then
        Break;
    end;
    TcpWrite(c, Frame(8, '', True, 1));
    TcpClose(c);
  end;
  if not ok then
    AtomicAdd(@bad, 1);
  done.Done;
end;

procedure SelfTest(N: Integer);
var
  l, i, lim: Integer;
begin
  lim := RaiseFdLimit;
  if lim < 2 * N + 64 then
    N := (lim - 64) div 2;
  l := TcpListen(0);
  if l < 0 then
  begin
    WriteLn('wsd: cannot listen');
    Halt(1);
  end;
  pas Listen(l);
  done.Add(N);
  for i := 1 to N do
    pas Client(TcpPort(l), i);
  done.Wait;
  WriteLn(N, ' clients, ', N * Frames, ' frames, ', echoed, ' echoed, ', bad, ' bad');
  if (echoed <> N * Frames) or (bad <> 0) then
    Halt(1);
  Halt(0);                { the server routine parks for ever: end without waiting for it }
end;

var
  port, l: Integer;
begin
  if (ParamCount >= 1) and (ParamStr(1) = '-selftest') then
  begin
    if ParamCount >= 2 then
      SelfTest(StrToIntDef(ParamStr(2), 2000))
    else
      SelfTest(2000);
    Exit;
  end;
  if (ParamCount >= 5) and (ParamStr(1) = '-send') then
  begin
    SendText(ParamStr(2), StrToIntDef(ParamStr(3), 8081), ParamStr(4), ParamStr(5));
    Exit;
  end;
  port := 8081;
  if ParamCount >= 1 then
    port := StrToIntDef(ParamStr(1), 8081);
  RaiseFdLimit;
  l := TcpListenAt('', port, 1024);
  if l < 0 then
  begin
    WriteLn('wsd: cannot listen on port ', port);
    Halt(1);
  end;
  WriteLn('wsd: WebSocket on port ', TcpPort(l), ' (/echo, /chat)');
  Listen(l);
end.
```

A chat: rooms over a line protocol, a reader routine per client and
a writer routine on a `select` of the client's channel and a stop
channel, so the reader's end ends the writer without a sentinel line.
A line said goes to every other member of the room through their
channels, and a slow reader holds nobody up beyond the size of its
channel. `chat -connect host port` is the client.

`examples/chat.paslang`:

```pascal
{ A chat server (P119): rooms over TCP, a line protocol. A routine
  reads each client's lines; a second routine writes to it what its
  channel brings, and a select on that channel and a stop channel ends
  the writer when the reader is gone. A line said in a room goes to
  every other member through their channels, so no two routines write
  to one socket at once and a slow reader holds nobody else up beyond
  the size of its channel.

    chat [port]              serve (2324 by default) until killed
    chat -connect host port  a client: your lines go up, the room's
                             come down, until quit or the end of input
    chat -selftest [n]       n clients (2000 by default) in rooms of
                             ten, each says one line and reads the
                             other nine, in this same process

  The commands: name <yours>, join <room>, who, quit; any other line
  is said to the room. }
program chat;

uses pasnet, paslib;

const
  RoomSize = 10;

type
  PClient = ^TClient;
  TClient = record
    Fd: Integer;
    Name, Room: string;
    Out: chan of string;
    Stop: chan of Integer;
  end;
  PRoom = ^TRoom;
  TRoom = record
    Members: map[Integer] of PClient;
  end;

var
  rooms: map[string] of PRoom;
  guard: Mutex;
  nextId, said, delivered, bad: Integer;
  joined, done: WaitGroup;

function StrToIntDef(const S: string; Def: Integer): Integer;
var
  v, i: Integer;
begin
  v := 0;
  if S = '' then
  begin
    Result := Def;
    Exit;
  end;
  for i := 1 to Length(S) do
  begin
    if (S[i] < '0') or (S[i] > '9') then
    begin
      Result := Def;
      Exit;
    end;
    v := v * 10 + Ord(S[i]) - 48;
  end;
  Result := v;
end;

{ The first word of S and the rest after the space. }
procedure HeadRest(const S: string; out Head, Rest: string);
var
  i: Integer;
begin
  i := 1;
  while (i <= Length(S)) and (S[i] <> ' ') do
    i := i + 1;
  Head := Copy(S, 1, i - 1);
  while (i <= Length(S)) and (S[i] = ' ') do
    i := i + 1;
  Rest := Copy(S, i, Length(S) - i + 1);
end;

{ ---- the server ---- }

{ The writer: lines from the channel to the socket, until the stop. }
procedure Writer(C: PClient);
var
  line: string;
  x: Integer;
  more: Boolean;
begin
  more := True;
  while more do
    select
      Recv(C^.Out, line):
        if TcpWrite(C^.Fd, line + #10) < 0 then
          more := False;
      Recv(C^.Stop, x):
        more := False;
    end;
  TcpClose(C^.Fd);
end;

{ Under the guard: the client out of its room, the room gone when empty. }
procedure Leave(C: PClient);
var
  r: PRoom;
begin
  if C^.Room = '' then
    Exit;
  r := rooms[C^.Room];
  if r <> nil then
  begin
    Delete(r^.Members, C^.Fd);
    if Length(r^.Members) = 0 then
      Delete(rooms, C^.Room);
  end;
  C^.Room := '';
end;

procedure Enter(C: PClient; const Name: string);
var
  r: PRoom;
begin
  guard.Lock;
  Leave(C);
  r := rooms[Name];
  if r = nil then
  begin
    New(r);
    New(r^.Members);
    rooms[Name] := r;
  end;
  r^.Members[C^.Fd] := C;
  C^.Room := Name;
  guard.Unlock;
end;

{ The line to every other member of the client's room. }
procedure Say(C: PClient; const Text: string);
var
  r: PRoom;
  id: Integer;
  m: PClient;
begin
  guard.Lock;
  r := nil;
  if C^.Room <> '' then
    r := rooms[C^.Room];
  if r <> nil then
    for id, m in r^.Members do
      if m <> C then
        Send(m^.Out, '[' + C^.Name + '] ' + Text);
  guard.Unlock;
end;

function Who(C: PClient): string;
var
  r: PRoom;
  id: Integer;
  m: PClient;
begin
  Result := '';
  guard.Lock;
  r := nil;
  if C^.Room <> '' then
    r := rooms[C^.Room];
  if r <> nil then
    for id, m in r^.Members do
      if Result = '' then
        Result := m^.Name
      else
        Result := Result + ' ' + m^.Name;
  guard.Unlock;
  if Result = '' then
    Result := 'nobody: join a room first';
end;

{ The reader of a client: its lines, the commands, the rest said. }
procedure Serve(Fd: Integer);
var
  c: PClient;
  buf, line, cmd, arg: string;
begin
  New(c);
  c^.Fd := Fd;
  c^.Name := 'guest' + IntToStr(AtomicAdd(@nextId, 1));
  c^.Room := '';
  c^.Out := MakeChan(256);
  c^.Stop := MakeChan(1);
  pas Writer(c);
  Send(c^.Out, 'welcome ' + c^.Name + ': name <yours>, join <room>, who, quit; anything else is said');
  buf := '';
  while TcpReadLine(Fd, buf, line) do
  begin
    HeadRest(line, cmd, arg);
    if cmd = 'quit' then
      Break
    else if (cmd = 'name') and (arg <> '') then
    begin
      c^.Name := arg;
      Send(c^.Out, 'you are ' + arg);
    end
    else if (cmd = 'join') and (arg <> '') then
    begin
      Enter(c, arg);
      Send(c^.Out, 'in ' + arg + ' with ' + Who(c));
    end
    else if cmd = 'who' then
      Send(c^.Out, Who(c))
    else if line <> '' then
    begin
      AtomicAdd(@said, 1);            { counted before the line leaves: the clients can end first }
      Say(c, line);
    end;
  end;
  guard.Lock;
  Leave(c);
  guard.Unlock;
  Send(c^.Stop, 1);
end;

procedure Listen(L: Integer);
var
  c: Integer;
begin
  while True do
  begin
    c := TcpAccept(L);
    if c < 0 then
      Break;
    pas Serve(c);
  end;
end;

{ ---- the client ---- }

procedure Down(C: Integer);
var
  buf, line: string;
begin
  buf := '';
  while TcpReadLine(C, buf, line) do
    WriteLn(line);
  Halt(0);
end;

procedure Connect(const Host: string; Port: Integer);
var
  c: Integer;
  line: string;
begin
  c := TcpConnectTo(Host, Port);
  if c < 0 then
  begin
    WriteLn('chat: cannot connect to ', Host, ' port ', Port);
    Halt(1);
  end;
  pas Down(c);
  while True do
  begin
    ReadLn(line);
    if line = '' then             { an empty line, or the end of the input }
      line := 'quit';
    if TcpWrite(c, line + #10) < 0 then
      Break;
    if line = 'quit' then
      Break;
  end;
  Sleep(100);
  TcpClose(c);
end;

{ ---- the self-test ---- }

{ A connection that has said its greeting, or -1: the greeting is read
  with a deadline and a new connection tried when it does not come. A
  burst of connections past the kernel's SYN backlog is answered with
  SYN cookies, and one whose last ACK meets a full accept queue is
  dropped with nothing kept to retry it: the client holds a connection
  the server never had, and where the server speaks first both would
  wait for ever (termd has the same). }
function Greeted(Port: Integer; var Buf: string): Integer;
var
  k, c: Integer;
  line: string;
begin
  Result := -1;
  for k := 1 to 5 do
  begin
    c := TcpConnectTo('127.0.0.1', Port);
    if c >= 0 then
    begin
      Buf := TcpReadDeadline(c, 512, 3000);
      if (Buf <> '') and TcpReadLine(c, Buf, line) and (Copy(line, 1, 8) = 'welcome ') then
      begin
        Result := c;
        Exit;
      end;
      TcpClose(c);
    end;
  end;
end;

{ A client: named, in its room, then (everyone in) one line said and
  the others' lines read. The room of client i is i div RoomSize. }
procedure TestClient(Port, Id, Expect: Integer);
var
  c, got: Integer;
  buf, line: string;
  ok: Boolean;
begin
  ok := False;
  got := 0;
  buf := '';
  c := Greeted(Port, buf);
  if c >= 0 then
  begin
    ok := True;
    if ok then
    begin
      TcpWrite(c, 'name c' + IntToStr(Id) + #10);
      ok := TcpReadLine(c, buf, line) and (line = 'you are c' + IntToStr(Id));
    end;
    if ok then
    begin
      TcpWrite(c, 'join room' + IntToStr(Id div RoomSize) + #10);
      ok := TcpReadLine(c, buf, line) and (Copy(line, 1, 3) = 'in ');
    end;
    joined.Done;
    joined.Wait;                      { everyone is in before anyone speaks }
    if ok then
    begin
      TcpWrite(c, 'hi from c' + IntToStr(Id) + #10);
      while (got < Expect) and TcpReadLine(c, buf, line) do
        if (Copy(line, 1, 2) = '[c') and (Copy(line, Length(line) - 7, 8) = 'hi from ') or
          (Length(line) > 10) and (Copy(line, 1, 2) = '[c') then
          got := got + 1
        else
        begin
          ok := False;
          Break;
        end;
      ok := ok and (got = Expect);
    end;
    TcpWrite(c, 'quit' + #10);
    TcpClose(c);
  end
  else
    joined.Done;
  AtomicAdd(@delivered, got);
  if not ok then
    AtomicAdd(@bad, 1);
  done.Done;
end;

procedure SelfTest(N: Integer);
var
  l, i, lim, size, expect: Integer;
begin
  lim := RaiseFdLimit;
  if lim < 2 * N + 64 then
    N := (lim - 64) div 2;
  l := TcpListen(0);
  if l < 0 then
  begin
    WriteLn('chat: cannot listen');
    Halt(1);
  end;
  New(rooms);
  pas Listen(l);
  done.Add(N);
  joined.Add(N);
  expect := 0;
  for i := 0 to N - 1 do
  begin
    size := N - (i div RoomSize) * RoomSize;
    if size > RoomSize then
      size := RoomSize;
    expect := expect + size - 1;
    pas TestClient(TcpPort(l), i, size - 1);
  end;
  done.Wait;
  WriteLn(N, ' clients, ', said, ' said, ', delivered, ' delivered of ', expect, ', ', bad, ' bad');
  if (said <> N) or (delivered <> expect) or (bad <> 0) then
    Halt(1);
  Halt(0);                { the server routine parks for ever: end without waiting for it }
end;

var
  port, l: Integer;
begin
  if (ParamCount >= 1) and (ParamStr(1) = '-selftest') then
  begin
    if ParamCount >= 2 then
      SelfTest(StrToIntDef(ParamStr(2), 2000))
    else
      SelfTest(2000);
    Exit;
  end;
  if (ParamCount >= 3) and (ParamStr(1) = '-connect') then
  begin
    Connect(ParamStr(2), StrToIntDef(ParamStr(3), 2324));
    Exit;
  end;
  port := 2324;
  if ParamCount >= 1 then
    port := StrToIntDef(ParamStr(1), 2324);
  RaiseFdLimit;
  l := TcpListenAt('', port, 1024);
  if l < 0 then
  begin
    WriteLn('chat: cannot listen on port ', port);
    Halt(1);
  end;
  WriteLn('chat: rooms on port ', TcpPort(l));
  New(rooms);
  Listen(l);
end.
```

A reverse proxy at the level of TCP: every connection accepted is
joined to a new connection to the backend, and two routines copy the
bytes, one each way, until each side ends; a direction that ends
shuts the write side of the other socket (`TcpShutdown`) so the peer
sees the end, and the last of the two routines closes both. Anything
over TCP goes through as it is. The self-test puts a small HTTP
backend behind it.

`examples/proxy.paslang`:

```pascal
{ A reverse proxy (P119): every connection accepted is joined to a new
  connection to the backend, and two routines copy the bytes, one each
  way, until each side ends; the proxy sees no protocol, so HTTP,
  WebSocket or anything over TCP goes through as it is. Ten thousand
  connections are twenty thousand parked routines.

    proxy [port] host backendport   listen (8082 by default) and forward
                                    to host:backendport until killed
    proxy -selftest [n]             a small HTTP backend, the proxy in
                                    front, n clients (2000 by default)
                                    through it with three requests each
                                    on a kept-alive connection, every
                                    answer checked, in this same process

  make check runs the self-test on both machines. }
program proxy;

uses pasnet, paslib;

const
  Requests = 3;

var
  forwarded, served, bad: Integer;
  done: WaitGroup;

function StrToIntDef(const S: string; Def: Integer): Integer;
var
  v, i: Integer;
begin
  v := 0;
  if S = '' then
  begin
    Result := Def;
    Exit;
  end;
  for i := 1 to Length(S) do
  begin
    if (S[i] < '0') or (S[i] > '9') then
    begin
      Result := Def;
      Exit;
    end;
    v := v * 10 + Ord(S[i]) - 48;
  end;
  Result := v;
end;

function Token(const S: string; var I: Integer): string;
var
  j: Integer;
begin
  j := I;
  while (j <= Length(S)) and (S[j] <> ' ') do
    j := j + 1;
  Result := Copy(S, I, j - I);
  I := j;
  while (I <= Length(S)) and (S[I] = ' ') do
    I := I + 1;
end;

{ ---- the proxy ---- }

{ One direction: what comes from A goes to B until A ends, then B is
  told there is no more (its write side shut); the last of the two
  routines to end closes both. }
procedure Copy1(A, B: Integer; Left: PInteger);
var
  data: string;
begin
  while True do
  begin
    data := TcpRead(A, 65536);
    if data = '' then
      Break;
    if TcpWrite(B, data) < 0 then
      Break;
  end;
  TcpShutdown(B, 1);
  if AtomicAdd(Left, -1) = 0 then
  begin
    TcpClose(A);
    TcpClose(B);
    FreeMem(Left);
  end;
end;

procedure Relay(C: Integer; const Host: string; Port: Integer);
var
  b: Integer;
  left: PInteger;
begin
  b := TcpConnectTo(Host, Port);
  if b < 0 then
  begin
    TcpClose(C);
    AtomicAdd(@bad, 1);
    Exit;
  end;
  AtomicAdd(@forwarded, 1);
  GetMem(left, 8);
  left^ := 2;
  pas Copy1(C, b, left);
  Copy1(b, C, left);
end;

procedure Listen(L: Integer; const Host: string; Port: Integer);
var
  c: Integer;
begin
  while True do
  begin
    c := TcpAccept(L);
    if c < 0 then
      Break;
    pas Relay(c, Host, Port);
  end;
end;

{ ---- the backend of the self-test: GET /hello, kept alive ---- }

procedure Backend(C: Integer);
var
  buf, line, method, path: string;
  i: Integer;
  body: string;
begin
  buf := '';
  while TcpReadLine(C, buf, line) do
  begin
    if line = '' then
      Continue;
    i := 1;
    method := Token(line, i);
    path := Token(line, i);
    while TcpReadLine(C, buf, line) and (line <> '') do
      ;
    if (method = 'GET') and (path = '/hello') then
      body := 'hello through the proxy' + #10
    else
      body := 'no' + #10;
    AtomicAdd(@served, 1);            { counted before the answer leaves: its client can end first }
    if TcpWrite(C, 'HTTP/1.1 200 OK' + #13#10 + 'Content-Length: ' + IntToStr(Length(body)) + #13#10 +
      'Connection: keep-alive' + #13#10 + #13#10 + body) < 0 then
    begin
      AtomicAdd(@served, -1);
      Break;
    end;
  end;
  TcpClose(C);
end;

procedure BackendListen(L: Integer);
var
  c: Integer;
begin
  while True do
  begin
    c := TcpAccept(L);
    if c < 0 then
      Break;
    pas Backend(c);
  end;
end;

{ A client through the proxy: Requests requests on one connection. }
procedure Client(Port, Id: Integer);
var
  c, k, i, n: Integer;
  buf, line, body: string;
  ok: Boolean;
begin
  c := TcpConnectTo('127.0.0.1', Port);
  if c < 0 then
  begin
    AtomicAdd(@bad, 1);
    done.Done;
    Exit;
  end;
  buf := '';
  for k := 1 to Requests do
  begin
    if TcpWrite(c, 'GET /hello HTTP/1.1' + #13#10 + 'Host: self' + #13#10 + #13#10) < 0 then
    begin
      AtomicAdd(@bad, 1);
      Break;
    end;
    ok := TcpReadLine(c, buf, line) and (line = 'HTTP/1.1 200 OK');
    n := -1;
    while ok and TcpReadLine(c, buf, line) and (line <> '') do
    begin
      i := 1;
      if Token(line, i) = 'Content-Length:' then
        n := StrToIntDef(Token(line, i), -1);
    end;
    if ok and (n >= 0) then
      ok := TcpReadN(c, n, buf, body) and (body = 'hello through the proxy' + #10)
    else
      ok := False;
    if not ok then
    begin
      AtomicAdd(@bad, 1);
      Break;
    end;
  end;
  TcpClose(c);
  done.Done;
end;

procedure SelfTest(N: Integer);
var
  b, l, i, lim: Integer;
begin
  lim := RaiseFdLimit;
  if lim < 4 * N + 64 then
    N := (lim - 64) div 4;
  b := TcpListen(0);
  l := TcpListen(0);
  if (b < 0) or (l < 0) then
  begin
    WriteLn('proxy: cannot listen');
    Halt(1);
  end;
  pas BackendListen(b);
  pas Listen(l, '127.0.0.1', TcpPort(b));
  done.Add(N);
  for i := 1 to N do
    pas Client(TcpPort(l), i);
  done.Wait;
  WriteLn(N, ' clients, ', forwarded, ' forwarded, ', N * Requests, ' requests, ', served, ' served, ',
    bad, ' bad');
  if (forwarded <> N) or (served <> N * Requests) or (bad <> 0) then
    Halt(1);
  Halt(0);                { the server routines park for ever: end without waiting for them }
end;

var
  port, l: Integer;
begin
  if (ParamCount >= 1) and (ParamStr(1) = '-selftest') then
  begin
    if ParamCount >= 2 then
      SelfTest(StrToIntDef(ParamStr(2), 2000))
    else
      SelfTest(2000);
    Exit;
  end;
  if ParamCount < 3 then
  begin
    WriteLn('proxy [port] host backendport, or proxy -selftest [n]');
    Halt(2);
  end;
  port := StrToIntDef(ParamStr(1), 8082);
  RaiseFdLimit;
  l := TcpListenAt('', port, 1024);
  if l < 0 then
  begin
    WriteLn('proxy: cannot listen on port ', port);
    Halt(1);
  end;
  WriteLn('proxy: port ', TcpPort(l), ' to ', ParamStr(2), ':', ParamStr(3));
  Listen(l, ParamStr(2), StrToIntDef(ParamStr(3), 80));
end.
```

`pasnet` is written over the compiler's own network words, which every
program has without `uses`:

| Word | What it does |
|---|---|
| `NetListen(port)` | a TCP socket bound to `port` on every IPv4 address and listening, non-blocking, with `SO_REUSEADDR` and `TCP_NODELAY`: its descriptor, or a negative number when that fails |
| `NetPort(fd)` | the socket's local port; 0 when it cannot be read |
| `NetAccept(fd)` | the descriptor of the next connection, parking until one comes; negative on an error |
| `NetConnect(ip4, port)` | a connection to the IPv4 address given as one `Integer` (`127.0.0.1` is `$7F000001`), parking until it is made: its descriptor, or -1 |
| `NetRead(fd, max, s)` | a procedure: parks until bytes come and puts up to `max` of them (1 to 65536) in the string variable `s`, which is empty at the end of the stream or on an error |
| `NetWrite(fd, s)` | writes all of `s`, parking while the socket is full: the count written, negative on an error |
| `NetClose(fd)` | a procedure: takes the descriptor off the poller and closes it |
| `WaitFd(fd)` | parks until `fd` can be read |
| `WaitIo(fd, ev)` | parks until `fd` is ready for `ev`: 1 to read, 4 to write |
| `WaitMs(fd, ev, ms)` | `WaitIo`, which also returns after `ms` milliseconds; 0 or less returns at once |

The three `Wait` words park the routine on the runtime's epoll, one wake
per wait, and the thread goes on with other routines. Their `Integer`
result says nothing: after one the caller tries its read or its write
again, as `pasnet` does:

```
nr := 63;                                { read on arm64 }
if Amd64 = 1 then
  nr := 0;                               { read on amd64 }
n := Syscall(nr, fd, @buf, 512);         { -11: nothing yet (EAGAIN) }
while n = -11 do
begin
  WaitIo(fd, 1);                         { park until fd can be read }
  n := Syscall(nr, fd, @buf, 512);
end;
```

`uses paslib` gives files and processes: `ReadFile`, `WriteFile`,
`FileExists`, `ListDir`, `GetEnv`, `Run(exe, args)`, `RunCapture`,
`IntToStr`, `StrToInt64` and string helpers. `uses paslinux` gives the
raw system calls under Pascal names such as `OsOpen`, `OsRead`,
`OsWrite`, `OsFork` and `OsWait`.

The words of `paslib`, with their shapes: `ReadFile(path, out data)`
and `WriteFile(path, data)` take or write the whole of a file and say
whether they could, `ReadPrefix(path, n, out data)` the first `n`
bytes, `FileExists(path)`, `FileSize(path)`, `EnsureDir(path)`,
`CopyFile(src, dst)`, `ReadLink(path, out target)` and
`ListDir(path)`, the names of the entries joined by a newline (`''` for
a directory that cannot be read). A piece at a time goes through a
descriptor, an `Int64` below zero when the open failed: `FileOpen`
opens to read, `FileCreate` makes or empties and opens to write,
`FileAppend` opens to add at the end, making the file when it is not
there, `FileEdit` opens to read and write keeping what is there;
`FileRead(fd, n)` gives up to `n` bytes from where the handle stands,
`''` at the end, `FileWrite(fd, data)` the count written,
`FileSeek(fd, off, whence)` moves it (0 from the start, 1 from where
it is, 2 from the end) and gives the new place, `FileTell` where it
is, `FileEnd` moves to the end, and `FileClose` closes. `Run(exe,
args)` runs a program with an `array of string` of arguments and waits
for it, giving the status it ended with; `RunCapture(exe, args, out
output)` also collects what it wrote to standard output; `LookPath(exe)`
finds a name with no slash in `PATH`, as a shell does. `GetEnv(name)`
reads the environment, `IntToStr`, `StrToInt64(s, out v)`,
`IntToHex2(b)`, `ToLower`, `HasSuffix`, `ChangeExt`, `BaseName`,
`DirName` and `JoinPath` shape strings and paths.

## 16. The clock, chance and order

Four more units are installed beside the compiler. They are ordinary
paslang over `Syscall`, not part of the language: name them in `uses`.

`pastime` has two clocks, and they are not the same one. `NowUnix` and
`NowNanos` read the wall clock, which says what time it is and can jump
when somebody sets it. `Monotonic` and `Since` read the clock that only
goes forward, which is the one to measure with. `UnixToDate` takes a
moment apart into a `TDate` (year, month, day, hour, minute, second,
weekday, day of the year) and `DateToUnix(y, m, d, hh, mm, ss)` gives
the moment of a date; `DateStr`, `TimeStr` and `StampStr` write a
moment, and `DateOf`, `TimeOf` and `StampOf` a `TDate`, the way an ISO
date is written, `WeekdayName` and `MonthName` name its day and month,
and `Duration` says a length of time the way a person would.
Dates are UTC: there is no timezone file to read and none is read.

`NowUnix` is seconds and `NowNanos` nanoseconds of the wall clock,
`Monotonic` nanoseconds of `CLOCK_MONOTONIC` and `Since(t0)` is
`Monotonic - t0`; `Millis`, `Micros` and `SecsOf` divide a count of
nanoseconds, and `NsPerMs`, `NsPerUs` and `NsPerSec` are the constants
to multiply by. `Duration(ns)` writes `ns` as `999ns` below a
microsecond, `12.3us`, `12.3ms` and `12.3s` with one decimal below a
millisecond, a second and a minute, and `2m05s` from a minute on, with
a `-` in front of a negative one.

`pasrand` draws numbers. `RandInit(R, Seed)` gives you a generator of
your own, and `RandNext`, `RandBelow`, `RandRange`, `RandReal` and
`RandBool` draw from it; the same seed gives the same sequence, which
is what a test needs. `RandSeed`, `Randomize`, `RandInt`, `RandN`,
`RandRangeN` and `RandFloat` use one global generator behind a mutex,
so two routines may call them at once. The stream is xoshiro256**,
seeded through splitmix64. It is not for secrets.

`RandNext(g)` is the whole word, sign included, so it prints negative
half the time. `RandBelow(g, n)` is from 0 to `n - 1`: the top of the
range that does not divide evenly by `n` is thrown away and drawn
again, so every value is as likely as every other, and an `n` of 1 or
less gives 0. `RandRange(g, lo, hi)` includes both ends and gives `lo`
when `hi` is below it. `RandReal(g)` is from 0 up to but not including
1, built from the top 53 bits, and `RandBool(g)` is the top bit.
`RandInit(g, seed)` makes the four words of state from the seed with
splitmix64, so nearby seeds give unrelated streams, and the one state
the generator cannot leave, all zero, is turned into another; a
`TRand` is a record of four `Int64` and assigning one copies the
stream, both copies then drawing the same numbers. The same seed draws
the same numbers on amd64 and on arm64. The global generator seeds
itself from the kernel (`getrandom`) the first time it is used, unless
`RandSeed` came first; `Randomize` seeds it from the kernel again.

`passort` puts things in order. `SortInts`, `SortReals` and
`SortStrings` sort a slice in place with quicksort (a `var` parameter
of `array of Int64`, `Real` or `string`: a static array goes as
`a[Low(a)..High(a)]`, which shares its elements), and
`SortIntsBy`, `SortRealsBy` and `SortStringsBy` take the order as a
routine value (`function(A, B: Int64): Boolean`), which is what Go's
`sort.Slice` takes. They use quicksort too, with the middle of three
for the pivot, so an array that is already sorted is not the slow
case; they have no insertion-sort cutoff, since each comparison is a
call of the routine value either way. `IntsSorted` and
its kin say whether an array is in order. `FindInt` and `FindStr` look
a value up in a sorted array and `PlaceInt` and `PlaceStr` say where
one would go.

`examples/sorting.paslang`:

```pascal
{ passort puts a slice in order, by < or by an order handed in as a
  routine value; a heap of T gives its least element first, so it is a
  priority queue, and a heap kept at k elements holds the k largest. }
program sorting;

uses
  passort;

var
  nums: array of Int64;
  names: array of string;
  queue: heap of string;
  top: heap of Int64;
  i: Integer;
  s: string;

function Descending(A, B: Int64): Boolean;
begin
  Result := A > B;
end;

procedure ShowInts;
begin
  for i := 0 to High(nums) do
    Write(nums[i], ' ');
  WriteLn;
end;

begin
  SetLength(nums, 8);
  nums[0] := 42; nums[1] := -7; nums[2] := 19; nums[3] := 0;
  nums[4] := 19; nums[5] := 100; nums[6] := -70; nums[7] := 3;
  SortInts(nums);
  ShowInts;                                   { -70 -7 0 3 19 19 42 100 }
  WriteLn(FindInt(nums, 19), ' ', FindInt(nums, 20), ' ', PlaceInt(nums, 20));   { 4 -1 6 }
  SortIntsBy(nums, @Descending);              { @ takes the routine as a value }
  ShowInts;                                   { 100 42 19 19 3 0 -7 -70 }
  SetLength(names, 5);
  names[0] := 'pear'; names[1] := 'Fig'; names[2] := 'apple'; names[3] := 'fig'; names[4] := 'kiwi';
  SortStrings(names);
  for i := 0 to High(names) do
    Write(names[i], ' ');
  WriteLn;                                    { Fig apple fig kiwi pear: by bytes, F before a }
  New(queue);                                 { the least string first: the priority, then the text }
  Push(queue, '2 write the report');
  Push(queue, '1 call back');
  Push(queue, '3 lunch');
  Push(queue, '1 answer the door');
  while Pop(queue, s) do
    WriteLn(s);
  New(top);                                   { the three largest of nums }
  for i := 0 to High(nums) do
  begin
    Push(top, nums[i]);
    if Length(top) > 3 then
      Pop(top);                               { the least of the four goes }
  end;
  WriteLn(Low(top), ' ', Pop(top), ' ', Pop(top), ' ', Pop(top));   { 19 19 42 100 }
end.
```

prints

```
-70 -7 0 3 19 19 42 100 
4 -1 6
100 42 19 19 3 0 -7 -70 
Fig apple fig kiwi pear 
1 answer the door
1 call back
2 write the report
3 lunch
19 19 42 100
```

`@Descending` is the routine as a value (§5); `SortIntsBy(a, nil)`
sorts nothing. The `By` forms partition down to two elements and never
switch to insertion sort, so their cost is the compares of quicksort
alone, one call of the routine each; the routine must answer the same
way about the same two values every time, and must not say both `A`
before `B` and `B` before `A`. `FindInt`, `FindStr`, `PlaceInt` and
`PlaceStr` are binary searches and ask for a sorted array: `PlaceInt`
is the first index whose value is not below the one sought, `Length`
when it goes at the end, and `FindInt` is that index when the value is
there, so of two equal values it names the first, and `-1` otherwise.
`SortStrings` orders bytes, `'Fig'` before `'apple'`; an order that
folds case, or sorts by length as `ByLength` might, is a `TStrLess`
handed to `SortStringsBy`. The heap of strings orders the same way,
which is why a priority written as a leading digit sorts the queue.

`pasx11` (`uses pasx11`) is raw X11 over the display's Unix socket, no
Xlib: a `TX11` object with `Connect`, `CreateWin`, `CreateGc`,
`MapWin`, `SetTitle`, `SetClass`, `SetProtocols` and `IsCloseEvent`
(the window manager's close), `FillRect`, `DrawLine`, `DrawText` (with
`LoadFont` and `TextWidth`), `SetFg`, `SetBg`, `SetClip`, `Sync`,
`NextEvent`, `Queued` and `CanRead` (the routine that draws parks on
the socket with `WaitFd` while nothing arrives), `Atom`, `TakeProp`,
`AnswerSel` and `ClipRound` for the clipboard, `Keysym` and
`KeysymShift` for the keyboard, `SendClick` and `SendKey` to drive a
window from a test, and `PixelAt` to read one back. `make check` opens
its windows on an `Xvfb` display when `Xvfb` is installed, and on the
current display otherwise.

`examples/clock.paslang`:

```pascal
{ The clock, chance and order: three units of the installed library.
  pastime reads the two clocks and turns a moment into a date, pasrand
  draws numbers from a seed you choose, and passort puts them in order.
  Everything printed here is the same on every run: the date comes from
  a moment written down, the numbers from a seed written down, and the
  measured sleep is only asked whether it lasted. }
program clock;

uses
  paslib, pastime, pasrand, passort;

var
  start, took: Int64;
  d: TDate;
  g: TRand;
  a: array of Int64;
  i: Integer;
  line: string;

begin
  { The monotonic clock measures; it never goes back, whatever anybody
    does to the wall clock while we are counting. }
  start := Monotonic;
  Sleep(30);
  took := Since(start);
  WriteLn('slept at least 30ms: ', took >= 30 * NsPerMs);

  { The wall clock says what time it is. This one is written down so
    the example prints the same thing for everybody. }
  d := UnixToDate(1234567890);
  WriteLn(StampOf(d), ' ', WeekdayName(d.Wday));
  WriteLn(d.Year, ' ', MonthName(d.Month), ' ', d.Day, ' day ', d.Yday);
  WriteLn(DateToUnix(2009, 2, 13, 23, 31, 30) = 1234567890);

  { Ten numbers from a seed, and the same ten in order. }
  RandInit(g, 2026);
  SetLength(a, 10);
  line := '';
  for i := 0 to 9 do
  begin
    a[i] := RandBelow(g, 100);
    line := line + IntToStr(a[i]) + ' ';
  end;
  WriteLn(line);
  SortInts(a);
  line := '';
  for i := 0 to 9 do
    line := line + IntToStr(a[i]) + ' ';
  WriteLn(line, IntsSorted(a));
  WriteLn('50 would go at ', PlaceInt(a, 50));
end.
```

prints

```
slept at least 30ms: 1
2009-02-13 23:31:30 Friday
2009 February 13 day 44
1
54 56 9 93 97 68 86 19 65 66 
9 19 54 56 65 66 68 86 93 97 1
50 would go at 2
```

## 17. The runtime model

A running program is a set of routines, Gs, on a set of OS threads, Ms.
At most one M runs Pascal code for each CPU the program may use (its
affinity mask); only the first M starts with the program, and another
starts when there is work for it and no M is idle (1.0.70). The current
G is in a register (`r14` on amd64, `x28` on arm64) and every routine
has its own stack that grows on demand: each routine entry checks the
stack and calls the runtime when it needs more. A system monitor thread
marks a long-running routine every 10 ms, and the scheduler takes it
off its M at its next routine entry or loop head; a `for` whose body
calls nothing and holds no other loop asks once every 1024 passes.

A routine that waits, on a channel, a mutex, a condition, `Sleep`, a
socket or standard input, parks: its registers and stack pointer are
saved in the G and the thread picks the next runnable routine. A
routine that another one readies goes first in line on the thread that
readied it, so a send and the receive it wakes cost no thread switch.
When nothing is runnable a thread looks for work for a short while and
then sleeps: one thread waits in `epoll_wait` for events and timers,
the others on a futex until they are needed; an idle program uses no
CPU. The timers are one heap of routines by wake time, as Go's: `Sleep`
and a wait with a deadline (`WaitMs`, `TcpReadDeadline`,
`UdpRecvFromMs`) go in and out of it in O(log n) and cost no system
call, whichever of the descriptor and the deadline comes first; ten
thousand routines asleep at once are ten thousand entries and nothing
else (1.1.1). The last thread to go to sleep checks whether anything can still
happen: with no timer pending, no routine waiting on a descriptor, no
thread in a system call or looking for work, and a routine still alive,
it stops the program with `paslang: all routines are asleep: deadlock`
(§10, 1.0.139).

The program does not link libc. Every operation is a system call from
the runtime or from a Pascal unit: `Syscall(nr, a, b, ...)` takes 1 to 7
arguments and gives the kernel's answer, a negative error number when
the call failed: `n := Syscall(...)`. As a statement it makes the call
and drops the answer (1.0.136; the statement put the number in the
wrong register and ran whatever call that register held).
The constant `Amd64` is 1 on an amd64 compile and 0 on arm64, the way to
pick a system call number. The child of a fork may run only raw system
calls until it calls `execve`; `paslib`'s `Run` shows the pattern.

`Remove` in `examples/kvstore.paslang` (§11) is the pattern at its
smallest: the path gets a `#0` on the end and goes as `Integer(@z[1])`,
the number is picked by `Amd64` since arm64 has no `unlink` (87 on
amd64) but only `unlinkat` (35, with `-100` for `AT_FDCWD` in front of
the path), and the call is a statement because nobody reads the
answer. A kernel error comes back as a negative number and does not
stop the program: a `Syscall` that must succeed is assigned and tested.

Memory is collected. A cycle of the collector stops the routines at
their next safe point, marks every block the globals, the routines'
records and their stacks reach, and frees the rest; pages that stay
free go back to the kernel. Compiled code carries a map of its frame at
every call, so a stack is read by the types of what it holds. The next
cycle comes when what was handed out since the last one reaches twice
what it left alive: `PASLANG_GC=100` is the default, a larger number
trades memory for fewer cycles, and `PASLANG_GC=off` never collects.
`GcCollect` runs a cycle at once and answers 1 (0 when it cannot, under
a runtime lock). `HeapStat(k)` reads the heap's figures: 0 cycles, 1
bytes alive after the last one, 2 the next goal, 3 bytes mapped, 4 given
back to the kernel, 5 in use, 6 free, 7 handed out, 8 and 9 the total
and the last pause in nanoseconds, 14 the workers that marked the last
cycle, 15 how many may mark one, and 16, 17 and 18 the last cycle's
stop, mark and sweep in nanoseconds. The marking is shared: the threads
the cycle stopped and the idle ones take the roots in turn and give
each other what they still have to scan, at most 16 of them, since
past that waking them costs more than they mark; `PASLANG_GCWORKERS=n`
sets another limit, 0 every thread, 1 the cycle's thread alone.
`FreeMem` does nothing: a block goes
when nothing points to it any more. An `Integer` holding an address
does not keep a block alive, as in Go; keep the pointer too.

Three switches test the runtime itself. `PASLANG_GCSTRESS=n` runs a
cycle every n-th time an allocation takes a new run of slots;
`PASLANG_GCPOISON=1` fills every freed block with $de, so a pointer the
collector did not see reads nonsense at once; `PASLANG_GCVERIFY=1`
reads every stack a second time word by word after the maps and fills
with $de, without freeing it, whatever only that reading keeps, so a
pointer a map left out shows the same way; it also moves every stack
after each cycle and fills the old one with $de. `HeapStat(11)` counts
those blocks, `HeapStat(12)` the frames whose map did not fit and
`HeapStat(13)` the stacks moved, grown or asked to.

Some words look at the program from inside, for tests and debuggers,
and DWARF line numbers are always emitted:

| Word | What it does |
|---|---|
| `DumpLocals` | a statement: prints the integer locals of the current routine, `name=value` a line, on both machines |
| `SrcLine` | the line of the source where it is written, an `Integer` |
| `Breakpoint` | parks the current routine and records it and the address its call returns to; one routine is recorded, the last |
| `BreakCount`, `BreakPC` | how many `Breakpoint`s have run, and that address of the last one |
| `ContinueBreak` | from another routine: readies the routine the last `Breakpoint` parked; nothing when none has |
| `HeapCheck` | walks the heap and counts what does not hold (a span, a page's entry, a block's class or bits, the collector's lists): 0 is a sound heap |
| `HeapMaskOf(p)` | the pointer bits the heap keeps for the block that holds `p`, bit i for word i of its first 64: what the collector scans; -1 when `p` is in no heap block |

```
pas Worker;                    { Worker calls Breakpoint }
while BreakCount = 0 do
  Yield;
WriteLn(BreakPC <> 0);         { 1 }
ContinueBreak;                 { Worker goes on }
```

A fatal runtime error prints one line on standard error and exits 1,
the way `paslang: nil map` does. The line names the statement in the
program file when the fault is in it:

```
paslang: nil pointer dereference at line 16
paslang: integer divide by zero at line 11
paslang: index 10 out of range [0..4] at line 12
paslang: stack overflow at line 12
paslang: out of memory: 4 MiB mapped
paslang: send on closed channel at line 11
paslang: real out of integer range at line 11
paslang: sqrt domain at line 4
paslang: pointer outside its object at line 35
paslang: all routines are asleep: deadlock
```

The last one names no line: every routine is asleep and none is at
fault (§10).

Every index is checked, on every read and write, as in Go: a static
array's against its bounds, a slice's against `0..Length - 1`, a
string's against `1..Length`, a `View`'s against its `n`; a pointer's
(`PChar`, `p[i]` of a `^T`) is not, unless the unit is built with
`-checkptr`, which holds `p[i]` to `p`'s own object (§6). There is no
switch to turn it off, and a constant index of a
static array is checked when the program is compiled, so it costs
nothing when it is in range. A `for` whose body calls nothing checks
`a[i]`, `a[i + 1]` or `a[i - 1]` (a static array's, or a slice's the
loop does not assign) once for every 1024 passes: when the whole run is
in range it runs without the checks, as Go's compiler leaves out the
ones it can prove, and otherwise with them, so the program still stops
at the first index out of range, at its line. A `for` from a constant
of at least 1 to `Length(s)` of a string variable whose body only
stores `s[i]` from values that call nothing checks `s` once before the
loop, making its characters its own, and its stores check nothing: the
loop can neither change the length nor share the string (1.1.1).

The domain errors of the calculation set (`ln`, `log`, `power`,
`arcsin`, `arccos`, `arcsec`, `arccsc`, `arccosh`, `arctanh`, `lnxp1`)
read like `sqrt domain`. The others include `invalid memory address
0x...`, `bus error`, `integer overflow`, `close of closed channel`,
`close of a channel with a waiting sender`, `channel capacity N out of
range`, `concurrent map writes` (and `concurrent map read and map
write`, `concurrent map iteration and map write`), `bit N out of
range`, `128-bit division overflow`, `out of stack memory`,
`allocation too large` and `mmap failed`. A fault inside a unit or
inside the runtime names no line but the address instead, as Go's
signal report does: `paslang: nil pointer dereference at pc 0x4086e7`. There is no core dump to read first
and no signal to catch: the program has said what happened.

### Runtime words

`pasroutines` is Pascal over a few words of the scheduler, which any
program may use to build a waiting structure of its own. A queue here
is one word (the first routine) or two (the first and the last), and
the routines in it are linked through a word of each routine's record,
so a routine is in one queue at a time. `@q` and `@w` are the addresses
of those words; a routine is an `Integer`, 0 for none.

| Word | What it does |
|---|---|
| `AtomicAdd(@v, d)` | adds `d` to the `Integer` `v` at once for every routine (`lock xadd`; `ldaxr`/`stlxr`) and gives the new value |
| `AtomicCas(@v, old, new)` | puts `new` in `v` when it holds `old`, at once for every routine, and says whether it did: a `Boolean` |
| `Pause` | the spin hint, `pause` (`yield` on arm64) |
| `SpinLock(@w)`, `SpinUnlock(@w)` | the runtime's lock on the word `w` (0 free, 1 held, 2 held with sleepers), Go's: a waiter spins a little, yields the thread, then sleeps on a futex. A routine that holds one is not preempted |
| `QWait(@q)` | puts the current routine in the one-word queue `q`, first; it does not park |
| `ParkUnlock(@w)` | marks the current routine waiting, releases the lock `w` and parks until something readies it; a wake that comes before the park is kept |
| `QWake1(@q)` | takes the first routine off the one-word queue `q` (the one queued last), or 0 |
| `ReadyG(g)` | makes `g` runnable: it runs next on this thread, when the current routine parks or yields |
| `QWaitBack(@q)`, `QWaitFront(@q)` | put the current routine at the end, or at the front, of the two-word queue `q` |
| `QWakeFirst(@q)` | takes the first routine off the two-word queue `q`, or 0 |
| `QSplice(@dst, @src)` | moves all of the two-word queue `src` to the end of `dst` |
| `WaitPush(@st, old, new, @stack)` | puts `new` in the word `st` when it holds `old`, and then pushes the current routine, marked about to park, on the one-word `stack`: `True`; `False`, and nothing done, when `st` had changed |
| `WaitFront(@st, old, new, @q)` | the same, with the current routine put first in the two-word queue `q` |
| `WaitTake(@stack, @q)` | the first routine of `q`; when `q` is empty it first moves the whole `stack` into it, in the order the routines came; 0 when both are empty |
| `ParkMarked` | parks a routine that `WaitPush` or `WaitFront` marked; returns at once when it was readied meanwhile |
| `Goyield` | puts the current routine at the end of its thread's own queue and runs the next one |
| `CanSpin` | whether a lock's waiter should spin rather than park: other threads are running and this one has nothing else queued (Go's `canSpin`) |
| `Nanotime` | the monotonic clock in nanoseconds, an `Integer` |

A gate that routines wait at until another opens it; `cond` is built
this way, and `mutex` on `WaitPush`, `WaitTake`, `WaitFront` and
`ParkMarked`:

```
type
  TGate = record
    Spin: Integer;            { the lock word }
    Head: Integer;            { the routines waiting: a one-word queue }
    Open: Integer;
  end;

procedure Pass(var G: TGate);
begin
  SpinLock(@G.Spin);
  while G.Open = 0 do
  begin
    QWait(@G.Head);           { queue this routine, }
    ParkUnlock(@G.Spin);      { release the lock and park }
    SpinLock(@G.Spin);
  end;
  SpinUnlock(@G.Spin);
end;

procedure OpenGate(var G: TGate);
var
  w: Integer;
begin
  SpinLock(@G.Spin);
  G.Open := 1;
  w := QWake1(@G.Head);
  while w <> 0 do
  begin
    ReadyG(w);
    w := QWake1(@G.Head);
  end;
  SpinUnlock(@G.Spin);
end;
```

### The debugger inside the executable

`paslangc -debug` builds a program that carries its own debugger. The
compiler adds `uses pasdebug` as if the program had written it, calls
the debugger at the start of every statement with the line, the routine
and the frame, and writes tables of the routines, their variables (name,
place, type) and the lines into the executable; a routine is never put
in place and no variable is kept in a register under the flag, so every
line is where it was written and every variable is in its slot. The
program runs as it is until the environment names a socket:

```
$ paslangc -debug prog.paslang
$ PASLANG_DEBUG=/tmp/prog.sock ./a.out args...      # a path
$ PASLANG_DEBUG=@prog ./a.out args...               # an abstract name
$ pasdbg /tmp/prog.sock                             # the console
```

or the program's first argument asks for the console (below):
`./a.out --debug-mode args...` runs it with a console on its own
terminal.

Then it listens there, one client at a time, and answers a text
protocol: one request a line, a reply of lines that ends in `ok` or
`error: ...`. `pasdbg <socket>` is the console for it (`bin/pasdbg`,
built from `cmd/pasdbg` by `make` and installed with the compiler); `pasdbg <socket> <request>` sends one request and prints
the reply; and any program that opens the socket (an editor, a script,
another paslang program) speaks the same lines. Without `-debug` a
program carries none of it, and without the variable the hooks cost a
call each and nothing listens.

| Request | Reply |
|---|---|
| `routines` | every live routine: `g<n> <state>`, the state `running`, `ready`, `waiting` or `parked`, followed by `at <routine> <file>:<line>` for one the debugger has seen a statement of, or `stopped at <routine> <file>:<line>` for one it stopped |
| `stopped` | the routines stopped by the debugger and where each is |
| `wait [ms]` | waits until a routine stops (5000 ms by default) and says which and where; `error: nothing stopped in <ms> ms` otherwise; a stop already seen through `stopped` and let go on is not reported |
| `where g<n>` | the frames of a stopped routine, its own first: `<depth> <routine> <file>:<line>`, up the frame pointers while the return address is in a routine the tables know |
| `vars g<n> [frame]` | the variables of a frame (0, its own, by default): `name = value`, an integer as a number, a string quoted the Pascal way (`'it''s'#10`), a real with six decimals, a Boolean, a Char, a pointer as `nil` or `$hex`, anything else as `<n bytes>`; a variable a closure holds is read through its box |
| `globals` | the program's global variables the same way |
| `functions` | every routine with its source and first line, and `main` |
| `list <file>:<line> [n]` | n lines (10 by default) of a source of the program from that line, each `<line><tab><text>`; the file by its name in the tables or its base name, read where the program runs |
| `break <line>`, `break <file>:<line>`, `break <routine>` | a break at a line of the program (or of that file) or at every entry of a routine; the reply numbers it |
| `breaks` | the breaks set |
| `delete <n>` | removes one |
| `step g<n>` | lets a stopped routine run to its next statement, in any routine |
| `next g<n>` | to its next statement in the same frame or an outer one (a call runs through) |
| `continue g<n>` | lets it run |
| `stop [g<n>]` | stops one routine, or every routine, at its next statement |
| `run [args...]` | starts the program again from the beginning with those words as its command line, the environment (and the socket) the same, and closes the session |
| `help` | the commands |
| `quit` | ends the session; its breaks go and every stopped routine runs on |

A routine that stops parks on a channel of its own and the others run
on; the socket is served by a routine of the program, so the program
must be scheduling for the debugger to answer: a program spinning in a
loop that calls nothing is reached at its next routine entry or loop
head, as the monitor reaches it (§17). A stopped routine holds whatever
locks it holds. The serving routine is not one the program waits for
when its main routine ends.

`testdata/debug1.paslang` debugs itself under `make check`, on both
machines: its main routine connects to its own socket and drives the
session. Its heart:

```pascal
function Twice(V: Integer): Integer;
begin
  Result := V * 2;
end;

procedure Work(Fin: chan of Integer);
var
  i, x, y: Integer;
  name: string;
  half: Real;
  flag: Boolean;
begin
  name := 'worker';
  flag := False;
  for i := 1 to 3 do
  begin
    x := Twice(i * 5);
    y := x + 1;
    half := x / 4;
    flag := y > 20;
    total := total + y;
  end;
  Send(Fin, 1);
end;

{ The session: its state is local here, so the globals the debugger
  lists are total and greeting alone, the same on every machine. }
procedure Session;
var
  c, v: Integer;
  buf, line: string;
  fin: chan of Integer;

  procedure Ask(const Cmd: string);
  var
    l: string;
  begin
    WriteLn('> ', Cmd);
    TcpWrite(c, Cmd + #10);
    while TcpReadLine(c, buf, l) do
    begin
      WriteLn(l);
      if (l = 'ok') or (Copy(l, 1, 7) = 'error: ') then
        Break;
    end;
  end;

begin
  fin := MakeChan(1);
  c := UnixConnect(ParamStr(1));
  if c < 0 then
  begin
    WriteLn('debug1: no debugger at ', ParamStr(1));
    Halt(1);
  end;
  buf := '';
  TcpReadLine(c, buf, line);
  WriteLn(line);
  Ask('functions');
  Ask('break 29');
  Ask('breaks');
  pas Work(fin);
  Ask('wait');
  Ask('vars g3');
  Ask('where g3');
  Ask('step g3');
  Ask('wait');
  Ask('vars g3');
  Ask('next g3');
  Ask('wait');
  Ask('vars g3');
  Ask('delete 1');
  Ask('break Twice');
  Ask('continue g3');
  Ask('wait');
  Ask('where g3');
  Ask('vars g3 1');
  Ask('delete 2');
  Ask('continue g3');
  v := Recv(fin);
  Ask('globals');
  Ask('quit');
  TcpClose(c);
end;
```

prints

```
paslang debugger: help for the commands
> functions
Twice debug1.paslang:17
Work debug1.paslang:27
Session debug1.paslang:63
Ask debug1.paslang:52
main debug1.paslang:101
ok
> break 29
break 1 at 29
ok
> breaks
break 1 at 29
ok
> wait
stopped g3 at Work debug1.paslang:29
ok
> vars g3
Fin = <8 bytes>
i = 0
x = 0
y = 0
name = 'worker'
half = 0.000000
flag = False
ok
> where g3
0 Work debug1.paslang:29
ok
> step g3
ok
> wait
stopped g3 at Work debug1.paslang:31
ok
> vars g3
Fin = <8 bytes>
i = 1
x = 0
y = 0
name = 'worker'
half = 0.000000
flag = False
ok
> next g3
ok
> wait
stopped g3 at Work debug1.paslang:32
ok
> vars g3
Fin = <8 bytes>
i = 1
x = 10
y = 0
name = 'worker'
half = 0.000000
flag = False
ok
> delete 1
ok
> break Twice
break 2 at Twice
ok
> continue g3
ok
> wait
stopped g3 at Twice debug1.paslang:17
ok
> where g3
0 Twice debug1.paslang:17
1 Work debug1.paslang:31
ok
> vars g3 1
Fin = <8 bytes>
i = 2
x = 10
y = 11
name = 'worker'
half = 2.500000
flag = False
ok
> delete 2
ok
> continue g3
ok
> globals
total = 63
greeting = 'hello'
ok
> quit
ok
total 63
```

### The console

A program compiled with `-debug` takes one of three words as its first
argument, and the words leave its command line before it starts:
`ParamCount` and `ParamStr` see the rest, and the environment is as it
was.

| Word | What the program does |
|---|---|
| `--debug-mode args...` | runs with a console on its terminal, stopped before its first statement |
| `--debug-listen <socket> args...` | serves the socket and waits there, stopped before its first statement, for a console or any client |
| `--debug-attach <socket>` | does not run: it is a console for the program that listens at the socket (waiting up to five seconds for it) |

`pasdbg <socket>` is the same console, for a program started with
`PASLANG_DEBUG` (which runs at once) or `--debug-listen`. The console
speaks the protocol above; the routine that stopped last is the one its
commands act on, so `step` needs no `g<n>`:

```
$ paslangc -debug -o debug2 testdata/debug2.paslang
$ ./debug2 --debug-mode one two
paslang debugger: help for the commands
g1 stopped at main debug2.paslang:26
=>   26    name := 'debug2';
(pasdbg) b Square
break 1 at Square
(pasdbg) c
args 2 one two
env 
g1 stopped at Square debug2.paslang:19
=>   19    r := X * X;
(pasdbg) bt
#0 Square debug2.paslang:19
#1 main debug2.paslang:31
(pasdbg) p X
X = 1
(pasdbg) n
g1 stopped at Square debug2.paslang:20
=>   20    Result := r;
(pasdbg) d 1
break 1 deleted
(pasdbg) c
total 14 of debug2
the program ended
```

| Command | Short | What it does |
|---|---|---|
| `break [line \| file:line \| routine]` | `b` | a break; alone, at the line the routine stopped at |
| `breaks`, `info b` | | the breaks |
| `delete n` | `d` | removes one |
| `continue` | `c` | lets the current routine run until a routine stops or the program ends |
| `step` | `s` | to its next statement, in any routine |
| `next` | `n` | to its next statement in this frame or an outer one |
| `stop` | | every routine at its next statement (waits a second for one) |
| `wait` | | waits for a routine to stop |
| `where` | `bt` | the frames, `#0` its own |
| `frame n` | `f` | the frame `vars` and `print` read |
| `vars`, `locals` | | the frame's variables |
| `globals` | | the program's global variables |
| `print name` | `p` | one variable, of the frame or global |
| `list [line \| file:line \| routine]` | `l` | ten lines around the stop, or around there; again, the next ten |
| `routines` | | every routine and where it is |
| `routine n` | `g` | makes a stopped routine the current one |
| `functions` | | the routines of the program |
| `run [args]` | `r` | starts the program again with those arguments, the breaks kept |
| `quit` | `q` | leaves: under `--debug-mode` the program ends; otherwise it runs on without its breaks |
| `help` | `h` | the commands |

An empty line repeats `continue`, `step`, `next` or `list`. Any other
line, or `raw` and a request, goes to the program's debugger as it is.
While the program runs, Ctrl-C stops every routine at its next
statement; a second Ctrl-C gives the prompt back and the program runs
on, since a routine waiting for input or a lock reaches no statement.
The end of the input (Ctrl-D) is `quit`. Under `--debug-mode` the
program and the console share the terminal, and the console reads it
only while something is stopped: a program that reads its standard
input is debugged with `--debug-listen` in one terminal and
`--debug-attach` (or `pasdbg`) in another. `run` starts the program
again in the same process with the same words, the breaks passed in
`PASLANG_DEBUG_BREAKS`; the console of `--debug-attach` connects again
to the new one. `testdata/debug2.paslang` runs under `make check` with
the commands on standard input, under `--debug-mode` and under
`--debug-listen` with `--debug-attach`, on both machines.

## 18. Limits and differences from other Pascals

- `Byte`, `Word`, `Int32` and the rest keep their width in their values
  and in memory, and a record's fields lie at their natural alignment:
  a binary layout is declared as a record (a field that holds a pointer
  still starts on a word).
- `/` is never integer division.
- A comparison binds before `and`, `or` and `xor`, as in C and Go:
  `(j > 3) and (s <> '')` needs no parentheses, and `x and 4 = 4`, which
  would mix a Boolean with an integer, is a compile error (§3).
- A routine's `var`, `const` and `type` sections and its nested routines
  come in any order, as in FPC; a nested routine sees what is declared
  before it. So do the sections and the routines of a unit's
  implementation: a `const` after a routine is seen by the routines
  below it.
- No `Text`, no `file`, no `file of`. No C foreign function interface.
- No `Random`.
- A static array does not go into an `array of T` parameter, `var`,
  `const` or plain: pass `a[Low(a)..High(a)]`, a slice that shares its
  elements. `var a: array of T` passes a slice by reference, so a
  `SetLength` inside changes the caller's.
- No default value on `var` or `out`, or in a record.
- `cdecl` and `nostackframe` are skipped; `inline` after a routine's
  head puts it in place wherever it is called, whatever its size (§5;
  under `-inline 0` it stays a call). A routine whose body
  is `assembler` or `asm ... end` has that body discarded; the statement
  `asm amd64 (...) ... end` beside `asm arm64 (...) ... end` is assembled
  (inline assembly, §3).
- `packed` is a reserved word that nothing takes: `packed record` is
  `unknown type packed`. A record lies at its fields' natural alignment;
  there is no packed layout.
- `private`, `strict private`, `protected` and `strict protected` are
  held to (1.0.137); `Free` calls `Destroy` when there is one (§7).
- An integer of any width goes into an `array of const` as a
  `vtInteger` of 64 bits (Free Pascal makes an `Int64` a `vtInt64` and a
  `QWord` a `vtQWord`), and a string or a real lies in the `TVarRec`
  itself.
- `TClass` is the compiler's own name for `class of TObject`, a word
  of the language as `TObject` is. A program's class destructors run
  after its last statement, where Free Pascal runs them after the
  output is closed.
- `Close`, like `Send`, is a keyword (a channel's), so no method or
  routine takes the name.
- `Str(x, s)` of a real without a width writes what `Write(x)` writes
  (`2.5`), where Free Pascal writes ` 2.500000000E+00`; `Integer` is 64
  bits, so `Val` into one reads 64 bits, where Free Pascal's `Integer`
  is 32. `Insert` and `Delete` of a slice read it more than once: one
  a call reaches is put in a variable first.
- A one-character literal is a string where a helper's method is called
  on it (`'x'.Twice` is string's helper), where Free Pascal takes it for
  a `Char`. A helper has no constructor.
- `Write` prints no set, as Free Pascal; it prints a `Boolean` as 1 or
  0, where Free Pascal writes TRUE and FALSE. A set's bit n is element
  n whatever its range, so `set of 60..140` takes 32 bytes; a list in
  brackets may mix a constant and an integer variable (`[60, n]`),
  which Free Pascal refuses as a type conflict.
- An exception object is not freed when its handler ends, as Free
  Pascal frees it: the collector takes it back when nothing points to
  it, so a handler may keep it or raise it again with `raise E`.
  `raise;` outside an `except` part raises no object, where Free
  Pascal refuses it (§9).
- A value parameter is the routine's own copy: a change the routine
  makes to the caller's variable some other way (a global passed in,
  through a pointer, through a call) never shows in it (1.0.136; a
  parameter the routine only read followed such a change).
- A real goes into an integer only through `Trunc` or `Round`, also as
  an index, a `for` limit, an `Inc` step of an integer, a `SetLength`
  length, a `case` selector or a condition (1.0.136; its bits were
  taken).
- A hexadecimal literal is the word's bit pattern, so `$8000000000000000`
  and above are negative; a decimal literal above 2^63 - 1 is a compile
  error, and `-9223372036854775808` is written as such.
- A program's variable or routine may not take the name of a variable of
  a unit it uses: `duplicate identifier Counter (a variable of unit uv)`.
- When two units a program uses have a name in common, the later one in
  `uses` hides the earlier one's, as in Free Pascal (a routine of the
  same parameters, a constant, a variable, a type that is another); a
  unit's name reaches its own names, hidden or not: `ua.Twice`,
  `ua.Count`, `var b: ua.TBox` (1.1.13).
- A map key cannot be a record, a real, a slice, a map or a method value.
- A map is not safe for concurrent writers; the runtime stops the
  program when it catches that.
- A bare `Syscall(...)` statement makes the call and drops its answer
  (1.0.136; it ran whatever call a register happened to hold).
- A routine takes at most 32 parameters. `pas` passes values, so it
  does not start a routine with a `var` parameter.
- `Move(a, b, n)` copies between the two variables named; write
  `Move(p^, q^, n)` to copy through pointers.
- `send` is a keyword, so a routine cannot be named `Send`; the builtin
  `Send(c, v)` is the channel send.
- When the main routine ends, the program waits for every routine it
  started; when all of them are asleep and nothing can wake one, it
  stops with `paslang: all routines are asleep: deadlock` (§10).
- The target is GNU/Linux only, kernel 6.13 or newer, amd64 and arm64.

## 19. Reserved words

The lexer reserves these words, in any case of letters; none can name
a variable, a type or a routine, and one where a name goes says so:
`sleep is a reserved word, not a name at 5:3`.

The Pascal set: `and array as asm assembler begin case class const
constructor destructor div do downto else end except exit false
finally for function generic halt if implementation in inherited
initialization finalization interface is mod nil not object of or out
procedure program property raise read record repeat set shl shr
specialize string then to true try type unit until uses var virtual
while with xor`, and `break continue`.

Names that other Pascals predeclare and paslang reserves: `integer
boolean new write writeln readln`.

The paslang additions: `pas chan makechan send recv close select map
lock once mutex rwmutex waitgroup cond sleep safe tree heap store`, and
`package contains` (Delphi's, §2).

Every predefined name is reserved as well (1.0.138; from 1.0.131 to
1.0.137 only the words added since 1.0.131 were, and the older ones could
be declared and hid the builtin, at times in silence and wrongly: a
`function Length` was ignored). Each still means what it means only in
its place:

- the bit operators `nand nor xnor andnot sar rol ror`;
- the declaration words `forward overload override abstract public
  private published protected strict operator inline cdecl nostackframe`,
  and `packed`, which has no place at all: it is refused everywhere (§18);
- the slice words `Append` and `Cap`;
- the ordinal, string, slice, map and memory words `Ord Chr Succ Pred Low
  High Odd SizeOf Length Copy Delete Clear TryGet Default Assigned
  SetLength Inc Dec GetMem FreeMem Move FillChar View MemBase MemSize
  MemEnd`, and Pascal's string words `Pos Insert Concat UpCase LowerCase
  StringOfChar Str Val` (1.1.10);
- the tree, heap and store words (§11): `Rank KeyAt PopLow PopHigh Split
  Join Include Exclude Push Pop StoreOpen StorePut StoreGet StoreDelete
  StoreSync StoreClose StoreAbandon`, and the types `tree`, `heap` and
  `store` are keywords;
- the hash words (§13): `Hex Md5 Sha1 Sha224 Sha256 Sha384 Sha512
  Sha3_224 Sha3_256 Sha3_384 Sha3_512 HmacMd5 HmacSha1 HmacSha224
  HmacSha256 HmacSha384 HmacSha512 Crc32 Crc32c Adler32 Fnv1a32 Fnv1a64
  Murmur3 SipHash MerkleRoot MerkleProof MerkleCheck` (the table in §13,
  The algorithms, says what each computes and what it is for);
- the calculation set (§14): `Abs Sqr Sqrt Trunc Round Int Frac Floor
  Ceil Min Max Pi Exp Ln LnXP1 Log10 Log2 LogN Power Hypot Ldexp Poly
  Sin Cos Tan Cot Sec Csc ArcSin ArcCos ArcTan ArcTan2 ArcCot ArcSec
  ArcCsc Sinh Cosh Tanh ArcSinh ArcCosh ArcTanh IsNan IsInfinite`;
- the program's, the debugger's and the runtime's words `ParamStr
  ParamCount SrcLine ErrOutput Syscall Amd64 GcCollect HeapStat HeapCheck
  HeapMaskOf DumpLocals Breakpoint BreakCount BreakPC ContinueBreak
  XxHash32 XxHash64 XxHash3 Nanotime Pause GId GCount Gosched Goyield
  ReadyG CanSpin SpinLock SpinUnlock ParkMarked ParkUnlock QSplice QWait
  QWaitBack QWaitFront QWake1 QWakeFirst WaitFd WaitIo WaitMs WaitFront
  WaitPush WaitTake`;
- the network words `NetListen NetAccept NetConnect NetClose NetRead
  NetWrite NetPort` and the RTTI words `PropKind GetPropInt GetPropStr
  SetPropInt SetPropStr SetPropMeth CallProp`;
- Carry's: `Carry CarryOn CarryOff CarryFlip`;
- the rotations and shifts: `RotateLeft RotateRight RotateLeftToCarry
  RotateRightToCarry RotateLeftThroughCarry RotateRightThroughCarry
  ShiftLeft ShiftRight ShiftRightSigned ShiftLeftToCarry
  ShiftRightToCarry ShiftRightSignedToCarry FunnelLeft FunnelRight`;
- the bit words: `IsBitSet SetBit ToggleBit GetBits SetBits PopCount
  LeadingZeros TrailingZeros ReverseBits ByteSwap AtomicSetBit
  AtomicClearBit`;
- the wide arithmetic: `MulHi MulHiS Mul128 DivMod128 AddCarry SubBorrow
  AddOverflow SubOverflow MulOverflow AddSat SubSat`;
- the memory words: `LoadFence StoreFence FullFence Prefetch
  PrefetchWrite CacheLine StoreNT AtomicLoad AtomicStore AtomicExchange
  AtomicAnd AtomicOr AtomicXor AtomicAdd AtomicCas LoadBE16 LoadBE32
  LoadBE64 LoadLE16 LoadLE32 LoadLE64 StoreBE16 StoreBE32 StoreBE64
  StoreLE16 StoreLE32 StoreLE64`;
- the processor's: `CycleCount CycleFreq CpuHas CpuFeatures`;
- the vectors: `V128`, `V256` and every vector word of §3 (`VAdd8` to
  `VSum64`, `VShrS64` included);
- the predefined types and their pointers: `Byte UInt8 Int8 ShortInt
  Word UInt16 Int16 SmallInt UInt32 LongWord DWord Int32 Int64 LongInt
  SizeInt NativeInt PtrInt Cardinal QWord UInt64 Rune Char AnsiChar Real
  Double Single Quad Pointer PChar` and `PByte PUInt8 PInt8 PShortInt
  PWord PUInt16 PInt16 PSmallInt PDWord PLongWord PUInt32 PInt32
  PInteger PInt64 PSingle PDouble PQuad PBoolean PPointer`;
- what the core units export (§15), predefined in every program and
  unit: `Goid NumGoroutine Yield PasReadLn`, the sync types `TPasMutex
  TPasRWMutex TPasWaitGroup TPasCond TPasOnce` with their `PasMutexLock`
  … `PasOnceDone` routines, pasfmt's `PasFmtReal` … `PasFmtQuad`,
  pashash's `PasHex PasMd5 PasSha1Cpu` … `PasMerkleCheckBase` and
  pastree's `PasTreeNew` … `PasStoreAbandon`, and pasobject's `TObject`
  with `PasClassName` … `PasUncaught`, and the compiler's `TClass`
  (`class of TObject`), `TVarRec` and its kinds `vtInteger` …
  `vtQuad`. A core unit declares its
  own exports; nothing else may, and a unit's implementation types are
  its own (an importer cannot name them, and they are not reserved).

A variable, a constant, a type, a routine, a parameter, a field, a
method, a property or an enumeration member of one of these names is a
compile error that names it, at the name: `Length is a reserved word,
not a name at 5:3`. A unit's `.pi` is not checked for these names when
it loads. The compiler loads only a `.pi` of the format it writes,
`PASLANGI15` since 1.1.4, and refuses an older one: `build/geometry.pi
was compiled by a paslang older than 1.1.4; compile geometry again`.

`safe` before `program`, `unit`, `procedure`, `function`,
`constructor` or `destructor` (a method's declaration in its class
too) forbids raw pointer work in that code: pointer arithmetic, `Inc`
and `Dec` of a pointer, `p[i]`, views (`PT(q)` of another pointer
type, `^T(q)`, `T(q^)`, `TRec(q)`), `View(p, n)`, `Pointer(n)` and `p^`
of an untyped `Pointer`. `New`, `p^` of a typed pointer, `@x`, `nil`, comparisons,
arrays, strings, classes and slices stay. A routine declared inside a
safe one is safe too; a safe unit's `.pi` says so. It costs nothing at
run time.

`WriteLn`, `Write`, `ReadLn`, `New`, `Sleep`, `MakeChan`, `Send`,
`Recv` and `Close` are keywords (above) and are never names.

## 20. Command reference

```
paslangc [options] file.paslang
```

| Option | Meaning |
|--------|---------|
| `-o <path>` | output file; a program defaults to `a.out`, a unit to `build/<name>` (`build/a64/<name>` with `-target arm64`) |
| `-c` | compile and assemble only, no link |
| `-checkptr` | check every pointer step and access against its object while the program runs (§6) |
| `-inline <n>` | inline by measure (§5): a plain routine of the unit whose body counts `n` statements and expression nodes or fewer goes in place where it is called; a routine declared `inline` goes in whatever its size; `-inline 0` keeps one copy of every routine and every loop; 40 by default |
| `-inline-trace` | say on the error output why each routine of the unit stays a call |
| `-debug` | the debugger inside the executable (§17): `uses pasdebug`, a call of the debugger at every statement, the tables of the routines, variables and lines; `-inline 0` and no variable in a register; run with `PASLANG_DEBUG=<socket>` and speak to it with `pasdbg <socket>` |
| `-Fu <dir>` | a directory of compiled units, repeatable |
| `-install <dir>` | compile a package and install its units there |
| `-target amd64`, `-target intel64`, `-target arm64` | the machine to emit for; on amd64 the arm64 output is cross-assembled with `aarch64-linux-gnu-as` and `-ld`, and an arm64 machine uses its own `as` and `ld` |
| `-cpu <set>` | the processor the code is compiled for: `base` (SSE2; `fp` and `asimd` on arm64, runs anywhere), `native` (what the machine compiling has; the default when the target is this machine), `max` (every feature the target names), the x86-64 psABI levels `v2`, `v3`, `v4`, the arm64 steps `v8.1`, `v8.2`, `crypto`, or names of `CpuHas` joined by `+` (`-cpu v3+sha+pclmul`); `base` is the default when compiling across. The compiler chooses the instructions and the bodies of the words by it and the program tests nothing at run time; on a processor without them it dies with an illegal instruction |
| `--lex` | print the first 41 tokens of the source (number, kind, text, line:column) and stop |
| `-h` | the version banner and the index of the built-in help |
| `--help`, `--help <topic>` | the banner and the built-in help: every section, or one of `flags`, `types`, `lang`, `runtime`, `lib`, `limits`, `examples`; `all` is every section, `index` (or `short`) the index, and an unknown topic says so and prints the index |
| `-v`, `--version` | the version banner |

The program is linked statically, with only the routines it reaches:
every routine sits in a section of its own and the linker drops the
ones nothing names (1.1.1), so a program that uses no tree, hash or
map carries none of their code (`hello` is about 114 KB of code on
amd64 and 154 on arm64, where it was 374).

A missing file, a syntax error or a failed assemble or link prints a
message on standard error and exits with a non-zero status. A compile
error names its file, and its line and column when it has them:
`paslangc: two pointers do not add at 7:13 in src/demo.paslang`.

The whole source tree is checked with `make check`: the golden programs
in `testdata/`, the examples of this manual, the network tests, the
stage-2 rebuild of the compiler by itself, and the arm64 build under
qemu.

---

Copyright (C) 2026 Germán Luis Aracil Boned.

Permission is granted to copy, distribute and/or modify this document
under the terms of the GNU Free Documentation License, Version 1.3 or
any later version published by the Free Software Foundation; with no
Invariant Sections, no Front-Cover Texts, and no Back-Cover Texts. A
copy of the license is included in the file COPYING.DOC.
