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

// P223: the string words, the twin of b13strw.paslang (its comment
// says what each section does).
package main

import (
	"fmt"
	"os"
	"strings"
)

var text string

func makeText() {
	b := make([]byte, 65536)
	x := 12345
	for i := 0; i < 65536; i++ {
		x = (x*1103515245 + 12345) & 0x7FFFFFFF
		if (x>>16)%7 == 0 {
			b[i] = ' '
		} else {
			b[i] = byte(97 + (x>>16)%26)
		}
	}
	text = string(b)
}

func index() {
	w := text[64999 : 64999+12]
	t := 0
	for i := 1; i <= 20000; i++ {
		t += strings.Index(text, w) + 1
	}
	fmt.Println(t)
}

func upper() {
	s := text[:1024]
	t := 0
	for i := 1; i <= 300000; i++ {
		u := strings.ToUpper(s)
		t += int(u[i%1024])
	}
	fmt.Println(t)
}

func lower() {
	s := strings.ToUpper(text[:1024])
	t := 0
	for i := 1; i <= 300000; i++ {
		u := strings.ToLower(s)
		t += int(u[i%1024])
	}
	fmt.Println(t)
}

func replace() {
	s := text[:1024]
	t := 0
	for i := 1; i <= 200000; i++ {
		u := strings.ReplaceAll(s, "ab", "xyz")
		t += len(u)
	}
	fmt.Println(t)
}

func trim() {
	s := "      " + text[99:99+28] + "      "
	t := 0
	for i := 1; i <= 5000000; i++ {
		u := strings.TrimSpace(s)
		t += len(u)
	}
	fmt.Println(t)
}

func compare() {
	a := text[:1024]
	b := text[:1023] + "~"
	t := 0
	for i := 1; i <= 2000000; i++ {
		c := strings.Compare(a, b)
		if c < 0 {
			t--
		} else if c > 0 {
			t++
		}
	}
	fmt.Println(t)
}

func equalFold() {
	a := text[:1024]
	b := strings.ToUpper(text[:1023]) + "~"
	t := 0
	for i := 1; i <= 2000000; i++ {
		if strings.EqualFold(a, b) {
			t++
		} else {
			t += 2
		}
	}
	fmt.Println(t)
}

func concat() {
	var sb strings.Builder
	for i := 1; i <= 20000000; i++ {
		sb.WriteByte(text[i%65536])
	}
	s := sb.String()
	fmt.Println(len(s), int(s[12344]))
}

func main() {
	makeText()
	arg := ""
	if len(os.Args) > 1 {
		arg = os.Args[1]
	}
	switch arg {
	case "index":
		index()
	case "upper":
		upper()
	case "lower":
		lower()
	case "replace":
		replace()
	case "trim":
		trim()
	case "compare":
		compare()
	case "equalfold":
		equalFold()
	case "concat":
		concat()
	default:
		fmt.Println("b13strw: index, upper, lower, replace, trim, compare, equalfold or concat")
		os.Exit(2)
	}
}
