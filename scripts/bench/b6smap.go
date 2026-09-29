package main

import (
	"fmt"
	"strconv"
)

func main() {
	keys := make([]string, 1000000)
	for i := 0; i < 1000000; i++ {
		keys[i] = "key" + strconv.Itoa(i*7919)
	}
	m := make(map[string]int)
	for i := 0; i < 1000000; i++ {
		m[keys[i]] = i
	}
	t := 0
	for i := 0; i < 1000000; i++ {
		t += m[keys[i]]
	}
	fmt.Println(len(m), t)
}
