# The heap, and the collector for P95

Part 1 is measured (2026-09-26, paslangc 1.0.52 against Go 1.27.1 on the
development machine, a Ryzen 9 5950X with 32 threads). Part 2 is the
design, decided on 2026-09-26: conservative stacks first and precise
maps as the second step (D1 B), typed pointer bitmaps with `GetMem`
conservative (D2), stop the world (D3), `PASLANG_GC=100` (D4), and the
steps P95a to P95d (D5). The goal is to be better than Go in
everything, memory included, not only equal.

## 1. Why a paslang program held more memory than Go's (1.0.52)

### The allocator before P95 (1.0.52)

`rt_alloc` rounded a request up to 8 bytes. A block of up to 4 KB came
from a 64 KB bump region of the running P (P+2120 next, P+2128 end,
P94); a larger one, and every refill of a region, came from the shared
heap, which grew in mappings of at least 16 MiB (`rt_maptot` counts
them). A block had no header and no type: the runtime could not tell the
bytes of a string from the pointers of a record. **Nothing was ever
given back.** `FreeMem` compiles to nothing (it still does), a
destructor freed nothing, and at 256 MiB mapped `rt_dieoom` stopped the
program. Routine records and stacks were recycled (P92, P98); the heap
was not. Section 2 and "Where it stands" tell what replaced it.

So the resident memory of a paslang program was everything it ever
allocated, while Go's is what is still reachable plus the headroom its
collector allows before the next cycle (the heap may grow to twice the
live heap, with a 4 MB minimum; `GOGC=100`).

### b2str: every temporary string is kept

Three million iterations of `s := 'item-' + IntToStr(i)`.

| | paslang | Go |
|---|---|---|
| blocks allocated | 6 000 000 (`IntToStr` 8 B, the concatenation 8 or 16 B) | 3 000 239 |
| bytes allocated | ≈ 69 MiB | 23.2 MiB |
| collections | none | 7 |
| heap at the end | ≈ 69 MiB (4 mappings of 16 MiB full, 3.9 MiB of the fifth) | 1.1 MiB live, 4 MB goal |
| peak resident | 73 MB | 12–14 MB |

Everything paslang allocates stays. Go allocates half as much, because
its compiler sees that the concatenation does not escape (`-gcflags=-m`:
`"item-" + ~r0 does not escape`) and builds it in a 32-byte buffer on the
stack (`tmpStringBufSize` in `runtime/string.go`); what it does allocate
dies at once and seven cycles take it back.

### b5map: every outgrown table is kept

A million integer keys inserted, then read. `pasmap` (1.0.52) doubled
its table when it filled to 7/8 and moved the entries into the new one;
the old table was "left in place for loops that started on it", and
nobody freed it (1.0.59 replaced this with Go's table split, below).

| | paslang | Go |
|---|---|---|
| tables allocated | 8 of 272 KiB … 34 MiB, doubling (67.7 MiB) | the same work, 72.7 MiB in total |
| collections | none | 8 |
| live at the end | 34 MiB (the last table: 2 097 152 slots, 1 000 000 used; the entries themselves are 15.3 MiB) | 34 MB |
| peak resident | 73–75 MB | 52–54 MB |

Both allocate about the same. The difference is the 33.7 MiB of the seven
outgrown tables, which Go's collector frees. Go also grows differently:
its map is a directory of tables of at most 1024 slots
(`maxTableCapacity`, `internal/runtime/maps/table.go`) that split one at a
time, so a growth step is at most about 17 KB, while ours holds the old
17 MiB table and the new 34 MiB one at the same moment.

### p1alloccap: the program dies

The same loop as b2str, twenty million times: `paslang: out of memory:
256 MiB mapped` after 0.29 s, at 259 MB resident. Go runs it to the end
in 12 MB.

### The three causes, in order

1. **No reclamation.** All of b2str's excess (69 MiB kept against a 4 MB
   heap goal), and in b5map the 33.7 MiB of outgrown tables (the
   resident gap is 21 MB, because Go's peak carries its own headroom
   until the next cycle). This is P95.
2. **Temporaries go to the heap.** A string that does not outlive its
   statement is still allocated. Go's escape analysis halves b2str's
   allocations. With a collector this costs time, not memory; it is a
   later milestone, not P95.
3. **The map grows by whole doubling.** Even with a collector, the last
   rehash holds 17 + 34 MiB at once, about Go's whole peak. Go's table
   split was P96, built in 1.0.59 (below).

## 2. The design of the collector (P95)

### 2.1 Go's collector, the reference

`runtime/mgc.go` (header comment): concurrent, precise, non-generational
and non-compacting mark and sweep with a write barrier. A cycle stops
the world to reach a safe point, marks from the roots (stacks, globals,
off-heap runtime data) through a grey work queue, stops the world again
to finish, and sweeps span by span, lazily as allocation needs a span
and in the background. The next cycle starts when the heap reaches the
live heap times `1 + GOGC/100` (4 MB minimum).

`runtime/malloc.go`: 8 KiB pages; 68 size classes up to 32 KiB
(`internal/runtime/gc/sizeclasses.go`); an `mspan` is a run of pages
holding objects of one class; each P has an `mcache` with one span per
class, so a small allocation takes no lock; `mcentral` keeps the spans
of a class, `mheap` the pages. Objects without pointers go to `noscan`
spans and are never scanned. Objects under 16 bytes without pointers
share 16-byte blocks (the tiny allocator). A slot that is reused is
zeroed when it is handed out (`needzero`).

`runtime/mbitmap.go`: one bit per word says pointer or not. For objects
up to 512 bytes the bits live at the end of the span; a bigger object
has a type word in front of it.

`runtime/mgcmark.go`: a stack is scanned with the compiler's stack maps
(which slots hold pointers at each call site), except a frame stopped by
asynchronous preemption, which has no map: Go scans that one
conservatively, word by word, and does not move what it finds that way.

### 2.2 What in paslang shapes the choice

- The heap does not move and need not: Go's does not either. A
  conservative word can only keep a block alive, never break it.
- Stacks do move: `rt_newstack` copies a growing stack and adds the
  offset to every word whose value falls inside the old stack. That is
  already conservative.
- The code generator kept temporaries on the machine stack (1.0.52): 86 `push`
  sites on amd64, 77 on arm64, 31 places that take a `Scratch` slot, and
  156 places that emit a call. A precise map needs, at every call, the
  type of every pushed temporary and every live scratch slot.
- The runtime is hand-written assembly on both machines and keeps
  pointers in callee-saved registers across calls (`rt_concat` holds
  both source strings across `rt_alloc`). It has no maps.
- Safe points exist: the prologue and loop-head preemption checks
  (sysmon), every park, every system call. A routine holding a runtime
  lock is not preempted (G+184, 1.0.51). Promoted variables live in
  registers only inside regions without calls, and the preemption stubs
  spill them home.
- The allocation sites are few and known: `GetMem`, `New`, constructors,
  `MakeChan`, a function returning a record (a heap copy per return,
  P80), and the string and dynamic-array routines (`rt_concat`,
  `rt_setlength`, `rt_strcopy`, `rt_chstr`, `rt_readln`, `rt_tcpread`):
  24 call sites in the emitter, plus `pasmap`'s groups through `GetMem`.

### 2.3 The design

1. **Heap.** Arenas of 64 MiB mapped as needed, 8 KiB pages, a page-to-
   span table per arena (so any address answers "which span, which
   object"), Go's 68 size classes, span class = size class × 2 + noscan,
   an alloc bitmap and a mark bitmap per span, a span of its own for an
   object over 32 KiB. The 256 MiB cap goes; the limit is the machine's
   (as built, the heap grows in place up to 64 GiB, `HeapReserve`).
2. **Allocation.** `rt_alloc(size, type)`. The fast path stays in
   assembly and takes no lock: the P's `mcache` span for the class, the
   next free slot from a 64-bit window of the alloc bits (count trailing
   zeros, Go's `nextFreeFast`); a span never used before is bumped, as
   today. Tiny allocator for pointer-free blocks under 16 bytes (b2str's
   blocks). The slow path takes a span from the class's `mcentral`
   (sweeping it first), else pages from `mheap`, else a new arena. A
   reused slot is zeroed when handed out; fresh memory is not, so P94's
   gain stays.
3. **What a block holds.** Three kinds, decided by the compiler at the
   allocation site: *noscan* (strings, arrays of scalars, sets);
   *typed*, with a pointer bitmap the compiler writes in `.rodata`
   (records, classes, dynamic arrays and channel buffers of pointerful
   elements, record results, map groups from the map descriptor); and
   *conservative*, every word checked (`GetMem`, whose type nobody
   knows). Typed blocks up to 512 bytes keep their bits in the span,
   bigger ones a type word, as Go.
4. **Roots.** Globals: the compiler writes, for the program and each
   unit, a table of (address, size, pointer bitmap) of its variables in
   a section `pasgcroots`, which the linker gathers
   (`__start_pasgcroots`, `__stop_pasgcroots`). Every routine record: its
   argument and saved-register words, through a list of all records
   (Go's `allgs`). Every stack: see D1. The runtime keeps no heap pointer
   of its own today (`raise` carries no object; channel buffers are heap
   objects; waiting entries live on the waiting routine's stack); a
   runtime word that ever holds one goes on a short list of roots.
5. **Stopping the world.** A word of the heap state, `HGcWaiting`;
   every running routine's guard poisoned as sysmon does; an M stops in
   `rt_gcstopm`, from `rt_mloop` (where a yield and a preemption at
   `.ms_preempt` land) or on losing the race to start the cycle; an idle
   M counts as stopped, and so does one inside a system call (MState 2),
   which waits on the way out for the cycle that counted it; a routine
   holding a runtime lock runs until it lets go. The cycle runs on the
   g0 of the M that started it.
6. **Mark.** A grey stack in memory outside the heap; mark bits per span;
   an interior pointer (`@r.f`, `PChar` arithmetic) finds its object
   through the span table; a word that is not inside an allocated object
   is ignored.
7. **Sweep.** Lazily, span by span, when an `mcache` needs a span of
   that class, and whatever is left before the next cycle. An empty span
   goes back to `mheap`. Pages that stay free are returned to the kernel
   with `madvise(MADV_DONTNEED)` (Go's scavenger), so the resident size
   falls again.
8. **Pacing.** Go's rule: the next cycle when the heap in use reaches
   the live heap times `1 + PASLANG_GC/100`, 4 MiB minimum;
   `PASLANG_GC=100` by default, `off` to disable, like `GOGC`.
9. **Stack growth.** `rt_newstack` keeps copying stacks; with precise
   maps it adjusts only the words the maps call pointers.
10. **What stays.** `FreeMem` stays a no-op, a destructor frees nothing,
    no finalizers.

### 2.4 Decisions (2026-09-26)

**D1, stacks: precise maps first, or conservative first.** (A) writes a
map for every call site first, then the collector. (B)
scans stacks and the assembly runtime's frames conservatively in the
first collector and adds precise maps for compiled frames as the next
step, checked against the conservative result. (B) was chosen:

- a pointer missing from a precise map frees a live block, which is
  silent corruption; a conservative word only keeps a block alive;
- the runtime's assembly has no maps and keeps pointers in registers;
  under (A) it needs maps too, or conservative scanning anyway;
- Go itself scans frames without a map conservatively;
- the heap does not move, so a conservative stack is correct.

The cost of (B) is some memory kept by an integer that looks like a
pointer, which is rare with 64-bit addresses. `CONSTRAINTS.md` records
the result.

**D2, heap precision:** typed pointer bitmaps for every typed site (the
noscan kind needs the types anyway), conservative
only for `GetMem`.

**D3, concurrency:** stop the world in P95. A concurrent mark needs a
write barrier in every pointer store the compiler emits, and is its own
milestone.

**D4, the knob:** the name and default of `PASLANG_GC`.

**D5, the steps:** P95 split as below, each closed on its own numbers.

### 2.5 Steps

All four are built (1.0.53 to 1.0.66); "Where it stands" tells each.

| step | what | proves it |
|---|---|---|
| P95a | Typed allocation, span allocator, tiny allocator; nothing collected yet | every site passes a type; b1–b5 at today's times (b2str ≤ Go); make check on both machines |
| P95b | Roots, stop the world, mark, lazy sweep, pacing, scavenger; stacks per D1 | p1alloccap under 64 MB; b2str resident ≤ Go; b5map resident about Go's; the compiler builds itself under the same ulimit; a stress mode (`PASLANG_GCSTRESS=n`, a cycle every n-th span refill) and a poison mode (`PASLANG_GCPOISON=1`, freed slots filled with 0xde) pass the concurrency tests 30 times on amd64 and 10 under qemu |
| P95c | Precise stack maps for compiled frames (under B), a verify mode that compares them with the conservative scan, `rt_newstack` adjusting by map | every golden test verifies on both machines |
| P95d | Parallel mark on every M (done, 1.0.66) | a cycle's pause scales with the Ms |

Later, apart: a concurrent mark with Go's hybrid write barrier and
escape analysis for temporaries. Go's table split for the map (P96),
listed here at first, was built in 1.0.59 (below).

**Where it stands.** P95a is built (1.0.53 types every allocation,
1.0.54 the span heap). Two changes from 2.3: the heap is not reserved
ahead in arenas but grows in place from a base address, in steps of
4 MiB with one page-to-span table below it, because the build runs
under `ulimit -v` and an address space limit counts a PROT_NONE
reservation too; and the cycle runs on a routine record of the
collector's own (`HGcG`), whose stack never grows, on the M that claimed
it, not on that M's g0.

P95b's collector is built (1.0.55 the roots, 1.0.58 the cycle). Three
changes from 2.3: the sweep runs in the same stop as the mark, since
with bitmaps it costs a pass over the spans and keeps `rt_alloc`'s fast
path as it was; an empty span stays on its central list one cycle, so a
program that makes garbage at a steady rate takes it again as it is;
and a reused run is cleared by `rt_alloc` with `rep stosq` (`stp` on
arm64). Since 1.0.68 `rt_alloc` also takes the next run of a swept span
from a bitmap of the 64 slots after the current run, as Go's
`allocCache`: a program that keeps one string and drops the next left
every other slot free, and paid a call into pasheap per slot (the keys
of `b6smap` took 60 ms against Go's 44, 33–38 now; `allocbits`). Measured on 2026-09-26 with `scripts/bench/run.py -n 9`, twice,
on a quiet machine (medians, peak resident) against Go 1.27.1, with
1.0.59; part 1 has the 1.0.54 figures for b2str (73 MB) and b5map
(73–75 MB):

| pair | time pl / Go | Go MB | paslang MB |
|---|---|---|---|
| b1loop | 1.0 | 11–12 | 11–12 |
| b2str | 0.96–0.98 | 12–14 | 11–12 |
| b3spawn | 0.9–1.0 | 28–30 | 11–12 |
| b4chan | 0.3–0.4 | 11–12 | 11–12 |
| b5map | 0.8 | 52–54 | 48 |

`p1alloccap`, which died at 256 MiB, runs to the end in 0.5 s and
12 MB. b5map was at 55 MB with 1.0.58: at its last doubling the old
table (18 MB) and the new one (36 MB) were alive together, whatever the
pacing. 1.0.59 split the map as Go does, into tables of at most 1024
slots that grow one at a time (P96), and that was P95b's last
criterion. b1loop is one chain of dependent additions, which bounds
paslang and Go alike: pinned to one CPU the two take the same cycles
(2.24 G) and the same time; unpinned, the few percent either way are
the clock of the core each lands on.

P95c's stack maps are built (1.0.60 the maps, the walk and the verify
mode, 1.0.61 `rt_newstack` by map). Every call of compiled code has a
descriptor of its frame; the collector reads a stopped routine's frames
by them, and the runtime's own frames, and the frame that called them,
word by word, as Go reads a frame without a map. The pushed temporaries
say what they hold (no push of the compiler's own code is left unknown;
38 frame words in it are, the registers a promoted loop keeps for its
caller). `PASLANG_GCVERIFY=1` reads the stacks again word by word after
the maps and poisons, without freeing, what only that keeps; it moves
every stack after each cycle and poisons the old copy; `make check`
runs every golden test so on both machines. The work found three older
faults: `PASLANG_GCSTRESS=1` never got past the refill that asked for a
cycle; `rt_newstack` did not move the head of the try records, so a
raise after the stack grew twice in a try read an unmapped stack
(`trygrow`); and on arm64 it did not adjust the copy at all, so the
first return past it went back to the old stack and every allocation
after that went to the persistent heap, never collected (`growgc`).

P95d's parallel mark is built (1.0.66). The roots are jobs (the
globals, the Ms, the persistent heap, then one per routine) that any
worker takes by an atomic counter; each worker has a grey stack of its
own and, when another one waits with nothing and the shared stack is
empty, gives the oldest half of it there (in a tree, the roots of the
largest parts); a waiter claims half of what is there by compare and
swap before it takes the lock; a mark bit is set by compare and swap
only while more than one worker marks; an object larger than 128 KB is
scanned in slices of 128 KB put on the shared stack at once. The workers are the M
that runs the cycle and the Ms it stopped or found idle: each of them,
waiting on its futex for the world to start again, sees the cycle's
epoch and calls `rt_gcwork`, which runs `PasGcWorker` on the M's system
stack. The cycle ends as Go's `gcMarkDone` does: when no worker holds
anything and none is still inside. Measured on the development machine (32
threads, a Ryzen 9 5950X), the mark of one cycle on a finished heap,
against `PASLANG_GCWORKERS` (`HeapStat(17)`, average of 20 or 30
cycles):

| heap | 1 | 4 | 8 | 16 | all (31) |
|---|---|---|---|---|---|
| a million strings and their map, 83 MB | 37 ms | — | 6.3 | 3.7–4.5 | 3.6–3.9 |
| 16 binary trees of depth 15 and 500 000 strings, 78 MB | 67 | 18 | 8.4 | 5.0 | 4.2 |
| an array of 4 million strings, 122 MB | 61 | 17 | 8.8 | 5.1 | 4.5 |

and the total stop of the 5 cycles of `b6smap` (a million strings put
in a map while the heap grows):

| workers | 1 | 2 | 4 | 6 | 8 | 12 | 16 | all (31) |
|---|---|---|---|---|---|---|---|---|
| ms | 77–78 | 47–54 | 27–30 | 19–23 | 16.3–16.5 | 13–14 | 12.4–14 | 17–32 |

The sweep stays on the cycle's M: 0.2 ms after one worker, 0.6–0.9
after many, since the mark bits it reads were written on other cores.
While the heap grows, waking 31 threads for small cycles costs more
than they mark, so a cycle takes at most 16 unless `PASLANG_GCWORKERS`
says otherwise (0 every M).

The first version shared badly and was measured before it was kept.
16 workers marked the trees only 5 times as fast as one: a worker gave
on every block while anyone waited, taking the lock each time; every
waiter locked when blocks appeared, and the first took them all; the
heap's range, read for every pointer, sat on the cache line of the
counters the waiting workers add to; the top of a stack was given, the
smallest parts of a tree; and an oblet counted as one block, so the
worker that held them gave every 16 of them, 4 ms. Each was found by
sampling every CPU's instruction pointer (`perf_event_open`) and fixed as Go does it or better.
`HeapStat(14)` counts the workers that marked the last cycle and
`HeapStat(15)` how many may, 16 to 18 the last cycle's stop, mark and
sweep. `GcCollect` runs one cycle now; `HeapCheck` counts inconsistent
heap spans (0 is sound) and `HeapMaskOf(p)` is the pointer bitmap of
the block holding `p` (its first 64 words, -1 off the heap): the words
of `--help runtime` that a test uses to look at the collector. Since P91 the Ms have threads only when there is work for them,
so a cycle's winner first starts as many as it may mark with (heap
state +536, `rt_gcms`); `parmark` checks on both machines that a graph marked so
survives with one worker, two, the default and all, under poison,
verify and stress, and a runtime that drops what one worker gives the
other, or the oblets it puts on the shared stack, breaks it.

**What later versions give the collector.** Each of these is read by
the rules above.

- *Strings (1.0.82).* A string's block is its length plus one byte,
  GC word 0, and the value points at block + 1: the byte before the
  characters is the shared mark of copy on write, and
  the value is an interior pointer, which marks the block. The empty
  string is `rt_zerobase`, outside the heap. A literal is in `.rodata`.
- *Channels (1.0.83, 1.0.85).* A value wider than a word travels in a
  box allocated with its type's GC word, so a box is scanned as that
  type would be. A channel without a buffer is 64 bytes with GC word 0:
  its queues point into the waiting routines' stacks, which are scanned
  anyway. A buffered one is 80 bytes and a ring of `n * 8`, both with GC
  word 1 (a slot may hold a box, a pointer or a plain value, so every
  word is a candidate), and `rt_chbget` clears a slot it takes, so a
  consumed box is not kept.
- *Routine values (1.0.133).* A routine value is two words, the code
  and an environment; `GcMark` sets the bit of the second word only, so
  the environment is a pointer everywhere a type's bits are read: a
  frame's map (`MapBegin`), a pushed word (`VCls`), a global's root
  entry, a heap block's descriptor, a record's field. A nested routine's
  static link at -8 from its frame pointer is always a pointer in the
  map.
- *Closures (1.0.134).* A routine with a closure inside allocates its
  box with `rt_alloc(8 + its shared variables, 1)`: GC word 1, every
  word a candidate. Word 0 is the routine's own static link, the shared
  variables follow, each on 8 bytes; the hidden local `$box` holds
  block + 8, so the box looks like a frame to the link walk, and each
  shared variable's frame slot holds the address of its field; both are
  interior pointers, pointer words in the frame's map. A closure that
  pins loop cells has a scope box, `rt_alloc(8 + 8k, 1)`, the parent's
  link and then each cell's address, and the closure's environment is
  that block + 8. A cell (`cell.N`, one a pass) is `New` of the
  counter's type and is scanned by that type. `pas` of a nested routine
  or of any call keeps the environment at G+248 until `rt_execute` loads
  it; the routine's record is scanned whole and word by word
  (`GRecSize`, 272 bytes), so the box stays alive, and `PasStackAdjust`
  moves G+248 when it points into a stack that moved.
- *Trees, heaps and the store (1.0.141–1.0.145, P110).* A tree's header
  and every node of it (`pastree`) come from two-argument `GetMem`,
  scanned word by word: a node holds its parent, its neighbours and its
  children or its string keys and values, so the collector follows them
  all, and an integer key that looks like an address is a candidate it
  looks up and drops. A heap's array is `GetMem(n, 0)` when `T` holds no
  pointer, else scanned too. The store's memtable is a tree and its
  blocks are strings.

### 2.6 Rules the code must keep

- An `Integer` holding an address does not keep the block alive (Go's
  `uintptr` rule). `pasmap` computes addresses in integers but always
  keeps the `Pointer` too (`t^.Groups`, and `TMap.Dir`); a program must
  do the same. The directory's entries are addresses inside the tables,
  in a block from two-argument `GetMem`, which is scanned word by word,
  and a word inside a block marks the block (1.0.59).
- A pointer one past the end of a block does not keep the block alive:
  it points where the next block starts, and a word there marks that
  one. The language allows such a pointer (a walk may end there, and
  `-checkptr` lets a step reach it, 1.0.111), so the manual tells a
  program to keep a pointer to the block while it uses one; the runtime
  itself never keeps one alone, and an empty string or slice points to
  nil or to its start.
- `-checkptr`'s cache of the last object (G+160/+168 on amd64, G+120 on
  arm64, 1.0.111) is a pointer to that object in the G, which the
  collector scans word by word: the cached object stays alive, and its
  span keeps its layout, while the cache holds it. That is what makes
  the cache safe without a generation count; `rt_pas` clears it when a
  record starts another routine.
- A pointer inside a block keeps the block: a string's characters
  (block + 1), a closure's `$box` and environment (block + 8) and a
  shared variable's field address are never the block's start. The
  value such a word is kept for must lie inside the block, not at its
  end.
- Nothing parks while it holds a runtime lock (a rule since 1.0.51).

### 2.7 What it should give, and what it gave

The estimates of the proposal were b2str from 73 MB to the size of its
heap goal, a few MB; b5map from 74 MB to about 51 MiB at the last
rehash, Go's 52, and below Go only with the table split; p1alloccap from
death at 256 MiB to a few MB. The runs replaced them (the table under
"Where it stands"): b2str 11–12 MB against Go's 12–14, b5map 48 MB with
the table split against Go's 52–54, p1alloccap to the end in 12 MB.
