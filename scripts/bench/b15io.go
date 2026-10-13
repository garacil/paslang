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

// P223: file reads and writes, the twin of b15io.paslang (its comment
// says what each section does).
package main

import (
	"fmt"
	"os"
)

const path = "/dev/shm/paslang-b15io-go"

func writeBlocks(size, count int) {
	buf := make([]byte, size)
	for i := range buf {
		buf[i] = byte(i * 7)
	}
	f, err := os.Create(path)
	if err != nil {
		panic(err)
	}
	n := 0
	for i := 1; i <= count; i++ {
		w, _ := f.Write(buf)
		n += w
	}
	f.Close()
	fmt.Println(n, buf[size-1])
}

func readBack() {
	buf := make([]byte, 65536)
	for i := range buf {
		buf[i] = byte(i * 7)
	}
	f, err := os.Create(path)
	if err != nil {
		panic(err)
	}
	for i := 1; i <= 1024; i++ {
		f.Write(buf)
	}
	f.Close()
	small := make([]byte, 256)
	n := 0
	f, err = os.Open(path)
	if err != nil {
		panic(err)
	}
	for {
		got, _ := f.Read(small)
		n += got
		if got <= 0 {
			break
		}
	}
	f.Close()
	fmt.Println(n, small[255])
}

func main() {
	arg := ""
	if len(os.Args) > 1 {
		arg = os.Args[1]
	}
	switch arg {
	case "small":
		writeBlocks(256, 262144)
	case "smallread":
		readBack()
	default:
		fmt.Println("b15io: small or smallread")
		os.Exit(2)
	}
	os.Remove(path)
}
