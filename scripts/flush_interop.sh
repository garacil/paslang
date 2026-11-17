#!/bin/sh
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
#
# flush_interop.sh PROGRAM ORACLE [RUNNER] (P661): PROGRAM, testdata/httpflush
# under RUNNER (qemu for arm64), serves an event stream on 127.0.0.1 with
# the port it chose; ORACLE, Go's net/http client built from
# scripts/flushoracle, and then curl -N read it, and each says, event by
# event, whether it came at least 200 ms after the one before (the
# server flushes them 300 ms apart). make check compares the lines with
# testdata/httpflushgo.out. Without curl only Go's lines are written.
P=$1
G=$2
R=$3
T=$(mktemp -d)
$R $P serve > $T/port &
pid=$!
n=0
until grep -q '^port ' $T/port 2>/dev/null; do
  n=$((n + 1))
  if [ $n -gt 600 ]; then
    echo "the server did not start"
    kill $pid
    rm -rf $T
    exit 1
  fi
  sleep 0.05
done
port=$(sed -n 's/^port //p' $T/port)
$G http://127.0.0.1:$port/tick
if command -v curl > /dev/null 2>&1; then
  curl -N -s http://127.0.0.1:$port/tick | python3 -I -c '
import sys, time
n = 0
last = None
for line in sys.stdin:
    now = time.monotonic()
    if line.startswith("data: "):
        n += 1
        if last is None:
            print("curl: event %d: %s" % (n, line[6:]), end="")
        else:
            print("curl: event %d, 200 ms or more after the one before %s: %s" % (n, "true" if now - last >= 0.2 else "false", line[6:]), end="")
        last = now
print("curl: the stream ended after %d events" % n)
'
fi
kill -TERM $pid
wait $pid
rm -rf $T
