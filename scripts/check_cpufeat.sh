#!/bin/sh
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
# P196: a kernel word calls its processor body only when the -cpu the
# program is compiled for has every feature that body uses. For each
# -cpu of a matrix, testdata/cpufeat is compiled, the .s is read for the
# body each word calls, and the program runs (arm64 under qemu) and must
# print testdata/cpufeat.out. The SHA-NI bodies need sha, ssse3 and
# sse41 on amd64: -cpu sha and -cpu sha,ssse3 must keep the base body.
set -eu
compiler=$1
build_dir=$2
qemu=$3
work_dir=$build_dir/check-cpufeat
rm -rf "$work_dir"
mkdir -p "$work_dir"

# expect TARGET SPEC WORD... : each WORD is name=cpu or name=base
expect() {
    target=$1
    spec=$2
    shift 2
    out=$work_dir/cpufeat-$target-$(printf '%s' "$spec" | tr ',+.' '___')
    "$compiler" -target "$target" -cpu "$spec" -o "$out" testdata/cpufeat.paslang
    for want in "$@"; do
        name=${want%=*}
        body=${want#*=}
        if [ "$body" = cpu ]; then other=base; else other=cpu; fi
        if ! grep -qE "_pas${name}${body}([^a-z0-9]|\$)" "$out.s"; then
            echo "cpufeat $target -cpu $spec: $name does not call its $body body"
            exit 1
        fi
        if grep -qE "_pas${name}${other}([^a-z0-9]|\$)" "$out.s"; then
            echo "cpufeat $target -cpu $spec: $name calls its $other body"
            exit 1
        fi
    done
    if [ "$target" = arm64 ]; then
        timeout 120 "$qemu" "$out" > "$out.got"
    elif runs_here "$spec"; then
        timeout 60 "$out" > "$out.got"
    else
        return 0
    fi
    diff -u testdata/cpufeat.out "$out.got"
}

# An amd64 program runs only on a processor with every flag its -cpu
# names (/proc/cpuinfo); the .s is read for every -cpu, here or not.
runs_here() {
    case $1 in
        base) need= ;;
        sha) need=sha_ni ;;
        sha,ssse3) need='sha_ni ssse3' ;;
        sha,sse41) need='sha_ni sse4_1' ;;
        sha,ssse3,sse41) need='sha_ni ssse3 sse4_1' ;;
        v2) need='pni ssse3 sse4_1 sse4_2 popcnt cx16' ;;
        pclmul) need=pclmulqdq ;;
        pclmul,sse41) need='pclmulqdq sse4_1' ;;
        v3) need='pni ssse3 sse4_1 sse4_2 popcnt cx16 avx avx2 bmi1 bmi2 fma f16c movbe abm' ;;
        *) return 1 ;;
    esac
    flags=" $(grep -m1 '^flags' /proc/cpuinfo | cut -d: -f2) "
    for f in $need; do
        case $flags in
            *" $f "*) ;;
            *) return 1 ;;
        esac
    done
    return 0
}

sha='sha1 sha256 sha224 hmac merkleroot'
each() {
    body=$1
    shift
    for w in "$@"; do printf '%s=%s ' "$w" "$body"; done
}

# amd64: the SHA-NI bodies need sha, ssse3 and sse41; CRC-32 pclmul and
# sse41; CRC-32C sse42; the search avx2.
expect amd64 base $(each base $sha crc32 crc32c poschar)
expect amd64 sha $(each base $sha crc32 crc32c poschar)
expect amd64 sha,ssse3 $(each base $sha crc32 crc32c poschar)
expect amd64 sha,sse41 $(each base $sha crc32 crc32c poschar)
expect amd64 sha,ssse3,sse41 $(each cpu $sha) $(each base crc32 crc32c poschar)
expect amd64 v2 $(each base $sha crc32 poschar) crc32c=cpu
expect amd64 pclmul $(each base $sha crc32 crc32c poschar)
expect amd64 pclmul,sse41 $(each base $sha crc32c poschar) crc32=cpu
expect amd64 v3 $(each base $sha crc32) crc32c=cpu poschar=cpu
expect amd64 max $(each cpu $sha crc32 crc32c poschar)

# arm64: SHA1/SHA256 are the crypto extension, both CRCs crc32 (v8.1);
# the AVX2 search is never arm64's, which has its NEON body in Base.
expect arm64 base $(each base $sha crc32 crc32c poschar)
expect arm64 crypto $(each cpu $sha) $(each base crc32 crc32c poschar)
expect arm64 v8.1 $(each base $sha poschar) crc32=cpu crc32c=cpu
expect arm64 max $(each cpu $sha crc32 crc32c) poschar=base

rm -rf "$work_dir"
echo 'ok cpufeat (every feature of a kernel body, amd64 and arm64)'
