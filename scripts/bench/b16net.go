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

// P223: a stream between two goroutines, the twin of b16net.paslang
// (its comment says what each section does).
package main

import (
	"fmt"
	"net"
	"os"
	"syscall"
)

const (
	total = 1 << 30
	block = 65536
)

var blk []byte

func writer(c net.Conn) {
	sent := 0
	for sent < total {
		n, err := c.Write(blk)
		if err != nil {
			panic(err)
		}
		sent += n
	}
	c.Close()
}

func drain(c net.Conn) {
	buf := make([]byte, block)
	n, last := 0, 0
	for {
		got, err := c.Read(buf)
		n += got
		if got > 0 {
			last = int(buf[got-1])
		}
		if err != nil {
			break
		}
	}
	fmt.Println(n, last)
}

func tcp() {
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		panic(err)
	}
	c, err := net.Dial("tcp", l.Addr().String())
	if err != nil {
		panic(err)
	}
	a, err := l.Accept()
	if err != nil {
		panic(err)
	}
	go writer(c)
	drain(a)
}

func unix() {
	fds, err := syscall.Socketpair(syscall.AF_UNIX, syscall.SOCK_STREAM, 0)
	if err != nil {
		panic(err)
	}
	// FileConn takes a copy of the descriptor: the file is closed after,
	// or the reader would never see the end of the stream.
	fa, fb := os.NewFile(uintptr(fds[0]), "a"), os.NewFile(uintptr(fds[1]), "b")
	a, err := net.FileConn(fa)
	if err != nil {
		panic(err)
	}
	b, err := net.FileConn(fb)
	if err != nil {
		panic(err)
	}
	fa.Close()
	fb.Close()
	go writer(a)
	drain(b)
}

func main() {
	blk = make([]byte, block)
	for i := range blk {
		blk[i] = byte((i + 1) * 7)
	}
	arg := ""
	if len(os.Args) > 1 {
		arg = os.Args[1]
	}
	switch arg {
	case "tcp":
		tcp()
	case "unix":
		unix()
	default:
		fmt.Println("b16net: tcp or unix")
		os.Exit(2)
	}
}
