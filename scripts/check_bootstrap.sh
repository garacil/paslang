#!/bin/sh
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
# P182: isolated FPC bootstrap, followed by two native stages.
set -eu
build_dir=$1
work_dir=$(mktemp -d "$build_dir/bootstrap-XXXXXX")
work_dir=$(readlink -f "$work_dir")
host_dir="$work_dir/host"
mkdir -p "$host_dir" "$work_dir/units" "$work_dir/build"
cp src/compiler/*.paslang src/lib/*.paslang "$host_dir/"
cp cmd/paslangc/paslangc.paslang "$host_dir/paslangc.pas"
for source in "$host_dir"/*.paslang; do mv "$source" "${source%.paslang}.pas"; done
python3 scripts/host_syscall.py "$host_dir"
fpc -Mobjfpc -Scgi -O2 -Fu"$host_dir" -FE"$work_dir" -FU"$work_dir/units" \
    -gl -vwnh -Sewnh -vm11030,11031,6018 "$host_dir/paslangc.pas" > "$work_dir/fpc.log" 2>&1 || {
    cat "$work_dir/fpc.log"; exit 1;
}
cc -std=c11 -O2 -Wall -Wextra -Werror -o "$work_dir/env-launcher" testdata/sysenvironment_launcher.c
fpc -Mobjfpc -Scgi -O2 -Fu"$host_dir" -FE"$work_dir" -FU"$work_dir/units" \
    -gl -vwnh -Sewnh -vm11030,11031,6018 testdata/bootstrapcore.paslang > "$work_dir/fpc-core.log" 2>&1 || {
    cat "$work_dir/fpc-core.log"; exit 1;
}
timeout 30 "$work_dir/env-launcher" "$work_dir/bootstrapcore" > "$work_dir/fpc-core.got"
diff -u testdata/bootstrapcore.out "$work_dir/fpc-core.got"
fpc -Mobjfpc -Scgi -O2 -Fu"$host_dir" -FE"$work_dir" -FU"$work_dir/units" \
    -gl -vwnh -Sewnh -vm11030,11031,6018 testdata/currencykernelmodel.paslang > "$work_dir/fpc-currency.log" 2>&1 || {
    cat "$work_dir/fpc-currency.log"; exit 1;
}
python3 scripts/check_currency.py "$work_dir/currencykernelmodel"
# Use the project's actual stage recipe, not a second dependency list.
# All generated artifacts live in our exclusive directory.
for stage in 1 2; do
    boot="$work_dir/paslangc"
    if test "$stage" = 2; then boot="$work_dir/native-1"; fi
    timeout 180 make --no-print-directory stage HOST="$boot" STAGE="$work_dir/native-$stage" \
        STAGE_DIR="$work_dir/stage-$stage" BUILDDIR="$work_dir/build" > "$work_dir/stage-$stage.log" 2>&1 || {
        cat "$work_dir/stage-$stage.log"; exit 1;
    }
done
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
echo 'ok clean FPC bootstrap, integer/environment fixture and two native stages'
