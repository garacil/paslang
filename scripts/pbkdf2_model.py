#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacil@tucall.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Independent byte oracle for P678; hashlib/OpenSSL, no project imports."""
import hashlib


def raw(n, seed):
    return bytes((i * 131 + seed) & 255 for i in range(1, n + 1))


CASES = (
    ('sha1', 0, 0, 1, 1),
    ('sha1', 0, 0, 2, 65),
    ('sha1', 64, 0, 3, 41),
    ('sha1', 65, 52, 2, 65),
    ('sha1', 129, 60, 3, 65),
    ('sha1', 63, 64, 7, 41),
    ('sha1', 64, 65, 2, 33),
    ('sha1', 65, 128, 2, 41),
    ('sha1', 129, 129, 2, 5137),
    ('sha256', 0, 0, 1, 1),
    ('sha256', 0, 0, 2, 65),
    ('sha256', 64, 0, 3, 41),
    ('sha256', 65, 52, 2, 65),
    ('sha256', 129, 60, 3, 65),
    ('sha256', 63, 64, 7, 41),
    ('sha256', 64, 65, 2, 33),
    ('sha256', 65, 128, 2, 41),
    ('sha256', 129, 129, 2, 8193),
    ('sha1', 65537, 65537, 2, 65),
    ('sha256', 65537, 65537, 2, 65),
)


def main():
    for number, (algorithm, plen, slen, count, length) in enumerate(CASES, 1):
        result = hashlib.pbkdf2_hmac(algorithm, raw(plen, 128), raw(slen, 255), count, length)
        if len(result) != length:
            raise RuntimeError('PBKDF2 oracle output length mismatch')
        print(number, result.hex())


if __name__ == '__main__':
    main()
