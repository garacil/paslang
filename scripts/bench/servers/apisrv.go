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

// The Go twin of examples/apisrv.paslang (P434): net/http's server and
// ServeMux with a {id} pattern, encoding/json in and out, the same
// clients and the same answers, for scripts/bench/servers.py.
package main

import (
	"bufio"
	"context"
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

var served, bad int64

type item struct {
	ID   int64  `json:"id"`
	Name string `json:"name"`
}

func hello(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&served, 1)
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	io.WriteString(w, "hello\n")
}

func getItem(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&served, 1)
	id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
	if err != nil {
		http.Error(w, "bad id", 400)
		return
	}
	b, _ := json.Marshal(item{id, "item " + strconv.FormatInt(id, 10)})
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Write(b)
}

func addItem(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&served, 1)
	var it item
	if err := json.NewDecoder(r.Body).Decode(&it); err != nil {
		http.Error(w, err.Error(), 400)
		return
	}
	b, _ := json.Marshal(item{it.ID + 1, it.Name})
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(201)
	w.Write(b)
}

func client(port, id int, wg *sync.WaitGroup) {
	defer wg.Done()
	c, err := net.Dial("tcp", fmt.Sprintf("127.0.0.1:%d", port))
	if err != nil {
		atomic.AddInt64(&bad, 1)
		return
	}
	defer c.Close()
	rd := bufio.NewReader(c)
	for k := 1; k <= requests; k++ {
		var want string
		status := 200
		switch k {
		case 1:
			io.WriteString(c, "GET /hello HTTP/1.1\r\nHost: self\r\n\r\n")
			want = "hello\n"
		case 2:
			io.WriteString(c, fmt.Sprintf("GET /api/items/%d HTTP/1.1\r\nHost: self\r\n\r\n", id))
			want = fmt.Sprintf(`{"id":%d,"name":"item %d"}`, id, id)
		default:
			body := fmt.Sprintf(`{"id":%d,"name":"new"}`, id)
			io.WriteString(c, fmt.Sprintf("POST /api/items HTTP/1.1\r\nHost: self\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n%s", len(body), body))
			want = fmt.Sprintf(`{"id":%d,"name":"new"}`, id+1)
			status = 201
		}
		resp, err := http.ReadResponse(rd, nil)
		if err != nil || resp.StatusCode != status {
			atomic.AddInt64(&bad, 1)
			return
		}
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		if string(body) != want {
			atomic.AddInt64(&bad, 1)
			return
		}
	}
}

func mux() *http.ServeMux {
	m := http.NewServeMux()
	m.HandleFunc("GET /hello", hello)
	m.HandleFunc("GET /api/items/{id}", getItem)
	m.HandleFunc("POST /api/items", addItem)
	return m
}

func selfTest(n int) {
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		fmt.Println("apisrv: cannot listen")
		os.Exit(1)
	}
	port := l.Addr().(*net.TCPAddr).Port
	srv := &http.Server{Handler: mux()}
	go srv.Serve(l)
	var wg sync.WaitGroup
	wg.Add(n)
	for i := 1; i <= n; i++ {
		go client(port, i, &wg)
	}
	wg.Wait()
	srv.Shutdown(context.Background())
	fmt.Printf("%d clients, %d requests, %d served, %d bad\n", n, n*requests, atomic.LoadInt64(&served), atomic.LoadInt64(&bad))
	if served != int64(n*requests) || bad != 0 {
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
	fmt.Printf("apisrv: listening on 127.0.0.1:%d\n", port)
	http.ListenAndServe(fmt.Sprintf("127.0.0.1:%d", port), mux())
}
