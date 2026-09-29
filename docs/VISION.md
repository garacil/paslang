# Vision

paslang is a **new Pascal** whose execution model is Go’s: thousands of
lightweight threads (G) multiplexed on a few OS threads (M), with a
logical processor (P) as the right to run user code.

The goal is **everything Pascal allows**, running on **Go’s technology**:
G/M/P, `morestack`, park instead of block, channels. We implement Go’s
engine **under Pascal**, not a toy subset forever.

## Essence (do not lose it)

paslang must still **feel like Pascal**. Go supplies the engine, not a
new personality.

Keep:

- Readability: `begin` / `end`, explicit structure, keywords you can
  teach.
- Strong static types; the compiler is strict.
- Units and separate compilation (`uses` is not `#include`).
- `WriteLn`, ordinal types, records, nested procedures, the program as
  a readable essay.
- Types that still *read* as Pascal (`string`, `Integer`, `array of T`)
  but use a **modern ABI** (see [TYPES.md](TYPES.md)): unbounded
  strings, 64-bit `Integer`, slices — not ShortString(255).
- The programmer says what they mean; the runtime does not invent a
  second dialect (`PasWriteLn`, `fmt.Println`, `go func()`).

Do not:

- Turn Pascal into Go with `begin` glued on (`:=` for assignment is
  Pascal; we do not switch to Go’s `:=` for declare-and-assign as the
  main style unless Pascal already has it).
- Hide types, drop units, or merge files like C.
- Make concurrency look like Go source (`go f()`, `make(chan int)` as
  the spellings). The spellings stay Pascal: `pas f`, `chan of Integer`,
  `WriteLn`.

If a change would make a Pascal programmer not recognize the program as
Pascal, it is rejected — even if it would make the runtime easier.

The compiler is delivered in slices (hello, then `pas`, then units, then
classes…). The **language goal** is full Pascal (ObjFPC-shaped: units,
nested procedures, objects/classes, generics, `try`/`except`, sets; I/O
through the parking library, not `file of`). Features ship when
they honour G/M/P — they are not deleted from the language.

## Two inspirations (read both, always)

| Source | What we take | What we do not take |
|---|---|---|
| **Pascal** | The **language** in full: syntax, units, separate compilation, nested procs, objects, generics | Someone else’s compiler or RTL |
| **Go** | The **technology**: G/M/P, `morestack`, park not block, errors as values, a small stdlib that parks | Go’s syntax, `fmt.Println`, cgo |

When building: read a mature Pascal compiler only as a **guide** to
compatibility. Read Go's `src/runtime` and `cmd/compile` for how a
modern concurrent language is engineered. We **write** parser, types,
codegen, and stdlib ourselves — better and tighter, Go-minded.

## Living Pascal (compatibility north star)

There is no current ISO that describes the Pascal we want. ISO 7185 and
Extended Pascal (10206) are museum pieces: 16-bit `Integer`,
ShortString, DOS-shaped files. We do **not** implement them as the
language.

The living language is **Object Pascal** as programmers write it now
(units, classes, generics, `try`/`except`, `WriteLn`). The readable
spec for *which constructs exist* is the Free Pascal **Language
reference** ([online](https://www.freepascal.org/docs-html/current/ref/ref.html)).
FPC’s compiler and RTL are a source of **ideas** (how a construct is
parsed, what a unit interface is), never a source of code, ABI, or
defaults.

Take from that reference: spellings, units, nested procedures, records,
classes, generics, sets, structured statements. Leave behind: modes
soup (`tp`, `macpas`), 16/32-bit `Integer`, default ShortString(255)
and `string[n]` (a syntax error in paslang), `file of` as the I/O model,
overlays, far pointers, real-48, `absolute`, COM, `threadvar`, and
anything that assumes a 4 MiB OS thread stack. `published` was taken
when it was needed (P21): a class's properties outside a `private` or
`protected` section whose accessor is a field get an RTTI table that
`GetPropInt`, `SetPropStr`, `CallProp` and their kin read by name.

Our defaults stay the modern ABI in [TYPES.md](TYPES.md): unbounded
UTF-8 `string`, 64-bit `Integer`, slices. Compatible *as Pascal*, not
as Turbo Pascal 7.

## Separate compilation (Pascal, not C)

A unit is a **compilation unit**. `uses Foo` imports Foo’s **already
compiled interface**, it does **not** paste `foo.pas` into the current
file like `#include`.

- Each `.paslang` → interface artifact + object.
- Changing a unit’s **implementation** does not force recompilation of
  clients, as long as the interface checksum is unchanged.
- There is no preprocessor that concatenates sources into one translation
  unit. Macros that rewrite the program are not part of the language.
- Cycles: interface `uses` must be acyclic; implementation `uses` may
  refer back (Pascal rule). That is the compilation philosophy we keep.

Go packages are also separate compilation; C headers are not. We follow
Pascal here, not cpp.

The compiler and stdlib are **ours** (`paslib`, `paslinux`, parser, emit).

## Names are Pascal; mechanics are Go

```pascal
WriteLn('hello from ', id);
Write(x, y);
ReadLn(s);
pas worker(1);
```

- **`WriteLn` / `Write` / `ReadLn`** are builtins. They desugar to
  runtime calls that take the current **G**, hold a print lock so
  concurrent lines do not tear (like Go `fmt`), and **park** (or
  `entersyscall`) if the fd would block the M. They never assume a
  4 MiB pthread stack.
- There is **no** `PasWriteLn`, no unit `Pasio`, no second API.
- **`pas`** is a keyword (spawn), not `Pas(@f)`.
- **`chan of T`** and **`select`** are the language, not a library
  bolted onto `TThread`.

If a builtin cannot honour G/M/P, it does not ship.

## Execution model

| Object | Role |
|---|---|
| **G** | goroutine: contiguous stack that grows via `morestack` |
| **M** | OS thread (pthread). Owns `g0` (scheduler stack) |
| **P** | logical processor: `runq[256]`, work steal |

- `g` lives in a register: amd64 **r14**, arm64 **x28**.
- Every function prologue compares SP to `g.stackguard` and may call
  `morestack`.
- Park = save gobuf, switch to `g0`, `schedule`. Never `pthread_create`
  per `pas`.
- Wait = event: channel, timer, epoll. Stdlib `read`/`connect` go
  through netpoll so an M in a real syscall **drops its P**.

Panic / `try`/`except` state lives **on the G**, not in a pthread threadvar.
`threadvar` is not a word of paslang (a syntax error): a routine may run
on any M and move between them, so data per OS thread would mean
nothing to it. Goroutine-local data is a different primitive if we add
it; `Carry` (G+256, P108) is per routine, as the try records are.

Nested procedures keep a static link. **`morestack` must relocate that
link** when a stack moves. Classes and
`of object` are heap `Self` + code pointer; the compiler emits that ABI
on the growable G stack (P12, P26).

## Ultra efficient, and dynamic (2026-09-29)

paslang is dynamic in the Go sense, thousands of routines that park
instead of blocking, and it is **ultra efficient**: every word of the
language runs the best code the machine has, decided once, not at each
call. The rules that follow from that (`docs/KERNELS.md`):

- A hot routine the processor does with an instruction (SHA, CRC,
  PCLMUL, popcnt, the vectors) is a **kernel written once per machine**,
  after the manual and after Go, validated against an oracle, and
  reused; the code that uses it adapts only its input and output.
- **The processor is chosen when the program is compiled** (`-cpu`, as
  Go's `GOAMD64` and gcc's `-march`): the compiler calls the body on the
  processor's instructions or the Pascal body, and writes `popcnt`, the
  AVX2 vectors or the SSE2 ones, directly. The program tests nothing at
  run time; a jump is a jump, and the base processor is a separate
  compile (`-cpu base`), not a branch.
- **Every kernel has its Pascal body beside it**, the reference, and the
  program always compiles and runs without the extension.
- **Rounds are written out**, not looped: SHA-256's 64 rounds and SHA-1's
  80 are unrolled in the kernels and in the Pascal bodies, as OpenSSL,
  Intel and Go write them, because unrolling removes the loop and lets
  the registers rotate without moves. The loop over the blocks stays:
  the length of a message is not known when the program is compiled,
  and a predicted taken branch per 64 bytes costs nothing measurable.
- Code that is **continuous everywhere** (no jumps, no calls) is not the
  goal: the processors' own manuals (the Intel
  optimization manual, AMD's guide for family 19h, Arm's for Neoverse
  N2) say what unrolling past the instruction cache and the loop stream
  costs. What is worth having, and what `-inline` does since 1.1.1, is
  `inline` by measure: a plain routine whose body counts at most
  `-inline N` statements and expression nodes (40 by default), or any
  routine declared `inline`, put in place where it is called, and a
  `for` of a constant count of four or fewer with a small body written
  out at that level; and beside it a size level, `-inline 0`, one copy
  of every routine, for when memory is what counts. At every level a
  program carries only the unit routines it reaches: what a unit offers
  and the program never reaches is not linked; the runtime is linked
  whole.

## What this is not

- Not a wrapper around another Pascal compiler.
- Not a library of green threads on someone else’s compiler.
- Not cgo. User programs do not `#include` C.
- Not “Go with `begin`/`end`”. Not a smaller language pretending to be
  Pascal. Full Pascal, Go engine, essence intact.

---

Copyright (C) 2026 Germán Luis Aracil Boned.

Permission is granted to copy, distribute and/or modify this document
under the terms of the GNU Free Documentation License, Version 1.3 or
any later version published by the Free Software Foundation; with no
Invariant Sections, no Front-Cover Texts, and no Back-Cover Texts. A
copy of the license is included in the file COPYING.DOC.
