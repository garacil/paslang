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

OUTDIR   := ./bin
BUILDDIR := ./build
# paslang is built by paslangc alone (P262, Reglas 9 and 15). The oldest
# paslangc that compiles these sources (cmd/paslangc says it with $if
# too), and the seed a machine with none starts from: the assembly
# paslangc writes for itself, built with as and ld (scripts/bootstrap_seed.py).
BOOT_MIN := 1.1.156
SEED_DIR := bootstrap
# The processor bin/paslangc is built for (P264, Reglas 14 and 15): the
# machine building it, as every program is by default; make
# SELF_CPU=<processor, level or features> another, base for any machine
# of its kind. Its units and the core units it links are built for it
# too, in the stage's own directory; the installed core units stay built
# for base and their level (P143). What a release carries for other
# machines, bin/paslangc-base and bin/paslangc-arm64, is built for base.
SELF_CPU ?= native

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

.PHONY: package distpkg release-assets check-release bench-rounds all hello check check-arm64 clean bootstrap-seed self self-arm64 stage compilers core core-arm64 libs libs-arm64 bench manual \
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

# The machine make runs on, which configure found (config.mk), else
# uname: make builds and installs that machine's units. paslangc
# assembles amd64 with /usr/bin/as, so the amd64 units are built on amd64
# alone. The arm64 units are built on arm64, and on amd64 when asked for
# (./configure --enable-arm64, or ARM64=yes), which needs the arm64
# binutils by the paths paslangc runs them (Assemble and the link in
# cmd/paslangc). make check, on amd64, needs both.
ifeq ($(origin MACHINE),undefined)
ifneq ($(filter aarch64 arm64,$(shell uname -m)),)
MACHINE := arm64
else
MACHINE := amd64
endif
endif
ARM64 ?=
ifeq ($(MACHINE),arm64)
AMD64 :=
override ARM64 := yes
else
AMD64 := yes
endif

# Every unit is built again for one processor level of each machine
# (P143), x86-64-v3 and ARMv8.2 with its crypto extension, in a
# directory beside the base build: a program compiled for a -cpu with
# every feature of the level links those objects, so a unit's words
# that choose a kernel by -cpu take the program's, as Go compiles every
# package at its GOAMD64 level. The interfaces (.pi) are the same.
# amd64's level is x86-64-v3 with AES-NI and PCLMULQDQ (P465), which v3
# leaves out and pascipher's kernels need, in the directory v3.
LVL_X64 := v3
LVL_X64_CPU := v3+aes+pclmul
LVL_A64 := v8.2+crypto
A64_OBJDUMP ?= aarch64-linux-gnu-objdump

# The golden tests: testdata/<t>.paslang must print testdata/<t>.out.
GOLDEN := hello arith ifthen loops const caseof procs recfn records ptrs arrs strs grow paswork pingpong chclose sel exc excg nest cls gen enums sets dbg opt gdbg inherit rtti args8 mevent slice chlit armmeth propacc runes variant opadd args20 iface opmore props pindex dwarfloc shift dynnil xor inhcall isas sysid forward defaults abstract overload methov strdef trig logexp arctan invpow logx trig2 hyper miscmath xxh32 xxh64 map1 map2 sync1 sync2 finexit zerolocal pchar selx selstress wrchar chstr lookpath strcmp dupparam recarg funcval constk regloop reszero divconst bareln gctypes chr charcat heapspan blobzero gcbasic mapsplit stackmap trygrow growgc xxh3 mapgetstr bounds fairq sized fwdptr constexpr int2real typedconst caserange emptystmt writefmt realparse realfmt valpar strcow chanany chanbuf memmove overnarrow slicegrow fatexit narrow narrowmem recalign narrowbounds dwarfnarrow narrowgo forlimit bce inplace narrowasm slicereg forrun addrform bcerun inspine framearr realstep f32conv single dwarfreal ptrtyped ptrarith ptrsafe memview checkptr ptrreach cpwalk realint quadcore quadfmt quad quadconst dwarfquad bitops declorder convchain bitwords bitmem bitany views blocks wide ifdef quadfast memwords cpuwords vectors vecmore inlineasm vecpool addrlocal rotwords rotmem ctxwords append funcval2 closures pasargs ifaceargs vshrs64 auditfix closurebox audit2 visibility freedestroy reservedall nodeadlock mapfix tree1 tree2 hash1 store1 immwide constref inline1 stackargs mainexit networds charcmp unixsock sigpipe sleepmany deadlines strfill narrowpop tobject1 excobj1 excobj2 excobj3 classref1 ctorargs aconst1 aconst2 methdef1 set256 subrange1 subrange2 helper1 helper2 strwords strkern slicedit strcmpk scope1 classfwd ifacebind overconv overrank valunsigned sysutils1 sysutils2 initvar extended1 valround valround2 cmpwords fmtfloat1 fmtfloat2 format1 realtext quadtext valrange hidesys arrindex constround dates1 dates2 nestscope recmeth
GOLDEN_A64 := map1 map2 sync1 sync2 finexit zerolocal pchar pingpong sel chclose paswork selx selstress wrchar args8 arith arrs caseof chlit cls const enums exc excg gen grow hyper ifthen inherit loops mevent miscmath nest procs ptrs recfn records sets strs trig2 xxh32 xxh64 rtti gdbg chstr strcmp recarg funcval constk regloop reszero divconst bareln gctypes chr charcat heapspan blobzero gcbasic mapsplit stackmap trygrow growgc xxh3 mapgetstr bounds fairq sized fwdptr constexpr int2real typedconst caserange emptystmt writefmt realparse realfmt valpar strcow chanany chanbuf memmove overnarrow slicegrow fatexit narrow narrowmem recalign narrowbounds dwarfnarrow narrowgo forlimit bce inplace narrowasm slicereg forrun addrform bcerun inspine framearr realstep f32conv single dwarfreal ptrtyped ptrarith ptrsafe memview checkptr ptrreach cpwalk realint quadcore quadfmt quad quadconst dwarfquad bitops declorder convchain bitwords bitmem bitany views blocks wide ifdef quadfast memwords cpuwords vectors vecmore inlineasm vecpool addrlocal rotwords rotmem ctxwords append funcval2 closures pasargs ifaceargs vshrs64 auditfix closurebox audit2 visibility freedestroy reservedall nodeadlock mapfix tree1 tree2 hash1 store1 immwide constref inline1 stackargs mainexit networds charcmp unixsock sigpipe sleepmany deadlines strfill narrowpop tobject1 excobj1 excobj2 excobj3 classref1 ctorargs aconst1 aconst2 methdef1 set256 subrange1 subrange2 helper1 helper2 strwords strkern slicedit strcmpk scope1 classfwd ifacebind overconv overrank valunsigned sysutils1 sysutils2 initvar extended1 valround valround2 cmpwords fmtfloat1 fmtfloat2 format1 realtext quadtext valrange hidesys arrindex constround dates1 dates2 nestscope recmeth

# P166: record operands bind once, including a with inside recursion.
GOLDEN += withonce withcapture withmap
GOLDEN_A64 += withonce withcapture withmap
# P343: HMAC with its pad in the hash state, no copy of the message.
GOLDEN += hmacstream
GOLDEN_A64 += hmacstream
# P172: with on an object.
GOLDEN += withobj
GOLDEN_A64 += withobj
GOLDEN += treewide
GOLDEN_A64 += treewide
GOLDEN += recstatic
GOLDEN_A64 += recstatic
GOLDEN += nestednames nestedmore nestedgeneric genericlocal
GOLDEN_A64 += nestednames nestedmore nestedgeneric genericlocal
GOLDEN += forkguard forksignals
GOLDEN_A64 += forkguard forksignals
GOLDEN += textcasts
GOLDEN_A64 += textcasts
GOLDEN += syshelpers sysguid
GOLDEN_A64 += syshelpers sysguid
GOLDEN += sysfamilies
GOLDEN_A64 += sysfamilies
GOLDEN += currency1 syscurrency corekinds
GOLDEN_A64 += currency1 syscurrency corekinds
GOLDEN += placeonce dwarfcurrency selectflow realincplace quadincplace intcompplace
GOLDEN_A64 += placeonce dwarfcurrency selectflow realincplace quadincplace intcompplace
GOLDEN += arrayidentity
GOLDEN_A64 += arrayidentity
GOLDEN += debuggrow
GOLDEN_A64 += debuggrow
# P197: maps made by 64 routines at once each take a seed of their own.
GOLDEN += mapseed
GOLDEN_A64 += mapseed
# P198: strings that are views of a block nothing writes (PasStrView).
GOLDEN += strview
GOLDEN_A64 += strview
# P199: the one loop of I/O that parks (PasIoRetry): EINTR, EAGAIN on
# pipes and sockets, deadlines, failed waits, 64 routines parked.
GOLDEN += ioretry
GOLDEN_A64 += ioretry
# P212: standard output and standard error, a lock each; a WriteLn that
# fits in 4096 bytes is one write, so two streams on one pipe keep their
# lines whole.
GOLDEN += stdlocks
GOLDEN_A64 += stdlocks
# P213: WaitMs with no time left answers 0 at once, on a pipe and a
# socket, from main and from a routine while main goes on.
GOLDEN += waitms0
GOLDEN_A64 += waitms0
# P214, P222: SetLength that shortens a string it owns keeps its block
# while the string fills more than half of it; a shared string, a
# literal and a view are still copied.
GOLDEN += strshrink
GOLDEN_A64 += strshrink
# P215: UdpRecvFrom and UdpRecvFromMs are one body: an IPv6 sender, an
# IPv4 one and an empty datagram named alike by both, on both machines.
GOLDEN += udpfrom
GOLDEN_A64 += udpfrom
# P216: connecting waits as Go's netFD.connect does: slow connects while
# the listener's queue is full, closed ports, unreachable addresses and
# a deadline that bounds a name's resolution (check_syscalls.py adds
# EINTR, a spurious wake and a silent nameserver under gdb).
GOLDEN += connwait
GOLDEN_A64 += connwait
# P227: TryGet of a map marks the strings it copies out, as TryGet of a
# tree does: a write to the copy left the map's value changed.
GOLDEN += trygetshare
GOLDEN_A64 += trygetshare
# P228: an element of a tree given as a var or out argument is its
# value's slot on both machines, as a map's is.
GOLDEN += treevarg
GOLDEN_A64 += treevarg
# P221: a string a routine builds and returns is stored without the
# shared mark; one another variable holds is marked whichever way it
# reaches Result, and the holder never changes.
GOLDEN += resultmark
GOLDEN_A64 += resultmark
# P242: s := s + x and s += x grow s in its own block when it has room,
# and a block past 32 KiB grows where it is: every answer is the
# concatenation's, through every kind of place, shared strings, places
# x's routines change, the collector and two large strings in turn.
GOLDEN += strappend
GOLDEN_A64 += strappend
# a condition as branches against the same condition as a value (P265)
GOLDEN += condjump
GOLDEN_A64 += condjump
# a function of one expression goes in as its expression (P266)
GOLDEN += exprinline
GOLDEN_A64 += exprinline
# the processor in the code: $CPU and $TUNE, LZCNT and TZCNT (P261)
GOLDEN += cputune
GOLDEN_A64 += cputune
# UTF-8 validation, one kernel per machine (P201)
GOLDEN += utf8kern
GOLDEN_A64 += utf8kern
GOLDEN += longslice
GOLDEN_A64 += longslice
GOLDEN += rtlong
GOLDEN_A64 += rtlong
GOLDEN += fillkern
GOLDEN_A64 += fillkern
# JSON's scans, one kernel per machine (P202)
GOLDEN += jsonkern
GOLDEN_A64 += jsonkern
# the json type (P203): reading, the errors, the numbers, RFC 8785, and a
# document read by 64 routines at once
GOLDEN += json1 json2 jsonnum jsoncanon jsonshare
GOLDEN_A64 += json1 json2 jsonnum jsoncanon jsonshare
# P203: a register-held index scaled for a record of 56 bytes in a loop
# whose run end lives in r11
GOLDEN += chunkidx
GOLDEN_A64 += chunkidx
# P263: code chooses by the version of paslangc compiling it: {$if},
# {$elseif}, PASLANG_FULLVERSION and its parts, defined(), skipped branches.
GOLDEN += condver
GOLDEN_A64 += condver
# P274: paslib reads a whole file in place: every length about 512
# and 4096, some MB, a pipe a child writes, a file of /proc, a
# directory, ReadPrefix and RunCapture, the bytes compared.
GOLDEN += readwhole
GOLDEN_A64 += readwhole
# P275: a var or out parameter of a record goes in place; a place found
# through a variable another var parameter is given stays a call.
GOLDEN += inlinevar
GOLDEN_A64 += inlinevar
# P276: SysUtils reads a whole file into the result itself: lengths about
# 512 and 4096 and some MB, budgets either side, a handle in the middle,
# GetFileAsString, /proc, a pipe a routine writes.
GOLDEN += syswhole
GOLDEN_A64 += syswhole
# P277: every descriptor paslib opens closes on exec: the flag in
# /proc/self/fdinfo, and a child another routine runs has none of them.
GOLDEN += cloexec
GOLDEN_A64 += cloexec
# P204: json with the rest of the language: channels, select, map, tree,
# fields, arrays, generics, closures, pas, helpers, case, array of const,
# Format, Write widths, safe.
GOLDEN += jsonlang
GOLDEN_A64 += jsonlang
# P205: JsonEncode and JsonOf of a value of any type with a JSON form,
# through the encoder the compiler writes for it, every directive.
GOLDEN += jsonbind1 jsonbind2 jsonbind3
GOLDEN_A64 += jsonbind1 jsonbind2 jsonbind3
# P282: a loop reads and writes the fields of a var or const parameter
# through a register that keeps its address, on a stack that grows.
GOLDEN += varparts
GOLDEN_A64 += varparts
# P283: a while and a repeat that count run in runs of 1024 passes with
# one preemption test a run, as a for does.
GOLDEN += whilerun
GOLDEN_A64 += whilerun
# P284: a local or a Result that every path writes first starts as it
# is, and a call's stack map counts it only where it is written.
GOLDEN += lazyzero
GOLDEN_A64 += lazyzero
# P285: a map of up to eight keys is one group, as Go's small map, and
# takes less memory than Go's at every count of keys.
GOLDEN += mapsmall
GOLDEN_A64 += mapsmall
# P286: a string of one character takes no memory, as Go's: the
# runtime's table of the 256, shared.
GOLDEN += strone
GOLDEN_A64 += strone
# P287: a slice's frontier costs no size class, the guarantees of 1.0.88
# kept.
GOLDEN += slicefront
GOLDEN_A64 += slicefront
# P288: a small leaf routine has no stack check and no frame, and a
# routine that calls nothing no stack check.
GOLDEN += leafcall
GOLDEN_A64 += leafcall
# P289: a bounds check the index's range proves is left out.
GOLDEN += bceprove
GOLDEN_A64 += bceprove
# P290: arm64 works on a register variable where it lives.
GOLDEN += armregs
GOLDEN_A64 += armregs
# P291: a field of a local record is read and written from the frame
# pointer.
GOLDEN += framefield
GOLDEN_A64 += framefield
# P292: a range test is one unsigned compare.
GOLDEN += rangetest
GOLDEN_A64 += rangetest
# P293: a loop that does not count is preempted by a signal, as Go's.
GOLDEN += asyncspin asyncgc asyncleaf
GOLDEN_A64 += asyncspin asyncgc asyncleaf
# P350: a Sleep pokes the poller only for a timer before the earliest,
# the first one and one after the heap emptied beside a poller's wait.
GOLDEN += pokewait
GOLDEN_A64 += pokewait
# P352: each P keeps its own timers: sleeps and deadlines spread over the
# Ps, one poller, a deadline's timer off the P that holds it.
GOLDEN += ptimers
GOLDEN_A64 += ptimers
# P345: a global only the main block names lets its value go after its last use.
GOLDEN += mainlive
GOLDEN_A64 += mainlive
# P328: a word worked out in the pool lands in the register that reads it.
GOLDEN += argreg
GOLDEN_A64 += argreg
# P332: several arguments worked out in the pool push nothing.
GOLDEN += manyargs
GOLDEN_A64 += manyargs
# P355: every argument that calls nothing pushes nothing.
GOLDEN += heldargs
GOLDEN_A64 += heldargs
# P359: the lowest Int64 divided by -1 wraps on amd64 as on arm64.
GOLDEN += divwrap
GOLDEN_A64 += divwrap
# P356: a division's value lands in the register that reads it.
GOLDEN += divreg
GOLDEN_A64 += divreg
# P357: a nested routine reads its outer routine's variables in the pool.
GOLDEN += uplevel
GOLDEN_A64 += uplevel
# P358: a routine with nested ones zeroes only the locals a read may reach first.
GOLDEN += nestzero
GOLDEN_A64 += nestzero
# P360: a binary operation keeps its left side in a register while a right side that calls nothing is worked out.
GOLDEN += keepleft
GOLDEN_A64 += keepleft
# P150: among overloads the nearest conversion wins.
GOLDEN += overnear
GOLDEN_A64 += overnear
# P334: a closure or nested routine that calls nothing has no frame.
GOLDEN += nestflat
GOLDEN_A64 += nestflat
# P361: a routine with no frame works its value out in the register it returns it in.
GOLDEN += retreg
GOLDEN_A64 += retreg
# P362: a label no jump reaches stands in no fold's way.
GOLDEN += adrplast
GOLDEN_A64 += adrplast
# P153: a record result without the heap.
GOLDEN += recres
GOLDEN_A64 += recres
# P364: for x in a static array a call gives takes the array once.
GOLDEN += forinonce
GOLDEN_A64 += forinonce
# P365: a field of the record a property's getter gives.
GOLDEN += propblob
GOLDEN_A64 += propblob
# P366: a record of up to three words comes back in registers.
GOLDEN += regres
GOLDEN_A64 += regres
# P367: a record Result written field by field before it is read starts as it is.
GOLDEN += fieldfirst
GOLDEN_A64 += fieldfirst
# P370: a block assigned is copied or zeroed in line, and a copy through nil stops.
GOLDEN += blockcopy
GOLDEN_A64 += blockcopy
# P368: a routine whose result is a block is put in place.
GOLDEN += blockinl
GOLDEN_A64 += blockinl
# P369: a method no override can change is put in place.
GOLDEN += methinl
GOLDEN_A64 += methinl
# P371: Result and the main block's own globals are operands no call put in place changes.
GOLDEN += aheadres
GOLDEN_A64 += aheadres
# P373: the address of an element goes straight into the register that reads it.
GOLDEN += elemaddr
GOLDEN_A64 += elemaddr
# P377: High of a slice reads its length alone, and a test of an index against both its ends is one compare.
GOLDEN += boundsidiom
GOLDEN_A64 += boundsidiom
# P374: on arm64 a global's field or element at a constant offset is one adrp and one access.
GOLDEN += globoff
GOLDEN_A64 += globoff
# P378: the hidden variables of routines put in place share the frame's slots.
GOLDEN += hidshare
GOLDEN_A64 += hidshare
# P157: operators on two types with no name are two routines.
GOLDEN += opanon
GOLDEN_A64 += opanon
# P170: a class helper's constructor and static method through the class's name.
GOLDEN += helpctor
GOLDEN_A64 += helpctor
# P380: a class's helper is searched at the class's own level.
GOLDEN += helplevel
GOLDEN_A64 += helplevel
# P171: operators declared in a record.
GOLDEN += recops
GOLDEN_A64 += recops
# P381: the rest of the operators, top level and a record's.
GOLDEN += opunary recops2
GOLDEN_A64 += opunary recops2
# P224: Resolve asks as Go's resolver does.
GOLDEN += resolveask
GOLDEN_A64 += resolveask
# P225: no pasnet word ends the program over a host it cannot read.
GOLDEN += hostread
GOLDEN_A64 += hostread
# P207: building and transforming json.
GOLDEN += jsonbuild jsonmod
GOLDEN_A64 += jsonbuild jsonmod
# P382: a write to a broken pipe is EPIPE.
GOLDEN += brokenpipe
GOLDEN_A64 += brokenpipe
# P208: json streams that park.
GOLDEN += jsonstream jsonpark
GOLDEN_A64 += jsonstream jsonpark
# P401: a descriptor the poller holds leaves its set before it is closed.
GOLDEN += pollclose
GOLDEN_A64 += pollclose
# P209: json constants checked by the compiler.
GOLDEN += jsonconst
GOLDEN_A64 += jsonconst
# P354: a routine's record keeps no saved register once it is loaded back.
GOLDEN += gstale
GOLDEN_A64 += gstale
# P294: arithmetic in one instruction where it took several.
GOLDEN += leaform
GOLDEN_A64 += leaform
# P299: a check's failure out of line, the checked path without a branch.
GOLDEN += coldfail
GOLDEN_A64 += coldfail
# P301: a loop whose only calls sit on slow paths keeps its variables in
# registers.
GOLDEN += coldloop
GOLDEN_A64 += coldloop
# P303: a pointer a region keeps in a register is read and tested where
# it lives.
GOLDEN += ptrwalk
GOLDEN_A64 += ptrwalk
# P305: an if without an else jumps over nothing.
GOLDEN += ifcase
GOLDEN_A64 += ifcase
# P304: Move and FillChar of a constant count up to 128 bytes in line.
GOLDEN += movefill
GOLDEN_A64 += movefill
# P306: a constant an instruction can take is its immediate.
GOLDEN += immconst
GOLDEN_A64 += immconst
# P295: a product by a constant is shifts and adds where that is faster.
GOLDEN += mulconst
GOLDEN_A64 += mulconst
# P308: an arm64 prologue takes its frame size as immediates.
GOLDEN += framesize
GOLDEN_A64 += framesize
# P307: an if whose arms only assign a word is a conditional select.
GOLDEN += selectif
GOLDEN_A64 += selectif
# P298: a lea of three components is two where the processor makes it slow.
GOLDEN += leasplit
GOLDEN_A64 += leasplit
# P310: an element's index is scaled by shifts and leas.
GOLDEN += idxscale
GOLDEN_A64 += idxscale
# P311: a field of an element is read and written through one address.
GOLDEN += fieldaddr
GOLDEN_A64 += fieldaddr
# P312: every product by a constant takes its recipe, the remainder's too.
GOLDEN += modconst
GOLDEN_A64 += modconst
# P313: an index that is a sum takes its constant into the displacement.
GOLDEN += idxsum
GOLDEN_A64 += idxsum
# P314: an element's index is scaled once for its fields.
GOLDEN += fieldcse
GOLDEN_A64 += fieldcse
# P315: an arm64 constant goes into its register with no literal load.
GOLDEN += armconst
GOLDEN_A64 += armconst
# P316: a bounds check an earlier one proves is left out.
GOLDEN += chkcse
GOLDEN_A64 += chkcse
# P317: a product inside a conversion reads its variable in its register.
GOLDEN += convmul
GOLDEN_A64 += convmul
# P318: a variable a register keeps is assigned there, a narrow one read there.
GOLDEN += regassign
GOLDEN_A64 += regassign
# P319: a run's head proves a slice by its length, in a register or at home.
GOLDEN += runlen
GOLDEN_A64 += runlen
# P320: an and with $FF, $FFFF or $FFFFFFFF is a zero extension.
GOLDEN += andmask
GOLDEN_A64 += andmask
# P321: a constant from 0 to 2^32 - 1 by a movl, 0 by an xorl where the flags die.
GOLDEN += movconst
GOLDEN_A64 += movconst
# P322: an and compared with 0 is one test of its source.
GOLDEN += andtest
GOLDEN_A64 += andtest
# P296: a routine that calls nothing keeps its variables in registers, no frame.
GOLDEN += flatproc
GOLDEN_A64 += flatproc
# P323: a product by a constant with no recipe is one imulq from its variable.
GOLDEN += imulconst
GOLDEN_A64 += imulconst
# P324: a check against a slice's length at its home is kept, eight at a time.
GOLDEN += memlen
GOLDEN_A64 += memlen
# P297: a call inside an expression pushes nothing, its operands in their order.
GOLDEN += callexpr
GOLDEN_A64 += callexpr
# P327: a for loop whose body calls reads its counter once a pass.
GOLDEN += forstep
GOLDEN_A64 += forstep
# P330: a value goes to its place without the stack.
GOLDEN += twostore
GOLDEN_A64 += twostore
GOLDEN += elemop
GOLDEN_A64 += elemop
# P331: an arm64 global is loaded and stored by adrp and its low twelve bits.
GOLDEN += globfold
GOLDEN_A64 += globfold
# P333: an exec and a new thread do not race (amd64: qemu-user does not
# execve an arm64 program, so arm64 reads the runtime's forms).
GOLDEN += execrace
# P326: an inlined call is put ahead only of what it cannot change.
GOLDEN += inlineorder
GOLDEN_A64 += inlineorder
# P336: an unrolled loop keeps its counter where what it calls reads it.
GOLDEN += unrollctr
GOLDEN_A64 += unrollctr
# P325: a var parameter through a routine value or a method value.
GOLDEN += varvalue
GOLDEN_A64 += varvalue
# P339: a token at the end of its line has that line, SrcLine its own.
GOLDEN += lineend
GOLDEN_A64 += lineend
# P338: a routine value, a method value and an interface take their kind.
GOLDEN += valkinds
GOLDEN_A64 += valkinds
# P384: a loop that calls keeps its variables in registers.
GOLDEN += isles
GOLDEN_A64 += isles
# P385: the address of a pointer's element is one instruction.
GOLDEN += ptrelem
GOLDEN_A64 += ptrelem
# P386: a store whose place is registers alone pushes no value.
GOLDEN += storereg
GOLDEN_A64 += storereg
# P390: a comparison deeper than the pool, as a condition, makes no Boolean.
GOLDEN += cmpdeep
GOLDEN_A64 += cmpdeep
# P391: an expression deeper than the pool keeps its partial values in registers.
GOLDEN += parkleft
GOLDEN_A64 += parkleft
# P392: a slice's element from its pointer and length alone.
GOLDEN += slicehead
GOLDEN_A64 += slicehead
# P211: JsonValid where its window ends, a text again by Token, a decode's
# arrays counted within a bound and grown past it, escapes undone in place.
GOLDEN += jsonvalidwin jsontoken jsondecgrow jsondecesc
GOLDEN_A64 += jsonvalidwin jsontoken jsondecgrow jsondecesc
# P387: a byte's test against a constant set, its bit in the set's word.
GOLDEN += bytesetin
GOLDEN_A64 += bytesetin
# P394: a bit count of a value an if proved not zero, no sentinel.
GOLDEN += bitnz
GOLDEN_A64 += bitnz
# P395: the token reader's errors in Go's Decoder's words.
GOLDEN += jsontokerr
GOLDEN_A64 += jsontokerr
# P396: a routine's straight code keeps its variables in registers.
GOLDEN += straight
GOLDEN_A64 += straight
# P397: a field of an object a register holds is a leaf of an expression.
GOLDEN += regleaf
GOLDEN_A64 += regleaf
# P402: Inc and Dec of a place in memory are one add or sub.
GOLDEN += incplace
GOLDEN_A64 += incplace
# P398: an element of a slice a field holds is reached with no push.
GOLDEN += sliceat
GOLDEN_A64 += sliceat
# P399: Move's three arguments go straight to their registers.
GOLDEN += moveregs
GOLDEN_A64 += moveregs
# P400: a statement whose expression calls keeps the rest of it in the region.
GOLDEN += splitcall
GOLDEN_A64 += splitcall
# P474: JsonEncode still takes a set, a typed variable and JsonArray of a list.
GOLDEN += jsonlistok
GOLDEN_A64 += jsonlistok
# P463: ToLower of a string with no capital is the string itself.
GOLDEN += tolowershare
GOLDEN_A64 += tolowershare
# P403: SQLite named in a uses clause, uses sqlite since P418, a database in memory.
GOLDEN += sqluses
GOLDEN_A64 += sqluses
# P419: SetLength(a, 0) of a dynamic array leaves it nil and lets its
# block go; a nil array set to length 0 and the literal [] take no block.
GOLDEN += setlenzero
GOLDEN_A64 += setlenzero
# P421: a routine value, a closure and a method value called with 7, 9
# and 12 arguments, past the registers on the stack.
GOLDEN += callvalargs
GOLDEN_A64 += callvalargs
# P422: var and out parameters given variables of their own types, open
# arrays any array of their element type.
GOLDEN += varparamtype
GOLDEN_A64 += varparamtype
# P423: GcCollect frees a block whose address only dead scratch registers
# hold, put there by inline assembly before the call.
GOLDEN += gcdeadreg
GOLDEN_A64 += gcdeadreg
# P439: signals as the os/signal of Go sends them, uses passignal; on arm64 in
# its own block, whose children run under qemu.
GOLDEN += signals
# P434: the HTTP server, every limit, deadline, error and feature.
GOLDEN += httpsrv
GOLDEN_A64 += httpsrv
# P438: Argon2 and BLAKE2b against their published vectors, the PHC string.
GOLDEN += argon2kat
GOLDEN_A64 += argon2kat
# P428: AES, GCM, ChaCha20-Poly1305, HKDF and the TLS 1.2 PRF against Go's tests and Wycheproof.
GOLDEN += cipherkat cipherwyche
GOLDEN_A64 += cipherkat cipherwyche
# P429: X25519, P-256 and P-384, RSA against RFC 7748 and Wycheproof.
GOLDEN += x25519kat x25519wyche nistwyche rsawyche
GOLDEN_A64 += x25519kat x25519wyche nistwyche rsawyche
# P430: X.509 against Go's crypto/x509, PEM, routines sharing roots.
GOLDEN += x509verify x509pem x509conc
GOLDEN_A64 += x509verify x509pem x509conc
# P440: the digests in pieces equal the whole-message words, every cut.
GOLDEN += hashpieces
GOLDEN_A64 += hashpieces
# P443: HMAC and SHA-3 in pieces equal the whole-message words, every cut.
GOLDEN += hashpieces2
GOLDEN_A64 += hashpieces2
# P435: base64, URL, CSV and letters against Go's own output; LoadZone
# against time.LoadLocation (the system's zoneinfo).
GOLDEN += codec zones
GOLDEN_A64 += codec zones
# P445: a closure over a const parameter of every kind, kept past the call.
GOLDEN += closureconst
GOLDEN_A64 += closureconst
# P456: Default of a block passed as an argument and stored where no plain variable is.
GOLDEN += defaultarg
GOLDEN_A64 += defaultarg
# P426: the XML reader against expat on 2672 documents, and the tree's edits.
GOLDEN += xmlcorpus xmldom xmlentity
GOLDEN_A64 += xmlcorpus xmldom xmlentity
# P427: DEFLATE, zlib and gzip read against zlib and Go on 1893 streams, the writer round trip, ZIP against zipfile and Go.
GOLDEN += flate flatec zip
GOLDEN_A64 += flate flatec zip
# P436: XLSX templates filled, the entries not written kept as they were.
GOLDEN += xlsx
GOLDEN_A64 += xlsx
# P454: shared strings written, rows given a model row's attributes.
GOLDEN += xlsxsst
GOLDEN_A64 += xlsxsst
# P432: URLs and HTTP messages against Go, and the HTTP client over loopback.
GOLDEN += url httpmsg httpcli
GOLDEN_A64 += url httpmsg httpcli
# P453: a head fed a byte at a time costs time linear in its size.
GOLDEN += httpslow
GOLDEN_A64 += httpslow
# P433: mail against Go (mime, net/mail, net/smtp) and Python (email), SMTP and IMAP over loopback.
GOLDEN += mime mailtree mailbuild mailscale mailtls smtp imap
GOLDEN_A64 += mime mailtree mailbuild mailscale mailtls smtp imap
# P451: base64 as it was written first, against the faster one.
GOLDEN += base64fast
GOLDEN_A64 += base64fast
# P480: Val and StrToInt on the short path and the long, as the compiler before it read them.
GOLDEN += valdec
GOLDEN_A64 += valdec
# P481: FloatToStr of a Double and a Single, as the compiler before it wrote them.
GOLDEN += ftoashort
GOLDEN_A64 += ftoashort
# P482: StrToFloat on the short path and the long, as the compiler before it read them.
GOLDEN += atoffast
GOLDEN_A64 += atoffast
# P483: Format on its short paths and the long, as the compiler before it wrote them.
GOLDEN += fmtfast
GOLDEN_A64 += fmtfast
# P484: Hex by pairs, as the compiler before it wrote it.
GOLDEN += hexfast
GOLDEN_A64 += hexfast
# P485: what the scavenger gives back, and what it keeps.
GOLDEN += scavenge
GOLDEN_A64 += scavenge
# P487: the rwmutex as Go's, and once on its word.
GOLDEN += rwstress oncefast
GOLDEN_A64 += rwstress oncefast
# P486: real expressions in the xmm registers, against the compiler before.
GOLDEN += realregs
GOLDEN_A64 += realregs
# P476: PDF files read, their text, and the same bytes bent.
GOLDEN += pdftext
GOLDEN_A64 += pdftext

# The core units are part of the language: every program links pasmap
# (map[K] of V) and sees pasroutines (mutex, waitgroup, ...) without a
# uses clause. They are compiled by paslangc itself, once per target.
CORE_UNITS := \
	src/lib/pasnum.paslang \
	src/lib/pasobject.paslang \
	src/lib/pasroutines.paslang \
	src/lib/pasmap.paslang \
	src/lib/pashash.paslang \
	src/lib/pastree.paslang \
	src/lib/pasheap.paslang \
	src/lib/pasfmt.paslang \
	src/lib/passtr.paslang \
	src/lib/pasquad.paslang \
	src/lib/pasjson.paslang

# The library units a program reaches with a uses clause. They are not
# part of the language, but they are part of the installation, so a
# project outside this tree (lazlang, for one) can compile against
# them. Order matters: each one only uses the ones before it.
LIB_UNITS := \
	src/lib/paslinux.paslang \
	src/lib/paslib.paslang \
	src/lib/pasnet.paslang \
	src/lib/passignal.paslang \
	src/lib/pasdebug.paslang \
	src/lib/pasrand.paslang \
	src/lib/passort.paslang \
	src/lib/pastime.paslang \
	src/lib/pasx11.paslang \
	src/rtl/sysutils.paslang \
	src/lib/argon2.paslang \
	src/lib/pascipher.paslang \
	src/lib/pasx25519.paslang \
	src/lib/pasnist.paslang \
	src/lib/pasrsa.paslang \
	src/lib/pascodec.paslang \
	src/lib/pasxml.paslang \
	src/lib/pasflate.paslang \
	src/lib/paszip.paslang \
	src/lib/pasxlsx.paslang \
	src/lib/paspdfenc.paslang \
	src/lib/paspdf.paslang \
	src/lib/pasconn.paslang \
	src/lib/pasurl.paslang \
	src/lib/pasx509.paslang \
	src/lib/pastls.paslang \
	src/lib/pastextproto.paslang \
	src/lib/pashttp.paslang \
	src/lib/httpclient.paslang \
	src/lib/pasmime.paslang \
	src/lib/passmtp.paslang \
	src/lib/pasimap.paslang \
	src/lib/httpserver.paslang \
	src/lib/sqlite.paslang

all: $(OUTDIR)/paslangc $(if $(AMD64),core libs) $(if $(ARM64),core-arm64 libs-arm64) $(OUTDIR)/pasdbg

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
	  $(OUTDIR)/paslangc -cpu $(LVL_X64_CPU) -c -Fu $(BUILDDIR) -o $(BUILDDIR)/$(LVL_X64)/$$b $$u; \
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
	@if [ -z '$(AMD64)' ]; then \
	  echo 'the amd64 units are built on an amd64 machine: paslangc assembles them with /usr/bin/as'; \
	  exit 1; \
	fi
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
	  $(OUTDIR)/paslangc -cpu $(LVL_X64_CPU) -c -Fu $(BUILDDIR) -o $(BUILDDIR)/$(LVL_X64)/$$b $$u; \
	done

core-arm64: $(OUTDIR)/paslangc $(CORE_UNITS) | $(BUILDDIR)
	@if [ -z '$(ARM64)' ]; then \
	  echo 'the arm64 units are not built on this amd64 machine: ./configure --enable-arm64 (or make ARM64=yes) builds them'; \
	  exit 1; \
	fi
	@if [ -n '$(AMD64)' ] && { [ ! -x /usr/bin/aarch64-linux-gnu-as ] || [ ! -x /usr/bin/aarch64-linux-gnu-ld ]; }; then \
	  echo 'the arm64 units need /usr/bin/aarch64-linux-gnu-as and /usr/bin/aarch64-linux-gnu-ld (binutils-aarch64-linux-gnu on Debian, aarch64-linux-gnu-binutils on Arch)'; \
	  exit 1; \
	fi
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

compilers: $(OUTDIR)/paslangc core $(OUTDIR)/paslangc-arm64 $(OUTDIR)/paslangc-base

# The amd64 compiler a release carries (P264): built for the base
# processor, so it runs on any amd64 machine, where bin/paslangc is
# built for the one that built it (SELF_CPU). Its units go to their own
# directory; it links the base core units of build/.
$(OUTDIR)/paslangc-base: $(OUTDIR)/paslangc core $(SELF_UNITS) cmd/paslangc/paslangc.paslang | $(OUTDIR) $(BUILDDIR)
	mkdir -p $(BUILDDIR)/ccbase
	@set -e; ulimit -v 2097152; \
	for u in $(SELF_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "base $$b"; \
	  $(OUTDIR)/paslangc -cpu base -c -Fu $(BUILDDIR)/ccbase -o $(BUILDDIR)/ccbase/$$b $$u; \
	done; \
	$(OUTDIR)/paslangc -cpu base -Fu $(BUILDDIR)/ccbase -o $@ cmd/paslangc/paslangc.paslang

$(OUTDIR)/paslangc-arm64: $(OUTDIR)/paslangc core-arm64 $(SELF_UNITS) cmd/paslangc/paslangc.paslang | $(OUTDIR) $(BUILDDIR)
	mkdir -p $(A64DIR)
	@set -e; ulimit -v 2097152; \
	for u in $(SELF_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "arm64 $$b"; \
	  $(OUTDIR)/paslangc -target arm64 -cpu base -c -Fu $(A64DIR) -o $(A64DIR)/$$b $$u; \
	done; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -Fu $(A64DIR) -o $@ cmd/paslangc/paslangc.paslang

$(OUTDIR) $(BUILDDIR):
	mkdir -p $@

# The compiler the boot compiler builds runs that compiler's runtime;
# built again by itself it runs its own, so a fix to the runtime
# (rt_setlength, 1.0.88) is in bin/paslangc, and so in what make check
# tests and make install installs, from its own version on. The boot
# compiler is the installed paslangc or bin/'s when it is BOOT_MIN or
# later, else the one the seed of this machine gives with as and ld
# (bootstrap/seed-<machine>.tar.xz, P262): no other compiler is ever
# needed, on amd64 or on arm64 (Regla 15, as Go builds itself with an
# earlier Go).
$(OUTDIR)/paslangc: $(PASLANG_SRC) $(CORE_UNITS) | $(OUTDIR) $(BUILDDIR)
	@set -e; \
	boot=""; \
	for c in "$(bindir)/paslangc" "$(OUTDIR)/paslangc"; do \
	  if [ -z "$$boot" ] && [ -x "$$c" ]; then \
	    v=$$("$$c" -v 2>/dev/null | grep -o '[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*' | head -1); \
	    if [ -n "$$v" ] && printf '%s\n%s\n' "$(BOOT_MIN)" "$$v" | sort -V -C; then boot="$$c"; \
	    else echo "$$c is $$v, older than $(BOOT_MIN): the seed builds the boot compiler"; fi; \
	  fi; \
	done; \
	if [ -z "$$boot" ]; then \
	  echo "paslangc from the seed $(SEED_DIR)/seed-$(MACHINE).tar.xz with as and ld"; \
	  rm -rf "$(BUILDDIR)/seed"; \
	  python3 scripts/bootstrap_seed.py build --seed "$(SEED_DIR)/seed-$(MACHINE).tar.xz" --out "$(BUILDDIR)/seed"; \
	  boot="$(BUILDDIR)/seed/paslangc"; \
	fi; \
	echo "stage paslangc via $$boot"; \
	absboot=$$(readlink -f "$$boot"); \
	abstarget=""; \
	if [ -x "$(OUTDIR)/paslangc" ]; then abstarget=$$(readlink -f "$(OUTDIR)/paslangc"); fi; \
	if [ -n "$$abstarget" ] && [ "$$absboot" = "$$abstarget" ]; then \
	  cp "$(OUTDIR)/paslangc" "$(BUILDDIR)/paslangc.prev"; \
	  boot="$(BUILDDIR)/paslangc.prev"; \
	fi; \
	$(MAKE) stage HOST="$$boot" STAGE="$(OUTDIR)/paslangc"; \
	echo "paslangc by itself, for $(SELF_CPU)"; \
	$(MAKE) stage HOST="$(OUTDIR)/paslangc" STAGE="$(BUILDDIR)/paslangc.self" STAGECPU="$(SELF_CPU)"; \
	mv "$(BUILDDIR)/paslangc.self" "$(OUTDIR)/paslangc"

# The seeds of the bootstrap (P262): the assembly bin/paslangc writes for
# itself, every unit and the program for -cpu base, for amd64 and for
# arm64, with the link line, packed by scripts/bootstrap_seed.py into
# bootstrap/. Written again when BOOT_MIN moves past the seeds' version.
bootstrap-seed: $(OUTDIR)/paslangc
	python3 scripts/bootstrap_seed.py make --compiler "$(OUTDIR)/paslangc" --arch amd64 \
	  --out "$(SEED_DIR)/seed-amd64.tar.xz" -- $(CORE_UNITS) $(SELF_UNITS) cmd/paslangc/paslangc.paslang
	python3 scripts/bootstrap_seed.py make --compiler "$(OUTDIR)/paslangc" --arch arm64 \
	  --out "$(SEED_DIR)/seed-arm64.tar.xz" -- $(CORE_UNITS) $(SELF_UNITS) cmd/paslangc/paslangc.paslang

# The compiler reproduces itself: bin/paslangc builds the compiler into
# self2, that compiler builds it again into self3, and the assembly of
# every unit must be the same both times; then both compilers compile
# every golden test for both machines and must write the same assembly. A code generator that
# miscompiles the compiler shows here, on the biggest program there is,
# and not only on hello (1.0.40 passed every test and still miscompiled
# SetLength in the parser, P94).
self: $(OUTDIR)/paslangc $(OUTDIR)/paslangc-base core | $(BUILDDIR)
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
	: the same two stages for the processor bin/paslangc is built for, P264; \
	N2=$(BUILDDIR)/self2n; N3=$(BUILDDIR)/self3n; \
	rm -rf $$N2 $$N3; mkdir -p $$N2 $$N3; \
	for u in $(SELF_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "self2 $(SELF_CPU) $$b"; \
	  $(OUTDIR)/paslangc -cpu $(SELF_CPU) -c -Fu $$N2 -o $$N2/$$b $$u; \
	done; \
	$(OUTDIR)/paslangc -cpu $(SELF_CPU) -Fu $$N2 -o $$N2/paslangc cmd/paslangc/paslangc.paslang; \
	for u in $(SELF_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "self3 $(SELF_CPU) $$b"; \
	  $$N2/paslangc -cpu $(SELF_CPU) -c -Fu $$N3 -o $$N3/$$b $$u; \
	done; \
	$$N2/paslangc -cpu $(SELF_CPU) -Fu $$N3 -o $$N3/paslangc cmd/paslangc/paslangc.paslang; \
	for u in $(SELF_UNITS) cmd/paslangc/paslangc.paslang; do \
	  b=$$(basename $$u .paslang); \
	  cmp $$N2/$$b.s $$N3/$$b.s; \
	done; \
	$$N3/paslangc -o $(BUILDDIR)/hello-n3 testdata/hello.paslang; \
	$(BUILDDIR)/hello-n3; \
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
	: the compiler a release carries, P264: built for base it writes what S2 writes, and on amd64 it has no instruction past SSE2; \
	B=$(BUILDDIR)/selfb; rm -rf $$B; mkdir -p $$B; \
	for u in $(SELF_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  $(OUTDIR)/paslangc-base -cpu base -c -Fu $$B -o $$B/$$b $$u; \
	  cmp $$S2/$$b.s $$B/$$b.s; \
	done; \
	if [ -n "$(AMD64)" ]; then \
	  python3 -I scripts/check_cpubin.py base $(OUTDIR)/paslangc-base; \
	  if [ "$(SELF_CPU)" = native ]; then python3 -I scripts/check_cpubin.py native $(OUTDIR)/paslangc; fi; \
	fi; \
	echo ok self

HOST ?= $(bindir)/paslangc
STAGE ?= $(BUILDDIR)/paslangc-stage
# The processor a stage builds the compiler, its units and the core
# units it links for: STAGECPU when the caller gives it (the last stage,
# SELF_CPU: P264), else the base processor, which every host takes. A
# host older than 1.0.144 does not know -cpu, so the flag is passed only
# when its help names it.
STAGECPU ?=
HOSTCPU = $$(if $(HOST) --help flags 2>/dev/null | grep -q '^-cpu'; then echo -cpu base; fi)
STAGECPUFLAG = $(if $(STAGECPU),-cpu $(STAGECPU),$(HOSTCPU))
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
	@v=$$("$(HOST)" -v 2>/dev/null | grep -o '[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*' | head -1); \
	if [ -z "$$v" ] || ! printf '%s\n%s\n' "$(BOOT_MIN)" "$$v" | sort -V -C; then \
	  echo "stage: $(HOST) is $${v:-of no version}, older than BOOT_MIN $(BOOT_MIN): it cannot build these sources"; \
	  exit 1; \
	fi
	@set -e; ulimit -v 2097152; \
	: a clean directory each time, 1.1.2: a .pi another compiler wrote there, of another format, was read before this host rewrote it; \
	rm -rf $(STAGE_DIR); \
	mkdir -p $(STAGE_DIR) $(STAGE_DIR)/core; \
	for u in $(CORE_UNITS) $(SELF_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "stage $$b"; \
	  $(HOST) $(STAGECPUFLAG) -c -Fu $(STAGE_DIR) -o $(STAGE_DIR)/$$b $$u; \
	done; \
	echo "stage paslangc"; \
	$(HOST) $(STAGECPUFLAG) -Fu $(STAGE_DIR) -o $(STAGE) cmd/paslangc/paslangc.paslang; \
	for u in $(CORE_UNITS); do \
	  b=$$(basename $$u .paslang); \
	  echo "stage core $$b"; \
	  $(STAGE) -cpu base -c -Fu $(STAGE_DIR)/core -o $(STAGE_DIR)/core/$$b $$u; \
	done; \
	$(STAGE) -Fu $(STAGE_DIR)/core -o $(BUILDDIR)/stage-hello testdata/hello.paslang; \
	$(BUILDDIR)/stage-hello; \
	echo ok stage

self-arm64: $(OUTDIR)/paslangc-arm64 $(BUILDDIR)/qemu-aarch64 | $(BUILDDIR)
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

hello: $(OUTDIR)/paslangc $(if $(AMD64),core,core-arm64) testdata/hello.paslang | $(BUILDDIR)
	$(OUTDIR)/paslangc -o $(OUTDIR)/hello testdata/hello.paslang
	$(OUTDIR)/hello

# P89: paslang against Go (scripts/bench/run.py): every pair built with
# this tree's compiler for -cpu native and -cpu base and with go, seven
# alternating rounds, time and memory against the budgets in run.py (all
# below 1.00 since P223; exit 1 when one passes it or an output differs),
# then the robustness probes; then paslangc against go build on one
# generated program (scripts/bench/build.py, P223). Both run, and the
# target fails if either does. Go is not a dependency of the compiler:
# make check does not run this.
bench: $(OUTDIR)/paslangc core libs
	@mkdir -p $(BUILDDIR)/bench; rc=0; \
	PATH="$(abspath $(OUTDIR)):$$PATH" python3 scripts/bench/run.py -n 7 --json $(BUILDDIR)/bench/last.json || rc=1; \
	PATH="$(abspath $(OUTDIR)):$$PATH" python3 scripts/bench/build.py -n 8 --json $(BUILDDIR)/bench/build.json || rc=1; \
	exit $$rc

# The debugger's terminal (P118): pasdbg <socket> speaks to a program
# compiled with -debug and run with PASLANG_DEBUG=<socket>.
$(OUTDIR)/pasdbg: $(OUTDIR)/paslangc $(if $(AMD64),libs,libs-arm64) cmd/pasdbg/pasdbg.paslang
	$(OUTDIR)/paslangc -cpu base -Fu $(if $(AMD64),$(BUILDDIR),$(A64DIR)) -o $(OUTDIR)/pasdbg cmd/pasdbg/pasdbg.paslang

# The three servers against their Go twins (P115): scripts/bench/servers.py.
# The pairs again in alternating rounds (scripts/bench/rounds.py), the
# median of each round's ratio: steadier than a median of runs on a
# machine that runs anything else. After make bench, which builds them.
bench-rounds:
	python3 scripts/bench/rounds.py -n 40 --json $(BUILDDIR)/bench/rounds.json

# JSON's stages one at a time, GB/s and the time stamp counter's ticks a
# byte, for this processor and the base one (P211): scripts/bench/k12json.
bench-stages: $(OUTDIR)/paslangc core libs
	@mkdir -p $(BUILDDIR)/bench
	PATH="$(abspath $(OUTDIR)):$$PATH" python3 scripts/bench/run.py stages

bench-servers: $(OUTDIR)/paslangc core libs
	PATH=$(OUTDIR):$$PATH python3 scripts/bench/servers.py -n 3 --json $(BUILDDIR)/bench/servers.json

check: $(OUTDIR)/paslangc core core-arm64 libs libs-arm64 $(BUILDDIR)/qemu-aarch64
	@python3 scripts/check_recipes.py
	@python3 scripts/check_debug_growth.py "$(OUTDIR)/paslangc" "$(BUILDDIR)" $(QEMU_A64)
	@sh scripts/check_bootstrap.sh "$(BUILDDIR)" $(QEMU_A64) $(CORE_UNITS)
	@sh scripts/check_cpufeat.sh "$(OUTDIR)/paslangc" "$(BUILDDIR)" $(QEMU_A64)
	@set -e; \
	xrun=""; \
	: each run its own X server on a display it picks and writes, -displayfd, so two runs keep apart, P156; \
	if command -v Xvfb > /dev/null 2>&1; then \
	  rm -f $(BUILDDIR)/xvfb.display; \
	  Xvfb -displayfd 3 -screen 0 1024x768x24 -ac 3> $(BUILDDIR)/xvfb.display > /dev/null 2>&1 & \
	  echo $$! > $(BUILDDIR)/xvfb.pid; \
	  for i in 1 2 3 4 5 6 7 8 9 10; do [ -s $(BUILDDIR)/xvfb.display ] && break; sleep 1; done; \
	  xrun="env DISPLAY=:$$(cat $(BUILDDIR)/xvfb.display)"; \
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
	  timeout 300 $(BUILDDIR)/$$t > $(BUILDDIR)/$$t.got; \
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
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/jsonbind10 testdata/jsonbind1.paslang; \
	$(BUILDDIR)/jsonbind10 > $(BUILDDIR)/jsonbind10.got; \
	diff -u testdata/jsonbind1.out $(BUILDDIR)/jsonbind10.got; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/jsonbind20 testdata/jsonbind2.paslang; \
	$(BUILDDIR)/jsonbind20 > $(BUILDDIR)/jsonbind20.got; \
	diff -u testdata/jsonbind2.out $(BUILDDIR)/jsonbind20.got; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/jsonlang0 testdata/jsonlang.paslang; \
	$(BUILDDIR)/jsonlang0 > $(BUILDDIR)/jsonlang0.got; \
	diff -u testdata/jsonlang.out $(BUILDDIR)/jsonlang0.got; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/inlinevar0 testdata/inlinevar.paslang; \
	$(BUILDDIR)/inlinevar0 > $(BUILDDIR)/inlinevar0.got; \
	diff -u testdata/inlinevar.out $(BUILDDIR)/inlinevar0.got; \
	: a var or out parameter of a record goes in place P275, and a place found through a variable another var parameter is given stays a call; \
	for f in step sum wipe tag shift inner; do \
	  if grep -q "call p_$$f$$" $(BUILDDIR)/inlinevar.s; then echo "inlinevar.s still calls $$f, which should be in place"; exit 1; fi; \
	done; \
	for f in bump bumppos repoint; do \
	  grep -q "call p_$$f$$" $(BUILDDIR)/inlinevar.s || { echo "inlinevar.s does not call $$f, which should stay a call"; exit 1; }; \
	done; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/trygetshare0 testdata/trygetshare.paslang; \
	$(BUILDDIR)/trygetshare0 > $(BUILDDIR)/trygetshare0.got; \
	diff -u testdata/trygetshare.out $(BUILDDIR)/trygetshare0.got; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/treevarg0 testdata/treevarg.paslang; \
	$(BUILDDIR)/treevarg0 > $(BUILDDIR)/treevarg0.got; \
	diff -u testdata/treevarg.out $(BUILDDIR)/treevarg0.got; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/resultmark0 testdata/resultmark.paslang; \
	$(BUILDDIR)/resultmark0 > $(BUILDDIR)/resultmark0.got; \
	diff -u testdata/resultmark.out $(BUILDDIR)/resultmark0.got; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/strappend0 testdata/strappend.paslang; \
	$(BUILDDIR)/strappend0 > $(BUILDDIR)/strappend0.got; \
	diff -u testdata/strappend.out $(BUILDDIR)/strappend0.got; \
	grep -q 'call rt_strappendc$$' $(BUILDDIR)/strappend.s || { echo "strappend.s does not append a character through rt_strappendc"; exit 1; }; \
	grep -q 'call rt_strappend$$' $(BUILDDIR)/strappend.s || { echo "strappend.s does not append a string through rt_strappend"; exit 1; }; \
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
	grep -qx '.section pasgcroots.v_pl,"awo",@progbits,v_pl' $(BUILDDIR)/gctypes.s; \
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
	: the same input nonblocking, as a shell may hand it over: ReadLn parks on the poller, P217; \
	(sleep 0.05; head -c 3000 testdata/readlines.in; sleep 0.05; tail -c +3001 testdata/readlines.in) | python3 scripts/nonblocking.py $(BUILDDIR)/readlines > $(BUILDDIR)/readlines.got; \
	diff -u testdata/readlines.out $(BUILDDIR)/readlines.got; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/spurwake testdata/spurwake.paslang; \
	(sleep 0.2; printf 'x\n'; head -c 100000 /dev/zero | tr '\0' y) | timeout 20 $(BUILDDIR)/spurwake > $(BUILDDIR)/spurwake.got; \
	diff -u testdata/spurwake.out $(BUILDDIR)/spurwake.got; \
	(sleep 0.2; printf 'x\n'; head -c 100000 /dev/zero | tr '\0' y) | timeout 20 python3 scripts/nonblocking.py $(BUILDDIR)/spurwake > $(BUILDDIR)/spurwake.got; \
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
	for t in heapspan map2 sync2 strs mapsplit closurebox tree1 tree2 hash1 store1 mapseed strview ioretry stdlocks strshrink json1 jsonshare jsonstream jsonpark; do \
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
	for t in vectors vecmore vecpool bitwords xxh3 inlineasm hash1 tree1 store1 mapsplit set256 strwords strkern strcmpk cmpwords sysutils1 utf8kern jsonkern longslice rtlong fillkern json1 jsoncanon hmacstream hashpieces hashpieces2 cipherkat cipherwyche x25519kat nistwyche rsawyche; do \
	  $(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/$$t-base testdata/$$t.paslang; \
	  $(BUILDDIR)/$$t-base > $(BUILDDIR)/$$t.bgot; \
	  diff -u testdata/$$t.out $(BUILDDIR)/$$t.bgot; \
	  PASLANG_CPU=base $(BUILDDIR)/$$t-base > $(BUILDDIR)/$$t.bgot; \
	  diff -u testdata/$$t.out $(BUILDDIR)/$$t.bgot; \
	done; \
	grep -q 'p_pashash_passha256cpu' $(BUILDDIR)/hash1.s; \
	grep -q 'p_pashash_passha256base' $(BUILDDIR)/hash1-base.s; \
	grep -q 'p_pashash_passha256updatecpu' $(BUILDDIR)/hashpieces.s; \
	grep -q 'p_pashash_passha256updatebase' $(BUILDDIR)/hashpieces-base.s; \
	if grep -q 'p_pashash_passha256updatecpu' $(BUILDDIR)/hashpieces-base.s; then echo "hashpieces-base.s calls the SHA-NI body"; exit 1; fi; \
	: the HMAC in pieces calls the Cpu or the Base body of its hash by the processor, P443; \
	grep -q 'p_pashash_pashmacupdatecpu' $(BUILDDIR)/hashpieces2.s; \
	grep -q 'p_pashash_pashmacupdatebase' $(BUILDDIR)/hashpieces2-base.s; \
	if grep -q 'p_pashash_pashmacupdatecpu' $(BUILDDIR)/hashpieces2-base.s; then echo "hashpieces2-base.s calls the SHA-NI body"; exit 1; fi; \
	if grep -q 'p_pashash_passha256cpu' $(BUILDDIR)/hash1-base.s; then echo "hash1-base.s calls the SHA-NI body"; exit 1; fi; \
	if grep -q 'popcntq' $(BUILDDIR)/bitwords-base.s; then echo "bitwords-base.s carries popcnt"; exit 1; fi; \
	: pastls against Go crypto/tls and openssl s_server, each case a server on 127.0.0.1, P431; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/tlsinterop testdata/tlsinterop.paslang; \
	: the manual shows the program that sets a TTlsConfig and make check runs it against Go, P473; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/tlsdoc testdata/tlsdoc.paslang; \
	python3 scripts/check_tlsdoc.py docs/MANUAL.md testdata/tlsdoc.paslang; \
	if command -v go > /dev/null 2>&1; then \
	  (cd scripts/tlsoracle && GOCACHE=$(abspath $(BUILDDIR))/gocache GOFLAGS=-mod=mod go build -o $(abspath $(BUILDDIR))/tlsoracle .); \
	  sh scripts/tls_interop.sh go $(BUILDDIR)/tlsoracle $(BUILDDIR)/tlsinterop '' $(BUILDDIR)/tlsdoc > $(BUILDDIR)/tlsinterop-go.got; \
	  diff -u testdata/tlsinterop-go.out $(BUILDDIR)/tlsinterop-go.got; \
	fi; \
	if command -v openssl > /dev/null 2>&1; then \
	  sh scripts/tls_interop.sh openssl - $(BUILDDIR)/tlsinterop > $(BUILDDIR)/tlsinterop-openssl.got; \
	  diff -u testdata/tlsinterop-openssl.out $(BUILDDIR)/tlsinterop-openssl.got; \
	fi; \
	: the system roots pasx509 loads are those Go loads, in the same order, P430; \
	if command -v go > /dev/null 2>&1; then \
	  (cd scripts/x509oracle && GOCACHE=$(abspath $(BUILDDIR))/gocache GOFLAGS=-mod=mod go build -o $(abspath $(BUILDDIR))/x509roots-go ./rootcheck); \
	  $(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/x509roots testdata/x509roots.paslang; \
	  $(BUILDDIR)/x509roots-go > $(BUILDDIR)/x509roots.want; \
	  $(BUILDDIR)/x509roots > $(BUILDDIR)/x509roots.got; \
	  diff -u $(BUILDDIR)/x509roots.want $(BUILDDIR)/x509roots.got; \
	fi; \
	: pascipher compiled for this processor seals through AES-NI and PCLMULQDQ, its base build through neither, P428; \
	mkdir -p $(BUILDDIR)/cipherk; \
	$(OUTDIR)/paslangc -c -Fu $(BUILDDIR) -o $(BUILDDIR)/cipherk/pascipher src/lib/pascipher.paslang; \
	grep -q 'aesenc %xmm1, %xmm0' $(BUILDDIR)/cipherk/pascipher.s; \
	grep -q 'pclmulqdq' $(BUILDDIR)/cipherk/pascipher.s; \
	if grep -q 'aesenc %xmm\|pclmulqdq' $(BUILDDIR)/pascipher.s; then echo "pascipher's base build carries AES-NI"; exit 1; fi; \
	for t in cipherkat cipherwyche; do \
	  $(OUTDIR)/paslangc -Fu $(BUILDDIR)/cipherk -Fu $(BUILDDIR) -o $(BUILDDIR)/$$t-k testdata/$$t.paslang; \
	  $(BUILDDIR)/$$t-k > $(BUILDDIR)/$$t.kgot; \
	  diff -u testdata/$$t.out $(BUILDDIR)/$$t.kgot; \
	done; \
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
	: a program for the base processor links no instruction past it, P268: inlineasm writes AVX2 itself and strkern calls the AVX2 kernels to test them; \
	for t in vectors vecmore vecpool bitwords xxh3 hash1 tree1 store1 mapsplit set256 strwords strcmpk cmpwords sysutils1 utf8kern jsonkern longslice rtlong fillkern json1 jsoncanon hmacstream cipherkat cipherwyche x25519kat nistwyche rsawyche; do \
	  python3 -I scripts/check_cpubin.py base $(BUILDDIR)/$$t-base > /dev/null || { python3 -I scripts/check_cpubin.py base $(BUILDDIR)/$$t-base; exit 1; }; \
	done; \
	: the UTF-8 kernels against the strict decoder of Python, P201: the expected output is the model output; \
	python3 -I scripts/utf8kern_model.py testdata/utf8kern.paslang | diff -u testdata/utf8kern.out -; \
	: every front of a kernel against Python across the edges of its slices of 64 KiB, P270; \
	python3 -I scripts/longslice_model.py testdata/longslice.paslang | diff -u testdata/longslice.out -; \
	: the copies, clears, comparisons and hashes of the runtime across the edges of their pieces, the hashes against xxhsum when it is there, P271; \
	if command -v xxhsum > /dev/null; then python3 -I scripts/rtlong_model.py testdata/rtlong.paslang | diff -u testdata/rtlong.out -; fi; \
	: pashash is what scripts/hashgen.py writes from its template, P270; \
	python3 -I scripts/hashgen.py --check; \
	: paspdfenc is what scripts/gen_pdfenc.py writes and testdata/pdftext.txt what scripts/gen_pdf_tests.py writes, P476; \
	python3 -I scripts/gen_pdfenc.py --check; \
	python3 -I scripts/gen_pdf_tests.py --check; \
	grep -q 'call p_passtr_pasfindbytecpu$$' $(BUILDDIR)/longslice.s || { echo "longslice.s does not call the AVX2 front of IndexByte"; exit 1; }; \
	grep -q 'call p_passtr_pascomparebytecpu$$' $(BUILDDIR)/longslice.s || { echo "longslice.s does not call the AVX2 front of CompareByte"; exit 1; }; \
	grep -q 'call p_passtr_pasfindbytebase$$' $(BUILDDIR)/longslice-base.s || { echo "longslice-base.s does not call the base front of IndexByte"; exit 1; }; \
	if grep -q 'call p_passtr_pas[a-z]*cpu$$' $(BUILDDIR)/longslice-base.s; then echo "longslice-base.s calls an AVX2 front"; exit 1; fi; \
	grep -q 'call p_passtr_pasutf8blockscpu$$' $(BUILDDIR)/$(LVL_X64)/passtr.s || { echo "passtr's v3 build does not call the AVX2 UTF-8 kernel"; exit 1; }; \
	if grep -q 'call p_passtr_pasutf8blockscpu$$' $(BUILDDIR)/passtr.s; then echo "passtr's base build calls the AVX2 UTF-8 kernel"; exit 1; fi; \
	: the scans of JSON against their definitions, P202: the expected output is the model output, the v3 build calls the AVX2 kernels and the base build the SSE2 ones; \
	python3 -I scripts/jsonkern_model.py testdata/jsonkern.paslang | diff -u testdata/jsonkern.out -; \
	for k in pasjsonindex pasjsonescindex; do \
	  grep -q "call p_pasjson_$${k}cpu$$" $(BUILDDIR)/$(LVL_X64)/pasjson.s || { echo "pasjson's v3 build does not call $${k}cpu"; exit 1; }; \
	  grep -q "call p_pasjson_$${k}base$$" $(BUILDDIR)/pasjson.s || { echo "pasjson's base build does not call $${k}base"; exit 1; }; \
	  if grep -q "call p_pasjson_$${k}cpu$$" $(BUILDDIR)/pasjson.s; then echo "pasjson's base build calls $${k}cpu"; exit 1; fi; \
	done; \
	echo ok cpu-base; \
	echo "==== the json type (P203) ===="; \
	: the parser and the writer held to the encoding json v2 of Go when Go is there and to expect.txt always, the index and a byte at a time alike on every document, for this processor and the base one; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/jsoncheck testdata/jsoncheck.paslang; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/jsoncheck-base testdata/jsoncheck.paslang; \
	if command -v go > /dev/null; then \
	  (cd testdata/json && GOEXPERIMENT=jsonv2 go build -o $(abspath $(BUILDDIR))/json-oracle oracle.go); \
	  python3 -I scripts/check_json.py $(BUILDDIR)/jsoncheck $(BUILDDIR)/json-oracle; \
	else \
	  python3 -I scripts/check_json.py $(BUILDDIR)/jsoncheck -; \
	fi; \
	python3 -I scripts/check_json.py $(BUILDDIR)/jsoncheck-base -; \
	: every document of the suite, the corpus and the cases as a json constant, taken or refused at its byte as JsonParse does, P209; \
	python3 -I scripts/check_jsonconst.py $(OUTDIR)/paslangc $(BUILDDIR); \
	: typed JSON held to the Go v2 of the model, schema by schema P205; \
	python3 -I scripts/jsonmodel.py $(OUTDIR)/paslangc $(BUILDDIR) $(QEMU_A64); \
	: what the compiler refuses of a json, each with its message; \
	for f in 'fromstr:string does not go into json: JsonParse reads JSON text at 10:8' \
	  'toint:a json does not go into Integer: j.AsString, j.AsInteger and the other members read its value at 10:8' \
	  'tostr:a json does not go into string' \
	  'intcast:a json is no number: j.AsInteger reads one at 10:8' \
	  'boolcast:a json is no Boolean: j.AsBoolean reads one, j.IsNull says null at 10:16' \
	  'ptrcast:a json becomes Pointer through its members' \
	  'lessthan:json values compare with = and <> only at 10:8' \
	  'plus:+ does not take a json: its members read its value at 10:8' \
	  'strarith:+ does not take a json' \
	  'realidx:a json is indexed by a name, a string, or a place, an Integer, not Real at 10:10' \
	  'downto:for x in a json walks it forward: downto does not at 10:3' \
	  'forreal:for in a json decodes each value into a variable of a type with a JSON form, and Pointer has none at 10:3' \
	  "kvbad:for k, v in a json: k is a string, an object's names, or an Integer, an array's places, not Boolean at 10:3" \
	  'nottest:a json does not go into Boolean' \
	  'inint:in a json looks for a member' \
	  'ifjson:a json is no condition: j.AsBoolean reads one, j.IsNull says null at 10:6' \
	  'tryreal:TryGet of a json takes a name, a string, or a place, an Integer at 10:8' \
	  'mapkey:a json is no map key' \
	  'treej:a json is no tree key' \
	  'heapj:a json is no heap element: json values have no order, = and <> only; a heap of its text, JsonEncode(j, JsonCanonical), has one at 3:14' \
	  'bindname2:a json name names one member, and this declaration gives 2 at 4:19' \
	  'bindopt:bogus is no json option: omitzero, omitempty, quoted, required, ignore, unknown, embed or rfc3339 at 4:21' \
	  'bindquoted:json quoted writes a number inside a string, and string is no number at 4:15' \
	  'bindignore:json ignore leaves the member out and takes nothing else at 4:16' \
	  'bindunknown:json unknown takes a json, which keeps the members no other takes, not Integer at 4:16' \
	  'bindembed:json embed takes a record or a pointer to one, not Integer at 4:16' \
	  'bindrfc:json rfc3339 takes a TDateTime, a Double, not Integer at 4:16' \
	  'bindtwice:json omitzero twice at 4:30' \
	  "bindempty:a json name is not empty: leave the name out for the member's own at 4:16" \
	  "binddup:two members of TR are 'x' in JSON: json 'name' gives one another, json ignore leaves one out at 5:5" \
	  "bindbare:json after a member's type takes its name, a string, or its options at 4:16" \
	  'bindvariant:a member of a variant part takes json ignore alone: json writes no variant at 5:22' \
	  "bindvarenc:TR.A is in a variant part and has no JSON form: json ignore on each of the part's fields leaves it out at 10:11" \
	  'bindchan:TR.C has no JSON form (a channel): json ignore leaves it out at 9:11' \
	  'bindptr:JsonEncode takes a value with a JSON form, and Pointer has none at 5:11' \
	  'bindclassvar:a class variable is no member of an object: json writes none at 5:15' \
	  'bindrecprop:a record is its fields in JSON, not its properties: json goes after a field at 7:33' \
	  'bindwprop:TC.A is read by no accessor, or by an index: json writes no such property at 12:11' \
	  'bindutf8:a json name is UTF-8 with no noncharacter (RFC 7493 2.1) at 4:16' \
	  'jsonofargs:JsonOf takes a value at 5:11' \
	  'jsonvar:json is a reserved word, not a name at 3:3' \
	  'corename:JsonParse is a reserved word, not a name at 3:3' \
	  'decabstract:JsonDecode makes a TA with its Create, and TA is abstract at 9:3' \
	  'decctor:JsonDecode makes a TA with Create, and TA.Create takes arguments at 14:3' \
	  'decnotvar:JsonDecode(s, x): x needs a variable at 7:3' \
	  'decform:JsonDecode takes a variable of a type with a JSON form, and Pointer has none at 5:3' \
	  'decsrc:JsonDecode reads JSON text, a string, or a json, not Integer at 5:14' \
	  'decargs:JsonDecode takes the text or a json, a variable and the options if any at 5:3' \
	  'tryargs:TryJsonDecode takes the text or a json, a variable, the error and the options if any at 5:6' \
	  'tryerr:TryJsonDecode(s, x, err): err is Integer, not EJsonError at 5:28' \
	  'trygetform:TryGet of a json takes a v of a type with a JSON form, and Pointer has none at 6:21' \
	  'decchan:TR.C has no JSON form (a channel): json ignore leaves it out at 10:3' \
	  'decvar:JsonDecode is a reserved word, not a name at 3:3'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/jb_$$n testdata/jsonbad/$$n.paslang >$(BUILDDIR)/jb_$$n.err 2>&1; then \
	    echo "jsonbad/$$n should fail"; exit 1; \
	  fi; \
	  grep -qF -e "$$w" $(BUILDDIR)/jb_$$n.err || { cat $(BUILDDIR)/jb_$$n.err; exit 1; }; \
	done; \
	echo ok json; \
	echo "==== the benchmark programs compile (P197) ===="; \
	mkdir -p $(BUILDDIR)/benchcheck; \
	for f in scripts/bench/*.paslang; do \
	  $(OUTDIR)/paslangc -o $(BUILDDIR)/benchcheck/$$(basename $$f .paslang) $$f; \
	done; \
	rm -rf $(BUILDDIR)/benchcheck; \
	echo ok bench programs; \
	echo "==== parallel mark ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/parmark testdata/parmark.paslang; \
	for w in "" "" "" PASLANG_GCWORKERS=1 PASLANG_GCWORKERS=2 PASLANG_GCWORKERS=0 "PASLANG_GCVERIFY=1 PASLANG_GCPOISON=1" "PASLANG_GCSTRESS=50 PASLANG_GCPOISON=1"; do \
	  env $$w timeout 300 $(BUILDDIR)/parmark > $(BUILDDIR)/parmark.got; \
	  diff -u testdata/parmark.out $(BUILDDIR)/parmark.got; \
	done; \
	echo ok parmark; \
	: with a cap on the workers every M a cycle may mark with marks, the poller and Ms with no thread no pick, P337; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/gcwake testdata/gcwake.paslang; \
	for w in PASLANG_GCWORKERS=2 PASLANG_GCWORKERS=4; do \
	  env $$w timeout 300 $(BUILDDIR)/gcwake > $(BUILDDIR)/gcwake.got; \
	  diff -u testdata/gcwake.out $(BUILDDIR)/gcwake.got; \
	done; \
	echo ok gcwake; \
	echo "==== lazy Ms ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/lazym testdata/lazym.paslang; \
	for w in "" "" PASLANG_GCWORKERS=1 PASLANG_GCWORKERS=0; do \
	  env $$w timeout 120 $(BUILDDIR)/lazym > $(BUILDDIR)/lazym.got; \
	  diff -u testdata/lazym.out $(BUILDDIR)/lazym.got; \
	done; \
	echo ok lazym; \
	echo "==== idle mark workers (P219) ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/markidle testdata/markidle.paslang; \
	for w in "" PASLANG_GC=off PASLANG_GCWORKERS=1 PASLANG_GCWORKERS=0; do \
	  env $$w timeout 120 $(BUILDDIR)/markidle > $(BUILDDIR)/markidle.got; \
	  diff -u testdata/markidle.out $(BUILDDIR)/markidle.got; \
	done; \
	taskset -c 0 timeout 120 $(BUILDDIR)/markidle > $(BUILDDIR)/markidle.got; \
	diff -u testdata/markidle.out $(BUILDDIR)/markidle.got; \
	echo ok markidle; \
	echo "==== a kernel's calls give way (P269) ===="; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/utf8slice testdata/utf8slice.paslang; \
	taskset -c 0 timeout 120 $(BUILDDIR)/utf8slice > $(BUILDDIR)/utf8slice.got; \
	diff -u testdata/utf8slice.out $(BUILDDIR)/utf8slice.got; \
	echo ok utf8slice; \
	echo "==== the core units' kernels give way (P270) ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/kernslice testdata/kernslice.paslang; \
	taskset -c 0 timeout 300 $(BUILDDIR)/kernslice all > $(BUILDDIR)/kernslice.got; \
	diff -u testdata/kernslice.out $(BUILDDIR)/kernslice.got; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/kernslice-base testdata/kernslice.paslang; \
	taskset -c 0 timeout 300 $(BUILDDIR)/kernslice-base str > $(BUILDDIR)/kernslice.bgot; \
	head -n 7 testdata/kernslice.out | diff -u - $(BUILDDIR)/kernslice.bgot; \
	echo ok kernslice; \
	echo "==== the runtime's copies, clears, comparisons and hashes give way (P271) ===="; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/rtslice testdata/rtslice.paslang; \
	PASLANG_GC=20000 taskset -c 0 timeout 300 $(BUILDDIR)/rtslice > $(BUILDDIR)/rtslice.got; \
	diff -u testdata/rtslice.out $(BUILDDIR)/rtslice.got; \
	PASLANG_GC=20000 PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=50 PASLANG_GCPOISON=1 taskset -c 0 timeout 600 $(BUILDDIR)/rtslice > $(BUILDDIR)/rtslice.vgot; \
	diff -u testdata/rtslice.out $(BUILDDIR)/rtslice.vgot; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/rtslice-base testdata/rtslice.paslang; \
	PASLANG_GC=20000 taskset -c 0 timeout 300 $(BUILDDIR)/rtslice-base > $(BUILDDIR)/rtslice.bgot; \
	diff -u testdata/rtslice.out $(BUILDDIR)/rtslice.bgot; \
	echo ok rtslice; \
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
	: a leaf keeps its parameters in the registers they came in, and the debugger reads them there, P288; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/leafgdb testdata/leafcall.paslang; \
	gdb -batch -nx -ex 'set debuginfod enabled off' -ex 'break leafcall.paslang:66' \
	  -ex 'run > /dev/null' -ex 'print A' -ex 'print B' -ex 'print C' -ex kill \
	  $(BUILDDIR)/leafgdb > $(BUILDDIR)/leafgdb.gdb 2>&1; \
	grep -q '^.1 = 2$$' $(BUILDDIR)/leafgdb.gdb; \
	grep -q '^.2 = 3$$' $(BUILDDIR)/leafgdb.gdb; \
	grep -q '^.3 = 4$$' $(BUILDDIR)/leafgdb.gdb; \
	: a routine with no frame keeps its parameters and locals in registers, and the debugger reads them there, P296; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/flatgdb testdata/flatproc.paslang; \
	gdb -batch -nx -ex 'set debuginfod enabled off' -ex 'break flatproc.paslang:32' \
	  -ex 'run > /dev/null' -ex 'print X' -ex 'print Lo' -ex 'print Hi' -ex 'print r' -ex kill \
	  $(BUILDDIR)/flatgdb > $(BUILDDIR)/flatgdb.gdb 2>&1; \
	grep -q '^.1 = 5$$' $(BUILDDIR)/flatgdb.gdb; \
	grep -q '^.2 = 1$$' $(BUILDDIR)/flatgdb.gdb; \
	grep -q '^.3 = 9$$' $(BUILDDIR)/flatgdb.gdb; \
	grep -q '^.4 = 5$$' $(BUILDDIR)/flatgdb.gdb; \
	: a nested routine with no frame keeps its own variables in registers, and the debugger reads them there, P334; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/nestflatgdb testdata/nestflat.paslang; \
	gdb -batch -nx -ex 'set debuginfod enabled off' -ex 'break nestflat.paslang:50' \
	  -ex 'run > /dev/null' -ex 'print A' -ex 'print B' -ex 'print m' -ex kill \
	  $(BUILDDIR)/nestflatgdb > $(BUILDDIR)/nestflatgdb.gdb 2>&1; \
	grep -q '^.1 = 4$$' $(BUILDDIR)/nestflatgdb.gdb; \
	grep -q '^.2 = 5$$' $(BUILDDIR)/nestflatgdb.gdb; \
	grep -q '^.3 = 4$$' $(BUILDDIR)/nestflatgdb.gdb; \
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
	: blockrd, the line comes once main has written 1 or after 20 s, so R waits in ReadLn while main runs whatever the load, where a line 0.2 s late came after main under the chain once; \
	rm -f $(BUILDDIR)/blockrd.got; \
	{ timeout 20 sh -c 'until grep -qx 1 $(BUILDDIR)/blockrd.got 2>/dev/null; do sleep 0.02; done'; printf 'x\n'; } | $(BUILDDIR)/blockrd > $(BUILDDIR)/blockrd.got; \
	diff -u testdata/blockrd.out $(BUILDDIR)/blockrd.got; \
	rm -f $(BUILDDIR)/blockrd.got; \
	{ timeout 20 sh -c 'until grep -qx 1 $(BUILDDIR)/blockrd.got 2>/dev/null; do sleep 0.02; done'; printf 'x\n'; } | python3 scripts/nonblocking.py $(BUILDDIR)/blockrd > $(BUILDDIR)/blockrd.got; \
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
	: a json in the console, its text, from --debug-mode and attached P204; \
	$(OUTDIR)/paslangc -debug -Fu $(BUILDDIR) -o $(BUILDDIR)/jsondbg testdata/jsondbg.paslang; \
	timeout 60 $(BUILDDIR)/jsondbg --debug-mode < testdata/jsondbg.in > $(BUILDDIR)/jsondbg.got 2>&1; \
	diff -u testdata/jsondbg.out $(BUILDDIR)/jsondbg.got; \
	s=@paslang-jsondbg-$$$$; \
	timeout 60 $(BUILDDIR)/jsondbg --debug-listen $$s > $(BUILDDIR)/jsondbgattach.prog 2>&1 & p=$$!; \
	timeout 60 $(BUILDDIR)/jsondbg --debug-attach $$s < testdata/jsondbg.in > $(BUILDDIR)/jsondbgattach.got 2>&1; \
	wait $$p; \
	echo '--- the program' >> $(BUILDDIR)/jsondbgattach.got; \
	cat $(BUILDDIR)/jsondbgattach.prog >> $(BUILDDIR)/jsondbgattach.got; \
	diff -u testdata/jsondbgattach.out $(BUILDDIR)/jsondbgattach.got; \
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
	grep -q 'unknown identifier Err at 12:11' $(BUILDDIR)/excbad_onscope.err; \
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
	grep -q 'an array of const is read, indexed, measured, walked or passed on to another, not kept in array of TVarRec at 7:12' $(BUILDDIR)/aconstbad_keep.err; \
	grep -q 'an array of const lives for the call: its address is not taken at 7:9' $(BUILDDIR)/aconstbad_addr.err; \
	grep -q 'A, an array of const, lives for the call: a closure in P may not keep it' $(BUILDDIR)/aconstbad_closure.err; \
	grep -q 'pas passes values, and an array of const lives for the call it is given to at 7:9' $(BUILDDIR)/aconstbad_paslist.err; \
	grep -q 'an array of const is given to a routine, not a var or out parameter at 3:20' $(BUILDDIR)/aconstbad_varparam.err; \
	grep -q 'array of const is the type of a parameter at 4:15' $(BUILDDIR)/aconstbad_vartype.err; \
	grep -q 'an array of const takes ordinals, reals, strings, pointers, objects, classes, interfaces and json, not TR at 13:6' $(BUILDDIR)/aconstbad_recval.err; \
	grep -q 'an array of const takes values, not a range at 7:6' $(BUILDDIR)/aconstbad_range.err; \
	echo ok aconstbad; \
	echo "==== default parameter rejects (P125) ===="; \
	for n in mvar mlast mimpl nilint mcount mfew; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/defbad_$$n testdata/defbad/$$n.paslang >$(BUILDDIR)/defbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q 'default on var parameter at 5:30' $(BUILDDIR)/defbad_mvar.err; \
	grep -q 'default parameters must be last at 5:31' $(BUILDDIR)/defbad_mlast.err; \
	grep -q 'the default of X is the declaration.s at 7:14' $(BUILDDIR)/defbad_mimpl.err; \
	grep -q 'nil is the default of a pointer, an object, a class, a routine, an interface or a slice, not of Integer at 3:24' $(BUILDDIR)/defbad_nilint.err; \
	grep -q 'wrong number of arguments for P at 14:5' $(BUILDDIR)/defbad_mcount.err; \
	grep -q 'wrong number of arguments for P at 16:5' $(BUILDDIR)/defbad_mfew.err; \
	echo ok defbad; \
	echo "==== set rejects (P126) ===="; \
	for n in range ofint strelem kinds outside forvar writeset divide inclconst charint inkind; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/setbad_$$n testdata/setbad/$$n.paslang >$(BUILDDIR)/setbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q 'a set holds elements 0 to 255, not 0..300 at 3:17' $(BUILDDIR)/setbad_range.err; \
	grep -q 'a set is of Char, Byte, Boolean, an enumeration or a subrange, not Integer at 3:18' $(BUILDDIR)/setbad_ofint.err; \
	grep -q 'a set holds ordinals, not string at 5:14' $(BUILDDIR)/setbad_strelem.err; \
	grep -q 'TBytes and TChars are sets of other elements at 10:8' $(BUILDDIR)/setbad_kinds.err; \
	grep -q 'set element out of 0..7 at 7:12' $(BUILDDIR)/setbad_outside.err; \
	grep -q 'for x in TBytes: x is a Char, not an element of it at 9:12' $(BUILDDIR)/setbad_forvar.err; \
	grep -q 'Write does not print a set: x in s tests an element at 6:11' $(BUILDDIR)/setbad_writeset.err; \
	grep -q '/ does not take a set: +, -, \*, =, <>, <= and >= do at 6:8' $(BUILDDIR)/setbad_divide.err; \
	grep -q 'S is a const parameter: the routine may not change it' $(BUILDDIR)/setbad_inclconst.err; \
	grep -q 'a list in brackets holds elements of one kind, not an integer and a Char at 5:12' $(BUILDDIR)/setbad_charint.err; \
	grep -q 'Integer is no element of set of Char at 7:6' $(BUILDDIR)/setbad_inkind.err; \
	echo ok setbad; \
	echo "==== subrange rejects (P135) ===="; \
	for n in mixed reversed twoenums notfit otherenum intenum charin; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/subbad_$$n testdata/subbad/$$n.paslang >$(BUILDDIR)/subbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q 'a subrange.s bounds are of one type, not Char and Integer at 3:10' $(BUILDDIR)/subbad_mixed.err; \
	grep -q 'bad subrange: 57 is above 48 at 3:11' $(BUILDDIR)/subbad_reversed.err; \
	grep -q 'a subrange.s bounds are of one type, not TColor and TDay at 5:10' $(BUILDDIR)/subbad_twoenums.err; \
	grep -q 'constant #120 does not fit TDigit at 7:8' $(BUILDDIR)/subbad_notfit.err; \
	grep -q 'a list in brackets holds elements of one kind, not TDay and TColor at 9:15' $(BUILDDIR)/subbad_otherenum.err; \
	grep -q 'Integer is no element of a set of TDay at 7:10' $(BUILDDIR)/subbad_intenum.err; \
	grep -q 'Char is no element of set of TDay at 10:6' $(BUILDDIR)/subbad_charin.err; \
	echo ok subbad; \
	echo "==== array index rejects (P161) ===="; \
	for n in idxreal idxbig idxwide idxrev; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/arrbad_$$n testdata/arrbad/$$n.paslang >$(BUILDDIR)/arrbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q 'an array.s index is an ordinal type or a range, not Real at 5:12' $(BUILDDIR)/arrbad_idxreal.err; \
	grep -q 'an array from -9223372036854775808 to 9223372036854775807 of Byte does not fit in 2147483647 bytes at 5:12' $(BUILDDIR)/arrbad_idxbig.err; \
	grep -q 'an array from 0 to 300000000 of Integer does not fit in 2147483647 bytes at 6:12' $(BUILDDIR)/arrbad_idxwide.err; \
	grep -q 'bad subrange: 3 is above 1 at 6:12' $(BUILDDIR)/arrbad_idxrev.err; \
	echo ok arrbad; \
	echo "==== helper rejects (P127) ===="; \
	for n in typerec recint field virt clsstat lastone strict typecall nodecl clsctor valmeth otherkind nomember; do \
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
	grep -q 'Hidden is strict private to TH at 24:13' $(BUILDDIR)/helpbad_strict.err; \
	grep -q 'TH.Twice is a method of a value, not of the type at 13:19' $(BUILDDIR)/helpbad_typecall.err; \
	grep -q 'TH declares no method Thrice of these parameters at 12:13' $(BUILDDIR)/helpbad_nodecl.err; \
	grep -q 'a helper has no class constructor at 7:11' $(BUILDDIR)/helpbad_clsctor.err; \
	grep -q 'TH.Twice is a method of a value, not of the type at 14:16' $(BUILDDIR)/helpbad_valmeth.err; \
	grep -q 'a helper descends from a helper of its kind at 9:22' $(BUILDDIR)/helpbad_otherkind.err; \
	grep -q 'Integer has no members: Twice needs a record, an object or a helper for Integer at 6:13' $(BUILDDIR)/helpbad_nomember.err; \
	echo ok helpbad; \
	echo "==== every error says where it is and what it met (P383) ===="; \
	for n in fieldkw fieldsym methname paramname ordargs sqrtargs enummember emptyenum unitname unitkw progname forvar readlnvar propname propword inheritedout vardefault ifacevar opsymbol genname breakout; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/placebad_$$n testdata/placebad/$$n.paslang >$(BUILDDIR)/placebad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q 'tree is a reserved word, not a field.s name at 5:5 \[tree\]' $(BUILDDIR)/placebad_fieldkw.err; \
	grep -q 'a field.s name expected at 5:5 \[5\]' $(BUILDDIR)/placebad_fieldsym.err; \
	grep -q 'a method.s name expected at 4:15 \[1\]' $(BUILDDIR)/placebad_methname.err; \
	grep -q 'a parameter.s name expected at 2:13 \[1\]' $(BUILDDIR)/placebad_paramname.err; \
	grep -q 'Ord takes 1 argument at 6:5' $(BUILDDIR)/placebad_ordargs.err; \
	grep -q 'Sqrt takes 1 argument at 5:8' $(BUILDDIR)/placebad_sqrtargs.err; \
	grep -q 'an enumeration.s member expected at 3:14 \[1\]' $(BUILDDIR)/placebad_enummember.err; \
	grep -q 'an enumeration.s member expected at 3:9 \[)\]' $(BUILDDIR)/placebad_emptyenum.err; \
	grep -q 'a unit.s name expected at 2:6 \[1\]' $(BUILDDIR)/placebad_unitname.err; \
	grep -q 'tree is a reserved word, not a unit.s name at 2:6 \[tree\]' $(BUILDDIR)/placebad_unitkw.err; \
	grep -q 'the program.s name expected at 1:9 \[1\]' $(BUILDDIR)/placebad_progname.err; \
	grep -q 'the for.s variable expected at 5:7 \[1\]' $(BUILDDIR)/placebad_forvar.err; \
	grep -q 'a variable for ReadLn expected at 3:10 \[1\]' $(BUILDDIR)/placebad_readlnvar.err; \
	grep -q 'a property.s name expected at 5:14 \[1\]' $(BUILDDIR)/placebad_propname.err; \
	grep -q 'read, write or json expected in a property, or its semicolon at 5:25 \[reed\]' $(BUILDDIR)/placebad_propword.err; \
	grep -q 'inherited is for a method of a class: it calls the parent.s at 4:3' $(BUILDDIR)/placebad_inheritedout.err; \
	grep -q 'a var parameter takes no default value at 2:28' $(BUILDDIR)/placebad_vardefault.err; \
	grep -q 'procedure or function expected in an interface at 4:5 \[var\]' $(BUILDDIR)/placebad_ifacevar.err; \
	grep -q 'an operator.s symbol expected at 6:10 \[@\]' $(BUILDDIR)/placebad_opsymbol.err; \
	grep -q 'a generic type.s name expected at 3:11 \[1\]' $(BUILDDIR)/placebad_genname.err; \
	grep -q 'break not in loop at line 7' $(BUILDDIR)/placebad_breakout.err; \
	: the emitter on arm64 refuses with the line it emits too, P383; \
	if $(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/placebad_breakouta testdata/placebad/breakout.paslang >$(BUILDDIR)/placebad_breakouta.err 2>&1; then \
	  echo "breakout should fail on arm64"; exit 1; \
	fi; \
	grep -q 'break not in loop at line 7' $(BUILDDIR)/placebad_breakouta.err; \
	python3 -I scripts/check_dieplace.py src/compiler/pasparse.paslang src/compiler/pasemit.paslang; \
	echo ok placebad; \
	echo "==== record operator rejects (P171) ===="; \
	for n in nobody badname notbool norec twice bodytypes cast explicitonly; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/recopbad_$$n testdata/recopbad/$$n.paslang >$(BUILDDIR)/recopbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q "missing body of TR.s operator + on TR and TR at 5:20" $(BUILDDIR)/recopbad_nobody.err; \
	grep -q "a record.s class operator is a symbol of Free Pascal.s or a name of Delphi.s (Free Pascal.s reference, table 9.1), not Power at 5:20" $(BUILDDIR)/recopbad_badname.err; \
	grep -q "class operator = gives a Boolean at 5:20" $(BUILDDIR)/recopbad_notbool.err; \
	grep -q "TR.s class operator + takes a TR at 5:20" $(BUILDDIR)/recopbad_norec.err; \
	grep -q "operator + on TR and TR declared twice at 6:20" $(BUILDDIR)/recopbad_twice.err; \
	grep -q "the body of TR.s operator + on TR and TR is of other types than its head at 7:19" $(BUILDDIR)/recopbad_bodytypes.err; \
	grep -q "Integer does not go into TR: a class operator Explicit or Implicit makes one, x as T sees its bytes at 9:11" $(BUILDDIR)/recopbad_cast.err; \
	grep -q "Integer does not go into TR; x as T sees its bytes at 15:8" $(BUILDDIR)/recopbad_explicitonly.err; \
	echo ok recopbad; \
	echo "==== operator rejects (P381) ===="; \
	for n in notargs incother convsame incstep recinc; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/opunbad_$$n testdata/opunbad/$$n.paslang >$(BUILDDIR)/opunbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q "operator not takes 1 argument at 8:10" $(BUILDDIR)/opunbad_notargs.err; \
	grep -q "operator inc gives a TV at 8:10" $(BUILDDIR)/opunbad_incother.err; \
	grep -q "operator := takes and gives a TV; a conversion goes from one type to another at 8:10" $(BUILDDIR)/opunbad_convsame.err; \
	grep -q "the operator inc of TV takes no step at 17:8" $(BUILDDIR)/opunbad_incstep.err; \
	grep -q "class operator Inc gives a TV at 6:20" $(BUILDDIR)/opunbad_recinc.err; \
	echo ok opunbad; \
	echo "==== json constants the compiler refuses (P209) ===="; \
	for n in place lines joined twice utf8 notext quote control; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/jsonconstbad_$$n testdata/jsonconstbad/$$n.paslang >$(BUILDDIR)/jsonconstbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q 'json constant: invalid character .}. at start of value within "/a" at 3:19' $(BUILDDIR)/jsonconstbad_place.err; \
	grep -q 'json constant: invalid character .]. at start of value within "/2" at 6:3' $(BUILDDIR)/jsonconstbad_lines.err; \
	grep -q 'json constant: invalid character .{. after top-level value at byte 7 of the text that starts at 3:13' $(BUILDDIR)/jsonconstbad_joined.err; \
	grep -q 'json constant: duplicate object member name "a" within "/y" at 3:32' $(BUILDDIR)/jsonconstbad_twice.err; \
	grep -q 'json constant: invalid UTF-8 within "/0" at 3:20' $(BUILDDIR)/jsonconstbad_utf8.err; \
	grep -q 'a json constant takes the text of its value, a string, or nil at 3:3' $(BUILDDIR)/jsonconstbad_notext.err; \
	grep -q 'json constant: invalid character .... at start of value within "/0" at 3:15' $(BUILDDIR)/jsonconstbad_quote.err; \
	grep -q 'json constant: invalid character ..t. in string (expecting non-control character) within "/a" at 5:29' $(BUILDDIR)/jsonconstbad_control.err; \
	echo ok jsonconstbad; \
	echo "==== record member rejects (P165) ===="; \
	for n in strictf strictm virt prot dtor clsctor nostat fieldafter typecall ctorres selfrec nodecl plainrec; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/recbad_$$n testdata/recbad/$$n.paslang >$(BUILDDIR)/recbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q 'FN is strict private to TR at 17:5' $(BUILDDIR)/recbad_strictf.err; \
	grep -q 'Hidden is strict private to TR at 17:5' $(BUILDDIR)/recbad_strictm.err; \
	grep -q 'a record.s method is not virtual: a record has no method table at 6:21' $(BUILDDIR)/recbad_virt.err; \
	grep -q 'a record has no descendants: private, strict private or public at 6:3' $(BUILDDIR)/recbad_prot.err; \
	grep -q 'a record has no destructor at 6:5' $(BUILDDIR)/recbad_dtor.err; \
	grep -qF 'missing body of TR.Init at 6:23' $(BUILDDIR)/recbad_clsctor.err; \
	grep -q 'a record.s class method is static: class function F: T; static; at 6:20' $(BUILDDIR)/recbad_nostat.err; \
	grep -q 'a record.s fields come before its methods and properties, or after private or public at 7:5' $(BUILDDIR)/recbad_fieldafter.err; \
	grep -q 'TR.Twice is a method of a value, not of the type at 13:14' $(BUILDDIR)/recbad_typecall.err; \
	grep -q 'unknown identifier Result at 10:3' $(BUILDDIR)/recbad_ctorres.err; \
	grep -q 'a record holds no field of its own type: TR at 6:12' $(BUILDDIR)/recbad_selfrec.err; \
	grep -q 'TR declares no method Thrice of these parameters at 12:13' $(BUILDDIR)/recbad_nodecl.err; \
	grep -q 'TR is a record with no methods at 6:13' $(BUILDDIR)/recbad_plainrec.err; \
	echo ok recbad; \
	echo "==== value kind rejects (P338) ===="; \
	for target in amd64 arm64; do \
	  for n in intproc intmeth intiface callmeth argproc resproc; do \
	    if $(OUTDIR)/paslangc -target $$target -o $(BUILDDIR)/valkindbad_$$n-$$target testdata/valkindbad/$$n.paslang >$(BUILDDIR)/valkindbad_$$n-$$target.err 2>&1; then \
	      echo "$$n should fail"; exit 1; \
	    fi; \
	  done; \
	  grep -qF 'Integer does not go into routine at 11:8' $(BUILDDIR)/valkindbad_intproc-$$target.err; \
	  grep -qF 'Integer does not go into method at 11:8' $(BUILDDIR)/valkindbad_intmeth-$$target.err; \
	  grep -qF 'Integer does not go into IVal at 13:8' $(BUILDDIR)/valkindbad_intiface-$$target.err; \
	  grep -qF 'this calls the method; @ before it gives the method value at 23:8' $(BUILDDIR)/valkindbad_callmeth-$$target.err; \
	  grep -qF 'string does not go into routine at 12:7' $(BUILDDIR)/valkindbad_argproc-$$target.err; \
	  grep -qF 'Integer does not go into routine at 9:13' $(BUILDDIR)/valkindbad_resproc-$$target.err; \
	done; \
	echo ok valkindbad; \
	echo "==== line end rejects (P339) ===="; \
	for target in amd64 arm64; do \
	  for n in bignum strend wordend readvar forvar methname; do \
	    if $(OUTDIR)/paslangc -target $$target -o $(BUILDDIR)/linebad_$$n-$$target testdata/linebad/$$n.paslang >$(BUILDDIR)/linebad_$$n-$$target.err 2>&1; then \
	      echo "$$n should fail"; exit 1; \
	    fi; \
	  done; \
	  grep -qF 'constant 99999999999999999999 does not fit Integer at 10:8' $(BUILDDIR)/linebad_bignum-$$target.err; \
	  grep -qF 'syntax error at 9:5 [abc]' $(BUILDDIR)/linebad_strend-$$target.err; \
	  grep -qF 'syntax error at 9:5 [abc]' $(BUILDDIR)/linebad_wordend-$$target.err; \
	  grep -qF 'unknown identifier Nope at 8:10' $(BUILDDIR)/linebad_readvar-$$target.err; \
	  grep -qF 'unknown identifier Nope at 8:7' $(BUILDDIR)/linebad_forvar-$$target.err; \
	  grep -qF 'unknown identifier Nope at 14:8' $(BUILDDIR)/linebad_methname-$$target.err; \
	done; \
	echo ok linebad; \
	echo "==== var argument rejects (P325) ===="; \
	for target in amd64 arm64; do \
	  for n in constarg exprarg fewargs manyargs; do \
	    if $(OUTDIR)/paslangc -target $$target -o $(BUILDDIR)/varbad_$$n-$$target testdata/varbad/$$n.paslang >$(BUILDDIR)/varbad_$$n-$$target.err 2>&1; then \
	      echo "$$n should fail"; exit 1; \
	    fi; \
	  done; \
	  grep -qF 'a var or out parameter needs a variable, not a value at 10:8' $(BUILDDIR)/varbad_constarg-$$target.err; \
	  grep -qF 'a var or out parameter needs a variable, not a value at 20:5' $(BUILDDIR)/varbad_exprarg-$$target.err; \
	  grep -qF 'wrong number of arguments for the routine value at 18:11' $(BUILDDIR)/varbad_fewargs-$$target.err; \
	  grep -qF 'wrong number of arguments for the routine value at 18:11' $(BUILDDIR)/varbad_manyargs-$$target.err; \
	done; \
	echo ok varbad; \
	echo "==== with rejects (P166, P172) ===="; \
	for target in amd64 arm64; do \
	  if $(OUTDIR)/paslangc -target $$target -o $(BUILDDIR)/withbad_$$target testdata/withbad/constwrite.paslang >$(BUILDDIR)/withbad_$$target.err 2>&1; then \
	    echo "a with must not change a const record"; exit 1; \
	  fi; \
	  grep -qF 'R is a const parameter: a with may not change it at line 11' $(BUILDDIR)/withbad_$$target.err; \
	  for n in constcapture varcapture; do \
	    if $(OUTDIR)/paslangc -target $$target -o $(BUILDDIR)/withbad_$$n-$$target testdata/withbad/$$n.paslang >$(BUILDDIR)/withbad_$$n-$$target.err 2>&1; then \
	      echo "$$n should fail"; exit 1; \
	    fi; \
	  done; \
	  grep -qF 'R is a const parameter: a closure in a with may not change it at line 12' $(BUILDDIR)/withbad_constcapture-$$target.err; \
	  grep -qF 'R is a var parameter of Capture, which has a closure inside' $(BUILDDIR)/withbad_varcapture-$$target.err; \
	  for n in intwith strictwith unknownwith; do \
	    if $(OUTDIR)/paslangc -target $$target -o $(BUILDDIR)/withbad_$$n-$$target testdata/withbad/$$n.paslang >$(BUILDDIR)/withbad_$$n-$$target.err 2>&1; then \
	      echo "$$n should fail"; exit 1; \
	    fi; \
	  done; \
	  grep -qF 'Integer has no members: with takes a record or an object at 11:8' $(BUILDDIR)/withbad_intwith-$$target.err; \
	  grep -qF 'Hidden is strict private to TSecret at 21:5' $(BUILDDIR)/withbad_strictwith-$$target.err; \
	  grep -qF 'unknown identifier M at 16:5' $(BUILDDIR)/withbad_unknownwith-$$target.err; \
	done; \
	echo ok withbad; \
	echo "==== unresolved method bodies (P167) ===="; \
	for target in amd64 arm64; do \
	  for n in rec cls help ctor static life over unitrec; do \
	    if $(OUTDIR)/paslangc -target $$target -o $(BUILDDIR)/methbodybad_$$n-$$target testdata/methbodybad/$$n.paslang >$(BUILDDIR)/methbodybad_$$n-$$target.err 2>&1; then \
	      echo "$$n must require a method body"; exit 1; \
	    fi; \
	    grep -qF 'paslangc: missing body of ' $(BUILDDIR)/methbodybad_$$n-$$target.err; \
	  done; \
	  for f in 'rec:TR.Twice at 5:14' 'cls:TC.Twice at 4:14' 'help:TH.Twice at 5:14' 'ctor:TR.Create at 5:17' 'static:TC.Twice at 4:20' 'life:TC.Start at 4:23' 'over:TR.Twice at 6:14' 'unitrec:TR.Twice at 6:14'; do \
	    n=$${f%%:*}; msg=$${f#*:}; \
	    grep -qF "missing body of $$msg" $(BUILDDIR)/methbodybad_$$n-$$target.err; \
	  done; \
	done; \
	echo ok methbodybad; \
	echo "==== record static rejects (P168) ===="; \
	for target in amd64 arm64; do \
	  for f in 'strictvar:X is strict private to TR at 6:18' 'strictprop:P is strict private to TR at 7:18' 'twoctor:a record has one class constructor at 4:21' 'lifeparams:a class constructor takes no parameters at 3:21' 'fielddup:X is a class variable already at 5:3' 'missing:missing body of TR.Start at 3:21'; do \
	    n=$${f%%:*}; msg=$${f#*:}; \
	    if $(OUTDIR)/paslangc -target $$target -o $(BUILDDIR)/recstaticbad_$$n-$$target testdata/recstaticbad/$$n.paslang >$(BUILDDIR)/recstaticbad_$$n-$$target.err 2>&1; then \
	      echo "$$n must fail"; exit 1; \
	    fi; \
	    grep -qF "$$msg" $(BUILDDIR)/recstaticbad_$$n-$$target.err; \
	  done; \
	done; \
	echo ok recstaticbad; \
	for target in amd64 arm64; do \
	  for f in 'gettype:TR.P requires a static getter of Integer' 'setvar:TR.P requires a static setter of Integer' 'varprop:TR.P: class variable Text has type string, not Integer'; do \
	    n=$${f%%:*}; msg=$${f#*:}; \
	    if $(OUTDIR)/paslangc -target $$target -o $(BUILDDIR)/recstaticbad_$$n-$$target testdata/recstaticbad/$$n.paslang >$(BUILDDIR)/recstaticbad_$$n-$$target.err 2>&1; then \
	      echo "$$n must fail"; exit 1; \
	    fi; \
	    grep -qF "$$msg" $(BUILDDIR)/recstaticbad_$$n-$$target.err; \
	  done; \
	done
	@set -e; \
	echo "==== string word rejects (P134) ===="; \
	for n in copyslice insertconst insertslice editcall strstring strdec valchar valcode soc upint posname valname; do \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/strbad_$$n testdata/strbad/$$n.paslang >$(BUILDDIR)/strbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	done; \
	grep -q 'Copy takes a string or a slice, not Integer at 6:16' $(BUILDDIR)/strbad_copyslice.err; \
	grep -q 'Insert(src, s, i): s needs a variable at 3:15' $(BUILDDIR)/strbad_insertconst.err; \
	grep -q 'string does not go into Integer; x as T sees its bytes at 5:10' $(BUILDDIR)/strbad_insertslice.err; \
	grep -q 'a slice that a call reaches is edited in a variable: put it in one first at 13:10' $(BUILDDIR)/strbad_editcall.err; \
	grep -q 'Str takes a number or an enumeration.s member, not string at 5:7' $(BUILDDIR)/strbad_strstring.err; \
	grep -q 'decimals are for a real at 5:11' $(BUILDDIR)/strbad_strdec.err; \
	grep -q 'Val reads a number, a real or an enumeration.s member, not Char at 6:12' $(BUILDDIR)/strbad_valchar.err; \
	grep -q 'Val(s, v, code): code is an integer variable, not string at 6:15' $(BUILDDIR)/strbad_valcode.err; \
	grep -q 'StringOfChar takes a Char, not string at 3:24' $(BUILDDIR)/strbad_soc.err; \
	grep -q 'a string or a Char goes here, not Integer at 3:18' $(BUILDDIR)/strbad_upint.err; \
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
	grep -q 'duplicate identifier K at 5:3' $(BUILDDIR)/scopebad_twoconst.err; \
	grep -q 'unknown identifier Q at 13:3' $(BUILDDIR)/scopebad_outside.err; \
	grep -q 'unknown identifier K at 10:11' $(BUILDDIR)/scopebad_constout.err; \
	echo ok scopebad; \
	echo "==== short class forms rejects (P139) ===="; \
	for f in 'unresolved:forward type TA not resolved at 3:3' \
	  'asparent:TA is not declared whole yet: a parent class is declared before the classes that descend from it at 4:14' \
	  'selfparent:TA is not declared whole yet: a parent class is declared before the classes that descend from it at 3:14' \
	  'ifparent:IX is not declared whole yet: a parent interface is declared before the interfaces that descend from it at 4:18' \
	  'implements:IX is not declared whole yet: an interface is declared before the classes that implement it at 4:23' \
	  'mismatch:TA was declared forward as a class at 4:8' 'mismatch2:TA was declared forward as a class at 4:8' \
	  'ifclass:IX was declared forward as an interface at 4:8' 'helper:TA was declared forward as a class at 4:8' \
	  'twice:duplicate type TA at 4:3' 'done:duplicate type TA at 5:3' 'inner:forward type TA not resolved at 4:3'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/classfwdbad_$$n testdata/classfwdbad/$$n.paslang >$(BUILDDIR)/classfwdbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/classfwdbad_$$n.err || { cat $(BUILDDIR)/classfwdbad_$$n.err; exit 1; }; \
	done; \
	echo ok classfwdbad; \
	echo "==== object into interface rejects (P140) ===="; \
	for f in 'noiface:TPlain does not implement IShape at 18:8' 'parentiface:TA does not implement IBase at 24:8'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/ifacebad_$$n testdata/ifacebad/$$n.paslang >$(BUILDDIR)/ifacebad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/ifacebad_$$n.err || { cat $(BUILDDIR)/ifacebad_$$n.err; exit 1; }; \
	done; \
	echo ok ifacebad; \
	echo "==== overload ambiguities (P141) ===="; \
	for f in 'ambigset:ambiguous call G at 18:11' 'ambigref:ambiguous call H at 24:11' 'ambigptr:ambiguous call F at 30:11'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/overbad_$$n testdata/overbad/$$n.paslang >$(BUILDDIR)/overbad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/overbad_$$n.err || { cat $(BUILDDIR)/overbad_$$n.err; exit 1; }; \
	done; \
	echo ok overbad; \
	echo "==== the value of a call is no place to write (P365) ===="; \
	for f in 'callfield:a field or an element of the value a call gives is no place to write at 12:3' 'getterfield:a field or an element of the value a call gives is no place to write at 19:3' 'callelem:a field or an element of the value a call gives is no place to write at 12:3'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/valplace_$$n testdata/valplace/$$n.paslang >$(BUILDDIR)/valplace_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/valplace_$$n.err || { cat $(BUILDDIR)/valplace_$$n.err; exit 1; }; \
	done; \
	echo ok valplace; \
	echo "==== JsonEncode and JsonOf refuse a list in brackets that is no set (P474) ===="; \
	for f in 'strs:it with JsonArray([...]) at 5:11' 'vars:it with JsonArray([...]) at 9:11' 'reals:it with JsonArray([...]) at 5:11' \
	  'bigint:it with JsonArray([...]) at 5:11' 'jsonof:it with JsonArray([...]) at 7:8'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/jsonlist_$$n testdata/jsonlist/$$n.paslang >$(BUILDDIR)/jsonlist_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/jsonlist_$$n.err || { cat $(BUILDDIR)/jsonlist_$$n.err; exit 1; }; \
	done; \
	echo ok jsonlist; \
	echo "==== HMAC and SHA-3 in pieces refuse a wrong state or wrong arguments (P443) ===="; \
	for f in 'hmacargs:HmacSha256Begin takes a THmacState and the key, a string at 7:3' \
	  'hmacstate:HmacSha256Update is THashState, not THmacState at 8:20' \
	  'sha3args:Sha3_256Update takes a TSha3State and a string at 8:3' \
	  'sha3state:Sha3_256Final is THmacState, not TSha3State at 8:25'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/piecebad_$$n testdata/piecebad/$$n.paslang >$(BUILDDIR)/piecebad_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/piecebad_$$n.err || { cat $(BUILDDIR)/piecebad_$$n.err; exit 1; }; \
	done; \
	echo ok piecebad; \
	echo "==== variables with a value and absolute rejects (P144) ===="; \
	for f in 'absnone:unknown variable nothing at 3:21' 'abstwo:absolute names one variable at a time at 4:15' \
	  'abstype:b: Byte absolute x: Integer; absolute is another name for a variable of its own type' \
	  'twoinit:one variable at a time takes a value at 3:15' \
	  'absfieldlocal:absolute names a field of a global record, and p is local to a routine at 12:23' \
	  'absfieldint:absolute names a variable or a field of a record, and n is Integer, no record at 6:23' \
	  'absfieldnone:TPoint has no field Z at 11:23' \
	  'absfieldtype:b: Byte absolute p.Y: Integer; absolute is another name for a variable of its own type'; do \
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
	  'chrcode:char code 300 out of range at 4:7' 'realbound:integer constant at 4:15 near 2.5, which is not an integer' \
	  'truncbig:constant out of Integer range at 6:7'; do \
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
	for f in 'ambig:ambiguous call Two at 15:3' 'nofit:no matching overload for Put at 12:3' \
	  'signed:no matching overload for Put at 15:3' 'varexact:no matching overload for Get at 15:3'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/$$n testdata/overbad/$$n.paslang >$(BUILDDIR)/$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/$$n.err || { cat $(BUILDDIR)/$$n.err; exit 1; }; \
	done; \
	echo ok overbad; \
	echo "==== narrow rejects ===="; \
	for f in 'const300:constant 300 does not fit Byte at 5:8 in testdata/narrowbad/const300.paslang' 'conv300:constant 300 does not fit Byte at 5:13' \
	  'negbyte:constant -1 does not fit Byte at 5:13' 'narrowing:Integer needs a conversion to Byte at 7:8' \
	  'mixed:Integer needs a conversion to Byte at 7:8' 'compare:constant 300 does not fit Byte at 6:10' \
	  'caselabel:case label does not fit Byte at 8:5' 'forlimit:constant 300 does not fit Byte at 5:17' \
	  'argument:constant 300 does not fit Byte at 9:5' 'default:default value 300 does not fit Byte at 3:23' \
	  'typedconst:constant 300 does not fit Byte at 3:13' 'nocontext:constant 300 does not fit Byte at 6:15' \
	  'signtoword:Int8 needs a conversion to Word at 7:8' 'vararg:var parameter of type Integer given a Byte at 11:5' \
	  'atomic:AtomicAdd needs an 8-byte integer, not a Byte at 7:21'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/nb_$$n testdata/narrowbad/$$n.paslang >$(BUILDDIR)/nb_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/nb_$$n.err || { cat $(BUILDDIR)/nb_$$n.err; exit 1; }; \
	done; \
	echo ok narrowbad; \
	echo "==== real rejects ===="; \
	for f in 'assign:a real does not go into Integer: Trunc or Round says how at 7:8 in testdata/realbad/assign.paslang' \
	  'argument:a real does not go into Integer: Trunc or Round says how at 12:5' \
	  'exitreal:a real does not go into Integer: Trunc or Round says how at 5:8' \
	  'boolreal:a real does not go into Boolean at 7:8' \
	  'ordreal:Ord of a real: Trunc or Round says how at 6:15'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/rb_$$n testdata/realbad/$$n.paslang >$(BUILDDIR)/rb_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/rb_$$n.err || { cat $(BUILDDIR)/rb_$$n.err; exit 1; }; \
	done; \
	echo ok realbad; \
	echo "==== single rejects ===="; \
	for f in 'assign:Double needs Single(x) to become a Single at 7:8 in testdata/singlebad/assign.paslang' \
	  'mixed:Double needs Single(x) to become a Single at 8:8' \
	  'argument:Double needs Single(x) to become a Single at 12:5' \
	  'exitdbl:Double needs Single(x) to become a Single at 5:8' \
	  'bigconst:constant 1e39 does not fit Single at 5:8' \
	  'convbig:constant 4e38 does not fit Single at 5:16' \
	  'default:default value does not fit Single at 3:25' \
	  'typedconst:a constant that does not fit Single at 3:15' \
	  'polysingle:Poly takes an array of Real at 6:11'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/sb_$$n testdata/singlebad/$$n.paslang >$(BUILDDIR)/sb_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/sb_$$n.err || { cat $(BUILDDIR)/sb_$$n.err; exit 1; }; \
	done; \
	echo ok singlebad; \
	echo "==== pointer rejects ===="; \
	for f in 'readderef:the target of an untyped Pointer needs a type: T(p^) or PT(p)^ at 7:8 in testdata/ptrbad/readderef.paslang' \
	  'storederef:the target of an untyped Pointer needs a type: T(p^) or PT(p)^ at 7:3' \
	  'writederef:the target of an untyped Pointer needs a type: T(p^) or PT(p)^ at 7:11' \
	  'arithderef:the target of an untyped Pointer needs a type: T(p^) or PT(p)^ at 7:8' \
	  'indexptr:an untyped Pointer is indexed through a view: PByte(p)[i] at 7:8' \
	  'twotypes:pointers of two types: see both through one view, PT(p) - PT(q) at 8:14' \
	  'addptrs:two pointers do not add at 7:8' \
	  'intminusptr:an integer minus a pointer at 7:8' \
	  'caretbad:^T(q) sees a pointer, a class or an address at 7:8' \
	  'reachvar:pointer outside its object: x has 8 bytes and this reaches bytes 8 to 8 at 6:18' \
	  'reachneg:pointer outside its object: x has 8 bytes and this reaches bytes -1 to -1 at 7:18' \
	  'reachwide:pointer outside its object: b has 1 byte and this reaches bytes 0 to 7 at 6:20' \
	  'reachfield:pointer outside its object: r has 12 bytes and this reaches bytes 8 to 15 at 13:20' \
	  'reachindex:pointer outside its object: a has 8 bytes and this reaches bytes 8 to 9 at 6:17' \
	  'reachview:pointer outside its object: x has 8 bytes and this reaches bytes 0 to 11 at 13:17' \
	  'reachuntyped:pointer outside its object: x has 8 bytes and this reaches bytes 0 to 11 at 13:24' \
	  'reachfill:pointer outside its object: r has 12 bytes and this reaches bytes 0 to 99 at 12:12' \
	  'reachmove:pointer outside its object: x has 8 bytes and this reaches bytes 0 to 15 at 7:8'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/pb_$$n testdata/ptrbad/$$n.paslang >$(BUILDDIR)/pb_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/pb_$$n.err || { cat $(BUILDDIR)/pb_$$n.err; exit 1; }; \
	done; \
	echo ok ptrbad; \
	echo "==== safe rejects ===="; \
	for f in 'arith:safe code does not do pointer arithmetic at 10:8 in testdata/safebad/arith.paslang' \
	  'incptr:safe code does not step a pointer at 10:7' \
	  'indexptr:safe code does not index a pointer; an array or a slice checks its index at 10:13' \
	  'view:safe code does not see memory as another type at 10:13' \
	  'caret:safe code does not see memory as another type at 7:13' \
	  'untyped:safe code does not reach through an untyped Pointer at 11:8' \
	  'fromint:safe code does not see memory as another type at 5:13' \
	  'nested:safe code does not step a pointer at 12:9' \
	  'method:safe code does not see memory as another type at 11:13' \
	  'wholeprog:safe code does not do pointer arithmetic at 7:8' \
	  'notroutine:safe goes before a routine, a unit or a program at 2:6' \
	  'viewsafe:safe code does not see memory as an array at 9:8'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/sf_$$n testdata/safebad/$$n.paslang >$(BUILDDIR)/sf_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF "$$w" $(BUILDDIR)/sf_$$n.err || { cat $(BUILDDIR)/sf_$$n.err; exit 1; }; \
	done; \
	echo ok safebad; \
	echo "==== quad rejects ===="; \
	for f in 'todouble:a Quad becomes a Double only through Double(x) at 19:8 in testdata/quadbad/todouble.paslang' \
	  'tosingle:a Quad becomes a Single only through Single(x) at 19:8' \
	  'toint:a Quad does not go into Integer: Trunc or Round says how at 19:8' \
	  'tobool:a Quad does not go into Boolean at 19:8' \
	  'nosin:sin has no Quad form: write Double(x) for it at 19:8' \
	  'fromstr:a string does not become a Quad at 19:8' \
	  'toobig:constant 1e5000 does not fit Quad at 19:3' \
	  'quaddiv:a Quad takes +, -, *, / and the comparisons at 19:8' \
	  'quadnot:not does not take a real at 19:12'; do \
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
	for f in 'notplace:+= needs a variable at 22:8' \
	  'narrow:Integer needs a conversion to Byte at 22:3' \
	  'realnand:nand does not take a real at 22:8' \
	  'realrol:rol does not take a real at 22:8' \
	  'realdiv:div does not take a real at 22:3' \
	  'boolrol:rol takes two integers at 22:8' \
	  'strxnor:xnor does not take a string at 22:8' \
	  'strsub:- does not take a string at 22:3' \
	  'strint:+ joins a string with a string or a Char at 22:8' \
	  'strneg:- does not take a string at 22:9' \
	  'strnot:string does not go into Boolean; x as T sees its bytes at 22:8' \
	  'arradd:+ does not take an array at 22:9' \
	  'recand:a record does not go into Integer; x as T sees its bytes at 22:8' \
	  'mixnor:nor of a Boolean and an integer: a comparison binds first, so write (x and 4) = 4, or Ord(b) for the number at 22:8' \
	  'mixand:and of a Boolean and an integer: a comparison binds first, so write (x and 4) = 4, or Ord(b) for the number at 22:6' \
	  'inttobool:Integer does not go into Boolean: Boolean(x) is x <> 0 at 22:8' \
	  'booladd:Integer does not go into Boolean: Boolean(x) is x <> 0 at 22:8' \
	  'boolreal:a real does not go into Boolean: compare it at 22:16' \
	  'boolstr:Boolean() takes an ordinal or a pointer at 22:16' \
	  'quadrol:a Quad takes +, -, *, / and the comparisons at 22:3' \
	  'inexpr:an expression is expected, not = at 22:9' \
	  'laterlocal:unknown identifier n at 8:5' \
	  'bitconst:bit 8 out of range [0..7] at 22:8' \
	  'fieldconst:bits 6..9 out of range [0..7] at 22:8' \
	  'fieldwidth:GetBits takes a constant width at 22:8' \
	  'widthzero:GetBits takes a width of 1 to 8 at 22:8' \
	  'setbitconst:SetBit needs a variable at 22:3' \
	  'recbit:bit 64 out of range [0..63] at 23:8' \
	  'recfield:bits 60..67 out of range [0..63] at 23:8' \
	  'recrev:ReverseBits takes a value of up to 8 bytes at 23:8' \
	  'rawpop:PopCount of raw memory: it has no end; see it through View(p, n) at 23:8' \
	  'stratomic:AtomicSetBit of a string: its characters may be shared; use a slice or an integer at 23:8' \
	  'strcall:IsBitSet of a string or a slice that calls a routine: put it in a variable first at 23:8' \
	  'saferaw:safe code does not reach through an untyped Pointer at 23:10' \
	  'viewbig:a view of 2 bytes on Byte of 1 at 23:8' \
	  'viewrec:a view of 16 bytes on a record of 8 at 23:9' \
	  'viewval:a view of this value as array[0..7] of Byte needs a variable at 23:10' \
	  'viewwrite:a view that is written needs a variable whose place calls no routine at 23:3' \
	  'incexpr:Inc needs a variable at 23:7' \
	  'parenplace:a variable is expected before := at 23:11' \
	  'saferawview:safe code does not reach through an untyped Pointer at 23:8' \
	  'realconv:a real becomes Integer through Trunc or Round; x as Integer sees its bits at 22:15' \
	  'realbyte:a real becomes Byte through Trunc or Round; x as Byte sees its bits at 22:13' \
	  'blkptr:xor of a record, which holds strings, pointers or objects, would make addresses up at 24:8' \
	  'blksize:xor of blocks of 8 and 16 bytes at 24:8' \
	  'blkexpr:logic on a record or an array goes into a variable: r := a xor b at 24:3' \
	  'blkreal:and of array[0..1] of Integer takes a block of its size, or an integer for an array of integers at 24:8' \
	  'recint:TR does not go into Integer; x as T sees its bytes at 16:8' \
	  'strtoint:string does not go into Integer; x as T sees its bytes at 16:8' \
	  'dynelem:array of Byte does not go into array of Integer; x as T sees its bytes at 16:8' \
	  'mulhireal:MulHi takes integers at 22:8' \
	  'carryconst:AddCarry takes a variable whose place calls no routine at 22:8' \
	  'mul128byte:Mul128 takes an Integer variable at 22:3' \
	  'divmodargs:DivMod128 takes 5 arguments at 22:3' \
	  'prefint:Prefetch takes a pointer at 23:12' \
	  'aloadconst:AtomicLoad takes a variable whose place calls no routine at 23:8' \
	  "cpuname:CpuHas does not know 'avx3' at 24:6" \
	  "cpuvar:CpuHas takes the name of a feature in quotes, as CpuHas('avx2') at 25:6" \
	  'cycleargs:CycleCount takes no argument at 24:8' \
	  'vecwidth:VAdd8 takes vectors of one width, not a V128 and a V256 at 16:8' \
	  'vecint:VAdd8 takes a V128 or a V256, not Integer at 16:17' \
	  'vecsplat:VSplat8 takes an integer at 16:8' \
	  'veccount:VShl16 takes a shift count, an integer at 16:8' \
	  'vecargs:VAdd8 takes 2 arguments at 16:8' \
	  'vecdeep:a vector expression this deep needs more than the 14 vector registers: split it into two statements at 16:8' \
	  'vecnarrow:V256 does not go into V128; x as T sees its bytes at 16:8' \
	  'writevec:Write does not print a V128: view its lanes, as (v as array[0..15] of Byte)[i] at 16:11' \
	  'writerec:Write does not print a record: write its fields at 16:11' \
	  'writearr:Write does not print an array: write its elements at 16:14' \
	  'writechars:Write does not print an array: write its elements at 16:9' \
	  'vecsplatf:VSplatF32 takes a number at 10:8' \
	  'vecred:VSumU8 takes a V128 or a V256, not Integer at 10:15' \
	  'vecredint:Integer does not go into V128; x as T sees its bytes at 10:8' \
	  'asmalone:asm arm64 alone: this is compiled for amd64, so write an asm amd64 block beside it at 9:3' \
	  'asmreg:asm does not bind rsp: rsp and rbp hold the frame, r14 the running routine at 9:20' \
	  'asmtype:asm binds V128 to no integer register at 9:20' \
	  'asmxmm:asm amd64 does not bind Integer to xmm0: rax to r15 take integers, xmm a Single, a Double or a V128, ymm a V256 at 9:20' \
	  'asmout:asm out and inout take a variable at 9:21' \
	  'asmline:asm lines start on the line after the bindings at 9:23' \
	  'asmsafe:safe code does not take asm at 10:3' \
	  'asmtwo:two asm blocks for amd64 side by side at 11:7' \
	  'asmmode:an asm binding is in, out or inout at 9:17' \
	  'dupfield:x is a field already at 7:5' \
	  'dupinherit:A is a field already at 9:5' \
	  'storebig:constant 70000 does not fit Word at 23:16' \
	  'safeload:safe code does not see memory as another type at 23:17' \
	  'setbitsbig:constant 20 does not fit 4 bits at 22:3' \
	  'setbitcall:SetBit of a place that calls: assign it at 22:3' \
	  'rotptr:RotateLeftToCarry of TNamed, which holds strings, pointers or objects, would make addresses up at 15:26' \
	  'rotslptr:ShiftLeft of array of string, which holds strings, pointers or objects, would make addresses up at 8:18' \
	  'rotobj:RotateRight takes a value, not an object: turn its fields at 14:8' \
	  'rotraw:the target of an untyped Pointer needs a type: T(p^) or PT(p)^ at 10:26' \
	  'funnelmix:FunnelLeft takes two values of one type, not TPair and Integer at 14:19' \
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
	  'appendnot:Append takes a slice first, not Integer at 8:15' \
	  'capnot:Cap takes a slice, not string at 9:12' \
	  'appendelem:string does not go into Integer; x as T sees its bytes at 8:18' \
	  'slicerange:a slice takes values, not a range at 8:9' \
	  'resappend:Append is a reserved word, not a name at 4:11' \
	  'capvar:X is a var parameter of P, which has a closure inside: a closure may outlive the variable it points at; copy it to a local at 13:5' \
	  'capresult:Result of F, which has a closure inside, is not shared with the routines in it: use a local at 12:5' \
	  'capcounter:i is the counter a closure in this loop keeps: no loop inside may count with it at 18:5' \
	  'runechar:for c in a string walks its code points: c is a Rune or an Integer, not Char at 10:3' \
	  'assignednot:Assigned takes a pointer, an object, a routine value or a slice, not Integer at 9:20' \
	  'rotcount:ShiftLeft takes a count, an integer at 22:8' \
	  'carryarg:CarryOn takes no argument at 22:3' \
	  'carryint:Integer does not go into Boolean: Boolean(x) is x <> 0 at 22:12' \
	  'rotargs:RotateLeftToCarry takes 1 or 2 arguments at 22:8' \
	  'rotfit:constant 300 does not fit Byte at 22:26' \
	  'pasvar:pas passes values: parameter 1 of Bump is a var parameter at 13:3' \
	  'pasanonargs:pas runs a routine with no parameters: pas procedure begin ... end at 5:3' \
	  'pasnotcall:pas takes a call: pas F(a, b), pas f, pas obj.M(a) or pas procedure begin ... end at 8:3' \
	  'pasbuiltin:pas takes a routine of the program, not Length at 8:3' \
	  'pasmethvar:pas passes values: parameter 1 is a var parameter at 24:3' \
	  'methvalcount:wrong number of arguments for the method value at 22:3' \
	  'pasnoargs:this routine takes 2 arguments and none are written at 18:7' \
	  'methnoargs:this routine takes 2 arguments and none are written at 20:3' \
	  'setint:a set does not go into Integer at 8:8' \
	  'lengthint:Length takes a string, an array, a slice or a map, not Integer at 8:15' \
	  'makechanneg:MakeChan takes a capacity of 0 or more at 6:8' \
	  'makechanbig:MakeChan takes a capacity of up to 67108864 at 5:8' \
	  'v128int:Integer does not go into V128: VSplat8..64 or a view makes one at 5:13' \
	  'realinc:a real does not go into Integer: Trunc or Round says how at 6:10' \
	  'realidx:a real does not go into Integer: Trunc or Round says how at 6:5' \
	  'realfor:a real does not go into Integer: Trunc or Round says how at 6:17' \
	  'realif:a real does not go into Boolean: compare it at 6:6' \
	  'realwhile:a real does not go into Boolean: compare it at 6:9' \
	  'realsetlen:a real does not go into Integer: Trunc or Round says how at 6:16' \
	  'realcase:a real does not go into a case: Trunc or Round says how at 6:8' \
	  'caseacross:empty case range 9223372036854775807..-9223372036854775808: Integer is signed, so a hex constant from $$8000000000000000 up is negative at 9:6' \
	  'succlast:Succ past the last value of TColor at 4:16' \
	  'predfirst:Pred before the first value of TColor at 4:16' \
	  'subrreal:a real does not go into TSmall: Trunc or Round says how at 7:9' \
	  'dupglobal:duplicate identifier a at 4:5' \
	  'dechuge:constant 9223372036854775809 does not fit Integer at 6:8' \
	  'dec63:constant 9223372036854775808 does not fit Integer: -9223372036854775808 is the lowest at 6:8' \
	  'hexhuge:constant $$10000000000000001 does not fit Integer at 6:9' \
	  'highmap:High takes an array, a slice, a string, an ordinal or a tree, not map[Integer] of Integer at 9:13' \
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
	  'visstrictword:strict goes before private or protected at 6:10' \
	  'vismethval:Bump is strict private to TA at 21:10' \
	  'mapkeyreal:Real does not go into Integer, the key of map[Integer] of Integer at 9:5' \
	  'mapkeykind:Integer does not go into string, the key of map[string] of Integer at 10:10' \
	  'mapkeyfit:constant 300 does not fit Byte at 9:5' \
	  'mapforval:for k, v in map[Integer] of Integer: v is Byte, the values are Integer at 11:3' \
	  'mapforkey:for k in map[string] of Integer: k is Integer, the keys are string at 10:3' \
	  'maptryget:TryGet(m, k, v): v is string, the values of map[string] of Integer are Integer at 10:21' \
	  'mapaddr:the address of a map element is not taken: the table moves when the map grows at 10:9' \
	  'mapinto:map[string] of Integer does not go into map[Integer] of string at 10:8' \
	  'incstr:Inc takes a number, an ordinal or a pointer, not string at 9:7' \
	  'vararr:array[0..3] of Byte does not go into a var array of Byte parameter: a slice does at 13:8' \
	  'varelem:var parameter of type array of TRec given a array of TObj at 21:8' \
	  'outelem:var parameter of type array of Byte given a array of Word at 10:8' \
	  'varreal:var parameter of type Real given a Single at 12:8' \
	  'varclass:var parameter of type TBase given a TDer at 17:11' \
	  'varenum:var parameter of type TColor given a TOther at 15:9' \
	  'varbool:var parameter of type Boolean given a Integer at 11:8' \
	  'varrec:var parameter of type TA given a TB at 19:8' \
	  'atomicval:AtomicAdd takes the address of an Integer, as AtomicAdd(@v, ...), not the Integer itself at 5:13' \
	  'atomiccasval:AtomicCas takes the address of an Integer, as AtomicCas(@v, ...), not the Integer itself at 5:16' \
	  'merklestatic:MerkleRoot takes the leaves as a slice, array of string, not the static array[0..2] of string: SetLength one and fill it at 8:29' \
	  'constwrite:S is a const parameter: the routine may not change it or pass it as var; copy it into a variable first at 4:3' \
	  'constvar:S is a const parameter: the routine may not change it or pass it as var; copy it into a variable first at 8:5'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/bb_$$n testdata/bitbad/$$n.paslang >$(BUILDDIR)/bb_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF -e "$$w" $(BUILDDIR)/bb_$$n.err || { cat $(BUILDDIR)/bb_$$n.err; exit 1; }; \
	done; \
	echo ok bitbad; \
	echo "==== condbad ===="; \
	for f in 'unknown:{$$if} NOTHING is not a number (defined(NOTHING) says whether it is defined) at 3: NOTHING > 1' \
	  'paren:{$$if} wants ) at 3: (1 = 1' \
	  'trailing:{$$if} cannot read 2 after the expression at 3: 1 2' \
	  'empty:{$$if} wants an expression at 3' \
	  'plus:{$$if} cannot read '"'+'"' at 3: 1 + 2' \
	  'elseifbad:{$$if} NOWHERE is not a number (defined(NOWHERE) says whether it is defined) at 4: NOWHERE' \
	  'needed:{$$error} needs paslangc 99 or later at 4' \
	  'fatal:{$$fatal} stop here at 3'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/cb_$$n testdata/condbad/$$n.paslang >$(BUILDDIR)/cb_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF -e "$$w" $(BUILDDIR)/cb_$$n.err || { cat $(BUILDDIR)/cb_$$n.err; exit 1; }; \
	done; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/condver-info testdata/condver.paslang >/dev/null 2>$(BUILDDIR)/condver-info.err; \
	grep -qF 'paslangc: info: compiled by paslangc 1.1.108 or later at 66 in testdata/condver.paslang' $(BUILDDIR)/condver-info.err || { cat $(BUILDDIR)/condver-info.err; exit 1; }; \
	$(OUTDIR)/paslangc testdata/units/condu.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/conduse testdata/conduse.paslang; \
	$(BUILDDIR)/conduse > $(BUILDDIR)/conduse.got; \
	diff -u testdata/conduse.out $(BUILDDIR)/conduse.got; \
	echo ok condbad; \
	echo "==== cpubad and cputune ===="; \
	: the processor in the code, P261: the directives refused where they cannot be, the processors the flags do not know; \
	for f in 'unknown:{$$CPU zen9}: zen9 is no processor or feature of amd64 at 3' \
	  'empty:{$$CPU} wants a processor, a feature or DEFAULT at 3' \
	  'featarm:{$$CPU base+atomics}: atomics is no processor or feature of amd64 at 3' \
	  'tunearm:{$$TUNE neoverse-n1}: neoverse-n1 is no processor of the target' \
	  'inbody:{$$CPU} or {$$TUNE} at line 6 is inside the body of P: they stand between routines' \
	  'inmain:{$$CPU} or {$$TUNE} at line 5 is inside the main block' \
	  'ininit:{$$CPU} or {$$TUNE} at line 12 is inside the initialization or the finalization'; do \
	  n=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc -o $(BUILDDIR)/cpb_$$n testdata/cpubad/$$n.paslang >$(BUILDDIR)/cpb_$$n.err 2>&1; then \
	    echo "$$n should fail"; exit 1; \
	  fi; \
	  grep -qF -e "$$w" $(BUILDDIR)/cpb_$$n.err || { cat $(BUILDDIR)/cpb_$$n.err; exit 1; }; \
	done; \
	for f in '-cpu zen9:zen9 is no processor or feature of amd64' \
	  '-tune foo:-tune foo: no processor of the target' \
	  '-tune neoverse-n1:-tune neoverse-n1: no processor of the target' \
	  '-target arm64 -cpu native:native is the machine compiling, which is not an arm64 one' \
	  '-target arm64 -cpu zen2:zen2 is no processor or feature of arm64'; do \
	  o=$${f%%:*}; w=$${f#*:}; \
	  if $(OUTDIR)/paslangc $$o -o $(BUILDDIR)/cpb_flag testdata/hello.paslang >$(BUILDDIR)/cpb_flag.err 2>&1; then \
	    echo "paslangc $$o should fail"; exit 1; \
	  fi; \
	  grep -qF -e "$$w" $(BUILDDIR)/cpb_flag.err || { cat $(BUILDDIR)/cpb_flag.err; exit 1; }; \
	done; \
	$(OUTDIR)/paslangc -v | grep -q '^processor: ' || { echo "paslangc -v names no processor"; exit 1; }; \
	: the same counts compiled for the base, for a processor named, with the costs of another; \
	for c in base 'native -tune zen5' 'native -tune zen2' 'native -inline 0'; do \
	  $(OUTDIR)/paslangc -cpu $$c -o $(BUILDDIR)/cputune-c testdata/cputune.paslang; \
	  $(BUILDDIR)/cputune-c > $(BUILDDIR)/cputune-c.got; \
	  diff -u testdata/cputune.out $(BUILDDIR)/cputune-c.got; \
	done; \
	python3 -I scripts/cputune_out.py testdata/cputune.paslang | diff -u testdata/cputune.out - ; \
	: under -cpu base, the routines after the CPU haswell directive take lzcnt and tzcnt and say so, the base ones bsr and bsf, and One stays a call from the main block; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/cputune-b testdata/cputune.paslang; \
	awk '/^p_lzfast:/,/^\.section/' $(BUILDDIR)/cputune-b.s > $(BUILDDIR)/cputune-lzfast.s; \
	awk '/^p_tzfast:/,/^\.section/' $(BUILDDIR)/cputune-b.s > $(BUILDDIR)/cputune-tzfast.s; \
	awk '/^p_lzbase:/,/^\.section/' $(BUILDDIR)/cputune-b.s > $(BUILDDIR)/cputune-lzbase.s; \
	awk '/^p_tzbase:/,/^\.section/' $(BUILDDIR)/cputune-b.s > $(BUILDDIR)/cputune-tzbase.s; \
	awk '/^pas_main:/,/^\.section/' $(BUILDDIR)/cputune-b.s > $(BUILDDIR)/cputune-main.s; \
	test $$(grep -c 'lzcnt[lq] ' $(BUILDDIR)/cputune-lzfast.s) = 7 || { echo "cputune.s: LzFast has not seven lzcnt"; exit 1; }; \
	test $$(grep -c 'tzcnt[lq] ' $(BUILDDIR)/cputune-tzfast.s) = 7 || { echo "cputune.s: TzFast has not seven tzcnt"; exit 1; }; \
	if grep -q 'bsr\|bsf' $(BUILDDIR)/cputune-lzfast.s $(BUILDDIR)/cputune-tzfast.s; then echo "cputune.s: a haswell routine has bsr or bsf"; exit 1; fi; \
	test $$(grep -c 'bsrq ' $(BUILDDIR)/cputune-lzbase.s) = 7 && test $$(grep -c 'bsfq ' $(BUILDDIR)/cputune-tzbase.s) = 7 || { echo "cputune.s: the base routines are not bsr and bsf"; exit 1; }; \
	if grep -q 'lzcnt\|tzcnt' $(BUILDDIR)/cputune-lzbase.s $(BUILDDIR)/cputune-tzbase.s $(BUILDDIR)/cputune-main.s; then echo "cputune.s: a base routine has lzcnt or tzcnt"; exit 1; fi; \
	grep -qF '/* p_lzfast: cpu ' $(BUILDDIR)/cputune-b.s && grep -F '/* p_lzfast: cpu ' $(BUILDDIR)/cputune-b.s | grep -q 'bmi1.* lzcnt.*; tune haswell \*/' || { echo "cputune.s: LzFast does not say its processor"; exit 1; }; \
	grep -qF '; tune zen1 */' $(BUILDDIR)/cputune-b.s || { echo "cputune.s: Tuned does not say its tune"; exit 1; }; \
	if grep -qF '/* p_lzbase' $(BUILDDIR)/cputune-b.s; then echo "cputune.s: a routine of the command line's processor says one"; exit 1; fi; \
	grep -q 'call p_one$$' $(BUILDDIR)/cputune-main.s || { echo "cputune.s: One, of another processor, went into the main block"; exit 1; }; \
	if grep -q 'call p_two$$' $(BUILDDIR)/cputune-main.s; then echo "cputune.s: Two, of the main block's processor, stayed a call"; exit 1; fi; \
	: the runtime by -tune: the highest bit of the last word that differs is 63 - lzcnt on zen2, bsr on zen5 and haswell; \
	$(OUTDIR)/paslangc -cpu haswell -tune zen2 -o $(BUILDDIR)/cputune-hz2 testdata/cputune.paslang; \
	$(OUTDIR)/paslangc -cpu haswell -tune zen5 -o $(BUILDDIR)/cputune-hz5 testdata/cputune.paslang; \
	$(OUTDIR)/paslangc -cpu zen2 -tune generic -o $(BUILDDIR)/cputune-z2g testdata/cputune.paslang; \
	grep -A1 'lzcntq %rcx, %rcx' $(BUILDDIR)/cputune-hz2.s | grep -q 'xorq $$63, %rcx' && grep -A1 'lzcntq %rdx, %rcx' $(BUILDDIR)/cputune-hz2.s | grep -q 'xorq $$63, %rcx' || { echo "cputune-hz2.s: the runtime does not take 63 - lzcnt"; exit 1; }; \
	if grep -q 'bsrq %rcx, %rcx\|bsrq %rdx, %rcx' $(BUILDDIR)/cputune-hz2.s; then echo "cputune-hz2.s: the runtime keeps bsr on zen2's costs"; exit 1; fi; \
	for f in hz5 z2g; do \
	  grep -q 'bsrq %rcx, %rcx' $(BUILDDIR)/cputune-$$f.s && grep -q 'bsrq %rdx, %rcx' $(BUILDDIR)/cputune-$$f.s || { echo "cputune-$$f.s: the runtime does not keep bsr"; exit 1; }; \
	  if grep -q 'lzcntq %rcx, %rcx' $(BUILDDIR)/cputune-$$f.s; then echo "cputune-$$f.s: the runtime takes lzcnt"; exit 1; fi; \
	done; \
	: a unit compiled for base whose routine and initialization are for haswell; \
	$(OUTDIR)/paslangc -cpu base testdata/units/cpuu.paslang; \
	grep -qF '/* p_cpuu_uhigh: cpu ' $(BUILDDIR)/cpuu.s && grep -qF '/* u_cpuu_init: cpu ' $(BUILDDIR)/cpuu.s || { echo "cpuu.s: the unit's routine or initialization does not say its processor"; exit 1; }; \
	awk '/^p_cpuu_uhigh:/,/^\.section/' $(BUILDDIR)/cpuu.s | grep -q 'lzcnt' || { echo "cpuu.s: UHigh has no lzcnt"; exit 1; }; \
	$(OUTDIR)/paslangc -cpu base -Fu $(BUILDDIR) -o $(BUILDDIR)/cputuse testdata/cputuse.paslang; \
	$(BUILDDIR)/cputuse > $(BUILDDIR)/cputuse.got; \
	diff -u testdata/cputuse.out $(BUILDDIR)/cputuse.got; \
	echo ok cpubad; \
	echo "==== treebad ===="; \
	for f in 'tryset:TryGet needs a tree with values: k in t says whether k is there at 9:6 in testdata/treebad/tryset.paslang' \
	  'setval:+= of a tree of K: t[k] is True or False, and Include(t, k) puts k in at 8:11' \
	  'jointypes:Join takes two trees of one type at 9:3' \
	  'pushtype:string does not go into Integer, the elements of heap of Integer at 9:11' \
	  'popvar:Pop(h, v): v needs a variable at 8:13' \
	  'poptype:Pop(h, v): v is string, not Integer at 9:13' \
	  'keyatreal:a real does not go into Integer: Trunc or Round says how at 8:20' \
	  'succtree:Succ takes an ordinal, or a tree and a key, not tree[Integer] of Integer at 8:16' \
	  'merkleleaves:MerkleRoot takes the leaves as a slice of strings, not Integer at 4:29' \
	  'storearg:StorePut takes a store, a key and a value, both strings at 4:3' \
	  'forkv:for k, v needs a tree with values; for k in t walks a tree of K at 9:3' \
	  'lowmap:Low takes an array, a slice, a string, an ordinal or a tree, not map[Integer] of Integer at 8:15' \
	  'includeint:Include takes a tree and a key, or a set and an element at 7:3' \
	  'poplowset:PopLow of a tree of K takes the key alone at 9:6' \
	  'rangeval:for k, v in tree[Integer] of Integer: v is string, the values are Integer at 10:3' \
	  'forinheap:for x in does not walk a heap: take its elements with Pop at 10:3' \
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
	$(OUTDIR)/paslangc -checkptr -o $(BUILDDIR)/fatal_cpstrview testdata/fatal/cpstrview.paslang; \
	set +e; $(BUILDDIR)/fatal_cpstrview > $(BUILDDIR)/fatal_cpstrview.got 2> $(BUILDDIR)/fatal_cpstrview.err; rc=$$?; set -e; \
	test $$rc -eq 1; \
	diff -u testdata/fatal/expected.out $(BUILDDIR)/fatal_cpstrview.got; \
	grep -q 'paslang: pointer outside its object at line 21' $(BUILDDIR)/fatal_cpstrview.err; \
	$(OUTDIR)/paslangc -checkptr -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/fatal_cpstrview-arm testdata/fatal/cpstrview.paslang; \
	set +e; timeout 60 $(QEMU_A64) $(BUILDDIR)/fatal_cpstrview-arm > $(BUILDDIR)/fatal_cpstrview-arm.got 2> $(BUILDDIR)/fatal_cpstrview-arm.err; rc=$$?; set -e; \
	test $$rc -eq 1; \
	diff -u testdata/fatal/expected.out $(BUILDDIR)/fatal_cpstrview-arm.got; \
	grep -q 'paslang: pointer outside its object at line 21' $(BUILDDIR)/fatal_cpstrview-arm.err; \
	for t in ptrarith ptrtyped memview ptrsafe gcbasic pchar narrowmem cpwalk ptrreach strview strshrink jsonlang jsonbind1 jsonbind2; do \
	  $(OUTDIR)/paslangc -checkptr -o $(BUILDDIR)/cpok_$$t testdata/$$t.paslang; \
	  $(BUILDDIR)/cpok_$$t > $(BUILDDIR)/cpok_$$t.got; \
	  diff -u testdata/$$t.out $(BUILDDIR)/cpok_$$t.got; \
	done; \
	$(OUTDIR)/paslangc -checkptr -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/cpok_jsonlang-arm testdata/jsonlang.paslang; \
	timeout 120 $(QEMU_A64) $(BUILDDIR)/cpok_jsonlang-arm > $(BUILDDIR)/cpok_jsonlang-arm.got; \
	diff -u testdata/jsonlang.out $(BUILDDIR)/cpok_jsonlang-arm.got; \
	$(OUTDIR)/paslangc -checkptr -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/cpok_cpwalk-arm testdata/cpwalk.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/cpok_cpwalk-arm > $(BUILDDIR)/cpok_cpwalk-arm.got; \
	diff -u testdata/cpwalk.out $(BUILDDIR)/cpok_cpwalk-arm.got; \
	$(OUTDIR)/paslangc -checkptr -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/cpok_strview-arm testdata/strview.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/cpok_strview-arm > $(BUILDDIR)/cpok_strview-arm.got; \
	diff -u testdata/strview.out $(BUILDDIR)/cpok_strview-arm.got; \
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
	echo ok checkptr
	@set -e; \
	: SQLite files the C library writes read as it reads them, P403; \
	python3 -I scripts/sqlfixtures.py $(BUILDDIR)/sqlfx; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/sqlread testdata/sqlread.paslang; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/sqlread0 testdata/sqlread.paslang; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/sqlread-base testdata/sqlread.paslang; \
	for d in p512 p1024 p4096 p8192 p65536 big wr u16le u16be nocase free; do \
	  $(BUILDDIR)/sqlread $(BUILDDIR)/sqlfx/$$d.db > $(BUILDDIR)/sqlfx/$$d.got; \
	  cmp $(BUILDDIR)/sqlfx/$$d.exp $(BUILDDIR)/sqlfx/$$d.got; \
	done; \
	for d in p512 p65536 wr u16be nocase free; do \
	  $(BUILDDIR)/sqlread0 $(BUILDDIR)/sqlfx/$$d.db > $(BUILDDIR)/sqlfx/$$d.got0; \
	  cmp $(BUILDDIR)/sqlfx/$$d.exp $(BUILDDIR)/sqlfx/$$d.got0; \
	  $(BUILDDIR)/sqlread-base $(BUILDDIR)/sqlfx/$$d.db > $(BUILDDIR)/sqlfx/$$d.gotb; \
	  cmp $(BUILDDIR)/sqlfx/$$d.exp $(BUILDDIR)/sqlfx/$$d.gotb; \
	done; \
	PASLANG_GCSTRESS=1 PASLANG_GCVERIFY=1 $(BUILDDIR)/sqlread0 $(BUILDDIR)/sqlfx/p1024.db > $(BUILDDIR)/sqlfx/p1024.gotgc; \
	cmp $(BUILDDIR)/sqlfx/p1024.exp $(BUILDDIR)/sqlfx/p1024.gotgc; \
	$(BUILDDIR)/sqlread $(BUILDDIR)/sqlfx/empty.db | grep -qx 'pagesize 4096 encoding 1 userversion 0'; \
	$(BUILDDIR)/sqlread $(BUILDDIR)/sqlfx/notadb.db notadb | grep -qx 'notadb 26 26 file is not a database'; \
	$(BUILDDIR)/sqlread x memory | grep -qx 'memory pages 0 objects 0'; \
	python3 -I scripts/check_sqllock.py $(BUILDDIR)/sqlread $(BUILDDIR)/sqlfx/wr.db; \
	echo ok sqlread
	@set -e; \
	: a unit item nothing reaches leaves the program, P417, and SQLite is the library unit sqlite, P418; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/gc_hello testdata/hello.paslang; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/gc_sqlnone testdata/sqlnone.paslang; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/gc_sqluses testdata/sqluses.paslang; \
	python3 -I scripts/check_gcsections.py $(BUILDDIR)/gc_hello $(BUILDDIR)/gc_sqlnone $(BUILDDIR)/gc_sqluses; \
	$(BUILDDIR)/gc_sqlnone | grep -qx 'names sqlite, reaches none of it'; \
	if $(OUTDIR)/paslangc -o $(BUILDDIR)/gc_sqlnouses testdata/sqlnouses.paslang > $(BUILDDIR)/gc_sqlnouses.err 2>&1; then \
	  echo 'sqlnouses: TSqlite with no uses sqlite should not compile'; exit 1; \
	fi; \
	grep -qF 'unknown type TSqlite at 7:7' $(BUILDDIR)/gc_sqlnouses.err; \
	echo ok gcsections
	@set -e; \
	: SQL read as the SQLite parser reads it, P404; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/sqlparse testdata/sqlparse.paslang; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/sqlparse0 testdata/sqlparse.paslang; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/sqlparse-base testdata/sqlparse.paslang; \
	$(BUILDDIR)/sqlparse testdata/sqlparse.sql > $(BUILDDIR)/sqlparse.got; \
	cmp testdata/sqlparse.out $(BUILDDIR)/sqlparse.got; \
	$(BUILDDIR)/sqlparse0 testdata/sqlparse.sql > $(BUILDDIR)/sqlparse.got0; \
	cmp testdata/sqlparse.out $(BUILDDIR)/sqlparse.got0; \
	$(BUILDDIR)/sqlparse-base testdata/sqlparse.sql > $(BUILDDIR)/sqlparse.gotb; \
	cmp testdata/sqlparse.out $(BUILDDIR)/sqlparse.gotb; \
	PASLANG_GCSTRESS=1 PASLANG_GCVERIFY=1 $(BUILDDIR)/sqlparse0 testdata/sqlparse.sql > $(BUILDDIR)/sqlparse.gotgc; \
	cmp testdata/sqlparse.out $(BUILDDIR)/sqlparse.gotgc; \
	echo ok sqlparse
	@set -e; \
	: SQLite whole, P405: every script of testdata/sqlite through the C interface as SQLite 3.54.1 answers it, on UTF-8 and UTF-16 databases, and its corpora; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/sqlapi testdata/sqlapi.paslang; \
	$(OUTDIR)/paslangc -cpu base -inline 0 -o $(BUILDDIR)/sqlapi0 testdata/sqlapi.paslang; \
	python3 -I scripts/check_sqlapi.py $(BUILDDIR)/sqlapi $(BUILDDIR)/sqlapi.d --corpus; \
	python3 -I scripts/check_sqlapi.py $(BUILDDIR)/sqlapi0 $(BUILDDIR)/sqlapi0.d; \
	PASLANG_GCSTRESS=1 PASLANG_GCVERIFY=1 python3 -I scripts/check_sqlapi.py $(BUILDDIR)/sqlapi0 $(BUILDDIR)/sqlapi0gc.d --only d1,j1,w2,v2,fn1,coll1; \
	: P411: the math functions on 20000 arguments each as SQLite on glibc 2.44 answers them, the FMA instruction and the integer FMA; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/sqlmath testdata/sqlmath.paslang; \
	$(OUTDIR)/paslangc -cpu base -inline 0 -o $(BUILDDIR)/sqlmath0 testdata/sqlmath.paslang; \
	$(BUILDDIR)/sqlmath > $(BUILDDIR)/sqlmath.got; \
	cmp testdata/sqlmath.out $(BUILDDIR)/sqlmath.got; \
	PASLANG_CPU=base $(BUILDDIR)/sqlmath > $(BUILDDIR)/sqlmath.gotb; \
	cmp testdata/sqlmath.out $(BUILDDIR)/sqlmath.gotb; \
	$(BUILDDIR)/sqlmath0 > $(BUILDDIR)/sqlmath.got0; \
	cmp testdata/sqlmath.out $(BUILDDIR)/sqlmath.got0; \
	: the unit beside the system SQLite on the same files, read back, killed in a commit, at once, checkpoints, a million rows; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/sqlcompat testdata/sqlcompat.paslang; \
	python3 -I scripts/check_sqlite.py $(BUILDDIR)/sqlcompat $(BUILDDIR)/sqlcompat.d; \
	: routines on one connection and on one file, Regla 11; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/sqlroutines testdata/sqlroutines.paslang; \
	rm -f $(BUILDDIR)/sqlroutines.db $(BUILDDIR)/sqlroutines.db-wal $(BUILDDIR)/sqlroutines.db-shm; \
	$(BUILDDIR)/sqlroutines $(BUILDDIR)/sqlroutines.db > $(BUILDDIR)/sqlroutines.got; \
	cmp testdata/sqlroutines.out $(BUILDDIR)/sqlroutines.got; \
	echo ok sqlapi
	@set -e; \
	: P439: signals on the base processor with no inlining, its children the program itself; \
	$(OUTDIR)/paslangc -cpu base -inline 0 -o $(BUILDDIR)/signals0 testdata/signals.paslang; \
	timeout 300 $(BUILDDIR)/signals0 > $(BUILDDIR)/signals0.got; \
	diff -u testdata/signals.out $(BUILDDIR)/signals0.got; \
	echo ok signals0
	@set -e; \
	: P434: the HTTP server on the base processor with no inlining, and the sockets systemd passes as sd_listen_fds gives them; \
	$(OUTDIR)/paslangc -cpu base -inline 0 -o $(BUILDDIR)/httpsrv0 testdata/httpsrv.paslang; \
	timeout 300 $(BUILDDIR)/httpsrv0 > $(BUILDDIR)/httpsrv0.got; \
	diff -u testdata/httpsrv.out $(BUILDDIR)/httpsrv0.got; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/httpsrv-sd testdata/httpsrv.paslang; \
	timeout 300 python3 -I scripts/check_httpsystemd.py $(BUILDDIR)/httpsrv-sd; \
	echo ok httpsrv0
	@set -e; \
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
	: the bit words on a pool register, P261: popcnt, lzcnt and tzcnt for x86-64-v3, and for the base the SWAR count, bsr and bsf; \
	$(OUTDIR)/paslangc -cpu v3 -o $(BUILDDIR)/bitwords_s testdata/bitwords.paslang; \
	sed -n '/^p_pool:/,/cfi_endproc/p' $(BUILDDIR)/bitwords_s.s > $(BUILDDIR)/bitwords_pool.s; \
	for i in 'popcntq %r' 'lzcntq %r' 'tzcntq %r' 'lzcntl %e' 'tzcntl %e' 'bswapq %r' 'rolw $$8, %'; do \
	  grep -qF -e "$$i" $(BUILDDIR)/bitwords_pool.s || { echo "bitwords pool lacks $$i"; exit 1; }; \
	done; \
	if grep -q 'bsf\|bsr' $(BUILDDIR)/bitwords_pool.s; then echo "bitwords pool for v3 has bsf or bsr"; exit 1; fi; \
	test $$(grep -c rt_haspopcnt $(BUILDDIR)/bitwords_s.s) -eq 0; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/bitwords_b testdata/bitwords.paslang; \
	sed -n '/^p_pool:/,/cfi_endproc/p' $(BUILDDIR)/bitwords_b.s > $(BUILDDIR)/bitwords_bpool.s; \
	test $$(grep -c popcnt $(BUILDDIR)/bitwords_bpool.s) -eq 0; \
	grep -qF -e 'movabsq $$6148914691236517205, %' $(BUILDDIR)/bitwords_bpool.s; \
	for i in 'bsfq %r' 'bsrq %r'; do \
	  grep -qF -e "$$i" $(BUILDDIR)/bitwords_bpool.s || { echo "bitwords base pool lacks $$i"; exit 1; }; \
	done; \
	if grep -q 'lzcnt\|tzcnt' $(BUILDDIR)/bitwords_bpool.s; then echo "bitwords pool for base has lzcnt or tzcnt"; exit 1; fi; \
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
	: the and, or and not of a condition as branches, P265: the same answers with every routine a call, and Digit two compares and two jumps; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/condjump0 testdata/condjump.paslang; \
	$(BUILDDIR)/condjump0 > $(BUILDDIR)/condjump0.got; \
	diff -u testdata/condjump.out $(BUILDDIR)/condjump0.got; \
	awk '/^p_digit:/,/ret$$/' $(BUILDDIR)/condjump.s > $(BUILDDIR)/condjump-digit.s; \
	grep -qE 'subq [$$]48, |leaq -48[(]' $(BUILDDIR)/condjump-digit.s && grep -q 'cmpq $$9, ' $(BUILDDIR)/condjump-digit.s && test $$(grep -cE '^  j(l|g|le|ge|a|be) ' $(BUILDDIR)/condjump-digit.s) -eq 1 || { echo "condjump.s: Digit's range is not one subtraction, one compare without sign and one jump (P292)"; exit 1; }; \
	if grep -q '^  set' $(BUILDDIR)/condjump-digit.s; then echo "condjump.s: Digit's condition makes a Boolean"; exit 1; fi; \
	echo ok condjump; \
	: the address of a var or const parameter in a register a run, P282: the sums under the stress of the collector, and every field read and written from that register, none from a pool register loaded from the slot; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=3 PASLANG_GCPOISON=1 $(BUILDDIR)/varparts > $(BUILDDIR)/varparts-gc.got; \
	diff -u testdata/varparts.out $(BUILDDIR)/varparts-gc.got; \
	for f in sum sumwhile sumconst bump; do \
	  awk "/^p_$$f:/,/ret\$$/" $(BUILDDIR)/varparts.s > $(BUILDDIR)/varparts-$$f.s; \
	  grep -qE '[0-9]\(%r(bx|9|1[0-5])\)' $(BUILDDIR)/varparts-$$f.s || { echo "varparts.s: $$f reads no field from a kept register"; exit 1; }; \
	  if grep -qE '[0-9]\(%r(si|di)\)' $(BUILDDIR)/varparts-$$f.s; then echo "varparts.s: $$f reads a field through a pool register"; exit 1; fi; \
	done; \
	echo ok varparts-asm; \
	: a while or a repeat that counts runs in runs, P283: Spin and Spin2 work out a run end of 1023 passes with a cmov, Spin3 and Others, which do not count, work out none and test at every pass, a cmov of theirs being an if made a select by P307; \
	for f in spin spin2; do \
	  awk "/^p_$$f:/,/ret\$$/" $(BUILDDIR)/whilerun.s | grep -A3 'leaq 1023(' | grep -q 'cmovgq' || { echo "whilerun.s: $$f does not run in runs"; exit 1; }; \
	done; \
	for f in spin3 others; do \
	  if awk "/^p_$$f:/,/ret\$$/" $(BUILDDIR)/whilerun.s | grep -q 'leaq 1023('; then echo "whilerun.s: $$f runs in runs"; exit 1; fi; \
	done; \
	echo ok whilerun-asm; \
	: a local or a Result written first starts as it is, P284: lazyzero under the stress and verify of the collector, and BothArms, CaseArms, ForBody and EarlyExit clear no slot of their frames; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 $(BUILDDIR)/lazyzero > $(BUILDDIR)/lazyzero-gc.got; \
	diff -u testdata/lazyzero.out $(BUILDDIR)/lazyzero-gc.got; \
	for f in botharms casearms forbody earlyexit; do \
	  if awk "/^p_$$f:/,/^\.set/" $(BUILDDIR)/lazyzero.s | grep -q 'movq \$$0, -'; then echo "lazyzero.s: $$f clears a slot"; exit 1; fi; \
	done; \
	echo ok lazyzero-gc; \
	: a small map under the stress and verify of the collector, P285, its counts of memory left out; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 $(BUILDDIR)/mapsmall nomem > $(BUILDDIR)/mapsmall-gc.got; \
	grep -v ' keys: ' testdata/mapsmall.out | diff -u - $(BUILDDIR)/mapsmall-gc.got; \
	echo ok mapsmall-gc; \
	: strings of one character under the stress and verify of the collector, P286, the count of memory left out; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 $(BUILDDIR)/strone nomem > $(BUILDDIR)/strone-gc.got; \
	grep -v 'strings of one character' testdata/strone.out | diff -u - $(BUILDDIR)/strone-gc.got; \
	echo ok strone-gc; \
	: slices grown, cut and copied under the stress and verify of the collector, P287, the count of memory left out; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 $(BUILDDIR)/slicefront nomem > $(BUILDDIR)/slicefront-gc.got; \
	grep -v '20000 slices' testdata/slicefront.out | diff -u - $(BUILDDIR)/slicefront-gc.got; \
	echo ok slicefront-gc; \
	: a leaf has no stack check and no frame, P288, nor a routine that calls nothing, P296, one that calls keeps both; \
	for f in twice thrice mix rot big three same konst tshape_area tshape_areak tshape_link; do \
	  if awk "/^p_$$f:/,/cfi_endproc/" $(BUILDDIR)/leafcall.s | grep -q 'cmpq 16(%r14)\|pushq %rbp'; then echo "leafcall.s: $$f has a stack check or a frame"; exit 1; fi; \
	done; \
	if awk '/^p_clamp:/,/cfi_endproc/' $(BUILDDIR)/leafcall.s | grep -q 'pushq %rbp'; then echo "leafcall.s: Clamp has a frame"; exit 1; fi; \
	if awk '/^p_clamp:/,/cfi_endproc/' $(BUILDDIR)/leafcall.s | grep -q 'cmpq 16(%r14)'; then echo "leafcall.s: Clamp has a stack check"; exit 1; fi; \
	awk '/^p_worker:/,/cfi_endproc/' $(BUILDDIR)/leafcall.s | grep -q 'cmpq 16(%r14)' || { echo "leafcall.s: Worker has no stack check"; exit 1; }; \
	echo ok leafcall-asm; \
	: an index its range proves in the array has no check, P289; \
	for f in masked modpos shifted onebased byteidx sumfor callmasked pairat tripleat; do \
	  if awk "/^p_$$f:/,/cfi_endproc/" $(BUILDDIR)/bceprove.s | grep -q rt_boundsfail; then echo "bceprove.s: $$f checks an index it proved"; exit 1; fi; \
	done; \
	echo ok bceprove-asm; \
	: a field of a record in the frame is its load or store operand from rbp, the record not formed again, P291; \
	test $$(awk '/^p_near:/,/cfi_endproc/' $(BUILDDIR)/framefield.s | grep -c 'leaq -[0-9]*(%rbp)') -le 1 || { echo "framefield.s: Near forms its record's address for its fields"; exit 1; }; \
	echo ok framefield-asm; \
	: a test of both ends of a range is one compare without sign, two ranges whose span overflows keep their compares, P292; \
	test $$(awk '/^p_bits:/,/cfi_endproc/' $(BUILDDIR)/rangetest.s | grep -cE '^  (ja|jbe|seta|setbe) ') -eq 13 || { echo "rangetest.s: Bits has not 13 ranges in one compare"; exit 1; }; \
	test $$(awk '/^p_narrow:/,/cfi_endproc/' $(BUILDDIR)/rangetest.s | grep -cE '^  (ja|jbe) ') -eq 8 || { echo "rangetest.s: Narrow has not 8 ranges in one compare"; exit 1; }; \
	echo ok rangetest-asm; \
	: a loop tests nothing at its passes, one CPU still runs the other routines, the collector stops a loop by a signal and reads its registers, and the pasasync table holds routines only, each past its stack check, P293; \
	test $$(awk '/^p_spin:/,/cfi_endproc/' $(BUILDDIR)/asyncspin.s | grep -c 'cmpq 16(%r14)') -le 1 || { echo "asyncspin.s: Spin tests the guard in its loop"; exit 1; }; \
	taskset -c 0 timeout 60 $(BUILDDIR)/asyncspin > $(BUILDDIR)/asyncspin-1.got; \
	diff -u testdata/asyncspin.out $(BUILDDIR)/asyncspin-1.got; \
	for w in "" "taskset -c 0"; do \
	  PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 $$w timeout 300 $(BUILDDIR)/asyncgc > $(BUILDDIR)/asyncgc-gc.got; \
	  diff -u testdata/asyncgc.out $(BUILDDIR)/asyncgc-gc.got; \
	done; \
	python3 -I scripts/check_pasasync.py $(BUILDDIR)/asyncgc; \
	python3 -I scripts/check_pasasync.py $(BUILDDIR)/sysguid; \
	: PASLANG_ASYNCPREEMPTOFF=1 stops nothing by a signal, so the wait of Walker never ends and the cycle waits for it, as under the asyncpreemptoff of Go; \
	rc=0; PASLANG_ASYNCPREEMPTOFF=1 PASLANG_GCSTRESS=1 timeout 5 $(BUILDDIR)/asyncgc > /dev/null 2>&1 || rc=$$?; \
	test $$rc -eq 124 || { echo "asyncgc: PASLANG_ASYNCPREEMPTOFF=1 still stops Walker (exit $$rc)"; exit 1; }; \
	: a leaf without a check of its own, a frame of 192 bytes or more, is stopped by a signal at every depth with its vector registers in a block of their own, P342; \
	test $$(awk '/^p_spin:/,/cfi_endproc/' $(BUILDDIR)/asyncleaf.s | grep -c 'cmpq 16(%r14)') -eq 0 || { echo "asyncleaf.s: Spin checks its stack"; exit 1; }; \
	test $$(sed -n 's/^\.set \.Lfrp_spin, //p' $(BUILDDIR)/asyncleaf.s) -ge 192 || { echo "asyncleaf.s: Spin's frame is under 192 bytes"; exit 1; }; \
	for w in "" "taskset -c 0"; do \
	  PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 $$w timeout 120 $(BUILDDIR)/asyncleaf > $(BUILDDIR)/asyncleaf-gc.got; \
	  diff -u testdata/asyncleaf.out $(BUILDDIR)/asyncleaf-gc.got; \
	done; \
	: a stop loads each vector register no wider than its saved bits ask, a movq for one with nothing from bit 64 on, so Zen still knows its upper bits clear, AMD 56305 2.11.5, P344; \
	test $$(awk '/^rt_asyncpreempt:/,/^rt_sigurg:/' $(BUILDDIR)/asyncgc.s | grep -cE '^  v?movq [0-9]+\(%rdx\), %xmm') -eq 16 || { echo "asyncgc.s: rt_asyncpreempt does not load its registers by movq"; exit 1; }; \
	test $$(awk '/^rt_yieldpoint:/,/^rt_xget:/' $(BUILDDIR)/asyncgc.s | grep -cE '^  v?movq [0-9]+\(%rdx\), %xmm') -eq 16 || { echo "asyncgc.s: rt_yieldpoint does not load its registers by movq"; exit 1; }; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/asyncgc-base testdata/asyncgc.paslang; \
	test $$(awk '/^rt_asyncpreempt:/,/^rt_sigurg:/' $(BUILDDIR)/asyncgc-base.s | grep -cE '^  movq [0-9]+\(%rdx\), %xmm') -eq 16 || { echo "asyncgc-base.s: rt_asyncpreempt does not load its registers by movq"; exit 1; }; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 timeout 300 $(BUILDDIR)/asyncgc-base > $(BUILDDIR)/asyncgc-base.got; \
	diff -u testdata/asyncgc.out $(BUILDDIR)/asyncgc-base.got; \
	echo ok async-asm; \
	: a word worked out in the pool lands in the register that reads it, an argument, a condition, a WriteLn operand, P328; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/argreg0 testdata/argreg.paslang; \
	$(BUILDDIR)/argreg0 > $(BUILDDIR)/argreg0.got; \
	diff -u testdata/argreg.out $(BUILDDIR)/argreg0.got; \
	python3 -I scripts/check_argreg.py $(BUILDDIR)/argreg0.s; \
	echo ok argreg-asm; \
	: several arguments worked out in the pool push nothing, a direct call, a method and a routine value, P332; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/manyargs0 testdata/manyargs.paslang; \
	$(BUILDDIR)/manyargs0 > $(BUILDDIR)/manyargs0.got; \
	diff -u testdata/manyargs.out $(BUILDDIR)/manyargs0.got; \
	python3 -I scripts/check_argpush.py $(BUILDDIR)/manyargs0.s; \
	echo ok manyargs-asm; \
	: every argument that calls nothing pushes nothing, elements, fields and divisions among them, P355; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/heldargs0 testdata/heldargs.paslang; \
	$(BUILDDIR)/heldargs0 > $(BUILDDIR)/heldargs0.got; \
	diff -u testdata/heldargs.out $(BUILDDIR)/heldargs0.got; \
	python3 -I scripts/check_argpush.py $(BUILDDIR)/heldargs0.s --routines=p_bydirect,p_bydirect5,p_bymethod,p_bymethode,p_byvalue,p_byvalue5,p_bymethval,p_byiface,p_bynested; \
	echo ok heldargs-asm; \
	: the value of a division lands in the register that reads it, its dividend in rax, P356; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/divreg0 testdata/divreg.paslang; \
	$(BUILDDIR)/divreg0 > $(BUILDDIR)/divreg0.got; \
	diff -u testdata/divreg.out $(BUILDDIR)/divreg0.got; \
	python3 -I scripts/check_divmove.py $(BUILDDIR)/divreg0.s --min=10; \
	echo ok divreg-asm; \
	: a nested routine reads and writes the variables of its outer routines in the pool, P357; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/uplevel0 testdata/uplevel.paslang; \
	$(BUILDDIR)/uplevel0 > $(BUILDDIR)/uplevel0.got; \
	diff -u testdata/uplevel.out $(BUILDDIR)/uplevel0.got; \
	python3 -I scripts/check_argpush.py $(BUILDDIR)/uplevel0.s --routines=p_outer_mid_deep; \
	echo ok uplevel-asm; \
	: a loop that calls keeps its variables in registers across the calls, P384, at -inline 0 and under the verify and stress modes of the collector; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/isles0 testdata/isles.paslang; \
	$(BUILDDIR)/isles0 > $(BUILDDIR)/isles0.got; \
	diff -u testdata/isles.out $(BUILDDIR)/isles0.got; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=3 PASLANG_GCPOISON=1 timeout 300 $(BUILDDIR)/isles0 > $(BUILDDIR)/isles0.vgot; \
	diff -u testdata/isles.out $(BUILDDIR)/isles0.vgot; \
	echo ok isles-asm; \
	: the address of a pointer element is one lea from the registers of the pointer and the index, and the loads and stores through it take them, P385; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/ptrelem0 testdata/ptrelem.paslang; \
	$(BUILDDIR)/ptrelem0 > $(BUILDDIR)/ptrelem0.got; \
	diff -u testdata/ptrelem.out $(BUILDDIR)/ptrelem0.got; \
	python3 -I scripts/check_ptrelem.py $(BUILDDIR)/ptrelem0.s; \
	echo ok ptrelem-asm; \
	: a store whose place is registers and a constant alone names it at once and pushes no value, P386; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/storereg0 testdata/storereg.paslang; \
	$(BUILDDIR)/storereg0 > $(BUILDDIR)/storereg0.got; \
	diff -u testdata/storereg.out $(BUILDDIR)/storereg0.got; \
	python3 -I scripts/check_storereg.py $(BUILDDIR)/storereg0.s; \
	echo ok storereg-asm; \
	: a comparison whose sides the pool cannot hold, as a condition, is one compare and one branch, no Boolean made and tested, P390; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/cmpdeep0 testdata/cmpdeep.paslang; \
	$(BUILDDIR)/cmpdeep0 > $(BUILDDIR)/cmpdeep0.got; \
	diff -u testdata/cmpdeep.out $(BUILDDIR)/cmpdeep0.got; \
	python3 -I scripts/check_cmpdeep.py $(BUILDDIR)/cmpdeep.s; \
	python3 -I scripts/check_cmpdeep.py $(BUILDDIR)/cmpdeep0.s; \
	echo ok cmpdeep-asm; \
	: an expression deeper than the pool keeps a left side in rdx while its right side is worked out in the pool, no push, P391; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/parkleft0 testdata/parkleft.paslang; \
	$(BUILDDIR)/parkleft0 > $(BUILDDIR)/parkleft0.got; \
	diff -u testdata/parkleft.out $(BUILDDIR)/parkleft0.got; \
	python3 -I scripts/check_parkleft.py $(BUILDDIR)/parkleft.s; \
	python3 -I scripts/check_parkleft.py $(BUILDDIR)/parkleft0.s; \
	echo ok parkleft-asm; \
	: an element of a slice from its place is worked out from the slice pointer and length alone, its capacity not loaded, P392; \
	python3 -I scripts/check_slicehead.py $(BUILDDIR)/slicehead.s; \
	echo ok slicehead-asm; \
	: a value of 0..255 against a constant set is a bit test of the set word, no push and no range check, P387; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/bytesetin0 testdata/bytesetin.paslang; \
	$(BUILDDIR)/bytesetin0 > $(BUILDDIR)/bytesetin0.got; \
	diff -u testdata/bytesetin.out $(BUILDDIR)/bytesetin0.got; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/bytesetin-base testdata/bytesetin.paslang; \
	$(BUILDDIR)/bytesetin-base > $(BUILDDIR)/bytesetin-base.got; \
	diff -u testdata/bytesetin.out $(BUILDDIR)/bytesetin-base.got; \
	python3 -I scripts/check_bytesetin.py $(BUILDDIR)/bytesetin.s; \
	python3 -I scripts/check_bytesetin.py $(BUILDDIR)/bytesetin0.s; \
	python3 -I scripts/check_bytesetin.py $(BUILDDIR)/bytesetin-base.s; \
	echo ok bytesetin-asm; \
	: a bit count of a value an if proved not zero is bsf or bsr alone under -cpu base, no sentinel, P394; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/bitnz-base testdata/bitnz.paslang; \
	$(BUILDDIR)/bitnz-base > $(BUILDDIR)/bitnz-base.got; \
	diff -u testdata/bitnz.out $(BUILDDIR)/bitnz-base.got; \
	$(OUTDIR)/paslangc -cpu base -inline 0 -o $(BUILDDIR)/bitnz-base0 testdata/bitnz.paslang; \
	$(BUILDDIR)/bitnz-base0 > $(BUILDDIR)/bitnz-base0.got; \
	diff -u testdata/bitnz.out $(BUILDDIR)/bitnz-base0.got; \
	python3 -I scripts/check_bitnz.py $(BUILDDIR)/bitnz-base.s; \
	python3 -I scripts/check_bitnz.py $(BUILDDIR)/bitnz-base0.s; \
	echo ok bitnz-asm; \
	: the straight code of a routine keeps its variables in registers across its calls, Move in a region, a zero only where a read may come first, P396; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/straight0 testdata/straight.paslang; \
	$(BUILDDIR)/straight0 > $(BUILDDIR)/straight0.got; \
	diff -u testdata/straight.out $(BUILDDIR)/straight0.got; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/straight-base testdata/straight.paslang; \
	$(BUILDDIR)/straight-base > $(BUILDDIR)/straight-base.got; \
	diff -u testdata/straight.out $(BUILDDIR)/straight-base.got; \
	$(OUTDIR)/paslangc -cpu base -inline 0 -o $(BUILDDIR)/straight-base0 testdata/straight.paslang; \
	$(BUILDDIR)/straight-base0 > $(BUILDDIR)/straight-base0.got; \
	diff -u testdata/straight.out $(BUILDDIR)/straight-base0.got; \
	PASLANG_GCSTRESS=1 PASLANG_GCVERIFY=1 $(BUILDDIR)/straight0 > $(BUILDDIR)/straight0-gc.got; \
	diff -u testdata/straight.out $(BUILDDIR)/straight0-gc.got; \
	python3 -I scripts/check_straight.py $(BUILDDIR)/straight.s; \
	python3 -I scripts/check_straight.py $(BUILDDIR)/straight0.s; \
	python3 -I scripts/check_straight.py $(BUILDDIR)/straight-base.s; \
	echo ok straight-asm; \
	: a word field of an object a register holds is one load where it lies, an operand of add and cmp, P397; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/regleaf0 testdata/regleaf.paslang; \
	$(BUILDDIR)/regleaf0 > $(BUILDDIR)/regleaf0.got; \
	diff -u testdata/regleaf.out $(BUILDDIR)/regleaf0.got; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/regleaf-base testdata/regleaf.paslang; \
	$(BUILDDIR)/regleaf-base > $(BUILDDIR)/regleaf-base.got; \
	diff -u testdata/regleaf.out $(BUILDDIR)/regleaf-base.got; \
	PASLANG_GCSTRESS=1 PASLANG_GCVERIFY=1 $(BUILDDIR)/regleaf0 > $(BUILDDIR)/regleaf0-gc.got; \
	diff -u testdata/regleaf.out $(BUILDDIR)/regleaf0-gc.got; \
	python3 -I scripts/check_regleaf.py $(BUILDDIR)/regleaf.s; \
	python3 -I scripts/check_regleaf.py $(BUILDDIR)/regleaf0.s; \
	python3 -I scripts/check_regleaf.py $(BUILDDIR)/regleaf-base.s; \
	echo ok regleaf-asm; \
	: Inc and Dec of a place in memory by a constant or a register are one add or sub with the place as its operand, P402; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/incplace0 testdata/incplace.paslang; \
	$(BUILDDIR)/incplace0 > $(BUILDDIR)/incplace0.got; \
	diff -u testdata/incplace.out $(BUILDDIR)/incplace0.got; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/incplace-base testdata/incplace.paslang; \
	$(BUILDDIR)/incplace-base > $(BUILDDIR)/incplace-base.got; \
	diff -u testdata/incplace.out $(BUILDDIR)/incplace-base.got; \
	python3 -I scripts/check_incplace.py $(BUILDDIR)/incplace.s; \
	python3 -I scripts/check_incplace.py $(BUILDDIR)/incplace0.s; \
	python3 -I scripts/check_incplace.py $(BUILDDIR)/incplace-base.s; \
	echo ok incplace-asm; \
	: an element of a slice an object field holds takes its pointer and length where they lie, no push, P398; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/sliceat0 testdata/sliceat.paslang; \
	$(BUILDDIR)/sliceat0 > $(BUILDDIR)/sliceat0.got; \
	diff -u testdata/sliceat.out $(BUILDDIR)/sliceat0.got; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/sliceat-base testdata/sliceat.paslang; \
	$(BUILDDIR)/sliceat-base > $(BUILDDIR)/sliceat-base.got; \
	diff -u testdata/sliceat.out $(BUILDDIR)/sliceat-base.got; \
	python3 -I scripts/check_sliceat.py $(BUILDDIR)/sliceat.s; \
	python3 -I scripts/check_sliceat.py $(BUILDDIR)/sliceat0.s; \
	python3 -I scripts/check_sliceat.py $(BUILDDIR)/sliceat-base.s; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/sliceoob testdata/sliceoob.paslang; \
	if $(BUILDDIR)/sliceoob > $(BUILDDIR)/sliceoob.got 2> $(BUILDDIR)/sliceoob.err; then echo "sliceoob ran past the end of its slice"; exit 1; fi; \
	diff -u testdata/sliceoob.out $(BUILDDIR)/sliceoob.got; \
	grep -q 'index 2 out of range \[0..1\] at line 25' $(BUILDDIR)/sliceoob.err; \
	echo ok sliceat-asm; \
	: Move whose arguments call nothing sets its three registers with no push, P399; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/moveregs0 testdata/moveregs.paslang; \
	$(BUILDDIR)/moveregs0 > $(BUILDDIR)/moveregs0.got; \
	diff -u testdata/moveregs.out $(BUILDDIR)/moveregs0.got; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/moveregs-base testdata/moveregs.paslang; \
	$(BUILDDIR)/moveregs-base > $(BUILDDIR)/moveregs-base.got; \
	diff -u testdata/moveregs.out $(BUILDDIR)/moveregs-base.got; \
	python3 -I scripts/check_moveregs.py $(BUILDDIR)/moveregs.s; \
	python3 -I scripts/check_moveregs.py $(BUILDDIR)/moveregs0.s; \
	python3 -I scripts/check_moveregs.py $(BUILDDIR)/moveregs-base.s; \
	echo ok moveregs-asm; \
	: a call in a statement goes first into a hidden variable and a call alone takes and leaves registers, P400; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/splitcall0 testdata/splitcall.paslang; \
	$(BUILDDIR)/splitcall0 > $(BUILDDIR)/splitcall0.got; \
	diff -u testdata/splitcall.out $(BUILDDIR)/splitcall0.got; \
	$(OUTDIR)/paslangc -cpu base -inline 0 -o $(BUILDDIR)/splitcall-base0 testdata/splitcall.paslang; \
	$(BUILDDIR)/splitcall-base0 > $(BUILDDIR)/splitcall-base0.got; \
	diff -u testdata/splitcall.out $(BUILDDIR)/splitcall-base0.got; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/splitcall-base testdata/splitcall.paslang; \
	$(BUILDDIR)/splitcall-base > $(BUILDDIR)/splitcall-base.got; \
	diff -u testdata/splitcall.out $(BUILDDIR)/splitcall-base.got; \
	PASLANG_GCSTRESS=1 PASLANG_GCVERIFY=1 $(BUILDDIR)/splitcall0 > $(BUILDDIR)/splitcall0-gc.got; \
	diff -u testdata/splitcall.out $(BUILDDIR)/splitcall0-gc.got; \
	python3 -I scripts/check_splitcall.py $(BUILDDIR)/splitcall0.s; \
	python3 -I scripts/check_splitcall.py $(BUILDDIR)/splitcall-base0.s; \
	echo ok splitcall-asm; \
	: a routine with nested ones zeroes only the locals a read may reach first, P358; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/nestzero0 testdata/nestzero.paslang; \
	$(BUILDDIR)/nestzero0 > $(BUILDDIR)/nestzero0.got; \
	diff -u testdata/nestzero.out $(BUILDDIR)/nestzero0.got; \
	python3 -I scripts/check_nestzero.py $(BUILDDIR)/nestzero0.s --expect=p_early:2,p_late:0,p_branch:2,p_writeback:1; \
	echo ok nestzero-asm
	@set -e; \
	: the asm checks go on in a recipe of their own, each under 64 KiB, P397; \
	: the left side of a binary operation waits in r11 while a right side that calls nothing is worked out, P360; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/keepleft0 testdata/keepleft.paslang; \
	$(BUILDDIR)/keepleft0 > $(BUILDDIR)/keepleft0.got; \
	diff -u testdata/keepleft.out $(BUILDDIR)/keepleft0.got; \
	python3 -I scripts/check_argpush.py $(BUILDDIR)/keepleft0.s --routines=p_bysum,p_bysub,p_bymul,p_byless,p_byatleast,p_bydiv,p_bymod,p_byouter_in1; \
	echo ok keepleft-asm; \
	: a closure or nested routine that calls nothing has no frame, its link kept in r10, P334; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/nestflat0 testdata/nestflat.paslang; \
	$(BUILDDIR)/nestflat0 > $(BUILDDIR)/nestflat0.got; \
	diff -u testdata/nestflat.out $(BUILDDIR)/nestflat0.got; \
	python3 -I scripts/check_nestflat.py $(BUILDDIR)/nestflat0.s --flat=p_outer_flatadd,p_outer_flatlocal,p_outer_flatbump,p_outer_mid_flatdeep,p_adder_anon.1 --framed=p_outer_mid,p_outer; \
	echo ok nestflat-asm; \
	: a routine with no frame works its value out in rax, P361; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/retreg0 testdata/retreg.paslang; \
	$(BUILDDIR)/retreg0 > $(BUILDDIR)/retreg0.got; \
	diff -u testdata/retreg.out $(BUILDDIR)/retreg0.got; \
	python3 -I scripts/check_retreg.py $(BUILDDIR)/retreg0.s --routines=p_sum2,p_scale,p_half,p_addg,p_early,p_makeadd_anon.1 --short=p_makeadd_anon.1:2,p_sum2:1,p_addg:2; \
	echo ok retreg-asm; \
	: a routine whose result is a block writes it into the buffer its caller gives in rax, P153; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/recres0 testdata/recres.paslang; \
	$(BUILDDIR)/recres0 > $(BUILDDIR)/recres0.got; \
	diff -u testdata/recres.out $(BUILDDIR)/recres0.got; \
	python3 -I scripts/check_resbuf.py $(BUILDDIR)/recres0.s --routines=p_mkmid,p_mkbig,p_mkset,p_mkodd,p_tshape_twice,p_tboxer_boxed,p_climb,p_wrap,p_anon.1 --dest=7; \
	python3 -I scripts/check_resbuf.py $(BUILDDIR)/recres0.s --regs=p_mkpair,p_swap,p_op_add_tpair_tpair,p_tshape_box,p_tshape_unit1,p_tshape_getcorner,p_tsquare_box,p_climb2,p_outer,p_risky,p_grow,p_outer_inner --short=p_mkpair:2; \
	echo ok recres-asm; \
	: a block of one to three words comes back in rax, rdx and r8, a Result of whole-word fields kept word by word, P366; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/regres0 testdata/regres.paslang; \
	$(BUILDDIR)/regres0 > $(BUILDDIR)/regres0.got; \
	diff -u testdata/regres.out $(BUILDDIR)/regres0.got; \
	python3 -I scripts/check_resbuf.py $(BUILDDIR)/regres0.s --regs=p_mkone,p_mkpair,p_rot,p_rot3,p_bump,p_pick,p_sum,p_twice,p_mknamed,p_mkpacked,p_mkreal,p_mkarr3,p_tcounter_pair,p_tcounter_tri --short=p_mkpair:2,p_rot:3,p_mkone:1; \
	echo ok regres-asm; \
	: a record written field by field before it is read starts with no zero, P367; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/fieldfirst0 testdata/fieldfirst.paslang; \
	$(BUILDDIR)/fieldfirst0 > $(BUILDDIR)/fieldfirst0.got; \
	diff -u testdata/fieldfirst.out $(BUILDDIR)/fieldfirst0.got; \
	python3 -I scripts/check_fieldfirst.py $(BUILDDIR)/fieldfirst0.s --zeros=p_full:0,p_both:0,p_part:2,p_readfirst:5,p_branch:5,p_early:5,p_gap:2,p_localsum:5; \
	echo ok fieldfirst-asm; \
	: a block assigned is copied as Move copies and zeroed as FillChar zeroes, with no test of a zero address, in line up to 128 bytes, P370; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/blockcopy1 testdata/blockcopy.paslang; \
	if grep -q 'stblob' $(BUILDDIR)/blockcopy1.s; then echo "blockcopy.s: a block store tests a zero address"; exit 1; fi; \
	if awk '/^p_t40:/,/cfi_endproc/' $(BUILDDIR)/blockcopy1.s | grep -qE 'call rt_memcpy|rep stosb'; then echo "blockcopy.s: T40 copies or zeroes out of line"; exit 1; fi; \
	if awk '/^p_t200:/,/cfi_endproc/' $(BUILDDIR)/blockcopy1.s | grep -q 'rep stosb'; then echo "blockcopy.s: T200 zeroes a variable with rep stosb"; exit 1; fi; \
	awk '/^p_t300:/,/cfi_endproc/' $(BUILDDIR)/blockcopy1.s | grep -q 'call rt_memcpy' || { echo "blockcopy.s: T300 copies no block with rt_memcpy"; exit 1; }; \
	echo ok blockcopy-asm; \
	: a routine whose result is a block goes in where it is called, a field of it read where Result came from, P368; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/blockinl1 testdata/blockinl.paslang; \
	grep -q 'movq v_g+120+16(%rip), %r' $(BUILDDIR)/blockinl1.s || { echo "blockinl.s: Get(4).C is not one load of G[4].C"; exit 1; }; \
	if awk '/^p_fresh:/,/cfi_endproc/' $(BUILDDIR)/blockinl1.s | grep -q 'call'; then echo "blockinl.s: Fresh calls"; exit 1; fi; \
	test $$(awk '/^pas_main:/,/cfi_endproc/' $(BUILDDIR)/blockinl1.s | grep -c 'call p_get$$') -eq 1 || { echo "blockinl.s: the main block does not call Get once"; exit 1; }; \
	if awk '/^pas_main:/,/cfi_endproc/' $(BUILDDIR)/blockinl1.s | grep -q 'call p_mkpair$$'; then echo "blockinl.s: the main block calls MkPair"; exit 1; fi; \
	echo ok blockinl-asm; \
	: a method called with the dispatch the compiler fixes goes in where it is called, its Self the object, a virtual one keeping its dispatch, P369; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/methinl1 testdata/methinl.paslang; \
	if awk '/^pas_main:/,/cfi_endproc/' $(BUILDDIR)/methinl1.s | grep -qE 'call p_tbox_(bump|add|twice)$$'; then echo "methinl.s: the main block calls Bump, Add or Twice"; exit 1; fi; \
	test $$(awk '/^pas_main:/,/cfi_endproc/' $(BUILDDIR)/methinl1.s | grep -c 'call \*') -eq 4 || { echo "methinl.s: the main block does not make its four virtual calls"; exit 1; }; \
	: the compiler, TypeOf put in place: IsStrTyp reads the Kind of the element of FTypes with no call; \
	if awk '/^p_pasparse_tparser_isstrtyp:/,/cfi_endproc/' $(BUILDDIR)/stage/pasparse.s | grep -q 'call p_pasparse_tparser_typeof'; then echo "pasparse.s: IsStrTyp calls TypeOf"; exit 1; fi; \
	echo ok methinl-asm; \
	: Result and the main block globals no routine names are operands a call put in place cannot change, so the call to their right goes in, and a global a routine writes or whose address is taken keeps its place, P371; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/aheadres1 testdata/aheadres.paslang; \
	if awk '/^pas_main:/,/cfi_endproc/' $(BUILDDIR)/aheadres1.s | grep -q 'call p_tri$$'; then echo "aheadres.s: the main block calls Tri"; exit 1; fi; \
	if awk '/^p_sumtri:/,/cfi_endproc/' $(BUILDDIR)/aheadres1.s | grep -q 'call p_'; then echo "aheadres.s: SumTri calls"; exit 1; fi; \
	if awk '/^p_acc:/,/cfi_endproc/' $(BUILDDIR)/aheadres1.s | grep -q 'call p_'; then echo "aheadres.s: Acc calls"; exit 1; fi; \
	awk '/^p_nested:/,/cfi_endproc/' $(BUILDDIR)/aheadres1.s | grep -q 'call p_tri$$' || { echo "aheadres.s: Nested, whose Result a nested routine names, put Tri ahead"; exit 1; }; \
	awk '/^pas_main:/,/cfi_endproc/' $(BUILDDIR)/aheadres1.s | grep -q 'call p_bump$$' || { echo "aheadres.s: g + Bump put Bump ahead"; exit 1; }; \
	awk '/^pas_main:/,/cfi_endproc/' $(BUILDDIR)/aheadres1.s | grep -q 'call p_incvia$$' || { echo "aheadres.s: w + IncVia put IncVia ahead"; exit 1; }; \
	echo ok aheadres-asm; \
	: the address of an element goes straight into the register that reads it, its index in the pool register that worked it out, P373; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/elemaddr1 testdata/elemaddr.paslang; \
	grep -q 'leaq v_g0(,%rsi,8), %rsi' $(BUILDDIR)/elemaddr1.s || { echo "elemaddr.s: an element of g0 is not worked out in rsi"; exit 1; }; \
	awk '/^p_runlocal:/,/cfi_endproc/' $(BUILDDIR)/elemaddr1.s | grep -qE 'leaq -[0-9]+\(%rbp,%rsi,8\), %rsi' || { echo "elemaddr.s: RunLocal works out no element in rsi"; exit 1; }; \
	echo ok elemaddr-asm; \
	: an index tested against both ends of a slice is one compare without sign and one branch, its length the word at 8 alone, P377; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/boundsidiom1 testdata/boundsidiom.paslang; \
	for f in ina outa inr inp zero; do \
	  awk "/^p_$$f:/,/cfi_endproc/" $(BUILDDIR)/boundsidiom1.s > $(BUILDDIR)/boundsidiom-$$f.s; \
	  test $$(grep -cE '^  (jb|jae) ' $(BUILDDIR)/boundsidiom-$$f.s) -eq 1 || { echo "boundsidiom.s: $$f is not one branch without sign"; exit 1; }; \
	  if grep -q 'set' $(BUILDDIR)/boundsidiom-$$f.s; then echo "boundsidiom.s: $$f makes a Boolean"; exit 1; fi; \
	done; \
	: the compiler, TypeOf put in place: its check in IsStrTyp makes no Boolean of its index against High, its own result the one setcc; \
	if awk '/^p_pasparse_tparser_isstrtyp:/,/cfi_endproc/' $(BUILDDIR)/stage/pasparse.s | grep -q 'setg %al'; then echo "pasparse.s: the check in IsStrTyp makes a Boolean"; exit 1; fi; \
	echo ok boundsidiom-asm; \
	: the hidden variables of bodies put in place share the frame slots their lives do not meet, a pointer slot with pointers only, P378; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/hidshare1 testdata/hidshare.paslang; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 $(BUILDDIR)/hidshare1 > $(BUILDDIR)/hidshare1.got; \
	diff -u testdata/hidshare.out $(BUILDDIR)/hidshare1.got; \
	f=$$(grep -o '\.set \.Lfrp_many, [0-9]*' $(BUILDDIR)/hidshare1.s | grep -o '[0-9]*$$'); \
	test "$$f" -le 128 || { echo "hidshare.s: Many takes $$f bytes of frame"; exit 1; }; \
	echo ok hidshare-asm; \
	: c + k * x and y + k * x are one lea, x := x + k * y one lea on the register of x, r13 and rbp are never the base of a lea with an index, and a load at p - k takes the offset, P294; \
	awk '/^p_off8:/,/cfi_endproc/' $(BUILDDIR)/leaform.s > $(BUILDDIR)/leaform-off8.s; \
	grep -q 'leaq 8(,%r[a-z0-9]*,8), ' $(BUILDDIR)/leaform-off8.s || { echo "leaform.s: Off8 is not one lea"; exit 1; }; \
	if grep -qE 'imulq|shlq|addq' $(BUILDDIR)/leaform-off8.s; then echo "leaform.s: Off8 multiplies, shifts or adds"; exit 1; fi; \
	awk '/^p_base:/,/cfi_endproc/' $(BUILDDIR)/leaform.s | grep -qE 'leaq \(%[a-z0-9]+,%[a-z0-9]+,4\)' || { echo "leaform.s: Base is not one lea"; exit 1; }; \
	test $$(awk '/^p_loop:/,/cfi_endproc/' $(BUILDDIR)/leaform.s | grep -cE 'leaq \(%[a-z0-9]+,%[a-z0-9]+,[248]\), ') -eq 4 || { echo "leaform.s: the loop of Loop has not four leas"; exit 1; }; \
	if grep -qE 'leaq [-0-9]*\(%(r13|rbp),%' $(BUILDDIR)/leaform.s; then echo "leaform.s: r13 or rbp is the base of a lea with an index"; exit 1; fi; \
	awk '/^p_back:/,/cfi_endproc/' $(BUILDDIR)/leaform.s > $(BUILDDIR)/leaform-back.s; \
	test $$(grep -cE 'movq -(8|16)\(%r(si|di|[0-9]+)\), ' $(BUILDDIR)/leaform-back.s) -eq 2 || { echo "leaform.s: Back does not load at p - 8 and p - 16"; exit 1; }; \
	if grep -qE 'subq \$$(8|16), ' $(BUILDDIR)/leaform-back.s; then echo "leaform.s: Back subtracts before it loads"; exit 1; fi; \
	echo ok leaform-asm; \
	: every failure of a check and every slow path that comes back is after the ret of its routine, so the fast path takes no branch, P299 and P300; \
	python3 -I scripts/check_cold.py $(BUILDDIR)/coldfail.s 40 boundsfail,divzero,sqrtneg,realrange,bitfail,setfail,funnelfail,asfail,strappendc,strunique,fillbig; \
	echo ok coldfail-asm; \
	: a loop whose only calls sit on slow paths keeps its variables in registers, P301: coldloop under the stress of the collector, and no loop of it calls or writes its frame; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 $(BUILDDIR)/coldloop > $(BUILDDIR)/coldloop-gc.got; \
	diff -u testdata/coldloop.out $(BUILDDIR)/coldloop-gc.got; \
	python3 -I scripts/check_coldloop.py $(BUILDDIR)/coldloop.s counted,twocounters,shared,global,walk,deep,wash,wipe,own; \
	echo ok coldloop-asm; \
	: a pointer a region keeps in a register is tested where it lives, P303: ptrwalk under the stress of the collector, and its walks test their pointer with a test of the register, never a compare with 0; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 $(BUILDDIR)/ptrwalk > $(BUILDDIR)/ptrwalk-gc.got; \
	diff -u testdata/ptrwalk.out $(BUILDDIR)/ptrwalk-gc.got; \
	for f in widths last zeros spell; do \
	  awk "/^p_$$f:/,/cfi_endproc/" $(BUILDDIR)/ptrwalk.s > $(BUILDDIR)/ptrwalk-$$f.s; \
	  grep -qE '^  testq %([a-z0-9]+), %\1$$' $(BUILDDIR)/ptrwalk-$$f.s || { echo "ptrwalk.s: $$f does not test its pointer in its register"; exit 1; }; \
	  if grep -qE 'cmpq \$$0, %' $(BUILDDIR)/ptrwalk-$$f.s; then echo "ptrwalk.s: $$f compares a register with 0"; exit 1; fi; \
	done; \
	echo ok ptrwalk-asm; \
	: no jump goes to the next instruction in any golden program, P305: an if without an else, the last arm of a case and an Exit that ends a routine fall through; \
	python3 -I scripts/check_nextjump.py $(foreach t,$(GOLDEN),$(BUILDDIR)/$(t).s); \
	echo ok nextjump; \
	: Move and FillChar of a constant count up to 128 bytes are loads and stores in line, P304: movefill under the stress of the collector, no call and no rep stosb for 1 to 128 bytes, rt_memcpy from 129; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 $(BUILDDIR)/movefill > $(BUILDDIR)/movefill-gc.got; \
	diff -u testdata/movefill.out $(BUILDDIR)/movefill-gc.got; \
	for f in c1 c3 c8 c16 c17 c100 c128 whole; do \
	  if awk "/^p_$$f:/,/cfi_endproc/" $(BUILDDIR)/movefill.s | grep -qE 'call rt_memcpy|rep stosb'; then echo "movefill.s: $$f calls rt_memcpy or fills with rep stosb"; exit 1; fi; \
	done; \
	: the processor decides past 128 bytes, P372, for the base one Move of 129 bytes calls rt_memcpy and no ymm register is named, with AVX, v3, up to 256 bytes are 32-byte words in line and vzeroupper, from 257 rt_memcpy; \
	$(OUTDIR)/paslangc -cpu base -o $(BUILDDIR)/movefill-base testdata/movefill.paslang; \
	$(BUILDDIR)/movefill-base > $(BUILDDIR)/movefill-base.got; \
	diff -u testdata/movefill.out $(BUILDDIR)/movefill-base.got; \
	awk '/^p_c129:/,/cfi_endproc/' $(BUILDDIR)/movefill-base.s | grep -q 'call rt_memcpy' || { echo "movefill-base.s: c129 does not call rt_memcpy"; exit 1; }; \
	if grep -q 'ymm' $(BUILDDIR)/movefill-base.s; then echo "movefill-base.s: a ymm register on the base processor"; exit 1; fi; \
	$(OUTDIR)/paslangc -cpu v3 -o $(BUILDDIR)/movefill-v3 testdata/movefill.paslang; \
	$(BUILDDIR)/movefill-v3 > $(BUILDDIR)/movefill-v3.got; \
	diff -u testdata/movefill.out $(BUILDDIR)/movefill-v3.got; \
	for f in c129 c200 c256; do \
	  if awk "/^p_$$f:/,/cfi_endproc/" $(BUILDDIR)/movefill-v3.s | grep -q 'call rt_memcpy'; then echo "movefill-v3.s: $$f calls rt_memcpy"; exit 1; fi; \
	  awk "/^p_$$f:/,/cfi_endproc/" $(BUILDDIR)/movefill-v3.s | grep -q 'vzeroupper' || { echo "movefill-v3.s: $$f leaves the upper halves dirty"; exit 1; }; \
	done; \
	awk '/^p_c257:/,/cfi_endproc/' $(BUILDDIR)/movefill-v3.s | grep -q 'call rt_memcpy' || { echo "movefill-v3.s: c257 does not call rt_memcpy"; exit 1; }; \
	echo ok movefill-asm; \
	: a constant an instruction can take is its immediate, P306: the routines of immconst load no such constant into a register first; \
	python3 -I scripts/check_immediates.py $(BUILDDIR)/immconst.s adds,logic,steps,cmps,chars,kind,arrays; \
	echo ok immconst-asm; \
	: a product by a constant is one or two shifts, adds or leas where that costs less than a multiply, P295: Ten multiplies nothing and Large still does; \
	if awk '/^p_ten:/,/cfi_endproc/' $(BUILDDIR)/mulconst.s | grep -q 'imulq'; then echo "mulconst.s: Ten multiplies"; exit 1; fi; \
	awk '/^p_large:/,/cfi_endproc/' $(BUILDDIR)/mulconst.s | grep -q 'imulq' || { echo "mulconst.s: Large does not multiply"; exit 1; }; \
	echo ok mulconst-asm; \
	: an if whose arms only assign a word is a compare and a CMOVcc as the branchelim of Go makes it, P307: selectif under the stress of the collector and without inlining, every if it marks select a CMOVcc and no jump, every one it marks branch a jump; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 $(BUILDDIR)/selectif > $(BUILDDIR)/selectif-gc.got; \
	diff -u testdata/selectif.out $(BUILDDIR)/selectif-gc.got; \
	python3 -I scripts/check_select.py $(BUILDDIR)/selectif.s testdata/selectif.paslang; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/selectif0 testdata/selectif.paslang; \
	$(BUILDDIR)/selectif0 > $(BUILDDIR)/selectif0.got; \
	diff -u testdata/selectif.out $(BUILDDIR)/selectif0.got; \
	python3 -I scripts/check_select.py $(BUILDDIR)/selectif0.s testdata/selectif.paslang; \
	echo ok selectif-asm; \
	: a lea of three components is two where the processor makes it slow, P298: leasplit tuned for skylake and haswell keeps no such lea in its code or its runtime, for icelake and zen3 they stay, the same output for each, and heapspan has no base of r13 beside an unscaled index with no displacement; \
	for c in skylake haswell icelake zen3; do \
	  $(OUTDIR)/paslangc -tune $$c -o $(BUILDDIR)/leasplit-$$c testdata/leasplit.paslang; \
	  $(BUILDDIR)/leasplit-$$c > $(BUILDDIR)/leasplit-$$c.got; \
	  diff -u testdata/leasplit.out $(BUILDDIR)/leasplit-$$c.got; \
	done; \
	python3 -I scripts/check_lea.py $(BUILDDIR)/leasplit-skylake.s slow; \
	python3 -I scripts/check_lea.py $(BUILDDIR)/leasplit-haswell.s slow; \
	: the counts kept whole are those after P311, whose field of an element takes no lea of its address any more, 8 fewer in Locals; \
	python3 -I scripts/check_lea.py $(BUILDDIR)/leasplit-icelake.s whole 15; \
	python3 -I scripts/check_lea.py $(BUILDDIR)/leasplit-zen3.s whole 16; \
	python3 -I scripts/check_lea.py $(BUILDDIR)/heapspan.s whole 1; \
	echo ok leasplit-asm; \
	: an element index is scaled by shifts and leas, never by a multiply by a power of two, P310: idxscale under the stress of the collector and without inlining, its routines Loc, Glob, Dyn, Ptr and Cut multiplying nothing; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 $(BUILDDIR)/idxscale > $(BUILDDIR)/idxscale-gc.got; \
	diff -u testdata/idxscale.out $(BUILDDIR)/idxscale-gc.got; \
	python3 -I scripts/check_scale.py $(BUILDDIR)/idxscale.s loc,glob,dyn,ptr,cut; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/idxscale0 testdata/idxscale.paslang; \
	$(BUILDDIR)/idxscale0 > $(BUILDDIR)/idxscale0.got; \
	diff -u testdata/idxscale.out $(BUILDDIR)/idxscale0.got; \
	python3 -I scripts/check_scale.py $(BUILDDIR)/idxscale0.s loc,glob,dyn,ptr,cut; \
	echo ok idxscale-asm; \
	: a field of an element is read and written through one address, P311: fieldaddr under the stress of the collector and without inlining, its routines Loc, Glob, Heap2, Ptr and Nest forming no element address before a field; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 $(BUILDDIR)/fieldaddr > $(BUILDDIR)/fieldaddr-gc.got; \
	diff -u testdata/fieldaddr.out $(BUILDDIR)/fieldaddr-gc.got; \
	python3 -I scripts/check_fieldaddr.py $(BUILDDIR)/fieldaddr.s loc,glob,heap2,ptr,nest; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/fieldaddr0 testdata/fieldaddr.paslang; \
	$(BUILDDIR)/fieldaddr0 > $(BUILDDIR)/fieldaddr0.got; \
	diff -u testdata/fieldaddr.out $(BUILDDIR)/fieldaddr0.got; \
	python3 -I scripts/check_fieldaddr.py $(BUILDDIR)/fieldaddr0.s loc,glob,heap2,ptr,nest; \
	echo ok fieldaddr-asm; \
	: every product by a constant takes its recipe, P312: the routines of modconst multiply by a constant only where no recipe of Go costs less, the remainder and a source in r13 included, with and without inlining; \
	python3 -I scripts/check_modconst.py $(BUILDDIR)/modconst.s; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/modconst0 testdata/modconst.paslang; \
	$(BUILDDIR)/modconst0 > $(BUILDDIR)/modconst0.got; \
	diff -u testdata/modconst.out $(BUILDDIR)/modconst0.got; \
	python3 -I scripts/check_modconst.py $(BUILDDIR)/modconst0.s; \
	echo ok modconst-asm; \
	: an index that is a sum takes its constant into the displacement, P313: the routines Run of idxsum add nothing to an index before its scale and multiply no index, with and without inlining; \
	python3 -I scripts/check_idxsum.py $(BUILDDIR)/idxsum.s run12,run20,run24,run28,run40,run48,run56; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/idxsum0 testdata/idxsum.paslang; \
	$(BUILDDIR)/idxsum0 > $(BUILDDIR)/idxsum0.got; \
	diff -u testdata/idxsum.out $(BUILDDIR)/idxsum0.got; \
	python3 -I scripts/check_idxsum.py $(BUILDDIR)/idxsum0.s run12,run20,run24,run28,run40,run48,run56; \
	echo ok idxsum-asm; \
	: the scaled index of an element once for its fields, P314: fieldcse under the stress of the collector and without inlining, Same and InHeap scaling once a loop body; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 $(BUILDDIR)/fieldcse > $(BUILDDIR)/fieldcse-gc.got; \
	diff -u testdata/fieldcse.out $(BUILDDIR)/fieldcse-gc.got; \
	python3 -I scripts/check_fieldcse.py $(BUILDDIR)/fieldcse.s same:2,inheap:4; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/fieldcse0 testdata/fieldcse.paslang; \
	$(BUILDDIR)/fieldcse0 > $(BUILDDIR)/fieldcse0.got; \
	diff -u testdata/fieldcse.out $(BUILDDIR)/fieldcse0.got; \
	python3 -I scripts/check_fieldcse.py $(BUILDDIR)/fieldcse0.s same:2,inheap:4; \
	echo ok fieldcse-asm; \
	: a bounds check an earlier one of the same index and length proves left out, P316: chkcse under the stress of the collector and without inlining, Fields checking once an element; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 $(BUILDDIR)/chkcse > $(BUILDDIR)/chkcse-gc.got; \
	diff -u testdata/chkcse.out $(BUILDDIR)/chkcse-gc.got; \
	python3 -I scripts/check_chkcse.py $(BUILDDIR)/chkcse.s fields:6,called:1,joined:3,moved:3,grown:3; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/chkcse0 testdata/chkcse.paslang; \
	$(BUILDDIR)/chkcse0 > $(BUILDDIR)/chkcse0.got; \
	diff -u testdata/chkcse.out $(BUILDDIR)/chkcse0.got; \
	python3 -I scripts/check_chkcse.py $(BUILDDIR)/chkcse0.s fields:6,joined:3,moved:3,grown:3; \
	echo ok chkcse-asm; \
	: a product by a constant under a narrowing conversion read from the register of the variable, P317: convmul with and without inlining; \
	python3 -I scripts/check_convmul.py $(BUILDDIR)/convmul.s; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/convmul0 testdata/convmul.paslang; \
	$(BUILDDIR)/convmul0 > $(BUILDDIR)/convmul0.got; \
	diff -u testdata/convmul.out $(BUILDDIR)/convmul0.got; \
	python3 -I scripts/check_convmul.py $(BUILDDIR)/convmul0.s; \
	echo ok convmul-asm; \
	: a variable a register keeps assigned in its register and a narrow one read in place, P318: regassign with and without inlining, no value moved into a variable and none through rax in its loops; \
	python3 -I scripts/check_regassign.py $(BUILDDIR)/regassign.s; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/regassign0 testdata/regassign.paslang; \
	$(BUILDDIR)/regassign0 > $(BUILDDIR)/regassign0.got; \
	diff -u testdata/regassign.out $(BUILDDIR)/regassign0.got; \
	python3 -I scripts/check_regassign.py $(BUILDDIR)/regassign0.s; \
	echo ok regassign-asm; \
	: a run head proving a slice by its length in a register or at its home, P319: runlen with and without inlining, the free bodies checking none; \
	python3 -I scripts/check_chkcse.py $(BUILDDIR)/runlen.s sum5:5,mix5:5,back:4,local5:10; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/runlen0 testdata/runlen.paslang; \
	$(BUILDDIR)/runlen0 > $(BUILDDIR)/runlen0.got; \
	diff -u testdata/runlen.out $(BUILDDIR)/runlen0.got; \
	python3 -I scripts/check_chkcse.py $(BUILDDIR)/runlen0.s sum5:5,mix5:5,back:4,local5:10; \
	echo ok runlen-asm; \
	: an and with a mask of 8, 16 or 32 bits as a zero extension from its source, P320: andmask with and without inlining, no AND of a mask in its routines; \
	python3 -I scripts/check_andmask.py $(BUILDDIR)/andmask.s; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/andmask0 testdata/andmask.paslang; \
	$(BUILDDIR)/andmask0 > $(BUILDDIR)/andmask0.got; \
	diff -u testdata/andmask.out $(BUILDDIR)/andmask0.got; \
	python3 -I scripts/check_andmask.py $(BUILDDIR)/andmask0.s; \
	echo ok andmask-asm; \
	: a constant from 0 to 2^32 - 1 into a register by a movl of 32 bits and 0 by an xorl where the flags die, P321: movconst with and without inlining, the runtime included; \
	python3 -I scripts/check_movconst.py $(BUILDDIR)/movconst.s; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/movconst0 testdata/movconst.paslang; \
	$(BUILDDIR)/movconst0 > $(BUILDDIR)/movconst0.got; \
	diff -u testdata/movconst.out $(BUILDDIR)/movconst0.got; \
	python3 -I scripts/check_movconst.py $(BUILDDIR)/movconst0.s; \
	echo ok movconst-asm; \
	: an and compared with 0 as one TEST or BT of its source, P322: andtest with and without inlining, no AND before a test of it with zero; \
	python3 -I scripts/check_andtest.py $(BUILDDIR)/andtest.s; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/andtest0 testdata/andtest.paslang; \
	$(BUILDDIR)/andtest0 > $(BUILDDIR)/andtest0.got; \
	diff -u testdata/andtest.out $(BUILDDIR)/andtest0.got; \
	python3 -I scripts/check_andtest.py $(BUILDDIR)/andtest0.s; \
	echo ok andtest-asm; \
	: a routine that calls nothing with its variables in registers and no frame, P296: flatproc with and without inlining; \
	python3 -I scripts/check_flatproc.py $(BUILDDIR)/flatproc.s --clamp=7; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/flatproc0 testdata/flatproc.paslang; \
	$(BUILDDIR)/flatproc0 > $(BUILDDIR)/flatproc0.got; \
	diff -u testdata/flatproc.out $(BUILDDIR)/flatproc0.got; \
	python3 -I scripts/check_flatproc.py $(BUILDDIR)/flatproc0.s --clamp=7; \
	echo ok flatproc-asm; \
	: a product by a constant no recipe takes as one imulq from the register or the home of its variable, P323: imulconst with and without inlining; \
	python3 -I scripts/check_imulconst.py $(BUILDDIR)/imulconst.s --three=30; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/imulconst0 testdata/imulconst.paslang; \
	$(BUILDDIR)/imulconst0 > $(BUILDDIR)/imulconst0.got; \
	diff -u testdata/imulconst.out $(BUILDDIR)/imulconst0.got; \
	python3 -I scripts/check_imulconst.py $(BUILDDIR)/imulconst0.s --three=30; \
	echo ok imulconst-asm; \
	: a check against a slice length at its home kept as one against a register, eight kept at a time, P324: memlen with and without inlining; \
	python3 -I scripts/check_chkcse.py $(BUILDDIR)/memlen.s rotate:6,pair:2; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/memlen0 testdata/memlen.paslang; \
	$(BUILDDIR)/memlen0 > $(BUILDDIR)/memlen0.got; \
	diff -u testdata/memlen.out $(BUILDDIR)/memlen0.got; \
	python3 -I scripts/check_chkcse.py $(BUILDDIR)/memlen0.s rotate:6,pair:2; \
	echo ok memlen-asm; \
	: calls through values push nothing and operands are read in their order, P297: callexpr with and without inlining; \
	python3 -I scripts/check_callexpr.py $(BUILDDIR)/callexpr.s; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/callexpr0 testdata/callexpr.paslang; \
	$(BUILDDIR)/callexpr0 > $(BUILDDIR)/callexpr0.got; \
	diff -u testdata/callexpr.out $(BUILDDIR)/callexpr0.got; \
	python3 -I scripts/check_callexpr.py $(BUILDDIR)/callexpr0.s; \
	echo ok callexpr-asm; \
	: a counter at its home read once a pass, P327: forstep with and without inlining; \
	python3 -I scripts/check_forstep.py $(BUILDDIR)/forstep.s --loops=0; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/forstep0 testdata/forstep.paslang; \
	$(BUILDDIR)/forstep0 > $(BUILDDIR)/forstep0.got; \
	diff -u testdata/forstep.out $(BUILDDIR)/forstep0.got; \
	python3 -I scripts/check_forstep.py $(BUILDDIR)/forstep0.s --loops=4; \
	echo ok forstep-asm; \
	: a value stored from registers while its place is worked out, P330: twostore with and without inlining; \
	python3 -I scripts/check_twostore.py $(BUILDDIR)/twostore.s; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/twostore0 testdata/twostore.paslang; \
	$(BUILDDIR)/twostore0 > $(BUILDDIR)/twostore0.got; \
	diff -u testdata/twostore.out $(BUILDDIR)/twostore0.got; \
	python3 -I scripts/check_twostore.py $(BUILDDIR)/twostore0.s; \
	echo ok twostore-asm; \
	: a value of two words loaded and stored at the element itself, P329: elemop with and without inlining; \
	python3 -I scripts/check_elemop.py $(BUILDDIR)/elemop.s --pairs=21; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/elemop0 testdata/elemop.paslang; \
	$(BUILDDIR)/elemop0 > $(BUILDDIR)/elemop0.got; \
	diff -u testdata/elemop.out $(BUILDDIR)/elemop0.got; \
	python3 -I scripts/check_elemop.py $(BUILDDIR)/elemop0.s --pairs=21; \
	echo ok elemop-asm; \
	: the exec lock around a new thread and an execve, clone again on EAGAIN, P333: the runtime in execrace; \
	python3 -I scripts/check_execlock.py $(BUILDDIR)/execrace.s; \
	echo ok execlock-asm; \
	: the same answers at every -inline, operands left to right, P326: inlineorder with -inline 0 and 200; \
	for n in 0 200; do \
	  $(OUTDIR)/paslangc -inline $$n -o $(BUILDDIR)/inlineorder$$n testdata/inlineorder.paslang; \
	  $(BUILDDIR)/inlineorder$$n > $(BUILDDIR)/inlineorder$$n.got; \
	  diff -u testdata/inlineorder.out $(BUILDDIR)/inlineorder$$n.got; \
	done; \
	echo ok inlineorder-inline; \
	: an unrolled loop stores its counter before each copy, P336: unrollctr with -inline 0 and 200; \
	for n in 0 200; do \
	  $(OUTDIR)/paslangc -inline $$n -o $(BUILDDIR)/unrollctr$$n testdata/unrollctr.paslang; \
	  $(BUILDDIR)/unrollctr$$n > $(BUILDDIR)/unrollctr$$n.got; \
	  diff -u testdata/unrollctr.out $(BUILDDIR)/unrollctr$$n.got; \
	done; \
	echo ok unrollctr-inline; \
	: every loop of an asm kernel of the units starts aligned, as the loops paslangc compiles, P302; \
	python3 -I scripts/check_kernel_align.py src/lib/*.paslang src/rtl/*.paslang; \
	echo ok kernel-align; \
	: every routine within the room its check gives, as the Go linker proves its nosplit chains, and the 144 bytes of a stop wherever a routine of the pasasync table runs, P342: the golden programs and the units; \
	python3 -I scripts/check_stack.py $(foreach t,$(GOLDEN),$(BUILDDIR)/$(t).s) $(foreach u,$(CORE_UNITS) $(LIB_UNITS),$(BUILDDIR)/$(basename $(notdir $(u))).s) --room=rt_yieldpoint,rt_asyncpreempt --async=144 --margin=64; \
	echo ok stack-room; \
	: the stack maps and the table of stops of every golden program and of the compiler in the order of their code as linked, as the Go linker writes its function table, P388; \
	python3 -I scripts/check_maporder.py $(foreach t,$(GOLDEN),$(BUILDDIR)/$(t)) $(OUTDIR)/paslangc; \
	echo ok map-order; \
	: a sleeping routine takes its record and first stack, P342; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/sleepers testdata/sleepers.paslang; \
	python3 -I scripts/check_routinemem.py $(BUILDDIR)/sleepers --limit=1440; \
	echo ok routinemem; \
	: a function of one expression goes in as its expression, P266: the output of every routine a call, and Branchy one compare and a select, P307, with no call of Less; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/exprinline0 testdata/exprinline.paslang; \
	$(BUILDDIR)/exprinline0 > $(BUILDDIR)/exprinline0.got; \
	diff -u testdata/exprinline.out $(BUILDDIR)/exprinline0.got; \
	awk '/^p_branchy:/,/ret$$/' $(BUILDDIR)/exprinline.s > $(BUILDDIR)/exprinline-branchy.s; \
	grep -q '^  cmovlq ' $(BUILDDIR)/exprinline-branchy.s || { echo "exprinline.s: Branchy is not a select on Less's compare"; exit 1; }; \
	if grep -q 'call p_less\|^  set' $(BUILDDIR)/exprinline-branchy.s; then echo "exprinline.s: Branchy calls Less or makes a Boolean"; exit 1; fi; \
	echo ok exprinline; \
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
	: an operator declared twice in one program or unit, and an interface operator with no body or with another result, are refused, P157; \
	if $(OUTDIR)/paslangc -c testdata/units/opmissu.paslang >$(BUILDDIR)/opmissu.err 2>&1; then \
	  echo 'an interface operator without a body should fail'; exit 1; \
	fi; \
	grep -q 'missing implementation of operator + on TV and TV' $(BUILDDIR)/opmissu.err; \
	if $(OUTDIR)/paslangc -c testdata/units/opbadu.paslang >$(BUILDDIR)/opbadu.err 2>&1; then \
	  echo 'an interface operator whose body returns another type should fail'; exit 1; \
	fi; \
	grep -q 'implementation does not match operator + on TV and TV at 15:10' $(BUILDDIR)/opbadu.err; \
	if $(OUTDIR)/paslangc -c testdata/units/opdupu.paslang >$(BUILDDIR)/opdupu.err 2>&1; then \
	  echo 'an interface operator declared twice should fail'; exit 1; \
	fi; \
	grep -q 'operator + on TV and TV declared twice at 12:10' $(BUILDDIR)/opdupu.err; \
	if $(OUTDIR)/paslangc -c testdata/units/opdup2u.paslang >$(BUILDDIR)/opdup2u.err 2>&1; then \
	  echo 'an interface operator with two bodies should fail'; exit 1; \
	fi; \
	grep -q 'operator + on TV and TV declared twice at 20:10' $(BUILDDIR)/opdup2u.err; \
	if $(OUTDIR)/paslangc -o $(BUILDDIR)/opdup testdata/opdup.paslang >$(BUILDDIR)/opdup.err 2>&1; then \
	  echo 'an operator with two bodies should fail'; exit 1; \
	fi; \
	grep -q 'operator + on TV and TV declared twice at 15:10' $(BUILDDIR)/opdup.err; \
	if $(OUTDIR)/paslangc -o $(BUILDDIR)/defaults_order testdata/defaults_order.paslang >$(BUILDDIR)/defaults_order.err 2>&1; then \
	  echo 'default before a required parameter should fail'; exit 1; \
	fi; \
	grep -q 'default parameters must be last' $(BUILDDIR)/defaults_order.err; \
	if $(OUTDIR)/paslangc -o $(BUILDDIR)/defaults_var testdata/defaults_var.paslang >$(BUILDDIR)/defaults_var.err 2>&1; then \
	  echo 'default on var should fail'; exit 1; \
	fi; \
	grep -q 'a var parameter takes no default value at ' $(BUILDDIR)/defaults_var.err; \
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
	:
	@set -e; \
	xrun=""; if [ -s $(BUILDDIR)/xvfb.display ]; then xrun="env DISPLAY=:$$(cat $(BUILDDIR)/xvfb.display)"; fi; \
	echo "==== units ===="; \
	$(OUTDIR)/paslangc testdata/units/adder.paslang; \
	$(OUTDIR)/paslangc testdata/units/dbl.paslang; \
	test -f $(BUILDDIR)/adder.pi; \
	test -f $(BUILDDIR)/dbl.pi; \
	grep -q PASLANGI34 $(BUILDDIR)/adder.pi; \
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
	: json through a unit P204: a variable, routines, a record, a class, a generic instance and a helper of the unit that hides TJsonHelper; \
	$(OUTDIR)/paslangc testdata/units/jsonu.paslang; \
	grep -q '^TYPE json [0-9]* 26 8 ' $(BUILDDIR)/jsonu.pi; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/jsonuse testdata/units/jsonuse.paslang; \
	$(BUILDDIR)/jsonuse > $(BUILDDIR)/jsonuse.got; \
	diff -u testdata/units/jsonuse.out $(BUILDDIR)/jsonuse.got; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=3 PASLANG_GCPOISON=1 $(BUILDDIR)/jsonuse > $(BUILDDIR)/jsonuse.got; \
	diff -u testdata/units/jsonuse.out $(BUILDDIR)/jsonuse.got; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/jsonu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/jsonuse-arm testdata/units/jsonuse.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/jsonuse-arm > $(BUILDDIR)/jsonuse-arm.got; \
	diff -u testdata/units/jsonuse.out $(BUILDDIR)/jsonuse-arm.got; \
	: a unit types written by the program that uses it, its json directives through the pi P205; \
	$(OUTDIR)/paslangc testdata/units/bindu.paslang; \
	grep -q '^FLD Name 0 3 0 5 s66756c6c206e616d65$$' $(BUILDDIR)/bindu.pi; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/bindmain testdata/units/bindmain.paslang; \
	$(BUILDDIR)/bindmain > $(BUILDDIR)/bindmain.got; \
	diff -u testdata/units/bindmain.out $(BUILDDIR)/bindmain.got; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/bindu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/bindmain-arm testdata/units/bindmain.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/bindmain-arm > $(BUILDDIR)/bindmain-arm.got; \
	diff -u testdata/units/bindmain.out $(BUILDDIR)/bindmain-arm.got; \
	: a unit types read by the program that uses it, private fields too, and the unit reading in its own routines P206; \
	$(OUTDIR)/paslangc testdata/units/jsondec.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/jsondecuse testdata/units/jsondecuse.paslang; \
	$(BUILDDIR)/jsondecuse > $(BUILDDIR)/jsondecuse.got; \
	diff -u testdata/units/jsondecuse.out $(BUILDDIR)/jsondecuse.got; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=3 PASLANG_GCPOISON=1 $(BUILDDIR)/jsondecuse > $(BUILDDIR)/jsondecuse.got; \
	diff -u testdata/units/jsondecuse.out $(BUILDDIR)/jsondecuse.got; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/jsondec.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/jsondecuse-arm testdata/units/jsondecuse.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/jsondecuse-arm > $(BUILDDIR)/jsondecuse-arm.got; \
	diff -u testdata/units/jsondecuse.out $(BUILDDIR)/jsondecuse-arm.got; \
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
	: TVisBase descends from TObject, type 18 after Currency, and has its 6 slots and 2 of its own: its Destroy is slot 0 P121; \
	grep -q '^CLASS 18 8 ' $(BUILDDIR)/visu.pi; \
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
	grep -q 'Pad is private to TStrTools.s unit at 9:13' $(BUILDDIR)/helppriv.err; \
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
	grep -q 'unknown identifier shada.Nope at 4:11' $(BUILDDIR)/shadbad.err; \
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
	: a unit .pi holds each type once, however long the chain of units before it: the eighth of a chain under twice the first, where it was 132 times, P460; \
	for i in 1 2 3 4 5 6 7 8; do \
	  $(OUTDIR)/paslangc -Fu $(BUILDDIR) testdata/units/pichain$$i.paslang; \
	  $(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) testdata/units/pichain$$i.paslang; \
	done; \
	for d in $(BUILDDIR) $(A64DIR); do \
	  a=$$(wc -c < $$d/pichain1.pi); z=$$(wc -c < $$d/pichain8.pi); \
	  if [ $$z -ge $$((2 * a)) ]; then echo "$$d/pichain8.pi has $$z bytes, pichain1.pi $$a: a .pi grows along a chain of units"; exit 1; fi; \
	  if [ $$(grep -c '^TYPE TSysError ' $$d/pichain8.pi) -ne 1 ]; then echo "$$d/pichain8.pi holds TSysError more than once"; exit 1; fi; \
	done; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/pichainuse testdata/units/pichainuse.paslang; \
	$(BUILDDIR)/pichainuse > $(BUILDDIR)/pichainuse.got; \
	diff -u testdata/units/pichainuse.out $(BUILDDIR)/pichainuse.got; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/pichainuse-arm testdata/units/pichainuse.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/pichainuse-arm > $(BUILDDIR)/pichainuse-arm.got; \
	diff -u testdata/units/pichainuse.out $(BUILDDIR)/pichainuse-arm.got; \
	: a chain of units gives one type of each record, TSysError and the records with methods of the units, whatever the order the program names them, P458; \
	for u in idchain1 idchain2 idchain3 idchain4 idsys1 idsys2 idsys3; do \
	  $(OUTDIR)/paslangc -Fu $(BUILDDIR) testdata/units/$$u.paslang; \
	  $(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) testdata/units/$$u.paslang; \
	done; \
	for p in idchainuse idchainuse2 idsysuse; do \
	  $(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/$$p testdata/units/$$p.paslang; \
	  $(BUILDDIR)/$$p > $(BUILDDIR)/$$p.got; \
	  diff -u testdata/units/$$p.out $(BUILDDIR)/$$p.got; \
	  $(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/$$p-arm testdata/units/$$p.paslang; \
	  timeout 60 $(QEMU_A64) $(BUILDDIR)/$$p-arm > $(BUILDDIR)/$$p-arm.got; \
	  diff -u testdata/units/$$p.out $(BUILDDIR)/$$p-arm.got; \
	done; \
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
	: absolute names a field of a global record, in a program and through a unit, P162; \
	$(OUTDIR)/paslangc testdata/units/absu.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/absuse testdata/units/absuse.paslang; \
	$(BUILDDIR)/absuse > $(BUILDDIR)/absuse.got; \
	diff -u testdata/units/absuse.out $(BUILDDIR)/absuse.got; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/absu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/absuse-arm testdata/units/absuse.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/absuse-arm > $(BUILDDIR)/absuse-arm.got; \
	diff -u testdata/units/absuse.out $(BUILDDIR)/absuse-arm.got; \
	: a routine hides the routines around it unless it is declared overload, P160; \
	for u in ovan ovao ovbn ovbo; do \
	  $(OUTDIR)/paslangc testdata/units/$$u.paslang; \
	  $(OUTDIR)/paslangc -target arm64 testdata/units/$$u.paslang; \
	done; \
	for p in ovuse1 ovuse2 ovuse3 ovuse4; do \
	  $(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/$$p testdata/units/$$p.paslang; \
	  $(BUILDDIR)/$$p > $(BUILDDIR)/$$p.got; \
	  diff -u testdata/units/$$p.out $(BUILDDIR)/$$p.got; \
	  $(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/$$p-arm testdata/units/$$p.paslang; \
	  timeout 60 $(QEMU_A64) $(BUILDDIR)/$$p-arm > $(BUILDDIR)/$$p-arm.got; \
	  diff -u testdata/units/$$p.out $(BUILDDIR)/$$p-arm.got; \
	done; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/ovbad testdata/units/ovbad.paslang > $(BUILDDIR)/ovbad.err 2>&1; then \
	  echo 'ovbad should fail'; exit 1; \
	fi; \
	grep -q 'a real does not go into Integer: Trunc or Round says how at 11:16' $(BUILDDIR)/ovbad.err; \
	: a nested routine hides the names around it, of a unit too, P159; \
	$(OUTDIR)/paslangc testdata/units/nestu.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/nestuse testdata/units/nestuse.paslang; \
	$(BUILDDIR)/nestuse > $(BUILDDIR)/nestuse.got; \
	diff -u testdata/units/nestuse.out $(BUILDDIR)/nestuse.got; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/nestu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/nestuse-arm testdata/units/nestuse.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/nestuse-arm > $(BUILDDIR)/nestuse-arm.got; \
	diff -u testdata/units/nestuse.out $(BUILDDIR)/nestuse-arm.got; \
	: records with methods and properties across a unit, and their private members, P165; \
	sh scripts/check_scoped_types.sh "$(OUTDIR)/paslangc" "$(BUILDDIR)" $(QEMU_A64); \
	python3 scripts/check_syscalls.py "$(OUTDIR)/paslangc" "$(BUILDDIR)" $(QEMU_A64); \
	: a stop asked for while a runtime lock is held leaves no saved register in the routine record, P363; \
	python3 scripts/check_nopre.py "$(OUTDIR)/paslangc" "$(BUILDDIR)" $(QEMU_A64); \
	: the standard streams keep the flags the program found, P217; \
	python3 scripts/check_stdstreams.py "$(OUTDIR)/paslangc" "$(BUILDDIR)" $(QEMU_A64); \
	: an alignment the emitter writes means bytes on both machines, P218; \
	python3 scripts/check_align.py "$(OUTDIR)/paslangc" "$(BUILDDIR)" $(QEMU_A64) $(CORE_UNITS); \
	python3 scripts/check_sysutils.py "$(OUTDIR)/paslangc" "$(BUILDDIR)" $(QEMU_A64); \
	python3 scripts/check_currency_language.py "$(OUTDIR)/paslangc" "$(BUILDDIR)" $(QEMU_A64); \
	: numbers as text, exact on both machines against the model and Go, P200; \
	python3 scripts/check_pasnum.py "$(OUTDIR)/paslangc" "$(BUILDDIR)" $(QEMU_A64); \
	for level in 0 40; do \
	  for cpu in native base; do \
	    $(OUTDIR)/paslangc -inline $$level -cpu $$cpu -Fu $(BUILDDIR) -o $(BUILDDIR)/currencykernelmodel testdata/currencykernelmodel.paslang; \
	    python3 scripts/check_currency.py $(BUILDDIR)/currencykernelmodel; \
	    $(OUTDIR)/paslangc -inline $$level -cpu $$cpu -Fu $(BUILDDIR) -o $(BUILDDIR)/currencyfrontendmodel testdata/currencyfrontendmodel.paslang; \
	    python3 scripts/check_currency.py --frontend $(BUILDDIR)/currencyfrontendmodel; \
	  done; \
	  for cpu in max base; do \
	    $(OUTDIR)/paslangc -target arm64 -inline $$level -cpu $$cpu -Fu $(A64DIR) -o $(BUILDDIR)/currencykernelmodel-arm testdata/currencykernelmodel.paslang; \
	    python3 scripts/check_currency.py $(QEMU_A64) $(BUILDDIR)/currencykernelmodel-arm; \
	    $(OUTDIR)/paslangc -target arm64 -inline $$level -cpu $$cpu -Fu $(A64DIR) -o $(BUILDDIR)/currencyfrontendmodel-arm testdata/currencyfrontendmodel.paslang; \
	    python3 scripts/check_currency.py --frontend $(QEMU_A64) $(BUILDDIR)/currencyfrontendmodel-arm; \
	  done; \
	done; \
	$(OUTDIR)/paslangc testdata/units/recu.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/recuse testdata/units/recuse.paslang; \
	$(BUILDDIR)/recuse > $(BUILDDIR)/recuse.got; \
	diff -u testdata/units/recuse.out $(BUILDDIR)/recuse.got; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/recu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/recuse-arm testdata/units/recuse.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/recuse-arm > $(BUILDDIR)/recuse-arm.got; \
	diff -u testdata/units/recuse.out $(BUILDDIR)/recuse-arm.got; \
	for p in recpriv1 recpriv2 recpriv3; do \
	  if $(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/$$p testdata/units/$$p.paslang > $(BUILDDIR)/$$p.err 2>&1; then \
	    echo "$$p should fail"; exit 1; \
	  fi; \
	done; \
	grep -q 'FPeak is private to TStack.s unit at 8:13' $(BUILDDIR)/recpriv1.err; \
	grep -q 'GetCount is private to TStack.s unit at 8:13' $(BUILDDIR)/recpriv2.err; \
	grep -q 'FCents is strict private to TMoney at 9:13' $(BUILDDIR)/recpriv3.err; \
	: the local clock under five zones, a TZif file each, against Go, P131; \
	: record class state and lifetime across a unit, P168 and P174; \
	for inl in 0 40; do \
	  for u in initinla initinlb; do $(OUTDIR)/paslangc -inline $$inl testdata/units/$$u.paslang; done; \
	  $(OUTDIR)/paslangc -inline $$inl -Fu $(BUILDDIR) -o $(BUILDDIR)/initinluse testdata/units/initinluse.paslang; \
	  $(BUILDDIR)/initinluse > $(BUILDDIR)/initinluse.got; \
	  diff -u testdata/units/initinluse.out $(BUILDDIR)/initinluse.got; \
	  for u in initinla initinlb; do $(OUTDIR)/paslangc -inline $$inl -target arm64 testdata/units/$$u.paslang; done; \
	  $(OUTDIR)/paslangc -inline $$inl -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/initinluse-arm testdata/units/initinluse.paslang; \
	  timeout 60 $(QEMU_A64) $(BUILDDIR)/initinluse-arm > $(BUILDDIR)/initinluse-arm.got; \
	  diff -u testdata/units/initinluse.out $(BUILDDIR)/initinluse-arm.got; \
	  $(OUTDIR)/paslangc -inline $$inl testdata/units/recsu.paslang; \
	  $(OUTDIR)/paslangc -inline $$inl -Fu $(BUILDDIR) -o $(BUILDDIR)/recsuse testdata/units/recsuse.paslang; \
	  $(BUILDDIR)/recsuse > $(BUILDDIR)/recsuse.got; \
	  diff -u testdata/units/recsuse.out $(BUILDDIR)/recsuse.got; \
	  $(OUTDIR)/paslangc -inline $$inl -target arm64 testdata/units/recsu.paslang; \
	  $(OUTDIR)/paslangc -inline $$inl -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/recsuse-arm testdata/units/recsuse.paslang; \
	  timeout 60 $(QEMU_A64) $(BUILDDIR)/recsuse-arm > $(BUILDDIR)/recsuse-arm.got; \
	  diff -u testdata/units/recsuse.out $(BUILDDIR)/recsuse-arm.got; \
	done; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/recspriv testdata/units/recspriv.paslang >$(BUILDDIR)/recspriv.err 2>&1; then \
	  echo 'a record class variable must remain private across a unit'; exit 1; \
	fi; \
	grep -qF 'FCount is private to TCache at 3:22' $(BUILDDIR)/recspriv.err; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/zone1 testdata/zone1.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/dates3 testdata/dates3.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/dates4 testdata/dates4.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/zone1-arm testdata/zone1.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/dates3-arm testdata/dates3.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/dates4-arm testdata/dates4.paslang; \
	for t in zone1 dates3 dates4; do \
	  : > $(BUILDDIR)/$$t.got; \
	  : > $(BUILDDIR)/$$t-arm.got; \
	  for z in Europe_Madrid America_New_York Asia_Kolkata Australia_Sydney Pacific_Chatham; do \
	    TZ=$(CURDIR)/testdata/zoneinfo/$$z $(BUILDDIR)/$$t >> $(BUILDDIR)/$$t.got; \
	    TZ=$(CURDIR)/testdata/zoneinfo/$$z timeout 60 $(QEMU_A64) $(BUILDDIR)/$$t-arm >> $(BUILDDIR)/$$t-arm.got; \
	  done; \
	  diff -u testdata/$$t.out $(BUILDDIR)/$$t.got; \
	  diff -u testdata/$$t.out $(BUILDDIR)/$$t-arm.got; \
	done; \
	: a pointer type is one type whichever unit brings it, both uses orders, P164; \
	$(OUTDIR)/paslangc testdata/units/ptra.paslang; \
	$(OUTDIR)/paslangc testdata/units/ptrb.paslang; \
	for p in ptrause ptrbuse; do \
	  $(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/$$p testdata/units/$$p.paslang; \
	  $(BUILDDIR)/$$p > $(BUILDDIR)/$$p.got; \
	  diff -u testdata/units/ptrause.out $(BUILDDIR)/$$p.got; \
	done; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/ptra.paslang; \
	$(OUTDIR)/paslangc -target arm64 testdata/units/ptrb.paslang; \
	for p in ptrause ptrbuse; do \
	  $(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/$$p-arm testdata/units/$$p.paslang; \
	  timeout 60 $(QEMU_A64) $(BUILDDIR)/$$p-arm > $(BUILDDIR)/$$p-arm.got; \
	  diff -u testdata/units/ptrause.out $(BUILDDIR)/$$p-arm.got; \
	done; \
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
	$(OUTDIR)/paslangc -cpu $(LVL_X64_CPU) -c -Fu $(BUILDDIR) -o $(BUILDDIR)/$(LVL_X64)/lvlu testdata/units/lvlu.paslang; \
	for c in base $(LVL_X64_CPU); do \
	  $(OUTDIR)/paslangc -cpu $$c -Fu $(BUILDDIR) -o $(BUILDDIR)/lvluse-$$c testdata/units/lvluse.paslang; \
	  $(BUILDDIR)/lvluse-$$c > $(BUILDDIR)/lvluse-$$c.got; \
	  diff -u testdata/units/lvluse.out $(BUILDDIR)/lvluse-$$c.got; \
	done; \
	objdump -d --no-show-raw-insn $(BUILDDIR)/lvluse-base | awk '/<p_lvlu_check>:/,/ret/' | grep -q pascrc32cbase; \
	objdump -d --no-show-raw-insn $(BUILDDIR)/lvluse-$(LVL_X64_CPU) | awk '/<p_lvlu_check>:/,/ret/' | grep -q pascrc32ccpu; \
	: a program for plain v3 lacks the level and links the base build, P465; \
	$(OUTDIR)/paslangc -cpu v3 -Fu $(BUILDDIR) -o $(BUILDDIR)/lvluse-v3plain testdata/units/lvluse.paslang; \
	objdump -d --no-show-raw-insn $(BUILDDIR)/lvluse-v3plain | awk '/<p_lvlu_check>:/,/ret/' | grep -q pascrc32cbase; \
	: pascipher at the amd64 level seals through AES-NI and PCLMULQDQ, P465; \
	grep -q 'aesenc %xmm1, %xmm0' $(BUILDDIR)/$(LVL_X64)/pascipher.s; \
	grep -q 'pclmulqdq' $(BUILDDIR)/$(LVL_X64)/pascipher.s; \
	for c in base $(LVL_X64_CPU); do \
	  $(OUTDIR)/paslangc -cpu $$c -o $(BUILDDIR)/sysutils1-$$c testdata/sysutils1.paslang; \
	  $(BUILDDIR)/sysutils1-$$c > $(BUILDDIR)/sysutils1-$$c.got; \
	  diff -u testdata/sysutils1.out $(BUILDDIR)/sysutils1-$$c.got; \
	done; \
	objdump -d --no-show-raw-insn $(BUILDDIR)/sysutils1-base | awk '/<p_sysutils_uppercase>:/,/ret/' | grep -q pasupperbase; \
	objdump -d --no-show-raw-insn $(BUILDDIR)/sysutils1-$(LVL_X64_CPU) | awk '/<p_sysutils_uppercase>:/,/ret/' | grep -q pasuppercpu; \
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
	sed '1s/PASLANGI34/PASLANGI1/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	cp $(BUILDDIR)/dbl.o $(BUILDDIR)/oldpi/; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.49 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.49; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI2/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.55 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.55; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI3/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.58 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.58; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI4/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.87 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.87; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI5/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.91 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.91; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI6/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.104 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.104; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI7/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.108 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.108; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI8/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.110 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.110; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI9/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.114 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.114; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI10/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.125 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.125; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI11/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.133 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.133; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI12/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.0.137 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.0.137; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI13/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.1.2 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.2; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI14/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.1.4 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.4; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI15/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.1.6 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.6; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI16/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.1.7 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.7; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI17/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.1.8 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.8; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI18/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.1.9 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.9; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI19/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.1.28 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.28; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI20/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from before 1.1.37 should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.37; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI21/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface without nested namespaces should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.44; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI22/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface without generic instance identity should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.47; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI23/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface without all type aliases should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.48; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI24/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface without Currency builtin identity should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.79; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI25/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface without the json type should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.124; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI26/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface without json directives should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.131; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI27/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface whose routines return blocks without a buffer should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.213; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI28/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface whose small blocks come back through a buffer should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.217; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI29/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface that does not carry its operators should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.230; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI30/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface that does not carry its records conversions should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.233; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI31/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface that does not carry its operators of one operand should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.234; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI32/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface whose object keeps its plain code maps in plain sections should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.244; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI33/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface whose types come again in each unit that reads it should be refused'; exit 1; \
	fi; \
	grep -q 'compiled by a paslang older than 1.1.274; compile dbl again' $(BUILDDIR)/oldpi.err; \
	sed '1s/PASLANGI34/PASLANGI35/' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'an interface from a later paslang should be refused'; exit 1; \
	fi; \
	grep -q 'was compiled by a newer paslang (PASLANGI35); compile dbl again with this one' $(BUILDDIR)/oldpi.err; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/pisum testdata/units/pisum.paslang; \
	sed 's/^TYPE Byte 6 1 1 /TYPE Byte 6 1 4 /' $(BUILDDIR)/dbl.pi > $(BUILDDIR)/oldpi/dbl.pi; \
	$(BUILDDIR)/pisum $(BUILDDIR)/oldpi/dbl.pi; \
	grep -q '^TYPE Byte 6 1 4 ' $(BUILDDIR)/oldpi/dbl.pi; \
	if $(OUTDIR)/paslangc -Fu $(BUILDDIR)/oldpi -o $(BUILDDIR)/oldpiuse testdata/units/main.paslang > $(BUILDDIR)/oldpi.err 2>&1; then \
	  echo 'a unit with other builtin types should be refused'; exit 1; \
	fi; \
	grep -q 'a compiled unit has other builtin types (Byte): compile it again' $(BUILDDIR)/oldpi.err; \
	echo ok units; \
	echo "==== a core unit missing ===="; \
	: a core unit whose interface is not found stops the compile with its name P279, and is never left out of the link; \
	rm -rf $(BUILDDIR)/nocore; mkdir -p $(BUILDDIR)/nocore/core; \
	cp $(BUILDDIR)/*.pi $(BUILDDIR)/*.o $(BUILDDIR)/nocore/core/; \
	rm -f $(BUILDDIR)/nocore/core/pashash.pi; \
	if (cd $(BUILDDIR)/nocore && $(CURDIR)/$(OUTDIR)/paslangc -Fu core -o hello $(CURDIR)/testdata/hello.paslang) > $(BUILDDIR)/nocore.err 2>&1; then \
	  echo 'a program without the core unit pashash should be refused'; exit 1; \
	fi; \
	grep -q 'the core unit pashash is missing: no pashash.pi in core, ' $(BUILDDIR)/nocore.err; \
	rm -rf $(BUILDDIR)/nocore; \
	echo ok nocore; \
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
	echo ok reguse
	@set -e; \
	xrun=""; if [ -s $(BUILDDIR)/xvfb.display ]; then xrun="env DISPLAY=:$$(cat $(BUILDDIR)/xvfb.display)"; fi; \
	echo "==== unit block results (P153) ===="; \
	$(OUTDIR)/paslangc testdata/units/blobu.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/blobuse testdata/units/blobuse.paslang; \
	$(BUILDDIR)/blobuse > $(BUILDDIR)/blobuse.got; \
	diff -u testdata/units/blobuse.out $(BUILDDIR)/blobuse.got; \
	echo ok blobuse; \
	echo "==== unit operators (P157) ===="; \
	$(OUTDIR)/paslangc testdata/units/opvecu.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) testdata/units/opcolu.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/opvecuse testdata/units/opvecuse.paslang; \
	$(BUILDDIR)/opvecuse > $(BUILDDIR)/opvecuse.got; \
	diff -u testdata/units/opvecuse.out $(BUILDDIR)/opvecuse.got; \
	test $$(grep -c '^OPER ' $(BUILDDIR)/opvecu.pi) -eq 5 || { echo "opvecu.pi does not carry its five operators"; exit 1; }; \
	if grep -q '^OPER div ' $(BUILDDIR)/opvecu.pi; then echo "opvecu.pi carries the div of its implementation"; exit 1; fi; \
	awk '/^pas_main:/,/cfi_endproc/' $(BUILDDIR)/opvecuse.s | grep -q 'call p_opcolu_op_lt_tvec_tvec$$' || { echo "opvecuse.s: the main block's < is not opcolu's"; exit 1; }; \
	echo ok opvecuse; \
	echo "==== a unit's class helper constructor (P170) ===="; \
	$(OUTDIR)/paslangc testdata/units/helpctoru.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/helpctoruse testdata/units/helpctoruse.paslang; \
	$(BUILDDIR)/helpctoruse > $(BUILDDIR)/helpctoruse.got; \
	diff -u testdata/units/helpctoruse.out $(BUILDDIR)/helpctoruse.got; \
	echo ok helpctoruse; \
	echo "==== a unit's record operators (P171) ===="; \
	$(OUTDIR)/paslangc testdata/units/recopsu.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/recopsuse testdata/units/recopsuse.paslang; \
	$(BUILDDIR)/recopsuse > $(BUILDDIR)/recopsuse.got; \
	diff -u testdata/units/recopsuse.out $(BUILDDIR)/recopsuse.got; \
	test $$(grep -c '^CONV ' $(BUILDDIR)/recopsu.pi) -eq 2 || { echo "recopsu.pi does not carry its two conversions"; exit 1; }; \
	test $$(grep -c '^OPER ' $(BUILDDIR)/recopsu.pi) -eq 2 || { echo "recopsu.pi does not carry its two operators"; exit 1; }; \
	echo ok recopsuse; \
	echo "==== a unit's operators of one operand (P381) ===="; \
	$(OUTDIR)/paslangc testdata/units/opunu.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/opunuse testdata/units/opunuse.paslang; \
	$(BUILDDIR)/opunuse > $(BUILDDIR)/opunuse.got; \
	diff -u testdata/units/opunuse.out $(BUILDDIR)/opunuse.got; \
	test $$(grep -c '^UNOP ' $(BUILDDIR)/opunu.pi) -eq 4 || { echo "opunu.pi does not carry its four operators of one operand"; exit 1; }; \
	grep -q '^OPER xor ' $(BUILDDIR)/opunu.pi || { echo "opunu.pi does not carry its xor"; exit 1; }; \
	echo ok opunuse; \
	echo "==== a unit's json constants (P209) ===="; \
	$(OUTDIR)/paslangc testdata/units/jsonconstu.paslang; \
	$(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/jsonconstuse testdata/units/jsonconstuse.paslang; \
	$(BUILDDIR)/jsonconstuse > $(BUILDDIR)/jsonconstuse.got; \
	diff -u testdata/units/jsonconstuse.out $(BUILDDIR)/jsonconstuse.got; \
	echo ok jsonconstuse; \
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
	: the same client on arm64 under qemu against the same server, P278: it made amd64 system calls there; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/xcanvas-arm testdata/xcanvas.paslang; \
	$$xrun timeout 120 $(QEMU_A64) $(BUILDDIR)/xcanvas-arm > $(BUILDDIR)/xcanvas-arm.got; \
	diff -u testdata/xcanvas.out $(BUILDDIR)/xcanvas-arm.got; \
	echo ok xcanvas-arm; \
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
	  'enumvar:duplicate identifier Green (a constant of the name) at 7:3' \
	  'nestprocvar:duplicate identifier X (a routine of the name) at 13:5'; do \
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
	for t in divzero nilptr deep oom oomlimit closed divloop bstatic bslice bstring bneg bempty bloop bref bnested bconst bstrcall bsame bslicereg bversion bslicehi bviewneg rrtrunc rrround rrfloor rrceil qtrunc qsqrt bitchk bitneg bitpool bitfield bitstr bitempty bitrec bitcall bitslice viewstr blkstr divover divzero128 funnelstr funnelslice mainraise raiseobj setelem setincl svneg svnil svmark svwrap exprarg leafnil bmaskwide bmodneg bmaskone bforpast bvarctr bnestctr bsumstat bsumdyn bsumneg bkeepfirst bkeepmoved bkeepstat bkeepshrunk brunlen brunloc divfirst idxline nilline bflatidx bflatpush nilblk nilbig nilzero nildest nilmeth elemidx jsonbusy jsonrbusy jsonwbusy divcall; do \
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
	grep -q 'paslang: integer divide by zero at line 15' $(BUILDDIR)/fatal_divfirst.err; \
	: P400: a division that stops the program comes before the call after it, put in place or not; \
	grep -q 'paslang: integer divide by zero at line 17' $(BUILDDIR)/fatal_divcall.err; \
	$(OUTDIR)/paslangc -inline 0 -o $(BUILDDIR)/fatal_divcall0 testdata/fatal/divcall.paslang; \
	set +e; $(BUILDDIR)/fatal_divcall0 > $(BUILDDIR)/fatal_divcall0.got 2> $(BUILDDIR)/fatal_divcall0.err; rc=$$?; set -e; \
	test $$rc -eq 1; \
	diff -u testdata/fatal/expected.out $(BUILDDIR)/fatal_divcall0.got; \
	grep -q 'paslang: integer divide by zero at line 17' $(BUILDDIR)/fatal_divcall0.err; \
	grep -q 'paslang: index 12 out of range \[0..9\] at line 15' $(BUILDDIR)/fatal_idxline.err; \
	grep -q 'paslang: nil pointer dereference at line 20' $(BUILDDIR)/fatal_nilline.err; \
	: P370: a block read or written through nil stops at its line, in line and past rt_memcpy and rt_fill; \
	grep -q 'paslang: nil pointer dereference at line 19' $(BUILDDIR)/fatal_nilblk.err; \
	grep -q 'paslang: nil pointer dereference at line 19' $(BUILDDIR)/fatal_nilbig.err; \
	grep -q 'paslang: nil pointer dereference at line 17' $(BUILDDIR)/fatal_nilzero.err; \
	grep -q 'paslang: nil pointer dereference at line 19' $(BUILDDIR)/fatal_nildest.err; \
	: P369: a method put in place on a nil object stops at the line of its call; \
	grep -q 'paslang: nil pointer dereference at line 24' $(BUILDDIR)/fatal_nilmeth.err; \
	: P373: an index kept in the pool register that worked it out reports its value; \
	grep -q 'paslang: index 9 out of range \[0..7\] at line 20' $(BUILDDIR)/fatal_elemidx.err; \
	grep -q 'paslang: nil pointer dereference at line 16' $(BUILDDIR)/fatal_nilptr.err; \
	grep -q 'paslang: nil pointer dereference at line 14' $(BUILDDIR)/fatal_leafnil.err; \
	grep -q 'paslang: index 100 out of range \[0..63\] at line 11' $(BUILDDIR)/fatal_bmaskwide.err; \
	grep -q 'paslang: index -5 out of range \[0..63\] at line 12' $(BUILDDIR)/fatal_bmodneg.err; \
	grep -q 'paslang: index 64 out of range \[0..63\] at line 11' $(BUILDDIR)/fatal_bmaskone.err; \
	grep -q 'paslang: index 64 out of range \[0..63\] at line 11' $(BUILDDIR)/fatal_bforpast.err; \
	grep -q 'paslang: index 50 out of range \[0..9\] at line 20' $(BUILDDIR)/fatal_bvarctr.err; \
	grep -q 'paslang: index 50 out of range \[0..9\] at line 21' $(BUILDDIR)/fatal_bnestctr.err; \
	: P313: an index v + c with v in a register reports v + c; \
	grep -q 'paslang: index 65 out of range \[1..64\] at line 15' $(BUILDDIR)/fatal_bsumstat.err; \
	grep -q 'paslang: index 10 out of range \[0..9\] at line 14' $(BUILDDIR)/fatal_bsumdyn.err; \
	grep -q 'paslang: index -4 out of range \[-3..20\] at line 17' $(BUILDDIR)/fatal_bsumneg.err; \
	: P316: the first of the checks of an element reports its index, and one is made again where the index or the length changed; \
	grep -q 'paslang: index 10 out of range \[0..9\] at line 17' $(BUILDDIR)/fatal_bkeepfirst.err; \
	grep -q 'paslang: index 10 out of range \[0..9\] at line 20' $(BUILDDIR)/fatal_bkeepmoved.err; \
	grep -q 'paslang: index 9 out of range \[1..8\] at line 20' $(BUILDDIR)/fatal_bkeepstat.err; \
	grep -q 'paslang: index 3 out of range \[0..2\] at line 15' $(BUILDDIR)/fatal_bkeepshrunk.err; \
	: P319: a run that does not fit a slice proved by its length at home runs the checked body, which reports the index; \
	grep -q 'paslang: index 30 out of range \[0..29\] at line 15' $(BUILDDIR)/fatal_brunlen.err; \
	grep -q 'paslang: index 1500 out of range \[0..1499\] at line 17' $(BUILDDIR)/fatal_brunloc.err; \
	: P296: an index past its array in a routine with no frame, nothing pushed or a register pushed, reports it; \
	grep -q 'paslang: index 10 out of range \[0..9\] at line 11' $(BUILDDIR)/fatal_bflatidx.err; \
	grep -q 'paslang: index -1 out of range \[0..9\] at line 14' $(BUILDDIR)/fatal_bflatpush.err; \
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
	grep -q 'paslang: index 9 out of range \[0..4\] at line 17' $(BUILDDIR)/fatal_exprarg.err; \
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
	grep -q 'paslang: concurrent json builder use' $(BUILDDIR)/fatal_jsonbusy.err; \
	grep -q 'paslang: concurrent json reader use' $(BUILDDIR)/fatal_jsonrbusy.err; \
	grep -q 'paslang: concurrent json writer use' $(BUILDDIR)/fatal_jsonwbusy.err; \
	grep -q 'paslang: index 4 out of range \[1..3\] at line 16' $(BUILDDIR)/fatal_bstrcall.err; \
	grep -q '^paslang: string view length -2 out of range$$' $(BUILDDIR)/fatal_svneg.err; \
	grep -q '^paslang: string view of nil with length 3$$' $(BUILDDIR)/fatal_svnil.err; \
	grep -q '^paslang: string view over bytes not marked shared$$' $(BUILDDIR)/fatal_svmark.err; \
	grep -q '^paslang: string view length 16 out of range$$' $(BUILDDIR)/fatal_svwrap.err; \
	echo ok fatal; \
	: P382 a broken standard output or error ends the program by SIGPIPE, 141, as in Go; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/brokenpipe_die testdata/brokenpipe.paslang; \
	(set +e; $(BUILDDIR)/brokenpipe_die out; echo $$? > $(BUILDDIR)/brokenpipe_out.rc) | head -c 1 > /dev/null; \
	(set +e; $(BUILDDIR)/brokenpipe_die err; echo $$? > $(BUILDDIR)/brokenpipe_err.rc) 2>&1 > /dev/null | head -c 1 > /dev/null; \
	test "`cat $(BUILDDIR)/brokenpipe_out.rc` `cat $(BUILDDIR)/brokenpipe_err.rc`" = "141 141"; \
	echo ok brokenpipe; \
	: P208 a reader parked while 32 routines parse, on one processor, and under the collector stress there; \
	$(OUTDIR)/paslangc -o $(BUILDDIR)/jsonpark1 testdata/jsonpark.paslang; \
	taskset -c 0 timeout 120 $(BUILDDIR)/jsonpark1 > $(BUILDDIR)/jsonpark1.got; \
	diff -u testdata/jsonpark.out $(BUILDDIR)/jsonpark1.got; \
	PASLANG_GCSTRESS=5 PASLANG_GCPOISON=1 taskset -c 0 timeout 120 $(BUILDDIR)/jsonpark1 > $(BUILDDIR)/jsonpark1.got; \
	diff -u testdata/jsonpark.out $(BUILDDIR)/jsonpark1.got; \
	echo ok jsonpark; \
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
	for t in hello values control routines varargs records scopedtypes classes registry helpers convert report money systemerrors boundedfiles filemetadata directories paths environments processes temporaryresources systempaths textbuilding textencoding textbuffers valuehelpers identifiers generics errors excobjects bank concurrent blockedio fanin maps sync wordcount strings maths narrow pointers single quad bits rotations carry bigrot bitfields wide atomics views vectors machine assembly hashes closures slices properties cleanup pipeline kvstore sorting timeout digest bitmap trees dates jsonread jsonwrite jsonlang jsonbind jsonunbind jsonstream; do \
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
	for t in httpd dnsd termd ftpd ntpd wsd chat proxy jsonrpc apisrv; do \
	  $(OUTDIR)/paslangc -Fu $(BUILDDIR) -o $(BUILDDIR)/ex_$$t examples/$$t.paslang; \
	  timeout 120 $(BUILDDIR)/ex_$$t -selftest 2000 > $(BUILDDIR)/ex_$$t.got; \
	  diff -u examples/$$t.out $(BUILDDIR)/ex_$$t.got; \
	  echo ok servers-$$t; \
	done; \
	python3 -I scripts/check_maporder.py $$(ls $(BUILDDIR)/ex_* | grep -v '[.][a-z]*$$'); \
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
	  rm -f $(BUILDDIR)/xvfb.pid $(BUILDDIR)/xvfb.display; \
	fi; \
	echo "==== stage ===="; \
	: the installed paslangc builds the sources when it is BOOT_MIN or later, as for bin/paslangc, else the one in bin/ does; \
	host="$(bindir)/paslangc"; v=""; \
	if [ -x "$$host" ]; then v=$$("$$host" -v 2>/dev/null | grep -o '[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*' | head -1); fi; \
	if [ -z "$$v" ] || ! printf '%s\n%s\n' "$(BOOT_MIN)" "$$v" | sort -V -C; then host="$(OUTDIR)/paslangc"; fi; \
	$(MAKE) stage HOST="$$host" STAGE="$(BUILDDIR)/paslangc-stage"; \
	echo "==== self ===="; \
	$(MAKE) self; \
	$(MAKE) check-arm64

# The arm64 tests run under QEMU's user mode built here, from the signed
# 11.1.1 release in docs/ref/qemu (fetched once, checked by its SHA-256)
# with the patches of scripts/qemu: QEMU 11.1.1 deadlocks a program that
# forks while another of its threads makes a system call (P226), fails
# MADV_GUARD_INSTALL, starts a thread with every host signal blocked
# (P302), and changes gdb's breakpoints while the other threads walk
# them (P349). The tests alone need it.
QEMU_A64 := $(BUILDDIR)/qemu-aarch64

$(BUILDDIR)/qemu-aarch64: scripts/build_qemu.py $(wildcard scripts/qemu/*.patch) | $(BUILDDIR)
	python3 scripts/build_qemu.py $(BUILDDIR) docs/ref/qemu/qemu-11.1.1.tar.xz

check-arm64: $(OUTDIR)/paslangc core-arm64 $(OUTDIR)/paslangc-arm64 $(BUILDDIR)/qemu-aarch64
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
	grep -q 'bl rt_strappendc$$' $(BUILDDIR)/strappend-arm.s || { echo "strappend-arm.s does not append a character through rt_strappendc"; exit 1; }; \
	grep -q 'bl rt_strappend$$' $(BUILDDIR)/strappend-arm.s || { echo "strappend-arm.s does not append a string through rt_strappend"; exit 1; }; \
	$(OUTDIR)/paslangc -target arm64 -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/condjump0-arm testdata/condjump.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/condjump0-arm > $(BUILDDIR)/condjump0-arm.got; \
	diff -u testdata/condjump.out $(BUILDDIR)/condjump0-arm.got; \
	awk '/^p_digit:/,/ret$$/' $(BUILDDIR)/condjump-arm.s > $(BUILDDIR)/condjump-digit-arm.s; \
	grep -qE 'sub x[0-9]+, x[0-9]+, #48' $(BUILDDIR)/condjump-digit-arm.s && grep -qE 'cmp x[0-9]+, #9$$' $(BUILDDIR)/condjump-digit-arm.s && test $$(grep -cE 'b[.](lt|gt|le|ge|hi|ls) ' $(BUILDDIR)/condjump-digit-arm.s) -eq 1 || { echo "condjump-arm.s: Digit's range is not one subtraction, one compare without sign and one branch (P292)"; exit 1; }; \
	if grep -q 'cset' $(BUILDDIR)/condjump-digit-arm.s; then echo "condjump-arm.s: Digit's condition makes a Boolean"; exit 1; fi; \
	for f in sum sumwhile sumconst bump; do \
	  awk "/^p_$$f:/,/ret\$$/" $(BUILDDIR)/varparts-arm.s > $(BUILDDIR)/varparts-$$f-arm.s; \
	  grep -qE '\[x(19|2[0-8])(, #[0-9]+)?\]' $(BUILDDIR)/varparts-$$f-arm.s || { echo "varparts-arm.s: $$f reads no field from a kept register"; exit 1; }; \
	  if grep -qE '\[x(9|1[0-7])(, #[0-9]+)?\]' $(BUILDDIR)/varparts-$$f-arm.s; then echo "varparts-arm.s: $$f reads a field through a pool register"; exit 1; fi; \
	done; \
	echo ok varparts-arm-asm; \
	for f in spin spin2; do \
	  awk "/^p_$$f:/,/ret\$$/" $(BUILDDIR)/whilerun-arm.s | grep -q 'csel x26' || { echo "whilerun-arm.s: $$f does not run in runs"; exit 1; }; \
	done; \
	for f in spin3 others; do \
	  if awk "/^p_$$f:/,/ret\$$/" $(BUILDDIR)/whilerun-arm.s | grep -qE '^  add x26, x[0-9]+, #1023$$'; then echo "whilerun-arm.s: $$f runs in runs"; exit 1; fi; \
	done; \
	echo ok whilerun-arm-asm; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 timeout 300 $(QEMU_A64) $(BUILDDIR)/lazyzero-arm > $(BUILDDIR)/lazyzero-arm-gc.got; \
	diff -u testdata/lazyzero.out $(BUILDDIR)/lazyzero-arm-gc.got; \
	for f in botharms casearms forbody earlyexit; do \
	  if awk "/^p_$$f:/,/cfi_endproc/" $(BUILDDIR)/lazyzero-arm.s | grep -q 'xzr, \[x29'; then echo "lazyzero-arm.s: $$f clears a slot"; exit 1; fi; \
	done; \
	echo ok lazyzero-arm-gc; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 timeout 300 $(QEMU_A64) $(BUILDDIR)/mapsmall-arm nomem > $(BUILDDIR)/mapsmall-arm-gc.got; \
	grep -v ' keys: ' testdata/mapsmall.out | diff -u - $(BUILDDIR)/mapsmall-arm-gc.got; \
	echo ok mapsmall-arm-gc; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 timeout 300 $(QEMU_A64) $(BUILDDIR)/strone-arm nomem > $(BUILDDIR)/strone-arm-gc.got; \
	grep -v 'strings of one character' testdata/strone.out | diff -u - $(BUILDDIR)/strone-arm-gc.got; \
	echo ok strone-arm-gc; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 timeout 300 $(QEMU_A64) $(BUILDDIR)/slicefront-arm nomem > $(BUILDDIR)/slicefront-arm-gc.got; \
	grep -v '20000 slices' testdata/slicefront.out | diff -u - $(BUILDDIR)/slicefront-arm-gc.got; \
	echo ok slicefront-arm-gc; \
	for f in twice thrice mix rot big three same konst tshape_area tshape_areak tshape_link; do \
	  if awk "/^p_$$f:/,/cfi_endproc/" $(BUILDDIR)/leafcall-arm.s | grep -q 'x28, #16\|stp x29, x30'; then echo "leafcall-arm.s: $$f has a stack check or a frame"; exit 1; fi; \
	done; \
	if awk '/^p_clamp:/,/cfi_endproc/' $(BUILDDIR)/leafcall-arm.s | grep -q 'stp x29, x30'; then echo "leafcall-arm.s: Clamp has a frame"; exit 1; fi; \
	if awk '/^p_clamp:/,/cfi_endproc/' $(BUILDDIR)/leafcall-arm.s | grep -q 'x28, #16'; then echo "leafcall-arm.s: Clamp has a stack check"; exit 1; fi; \
	awk '/^p_worker:/,/cfi_endproc/' $(BUILDDIR)/leafcall-arm.s | grep -q 'x28, #16' || { echo "leafcall-arm.s: Worker has no stack check"; exit 1; }; \
	echo ok leafcall-arm-asm; \
	for f in masked modpos shifted onebased byteidx sumfor callmasked pairat tripleat; do \
	  if awk "/^p_$$f:/,/cfi_endproc/" $(BUILDDIR)/bceprove-arm.s | grep -q rt_boundsfail; then echo "bceprove-arm.s: $$f checks an index it proved"; exit 1; fi; \
	done; \
	echo ok bceprove-arm-asm; \
	: a variable a register keeps is loaded, compared, stepped and masked where it lives, with the immediates arm64 takes, P290; \
	awk '/^p_digits:/,/cfi_endproc/' $(BUILDDIR)/armregs-arm.s > $(BUILDDIR)/armregs-digits-arm.s; \
	grep -qE 'ldrb w(19|2[0-8]), \[x(19|2[0-8]), x(19|2[0-8])' $(BUILDDIR)/armregs-digits-arm.s || { echo "armregs-arm.s: Digits does not load into its variable"; exit 1; }; \
	grep -qE 'sub x[0-9]+, x(19|2[0-8]), #48$$' $(BUILDDIR)/armregs-digits-arm.s || { echo "armregs-arm.s: Digits copies b before its range test (P290, P292)"; exit 1; }; \
	grep -qE 'add (x[0-9]+), \1, #1$$' $(BUILDDIR)/armregs-digits-arm.s || { echo "armregs-arm.s: Digits does not step k in place"; exit 1; }; \
	if awk '/p2align 5/{l=1} l{print} l&&/csel x26/{exit}' $(BUILDDIR)/armregs-digits-arm.s | grep -qE 'mov x[01], x(19|2[0-8])$$'; then echo "armregs-arm.s: the loop of Digits copies a kept register into x0 or x1"; exit 1; fi; \
	if awk '/p2align 5/{l=1} l{print} l&&/csel x26/{exit}' $(BUILDDIR)/armregs-digits-arm.s | grep -q 'x28, #16'; then echo "armregs-arm.s: the loop of Digits tests the guard (P293)"; exit 1; fi; \
	awk '/^p_imms:/,/cfi_endproc/' $(BUILDDIR)/armregs-arm.s | grep -qE 'sub x[0-9]+, x[0-9]+, #1, lsl #12' || { echo "armregs-arm.s: Imms does not take 4096 as an immediate"; exit 1; }; \
	awk '/^p_cmps:/,/cfi_endproc/' $(BUILDDIR)/armregs-arm.s | grep -qE 'cmn x[0-9]+, #4095' || { echo "armregs-arm.s: Cmps does not compare -4095 with cmn"; exit 1; }; \
	awk '/^p_loads:/,/cfi_endproc/' $(BUILDDIR)/armregs-arm.s | grep -qE 'and x[0-9]+, x[0-9]+, #0x0*3f' || { echo "armregs-arm.s: Loads does not mask i where it lives"; exit 1; }; \
	echo ok armregs-arm-asm; \
	if awk '/^p_near:/,/cfi_endproc/' $(BUILDDIR)/framefield-arm.s | grep -qE 'sub x(9|1[0-7]), x29'; then echo "framefield-arm.s: Near forms its record's address for its fields"; exit 1; fi; \
	echo ok framefield-arm-asm; \
	test $$(awk '/^p_bits:/,/cfi_endproc/' $(BUILDDIR)/rangetest-arm.s | grep -cE 'b[.](hi|ls) |cset x0, (hi|ls)') -eq 13 || { echo "rangetest-arm.s: Bits has not 13 ranges in one compare"; exit 1; }; \
	test $$(awk '/^p_narrow:/,/cfi_endproc/' $(BUILDDIR)/rangetest-arm.s | grep -cE 'b[.](hi|ls) ') -eq 8 || { echo "rangetest-arm.s: Narrow has not 8 ranges in one compare"; exit 1; }; \
	echo ok rangetest-arm-asm; \
	test $$(awk '/^p_spin:/,/cfi_endproc/' $(BUILDDIR)/asyncspin-arm.s | grep -c 'x28, #16') -le 1 || { echo "asyncspin-arm.s: Spin tests the guard in its loop"; exit 1; }; \
	taskset -c 0 timeout 120 $(QEMU_A64) $(BUILDDIR)/asyncspin-arm > $(BUILDDIR)/asyncspin-arm-1.got; \
	diff -u testdata/asyncspin.out $(BUILDDIR)/asyncspin-arm-1.got; \
	for w in "" "taskset -c 0"; do \
	  PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 $$w timeout 600 $(QEMU_A64) $(BUILDDIR)/asyncgc-arm > $(BUILDDIR)/asyncgc-arm-gc.got; \
	  diff -u testdata/asyncgc.out $(BUILDDIR)/asyncgc-arm-gc.got; \
	done; \
	python3 -I scripts/check_pasasync.py $(BUILDDIR)/asyncgc-arm; \
	rc=0; PASLANG_ASYNCPREEMPTOFF=1 PASLANG_GCSTRESS=1 timeout 15 $(QEMU_A64) $(BUILDDIR)/asyncgc-arm > /dev/null 2>&1 || rc=$$?; \
	test $$rc -eq 124 || { echo "asyncgc-arm: PASLANG_ASYNCPREEMPTOFF=1 still stops Walker (exit $$rc)"; exit 1; }; \
	test $$(awk '/^p_spin:/,/cfi_endproc/' $(BUILDDIR)/asyncleaf-arm.s | grep -c 'x28, #16') -eq 0 || { echo "asyncleaf-arm.s: Spin checks its stack"; exit 1; }; \
	test $$(awk '/^p_spin:/,/cfi_endproc/' $(BUILDDIR)/asyncleaf-arm.s | sed -n 's/^  sub sp, sp, #//p' | head -1) -ge 192 || { echo "asyncleaf-arm.s: Spin's frame is under 192 bytes"; exit 1; }; \
	for w in "" "taskset -c 0"; do \
	  PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 $$w timeout 300 $(QEMU_A64) $(BUILDDIR)/asyncleaf-arm > $(BUILDDIR)/asyncleaf-arm-gc.got; \
	  diff -u testdata/asyncleaf.out $(BUILDDIR)/asyncleaf-arm-gc.got; \
	done; \
	echo ok async-arm-asm; \
	: P328 on arm64: a word worked out in the pool lands in the register that reads it, WriteLn operands at the offset of sp; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/argreg0-arm testdata/argreg.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/argreg0-arm > $(BUILDDIR)/argreg0-arm.got; \
	diff -u testdata/argreg.out $(BUILDDIR)/argreg0-arm.got; \
	python3 -I scripts/check_argreg.py $(BUILDDIR)/argreg0-arm.s --arm; \
	echo ok argreg-arm-asm; \
	: P332 on arm64: several arguments worked out in the pool push nothing; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/manyargs0-arm testdata/manyargs.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/manyargs0-arm > $(BUILDDIR)/manyargs0-arm.got; \
	diff -u testdata/manyargs.out $(BUILDDIR)/manyargs0-arm.got; \
	python3 -I scripts/check_argpush.py $(BUILDDIR)/manyargs0-arm.s --arm; \
	echo ok manyargs-arm-asm; \
	: P355 on arm64: every argument that calls nothing pushes nothing; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/heldargs0-arm testdata/heldargs.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/heldargs0-arm > $(BUILDDIR)/heldargs0-arm.got; \
	diff -u testdata/heldargs.out $(BUILDDIR)/heldargs0-arm.got; \
	python3 -I scripts/check_argpush.py $(BUILDDIR)/heldargs0-arm.s --arm --routines=p_bydirect,p_bydirect5,p_bymethod,p_bymethode,p_byvalue,p_byvalue5,p_bymethval,p_byiface,p_bynested; \
	echo ok heldargs-arm-asm; \
	: P356 on arm64: a division on the registers of its operands, its value where it is read; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/divreg0-arm testdata/divreg.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/divreg0-arm > $(BUILDDIR)/divreg0-arm.got; \
	diff -u testdata/divreg.out $(BUILDDIR)/divreg0-arm.got; \
	python3 -I scripts/check_divmove.py $(BUILDDIR)/divreg0-arm.s --arm --min=10; \
	echo ok divreg-arm-asm; \
	: P357 on arm64: the variables of outer routines in the pool; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/uplevel0-arm testdata/uplevel.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/uplevel0-arm > $(BUILDDIR)/uplevel0-arm.got; \
	diff -u testdata/uplevel.out $(BUILDDIR)/uplevel0-arm.got; \
	python3 -I scripts/check_argpush.py $(BUILDDIR)/uplevel0-arm.s --arm --routines=p_outer_mid_deep; \
	echo ok uplevel-arm-asm; \
	: P384 on arm64: a loop that calls keeps its variables in x19 to x26, a try keeps them for its handler, and the runtime keeps them on both machines; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/isles0-arm testdata/isles.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/isles0-arm > $(BUILDDIR)/isles0-arm.got; \
	diff -u testdata/isles.out $(BUILDDIR)/isles0-arm.got; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=3 PASLANG_GCPOISON=1 timeout 300 $(QEMU_A64) $(BUILDDIR)/isles0-arm > $(BUILDDIR)/isles0-arm.vgot; \
	diff -u testdata/isles.out $(BUILDDIR)/isles0-arm.vgot; \
	python3 -I scripts/check_isles.py $(BUILDDIR)/isles0.s $(BUILDDIR)/isles0-arm.s; \
	python3 -I scripts/check_calleesaved.py $(BUILDDIR)/isles0.s $(BUILDDIR)/isles0-arm.s; \
	echo ok isles-arm-asm; \
	: P385 on arm64: the address of a pointer element is one add of the shifted register, and the loads and stores through it take the register offset; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/ptrelem0-arm testdata/ptrelem.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/ptrelem0-arm > $(BUILDDIR)/ptrelem0-arm.got; \
	diff -u testdata/ptrelem.out $(BUILDDIR)/ptrelem0-arm.got; \
	python3 -I scripts/check_ptrelem.py $(BUILDDIR)/ptrelem0-arm.s --arm; \
	echo ok ptrelem-arm-asm; \
	: P386 on arm64: a store whose place is registers and a constant alone names it at once and pushes no value; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/storereg0-arm testdata/storereg.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/storereg0-arm > $(BUILDDIR)/storereg0-arm.got; \
	diff -u testdata/storereg.out $(BUILDDIR)/storereg0-arm.got; \
	python3 -I scripts/check_storereg.py $(BUILDDIR)/storereg0-arm.s --arm; \
	echo ok storereg-arm-asm; \
	: P390 on arm64: a comparison deeper than the pool, as a condition, is one compare and one branch; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/cmpdeep0-arm testdata/cmpdeep.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/cmpdeep0-arm > $(BUILDDIR)/cmpdeep0-arm.got; \
	diff -u testdata/cmpdeep.out $(BUILDDIR)/cmpdeep0-arm.got; \
	python3 -I scripts/check_cmpdeep.py $(BUILDDIR)/cmpdeep-arm.s --arm; \
	python3 -I scripts/check_cmpdeep.py $(BUILDDIR)/cmpdeep0-arm.s --arm; \
	echo ok cmpdeep-arm-asm; \
	: P391 on arm64: an expression deeper than the pool keeps a left side in the pool top register, no push; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/parkleft0-arm testdata/parkleft.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/parkleft0-arm > $(BUILDDIR)/parkleft0-arm.got; \
	diff -u testdata/parkleft.out $(BUILDDIR)/parkleft0-arm.got; \
	python3 -I scripts/check_parkleft.py $(BUILDDIR)/parkleft-arm.s --arm; \
	python3 -I scripts/check_parkleft.py $(BUILDDIR)/parkleft0-arm.s --arm; \
	echo ok parkleft-arm-asm; \
	: P392 on arm64: one LDP of a slice pointer and length for its element, no load of its capacity; \
	python3 -I scripts/check_slicehead.py $(BUILDDIR)/slicehead-arm.s --arm; \
	echo ok slicehead-arm-asm; \
	: P387 on arm64: a value of 0..255 against a constant set is an lsr of the set word, no push; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/bytesetin0-arm testdata/bytesetin.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/bytesetin0-arm > $(BUILDDIR)/bytesetin0-arm.got; \
	diff -u testdata/bytesetin.out $(BUILDDIR)/bytesetin0-arm.got; \
	python3 -I scripts/check_bytesetin.py $(BUILDDIR)/bytesetin-arm.s --arm; \
	python3 -I scripts/check_bytesetin.py $(BUILDDIR)/bytesetin0-arm.s --arm; \
	echo ok bytesetin-arm-asm; \
	: P394 on arm64: the narrow trailing count of a value an if proved not zero takes no sentinel bit; \
	python3 -I scripts/check_bitnz.py $(BUILDDIR)/bitnz-arm.s --arm; \
	echo ok bitnz-arm-asm; \
	: P396 on arm64: the straight code of a routine keeps its variables in x19 to x26 across its calls; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/straight0-arm testdata/straight.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/straight0-arm > $(BUILDDIR)/straight0-arm.got; \
	diff -u testdata/straight.out $(BUILDDIR)/straight0-arm.got; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -Fu $(A64DIR) -o $(BUILDDIR)/straight-base-arm testdata/straight.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/straight-base-arm > $(BUILDDIR)/straight-base-arm.got; \
	diff -u testdata/straight.out $(BUILDDIR)/straight-base-arm.got; \
	PASLANG_GCSTRESS=1 PASLANG_GCVERIFY=1 timeout 600 $(QEMU_A64) $(BUILDDIR)/straight0-arm > $(BUILDDIR)/straight0-arm-gc.got; \
	diff -u testdata/straight.out $(BUILDDIR)/straight0-arm-gc.got; \
	python3 -I scripts/check_straight.py $(BUILDDIR)/straight-arm.s --arm; \
	python3 -I scripts/check_straight.py $(BUILDDIR)/straight0-arm.s --arm; \
	echo ok straight-arm-asm; \
	: P397 on arm64: a word field of an object a register holds is one ldr at an offset from that register; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/regleaf0-arm testdata/regleaf.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/regleaf0-arm > $(BUILDDIR)/regleaf0-arm.got; \
	diff -u testdata/regleaf.out $(BUILDDIR)/regleaf0-arm.got; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -Fu $(A64DIR) -o $(BUILDDIR)/regleaf-base-arm testdata/regleaf.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/regleaf-base-arm > $(BUILDDIR)/regleaf-base-arm.got; \
	diff -u testdata/regleaf.out $(BUILDDIR)/regleaf-base-arm.got; \
	python3 -I scripts/check_regleaf.py $(BUILDDIR)/regleaf-arm.s --arm; \
	python3 -I scripts/check_regleaf.py $(BUILDDIR)/regleaf0-arm.s --arm; \
	echo ok regleaf-arm-asm; \
	: P402 on arm64: Inc and Dec of a place in memory load, add and store at the place, nothing pushed; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/incplace0-arm testdata/incplace.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/incplace0-arm > $(BUILDDIR)/incplace0-arm.got; \
	diff -u testdata/incplace.out $(BUILDDIR)/incplace0-arm.got; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -Fu $(A64DIR) -o $(BUILDDIR)/incplace-base-arm testdata/incplace.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/incplace-base-arm > $(BUILDDIR)/incplace-base-arm.got; \
	diff -u testdata/incplace.out $(BUILDDIR)/incplace-base-arm.got; \
	python3 -I scripts/check_incplace.py $(BUILDDIR)/incplace-arm.s --arm; \
	python3 -I scripts/check_incplace.py $(BUILDDIR)/incplace0-arm.s --arm; \
	echo ok incplace-arm-asm; \
	: P398 on arm64: an element of a slice an object field holds loads its pointer and length at an offset, no push; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/sliceat0-arm testdata/sliceat.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/sliceat0-arm > $(BUILDDIR)/sliceat0-arm.got; \
	diff -u testdata/sliceat.out $(BUILDDIR)/sliceat0-arm.got; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -Fu $(A64DIR) -o $(BUILDDIR)/sliceat-base-arm testdata/sliceat.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/sliceat-base-arm > $(BUILDDIR)/sliceat-base-arm.got; \
	diff -u testdata/sliceat.out $(BUILDDIR)/sliceat-base-arm.got; \
	python3 -I scripts/check_sliceat.py $(BUILDDIR)/sliceat-arm.s --arm; \
	python3 -I scripts/check_sliceat.py $(BUILDDIR)/sliceat0-arm.s --arm; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -Fu $(A64DIR) -o $(BUILDDIR)/sliceoob-arm testdata/sliceoob.paslang; \
	if timeout 300 $(QEMU_A64) $(BUILDDIR)/sliceoob-arm > $(BUILDDIR)/sliceoob-arm.got 2> $(BUILDDIR)/sliceoob-arm.err; then echo "sliceoob-arm ran past the end of its slice"; exit 1; fi; \
	diff -u testdata/sliceoob.out $(BUILDDIR)/sliceoob-arm.got; \
	grep -q 'index 2 out of range \[0..1\] at line 25' $(BUILDDIR)/sliceoob-arm.err; \
	echo ok sliceat-arm-asm; \
	: P399 on arm64: Move sets x1, x0 and x2 with no push; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/moveregs0-arm testdata/moveregs.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/moveregs0-arm > $(BUILDDIR)/moveregs0-arm.got; \
	diff -u testdata/moveregs.out $(BUILDDIR)/moveregs0-arm.got; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -Fu $(A64DIR) -o $(BUILDDIR)/moveregs-base-arm testdata/moveregs.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/moveregs-base-arm > $(BUILDDIR)/moveregs-base-arm.got; \
	diff -u testdata/moveregs.out $(BUILDDIR)/moveregs-base-arm.got; \
	python3 -I scripts/check_moveregs.py $(BUILDDIR)/moveregs-arm.s --arm; \
	python3 -I scripts/check_moveregs.py $(BUILDDIR)/moveregs0-arm.s --arm; \
	echo ok moveregs-arm-asm; \
	: P400 on arm64: a call alone takes its arguments from x19 to x26 and leaves its value in one; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/splitcall0-arm testdata/splitcall.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/splitcall0-arm > $(BUILDDIR)/splitcall0-arm.got; \
	diff -u testdata/splitcall.out $(BUILDDIR)/splitcall0-arm.got; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -Fu $(A64DIR) -o $(BUILDDIR)/splitcall-base-arm testdata/splitcall.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/splitcall-base-arm > $(BUILDDIR)/splitcall-base-arm.got; \
	diff -u testdata/splitcall.out $(BUILDDIR)/splitcall-base-arm.got; \
	PASLANG_GCSTRESS=1 PASLANG_GCVERIFY=1 timeout 600 $(QEMU_A64) $(BUILDDIR)/splitcall0-arm > $(BUILDDIR)/splitcall0-arm-gc.got; \
	diff -u testdata/splitcall.out $(BUILDDIR)/splitcall0-arm-gc.got; \
	python3 -I scripts/check_splitcall.py $(BUILDDIR)/splitcall0-arm.s --arm; \
	echo ok splitcall-arm-asm; \
	: P358 on arm64: the locals a read may reach first, zeroed alone; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/nestzero0-arm testdata/nestzero.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/nestzero0-arm > $(BUILDDIR)/nestzero0-arm.got; \
	diff -u testdata/nestzero.out $(BUILDDIR)/nestzero0-arm.got; \
	python3 -I scripts/check_nestzero.py $(BUILDDIR)/nestzero0-arm.s --arm --expect=p_early:2,p_late:0,p_branch:2,p_writeback:1; \
	echo ok nestzero-arm-asm; \
	: P360 on arm64: the left side waits in x8; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/keepleft0-arm testdata/keepleft.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/keepleft0-arm > $(BUILDDIR)/keepleft0-arm.got; \
	diff -u testdata/keepleft.out $(BUILDDIR)/keepleft0-arm.got; \
	python3 -I scripts/check_argpush.py $(BUILDDIR)/keepleft0-arm.s --arm --routines=p_bysum,p_bysub,p_bymul,p_byless,p_byatleast,p_bydiv,p_bymod,p_byouter_in1; \
	echo ok keepleft-arm-asm; \
	: P334 on arm64: no frame, the link kept in x27; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/nestflat0-arm testdata/nestflat.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/nestflat0-arm > $(BUILDDIR)/nestflat0-arm.got; \
	diff -u testdata/nestflat.out $(BUILDDIR)/nestflat0-arm.got; \
	python3 -I scripts/check_nestflat.py $(BUILDDIR)/nestflat0-arm.s --arm --flat=p_outer_flatadd,p_outer_flatlocal,p_outer_flatbump,p_outer_mid_flatdeep,p_adder_anon.1 --framed=p_outer_mid,p_outer; \
	echo ok nestflat-arm-asm; \
	: P361 on arm64: the value worked out in x0; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/retreg0-arm testdata/retreg.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/retreg0-arm > $(BUILDDIR)/retreg0-arm.got; \
	diff -u testdata/retreg.out $(BUILDDIR)/retreg0-arm.got; \
	python3 -I scripts/check_retreg.py $(BUILDDIR)/retreg0-arm.s --arm --routines=p_sum2,p_scale,p_half,p_addg,p_early,p_makeadd_anon.1 --short=p_makeadd_anon.1:2,p_sum2:1,p_addg:4; \
	echo ok retreg-arm-asm; \
	: P362 on arm64: the add of a global read last before a return goes into the load, past a label no jump reaches; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/adrplast0-arm testdata/adrplast.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/adrplast0-arm > $(BUILDDIR)/adrplast0-arm.got; \
	diff -u testdata/adrplast.out $(BUILDDIR)/adrplast0-arm.got; \
	python3 -I scripts/check_adrpfold.py $(BUILDDIR)/adrplast0-arm.s --folds=6; \
	echo ok adrplast-arm-asm; \
	: P153 on arm64: the buffer comes in x8; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/recres0-arm testdata/recres.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/recres0-arm > $(BUILDDIR)/recres0-arm.got; \
	diff -u testdata/recres.out $(BUILDDIR)/recres0-arm.got; \
	python3 -I scripts/check_resbuf.py $(BUILDDIR)/recres0-arm.s --arm --routines=p_mkmid,p_mkbig,p_mkset,p_mkodd,p_tshape_twice,p_tboxer_boxed,p_climb,p_wrap,p_anon.1 --dest=8; \
	python3 -I scripts/check_resbuf.py $(BUILDDIR)/recres0-arm.s --arm --regs=p_mkpair,p_swap,p_op_add_tpair_tpair,p_tshape_box,p_tshape_unit1,p_tshape_getcorner,p_tsquare_box,p_climb2,p_outer,p_risky,p_grow,p_outer_inner --short=p_mkpair:1; \
	echo ok recres-arm-asm; \
	: P366 on arm64: in x0, x2 and x3; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/regres0-arm testdata/regres.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/regres0-arm > $(BUILDDIR)/regres0-arm.got; \
	diff -u testdata/regres.out $(BUILDDIR)/regres0-arm.got; \
	python3 -I scripts/check_resbuf.py $(BUILDDIR)/regres0-arm.s --arm --regs=p_mkone,p_mkpair,p_rot,p_rot3,p_bump,p_pick,p_sum,p_twice,p_mknamed,p_mkpacked,p_mkreal,p_mkarr3,p_tcounter_pair,p_tcounter_tri --short=p_mkpair:1,p_rot:4; \
	echo ok regres-arm-asm; \
	: P367 on arm64; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/fieldfirst0-arm testdata/fieldfirst.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/fieldfirst0-arm > $(BUILDDIR)/fieldfirst0-arm.got; \
	diff -u testdata/fieldfirst.out $(BUILDDIR)/fieldfirst0-arm.got; \
	python3 -I scripts/check_fieldfirst.py $(BUILDDIR)/fieldfirst0-arm.s --arm --zeros=p_full:0,p_both:0,p_part:2,p_readfirst:5,p_branch:5,p_early:5,p_gap:2,p_localsum:5; \
	echo ok fieldfirst-arm-asm; \
	: P370 on arm64; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/blockcopy1-arm testdata/blockcopy.paslang; \
	if grep -q 'azero' $(BUILDDIR)/blockcopy1-arm.s; then echo "blockcopy-arm.s: a block store tests a zero address"; exit 1; fi; \
	if awk '/^p_t40:/,/cfi_endproc/' $(BUILDDIR)/blockcopy1-arm.s | grep -qE 'bl rt_memcpy|bl rt_fill'; then echo "blockcopy-arm.s: T40 copies or zeroes out of line"; exit 1; fi; \
	if awk '/^p_t200:/,/cfi_endproc/' $(BUILDDIR)/blockcopy1-arm.s | grep -q 'bl rt_fill'; then echo "blockcopy-arm.s: T200 zeroes a variable with rt_fill"; exit 1; fi; \
	awk '/^p_t300:/,/cfi_endproc/' $(BUILDDIR)/blockcopy1-arm.s | grep -q 'bl rt_memcpy' || { echo "blockcopy-arm.s: T300 copies no block with rt_memcpy"; exit 1; }; \
	echo ok blockcopy-arm-asm; \
	: P368 on arm64; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/blockinl1-arm testdata/blockinl.paslang; \
	if awk '/^p_fresh:/,/cfi_endproc/' $(BUILDDIR)/blockinl1-arm.s | grep -q 'bl '; then echo "blockinl-arm.s: Fresh calls"; exit 1; fi; \
	test $$(awk '/^pas_main:/,/cfi_endproc/' $(BUILDDIR)/blockinl1-arm.s | grep -c 'bl p_get$$') -eq 1 || { echo "blockinl-arm.s: the main block does not call Get once"; exit 1; }; \
	if awk '/^pas_main:/,/cfi_endproc/' $(BUILDDIR)/blockinl1-arm.s | grep -q 'bl p_mkpair$$'; then echo "blockinl-arm.s: the main block calls MkPair"; exit 1; fi; \
	echo ok blockinl-arm-asm; \
	: P369 on arm64; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/methinl1-arm testdata/methinl.paslang; \
	if awk '/^pas_main:/,/cfi_endproc/' $(BUILDDIR)/methinl1-arm.s | grep -qE 'bl p_tbox_(bump|add|twice)$$'; then echo "methinl-arm.s: the main block calls Bump, Add or Twice"; exit 1; fi; \
	test $$(awk '/^pas_main:/,/cfi_endproc/' $(BUILDDIR)/methinl1-arm.s | grep -c 'blr ') -eq 4 || { echo "methinl-arm.s: the main block does not make its four virtual calls"; exit 1; }; \
	echo ok methinl-arm-asm; \
	: P371 on arm64; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/aheadres1-arm testdata/aheadres.paslang; \
	if awk '/^pas_main:/,/cfi_endproc/' $(BUILDDIR)/aheadres1-arm.s | grep -q 'bl p_tri$$'; then echo "aheadres-arm.s: the main block calls Tri"; exit 1; fi; \
	if awk '/^p_sumtri:/,/cfi_endproc/' $(BUILDDIR)/aheadres1-arm.s | grep -q 'bl p_'; then echo "aheadres-arm.s: SumTri calls"; exit 1; fi; \
	awk '/^p_nested:/,/cfi_endproc/' $(BUILDDIR)/aheadres1-arm.s | grep -q 'bl p_tri$$' || { echo "aheadres-arm.s: Nested put Tri ahead"; exit 1; }; \
	awk '/^pas_main:/,/cfi_endproc/' $(BUILDDIR)/aheadres1-arm.s | grep -q 'bl p_bump$$' || { echo "aheadres-arm.s: g + Bump put Bump ahead"; exit 1; }; \
	echo ok aheadres-arm-asm; \
	: P373 on arm64; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/elemaddr1-arm testdata/elemaddr.paslang; \
	awk '/^p_runlocal:/,/cfi_endproc/' $(BUILDDIR)/elemaddr1-arm.s | grep -qE '^  (madd|add) x10, ' || { echo "elemaddr-arm.s: RunLocal works out no element in x10"; exit 1; }; \
	echo ok elemaddr-arm-asm; \
	: P377 on arm64; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/boundsidiom1-arm testdata/boundsidiom.paslang; \
	for f in ina outa inr inp zero; do \
	  test $$(awk "/^p_$$f:/,/cfi_endproc/" $(BUILDDIR)/boundsidiom1-arm.s | grep -cE '^  b\.(lo|hs) ') -eq 1 || { echo "boundsidiom-arm.s: $$f is not one branch without sign"; exit 1; }; \
	done; \
	echo ok boundsidiom-arm-asm; \
	: a global field or element at a constant offset is one adrp and one access with the offset in its lo12, a field of a record in an element of an array as well, P374; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/globoff1-arm testdata/globoff.paslang; \
	grep -qE '^  ldrb w[0-9]+, \[x[0-9]+, :lo12:v_o\+8\]' $(BUILDDIR)/globoff1-arm.s || { echo "globoff-arm.s: o.Inner.B is not one adrp and one ldrb"; exit 1; }; \
	grep -qE '^  ldr x[0-9]+, \[x[0-9]+, :lo12:v_g\+240\]' $(BUILDDIR)/globoff1-arm.s || { echo "globoff-arm.s: g[3].Arr[2].Q is not one adrp and one ldr"; exit 1; }; \
	echo ok globoff-arm-asm; \
	: P378 on arm64, under the collector verify mode; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/hidshare1-arm testdata/hidshare.paslang; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 timeout 300 $(QEMU_A64) $(BUILDDIR)/hidshare1-arm > $(BUILDDIR)/hidshare1-arm.got; \
	diff -u testdata/hidshare.out $(BUILDDIR)/hidshare1-arm.got; \
	echo ok hidshare-arm-asm; \
	: every call of a routine that takes a buffer gives one, in every program and unit of both machines, P153; \
	python3 -I scripts/check_resbuf.py --all $(BUILDDIR) $(BUILDDIR)/$(LVL_X64) $(A64DIR) '$(A64DIR)/$(LVL_A64)'; \
	echo ok resbuf-all; \
	: P294 on arm64: c + k * x a move and one add with the shift, y + k * x and x := x + k * y one add, and loads at p - k, p + k and p + i shl s in the load, within the offsets of LDUR and LDR; \
	awk '/^p_off8:/,/cfi_endproc/' $(BUILDDIR)/leaform-arm.s > $(BUILDDIR)/leaform-off8-arm.s; \
	grep -qE 'add x[0-9]+, x17, x[0-9]+, lsl #3' $(BUILDDIR)/leaform-off8-arm.s || { echo "leaform-arm.s: Off8 is not a move and one add"; exit 1; }; \
	if grep -q 'mul ' $(BUILDDIR)/leaform-off8-arm.s; then echo "leaform-arm.s: Off8 multiplies"; exit 1; fi; \
	awk '/^p_base:/,/cfi_endproc/' $(BUILDDIR)/leaform-arm.s | grep -qE 'add x[0-9]+, x[0-9]+, x[0-9]+, lsl #2' || { echo "leaform-arm.s: Base is not one add"; exit 1; }; \
	test $$(awk '/^p_loop:/,/cfi_endproc/' $(BUILDDIR)/leaform-arm.s | grep -cE 'add x(19|2[0-6]), x(19|2[0-6]), x(19|2[0-6]), lsl #[123]') -eq 4 || { echo "leaform-arm.s: the loop of Loop has not four adds with a shift"; exit 1; }; \
	if awk '/^p_loop:/,/cfi_endproc/' $(BUILDDIR)/leaform-arm.s | grep -q 'mul '; then echo "leaform-arm.s: Loop multiplies"; exit 1; fi; \
	awk '/^p_back:/,/cfi_endproc/' $(BUILDDIR)/leaform-arm.s > $(BUILDDIR)/leaform-back-arm.s; \
	test $$(grep -cE 'ldr x[0-9]+, \[x[0-9]+, #-(8|16)\]' $(BUILDDIR)/leaform-back-arm.s) -eq 2 || { echo "leaform-arm.s: Back does not load at p - 8 and p - 16"; exit 1; }; \
	if grep -qE 'sub x[0-9]+, x[0-9]+, #(8|16)$$' $(BUILDDIR)/leaform-back-arm.s; then echo "leaform-arm.s: Back subtracts before it loads"; exit 1; fi; \
	awk '/^p_far:/,/cfi_endproc/' $(BUILDDIR)/leaform-arm.s > $(BUILDDIR)/leaform-far-arm.s; \
	grep -qE '\[x[0-9]+, #-256\]' $(BUILDDIR)/leaform-far-arm.s || { echo "leaform-arm.s: Far does not load at p - 256"; exit 1; }; \
	grep -qE 'sub x[0-9]+, x[0-9]+, #264$$' $(BUILDDIR)/leaform-far-arm.s || { echo "leaform-arm.s: Far folds p - 264, past LDUR"; exit 1; }; \
	awk '/^p_idx:/,/cfi_endproc/' $(BUILDDIR)/leaform-arm.s | grep -qE 'ldr x[0-9]+, \[x[0-9]+, x[0-9]+, lsl #3\]' || { echo "leaform-arm.s: Idx does not index the load"; exit 1; }; \
	echo ok leaform-arm-asm; \
	python3 -I scripts/check_cold.py $(BUILDDIR)/coldfail-arm.s 40 boundsfail,divzero,sqrtneg,realrange,bitfail,setfail,funnelfail,asfail,strappendc,strunique,fillbig; \
	echo ok coldfail-arm-asm; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 timeout 300 $(QEMU_A64) $(BUILDDIR)/coldloop-arm > $(BUILDDIR)/coldloop-arm-gc.got; \
	diff -u testdata/coldloop.out $(BUILDDIR)/coldloop-arm-gc.got; \
	python3 -I scripts/check_coldloop.py $(BUILDDIR)/coldloop-arm.s counted,twocounters,shared,global,walk,deep,wash,wipe,own; \
	echo ok coldloop-arm-asm; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 timeout 300 $(QEMU_A64) $(BUILDDIR)/ptrwalk-arm > $(BUILDDIR)/ptrwalk-arm-gc.got; \
	diff -u testdata/ptrwalk.out $(BUILDDIR)/ptrwalk-arm-gc.got; \
	for f in widths last zeros spell; do \
	  awk "/^p_$$f:/,/cfi_endproc/" $(BUILDDIR)/ptrwalk-arm.s > $(BUILDDIR)/ptrwalk-$$f-arm.s; \
	  grep -qE '^  cbnz x[0-9]+, ' $(BUILDDIR)/ptrwalk-$$f-arm.s || { echo "ptrwalk-arm.s: $$f does not test its pointer with cbnz"; exit 1; }; \
	  if grep -qE '^  mov x(9|1[0-5]), x(19|2[0-6])$$' $(BUILDDIR)/ptrwalk-$$f-arm.s; then echo "ptrwalk-arm.s: $$f copies a register variable into the pool"; exit 1; fi; \
	  if grep -q 'mov x17, #0$$' $(BUILDDIR)/ptrwalk-$$f-arm.s; then echo "ptrwalk-arm.s: $$f compares with a register of zero"; exit 1; fi; \
	done; \
	echo ok ptrwalk-arm-asm; \
	python3 -I scripts/check_nextjump.py $(foreach t,$(GOLDEN_A64),$(BUILDDIR)/$(t)-arm.s); \
	echo ok nextjump-arm; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 timeout 300 $(QEMU_A64) $(BUILDDIR)/movefill-arm > $(BUILDDIR)/movefill-arm-gc.got; \
	diff -u testdata/movefill.out $(BUILDDIR)/movefill-arm-gc.got; \
	for f in c1 c3 c8 c16 c17 c100 c128 whole; do \
	  if awk "/^p_$$f:/,/cfi_endproc/" $(BUILDDIR)/movefill-arm.s | grep -qE 'bl rt_memcpy|bl rt_fill$$'; then echo "movefill-arm.s: $$f calls rt_memcpy or rt_fill"; exit 1; fi; \
	done; \
	awk '/^p_c129:/,/cfi_endproc/' $(BUILDDIR)/movefill-arm.s | grep -q 'bl rt_memcpy' || { echo "movefill-arm.s: c129 does not call rt_memcpy"; exit 1; }; \
	: two 16-byte words side by side are one LDP or STP of Q registers, P372; \
	awk '/^p_c128:/,/cfi_endproc/' $(BUILDDIR)/movefill-arm.s | grep -q 'ldp q' || { echo "movefill-arm.s: c128 loads no pair of Q registers"; exit 1; }; \
	awk '/^p_c128:/,/cfi_endproc/' $(BUILDDIR)/movefill-arm.s | grep -q 'stp q' || { echo "movefill-arm.s: c128 stores no pair of Q registers"; exit 1; }; \
	echo ok movefill-arm-asm; \
	python3 -I scripts/check_immediates.py $(BUILDDIR)/immconst-arm.s adds,logic,steps,cmps,chars,kind,arrays; \
	echo ok immconst-arm-asm; \
	: P295 on arm64: Ten multiplies nothing, SixFortyOne multiplies only where the multiply is fast and not tuned for Neoverse N1, whose takes 4 cycles; \
	if awk '/^p_ten:/,/cfi_endproc/' $(BUILDDIR)/mulconst-arm.s | grep -q '^  mul '; then echo "mulconst-arm.s: Ten multiplies"; exit 1; fi; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -tune neoverse-n1 -Fu $(A64DIR) -o $(BUILDDIR)/mulconst-n1-arm testdata/mulconst.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/mulconst-n1-arm > $(BUILDDIR)/mulconst-n1-arm.got; \
	diff -u testdata/mulconst.out $(BUILDDIR)/mulconst-n1-arm.got; \
	if awk '/^p_sixfortyone:/,/cfi_endproc/' $(BUILDDIR)/mulconst-n1-arm.s | grep -q '^  mul '; then echo "mulconst-n1-arm.s: SixFortyOne multiplies on Neoverse N1"; exit 1; fi; \
	awk '/^p_large:/,/cfi_endproc/' $(BUILDDIR)/mulconst-n1-arm.s | grep -q '^  mul ' || { echo "mulconst-n1-arm.s: Large does not multiply"; exit 1; }; \
	echo ok mulconst-arm-asm; \
	: an arm64 prologue and stack check take the frame size as SUB immediates with no load of a word after the body, P308: one SUB for Small, two for Big, the literal past 16 MiB for Huge, no mark left; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 timeout 300 $(QEMU_A64) $(BUILDDIR)/framesize-arm > $(BUILDDIR)/framesize-arm-gc.got; \
	diff -u testdata/framesize.out $(BUILDDIR)/framesize-arm-gc.got; \
	if grep -qE 'ldr x(9|16), \.Lf|/\* (frame|check) ' $(BUILDDIR)/framesize-arm.s; then echo "framesize-arm.s: a frame size loaded from a word, or a mark left"; exit 1; fi; \
	awk '/^p_small:/,/cfi_endproc/' $(BUILDDIR)/framesize-arm.s | grep -qE '^  sub sp, sp, #[0-9]+$$' || { echo "framesize-arm.s: Small's frame is not one SUB"; exit 1; }; \
	awk '/^p_big:/,/cfi_endproc/' $(BUILDDIR)/framesize-arm.s | grep -qE '^  sub sp, sp, #[0-9]+, lsl #12$$' || { echo "framesize-arm.s: Big's frame is not two SUBs"; exit 1; }; \
	awk '/^p_huge:/,/cfi_endproc/' $(BUILDDIR)/framesize-arm.s | grep -q '^  sub sp, sp, x16$$' || { echo "framesize-arm.s: Huge's frame past 16 MiB is not through x16"; exit 1; }; \
	echo ok framesize-arm-asm; \
	: P307 on arm64: selectif under the stress of the collector and without inlining, every if it marks select a CSEL, CSINC or CINC and no branch, every one it marks branch a branch; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 timeout 300 $(QEMU_A64) $(BUILDDIR)/selectif-arm > $(BUILDDIR)/selectif-arm-gc.got; \
	diff -u testdata/selectif.out $(BUILDDIR)/selectif-arm-gc.got; \
	python3 -I scripts/check_select.py $(BUILDDIR)/selectif-arm.s testdata/selectif.paslang; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/selectif0-arm testdata/selectif.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/selectif0-arm > $(BUILDDIR)/selectif0-arm.got; \
	diff -u testdata/selectif.out $(BUILDDIR)/selectif0-arm.got; \
	python3 -I scripts/check_select.py $(BUILDDIR)/selectif0-arm.s testdata/selectif.paslang; \
	echo ok selectif-arm-asm; \
	: P310 on arm64: idxscale under the stress of the collector, and tuned for Neoverse N1 and N2, whose shifted adds cost less than a MADD, Loc, Glob, Dyn, Ptr and Cut multiply nothing; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 timeout 300 $(QEMU_A64) $(BUILDDIR)/idxscale-arm > $(BUILDDIR)/idxscale-arm-gc.got; \
	diff -u testdata/idxscale.out $(BUILDDIR)/idxscale-arm-gc.got; \
	for c in neoverse-n1 neoverse-n2; do \
	  $(OUTDIR)/paslangc -target arm64 -cpu max -tune $$c -Fu $(A64DIR) -o $(BUILDDIR)/idxscale-$$c-arm testdata/idxscale.paslang; \
	  timeout 300 $(QEMU_A64) $(BUILDDIR)/idxscale-$$c-arm > $(BUILDDIR)/idxscale-$$c-arm.got; \
	  diff -u testdata/idxscale.out $(BUILDDIR)/idxscale-$$c-arm.got; \
	  python3 -I scripts/check_scale.py $(BUILDDIR)/idxscale-$$c-arm.s loc,glob,dyn,ptr,cut --arm; \
	done; \
	echo ok idxscale-arm-asm; \
	: P311 on arm64: fieldaddr under the stress of the collector and without inlining, a field offset in its load or store with no add of it first; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 timeout 300 $(QEMU_A64) $(BUILDDIR)/fieldaddr-arm > $(BUILDDIR)/fieldaddr-arm-gc.got; \
	diff -u testdata/fieldaddr.out $(BUILDDIR)/fieldaddr-arm-gc.got; \
	python3 -I scripts/check_fieldaddr.py $(BUILDDIR)/fieldaddr-arm.s loc,glob,heap2,ptr,nest --arm; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/fieldaddr0-arm testdata/fieldaddr.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/fieldaddr0-arm > $(BUILDDIR)/fieldaddr0-arm.got; \
	diff -u testdata/fieldaddr.out $(BUILDDIR)/fieldaddr0-arm.got; \
	python3 -I scripts/check_fieldaddr.py $(BUILDDIR)/fieldaddr0-arm.s loc,glob,heap2,ptr,nest --arm; \
	echo ok fieldaddr-arm-asm; \
	: P312 on arm64: modconst multiplies and multiplies back only where no recipe or form of ScaleSubArm costs less, with no tune and tuned for Neoverse N1, and without inlining, every shift read by the next add or sub folded into it; \
	python3 -I scripts/check_modconst.py $(BUILDDIR)/modconst-arm.s --arm; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -tune neoverse-n1 -Fu $(A64DIR) -o $(BUILDDIR)/modconst-n1-arm testdata/modconst.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/modconst-n1-arm > $(BUILDDIR)/modconst-n1-arm.got; \
	diff -u testdata/modconst.out $(BUILDDIR)/modconst-n1-arm.got; \
	python3 -I scripts/check_modconst.py $(BUILDDIR)/modconst-n1-arm.s --arm --tune=n1; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/modconst0-arm testdata/modconst.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/modconst0-arm > $(BUILDDIR)/modconst0-arm.got; \
	diff -u testdata/modconst.out $(BUILDDIR)/modconst0-arm.got; \
	python3 -I scripts/check_modconst.py $(BUILDDIR)/modconst0-arm.s --arm; \
	echo ok modconst-arm-asm; \
	: P313 on arm64: the routines Run of idxsum add no constant to an index before its scale and none to the address of an element where the offset of the load or store takes it, with and without inlining; \
	python3 -I scripts/check_idxsum.py $(BUILDDIR)/idxsum-arm.s run12,run20,run24,run28,run40,run48,run56 --arm; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/idxsum0-arm testdata/idxsum.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/idxsum0-arm > $(BUILDDIR)/idxsum0-arm.got; \
	diff -u testdata/idxsum.out $(BUILDDIR)/idxsum0-arm.got; \
	python3 -I scripts/check_idxsum.py $(BUILDDIR)/idxsum0-arm.s run12,run20,run24,run28,run40,run48,run56 --arm; \
	echo ok idxsum-arm-asm; \
	: P314 on arm64: fieldcse under the stress of the collector and without inlining, one element address a loop body; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 timeout 300 $(QEMU_A64) $(BUILDDIR)/fieldcse-arm > $(BUILDDIR)/fieldcse-arm-gc.got; \
	diff -u testdata/fieldcse.out $(BUILDDIR)/fieldcse-arm-gc.got; \
	python3 -I scripts/check_fieldcse.py $(BUILDDIR)/fieldcse-arm.s same:4,inheap:4 --arm; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/fieldcse0-arm testdata/fieldcse.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/fieldcse0-arm > $(BUILDDIR)/fieldcse0-arm.got; \
	diff -u testdata/fieldcse.out $(BUILDDIR)/fieldcse0-arm.got; \
	python3 -I scripts/check_fieldcse.py $(BUILDDIR)/fieldcse0-arm.s same:4,inheap:4 --arm; \
	echo ok fieldcse-arm-asm; \
	: P315 on arm64: no literal load in armconst, the runtime included, each constant in as many instructions as Go writes it, with no tune, tuned for Neoverse N1 and without inlining; \
	python3 -I scripts/check_armconst.py $(BUILDDIR)/armconst-arm.s --source=testdata/armconst.paslang; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -tune neoverse-n1 -Fu $(A64DIR) -o $(BUILDDIR)/armconst-n1-arm testdata/armconst.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/armconst-n1-arm > $(BUILDDIR)/armconst-n1-arm.got; \
	diff -u testdata/armconst.out $(BUILDDIR)/armconst-n1-arm.got; \
	python3 -I scripts/check_armconst.py $(BUILDDIR)/armconst-n1-arm.s --source=testdata/armconst.paslang; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/armconst0-arm testdata/armconst.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/armconst0-arm > $(BUILDDIR)/armconst0-arm.got; \
	diff -u testdata/armconst.out $(BUILDDIR)/armconst0-arm.got; \
	python3 -I scripts/check_armconst.py $(BUILDDIR)/armconst0-arm.s --source=testdata/armconst.paslang; \
	echo ok armconst-arm-asm; \
	: P316 on arm64: chkcse under the stress of the collector and without inlining, Fields checking once an element; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 timeout 300 $(QEMU_A64) $(BUILDDIR)/chkcse-arm > $(BUILDDIR)/chkcse-arm-gc.got; \
	diff -u testdata/chkcse.out $(BUILDDIR)/chkcse-arm-gc.got; \
	python3 -I scripts/check_chkcse.py $(BUILDDIR)/chkcse-arm.s fields:6,called:1,joined:3,moved:3,grown:3; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/chkcse0-arm testdata/chkcse.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/chkcse0-arm > $(BUILDDIR)/chkcse0-arm.got; \
	diff -u testdata/chkcse.out $(BUILDDIR)/chkcse0-arm.got; \
	python3 -I scripts/check_chkcse.py $(BUILDDIR)/chkcse0-arm.s fields:6,joined:3,moved:3,grown:3; \
	echo ok chkcse-arm-asm; \
	: P317 on arm64: convmul with and without inlining, the recipe from the register of the variable; \
	python3 -I scripts/check_convmul.py $(BUILDDIR)/convmul-arm.s --arm; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/convmul0-arm testdata/convmul.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/convmul0-arm > $(BUILDDIR)/convmul0-arm.got; \
	diff -u testdata/convmul.out $(BUILDDIR)/convmul0-arm.got; \
	python3 -I scripts/check_convmul.py $(BUILDDIR)/convmul0-arm.s --arm; \
	echo ok convmul-arm-asm; \
	: P318 on arm64: regassign with and without inlining, no value moved into a variable and none through x17 in its loops; \
	python3 -I scripts/check_regassign.py $(BUILDDIR)/regassign-arm.s --arm; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/regassign0-arm testdata/regassign.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/regassign0-arm > $(BUILDDIR)/regassign0-arm.got; \
	diff -u testdata/regassign.out $(BUILDDIR)/regassign0-arm.got; \
	python3 -I scripts/check_regassign.py $(BUILDDIR)/regassign0-arm.s --arm; \
	echo ok regassign-arm-asm; \
	: P319 on arm64: runlen with and without inlining, the free bodies checking none; \
	python3 -I scripts/check_chkcse.py $(BUILDDIR)/runlen-arm.s sum5:5,mix5:5,back:4,local5:10; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/runlen0-arm testdata/runlen.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/runlen0-arm > $(BUILDDIR)/runlen0-arm.got; \
	diff -u testdata/runlen.out $(BUILDDIR)/runlen0-arm.got; \
	python3 -I scripts/check_chkcse.py $(BUILDDIR)/runlen0-arm.s sum5:5,mix5:5,back:4,local5:10; \
	echo ok runlen-arm-asm; \
	: P320 on arm64: andmask with and without inlining, no AND of a mask in its routines; \
	python3 -I scripts/check_andmask.py $(BUILDDIR)/andmask-arm.s --arm; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/andmask0-arm testdata/andmask.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/andmask0-arm > $(BUILDDIR)/andmask0-arm.got; \
	diff -u testdata/andmask.out $(BUILDDIR)/andmask0-arm.got; \
	python3 -I scripts/check_andmask.py $(BUILDDIR)/andmask0-arm.s --arm; \
	echo ok andmask-arm-asm; \
	: P322 on arm64: andtest with and without inlining, one TST and the tests of one bit TBZ or TBNZ; \
	python3 -I scripts/check_andtest.py $(BUILDDIR)/andtest-arm.s --arm --tbz=38; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/andtest0-arm testdata/andtest.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/andtest0-arm > $(BUILDDIR)/andtest0-arm.got; \
	diff -u testdata/andtest.out $(BUILDDIR)/andtest0-arm.got; \
	python3 -I scripts/check_andtest.py $(BUILDDIR)/andtest0-arm.s --arm --tbz=38; \
	echo ok andtest-arm-asm; \
	: P296 on arm64: flatproc with and without inlining, no frame and no saved link register; \
	python3 -I scripts/check_flatproc.py $(BUILDDIR)/flatproc-arm.s --arm --clamp=8; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/flatproc0-arm testdata/flatproc.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/flatproc0-arm > $(BUILDDIR)/flatproc0-arm.got; \
	diff -u testdata/flatproc.out $(BUILDDIR)/flatproc0-arm.got; \
	python3 -I scripts/check_flatproc.py $(BUILDDIR)/flatproc0-arm.s --arm --clamp=8; \
	echo ok flatproc-arm-asm; \
	: P324 on arm64: memlen with and without inlining, the length loaded only where a compare reads it; \
	python3 -I scripts/check_chkcse.py $(BUILDDIR)/memlen-arm.s rotate:6,pair:2; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/memlen0-arm testdata/memlen.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/memlen0-arm > $(BUILDDIR)/memlen0-arm.got; \
	diff -u testdata/memlen.out $(BUILDDIR)/memlen0-arm.got; \
	python3 -I scripts/check_chkcse.py $(BUILDDIR)/memlen0-arm.s rotate:6,pair:2; \
	echo ok memlen-arm-asm; \
	: P297 on arm64: callexpr with and without inlining, the code and second word of a call in x8 and x27; \
	python3 -I scripts/check_callexpr.py $(BUILDDIR)/callexpr-arm.s --arm; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/callexpr0-arm testdata/callexpr.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/callexpr0-arm > $(BUILDDIR)/callexpr0-arm.got; \
	diff -u testdata/callexpr.out $(BUILDDIR)/callexpr0-arm.got; \
	python3 -I scripts/check_callexpr.py $(BUILDDIR)/callexpr0-arm.s --arm; \
	echo ok callexpr-arm-asm; \
	: P327 on arm64: forstep with and without inlining; \
	python3 -I scripts/check_forstep.py $(BUILDDIR)/forstep-arm.s --arm --loops=0; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/forstep0-arm testdata/forstep.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/forstep0-arm > $(BUILDDIR)/forstep0-arm.got; \
	diff -u testdata/forstep.out $(BUILDDIR)/forstep0-arm.got; \
	python3 -I scripts/check_forstep.py $(BUILDDIR)/forstep0-arm.s --arm --loops=3; \
	echo ok forstep-arm-asm; \
	: P330 on arm64: twostore with and without inlining, one stp of x8 and x27; \
	python3 -I scripts/check_twostore.py $(BUILDDIR)/twostore-arm.s --arm; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/twostore0-arm testdata/twostore.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/twostore0-arm > $(BUILDDIR)/twostore0-arm.got; \
	diff -u testdata/twostore.out $(BUILDDIR)/twostore0-arm.got; \
	python3 -I scripts/check_twostore.py $(BUILDDIR)/twostore0-arm.s --arm; \
	echo ok twostore-arm-asm; \
	: P329 on arm64: elemop with and without inlining, one ldp or stp a pair, the add before it in its offset; \
	python3 -I scripts/check_elemop.py $(BUILDDIR)/elemop-arm.s --arm --pairs=12; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/elemop0-arm testdata/elemop.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/elemop0-arm > $(BUILDDIR)/elemop0-arm.got; \
	diff -u testdata/elemop.out $(BUILDDIR)/elemop0-arm.got; \
	python3 -I scripts/check_elemop.py $(BUILDDIR)/elemop0-arm.s --arm --pairs=12; \
	echo ok elemop-arm-asm; \
	: P331 on arm64: globfold with and without inlining, a global by adrp and the low twelve bits, two reads fewer since gp goes to nil after its last use and they come from a register, P345; \
	python3 -I scripts/check_adrpfold.py $(BUILDDIR)/globfold-arm.s --folds=30; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/globfold0-arm testdata/globfold.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/globfold0-arm > $(BUILDDIR)/globfold0-arm.got; \
	diff -u testdata/globfold.out $(BUILDDIR)/globfold0-arm.got; \
	python3 -I scripts/check_adrpfold.py $(BUILDDIR)/globfold0-arm.s --folds=21; \
	echo ok globfold-arm-asm; \
	: P346 on arm64: exc with and without inlining, a line label in no global fold of P331; \
	python3 -I scripts/check_adrpfold.py $(BUILDDIR)/exc-arm.s --folds=1; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/exc0-arm testdata/exc.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/exc0-arm > $(BUILDDIR)/exc0-arm.got; \
	diff -u testdata/exc.out $(BUILDDIR)/exc0-arm.got; \
	python3 -I scripts/check_adrpfold.py $(BUILDDIR)/exc0-arm.s --folds=1; \
	echo ok linefold-arm-asm; \
	: P342 on arm64: every routine within the room its check gives, and the 368 bytes of a stop, the golden programs and the units; \
	python3 -I scripts/check_stack.py $(foreach t,$(GOLDEN_A64),$(BUILDDIR)/$(t)-arm.s) $(foreach u,$(CORE_UNITS) $(LIB_UNITS),$(A64DIR)/$(basename $(notdir $(u))).s) --arm --room=rt_yieldpoint:16,rt_asyncpreempt --async=368 --margin=64; \
	echo ok stack-room-arm; \
	: the same order in every golden program of arm64, P388; \
	python3 -I scripts/check_maporder.py $(foreach t,$(GOLDEN_A64),$(BUILDDIR)/$(t)-arm); \
	echo ok map-order-arm; \
	: P342 on arm64: a sleeping routine takes its record and first stack; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -Fu $(A64DIR) -o $(BUILDDIR)/sleepers-arm testdata/sleepers.paslang; \
	python3 -I scripts/check_routinemem.py $(BUILDDIR)/sleepers-arm --limit=2560 --qemu=$(QEMU_A64); \
	echo ok routinemem-arm; \
	: P333 on arm64: the runtime of execrace, the exec lock around a new thread and an execve; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -Fu $(A64DIR) -o $(BUILDDIR)/execrace-arm testdata/execrace.paslang; \
	python3 -I scripts/check_execlock.py $(BUILDDIR)/execrace-arm.s --arm; \
	echo ok execlock-arm-asm; \
	: P326 on arm64: inlineorder with -inline 0 and 200; \
	for n in 0 200; do \
	  $(OUTDIR)/paslangc -target arm64 -cpu max -inline $$n -Fu $(A64DIR) -o $(BUILDDIR)/inlineorder$$n-arm testdata/inlineorder.paslang; \
	  timeout 300 $(QEMU_A64) $(BUILDDIR)/inlineorder$$n-arm > $(BUILDDIR)/inlineorder$$n-arm.got; \
	  diff -u testdata/inlineorder.out $(BUILDDIR)/inlineorder$$n-arm.got; \
	done; \
	echo ok inlineorder-arm-inline; \
	: P336 on arm64: unrollctr with -inline 0 and 200; \
	for n in 0 200; do \
	  $(OUTDIR)/paslangc -target arm64 -cpu max -inline $$n -Fu $(A64DIR) -o $(BUILDDIR)/unrollctr$$n-arm testdata/unrollctr.paslang; \
	  timeout 300 $(QEMU_A64) $(BUILDDIR)/unrollctr$$n-arm > $(BUILDDIR)/unrollctr$$n-arm.got; \
	  diff -u testdata/unrollctr.out $(BUILDDIR)/unrollctr$$n-arm.got; \
	done; \
	echo ok unrollctr-arm-inline; \
	$(OUTDIR)/paslangc -target arm64 -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/exprinline0-arm testdata/exprinline.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/exprinline0-arm > $(BUILDDIR)/exprinline0-arm.got; \
	diff -u testdata/exprinline.out $(BUILDDIR)/exprinline0-arm.got; \
	awk '/^p_branchy:/,/ret$$/' $(BUILDDIR)/exprinline-arm.s > $(BUILDDIR)/exprinline-branchy-arm.s; \
	grep -qE '^  csel x[0-9]+, x[0-9]+, x[0-9]+, lt$$' $(BUILDDIR)/exprinline-branchy-arm.s || { echo "exprinline-arm.s: Branchy is not a select on Less's compare"; exit 1; }; \
	if grep -q 'bl p_less\|cset' $(BUILDDIR)/exprinline-branchy-arm.s; then echo "exprinline-arm.s: Branchy calls Less or makes a Boolean"; exit 1; fi; \
	: the processor in the code on arm64, P261: the routines after the CPU neoverse-n1 directive say it, LSE is on for them, and the unit runs; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -Fu $(A64DIR) -o $(BUILDDIR)/cputune-ab testdata/cputune.paslang; \
	grep -q '^.arch_extension lse$$' $(BUILDDIR)/cputune-ab.s || { echo "cputune-ab.s: no LSE for the neoverse-n1 routines"; exit 1; }; \
	grep -F '/* p_lzfast: cpu ' $(BUILDDIR)/cputune-ab.s | grep -q 'atomics.*; tune neoverse-n1 \*/' || { echo "cputune-ab.s: LzFast does not say its processor"; exit 1; }; \
	grep -qF '; tune neoverse-v1 */' $(BUILDDIR)/cputune-ab.s || { echo "cputune-ab.s: Tuned does not say its tune"; exit 1; }; \
	awk '/^pas_main:/,/^\.section/' $(BUILDDIR)/cputune-ab.s | grep -q 'bl p_one$$' || { echo "cputune-ab.s: One, of another processor, went into the main block"; exit 1; }; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/cputune-ab > $(BUILDDIR)/cputune-ab.got; \
	diff -u testdata/cputune.out $(BUILDDIR)/cputune-ab.got; \
	$(OUTDIR)/paslangc -target arm64 -cpu base testdata/units/cpuu.paslang; \
	grep -qF '/* u_cpuu_init: cpu ' $(A64DIR)/cpuu.s || { echo "cpuu-arm.s: the initialization does not say its processor"; exit 1; }; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -Fu $(A64DIR) -o $(BUILDDIR)/cputuse-arm testdata/cputuse.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/cputuse-arm > $(BUILDDIR)/cputuse-arm.got; \
	diff -u testdata/cputuse.out $(BUILDDIR)/cputuse-arm.got
	@set -e; \
	echo "==== the base processor arm64 ===="; \
	for t in hash1 tree1 store1 vectors bitwords set256 strwords strkern strcmpk cmpwords sysutils1 utf8kern jsonkern longslice rtlong fillkern json1 jsoncanon hmacstream hashpieces hashpieces2 cipherkat cipherwyche x25519kat nistwyche rsawyche; do \
	  $(OUTDIR)/paslangc -target arm64 -cpu base -o $(BUILDDIR)/$$t-arm-base testdata/$$t.paslang; \
	  timeout 120 $(QEMU_A64) $(BUILDDIR)/$$t-arm-base > $(BUILDDIR)/$$t-arm.bgot; \
	  diff -u testdata/$$t.out $(BUILDDIR)/$$t-arm.bgot; \
	done; \
	grep -q 'p_pashash_passha256cpu' $(BUILDDIR)/hash1-arm.s; \
	grep -q 'p_pashash_passha512cpu' $(BUILDDIR)/hash1-arm.s; \
	grep -q 'p_pashash_passha256updatecpu' $(BUILDDIR)/hashpieces-arm.s; \
	if grep -q 'p_pashash_passha256updatecpu' $(BUILDDIR)/hashpieces-arm-base.s; then echo "hashpieces-arm-base.s calls the SHA-256 body"; exit 1; fi; \
	grep -q 'p_pashash_pashmacupdatecpu' $(BUILDDIR)/hashpieces2-arm.s; \
	if grep -q 'p_pashash_pashmacupdatecpu' $(BUILDDIR)/hashpieces2-arm-base.s; then echo "hashpieces2-arm-base.s calls the SHA-256 body"; exit 1; fi; \
	if grep -q 'p_pashash_passha256cpu' $(BUILDDIR)/hash1-arm-base.s; then echo "hash1-arm-base.s calls the SHA-256 body"; exit 1; fi; \
	: pastls for the base arm64 on qemu against Go crypto/tls and openssl s_server on the host, ChaCha20 first, P431; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -Fu $(A64DIR) -o $(BUILDDIR)/tlsinterop-arm testdata/tlsinterop.paslang; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -Fu $(A64DIR) -o $(BUILDDIR)/tlsdoc-arm testdata/tlsdoc.paslang; \
	if command -v go > /dev/null 2>&1; then \
	  (cd scripts/tlsoracle && GOCACHE=$(abspath $(BUILDDIR))/gocache GOFLAGS=-mod=mod go build -o $(abspath $(BUILDDIR))/tlsoracle .); \
	  sh scripts/tls_interop.sh go $(BUILDDIR)/tlsoracle $(BUILDDIR)/tlsinterop-arm $(QEMU_A64) $(BUILDDIR)/tlsdoc-arm > $(BUILDDIR)/tlsinterop-go-arm.got; \
	  diff -u testdata/tlsinterop-go-base.out $(BUILDDIR)/tlsinterop-go-arm.got; \
	fi; \
	if command -v openssl > /dev/null 2>&1; then \
	  sh scripts/tls_interop.sh openssl - $(BUILDDIR)/tlsinterop-arm $(QEMU_A64) > $(BUILDDIR)/tlsinterop-openssl-arm.got; \
	  diff -u testdata/tlsinterop-openssl-base.out $(BUILDDIR)/tlsinterop-openssl-arm.got; \
	fi; \
	: pascipher at the arm64 level seals through aese and pmull, its base build through neither, P428; \
	grep -q 'aese v0.16b, v1.16b' '$(A64DIR)/$(LVL_A64)/pascipher.s'; \
	grep -q 'pmull2 v6.1q' '$(A64DIR)/$(LVL_A64)/pascipher.s'; \
	if grep -q 'aese v0\|pmull' $(A64DIR)/pascipher.s; then echo "pascipher's arm64 base build carries the crypto extension"; exit 1; fi; \
	echo ok cpu-base-arm; \
	: the json type on arm64, P203: every document of the oracle test as expect.txt holds it, the index and a byte at a time alike; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/jsoncheck-arm testdata/jsoncheck.paslang; \
	python3 -I scripts/check_json.py --qemu=$(QEMU_A64) $(BUILDDIR)/jsoncheck-arm -; \
	echo ok json-arm; \
	grep -q 'gctype TNode size 32 words 1 mask 0x0000000000000009' $(BUILDDIR)/gctypes-arm.s; \
	grep -q 'gctype TBox instance size 48 words 1 mask 0x000000000000000a' $(BUILDDIR)/gctypes-arm.s; \
	grep -A1 -x '  .quad v_pl' $(BUILDDIR)/gctypes-arm.s | grep -qx '  .quad 8'; \
	if grep -qx '  .quad v_total' $(BUILDDIR)/gctypes-arm.s; then echo "gctypes-arm.s lists v_total, which holds no pointer, as a root"; exit 1; fi; \
	echo ok gctypes-descriptors-arm; \
	echo "==== stdin arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/readlines-arm testdata/readlines.paslang; \
	timeout 60 $(QEMU_A64) $(BUILDDIR)/readlines-arm < testdata/readlines.in > $(BUILDDIR)/readlines-arm.got; \
	diff -u testdata/readlines.out $(BUILDDIR)/readlines-arm.got; \
	(sleep 0.05; head -c 3000 testdata/readlines.in; sleep 0.05; tail -c +3001 testdata/readlines.in) | timeout 60 python3 scripts/nonblocking.py $(QEMU_A64) $(BUILDDIR)/readlines-arm > $(BUILDDIR)/readlines-arm.got; \
	diff -u testdata/readlines.out $(BUILDDIR)/readlines-arm.got; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/spurwake-arm testdata/spurwake.paslang; \
	(sleep 0.5; printf 'x\n'; head -c 100000 /dev/zero | tr '\0' y) | timeout 60 $(QEMU_A64) $(BUILDDIR)/spurwake-arm > $(BUILDDIR)/spurwake-arm.got; \
	diff -u testdata/spurwake.out $(BUILDDIR)/spurwake-arm.got; \
	(sleep 0.5; printf 'x\n'; head -c 100000 /dev/zero | tr '\0' y) | timeout 60 python3 scripts/nonblocking.py $(QEMU_A64) $(BUILDDIR)/spurwake-arm > $(BUILDDIR)/spurwake-arm.got; \
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
	: store1 under the stress of the collector takes 400 s of qemu on a machine half loaded and 1800 lets a loaded one finish it, P335; \
	for t in $(GOLDEN_A64); do \
	  PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=3 PASLANG_GCPOISON=1 timeout 1800 $(QEMU_A64) $(BUILDDIR)/$$t-arm > $(BUILDDIR)/$$t-arm.vgot; \
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
	: P337 on arm64: every M a capped cycle may mark with marks; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/gcwake-arm testdata/gcwake.paslang; \
	for w in PASLANG_GCWORKERS=2 PASLANG_GCWORKERS=4; do \
	  env $$w timeout 600 $(QEMU_A64) $(BUILDDIR)/gcwake-arm > $(BUILDDIR)/gcwake-arm.got; \
	  diff -u testdata/gcwake.out $(BUILDDIR)/gcwake-arm.got; \
	done; \
	echo ok gcwake-arm; \
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
	echo "==== idle mark workers arm64 (P219) ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/markidle-arm testdata/markidle.paslang; \
	for w in "" PASLANG_GC=off PASLANG_GCWORKERS=1; do \
	  env $$w timeout 600 $(QEMU_A64) $(BUILDDIR)/markidle-arm > $(BUILDDIR)/markidle-arm.got; \
	  diff -u testdata/markidle.out $(BUILDDIR)/markidle-arm.got; \
	done; \
	taskset -c 0 timeout 600 $(QEMU_A64) $(BUILDDIR)/markidle-arm > $(BUILDDIR)/markidle-arm.got; \
	diff -u testdata/markidle.out $(BUILDDIR)/markidle-arm.got; \
	echo ok markidle-arm; \
	echo "==== a kernel's calls give way arm64 (P269) ===="; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -o $(BUILDDIR)/utf8slice-arm testdata/utf8slice.paslang; \
	taskset -c 0 timeout 600 $(QEMU_A64) $(BUILDDIR)/utf8slice-arm > $(BUILDDIR)/utf8slice-arm.got; \
	diff -u testdata/utf8slice.out $(BUILDDIR)/utf8slice-arm.got; \
	echo ok utf8slice-arm; \
	echo "==== the core units' kernels give way arm64 (P270) ===="; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -o $(BUILDDIR)/kernslice-arm testdata/kernslice.paslang; \
	taskset -c 0 timeout 600 $(QEMU_A64) $(BUILDDIR)/kernslice-arm all > $(BUILDDIR)/kernslice-arm.got; \
	diff -u testdata/kernslice.out $(BUILDDIR)/kernslice-arm.got; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -o $(BUILDDIR)/kernslice-armb testdata/kernslice.paslang; \
	taskset -c 0 timeout 600 $(QEMU_A64) $(BUILDDIR)/kernslice-armb str > $(BUILDDIR)/kernslice-armb.got; \
	head -n 7 testdata/kernslice.out | diff -u - $(BUILDDIR)/kernslice-armb.got; \
	echo ok kernslice-arm; \
	echo "==== the runtime's copies, clears, comparisons and hashes give way arm64 (P271) ===="; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -o $(BUILDDIR)/rtslice-arm testdata/rtslice.paslang; \
	PASLANG_GC=20000 taskset -c 0 timeout 600 $(QEMU_A64) $(BUILDDIR)/rtslice-arm > $(BUILDDIR)/rtslice-arm.got; \
	diff -u testdata/rtslice.out $(BUILDDIR)/rtslice-arm.got; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -o $(BUILDDIR)/rtslice-armb testdata/rtslice.paslang; \
	PASLANG_GC=20000 taskset -c 0 timeout 600 $(QEMU_A64) $(BUILDDIR)/rtslice-armb > $(BUILDDIR)/rtslice-armb.got; \
	diff -u testdata/rtslice.out $(BUILDDIR)/rtslice-armb.got; \
	echo ok rtslice-arm; \
	echo "==== DC ZVA on a processor -cpu names (P273) ===="; \
	$(OUTDIR)/paslangc -target arm64 -cpu neoverse-n1 -o $(BUILDDIR)/fillkern-n1 testdata/fillkern.paslang; \
	grep -q 'dc zva' $(BUILDDIR)/fillkern-n1.s || { echo "fillkern-n1.s has no dc zva"; exit 1; }; \
	if grep -q 'dc zva' $(BUILDDIR)/fillkern-arm.s; then echo "fillkern-arm.s, compiled for max, has dc zva"; exit 1; fi; \
	timeout 300 $(QEMU_A64) -cpu neoverse-n1 $(BUILDDIR)/fillkern-n1 > $(BUILDDIR)/fillkern-n1.got; \
	diff -u testdata/fillkern.out $(BUILDDIR)/fillkern-n1.got; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=3 PASLANG_GCPOISON=1 timeout 600 $(QEMU_A64) -cpu neoverse-v1 $(BUILDDIR)/fillkern-n1 > $(BUILDDIR)/fillkern-n1.got; \
	diff -u testdata/fillkern.out $(BUILDDIR)/fillkern-n1.got; \
	if timeout 60 $(QEMU_A64) -cpu a64fx $(BUILDDIR)/fillkern-n1 > $(BUILDDIR)/fillkern-a64fx.got 2>&1; then echo "fillkern-n1 ran on a64fx"; exit 1; fi; \
	grep -qx 'paslang: compiled for neoverse-n1, whose DC ZVA zeroes 64 bytes; this processor reads DCZID_EL0 6' $(BUILDDIR)/fillkern-a64fx.got || { cat $(BUILDDIR)/fillkern-a64fx.got; exit 1; }; \
	echo ok zva-arm; \
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
	for t in divzero nilptr deep oom closed divloop bstatic bslice bstring bneg bempty bloop bref bnested bconst bstrcall bsame bslicereg bversion bslicehi bviewneg rrtrunc rrround rrfloor rrceil qtrunc qsqrt bitchk bitneg bitpool bitfield bitstr bitempty bitrec bitcall bitslice viewstr blkstr divover divzero128 funnelstr funnelslice mainraise raiseobj setelem setincl svneg svnil svmark svwrap exprarg leafnil bmaskwide bmodneg bmaskone bforpast bvarctr bnestctr bsumstat bsumdyn bsumneg bkeepfirst bkeepmoved bkeepstat bkeepshrunk brunlen brunloc divfirst idxline nilline bflatidx bflatpush nilblk nilbig nilzero nildest nilmeth elemidx jsonbusy jsonrbusy jsonwbusy divcall; do \
	  $(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/fatal_$$t-arm testdata/fatal/$$t.paslang; \
	  set +e; timeout 60 $(QEMU_A64) $(BUILDDIR)/fatal_$$t-arm > $(BUILDDIR)/fatal_$$t-arm.got 2> $(BUILDDIR)/fatal_$$t-arm.err; rc=$$?; set -e; \
	  test $$rc -eq 1; \
	  diff -u testdata/fatal/expected.out $(BUILDDIR)/fatal_$$t-arm.got; \
	done; \
	grep -q 'paslang: integer divide by zero at line 11' $(BUILDDIR)/fatal_divzero-arm.err; \
	grep -q 'paslang: integer divide by zero at line 15' $(BUILDDIR)/fatal_divfirst-arm.err; \
	grep -q 'paslang: integer divide by zero at line 17' $(BUILDDIR)/fatal_divcall-arm.err; \
	grep -q 'paslang: index 12 out of range \[0..9\] at line 15' $(BUILDDIR)/fatal_idxline-arm.err; \
	grep -q 'paslang: nil pointer dereference at line 20' $(BUILDDIR)/fatal_nilline-arm.err; \
	grep -q 'paslang: nil pointer dereference at line 19' $(BUILDDIR)/fatal_nilblk-arm.err; \
	grep -q 'paslang: nil pointer dereference at line 19' $(BUILDDIR)/fatal_nilbig-arm.err; \
	grep -q 'paslang: nil pointer dereference at line 17' $(BUILDDIR)/fatal_nilzero-arm.err; \
	grep -q 'paslang: nil pointer dereference at line 19' $(BUILDDIR)/fatal_nildest-arm.err; \
	grep -q 'paslang: nil pointer dereference at line 24' $(BUILDDIR)/fatal_nilmeth-arm.err; \
	grep -q 'paslang: index 9 out of range \[0..7\] at line 20' $(BUILDDIR)/fatal_elemidx-arm.err; \
	grep -q 'paslang: nil pointer dereference at line 16' $(BUILDDIR)/fatal_nilptr-arm.err; \
	grep -q 'paslang: nil pointer dereference at line 14' $(BUILDDIR)/fatal_leafnil-arm.err; \
	grep -q 'paslang: index 100 out of range \[0..63\] at line 11' $(BUILDDIR)/fatal_bmaskwide-arm.err; \
	grep -q 'paslang: index -5 out of range \[0..63\] at line 12' $(BUILDDIR)/fatal_bmodneg-arm.err; \
	grep -q 'paslang: index 64 out of range \[0..63\] at line 11' $(BUILDDIR)/fatal_bmaskone-arm.err; \
	grep -q 'paslang: index 64 out of range \[0..63\] at line 11' $(BUILDDIR)/fatal_bforpast-arm.err; \
	grep -q 'paslang: index 50 out of range \[0..9\] at line 20' $(BUILDDIR)/fatal_bvarctr-arm.err; \
	grep -q 'paslang: index 50 out of range \[0..9\] at line 21' $(BUILDDIR)/fatal_bnestctr-arm.err; \
	grep -q 'paslang: index 65 out of range \[1..64\] at line 15' $(BUILDDIR)/fatal_bsumstat-arm.err; \
	grep -q 'paslang: index 10 out of range \[0..9\] at line 14' $(BUILDDIR)/fatal_bsumdyn-arm.err; \
	grep -q 'paslang: index -4 out of range \[-3..20\] at line 17' $(BUILDDIR)/fatal_bsumneg-arm.err; \
	grep -q 'paslang: index 10 out of range \[0..9\] at line 17' $(BUILDDIR)/fatal_bkeepfirst-arm.err; \
	grep -q 'paslang: index 10 out of range \[0..9\] at line 20' $(BUILDDIR)/fatal_bkeepmoved-arm.err; \
	grep -q 'paslang: index 9 out of range \[1..8\] at line 20' $(BUILDDIR)/fatal_bkeepstat-arm.err; \
	grep -q 'paslang: index 3 out of range \[0..2\] at line 15' $(BUILDDIR)/fatal_bkeepshrunk-arm.err; \
	grep -q 'paslang: index 30 out of range \[0..29\] at line 15' $(BUILDDIR)/fatal_brunlen-arm.err; \
	grep -q 'paslang: index 1500 out of range \[0..1499\] at line 17' $(BUILDDIR)/fatal_brunloc-arm.err; \
	grep -q 'paslang: index 10 out of range \[0..9\] at line 11' $(BUILDDIR)/fatal_bflatidx-arm.err; \
	grep -q 'paslang: index -1 out of range \[0..9\] at line 14' $(BUILDDIR)/fatal_bflatpush-arm.err; \
	grep -q 'paslang: stack overflow at line 12' $(BUILDDIR)/fatal_deep-arm.err; \
	grep -q 'paslang: out of memory: [0-9][0-9]* MiB mapped' $(BUILDDIR)/fatal_oom-arm.err; \
	grep -q 'paslang: send on closed channel at line 11' $(BUILDDIR)/fatal_closed-arm.err; \
	grep -q 'paslang: uncaught raise in the main routine' $(BUILDDIR)/fatal_mainraise-arm.err; \
	grep -q 'paslang: uncaught raise in the main routine: EOops' $(BUILDDIR)/fatal_raiseobj-arm.err; \
	grep -q 'paslang: set element 300 out of range \[0..255\] at line 16' $(BUILDDIR)/fatal_setelem-arm.err; \
	grep -q 'paslang: set element 1 out of range \[2..7\] at line 16' $(BUILDDIR)/fatal_setincl-arm.err; \
	grep -q 'paslang: integer divide by zero at line 13' $(BUILDDIR)/fatal_divloop-arm.err; \
	grep -q 'paslang: index 10 out of range \[0..4\] at line 11' $(BUILDDIR)/fatal_bstatic-arm.err; \
	grep -q 'paslang: index 9 out of range \[0..4\] at line 17' $(BUILDDIR)/fatal_exprarg-arm.err; \
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
	grep -q 'paslang: concurrent json builder use' $(BUILDDIR)/fatal_jsonbusy-arm.err; \
	grep -q 'paslang: concurrent json reader use' $(BUILDDIR)/fatal_jsonrbusy-arm.err; \
	grep -q 'paslang: concurrent json writer use' $(BUILDDIR)/fatal_jsonwbusy-arm.err; \
	grep -q 'paslang: index 4 out of range \[1..3\] at line 16' $(BUILDDIR)/fatal_bstrcall-arm.err; \
	grep -q '^paslang: string view length -2 out of range$$' $(BUILDDIR)/fatal_svneg-arm.err; \
	grep -q '^paslang: string view of nil with length 3$$' $(BUILDDIR)/fatal_svnil-arm.err; \
	grep -q '^paslang: string view over bytes not marked shared$$' $(BUILDDIR)/fatal_svmark-arm.err; \
	grep -q '^paslang: string view length 16 out of range$$' $(BUILDDIR)/fatal_svwrap-arm.err; \
	echo ok fatal-arm; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -Fu $(A64DIR) -o $(BUILDDIR)/brokenpipe_die-arm testdata/brokenpipe.paslang; \
	(set +e; $(QEMU_A64) $(BUILDDIR)/brokenpipe_die-arm out; echo $$? > $(BUILDDIR)/brokenpipe_out-arm.rc) | head -c 1 > /dev/null; \
	(set +e; $(QEMU_A64) $(BUILDDIR)/brokenpipe_die-arm err; echo $$? > $(BUILDDIR)/brokenpipe_err-arm.rc) 2>&1 > /dev/null | head -c 1 > /dev/null; \
	test "`cat $(BUILDDIR)/brokenpipe_out-arm.rc` `cat $(BUILDDIR)/brokenpipe_err-arm.rc`" = "141 141"; \
	echo ok brokenpipe-arm; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -Fu $(A64DIR) -o $(BUILDDIR)/jsonpark1-arm testdata/jsonpark.paslang; \
	taskset -c 0 timeout 600 $(QEMU_A64) $(BUILDDIR)/jsonpark1-arm > $(BUILDDIR)/jsonpark1-arm.got; \
	diff -u testdata/jsonpark.out $(BUILDDIR)/jsonpark1-arm.got; \
	echo ok jsonpark-arm; \
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
	for t in hello values control routines varargs records scopedtypes classes registry helpers convert report money systemerrors boundedfiles filemetadata directories paths environments processes temporaryresources systempaths textbuilding textencoding textbuffers valuehelpers identifiers generics errors excobjects bank concurrent blockedio fanin maps sync wordcount strings maths narrow pointers single quad bits rotations carry bigrot bitfields wide atomics views vectors machine assembly hashes closures slices properties cleanup pipeline kvstore sorting timeout digest bitmap trees dates jsonread jsonwrite jsonlang jsonbind jsonunbind jsonstream; do \
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
	python3 -I scripts/check_maporder.py $$(ls $(BUILDDIR)/ex_*-arm); \
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
	: native and cross defaults intentionally differ, so compare identical explicit CPU profiles; \
	for cpu in base max; do \
	  model=max; if [ $$cpu = base ]; then model=cortex-a53; fi; \
	  timeout 60 $(QEMU_A64) -cpu $$model $(OUTDIR)/paslangc-arm64 -cpu $$cpu -o $(BUILDDIR)/hello-byarm-$$cpu testdata/hello.paslang > $(BUILDDIR)/hello-byarm-$$cpu.log 2>&1; \
	  test -s $(BUILDDIR)/hello-byarm-$$cpu.s; \
	  $(OUTDIR)/paslangc -target arm64 -cpu $$cpu -o $(BUILDDIR)/hello-bycross-$$cpu testdata/hello.paslang; \
	  diff -u $(BUILDDIR)/hello-byarm-$$cpu.s $(BUILDDIR)/hello-bycross-$$cpu.s; \
	  timeout 20 $(QEMU_A64) -cpu $$model $(BUILDDIR)/hello-byarm-$$cpu > $(BUILDDIR)/hello-byarm-$$cpu.got; \
	  diff -u testdata/hello.out $(BUILDDIR)/hello-byarm-$$cpu.got; \
	done; \
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
	: every routine of an arm64 program starts on 32 bytes, P267; \
	bad=$$(nm -n $(BUILDDIR)/hello-arm | grep -E ' [Tt] (p_|rt_)' | while read a t n; do if [ $$((0x$$a % 32)) -ne 0 ]; then echo $$n; fi; done | wc -l); \
	test "$$bad" -eq 0 || { echo "hello-arm: $$bad routines do not start on 32 bytes"; exit 1; }; \
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
	echo "==== unit block results arm64 (P153) ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/a64/blobu testdata/units/blobu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/blobuse-arm testdata/units/blobuse.paslang; \
	$(QEMU_A64) $(BUILDDIR)/blobuse-arm > $(BUILDDIR)/blobuse-arm.got; \
	diff -u testdata/units/blobuse.out $(BUILDDIR)/blobuse-arm.got; \
	echo ok blobuse-arm; \
	echo "==== unit operators arm64 (P157) ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/a64/opvecu testdata/units/opvecu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/a64/opcolu testdata/units/opcolu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/opvecuse-arm testdata/units/opvecuse.paslang; \
	$(QEMU_A64) $(BUILDDIR)/opvecuse-arm > $(BUILDDIR)/opvecuse-arm.got; \
	diff -u testdata/units/opvecuse.out $(BUILDDIR)/opvecuse-arm.got; \
	echo ok opvecuse-arm; \
	echo "==== a unit's class helper constructor arm64 (P170) ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/a64/helpctoru testdata/units/helpctoru.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/helpctoruse-arm testdata/units/helpctoruse.paslang; \
	$(QEMU_A64) $(BUILDDIR)/helpctoruse-arm > $(BUILDDIR)/helpctoruse-arm.got; \
	diff -u testdata/units/helpctoruse.out $(BUILDDIR)/helpctoruse-arm.got; \
	echo ok helpctoruse-arm; \
	echo "==== a unit's record operators arm64 (P171) ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/a64/recopsu testdata/units/recopsu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/recopsuse-arm testdata/units/recopsuse.paslang; \
	$(QEMU_A64) $(BUILDDIR)/recopsuse-arm > $(BUILDDIR)/recopsuse-arm.got; \
	diff -u testdata/units/recopsuse.out $(BUILDDIR)/recopsuse-arm.got; \
	echo ok recopsuse-arm; \
	echo "==== a unit's operators of one operand arm64 (P381) ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/a64/opunu testdata/units/opunu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/opunuse-arm testdata/units/opunuse.paslang; \
	$(QEMU_A64) $(BUILDDIR)/opunuse-arm > $(BUILDDIR)/opunuse-arm.got; \
	diff -u testdata/units/opunuse.out $(BUILDDIR)/opunuse-arm.got; \
	echo ok opunuse-arm; \
	echo "==== a unit's json constants arm64 (P209) ===="; \
	$(OUTDIR)/paslangc -target arm64 -o $(BUILDDIR)/a64/jsonconstu testdata/units/jsonconstu.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/jsonconstuse-arm testdata/units/jsonconstuse.paslang; \
	$(QEMU_A64) $(BUILDDIR)/jsonconstuse-arm > $(BUILDDIR)/jsonconstuse-arm.got; \
	diff -u testdata/units/jsonconstuse.out $(BUILDDIR)/jsonconstuse-arm.got; \
	echo ok jsonconstuse-arm; \
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
	$(OUTDIR)/paslangc -target arm64 -debug -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/jsondbg-arm testdata/jsondbg.paslang; \
	timeout 120 $(QEMU_A64) $(BUILDDIR)/jsondbg-arm --debug-mode < testdata/jsondbg.in > $(BUILDDIR)/jsondbg-arm.got 2>&1; \
	diff -u testdata/jsondbg.out $(BUILDDIR)/jsondbg-arm.got; \
	echo ok debug-console-arm; \
	echo "==== network servers arm64 ===="; \
	$(OUTDIR)/paslangc -target arm64 -c src/lib/pasnet.paslang; \
	for t in httpd dnsd termd ftpd ntpd wsd chat proxy apisrv; do \
	  $(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/ex_$$t-arm examples/$$t.paslang; \
	  timeout 120 $(QEMU_A64) $(BUILDDIR)/ex_$$t-arm -selftest 300 > $(BUILDDIR)/ex_$$t-arm.got; \
	done; \
	printf '300 clients, 900 requests, 900 served, 0 bad\nstats.json: 301 connections, 901 requests, 0 bad\n' | diff -u - $(BUILDDIR)/ex_httpd-arm.got; \
	echo "300 clients, 300 answered, 0 missed, 0 bad" | diff -u - $(BUILDDIR)/ex_dnsd-arm.got; \
	echo "300 sessions, 300 quit, 0 bad" | diff -u - $(BUILDDIR)/ex_termd-arm.got; \
	echo "300 sessions, 300 stored, 300 fetched, 0 bad" | diff -u - $(BUILDDIR)/ex_ftpd-arm.got; \
	echo "300 queries, 300 answered, 0 missed, 0 bad" | diff -u - $(BUILDDIR)/ex_ntpd-arm.got; \
	echo "300 clients, 900 frames, 900 echoed, 0 bad" | diff -u - $(BUILDDIR)/ex_wsd-arm.got; \
	echo "300 clients, 300 said, 2700 delivered of 2700, 0 bad" | diff -u - $(BUILDDIR)/ex_chat-arm.got; \
	echo "300 clients, 300 forwarded, 900 requests, 900 served, 0 bad" | diff -u - $(BUILDDIR)/ex_proxy-arm.got; \
	echo "300 clients, 900 requests, 900 served, 0 bad" | diff -u - $(BUILDDIR)/ex_apisrv-arm.got; \
	: P210 JSON-RPC over NDJSON, its 2000 clients under qemu too; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(BUILDDIR)/a64 -o $(BUILDDIR)/ex_jsonrpc-arm examples/jsonrpc.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/ex_jsonrpc-arm -selftest 2000 > $(BUILDDIR)/ex_jsonrpc-arm.got; \
	diff -u examples/jsonrpc.out $(BUILDDIR)/ex_jsonrpc-arm.got; \
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
	@set -e; \
	: P403 on arm64: SQLite files the C library writes read under qemu, its locks kept; \
	python3 -I scripts/sqlfixtures.py $(BUILDDIR)/sqlfx-arm; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -Fu $(A64DIR) -o $(BUILDDIR)/sqlread-arm testdata/sqlread.paslang; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/sqlread0-arm testdata/sqlread.paslang; \
	for d in p512 p65536 big wr u16le u16be nocase free; do \
	  timeout 600 $(QEMU_A64) $(BUILDDIR)/sqlread-arm $(BUILDDIR)/sqlfx-arm/$$d.db > $(BUILDDIR)/sqlfx-arm/$$d.got; \
	  cmp $(BUILDDIR)/sqlfx-arm/$$d.exp $(BUILDDIR)/sqlfx-arm/$$d.got; \
	done; \
	for d in p1024 wr u16be; do \
	  timeout 600 $(QEMU_A64) $(BUILDDIR)/sqlread0-arm $(BUILDDIR)/sqlfx-arm/$$d.db > $(BUILDDIR)/sqlfx-arm/$$d.got0; \
	  cmp $(BUILDDIR)/sqlfx-arm/$$d.exp $(BUILDDIR)/sqlfx-arm/$$d.got0; \
	done; \
	python3 -I scripts/check_sqllock.py $(BUILDDIR)/sqlread-arm $(BUILDDIR)/sqlfx-arm/wr.db $(QEMU_A64); \
	echo ok sqlread-arm
	@set -e; \
	: P417 and P418 on arm64: a unit item nothing reaches leaves the program, SQLite is the library unit sqlite; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/gc_hello-arm testdata/hello.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/gc_sqlnone-arm testdata/sqlnone.paslang; \
	$(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/gc_sqluses-arm testdata/sqluses.paslang; \
	python3 -I scripts/check_gcsections.py $(BUILDDIR)/gc_hello-arm $(BUILDDIR)/gc_sqlnone-arm $(BUILDDIR)/gc_sqluses-arm --arm; \
	timeout 25 $(QEMU_A64) $(BUILDDIR)/gc_sqlnone-arm | grep -qx 'names sqlite, reaches none of it'; \
	if $(OUTDIR)/paslangc -target arm64 -Fu $(A64DIR) -o $(BUILDDIR)/gc_sqlnouses-arm testdata/sqlnouses.paslang > $(BUILDDIR)/gc_sqlnouses-arm.err 2>&1; then \
	  echo 'sqlnouses: TSqlite with no uses sqlite should not compile'; exit 1; \
	fi; \
	grep -qF 'unknown type TSqlite at 7:7' $(BUILDDIR)/gc_sqlnouses-arm.err; \
	echo ok gcsections-arm
	@set -e; \
	: P404 on arm64: SQL read as the SQLite parser reads it under qemu; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -Fu $(A64DIR) -o $(BUILDDIR)/sqlparse-arm testdata/sqlparse.paslang; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/sqlparse0-arm testdata/sqlparse.paslang; \
	timeout 600 $(QEMU_A64) $(BUILDDIR)/sqlparse-arm testdata/sqlparse.sql > $(BUILDDIR)/sqlparse-arm.got; \
	cmp testdata/sqlparse.out $(BUILDDIR)/sqlparse-arm.got; \
	timeout 600 $(QEMU_A64) $(BUILDDIR)/sqlparse0-arm testdata/sqlparse.sql > $(BUILDDIR)/sqlparse0-arm.got; \
	cmp testdata/sqlparse.out $(BUILDDIR)/sqlparse0-arm.got; \
	echo ok sqlparse-arm
	@set -e; \
	: P405 on arm64: every script of testdata/sqlite as SQLite answers it, the unit beside the system SQLite, routines; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -Fu $(A64DIR) -o $(BUILDDIR)/sqlapi-arm testdata/sqlapi.paslang; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/sqlapi0-arm testdata/sqlapi.paslang; \
	python3 -I scripts/check_sqlapi.py $(BUILDDIR)/sqlapi-arm $(BUILDDIR)/sqlapi-arm.d $(QEMU_A64) --corpus; \
	python3 -I scripts/check_sqlapi.py $(BUILDDIR)/sqlapi0-arm $(BUILDDIR)/sqlapi0-arm.d $(QEMU_A64); \
	: P411 on arm64: the math functions with FMADD, as on amd64; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -Fu $(A64DIR) -o $(BUILDDIR)/sqlmath-arm testdata/sqlmath.paslang; \
	timeout 600 $(QEMU_A64) $(BUILDDIR)/sqlmath-arm > $(BUILDDIR)/sqlmath-arm.got; \
	cmp testdata/sqlmath.out $(BUILDDIR)/sqlmath-arm.got; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -Fu $(A64DIR) -o $(BUILDDIR)/sqlcompat-arm testdata/sqlcompat.paslang; \
	python3 -I scripts/check_sqlite.py $(BUILDDIR)/sqlcompat-arm $(BUILDDIR)/sqlcompat-arm.d $(QEMU_A64); \
	$(OUTDIR)/paslangc -target arm64 -cpu max -Fu $(A64DIR) -o $(BUILDDIR)/sqlroutines-arm testdata/sqlroutines.paslang; \
	rm -f $(BUILDDIR)/sqlroutines-arm.db $(BUILDDIR)/sqlroutines-arm.db-wal $(BUILDDIR)/sqlroutines-arm.db-shm; \
	timeout 600 $(QEMU_A64) $(BUILDDIR)/sqlroutines-arm $(BUILDDIR)/sqlroutines-arm.db > $(BUILDDIR)/sqlroutines-arm.got; \
	cmp testdata/sqlroutines.out $(BUILDDIR)/sqlroutines-arm.got; \
	echo ok sqlapi-arm
	@set -e; \
	: P439 on arm64: signals, each child the program again under qemu, given as the first argument, and under the collector stress; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -Fu $(A64DIR) -o $(BUILDDIR)/signals-arm testdata/signals.paslang; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/signals0-arm testdata/signals.paslang; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/signals-arm $(QEMU_A64) > $(BUILDDIR)/signals-arm.got; \
	diff -u testdata/signals.out $(BUILDDIR)/signals-arm.got; \
	timeout 300 $(QEMU_A64) $(BUILDDIR)/signals0-arm $(QEMU_A64) > $(BUILDDIR)/signals0-arm.got; \
	diff -u testdata/signals.out $(BUILDDIR)/signals0-arm.got; \
	PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=3 PASLANG_GCPOISON=1 timeout 1800 $(QEMU_A64) $(BUILDDIR)/signals0-arm $(QEMU_A64) > $(BUILDDIR)/signals0-arm.vgot; \
	diff -u testdata/signals.out $(BUILDDIR)/signals0-arm.vgot; \
	echo ok signals-arm
	@set -e; \
	: P434 on arm64: the HTTP server with no inlining under qemu, and the sockets systemd passes through it; \
	$(OUTDIR)/paslangc -target arm64 -cpu base -inline 0 -Fu $(A64DIR) -o $(BUILDDIR)/httpsrv0-arm testdata/httpsrv.paslang; \
	timeout 600 $(QEMU_A64) $(BUILDDIR)/httpsrv0-arm > $(BUILDDIR)/httpsrv0-arm.got; \
	diff -u testdata/httpsrv.out $(BUILDDIR)/httpsrv0-arm.got; \
	$(OUTDIR)/paslangc -target arm64 -cpu max -Fu $(A64DIR) -o $(BUILDDIR)/httpsrv-sd-arm testdata/httpsrv.paslang; \
	timeout 600 python3 -I scripts/check_httpsystemd.py $(BUILDDIR)/httpsrv-sd-arm $(QEMU_A64); \
	echo ok httpsrv-arm

install: all installdirs
	$(NORMAL_INSTALL)
	$(INSTALL_PROGRAM) $(OUTDIR)/paslangc $(DESTDIR)$(bindir)/paslangc
	$(INSTALL_PROGRAM) $(OUTDIR)/pasdbg $(DESTDIR)$(bindir)/pasdbg
	if [ -x $(OUTDIR)/paslangc-arm64 ]; then \
	  $(INSTALL_PROGRAM) $(OUTDIR)/paslangc-arm64 $(DESTDIR)$(bindir)/paslangc-arm64; \
	fi
	$(PRE_INSTALL)
	: P418, passqlite was a unit of the core up to 1.1.246 and is the library unit sqlite now, its old files go so that uses passqlite finds none; \
	rm -f $(DESTDIR)$(libdir)/paslang/passqlite.pi $(DESTDIR)$(libdir)/paslang/passqlite.o \
	  $(DESTDIR)$(libdir)/paslang/$(LVL_X64)/passqlite.o \
	  $(DESTDIR)$(libdir)/paslang/aarch64/passqlite.pi $(DESTDIR)$(libdir)/paslang/aarch64/passqlite.o \
	  '$(DESTDIR)$(libdir)/paslang/aarch64/$(LVL_A64)/passqlite.o'
	: the amd64 units, built on amd64, AMD64: every core unit, passtr too, P143: a list written out left it behind; \
	if [ -n '$(AMD64)' ]; then \
	  for u in $(CORE_UNITS) $(LIB_UNITS); do \
	    b=$$(basename $$u .paslang); \
	    $(INSTALL_DATA) $(BUILDDIR)/$$b.pi $(BUILDDIR)/$$b.o $(DESTDIR)$(libdir)/paslang/; \
	  done; \
	fi
	: the level builds, P143; \
	if [ -n '$(AMD64)' ]; then \
	  mkdir -p $(DESTDIR)$(libdir)/paslang/$(LVL_X64); \
	  for u in $(CORE_UNITS) $(LIB_UNITS); do \
	    b=$$(basename $$u .paslang); \
	    $(INSTALL_DATA) $(BUILDDIR)/$(LVL_X64)/$$b.o $(DESTDIR)$(libdir)/paslang/$(LVL_X64)/; \
	  done; \
	fi
	: the arm64 units when make built them, ARM64; \
	if [ -n '$(ARM64)' ]; then \
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
	: the program and what the compile wrote beside it, so a root install leaves nothing of root in build/
	rm -f $(BUILDDIR)/paslang-install-hello $(BUILDDIR)/paslang-install-hello.s $(BUILDDIR)/paslang-install-hello.o $(BUILDDIR)/paslang-install-hello.ld $(BUILDDIR)/paslang-install-hello.link
	: an arm64 program from amd64 when the arm64 units were asked for, since on arm64 hello was one; \
	if [ -n '$(AMD64)' ] && [ -n '$(ARM64)' ]; then \
	  $(DESTDIR)$(bindir)/paslangc -target arm64 -o $(BUILDDIR)/paslang-install-a64 $(srcdir)/testdata/heapspan.paslang; \
	  rm -f $(BUILDDIR)/paslang-install-a64 $(BUILDDIR)/paslang-install-a64.s $(BUILDDIR)/paslang-install-a64.o $(BUILDDIR)/paslang-install-a64.ld $(BUILDDIR)/paslang-install-a64.link; \
	fi

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
	    cp $(OUTDIR)/paslangc-base $$d/bin/paslangc; \
	    cp $(OUTDIR)/pasdbg $$d/bin/; \
	    for u in $(CORE_UNITS) $(LIB_UNITS); do \
	      b=$$(basename $$u .paslang); cp $(BUILDDIR)/$$b.pi $(BUILDDIR)/$$b.o $$d/lib/paslang/; \
	      cp $(BUILDDIR)/$(LVL_X64)/$$b.o $$d/lib/paslang/$(LVL_X64)/; \
	    done; \
	  else \
	    cp $(OUTDIR)/paslangc-arm64 $$d/bin/paslangc; \
	    $(OUTDIR)/paslangc -target arm64 -cpu base -Fu $(A64DIR) -o $$d/bin/pasdbg cmd/pasdbg/pasdbg.paslang; \
	    rm -f $$d/bin/pasdbg.o $$d/bin/pasdbg.s $$d/bin/pasdbg.ld $$d/bin/pasdbg.link; \
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

# Validate all archive formats and execute both relocated package compilers.
check-release: release-assets
	python3 scripts/check_release.py

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
	mkdir -p $(DESTDIR)$(bindir) $(DESTDIR)$(libdir)/paslang
	if [ -n '$(AMD64)' ]; then \
	  mkdir -p $(DESTDIR)$(libdir)/paslang/$(LVL_X64); \
	fi
	if [ -n '$(ARM64)' ]; then \
	  mkdir -p $(DESTDIR)$(libdir)/paslang/aarch64 '$(DESTDIR)$(libdir)/paslang/aarch64/$(LVL_A64)'; \
	fi

installcheck:
	$(DESTDIR)$(bindir)/paslangc -o $(BUILDDIR)/paslang-installcheck $(srcdir)/testdata/hello.paslang
	$(BUILDDIR)/paslang-installcheck
	rm -f $(BUILDDIR)/paslang-installcheck $(BUILDDIR)/paslang-installcheck.s $(BUILDDIR)/paslang-installcheck.o $(BUILDDIR)/paslang-installcheck.ld $(BUILDDIR)/paslang-installcheck.link
	$(DESTDIR)$(bindir)/paslangc -o $(BUILDDIR)/paslang-installcheck-who $(srcdir)/examples/pasroutines/who.paslang
	$(BUILDDIR)/paslang-installcheck-who
	rm -f $(BUILDDIR)/paslang-installcheck-who $(BUILDDIR)/paslang-installcheck-who.s $(BUILDDIR)/paslang-installcheck-who.o $(BUILDDIR)/paslang-installcheck-who.ld $(BUILDDIR)/paslang-installcheck-who.link

mostlyclean:

distclean: clean
	rm -f config.mk config.status config.log

maintainer-clean:
	@echo 'This command is intended for maintainers to use; it'
	@echo 'deletes files that may need special tools to rebuild.'
	$(MAKE) distclean

clean:
	rm -rf $(OUTDIR) $(BUILDDIR)
