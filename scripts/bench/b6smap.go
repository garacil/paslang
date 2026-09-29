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
	"fmt"
	"strconv"
)

func main() {
	keys := make([]string, 1000000)
	for i := 0; i < 1000000; i++ {
		keys[i] = "key" + strconv.Itoa(i*7919)
	}
	m := make(map[string]int)
	for i := 0; i < 1000000; i++ {
		m[keys[i]] = i
	}
	t := 0
	for i := 0; i < 1000000; i++ {
		t += m[keys[i]]
	}
	fmt.Println(len(m), t)
}
