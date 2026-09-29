// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacil@tucall.com>
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
	a := make(chan int)
	b := make(chan int)
	go func() {
		for {
			n := <-a
			if n < 0 {
				return
			}
			b <- n + 1
		}
	}()
	x := 0
	for i := 0; i < 1000000; i++ {
		a <- x
		x = <-b
	}
	a <- -1
	fmt.Println(x)
}
