# paslangc manual

The manual is inside the compiler so a checkout is not required to read it.

```bash
paslangc
paslangc -v
paslangc --version
```

The version is the one `paslangc -v` prints; it lives only in
`PaslangVersion` (`src/compiler/pashelp.paslang`) and rises with every
change. With no arguments, `-v`, or `--version`, paslangc
prints a card:

```
  ╭────────────────────────────────────────────────────────────╮
  │  paslangc  x.y.z                                           │
  │  living modern pascal                                      │
  │                                                            │
  │  Pascal spelling. 64-bit Integer. UTF-8 string.            │
  │  / divides reals. div divides integers.                    │
  │  A routine is a G. It parks; the thread stays free.        │
  │  GNU/Linux amd64. The program does not link libc.          │
  ╰────────────────────────────────────────────────────────────╯
```

`paslangc` and `paslangc -h` then print the topic index in the same kind of frame.
`paslangc --help` prints that index and every section.
`paslangc --help types` prints one section: the word after `--help` is
the topic when it does not start with `-`.

```bash
paslangc
paslangc -h
paslangc --help
paslangc --help flags
paslangc --help types
paslangc --help lang
paslangc --help runtime
paslangc --help lib
paslangc --help limits
paslangc --help examples
paslangc --help all
paslangc --help index
```

`--help` with no topic, or with `all`, prints the index and every
section; `index` (also `short`) prints the index alone, as `-h` does. An
unknown topic prints `unknown help topic: <topic>` and the index. Every
form prints the card first and exits 0. The source of that text is
`src/compiler/pashelp.paslang`. Spellings, sizes, and examples there are
the ones the compiler implements. A form that is not listed under
`limits` or `lang` is not a promise.

Topics:

| Topic | What it answers |
|---|---|
| flags | `-h`, `-v`/`--version`, `--help`, `-o`, `-c`, `-checkptr`, `-Fu` and the unit search order, `-install`, `-cpu`, `-inline` and `-inline-trace`, `-debug`, `-target`, `--lex`, exit status |
| types | sizes: `Integer` 64, the narrow integers 8/16/32, `Char` 1 byte, `string` pointer+length, `Real` binary64, `Single` binary32, `Quad` binary128, slices, records, sets, channels, maps, the sync types, method and interface values, pointers and views |
| lang | statements, units, classes, channels, a hello program |
| runtime | G/M, preemption, the collector, the fatal errors, `Syscall`, and the builtins: the calculation set, hashing, `GetMem`, the debugging words, RTTI, the atomics and the scheduler's words |
| lib | the eight core units (`pasobject`, `pasroutines`, `pasmap`, `pashash`, `pastree`, `pasfmt`, `pasheap`, `pasquad`), the installed units `pastime`, `pasrand`, `passort`, `paslib`, `pasnet`, `pasdebug` (written by `-debug`) and `pasx11`, and the `Net` builtins under `pasnet` |
| limits | forms the compiler does not accept or treats otherwise than another Pascal, and the reserved words |
| examples | commands that compile and run |
| all | every section above, after the index |
| index, short | the index alone |

---

Copyright (C) 2026 Germán Luis Aracil Boned.

Permission is granted to copy, distribute and/or modify this document
under the terms of the GNU Free Documentation License, Version 1.3 or
any later version published by the Free Software Foundation; with no
Invariant Sections, no Front-Cover Texts, and no Back-Cover Texts. A
copy of the license is included in the file COPYING.DOC.
