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

// P223: the hashes, the twin of b20hash.paslang (its comment says what
// each section does).
package main

import (
	"crypto/hmac"
	"crypto/md5"
	"crypto/sha1"
	"crypto/sha256"
	"crypto/sha3"
	"crypto/sha512"
	"encoding/hex"
	"fmt"
	"hash/adler32"
	"hash/crc32"
	"hash/fnv"
	"os"
)

func main() {
	s := make([]byte, 1048576)
	for k := 1; k <= len(s); k++ {
		s[k-1] = byte((k * 31) & 255)
	}
	var d []byte
	acc := int64(0)
	arg := ""
	if len(os.Args) > 1 {
		arg = os.Args[1]
	}
	switch arg {
	case "md5":
		for i := 1; i <= 128; i++ {
			s[0] = byte(i)
			h := md5.Sum(s)
			d = h[:]
		}
	case "sha1":
		for i := 1; i <= 256; i++ {
			s[0] = byte(i)
			h := sha1.Sum(s)
			d = h[:]
		}
	case "sha512":
		for i := 1; i <= 128; i++ {
			s[0] = byte(i)
			h := sha512.Sum512(s)
			d = h[:]
		}
	case "sha3":
		for i := 1; i <= 64; i++ {
			s[0] = byte(i)
			h := sha3.Sum256(s)
			d = h[:]
		}
	case "hmac":
		for i := 1; i <= 256; i++ {
			s[0] = byte(i)
			m := hmac.New(sha256.New, []byte("key of the bench"))
			m.Write(s)
			d = m.Sum(nil)
		}
	case "crc32":
		for i := 1; i <= 2048; i++ {
			s[0] = byte(i & 255)
			s[1] = byte(i >> 8)
			acc ^= int64(crc32.ChecksumIEEE(s))
		}
	case "adler32":
		for i := 1; i <= 512; i++ {
			s[0] = byte(i & 255)
			acc ^= int64(adler32.Checksum(s))
		}
	case "fnv":
		for i := 1; i <= 256; i++ {
			s[0] = byte(i)
			h := fnv.New64a()
			h.Write(s)
			acc ^= int64(h.Sum64())
		}
	default:
		fmt.Println("b20hash: md5, sha1, sha512, sha3, hmac, crc32, adler32 or fnv")
		os.Exit(2)
	}
	if d != nil {
		fmt.Println(hex.EncodeToString(d))
	} else {
		fmt.Println(acc)
	}
}
