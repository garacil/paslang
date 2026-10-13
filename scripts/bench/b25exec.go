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

// P223: starting programs, the twin of b25exec.paslang (its comment
// says what each section does).
package main

import (
	"fmt"
	"os"
	"os/exec"
	"sync"
	"sync/atomic"
)

func run() int {
	if err := exec.Command("/usr/bin/true").Run(); err != nil {
		return 1
	}
	return 0
}

func main() {
	var total int64
	arg := ""
	if len(os.Args) > 1 {
		arg = os.Args[1]
	}
	switch arg {
	case "serial":
		for i := 1; i <= 500; i++ {
			total += int64(run())
		}
	case "par":
		var wg sync.WaitGroup
		wg.Add(8)
		for i := 1; i <= 8; i++ {
			go func() {
				t := 0
				for k := 1; k <= 50; k++ {
					t += run()
				}
				atomic.AddInt64(&total, int64(t))
				wg.Done()
			}()
		}
		wg.Wait()
	default:
		fmt.Println("b25exec: serial or par")
		os.Exit(2)
	}
	fmt.Println(total)
}
