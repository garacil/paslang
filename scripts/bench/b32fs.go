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

// P223: the file system, the twin of b32fs.paslang (its comment says
// what each section does).
package main

import (
	"fmt"
	"os"
	"strconv"
)

func main() {
	dir := "/dev/shm/paslang-b32fs-go"
	os.MkdirAll(dir, 0755)
	for i := 1; i <= 2000; i++ {
		f, err := os.Create(dir + "/f" + strconv.Itoa(i))
		if err != nil {
			panic(err)
		}
		f.Close()
	}
	t := 0
	arg := ""
	if len(os.Args) > 1 {
		arg = os.Args[1]
	}
	switch arg {
	case "stat":
		for i := 1; i <= 500000; i++ {
			if _, err := os.Stat(dir + "/f" + strconv.Itoa(1+i%2000)); err == nil {
				t++
			}
		}
	case "list":
		for i := 1; i <= 500; i++ {
			d, err := os.Open(dir)
			if err != nil {
				panic(err)
			}
			names, _ := d.Readdirnames(-1)
			d.Close()
			t += len(names)
		}
	default:
		fmt.Println("b32fs: stat or list")
		os.Exit(2)
	}
	for i := 1; i <= 2000; i++ {
		os.Remove(dir + "/f" + strconv.Itoa(i))
	}
	os.Remove(dir)
	fmt.Println(t)
}
