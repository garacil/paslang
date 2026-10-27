#!/bin/sh
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
#
# regen.sh: writes testdata/x509 again with Go's crypto/x509 as the oracle
# of P430 (run from the top of the tree, Go 1.27 at /usr/lib/go):
#   gen      the generated PKIs, at fixed times (fresh keys, the same verdicts)
#   pemgen   PEM's cases (the tree keeps the first 300 and every tenth after)
#   realgen  the real chains of testdata/x509/*.pem at fixed times; the
#            system roots it names are then written as the roots of
#            testdata/x509/realroots.pem (root lines), so the file holds
#            on any machine
#   overlay  verify_test.go's, name_constraints_test.go's and PKITS'
#            tables, dumped by a test laid over crypto/x509
#   rootcheck  the system roots Go loads, which make check compares with
#            pasx509's when Go is there
set -e
S=$(cd $(dirname $0) && pwd)
T=$PWD/testdata/x509
cd $S
go build -o /tmp/x509-gen ./gen
go build -o /tmp/x509-pemgen ./pemgen
go build -o /tmp/x509-realgen ./realgen
/tmp/x509-gen > $T/cases.txt
/tmp/x509-pemgen | python3 -c 'import sys
c=sys.stdin.read().split("end\n")
print("".join(x+"end\n" for i,x in enumerate(c[:-1]) if i<300 or i%10==0),end="")' > $T/pem.txt
(cd $T/.. && /tmp/x509-realgen) > /tmp/x509-real.txt
printf '{"Replace": {"/usr/lib/go/src/crypto/x509/zz_dump_test.go": "%s/overlay/dump_test.go"}}\n' $S > /tmp/x509-overlay.json
(export DUMP_DIR=$T; unset GOFLAGS; cd /usr/lib/go/src/crypto/x509 && go test -overlay /tmp/x509-overlay.json -run TestDump -count=1 .)
echo "now replace the sysroots lines of /tmp/x509-real.txt by root lines of testdata/x509/realroots.pem into $T/real.txt"
