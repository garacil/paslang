#!/bin/sh
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
# P169/P176/P177: scopes, generic identities and exported aliases.
set -eu

compiler=$1
build_dir=$2
shift 2
test "$#" -gt 0

assert_rejected() {
    rejected_source=$1
    expected_error=$2
    if "$compiler" -target "$target" -Fu "$work_dir" -Fu "$core_dir" \
        -o "$work_dir/rejected" "$rejected_source" > "$work_dir/rejected.err" 2>&1; then
        echo "accepted invalid source: $rejected_source" >&2
        exit 1
    fi
    if ! grep -qF "$expected_error" "$work_dir/rejected.err"; then
        cat "$work_dir/rejected.err" >&2
        exit 1
    fi
}

for target in amd64 arm64; do
    work_dir="$build_dir/scoped-types/$target"
    core_dir=$build_dir
    if test "$target" = arm64; then core_dir="$build_dir/a64"; fi
    mkdir -p "$work_dir"
    for level in 0 40; do
        for unit in nestedu nestedwrap nestedgu genericu generica genericb genericwrap aliasu aliaswrap; do
            "$compiler" -target "$target" -inline "$level" -c \
                -Fu "$work_dir" -Fu "$core_dir" -o "$work_dir/$unit.o" \
                "testdata/units/$unit.paslang"
        done
        for source in nestednames nestedmore nestedgeneric genericlocal gen \
            units/nesteduse units/nestedguse units/genericprobe units/genericuse units/aliasuse; do
            name=${source##*/}
            binary="$work_dir/$name-$level"
            "$compiler" -target "$target" -inline "$level" -Fu "$work_dir" \
                -Fu "$core_dir" -o "$binary" "testdata/$source.paslang"
            if test "$target" = arm64; then
                env PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 \
                    timeout 60 "$@" "$binary" > "$binary.got"
            else
                env PASLANG_GCVERIFY=1 PASLANG_GCSTRESS=1 PASLANG_GCPOISON=1 \
                    timeout 60 "$binary" > "$binary.got"
            fi
            diff -u "testdata/$source.out" "$binary.got"
        done
    done
    for spec in \
        'genericbadarg:TCell<TItem> does not go into TCell<TItem>; x as T sees its bytes at 9:14' \
        'genericbadorigin:TOther<Integer> does not go into TOther<Integer>; x as T sees its bytes at 9:14' \
        'genericbadname:unknown type TCell_string at 7:8' \
        'nestpriv1:UnitOnly is private to TInfo at 3:29' \
        'nestpriv2:TUnitOnly is private to TInfo at 3:8' \
        'nestpriv3:Hidden is strict private to TInfo at 3:35' \
        'nestpriv4:THidden is strict private to TInfo at 3:8'; do
        name=${spec%%:*}
        assert_rejected "testdata/units/$name.paslang" "${spec#*:}"
    done
    for spec in \
        'classvarconst:duplicate identifier TOuter.N (a variable of the name) at 5:9' \
        'constfield:N is a field already at 8:1' \
        'fieldconst:N is a field already at 6:1' \
        'helperconst:N is a method already at 7:6' \
        'leak:unknown identifier N at 6:16' \
        'methodtype:N is a method already at 6:1' \
        'privateconst:N is strict private to TOuter at 7:23' \
        'privatetype:TNum is strict private to TOuter at 7:8' \
        'protectedtype:TNum is strict protected to TOuter at 7:8' \
        'shadowtype:unknown type TNum at 9:8' \
        'typemethod:N is a method already at 7:4' \
        'typeproperty:N is a property already at 9:1'; do
        name=${spec%%:*}
        assert_rejected "testdata/nestedbad/$name.paslang" "${spec#*:}"
    done
    echo "ok scoped-types $target (inline 0/40, GC verify/stress/poison, rejects)"
done
