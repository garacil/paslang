package main

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"hash/crc32"
)

func main() {
	s := make([]byte, 1048576)
	for i := 1; i <= len(s); i++ {
		s[i-1] = byte((i * 31) & 255)
	}
	acc := 0
	var d [32]byte
	for i := 1; i <= 64; i++ {
		s[0] = byte(i)
		d = sha256.Sum256(s)
		acc += int(d[0]) + int(d[31])
	}
	tab := crc32.MakeTable(crc32.Castagnoli)
	crc := 0
	for i := 1; i <= 256; i++ {
		s[0] = byte(i)
		crc ^= int(crc32.Checksum(s, tab))
	}
	fmt.Println(acc, crc, hex.EncodeToString(d[:]))
}
