#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacil@tucall.com>
#
# paslang is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# paslang is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with paslang.  If not, see <https://www.gnu.org/licenses/>.

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
