# Benchmark comparisons

The goal is lower time and peak memory than each reference on equal work.
A failing comparison exits nonzero. Matching output, a single fast sample
or an old result does not establish an overall advantage.

The ordinary Go suite has 45 programs and 218 sections. Rust has 11 audited standard-library
twins covering 28 sections:
b1loop, b2str, b5map, b6smap, b7narrow, b8ptr, b10rot, b14sort, b24math,
b26slice and b31map. An explicitly requested unsupported Rust section is
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
current runtime; current 1.2.406 correctness, self-reproduction, SDK and
installation checks pass with that implementation unchanged. This records
existing performance evidence, not a new 1.2.406 timing run. The budgets are
unchanged. Rust integer-append losses remain open under P608.

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
`go1.27.3-X:nodwarf5` toolchain identified in reference_policy.py. Other
builds, including plain go1.27.3, require a new source and identity review.
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
assertion file that overrides this gate. The eleven audited Go peers used
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
Real correctness comparisons run all 28 sections on amd64 native/base and
arm64 under QEMU. QEMU results establish correctness, not native ARM speed.

Equal output does not prove equal memory-safety or HashDoS guarantees.
Rust ownership checks, runtime bounds checks and programmer obligations
are distinct contracts. Preserve those distinctions when explaining wins
or planning an optimization. Losses and ties remain visible work items.
