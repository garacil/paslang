# Benchmark comparisons

The goal is lower time and peak memory than each reference on equal work.
A failing comparison exits nonzero. Matching output, a single fast sample
or an old result does not establish an overall advantage.

The ordinary Go suite has 46 programs and 221 sections. Rust has 12 audited standard-library
twins covering 29 sections:
b1loop, b2str, b5map, b6smap, b7narrow, b8ptr, b10rot, b14sort, b24math,
b26slice, b31map and b44fma. The other 34 programs and 192 sections still
need audited Rust twins. An explicitly requested unsupported Rust section is
refused before building. It is never counted as a win.

## Recorded integer-append comparison

The [frozen 1.2.405 measurements](https://github.com/garacil/paslang/wiki/Benchmark-Results-P525-405)
recorded on 2026-11-13 meet P254's original Go acceptance. Each side appends
twenty million integers individually and reads every element for the sum;
each timed sample covers the complete program process, including setup,
allocation and any collection during execution.
Ratios below are paslang / Go on the recorded Ryzen 7 4800H host.

| CPU | Median paired time ratio | Time Q3 | Peak-RSS ratio | Time / memory budgets |
|---|---:|---:|---:|---|
| native | 0.712877 | 0.750116 | 0.574234 | 0.99 / 0.99 |
| base | 0.681668 | 0.703000 | 0.574465 | 0.99 / 0.99 |

Both profiles retain forty alternating rounds and five traced memory samples
per side, with exact output and clean statuses and diagnostics. P287's
existing class/frontier allocation fix is present in both the measured and
current runtime; the 1.2.406 baseline correctness, self-reproduction, SDK and
installation checks pass with that implementation unchanged. This records
existing performance evidence, not a new 1.2.406 timing run. The budgets are
unchanged. Rust integer-append losses remain open under P608.

## Recorded UInt32 hash comparison

The P548 measurements compare paslangc 1.2.407 with 1.2.406 and the reviewed
Go toolchain on a Ryzen 7 4800H. Each comparison has forty alternating
full-process pairs and five separate traced memory samples per side.
Native uses the host instructions and Go v3; base uses the existing
verified Go v1 capability policy. Sources, compilers, actual linked SDK
variants, executables and complete outputs remained unchanged.

Ratios below are candidate / previous release, or candidate / Go.
Q3 is the exclusive upper quartile of the forty paired time ratios.
The Go gate requires time and RSS ratios at most 0.99 and time Q3 below 1;
its seven failures remain failures under P232 and P248.

| CPU | Workload | New/old time | Q3 | New/old RSS | New/Go time | Q3 | New/Go RSS | Go gate |
|---|---|---:|---:|---:|---:|---:|---:|---|
| native | b9hash | 0.999627 | 1.005602 | 1.000000 | 1.003698 | 1.011885 | 0.371591 | FAIL |
| native | b20hash:md5 | 0.947292 | 0.951054 | 1.000000 | 1.024166 | 1.028459 | 0.389450 | FAIL |
| native | b20hash:sha1 | 1.000453 | 1.003005 | 1.000000 | 0.993448 | 0.996649 | 0.390572 | FAIL |
| native | b20hash:crc32 | 1.000366 | 1.004663 | 1.000000 | 1.001705 | 1.006118 | 0.385475 | FAIL |
| native | b20hash:adler32 | 1.000216 | 1.003817 | 1.000000 | 0.716076 | 0.722898 | 0.392817 | PASS |
| base | b9hash | 0.917264 | 0.919200 | 1.002994 | 1.208625 | 1.211196 | 0.373884 | FAIL |
| base | b20hash:md5 | 0.948561 | 0.950913 | 0.997183 | 1.025452 | 1.029601 | 0.395531 | FAIL |
| base | b20hash:sha1 | 0.837102 | 0.839450 | 0.997191 | 0.753035 | 0.754810 | 0.390110 | PASS |
| base | b20hash:crc32 | 1.003396 | 1.006669 | 0.997167 | 1.386537 | 1.388617 | 0.383442 | FAIL |
| base | b20hash:adler32 | 0.998655 | 1.003920 | 0.997207 | 0.717701 | 0.723832 | 0.392308 | PASS |

The base SHA-1 workload takes about 16% less time than the previous release;
the combined b9hash workload takes about 8% less, and MD5 about 5% less
on both CPU profiles. b9hash includes 64 SHA-256 and 256 CRC-32C passes
over 1 MiB; its improvement cannot be attributed to SHA-256 alone.
The IEEE CRC workload shows no runtime improvement here despite fewer
loop instructions. Base b9hash retains about 0.3% more peak RSS; the
other base workloads retain slightly less and native RSS is unchanged.
The unchanged Adler-32 control and native hardware paths remain visible.
These results do not establish an overall advantage over Go or Rust;
there is no audited Rust twin for these hash programs.

[Full results and protocol](https://github.com/garacil/paslang/wiki/Benchmark-Results-P548-407)
include every round, output, memory sample and strict verdict.
The [raw record](https://raw.githubusercontent.com/wiki/garacil/paslang/benchmark-results-p548-407.json)
has SHA-256 `c178141c3dea28251fb0fed57e574ecbca12c828334db25f6668a8927a4d36d5`.

## Recorded FMA comparison

The historical P602 measurements use an unpublished paslangc 1.2.408 candidate, Go 1.27.3-X:nodwarf5 and Rust
1.99.1 on the Ryzen 7 4800H. Every row evaluates sixteen fused Horner steps
at thirty million points and accumulates the results in order. Every complete
output is `4737506260561199801` followed by a newline. Forty alternating
process pairs and five separate traced RSS samples per side give 400 timed
executions and 50 memory executions across these five comparisons.

Ratios are paslang / reference; Q3 is the exclusive upper quartile of the
forty paired time ratios. The gates remain time and RSS at most 0.99, with
Q3 below 1. Both Go rows pass. All three Rust rows fail time and Q3 while
passing memory; those gaps remain open under P613.

| Reference/provider | CPU | Time ratio | Q3 | Peak-RSS ratio | Gate |
|---|---|---:|---:|---:|---|
| Go | native | 0.987872 | 0.997571 | 0.121377 | PASS |
| Go | base | 0.914949 | 0.919747 | 0.107584 | PASS |
| Rust musl | native | 2.693034 | 2.716505 | 0.720430 | FAIL |
| Rust musl | base | 1.378774 | 1.384112 | 0.559633 | FAIL |
| Rust GNU | native | 2.667997 | 2.685876 | 0.112605 | FAIL |

Native uses the host's FMA instructions and Go v3. Base pairs the compiled
Paslang software path with the reviewed Go v1 software path or the proved
static musl software provider. GNU keeps its ordinary native provider;
GNU base FMA remains outside the reviewed baseline evidence. These are
focused FMA results, with the other benchmark workloads retaining their
own measurements and pending targets.

The original comparison coordinator stopped after its two valid Go rows
because its post-run validator used the wrong section budget key. The
separate retained-data proof preserves that failed record and certifies the
Go rows against unchanged measured inputs, binaries and every Go selection.
A fresh corrected coordinator measured all three Rust rows. The complete
records preserve both intervals, all raw outputs and strict verdicts.

[Full results and protocol](https://github.com/garacil/paslang/wiki/Benchmark-Results-P602-408)
include every paired round and memory sample. The
[raw record](https://raw.githubusercontent.com/wiki/garacil/paslang/benchmark-results-p602-408.json)
has SHA-256 `ff712e6ba0915b270020ca28fdd0b6a3c406a7da46d692db439f258d482e8b92`.

These are retained prototype measurements, not a new run of the current
release. They do not establish an overall runtime advantage.

## Go

Review the host and operating-system CPU capabilities, then set the highest
supported GOAMD64 level explicitly. For a reviewed v3 host:

~~~sh
make bench BENCH_GO_NATIVE_LEVEL=v3
make bench-rounds BENCH_GO_NATIVE_LEVEL=v3
~~~

Both use the full Go suite. Select programs with BENCH_PAIRS and references
with BENCH_REFERENCE=go,rust. Set BENCH_CPU=native or base for one profile;
the default covers both. Compiler measurements use a fresh generated nonce
every round and record executable sizes alongside build time.

Compiler processes keep their ordinary host CPU capabilities. Target flags
select the generated program's CPU profile; the Go base runtime mask applies
only when that program executes. Build and execution environments are recorded
separately, so targeting a baseline CPU does not throttle the Go compiler.

The reviewed Go reference is the exact Linux/amd64
`go1.27.4-X:nodwarf5` toolchain identified in reference_policy.py. Other
builds, including plain go1.27.4, require a new source and identity review.
The full Go source, assembly headers and compiler tools enter the reuse
fingerprint. GOENV is disabled, inherited CPU overrides are removed and
GOEXPERIMENT is cleared while retaining the reviewed embedded defaults.

Each invocation builds a fresh metadata probe before measurement. It reads
all 36 internal CPU booleans and raw CPUID, and initializes net/http so both
Go CPU parsers run. Native keeps ordinary detection. Base uses GOAMD64=v1
and cpu.all=off, restoring ERMS only when independently detected. Hosts
with FSRM or uncontrolled optional ISA fields cannot currently receive a
baseline comparison. The effective state and silent startup are checked;
unsupported baseline configurations fail before timing. Only CPUID's
logical-CPU APIC identifier is excluded from stable capability identity;
raw observations remain available.

Each actual Go executable also receives an ELF/provider check. Base
currently requires a static executable without PT_INTERP, DT_NEEDED or
PT_DYNAMIC. External loaders and C libraries require separate reviewed
startup/IFUNC evidence. Native keeps ordinary linkage, and CGO defaults
stay unchanged. Refused comparisons retain artifact metadata and their
reason in JSON; they are missing evidence, never speed wins. There is no
assertion file that overrides this gate. The twelve audited Go peers used
for the Rust comparison are static; this does not certify every program
in the full Go suite.

To prepare and inspect the same capability discovery directly:

~~~sh
python3 -I -c 'import json,shutil,sys; sys.path.insert(0,"scripts/bench"); from reference_policy import prepare_go_capabilities; print(json.dumps(prepare_go_capabilities(shutil.which("go"),"build/bench/go-capabilities"),indent=1))'
~~~

The discovery directory retains raw command, environment, binary, source
and process-cleanup evidence. Its supervisor has a deadline and owns only
that command's descendants. A failed or forced cleanup invalidates the
discovery. No probe runs inside a workload or compiler timing sample.

## Rust

Use a compiler and matching standard-library components. Put that compiler
on PATH before invoking Make. An explicit sysroot does not make a different
distribution's compiler metadata compatible.

BENCH_RUST_TARGET selects the target triple, BENCH_RUST_SYSROOT selects its
matching standard library, and BENCH_RUST_PROVIDER identifies gnu or musl.
Those inputs and their content fingerprints are retained in JSON and
artifact reuse records.

An ordinary GNU native comparison is:

~~~sh
make bench-rust BENCH_CPU=native \
  BENCH_RUST_TARGET=x86_64-unknown-linux-gnu \
  BENCH_RUST_SYSROOT=/path/to/matching/sysroot \
  BENCH_RUST_PROVIDER=gnu
~~~

Use make bench-rust-rounds with the same configuration for 40 alternating
rounds. GNU-native remains an ordinary, unmasked reference. A musl
native/base series is separate from GNU; their results are never merged
into one native/base series.

Baseline performance requires retained linked-program ISA/provider evidence,
selected with BENCH_RUST_CAPABILITY_PROOF. Merely using target-cpu=x86-64,
a musl target, a successful run on a newer CPU, or
RUST_STD_DETECT_UNSTABLE does not certify precompiled std, compiler-builtins,
libm, libc or their dispatch paths. Missing evidence fails before timing.

Prepare portable candidate evidence from retained files with:

~~~sh
python3 scripts/bench/reference_caps.py \
  --rustc /path/to/matching/sysroot/bin/rustc \
  --rust-sysroot /path/to/matching/sysroot \
  --binary /path/to/compiled-musl-base-program \
  --evidence correctness=/path/to/correctness.json \
  --evidence isa=/path/to/reviewed-disassembly.txt \
  --evidence provider=/path/to/provider-provenance.txt \
  --prepare-proof /path/to/base-proof.json
~~~

This inspects linkage and text against the fixed reviewed policy; it leaves
all review checks false. Review the retained correctness, ISA and provider
evidence before marking those checks true. Unknown optional instructions
and unreviewed REP-BSF contexts are refused. A supplied JSON assertion
cannot widen the fixed CPU-discovery or instruction-context exceptions.
The benchmark scans and binds each actual linked executable, including
fresh generated compiler-probe nonces, before any baseline timing.

Rust uses opt-level=3, default randomized HashMap hashing and ordinary
destruction. String-map keys borrow stable prebuilt strings; inserts do not
clone String values. Pointer workloads use safe ownership and iterative
list destruction, whose work remains timed.

## Fused multiply-add capabilities

The b44fma pair evaluates the same sixteen-term Horner polynomial at thirty
million points and accumulates the results in order. Paslang uses `Fma`, Go
uses `math.FMA`, and Rust uses `f64::mul_add`; the complete output must match.
A multiply followed by an add is insufficient because it rounds twice.

Every b44 executable receives a linked-code check before timing. Paslang
base must contain no optional FMA instruction; native must select the path
supported by the observed host. The Go base CPU mask must select its pure
software fallback, while a native FMA host must reach hardware FMA. Rust
musl base requires both the fixed linked-program ISA proof and proved calls
to its static software FMA provider. Native Rust must reach hardware FMA
on an FMA host. A GNU base executable with an optional dispatch path is
refused before measurement. Provider identity and retained disassembly
remain bound to the actual executable.

A Rust-only b44 native run also requires the reviewed Go toolchain for an
untimed CPU probe. This supplies an independent host capability observation;
it does not run Go as a timed reference. A Rust-only base run does not need
that probe. The usual Go native-level option is required when Go itself is
a selected native reference. Probe setup and code inspection stay outside
all workload timing samples.

The compiled-target FMA policy applies even on a host with FMA. It was first
validated in the held 1.2.408 candidate; earlier implementations could dispatch
to hardware. Comparing those binaries directly does not compare equal CPU
capabilities. This suite checks the actual selected path rather than accepting
a target flag as evidence.

## Evidence and tests

run.py and rounds.py retain every requested round, full stdout including trailing
newlines and non-UTF8 bytes, stderr, statuses, timeouts and memory failures.
Every sample must finish successfully with empty stderr. CPU warnings with
status zero invalidate the sample. Time and memory samples alternate execution order. A failed early round
cannot disappear behind a later successful round. Forty-round comparisons
also require the upper quartile below 1; all existing time/memory budgets
remain strictly below 1.

Peak memory is the process's VmHWM at its traced exit, with transparent
huge pages disabled. A separate sampler consumes SIGCHLD through signalfd
and promptly forwards delivery signals, including Go's preemption signals.
The caller's signal handlers, mask, timers and wakeup descriptor stay intact.
Setup, exec and execution share a deadline; cleanup is bounded separately.
Timeouts, observer failures and leftover descendants invalidate the sample.
The helper requires a single-threaded caller and a reviewed GNU libc ABI.
Timed runs remain separate from traced memory samples.

JSON identifies compiler versions/bytes, CPU configuration, flags, source
and linked-library contents, provider and executable identity. Reusing a
stale artifact fails. Report generation keeps Go and Rust columns separate
and preserves legacy records without inventing missing Rust observations.

Normal make check runs deterministic compiler-free harness, tracer, Go
policy/process-scope, Rust capability and compiler-report checks. Their stubs use synthetic timing values only to
test verdicts and failure accounting; they are never performance evidence.
Real correctness comparisons run all 29 sections on amd64 native/base and
arm64 under QEMU. QEMU results establish correctness, not native ARM speed.

Equal output does not prove equal memory-safety or HashDoS guarantees.
Rust ownership checks, runtime bounds checks and programmer obligations
are distinct contracts. Preserve those distinctions when explaining wins
or planning an optimization. Losses and ties remain visible work items.
