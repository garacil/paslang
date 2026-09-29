package main

import (
	"encoding/binary"
	"fmt"
)

type Node struct {
	Val  int64
	Next *Node
}

func main() {
	n := 32 * 1024 * 1024
	buf := make([]byte, n)
	var sum int64
	for r := 1; r <= 4; r++ {
		for i := 0; i < n; i++ {
			buf[i] = byte(i + r)
		}
		for i := 0; i < n; i += 4 {
			sum += int64(binary.LittleEndian.Uint32(buf[i:]))
		}
	}
	var head *Node
	for i := 1; i <= 1000000; i++ {
		head = &Node{Val: int64(i), Next: head}
	}
	for r := 1; r <= 20; r++ {
		for nd := head; nd != nil; nd = nd.Next {
			sum += nd.Val
		}
	}
	fmt.Println(sum)
}
