// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
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

// The Go side of b37argon2 (P438): golang.org/x/crypto/argon2 IDKey with
// the same parameters, and blake2b.Sum512 of the same buffer.
package main

import (
	"encoding/hex"
	"fmt"
	"os"

	"golang.org/x/crypto/argon2"
	"golang.org/x/crypto/blake2b"
)

func main() {
	if len(os.Args) > 1 && os.Args[1] == "argon2id" {
		acc := make([]byte, 32)
		for i := 1; i <= 8; i++ {
			tag := argon2.IDKey([]byte("correct horse battery staple"), []byte(fmt.Sprintf("salt%dsaltsalt", i)), 3, 65536, 4, 32)
			for k := range acc {
				acc[k] ^= tag[k]
			}
		}
		fmt.Println(hex.EncodeToString(acc))
		return
	}
	s := make([]byte, 1048576)
	for k := 1; k <= len(s); k++ {
		s[k-1] = byte((k * 31) & 255)
	}
	var acc [64]byte
	for i := 1; i <= 64; i++ {
		s[0] = byte(i)
		acc = blake2b.Sum512(s)
	}
	fmt.Println(hex.EncodeToString(acc[:]))
}
