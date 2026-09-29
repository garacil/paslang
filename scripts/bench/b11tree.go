// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
//
// paslang is free software: you can redistribute it and/or modify it
// under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// paslang is distributed in the hope that it will be useful, but
// WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
// General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with paslang.  If not, see <https://www.gnu.org/licenses/>.

// The same B+ tree as paslang's tree[Integer] of Integer, written in Go:
// nodes of at most 32 keys, values in the leaves, leaves linked in key
// order, a binary search in every node, the split at 16. Go's library
// has no ordered map, so the twin is the same algorithm, and the pair
// measures the two compilers and runtimes on the same work.
package main

import "fmt"

const maxK = 32

type node struct {
	leaf   bool
	n      int
	keys   [maxK]int
	vals   [maxK]int
	kids   [maxK + 1]*node
	next   *node
	parent *node
}

type tree struct {
	root  *node
	count int
}

func (t *tree) findLeaf(k int) *node {
	n := t.root
	for !n.leaf {
		lo, hi := 0, n.n
		for lo < hi {
			mid := (lo + hi) >> 1
			if n.keys[mid] <= k {
				lo = mid + 1
			} else {
				hi = mid
			}
		}
		n = n.kids[lo]
	}
	return n
}

func lowerBound(n *node, k int) int {
	lo, hi := 0, n.n
	for lo < hi {
		mid := (lo + hi) >> 1
		if n.keys[mid] < k {
			lo = mid + 1
		} else {
			hi = mid
		}
	}
	return lo
}

func (t *tree) get(k int) (int, bool) {
	if t.root == nil {
		return 0, false
	}
	l := t.findLeaf(k)
	p := lowerBound(l, k)
	if p < l.n && l.keys[p] == k {
		return l.vals[p], true
	}
	return 0, false
}

func (t *tree) put(k, v int) {
	if t.root == nil {
		t.root = &node{leaf: true}
		t.root.keys[0], t.root.vals[0], t.root.n = k, v, 1
		t.count = 1
		return
	}
	l := t.findLeaf(k)
	p := lowerBound(l, k)
	if p < l.n && l.keys[p] == k {
		l.vals[p] = v
		return
	}
	if l.n >= maxK {
		t.splitLeaf(l)
		l = t.findLeaf(k)
		p = lowerBound(l, k)
	}
	copy(l.keys[p+1:l.n+1], l.keys[p:l.n])
	copy(l.vals[p+1:l.n+1], l.vals[p:l.n])
	l.keys[p], l.vals[p] = k, v
	l.n++
	t.count++
}

func (t *tree) splitLeaf(l *node) {
	r := &node{leaf: true}
	copy(r.keys[:16], l.keys[16:32])
	copy(r.vals[:16], l.vals[16:32])
	l.n, r.n = 16, 16
	r.next = l.next
	l.next = r
	t.insertSep(l.parent, l, r.keys[0], r)
}

func (t *tree) insertSep(parent, left *node, sep int, right *node) {
	if parent == nil {
		nr := &node{}
		nr.keys[0], nr.kids[0], nr.kids[1], nr.n = sep, left, right, 1
		left.parent, right.parent = nr, nr
		t.root = nr
		return
	}
	if parent.n >= maxK {
		t.splitInner(parent)
		parent = left.parent
	}
	idx := 0
	for idx <= parent.n && parent.kids[idx] != left {
		idx++
	}
	copy(parent.keys[idx+1:parent.n+1], parent.keys[idx:parent.n])
	copy(parent.kids[idx+2:parent.n+2], parent.kids[idx+1:parent.n+1])
	parent.keys[idx], parent.kids[idx+1] = sep, right
	right.parent = parent
	parent.n++
}

func (t *tree) splitInner(n *node) {
	r := &node{}
	sep := n.keys[16]
	copy(r.keys[:15], n.keys[17:32])
	copy(r.kids[:16], n.kids[17:33])
	for i := 0; i < 16; i++ {
		r.kids[i].parent = r
	}
	r.n, n.n = 15, 16
	t.insertSep(n.parent, n, sep, r)
}

func main() {
	t := &tree{}
	for i := 1; i <= 1000000; i++ {
		t.put((i*2654435761)&0xFFFFFFFF, i)
	}
	sum := 0
	for i := 1; i <= 1000000; i++ {
		v, _ := t.get((i * 2654435761) & 0xFFFFFFFF)
		sum += v
	}
	inorder, last := 0, -1
	l := t.root
	for !l.leaf {
		l = l.kids[0]
	}
	low := l.keys[0]
	high := 0
	for ; l != nil; l = l.next {
		for i := 0; i < l.n; i++ {
			if l.keys[i] > last {
				inorder++
			}
			last = l.keys[i]
			high = l.keys[i]
		}
	}
	fmt.Println(t.count, sum, inorder, low, high)
}
