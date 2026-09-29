package main

import (
	"fmt"
	"sync"
)

func main() {
	var wg sync.WaitGroup
	var mu sync.Mutex
	n := 0
	wg.Add(100000)
	for i := 0; i < 100000; i++ {
		go func() {
			mu.Lock()
			n++
			mu.Unlock()
			wg.Done()
		}()
	}
	wg.Wait()
	fmt.Println(n)
}
