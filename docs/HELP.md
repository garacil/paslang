# paslangc manual

Run `paslangc --help` to read the compiler's built-in reference. The
programmer's manual covers library contracts, executable examples and
the runtime model. [Programmer's manual](MANUAL.md)

```bash
paslangc
paslangc -v
paslangc --version
```

With no arguments, `paslangc` prints concise usage and exits 0. The same
summary is available with `-h`, `--help index` or `--help short`.
The output is plain text with stable headings and no terminal-dependent
framing or escape sequences. On an amd64 compiler it reads:

```text
paslangc - modern Pascal compiler
Compile .paslang source into native Linux programs and units.
Default target: linux/amd64

Usage:
  paslangc [options] source.paslang

Build and run:
  paslangc -o app source.paslang
  ./app

Common options:
  -o <path>          Output executable (default: a.out)
  -c                 Compile an object without linking
  -Fu <dir>          Add a compiled-unit search directory
  -target <arch>     amd64 (also intel64) or arm64
  -cpu <processor>   Instruction set: native, base, max or a processor
  -debug             Include the interactive debugger

Help:
  paslangc -h                 Short usage summary
  paslangc -v                 Version, target, processor and license
  paslangc --help             Complete built-in reference
  paslangc --help <topic>     Read one topic
  Topics: flags, types, lang, runtime, lib, limits, examples

Documentation:
  https://github.com/garacil/paslang/wiki
```

The ARM compiler reports `linux/arm64` as its default target. The example
uses an explicit output name; without `-o`, a program is written to
`a.out`. Unit output defaults to `build/<name>.pi` and
`build/<name>.o` (`build/a64/` for ARM).

`paslangc -v` and `paslangc --version` print a first line of
`paslangc x.y.z`, then `target:` and `processor:` metadata and the
copyright and license. The version lives in `PaslangVersion`
(`src/compiler/pashelp.paslang`).

`paslangc --help` or `paslangc --help all` prints the summary followed
by every reference section. `paslangc --help types` prints only that
section. Topic names are case-insensitive. Successful help and version
commands write to standard output and exit 0. An unknown topic writes
`paslangc: unknown help topic: <topic>; use paslangc --help index`
to standard error and exits 1. Build options without a source file also
report an error and exit 1.

The built-in reference comes from `src/compiler/pashelp.paslang`.
Spellings, sizes and examples describe the compiler's implemented contract.

| Topic | What it answers |
|---|---|
| flags | `-h`, `-v`/`--version`, `--help`, `-o`, `-c`, `-checkptr`, `-Fu` and the unit search order, `-install`, `-cpu` and `-tune`, `-inline` and `-inline-trace`, `-debug`, `-target`, `--lex`, exit status |
| types | Integer and real widths, checked four-place `Currency`, strings, slices, records, sets, channels, maps, JSON, method and interface values, and the pointer operations allowed by `safe` |
| lang | statements, units, classes, channels, a hello program |
| runtime | pasroutines, stack growth, asynchronous and cooperative preemption, the collector, checked failures, `Syscall`, atomics, RTTI and scheduler operations |
| lib | the core units and installed libraries for SysUtils, time, networking, TLS, cryptography, text codecs, HTML and XML |
| limits | forms the compiler does not accept or treats otherwise than another Pascal, and the reserved words |
| examples | commands that compile and run |
| all | every section above, after the index |
| index, short | the index alone |

The [core and library chapter](MANUAL.md#16-the-core-library-and-pasnet)
covers additional libraries, and the [SQLite guide](SQLITE_GUIDE.md)
walks through the database API.

Compiled interfaces currently use `PASLANGI36`, as `--help lang` reports.
Rebuild older `.pi` and `.o` files together, including library CPU variants.
The loader rejects an older format or a changed dependency checksum and
names the unit to compile again. Scope components keep underscored unit,
routine, class and helper names distinct; Pascal lookup remains insensitive
to letter case. See [units](MANUAL.md#2-programs-and-units).

---

Copyright (C) 2026 Germán Luis Aracil Boned.

Permission is granted to copy, distribute and/or modify this document
under the terms of the GNU Free Documentation License, Version 1.3 or
any later version published by the Free Software Foundation; with no
Invariant Sections, no Front-Cover Texts, and no Back-Cover Texts. A
copy of the license is included in the file COPYING.DOC.
