# Constraints — non-negotiable

Code that violates this file is wrong. Do not add “just one exception”.

1. **New language, new compiler.** We write it. Pascal is the language; Go is the engine.
2. **Targets:** GNU/Linux amd64 and arm64 only. Nothing 32-bit. No 8086, no i386, no JVM, no ObjC.
3. **GNU/Linux, kernel ≥ 6.13.** `MADV_GUARD_INSTALL` is required. `EINVAL` is a hard error. No `mprotect(PROT_NONE)` dual path. No `#ifdef` for 5.x / 6.1 / 6.12.
4. **No C libraries in v1.** No `.h`, no `importc`, no cgo, no libclang. Syscalls are owned by the runtime. FFI may return later; until then user code does not call libc.
5. **G hangs off M.** `pthread_create` exists only to make Ms. Never one pthread per `pas`.
6. **Every compiled function talks to the scheduler.** Prologue: stackguard / `morestack`, except a wrapper whose body is only `Result := Syscall(...)`, which must not grow or be preempted in the middle of the call (TYPES.md). `g` in r14 (amd64) / x28 (arm64).
7. **Blocking I/O in user programs is a bug.** The stdlib parks the G. A raw blocking `write` that pins the P does not ship.
8. **Golden rule: the compiler must be compilable by itself.** Compiler sources are **`.paslang`**, written in the same Pascal we implement (Go-shaped engine underneath). A feature the compiler uses, paslangc must eventually compile. No dialect the product cannot parse. `bin/paslangc` is built by the previous `paslangc` (the installed one, else `bin/`), then again by itself (Makefile `stage`); FPC host-compiles only when no `paslangc` exists at all, from a bootstrap copy `.paslang` → temporary `.pas` in `build/host/` (`make hostsrc`, `scripts/host_syscall.py`). Canonical files stay `.paslang`.
9. **Pascal names, Go mechanics.** `WriteLn` is `WriteLn`. `pas` is a keyword. Internals: print lock + park/`entersyscall`. If it cannot honour G/M/P, it does not exist.
10. **Our library.** Compiler support code is `paslib` / `paslinux` / compiler units. We rewrite what we need. No foreign RTL in the product.
11. **Units compile independently.** `uses U` is a link to U’s compiled interface, never a textual include. No `#include`. Interface changes rebuild importers; implementation-only changes do not. Pascal compilation, not cpp.
12. **Do not lose Pascal’s essence.** Everything Pascal allows, Go underneath. If a program no longer looks or thinks like Pascal (units, strong types, `begin`/`end`, `WriteLn`, nested procedures), the change is wrong even when it copies Go. Go is the engine; Pascal is the language. Neither is diluted.
13. **Modern type ABI.** Default `string` is unbounded UTF-8 (pointer + length), like Go — **not** ShortString 255. Default `Integer` is 64-bit, and `Cardinal` is that same signed `Integer`. Default `array of T` is a slice (ptr, len, cap). There is no ShortString: `string[n]` is a syntax error. Details: [TYPES.md](TYPES.md).

## Kernel floor (why not 6.3)

| Kernel | Guard pages for 10⁵ stacks |
|---|---|
| ≤ 6.12 | `mprotect` → extra VMA per stack; `vm.max_map_count` kills density |
| **6.13+** | `MADV_GUARD_INSTALL` → guard PTEs inside **one** anonymous VMA |

6.3 is too old for this model. No fallback.

## Language vs delivery

**Language goal:** living Object Pascal (units, nested procedures,
objects/classes, generics, sets, `try`/`except`, `WriteLn`), wired to
G/M/P. FPC’s language reference is the construct list; ISO 7185 is
not the spec. We do **not** invent a smaller language and call it Pascal.

**Delivery order** (compiler slices, not a smaller language):

1. `program` + `WriteLn` literals (done: hello, P1).
2. Procedures, integers, `pas` spawn (done: P3, P7).
3. Units + independent compilation (done: P5).
4. Nested procs with static link + moving stacks (done: P11).
5. Records, pointers, arrays, strings (done: P4).
6. Classes / `of object` (done: P12, P26).
7. Generics, `try`/`except` on the G (done: P13, P10).

All seven are done.

**Still out of the product (not Pascal features):** C FFI for now,
Windows, macOS, 32-bit. The collector (P95, `GC.md`, decided
2026-09-26) exists: it scanned stacks conservatively first (1.0.58) and
reads compiled frames by the stack maps the compiler writes at every
call since 1.0.60 (P95c), the runtime's own frames word by word. The
heap never moves, so a conservative word can only keep a block alive.

`threadvar` is not in the language (a syntax error): a routine is not
tied to an M. `try`/`except` = per **G**.
