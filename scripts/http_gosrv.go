// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// The second server of testdata/httpcli (P432): Go's net/http serving the
// same routes the program's own httpserver serves, so that scripts/
// http_client_go.sh can run the client's checks against both and compare
// what it prints. It writes its port on the first line of standard output.
//
//	go run scripts/http_gosrv.go
package main

import (
	"bytes"
	"compress/gzip"
	"fmt"
	"net"
	"net/http"
	"strings"
	"time"
)

func main() {
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		panic(err)
	}
	port := l.Addr().(*net.TCPAddr).Port
	var text strings.Builder
	for i := 1; i <= 400; i++ {
		fmt.Fprintf(&text, "line %d of the compressed body\n", i)
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /hello", func(w http.ResponseWriter, r *http.Request) { fmt.Fprint(w, "hello\n") })
	echo := func(w http.ResponseWriter, r *http.Request) {
		var b bytes.Buffer
		b.ReadFrom(r.Body)
		fmt.Fprintf(w, "%s ct=[%s] body=[%s]\n", r.Method, r.Header.Get("Content-Type"), b.String())
	}
	mux.HandleFunc("POST /echo", echo)
	mux.HandleFunc("PUT /echo", echo)
	mux.HandleFunc("GET /echo", echo)
	mux.HandleFunc("GET /hdrs", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintf(w, "ua=[%s] ae=[%s] auth=[%s] referer=[%s] cookie=[%s] x=[%s] host=[%s]\n", r.Header.Get("User-Agent"),
			r.Header.Get("Accept-Encoding"), r.Header.Get("Authorization"), r.Header.Get("Referer"), r.Header.Get("Cookie"),
			r.Header.Get("X-Custom"), r.Host)
	})
	redir := func(path string, code int, to string) {
		mux.HandleFunc(path, func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Location", to)
			w.WriteHeader(code)
		})
	}
	redir("GET /r301", 301, "/hello")
	redir("POST /r302", 302, "/echo")
	redir("POST /r303", 303, "/echo")
	redir("POST /r307", 307, "/echo")
	redir("POST /r308", 308, "echo")
	redir("GET /rel", 302, "sub/../hello?x=1")
	redir("GET /loop", 302, "/loop")
	redir("GET /abroad", 302, fmt.Sprintf("http://localhost:%d/hdrs", port))
	mux.HandleFunc("GET /noloc", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(302)
		fmt.Fprint(w, "no Location here")
	})
	mux.HandleFunc("GET /gz", func(w http.ResponseWriter, r *http.Request) {
		var b bytes.Buffer
		zw := gzip.NewWriter(&b)
		zw.Write([]byte(text.String()))
		zw.Close()
		w.Header().Set("Content-Encoding", "gzip")
		w.Header().Set("Content-Type", "text/plain")
		w.Write(b.Bytes())
	})
	mux.HandleFunc("GET /stream", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/plain")
		for i := 0; i < 3; i++ {
			w.Write([]byte(strings.Repeat(string(rune('a'+i)), 10000)))
			w.(http.Flusher).Flush()
		}
	})
	mux.HandleFunc("GET /big", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/octet-stream")
		w.Write([]byte(strings.Repeat("B", 1500000)))
	})
	mux.HandleFunc("GET /close", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Connection", "close")
		fmt.Fprint(w, "bye\n")
	})
	mux.HandleFunc("GET /slow", func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(1500 * time.Millisecond)
		fmt.Fprint(w, "late\n")
	})
	mux.HandleFunc("GET /status/{code}", func(w http.ResponseWriter, r *http.Request) {
		var c int
		fmt.Sscan(r.PathValue("code"), &c)
		w.WriteHeader(c)
		fmt.Fprintf(w, "status %d\n", c)
	})
	fmt.Println(port)
	http.Serve(l, mux)
}
