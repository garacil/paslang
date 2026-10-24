// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// P451: base64, the Go side of scripts/bench/b41base64.paslang: ten times a
// buffer of 3 MB encoded with encoding/base64 and decoded again, the lengths
// summed.
package main

import (
	"encoding/base64"
	"fmt"
)

func main() {
	s := make([]byte, 3000000)
	for i := range s {
		s[i] = byte((i + 1) * 7)
	}
	sum := 0
	for j := 0; j < 10; j++ {
		e := base64.StdEncoding.EncodeToString(s)
		d, _ := base64.StdEncoding.DecodeString(e)
		sum += len(e) + len(d)
	}
	fmt.Println(sum)
}
