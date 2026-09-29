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
