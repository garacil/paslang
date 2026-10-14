# Kernels: one body per machine, written once

Every hot routine that a processor extension does better than the base
instruction set is written **once per machine** as a kernel with a fixed
contract, read from the manual and from Go, validated against an oracle,
and reused from then on. The program is compiled for a processor set
(`-cpu`, `paslangc --help flags`): the compiler calls the `Cpu` body or
the `Base` body of a word, and writes `popcnt`, the AVX2 vectors or the
SSE2 ones, directly. **Nothing is tested at run time**; a binary compiled
for a processor the machine is not dies with an illegal instruction, as
with `-march=native`. `-cpu base` compiles the base paths and `make check`
runs the tests both ways on both machines.

A unit chooses its kernels where it is compiled. So every installed unit
is built twice (P143): for the base processor, and for one level of each
machine, x86-64-v3 (`v3`) and ARMv8.2 with crypto (`v8.2+crypto`), in a
directory of that name beside the base build. A program whose `-cpu` has
every feature of the level links the level's objects; the interfaces are
the same. A unit's `UpCase` of a string calls `PasUpperCpu` in a program
compiled `-cpu native` on an AVX2 machine and `PasUpperBase` under `-cpu
base`, as Go compiles every package at the program's `GOAMD64`.

The manuals: Intel's Software Developer's Manual and Arm's Architecture
Reference Manual (what each instruction does), Intel's optimization
manual, AMD's software optimization guide for family 19h and Arm's for
Neoverse N2 (what is fast on the machines we have: branch cost, loop
streams, unrolling, alignment). The kernels follow Go 1.23's assembly
for each machine (its license is in `LICENSE-GO`);
`scripts/asm_from_go.py` turns Go's arm64 syntax into GNU's.

| Kernel | What | Extension (`-cpu` name) | Base path | Test and oracle | Where |
|---|---|---|---|---|---|
| `Sha256BlocksCpu` | SHA-256 and SHA-224 rounds, N blocks, at most 1024 a call from `Sha256OfCpu` (P270) | amd64 SHA-NI with SSSE3 and SSE4.1 (`sha2 ssse3 sse41`: PSHUFB, PALIGNR, PINSRQ, PBLENDW, as Go's gate; no VEX moves, so no AVX); arm64 FEAT_SHA256 (`sha2`) | `Sha256BlocksPlain`, the 64 rounds written out | `testdata/hash1` against `scripts/hashmodel.py` (Python hashlib), FIPS 180-4 vectors | `src/lib/pashash.paslang`, after Go's `sha256block_{amd64,arm64}.s` |
| `Sha1BlocksCpu` | SHA-1 rounds, at most 1024 blocks a call from `PasSha1Cpu` (P270) | amd64 SHA-NI with SSSE3 and SSE4.1 (`sha1 ssse3 sse41`: PSHUFB, PINSRQ, PINSRD); arm64 FEAT_SHA1 (`sha1`) | `Sha1BlocksPlain`, 80 rounds written out | `hash1` | `pashash`, after `SHA1RNDS4`, `SHA1NEXTE`, `SHA1MSG1` and `SHA1MSG2` in the SDM vol. 2B (Go 1.23 has no SHA-NI body for SHA-1) and Go's `sha1block_arm64.s` |
| `Sha512BlocksCpu` | SHA-512 and SHA-384 rounds, at most 512 blocks a call from `Sha512OfCpu` (P270) | arm64 FEAT_SHA512 (`sha512`); amd64 none (no processor here answers for its SHA512 extension) | `Sha512BlocksPlain`, 80 rounds written out | `hash1` | `pashash`, after Go's `sha512block_arm64.s` |
| `Crc32cCpu`, `Crc32cTriple` | CRC-32C (Castagnoli), at most 64 KiB a call (P270) | amd64 SSE4.2 `crc32` (`sse42`), three chains at once over pieces of 1344 and 168 bytes joined by shift tables built at first use (Go's `castagnoliSSE42Triple`, 33 GB/s here; a PCLMULQDQ fold with Castagnoli's constants gave 18 and was dropped); arm64 FEAT_CRC32 (`crc32`) | the 256-entry table | `hash1` against RFC 3720's definition | `pashash`, after Go's `crc32_{amd64,arm64}.s` and `crc32_amd64.go` |
| `Crc32Cpu` | CRC-32 (IEEE, zlib), at most 64 KiB a call, the last piece keeping the 64 bytes of the folding (P270) | amd64 PCLMULQDQ folding (`pclmul`, `sse41`), 64 bytes and up; arm64 FEAT_CRC32 (`crc32`) | the table | `hash1` against zlib | `pashash`, after Go's `ieeeCLMUL` and Intel's paper on PCLMULQDQ CRC |
| `rt_xxh3` long path | XXH3 over 1 KiB blocks (maps, `XxHash3`), with rt_yieldpoint every 256 blocks (P271) | amd64 AVX2 (`avx2`); arm64 NEON, part of the base (one body, no choice) | the SSE2 stripes | `testdata/xxh3` against xxhash 0.8 | `src/compiler/pasemit.paslang`, `EmitXxh3X86` and `EmitXxh3Arm` |
| `PopCount` | bits set | `popcnt` | the SWAR count | `testdata/bitwords` | `pasemit`, `uoPopCnt` and `rt_popcntmem` |
| `PasUtf8BlocksCpu` | UTF-8 checked 64 bytes a block (RFC 3629, and I-JSON's noncharacters, RFC 7493 2.1): JSON's strings, SysUtils' strict encodings | amd64 AVX2 (`avx2`): simdjson's lookup4, `vperm2i128` and `vpalignr` for the bytes one to three back, three `vpshufb` nibble tables ANDed, `vpsubusb` for the third and fourth bytes, a block of ASCII by `vpmovmskb`; arm64 NEON, part of the base: `ext`, `tbl`, `uqsub`, `umaxv` | `PasUtf8BlocksBase`: SSE2's ASCII skip 64 bytes a step (four `movdqu`, `por`, one `pmovmskb`) then 16 with `bsf`, and Go's `utf8.Valid` automaton in compares (`Utf8ScanBase`); `PasUtf8Plain` the reference; `PasUtf8Valid` finds the exact byte with it and reads the tail through a padded block; `PasUtf8Valid` and `PasUtf8Feed` give either kernel at most 1024 blocks (64 KiB) a call, `Prev` carried between them, so the routine can be stopped between two (P269) | `testdata/utf8kern` (45 classes at every place of every length to 70 and around two blocks, four fillers, both modes, in three pieces: 1,144,832 cases; at the end of a page whose next is unmapped; and six classes around each edge of the slices of 64 KiB in texts of 200,000 bytes) native, base, arm64 max and base, against `scripts/utf8kern_model.py` (Python's strict decoder); `testdata/utf8slice` (a routine of 1 ms runs inside two calls of 256 MiB on one processor) | `passtr`, after simdjson 5.0.3's `utf8_lookup4_algorithm.h` and Go's `unicode/utf8` |
| `PasJsonIndexCpu` | JSON's structural scan, 64 bytes a block (P202, after simdjson 5.0.3's stage 1): each byte's class by two nibble tables (a comma, a colon, a bracket or brace, a space, a tab, line feed or carriage return, a control byte, an opening bracket or brace; exact, where simdjson's take 0Ch, 1Ah or FFh for operators too), the escaping backslashes by the borrow over the odd bits, the bytes inside strings by a prefix XOR of six shifts, the scalars' first bytes; the index (every quote, every operator and scalar start outside a string, every escaping backslash and control byte inside one) and the counts of the document's values, scalars and bytes | amd64 AVX2 with BMI1 and POPCNT (`avx2 bmi1 popcnt`, the x86-64-v3 build): two `vpshufb` for the class, `vpcmpeqb` and `vpmovmskb` for six masks, `andn`, `popcnt`, the index by `tzcnt` and `blsr` eight places a step (Zen 2: `andn` and `popcnt` one operation, `tzcnt` and `blsr` two, `shld` microcode, so a mask's carry is a shift and an or); arm64 NEON, part of the base: two `tbl`, `cmeq`, `cmtst`, `cmlt`, each mask by the AND of its bits' weights and three `addp`, two masks a register, the prefix XOR by `eor` with a shifted register, `cnt` and `uaddlp` for the counts into 64-bit lanes, `rbit` once and `clz` for the index | `PasJsonIndexBase`: SSE2's `pcmpeqb` per character (brackets and braces after an OR with 20h), `pminub` for control bytes, four `pmovmskb` a mask, counts by halves (SWAR), `bsf`; `PasJsonIndexPlain` | `testdata/jsonkern`: every length to 300 at every place to 63, two offsets (one near 2^32), the kernels in two calls; patterns across the blocks' edges (runs of backslashes and quotes across bit 63), outside and inside a string; a text that ends at an unmapped page; Plain against `scripts/jsonkern_model.py` (the definitions); native, base, arm64 max and base | `src/lib/pasjson.paslang` |
| `PasJsonEscIndexCpu` | the first byte of a string that JSON writes escaped: a quote, a backslash, a byte below 20h and, for HTML, `&`, `<`, `>` (P202); at most 64 KiB a call from `PasJsonEscIndex` (P270) | amd64 AVX2 with BMI1 (`avx2 bmi1`): two `vpshufb` of nibble tables, `vptest` 32 bytes a step from the string's start rounded down to 32, `vpcmpeqb`, `vpmovmskb` and `tzcnt` for the place; arm64 NEON: two `tbl`, `umaxv` 16 bytes a step, `cmtst` and `shrn` by 4 into a syndrome, `rbit` and `clz`; aligned blocks never cross a page, what lies outside the string is dropped | `PasJsonEscIndexBase`: SSE2's `pcmpeqb` and `pminub` 16 bytes a step, the HTML bytes ANDed with a mask of the mode, `bsf`; `PasJsonEscIndexPlain` | `testdata/jsonkern`: every length to 200 at every place to 63, both modes; every byte at every place of a string; strings that end at an unmapped page and that begin after one | `pasjson` |
| `TrailingZeros`, `LeadingZeros` | the zeros below the lowest 1 and above the highest, the width for 0 | amd64 BMI1 `tzcnt` (`bmi1`) and `lzcnt` (`lzcnt`), which count a zero's width themselves (P261): `tzcnt` 2 ops of latency 2 against `bsf`'s 6 of latency 3 on Zen to Zen 3, the same as `bsf` on Zen 5 and Skylake; `lzcnt` 1 of latency 1 against `bsr`'s 6 of latency 4 (AMD's latency tables, Intel 336289-001); arm64 `rbit` and `clz`, part of the base | `bsf` over a sentinel bit, `bsr` with a `cmov` for 0 | `testdata/bitwords`, `testdata/cputune` (the `.s` of each processor) | `pasemit`, `EmitBitUn` |
| `V256` words | 32-byte vectors | AVX2 (`avx2`); `VShuffle8` SSSE3 (`ssse3`) | two SSE2 halves | `testdata/vectors`, `vecmore`, `vecpool` | `pasemit`, `EmitVecStmt` |
| Sets of 32 bytes | `+ - *` of two sets of up to 256 elements, `=`, `<>`, and `<=` and `>=` as subset tests; a set made one of another range | amd64 AVX2 (`avx2`): one `vpor`, `vpand`, `vpandn`, and `vptest` whose CF says the subset; SSE4.1 (`sse41`) `ptest` for the subset; arm64 NEON, part of the base (`orr`, `and`, `bic`, `eor` on two q registers) | two SSE2 halves, `pcmpeqb` and `pmovmskb` for the tests | `testdata/set256` against Free Pascal 3.2.2, native, `-cpu v2` and `-cpu base`, arm64 `max` and `base` | `pasemit`, `EmitSetBin`, `EmitSetConv` |
| Set walk and words | `for x in s`, the next element; `x - y` and the subset of sets of one word | BMI1 (`bmi1`): `tzcnt` and `blsr`, `andn` (whose ZF is the subset test); arm64 `rbit` and `clz`, part of the base | `bsf`, and `lea` and `and`; `not` and `and` | `testdata/set256`, as above | `pasemit`, `EmitSetFor`, `EmitSetBin` |
| `PasIndexByteCpu` | the first place of a byte in a run of bytes: `Pos` of a `Char`, and of a string the next first byte; at most 64 KiB a call from `PasFindByteCpu` (`IndexByte`) and `Pos` (P270) | amd64 AVX2 (`avx2`): `vpbroadcastb`, `vpcmpeqb` and `vptest` 32 bytes a step, `vpmovmskb` and `bsf` for the place; arm64 NEON, part of the base: `cmeq` over 32 aligned bytes and a 64-bit syndrome, `rbit` and `clz` | `PasIndexByteBase`: SSE2's `pcmpeqb` and `pmovmskb` 16 bytes a step, a run under 16 read in one load that stays in its page; `PasIndexBytePlain` the reference | `testdata/strkern` (every length to 160, every alignment to 33, ending at a page's end, against the Pascal body), `strwords` against Free Pascal 3.2.2 | `src/lib/passtr.paslang`, after Go 1.23's `indexbyte_amd64.s` and `indexbyte_arm64.s` |
| `PasMemEqCpu` | two runs of bytes equal: `Pos`'s check of the rest of a match, at most 64 KiB a call (a longer needle a slice at a time, P270) | amd64 AVX2 (`avx2`): two `vpcmpeqb` over 64 bytes a step; arm64 NEON: 64 bytes compared as words, then `ldp` 16 at a time | `PasMemEqBase`: SSE2's four `pcmpeqb` over 64 bytes, then 8 bytes a step and one load for the last 8; `PasMemEqPlain` | `testdata/strkern`, `strwords` | `passtr`, after Go 1.23's `equal_amd64.s` and `equal_arm64.s`; `Pos`'s search is written once for each body, `IndexOfCpu` and `IndexOfBase`, each calling its own kernels, so a program for the base links no AVX2 kernel (P268; `scripts/check_cpubin.py`) |
| `PasCmpByteCpu` | `CompareByte(a, b, n)`: the difference of the first bytes that differ (SysUtils' `CompareStr` and `CompareMem`); at most 64 KiB a call from `PasCompareByteCpu`, `CompareStr` and `CompareMem` (P270) | amd64 AVX2 (`avx2`): `vpcmpeqb` over 64 bytes a step, then 32, the last 32 read ending at the end, the equal mask inverted by `xor` (`not` sets no flag) and `bsf` for the place; arm64 NEON, part of the base: `cmeq`, `not`, `shrn` by 4 into a 64-bit syndrome of four bits a byte, `rbit` and `clz` | `PasCmpByteBase`: SSE2's `pcmpeqb` 16 bytes a step, the last 16 ending at the end; under 16 two 8-byte words and `bsf` of their `xor`, under 8 a byte at a time; `PasCmpBytePlain` | `testdata/strkern` (every length to 200 at every alignment of both runs, a byte above and below at each place, ending at a page's end, counts below 1) native, base, arm64 max and base; `cmpwords` against Free Pascal 3.2.2 | `passtr`, after Go 1.23's `compare_amd64.s` and `compare_arm64.s`, the place of the difference kept |
| `PasCaseCmpCpu` | SysUtils' `CompareText`, `SameText`, `AnsiCompareText`: the difference of the first bytes that differ once the ASCII letters of both runs are capitals; at most 64 KiB a call from `CompareText` (P270) | amd64 AVX2 (`avx2`): both 32-byte blocks made capitals as `PasCaseMap` makes them (`vpsubb`, `vpminub`, `vpcmpeqb`, `vpand`, `vpxor`), then `vpcmpeqb`, `vpmovmskb` inverted by `xor` and `bsf`, the last 32 read ending at the end; arm64 NEON, part of the base: `sub`, `cmhi` against 26, `and`, `eor`, then `cmeq`, `not`, `shrn` and `rbit`, `clz` | `PasCaseCmpBase`: the same on SSE2, 16 bytes a step; under 16 a byte at a time; `PasCaseCmpPlain` | `testdata/strkern` (bytes around the letters' ranges, the other run's case changed at random, a byte that differs as a capital at each place, every length and alignment) native, base, arm64 max and base; `sysutils1` against Free Pascal 3.2.2 | `passtr`; SysUtils chooses it with `{$ifdef CPU_AVX2}` (P148), so its level build takes the AVX2 body |
| `PasCaseMapCpu` | `UpCase` and `LowerCase` of a string: its ASCII letters' case bit flipped, at most 64 KiB a call (P270) | amd64 AVX2 (`avx2`): `vpsubb`, `vpminub` and `vpcmpeqb` mark the letters, `vpand` and `vpxor` flip bit 32, 32 bytes a step; arm64 NEON: `sub`, `cmhi`, `and`, `eor`, 16 a step | `PasCaseMapBase`: the same on SSE2, 16 bytes a step; `PasCaseMapPlain` | `testdata/strkern`, `strwords` | `passtr` |
| `rt_streq`, `rt_strcmp` | string `=` and `<>`, and `<`, `<=`, `>`, `>=` (the first differing byte, then the length), a chunk of 256 KiB at a time with rt_yieldpoint between two (P271) | amd64 AVX2 (`avx2`): `vpcmpeqb` 64 bytes a step, `vpmovmskb` and `bsf` (`tzcnt` on BMI1, P261) for the first difference, the highest differing bit of the last 8 bytes by `bsr`, or `63 - lzcnt` where the processor tuned for has it cheaper (`-tune`, Zen to Zen 3); arm64 NEON, part of the base: 64 bytes compared as words (`v16` on, no callee-saved register), `ldp` 16 at a time, `rev` to order the first differing word | SSE2's `pcmpeqb` 16 or 64 bytes a step, 8 a step and one load for the last 8, under 8 one load of each that stays in its page (the emitter writes the one `-cpu` asks for into the runtime) | `testdata/strcmpk` (every length to 150, equal, prefixes, a byte above and below at each place, 0 and 255) native, `-cpu v2`, base, arm64 max and base | `src/compiler/pasemit.paslang`, `EmitRuntime` and `EmitRuntimeArm`, after Go 1.23's `equal_*.s` and `compare_*.s` |
| `rt_fill`, `rt_fillbig` | `FillChar`, a zero value from 64 bytes, a large block made ready (P271, P272) | arm64 NEON, part of the base: `dup` of the byte into v31 (Arm ARM C7.2.41), `stp` of two Q registers 32 bytes a store, four a loop over 128 bytes as the Neoverse V2 and N2 guides write memset, the head and the tail by stores that overlap and end at the end; amd64 `rep stosb` (ERMS) | none on arm64 (NEON is the base); a frame's words by `stp xzr` pairs | `testdata/fillkern` (every length to 300 at every place to 63 with the bytes around untouched, lengths about the 128-byte step and the 256 KiB pieces, zero values of 8 to 520 bytes, frames of 17 to 41 words) on both machines and processors | `src/compiler/pasemit.paslang` (the runtime), after Go's `memclr_arm64.s`; zeros of 256 bytes and more by DC ZVA, two a loop, when `-cpu` names an Arm core (its TRM: a 64-byte block), the size checked at start (P273, `fillkern` under QEMU's `-cpu neoverse-n1` and `neoverse-v1`, and a stop on `a64fx`) |

Currency's checked arithmetic reuses `pasfmt`'s existing `Mul128` and
`DivMod128` pair: exact signed magnitudes, one scale adjustment and one
nearest-even rounding. Decimal parse/format and binary64/binary128 conversion
use its common exact big-integer/IEEE helpers, not another assembly
implementation. `scripts/check_currency.py` supplies an
independent rational oracle for 11,005 cases, exercised for both raw kernels
and typed language/SysUtils paths on both machines and CPU selections.

The scheduler's G-state CAS has one arm64 emitter kernel, `ArmGStatusCas`
in `pasemit`: address x9, expected w1, new w2, observed w3 and exclusive
status w4. Ready, park, park-unlock and IO park reuse it. `-cpu` with
`atomics`/`lse` chooses `CASAL`; the ARMv8.0 base uses `LDAXR`/`STLXR`.
Both acquire an early wake and release transferred values/saved contexts,
after current Go's `atomic_arm64.s`; there is no runtime feature branch.
The debugger gate decodes all five sites, and concurrency/GC gates run
both CPU paths. AMD64 already uses locked `CMPXCHG`.

Words with no kernel yet (the Pascal body serves every processor):
MD5 (no instruction exists), SHA-3 (arm64 FEAT_SHA3 could serve it),
Adler-32, FNV-1a, MurmurHash3, SipHash, the B+ tree and the heap. `Pos` searches as Go's `strings.Index` does, `IndexByte` and `MemEq` above and Rabin-Karp when the first byte keeps matching in vain; Go's brute-force `IndexString` for needles under 64 bytes is not taken, the search stays linear without it.

## Adding a kernel

1. Read the instruction in the manual and Go's routine for that
   machine; port it with the converter when it is arm64.
2. Write it as an `asm amd64` and an `asm arm64` block in the core unit,
   with the contract `(State, Data, N)` or `(Crc, P, N)`, and keep the
   Pascal body beside it. `pashash` is written by `scripts/hashgen.py`:
   change the template there and run it.
3. Export the word twice, `XxxCpu` and `XxxBase`; in the parser, choose by
   `CpuSuffix('<features>')`, naming every extension the body's
   instructions belong to (P196: the SHA-NI bodies also need SSSE3 and
   SSE4.1); `scripts/check_cpufeat.sh` proves the choice for a matrix
   of `-cpu`.
4. Give it at most 64 KiB a call from the words that call it, the state
   carried from one call to the next (P269, P270): an `asm` block is not
   preempted, and the loop head between two calls is where the routine
   can be stopped, for the collector or for another routine. A short
   run goes to the kernel at once past one compare, a longer one to a
   function with the loop: a loop's test, with its preemption check,
   costs every call (P270 measured 1 to 13 per cent on the string
   pairs with the loop on the way of every call). `testdata/kernslice`
   shows another routine running inside a long call, and fails when one
   call takes it all.
5. Add the oracle's vectors to the test and run it with `-cpu native`,
   `-cpu base` and, on arm64, `-cpu max` under qemu, with lengths that
   cross the edges of the slices (`testdata/longslice`).
6. Add the row above.

## Adding a hash word (a new algorithm)

Every algorithm of §13 of the manual went in this way; a new one
follows the same steps, in this order, and is not done until the last.

1. The algorithm is written from its standard's text, never from
   memory, and its test vectors come from it.
2. The Pascal body goes into the template of `scripts/hashgen.py`: the
   rounds written out (a loop only over the blocks), the
   entry point `PasXxx(const S: string): string` (a digest) or
   `...: Integer` (a checksum, with the value so far when the algorithm
   chains). A word with a kernel gets its `asm amd64` and `asm arm64`
   blocks beside the Pascal body, read from the manuals and Go's
   assembly (`scripts/asm_from_go.py` turns Go's arm64 syntax into
   GNU's), and two entry points from `variant()`, `PasXxxCpu` and
   `PasXxxBase`. Then `python3 scripts/hashgen.py` writes
   `src/lib/pashash.paslang`; the unit's text is what the compiler
   reads, so the script runs after every change.
3. The parser: the name joins `AddReserved` in `InitReserved`
   (`src/compiler/pasparse.paslang`), and the lowering beside the other
   hash words turns `Xxx(s)` into `CoreProc('PasXxx' +
   CpuSuffix('<feature>'), args, TyString)` (or `'PasXxx'` alone for a
   word with one body), checking the arguments and dying with plain
   words on the wrong ones. The feature names are those of
   `CpuFeatBit` in `pasast` (`sha1`, `sha2`, `sha512`, `crc32`,
   `sse42`, `pclmul`, `avx2`, …); every name in the space-separated
   list is needed, and a name no machine knows stops the compile (P196).
   A body for one machine names that machine's features: the SHA words
   go through `ShaSuffix`, `sha2 ssse3 sse41` on amd64 and `sha2` on
   arm64.
4. The model: `scripts/hashmodel.py` computes the word over the same
   inputs with Python's `hashlib`, `hmac`, `zlib` or the reference
   definition, and writes `testdata/hash1.out`; `testdata/hash1.paslang`
   prints the word over the standard's vectors, every length from 0 to
   300 bytes, and a long message. `make check` runs it on both
   machines, native and `-cpu base`, and requires the base build to
   call the `Base` body.
5. The words of the manual: the table in §13 (algorithm, what it
   gives, what it takes, the feature, what it is for), §20's list, the
   `lib` section of `paslangc --help` (`src/compiler/pashelp.paslang`,
   with the version raised), and a row in the table above
   when there is a kernel.

---

Copyright (C) 2026 Germán Luis Aracil Boned.

Permission is granted to copy, distribute and/or modify this document
under the terms of the GNU Free Documentation License, Version 1.3 or
any later version published by the Free Software Foundation; with no
Invariant Sections, no Front-Cover Texts, and no Back-Cover Texts. A
copy of the license is included in the file COPYING.DOC.
