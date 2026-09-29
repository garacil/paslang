#!/usr/bin/env python3
"""qemu-user 11.1 returns EINVAL for unknown madvise, including
MADV_GUARD_INSTALL (102). Patch a copy so that path returns 0.
Generated paslang still issues madvise 102; this is the qemu harness."""
import sys
from pathlib import Path

def main() -> None:
    p = Path(sys.argv[1])
    b = bytearray(p.read_bytes())
    off = 0x327F5D
    want = bytes.fromhex('41b8eaffffff')  # mov r8d, -22
    if bytes(b[off:off + 6]) == bytes.fromhex('41b800000000'):
        return
    if bytes(b[off:off + 6]) != want:
        raise SystemExit('unexpected qemu-aarch64-static layout at target_madvise')
    b[off:off + 6] = bytes.fromhex('41b800000000')  # mov r8d, 0
    p.write_bytes(b)

if __name__ == '__main__':
    main()
