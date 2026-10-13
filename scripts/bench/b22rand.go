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

// P223: random numbers, the twin of b22rand.paslang (its comment says
// what each section does).
package main

import (
	"fmt"
	"math/rand/v2"
	"os"
	"sync"
	"sync/atomic"
)

var sink int64

func main() {
	r := rand.New(rand.NewPCG(42, 1))
	t, n := uint64(0), 0
	arg := ""
	if len(os.Args) > 1 {
		arg = os.Args[1]
	}
	switch arg {
	case "own":
		for i := 1; i <= 100000000; i++ {
			t ^= r.Uint64()
		}
		n = 100000000
	case "below":
		for i := 1; i <= 50000000; i++ {
			t += uint64(r.IntN(1000))
		}
		n = 50000000
	case "real":
		f := 0.0
		for i := 1; i <= 50000000; i++ {
			f += r.Float64()
		}
		t = uint64(f)
		n = 50000000
	case "global":
		for i := 1; i <= 20000000; i++ {
			t ^= rand.Uint64()
		}
		n = 20000000
	case "globalpar":
		var wg sync.WaitGroup
		wg.Add(8)
		for i := 1; i <= 8; i++ {
			go func() {
				u := uint64(0)
				for k := 1; k <= 2500000; k++ {
					u ^= rand.Uint64()
				}
				atomic.AddInt64(&sink, int64(u&1))
				wg.Done()
			}()
		}
		wg.Wait()
		n = 20000000
	default:
		fmt.Println("b22rand: own, below, real, global or globalpar")
		os.Exit(2)
	}
	if t == 1 {
		sink++
	}
	fmt.Println(n)
}
