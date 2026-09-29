package main

import "fmt"

func main() {
	m := make(map[int]int)
	for i := 1; i <= 1000000; i++ {
		m[i*7919] = i
	}
	t := 0
	for i := 1; i <= 1000000; i++ {
		t += m[i*7919]
	}
	fmt.Println(len(m), t)
}
