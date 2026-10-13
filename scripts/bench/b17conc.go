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

// P223: channels and time, the twin of b17conc.paslang (its comment
// says what each section does).
package main

import (
	"fmt"
	"os"
	"sync"
	"sync/atomic"
	"time"
)

var (
	wg    sync.WaitGroup
	count int64
)

func sleeper() {
	for k := 1; k <= 10; k++ {
		time.Sleep(time.Millisecond)
	}
	atomic.AddInt64(&count, 1)
	wg.Done()
}

func waiter() {
	never := make(chan int)
	for k := 1; k <= 5; k++ {
		select {
		case <-never:
			atomic.AddInt64(&count, 100)
		case <-time.After(time.Millisecond):
			atomic.AddInt64(&count, 1)
		}
	}
	wg.Done()
}

func producer(c chan int, n int) {
	for i := 1; i <= n; i++ {
		c <- i
	}
}

func pipe() {
	c := make(chan int, 128)
	go producer(c, 10000000)
	t := 0
	for i := 1; i <= 10000000; i++ {
		t += <-c
	}
	fmt.Println(t)
}

func fanIn() {
	a, b, c, d := make(chan int, 64), make(chan int, 64), make(chan int, 64), make(chan int, 64)
	go producer(a, 2500000)
	go producer(b, 2500000)
	go producer(c, 2500000)
	go producer(d, 2500000)
	t := 0
	for i := 1; i <= 10000000; i++ {
		select {
		case x := <-a:
			t += x
		case x := <-b:
			t += x
		case x := <-c:
			t += x
		case x := <-d:
			t += x
		}
	}
	fmt.Println(t)
}

func main() {
	arg := ""
	if len(os.Args) > 1 {
		arg = os.Args[1]
	}
	switch arg {
	case "sleep":
		wg.Add(20000)
		for i := 1; i <= 20000; i++ {
			go sleeper()
		}
		wg.Wait()
		fmt.Println(count)
	case "timeout":
		wg.Add(20000)
		for i := 1; i <= 20000; i++ {
			go waiter()
		}
		wg.Wait()
		fmt.Println(count)
	case "pipe":
		pipe()
	case "fanin":
		fanIn()
	default:
		fmt.Println("b17conc: sleep, timeout, pipe or fanin")
		os.Exit(2)
	}
}
