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

// P223: more of the map, the twin of b31map.paslang (its comment says
// what each section does).
package main

import (
	"fmt"
	"os"
)

func main() {
	m := make(map[int]int)
	for i := 1; i <= 1000000; i++ {
		m[i*7919] = i
	}
	t := 0
	arg := ""
	if len(os.Args) > 1 {
		arg = os.Args[1]
	}
	switch arg {
	case "iter":
		for r := 1; r <= 20; r++ {
			for k, v := range m {
				t += k ^ v
			}
		}
	case "delete":
		for i := 1; i <= 1000000; i++ {
			delete(m, i*7919)
		}
		t = 1
	case "update":
		for r := 1; r <= 10; r++ {
			for i := 1; i <= 1000000; i++ {
				m[i*7919]++
			}
		}
		t = m[7919] + m[7919*1000000]
	default:
		fmt.Println("b31map: iter, delete or update")
		os.Exit(2)
	}
	fmt.Println(t, len(m))
}
