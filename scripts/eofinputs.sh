#!/bin/sh
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file
# COPYING. It comes with ABSOLUTELY NO WARRANTY.
#
# eofinputs.sh DIR QEMU SUFFIX (P665): DIR/eofcopySUFFIX gives back eight
# inputs byte for byte (empty lines, a last line without a line feed, an
# empty input, a megabyte of lines with and without its last line feed)
# from a file, a pipe and a nonblocking pipe, and with the spellings
# Eof(Input) and Eof(); DIR/eofparkSUFFIX waits in Eof on a pipe whose
# writer is late while another routine runs. QEMU is "" for the host's
# own programs. Run from the tree; stops at the first difference.
set -e
D=$1
Q=$2
X=$3
printf 'one\n\nthree\n\n\n' > $D/in1
printf 'one\n\nlast' > $D/in2
: > $D/in3
printf '\n' > $D/in4
printf 'no line feed at all' > $D/in5
printf '\n\n\n' > $D/in6
awk 'BEGIN { for (i = 1; i <= 120000; i++) { if (i % 7 == 0) print ""; else print "line " i " of a megabyte" } }' > $D/in7
head -c -1 $D/in7 > $D/in8
: > $D/counts$X
for f in in1 in2 in3 in4 in5 in6 in7 in8; do
  timeout 120 $Q $D/eofcopy$X < $D/$f > $D/$f.file$X
  cmp $D/$f $D/$f.file$X
  cat $D/$f | timeout 120 $Q $D/eofcopy$X > $D/$f.pipe$X
  cmp $D/$f $D/$f.pipe$X
  (head -c 5000 $D/$f; sleep 0.05; tail -c +5001 $D/$f) | timeout 120 python3 scripts/nonblocking.py $Q $D/eofcopy$X > $D/$f.nb$X
  cmp $D/$f $D/$f.nb$X
  timeout 120 $Q $D/eofcopy$X spell < $D/$f > $D/$f.spell$X 2>> $D/counts$X
  cmp $D/$f $D/$f.spell$X
done
printf '%s lines, then the end: True, True, False\n' 5 3 0 1 1 3 120000 120000 | diff -u - $D/counts$X
printf 'the end before the line: False\nthe other routine ran while Eof waited: True\nthe line: the line, fed: True\nthen the end: True\n' > $D/eofpark.want
(sleep 0.3; printf 'the line\n') | timeout 60 $Q $D/eofpark$X > $D/eofpark.got$X
diff -u $D/eofpark.want $D/eofpark.got$X
(sleep 0.3; printf 'the line\n') | timeout 60 python3 scripts/nonblocking.py $Q $D/eofpark$X > $D/eofpark.got$X
diff -u $D/eofpark.want $D/eofpark.got$X
