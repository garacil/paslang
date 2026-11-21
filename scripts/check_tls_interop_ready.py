#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacil@tucall.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Hold the new OpenSSL peer before it opens its output (P684)."""
from pathlib import Path
import subprocess
import tempfile

source = Path(__file__).with_name("tls_interop.sh").read_text()
start = source.index("ossl_case() {")
end = source.index('\nif [ "$KIND"', start)
case = source[start:end]
launch = next(line for line in case.splitlines() if "openssl s_server " in line)
delay = '''  (sleep 0.25
     printf 'ACCEPT 127.0.0.1:%s\\n' "$port" > "$T/srv"
     exec sleep 2) & pid=$!'''
reset = '  : > "$T/srv"\n'
if case.count(reset) != 1:
    raise SystemExit("TLS readiness reset is missing or ambiguous")
case = case.replace(launch, delay, 1)

driver = '''
port=41001
ossl_case first x
port=41002
ossl_case second x
'''


def run(function, directory):
    sh = '''
T=$1
K=$T
C=client
R=
client() { printf '%s\\n' "$2"; }
''' + function + driver
    return subprocess.run(
        ["sh", "-c", sh, "tls-readiness", str(directory)],
        text=True, capture_output=True, timeout=10, check=True,
    )


with tempfile.TemporaryDirectory(prefix="paslang-tls-ready-") as folder:
    directory = Path(folder)
    good = directory / "fresh"
    stale = directory / "stale"
    good.mkdir()
    stale.mkdir()
    fixed = run(case, good)
    old = run(case.replace(reset, "", 1), stale)
    if fixed.stderr or fixed.stdout != "first: 41001 \nsecond: 41002 \n":
        raise SystemExit("the current peer's port was not read: " + repr(fixed))
    if old.stdout != "first: 41001 \nsecond: 41001 \n":
        raise SystemExit("the stale-readiness control was not reproduced: " + repr(old))

print("TLS readiness checks each freshly started OpenSSL peer")
