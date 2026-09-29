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

// The Go twin of examples/termd.paslang: the line protocol over TCP, a
// goroutine per session, the sessions in a map under a mutex, a writer
// goroutine per session fed by a channel, and the same self-test.
package main

import (
	"bufio"
	"fmt"
	"net"
	"os"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

type session struct {
	conn net.Conn
	name string
	out  chan string // lines to write; "\n" alone tells the writer to close
}

var (
	sessions  = map[int]*session{}
	guard     sync.Mutex
	nextID    int
	quitCount int64
	bad       int64
)

func writer(s *session) {
	for line := range s.out {
		if line == "\n" {
			break
		}
		fmt.Fprintf(s.conn, "%s\n", line)
	}
	s.conn.Close()
}

func broadcast(from *session, text string) {
	guard.Lock()
	for _, s := range sessions {
		if s != from {
			s.out <- "[" + from.name + "] " + text
		}
	}
	guard.Unlock()
}

func who() string {
	var b strings.Builder
	guard.Lock()
	for _, s := range sessions {
		b.WriteString(s.name + " ")
	}
	guard.Unlock()
	return b.String()
}

func serveSession(c net.Conn) {
	s := &session{conn: c, out: make(chan string, 64)}
	guard.Lock()
	nextID++
	id := nextID
	s.name = fmt.Sprintf("guest%d", id)
	sessions[id] = s
	guard.Unlock()
	go writer(s)
	s.out <- "welcome " + s.name + ", type help"
	sc := bufio.NewScanner(c)
	for sc.Scan() {
		line := sc.Text()
		cmd, arg, _ := strings.Cut(line, " ")
		switch cmd {
		case "help":
			s.out <- "help name who echo say count quit"
		case "name":
			if arg != "" {
				guard.Lock()
				s.name = arg
				guard.Unlock()
			}
			s.out <- "you are " + s.name
		case "who":
			s.out <- who()
		case "echo":
			s.out <- arg
		case "say":
			broadcast(s, arg)
			s.out <- "said"
		case "count":
			guard.Lock()
			s.out <- strconv.Itoa(len(sessions))
			guard.Unlock()
		case "quit":
			guard.Lock()
			delete(sessions, id)
			atomic.AddInt64(&quitCount, 1)
			guard.Unlock()
			s.out <- "bye"
			s.out <- "\n"
			return
		default:
			s.out <- "what? " + cmd
		}
	}
	// the peer went without quit: not counted as one
	guard.Lock()
	delete(sessions, id)
	guard.Unlock()
	s.out <- "\n"
}

func listen(l net.Listener) {
	for {
		c, err := l.Accept()
		if err != nil {
			return
		}
		go serveSession(c)
	}
}

func expect(c net.Conn, rd *bufio.Reader, cmd, want string) bool {
	if _, err := fmt.Fprintf(c, "%s\n", cmd); err != nil {
		return false
	}
	line, err := rd.ReadString('\n')
	if err != nil {
		return false
	}
	return strings.TrimRight(line, "\r\n") == want
}

// greeted is a connection that has said welcome: the greeting read with a
// deadline and a new connection tried when it does not come, as the
// paslang twin does (a burst past the SYN backlog leaves connections the
// server never had, and the server speaks first).
func greeted(port int) (net.Conn, *bufio.Reader) {
	for k := 0; k < 5; k++ {
		c, err := net.Dial("tcp", fmt.Sprintf("127.0.0.1:%d", port))
		if err != nil {
			continue
		}
		c.SetReadDeadline(time.Now().Add(3 * time.Second))
		rd := bufio.NewReader(c)
		line, err := rd.ReadString('\n')
		if err == nil && strings.HasPrefix(line, "welcome ") {
			c.SetReadDeadline(time.Time{})
			return c, rd
		}
		c.Close()
	}
	return nil, nil
}

func client(port, id int, wg *sync.WaitGroup) {
	defer wg.Done()
	c, rd := greeted(port)
	if c == nil {
		atomic.AddInt64(&bad, 1)
		return
	}
	defer c.Close()
	ok := expect(c, rd, fmt.Sprintf("name user%d", id), fmt.Sprintf("you are user%d", id))
	ok = ok && expect(c, rd, fmt.Sprintf("echo hello %d", id), fmt.Sprintf("hello %d", id))
	ok = ok && expect(c, rd, "nothing", "what? nothing")
	ok = ok && expect(c, rd, "quit", "bye")
	if !ok {
		atomic.AddInt64(&bad, 1)
	}
}

func selfTest(n int) {
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		fmt.Println("termd: cannot listen")
		os.Exit(1)
	}
	port := l.Addr().(*net.TCPAddr).Port
	go listen(l)
	var wg sync.WaitGroup
	wg.Add(n)
	for i := 1; i <= n; i++ {
		go client(port, i, &wg)
	}
	wg.Wait()
	fmt.Printf("%d sessions, %d quit, %d bad\n", n, atomic.LoadInt64(&quitCount), atomic.LoadInt64(&bad))
	if quitCount != int64(n) || bad != 0 {
		os.Exit(1)
	}
}

func main() {
	if len(os.Args) >= 2 && os.Args[1] == "-selftest" {
		n := 2000
		if len(os.Args) >= 3 {
			n, _ = strconv.Atoi(os.Args[2])
		}
		selfTest(n)
		return
	}
	port := 2323
	if len(os.Args) >= 2 {
		port, _ = strconv.Atoi(os.Args[1])
	}
	l, err := net.Listen("tcp", fmt.Sprintf(":%d", port))
	if err != nil {
		fmt.Println("termd: cannot listen on port", port)
		os.Exit(1)
	}
	fmt.Println("termd: listening on port", port)
	listen(l)
}
