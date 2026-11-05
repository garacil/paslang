#!/usr/bin/env python3
"""gen_maprmw.py: the expected output of testdata/maprmw.paslang, worked out statement by statement on
Python dictionaries, not from running the program (P555).
Usage: gen_maprmw.py > testdata/maprmw.out"""

out = []

# Basic
m = {}
k, n = 5, 7
m[k] = m.get(k, 0) + n
out.append('absent add %d %d' % (m[k], len(m)))
m[6] = m.get(6, 0) - 7
out.append('absent sub %d %d' % (m[6], len(m)))
m[k] += 1
m[k] += 1
m[k] += 10
m[k] -= 1
m[k] -= 3
out.append('present %d' % m[k])
m[k] = n + m[k]
out.append('swapped %d' % m[k])
m[k] = m[k] - n
out.append('difference %d' % m[k])
m[k] = n - m[k]
out.append('reversed %d' % m[k])
m[k] = m[k] + m[k]
out.append('doubled %d' % m[k])
m[k] = m[k] + m[6]
out.append('other entry %d' % m[k])
m[k] = m[k] - (n * 3 - 4)
out.append('expression %d' % m[k])
m[9] = m.get(9, 0) + m.get(9, 0)
out.append('absent doubled %d %d' % (m[9], len(m)))
m[77] = m.get(77, 0) + 4
m[77] += 1
m[77] -= 4
m[77] = 4 + m[77]
m[77] = m[77] - 3
out.append('routine %d %d' % (m[77], len(m)))
m[21] = 100
m[20] = m[21] + 3
m[21] = m.get(22, 0) - 2
out.append('other keys %d %d %d %d' % (m[20], m[21], m.get(22, 0), len(m)))
m2 = {}
m2[k] = m[k] + 1
m2[k] = m2[k] + m[k]
out.append('two maps %d %d %d' % (m2[k], m[k], len(m2)))

# Keys
m = {}
a = [i * 11 for i in range(5)]
for i in range(1, 21):
    j = i % 5
    m[a[j]] = m.get(a[j], 0) + i
    m[i * 3 + 1] = m.get(i * 3 + 1, 0) + 2
    m[j + 100] = m.get(j + 100, 0) - i
kk = sum(m.get(a[i], 0) * (i + 1) for i in range(5))
out.append('keys %d %d %d %d %d %d' % (kk, len(m), m.get(0, 0), m.get(44, 0), m.get(102, 0), m.get(61, 0)))
rec = {3: 8}
p = {3: -4 + 9}
recs = [dict((j, i * j) for j in range(1, 6)) for i in range(3)]
out.append('fields %d %d %d %d %d' % (rec[3], p[3], recs[2][5], recs[1][4], recs[0].get(3, 0)))

# Strings
words = ['the', 'quick', 'brown', 'fox', 'jumps', 'over', 'lazy', 'dog']
s = {}
counts = [0] * 8
for n in range(1, 5001):
    i = (n * 7 + n // 3) % 8
    s[words[i]] = s.get(words[i], 0) + 1
    counts[i] += 1
s['literal'] = s.get('literal', 0) + 4
s['literal'] += 5
s['other'] = s.get('other', 0) - 1
cnt = sum(1 for i in range(8) if s[words[i]] == counts[i])
out.append('strings %d %d %d %d %d' % (cnt, sum(s.values()), s['literal'], s['other'], len(s)))
s['y'] = 10
s['x'] = s['y'] + 5
s['y'] = s['x'] - 1
out.append('string keys %d %d %d' % (s['x'], s['y'], len(s)))
s['q'] = 4
s[''] = 10
s['q'] = s[''] + 1
out.append('literal and variable %d %d' % (s['q'], s['']))

# Calling: the key is worked out twice, E is read after the entry, the entry is read before E is called
out.append('call in the key 3 2')
out.append('call in E 5 3')
out.append('E writes the entry 10 201')
out.append('E first, the entry later 1005')

# Wrap
out.append('wrap up %d' % (-2 ** 63))
out.append('wrap down %d' % (2 ** 63 - 1))
u = (0 - 1) % 2 ** 64
out.append('unsigned %d %d' % (u >> 63, u & 255))
u = (u + 2) % 2 ** 64
out.append('unsigned back %d %d' % (u >> 63, u & 255))

# Others
def wrap(v, bits, signed):
    v %= 1 << bits
    if signed and v >= 1 << (bits - 1):
        v -= 1 << bits
    return v


b7 = wrap(1000, 8, False)
w7 = wrap(100 * 1000, 16, False)
w8 = wrap(-1000, 16, False)
i37 = wrap(10 * 1000000000, 32, True)
i38 = wrap(-10 * 1000000000, 32, True)
out.append('narrow %d %d %d %d %d %d %d %d %d %d' % (b7, w7, w8, i37, i38, -50, 18, 100, 100, 4))
out.append('byte 100 100 100')
out.append('long %d %d %d' % ((10 ** 11,) * 3))
dv = [0.0, 0.0, 0.0]
for kk2 in range(1, 301):
    dv[kk2 % 3] += 0.5
    dv[kk2 % 3] += kk2
out.append('double %.1f %.1f %.1f' % tuple(dv))

# Growth
total = sum(2 * i for i in range(1, 200001) if i % 3 != 0)
out.append('growth 200000 %d 0' % total)
out.append('fuzz rounds=200 bad=0')
print('\n'.join(out))
