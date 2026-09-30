# Types — modern Pascal, Go-shaped values

Syntax stays Pascal. **Representations are modern** (Go-minded): no
255-character strings, no hidden headers that break layout, no 16-bit
`Integer`. Documented here so the compiler does not silently revive
ShortString.

## Principles

1. A type’s size and layout are explicit and 64-bit native.
2. Default `string` is **unbounded** (memory is the only limit), like Go.
3. What looks like a Pascal `record` has C-compatible field layout
   (SysV amd64 / AAPCS64).
4. Hidden refcounts, length bytes *before* the pointer, and 1-based
   magic are not the default ABI.
5. Pascal spellings: `string`, `array of T`, `Integer`, `Boolean`.

## Integers and ordinals

| Name | Size (bits) | Notes |
|---|---|---|
| **`Integer`** | **64** | Machine signed int (Go `int` on amd64/arm64). Not 16- or 32-bit. |
| `Cardinal` `LongInt` `Int64` `UInt64` `QWord` `SizeInt` `NativeInt` `PtrInt` | 64 | the same signed 8-byte `Integer`: there is no unsigned 64-bit type, so `High(Cardinal)` is 9223372036854775807 and `Cardinal(0) - 1` is -1 |
| `Byte` `UInt8` · `Int8` `ShortInt` · `Word` `UInt16` · `Int16` `SmallInt` · `UInt32` `LongWord` `DWord` · `Int32` | **8, 16, 32** | six types of their own since 1.0.87 (P99), the names between dots one type: overloads tell them apart. Their values keep their width since 1.0.89: the indicated type decides the width of the work (`i := b + 1` is 256, `b := b + 1` wraps to 0), widening is implicit, narrowing needs a conversion, a constant that does not fit is a compile error. Since 1.0.91 they take their width in memory: 1, 2 and 4 bytes in arrays, fields and through pointers (a local or a global keeps a word's slot). |
| `Boolean` | 64 | `False`/`True`, one word. Only a Boolean goes into one (`t := i` is an error since 1.0.116: it stored 5); `Boolean(x)` is `x <> 0`. In integer arithmetic a Boolean is its `Ord`, as a `Char` is its code; `and`, `or` and `xor` take two Booleans or two integers. |
| `Char` `AnsiChar` | 8 | UTF-8 **byte** (Go `byte`), a type of its own (`Ord(c)` is its code). For a Unicode scalar use `Rune`. |
| `Rune` | 64 | Unicode code point in a machine word (same storage as `Integer`). |

`LongInt` is an alias of `Integer` (64). We do not keep a 32-bit
`LongInt` trap from old Pascal. A load through a pointer, of a field or
of an element reads the size of the type it has there
(`TEmitter.LoadSize`, `testdata/pchar.paslang`, `narrowmem.paslang`).

### Narrow integers in detail (P99, 1.0.87–1.0.92)

- **The indicated type decides.** The context fixes the width of the
  work: a conversion `T(e)`, the target of `v := e` (also `a[i]`, `r.f`,
  `Result`, `Exit`), a value parameter, a `for` counter and its limits,
  a `case` selector. With `b: Byte = 255`, `i := b + 1` and
  `Integer(b + 1)` are 256, `b := b + 1` is 0.
- **No context:** the operands' width; a constant with no type adapts to
  the other operand, and two types join in the wider. `WriteLn(b + 1)`
  is 0. A comparison compares both sides at their common width.
- **Signed and unsigned** join in the signed type that holds both:
  `Byte` + `Int8` → `Int16`, `Word` + `Int16` → `Int32`, `UInt32` +
  `Int32` → `Integer`. A signed type into a wider unsigned one
  (`Int8` → `Word`) is an error without `Word(x)`: −1 is no `Word`.
- **A conversion is a boundary** (1.0.116): the work inside `T(e)` is
  done in `T`, and a conversion around it does not reach in:
  `Integer(Byte(i))` is 44 for 300 and `Integer(Byte(b + 1))` is 0 for
  255 (they gave 300 and 256). `Ord` of a constant is a constant with
  no type, as a literal is: `b := Ord('X')` compiles.
- **Widening** is implicit (zeros for unsigned, the sign for signed);
  **narrowing** needs a conversion, which keeps the low bits
  (`Byte(300)` of a variable is 44): `b := i` and `b := b + i` are
  errors, `b := b + 1` is not.
- **Constants that do not fit** are compile errors: `b := 300`,
  `Byte(300)`, `Byte(-1)`, case labels, typed constants, defaults,
  arguments. So is a constant expression that leaves `Int64`.
- **Arithmetic:** `shr` keeps the sign in `Int8`, `Int16` and `Int32`
  and is logical in the unsigned types and in `Integer` (pasrand,
  pasmap and xxHash rely on that). `sar` (1.0.116) brings in copies of
  the top bit of the width in every type, so `Byte($C8) sar 1` is 228;
  `rol` and `ror` turn within the width. `shl`, `shr` and `sar` count
  modulo 64, `rol` and `ror` modulo the width, the same on both
  machines. The width is the indicated type's: `i := b rol 1` turns 64
  bits, `Byte(b rol 1)` turns the byte. `not` of a constant with no type
  is taken in the width it is used in: `b and not 2` clears bit 1 of a
  `Byte`, and `b := not 2` is 253. `div`, `mod`, `Abs`, `Min` and `Max`
  work on extended values and wrap to the width; `Inc` and `Dec` wrap.
- **Bit words** (1.0.117): `IsBitSet`, `SetBit`, `ToggleBit`,
  `GetBits`, `SetBits`, `PopCount`, `LeadingZeros`, `TrailingZeros`,
  `ReverseBits`, `ByteSwap`, `RotateLeft` and `RotateRight` work in the
  width of their operand's type, whatever the context (a `Char` has 8
  bits); a bit number out of the width is a compile error when constant
  and stops the program when it varies. Since 1.0.118 they take any
  variable: a real, a Boolean, an enumeration, a pointer or a set as its
  bits, and the bytes of a record, an array, a `Quad`, an object, a
  string (made its own before a write) or a slice, bit n being bit n
  mod 8 of byte n div 8; `AtomicSetBit` and `AtomicClearBit` too.
  `ReverseBits` and `ByteSwap` take a value of up to 8 bytes; the
  rotations did too until 1.0.130.
- **Views** (1.0.119): `x as T` is the bytes of `x` seen as `T`, not
  converted, readable and writable (`(d as UInt64) xor= Sign`, `(r as
  TPair).Hi := 7`); `T(x)` stays the conversion of the value and `obj as
  TClass` the checked cast. A view bigger than its variable is a compile
  error, past a string's or a slice's bytes a stop at run time.
- **Closures** (1.0.134): `function(x: Integer): Integer begin ... end`
  and `procedure ... begin ... end` are values that keep the variables
  around them by reference, outliving the routine; `@Nested` and `pas
  Nested` too; a loop counter a closure keeps is each pass's own.
  `for x in` walks a slice or a static array.
- **pas takes any call** (1.0.135): `pas F(a, b, c)` with any number
  of arguments of any type, `pas f(a)` of a routine value, `pas obj.M(a)`,
  `pas m(a)` of a method value and `pas procedure begin ... end`; the
  arguments are worked out when `pas` runs, as in Go.
  `function ... of object` is a method value with its signature, and
  an interface's call takes strings, records, reals and more than five
  arguments.
- **Routine values are 16 bytes** (1.0.133): the code and an
  environment, nil for `@Routine`, a closure's captured variables from
  1.0.134. `SizeOf(f)` is 16; `Assigned(f)` is `f <> nil`.
- **Slices grow with `Append`** (1.0.132): `s := Append(s, a, b)` or
  `Append(s, u)` for a slice of the same type, `Cap(s)`, and a list in
  brackets where a slice goes, `[1, 2, 3]`, is a new slice. Growth is in
  place only from the block's frontier, so no other slice of the block
  sees the new elements.
- **Carry, rotations and shifts** (1.0.129): each routine has a Carry
  bit of its own (`Carry`, `Carry := b`, `CarryOn`, `CarryOff`,
  `CarryFlip`), 0 when it starts and kept across calls.
  `RotateLeftToCarry`/`RotateRightToCarry` (circular, the last bit
  copied to Carry), `RotateLeftThroughCarry`/`RotateRightThroughCarry`
  (a ring of the width + 1 bits), `ShiftLeft`, `ShiftRight`,
  `ShiftRightSigned` and their `ToCarry` forms, and `FunnelLeft`/
  `FunnelRight(hi, lo, n)` work in the width of their operand's type (a
  constant with no type: of where it goes); a count of 0 or less changes
  nothing and one past the width is exact. `RotateLeft` and
  `RotateRight` are `rol` and `ror`: a negative count turns the other
  way, in a register and on a whole value alike (1.0.147). `rol`,
  `ror`, `shl`, `shr` and `sar` never touch Carry. Since 1.0.130 they, `RotateLeft` and
  `RotateRight` take any value whole: a record, an array, a `Quad`, a
  vector, a string's characters, a slice's elements (none that holds
  strings, pointers or objects).
- **`for` with a narrow counter** stops on its limit: `for b := 0 to
  255` ends, and the counter holds the limit afterwards.
- **`var` parameters** take their exact type (the names of one row are
  one type). Overloads rank: the same type, then an integer that widens
  without loss (the nearer width, the same sign first), then an integer
  for a real; a tie is ambiguous.
- `SizeOf` gives 1, 2 or 4; `High(T)` and `Low(T)` are constants of the
  type; RTTI reads and writes a published narrow property at its width
  and sign; `AtomicAdd` and `AtomicCas` refuse a narrow target.
- **Storage:** 1, 2 or 4 bytes in arrays, fields and through pointers;
  a local or a global keeps an 8-byte slot, read and written at its
  width; maps and channels hold the value in a normalized 8-byte word.
  `examples/narrow.paslang` is the manual's walk through these rules.

## Real numbers

`Real` and `Double` are one type: IEEE binary64, 8 bytes. `Single` is
IEEE binary32, 4 bytes, worked out in 32 bits (`addss`, `fadd s`), as
Go's `float32` (1.0.104; before it was binary64 under another name).
The rules are the integers' (P99):

- Single with Single stays Single; Single with Double is worked out
  in Double, the Single widening exactly.
- A constant with no type (`0.1`, `Pi`, `const E = 2.5`) takes the
  type it meets, rounded once from its digits to the nearest (a tie to
  even): `s := 0.1` then `s = 0.1` is true. One that does not fit
  `Single` is a compile error.
- The context gives the width: `d := s * t` and `Double(s * t)` work in
  Double, `s := s * t` in Single; `WriteLn(s * t)` has no context and
  works in Single.
- Single to Double is implicit and exact. Double to Single takes
  `Single(x)`, which rounds to the nearest; `s := d` is an error.
- `Abs`, `Sqr`, `Sqrt`, `Min` and `Max` of Singles are Singles; the
  other routines take a Double, and a Single widens for them.

`Quad` is IEEE binary128 (P103, 1.0.114): 16 bytes, 113 bits of
significand, worked out in software by the core unit `pasquad`, so the
same bits on both machines ([QUAD.md](QUAD.md)). The rules are the
integers' and the other reals':

- Everything widens to a `Quad` exactly: an `Integer`, a `Double`, a
  `Single`; an operation with a `Quad` side works in `Quad`.
- The context gives the width: `q := d * d` and `Quad(d * d)` work in
  `Quad`. A constant with no type is read from its digits as the nearest
  binary128; `Pi` has all 113 bits. One past the range is an error.
- `Double(q)` and `Single(q)` round once to the nearest; `d := q` is an
  error. `Trunc`, `Round`, `Floor` and `Ceil` give an `Integer` and stop
  on a value no `Integer` holds.
- `+ - * /`, the comparisons (a NaN compares with nothing), unary minus,
  `Abs`, `Sqr`, `Sqrt` (below 0 it stops), `Int`, `Frac`, `Min`, `Max`,
  `Inc`, `Dec` and `WriteLn` (exact, `q:w:d`) take a `Quad`; the other
  routines of the calculation set refuse it ("write Double(x)").
- A `Quad` value travels as two words in `rax:rdx` (`x0:x2`), no pointer
  in either; a parameter goes by address, as a string does.
- A named constant is folded in binary128 as well as in `Double` (1.0.115):
  `const Third = 1 / 3` gives a `Quad` all 113 bits, and a unit's `.pi`
  carries those words (`CONST name bits r lo hi`). A typed constant and a
  default value can be `Quad`.
- A `Quad` lies on 16 bytes in a record and as a global, as C's
  `_Float128`: `record B: Byte; Q: Quad end` is 32 bytes. In a frame or a
  large heap block it may lie on 8, which the arithmetic does not mind.
- DWARF names a `Quad` local's type `_Float128`, the name gdb reads as
  binary128 on both machines.
- Not in `Quad`: the trigonometric, logarithmic and exponential routines;
  they take `Double(q)`.

`V128` and `V256` (P106, 1.0.125) are 16 and 32 bytes of vector lanes:
builtin types 15 and 16 (`.pi` `PASLANGI11`), records of no fields to
the rest of the language, aligned on 16. They have no arithmetic of
their own: the vector words (`VAdd8`, `VCmpGtU16`, `VSelect`, …, MANUAL
"Vectors") and the logic operators work them lane by lane, and `x as
T` reads a lane. A V256 never goes into a V128 or back: a view says
which bytes. On amd64 a V256 word is written in ymm when the processor
chosen at compile time has AVX2 (`-cpu`, the default `native` on the
same machine) and as two SSE2 halves when it has not (`-cpu base`);
nothing is tested at run time (`KERNELS.md`).

`Double(n)` is always the conversion: `Double` is reserved, so no
routine takes the name. `Real(n)` converts an integer.
A real value is passed and returned in the integer registers (`rax` /
`x0`, a Single in the low 32 bits); arithmetic moves those bits into
`xmm` / `d` or `s`.

`/` is real division, including when both operands are integers.
`div` and `mod` stay integer. `+`, `-`, and `*` are real when either
operand is real. Comparisons of a real and an integer promote the
integer. A real never goes where an integer, a `Boolean` or an enum goes, and
`Ord` does not take one: `Trunc` or `Round` says how it rounds (the bits went
in as they were before 1.0.103). `Abs`, `Sqr`, `Sqrt`, `Sin`, `Cos`, `Trunc`, and `Round` accept a
real. `Sqrt`, `Sin`, `Cos`, `Ln`, `Exp`, `Frac`, and `Int` also accept an
integer and return a real. `Sqrt` below 0 stops the program (`Sqrt(-0)`
is -0, a NaN stays a NaN). `Ln` of a non-positive value stops the
program. Every such stop names its line (1.0.112). `Trunc`, `Round`,
`Floor` and `Ceil` of a NaN, an infinity or a value out of `Integer`'s
range stop with `real out of integer range at line N`, the same on both
machines (`testdata/realint.paslang`, `fatal/rr*`). `Sin` and
`Cos` take radians. `Int` truncates toward zero and returns a real.
`Frac` is the signed remainder. `ArcTan`, `ArcSin`, and `ArcCos` return radians. `ArcSin` and
`ArcCos` stop outside `-1..1`. `Power(base, exponent)` returns a real. `Log10` and `Log2` are the
base-10 and base-2 logarithms. `Hypot(x, y)` is the hypotenuse.
The Math family completes the calculation set: `Tan`, `Cot`, `Sec`, `Csc`,
`ArcTan2(y, x)` (four quadrants, `ArcTan2(0,0)` is 0), `ArcCot` (`Pi/2 - ArcTan`),
`ArcSec`/`ArcCsc` (stop outside `|x| >= 1`), `Sinh`, `Cosh`, `Tanh` (saturates at
`±1` past `|x| >= 20`), `ArcSinh` (odd: negative `x` is computed through `-x`),
`ArcCosh` (stops below 1), `ArcTanh` (stops outside `-1..1`), `LnXP1` (stops when
`1+x` is non-positive), `LogN(base, x)` (stops on non-positive base or `x`, or
base 1), `Ldexp(x, p)` with an `Integer` exponent, `Poly(x, a)` over an
`array of Real` by Horner (`a[0]` is the constant term), `Floor` and `Ceil`
(return `Integer`, toward −∞ / +∞), `Min`/`Max` (two integers or two reals),
`Odd`, `IsNan`, `IsInfinite`, and `Pi` (bare or `Pi()`).
`XxHash32(s)`, `XxHash64(s)` and `XxHash3(s)` (XXH3, 64 bits) hash the
bytes of a string (optional second `Integer` seed); `XxHash64` and
`XxHash3` return the 64 bits in an `Integer`, so a hash with the top bit
set prints negative. The other hash words (`Sha256`, `Crc32c`, …) are the
core unit `pashash`'s (1.0.144).
These calls need parentheses; their names are reserved, so no variable
takes one. `Round` uses round-to-nearest, ties to even. `WriteLn` of a real prints a
sign, the integer part, and up to six fractional digits with trailing
zeros removed, keeping one digit (`4.0`, `2.5`, `-1.5`).
`testdata/reals.paslang` covers GNU/Linux amd64 and arm64.

An `Integer` local or spilled `Integer` parameter is one frame slot.
DWARF names it with `DW_OP_fbreg` and the byte offset from `rbp`
(amd64) or `x29` (arm64). `testdata/dwarfloc.paslang`. A narrow local
has a base type of its width and sign (1.0.92, `dwarfnarrow`), and a
`Single` or `Double` local a float of 4 or 8 bytes (1.0.104,
`dwarfreal`).

Enumerations and subranges stay Pascal; each is an 8-byte integer.

## Sets

`set of T` is one 8-byte word, a bitset: bit n is the element whose
ordinal is n. `T` is a `Boolean`, an enumeration or a subrange whose
values lie in 0..63 (`set of 0..63`, `set of TDay`); a range past it is
`set too large`, and `set of Byte`, `set of Char` or `set of Integer` is
refused (`set of ordinal type`), since their values pass 63. `[1, 3..5]`
is a set value and `[]` the empty one; `+` is the union, `*` the
intersection, `-` the difference, `=` and `<>` compare, `x in s` tests
one element, and `for x in s do` walks the members from the lowest. A
set goes only where a set goes: `i := [1, 2]` is a compile error
(1.0.136; it stored the bitmask, 6). The bit words see its 64 bits
(`PopCount(s)` counts the members). `Include` and `Exclude` are the
tree's words (below) and refused on a set: `s := s + [x]` and
`s := s - [x]` are the same thing.

## `string` — not ShortString

Classic Pascal `string` is `string[255]`: one length byte, max 255
characters. That is **not** our default.

**Default `string` (Go `string`):**

- Representation: **pointer + length** (two machine words, 16 bytes).
- Content: **UTF-8** bytes, which the program may write (`s[i] := c`,
  1.0.82). Characters are shared by copy on write: the byte just before
  them in their block says whether another string shares them (bit 0),
  so an assignment, a parameter or a field shares them for nothing, and
  the first write through any holder copies them for that holder alone
  (`rt_strunique`; a literal's characters are always shared).
- Length: `Length(s)` is the byte count; **no 255 cap**. Limited by
  address space / allocation.
- Assignment and argument passing **copy the fat pointer**, not the
  bytes. Concatenation (`s + t` or `WriteLn` pieces) allocates a new
  buffer.
- Indexing `s[i]` is a **byte** (`Char`), 1-based to stay Pascal
  (`s[1]` is the first byte); `Low(s)` is 1 and `High(s)` is
  `Length(s)` (1.0.136; `Low` gave 0). Out of range stops the program with
  `paslang: index I out of range [1..N]` and the line (P87).
  `WriteLn(c)` writes that byte, the character itself, as every Pascal
  does; `Ord(c)` is the code. Go prints a `byte` as a number only
  because it has no character type; that is not one of the parts we
  take. Writing `s[i]` for every `i` reproduces the string, multibyte
  characters included. `Rune` stays an integer and prints as one.
  `testdata/wrchar.paslang`.
  A `Char` where a `string` is wanted is converted, as in every Pascal:
  `s := c`, `Take(c)` and `Take(#10)` all pass a one-byte string. The
  parser wraps it in `rt_chstr`, which allocates that byte, so the
  string outlives the frame that made it. Before, an argument passed
  the raw byte where a descriptor address belonged and the callee read
  through it.
  The load is one byte (`movzbq` / `ldrb`) even if `Ord(s[i])` has
  widened the expression type to `Integer`. An 8-byte load of `s[1]`
  in `'20'` pulls `'2'` and `'0'` together; a single digit happens to
  work because `rt_alloc` zeros the rest of the word.
- `for r in s do` walks **Unicode scalars**, not bytes. `r` is a
  `Rune` (or any 8-byte ordinal). A valid UTF-8 sequence is one
  iteration and consumes 1 to 4 bytes. An invalid lead, an overlong
  sequence, or a surrogate yields U+FFFD (65533) and consumes that
  one byte; decoding then resumes at the next byte. `s[i]` stays a
  1-based byte. `testdata/runes.paslang`.

**There is no fixed-length string.** `string[n]` is a syntax error; a
wire layout is a record or an `array[0..n - 1] of Char`, and nothing
truncates a `string` to 255.

## Dynamic arrays — slices

Classic `array of T` is often a pointer to a heap block with a hidden
refcount and length *before* the first element. That surprises and
breaks C-shaped layout.

**Default `array of T` (Go slice):**

- Representation: **pointer, length, capacity** (three words).
- `Length` reads the length word. `SetLength` grows and may reallocate.
  After its elements a buffer keeps its frontier, the length the
  furthest slice of it reached. A shrink changes the length alone; a grow
  stays in the buffer only from the frontier, where the elements are
  still zero and no other slice sees them, else it takes a new buffer.
  So the elements a grow adds are always zero and another slice of the
  buffer never changes under it, as with FPC's `SetLength`, while a
  slice grown one element at a time stays in place (1.0.88; before, a
  grow within the capacity showed what a shrink or another slice had
  left there).
- Indexing is **0-based** (`a[0]` is the first element). Strings stay
  1-based. Every index is checked against the length (P87):
  `paslang: index I out of range [0..N-1]`, before a write writes.
- Static `array[Low..High] of T` stays Pascal (fixed bounds, no header).
- `d[i..j]` (1.0.109) is elements `i` to `j` of a slice or a static
  array as a slice sharing them: pointer `@d[i]`, length `j - i + 1`,
  capacity 0, so `SetLength` of it copies. The bounds are checked where
  it is made (`i` in `0..Length`, `j + 1` in `i..Length`). `s[i..j]` of
  a string is a copy (strings share by copy on write).
- `View(p, n)` (1.0.109) is the `n` elements at `p` as a slice
  (`array of T` for a `^T`, bytes for a `Pointer`), capacity 0, its
  index checked; a length below 0 stops the program.

## Records and pointers

- `record` … `end`: C field order and alignment. No hidden vptr.
  A trailing `case` overlays the variants at one offset. A tag
  `case Kind: Integer of` is a real field before that overlay.
  Each field lies at its natural alignment (1.0.91): a one-byte field
  anywhere, a two-byte one on two, a four-byte one on four, and a field
  that holds a pointer on a word; the size rounds up to the most aligned
  field, so `record B: Byte; W: Word; I: Int32 end` is 8 bytes
  (`testdata/narrowmem.paslang`, `recalign.paslang`, `variant.paslang`).
- `operator` defines `+ - * / div mod = <> < <= > >=` as a function.
  Integer, string, and set operations stay builtin when no operator is
  declared. A record without one is an error. `testdata/opadd.paslang`,
  `testdata/opmore.paslang`.
- `property S: string read GetS write SetS` passes the string as a
  descriptor. `property Item[I: Integer]: Integer` passes the indexes
  and then the value. `testdata/props.paslang`, `testdata/pindex.paslang`.
- `^T`: one machine word; the pointers are the next section.
- A class value is one pointer to an object in the collected heap,
  whose first word points to the class's method table (VMT). A class
  with no parent descends from `TObject` (the core unit `pasobject`,
  1.1.2), whose virtual methods take the first six slots. The words
  before the method table are, from the nearest: the table of its
  published properties (the RTTI that `PropKind` and its kin read,
  MANUAL §7), the parent's method table (0 for `TObject`), the size of
  an instance, and the length and the address of the class's name,
  which lies as a string literal does. Inside a method `Self` is that
  pointer. A plain `record` has no VMT.
- An exception object is any object: `raise X` puts it in the raising
  routine's record, at G+272, and where it was raised at G+280 (1.1.3);
  a handler's `on E: T` is `is`, a walk up the parents' method tables.
  The collector reads the routine record whole, so the object lives
  while a handler has it.
- `I = interface` is a 16-byte value: the object pointer and a method
  table. `TBox = class(I)` or `class(TParent, I)` lists what the class
  implements. `G := Obj` is checked from the static class, including
  interfaces inherited from the parent class and parent interface.
  A call uses that table and passes the object as `Self`. There is no
  reference count; the object lives in the collected heap and goes when
  nothing points to it.
  `testdata/iface.paslang`.


## Pointers (P102, P104)

A pointer is an address; what it points at has the type of the view it
is seen through (`examples/pointers.paslang`).

- **`Pointer`** is untyped (1.0.106): `p^` alone is only an untyped
  argument (`Move`, `FillChar`); anything else needs a view.
- **Predefined pointer types**, each `^` of its type: `PByte`, `PWord`,
  `PDWord`, `PInt8`, `PInt16`, `PInt32`, `PUInt8`, `PUInt16`,
  `PUInt32`, `PShortInt`, `PSmallInt`, `PLongWord`, `PInteger`,
  `PInt64`, `PSingle`, `PDouble`, `PQuad`, `PBoolean`, `PPointer`,
  `PChar`. The names are reserved: a program cannot declare one.
- **Views:** `PT(q)` (a pointer, a class or an `Integer` address seen as
  a `PT`; a copy of the node, so it stays a variable for `Inc` and
  `var`), `^T(q)` in line for any `T`, `T(q^)` the `T` at that address
  as a variable, `TRec(q)` = `TRec(q^)`, `TForm(q)` the object. Through
  a typed pointer `T(pb^)` converts the value: `Integer(pb^)` of a
  `PByte` is the byte; `PInteger(pb)^` reads 8 bytes.
- **Arithmetic** scales by the view's element size: `PDWord(X) + 1` is
  +4, a `Pointer` counts bytes; `Inc(PDWord(X))` and `Inc(PWord(X), 3)`
  step for good. `q - r` of one type is `(q - r) div size`; two types
  need one view. `=`, `<>`, `<`, `>` compare addresses.
- **`safe`** before `program`, `unit` or a routine refuses arithmetic,
  views, conversions between pointer types, `Pointer(n)`, `p[i]`,
  `View` and an untyped `p^`; `New`, a typed `p^`, `@x`, `nil`, arrays,
  strings, classes and slices stay. Free at run time; the `.pi` says
  `SAFE`.
- **`MemBase(p)`, `MemSize(p)`, `MemEnd(p)`** (1.0.109): the object `p`
  is in — a heap block (found from its span), the routine's stack, the
  globals — or 0.
- **Compile-time reach errors** (1.0.111): an access through `@v` (a
  local or global holding its own value), a field or a constant element
  of it, moved a constant number of bytes, that leaves `v` is an error:
  `pointer outside its object: x has 8 bytes and this reaches bytes 8 to
  8`. Also `FillChar` and `Move` with a constant count. A step alone is
  not an access; a var parameter never counts as the whole object.
- **`-checkptr`** (1.0.110, rules of 1.0.111): every step must stay in
  the object of the pointer it came from or reach one past its end (as
  in C); every access (`p^`, `p[i]`, a view, a field through a pointer)
  must lie in one object, and `p[i]` and `(p + n)^` in `p`'s own. The
  failure is `pointer outside its object at line N`. Per unit (the `.pi`
  says `CHECKPTR`).
- **The collector and end pointers:** a pointer one past the end of a
  heap block points where the next block starts and keeps that one
  alive, not its own: keep a pointer to the block while it is used
  (GC.md).
## Channels

`chan of T` is a language type (runtime heap object + pointer). Same
idea as Go `chan T`. Not a Pascal file type. `MakeChan()` makes one
without a buffer, `MakeChan(n)` one that holds up to `n` values
(1.0.85).

## Maps

`map[K] of V` is one pointer, `nil` until `New(m)` or `New(m, hint)`.
`K` is an ordinal, a `string`, a pointer, or a class; `V` is any type,
records included. `m[k]` reads (the zero value when the key is absent
or the map is `nil`, a field of it too), `m[k] := v` writes (a `nil`
map stops the program with `paslang: nil map`), `k in m` tests,
`TryGet(m, k, v)` reads with a Boolean into a `v` of type `V`,
`Delete(m, k)` removes, `Clear(m)` empties, `Length(m)` counts, and
`for k in m do` / `for k, v in m do` walk the entries in no particular
order, `k` of type `K` (or a wider integer type) and `v` of type `V`;
delete and insert during a walk are allowed, and the map is worked out
once. The key is converted as a call's argument is (1.0.140): a `Char`
into a `string` key, a constant that must fit a `Byte` key, a wrong
kind refused. `m[k] op= e`, `Inc(m[k])`, `m[k].X := e`, `with m[k] do`,
`SetLength(m[k], n)` and `m[k]` as a `var` argument write the entry,
inserted with a zero value when the key was missing (the parser turns
the `rt_mapget` at the root of the written place into `rt_mapput`, the
slot's address); `@m[k]` is refused. A map goes only into its own map
type (`SameTyp` compares key and value, so the type is one across
units), and `nil` into any.

The table is the Go 1.24 / Abseil Swiss table written in Pascal
(`src/lib/pasmap.paslang`, the core unit `pasmap`), split as Go splits
it (1.0.59): a directory of tables indexed by bits of the upper half of
the hash, each table at most 1024 slots. A table doubles until it
reaches 1024 slots and then splits in two, so a growing map never holds
an old and a new copy of all of itself. Groups of eight slots share an
8-byte control word (128 empty, 254 deleted, else the low seven bits of
the hash); a lookup probes the groups quadratically, the load is 7/8,
and a delete leaves a tombstone only in a full group. `New(m, hint)`
makes one table while the hint fits one (up to 896 entries), else 2^k
tables of 1024 slots at half load. Keys hash with XXH3 (1.0.64): a
string key as `XxHash3` of its bytes, an eight-byte key through XXH3's
path for 4 to 8 bytes, in line; every map has its own seed, drawn from
one `getrandom` per process, so the order differs between runs. A
`Writing` flag catches two routines writing at once (`paslang:
concurrent map writes`). The compiler passes a descriptor
(`.LdescMap_<type>`: key kind, key size, value size, whether a slot
holds a pointer) to `PasMapNew`, `PasMapGet`, `PasMapPut`,
`PasMapNext`, `PasMapDelete` and `PasMapClear` (the last two zero the
slots they empty, 1.0.140, so what a dropped entry held is freed); an
eight-byte key goes
in a register to `PasMapGetInt` and `PasMapPutInt`, a string key to
`PasMapGetStr` (`TryGet`) and `PasMapPutStr`, and `m[s]` and `s in m`
of a string key call
`rt_mapgetstr`, the same lookup written in the runtime's assembly
(1.0.69). `Length(m)` reads the first word of the map inline. The key kind and value type ride in the
`.pi` line of a map type (`Elem2` is the value). `testdata/map1.paslang`,
`testdata/map2.paslang`, `testdata/units/mapuse.paslang`.

## Trees, heaps and the store (P110)

`tree[K] of V` is an **ordered map**, one pointer, `nil` until `New(t)`:
a B+ tree in memory (`src/lib/pastree.paslang`, the core unit
`pastree`, linked without `uses` as `pasmap` is) with at most 32 keys
in a node, the values only in the leaves, and the leaves linked in key
order, so a walk is a walk along the leaves. `K` is an ordinal, a
`string`, a pointer or a class, ordered as `<` orders it (strings byte
by byte); `V` is any type. `tree of K` is the same tree with no value,
a set. The map's words work on it: `t[k]` (the zero value when absent),
`t[k] := v`, `k in t`, `TryGet(t, k, v)`, `Delete(t, k)`, `Clear(t)`,
`Length(t)`, `for k in t do` and `for k, v in t do`, which walk in key
order; `downto` walks backwards; `for k, v in t[a..b] do` walks the
keys from `a` to `b`, both in. The order words: `Low(t)` and `High(t)`
(the first and the last key), `Succ(t, k)` and `Pred(t, k)` (the key
after and before `k`, `k` in the tree or not), `Floor(t, k)` (the
greatest key not above `k`) and `Ceil(t, k)` (the least key not below);
when there is none the program stops (`paslang: empty tree`, `tree
succ`, …), so guard with `Length`, `in` or `Rank`. `Rank(t, k)` counts the
keys below `k` and `KeyAt(t, i)` is the key of rank `i`, both by the
subtree counts the nodes keep. `PopLow(t, k, v)` and `PopHigh(t, k, v)`
take the least or the greatest entry out and say whether there was
one (`PopLow(t, k)` of a `tree of K`). `u := Split(t, k)` moves the
keys from `k` up into a new tree; `Join(t, u)` moves every entry of `u`
into `t`, `u`'s value winning, and empties `u`. A `tree of K`: `t[k]`
reads `True` or `False`, and `t[k] := True`, `Include(t, k)` and
`Exclude(t, k)` change it (`Include`/`Exclude` on a `set` are refused
with the spelling that works, `s := s + [x]`). The nodes are scanned by
the collector; a walk's key and value share the tree's strings, marked
shared, as a map's do. Two routines writing at once stop the program
(`paslang: concurrent tree writes`); a walk during a write too.

`heap of T` is a **binary min-heap** in an array (Go's
`container/heap`): `New(h)`, `Push(h, x)`, `Pop(h, x)` with a Boolean,
`Pop(h)` and `Low(h)` (the least element; an empty heap stops the
program with `paslang: empty heap`), `Length(h)`. `T` is an ordinal, a
`string` or a real.

`store` is a **key-value store on disk**, a log-structured merge store
on the tree, after LevelDB: `db := StoreOpen(path)` makes or opens
`path` (the table) and `path.wal` (the log); `StorePut(db, k, v)`,
`StoreGet(db, k)` (`''` when absent), `k in db`, `StoreDelete(db, k)`,
`StoreSync(db)` (the log to disk), `StoreClose(db)` (the memtable
written as a run, the files closed), `StoreAbandon(db)` (closed as a
crash would leave it; the log recovers it on the next open). Keys and
values are strings of any length. A write goes to the log first, a
record with its CRC32C, and a torn log is cut at its last whole record;
past 1 MiB of log the memtable becomes a run of data blocks with an
index kept in memory; past four runs they are merged into one, written
to `path.new` and renamed over `path`. A `store` variable is one
pointer; the words are the language's, the code the core unit's.

The compiler passes `.LdescTree_<type>` and `.LdescHeap_<type>` (key
kind, key size, value size, whether a slot holds a pointer) to the
unit's routines, and calls them by the map's convention.

## Sync types

`mutex` (32 bytes), `rwmutex` (48), `waitgroup` (24), `cond` (16), and
`once` (32) are reserved words for the records of the core unit
`pasroutines` (`TPasMutex`, `TPasRWMutex`, `TPasWaitGroup`, `TPasCond`,
`TPasOnce`). Their zero value is ready, so they live where declared:
a global, a local, or a record field, never created. `lock mu do stmt`
is `PasMutexLock` plus a `try ... finally PasMutexUnlock`, so the mutex
is released on `exit`, `break`, `continue`, and `raise`; `lock rw do`
and `lock rw read do` are the writer and reader sides; `once o do stmt`
is `if PasOnceBegin(o) then try stmt finally PasOnceEnd(o)`. The
methods `Lock`, `Unlock`, `TryLock`, `BeginRead`, `EndRead`, `Add`,
`Done`, `Wait`, `Wait(mu)`, `Signal`, `Broadcast` rewrite to the unit
procedures. `GetMem(p, n)` gives n bytes the collector will scan
word by word; `GetMem(p, n, 0)` gives n bytes that hold no pointer;
`GetMem(n)` and `GetMem(n, 0)` are the same as functions, giving the
block as a `^Integer`.
A waiter parks the G, so the M stays free: the mutex is
Go's `sync.Mutex` and parks without a lock (`WaitPush`, `WaitTake`,
`WaitFront`, `ParkMarked`); the others park on the record's queue under
a spin word (`QWait`, `ParkUnlock`, `QWake1`, `ReadyG`).
`testdata/sync1.paslang`, `testdata/sync2.paslang`.

## Sockets

`TcpRead` (`uses pasnet`) returns a `string`: the pointer is the bytes
just read, and the length is that count. It is not a C string. An
empty string means end of stream. The bytes are an ordinary string of
the collected heap, given back when nothing holds it.
`TcpReadDeadline(Fd, MaxN, Ms)` is the same read with a wait of at most
`Ms` milliseconds; on the timeout it returns the empty string.
`testdata/tcppark.paslang`.

## What we refuse

- A record, a static array, a string or a slice where another type goes
  (1.0.120): `i := r`, `s := r`, `r := r2` of another record, a slice of
  `Byte` into a slice of `Integer`. A type a unit brings in again under
  another id is the same type (same name, kind and size).
- Logic on a record or an array that holds strings, slices, pointers or
  objects (1.0.120): it would make addresses up.
- Operators on the hidden address (1.0.116): a `string` takes `+`
  (with a string or a `Char`) and the comparisons; any other operator
  on a string, and any arithmetic or logic operator on an array, an
  object, a map, a channel, a routine value or a record that does not
  declare it, is a compile error. They compiled:
  `s + 1` dropped the 1, `-s` stopped the program, `a + a` added two
  slice addresses.
- A Boolean mixed with an integer in `and`, `or`, `xor` (and `nand`,
  `nor`, `xnor`, `andnot`): with comparisons binding first, `x and 4 =
  4` is `x and True`, the slip C compilers warn about.
- Default `string` = ShortString(255).
- `Integer` = 16-bit.
- Length byte stored *in front of* a `PChar` that user code might pass
  as a raw pointer (classic AnsiString header).
- 1-based vs 0-based mixed without a rule: **strings are 1-based**
  (`s[1]` is the first byte). **Dynamic arrays are 0-based** (`a[0]` is
  the first element). Static arrays use their declared bounds.

## Implementation notes

Runtime helpers: `rt_concat` (joins strings), `rt_setlength` (sizes a
string or a slice), `rt_append` (`Append`). They run on the **G**, may
allocate, never assume a 4 MiB OS stack. Growing a slice
or string is a call that `morestack` can see.

**Emit load size follows storage, not a widened `Typ`.** `Ord(e)` sets
`e^.Typ := TyInteger` on the same node, except for a Boolean: an
operation's code depends on its type (`not` of a Boolean flips one bit,
of an integer every bit), so `Ord`, `Integer(b)` and `Byte(b)` of a
Boolean wrap it in a conversion node instead (`TParser.AsInt`, 1.0.116;
relabelled, `Ord(not t)` was -2). Index/field/deref loads must
still use the element size of the base (`string` → 1, `array of T` →
`TSize(elem)`). Helper: `TEmitter.LoadSize`.

**Fat ABI:** `string` and a method pointer are two words (ptr+len, or
code+self). `array of T` is three words (ptr, len, cap), 24 bytes.
`nil` zeros the words that exist. `SetLength` on a string always
allocates a new buffer and does not read a capacity word. `SetLength`
on a slice passes the element size; a shrink keeps the buffer, and a
grow stays in it only from its frontier (Dynamic arrays, above).
`const S: string` is a pointer to the two-word descriptor. Class-typed
fields are 8-byte pointers, not instance size.

**`rt_execute` restores SysV argument registers** (and the nested-proc
static link) from the G before jumping to `gobuf.pc`. `morestack`
saves them; sysmon preemption restarts the prologue. Without the
restore, `Self` and `const string` args are garbage after a 10 ms
preempt.

**`and`/`or`:** Boolean operands short-circuit (FPC `{$B-}`). Integer
operands are bitwise. Const-fold must follow that split: `1 or 64 or
512` is `577` (open flags), not `1`.

**`Char` locals** load with `movzbq`/`ldrb`. An 8-byte load of a 1-byte
slot compares uninitialized high bits (`SameId` on `WriteLn` failed).

`Syscall(nr, ...)` is the compiler builtin for a GNU/Linux system call,
on amd64 and on arm64. `paslinux` `Sys0`…`Sys4` are Pascal wrappers
around it. A wrapper whose body is only `Result := Syscall(...)` skips
the `morestack` prologue and the 2 KiB scratch frame, so `fork` and
`wait4` do not grow or preempt mid-call. `Amd64` is 1 on GNU/Linux amd64
and 0 on arm64, so one source can pick the syscall number.
The numeric constants in `paslinux` are the amd64 numbers. There is
no assembler in that unit.

---

Copyright (C) 2026 Germán Luis Aracil Boned.

Permission is granted to copy, distribute and/or modify this document
under the terms of the GNU Free Documentation License, Version 1.3 or
any later version published by the Free Software Foundation; with no
Invariant Sections, no Front-Cover Texts, and no Back-Cover Texts. A
copy of the license is included in the file COPYING.DOC.
