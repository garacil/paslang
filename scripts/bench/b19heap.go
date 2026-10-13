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

// P223: a binary min-heap, the twin of b19heap.paslang (its comment
// says what each section does): container/heap, Go's heap.
package main

import (
	"container/heap"
	"fmt"
	"os"
	"strconv"
)

var x int64 = 12345

func next() uint64 {
	x = x*6364136223846793005 + 1442695040888963407
	return uint64(x)
}

type intHeap []int64

func (h intHeap) Len() int           { return len(h) }
func (h intHeap) Less(i, j int) bool { return h[i] < h[j] }
func (h intHeap) Swap(i, j int)      { h[i], h[j] = h[j], h[i] }
func (h *intHeap) Push(v any)        { *h = append(*h, v.(int64)) }
func (h *intHeap) Pop() any {
	old := *h
	n := len(old)
	v := old[n-1]
	*h = old[:n-1]
	return v
}

type strHeap []string

func (h strHeap) Len() int           { return len(h) }
func (h strHeap) Less(i, j int) bool { return h[i] < h[j] }
func (h strHeap) Swap(i, j int)      { h[i], h[j] = h[j], h[i] }
func (h *strHeap) Push(v any)        { *h = append(*h, v.(string)) }
func (h *strHeap) Pop() any {
	old := *h
	n := len(old)
	v := old[n-1]
	*h = old[:n-1]
	return v
}

func ints() {
	h := &intHeap{}
	for i := 1; i <= 2000000; i++ {
		heap.Push(h, int64(next()>>11))
	}
	t, v := int64(0), int64(0)
	for i := 1; i <= 2000000; i++ {
		v = heap.Pop(h).(int64)
		t += (v & 1023) * int64(i&7)
	}
	fmt.Println(t, v)
}

func strs() {
	h := &strHeap{}
	for i := 1; i <= 500000; i++ {
		heap.Push(h, "k"+strconv.FormatInt(int64(next()>>40), 10))
	}
	t, v := 0, ""
	for i := 1; i <= 500000; i++ {
		v = heap.Pop(h).(string)
		t += len(v) * (i & 7)
	}
	fmt.Println(t, v)
}

func main() {
	arg := ""
	if len(os.Args) > 1 {
		arg = os.Args[1]
	}
	switch arg {
	case "ints":
		ints()
	case "strings":
		strs()
	default:
		fmt.Println("b19heap: ints or strings")
		os.Exit(2)
	}
}
