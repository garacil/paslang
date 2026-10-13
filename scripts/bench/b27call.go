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

// P223: calls through a value, the twin of b27call.paslang (its comment
// says what each section does).
package main

import (
	"fmt"
	"os"
)

type shape interface {
	Area(k int) int
}

type square struct{ side int }
type rect struct{ w, h int }

func (s *square) Area(k int) int { return s.side*s.side + k }
func (r *rect) Area(k int) int   { return r.w*r.h - k }

//go:noinline
func twice(k int) int { return k * 2 }

//go:noinline
func thrice(k int) int { return k * 3 }

func adder(n int) func(int) int {
	return func(k int) int { return k + n }
}

func main() {
	t := 0
	arg := ""
	if len(os.Args) > 1 {
		arg = os.Args[1]
	}
	switch arg {
	case "iface":
		var shapes [64]shape
		for i := 0; i < 64; i++ {
			if i%2 == 0 {
				shapes[i] = &square{side: i}
			} else {
				shapes[i] = &rect{w: i, h: 3}
			}
		}
		for i := 1; i <= 100000000; i++ {
			t += shapes[i&63].Area(i & 15)
		}
	case "closure":
		var fns [64]func(int) int
		for i := 0; i < 64; i++ {
			fns[i] = adder(i)
		}
		for i := 1; i <= 100000000; i++ {
			t += fns[i&63](i & 15)
		}
	case "proc":
		var fns [64]func(int) int
		for i := 0; i < 64; i++ {
			if i%2 == 0 {
				fns[i] = twice
			} else {
				fns[i] = thrice
			}
		}
		for i := 1; i <= 100000000; i++ {
			t += fns[i&63](i & 15)
		}
	default:
		fmt.Println("b27call: iface, closure or proc")
		os.Exit(2)
	}
	fmt.Println(t)
}
