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

// P617: an HTTP/2 client, the twin of b46http2.paslang (its comment says
// what each section does): net/http's client with HTTP/2 by prior
// knowledge on one end of a pair of connected Unix sockets, and on the
// other a goroutine that plays the server as the paslang program's does.
package main

import (
	"context"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"strconv"
	"sync"
	"syscall"
)

func frame(typ, flags byte, id int, payload []byte) []byte {
	n := len(payload)
	b := []byte{byte(n >> 16), byte(n >> 8), byte(n), typ, flags, byte(id >> 24), byte(id >> 16), byte(id >> 8), byte(id)}
	return append(b, payload...)
}

func writeAll(c net.Conn, b []byte) {
	if _, err := c.Write(b); err != nil {
		os.Exit(3)
	}
}

// the server: a response of bodyLen octets to every request
func peer(c net.Conn, bodyLen int) {
	// the response once: HEADERS, then DATA frames; ids holds where each
	// frame's stream number goes
	ln := strconv.Itoa(bodyLen)
	block := []byte{136, 15, 16, 10}
	block = append(block, "text/plain"...)
	block = append(block, 15, 13, byte(len(ln)))
	block = append(block, ln...)
	resp := frame(1, 4, 0, block)
	ids := []int{5}
	body := make([]byte, 16384)
	for i := range body {
		body[i] = byte(97 + (i+1)%26)
	}
	for i := 0; i < bodyLen; {
		part := min(bodyLen-i, 16384)
		var flags byte
		if i+part == bodyLen {
			flags = 1
		}
		ids = append(ids, len(resp)+5)
		resp = append(resp, frame(0, flags, 0, body[:part])...)
		i += part
	}
	buf := make([]byte, 65536)
	have, pos := 0, 0
	// the preface, then SETTINGS: a thousand streams at once
	for have < 24 {
		k, err := c.Read(buf[have:])
		if err != nil {
			return
		}
		have += k
	}
	pos = 24
	writeAll(c, frame(4, 0, 0, []byte{0, 3, 0, 0, 3, 232}))
	for {
		// a whole frame in buf from pos
		for have-pos < 9 || have-pos < 9+(int(buf[pos])<<16|int(buf[pos+1])<<8|int(buf[pos+2])) {
			if pos > 0 {
				copy(buf, buf[pos:have])
				have -= pos
				pos = 0
			}
			k, err := c.Read(buf[have:])
			if err != nil {
				return
			}
			have += k
		}
		n := int(buf[pos])<<16 | int(buf[pos+1])<<8 | int(buf[pos+2])
		typ, flags := buf[pos+3], buf[pos+4]
		id := int(buf[pos+5])<<24 | int(buf[pos+6])<<16 | int(buf[pos+7])<<8 | int(buf[pos+8])
		pos += 9 + n
		if typ == 4 && flags&1 == 0 {
			writeAll(c, frame(4, 1, 0, nil))
		} else if typ == 1 {
			for _, k := range ids {
				resp[k], resp[k+1], resp[k+2], resp[k+3] = byte(id>>24), byte(id>>16), byte(id>>8), byte(id)
			}
			writeAll(c, resp)
		}
	}
}

var (
	client *http.Client
	total  int
	mu     sync.Mutex
)

func fetch(i int) int {
	req, err := http.NewRequest("GET", "http://bench/item/"+strconv.Itoa(i), nil)
	if err != nil {
		panic(err)
	}
	req.Header.Set("user-agent", "bench/1.0")
	req.Header.Set("accept", "*/*")
	req.Header.Set("authorization", "Bearer abcdefghijklmnopqrstuvwxyz0123456789abcdefghijklmnopqrstuvwxyz")
	resp, err := client.Do(req)
	if err != nil {
		fmt.Println("failed:", err)
		os.Exit(1)
	}
	b, err := io.ReadAll(resp.Body)
	resp.Body.Close()
	if err != nil || resp.StatusCode != 200 {
		os.Exit(4)
	}
	return len(b)
}

func run(routines, each, bodyLen int) {
	fds, err := syscall.Socketpair(syscall.AF_UNIX, syscall.SOCK_STREAM, 0)
	if err != nil {
		panic(err)
	}
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
	go peer(b, bodyLen)
	// one connection: the end of the pair, handed out once
	var once sync.Once
	tr := &http.Transport{DisableCompression: true}
	tr.Protocols = new(http.Protocols)
	tr.Protocols.SetUnencryptedHTTP2(true)
	tr.DialContext = func(ctx context.Context, network, addr string) (net.Conn, error) {
		var c net.Conn
		once.Do(func() { c = a })
		if c == nil {
			return nil, fmt.Errorf("a second connection was asked for")
		}
		return c, nil
	}
	client = &http.Client{Transport: tr}
	// the connection is made by a first request, so that every routine
	// finds it there
	fetch(0)
	var wg sync.WaitGroup
	for k := 1; k <= routines; k++ {
		wg.Add(1)
		go func(k int) {
			s := 0
			for i := 1; i <= each; i++ {
				s += fetch(k*100000 + i)
			}
			mu.Lock()
			total += s
			mu.Unlock()
			wg.Done()
		}(k)
	}
	wg.Wait()
	fmt.Println(routines*each, total)
	tr.CloseIdleConnections()
}

func main() {
	arg := ""
	if len(os.Args) > 1 {
		arg = os.Args[1]
	}
	switch arg {
	case "seq":
		run(1, 50000, 200)
	case "conc":
		run(64, 2000, 200)
	case "big":
		run(1, 100, 2097152)
	default:
		fmt.Println("b46http2: seq, conc or big")
		os.Exit(2)
	}
}
