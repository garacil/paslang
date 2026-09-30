# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
#
# paslang is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# paslang is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with paslang.  If not, see <https://www.gnu.org/licenses/>.

# GNU installation directories. ./configure writes config.mk.
# Defaults match the GNU coding standards, so make works before configure.
-include config.mk

prefix ?= /usr/local
exec_prefix ?= $(prefix)
bindir ?= $(exec_prefix)/bin
sbindir ?= $(exec_prefix)/sbin
libexecdir ?= $(exec_prefix)/libexec
libdir ?= $(exec_prefix)/lib
includedir ?= $(prefix)/include
datarootdir ?= $(prefix)/share
datadir ?= $(datarootdir)
docdir ?= $(datarootdir)/doc/paslang
mandir ?= $(datarootdir)/man
infodir ?= $(datarootdir)/info
srcdir ?= .
INSTALL ?= install
INSTALL_PROGRAM ?= $(INSTALL)
INSTALL_DATA ?= $(INSTALL) -m 644
NORMAL_INSTALL = :
PRE_INSTALL = :
POST_INSTALL = :

HOSTC    ?= fpc
OUTDIR   := ./bin
UNITDIR  := ./units
BUILDDIR := ./build
HOSTDIR  := $(BUILDDIR)/host
WARN     := -vwnh -Sewnh -vm11030,11031,6018
FLAGS    := -Mobjfpc -Scgi -O2 -Fu$(HOSTDIR) -FE$(OUTDIR) -FU$(UNITDIR) -gl $(WARN)

PASLANG_SRC := \
	src/compiler/pasast.paslang \
	src/compiler/paslex.paslang \
	src/compiler/pasparse.paslang \
	src/compiler/pasopt.paslang \
	src/compiler/pasemit.paslang \
	src/compiler/pasiface.paslang \
	src/compiler/pashelp.paslang \
	src/lib/paslib.paslang \
	src/lib/paslinux.paslang \
	cmd/paslangc/paslangc.paslang

.PHONY: package distpkg release-assets bench-rounds all hello check check-arm64 clean hostsrc self self-arm64 stage compilers core core-arm64 libs libs-arm64 bench manual \
	install install-strip uninstall installdirs installcheck \
	mostlyclean distclean maintainer-clean

SELF_UNITS := \
	src/lib/paslinux.paslang \
	src/lib/paslib.paslang \
	src/compiler/pasast.paslang \
	src/compiler/paslex.paslang \
	src/compiler/pasiface.paslang \
	src/compiler/pashelp.paslang \
	src/compiler/pasparse.paslang \
	src/compiler/pasopt.paslang \
	src/compiler/pasemit.paslang

A64DIR := $(BUILDDIR)/a64

# Every unit is built again for one processor level of each machine
# (P143), x86-64-v3 and ARMv8.2 with its crypto extension, in a
# directory beside the base build: a program compiled for a -cpu with
# every feature of the level links those objects, so a unit's words
# that choose a kernel by -cpu take the program's, as Go compiles every
# package at its GOAMD64 level. The interfaces (.pi) are the same.
LVL_X64 := v3
LVL_A64 := v8.2+crypto
A64_OBJDUMP ?= aarch64-linux-gnu-objdump

# The golden tests: testdata/<t>.paslang must print testdata/<t>.out.
GOLDEN := hello arith ifthen loops const caseof procs recfn records ptrs arrs strs grow paswork pingpong chclose sel exc excg nest cls gen enums sets dbg opt gdbg inherit rtti args8 mevent slice chlit armmeth propacc runes variant opadd args20 iface opmore props pindex dwarfloc shift dynnil xor inhcall isas sysid forward defaults abstract overload methov strdef trig logexp arctan invpow logx trig2 hyper miscmath xxh32 xxh64 map1 map2 sync1 sync2 finexit zerolocal pchar selx selstress wrchar chstr lookpath strcmp dupparam recarg funcval constk regloop reszero divconst bareln gctypes chr charcat heapspan blobzero gcbasic mapsplit stackmap trygrow growgc xxh3 mapgetstr bounds fairq sized fwdptr constexpr int2real typedconst caserange emptystmt writefmt realparse realfmt valpar strcow chanany chanbuf memmove overnarrow slicegrow fatexit narrow narrowmem recalign narrowbounds dwarfnarrow narrowgo forlimit bce inplace narrowasm slicereg forrun addrform bcerun inspine framearr realstep f32conv single dwarfreal ptrtyped ptrarith ptrsafe memview checkptr ptrreach cpwalk realint quadcore quadfmt quad quadconst dwarfquad bitops declorder convchain bitwords bitmem bitany views blocks wide ifdef quadfast memwords cpuwords vectors vecmore inlineasm vecpool addrlocal rotwords rotmem ctxwords append funcval2 closures pasargs ifaceargs vshrs64 auditfix closurebox audit2 visibility freedestroy reservedall nodeadlock mapfix tree1 tree2 hash1 store1 immwide constref inline1 stackargs mainexit networds charcmp unixsock sigpipe sleepmany deadlines strfill narrowpop tobject1 excobj1 excobj2 excobj3 classref1 ctorargs aconst1 aconst2 methdef1 set256 subrange1 subrange2 helper1 helper2 strwords strkern slicedit strcmpk scope1 classfwd ifacebind overconv overrank valunsigned sysutils1 sysutils2 initvar extended1 valround valround2 cmpwords fmtfloat1 fmtfloat2 format1 realtext quadtext valrange hidesys arrindex
GOLDEN_A64 := map1 map2 sync1 sync2 finexit zerolocal pchar pingpong sel chclose paswork selx selstress wrchar args8 arith arrs caseof chlit cls const enums exc excg gen grow hyper ifthen inherit loops mevent miscmath nest procs ptrs recfn records sets strs trig2 xxh32 xxh64 rtti gdbg chstr strcmp recarg funcval constk regloop reszero divconst bareln gctypes chr charcat heapspan blobzero gcbasic mapsplit stackmap trygrow growgc xxh3 mapgetstr bounds fairq sized fwdptr constexpr int2real typedconst caserange emptystmt writefmt realparse realfmt valpar strcow chanany chanbuf memmove overnarrow slicegrow fatexit narrow narrowmem recalign narrowbounds dwarfnarrow narrowgo forlimit bce inplace narrowasm slicereg forrun addrform bcerun inspine framearr realstep f32conv single dwarfreal ptrtyped ptrarith ptrsafe memview checkptr ptrreach cpwalk realint quadcore quadfmt quad quadconst dwarfquad bitops declorder convchain bitwords bitmem bitany views blocks wide ifdef quadfast memwords cpuwords vectors vecmore inlineasm vecpool addrlocal rotwords rotmem ctxwords append funcval2 closures pasargs ifaceargs vshrs64 auditfix closurebox audit2 visibility freedestroy reservedall nodeadlock mapfix tree1 tree2 hash1 store1 immwide constref inline1 stackargs mainexit networds charcmp unixsock sigpipe sleepmany deadlines strfill narrowpop tobject1 excobj1 excobj2 excobj3 classref1 ctorargs aconst1 aconst2 methdef1 set256 subrange1 subrange2 helper1 helper2 strwords strkern slicedit strcmpk scope1 classfwd ifacebind overconv overrank valunsigned sysutils1 sysutils2 initvar extended1 valround valround2 cmpwords fmtfloat1 fmtfloat2 format1 realtext quadtext valrange hidesys arrindex

# The core units are part of the language: every program links pasmap
# (map[K] of V) and sees pasroutines (mutex, waitgroup, ...) without a
# uses clause. They are compiled by paslangc itself, once per target.
CORE_UNITS := \
	src/lib/pasobject.paslang \
	src/lib/pasroutines.paslang \
	src/lib/pasmap.paslang \
	src/lib/pashash.paslang \
	src/lib/pastree.paslang \
	src/lib/pasheap.paslang \
	src/lib/pasfmt.paslang \
	src/lib/passtr.paslang \
	src/lib/pasquad.paslang

# The library units a program reaches with a uses clause. They are not
# part of the language, but they are part of the installation, so a
# project outside this tree (lazlang, for one) can compile against
# them. Order matters: each one only uses the ones before it.
LIB_UNITS := \
	src/lib/paslinux.paslang \
	src/lib/paslib.paslang \
	src/lib/pasnet.paslang \
	src/lib/pasdebug.paslang \
	src/lib/pasrand.paslang \
	src/lib/passort.paslang \
	src/lib/pastime.paslang \
	src/lib/pasx11.paslang \
	src/rtl/sysutils.paslang

all: $(OUTDIR)/paslangc core core-arm64 libs libs-arm64 $(OUTDIR)/pasdbg

# The book in one page, docs/manual/index.html, from the canonical
# Markdown (MANUAL.md, TYPES.md, QUAD.md, GC.md, KERNELS.md, VISION.md).
manual:
	python3 scripts/manual_html.py

libs: $(OUTDIR)/paslangc core $(LIB_UNITS) | $(BUILDDIR)
	@set -e; \
	for u in $(LIB_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "lib $$b"; \
	  $(OUTDIR)/paslangc -cpu base -c -Fu $(BUILDDIR) -o $(BUILDDIR)/$$b $$u; \
	done; \
	mkdir -p $(BUILDDIR)/$(LVL_X64); \
	for u in $(LIB_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "lib $(LVL_X64) $$b"; \
	  $(OUTDIR)/paslangc -cpu $(LVL_X64) -c -Fu $(BUILDDIR) -o $(BUILDDIR)/$(LVL_X64)/$$b $$u; \
	done

# The library units for arm64 too (1.0.80): the installed compiler could
# not build an arm64 program that uses paslib.
libs-arm64: $(OUTDIR)/paslangc core-arm64 $(LIB_UNITS) | $(BUILDDIR)
	@set -e; mkdir -p $(A64DIR); \
	for u in $(LIB_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "lib-arm64 $$b"; \
	  $(OUTDIR)/paslangc -target arm64 -cpu base -c -Fu $(A64DIR) -o $(A64DIR)/$$b $$u; \
	done; \
	mkdir -p '$(A64DIR)/$(LVL_A64)'; \
	for u in $(LIB_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "lib-arm64 $(LVL_A64) $$b"; \
	  $(OUTDIR)/paslangc -target arm64 -cpu $(LVL_A64) -c -Fu $(A64DIR) -o '$(A64DIR)/$(LVL_A64)'/$$b $$u; \
	done

core: $(OUTDIR)/paslangc $(CORE_UNITS) | $(BUILDDIR)
	@set -e; \
	for u in $(CORE_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "core $$b"; \
	  $(OUTDIR)/paslangc -cpu base -c -Fu $(BUILDDIR) -o $(BUILDDIR)/$$b $$u; \
	done; \
	mkdir -p $(BUILDDIR)/$(LVL_X64); \
	for u in $(CORE_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "core $(LVL_X64) $$b"; \
	  $(OUTDIR)/paslangc -cpu $(LVL_X64) -c -Fu $(BUILDDIR) -o $(BUILDDIR)/$(LVL_X64)/$$b $$u; \
	done

core-arm64: $(OUTDIR)/paslangc $(CORE_UNITS) | $(BUILDDIR)
	@set -e; mkdir -p $(A64DIR); \
	for u in $(CORE_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "core-arm64 $$b"; \
	  $(OUTDIR)/paslangc -target arm64 -cpu base -c -Fu $(A64DIR) -o $(A64DIR)/$$b $$u; \
	done; \
	mkdir -p '$(A64DIR)/$(LVL_A64)'; \
	for u in $(CORE_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "core-arm64 $(LVL_A64) $$b"; \
	  $(OUTDIR)/paslangc -target arm64 -cpu $(LVL_A64) -c -Fu $(A64DIR) -o '$(A64DIR)/$(LVL_A64)'/$$b $$u; \
	done

compilers: $(OUTDIR)/paslangc core $(OUTDIR)/paslangc-arm64

$(OUTDIR)/paslangc-arm64: $(OUTDIR)/paslangc core-arm64 $(SELF_UNITS) cmd/paslangc/paslangc.paslang | $(OUTDIR) $(BUILDDIR)
	mkdir -p $(A64DIR)
	@set -e; ulimit -v 2097152; \
	for u in $(SELF_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "arm64 $$b"; \
	  $(OUTDIR)/paslangc -target arm64 -cpu base -c -Fu $(A64DIR) -o $(A64DIR)/$$b $$u; \
	done; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -Fu $(A64DIR) -o $@ cmd/paslangc/paslangc.paslang

$(OUTDIR) $(UNITDIR) $(BUILDDIR) $(HOSTDIR):
	mkdir -p $@

hostsrc: $(PASLANG_SRC) | $(HOSTDIR)
	cp src/compiler/*.paslang src/lib/*.paslang $(HOSTDIR)/
	cp cmd/paslangc/paslangc.paslang $(HOSTDIR)/paslangc.pas
	@cd $(HOSTDIR) && for f in *.paslang; do mv "$$f" "$${f%.paslang}.pas"; done
	python3 scripts/host_syscall.py $(HOSTDIR)

# The compiler the host builds runs the host's runtime; built again by
# itself it runs its own, so a fix to the runtime (rt_setlength, 1.0.88)
# is in bin/paslangc, and so in what make check tests and make install
# installs, from its own version on. The installed compiler lagged one
# version: 1.0.87's stale rt_setlength laid out a frame of the P99
# compiler wrong and the stage compiler crashed.
$(OUTDIR)/paslangc: $(PASLANG_SRC) $(CORE_UNITS) | $(OUTDIR) $(UNITDIR) $(HOSTDIR) $(BUILDDIR)
	@set -e; \
	boot=""; \
	if [ -x "$(bindir)/paslangc" ]; then boot="$(bindir)/paslangc"; \
	elif [ -x "$(OUTDIR)/paslangc" ]; then boot="$(OUTDIR)/paslangc"; \
	fi; \
	if [ -n "$$boot" ]; then \
	  echo "stage paslangc via $$boot"; \
	  absboot=$$(readlink -f "$$boot"); \
	  abstarget=""; \
	  if [ -x "$(OUTDIR)/paslangc" ]; then abstarget=$$(readlink -f "$(OUTDIR)/paslangc"); fi; \
	  if [ -n "$$abstarget" ] && [ "$$absboot" = "$$abstarget" ]; then \
	    cp "$(OUTDIR)/paslangc" "$(BUILDDIR)/paslangc.prev"; \
	    boot="$(BUILDDIR)/paslangc.prev"; \
	  fi; \
	  $(MAKE) stage HOST="$$boot" STAGE="$(OUTDIR)/paslangc"; \
	  echo "paslangc by itself"; \
	  $(MAKE) stage HOST="$(OUTDIR)/paslangc" STAGE="$(BUILDDIR)/paslangc.self"; \
	  mv "$(BUILDDIR)/paslangc.self" "$(OUTDIR)/paslangc"; \
	else \
	  echo "bootstrap paslangc via fpc"; \
	  $(MAKE) hostsrc; \
	  $(HOSTC) $(FLAGS) $(HOSTDIR)/paslangc.pas; \
	  echo "paslangc by itself"; \
	  $(MAKE) stage HOST="$(OUTDIR)/paslangc" STAGE="$(BUILDDIR)/paslangc.self"; \
	  mv "$(BUILDDIR)/paslangc.self" "$(OUTDIR)/paslangc"; \
	fi

# The compiler reproduces itself: bin/paslangc builds the compiler into
# self2, that compiler builds it again into self3, and the assembly of
# every unit must be the same both times; then both compilers compile
# every golden test for both machines and must write the same assembly. A code generator that
# miscompiles the compiler shows here, on the biggest program there is,
# and not only on hello (1.0.40 passed every test and still miscompiled
# SetLength in the parser, P94).
self: $(OUTDIR)/paslangc core | $(BUILDDIR)
	@set -e; ulimit -v 2097152; \
	S2=$(BUILDDIR)/self2; S3=$(BUILDDIR)/self3; \
	rm -rf $$S2 $$S3; mkdir -p $$S2 $$S3; \
	for u in $(SELF_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "self2 $$b"; \
	  $(OUTDIR)/paslangc -cpu base -c -Fu $$S2 -o $$S2/$$b $$u; \
	done; \
	$(OUTDIR)/paslangc -cpu base -Fu $$S2 -o $$S2/paslangc cmd/paslangc/paslangc.paslang; \
	for u in $(SELF_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "self3 $$b"; \
	  $$S2/paslangc -cpu base -c -Fu $$S3 -o $$S3/$$b $$u; \
	done; \
	$$S2/paslangc -cpu base -Fu $$S3 -o $$S3/paslangc cmd/paslangc/paslangc.paslang; \
	for u in $(SELF_UNITS) cmd/paslangc/paslangc.paslang; do \
	  b=$$(basename $$u .paslang); \
	  cmp $$S2/$$b.s $$S3/$$b.s; \
	done; \
	for t in $(GOLDEN); do \
	  $(OUTDIR)/paslangc -o $$S2/g_$$t testdata/$$t.paslang; \
	  $$S3/paslangc -o $$S3/g_$$t testdata/$$t.paslang; \
	  cmp $$S2/g_$$t.s $$S3/g_$$t.s; \
	done; \
	for t in $(GOLDEN_A64); do \
	  $(OUTDIR)/paslangc -target arm64 -o $$S2/a_$$t testdata/$$t.paslang; \
	  $$S3/paslangc -target arm64 -o $$S3/a_$$t testdata/$$t.paslang; \
	  cmp $$S2/a_$$t.s $$S3/a_$$t.s; \
	done; \
	$$S3/paslangc -o $(BUILDDIR)/hello-s3 testdata/hello.paslang; \
	$(BUILDDIR)/hello-s3; \
	echo ok self

HOST ?= $(bindir)/paslangc
STAGE ?= $(BUILDDIR)/paslangc-stage
# The compiler and the units are built for the base processor:
# the installed toolchain runs on any machine. A host older than 1.0.144
# does not know -cpu, so the flag is passed only when its help names it.
HOSTCPU = $$(if $(HOST) --help flags 2>/dev/null | grep -q '^-cpu'; then echo -cpu base; fi)
STAGE_DIR := $(BUILDDIR)/stage

# The compiler links the core units (its lexer reads reals with pasfmt), so
# they are among its prerequisites: an edit of pasfmt alone left the old
# compiler in place (P101 found it with a sabotage).
# The host compiles the core units too, into the stage directory, so the
# stage compiler links cores its own runtime can satisfy; the cores the
# stage compiler emits go to stage/core, since they may name runtime
# symbols the host does not have (rt_divzero did, P86).
stage: $(PASLANG_SRC) $(CORE_UNITS) | $(BUILDDIR)
	@test -n "$(HOST)"
	@test -x "$(HOST)"
	@set -e; ulimit -v 2097152; \
	: a clean directory each time, 1.1.2: a .pi another compiler wrote there, of another format, was read before this host rewrote it; \
	rm -rf $(STAGE_DIR); \
	mkdir -p $(STAGE_DIR) $(STAGE_DIR)/core; \
	for u in $(CORE_UNITS) $(SELF_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "stage $$b"; \
	  $(HOST) $(HOSTCPU) -c -Fu $(STAGE_DIR) -o $(STAGE_DIR)/$$b $$u; \
	done; \
	echo "stage paslangc"; \
	$(HOST) $(HOSTCPU) -Fu $(STAGE_DIR) -o $(STAGE) cmd/paslangc/paslangc.paslang; \
	for u in $(CORE_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "stage core $$b"; \
	  $(STAGE) -cpu base -c -Fu $(STAGE_DIR)/core -o $(STAGE_DIR)/core/$$b $$u; \
	done; \
	$(STAGE) -Fu $(STAGE_DIR)/core -o $(BUILDDIR)/stage-hello testdata/hello.paslang; \
	$(BUILDDIR)/stage-hello; \
	echo ok stage

self-arm64: $(OUTDIR)/paslangc-arm64 $(BUILDDIR)/qemu-aarch64-static | $(BUILDDIR)
	@set -e; ulimit -v 2097152; \
	mkdir -p $(BUILDDIR)/a64self; \
	for u in $(CORE_UNITS) $(SELF_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "self-arm64 $$b"; \
	  timeout 2400 taskset -c 0 $(QEMU_A64) $(OUTDIR)/paslangc-arm64 -c -Fu $(BUILDDIR)/a64self -o $(BUILDDIR)/a64self/$$b $$u; \
	done; \
	echo "self-arm64 paslangc"; \
	timeout 2400 taskset -c 0 $(QEMU_A64) $(OUTDIR)/paslangc-arm64 -Fu $(BUILDDIR)/a64self -o $(BUILDDIR)/paslangc-arm64-s2 cmd/paslangc/paslangc.paslang; \
	timeout 180 taskset -c 0 $(QEMU_A64) $(BUILDDIR)/paslangc-arm64-s2 -o $(BUILDDIR)/hello-a64s2 testdata/hello.paslang; \
	timeout 20 taskset -c 0 $(QEMU_A64) $(BUILDDIR)/hello-a64s2; \
	echo ok self-arm64

hello: $(OUTDIR)/paslangc core testdata/hello.paslang | $(BUILDDIR)
	$(OUTDIR)/paslangc -o $(OUTDIR)/hello testdata/hello.paslang
	$(OUTDIR)/hello

# P89: paslang against Go (scripts/bench/run.py): the six pairs built with
# this tree's compiler and with go, medians of seven runs, time and memory
# against the budgets in run.py (exit 1 when one passes it or an output
# differs), then the seven robustness probes. Go is not a dependency of the
# compiler: make check does not run this.
bench: $(OUTDIR)/paslangc core
	@mkdir -p $(BUILDDIR)/bench; PATH="$(abspath $(OUTDIR)):$$PATH" python3 scripts/bench/run.py -n 7 --json $(BUILDDIR)/bench/last.json

# The debugger's terminal (P118): pasdbg <socket> speaks to a program
# compiled with -debug and run with PASLANG_DEBUG=<socket>.
$(OUTDIR)/pasdbg: $(OUTDIR)/paslangc libs cmd/pasdbg/pasdbg.paslang
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(OUTDIR)/pasdbg cmd/pasdbg/pasdbg.paslang

# The three servers against their Go twins (P115): scripts/bench/servers.py.
# The pairs again in alternating rounds (scripts/bench/rounds.py), the
# median of each round's ratio: steadier than a median of runs on a
# machine that runs anything else. After make bench, which builds them.
bench-rounds:
	python3 scripts/bench/rounds.py -n 40 --json $(BUILDDIR)/bench/rounds.json

bench-servers: $(OUTDIR)/paslangc core libs
	PATH=$(OUTDIR):$$PATH python3 scripts/bench/servers.py -n 3 --json $(BUILDDIR)/bench/servers.json

check: $(OUTDIR)/paslangc core core-arm64 libs libs-arm64 $(BUILDDIR)/qemu-aarch64-static
	@set -e; \
	xrun=""; \
	if command -v Xvfb > /dev/null 2>&1; then \
	  if [ ! -e /tmp/.X11-unix/X99 ]; then \
	    Xvfb :99 -screen 0 1024x768x24 -ac > /dev/null 2>&1 & \
	    echo $$! > $(BUILDDIR)/xvfb.pid; \
	    sleep 1; \
	  fi; \
	  xrun="env DISPLAY=:99"; \
	fi; \
	rm -f $(BUILDDIR)/fh.txt; \
	echo "==== spawnrace ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/spawnrace testdata/spawnrace.paslang; \
	timeout 30 $(BUILDDIR)/spawnrace > $(BUILDDIR)/spawnrace.got; \
	diff -u testdata/spawnrace.out $(BUILDDIR)/spawnrace.got; \
	echo ok spawnrace; \
	echo "==== idlerace ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/idlerace testdata/idlerace.paslang; \
	timeout 60 $(BUILDDIR)/idlerace > $(BUILDDIR)/idlerace.got; \
	diff -u testdata/idlerace.out $(BUILDDIR)/idlerace.got; \
	echo ok idlerace; \
	echo "==== mutexfair ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/mutexfair testdata/mutexfair.paslang; \
	timeout 20 $(BUILDDIR)/mutexfair > $(BUILDDIR)/mutexfair.got; \
	diff -u testdata/mutexfair.out $(BUILDDIR)/mutexfair.got; \
	echo ok mutexfair; \
	echo "==== lockpreempt ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/lockpreempt testdata/lockpreempt.paslang; \
	timeout 20 $(BUILDDIR)/lockpreempt > $(BUILDDIR)/lockpreempt.got; \
	diff -u testdata/lockpreempt.out $(BUILDDIR)/lockpreempt.got; \
	echo ok lockpreempt; \
	echo "==== parkrace ===="; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/parkrace testdata/parkrace.paslang; \
	timeout 60 $(BUILDDIR)/parkrace > $(BUILDDIR)/parkrace.got; \
	diff -u testdata/parkrace.out $(BUILDDIR)/parkrace.got; \
	echo ok parkrace; \
	echo "==== sortunit ===="; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/sortunit testdata/sortunit.paslang; \
	$(BUILDDIR)/sortunit > $(BUILDDIR)/sortunit.got; \
	diff -u testdata/sortunit.out $(BUILDDIR)/sortunit.got; \
	echo ok sortunit; \
	echo "==== randunit ===="; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/randunit testdata/randunit.paslang; \
	$(BUILDDIR)/randunit > $(BUILDDIR)/randunit.got; \
	diff -u testdata/randunit.out $(BUILDDIR)/randunit.got; \
	echo ok randunit; \
	echo "==== filehandle ===="; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/filehandle testdata/filehandle.paslang; \
	$(BUILDDIR)/filehandle > $(BUILDDIR)/filehandle.got; \
	diff -u testdata/filehandle.out $(BUILDDIR)/filehandle.got; \
	echo ok filehandle; \
	echo "==== timeunit ===="; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/timeunit testdata/timeunit.paslang; \
	$(BUILDDIR)/timeunit > $(BUILDDIR)/timeunit.got; \
	diff -u testdata/timeunit.out $(BUILDDIR)/timeunit.got; \
	echo ok timeunit; \
	for t in $(GOLDEN); do \
	  echo "==== $$t ===="; \
	  $(OUTDIR)/paslangc -o $(BUILDDIR)/$$t testdata/$$t.paslang; \
	  $(BUILDDIR)/$$t > $(BUILDDIR)/$$t.got; \
	  diff -u testdata/$$t.out $(BUILDDIR)/$$t.got; \
	  echo ok $$t; \
	done; \
	echo "==== inline ===="; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/inline0 testdata/inline1.paslang; \
	$(BUILDDIR)/inline0 > $(BUILDDIR)/inline0.got; \
	diff -u testdata/inline1.out $(BUILDDIR)/inline0.got; \
	for f in tally swap clamp sq twice huge; do \
	  if grep -q "call p_$$f$$" $(BUILDDIR)/inline1.s; then echo "inline1.s still calls $$f, which should be in place"; exit 1; fi; \
	done; \
	for f in count fact len2 big; do \
	  grep -q "call p_$$f$$" $(BUILDDIR)/inline1.s || { echo "inline1.s does not call $$f, which should stay a call"; exit 1; }; \
	done; \
	grep -q "call p_sq$$" $(BUILDDIR)/inline0.s || { echo "inline0.s (-inline 0) does not call Sq"; exit 1; }; \
	echo ok inline; \
	echo "==== dead code ===="; \
	sz=$$(size $(BUILDDIR)/hello | awk 'NR==2 {print $$1}'); \
	[ "$$sz" -lt 160000 ] || { echo "hello's text is $$sz bytes: the core routines it does not use were linked"; exit 1; }; \
	grep -q '^\.section \.text\.p_pastree_pastreeget,' $(BUILDDIR)/pastree.s || { echo "pastree.s has no section per routine"; exit 1; }; \
	grep -q '^\.section pasgcmaps\.p_pastree_pastreeget,"awo"' $(BUILDDIR)/pastree.s || { echo "pastree.s has no map section per routine"; exit 1; }; \
	echo ok deadcode; \
	echo "==== gctypes descriptors ===="; \
	grep -q 'gctype TNode size 32 words 1 mask 0x0000000000000009' $(BUILDDIR)/gctypes.s; \
	grep -q 'gctype TPair size 32 words 1 mask 0x0000000000000005' $(BUILDDIR)/gctypes.s; \
	grep -q 'gctype TBox instance size 48 words 1 mask 0x000000000000000a' $(BUILDDIR)/gctypes.s; \
	if grep -q 'gctype TPlain' $(BUILDDIR)/gctypes.s; then echo "gctypes.s has a descriptor for TPlain, which holds no pointer"; exit 1; fi; \
	grep -qx '.section pasgcroots,"aw"' $(BUILDDIR)/gctypes.s; \
	grep -A1 -x '  .quad v_pl' $(BUILDDIR)/gctypes.s | grep -qx '  .quad 8'; \
	grep -A1 -x '  .quad v_pairs' $(BUILDDIR)/gctypes.s | grep -qx '  .quad 24'; \
	if grep -qx '  .quad v_total' $(BUILDDIR)/gctypes.s; then echo "gctypes.s lists v_total, which holds no pointer, as a root"; exit 1; fi; \
	echo ok gctypes-descriptors; \
	echo "==== stdin ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/readlines testdata/readlines.paslang; \
	$(BUILDDIR)/readlines < testdata/readlines.in > $(BUILDDIR)/readlines.got; \
	diff -u testdata/readlines.out $(BUILDDIR)/readlines.got; \
	(sleep 0.05; head -c 3000 testdata/readlines.in; sleep 0.05; tail -c +3001 testdata/readlines.in) | $(BUILDDIR)/readlines > $(BUILDDIR)/readlines.got; \
	diff -u testdata/readlines.out $(BUILDDIR)/readlines.got; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/spurwake testdata/spurwake.paslang; \
	(sleep 0.2; printf 'x\n'; head -c 100000 /dev/zero | tr '\0' y) | timeout 20 $(BUILDDIR)/spurwake > $(BUILDDIR)/spurwake.got; \
	diff -u testdata/spurwake.out $(BUILDDIR)/spurwake.got; \
	echo ok stdin; \
	echo "==== collector ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/gcoff testdata/gcoff.paslang; \
	$(BUILDDIR)/gcoff > $(BUILDDIR)/gcoff.got; \
	diff -u testdata/gcoff.out $(BUILDDIR)/gcoff.got; \
	PASLANG_GC=off $(BUILDDIR)/gcoff > $(BUILDDIR)/gcoff.got; \
	diff -u testdata/gcoff-off.out $(BUILDDIR)/gcoff.got; \
	for i in 1 2 3; do \
	  PASLANG_GCSTRESS=3 PASLANG_GCPOISON=1 timeout 300 $(BUILDDIR)/gcbasic > $(BUILDDIR)/gcbasic.got; \
	  diff -u testdata/gcbasic.out $(BUILDDIR)/gcbasic.got; \
	done; \
	for t in heapspan map2 sync2 strs mapsplit closurebox tree1 tree2 hash1 store1; do \
	  PASLANG_GCSTRESS=5 PASLANG_GCPOISON=1 timeout 300 $(BUILDDIR)/$$t > $(BUILDDIR)/$$t.got; \
	  diff -u testdata/$$t.out $(BUILDDIR)/$$t.got; \
	done; \
	echo ok collector; \
	echo "==== stop race ===="; \
	for r in 1 2 3 4 5; do \
	  pids=""; \
	  for k in 1 2 3 4; do \
	    PASLANG_GCSTRESS=3 PASLANG_GCPOISON=1 timeout 120 $(BUILDDIR)/gcbasic > $(BUILDDIR)/gcrace$$k.got & \
	    pids="$$pids $$!"; \
	  done; \
	  wait $$pids; \
	  for k in 1 2 3 4; do diff -u testdata/gcbasic.out $(BUILDDIR)/gcrace$$k.got; done; \
	done; \
	echo ok stoprace; \
	echo "==== stack maps ===="; \
	for t in $(GOLDEN); do \
	  PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=3 PASLANG_GCPOISON=1 timeout 300 $(BUILDDIR)/$$t > $(BUILDDIR)/$$t.vgot; \
	  diff -u testdata/$$t.out $(BUILDDIR)/$$t.vgot; \
	done; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 timeout 300 $(BUILDDIR)/stackmap > $(BUILDDIR)/stackmap.vgot; \
	diff -u testdata/stackmap.out $(BUILDDIR)/stackmap.vgot; \
	echo ok stackmaps; \
	echo "==== the base processor (-cpu base) ===="; \
	for t in vectors vecmore vecpool bitwords xxh3 inlineasm hash1 tree1 store1 mapsplit set256 strwords strkern strcmpk cmpwords sysutils1; do \
	  $(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/$$t-base testdata/$$t.paslang; \
	  $(BUILDDIR)/$$t-base > $(BUILDDIR)/$$t.bgot; \
	  diff -u testdata/$$t.out $(BUILDDIR)/$$t.bgot; \
	  PASLANG_CPU=base $(BUILDDIR)/$$t-base > $(BUILDDIR)/$$t.bgot; \
	  diff -u testdata/$$t.out $(BUILDDIR)/$$t.bgot; \
	done; \
	grep -q 'p_pashash_passha256cpu' $(BUILDDIR)/hash1.s; \
	grep -q 'p_pashash_passha256base' $(BUILDDIR)/hash1-base.s; \
	if grep -q 'p_pashash_passha256cpu' $(BUILDDIR)/hash1-base.s; then echo "hash1-base.s calls the SHA-NI body"; exit 1; fi; \
	if grep -q 'popcntq' $(BUILDDIR)/bitwords-base.s; then echo "bitwords-base.s carries popcnt"; exit 1; fi; \
	if grep -q 'btq \$$13, rt_cpufeat' $(BUILDDIR)/vectors.s; then echo "vectors.s tests rt_cpufeat at run time"; exit 1; fi; \
	$(OUTDIR)/paslangc -cpu v2 -o $(BUILDDIR)/set256-v2 testdata/set256.paslang; \
	$(BUILDDIR)/set256-v2 > $(BUILDDIR)/set256.v2got; \
	diff -u testdata/set256.out $(BUILDDIR)/set256.v2got; \
	if grep -qw 'vptest' $(BUILDDIR)/set256-base.s; then echo "set256-base.s carries AVX2"; exit 1; fi; \
	if grep -qw 'ptest' $(BUILDDIR)/set256-base.s; then echo "set256-base.s carries SSE4.1"; exit 1; fi; \
	if grep -qw 'tzcntq' $(BUILDDIR)/set256-base.s; then echo "set256-base.s carries BMI1"; exit 1; fi; \
	grep -qw 'vptest' $(BUILDDIR)/set256.s; \
	grep -q 'p_passtr_pasposcpu' $(BUILDDIR)/strwords.s; \
	$(OUTDIR)/paslangc -cpu v2 -o $(BUILDDIR)/strcmpk-v2 testdata/strcmpk.paslang; \
	$(BUILDDIR)/strcmpk-v2 > $(BUILDDIR)/strcmpk.v2got; \
	diff -u testdata/strcmpk.out $(BUILDDIR)/strcmpk.v2got; \
	grep -q 'vpcmpeqb %ymm1, %ymm0, %ymm4' $(BUILDDIR)/strcmpk.s; \
	if grep -q 'vpcmpeqb' $(BUILDDIR)/strcmpk-base.s; then echo "strcmpk-base.s carries AVX2"; exit 1; fi; \
	grep -q 'p_passtr_pasupperbase' $(BUILDDIR)/strwords-base.s; \
	if grep -q 'p_passtr_pasposcpu' $(BUILDDIR)/strwords-base.s; then echo "strwords-base.s calls the AVX2 search"; exit 1; fi; \
	grep -qw 'tzcntq' $(BUILDDIR)/set256.s; \
	grep -qw 'ptest' $(BUILDDIR)/set256-v2.s; \
	if grep -qw 'vptest' $(BUILDDIR)/set256-v2.s; then echo "set256-v2.s carries AVX2"; exit 1; fi; \
	echo ok cpu-base; \
	echo "==== parallel mark ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/parmark testdata/parmark.paslang; \
	for w in "" "" "" PASLANG_GCWORKERS=1 PASLANG_GCWORKERS=2 PASLANG_GCWORKERS=0 "PASLANG_GCVERIFY=1 PASLANG_GCPOISON=1" "PASLANG_GCSTRESS=50 PASLANG_GCPOISON=1"; do \
	  env $$w timeout 300 $(BUILDDIR)/parmark > $(BUILDDIR)/parmark.got; \
	  diff -u testdata/parmark.out $(BUILDDIR)/parmark.got; \
	done; \
	echo ok parmark; \
	echo "==== lazy Ms ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/lazym testdata/lazym.paslang; \
	for w in "" "" PASLANG_GCWORKERS=1 PASLANG_GCWORKERS=0; do \
	  env $$w timeout 120 $(BUILDDIR)/lazym > $(BUILDDIR)/lazym.got; \
	  diff -u testdata/lazym.out $(BUILDDIR)/lazym.got; \
	done; \
	echo ok lazym; \
	echo "==== alloc bits ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/allocbits testdata/allocbits.paslang; \
	for w in "" PASLANG_GCPOISON=1 "PASLANG_GCSTRESS=50 PASLANG_GCPOISON=1" "PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=10 PASLANG_GCPOISON=1" PASLANG_GC=off; do \
	  env $$w timeout 300 $(BUILDDIR)/allocbits > $(BUILDDIR)/allocbits.got; \
	  diff -u testdata/allocbits.out $(BUILDDIR)/allocbits.got; \
	done; \
	echo ok allocbits; \
	echo "==== dwarf ===="; \
	for t in dbg dwarfloc regloop dwarfnarrow dwarfreal dwarfquad gdbg; do \
	  $(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/$$t testdata/$$t.paslang; \
	done; \
	readelf -S $(BUILDDIR)/dbg | grep -q debug_line; \
	readelf --debug-dump=line $(BUILDDIR)/dbg | grep -q 'dbg.paslang'; \
	readelf --debug-dump=info $(BUILDDIR)/dwarfloc | grep -q 'DW_AT_name.*Kept'; \
	readelf --debug-dump=info $(BUILDDIR)/dwarfloc | grep -q 'DW_AT_name.*Arg'; \
	readelf --debug-dump=info $(BUILDDIR)/dwarfloc | grep -q 'DW_OP_reg6'; \
	readelf --debug-dump=info $(BUILDDIR)/dwarfloc | grep -q 'DW_OP_fbreg: -16'; \
	readelf --debug-dump=info $(BUILDDIR)/dwarfloc | grep -q 'DW_OP_fbreg: -8'; \
	if readelf --debug-dump=info $(BUILDDIR)/dwarfloc | grep -q 'DW_AT_name.*Title'; then echo "dwarfloc describes Title, which it should not"; exit 1; fi; \
	readelf --debug-dump=info $(BUILDDIR)/dwarfloc | grep -q 'DW_AT_stmt_list'; \
	readelf --debug-dump=loc $(BUILDDIR)/regloop | grep -q 'DW_OP_reg3 (rbx)'; \
	gdb -batch -nx -ex 'set debuginfod enabled off' -ex 'break regloop.paslang:18 if j == 500' \
	  -ex 'run > /dev/null' -ex 'print j' -ex 'print N' -ex kill $(BUILDDIR)/regloop > $(BUILDDIR)/regloop.gdb 2>&1; \
	grep -q '^.1 = 500$$' $(BUILDDIR)/regloop.gdb; \
	grep -q '^.2 = 1000$$' $(BUILDDIR)/regloop.gdb; \
	readelf --debug-dump=info $(BUILDDIR)/dwarfnarrow | grep -q 'DW_AT_name *: Int8'; \
	gdb -batch -nx -ex 'set debuginfod enabled off' -ex 'break dwarfnarrow.paslang:23' \
	  -ex 'run > /dev/null' -ex 'print s8' -ex 'print u32' -ex 'print s16' -ex 'ptype w' -ex kill \
	  $(BUILDDIR)/dwarfnarrow > $(BUILDDIR)/dwarfnarrow.gdb 2>&1; \
	grep -q '^.1 = -1 ' $(BUILDDIR)/dwarfnarrow.gdb; \
	grep -q '^.2 = 4000000000$$' $(BUILDDIR)/dwarfnarrow.gdb; \
	grep -q '^.3 = -2$$' $(BUILDDIR)/dwarfnarrow.gdb; \
	grep -q '^type = Word$$' $(BUILDDIR)/dwarfnarrow.gdb; \
	gdb -batch -nx -ex 'set debuginfod enabled off' -ex 'break dwarfreal.paslang:16' \
	  -ex 'run > /dev/null' -ex 'print s' -ex 'print d' -ex 'ptype s' -ex kill \
	  $(BUILDDIR)/dwarfreal > $(BUILDDIR)/dwarfreal.gdb 2>&1; \
	grep -q '^.1 = 0.300000012$$' $(BUILDDIR)/dwarfreal.gdb; \
	grep -q '^.2 = 0.10000000000000001$$' $(BUILDDIR)/dwarfreal.gdb; \
	grep -q '^type = Single$$' $(BUILDDIR)/dwarfreal.gdb; \
	gdb -batch -nx -ex 'set debuginfod enabled off' -ex 'break dwarfquad.paslang:12' \
	  -ex 'run > /dev/null' -ex 'print q' -ex 'ptype q' -ex kill \
	  $(BUILDDIR)/dwarfquad > $(BUILDDIR)/dwarfquad.gdb 2>&1; \
	grep -q '^.1 = 0.333333333333333333333333333333333317$$' $(BUILDDIR)/dwarfquad.gdb; \
	grep -q '^type = _Float128$$' $(BUILDDIR)/dwarfquad.gdb; \
	echo ok dwarf; \
	grep -q 'cmpq 16(%r14)' $(BUILDDIR)/opt.s; \
	grep -A30 '^pas_main:' $(BUILDDIR)/opt.s | grep -q 'call rt_morestack'; \
	if grep -qF '$$99' $(BUILDDIR)/opt.s; then echo "opt.s kept the dead WriteLn(99)"; exit 1; fi; \
	echo ok opt-prologue; \
	echo "==== sleep ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/sleep testdata/sleep.paslang; \
	$(BUILDDIR)/sleep > $(BUILDDIR)/sleep.got; \
	diff -u testdata/sleep.out $(BUILDDIR)/sleep.got; \
	echo ok sleep; \
	echo "==== readln ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/readln testdata/readln.paslang; \
	printf 'hello\n' | $(BUILDDIR)/readln > $(BUILDDIR)/readln.got; \
	diff -u testdata/readln.out $(BUILDDIR)/readln.got; \
	echo ok readln; \
	echo "==== busy ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/busy testdata/busy.paslang; \
	$(BUILDDIR)/busy > $(BUILDDIR)/busy.got; \
	diff -u testdata/busy.out $(BUILDDIR)/busy.got; \
	echo ok busy; \
	echo "==== blockrd ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/blockrd testdata/blockrd.paslang; \
	{ sleep 0.2; printf 'x\n'; } | $(BUILDDIR)/blockrd > $(BUILDDIR)/blockrd.got; \
	diff -u testdata/blockrd.out $(BUILDDIR)/blockrd.got; \
	echo ok blockrd; \
	echo "==== lines ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/lines testdata/lines.paslang; \
	$(BUILDDIR)/lines > $(BUILDDIR)/lines.got; \
	test $$(wc -l < $(BUILDDIR)/lines.got) -eq 40; \
	test $$(grep -c '^xxxxxxxxxx$$' $(BUILDDIR)/lines.got) -eq 40; \
	echo ok lines; \
	echo "==== pasrut ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/pasrut testdata/pasrut.paslang; \
	$(BUILDDIR)/pasrut > $(BUILDDIR)/pasrut.got; \
	diff -u testdata/pasrut.out $(BUILDDIR)/pasrut.got; \
	echo ok pasrut; \
	echo "==== wrout ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/wrout testdata/wrout.paslang; \
	$(BUILDDIR)/wrout > $(BUILDDIR)/wrout.got; \
	test $$(wc -l < $(BUILDDIR)/wrout.got) -eq 5; \
	test $$(grep -c '^aaaa$$' $(BUILDDIR)/wrout.got) -eq 1; \
	test $$(grep -c '^bbbb$$' $(BUILDDIR)/wrout.got) -eq 1; \
	test $$(grep -c '^cccc$$' $(BUILDDIR)/wrout.got) -eq 1; \
	test $$(grep -c '^dddd$$' $(BUILDDIR)/wrout.got) -eq 1; \
	tail -n 1 $(BUILDDIR)/wrout.got | grep -q '^done$$'; \
	echo ok wrout; \
	echo "==== store short file ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/storeshort testdata/storeshort.paslang; \
	rm -f $(BUILDDIR)/storeshort.txt $(BUILDDIR)/storeshort.txt.wal; \
	printf 'forty bytes of a text file, not a store\n' > $(BUILDDIR)/storeshort.txt; \
	cp $(BUILDDIR)/storeshort.txt $(BUILDDIR)/storeshort.orig; \
	set +e; $(BUILDDIR)/storeshort $(BUILDDIR)/storeshort.txt > $(BUILDDIR)/storeshort.got 2> $(BUILDDIR)/storeshort.err; rc=$$?; set -e; \
	test $$rc -eq 1; \
	grep -q 'paslang: store magic' $(BUILDDIR)/storeshort.err; \
	cmp $(BUILDDIR)/storeshort.orig $(BUILDDIR)/storeshort.txt; \
	if [ -e $(BUILDDIR)/storeshort.txt.wal ]; then echo "storeshort made a log beside a file it refused"; exit 1; fi; \
	rm -f $(BUILDDIR)/storeshort.new $(BUILDDIR)/storeshort.new.wal; \
	$(BUILDDIR)/storeshort $(BUILDDIR)/storeshort.new | grep -q '^opened '; \
	echo ok storeshort; \
	echo "==== debug ===="; \
	$(OUTDIR)/paslangc -debug -Fu $(BUILDDIR) -o $(BUILDDIR)/debug1 testdata/debug1.paslang; \
	PASLANG_DEBUG=@paslang-debug1-$$$$ timeout 60 $(BUILDDIR)/debug1 @paslang-debug1-$$$$ > $(BUILDDIR)/debug1.got; \
	diff -u testdata/debug1.out $(BUILDDIR)/debug1.got; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/debug1-plain testdata/debug1.paslang; \
	if nm $(BUILDDIR)/debug1-plain | grep -q pasdebug; then echo "a program compiled without -debug carries the debugger"; exit 1; fi; \
	if ! nm $(BUILDDIR)/debug1 | grep -q p_pasdebug_pasdebugline; then echo "the -debug program has no debugger"; exit 1; fi; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(OUTDIR)/pasdbg cmd/pasdbg/pasdbg.paslang; \
	echo ok debug; \
	echo "==== debug console ===="; \
	$(OUTDIR)/paslangc -debug -Fu $(BUILDDIR) -o $(BUILDDIR)/debug2 testdata/debug2.paslang; \
	DEBUG2_ENV=yes timeout 60 $(BUILDDIR)/debug2 --debug-mode one two < testdata/debug2.in > $(BUILDDIR)/debug2.got 2>&1; \
	diff -u testdata/debug2.out $(BUILDDIR)/debug2.got; \
	DEBUG2_ENV=yes timeout 60 $(BUILDDIR)/debug2 --debug-mode < testdata/debug2run.in > $(BUILDDIR)/debug2run.got 2>&1; \
	diff -u testdata/debug2run.out $(BUILDDIR)/debug2run.got; \
	for t in debug2attach debug2attrun; do \
	  s=@paslang-$$t-$$$$; \
	  DEBUG2_ENV=yes timeout 60 $(BUILDDIR)/debug2 --debug-listen $$s x y > $(BUILDDIR)/$$t.prog 2>&1 & p=$$!; \
	  timeout 60 $(BUILDDIR)/debug2 --debug-attach $$s < testdata/$$t.in > $(BUILDDIR)/$$t.got 2>&1; \
	  wait $$p; \
	  echo '--- the program' >> $(BUILDDIR)/$$t.got; \
	  cat $(BUILDDIR)/$$t.prog >> $(BUILDDIR)/$$t.got; \
	  diff -u testdata/$$t.out $(BUILDDIR)/$$t.got; \
	done; \
	echo ok debug-console; \
	echo "==== tcppark ===="; \
	$(OUTDIR)/paslangc -c src/lib/pasnet.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/tcppark testdata/tcppark.paslang; \
	timeout 15 $(BUILDDIR)/tcppark > $(BUILDDIR)/tcppark.got; \
	diff -u testdata/tcppark.out $(BUILDDIR)/tcppark.got; \
	echo ok tcppark; \
	echo "==== udppark ===="; \
	$(OUTDIR)/paslangc -c src/lib/pasnet.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/udppark testdata/udppark.paslang; \
	timeout 15 $(BUILDDIR)/udppark > $(BUILDDIR)/udppark.got; \
	diff -u testdata/udppark.out $(BUILDDIR)/udppark.got; \
	echo ok udppark; \
	echo "==== ip6park ===="; \
	$(OUTDIR)/paslangc -c src/lib/pasnet.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/ip6park testdata/ip6park.paslang; \
	timeout 15 $(BUILDDIR)/ip6park > $(BUILDDIR)/ip6park.got; \
	diff -u testdata/ip6park.out $(BUILDDIR)/ip6park.got; \
	echo ok ip6park; \
	echo "==== deadln ===="; \
	$(OUTDIR)/paslangc -c src/lib/pasnet.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/deadln testdata/deadln.paslang; \
	timeout 15 $(BUILDDIR)/deadln > $(BUILDDIR)/deadln.got; \
	diff -u testdata/deadln.out $(BUILDDIR)/deadln.got; \
	echo ok deadln; \
	echo "==== edgeacc ===="; \
	$(OUTDIR)/paslangc -c src/lib/pasnet.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/edgeacc testdata/edgeacc.paslang; \
	timeout 15 $(BUILDDIR)/edgeacc > $(BUILDDIR)/edgeacc.got; \
	diff -u testdata/edgeacc.out $(BUILDDIR)/edgeacc.got; \
	echo ok edgeacc; \
	echo "==== reals ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/reals testdata/reals.paslang; \
	$(BUILDDIR)/reals > $(BUILDDIR)/reals.got; \
	diff -u testdata/reals.out $(BUILDDIR)/reals.got; \
	echo ok reals; \
	echo "==== fastmath ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/fastmath testdata/fastmath.paslang; \
	$(BUILDDIR)/fastmath > $(BUILDDIR)/fastmath.got; \
	diff -u testdata/fastmath.out $(BUILDDIR)/fastmath.got; \
	echo ok fastmath; \
	echo "==== unknown type ===="; \
	if $(OUTDIR)/paslangc -o $(BUILDDIR)/typebad testdata/typebad/unknown.paslang >$(BUILDDIR)/typebad.err 2>&1; then \
	  echo 'an unknown type should fail'; exit 1; \
	fi; \
	grep -q 'unknown type Wrod at 4:6' $(BUILDDIR)/typebad.err; \
	echo ok typebad; \
	echo "==== exception rejects (P122) ===="; \
	for n in raiseint raiseat onint onunknown onscope; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/excbad_$$n testdata/excbad/$$n.paslang >$(BUILDDIR)/excbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q 'raise takes an object of a class, not Integer at 5:9' $(BUILDDIR)/excbad_raiseint.err; \
	grep -q 'raise ... at takes a pointer, not Integer at 5:27' $(BUILDDIR)/excbad_raiseat.err; \
	grep -q 'on takes a class, not Integer at 8:11' $(BUILDDIR)/excbad_onint.err; \
	grep -q 'unknown type ENowhere at 8:11' $(BUILDDIR)/excbad_onunknown.err; \
	grep -q 'unknown identifier Err at 12:14' $(BUILDDIR)/excbad_onscope.err; \
	echo ok excbad; \
	echo "==== class method and class reference rejects (P123) ===="; \
	for n in cmfield cmobjmeth staticvirt refdesc classofint cctorargs cmnoprefix objbyclass cpropnotstatic; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/classbad_$$n testdata/classbad/$$n.paslang >$(BUILDDIR)/classbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q 'N is a field of an object, and a class method has none at 10:13' $(BUILDDIR)/classbad_cmfield.err; \
	grep -q 'Show is an object.s method, and a class method has no object at 13:3' $(BUILDDIR)/classbad_cmobjmeth.err; \
	grep -q 'a static class method is not virtual at 5:21' $(BUILDDIR)/classbad_staticvirt.err; \
	grep -q 'class of TA does not go into TBClass: TA does not descend from TB' $(BUILDDIR)/classbad_refdesc.err; \
	grep -q 'class of takes a class, not Integer at 4:17' $(BUILDDIR)/classbad_classofint.err; \
	grep -q 'a class constructor takes no parameters at 5:23' $(BUILDDIR)/classbad_cctorargs.err; \
	grep -q 'Get is declared as a class method: class goes before its body at 7:13' $(BUILDDIR)/classbad_cmnoprefix.err; \
	grep -q 'Show is an object.s method: it is called on an object, not on TA at 11:6' $(BUILDDIR)/classbad_objbyclass.err; \
	grep -q 'Get, the accessor of class property P, is a static class method or a class variable at 13:14' $(BUILDDIR)/classbad_cpropnotstatic.err; \
	echo ok classbad; \
	echo "==== array of const rejects (P124) ===="; \
	for n in keep addr closure paslist varparam vartype recval range; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/aconstbad_$$n testdata/aconstbad/$$n.paslang >$(BUILDDIR)/aconstbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q 'an array of const is read, indexed, measured, walked or passed on to another, not kept in array of TVarRec at 7:13' $(BUILDDIR)/aconstbad_keep.err; \
	grep -q 'an array of const lives for the call: its address is not taken at 7:10' $(BUILDDIR)/aconstbad_addr.err; \
	grep -q 'A, an array of const, lives for the call: a closure in P may not keep it' $(BUILDDIR)/aconstbad_closure.err; \
	grep -q 'pas passes values, and an array of const lives for the call it is given to at 7:16' $(BUILDDIR)/aconstbad_paslist.err; \
	grep -q 'an array of const is given to a routine, not a var or out parameter at 3:34' $(BUILDDIR)/aconstbad_varparam.err; \
	grep -q 'array of const is the type of a parameter at 4:15' $(BUILDDIR)/aconstbad_vartype.err; \
	grep -q 'an array of const takes ordinals, reals, strings, pointers, objects, classes and interfaces, not TR at 13:9' $(BUILDDIR)/aconstbad_recval.err; \
	grep -q 'an array of const takes values, not a range at 7:12' $(BUILDDIR)/aconstbad_range.err; \
	echo ok aconstbad; \
	echo "==== default parameter rejects (P125) ===="; \
	for n in mvar mlast mimpl nilint mcount mfew; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/defbad_$$n testdata/defbad/$$n.paslang >$(BUILDDIR)/defbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q 'default on var parameter at 5:30' $(BUILDDIR)/defbad_mvar.err; \
	grep -q 'default parameters must be last at 5:40' $(BUILDDIR)/defbad_mlast.err; \
	grep -q 'the default of X is the declaration.s at 7:14' $(BUILDDIR)/defbad_mimpl.err; \
	grep -q 'nil is the default of a pointer, an object, a class, a routine, an interface or a slice, not of Integer at 3:24' $(BUILDDIR)/defbad_nilint.err; \
	grep -q 'wrong number of arguments for P at 14:8' $(BUILDDIR)/defbad_mcount.err; \
	grep -q 'wrong number of arguments for P at 16:9' $(BUILDDIR)/defbad_mfew.err; \
	echo ok defbad; \
	echo "==== set rejects (P126) ===="; \
	for n in range ofint strelem kinds outside forvar writeset divide inclconst charint inkind; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/setbad_$$n testdata/setbad/$$n.paslang >$(BUILDDIR)/setbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q 'a set holds elements 0 to 255, not 0..300 at 3:23' $(BUILDDIR)/setbad_range.err; \
	grep -q 'a set is of Char, Byte, Boolean, an enumeration or a subrange, not Integer at 3:25' $(BUILDDIR)/setbad_ofint.err; \
	grep -q 'a set holds ordinals, not string at 5:19' $(BUILDDIR)/setbad_strelem.err; \
	grep -q 'TBytes and TChars are sets of other elements at 10:13' $(BUILDDIR)/setbad_kinds.err; \
	grep -q 'set element out of 0..7 at 7:14' $(BUILDDIR)/setbad_outside.err; \
	grep -q 'for x in TBytes: x is a Char, not an element of it at 10:15' $(BUILDDIR)/setbad_forvar.err; \
	grep -q 'Write does not print a set: x in s tests an element at 6:12' $(BUILDDIR)/setbad_writeset.err; \
	grep -q '/ does not take a set: +, -, \*, =, <>, <= and >= do at 6:13' $(BUILDDIR)/setbad_divide.err; \
	grep -q 'S is a const parameter: the routine may not change it' $(BUILDDIR)/setbad_inclconst.err; \
	grep -q 'a list in brackets holds elements of one kind, not an integer and a Char at 5:16' $(BUILDDIR)/setbad_charint.err; \
	grep -q 'Integer is no element of set of Char at 8:13' $(BUILDDIR)/setbad_inkind.err; \
	echo ok setbad; \
	echo "==== subrange rejects (P135) ===="; \
	for n in mixed reversed twoenums notfit otherenum intenum charin; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/subbad_$$n testdata/subbad/$$n.paslang >$(BUILDDIR)/subbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q 'a subrange.s bounds are of one type, not Char and Integer at 3:16' $(BUILDDIR)/subbad_mixed.err; \
	grep -q 'bad subrange: 57 is above 48 at 3:19' $(BUILDDIR)/subbad_reversed.err; \
	grep -q 'a subrange.s bounds are of one type, not TColor and TDay at 5:18' $(BUILDDIR)/subbad_twoenums.err; \
	grep -q 'constant #120 does not fit TDigit at 7:11' $(BUILDDIR)/subbad_notfit.err; \
	grep -q 'a list in brackets holds elements of one kind, not TDay and TColor at 9:19' $(BUILDDIR)/subbad_otherenum.err; \
	grep -q 'Integer is no element of a set of TDay at 7:12' $(BUILDDIR)/subbad_intenum.err; \
	grep -q 'Char is no element of set of TDay at 11:14' $(BUILDDIR)/subbad_charin.err; \
	echo ok subbad; \
	echo "==== array index rejects (P161) ===="; \
	for n in idxreal idxbig idxwide idxrev; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/arrbad_$$n testdata/arrbad/$$n.paslang >$(BUILDDIR)/arrbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q 'an array.s index is an ordinal type or a range, not Real at 5:16' $(BUILDDIR)/arrbad_idxreal.err; \
	grep -q 'an array from -9223372036854775808 to 9223372036854775807 of Byte does not fit in 2147483647 bytes at 5:12' $(BUILDDIR)/arrbad_idxbig.err; \
	grep -q 'an array from 0 to 300000000 of Integer does not fit in 2147483647 bytes at 6:12' $(BUILDDIR)/arrbad_idxwide.err; \
	grep -q 'bad subrange: 3 is above 1 at 6:16' $(BUILDDIR)/arrbad_idxrev.err; \
	echo ok arrbad; \
	echo "==== helper rejects (P127) ===="; \
	for n in typerec recint field virt clsstat lastone strict typecall nodecl ctor otherkind nomember; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/helpbad_$$n testdata/helpbad/$$n.paslang >$(BUILDDIR)/helpbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q 'a type helper is for a simple type: record helper for a record, class helper for a class, not TPoint at 7:5' $(BUILDDIR)/helpbad_typerec.err; \
	grep -q 'a record helper is for a record, not Integer at 4:5' $(BUILDDIR)/helpbad_recint.err; \
	grep -q 'a helper has methods and properties, no fields at 4:5' $(BUILDDIR)/helpbad_field.err; \
	grep -q 'a helper.s method is not virtual: a helper has no method table at 4:30' $(BUILDDIR)/helpbad_virt.err; \
	grep -q 'a helper.s class method is static: class function F: T; static; at 4:20' $(BUILDDIR)/helpbad_clsstat.err; \
	grep -q 'Twice is no member of Integer: the helper in scope, TB, has none at 24:13' $(BUILDDIR)/helpbad_lastone.err; \
	grep -q 'Hidden is strict private to TH at 24:19' $(BUILDDIR)/helpbad_strict.err; \
	grep -q 'TH.Twice is a method of a value, not of the type at 13:24' $(BUILDDIR)/helpbad_typecall.err; \
	grep -q 'TH declares no method Thrice of these parameters at 12:13' $(BUILDDIR)/helpbad_nodecl.err; \
	grep -q 'a helper has no constructor or destructor: a static class function makes a value at 4:5' $(BUILDDIR)/helpbad_ctor.err; \
	grep -q 'a helper descends from a helper of its kind at 9:22' $(BUILDDIR)/helpbad_otherkind.err; \
	grep -q 'Integer has no members: Twice needs a record, an object or a helper for Integer at 6:13' $(BUILDDIR)/helpbad_nomember.err; \
	echo ok helpbad; \
	echo "==== string word rejects (P134) ===="; \
	for n in copyslice insertconst insertslice editcall strstring strdec valchar valcode soc upint posname valname; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/strbad_$$n testdata/strbad/$$n.paslang >$(BUILDDIR)/strbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q 'Copy takes a string or a slice, not Integer at 6:21' $(BUILDDIR)/strbad_copyslice.err; \
	grep -q 'Insert(src, s, i): s needs a variable at 3:24' $(BUILDDIR)/strbad_insertconst.err; \
	grep -q 'string does not go into Integer; x as T sees its bytes at 5:20' $(BUILDDIR)/strbad_insertslice.err; \
	grep -q 'a slice that a call reaches is edited in a variable: put it in one first at 13:27' $(BUILDDIR)/strbad_editcall.err; \
	grep -q 'Str takes a number or an enumeration.s member, not string at 5:16' $(BUILDDIR)/strbad_strstring.err; \
	grep -q 'decimals are for a real at 5:16' $(BUILDDIR)/strbad_strdec.err; \
	grep -q 'Val reads a number, a real or an enumeration.s member, not Char at 6:20' $(BUILDDIR)/strbad_valchar.err; \
	grep -q 'Val(s, v, code): code is an integer variable, not string at 6:20' $(BUILDDIR)/strbad_valcode.err; \
	grep -q 'StringOfChar takes a Char, not string at 3:32' $(BUILDDIR)/strbad_soc.err; \
	grep -q 'a string or a Char goes here, not Integer at 3:20' $(BUILDDIR)/strbad_upint.err; \
	grep -q 'Pos is a reserved word, not a name at 3:3' $(BUILDDIR)/strbad_posname.err; \
	grep -q 'Val is a reserved word, not a name at 2:10' $(BUILDDIR)/strbad_valname.err; \
	echo ok strbad; \
	echo "==== scope rejects (P137) ===="; \
	for n in varproc constvar typeconst procparam twoconst outside constout; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/scopebad_$$n testdata/scopebad/$$n.paslang >$(BUILDDIR)/scopebad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q 'duplicate identifier Part (the routine has a variable or a parameter of the name)' $(BUILDDIR)/scopebad_varproc.err; \
	grep -q 'duplicate identifier K (the routine has a constant of the name)' $(BUILDDIR)/scopebad_constvar.err; \
	grep -q 'duplicate identifier TPoint (the routine has a constant of the name)' $(BUILDDIR)/scopebad_typeconst.err; \
	grep -q 'duplicate identifier X (the routine has a variable or a parameter of the name)' $(BUILDDIR)/scopebad_procparam.err; \
	grep -q 'duplicate identifier K at 7:1' $(BUILDDIR)/scopebad_twoconst.err; \
	grep -q 'unknown identifier Q at 13:4' $(BUILDDIR)/scopebad_outside.err; \
	grep -q 'unknown identifier K at 10:12' $(BUILDDIR)/scopebad_constout.err; \
	echo ok scopebad; \
	echo "==== short class forms rejects (P139) ===="; \
	for f in 'unresolved:forward type TA not resolved at 3:3' \
	  'asparent:TA is not declared whole yet: a parent class is declared before the classes that descend from it at 4:14' \
	  'selfparent:TA is not declared whole yet: a parent class is declared before the classes that descend from it at 3:14' \
	  'ifparent:IX is not declared whole yet: a parent interface is declared before the interfaces that descend from it at 4:18' \
	  'implements:IX is not declared whole yet: an interface is declared before the classes that implement it at 4:23' \
	  'mismatch:TA was declared forward as a class at 5:8' 'mismatch2:TA was declared forward as a class at 5:8' \
	  'ifclass:IX was declared forward as an interface at 5:8' 'helper:TA was declared forward as a class at 4:8' \
	  'twice:duplicate type TA at 4:3' 'done:duplicate type TA at 5:3' 'inner:forward type TA not resolved at 4:3'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/classfwdbad_$$n testdata/classfwdbad/$$n.paslang >$(BUILDDIR)/classfwdbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/classfwdbad_$$n.err || { cat $(BUILDDIR)/classfwdbad_$$n.err; exit 1; }; \
	done; \
	echo ok classfwdbad; \
	echo "==== object into interface rejects (P140) ===="; \
	for f in 'noiface:TPlain does not implement IShape at 18:22' 'parentiface:TA does not implement IBase at 24:17'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/ifacebad_$$n testdata/ifacebad/$$n.paslang >$(BUILDDIR)/ifacebad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/ifacebad_$$n.err || { cat $(BUILDDIR)/ifacebad_$$n.err; exit 1; }; \
	done; \
	echo ok ifacebad; \
	echo "==== overload ambiguities (P141) ===="; \
	for f in 'ambigset:ambiguous call G at 13:24' 'ambigref:ambiguous call H at 20:20' 'ambigptr:ambiguous call F at 22:27'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/overbad_$$n testdata/overbad/$$n.paslang >$(BUILDDIR)/overbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/overbad_$$n.err || { cat $(BUILDDIR)/overbad_$$n.err; exit 1; }; \
	done; \
	echo ok overbad; \
	echo "==== variables with a value and absolute rejects (P144) ===="; \
	for f in 'absnone:unknown variable nothing at 3:21' 'abstwo:absolute names one variable at a time at 4:15' \
	  'abstype:b: Byte absolute x: Integer; absolute is another name for a variable of its own type' \
	  'twoinit:one variable at a time takes a value at 3:15'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/varbad_$$n testdata/varbad/$$n.paslang >$(BUILDDIR)/varbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/varbad_$$n.err || { cat $(BUILDDIR)/varbad_$$n.err; exit 1; }; \
	done; \
	echo ok varbad; \
	echo "==== forward pointer rejects ===="; \
	for f in fwdopen:TX:4:9 fwdvar:TZ:4:7 fwdlater:TW:4:9; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/$$n testdata/fwdbad/$$n.paslang >$(BUILDDIR)/$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -q "unknown type $${w%%:*} at $${w#*:}" $(BUILDDIR)/$$n.err || { cat $(BUILDDIR)/$$n.err; exit 1; }; \
	done; \
	echo ok fwdbad; \
	echo "==== constant expression rejects ===="; \
	for f in 'ovadd:constant out of Integer range at 5:10' 'ovmul:constant out of Integer range at 4:10' \
	  'divzero:division by zero in a constant at 5:7' 'notconst:constant at 7:7 near v' \
	  'chrcode:char code 300 out of range at 4:7' 'realbound:integer constant at 4:15 near 2.5, which is not an integer'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/$$n testdata/constbad/$$n.paslang >$(BUILDDIR)/$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/$$n.err || { cat $(BUILDDIR)/$$n.err; exit 1; }; \
	done; \
	echo ok constbad; \
	echo "==== typed constant rejects ===="; \
	for f in 'dynarr:a typed constant cannot be a dynamic array at 3:25' 'fewvals:2 values for 3 at 3:31' \
	  'manyvals:more than 2 values at 3:31' 'nofield:unknown field Z at 7:11' 'charlen:3 characters for 4 at 3:28' \
	  'strint:an ordinal constant at 3:16' 'charcode:char code 300 out of range at 3:13' \
	  'setrange:set element out of 0..63 at 3:21'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/$$n testdata/typedbad/$$n.paslang >$(BUILDDIR)/$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/$$n.err || { cat $(BUILDDIR)/$$n.err; exit 1; }; \
	done; \
	echo ok typedbad; \
	echo "==== case label rejects ===="; \
	for f in 'overlap:duplicate case label at 7:5' 'empty:empty case range at 6:5' \
	  'dupstr:duplicate case label at 7:10' 'strlabel:a string label at 6:5'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/$$n testdata/casebad/$$n.paslang >$(BUILDDIR)/$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/$$n.err || { cat $(BUILDDIR)/$$n.err; exit 1; }; \
	done; \
	echo ok casebad; \
	echo "==== overload rejects ===="; \
	for f in 'ambig:ambiguous call Two at 15:12' 'nofit:no matching overload for Put at 12:13' \
	  'signed:no matching overload for Put at 15:10' 'varexact:no matching overload for Get at 15:9'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/$$n testdata/overbad/$$n.paslang >$(BUILDDIR)/$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/$$n.err || { cat $(BUILDDIR)/$$n.err; exit 1; }; \
	done; \
	echo ok overbad; \
	echo "==== narrow rejects ===="; \
	for f in 'const300:constant 300 does not fit Byte at 5:11 in testdata/narrowbad/const300.paslang' 'conv300:constant 300 does not fit Byte at 5:17' \
	  'negbyte:constant -1 does not fit Byte at 5:16' 'narrowing:Integer needs a conversion to Byte at 7:9' \
	  'mixed:Integer needs a conversion to Byte at 7:13' 'compare:constant 300 does not fit Byte at 7:14' \
	  'caselabel:case label does not fit Byte at 8:5' 'forlimit:constant 300 does not fit Byte at 6:21' \
	  'argument:constant 300 does not fit Byte at 9:9' 'default:default value 300 does not fit Byte at 3:26' \
	  'typedconst:constant 300 does not fit Byte at 3:13' 'nocontext:constant 300 does not fit Byte at line 6' \
	  'signtoword:Int8 needs a conversion to Word at 7:9' 'vararg:var parameter of type Integer given a Byte at 11:7' \
	  'atomic:AtomicAdd needs an 8-byte integer, not a Byte at 7:26'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/nb_$$n testdata/narrowbad/$$n.paslang >$(BUILDDIR)/nb_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/nb_$$n.err || { cat $(BUILDDIR)/nb_$$n.err; exit 1; }; \
	done; \
	echo ok narrowbad; \
	echo "==== real rejects ===="; \
	for f in 'assign:a real does not go into Integer: Trunc or Round says how at 7:9 in testdata/realbad/assign.paslang' \
	  'argument:a real does not go into Integer: Trunc or Round says how at 12:7' \
	  'exitreal:a real does not go into Integer: Trunc or Round says how at 5:13' \
	  'boolreal:a real does not go into Boolean at 7:9' \
	  'ordreal:Ord of a real: Trunc or Round says how at 6:17' \
	  'inccall:Inc of a real place that calls: assign it at 11:12'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/rb_$$n testdata/realbad/$$n.paslang >$(BUILDDIR)/rb_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/rb_$$n.err || { cat $(BUILDDIR)/rb_$$n.err; exit 1; }; \
	done; \
	echo ok realbad; \
	echo "==== single rejects ===="; \
	for f in 'assign:Double needs Single(x) to become a Single at 7:9 in testdata/singlebad/assign.paslang' \
	  'mixed:Double needs Single(x) to become a Single at 8:13' \
	  'argument:Double needs Single(x) to become a Single at 12:7' \
	  'exitdbl:Double needs Single(x) to become a Single at 5:13' \
	  'bigconst:constant 1e39 does not fit Single at 5:12' \
	  'convbig:constant 4e38 does not fit Single at 5:21' \
	  'default:default value does not fit Single at 3:29' \
	  'typedconst:a constant that does not fit Single at 3:15' \
	  'polysingle:Poly takes an array of Real at 6:23'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/sb_$$n testdata/singlebad/$$n.paslang >$(BUILDDIR)/sb_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/sb_$$n.err || { cat $(BUILDDIR)/sb_$$n.err; exit 1; }; \
	done; \
	echo ok singlebad; \
	echo "==== pointer rejects ===="; \
	for f in 'readderef:the target of an untyped Pointer needs a type: T(p^) or PT(p)^ at 7:10 in testdata/ptrbad/readderef.paslang' \
	  'storederef:the target of an untyped Pointer needs a type: T(p^) or PT(p)^ at 7:9' \
	  'writederef:the target of an untyped Pointer needs a type: T(p^) or PT(p)^ at 7:13' \
	  'arithderef:the target of an untyped Pointer needs a type: T(p^) or PT(p)^ at 7:14' \
	  'indexptr:an untyped Pointer is indexed through a view: PByte(p)[i] at 7:12' \
	  'twotypes:pointers of two types: see both through one view, PT(p) - PT(q) at 8:28' \
	  'addptrs:two pointers do not add at 7:13' \
	  'intminusptr:an integer minus a pointer at 7:13' \
	  'caretbad:^T(q) sees a pointer, a class or an address at 7:19' \
	  'reachvar:pointer outside its object: x has 8 bytes and this reaches bytes 8 to 8 at 6:27' \
	  'reachneg:pointer outside its object: x has 8 bytes and this reaches bytes -1 to -1 at 7:27' \
	  'reachwide:pointer outside its object: b has 1 byte and this reaches bytes 0 to 7 at 6:24' \
	  'reachfield:pointer outside its object: r has 12 bytes and this reaches bytes 8 to 15 at 13:26' \
	  'reachindex:pointer outside its object: a has 8 bytes and this reaches bytes 8 to 9 at 6:26' \
	  'reachview:pointer outside its object: x has 8 bytes and this reaches bytes 0 to 11 at 13:21' \
	  'reachuntyped:pointer outside its object: x has 8 bytes and this reaches bytes 0 to 11 at 13:28' \
	  'reachfill:pointer outside its object: r has 12 bytes and this reaches bytes 0 to 99 at 12:21' \
	  'reachmove:pointer outside its object: x has 8 bytes and this reaches bytes 0 to 15 at 7:16'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/pb_$$n testdata/ptrbad/$$n.paslang >$(BUILDDIR)/pb_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/pb_$$n.err || { cat $(BUILDDIR)/pb_$$n.err; exit 1; }; \
	done; \
	echo ok ptrbad; \
	echo "==== safe rejects ===="; \
	for f in 'arith:safe code does not do pointer arithmetic at 10:13 in testdata/safebad/arith.paslang' \
	  'incptr:safe code does not step a pointer at 10:9' \
	  'indexptr:safe code does not index a pointer; an array or a slice checks its index at 10:17' \
	  'view:safe code does not see memory as another type at 10:21' \
	  'caret:safe code does not see memory as another type at 7:22' \
	  'untyped:safe code does not reach through an untyped Pointer at 11:10' \
	  'fromint:safe code does not see memory as another type at 5:24' \
	  'nested:safe code does not step a pointer at 12:14' \
	  'method:safe code does not see memory as another type at 11:22' \
	  'wholeprog:safe code does not do pointer arithmetic at 7:13' \
	  'notroutine:safe goes before a routine, a unit or a program at 3:6' \
	  'viewsafe:safe code does not see memory as an array at 9:32'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/sf_$$n testdata/safebad/$$n.paslang >$(BUILDDIR)/sf_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/sf_$$n.err || { cat $(BUILDDIR)/sf_$$n.err; exit 1; }; \
	done; \
	echo ok safebad; \
	echo "==== quad rejects ===="; \
	for f in 'todouble:a Quad becomes a Double only through Double(x) at 19:9 in testdata/quadbad/todouble.paslang' \
	  'tosingle:a Quad becomes a Single only through Single(x) at 19:9' \
	  'toint:a Quad does not go into Integer: Trunc or Round says how at 19:9' \
	  'tobool:a Quad does not go into Boolean at 19:9' \
	  'nosin:sin has no Quad form: write Double(x) for it at 19:14' \
	  'fromstr:a string does not become a Quad at 19:11' \
	  'toobig:constant 1e5000 does not fit Quad at 19:14' \
	  'quaddiv:a Quad takes +, -, *, / and the comparisons at 19:15' \
	  'quadnot:not does not take a real at 19:13' \
	  'incall:Inc of a Quad place that calls: assign it at 19:12'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/qb_$$n testdata/quadbad/$$n.paslang >$(BUILDDIR)/qb_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/qb_$$n.err || { cat $(BUILDDIR)/qb_$$n.err; exit 1; }; \
	done; \
	echo ok quadbad; \
	echo "==== 1.0.116 rejects: bits, operands, Booleans, declarations ===="; \
	$(OUTDIR)/paslangc testdata/units/visu.paslang; \
	$(OUTDIR)/paslangc testdata/units/visd.paslang; \
	for f in 'callplace:+= of a place that calls: assign it at 22:11 in testdata/bitbad/callplace.paslang' \
	  'notplace:+= needs a variable at 22:8' \
	  'narrow:Integer needs a conversion to Byte at 22:9' \
	  'realnand:nand does not take a real at 22:16' \
	  'realrol:rol does not take a real at 22:15' \
	  'realdiv:div does not take a real at 22:11' \
	  'boolrol:rol takes two integers at 22:15' \
	  'strxnor:xnor does not take a string at 22:16' \
	  'strsub:- does not take a string at 22:11' \
	  'strint:+ joins a string with a string or a Char at 22:13' \
	  'strneg:- does not take a string at 22:10' \
	  'strnot:string does not go into Boolean; x as T sees its bytes at 22:13' \
	  'arradd:+ does not take an array at 22:16' \
	  'recand:a record does not go into Integer; x as T sees its bytes at 22:15' \
	  'mixnor:nor of a Boolean and an integer: a comparison binds first, so write (x and 4) = 4, or Ord(b) for the number at 22:15' \
	  'mixand:and of a Boolean and an integer: a comparison binds first, so write (x and 4) = 4, or Ord(b) for the number at 22:18' \
	  'inttobool:Integer does not go into Boolean: Boolean(x) is x <> 0 at 22:9' \
	  'booladd:Integer does not go into Boolean: Boolean(x) is x <> 0 at 22:13' \
	  'boolreal:a real does not go into Boolean: compare it at 22:18' \
	  'boolstr:Boolean() takes an ordinal or a pointer at 22:18' \
	  'quadrol:a Quad takes +, -, *, / and the comparisons at 22:11' \
	  'inexpr:an expression is expected, not = at 22:9' \
	  'laterlocal:unknown identifier n at 8:7' \
	  'bitconst:bit 8 out of range [0..7] at 22:22' \
	  'fieldconst:bits 6..9 out of range [0..7] at 22:24' \
	  'fieldwidth:GetBits takes a constant width at 22:24' \
	  'widthzero:GetBits takes a width of 1 to 8 at 22:24' \
	  'setbitconst:SetBit needs a variable at 22:18' \
	  'recbit:bit 64 out of range [0..63] at 23:23' \
	  'recfield:bits 60..67 out of range [0..63] at 23:25' \
	  'recrev:ReverseBits takes a value of up to 8 bytes at 23:22' \
	  'rawpop:PopCount of raw memory: it has no end; see it through View(p, n) at 23:20' \
	  'stratomic:AtomicSetBit of a string: its characters may be shared; use a slice or an integer at 23:26' \
	  'strcall:IsBitSet of a string or a slice that calls a routine: put it in a variable first at 23:34' \
	  'saferaw:safe code does not reach through an untyped Pointer at 23:12' \
	  'viewbig:a view of 2 bytes on Byte of 1 at 23:17' \
	  'viewrec:a view of 16 bytes on a record of 8 at 23:34' \
	  'viewval:a view of this value as array[0..7] of Byte needs a variable at 23:39' \
	  'viewwrite:a view that is written needs a variable whose place calls no routine at 23:25' \
	  'incexpr:Inc needs a variable at 23:12' \
	  'parenplace:a variable is expected before := at 23:11' \
	  'saferawview:safe code does not reach through an untyped Pointer at 23:11' \
	  'realconv:a real becomes Integer through Trunc or Round; x as Integer sees its bits at 22:17' \
	  'realbyte:a real becomes Byte through Trunc or Round; x as Byte sees its bits at 22:15' \
	  'blkptr:xor of a record, which holds strings, pointers or objects, would make addresses up at 24:15' \
	  'blksize:xor of blocks of 8 and 16 bytes at 24:16' \
	  'blkexpr:logic on a record or an array goes into a variable: r := a xor b at 24:23' \
	  'blkreal:and of array[0..1] of Integer takes a block of its size, or an integer for an array of integers at 24:15' \
	  'recint:TR does not go into Integer; x as T sees its bytes at 16:9' \
	  'strtoint:string does not go into Integer; x as T sees its bytes at 16:9' \
	  'dynelem:array of Byte does not go into array of Integer; x as T sees its bytes at 16:10' \
	  'mulhireal:MulHi takes integers at 22:19' \
	  'carryconst:AddCarry takes a variable whose place calls no routine at 22:28' \
	  'mul128byte:Mul128 takes an Integer variable at 22:21' \
	  'divmodargs:DivMod128 takes 5 arguments at 22:24' \
	  'prefint:Prefetch takes a pointer at 23:14' \
	  'aloadconst:AtomicLoad takes a variable whose place calls no routine at 23:21' \
	  "cpuname:CpuHas does not know 'avx3' at 24:21" \
	  "cpuvar:CpuHas takes the name of a feature in quotes, as CpuHas('avx2') at 25:16" \
	  'cycleargs:CycleCount takes no argument at 24:21' \
	  'vecwidth:VAdd8 takes vectors of one width, not a V128 and a V256 at 16:19' \
	  'vecint:VAdd8 takes a V128 or a V256, not Integer at 16:19' \
	  'vecsplat:VSplat8 takes an integer at 16:20' \
	  'veccount:VShl16 takes a shift count, an integer at 16:22' \
	  'vecargs:VAdd8 takes 2 arguments at 16:16' \
	  'vecdeep:a vector expression this deep needs more than the 14 vector registers: split it into two statements at 16:109' \
	  'vecnarrow:V256 does not go into V128; x as T sees its bytes at 16:9' \
	  'writevec:Write does not print a V128: view its lanes, as (v as array[0..15] of Byte)[i] at 16:12' \
	  'writerec:Write does not print a record: write its fields at 16:12' \
	  'writearr:Write does not print an array: write its elements at 16:15' \
	  'writechars:Write does not print an array: write its elements at 16:10' \
	  'vecsplatf:VSplatF32 takes a number at 10:22' \
	  'vecred:VSumU8 takes a V128 or a V256, not Integer at 10:17' \
	  'vecredint:Integer does not go into V128; x as T sees its bytes at 10:21' \
	  'asmalone:asm arm64 alone: this is compiled for amd64, so write an asm amd64 block beside it at 11:6' \
	  'asmreg:asm does not bind rsp: rsp and rbp hold the frame, r14 the running routine at 9:20' \
	  'asmtype:asm binds V128 to no integer register at 9:20' \
	  'asmxmm:asm amd64 does not bind Integer to xmm0: rax to r15 take integers, xmm a Single, a Double or a V128, ymm a V256 at 9:20' \
	  'asmout:asm out and inout take a variable at 9:21' \
	  'asmline:asm lines start on the line after the bindings at 9:23' \
	  'asmsafe:safe code does not take asm at 10:3' \
	  'asmtwo:two asm blocks for amd64 side by side at 11:7' \
	  'asmmode:an asm binding is in, out or inout at 9:17' \
	  'dupfield:x is a field already at 7:12' \
	  'dupinherit:A is a field already at 10:3' \
	  'storebig:constant 70000 does not fit Word at 23:22' \
	  'safeload:safe code does not see memory as another type at 23:19' \
	  'setbitsbig:constant 20 does not fit 4 bits at 22:23' \
	  'setbitcall:SetBit of a place that calls: assign it at 22:21' \
	  'rotptr:RotateLeftToCarry of TNamed, which holds strings, pointers or objects, would make addresses up at 15:31' \
	  'rotslptr:ShiftLeft of array of string, which holds strings, pointers or objects, would make addresses up at 8:23' \
	  'rotobj:RotateRight takes a value, not an object: turn its fields at 14:25' \
	  'rotraw:the target of an untyped Pointer needs a type: T(p^) or PT(p)^ at 10:32' \
	  'funnelmix:FunnelLeft takes two values of one type, not TPair and Integer at 14:27' \
	  'resop:rol is a reserved word, not a name at 5:3' \
	  'resdecl:override is a reserved word, not a name at 5:6' \
	  'respre:Carry is a reserved word, not a name at 6:3' \
	  'resproc:PopCount is a reserved word, not a name at 4:10' \
	  'resfield:VAdd8 is a reserved word, not a name at 6:5' \
	  'resparam:MulHi is a reserved word, not a name at 4:13' \
	  'restype:ShiftLeft is a reserved word, not a name at 5:3' \
	  'resconst:LoadFence is a reserved word, not a name at 5:3' \
	  'resmeth:Prefetch is a reserved word, not a name at 6:15' \
	  'resvar:Length is a reserved word, not a name at 5:3' \
	  'resfunc:Sin is a reserved word, not a name at 4:10' \
	  'resclear:Clear is a reserved word, not a name at 7:15' \
	  'resmax:Max is a reserved word, not a name at 4:19' \
	  'rescopy:Copy is a reserved word, not a name at 6:5' \
	  'respbyte:PByte is a reserved word, not a name at 5:3' \
	  'respi:Pi is a reserved word, not a name at 5:3' \
	  'reslow:Low is a reserved word, not a name at 9:14' \
	  'resgoid:Goid is a reserved word, not a name at 8:3' \
	  'sleepvar:sleep is a reserved word, not a name at 5:3' \
	  'appendnot:Append takes a slice first, not Integer at 8:20' \
	  'capnot:Cap takes a slice, not string at 9:14' \
	  'appendelem:string does not go into Integer; x as T sees its bytes at 8:22' \
	  'slicerange:a slice takes values, not a range at 8:14' \
	  'resappend:Append is a reserved word, not a name at 4:11' \
	  'capvar:X is a var parameter of P, which has a closure inside: a closure may outlive the variable it points at; copy it to a local at 15:4' \
	  'capresult:Result of F, which has a closure inside, is not shared with the routines in it: use a local at 19:4' \
	  'capcounter:i is the counter a closure in this loop keeps: no loop inside may count with it at 20:6' \
	  'runechar:for c in a string walks its code points: c is a Rune or an Integer, not Char at 11:15' \
	  'assignednot:Assigned takes a pointer, an object, a routine value or a slice, not Integer at 9:22' \
	  'rotcount:ShiftLeft takes a count, an integer at 22:25' \
	  'carryarg:CarryOn takes no argument at 22:13' \
	  'carryint:Integer does not go into Boolean: Boolean(x) is x <> 0 at 22:13' \
	  'rotargs:RotateLeftToCarry takes 1 or 2 arguments at 22:34' \
	  'rotfit:constant 300 does not fit Byte at 22:30' \
	  'pasvar:pas passes values: parameter 1 of Bump is a var parameter at 13:17' \
	  'pasanonargs:pas runs a routine with no parameters: pas procedure begin ... end at 8:6' \
	  'pasnotcall:pas takes a call: pas F(a, b), pas f, pas obj.M(a) or pas procedure begin ... end at 8:8' \
	  'pasbuiltin:pas takes a routine of the program, not Length at 8:16' \
	  'pasmethvar:pas passes values: parameter 1 is a var parameter at 24:11' \
	  'methvalcount:wrong number of arguments for the method value at 22:7' \
	  'pasnoargs:this routine takes 2 arguments and none are written at 18:12' \
	  'methnoargs:this routine takes 2 arguments and none are written at 20:8' \
	  'setint:a set does not go into Integer at 8:14' \
	  'lengthint:Length takes a string, an array, a slice or a map, not Integer at 8:17' \
	  'makechanneg:MakeChan takes a capacity of 0 or more at 6:19' \
	  'makechanbig:MakeChan takes a capacity of up to 67108864 at 5:25' \
	  'v128int:Integer does not go into V128: VSplat8..64 or a view makes one at 5:15' \
	  'realinc:a real does not go into Integer: Trunc or Round says how at 6:11' \
	  'realidx:a real does not go into Integer: Trunc or Round says how at 6:8' \
	  'realfor:a real does not go into Integer: Trunc or Round says how at 6:19' \
	  'realif:a real does not go into Boolean: compare it at 6:8' \
	  'realwhile:a real does not go into Boolean: compare it at 6:11' \
	  'realsetlen:a real does not go into Integer: Trunc or Round says how at 6:17' \
	  'realcase:a real does not go into a case: Trunc or Round says how at 7:10' \
	  'caseacross:empty case range 9223372036854775807..-9223372036854775808: Integer is signed, so a hex constant from $$8000000000000000 up is negative at 9:6' \
	  'succlast:Succ past the last value of TColor at 4:21' \
	  'predfirst:Pred before the first value of TColor at 4:20' \
	  'subrreal:a real does not go into TSmall: Trunc or Round says how at 7:10' \
	  'dupglobal:duplicate identifier a at 4:5' \
	  'dechuge:constant 9223372036854775809 does not fit Integer at 6:8' \
	  'dec63:constant 9223372036854775808 does not fit Integer: -9223372036854775808 is the lowest at 6:8' \
	  'hexhuge:constant $$10000000000000001 does not fit Integer at 6:9' \
	  'highmap:High takes an array, a slice, a string, an ordinal or a tree, not map[Integer] of Integer at 9:15' \
	  'visprivfield:FPriv is private to TVisBase at 11:5' \
	  'visstrictpriv:FSecret is strict private to TA at 23:13' \
	  'visprot:FProt is protected to TVisBase at 12:13' \
	  'visstrictprot:FSP is strict protected to TA at 16:5' \
	  'visprivmeth:PrivShow is private to TVisBase at 11:5' \
	  'visprivprop:Priv is private to TVisBase at 11:13' \
	  'visselfpriv:FPriv is private to TVisBase at 14:21' \
	  'visselfmeth:PrivShow is private to TVisBase at 15:3' \
	  'visstrictdesc:FSecret is strict private to TA at 17:18' \
	  'visctor:MakeHidden is private to TVisBase at 10:17' \
	  'visinh:Hid is strict private to TA at 21:3' \
	  'visstrictword:strict goes before private or protected at 7:10' \
	  'vismethval:Bump is strict private to TA at 21:10' \
	  'mapkeyreal:Real does not go into Integer, the key of map[Integer] of Integer at 9:10' \
	  'mapkeykind:Integer does not go into string, the key of map[string] of Integer at 10:12' \
	  'mapkeyfit:constant 300 does not fit Byte at 9:10' \
	  'mapforval:for k, v in map[Integer] of Integer: v is Byte, the values are Integer at 12:17' \
	  'mapforkey:for k in map[string] of Integer: k is Integer, the keys are string at 11:14' \
	  'maptryget:TryGet(m, k, v): v is string, the values of map[string] of Integer are Integer at 11:24' \
	  'mapaddr:the address of a map element is not taken: the table moves when the map grows at 10:15' \
	  'mapinto:map[string] of Integer does not go into map[Integer] of string at 10:9' \
	  'incstr:Inc takes a number, an ordinal or a pointer, not string at 9:8' \
	  'vararr:array[0..3] of Byte does not go into a var array of Byte parameter: a slice does at 13:10' \
	  'atomicval:AtomicAdd takes the address of an Integer, as AtomicAdd(@v, ...), not the Integer itself at 5:18' \
	  'atomiccasval:AtomicCas takes the address of an Integer, as AtomicCas(@v, ...), not the Integer itself at 6:25' \
	  'merklestatic:MerkleRoot takes the leaves as a slice, array of string, not the static array[0..2] of string: SetLength one and fill it at 8:36' \
	  'constwrite:S is a const parameter: the routine may not change it or pass it as var; copy it into a variable first at 5:4' \
	  'constvar:S is a const parameter: the routine may not change it or pass it as var; copy it into a variable first at 9:4'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/bb_$$n testdata/bitbad/$$n.paslang >$(BUILDDIR)/bb_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF -e "$$w" $(BUILDDIR)/bb_$$n.err || { cat $(BUILDDIR)/bb_$$n.err; exit 1; }; \
	done; \
	echo ok bitbad; \
	echo "==== treebad ===="; \
	for f in 'tryset:TryGet needs a tree with values: k in t says whether k is there at 10:24 in testdata/treebad/tryset.paslang' \
	  'setval:+= of a tree of K: t[k] is True or False, and Include(t, k) puts k in at 8:11' \
	  'jointypes:Join takes two trees of one type at 9:13' \
	  'pushtype:string does not go into Integer, the elements of heap of Integer at 9:13' \
	  'popvar:Pop(h, v): v needs a variable at 9:16' \
	  'poptype:Pop(h, v): v is string, not Integer at 10:16' \
	  'keyatreal:a real does not go into Integer: Trunc or Round says how at 8:24' \
	  'succtree:Succ takes an ordinal, or a tree and a key, not tree[Integer] of Integer at 8:18' \
	  'merkleleaves:MerkleRoot takes the leaves as a slice of strings, not Integer at 4:31' \
	  'storearg:StorePut takes a store, a key and a value, both strings at 4:24' \
	  'forkv:for k, v needs a tree with values; for k in t walks a tree of K at 10:17' \
	  'lowmap:Low takes an array, a slice, a string, an ordinal or a tree, not map[Integer] of Integer at 8:17' \
	  'includeint:Include takes a tree and a key, or a set and an element at 7:16' \
	  'poplowset:PopLow of a tree of K takes the key alone at 10:22' \
	  'rangeval:for k, v in tree[Integer] of Integer: v is string, the values are Integer at 11:23' \
	  'forinheap:for x in does not walk a heap: take its elements with Pop at 11:14' \
	  'heapname:heap is a reserved word, not a name at 4:3'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/tb_$$n testdata/treebad/$$n.paslang >$(BUILDDIR)/tb_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF -e "$$w" $(BUILDDIR)/tb_$$n.err || { cat $(BUILDDIR)/tb_$$n.err; exit 1; }; \
	done; \
	echo ok treebad; \
	echo "==== checkptr ===="; \
	$(OUTDIR)/paslangc -checkptr -o $(BUILDDIR)/cp_chk testdata/checkptr.paslang; \
	set +e; $(BUILDDIR)/cp_chk > $(BUILDDIR)/cp_chk.got 2> $(BUILDDIR)/cp_chk.err; rc=$$?; set -e; \
	test $$rc -eq 1; \
	printf 'inside 3\nviews 0 2 0\nbefore\n' | diff - $(BUILDDIR)/cp_chk.got; \
	grep -q 'paslang: pointer outside its object at line 35' $(BUILDDIR)/cp_chk.err; \
	$(OUTDIR)/paslangc -checkptr -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/cp_chk-arm testdata/checkptr.paslang; \
	set +e; timeout 60 $(QEMU_A64) $(BUILDDIR)/cp_chk-arm > $(BUILDDIR)/cp_chk-arm.got 2> $(BUILDDIR)/cp_chk-arm.err; rc=$$?; set -e; \
	test $$rc -eq 1; \
	printf 'inside 3\nviews 0 2 0\nbefore\n' | diff - $(BUILDDIR)/cp_chk-arm.got; \
	grep -q 'paslang: pointer outside its object at line 35' $(BUILDDIR)/cp_chk-arm.err; \
	for t in cparith cpderef cpindex; do \
	  $(OUTDIR)/paslangc -checkptr -o $(BUILDDIR)/fatal_$$t testdata/fatal/$$t.paslang; \
	  set +e; $(BUILDDIR)/fatal_$$t > $(BUILDDIR)/fatal_$$t.got 2> $(BUILDDIR)/fatal_$$t.err; rc=$$?; set -e; \
	  test $$rc -eq 1; \
	  diff -u testdata/fatal/expected.out $(BUILDDIR)/fatal_$$t.got; \
	  grep -q 'paslang: pointer outside its object at line 17' $(BUILDDIR)/fatal_$$t.err; \
	  $(OUTDIR)/paslangc -checkptr -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/fatal_$$t-arm testdata/fatal/$$t.paslang; \
	  set +e; timeout 60 $(QEMU_A64) $(BUILDDIR)/fatal_$$t-arm > $(BUILDDIR)/fatal_$$t-arm.got 2> $(BUILDDIR)/fatal_$$t-arm.err; rc=$$?; set -e; \
	  test $$rc -eq 1; \
	  grep -q 'paslang: pointer outside its object at line 17' $(BUILDDIR)/fatal_$$t-arm.err; \
	done; \
	for t in ptrarith ptrtyped memview ptrsafe gcbasic pchar narrowmem cpwalk ptrreach; do \
	  $(OUTDIR)/paslangc -checkptr -o $(BUILDDIR)/cpok_$$t testdata/$$t.paslang; \
	  $(BUILDDIR)/cpok_$$t > $(BUILDDIR)/cpok_$$t.got; \
	  diff -u testdata/$$t.out $(BUILDDIR)/cpok_$$t.got; \
	done; \
	$(OUTDIR)/paslangc -checkptr -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/cpok_cpwalk-arm testdata/cpwalk.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/cpok_cpwalk-arm > $(BUILDDIR)/cpok_cpwalk-arm.got; \
	diff -u testdata/cpwalk.out $(BUILDDIR)/cpok_cpwalk-arm.got; \
	grep -q 'call rt_ptrfrom' $(BUILDDIR)/cp_chk.s; \
	grep -q 'call rt_ptrarith' $(BUILDDIR)/cp_chk.s; \
	grep -qE '^[[:space:]]+bl[[:space:]]+rt_ptrfrom' $(BUILDDIR)/cp_chk-arm.s; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/cp_free testdata/cpwalk.paslang; \
	if grep -qE '^[[:space:]]+(call|bl)[[:space:]]+rt_ptr(chk|arith|from)' $(BUILDDIR)/cp_free.s; then echo "cp_free.s calls a pointer check without -checkptr"; exit 1; fi; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/cp_free-arm testdata/cpwalk.paslang; \
	if grep -qE '^[[:space:]]+(call|bl)[[:space:]]+rt_ptr(chk|arith|from)' $(BUILDDIR)/cp_free-arm.s; then echo "cp_free-arm.s calls a pointer check without -checkptr"; exit 1; fi; \
	$(OUTDIR)/paslangc -checkptr testdata/units/safeu.paslang; \
	grep -q '^CHECKPTR$$' $(BUILDDIR)/safeu.pi; \
	$(OUTDIR)/paslangc testdata/units/safeu.paslang; \
	if grep -q '^CHECKPTR$$' $(BUILDDIR)/safeu.pi; then echo "safeu.pi says CHECKPTR without -checkptr"; exit 1; fi; \
	echo ok checkptr; \
	echo "==== index checks ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/bce_s testdata/bce.paslang; \
	if sed -n '/^p_table:/,/cfi_endproc/p' $(BUILDDIR)/bce_s.s | grep -q 'call rt_boundsfail'; then echo "bce: p_table kept a bounds check the loop does not need"; exit 1; fi; \
	sed -n '/^pas_main:/,/cfi_endproc/p' $(BUILDDIR)/bce_s.s | grep -q 'call rt_boundsfail'; \
	echo ok bce; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/inplace_s testdata/inplace.paslang; \
	sed -n '/^pas_main:/,/cfi_endproc/p' $(BUILDDIR)/inplace_s.s | grep -q 'addb $$10, '; \
	sed -n '/^pas_main:/,/cfi_endproc/p' $(BUILDDIR)/inplace_s.s | grep -q 'orw $$5, '; \
	echo ok inplace; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/narrowasm_s testdata/narrowasm.paslang; \
	test $$(sed -n '/^p_noclean:/,/cfi_endproc/p' $(BUILDDIR)/narrowasm_s.s | grep -c movzbl) -eq 0; \
	test $$(sed -n '/^p_clean:/,/cfi_endproc/p' $(BUILDDIR)/narrowasm_s.s | grep -c movzbl) -eq 1; \
	sed -n '/^p_bump:/,/cfi_endproc/p' $(BUILDDIR)/narrowasm_s.s | grep -q 'addb $$1, '; \
	echo ok narrowasm; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/bitops_s testdata/bitops.paslang; \
	sed -n '/^p_pool:/,/cfi_endproc/p' $(BUILDDIR)/bitops_s.s > $(BUILDDIR)/bitops_pool.s; \
	grep -q 'rolq $$13, %r' $(BUILDDIR)/bitops_pool.s; \
	grep -q 'rolb %cl, %' $(BUILDDIR)/bitops_pool.s; \
	grep -q 'rorw %cl, %' $(BUILDDIR)/bitops_pool.s; \
	test $$(grep -A1 'sarq $$2, %r' $(BUILDDIR)/bitops_pool.s | grep -c movsbq) -eq 0; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/bitops_a testdata/bitops.paslang; \
	sed -n '/^p_pool:/,/cfi_endproc/p' $(BUILDDIR)/bitops_a.s > $(BUILDDIR)/bitops_apool.s; \
	grep -q 'ror x[0-9]*, x[0-9]*, #51$$' $(BUILDDIR)/bitops_apool.s; \
	grep -q 'ror w[0-9]*, w[0-9]*, w16$$' $(BUILDDIR)/bitops_apool.s; \
	test $$(grep -A1 'asr x[0-9]*, x[0-9]*, #2$$' $(BUILDDIR)/bitops_apool.s | grep -c sxtb) -eq 0; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/bitwords_s testdata/bitwords.paslang; \
	sed -n '/^p_pool:/,/cfi_endproc/p' $(BUILDDIR)/bitwords_s.s > $(BUILDDIR)/bitwords_pool.s; \
	for i in 'popcntq %r' 'bsfq %r' 'bsrq %r' 'bswapq %r' 'rolw $$8, %'; do \
	  grep -qF -e "$$i" $(BUILDDIR)/bitwords_pool.s || { echo "bitwords pool lacks $$i"; exit 1; }; \
	done; \
	test $$(grep -c rt_haspopcnt $(BUILDDIR)/bitwords_s.s) -eq 0; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/bitwords_b testdata/bitwords.paslang; \
	sed -n '/^p_pool:/,/cfi_endproc/p' $(BUILDDIR)/bitwords_b.s > $(BUILDDIR)/bitwords_bpool.s; \
	test $$(grep -c popcnt $(BUILDDIR)/bitwords_bpool.s) -eq 0; \
	grep -qF -e 'movabsq $$6148914691236517205, %' $(BUILDDIR)/bitwords_bpool.s; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/bitwords_a testdata/bitwords.paslang; \
	sed -n '/^p_pool:/,/cfi_endproc/p' $(BUILDDIR)/bitwords_a.s > $(BUILDDIR)/bitwords_apool.s; \
	for i in 'cnt v16.8b, v16.8b' 'rbit x' 'clz x' 'rev x' 'rev16 w'; do \
	  grep -qF -e "$$i" $(BUILDDIR)/bitwords_apool.s || { echo "bitwords arm pool lacks $$i"; exit 1; }; \
	done; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/bitmem_s testdata/bitmem.paslang; \
	grep -q 'xorw $$32768, v_w(%rip)' $(BUILDDIR)/bitmem_s.s; \
	grep -q 'andl $$-3, v_s32(%rip)' $(BUILDDIR)/bitmem_s.s; \
	grep -q 'subb $$10, v_b(%rip)' $(BUILDDIR)/bitmem_s.s; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/wide_s testdata/wide.paslang; \
	sed -n '/^p_pool:/,/cfi_endproc/p' $(BUILDDIR)/wide_s.s | grep -q 'mulq %rcx'; \
	sed -n '/^p_pool:/,/cfi_endproc/p' $(BUILDDIR)/wide_s.s | grep -q 'imulq %rcx'; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/wide_a testdata/wide.paslang; \
	sed -n '/^p_pool:/,/cfi_endproc/p' $(BUILDDIR)/wide_a.s | grep -q 'umulh x'; \
	sed -n '/^p_pool:/,/cfi_endproc/p' $(BUILDDIR)/wide_a.s | grep -q 'smulh x'; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/memwords_s testdata/memwords.paslang; \
	for i in mfence lfence sfence prefetcht0 prefetchw 'xchgq' 'lock cmpxchgl' movnti; do \
	  grep -qF -e "$$i" $(BUILDDIR)/memwords_s.s || { echo "memwords lacks $$i"; exit 1; }; \
	done; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/memwords_a testdata/memwords.paslang; \
	for i in 'dmb ish' 'dmb ishld' 'dmb ishst' 'prfm pldl1keep' 'prfm pstl1keep' 'ldarb' 'stlrb' 'ldaxr' 'stlxr'; do \
	  grep -qF -e "$$i" $(BUILDDIR)/memwords_a.s || { echo "memwords arm lacks $$i"; exit 1; }; \
	done; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/cpuwords_s testdata/cpuwords.paslang; \
	for i in 'rdtsc' 'call rt_cyclefreq' 'rt_cpufeat(%rip), %rax' 'xgetbv'; do \
	  grep -qF -e "$$i" $(BUILDDIR)/cpuwords_s.s || { echo "cpuwords lacks $$i"; exit 1; }; \
	done; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/cpuwords_a testdata/cpuwords.paslang; \
	for i in 'mrs x0, cntvct_el0' 'mrs x0, cntfrq_el0' 'ubfx x0, x0, #'; do \
	  grep -qF -e "$$i" $(BUILDDIR)/cpuwords_a.s || { echo "cpuwords arm lacks $$i"; exit 1; }; \
	done; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/cpufold_s testdata/cpufold.paslang; \
	if grep -q 'only on arm64' $(BUILDDIR)/cpufold_s.s; then echo "cpufold amd64 kept the arm64 branch"; exit 1; fi; \
	grep -q 'only on amd64' $(BUILDDIR)/cpufold_s.s; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/cpufold_a testdata/cpufold.paslang; \
	grep -q 'only on arm64' $(BUILDDIR)/cpufold_a.s; \
	if grep -q 'only on amd64' $(BUILDDIR)/cpufold_a.s; then echo "cpufold arm64 kept the amd64 branch"; exit 1; fi; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/vectors_s testdata/vectors.paslang; \
	for i in 'vpaddb %ymm' 'vpmulld %ymm' 'vzeroupper'; do \
	  grep -qF -e "$$i" $(BUILDDIR)/vectors_s.s || { echo "vectors lacks $$i"; exit 1; }; \
	done; \
	if grep -q 'btq \$$13, rt_cpufeat' $(BUILDDIR)/vectors_s.s; then echo "vectors tests rt_cpufeat at run time"; exit 1; fi; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/vectors_b testdata/vectors.paslang; \
	for i in 'paddusb %xmm' 'pmuludq %xmm' 'pminub %xmm' 'movdqu %xmm3, 16(%rax)'; do \
	  grep -qF -e "$$i" $(BUILDDIR)/vectors_b.s || { echo "vectors base lacks $$i"; exit 1; }; \
	done; \
	test $$(grep -c '%ymm' $(BUILDDIR)/vectors_b.s) -eq 0; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/vectors_a testdata/vectors.paslang; \
	for i in 'uqadd v' 'cmhi v' 'bsl v' 'ushl v' 'sshr v' 'ldr q17, [x9' 'str q17, [x9, #16]'; do \
	  grep -qF -e "$$i" $(BUILDDIR)/vectors_a.s || { echo "vectors arm lacks $$i"; exit 1; }; \
	done; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/vecmore_s testdata/vecmore.paslang; \
	for i in 'vpshufb %ymm' 'pshufb %xmm' 'vpmovmskb %ymm2, %eax' 'vextracti128 $$1' 'vcmpltps %ymm'; do \
	  grep -qF -e "$$i" $(BUILDDIR)/vecmore_s.s || { echo "vecmore lacks $$i"; exit 1; }; \
	done; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/vecmore_b testdata/vecmore.paslang; \
	for i in '(%rbp,%rdx), %ecx' 'pmovmskb %xmm' 'psadbw %xmm4' 'minps %xmm' 'packuswb %xmm' 'cvtdq2ps %xmm' 'cmpltps %xmm'; do \
	  grep -qF -e "$$i" $(BUILDDIR)/vecmore_b.s || { echo "vecmore base lacks $$i"; exit 1; }; \
	done; \
	test $$(grep -c 'pshufb\|%ymm' $(BUILDDIR)/vecmore_b.s) -eq 0; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/vecmore_a testdata/vecmore.paslang; \
	for i in 'tbl v' 'sqxtun v' 'sqxtun2 v' 'sqxtn2 v' 'fcmgt v' 'fcmge v' 'uaddlv h18' 'saddlv d18' 'addp d18' 'fsqrt v' 'scvtf v' 'zip1 v' 'zip2 v'; do \
	  grep -qF -e "$$i" $(BUILDDIR)/vecmore_a.s || { echo "vecmore arm lacks $$i"; exit 1; }; \
	done; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/inlineasm_s testdata/inlineasm.paslang; \
	for i in '  pushq %rbx' '  popq %rbx' '  sqrtsd %xmm3, %xmm3' '  vpaddw %ymm4, %ymm4, %ymm4' '  vzeroupper' '  jnz 1b'; do \
	  grep -qF -e "$$i" $(BUILDDIR)/inlineasm_s.s || { echo "inlineasm lacks $$i"; exit 1; }; \
	done; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/inlineasm_a testdata/inlineasm.paslang; \
	for i in '  str x19, [sp, #-16]!' '  ldr x19, [sp], #16' '  fsqrt d3, d3' '  add v6.16b, v5.16b, v5.16b' '  b.ne 1b'; do \
	  grep -qF -e "$$i" $(BUILDDIR)/inlineasm_a.s || { echo "inlineasm arm lacks $$i"; exit 1; }; \
	done; \
	if grep -qF 'addq %rcx, %rax' $(BUILDDIR)/inlineasm_a.s; then echo "inlineasm arm took the amd64 block"; exit 1; fi; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/vecpool_s testdata/vecpool.paslang; \
	sed -n '/^p_dot:/,/cfi_endproc/p' $(BUILDDIR)/vecpool_s.s > $(BUILDDIR)/vecpool_dot.s; \
	for i in '%xmm13' '%xmm14' '%xmm15' 'vpmulld %xmm1'; do \
	  grep -qF -e "$$i" $(BUILDDIR)/vecpool_dot.s || { echo "vecpool Dot lacks $$i"; exit 1; }; \
	done; \
	sed -n '/^p_worker:/,/cfi_endproc/p' $(BUILDDIR)/vecpool_s.s | grep -qF '%ymm14'; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/vecpool_b testdata/vecpool.paslang; \
	sed -n '/^p_worker:/,/cfi_endproc/p' $(BUILDDIR)/vecpool_b.s | grep -qF '%xmm14'; \
	test $$(grep -c '%ymm' $(BUILDDIR)/vecpool_b.s) -eq 0; \
	if sed -n '/^p_declined:/,/cfi_endproc/p' $(BUILDDIR)/vecpool_s.s | grep -qF '%xmm15'; then echo "vecpool Declined kept a viewed vector in a register"; exit 1; fi; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/vecpool_a testdata/vecpool.paslang; \
	sed -n '/^p_worker:/,/cfi_endproc/p' $(BUILDDIR)/vecpool_a.s | grep -qF 'v8.'; \
	sed -n '/^p_dot:/,/cfi_endproc/p' $(BUILDDIR)/vecpool_a.s | grep -qF 'v10.'; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/addrlocal_s testdata/addrlocal.paslang; \
	if sed -n '/^p_mix:/,/cfi_endproc/p' $(BUILDDIR)/addrlocal_s.s | grep -q 'movq %rsi, -[0-9]*(%rbp)'; then echo "addrlocal Mix kept n in memory"; exit 1; fi; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/rotwords_s testdata/rotwords.paslang; \
	for i in 'rclb $$1, %r' 'setc %r' 'btl $$0, %r'; do \
	  sed -n '/^p_ring9:/,/cfi_endproc/p' $(BUILDDIR)/rotwords_s.s | grep -qF -e "$$i" || { echo "rotwords Ring9 lacks $$i"; exit 1; }; \
	done; \
	for i in 'rclq $$1, -' 'setc %r'; do \
	  sed -n '/^p_wide256:/,/cfi_endproc/p' $(BUILDDIR)/rotwords_s.s | grep -qF -e "$$i" || { echo "rotwords Wide256 lacks $$i"; exit 1; }; \
	done; \
	for i in 'rclb $$1, -' 'rcrb $$1, -' 'shlb $$1, -' 'testb $$128, -'; do \
	  sed -n '/^p_mbyte:/,/cfi_endproc/p' $(BUILDDIR)/rotwords_s.s | grep -qF -e "$$i" || { echo "rotwords MByte lacks $$i"; exit 1; }; \
	done; \
	for i in 'rcrq $$1, ' 'shldq $$63, %rdx, %rax' 'divq %rsi'; do \
	  grep -qF -e "$$i" $(BUILDDIR)/rotwords_s.s || { echo "rotwords lacks $$i"; exit 1; }; \
	done; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/rotwords_a testdata/rotwords.paslang; \
	for i in 'extr x0, x0, x2, #63' 'strb w9, [x28, #256]' 'udiv x10, x1, x9'; do \
	  grep -qF -e "$$i" $(BUILDDIR)/rotwords_a.s || { echo "rotwords arm lacks $$i"; exit 1; }; \
	done; \
	if sed -n '/^p_ring9:/,/cfi_endproc/p' $(BUILDDIR)/rotwords_a.s | grep -qF 'ldrb w9, [x28, #256]'; then echo "rotwords arm Ring9 reads Carry from memory"; exit 1; fi; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/ctxwords_a testdata/ctxwords.paslang; \
	for i in 'bic x' 'eon x' 'orn x'; do \
	  grep -qF -e "$$i" $(BUILDDIR)/ctxwords_a.s || { echo "ctxwords arm lacks $$i"; exit 1; }; \
	done; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/rotmem_s testdata/rotmem.paslang; \
	grep -qF 'call p_pasheap_pasrotmem' $(BUILDDIR)/rotmem_s.s || { echo "rotmem does not call PasRotMem"; exit 1; }; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/rotmem_a testdata/rotmem.paslang; \
	grep -qF 'bl p_pasheap_pasrotmem' $(BUILDDIR)/rotmem_a.s || { echo "rotmem arm does not call PasRotMem"; exit 1; }; \
	echo ok bitasm; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/addrform_s testdata/addrform.paslang; \
	grep -q 'v_w5-10(,%' $(BUILDDIR)/addrform_s.s; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/addrform_a testdata/addrform.paslang; \
	grep -q ', lsl #1]' $(BUILDDIR)/addrform_a.s; \
	echo ok addrform; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/bcerun_s testdata/bcerun.paslang; \
	grep -A3 'cmovbq' $(BUILDDIR)/bcerun_s.s | grep -q 'jae'; \
	grep -q '^  .p2align 5$$' $(BUILDDIR)/bcerun_s.s; \
	echo ok bcerun; \
	echo "==== narrow Go twin ===="; \
	if command -v go > /dev/null 2>&1; then \
	  rm -rf $(BUILDDIR)/gotwin; mkdir -p $(BUILDDIR)/gotwin; \
	  cp testdata/narrowgo.go $(BUILDDIR)/gotwin/main.go; \
	  (cd $(BUILDDIR)/gotwin && GOCACHE=$(abspath $(BUILDDIR))/gocache GOFLAGS=-mod=mod go mod init narrowgo > /dev/null 2>&1 && \
	    GOCACHE=$(abspath $(BUILDDIR))/gocache GOFLAGS=-mod=mod go run .) > $(BUILDDIR)/narrowgo.go.got; \
	  diff -u testdata/narrowgo.out $(BUILDDIR)/narrowgo.go.got; \
	  echo ok narrowgo twin; \
	else \
	  echo "no go: the narrow twin is skipped"; \
	fi; \
	echo "==== forward rejects ===="; \
	if $(OUTDIR)/paslangc -o $(BUILDDIR)/forward_miss testdata/forward_miss.paslang >$(BUILDDIR)/forward_miss.err 2>&1; then \
	  echo 'missing forward body should fail'; exit 1; \
	fi; \
	grep -q 'missing body of Later' $(BUILDDIR)/forward_miss.err; \
	if $(OUTDIR)/paslangc -o $(BUILDDIR)/forward_bad testdata/forward_bad.paslang >$(BUILDDIR)/forward_bad.err 2>&1; then \
	  echo 'forward signature mismatch should fail'; exit 1; \
	fi; \
	grep -q 'implementation does not match Later' $(BUILDDIR)/forward_bad.err; \
	if $(OUTDIR)/paslangc -o $(BUILDDIR)/forward_dup testdata/forward_dup.paslang >$(BUILDDIR)/forward_dup.err 2>&1; then \
	  echo 'duplicate forward should fail'; exit 1; \
	fi; \
	grep -q 'duplicate forward Later' $(BUILDDIR)/forward_dup.err; \
	if $(OUTDIR)/paslangc -c testdata/units/fwdmiss.paslang >$(BUILDDIR)/fwdmiss.err 2>&1; then \
	  echo 'unit forward without a body should fail'; exit 1; \
	fi; \
	grep -q 'missing body of Bar' $(BUILDDIR)/fwdmiss.err; \
	if $(OUTDIR)/paslangc -o $(BUILDDIR)/defaults_order testdata/defaults_order.paslang >$(BUILDDIR)/defaults_order.err 2>&1; then \
	  echo 'default before a required parameter should fail'; exit 1; \
	fi; \
	grep -q 'default parameters must be last' $(BUILDDIR)/defaults_order.err; \
	if $(OUTDIR)/paslangc -o $(BUILDDIR)/defaults_var testdata/defaults_var.paslang >$(BUILDDIR)/defaults_var.err 2>&1; then \
	  echo 'default on var should fail'; exit 1; \
	fi; \
	grep -q 'default on var parameter' $(BUILDDIR)/defaults_var.err; \
	if $(OUTDIR)/paslangc -o $(BUILDDIR)/defaults_short testdata/defaults_short.paslang >$(BUILDDIR)/defaults_short.err 2>&1; then \
	  echo 'omitted required parameter should fail'; exit 1; \
	fi; \
	grep -q 'wrong number of arguments for Need' $(BUILDDIR)/defaults_short.err; \
	if $(OUTDIR)/paslangc -o $(BUILDDIR)/abstract_new testdata/abstract_new.paslang >$(BUILDDIR)/abstract_new.err 2>&1; then \
	  echo 'constructing an abstract class should fail'; exit 1; \
	fi; \
	grep -q 'abstract class TBase' $(BUILDDIR)/abstract_new.err; \
	if $(OUTDIR)/paslangc -o $(BUILDDIR)/abstract_mid testdata/abstract_mid.paslang >$(BUILDDIR)/abstract_mid.err 2>&1; then \
	  echo 'constructing a descendant that skipped the override should fail'; exit 1; \
	fi; \
	grep -q 'abstract class TMid' $(BUILDDIR)/abstract_mid.err; \
	if $(OUTDIR)/paslangc -o $(BUILDDIR)/abstract_body testdata/abstract_body.paslang >$(BUILDDIR)/abstract_body.err 2>&1; then \
	  echo 'a body on an abstract method should fail'; exit 1; \
	fi; \
	grep -q 'abstract method Draw' $(BUILDDIR)/abstract_body.err; \
	if $(OUTDIR)/paslangc -o $(BUILDDIR)/overload_amb testdata/overload_amb.paslang >$(BUILDDIR)/overload_amb.err 2>&1; then \
	  echo 'an ambiguous overload should fail'; exit 1; \
	fi; \
	grep -q 'ambiguous call Show' $(BUILDDIR)/overload_amb.err; \
	if $(OUTDIR)/paslangc -o $(BUILDDIR)/overload_dup testdata/overload_dup.paslang >$(BUILDDIR)/overload_dup.err 2>&1; then \
	  echo 'a duplicate overload signature should fail'; exit 1; \
	fi; \
	grep -q 'duplicate identifier Show' $(BUILDDIR)/overload_dup.err; \
	if $(OUTDIR)/paslangc -o $(BUILDDIR)/methov_dup testdata/methov_dup.paslang >$(BUILDDIR)/methov_dup.err 2>&1; then \
	  echo 'a duplicate method signature should fail'; exit 1; \
	fi; \
	grep -q 'duplicate identifier Hit' $(BUILDDIR)/methov_dup.err; \
	for f in 'trigneg:sqrt' 'sqrtsgl:sqrt' 'lnneg:ln' 'asinneg:arcsin' 'acosneg:arccos' 'powneg:power' \
	  'logneg:log' 'log2neg:log' 'asecneg:arcsec' 'acscneg:arccsc' 'acoshneg:arccosh' 'atanhneg:arctanh' \
	  'lnxp1neg:lnxp1'; do \
	  n=$${f%%:*}; w="paslang: $${f#*:} domain at line 4"; \
	  $(OUTDIR)/paslangc -o $(BUILDDIR)/$$n testdata/$$n.paslang; \
	  if $(BUILDDIR)/$$n >$(BUILDDIR)/$$n.got 2>&1; then echo "$$n should stop: $$w"; exit 1; fi; \
	  grep -qF "$$w" $(BUILDDIR)/$$n.got || { cat $(BUILDDIR)/$$n.got; exit 1; }; \
	  $(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/$$n-arm testdata/$$n.paslang; \
	  if timeout 60 $(QEMU_A64) $(BUILDDIR)/$$n-arm >$(BUILDDIR)/$$n-arm.got 2>&1; then echo "$$n should stop on arm64: $$w"; exit 1; fi; \
	  grep -qF "$$w" $(BUILDDIR)/$$n-arm.got || { cat $(BUILDDIR)/$$n-arm.got; exit 1; }; \
	done; \
	echo ok forward-rejects; \
	echo "==== units ===="; \
	$(OUTDIR)/paslangc testdata/units/adder.paslang; \
	$(OUTDIR)/paslangc testdata/units/dbl.paslang; \
	test -f $(BUILDDIR)/adder.pi; \
	test -f $(BUILDDIR)/dbl.pi; \
	grep -q PASLANGI20 $(BUILDDIR)/adder.pi; \
	$(OUTDIR)/paslangc testdata/units/quadimpl.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/quadimplmain testdata/quadimpl.paslang; \
	$(BUILDDIR)/quadimplmain > $(BUILDDIR)/quadimpl.got; \
	diff -u testdata/quadimpl.out $(BUILDDIR)/quadimpl.got; \
	$(OUTDIR)/paslangc testdata/units/quadcu.paslang; \
	grep -q '^CONST Seventh 4594314991293244562 r 2635249153387078802 4610600329231503945$$' $(BUILDDIR)/quadcu.pi; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/quadcumain testdata/quadcu.paslang; \
	$(BUILDDIR)/quadcumain > $(BUILDDIR)/quadcu.got; \
	diff -u testdata/quadcu.out $(BUILDDIR)/quadcu.got; \
	$(OUTDIR)/paslangc testdata/units/quadu.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/quadmore testdata/quadmore.paslang; \
	$(BUILDDIR)/quadmore > $(BUILDDIR)/quadmore.got; \
	diff -u testdata/quadmore.out $(BUILDDIR)/quadmore.got; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/quadu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/quadmore-arm testdata/quadmore.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/quadmore-arm > $(BUILDDIR)/quadmore-arm.got; \
	diff -u testdata/quadmore.out $(BUILDDIR)/quadmore-arm.got; \
	$(OUTDIR)/paslangc testdata/units/anonrec.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/anonrecmain testdata/anonrec.paslang; \
	PASLANG_GCVERIFY=1 $(BUILDDIR)/anonrecmain > $(BUILDDIR)/anonrec.got; \
	diff -u testdata/anonrec.out $(BUILDDIR)/anonrec.got; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/anonrec.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/anonrecmain-arm testdata/anonrec.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/anonrecmain-arm > $(BUILDDIR)/anonrec-arm.got; \
	diff -u testdata/anonrec.out $(BUILDDIR)/anonrec-arm.got; \
	$(OUTDIR)/paslangc testdata/units/visu.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) testdata/units/visd.paslang; \
	grep -q '^FLD FPriv 16 1 2$$' $(BUILDDIR)/visu.pi; \
	grep -q '^PROP ProtProp 1 FProt FProt 32 32 0 0 1 0$$' $(BUILDDIR)/visu.pi; \
	: TVisBase descends from TObject, type 17, the first after the builtins, and has its 6 slots and 2 of its own: its Destroy is slot 0 P121; \
	grep -q '^CLASS 17 8 ' $(BUILDDIR)/visu.pi; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/visuse testdata/units/visuse.paslang; \
	$(BUILDDIR)/visuse > $(BUILDDIR)/visuse.got; \
	diff -u testdata/units/visuse.out $(BUILDDIR)/visuse.got; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=3 PASLANG_GCPOISON=1 $(BUILDDIR)/visuse > $(BUILDDIR)/visuse.got; \
	diff -u testdata/units/visuse.out $(BUILDDIR)/visuse.got; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/visu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) testdata/units/visd.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/visuse-arm testdata/units/visuse.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/visuse-arm > $(BUILDDIR)/visuse-arm.got; \
	diff -u testdata/units/visuse.out $(BUILDDIR)/visuse-arm.got; \
	: class members across a unit, P123: the class variable is a global of the unit, named by the .pi; \
	$(OUTDIR)/paslangc testdata/units/clsu.paslang; \
	grep -q '^CVAR FMade 1 clsu.TNode.FMade 2$$' $(BUILDDIR)/clsu.pi; \
	grep -q '^METH Label p_clsu_tnode_label 4 0 1 -1 2 3 0 3 4 0 0 0 0 s64666c74 1 58$$' $(BUILDDIR)/clsu.pi; \
	grep -q '^VAR TNode.FMade 1 clsu.TNode.FMade$$' $(BUILDDIR)/clsu.pi; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/clsuse testdata/units/clsuse.paslang; \
	$(BUILDDIR)/clsuse > $(BUILDDIR)/clsuse.got; \
	diff -u testdata/units/clsuse.out $(BUILDDIR)/clsuse.got; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=3 PASLANG_GCPOISON=1 $(BUILDDIR)/clsuse > $(BUILDDIR)/clsuse.got; \
	diff -u testdata/units/clsuse.out $(BUILDDIR)/clsuse.got; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/clsu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/clsuse-arm testdata/units/clsuse.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/clsuse-arm > $(BUILDDIR)/clsuse-arm.got; \
	diff -u testdata/units/clsuse.out $(BUILDDIR)/clsuse-arm.got; \
	: sets across a unit, P126: a named set of 32 bytes is its image in hex, one of a word its bits; \
	$(OUTDIR)/paslangc testdata/units/setu.paslang; \
	grep -q '^CONST Digits 0 w [0-9]* s000000000000ff03000000000000000000000000000000000000000000000000$$' $(BUILDDIR)/setu.pi; \
	grep -q '^CONST Odds 170 v [0-9]*$$' $(BUILDDIR)/setu.pi; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/setuse testdata/units/setuse.paslang; \
	$(BUILDDIR)/setuse > $(BUILDDIR)/setuse.got; \
	diff -u testdata/units/setuse.out $(BUILDDIR)/setuse.got; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=3 PASLANG_GCPOISON=1 $(BUILDDIR)/setuse > $(BUILDDIR)/setuse.got; \
	diff -u testdata/units/setuse.out $(BUILDDIR)/setuse.got; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/setu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/setuse-arm testdata/units/setuse.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/setuse-arm > $(BUILDDIR)/setuse-arm.got; \
	diff -u testdata/units/setuse.out $(BUILDDIR)/setuse-arm.got; \
	: subranges across a unit, P135: an enumeration member says its type, a subrange its host; \
	$(OUTDIR)/paslangc testdata/units/subu.paslang; \
	grep -q '^CONST Thu 3 v [0-9]*$$' $(BUILDDIR)/subu.pi; \
	grep -q '^TYPE TDigit [0-9]* 13 8 4 48 57 ' $(BUILDDIR)/subu.pi; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/subuse testdata/units/subuse.paslang; \
	$(BUILDDIR)/subuse > $(BUILDDIR)/subuse.got; \
	diff -u testdata/units/subuse.out $(BUILDDIR)/subuse.got; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/subu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/subuse-arm testdata/units/subuse.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/subuse-arm > $(BUILDDIR)/subuse-arm.got; \
	diff -u testdata/units/subuse.out $(BUILDDIR)/subuse-arm.got; \
	: helpers across a unit, P127: a TYPE of kind 24 with its methods, the parent on a CLASS line; \
	$(OUTDIR)/paslangc testdata/units/helpu.paslang; \
	grep -q '^TYPE TStrTools [0-9]* 24 0 3 0 ' $(BUILDDIR)/helpu.pi; \
	grep -q '^PROP Width 1 GetWidth _ ' $(BUILDDIR)/helpu.pi; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/helpuse testdata/units/helpuse.paslang; \
	$(BUILDDIR)/helpuse > $(BUILDDIR)/helpuse.got; \
	diff -u testdata/units/helpuse.out $(BUILDDIR)/helpuse.got; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/helppriv testdata/units/helppriv.paslang > $(BUILDDIR)/helppriv.err 2>&1; then \
	  echo 'a helper.s private method called from another unit should be refused'; exit 1; \
	fi; \
	grep -q 'Pad is private to TStrTools.s unit at 9:19' $(BUILDDIR)/helppriv.err; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/helpu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/helpuse-arm testdata/units/helpuse.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/helpuse-arm > $(BUILDDIR)/helpuse-arm.got; \
	diff -u testdata/units/helpuse.out $(BUILDDIR)/helpuse-arm.got; \
	: one name in two units, P138: the last unit in uses hides, the unit name reaches; \
	$(OUTDIR)/paslangc testdata/units/shada.paslang; \
	$(OUTDIR)/paslangc testdata/units/shadb.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/shaduse testdata/units/shaduse.paslang; \
	$(BUILDDIR)/shaduse > $(BUILDDIR)/shaduse.got; \
	diff -u testdata/units/shaduse.out $(BUILDDIR)/shaduse.got; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/shadbad testdata/units/shadbad.paslang > $(BUILDDIR)/shadbad.err 2>&1; then \
	  echo 'a name its unit does not have should be refused'; exit 1; \
	fi; \
	grep -q 'unknown identifier shada.Nope at 4:21' $(BUILDDIR)/shadbad.err; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/shada.paslang; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/shadb.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/shaduse-arm testdata/units/shaduse.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/shaduse-arm > $(BUILDDIR)/shaduse-arm.got; \
	diff -u testdata/units/shaduse.out $(BUILDDIR)/shaduse-arm.got; \
	: a program hides a unit type with its own, P155: a record, an alias, an enumeration, a class; \
	$(OUTDIR)/paslangc testdata/units/hideu.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/hideuse testdata/units/hideuse.paslang; \
	$(BUILDDIR)/hideuse > $(BUILDDIR)/hideuse.got; \
	diff -u testdata/units/hideuse.out $(BUILDDIR)/hideuse.got; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/hideu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/hideuse-arm testdata/units/hideuse.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/hideuse-arm > $(BUILDDIR)/hideuse-arm.got; \
	diff -u testdata/units/hideuse.out $(BUILDDIR)/hideuse-arm.got; \
	: a program hides every kind of a unit name with every kind of its own, P158; \
	$(OUTDIR)/paslangc testdata/units/hidek.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/hidekuse testdata/units/hidekuse.paslang; \
	$(BUILDDIR)/hidekuse > $(BUILDDIR)/hidekuse.got; \
	diff -u testdata/units/hidekuse.out $(BUILDDIR)/hidekuse.got; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/hidek.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/hidekuse-arm testdata/units/hidekuse.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/hidekuse-arm > $(BUILDDIR)/hidekuse-arm.got; \
	diff -u testdata/units/hidekuse.out $(BUILDDIR)/hidekuse-arm.got; \
	: a later unit hides an earlier unit name of another kind, and a unit type is reached in every place, P158; \
	$(OUTDIR)/paslangc testdata/units/hidea.paslang; \
	$(OUTDIR)/paslangc testdata/units/hideb.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/hideab testdata/units/hideab.paslang; \
	$(BUILDDIR)/hideab > $(BUILDDIR)/hideab.got; \
	diff -u testdata/units/hideab.out $(BUILDDIR)/hideab.got; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/hidea.paslang; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/hideb.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/hideab-arm testdata/units/hideab.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/hideab-arm > $(BUILDDIR)/hideab-arm.got; \
	diff -u testdata/units/hideab.out $(BUILDDIR)/hideab-arm.got; \
	: a unit names hide those of a unit its implementation uses, P158; \
	$(OUTDIR)/paslangc testdata/units/hidelo.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) testdata/units/hidehi.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/hideimpl testdata/units/hideimpl.paslang; \
	$(BUILDDIR)/hideimpl > $(BUILDDIR)/hideimpl.got; \
	diff -u testdata/units/hideimpl.out $(BUILDDIR)/hideimpl.got; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/hidelo.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) testdata/units/hidehi.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/hideimpl-arm testdata/units/hideimpl.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/hideimpl-arm > $(BUILDDIR)/hideimpl-arm.got; \
	diff -u testdata/units/hideimpl.out $(BUILDDIR)/hideimpl-arm.got; \
	: two units that declare the same class, interface, record and helper names, P154; \
	$(OUTDIR)/paslangc testdata/units/twina.paslang; \
	$(OUTDIR)/paslangc testdata/units/twinb.paslang; \
	grep -q '^CSYM twina_tshape$$' $(BUILDDIR)/twina.pi; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/twinuse testdata/units/twinuse.paslang; \
	$(BUILDDIR)/twinuse > $(BUILDDIR)/twinuse.got; \
	diff -u testdata/units/twinuse.out $(BUILDDIR)/twinuse.got; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/twina.paslang; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/twinb.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/twinuse-arm testdata/units/twinuse.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/twinuse-arm > $(BUILDDIR)/twinuse-arm.got; \
	diff -u testdata/units/twinuse.out $(BUILDDIR)/twinuse-arm.got; \
	: classes that name each other in a unit, P139: a forward class, its descendant before its parent; \
	$(OUTDIR)/paslangc testdata/units/clsfwdu.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/clsfwduse testdata/units/clsfwduse.paslang; \
	$(BUILDDIR)/clsfwduse > $(BUILDDIR)/clsfwduse.got; \
	diff -u testdata/units/clsfwduse.out $(BUILDDIR)/clsfwduse.got; \
	if $(OUTDIR)/paslangc -o $(BUILDDIR)/clsfwdbadu testdata/units/clsfwdbadu.paslang > $(BUILDDIR)/clsfwdbadu.err 2>&1; then \
	  echo 'a forward class of the interface declared in the implementation should be refused'; exit 1; \
	fi; \
	grep -q 'forward type TLeaf not resolved at 6:3' $(BUILDDIR)/clsfwdbadu.err; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/clsfwdu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/clsfwduse-arm testdata/units/clsfwduse.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/clsfwduse-arm > $(BUILDDIR)/clsfwduse-arm.got; \
	diff -u testdata/units/clsfwduse.out $(BUILDDIR)/clsfwduse-arm.got; \
	: the variables of a unit with a value and one absolute over another, exported, P144; \
	$(OUTDIR)/paslangc testdata/units/ivu.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/ivuse testdata/units/ivuse.paslang; \
	$(BUILDDIR)/ivuse > $(BUILDDIR)/ivuse.got; \
	diff -u testdata/units/ivuse.out $(BUILDDIR)/ivuse.got; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/ivu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/ivuse-arm testdata/units/ivuse.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/ivuse-arm > $(BUILDDIR)/ivuse-arm.got; \
	diff -u testdata/units/ivuse.out $(BUILDDIR)/ivuse-arm.got; \
	: a unit built for a processor level, P143: a program links the build its -cpu allows; \
	$(OUTDIR)/paslangc -cpu base testdata/units/lvlu.paslang; \
	$(OUTDIR)/paslangc -cpu $(LVL_X64) -c -Fu $(BUILDDIR) -o $(BUILDDIR)/$(LVL_X64)/lvlu testdata/units/lvlu.paslang; \
	for c in base $(LVL_X64); do \
	  $(OUTDIR)/paslangc -cpu $$c -Fu $(BUILDDIR) -o $(BUILDDIR)/lvluse-$$c testdata/units/lvluse.paslang; \
	  $(BUILDDIR)/lvluse-$$c > $(BUILDDIR)/lvluse-$$c.got; \
	  diff -u testdata/units/lvluse.out $(BUILDDIR)/lvluse-$$c.got; \
	done; \
	objdump -d --no-show-raw-insn $(BUILDDIR)/lvluse-base | awk '/<p_lvlu_check>:/,/ret/' | grep -q pascrc32cbase; \
	objdump -d --no-show-raw-insn $(BUILDDIR)/lvluse-$(LVL_X64) | awk '/<p_lvlu_check>:/,/ret/' | grep -q pascrc32ccpu; \
	for c in base $(LVL_X64); do \
	  $(OUTDIR)/paslangc -cpu $$c -o $(BUILDDIR)/sysutils1-$$c testdata/sysutils1.paslang; \
	  $(BUILDDIR)/sysutils1-$$c > $(BUILDDIR)/sysutils1-$$c.got; \
	  diff -u testdata/sysutils1.out $(BUILDDIR)/sysutils1-$$c.got; \
	done; \
	objdump -d --no-show-raw-insn $(BUILDDIR)/sysutils1-base | awk '/<p_sysutils_uppercase>:/,/ret/' | grep -q pasupperbase; \
	objdump -d --no-show-raw-insn $(BUILDDIR)/sysutils1-$(LVL_X64) | awk '/<p_sysutils_uppercase>:/,/ret/' | grep -q pasuppercpu; \
	$(OUTDIR)/paslangc -target arm64 -cpu base testdata/units/lvlu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -cpu $(LVL_A64) -c -Fu $(A64DIR) -o '$(A64DIR)/$(LVL_A64)/lvlu' testdata/units/lvlu.paslang; \
	for c in base max; do \
	  $(OUTDIR)/paslangc -target arm64 -cpu $$c -Fu $(A64DIR) -o $(BUILDDIR)/lvluse-arm-$$c testdata/units/lvluse.paslang; \
	  timeout 60 $(QEMU_A64) $(BUILDDIR)/lvluse-arm-$$c > $(BUILDDIR)/lvluse-arm-$$c.got; \
	  diff -u testdata/units/lvluse.out $(BUILDDIR)/lvluse-arm-$$c.got; \
	done; \
	$(A64_OBJDUMP) -d --no-show-raw-insn $(BUILDDIR)/lvluse-arm-base | awk '/<p_lvlu_check>:/,/ret/' | grep -q pascrc32cbase; \
	$(A64_OBJDUMP) -d --no-show-raw-insn $(BUILDDIR)/lvluse-arm-max | awk '/<p_lvlu_check>:/,/ret/' | grep -q pascrc32ccpu; \
	: the ifdef words of -cpu, P148: one CPU_ word for each feature; \
	for c in base $(LVL_X64); do \
	  $(OUTDIR)/paslangc -cpu $$c -o $(BUILDDIR)/cpudefs-$$c testdata/cpudefs.paslang; \
	  $(BUILDDIR)/cpudefs-$$c > $(BUILDDIR)/cpudefs-$$c.got; \
	  diff -u testdata/cpudefs-$$c.out $(BUILDDIR)/cpudefs-$$c.got; \
	done; \
	for c in base max; do \
	  $(OUTDIR)/paslangc -target arm64 -cpu $$c -o $(BUILDDIR)/cpudefs-arm-$$c testdata/cpudefs.paslang; \
	  timeout 60 $(QEMU_A64) $(BUILDDIR)/cpudefs-arm-$$c > $(BUILDDIR)/cpudefs-arm-$$c.got; \
	  diff -u testdata/cpudefs-arm-$$c.out $(BUILDDIR)/cpudefs-arm-$$c.got; \
	done; \
	$(OUTDIR)/paslangc testdata/units/safeu.paslang; \
	grep -q '^SAFE$$' $(BUILDDIR)/safeu.pi; \
	if grep -q '^SAFE$$' $(BUILDDIR)/adder.pi; then echo "adder.pi says SAFE for a unit that is not safe"; exit 1; fi; \
	grep -q "^DEP pasroutines " $(BUILDDIR)/adder.pi; \
	if grep -qi implementation $(BUILDDIR)/adder.pi; then echo "adder.pi carries the implementation"; exit 1; fi; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/umain testdata/units/main.paslang; \
	$(BUILDDIR)/umain > $(BUILDDIR)/umain.got; \
	diff -u testdata/units/main.out $(BUILDDIR)/umain.got; \
	cp $(BUILDDIR)/adder.pi $(BUILDDIR)/adder.pi.saved; \
	$(OUTDIR)/paslangc testdata/units/adder_mul.paslang; \
	diff -u $(BUILDDIR)/adder.pi.saved $(BUILDDIR)/adder.pi; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) testdata/units/twice.paslang; \
	grep -q "^DEP adder " $(BUILDDIR)/twice.pi; \
	$(OUTDIR)/paslangc testdata/units/adder_extra.paslang; \
	if cmp -s $(BUILDDIR)/adder.pi.saved $(BUILDDIR)/adder.pi; then \
	  echo 'interface checksum should change'; exit 1; \
	fi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/twiceuse testdata/units/twiceuse.paslang > $(BUILDDIR)/twiceuse.err 2>&1; then \
	  echo 'a unit compiled against another adder should be refused'; exit 1; \
	fi; \
	grep -q 'twice.pi was compiled against another adder.pi; compile twice again' $(BUILDDIR)/twiceuse.err; \
	$(OUTDIR)/paslangc testdata/units/adder.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/twiceuse testdata/units/twiceuse.paslang; \
	$(BUILDDIR)/twiceuse > $(BUILDDIR)/twiceuse.got; \
	diff -u testdata/units/twiceuse.out $(BUILDDIR)/twiceuse.got; \
	rm -rf $(BUILDDIR)/oldpi; mkdir -p $(BUILDDIR)/oldpi; \
	sed '1s/PASLANGI20/PASLANGI1/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	cp $(BUILDDIR)/dbl.o $(BUILDDIR)/oldpi/; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.49 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.49; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI20/PASLANGI2/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.55 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.55; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI20/PASLANGI3/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.58 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.58; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI20/PASLANGI4/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.87 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.87; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI20/PASLANGI5/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.91 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.91; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI20/PASLANGI6/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.104 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.104; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI20/PASLANGI7/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.108 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.108; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI20/PASLANGI8/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.110 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.110; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI20/PASLANGI9/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.114 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.114; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI20/PASLANGI10/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.125 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.125; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI20/PASLANGI11/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.133 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.133; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI20/PASLANGI12/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.137 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.137; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI20/PASLANGI13/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.1.2 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.2; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI20/PASLANGI14/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.1.4 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.4; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI20/PASLANGI15/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.1.6 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.6; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI20/PASLANGI16/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.1.7 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.7; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI20/PASLANGI17/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.1.8 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.8; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI20/PASLANGI18/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.1.9 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.9; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI20/PASLANGI19/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.1.28 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.28; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI20/PASLANGI21/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from a later paslang should be refused'; exit 1; \
	fi; \
	grep -q 'was compiled by a newer paslang (PASLANGI21); compile dbl again with this one' $(BUILDDIR)/oldpi.err; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/pisum testdata/units/pisum.paslang; \
	sed 's/^TYPE Byte 6 1 1 /TYPE Byte 6 1 4 /' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	$(BUILDDIR)/pisum $(BUILDDIR)/oldpi/dbl.pi; \
	grep -q '^TYPE Byte 6 1 4 ' $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'a unit with other builtin types should be refused'; exit 1; \
	fi; \
	grep -q 'a compiled unit has other builtin types (Byte): compile it again' $(BUILDDIR)/oldpi.err; \
	echo ok units; \
	echo "==== unit init ===="; \
	$(OUTDIR)/paslangc testdata/units/inita.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) testdata/units/initb.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/initp testdata/units/initp.paslang; \
	$(BUILDDIR)/initp > $(BUILDDIR)/initp.got; \
	diff -u testdata/units/initp.out $(BUILDDIR)/initp.got; \
	echo "==== kconst ===="; \
	$(OUTDIR)/paslangc testdata/units/kconst.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/kconstuse testdata/units/kconstuse.paslang; \
	$(BUILDDIR)/kconstuse > $(BUILDDIR)/kconstuse.got; \
	diff -u testdata/units/kconstuse.out $(BUILDDIR)/kconstuse.got; \
	echo ok kconst; \
	echo ok init; \
	echo "==== unit forward ===="; \
	$(OUTDIR)/paslangc testdata/units/fwda.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/fwduse testdata/units/fwduse.paslang; \
	$(BUILDDIR)/fwduse > $(BUILDDIR)/fwduse.got; \
	diff -u testdata/units/fwduse.out $(BUILDDIR)/fwduse.got; \
	echo ok fwduse; \
	echo "==== unit defaults ===="; \
	$(OUTDIR)/paslangc testdata/units/defu.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/defuse testdata/units/defuse.paslang; \
	$(BUILDDIR)/defuse > $(BUILDDIR)/defuse.got; \
	diff -u testdata/units/defuse.out $(BUILDDIR)/defuse.got; \
	echo ok defuse; \
	echo "==== unit variables ===="; \
	$(OUTDIR)/paslangc testdata/units/uvar.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) testdata/units/uvar2.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/uvaruse testdata/units/uvaruse.paslang; \
	$(BUILDDIR)/uvaruse > $(BUILDDIR)/uvaruse.got; \
	diff -u testdata/units/uvaruse.out $(BUILDDIR)/uvaruse.got; \
	PASLANG_GCSTRESS=3 PASLANG_GCVERIFY=1 PASLANG_GCPOISON=1 $(BUILDDIR)/uvaruse > $(BUILDDIR)/uvaruse.got; \
	diff -u testdata/units/uvaruse.out $(BUILDDIR)/uvaruse.got; \
	echo ok uvaruse; \
	echo "==== unit string default ===="; \
	$(OUTDIR)/paslangc testdata/units/sdef.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/suse testdata/units/suse.paslang; \
	$(BUILDDIR)/suse > $(BUILDDIR)/suse.got; \
	diff -u testdata/units/suse.out $(BUILDDIR)/suse.got; \
	echo ok suse; \
	echo "==== unit pointer result ===="; \
	$(OUTDIR)/paslangc testdata/units/filler.paslang; \
	$(OUTDIR)/paslangc testdata/units/retbox.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/retuse testdata/units/retuse.paslang; \
	$(BUILDDIR)/retuse > $(BUILDDIR)/retuse.got; \
	diff -u testdata/units/retuse.out $(BUILDDIR)/retuse.got; \
	echo ok retuse; \
	echo "==== unit map ===="; \
	$(OUTDIR)/paslangc testdata/units/mapu.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/mapuse testdata/units/mapuse.paslang; \
	$(BUILDDIR)/mapuse > $(BUILDDIR)/mapuse.got; \
	diff -u testdata/units/mapuse.out $(BUILDDIR)/mapuse.got; \
	echo ok mapuse; \
	echo "==== unit globals in registers ===="; \
	$(OUTDIR)/paslangc testdata/units/regu.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/reguse testdata/units/reguse.paslang; \
	$(BUILDDIR)/reguse > $(BUILDDIR)/reguse.got; \
	diff -u testdata/units/reguse.out $(BUILDDIR)/reguse.got; \
	echo ok reguse; \
	echo "==== pkg ===="; \
	$(OUTDIR)/paslangc -install $(BUILDDIR)/pkg testdata/pkg/arithkit.paslang; \
	test -f $(BUILDDIR)/pkg/scale.pi; \
	test -f $(BUILDDIR)/pkg/incn.o; \
	grep -q PASLANGPKG1 $(BUILDDIR)/pkg/arithkit.pkg; \
	grep -q 'UNIT scale' $(BUILDDIR)/pkg/arithkit.pkg; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR)/pkg -o $(BUILDDIR)/pkgmain testdata/pkg/useit.paslang; \
	$(BUILDDIR)/pkgmain > $(BUILDDIR)/pkgmain.got; \
	diff -u testdata/pkg/useit.out $(BUILDDIR)/pkgmain.got; \
	echo ok pkg; \
	echo "==== xcanvas ===="; \
	$(OUTDIR)/paslangc -c -Fu $(BUILDDIR) src/lib/paslinux.paslang; \
	$(OUTDIR)/paslangc -c -Fu $(BUILDDIR) src/lib/paslib.paslang; \
	$(OUTDIR)/paslangc -c -Fu $(BUILDDIR) src/lib/pasx11.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/xcanvas testdata/xcanvas.paslang; \
	$$xrun $(BUILDDIR)/xcanvas > $(BUILDDIR)/xcanvas.got; \
	diff -u testdata/xcanvas.out $(BUILDDIR)/xcanvas.got; \
	echo ok xcanvas; \
	echo "==== dirlist ===="; \
	$(OUTDIR)/paslangc -c -Fu $(BUILDDIR) src/lib/paslinux.paslang; \
	$(OUTDIR)/paslangc -c -Fu $(BUILDDIR) src/lib/paslib.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/dirlist testdata/dirlist.paslang; \
	$(BUILDDIR)/dirlist > $(BUILDDIR)/dirlist.got; \
	diff -u testdata/dirlist.out $(BUILDDIR)/dirlist.got; \
	echo ok dirlist; \
	echo "==== nilmap ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/nilmap testdata/nilmap.paslang; \
	set +e; $(BUILDDIR)/nilmap > $(BUILDDIR)/nilmap.got 2> $(BUILDDIR)/nilmap.err; rc=$$?; set -e; \
	test $$rc -eq 1; \
	diff -u testdata/nilmap.out $(BUILDDIR)/nilmap.got; \
	grep -q 'paslang: nil map' $(BUILDDIR)/nilmap.err; \
	echo ok nilmap; \
	echo "==== dupbad ===="; \
	for t in param twice field meth parammeth; do \
	  set +e; $(OUTDIR)/paslangc -o $(BUILDDIR)/dup_$$t testdata/dupbad/$$t.paslang > $(BUILDDIR)/dup_$$t.err 2>&1; rc=$$?; set -e; \
	  test $$rc -eq 1; \
	  grep -q 'duplicate identifier' $(BUILDDIR)/dup_$$t.err; \
	done; \
	grep -q 'it is a parameter' $(BUILDDIR)/dup_param.err; \
	grep -q 'it is a field of TA' $(BUILDDIR)/dup_field.err; \
	grep -q 'it is a method of TA' $(BUILDDIR)/dup_meth.err; \
	grep -q 'duplicate identifier Lab (it is a method of TA)' $(BUILDDIR)/dup_parammeth.err; \
	echo ok dupbad; \
	echo "==== duplicate names say where, P151 ===="; \
	for f in 'constproc:duplicate identifier Area (a constant of the name) at 6:10' \
	  'constvar:duplicate identifier Limit (a constant of the name) at 7:3' \
	  'enumconst:duplicate identifier Red (a constant of the name) at 7:20' \
	  'localtwice:duplicate identifier b (the routine already has one) at 6:3' \
	  'paramproc:duplicate identifier Format (a routine of the name) at 8:16' \
	  'procproc:duplicate identifier Half (a routine with the same parameters) at 8:10' \
	  'typetwice:duplicate type TPoint at 7:3' \
	  'varconst:duplicate identifier Count (a variable of the name) at 7:3' \
	  'varproc:duplicate identifier Show (a routine of the name) at 9:3' \
	  'aliastwice:duplicate type TPoint at 7:3' 'enumtwice:duplicate type TKind at 7:3' \
	  'reftwice:duplicate type TShapeClass at 7:3' \
	  'procvar:duplicate identifier Show (a variable of the name) at 6:11' \
	  'typevar:duplicate identifier TCount (a type of the name) at 7:3' \
	  'vartype:duplicate identifier Count (a variable of the name) at 7:3' \
	  'consttype:duplicate identifier Size (a constant of the name) at 7:3' \
	  'typeproc:duplicate identifier TShow (a type of the name) at 6:11' \
	  'enumvar:duplicate identifier Green (a constant of the name) at 7:3'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/dupw_$$n testdata/dupwhere/$$n.paslang >$(BUILDDIR)/dupw_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/dupw_$$n.err || { cat $(BUILDDIR)/dupw_$$n.err; exit 1; }; \
	done; \
	echo ok dupwhere; \
	echo "==== wgneg ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/wgneg testdata/wgneg.paslang; \
	set +e; $(BUILDDIR)/wgneg > $(BUILDDIR)/wgneg.got 2> $(BUILDDIR)/wgneg.err; rc=$$?; set -e; \
	test $$rc -eq 1; \
	diff -u testdata/wgneg.out $(BUILDDIR)/wgneg.got; \
	grep -q 'paslang: negative waitgroup counter' $(BUILDDIR)/wgneg.err; \
	echo ok wgneg; \
	echo "==== unlockfree ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/unlockfree testdata/unlockfree.paslang; \
	set +e; $(BUILDDIR)/unlockfree > $(BUILDDIR)/unlockfree.got 2> $(BUILDDIR)/unlockfree.err; rc=$$?; set -e; \
	test $$rc -eq 1; \
	diff -u testdata/unlockfree.out $(BUILDDIR)/unlockfree.got; \
	grep -q 'paslang: unlock of an unlocked mutex' $(BUILDDIR)/unlockfree.err; \
	echo ok unlockfree; \
	echo "==== fatal ===="; \
	for t in divzero nilptr deep oom oomlimit closed divloop bstatic bslice bstring bneg bempty bloop bref bnested bconst bstrcall bsame bslicereg bversion bslicehi bviewneg rrtrunc rrround rrfloor rrceil qtrunc qsqrt bitchk bitneg bitpool bitfield bitstr bitempty bitrec bitcall bitslice viewstr blkstr divover divzero128 funnelstr funnelslice mainraise raiseobj setelem setincl; do \
	  $(OUTDIR)/paslangc -o $(BUILDDIR)/fatal_$$t testdata/fatal/$$t.paslang; \
	  set +e; \
	  if [ $$t = oomlimit ]; then \
	    (ulimit -v 409600; $(BUILDDIR)/fatal_$$t > $(BUILDDIR)/fatal_$$t.got 2> $(BUILDDIR)/fatal_$$t.err); rc=$$?; \
	  else \
	    $(BUILDDIR)/fatal_$$t > $(BUILDDIR)/fatal_$$t.got 2> $(BUILDDIR)/fatal_$$t.err; rc=$$?; \
	  fi; \
	  set -e; \
	  test $$rc -eq 1; \
	  diff -u testdata/fatal/expected.out $(BUILDDIR)/fatal_$$t.got; \
	done; \
	grep -q 'paslang: integer divide by zero at line 11' $(BUILDDIR)/fatal_divzero.err; \
	grep -q 'paslang: nil pointer dereference at line 16' $(BUILDDIR)/fatal_nilptr.err; \
	grep -q 'paslang: stack overflow at line 12' $(BUILDDIR)/fatal_deep.err; \
	grep -q 'paslang: out of memory: [0-9][0-9]* MiB mapped' $(BUILDDIR)/fatal_oom.err; \
	grep -q 'paslang: out of memory: [0-9][0-9]* MiB mapped' $(BUILDDIR)/fatal_oomlimit.err; \
	grep -q 'paslang: send on closed channel at line 11' $(BUILDDIR)/fatal_closed.err; \
	grep -q 'paslang: uncaught raise in the main routine' $(BUILDDIR)/fatal_mainraise.err; \
	grep -q 'paslang: uncaught raise in the main routine: EOops' $(BUILDDIR)/fatal_raiseobj.err; \
	grep -q 'paslang: set element 300 out of range \[0..255\] at line 16' $(BUILDDIR)/fatal_setelem.err; \
	grep -q 'paslang: set element 1 out of range \[2..7\] at line 16' $(BUILDDIR)/fatal_setincl.err; \
	grep -q 'paslang: integer divide by zero at line 13' $(BUILDDIR)/fatal_divloop.err; \
	grep -q 'paslang: index 10 out of range \[0..4\] at line 11' $(BUILDDIR)/fatal_bstatic.err; \
	grep -q 'paslang: index 3 out of range \[0..2\] at line 13' $(BUILDDIR)/fatal_bslice.err; \
	grep -q 'paslang: index 3 out of range \[0..2\] at line 14' $(BUILDDIR)/fatal_bsame.err; \
	grep -q 'paslang: index 5 out of range \[0..4\] at line 15' $(BUILDDIR)/fatal_bslicereg.err; \
	grep -q 'paslang: index 2500 out of range \[0..2499\] at line 15' $(BUILDDIR)/fatal_bversion.err; \
	grep -q 'paslang: index 9 out of range \[0..4\] at line 12' $(BUILDDIR)/fatal_bslicehi.err; \
	grep -q 'paslang: index -2 out of range \[0..9223372036854775807\] at line 12' $(BUILDDIR)/fatal_bviewneg.err; \
	for t in rrtrunc rrround rrfloor rrceil qtrunc; do \
	  grep -q 'paslang: real out of integer range at line 11' $(BUILDDIR)/fatal_$$t.err; \
	done; \
	grep -q 'paslang: sqrt domain at line 10' $(BUILDDIR)/fatal_qsqrt.err; \
	grep -q 'paslang: index 0 out of range \[1..3\] at line 12' $(BUILDDIR)/fatal_bstring.err; \
	grep -q 'paslang: index -5 out of range \[-3..3\] at line 12' $(BUILDDIR)/fatal_bneg.err; \
	grep -q 'paslang: bit 8 out of range \[0..7\] at line 12' $(BUILDDIR)/fatal_bitchk.err; \
	grep -q 'paslang: bit -1 out of range \[0..15\] at line 12' $(BUILDDIR)/fatal_bitneg.err; \
	grep -q 'paslang: bit 32 out of range \[0..31\] at line 14' $(BUILDDIR)/fatal_bitpool.err; \
	grep -q 'paslang: bit 25 out of range \[0..24\] at line 13' $(BUILDDIR)/fatal_bitfield.err; \
	grep -q 'paslang: bit 16 out of range \[0..15\] at line 12' $(BUILDDIR)/fatal_bitstr.err; \
	grep -q 'paslang: bit 0 out of range \[0..-1\] at line 12' $(BUILDDIR)/fatal_bitempty.err; \
	grep -q 'paslang: bit 64 out of range \[0..63\] at line 12' $(BUILDDIR)/fatal_bitrec.err; \
	grep -q 'paslang: bit 70 out of range \[0..63\] at line 15' $(BUILDDIR)/fatal_bitcall.err; \
	grep -q 'paslang: bit 33 out of range \[0..31\] at line 13' $(BUILDDIR)/fatal_bitslice.err; \
	grep -q 'paslang: bit 31 out of range \[0..15\] at line 12' $(BUILDDIR)/fatal_viewstr.err; \
	grep -q 'paslang: logic on 3 and 4 bytes at line 11' $(BUILDDIR)/fatal_blkstr.err; \
	grep -q 'paslang: a funnel of 3 and 4 bytes at line 11' $(BUILDDIR)/fatal_funnelstr.err; \
	grep -q 'paslang: a funnel of 4 and 6 bytes at line 12' $(BUILDDIR)/fatal_funnelslice.err; \
	grep -q 'paslang: 128-bit division overflow at line 10' $(BUILDDIR)/fatal_divover.err; \
	grep -q 'paslang: integer divide by zero at line 10' $(BUILDDIR)/fatal_divzero128.err; \
	grep -q 'paslang: index 0 out of range \[0..-1\] at line 11' $(BUILDDIR)/fatal_bempty.err; \
	grep -q 'paslang: index 10 out of range \[0..9\] at line 15' $(BUILDDIR)/fatal_bloop.err; \
	grep -q 'paslang: index 7 out of range \[1..3\] at line 6' $(BUILDDIR)/fatal_bref.err; \
	grep -q 'paslang: index 5 out of range \[0..1\] at line 13' $(BUILDDIR)/fatal_bnested.err; \
	grep -q 'paslang: index 7 out of range \[0..4\] at line 10' $(BUILDDIR)/fatal_bconst.err; \
	grep -q 'paslang: index 4 out of range \[1..3\] at line 16' $(BUILDDIR)/fatal_bstrcall.err; \
	echo ok fatal; \
	echo "==== deadlock ===="; \
	for t in dlrecv dlsend dlcycle dlmutex dlmain dlselect; do \
	  $(OUTDIR)/paslangc -o $(BUILDDIR)/fatal_$$t testdata/fatal/$$t.paslang; \
	  set +e; timeout 60 $(BUILDDIR)/fatal_$$t > $(BUILDDIR)/fatal_$$t.got 2> $(BUILDDIR)/fatal_$$t.err; rc=$$?; set -e; \
	  test $$rc -eq 1; \
	  diff -u testdata/fatal/expected.out $(BUILDDIR)/fatal_$$t.got; \
	  grep -q '^paslang: all routines are asleep: deadlock$$' $(BUILDDIR)/fatal_$$t.err; \
	done; \
	echo ok deadlock; \
	echo "==== idlecpu ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/idle testdata/idle.paslang; \
	$(BUILDDIR)/idle > $(BUILDDIR)/idle.got & pid=$$!; sleep 1; \
	ticks=$$(awk '{print $$14}' /proc/$$pid/stat); wait $$pid; \
	diff -u testdata/idle.out $(BUILDDIR)/idle.got; \
	test "$$ticks" -lt 20; \
	echo "ok idlecpu ($$ticks user ticks after one second)"; \
	echo "==== examples ===="; \
	for t in hello values control routines varargs records classes registry helpers convert report generics errors excobjects bank concurrent fanin maps sync wordcount strings maths narrow pointers single quad bits rotations carry bigrot bitfields wide atomics views vectors machine assembly hashes closures slices properties cleanup pipeline kvstore sorting timeout digest bitmap trees; do \
	  $(OUTDIR)/paslangc -o $(BUILDDIR)/ex_$$t examples/$$t.paslang; \
	  $(BUILDDIR)/ex_$$t > $(BUILDDIR)/ex_$$t.got; \
	  diff -u examples/$$t.out $(BUILDDIR)/ex_$$t.got; \
	done; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/ex_clock examples/clock.paslang; \
	$(BUILDDIR)/ex_clock > $(BUILDDIR)/ex_clock.got; \
	diff -u examples/clock.out $(BUILDDIR)/ex_clock.got; \
	for t in cond once readwrite who workers; do \
	  $(OUTDIR)/paslangc -o $(BUILDDIR)/ex_$$t examples/pasroutines/$$t.paslang; \
	  $(BUILDDIR)/ex_$$t > $(BUILDDIR)/ex_$$t.got; \
	  diff -u examples/pasroutines/$$t.out $(BUILDDIR)/ex_$$t.got; \
	done; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/ex_lines examples/pasroutines/lines.paslang; \
	$(BUILDDIR)/ex_lines | sort > $(BUILDDIR)/ex_lines.got; \
	diff -u examples/pasroutines/lines.out $(BUILDDIR)/ex_lines.got; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/geometry examples/units/geometry.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/ex_usegeom examples/units/usegeom.paslang; \
	$(BUILDDIR)/ex_usegeom > $(BUILDDIR)/ex_usegeom.got; \
	diff -u examples/units/usegeom.out $(BUILDDIR)/ex_usegeom.got; \
	python3 scripts/check_examples.py; \
	for t in httpd dnsd termd ftpd ntpd wsd chat proxy; do \
	  $(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/ex_$$t examples/$$t.paslang; \
	  timeout 120 $(BUILDDIR)/ex_$$t -selftest 2000 > $(BUILDDIR)/ex_$$t.got; \
	  diff -u examples/$$t.out $(BUILDDIR)/ex_$$t.got; \
	  echo ok servers-$$t; \
	done; \
	echo ok examples; \
	echo "==== intel64 ===="; \
	$(OUTDIR)/paslangc -target intel64 -o $(BUILDDIR)/hello-i64 testdata/hello.paslang; \
	file $(BUILDDIR)/hello-i64 | grep -q 'x86-64'; \
	$(BUILDDIR)/hello-i64 > $(BUILDDIR)/hello-i64.got; \
	diff -u testdata/hello.out $(BUILDDIR)/hello-i64.got; \
	echo ok intel64; \
	echo "==== helpbox ===="; \
	$(OUTDIR)/paslangc > $(BUILDDIR)/paslangc.card; \
	test $$(grep -c . $(BUILDDIR)/paslangc.card) -ge 20; \
	test $$(awk 'NF{print length($$0)}' $(BUILDDIR)/paslangc.card | sort -u | wc -l) -eq 1; \
	grep -q 'core sync, maps, pasnet   ' $(BUILDDIR)/paslangc.card; \
	$(OUTDIR)/paslangc --help > $(BUILDDIR)/paslangc.help; \
	test $$(grep -c '^## ' $(BUILDDIR)/paslangc.help) -eq 7; \
	echo ok helpbox; \
	if [ -f $(BUILDDIR)/xvfb.pid ]; then \
	  kill $$(cat $(BUILDDIR)/xvfb.pid) 2> /dev/null || true; \
	  rm -f $(BUILDDIR)/xvfb.pid; \
	fi; \
	echo "==== stage ===="; \
	host="$(bindir)/paslangc"; \
	if [ ! -x "$$host" ]; then host="$(OUTDIR)/paslangc"; fi; \
	$(MAKE) stage HOST="$$host" STAGE="$(BUILDDIR)/paslangc-stage"; \
	echo "==== self ===="; \
	$(MAKE) self; \
	$(MAKE) check-arm64

QEMU_A64 := $(BUILDDIR)/qemu-aarch64-static

$(BUILDDIR)/qemu-aarch64-static: | $(BUILDDIR)
	cp /usr/bin/qemu-aarch64-static $@
	python3 scripts/patch-qemu-madv102.py $@

check-arm64: $(OUTDIR)/paslangc core-arm64 $(OUTDIR)/paslangc-arm64 $(BUILDDIR)/qemu-aarch64-static
	@set -e; \
	echo "==== lib units arm64 ===="; \
	for u in $(LIB_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  $(OUTDIR)/paslangc -target arm64 -c -Fu $(A64DIR) -o $(A64DIR)/$$b $$u; \
	done; \
	for t in $(GOLDEN_A64); do \
	  echo "==== $$t arm64 ===="; \
	  $(OUTDIR)/paslangc -target arm64 -cpu max -o $(BUILDDIR)/$$t-arm testdata/$$t.paslang; \
	  timeout 60 $(QEMU_A64) $(BUILDDIR)/$$t-arm > $(BUILDDIR)/$$t-arm.got; \
	  diff -u testdata/$$t.out $(BUILDDIR)/$$t-arm.got; \
	  echo ok $$t-arm; \
	done; \
	echo "==== the base processor arm64 ===="; \
	for t in hash1 tree1 store1 vectors bitwords set256 strwords strkern strcmpk cmpwords sysutils1; do \
	  $(OUTDIR)/paslangc -target arm64 -cpu base -o $(BUILDDIR)/$$t-arm-base testdata/$$t.paslang; \
	  timeout 120 $(QEMU_A64) $(BUILDDIR)/$$t-arm-base > $(BUILDDIR)/$$t-arm.bgot; \
	  diff -u testdata/$$t.out $(BUILDDIR)/$$t-arm.bgot; \
	done; \
	grep -q 'p_pashash_passha256cpu' $(BUILDDIR)/hash1-arm.s; \
	grep -q 'p_pashash_passha512cpu' $(BUILDDIR)/hash1-arm.s; \
	if grep -q 'p_pashash_passha256cpu' $(BUILDDIR)/hash1-arm-base.s; then echo "hash1-arm-base.s calls the SHA-256 body"; exit 1; fi; \
	echo ok cpu-base-arm; \
	grep -q 'gctype TNode size 32 words 1 mask 0x0000000000000009' $(BUILDDIR)/gctypes-arm.s; \
	grep -q 'gctype TBox instance size 48 words 1 mask 0x000000000000000a' $(BUILDDIR)/gctypes-arm.s; \
	grep -A1 -x '  .quad v_pl' $(BUILDDIR)/gctypes-arm.s | grep -qx '  .quad 8'; \
	if grep -qx '  .quad v_total' $(BUILDDIR)/gctypes-arm.s; then echo "gctypes-arm.s lists v_total, which holds no pointer, as a root"; exit 1; fi; \
	echo ok gctypes-descriptors-arm; \
	echo "==== stdin arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/readlines-arm testdata/readlines.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/readlines-arm < testdata/readlines.in > $(BUILDDIR)/readlines-arm.got; \
	diff -u testdata/readlines.out $(BUILDDIR)/readlines-arm.got; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/spurwake-arm testdata/spurwake.paslang; \
	(sleep 0.5; printf 'x\n'; head -c 100000 /dev/zero | tr '\0' y) | timeout 60 $(QEMU_A64) $(BUILDDIR)/spurwake-arm > $(BUILDDIR)/spurwake-arm.got; \
	diff -u testdata/spurwake.out $(BUILDDIR)/spurwake-arm.got; \
	echo ok stdin-arm; \
	echo "==== collector arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/gcoff-arm testdata/gcoff.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/gcoff-arm > $(BUILDDIR)/gcoff-arm.got; \
	diff -u testdata/gcoff.out $(BUILDDIR)/gcoff-arm.got; \
	PASLANG_GC=off timeout 300 $(QEMU_A64) $(BUILDDIR)/gcoff-arm > $(BUILDDIR)/gcoff-arm.got; \
	diff -u testdata/gcoff-off.out $(BUILDDIR)/gcoff-arm.got; \
	PASLANG_GCSTRESS=3 PASLANG_GCPOISON=1 timeout 600 $(QEMU_A64) $(BUILDDIR)/gcbasic-arm > $(BUILDDIR)/gcbasic-arm.got; \
	diff -u testdata/gcbasic.out $(BUILDDIR)/gcbasic-arm.got; \
	PASLANG_GCSTRESS=5 PASLANG_GCPOISON=1 timeout 600 $(QEMU_A64) $(BUILDDIR)/mapsplit-arm > $(BUILDDIR)/mapsplit-arm.got; \
	diff -u testdata/mapsplit.out $(BUILDDIR)/mapsplit-arm.got; \
	echo ok collector-arm; \
	echo "==== stack maps arm64 ===="; \
	for t in $(GOLDEN_A64); do \
	  PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=3 PASLANG_GCPOISON=1 timeout 600 $(QEMU_A64) $(BUILDDIR)/$$t-arm > $(BUILDDIR)/$$t-arm.vgot; \
	  diff -u testdata/$$t.out $(BUILDDIR)/$$t-arm.vgot; \
	done; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 timeout 600 $(QEMU_A64) $(BUILDDIR)/stackmap-arm > $(BUILDDIR)/stackmap-arm.vgot; \
	diff -u testdata/stackmap.out $(BUILDDIR)/stackmap-arm.vgot; \
	echo ok stackmaps-arm; \
	echo "==== parallel mark arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/parmark-arm testdata/parmark.paslang; \
	for w in "" "" PASLANG_GCWORKERS=1 PASLANG_GCWORKERS=2 "PASLANG_GCVERIFY=1 PASLANG_GCPOISON=1" "PASLANG_GCSTRESS=50 PASLANG_GCPOISON=1"; do \
	  env $$w timeout 600 $(QEMU_A64) $(BUILDDIR)/parmark-arm > $(BUILDDIR)/parmark-arm.got; \
	  diff -u testdata/parmark.out $(BUILDDIR)/parmark-arm.got; \
	done; \
	echo ok parmark-arm; \
	echo "==== dirlist arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/dirlist-arm testdata/dirlist.paslang; \
	timeout 120 $(QEMU_A64) $(BUILDDIR)/dirlist-arm > $(BUILDDIR)/dirlist-arm.got; \
	diff -u testdata/dirlist.out $(BUILDDIR)/dirlist-arm.got; \
	echo ok dirlist-arm; \
	echo "==== lazy Ms arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/lazym-arm testdata/lazym.paslang; \
	for w in "" PASLANG_GCWORKERS=1; do \
	  env $$w timeout 300 $(QEMU_A64) $(BUILDDIR)/lazym-arm > $(BUILDDIR)/lazym-arm.got; \
	  diff -u testdata/lazym.out $(BUILDDIR)/lazym-arm.got; \
	done; \
	echo ok lazym-arm; \
	echo "==== alloc bits arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/allocbits-arm testdata/allocbits.paslang; \
	for w in "" PASLANG_GCPOISON=1 "PASLANG_GCSTRESS=50 PASLANG_GCPOISON=1" "PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=50 PASLANG_GCPOISON=1" PASLANG_GC=off; do \
	  env $$w timeout 600 $(QEMU_A64) $(BUILDDIR)/allocbits-arm > $(BUILDDIR)/allocbits-arm.got; \
	  diff -u testdata/allocbits.out $(BUILDDIR)/allocbits-arm.got; \
	done; \
	echo ok allocbits-arm; \
	rm -f $(BUILDDIR)/fh.txt; \
	echo "==== busy arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/busy-arm testdata/busy.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/busy-arm > $(BUILDDIR)/busy-arm.got; \
	diff -u testdata/busy.out $(BUILDDIR)/busy-arm.got; \
	echo ok busy-arm; \
	echo "==== spawnrace arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/spawnrace-arm testdata/spawnrace.paslang; \
	timeout 120 $(QEMU_A64) $(BUILDDIR)/spawnrace-arm > $(BUILDDIR)/spawnrace-arm.got; \
	diff -u testdata/spawnrace.out $(BUILDDIR)/spawnrace-arm.got; \
	echo ok spawnrace-arm; \
	echo "==== idlerace arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/idlerace-arm testdata/idlerace.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/idlerace-arm > $(BUILDDIR)/idlerace-arm.got; \
	diff -u testdata/idlerace.out $(BUILDDIR)/idlerace-arm.got; \
	echo ok idlerace-arm; \
	echo "==== mutexfair arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/mutexfair-arm testdata/mutexfair.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/mutexfair-arm > $(BUILDDIR)/mutexfair-arm.got; \
	diff -u testdata/mutexfair.out $(BUILDDIR)/mutexfair-arm.got; \
	echo ok mutexfair-arm; \
	echo "==== lockpreempt arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/lockpreempt-arm testdata/lockpreempt.paslang; \
	timeout 120 $(QEMU_A64) $(BUILDDIR)/lockpreempt-arm > $(BUILDDIR)/lockpreempt-arm.got; \
	diff -u testdata/lockpreempt.out $(BUILDDIR)/lockpreempt-arm.got; \
	echo ok lockpreempt-arm; \
	echo "==== parkrace arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/parkrace-arm testdata/parkrace.paslang; \
	timeout 180 $(QEMU_A64) $(BUILDDIR)/parkrace-arm > $(BUILDDIR)/parkrace-arm.got; \
	diff -u testdata/parkrace.out $(BUILDDIR)/parkrace-arm.got; \
	echo ok parkrace-arm; \
	echo "==== sortunit arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/sortunit-arm testdata/sortunit.paslang; \
	timeout 120 $(QEMU_A64) $(BUILDDIR)/sortunit-arm > $(BUILDDIR)/sortunit-arm.got; \
	diff -u testdata/sortunit.out $(BUILDDIR)/sortunit-arm.got; \
	echo ok sortunit-arm; \
	echo "==== randunit arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/randunit-arm testdata/randunit.paslang; \
	timeout 120 $(QEMU_A64) $(BUILDDIR)/randunit-arm > $(BUILDDIR)/randunit-arm.got; \
	diff -u testdata/randunit.out $(BUILDDIR)/randunit-arm.got; \
	echo ok randunit-arm; \
	echo "==== filehandle arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/filehandle-arm testdata/filehandle.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/filehandle-arm > $(BUILDDIR)/filehandle-arm.got; \
	diff -u testdata/filehandle.out $(BUILDDIR)/filehandle-arm.got; \
	echo ok filehandle-arm; \
	echo "==== timeunit arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/timeunit-arm testdata/timeunit.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/timeunit-arm > $(BUILDDIR)/timeunit-arm.got; \
	diff -u testdata/timeunit.out $(BUILDDIR)/timeunit-arm.got; \
	echo ok timeunit-arm; \
	echo "==== nilmap arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/nilmap-arm testdata/nilmap.paslang; \
	set +e; timeout 60 $(QEMU_A64) $(BUILDDIR)/nilmap-arm > $(BUILDDIR)/nilmap-arm.got 2> $(BUILDDIR)/nilmap-arm.err; rc=$$?; set -e; \
	test $$rc -eq 1; \
	diff -u testdata/nilmap.out $(BUILDDIR)/nilmap-arm.got; \
	grep -q 'paslang: nil map' $(BUILDDIR)/nilmap-arm.err; \
	echo ok nilmap-arm; \
	echo "==== wgneg arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/wgneg-arm testdata/wgneg.paslang; \
	set +e; timeout 60 $(QEMU_A64) $(BUILDDIR)/wgneg-arm > $(BUILDDIR)/wgneg-arm.got 2> $(BUILDDIR)/wgneg-arm.err; rc=$$?; set -e; \
	test $$rc -eq 1; \
	diff -u testdata/wgneg.out $(BUILDDIR)/wgneg-arm.got; \
	grep -q 'paslang: negative waitgroup counter' $(BUILDDIR)/wgneg-arm.err; \
	echo ok wgneg-arm; \
	echo "==== unlockfree arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/unlockfree-arm testdata/unlockfree.paslang; \
	set +e; timeout 60 $(QEMU_A64) $(BUILDDIR)/unlockfree-arm > $(BUILDDIR)/unlockfree-arm.got 2> $(BUILDDIR)/unlockfree-arm.err; rc=$$?; set -e; \
	test $$rc -eq 1; \
	diff -u testdata/unlockfree.out $(BUILDDIR)/unlockfree-arm.got; \
	grep -q 'paslang: unlock of an unlocked mutex' $(BUILDDIR)/unlockfree-arm.err; \
	echo ok unlockfree-arm; \
	echo "==== fatal arm64 ===="; \
	for t in divzero nilptr deep oom closed divloop bstatic bslice bstring bneg bempty bloop bref bnested bconst bstrcall bsame bslicereg bversion bslicehi bviewneg rrtrunc rrround rrfloor rrceil qtrunc qsqrt bitchk bitneg bitpool bitfield bitstr bitempty bitrec bitcall bitslice viewstr blkstr divover divzero128 funnelstr funnelslice mainraise raiseobj setelem setincl; do \
	  $(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/fatal_$$t-arm testdata/fatal/$$t.paslang; \
	  set +e; timeout 60 $(QEMU_A64) $(BUILDDIR)/fatal_$$t-arm > $(BUILDDIR)/fatal_$$t-arm.got 2> $(BUILDDIR)/fatal_$$t-arm.err; rc=$$?; set -e; \
	  test $$rc -eq 1; \
	  diff -u testdata/fatal/expected.out $(BUILDDIR)/fatal_$$t-arm.got; \
	done; \
	grep -q 'paslang: integer divide by zero at line 11' $(BUILDDIR)/fatal_divzero-arm.err; \
	grep -q 'paslang: nil pointer dereference at line 16' $(BUILDDIR)/fatal_nilptr-arm.err; \
	grep -q 'paslang: stack overflow at line 12' $(BUILDDIR)/fatal_deep-arm.err; \
	grep -q 'paslang: out of memory: [0-9][0-9]* MiB mapped' $(BUILDDIR)/fatal_oom-arm.err; \
	grep -q 'paslang: send on closed channel at line 11' $(BUILDDIR)/fatal_closed-arm.err; \
	grep -q 'paslang: uncaught raise in the main routine' $(BUILDDIR)/fatal_mainraise-arm.err; \
	grep -q 'paslang: uncaught raise in the main routine: EOops' $(BUILDDIR)/fatal_raiseobj-arm.err; \
	grep -q 'paslang: set element 300 out of range \[0..255\] at line 16' $(BUILDDIR)/fatal_setelem-arm.err; \
	grep -q 'paslang: set element 1 out of range \[2..7\] at line 16' $(BUILDDIR)/fatal_setincl-arm.err; \
	grep -q 'paslang: integer divide by zero at line 13' $(BUILDDIR)/fatal_divloop-arm.err; \
	grep -q 'paslang: index 10 out of range \[0..4\] at line 11' $(BUILDDIR)/fatal_bstatic-arm.err; \
	grep -q 'paslang: index 3 out of range \[0..2\] at line 13' $(BUILDDIR)/fatal_bslice-arm.err; \
	grep -q 'paslang: index 3 out of range \[0..2\] at line 14' $(BUILDDIR)/fatal_bsame-arm.err; \
	grep -q 'paslang: index 5 out of range \[0..4\] at line 15' $(BUILDDIR)/fatal_bslicereg-arm.err; \
	grep -q 'paslang: index 2500 out of range \[0..2499\] at line 15' $(BUILDDIR)/fatal_bversion-arm.err; \
	grep -q 'paslang: index 9 out of range \[0..4\] at line 12' $(BUILDDIR)/fatal_bslicehi-arm.err; \
	grep -q 'paslang: index -2 out of range \[0..9223372036854775807\] at line 12' $(BUILDDIR)/fatal_bviewneg-arm.err; \
	for t in rrtrunc rrround rrfloor rrceil qtrunc; do \
	  grep -q 'paslang: real out of integer range at line 11' $(BUILDDIR)/fatal_$$t-arm.err; \
	done; \
	grep -q 'paslang: sqrt domain at line 10' $(BUILDDIR)/fatal_qsqrt-arm.err; \
	grep -q 'paslang: index 0 out of range \[1..3\] at line 12' $(BUILDDIR)/fatal_bstring-arm.err; \
	grep -q 'paslang: index -5 out of range \[-3..3\] at line 12' $(BUILDDIR)/fatal_bneg-arm.err; \
	grep -q 'paslang: bit 8 out of range \[0..7\] at line 12' $(BUILDDIR)/fatal_bitchk-arm.err; \
	grep -q 'paslang: bit -1 out of range \[0..15\] at line 12' $(BUILDDIR)/fatal_bitneg-arm.err; \
	grep -q 'paslang: bit 32 out of range \[0..31\] at line 14' $(BUILDDIR)/fatal_bitpool-arm.err; \
	grep -q 'paslang: bit 25 out of range \[0..24\] at line 13' $(BUILDDIR)/fatal_bitfield-arm.err; \
	grep -q 'paslang: bit 16 out of range \[0..15\] at line 12' $(BUILDDIR)/fatal_bitstr-arm.err; \
	grep -q 'paslang: bit 0 out of range \[0..-1\] at line 12' $(BUILDDIR)/fatal_bitempty-arm.err; \
	grep -q 'paslang: bit 64 out of range \[0..63\] at line 12' $(BUILDDIR)/fatal_bitrec-arm.err; \
	grep -q 'paslang: bit 70 out of range \[0..63\] at line 15' $(BUILDDIR)/fatal_bitcall-arm.err; \
	grep -q 'paslang: bit 33 out of range \[0..31\] at line 13' $(BUILDDIR)/fatal_bitslice-arm.err; \
	grep -q 'paslang: bit 31 out of range \[0..15\] at line 12' $(BUILDDIR)/fatal_viewstr-arm.err; \
	grep -q 'paslang: logic on 3 and 4 bytes at line 11' $(BUILDDIR)/fatal_blkstr-arm.err; \
	grep -q 'paslang: a funnel of 3 and 4 bytes at line 11' $(BUILDDIR)/fatal_funnelstr-arm.err; \
	grep -q 'paslang: a funnel of 4 and 6 bytes at line 12' $(BUILDDIR)/fatal_funnelslice-arm.err; \
	grep -q 'paslang: 128-bit division overflow at line 10' $(BUILDDIR)/fatal_divover-arm.err; \
	grep -q 'paslang: integer divide by zero at line 10' $(BUILDDIR)/fatal_divzero128-arm.err; \
	grep -q 'paslang: index 0 out of range \[0..-1\] at line 11' $(BUILDDIR)/fatal_bempty-arm.err; \
	grep -q 'paslang: index 10 out of range \[0..9\] at line 15' $(BUILDDIR)/fatal_bloop-arm.err; \
	grep -q 'paslang: index 7 out of range \[1..3\] at line 6' $(BUILDDIR)/fatal_bref-arm.err; \
	grep -q 'paslang: index 5 out of range \[0..1\] at line 13' $(BUILDDIR)/fatal_bnested-arm.err; \
	grep -q 'paslang: index 7 out of range \[0..4\] at line 10' $(BUILDDIR)/fatal_bconst-arm.err; \
	grep -q 'paslang: index 4 out of range \[1..3\] at line 16' $(BUILDDIR)/fatal_bstrcall-arm.err; \
	echo ok fatal-arm; \
	echo "==== deadlock arm64 ===="; \
	for t in dlrecv dlsend dlcycle dlmutex dlmain dlselect; do \
	  $(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/fatal_$$t-arm testdata/fatal/$$t.paslang; \
	  set +e; timeout 60 $(QEMU_A64) $(BUILDDIR)/fatal_$$t-arm > $(BUILDDIR)/fatal_$$t-arm.got 2> $(BUILDDIR)/fatal_$$t-arm.err; rc=$$?; set -e; \
	  test $$rc -eq 1; \
	  diff -u testdata/fatal/expected.out $(BUILDDIR)/fatal_$$t-arm.got; \
	  grep -q '^paslang: all routines are asleep: deadlock$$' $(BUILDDIR)/fatal_$$t-arm.err; \
	done; \
	echo ok deadlock-arm; \
	echo "==== examples arm64 ===="; \
	for t in hello values control routines varargs records classes registry helpers convert report generics errors excobjects bank concurrent fanin maps sync wordcount strings maths narrow pointers single quad bits rotations carry bigrot bitfields wide atomics views vectors machine assembly hashes closures slices properties cleanup pipeline kvstore sorting timeout digest bitmap trees; do \
	  $(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/ex_$$t-arm examples/$$t.paslang; \
	  timeout 60 $(QEMU_A64) $(BUILDDIR)/ex_$$t-arm > $(BUILDDIR)/ex_$$t-arm.got; \
	  diff -u examples/$$t.out $(BUILDDIR)/ex_$$t-arm.got; \
	done; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/ex_clock-arm examples/clock.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/ex_clock-arm > $(BUILDDIR)/ex_clock-arm.got; \
	diff -u examples/clock.out $(BUILDDIR)/ex_clock-arm.got; \
	for t in cond once readwrite who workers; do \
	  $(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/ex_$$t-arm examples/pasroutines/$$t.paslang; \
	  timeout 60 $(QEMU_A64) $(BUILDDIR)/ex_$$t-arm > $(BUILDDIR)/ex_$$t-arm.got; \
	  diff -u examples/pasroutines/$$t.out $(BUILDDIR)/ex_$$t-arm.got; \
	done; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/ex_lines-arm examples/pasroutines/lines.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/ex_lines-arm | sort > $(BUILDDIR)/ex_lines-arm.got; \
	diff -u examples/pasroutines/lines.out $(BUILDDIR)/ex_lines-arm.got; \
	$(OUTDIR)/paslangc -target arm64 examples/units/geometry.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/ex_usegeom-arm examples/units/usegeom.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/ex_usegeom-arm > $(BUILDDIR)/ex_usegeom-arm.got; \
	diff -u examples/units/usegeom.out $(BUILDDIR)/ex_usegeom-arm.got; \
	echo ok examples-arm; \
	echo "==== compiler arch ===="; \
	file $(OUTDIR)/paslangc | grep -q 'x86-64'; \
	file $(OUTDIR)/paslangc-arm64 | grep -q 'ARM aarch64'; \
	$(QEMU_A64) $(OUTDIR)/paslangc-arm64 -h > $(BUILDDIR)/paslangc-arm.help; \
	grep -q intel64 $(BUILDDIR)/paslangc-arm.help; \
	test $$(awk 'NF{print length($$0)}' $(BUILDDIR)/paslangc-arm.help | sort -u | wc -l) -eq 1; \
	echo ok compiler-help; \
	echo "==== compiler lex arm64 ===="; \
	$(QEMU_A64) $(OUTDIR)/paslangc-arm64 --lex testdata/hello.paslang > $(BUILDDIR)/hello-lex-arm.got; \
	grep -q 'hello world' $(BUILDDIR)/hello-lex-arm.got; \
	echo ok compiler-lex-arm; \
	echo "==== compiler emit arm64 ===="; \
	timeout 60 $(QEMU_A64) $(OUTDIR)/paslangc-arm64 -o $(BUILDDIR)/hello-byarm testdata/hello.paslang > $(BUILDDIR)/hello-byarm.log 2>&1; \
	test -s $(BUILDDIR)/hello-byarm.s; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/hello-bycross testdata/hello.paslang; \
	diff -u $(BUILDDIR)/hello-byarm.s $(BUILDDIR)/hello-bycross.s; \
	echo ok compiler-emit-arm; \
	echo "==== sysid arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/sysid-arm testdata/sysid.paslang; \
	$(QEMU_A64) $(BUILDDIR)/sysid-arm > $(BUILDDIR)/sysid-arm.got; \
	diff -u testdata/sysid.out $(BUILDDIR)/sysid-arm.got; \
	echo ok sysid-arm; \
	echo "==== hello arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/hello-arm testdata/hello.paslang; \
	$(QEMU_A64) $(BUILDDIR)/hello-arm > $(BUILDDIR)/hello-arm.got; \
	diff -u testdata/hello.out $(BUILDDIR)/hello-arm.got; \
	echo ok hello-arm; \
	echo "==== slice arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/slice-arm testdata/slice.paslang; \
	$(QEMU_A64) $(BUILDDIR)/slice-arm > $(BUILDDIR)/slice-arm.got; \
	diff -u testdata/slice.out $(BUILDDIR)/slice-arm.got; \
	echo ok slice-arm; \
	echo "==== paswork arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/paswork-arm testdata/paswork.paslang; \
	$(QEMU_A64) $(BUILDDIR)/paswork-arm > $(BUILDDIR)/paswork-arm.got; \
	diff -u testdata/paswork.out $(BUILDDIR)/paswork-arm.got; \
	echo ok paswork-arm; \
	echo "==== armargs arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/armargs-arm testdata/armargs.paslang; \
	$(QEMU_A64) $(BUILDDIR)/armargs-arm > $(BUILDDIR)/armargs-arm.got; \
	diff -u testdata/armargs.out $(BUILDDIR)/armargs-arm.got; \
	echo ok armargs-arm; \
	echo "==== armmeth arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/armmeth-arm testdata/armmeth.paslang; \
	$(QEMU_A64) $(BUILDDIR)/armmeth-arm > $(BUILDDIR)/armmeth-arm.got; \
	diff -u testdata/armmeth.out $(BUILDDIR)/armmeth-arm.got; \
	echo ok armmeth-arm; \
	echo "==== propacc arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/propacc-arm testdata/propacc.paslang; \
	$(QEMU_A64) $(BUILDDIR)/propacc-arm > $(BUILDDIR)/propacc-arm.got; \
	diff -u testdata/propacc.out $(BUILDDIR)/propacc-arm.got; \
	echo ok propacc-arm; \
	echo "==== runes arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/runes-arm testdata/runes.paslang; \
	$(QEMU_A64) $(BUILDDIR)/runes-arm > $(BUILDDIR)/runes-arm.got; \
	diff -u testdata/runes.out $(BUILDDIR)/runes-arm.got; \
	echo ok runes-arm; \
	echo "==== args20 arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/args20-arm testdata/args20.paslang; \
	$(QEMU_A64) $(BUILDDIR)/args20-arm > $(BUILDDIR)/args20-arm.got; \
	diff -u testdata/args20.out $(BUILDDIR)/args20-arm.got; \
	echo ok args20-arm; \
	echo "==== variant arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/variant-arm testdata/variant.paslang; \
	$(QEMU_A64) $(BUILDDIR)/variant-arm > $(BUILDDIR)/variant-arm.got; \
	diff -u testdata/variant.out $(BUILDDIR)/variant-arm.got; \
	echo ok variant-arm; \
	echo "==== opadd arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/opadd-arm testdata/opadd.paslang; \
	$(QEMU_A64) $(BUILDDIR)/opadd-arm > $(BUILDDIR)/opadd-arm.got; \
	diff -u testdata/opadd.out $(BUILDDIR)/opadd-arm.got; \
	echo ok opadd-arm; \
	echo "==== iface arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/iface-arm testdata/iface.paslang; \
	$(QEMU_A64) $(BUILDDIR)/iface-arm > $(BUILDDIR)/iface-arm.got; \
	diff -u testdata/iface.out $(BUILDDIR)/iface-arm.got; \
	echo ok iface-arm; \
	echo "==== opmore arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/opmore-arm testdata/opmore.paslang; \
	$(QEMU_A64) $(BUILDDIR)/opmore-arm > $(BUILDDIR)/opmore-arm.got; \
	diff -u testdata/opmore.out $(BUILDDIR)/opmore-arm.got; \
	echo ok opmore-arm; \
	echo "==== shift arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/shift-arm testdata/shift.paslang; \
	$(QEMU_A64) $(BUILDDIR)/shift-arm > $(BUILDDIR)/shift-arm.got; \
	diff -u testdata/shift.out $(BUILDDIR)/shift-arm.got; \
	echo ok shift-arm; \
	echo "==== dynnil arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/dynnil-arm testdata/dynnil.paslang; \
	$(QEMU_A64) $(BUILDDIR)/dynnil-arm > $(BUILDDIR)/dynnil-arm.got; \
	diff -u testdata/dynnil.out $(BUILDDIR)/dynnil-arm.got; \
	echo ok dynnil-arm; \
	echo "==== xor arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/xor-arm testdata/xor.paslang; \
	$(QEMU_A64) $(BUILDDIR)/xor-arm > $(BUILDDIR)/xor-arm.got; \
	diff -u testdata/xor.out $(BUILDDIR)/xor-arm.got; \
	echo ok xor-arm; \
	echo "==== inhcall arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/inhcall-arm testdata/inhcall.paslang; \
	$(QEMU_A64) $(BUILDDIR)/inhcall-arm > $(BUILDDIR)/inhcall-arm.got; \
	diff -u testdata/inhcall.out $(BUILDDIR)/inhcall-arm.got; \
	echo ok inhcall-arm; \
	echo "==== isas arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/isas-arm testdata/isas.paslang; \
	$(QEMU_A64) $(BUILDDIR)/isas-arm > $(BUILDDIR)/isas-arm.got; \
	diff -u testdata/isas.out $(BUILDDIR)/isas-arm.got; \
	echo ok isas-arm; \
	echo "==== unit globals in registers arm64 ===="; \
	mkdir -p $(BUILDDIR)/a64; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/a64/regu testdata/units/regu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/reguse-arm testdata/units/reguse.paslang; \
	$(QEMU_A64) $(BUILDDIR)/reguse-arm > $(BUILDDIR)/reguse-arm.got; \
	diff -u testdata/units/reguse.out $(BUILDDIR)/reguse-arm.got; \
	echo ok reguse-arm; \
	echo "==== unit init arm64 ===="; \
	mkdir -p $(BUILDDIR)/a64; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/a64/inita testdata/units/inita.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/a64/initb testdata/units/initb.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/initp-arm testdata/units/initp.paslang; \
	$(QEMU_A64) $(BUILDDIR)/initp-arm > $(BUILDDIR)/initp-arm.got; \
	diff -u testdata/units/initp.out $(BUILDDIR)/initp-arm.got; \
	echo ok init-arm; \
	echo "==== stale unit arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/a64/adder testdata/units/adder.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/a64/twice testdata/units/twice.paslang; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/a64/adder testdata/units/adder_extra.paslang; \
	if $(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/twiceuse-arm testdata/units/twiceuse.paslang > $(BUILDDIR)/twiceuse-arm.err 2>&1; then \
	  echo 'a unit compiled against another adder should be refused (arm64)'; exit 1; \
	fi; \
	grep -q 'twice.pi was compiled against another adder.pi' $(BUILDDIR)/twiceuse-arm.err; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/a64/adder testdata/units/adder.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/twiceuse-arm testdata/units/twiceuse.paslang; \
	$(QEMU_A64) $(BUILDDIR)/twiceuse-arm > $(BUILDDIR)/twiceuse-arm.got; \
	diff -u testdata/units/twiceuse.out $(BUILDDIR)/twiceuse-arm.got; \
	echo ok stale-arm; \
	echo "==== kconst arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/a64/kconst testdata/units/kconst.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/kconstuse-arm testdata/units/kconstuse.paslang; \
	$(QEMU_A64) $(BUILDDIR)/kconstuse-arm > $(BUILDDIR)/kconstuse-arm.got; \
	diff -u testdata/units/kconstuse.out $(BUILDDIR)/kconstuse-arm.got; \
	echo ok kconst-arm; \
	echo "==== unit forward arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/a64/fwda testdata/units/fwda.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/fwduse-arm testdata/units/fwduse.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/fwduse-arm > $(BUILDDIR)/fwduse-arm.got; \
	diff -u testdata/units/fwduse.out $(BUILDDIR)/fwduse-arm.got; \
	echo ok fwduse-arm; \
	echo "==== unit defaults arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/a64/defu testdata/units/defu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/defuse-arm testdata/units/defuse.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/defuse-arm > $(BUILDDIR)/defuse-arm.got; \
	diff -u testdata/units/defuse.out $(BUILDDIR)/defuse-arm.got; \
	echo ok defuse-arm; \
	echo "==== unit variables arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/a64/uvar testdata/units/uvar.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/a64/uvar2 testdata/units/uvar2.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/uvaruse-arm testdata/units/uvaruse.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/uvaruse-arm > $(BUILDDIR)/uvaruse-arm.got; \
	diff -u testdata/units/uvaruse.out $(BUILDDIR)/uvaruse-arm.got; \
	echo ok uvaruse-arm; \
	echo "==== props arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/props-arm testdata/props.paslang; \
	$(QEMU_A64) $(BUILDDIR)/props-arm > $(BUILDDIR)/props-arm.got; \
	diff -u testdata/props.out $(BUILDDIR)/props-arm.got; \
	echo ok props-arm; \
	echo "==== pindex arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/pindex-arm testdata/pindex.paslang; \
	$(QEMU_A64) $(BUILDDIR)/pindex-arm > $(BUILDDIR)/pindex-arm.got; \
	diff -u testdata/pindex.out $(BUILDDIR)/pindex-arm.got; \
	echo ok pindex-arm; \
	echo "==== dwarfloc arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/dwarfloc-arm testdata/dwarfloc.paslang; \
	$(QEMU_A64) $(BUILDDIR)/dwarfloc-arm > $(BUILDDIR)/dwarfloc-arm.got; \
	diff -u testdata/dwarfloc.out $(BUILDDIR)/dwarfloc-arm.got; \
	readelf --debug-dump=info $(BUILDDIR)/dwarfloc-arm | grep -q 'DW_OP_reg29'; \
	readelf --debug-dump=info $(BUILDDIR)/dwarfloc-arm | grep -q 'DW_OP_fbreg: -16'; \
	echo ok dwarfloc-arm; \
	echo "==== pasrut arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/pasrut-arm testdata/pasrut.paslang; \
	$(QEMU_A64) $(BUILDDIR)/pasrut-arm > $(BUILDDIR)/pasrut-arm.got; \
	diff -u testdata/pasrut.out $(BUILDDIR)/pasrut-arm.got; \
	echo ok pasrut-arm; \
	echo "==== wrout arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/wrout-arm testdata/wrout.paslang; \
	$(QEMU_A64) $(BUILDDIR)/wrout-arm > $(BUILDDIR)/wrout-arm.got; \
	test $$(wc -l < $(BUILDDIR)/wrout-arm.got) -eq 5; \
	test $$(grep -c '^aaaa$$' $(BUILDDIR)/wrout-arm.got) -eq 1; \
	test $$(grep -c '^bbbb$$' $(BUILDDIR)/wrout-arm.got) -eq 1; \
	test $$(grep -c '^cccc$$' $(BUILDDIR)/wrout-arm.got) -eq 1; \
	test $$(grep -c '^dddd$$' $(BUILDDIR)/wrout-arm.got) -eq 1; \
	tail -n 1 $(BUILDDIR)/wrout-arm.got | grep -q '^done$$'; \
	echo ok wrout-arm; \
	echo "==== tcppark arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -c src/lib/pasnet.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/tcppark-arm testdata/tcppark.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/tcppark-arm > $(BUILDDIR)/tcppark-arm.got; \
	diff -u testdata/tcppark.out $(BUILDDIR)/tcppark-arm.got; \
	echo ok tcppark-arm; \
	echo "==== udppark arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -c src/lib/pasnet.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/udppark-arm testdata/udppark.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/udppark-arm > $(BUILDDIR)/udppark-arm.got; \
	diff -u testdata/udppark.out $(BUILDDIR)/udppark-arm.got; \
	echo ok udppark-arm; \
	echo "==== debug arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -c src/lib/pasnet.paslang; \
	$(OUTDIR)/paslangc -target arm64 -c -Fu $(BUILDDIR)/a64 src/lib/pasdebug.paslang; \
	$(OUTDIR)/paslangc -target arm64 -debug -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/debug1-arm testdata/debug1.paslang; \
	PASLANG_DEBUG=@paslang-debug1-arm-$$$$ timeout 120 $(QEMU_A64) $(BUILDDIR)/debug1-arm @paslang-debug1-arm-$$$$ > $(BUILDDIR)/debug1-arm.got; \
	diff -u testdata/debug1.out $(BUILDDIR)/debug1-arm.got; \
	echo ok debug-arm; \
	echo "==== debug console arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -debug -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/debug2-arm testdata/debug2.paslang; \
	DEBUG2_ENV=yes timeout 120 $(QEMU_A64) $(BUILDDIR)/debug2-arm --debug-mode one two < testdata/debug2.in > $(BUILDDIR)/debug2-arm.got 2>&1; \
	diff -u testdata/debug2.out $(BUILDDIR)/debug2-arm.got; \
	s=@paslang-debug2attach-arm-$$$$; \
	DEBUG2_ENV=yes timeout 120 $(QEMU_A64) $(BUILDDIR)/debug2-arm --debug-listen $$s x y > $(BUILDDIR)/debug2attach-arm.prog 2>&1 & p=$$!; \
	timeout 120 $(QEMU_A64) $(BUILDDIR)/debug2-arm --debug-attach $$s < testdata/debug2attach.in > $(BUILDDIR)/debug2attach-arm.got 2>&1; \
	wait $$p; \
	echo '--- the program' >> $(BUILDDIR)/debug2attach-arm.got; \
	cat $(BUILDDIR)/debug2attach-arm.prog >> $(BUILDDIR)/debug2attach-arm.got; \
	diff -u testdata/debug2attach.out $(BUILDDIR)/debug2attach-arm.got; \
	echo ok debug-console-arm; \
	echo "==== network servers arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -c src/lib/pasnet.paslang; \
	for t in httpd dnsd termd ftpd ntpd wsd chat proxy; do \
	  $(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/ex_$$t-arm examples/$$t.paslang; \
	  timeout 120 $(QEMU_A64) $(BUILDDIR)/ex_$$t-arm -selftest 300 > $(BUILDDIR)/ex_$$t-arm.got; \
	done; \
	echo "300 clients, 900 requests, 900 served, 0 bad" | diff -u - $(BUILDDIR)/ex_httpd-arm.got; \
	echo "300 clients, 300 answered, 0 missed, 0 bad" | diff -u - $(BUILDDIR)/ex_dnsd-arm.got; \
	echo "300 sessions, 300 quit, 0 bad" | diff -u - $(BUILDDIR)/ex_termd-arm.got; \
	echo "300 sessions, 300 stored, 300 fetched, 0 bad" | diff -u - $(BUILDDIR)/ex_ftpd-arm.got; \
	echo "300 queries, 300 answered, 0 missed, 0 bad" | diff -u - $(BUILDDIR)/ex_ntpd-arm.got; \
	echo "300 clients, 900 frames, 900 echoed, 0 bad" | diff -u - $(BUILDDIR)/ex_wsd-arm.got; \
	echo "300 clients, 300 said, 2700 delivered of 2700, 0 bad" | diff -u - $(BUILDDIR)/ex_chat-arm.got; \
	echo "300 clients, 300 forwarded, 900 requests, 900 served, 0 bad" | diff -u - $(BUILDDIR)/ex_proxy-arm.got; \
	echo ok network-servers-arm; \
	echo "==== ip6park arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -c src/lib/pasnet.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/ip6park-arm testdata/ip6park.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/ip6park-arm > $(BUILDDIR)/ip6park-arm.got; \
	diff -u testdata/ip6park.out $(BUILDDIR)/ip6park-arm.got; \
	echo ok ip6park-arm; \
	echo "==== deadln arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -c src/lib/pasnet.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/deadln-arm testdata/deadln.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/deadln-arm > $(BUILDDIR)/deadln-arm.got; \
	diff -u testdata/deadln.out $(BUILDDIR)/deadln-arm.got; \
	echo ok deadln-arm; \
	echo "==== edgeacc arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -c src/lib/pasnet.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/edgeacc-arm testdata/edgeacc.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/edgeacc-arm > $(BUILDDIR)/edgeacc-arm.got; \
	diff -u testdata/edgeacc.out $(BUILDDIR)/edgeacc-arm.got; \
	echo ok edgeacc-arm; \
	echo "==== reals arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/reals-arm testdata/reals.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/reals-arm > $(BUILDDIR)/reals-arm.got; \
	diff -u testdata/reals.out $(BUILDDIR)/reals-arm.got; \
	echo ok reals-arm; \
	echo "==== fastmath arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/fastmath-arm testdata/fastmath.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/fastmath-arm > $(BUILDDIR)/fastmath-arm.got; \
	diff -u testdata/fastmath.out $(BUILDDIR)/fastmath-arm.got; \
	echo ok fastmath-arm; \
	echo "==== forward arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/forward-arm testdata/forward.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/forward-arm > $(BUILDDIR)/forward-arm.got; \
	diff -u testdata/forward.out $(BUILDDIR)/forward-arm.got; \
	echo ok forward-arm; \
	echo "==== defaults arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/defaults-arm testdata/defaults.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/defaults-arm > $(BUILDDIR)/defaults-arm.got; \
	diff -u testdata/defaults.out $(BUILDDIR)/defaults-arm.got; \
	echo ok defaults-arm; \
	echo "==== abstract arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/abstract-arm testdata/abstract.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/abstract-arm > $(BUILDDIR)/abstract-arm.got; \
	diff -u testdata/abstract.out $(BUILDDIR)/abstract-arm.got; \
	echo ok abstract-arm; \
	echo "==== overload arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/overload-arm testdata/overload.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/overload-arm > $(BUILDDIR)/overload-arm.got; \
	diff -u testdata/overload.out $(BUILDDIR)/overload-arm.got; \
	echo ok overload-arm; \
	echo "==== methov arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/methov-arm testdata/methov.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/methov-arm > $(BUILDDIR)/methov-arm.got; \
	diff -u testdata/methov.out $(BUILDDIR)/methov-arm.got; \
	echo ok methov-arm; \
	echo "==== strdef arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/strdef-arm testdata/strdef.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/strdef-arm > $(BUILDDIR)/strdef-arm.got; \
	diff -u testdata/strdef.out $(BUILDDIR)/strdef-arm.got; \
	echo ok strdef-arm; \
	echo "==== unit string default arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/a64/sdef testdata/units/sdef.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/suse-arm testdata/units/suse.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/suse-arm > $(BUILDDIR)/suse-arm.got; \
	diff -u testdata/units/suse.out $(BUILDDIR)/suse-arm.got; \
	echo ok suse-arm; \
	echo "==== trig arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/trig-arm testdata/trig.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/trig-arm > $(BUILDDIR)/trig-arm.got; \
	diff -u testdata/trig.out $(BUILDDIR)/trig-arm.got; \
	echo ok trig-arm; \
	echo "==== logexp arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/logexp-arm testdata/logexp.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/logexp-arm > $(BUILDDIR)/logexp-arm.got; \
	diff -u testdata/logexp.out $(BUILDDIR)/logexp-arm.got; \
	echo ok logexp-arm; \
	echo "==== arctan arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/arctan-arm testdata/arctan.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/arctan-arm > $(BUILDDIR)/arctan-arm.got; \
	diff -u testdata/arctan.out $(BUILDDIR)/arctan-arm.got; \
	echo ok arctan-arm; \
	echo "==== invpow arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/invpow-arm testdata/invpow.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/invpow-arm > $(BUILDDIR)/invpow-arm.got; \
	diff -u testdata/invpow.out $(BUILDDIR)/invpow-arm.got; \
	echo ok invpow-arm; \
	echo "==== logx arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/logx-arm testdata/logx.paslang; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/logx-arm > $(BUILDDIR)/logx-arm.got; \
	diff -u testdata/logx.out $(BUILDDIR)/logx-arm.got; \
	echo ok logx-arm

install: all installdirs
	$(NORMAL_INSTALL)
	$(INSTALL_PROGRAM) $(OUTDIR)/paslangc $(DESTDIR)$(bindir)/paslangc
	$(INSTALL_PROGRAM) $(OUTDIR)/pasdbg $(DESTDIR)$(bindir)/pasdbg
	if [ -x $(OUTDIR)/paslangc-arm64 ]; then \
	  $(INSTALL_PROGRAM) $(OUTDIR)/paslangc-arm64 $(DESTDIR)$(bindir)/paslangc-arm64; \
	fi
	$(PRE_INSTALL)
	: every core unit, passtr too, P143: a list written out left it behind; \
	for u in $(CORE_UNITS) $(LIB_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  $(INSTALL_DATA) $(BUILDDIR)/$$b.pi $(BUILDDIR)/$$b.o $(DESTDIR)$(libdir)/paslang/; \
	done
	: the level builds, P143; \
	mkdir -p $(DESTDIR)$(libdir)/paslang/$(LVL_X64); \
	for u in $(CORE_UNITS) $(LIB_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  $(INSTALL_DATA) $(BUILDDIR)/$(LVL_X64)/$$b.o $(DESTDIR)$(libdir)/paslang/$(LVL_X64)/; \
	done
	if [ -f $(A64DIR)/pasmap.o ]; then \
	  for u in $(CORE_UNITS) $(LIB_UNITS); do \
	    b=$$(basename $$u .paslang); \
	    $(INSTALL_DATA) $(A64DIR)/$$b.pi $(A64DIR)/$$b.o $(DESTDIR)$(libdir)/paslang/aarch64/; \
	  done; \
	  mkdir -p '$(DESTDIR)$(libdir)/paslang/aarch64/$(LVL_A64)'; \
	  for u in $(CORE_UNITS) $(LIB_UNITS); do \
	    b=$$(basename $$u .paslang); \
	    $(INSTALL_DATA) '$(A64DIR)/$(LVL_A64)'/$$b.o '$(DESTDIR)$(libdir)/paslang/aarch64/$(LVL_A64)/'; \
	  done; \
	fi
	$(POST_INSTALL)
	$(DESTDIR)$(bindir)/paslangc -o $(BUILDDIR)/paslang-install-hello $(srcdir)/testdata/hello.paslang
	$(BUILDDIR)/paslang-install-hello
	rm -f $(BUILDDIR)/paslang-install-hello
	$(DESTDIR)$(bindir)/paslangc -target arm64 -o $(BUILDDIR)/paslang-install-a64 $(srcdir)/testdata/heapspan.paslang
	rm -f $(BUILDDIR)/paslang-install-a64

install-strip:
	$(MAKE) INSTALL_PROGRAM='$(INSTALL_PROGRAM) -s' install

# The release archives: one for each machine, laid out as an
# installation (bin, lib/paslang, share/doc/paslang, share/paslang), that
# works wherever it is unpacked: the compiler finds lib/paslang beside its
# bin (lib/paslang/aarch64 for the arm64 target). The amd64 archive also
# carries the arm64 units, so its compiler can compile for arm64 with the
# cross binutils. build/pkg/paslang-<version>-linux-<machine>.tar.gz.
PKGDOCS := README.md AUTHORS COPYING COPYING.RUNTIME COPYING.DOC LICENSE-GO docs/MANUAL.md docs/HELP.md docs/TYPES.md \
	docs/GC.md docs/QUAD.md docs/KERNELS.md docs/VISION.md docs/CONSTRAINTS.md
package: all compilers $(OUTDIR)/pasdbg
	@set -e; \
	v=$$($(OUTDIR)/paslangc -v | grep -o 'paslangc  *[0-9][0-9.]*' | head -1 | awk '{print $$2}'); \
	test -n "$$v"; \
	for m in amd64 arm64; do \
	  n=paslang-$$v-linux-$$m; d=$(BUILDDIR)/pkg/$$n; \
	  rm -rf $$d $$d.tar.gz; \
	  mkdir -p $$d/bin $$d/lib/paslang/aarch64 $$d/lib/paslang/$(LVL_X64) "$$d/lib/paslang/aarch64/$(LVL_A64)" \
	    $$d/share/doc/paslang/manual $$d/share/paslang; \
	  if [ $$m = amd64 ]; then \
	    cp $(OUTDIR)/paslangc $(OUTDIR)/pasdbg $$d/bin/; \
	    for u in $(CORE_UNITS) $(LIB_UNITS); do \
	      b=$$(basename $$u .paslang); cp $(BUILDDIR)/$$b.pi $(BUILDDIR)/$$b.o $$d/lib/paslang/; \
	      cp $(BUILDDIR)/$(LVL_X64)/$$b.o $$d/lib/paslang/$(LVL_X64)/; \
	    done; \
	  else \
	    cp $(OUTDIR)/paslangc-arm64 $$d/bin/paslangc; \
	    $(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $$d/bin/pasdbg cmd/pasdbg/pasdbg.paslang; \
	    rm -f $$d/bin/pasdbg.o $$d/bin/pasdbg.s $$d/bin/pasdbg.ld; \
	  fi; \
	  for u in $(CORE_UNITS) $(LIB_UNITS); do \
	    b=$$(basename $$u .paslang); cp $(A64DIR)/$$b.pi $(A64DIR)/$$b.o $$d/lib/paslang/aarch64/; \
	    cp '$(A64DIR)/$(LVL_A64)'/$$b.o "$$d/lib/paslang/aarch64/$(LVL_A64)/"; \
	  done; \
	  cp $(PKGDOCS) $$d/share/doc/paslang/; \
	  cp docs/manual/index.html $$d/share/doc/paslang/manual/; \
	  cp -r examples $$d/share/paslang/examples; \
	  rm -rf $$d/share/paslang/examples/build; \
	  tar -C $(BUILDDIR)/pkg --owner=0 --group=0 --numeric-owner -czf $$d.tar.gz $$n; \
	  echo "$$d.tar.gz"; \
	done

# The packages of the distributions, for amd64 and arm64
# (scripts/distpkg.py): .deb, .rpm, Arch's .pkg.tar.zst and Slackware's
# .tgz, each installing under /usr, into build/pkg/dist.
distpkg: package
	python3 scripts/distpkg.py

# Everything a release carries, in build/pkg/release: the two archives
# of make package for this version (an older version's, left in
# build/pkg, stays out), the packages of make distpkg, and SHA256SUMS of
# them all. Every release uploads the whole directory.
release-assets: distpkg
	@set -e; \
	v=$$($(OUTDIR)/paslangc -v | grep -o 'paslangc  *[0-9][0-9.]*' | head -1 | awk '{print $$2}'); \
	test -n "$$v"; \
	rm -rf $(BUILDDIR)/pkg/release; mkdir -p $(BUILDDIR)/pkg/release; \
	cp $(BUILDDIR)/pkg/paslang-$$v-linux-*.tar.gz $(BUILDDIR)/pkg/dist/* $(BUILDDIR)/pkg/release/; \
	cd $(BUILDDIR)/pkg/release && sha256sum * > SHA256SUMS && cat SHA256SUMS

uninstall:
	rm -f $(DESTDIR)$(bindir)/paslangc $(DESTDIR)$(bindir)/paslangc-arm64 $(DESTDIR)$(bindir)/pasdbg
	rm -rf $(DESTDIR)$(libdir)/paslang

installdirs:
	mkdir -p $(DESTDIR)$(bindir) $(DESTDIR)$(libdir)/paslang $(DESTDIR)$(libdir)/paslang/aarch64 \
	  $(DESTDIR)$(libdir)/paslang/$(LVL_X64) '$(DESTDIR)$(libdir)/paslang/aarch64/$(LVL_A64)'

installcheck:
	$(DESTDIR)$(bindir)/paslangc -o $(BUILDDIR)/paslang-installcheck $(srcdir)/testdata/hello.paslang
	$(BUILDDIR)/paslang-installcheck
	rm -f $(BUILDDIR)/paslang-installcheck
	$(DESTDIR)$(bindir)/paslangc -o $(BUILDDIR)/paslang-installcheck-who $(srcdir)/examples/pasroutines/who.paslang
	$(BUILDDIR)/paslang-installcheck-who
	rm -f $(BUILDDIR)/paslang-installcheck-who

mostlyclean:

distclean: clean
	rm -f config.mk config.status config.log

maintainer-clean:
	@echo 'This command is intended for maintainers to use; it'
	@echo 'deletes files that may need special tools to rebuild.'
	$(MAKE) distclean

clean:
	rm -rf $(OUTDIR) $(UNITDIR) $(BUILDDIR)
