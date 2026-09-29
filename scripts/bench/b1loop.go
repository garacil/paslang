package main

import "fmt"

func main() {
	n := int64(1000000000)
	var s int64
	for i := int64(1); i <= n; i++ {
		s += (i ^ s) & 255
	}
	fmt.Println(s)
}
