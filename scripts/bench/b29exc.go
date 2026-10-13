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

// P223: an error carried up and caught, the twin of b29exc.paslang (its
// comment says what it does).
package main

import (
	"fmt"
	"os"
)

type bench struct{ code int }

//go:noinline
func deep3(k int) {
	if k >= 0 {
		panic(&bench{code: k & 7})
	}
}

//go:noinline
func deep2(k int) { deep3(k) }

//go:noinline
func deep1(k int) { deep2(k) }

func catch(k int) (r int) {
	defer func() {
		if e := recover(); e != nil {
			if b, ok := e.(*bench); ok {
				r = b.code
			} else {
				panic(e)
			}
		}
	}()
	deep1(k)
	return 0
}

func main() {
	if len(os.Args) < 2 || os.Args[1] != "raise" {
		fmt.Println("b29exc: raise")
		os.Exit(2)
	}
	t := 0
	for i := 1; i <= 1000000; i++ {
		t += catch(i)
	}
	fmt.Println(t)
}
