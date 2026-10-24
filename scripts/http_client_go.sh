#!/bin/sh
# http_client_go.sh PROGRAM: the checks of testdata/httpcli against the
# program's own server and against Go's net/http (scripts/http_gosrv.go),
# which must print the same. PROGRAM is testdata/httpcli built; run from
# the source root. Exit 1 on a difference.
set -e
P=$1
D=$(mktemp -d /home/german/.cache/paslang-vartmp/httpgoXXXXXX)
go run scripts/http_gosrv.go > $D/port 2>/dev/null &
G=$!
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  [ -s $D/port ] && break
  sleep 1
done
PORT=$(head -1 $D/port)
$P gosrv $PORT > $D/go.out
$P > $D/own.full
awk '/^== the real server/{f=1} /^== the scripted server: what is sent/{f=0} f' $D/own.full > $D/own.out
pkill -P $G 2>/dev/null || true
kill $G 2>/dev/null || true
if diff -u $D/own.out $D/go.out; then echo "client against Go's server: same ($(wc -l < $D/go.out) lines)"; rc=0; else rc=1; fi
rm -rf $D
exit $rc
