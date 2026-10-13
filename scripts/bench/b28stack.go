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

// P223: stacks that grow, the twin of b28stack.paslang (its comment
// says what each section does).
package main

import (
	"fmt"
	"os"
	"sync"
	"sync/atomic"
)

//go:noinline
func down(n int) int {
	if n == 0 {
		return 0
	}
	return down(n-1) + (n & 3)
}

func main() {
	var total int64
	arg := ""
	if len(os.Args) > 1 {
		arg = os.Args[1]
	}
	switch arg {
	case "deep":
		for i := 1; i <= 20; i++ {
			total += int64(down(1000000))
		}
	case "many":
		var wg sync.WaitGroup
		wg.Add(2000)
		for i := 1; i <= 2000; i++ {
			go func() {
				atomic.AddInt64(&total, int64(down(20000)))
				wg.Done()
			}()
		}
		wg.Wait()
	default:
		fmt.Println("b28stack: deep or many")
		os.Exit(2)
	}
	fmt.Println(total)
}
