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

import "fmt"

func main() {
	n := 64 * 1024 * 1024
	data := make([]byte, n)
	var x int64 = 12345
	for i := 0; i < n; i++ {
		x = x*1103515245 + 12345
		data[i] = byte(x >> 16)
	}
	var tab [256]byte
	for i := 0; i < 256; i++ {
		tab[i] = byte(i*7 + 3)
	}
	var hist [256]int64
	for pass := 1; pass <= 4; pass++ {
		for i := 0; i < n; i++ {
			data[i] = tab[data[i]]
		}
		for i := 0; i < n; i++ {
			hist[data[i]]++
		}
	}
	var sum int64
	for i := 0; i < 256; i++ {
		sum += hist[i] * int64(i)
	}
	fmt.Println(sum)
}
