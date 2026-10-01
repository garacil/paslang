# paslang

A **new Pascal** on a Go-shaped engine. The syntax and the essence stay
Pascal; underneath, thousands of lightweight routines run on a few OS
threads, stacks grow on demand, and I/O parks a routine instead of
blocking a thread. The compiler, the runtime and the library are written
here, in paslang itself, and emit native code for amd64 and arm64 on
GNU/Linux. No libc, no C runtime.

```paslang
program hello;

begin
  WriteLn('hello world');
end.
```

Source files use the `.paslang` extension.

## What the language has

- **Routines and channels.** `pas f(x)` starts a routine; channels,
  `select`, `mutex`, `rwmutex`, `waitgroup`, `cond` and `once` are part
  of the language, with `lock ... do` and `once ... do`.
- **Collections.** Maps (`map[K] of V`), ordered trees (`tree[K] of V`,
  `tree of K`, with rank and ranges), heaps (`heap of T`) and `store`, a
  key-value store on disk.
- **Hash words.** `Sha256`, `Sha1`, `Sha512`, `Sha3_256`, `Md5`, the
  HMACs, `Crc32`, `Crc32c`, `XxHash3` and more, each on the processor's
  own instructions where it has them.
- **The network.** TCP and UDP over both address families,
  Unix-domain sockets, a resolver and DNS messages, all on parked
  routines: a server of tens of thousands of connections is that many
  small stacks.
- **The processor chosen at compile time.** `-cpu` picks the
  instructions; a word with a kernel (SHA-1, SHA-256, SHA-512, the CRCs,
  XXH3, `PopCount`, the vectors) has a body for the processor's
  extensions and a plain one, and nothing is tested at run time.
- **Classes and exceptions with objects.** Every class descends from
  `TObject`; `raise` carries an object of any class, and an `except`
  part picks it by class with `on E: T do` handlers. The object belongs
  to the routine that raised it, and the collector takes it back.
  Class methods and class references, `array of const`, default
  parameters on methods, sets of `Char` and of `Byte`, subranges of
  `Char` and of an enumeration, and helpers (`type helper for string`)
  are Object Pascal's.
- **Inline assembly** per machine, `Quad` (IEEE binary128), vectors, and
  a collector that reads compiled frames through the compiler's stack
  maps.
- **SysUtils.** Pascal-style exceptions, string utilities, conversions,
  correctly rounded real formatting, exact checked decimal `Currency`,
  date/time routines, bounded files,
  explicit-base directories, exact metadata and lexical paths, immutable
  environments, owned child processes/deadlines, secure temporary resources
  and XDG configuration paths, owned builders, strict UTF-8/UTF-16/ASCII
  encoding, checked byte helpers and secure random/time-prefixed UUIDs.
  Compatibility is a reference, not a requirement to reproduce unsafe or obsolete APIs;
  the [manual](docs/MANUAL.md#17-sysutils) specifies supported contracts.
- **A debugger inside the executable.** A program compiled with `-debug`
  carries its own debugger: `./prog --debug-mode` runs it into a console
  on its terminal, stopped before its first statement, with gdb's short
  commands (break, step, next, continue, print, backtrace, list), and
  Ctrl-C stops it; `./prog --debug-listen <socket>` waits for a console
  that `./prog --debug-attach <socket>` or `pasdbg` opens from another
  terminal. Underneath, a line protocol on a Unix socket: routines,
  frames, variables and their values, breakpoints, stepping.

`examples/` has HTTP, DNS, FTP, NTP, WebSocket, chat, terminal and proxy
servers, each with a self-test of thousands of clients in one process.

## Speed

Every benchmark is one program in paslang and its twin in Go doing the
same work, run on the same machine (a Ryzen 9 5950X). paslang's time
over Go's, the median of forty rounds that alternate the two
(`make bench-rounds`):

| Benchmark | What it does | paslang over Go |
|---|---|---|
| b4chan | channels between routines | 0.31 |
| b5map | a hash map | 0.79 |
| b7narrow | narrow integer types | 0.80 |
| b8ptr | pointer structures | 0.89 |
| b3spawn | starting routines | 0.90 |
| b6smap | a map of strings | 0.92 |
| b2str | building strings | 0.94 |
| b11tree | an ordered tree of a million keys | 0.95 |
| b1loop | an arithmetic loop | 1.00 |
| b10rot | bit rotations, xoshiro256** | 1.01 |
| b9hash | SHA-256 and CRC-32C over 1 MiB | 1.01 |

The servers against Go's `net/http` and `net`, with the clients in the
same process: httpd and termd with 10,000 clients take 0.57 and 0.55 of
Go's time, and the other pairs between 0.82 and 1.01. Memory is at or
under Go's almost everywhere. The programs are in `scripts/bench/`:
`make bench` builds and runs the pairs (the median of seven runs each),
`make bench-rounds` runs them again in alternating rounds, and
`make bench-servers` runs the servers.

## Building

paslang runs on GNU/Linux, kernel 6.13 or newer, on amd64 or arm64.
Building it from source needs:

- the Free Pascal compiler (`fpc`), which builds the first compiler once;
  paslang then compiles itself,
- GNU binutils (`as`, `ld`) and, on an amd64 machine,
  `aarch64-linux-gnu-as` and `aarch64-linux-gnu-ld`: `make` builds the
  arm64 units too, and `make install` links an arm64 test program,
- Python 3,
- for `make check`, `gdb`, and `qemu-aarch64-static` 11.1 in `/usr/bin`
  (the arm64 tests run under a copy that
  `scripts/patch-qemu-madv102.py` patches so `MADV_GUARD_INSTALL`
  succeeds), and `Xvfb` if present for the X11 tests; for the
  benchmarks, Go.

```
./configure
make
make check
make install
```

`make` builds `bin/paslangc`, `bin/pasdbg`, and the core and library
units for both machines. `make check` runs every test program, every example of
the manual, the servers' self-tests and the arm64 build under qemu.
`make install` puts `paslangc` and `pasdbg` in `$(prefix)/bin` and the
units in `$(prefix)/lib/paslang` (the arm64 ones in
`lib/paslang/aarch64`); `./configure --prefix=...` chooses the prefix.
`make package` writes the two release archives under `build/pkg`, and
`make distpkg` the packages of the distributions under `build/pkg/dist`.

## Binary packages

Each release carries, for amd64 and arm64, a package for each family of
distributions and a relocatable archive; `SHA256SUMS` lists them all.
Each installs `paslangc` and `pasdbg` in `/usr/bin`, the units in
`/usr/lib/paslang`, the manual in `/usr/share/doc/paslang` and the
examples in `/usr/share/paslang/examples`, and pulls in GNU binutils,
which the compiler needs for `as` and `ld`.

| Distribution | amd64 | arm64 | Install |
|---|---|---|---|
| Debian, Ubuntu | `paslang_<v>-1_amd64.deb` | `paslang_<v>-1_arm64.deb` | `sudo apt install ./paslang_<v>-1_amd64.deb` |
| Fedora, RHEL, openSUSE | `paslang-<v>-1.x86_64.rpm` | `paslang-<v>-1.aarch64.rpm` | `sudo dnf install ./paslang-<v>-1.x86_64.rpm` (`sudo zypper install` on openSUSE) |
| Arch | `paslang-<v>-1-x86_64.pkg.tar.zst` | `paslang-<v>-1-aarch64.pkg.tar.zst` | `sudo pacman -U paslang-<v>-1-x86_64.pkg.tar.zst` |
| Slackware | `paslang-<v>-x86_64-1.tgz` | `paslang-<v>-aarch64-1.tgz` | `sudo installpkg paslang-<v>-x86_64-1.tgz` |
| Any, unpacked anywhere | `paslang-<v>-linux-amd64.tar.gz` | `paslang-<v>-linux-arm64.tar.gz` | `tar xzf paslang-<v>-linux-amd64.tar.gz` |

Once a package is installed the compiler is ready:

```
paslangc -o hello hello.paslang
./hello
```

An unpacked archive works the same from its own `bin`
(`paslang-<v>-linux-amd64/bin/paslangc`): the compiler finds its units in
`lib/paslang` beside its `bin`. On amd64, `paslangc -target arm64`
compiles for arm64 once the cross binutils are installed
(`binutils-aarch64-linux-gnu` on Debian, `aarch64-linux-gnu-binutils` on
Arch).

`make release-assets` builds all of them into `build/pkg/release`, with
`SHA256SUMS`; it needs `dpkg-deb`, `rpmbuild` and `makepkg`.
`make check-release` also validates every package format, the exact binaries
and manual, and both relocated compilers running the SysUtils examples.
It independently rebuilds both debuggers for the base CPU and compares every
byte, then tests the packaged debugger protocol against an instrumented
program. The arm64 tools also run on Cortex-A53, without LSE.
It additionally needs `bsdtar` and `rpm2cpio`.

## Documentation

The [wiki](https://github.com/garacil/paslang/wiki) has all of it, one page a
chapter, with the installation, the examples and the benchmarks.

| File | What |
|---|---|
| [docs/MANUAL.md](docs/MANUAL.md) | The programmer's manual; every program in it lives in `examples/` and runs under `make check` |
| [docs/manual/index.html](docs/manual/index.html) | The manual with TYPES, QUAD, GC, KERNELS and VISION as one page (`make manual`) |
| [docs/HELP.md](docs/HELP.md) | `paslangc --help`: the manual inside the compiler |
| [docs/TYPES.md](docs/TYPES.md) | The types: unbounded strings, slices, 64-bit integers, the modern ABI |
| [docs/GC.md](docs/GC.md) | The heap and the collector |
| [docs/QUAD.md](docs/QUAD.md) | `Quad`: IEEE binary128 in software |
| [docs/KERNELS.md](docs/KERNELS.md) | Kernels: one body per machine, chosen by `-cpu` |
| [docs/VISION.md](docs/VISION.md) | Pascal's essence on Go's engine |
| [docs/CONSTRAINTS.md](docs/CONSTRAINTS.md) | What does not change |

## Author

paslang is written by Germán Luis Aracil Boned (see [AUTHORS](AUTHORS)).

## License

paslang is free software.

| Part | License |
|---|---|
| The compiler (`src/compiler`, `cmd/paslangc`), `pasdbg`, the scripts, the tests and the examples | [GNU General Public License](COPYING), version 3 or any later version |
| The runtime library: the units of `src/lib` and `src/rtl` and the runtime `paslangc` writes into every program | GPL version 3 or later with the [paslang Runtime Library Exception](COPYING.RUNTIME) |
| The manual and the documentation in `docs/` | [GNU Free Documentation License](COPYING.DOC), version 1.3 or any later version, with no Invariant Sections, no Front-Cover Texts and no Back-Cover Texts |

The Runtime Library Exception lets a program compiled with paslang be
distributed under whatever terms its author chooses, although the runtime
and the units are linked into it; the runtime library itself stays under
the GPL.

The SHA-1, SHA-256, SHA-512 and CRC kernels of `src/lib/pashash.paslang`
and the string kernels of `src/lib/passtr.paslang` follow the assembly
of Go 1.23 for each machine, and the digits of a real in
`src/rtl/sysutils.paslang` follow Go's `strconv` (its unrounded scaling
and its table of powers of 10); Go's license, which covers those parts,
is in [LICENSE-GO](LICENSE-GO).

Copyright (C) 2026 Germán Luis Aracil Boned.
