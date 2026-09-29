package main

import "fmt"

func main() {
	n := 64 * 1024 * 1024
	data := make([]byte, n)
	var x int64 = 12345
	for i := 0; i < n; i++ {
		x = x*1103515245 + 12345
		data[i] = byte(x >> 16)
	}
	var tab [256]byte
	for i := 0; i < 256; i++ {
		tab[i] = byte(i*7 + 3)
	}
	var hist [256]int64
	for pass := 1; pass <= 4; pass++ {
		for i := 0; i < n; i++ {
			data[i] = tab[data[i]]
		}
		for i := 0; i < n; i++ {
			hist[data[i]]++
		}
	}
	var sum int64
	for i := 0; i < 256; i++ {
		sum += hist[i] * int64(i)
	}
	fmt.Println(sum)
}
