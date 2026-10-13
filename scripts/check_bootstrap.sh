#!/bin/sh
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
# P262: paslangc from its own assembly, the seed, with as and ld alone,
# then two stages of the current sources; no other compiler anywhere
# (Reglas 9 and 15). Until P262 (P182 on) Free Pascal built the first
# compiler here.
set -eu
build_dir=$1
qemu=$2
shift 2
# the rest: the core units, in the Makefile's order (CORE_UNITS)
# One directory, emptied on each run and removed when the check passes:
# a failure stays for inspection, nothing accumulates in the build tree.
work_dir=$build_dir/check-bootstrap
rm -rf "$work_dir"
mkdir -p "$work_dir"
work_dir=$(readlink -f "$work_dir")
mkdir -p "$work_dir/build"

# Nothing in the build, its scripts or its tests runs Free Pascal: the
# word as a command, in the Makefile, configure and the scripts.
if grep -n -E '(^|[[:space:];|&(])fpc([[:space:]]|$)|"fpc"|\<HOSTC\>' Makefile configure scripts/*.sh scripts/*.py \
    | grep -v '^scripts/check_bootstrap.sh:'; then
    echo 'the build still names fpc as a command (Regla 15)'; exit 1
fi
for f in src/lib/*.paslang src/compiler/*.paslang src/rtl/*.paslang cmd/paslangc/*.paslang; do
    if grep -n -i -E '\{\$(ifdef|ifndef) (FPC|PASLANG)\}|\{\$mode ' "$f"; then
        echo "$f carries code for another compiler (Regla 15)"; exit 1
    fi
done

# amd64: the seed gives the boot compiler with as and ld alone.
python3 scripts/bootstrap_seed.py build --seed bootstrap/seed-amd64.tar.xz --out "$work_dir/seed" \
    > "$work_dir/seed.log" 2>&1 || { cat "$work_dir/seed.log"; exit 1; }
for stage in 1 2; do
    boot="$work_dir/seed/paslangc"
    if test "$stage" = 2; then boot="$work_dir/native-1"; fi
    timeout 180 make --no-print-directory stage HOST="$boot" STAGE="$work_dir/native-$stage" \
        STAGE_DIR="$work_dir/stage-$stage" BUILDDIR="$work_dir/build" > "$work_dir/stage-$stage.log" 2>&1 || {
        cat "$work_dir/stage-$stage.log"; exit 1;
    }
done
cc -std=c11 -O2 -Wall -Wextra -Werror -o "$work_dir/env-launcher" testdata/sysenvironment_launcher.c
for source in bootstrapcore quadconst valround valunsigned; do
    timeout 30 "$work_dir/native-2" -cpu base -Fu "$work_dir/stage-2/core" \
        -Fu "$work_dir/stage-2" \
        -o "$work_dir/$source-native" "testdata/$source.paslang"
    if test "$source" = bootstrapcore; then
        timeout 30 "$work_dir/env-launcher" "$work_dir/$source-native" > "$work_dir/$source.got"
    else
        timeout 30 "$work_dir/$source-native" > "$work_dir/$source.got"
    fi
    diff -u "testdata/$source.out" "$work_dir/$source.got"
done

# arm64: its seed with the arm64 as and ld; under qemu, the compiler it
# gives compiles the core units and hello for arm64, and hello runs.
python3 scripts/bootstrap_seed.py build --seed bootstrap/seed-arm64.tar.xz --out "$work_dir/seed-arm" \
    --as /usr/bin/aarch64-linux-gnu-as --ld /usr/bin/aarch64-linux-gnu-ld --run "$qemu" \
    > "$work_dir/seed-arm.log" 2>&1 || { cat "$work_dir/seed-arm.log"; exit 1; }
mkdir -p "$work_dir/core-arm"
for u in "$@"; do
    b=$(basename "$u" .paslang)
    timeout 300 "$qemu" "$work_dir/seed-arm/paslangc" -cpu base -c -Fu "$work_dir/core-arm" \
        -o "$work_dir/core-arm/$b" "$u"
done
timeout 300 "$qemu" "$work_dir/seed-arm/paslangc" -Fu "$work_dir/core-arm" -o "$work_dir/hello-arm" testdata/hello.paslang
test "$(timeout 30 "$qemu" "$work_dir/hello-arm")" = "hello world"
rm -rf "$work_dir"
echo 'ok bootstrap from the seed with as and ld (amd64 two stages, arm64 under qemu), no other compiler'
