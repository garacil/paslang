package main

import (
	"fmt"
	"math/bits"
)

func main() {
	var s0, s1, s2, s3, sum uint64 = 1, 2, 3, 4, 0
	for i := 1; i <= 100000000; i++ {
		r := bits.RotateLeft64(s1*5, 7) * 9
		t := s1 << 17
		s2 ^= s0
		s3 ^= s1
		s1 ^= s2
		s0 ^= s3
		s2 ^= t
		s3 = bits.RotateLeft64(s3, 45)
		sum += r
	}
	fmt.Println(int64(sum), int64(s0))
}
