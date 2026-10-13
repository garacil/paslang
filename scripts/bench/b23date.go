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

// P223: dates, the twin of b23date.paslang (its comment says what each
// section does).
package main

import (
	"fmt"
	"os"
	"time"
)

func main() {
	t := 0
	arg := ""
	if len(os.Args) > 1 {
		arg = os.Args[1]
	}
	switch arg {
	case "stamp":
		for i := 1; i <= 2000000; i++ {
			s := time.Unix(1767225600+int64(i)*7919, 0).UTC().Format("2006-01-02 15:04:05")
			t += int(s[8]) + int(s[17])
		}
	case "date":
		for i := 1; i <= 20000000; i++ {
			y, m, d := time.Unix(1767225600+int64(i)*7919, 0).UTC().Date()
			t += y + int(m) + d
		}
	default:
		fmt.Println("b23date: stamp or date")
		os.Exit(2)
	}
	fmt.Println(t)
}
