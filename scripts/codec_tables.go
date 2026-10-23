// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// The case tables of src/lib/pascodec.paslang (P435): what Go's
// strings.ToUpper and strings.ToLower give each code point of U+0000 to
// U+017F (Latin-1 and Latin Extended-A), as lines "cp upper lower" for
// those that change, and the oracle of testdata/codec: with -oracle it
// prints the expected output of the test (see codec_oracle below).
//
//	go run scripts/codec_tables.go > build/codec_tables.txt
package main

import (
	"fmt"
	"strings"
)

func main() {
	for c := rune(0); c <= 0x17F; c++ {
		s := string(c)
		u := []rune(strings.ToUpper(s))
		l := []rune(strings.ToLower(s))
		if len(u) != 1 || len(l) != 1 {
			panic("multi")
		}
		if u[0] != c || l[0] != c {
			fmt.Printf("%04X %04X %04X\n", c, u[0], l[0])
		}
	}
}
