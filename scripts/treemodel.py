#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
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

"""The exact model of testdata/tree2.paslang (P110): an ordered map with
the words of tree[K] of V and a binary min-heap, run over the same
steps, printing what the program must print. Booleans print as 1 and 0,
as WriteLn prints them."""
import bisect
import heapq

MOD = 1000000007


class Tree:
    def __init__(self):
        self.keys = []
        self.vals = {}

    def __len__(self):
        return len(self.keys)

    def put(self, k, v):
        if k not in self.vals:
            bisect.insort(self.keys, k)
        self.vals[k] = v

    def get(self, k, zero):
        return self.vals.get(k, zero)

    def has(self, k):
        return k in self.vals

    def delete(self, k):
        if k not in self.vals:
            return False
        del self.vals[k]
        self.keys.pop(bisect.bisect_left(self.keys, k))
        return True

    def clear(self):
        self.keys = []
        self.vals = {}

    def low(self):
        return self.keys[0]

    def high(self):
        return self.keys[-1]

    def rank(self, k):
        return bisect.bisect_left(self.keys, k)

    def keyat(self, i):
        return self.keys[i]

    def succ(self, k):
        return self.keys[bisect.bisect_right(self.keys, k)]

    def pred(self, k):
        return self.keys[bisect.bisect_left(self.keys, k) - 1]

    def floor(self, k):
        return self.keys[bisect.bisect_right(self.keys, k) - 1]

    def ceil(self, k):
        return self.keys[bisect.bisect_left(self.keys, k)]

    def walk(self, lo=None, hi=None, down=False):
        ks = self.keys
        if lo is not None:
            a = bisect.bisect_left(ks, lo)
            b = bisect.bisect_right(ks, hi)
            ks = ks[a:b] if a <= b else []
        if down:
            ks = list(reversed(ks))
        return [(k, self.vals[k]) for k in ks]

    def poplow(self):
        k = self.keys[0]
        v = self.vals[k]
        self.delete(k)
        return k, v

    def pophigh(self):
        k = self.keys[-1]
        v = self.vals[k]
        self.delete(k)
        return k, v

    def split(self, k):
        u = Tree()
        i = bisect.bisect_left(self.keys, k)
        for key in self.keys[i:]:
            u.put(key, self.vals[key])
        for key in list(self.keys[i:]):
            self.delete(key)
        return u

    def join(self, other):
        for k, v in other.walk():
            self.put(k, v)
        other.clear()


def b(x):
    return '1' if x else '0'


def main():
    out = []
    w = out.append
    st = {'x': 0}

    def nxt():
        st['x'] = (st['x'] * 1103515245 + 12345) % 2147483648
        return st['x']

    t = Tree()
    st['x'] = 12345
    for i in range(1, 5001):
        t.put(nxt() % 100000, i)
    w(f"{len(t)} {t.low()} {t.high()}")
    acc = 0
    n = 0
    for k, v in t.walk():
        acc = (acc * 31 + k + v) % MOD
        n += 1
    w(f"{n} {acc}")
    acc = 0
    for k, v in t.walk(down=True):
        acc = (acc * 31 + k) % MOD
    w(f"{acc}")
    n = 0
    acc = 0
    for k, v in t.walk(20000, 30000):
        n += 1
        acc = (acc + k) % MOD
    w(f"{n} {acc}")
    w(f"{len(t.walk(30000, 20000))}")
    n = 0
    acc = 0
    for k, v in t.walk(20000, 30000, down=True):
        n += 1
        acc = (acc * 7 + k) % MOD
    w(f"{n} {acc}")
    w(f"{len(t.walk(t.high(), 1000000))}")
    k = t.keyat(100)
    w(f"{k} {t.rank(k)} {t.succ(k)} {t.pred(k)} {t.floor(k)} {t.ceil(k)}")
    w(f"{t.floor(50000)} {t.ceil(50000)} {t.succ(50000)} {t.pred(50000)}")
    w(f"{t.rank(0)} {t.rank(100000)} {t.rank(50000)} {t.keyat(0)} {t.keyat(len(t) - 1)}")
    st['x'] = 12345
    n = 0
    for i in range(1, 5001):
        k = nxt() % 100000
        if i % 3 == 0:
            if t.delete(k):
                n += 1
    w(f"{n} {len(t)}")
    acc = 0
    for k, v in t.walk():
        acc = (acc * 31 + k + v) % MOD
    w(f"{acc}")
    if t.has(12):
        w(f"has 12 {t.get(12, 0)}")
    else:
        w("no 12")
    k = t.keyat(7)
    if t.has(k):
        w(f"has {k} {t.get(k, 0)}")
    else:
        w(f"no {k}")
    w(f"{t.get(k, 0)} {t.get(-5, 0)} {b(t.has(-5))} {b(t.has(k))}")
    n = 0
    acc = 0
    while len(t):
        k, v = t.poplow()
        n += 1
        acc = (acc * 31 + k + v) % MOD
        if n == 100:
            break
    w(f"{n} {acc} {len(t)} {t.low()}")
    n = 0
    acc = 0
    while len(t):
        k, v = t.pophigh()
        n += 1
        acc = (acc * 31 + k) % MOD
        if n == 100:
            break
    w(f"{n} {acc} {len(t)} {t.high()}")
    u = t.split(50000)
    w(f"{len(t)} {len(u)} {t.high()} {u.low()}")
    t.join(u)
    w(f"{len(t)} {len(u)}")
    u = Tree()
    u.put(t.keyat(0), 999)
    u.put(123456, 7)
    t.join(u)
    w(f"{t.get(t.keyat(0), 0)} {t.get(123456, 0)} {len(t)} {len(u)}")
    t.clear()
    w(f"{len(t)} {b(t.has(5))} {t.get(5, 0)}")
    # a tree of strings
    s = Tree()
    s.put('pear', True)
    s.put('apple', True)
    s.put('fig', True)
    s.put('kiwi', True)
    s.delete('kiwi')
    s.delete('none')
    s.put('apple', True)
    w(f"{len(s)} {b(s.has('apple'))} {b(s.has('kiwi'))} {b(s.has('fig'))}")
    w(' '.join(k for k, _ in s.walk()) + ' ')
    w(' '.join(k for k, _ in s.walk(down=True)) + ' ')
    w(f"{s.low()} {s.high()} {s.succ('b')} {s.pred('g')} {s.floor('fig')} {s.ceil('g')}")
    w(' '.join(k for k, _ in s.walk('b', 'm')) + ' ')
    # string keys and values
    m = Tree()
    for i in range(1, 301):
        m.put('k' + str((i * 37) % 300), 'v' + str(i))
    w(f"{len(m)} {m.get('k0', '')} {m.get('k299', '')} {b(m.get('none', '') == '')} {m.low()} {m.high()}")
    n = 0
    acc = 0
    for ks, vs in m.walk('k10', 'k2'):
        n += 1
        acc = (acc * 31 + len(ks) + len(vs)) % MOD
    w(f"{n} {acc}")
    w(f"{m.get('k1', '')} {m.keyat(1)} {m.rank('k2')}")
    n = 0
    first = []
    while len(m):
        ks, vs = m.poplow()
        n += 1
        if n <= 3:
            first.append(f"{ks}={vs}")
    w(' '.join(first) + f" {n} {len(m)}")
    # the heaps
    h = []
    st['x'] = 777
    for i in range(1, 2001):
        heapq.heappush(h, nxt() % 1000)
    w(f"{len(h)} {h[0]}")
    n = 0
    acc = 0
    while h:
        k = heapq.heappop(h)
        n += 1
        acc = (acc * 31 + k) % MOD
    w(f"{n} {acc} {len(h)}")
    for v in (5, 3, 9):
        heapq.heappush(h, v)
    a1 = heapq.heappop(h)
    a2 = heapq.heappop(h)
    w(f"{a1} {a2} {h[0]} {len(h)}")
    hs = []
    for i in range(1, 61):
        heapq.heappush(hs, 's' + str((i * 17) % 60))
    w(f"{len(hs)} {hs[0]}")
    n = 0
    first = []
    while hs:
        ks = heapq.heappop(hs)
        n += 1
        if n <= 4:
            first.append(ks)
    w(' '.join(first) + f" {n}")
    hr = []
    for i in range(1, 101):
        heapq.heappush(hr, (nxt() % 10000) / 100.0)
    acc = 0
    n = 0
    while hr:
        r = heapq.heappop(hr)
        n += 1
        acc = (acc * 31 + round(r * 100)) % MOD
    w(f"{n} {acc}")
    print('\n'.join(out))


if __name__ == '__main__':
    main()
