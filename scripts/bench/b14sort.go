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

// P223: sorting, the twin of b14sort.paslang (its comment says what
// each section does).
package main

import (
	"fmt"
	"os"
	"slices"
	"strconv"
)

var x int64 = 12345

func next() uint64 {
	x = x*6364136223846793005 + 1442695040888963407
	return uint64(x)
}

func ints() {
	n := 2000000
	a := make([]int64, n)
	for i := range a {
		a[i] = int64(next() >> 11)
	}
	slices.Sort(a)
	fmt.Println(a[0], a[n/2], a[n-1])
}

func strs() {
	n := 500000
	a := make([]string, n)
	for i := range a {
		a[i] = "k" + strconv.FormatInt(int64(next()>>40), 10)
	}
	slices.Sort(a)
	fmt.Println(a[0], a[n/2], a[n-1])
}

func reals() {
	n := 2000000
	a := make([]float64, n)
	for i := range a {
		a[i] = float64(next()>>11) / 9007199254740992.0
	}
	slices.Sort(a)
	fmt.Println(int64(a[0]*1e15), int64(a[n/2]*1e15), int64(a[n-1]*1e15))
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
	case "reals":
		reals()
	default:
		fmt.Println("b14sort: ints, strings or reals")
		os.Exit(2)
	}
}
