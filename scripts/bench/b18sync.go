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

// P223: the sync words, the twin of b18sync.paslang (its comment says
// what each section does).
package main

import (
	"fmt"
	"os"
	"sync"
	"sync/atomic"
)

var (
	wg     sync.WaitGroup
	mu     sync.Mutex
	rw     sync.RWMutex
	once   sync.Once
	turn   = sync.NewCond(&mu)
	count  int64
	shared int64
	whose  int
)

func locker() {
	for k := 1; k <= 500000; k++ {
		mu.Lock()
		count++
		mu.Unlock()
	}
	wg.Done()
}

func reader() {
	var t int64
	for k := 1; k <= 1000000; k++ {
		rw.RLock()
		v := shared
		rw.RUnlock()
		t += v
	}
	atomic.AddInt64(&count, t)
	wg.Done()
}

func setup() {
	shared++
}

func player(me int) {
	for k := 1; k <= 200000; k++ {
		mu.Lock()
		for whose != me {
			turn.Wait()
		}
		whose = 1 - me
		count++
		turn.Signal()
		mu.Unlock()
	}
	wg.Done()
}

func adder() {
	for k := 1; k <= 2000000; k++ {
		atomic.AddInt64(&count, 1)
	}
	wg.Done()
}

func main() {
	shared = 3
	arg := ""
	if len(os.Args) > 1 {
		arg = os.Args[1]
	}
	switch arg {
	case "mutex":
		wg.Add(16)
		for i := 1; i <= 16; i++ {
			go locker()
		}
		wg.Wait()
	case "rwread":
		wg.Add(16)
		for i := 1; i <= 16; i++ {
			go reader()
		}
		wg.Wait()
	case "once":
		for i := 1; i <= 50000000; i++ {
			once.Do(setup)
		}
		count = shared
	case "cond":
		wg.Add(2)
		go player(0)
		go player(1)
		wg.Wait()
	case "atomic":
		wg.Add(16)
		for i := 1; i <= 16; i++ {
			go adder()
		}
		wg.Wait()
	default:
		fmt.Println("b18sync: mutex, rwread, once, cond or atomic")
		os.Exit(2)
	}
	fmt.Println(count)
}
