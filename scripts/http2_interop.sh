#!/bin/sh
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
#
# http2_interop.sh SERVERBIN CLIENT [RUNNER [DOC]]: pashttp2's client
# (testdata/http2go, under RUNNER, qemu for arm64) against Go's net/http
# server (SERVERBIN built from scripts/h2oracle), one server a case on
# 127.0.0.1 with the port it chose, over TLS and in the clear; prints
# what each case said, which make check compares with
# testdata/http2go.out (P617). With DOC (testdata/http2doc, the manual's
# example) a last line has it make one request more.
#
# http2_interop.sh nginx CLIENT [RUNNER]: the same client against nginx,
# another server's HTTP/2, over TLS and in the clear, with a
# configuration and files written here and the certificate of
# testdata/tls; make check compares it with testdata/http2nginx.out.
if [ "$1" = nginx ]; then
  C=$2; R=$3
  T=$(mktemp -d)
  K=$(pwd)/testdata/tls
  mkdir -p $T/www $T/tmp
  python3 -I -c 'import sys
def pattern(n): return bytes((i * 7 + (i >> 8)) & 255 for i in range(n))
open(sys.argv[1] + "/big.bin", "wb").write(pattern(5000000))
open(sys.argv[1] + "/medium.bin", "wb").write(pattern(70000))
open(sys.argv[1] + "/empty.txt", "wb").write(b"")
import socket
for name in ("tls", "h2c"):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); open(sys.argv[1] + "/../port-" + name, "w").write(str(s.getsockname()[1])); s.close()' $T/www
  pt=$(cat $T/port-tls); pc=$(cat $T/port-h2c)
  cat > $T/nginx.conf <<CONF
daemon off;
master_process off;
pid $T/nginx.pid;
error_log $T/error.log warn;
events { worker_connections 1024; }
http {
  access_log off;
  default_type text/plain;
  client_body_temp_path $T/tmp/body;
  proxy_temp_path $T/tmp/proxy;
  fastcgi_temp_path $T/tmp/fastcgi;
  uwsgi_temp_path $T/tmp/uwsgi;
  scgi_temp_path $T/tmp/scgi;
  client_max_body_size 20m;
  http2 on;
  http2_max_concurrent_streams 128;
  keepalive_requests 1000;
  server_tokens off;
  server {
    listen 127.0.0.1:$pt ssl;
    ssl_certificate $K/ec.pem;
    ssl_certificate_key $K/ec.key;
    root $T/www;
    location = /hello { return 200 "hello from nginx\n"; }
    location = /post { return 204; }
  }
  server {
    listen 127.0.0.1:$pc;
    root $T/www;
    location = /hello { return 200 "hello from nginx\n"; }
    location = /post { return 204; }
  }
}
CONF
  nginx -p $T -e $T/error.log -c $T/nginx.conf > $T/out 2>&1 & pid=$!
  i=0; while [ ! -s $T/nginx.pid ] && [ $i -lt 100 ]; do sleep 0.1; i=$((i+1)); done
  echo "== nginx tls"
  timeout 600 $R $C tls $pt nginx $K/ca.pem 2>&1
  echo "exit $?"
  echo "== nginx h2c"
  timeout 600 $R $C h2c $pc nginx $K/ca.pem 2>&1
  echo "exit $?"
  kill $pid; wait $pid 2>/dev/null
  rm -rf $T
  exit 0
fi
SRV=$1; C=$2; R=$3; DOC=$4
T=$(mktemp -d)
one() {
  smode=$1; kind=$2; name=$3; shift 3
  $SRV -mode $smode -dir $T "$@" > $T/port 2> $T/err & pid=$!
  i=0; while [ ! -s $T/port ] && [ $i -lt 100 ]; do sleep 0.1; i=$((i+1)); done
  p=$(head -1 $T/port)
  echo "== $smode $kind $name"
  timeout 600 $R $C $kind $p $name $T/ca.pem 2>&1
  echo "exit $?"
  kill $pid; wait $pid 2>/dev/null
  : > $T/port
}
one tls tls basic
one h2c h2c basic
one tls tls many
one h2c h2c many
one tls tls limit -streams 4
one h2c h2c limit -streams 4
one tls tls goaway
one h2c h2c goaway
one h1 tls noh2
one h1 h2c noh2 -dir ''
one tls tls race
one h2c h2c race
if [ -n "$DOC" ]; then
  $SRV -mode tls -dir $T > $T/port 2> $T/err & pid=$!
  i=0; while [ ! -s $T/port ] && [ $i -lt 100 ]; do sleep 0.1; i=$((i+1)); done
  p=$(head -1 $T/port)
  out=$(timeout 120 $R $DOC 127.0.0.1 $p $T/ca.pem 2>&1 | tr '\n' ' ')
  kill $pid; wait $pid 2>/dev/null
  echo "doc: $out"
fi
rm -rf $T
