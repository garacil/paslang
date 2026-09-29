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

package main

import (
	"encoding/binary"
	"fmt"
)

type Node struct {
	Val  int64
	Next *Node
}

func main() {
	n := 32 * 1024 * 1024
	buf := make([]byte, n)
	var sum int64
	for r := 1; r <= 4; r++ {
		for i := 0; i < n; i++ {
			buf[i] = byte(i + r)
		}
		for i := 0; i < n; i += 4 {
			sum += int64(binary.LittleEndian.Uint32(buf[i:]))
		}
	}
	var head *Node
	for i := 1; i <= 1000000; i++ {
		head = &Node{Val: int64(i), Next: head}
	}
	for r := 1; r <= 20; r++ {
		for nd := head; nd != nil; nd = nd.Next {
			sum += nd.Val
		}
	}
	fmt.Println(sum)
}
