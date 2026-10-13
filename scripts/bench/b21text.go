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

// P223: bytes as text, the twin of b21text.paslang (its comment says
// what each section does).
package main

import (
	"encoding/hex"
	"fmt"
	"os"
	"strings"
)

func makeText() []byte {
	var sb strings.Builder
	x := 12345
	for sb.Len() < 1048576 {
		x = (x*1103515245 + 12345) & 0x7FFFFFFF
		k := (x >> 16) % 10
		switch {
		case k < 6:
			sb.WriteByte(byte(97 + (x>>8)%26))
		case k < 8:
			sb.WriteString("ñ")
		case k < 9:
			sb.WriteString("€")
		default:
			sb.WriteString("😀")
		}
	}
	return []byte(sb.String())
}

func main() {
	text := makeText()
	arg := ""
	if len(os.Args) > 1 {
		arg = os.Args[1]
	}
	switch arg {
	case "hex":
		t := 0
		for i := 1; i <= 200; i++ {
			text[0] = byte(97 + i%26)
			h := hex.EncodeToString(text)
			t += int(h[i]) + len(h)
		}
		fmt.Println(t)
	case "runes":
		s := string(text)
		t, n := 0, 0
		for i := 1; i <= 100; i++ {
			for _, r := range s {
				t += int(r)
				n++
			}
		}
		fmt.Println(n, t)
	default:
		fmt.Println("b21text: hex or runes")
		os.Exit(2)
	}
}
