# paslang

A **new Pascal** on a Go-shaped engine. Lightweight pasroutines share OS
threads, grow their stacks on demand and park while waiting for pollable
I/O. Blocking kernel calls release scheduler capacity so other pasroutines
can run. The self-hosted compiler emits native Linux executables for amd64
and arm64, with a garbage collector and direct system calls.

[Download the latest release](https://github.com/garacil/paslang/releases/latest) ·
[Installation](https://github.com/garacil/paslang/wiki/Installation) ·
[Programmer's manual](docs/MANUAL.md)

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
- **JSON.** `json` is a type of the language: a value inside a
  document that never changes, read strict as Go's `encoding/json/v2`
  by scans on the processor's vectors; records, classes and any value
  go to JSON and back through code the compiler writes for their type;
  documents are built and transformed (RFC 6902, RFC 7396); streams,
  NDJSON and RFC 7464 sequences, are read and written on parked
  routines; and a constant's text is checked when the program compiles.
- **Networking and mail.** TCP and UDP over IPv4 and IPv6, Unix-domain
  sockets and DNS. The libraries include an HTTP server with graceful
  shutdown, an HTTP client with a cookie jar, TLS 1.2 and 1.3 clients,
  SMTP submission, IMAP and MIME message handling.
  [Core library and network](docs/MANUAL.md#16-the-core-library-and-pasnet)
- **SQLite and document formats.** `uses sqlite` opens SQLite databases
  from paslang, including rollback journals and WAL, with a `TSqlite`
  class and a low-level API under the `sqlite3_*` names. Libraries also
  cover XML, HTML tokenization, ZIP, XLSX and PDF.
  [SQLite guide](docs/SQLITE_GUIDE.md)
- **The processor chosen at compile time.** `-cpu` picks the
  instructions; a word with a kernel (SHA-1, SHA-256, SHA-512, the CRCs,
  XXH3, `PopCount`, the vectors) has a body for the processor's
  extensions and a plain one, and nothing is tested at run time. The
  compiler knows the machine it runs on and processors by name (`zen2`,
  `icelake`, `neoverse-v2`...), and `-tune` chooses between equal forms
  by the manufacturer's latency tables; `{$CPU}` and `{$TUNE}` in the
  code prevail over the command line.
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
  The manual describes ownership, error handling and compatibility for each
  family. [SysUtils](docs/MANUAL.md#18-sysutils)
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

## Benchmarks

These September 2026 measurements compare paslangc 1.0.147 and Go 1.27.1
on a Ryzen 9 5950X. Each pair does the same work. The table gives the
median ratio of paslang time to Go time over forty alternating rounds.
These results describe that toolchain and machine.

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

In the same historical suite, the HTTP and terminal servers with 10,000
in-process clients took 0.57 and 0.55 of their Go counterparts' time.
The wiki records timings, memory and workloads.
[Benchmark results](https://github.com/garacil/paslang/wiki/Benchmarks)

The goal is to beat Go and Rust on equal workloads while preserving
correctness and safety. The Go comparisons in `scripts/bench/` check
output, time and peak memory. With Go installed, run `make bench`,
`make bench-rounds` and `make bench-servers` to measure a checkout.

## Building

paslang runs on GNU/Linux, kernel 6.13 or newer, on amd64 or arm64.
Build with GNU Make and GNU binutils (`/usr/bin/as` and `/usr/bin/ld`).
`make` starts with a compatible paslangc in the configured `bindir` or
`bin/`. The Makefile's `BOOT_MIN` currently requires 1.1.156 or later.
On a fresh machine, Python 3 unpacks the assembly seed for that
architecture from `bootstrap/`. GNU `as` and `ld` turn it into a
bootstrap compiler. That compiler builds the current sources, then the
result rebuilds itself.

`./configure` selects the host's units. On amd64,
`./configure --enable-arm64` adds the arm64 units for
`paslangc -target arm64`. Cross-compilation needs
`aarch64-linux-gnu-as` and `aarch64-linux-gnu-ld` in `/usr/bin`
(`binutils-aarch64-linux-gnu` on Debian, `aarch64-linux-gnu-binutils` on
Arch).

```sh
./configure
make all
sudo make -o all install
make installcheck
```

`make all` builds `bin/paslangc`, `bin/pasdbg` and the selected units.
After that build, `-o all` lets the install step reuse its outputs.
The default prefix is `/usr/local`. Use `./configure --prefix=...`
to choose another prefix. A prefix you can write to needs no `sudo`.

For the full two-target checks on amd64, install the cross binutils,
Python 3, `gdb`, `cc` and Go for the test helpers and oracles.
QEMU's build also uses `meson`, `ninja` and GLib development headers.
`make check` fetches the pinned QEMU source archive, verifies its
SHA-256 and applies the patches in `scripts/qemu/`. It uses `Xvfb`
for X11 tests when available.

```sh
./configure --enable-arm64
make all
make check
```

`make check` runs the golden programs, manual examples, server self-tests,
compiler self-reproduction and arm64 checks under QEMU.

## Binary packages

The release page provides four distribution packages and a relocatable
archive for each architecture, with compilers and debuggers built for
`-cpu base`. Download `SHA256SUMS` alongside your package and run
`sha256sum -c SHA256SUMS --ignore-missing` in the download directory.
[Latest release](https://github.com/garacil/paslang/releases/latest)

Distribution packages install `paslangc` and `pasdbg` in `/usr/bin`, the
units in `/usr/lib/paslang`, the manual in `/usr/share/doc/paslang` and
the examples in `/usr/share/paslang/examples`. The compiler uses GNU
binutils for `as` and `ld`. On Slackware and with the relocatable archive,
install binutils separately if needed.

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

On an amd64 release build with `--enable-arm64`, run `make manual` and
`make check-release` after `make check` has built the patched QEMU.
`make check-release` builds all ten packages and archives plus `SHA256SUMS`
in `build/pkg/release`. It verifies their contents, recompiles and runs
examples with both relocated compilers, and exercises the packaged
debuggers, including Cortex-A53 emulation. The packaging and validation
tools include `dpkg-deb`, `rpmbuild`, `makepkg`, `fakeroot`, `bsdtar`
and `rpm2cpio`.

## Documentation

The [wiki](https://github.com/garacil/paslang/wiki) has all of it, one page a
chapter, with the installation, the examples and the benchmarks.

| File | What |
|---|---|
| [docs/MANUAL.md](docs/MANUAL.md) | The programmer's manual; every program in it lives in `examples/` and runs under `make check` |
| [docs/SQLITE_GUIDE.md](docs/SQLITE_GUIDE.md) | SQLite connections, transactions, WAL, callbacks and concurrent access |
| [docs/manual/index.html](docs/manual/index.html) | The manual, SQLite guide and design chapters as one page (`make manual`) |
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
