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

// P201: UTF-8 validation, the twin of b33utf8.paslang (its comment
// says what each section does).
package main

import (
	"fmt"
	"os"
	"unicode/utf8"
)

func main() {
	unit := "abcdefghijklmnopqrstuvwxyz0123456789 "
	if len(os.Args) > 1 && os.Args[1] == "mixed" {
		unit = "Grüße, 世界! añadir — ünïcödé 😀 text "
	}
	buf := make([]byte, 0, 1<<20)
	for len(buf)+len(unit) <= 1<<20 {
		buf = append(buf, unit...)
	}
	t := 0
	for i := 0; i < 2000; i++ {
		if utf8.Valid(buf) {
			t += len(buf)
		}
	}
	fmt.Println(t)
}
