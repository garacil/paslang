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

// P223: growing slices, the twin of b26slice.paslang (its comment says
// what each section does).
package main

import (
	"fmt"
	"os"
	"strconv"
)

func main() {
	t := 0
	arg := ""
	if len(os.Args) > 1 {
		arg = os.Args[1]
	}
	switch arg {
	case "ints":
		var a []int
		for i := 1; i <= 20000000; i++ {
			a = append(a, i*3)
		}
		for i := range a {
			t += a[i] & 7
		}
		fmt.Println(len(a), t)
	case "strings":
		var b []string
		for i := 1; i <= 2000000; i++ {
			b = append(b, "k"+strconv.Itoa(i))
		}
		for i := range b {
			t += len(b[i])
		}
		fmt.Println(len(b), t)
	default:
		fmt.Println("b26slice: ints or strings")
		os.Exit(2)
	}
}
