package main

import (
	"fmt"
	"strconv"
)

func main() {
	total := 0
	for i := 1; i <= 3000000; i++ {
		s := "item-" + strconv.Itoa(i)
		total += len(s)
	}
	fmt.Println(total)
}
