#!/usr/bin/env python3
"""gen_mapiter.py: the expected output of testdata/mapiter.paslang, worked out
from the formulas of the keys and values, not from running the program (P257).
Usage: gen_mapiter.py > testdata/mapiter.out"""


def key(i):
    return i * 7919 + 13


def whole(tag, n, step, dele):
    idx = [i for i in range(n)]
    if dele:
        idx = [i for i in idx if not (((i * 2654435761) >> 7) % step < 2)]
    cnt = len(idx)
    sk = sum(key(i) for i in idx)
    sv = sum(i ^ 5 for i in idx)
    return '%s n=%d len=%d count=%d sumk=%d sumv=%d dups=0 bad=0' % (tag, n, cnt, cnt, sk, sv)


SIZES = [0, 1, 2, 3, 7, 8, 9, 15, 16, 17, 63, 64, 65, 100, 127, 128, 129, 200, 255, 256, 257, 500, 511, 512,
         513, 1000, 1023, 1024, 1025, 2000, 2047, 2048, 2049, 4096, 5000, 9999, 20000, 100000]

out = []
for n in SIZES:
    out.append(whole('plain', n, 0, False))
for n in SIZES:
    out.append(whole('del', n, 5, True))
for n in SIZES:
    out.append(whole('del2', n, 3, True))
for n in (0, 1, 2, 9, 100, 1001, 5000):
    v = (n + 1) // 2
    out.append('partners n=%d visited=%d left=%d' % (n, v, v))
for n in (0, 7, 8, 9, 1000, 5000):
    out.append('eaten n=%d visited=%d left=0' % (n, n))
for n in (1, 5, 8, 9, 100, 1000, 3000):
    out.append('grows n=%d original=%d dups=0 bad=0 lenok=1' % (n, n))
for n in (0, 8, 9, 1000, 3000):
    out.append('rewrites n=%d visited=%d bad=0' % (n, n))
out.append('fuzz rounds=300 stale=0 dups=0 wrong=0 missing=0 1')
out.append('nested visited=%d' % (200 * 200))
out.append('nested3 matches=%d' % (200 * 2))
for r in (1, 2, 3):
    out.append('break %d 3' % r)
out.append('whole 1000')
out.append('continue 500')
out.append('nil 0')
out.append('empty 0')
out.append('emptied 0')
out.append('cleared 0')
out.append('byte word 200 %d %d' % (sum(range(200)), sum(i * 300 + 7 for i in range(200))))
out.append('int32 int32 500 %d %d' % (sum(i * 1000 - 250000 for i in range(500)), sum(i * 3 - 700 for i in range(500))))
out.append('int double 300 %d %.1f' % (sum(key(i) for i in range(300)), sum(i * 0.5 for i in range(300))))
out.append('string string 600 0 %d' % sum(len('key%d' % i) for i in range(600)))
out.append('string int 600 0 %d' % sum(range(600)))
out.append('int string 600 0')
out.append('rec8 300 %d' % sum(key(i) + i * 3 for i in range(300)))
out.append('rec16 300 %d %d' % (sum(i * 5 for i in range(300)), sum(i * 7 for i in range(300))))
out.append('rec24 300 %d %d %d' % (sum(i * 11 for i in range(300)), sum(i * 13 for i in range(300)),
                                   sum(i * 17 for i in range(300))))
out.append('bytes3 300 %d %d %d' % (sum(i % 256 for i in range(300)), sum((i * 2) % 256 for i in range(300)),
                                    sum((i * 3) % 256 for i in range(300))))
print('\n'.join(out))
