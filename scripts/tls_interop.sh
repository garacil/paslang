#!/bin/sh
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
#
# tls_interop.sh go|openssl SERVERBIN CLIENT [RUNNER [DOC]]: pastls' client
# (testdata/tlsinterop, under RUNNER, qemu for arm64) against Go's
# crypto/tls (SERVERBIN built from scripts/tlsoracle) or openssl s_server,
# one server a case on 127.0.0.1 with the port it chose; prints a line a
# case, which make check compares with testdata/tlsinterop-go.out or
# tlsinterop-openssl.out (P431). With DOC (testdata/tlsdoc, the manual's
# example) a last line has it dial one more server of Go's (P473).
KIND=$1; SRV=$2; C=$3; R=$4; DOC=$5
T=$(mktemp -d)
K=testdata/tls
go_case() {
  name=$1; mode=$2; host=${3:-localhost}
  $SRV -case $name -dir $T > $T/port 2> $T/err & pid=$!
  i=0; while [ ! -s $T/port ] && [ $i -lt 100 ]; do sleep 0.1; i=$((i+1)); done
  p=$(head -1 $T/port)
  out=$($R $C 127.0.0.1 $p $mode $T/ca.pem $host 2>&1 | tr '\n' ' ')
  kill $pid; wait $pid 2>/dev/null
  echo "$name $mode $host: $out"
  : > $T/port
}
ossl_case() {
  label=$1; mode=$2; shift 2
  openssl s_server -accept 127.0.0.1:0 -rev -naccept 1 "$@" > $T/srv 2>&1 & pid=$!
  i=0; while ! grep -q '^ACCEPT' $T/srv && [ $i -lt 100 ]; do sleep 0.1; i=$((i+1)); done
  p=$(sed -n 's/^ACCEPT 127.0.0.1://p' $T/srv | head -1)
  out=$($R $C 127.0.0.1 $p $mode $K/ca.pem localhost 2>&1 | tr '\n' ' ')
  kill $pid 2>/dev/null; wait $pid 2>/dev/null
  echo "$label: $out"
}
if [ "$KIND" = go ]; then
  go_case tls13 x
  go_case tls13rsa x
  go_case tls13p384 x
  go_case hrr x
  go_case hrr384 x
  go_case alpn alpn
  go_case certreq x
  go_case tls13 only12
  go_case tls13 big
  go_case tls13 x 127.0.0.1
  go_case tls13 x wrong.host
  go_case tls13 x sub.pastls.test
  go_case tls12-c02b only12
  go_case tls12-c02c only12
  go_case tls12-cca9 only12
  go_case tls12-c02f-rsa only12
  go_case tls12-c030-rsa only12
  go_case tls12-cca8-rsa only12
  go_case tls12-c02b-p384 only12
  go_case tls12-p256 only12
  go_case tls12certreq only12
  go_case tls12alpn alpn
  go_case tls12-c02b big
  go_case tls12-c02b only13
  go_case tls13 conc
  if [ -n "$DOC" ]; then
    $SRV -case alpn -dir $T > $T/port 2> $T/err & pid=$!
    i=0; while [ ! -s $T/port ] && [ $i -lt 100 ]; do sleep 0.1; i=$((i+1)); done
    p=$(head -1 $T/port)
    out=$($R $DOC 127.0.0.1 $p $T/ca.pem 2>&1 | tr '\n' ' ')
    kill $pid; wait $pid 2>/dev/null
    echo "doc: $out"
  fi
else
  E="-cert $K/ec.pem -key $K/ec.key"
  RS="-cert $K/rsa.pem -key $K/rsa.key"
  ossl_case "13 aes128" x $E -ciphersuites TLS_AES_128_GCM_SHA256
  ossl_case "13 aes256" x $E -ciphersuites TLS_AES_256_GCM_SHA384
  ossl_case "13 chacha20" x $E -ciphersuites TLS_CHACHA20_POLY1305_SHA256
  ossl_case "13 rsa-pss" x $RS
  ossl_case "13 P-256 by hrr" x $E -groups P-256
  ossl_case "13 P-384 by hrr" x $E -groups P-384
  ossl_case "13 x25519" x $E -groups X25519
  ossl_case "12 ecdhe-ecdsa-aes128-gcm" x $E -tls1_2 -cipher ECDHE-ECDSA-AES128-GCM-SHA256
  ossl_case "12 ecdhe-ecdsa-aes256-gcm" x $E -tls1_2 -cipher ECDHE-ECDSA-AES256-GCM-SHA384
  ossl_case "12 ecdhe-ecdsa-chacha20" x $E -tls1_2 -cipher ECDHE-ECDSA-CHACHA20-POLY1305
  ossl_case "12 ecdhe-rsa-aes128-gcm" x $RS -tls1_2 -cipher ECDHE-RSA-AES128-GCM-SHA256
  ossl_case "12 ecdhe-rsa-aes256-gcm" x $RS -tls1_2 -cipher ECDHE-RSA-AES256-GCM-SHA384
  ossl_case "12 ecdhe-rsa-chacha20" x $RS -tls1_2 -cipher ECDHE-RSA-CHACHA20-POLY1305
  ossl_case "12 rsa pkcs1 sha256" x $RS -tls1_2 -sigalgs RSA+SHA256
  ossl_case "12 P-384" x $E -tls1_2 -groups P-384
  ossl_case "12 no extended master secret" x $E -tls1_2 -no_ems
  ossl_case "12 aes-cbc only, refused" x $E -tls1_2 -cipher ECDHE-ECDSA-AES128-SHA256
fi
rm -rf $T
