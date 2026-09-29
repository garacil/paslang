// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacil@tucall.com>
//
// paslang is free software: you can redistribute it and/or modify it
// under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// paslang is distributed in the hope that it will be useful, but
// WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
// General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with paslang.  If not, see <https://www.gnu.org/licenses/>.

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
