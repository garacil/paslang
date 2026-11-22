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

// The Go twin of examples/httpd.paslang: an HTTP/1.1 server with
// keep-alive on net/http, and the same self-test: n client goroutines,
// three GET /hello each on one kept-alive connection, every answer
// checked. A final /stats.json request reads back the counters.
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"strconv"
	"sync"
	"sync/atomic"
)

const requests = 3

var served, opened, bad int64

type statistics struct {
	Connections int64 `json:"connections"`
	Requests    int64 `json:"requests"`
	Bad         int64 `json:"bad"`
}

func handler(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&served, 1)
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	switch r.URL.Path {
	case "/":
		io.WriteString(w, "go httpd: a goroutine per connection.\nTry /hello, /stats and /stats.json.\n")
	case "/hello":
		io.WriteString(w, "hello\n")
	case "/stats":
		fmt.Fprintf(w, "connections %d\nrequests %d\nbad %d\n", atomic.LoadInt64(&opened), atomic.LoadInt64(&served), atomic.LoadInt64(&bad))
	case "/stats.json":
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		json.NewEncoder(w).Encode(statistics{
			Connections: atomic.LoadInt64(&opened),
			Requests:    atomic.LoadInt64(&served),
			Bad:         atomic.LoadInt64(&bad),
		})
	default:
		w.WriteHeader(404)
		fmt.Fprintf(w, "no %s\n", r.URL.Path)
	}
}

func client(port int, wg *sync.WaitGroup) {
	defer wg.Done()
	c, err := net.Dial("tcp", fmt.Sprintf("127.0.0.1:%d", port))
	if err != nil {
		atomic.AddInt64(&bad, 1)
		return
	}
	defer c.Close()
	rd := bufio.NewReader(c)
	for k := 0; k < requests; k++ {
		if _, err := io.WriteString(c, "GET /hello HTTP/1.1\r\nHost: self\r\n\r\n"); err != nil {
			atomic.AddInt64(&bad, 1)
			return
		}
		resp, err := http.ReadResponse(rd, nil)
		if err != nil || resp.StatusCode != 200 {
			atomic.AddInt64(&bad, 1)
			return
		}
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		if string(body) != "hello\n" {
			atomic.AddInt64(&bad, 1)
			return
		}
	}
}

func readStatistics(port int) (statistics, error) {
	var stats statistics
	c, err := net.Dial("tcp", fmt.Sprintf("127.0.0.1:%d", port))
	if err != nil {
		return stats, err
	}
	defer c.Close()
	if _, err := io.WriteString(c, "GET /stats.json HTTP/1.1\r\nHost: self\r\nConnection: close\r\n\r\n"); err != nil {
		return stats, err
	}
	resp, err := http.ReadResponse(bufio.NewReader(c), nil)
	if err != nil {
		return stats, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return stats, fmt.Errorf("status %s", resp.Status)
	}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return stats, err
	}
	err = json.Unmarshal(body, &stats)
	return stats, err
}

func countConnection(_ net.Conn, state http.ConnState) {
	if state == http.StateNew {
		atomic.AddInt64(&opened, 1)
	}
}

func selfTest(n int) {
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		fmt.Println("httpd: cannot listen")
		os.Exit(1)
	}
	port := l.Addr().(*net.TCPAddr).Port
	srv := &http.Server{Handler: http.HandlerFunc(handler), ConnState: countConnection}
	go srv.Serve(l)
	var wg sync.WaitGroup
	wg.Add(n)
	for i := 0; i < n; i++ {
		go client(port, &wg)
	}
	wg.Wait()
	total, failures := atomic.LoadInt64(&served), atomic.LoadInt64(&bad)
	fmt.Printf("%d clients, %d requests, %d served, %d bad\n", n, n*requests, total, failures)
	if total != int64(n*requests) || failures != 0 {
		os.Exit(1)
	}
	stats, err := readStatistics(port)
	if err != nil {
		fmt.Printf("httpd: /stats.json: %s\n", err)
		os.Exit(1)
	}
	fmt.Printf("stats.json: %d connections, %d requests, %d bad\n", stats.Connections, stats.Requests, stats.Bad)
	if stats.Connections != int64(n)+1 || stats.Requests != total+1 || stats.Bad != 0 {
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
	port := 8080
	if len(os.Args) >= 2 {
		port, _ = strconv.Atoi(os.Args[1])
	}
	fmt.Printf("httpd: listening on port %d (GET /, /hello, /stats, /stats.json)\n", port)
	srv := &http.Server{Addr: fmt.Sprintf(":%d", port), Handler: http.HandlerFunc(handler), ConnState: countConnection}
	srv.ListenAndServe()
}
