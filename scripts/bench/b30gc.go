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

// P223: the collector under allocation, the twin of b30gc.paslang (its
// comment says what it does).
package main

import (
	"fmt"
	"os"
)

type node struct{ left, right *node }

func make1(d int) *node {
	n := &node{}
	if d > 0 {
		n.left = make1(d - 1)
		n.right = make1(d - 1)
	}
	return n
}

func check(n *node) int {
	if n.left == nil {
		return 1
	}
	return 1 + check(n.left) + check(n.right)
}

const (
	maxDepth = 18
	minDepth = 4
)

func main() {
	if len(os.Args) < 2 || os.Args[1] != "trees" {
		fmt.Println("b30gc: trees")
		os.Exit(2)
	}
	fmt.Println("stretch tree of depth", maxDepth+1, "check:", check(make1(maxDepth+1)))
	long := make1(maxDepth)
	for d := minDepth; d <= maxDepth; d += 2 {
		iters := 1 << (maxDepth - d + minDepth)
		chk := 0
		for i := 1; i <= iters; i++ {
			chk += check(make1(d))
		}
		fmt.Println(iters, "trees of depth", d, "check:", chk)
	}
	fmt.Println("long lived tree of depth", maxDepth, "check:", check(long))
}
