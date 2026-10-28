// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// P479: HTTP requests read, the Go side of scripts/bench/b42http.paslang:
// 200,000 requests of six shapes (a bare GET, a POST with a JSON body, a
// GET with a long query and cookies, a chunked POST, a PUT whose header
// names are in lower case, a GET with twelve headers) each read whole with
// net/http's ReadRequest from one bufio.Reader that is reset for each; the
// method, the path, the number of fields, the Content-Length and the body's
// length are summed.
package main

import (
	"bufio"
	"fmt"
	"io"
	"net/http"
	"strings"
)

const H = "\r\n"

func main() {
	reqs := []string{
		"GET /items/42 HTTP/1.1" + H + "Host: 127.0.0.1:8080" + H + "User-Agent: bench/1.0" + H +
			"Accept: */*" + H + "Accept-Encoding: gzip" + H + "Connection: keep-alive" + H + H,
		"POST /items HTTP/1.1" + H + "Host: 127.0.0.1:8080" + H + "User-Agent: bench/1.0" + H +
			"Content-Type: application/json" + H + "Content-Length: 21" + H + H + `{"name":"Ana","n":42}`,
		"GET /search?q=pascal&page=2&sort=name HTTP/1.1" + H + "Host: example.org" + H +
			"Cookie: session=0123456789abcdef0123456789abcdef; theme=dark; lang=es; tracking=abcdefghijklmnopqrstuvwxyz" + H +
			"Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123456789" + H + "Accept-Language: es-ES,es;q=0.9,en;q=0.8" + H + H,
		"POST /upload HTTP/1.1" + H + "Host: example.org" + H + "Transfer-Encoding: chunked" + H +
			"Content-Type: text/plain" + H + H + "10" + H + "0123456789abcdef" + H + "5" + H + "hello" + H + "0" + H + H,
		"PUT /files/a/b/c.txt HTTP/1.1" + H + "host: example.org" + H + "content-length: 5" + H +
			"content-type: text/plain" + H + "x-request-id: 42" + H + H + "hello",
		"GET /api/v1/users HTTP/1.1" + H + "Host: example.org" + H + "User-Agent: Mozilla/5.0 (X11; Linux x86_64)" + H +
			"Accept: text/html,application/xhtml+xml" + H + "Accept-Language: en-US" + H + "Accept-Encoding: gzip, deflate" + H +
			"Connection: keep-alive" + H + "Upgrade-Insecure-Requests: 1" + H + "Cache-Control: max-age=0" + H +
			"X-Forwarded-For: 10.0.0.1" + H + "X-Real-IP: 10.0.0.1" + H + "X-Request-Id: abcdef" + H + H,
	}
	sr := strings.NewReader("")
	br := bufio.NewReader(sr)
	var sum int64
	for n := 1; n <= 200000; n++ {
		i := n % 6
		sr.Reset(reqs[i])
		br.Reset(sr)
		r, err := http.ReadRequest(br)
		if err != nil {
			panic(err)
		}
		b, _ := io.ReadAll(r.Body)
		sum += int64(len(r.Method) + len(r.URL.Path) + len(r.Header) + len(b))
		sum += r.ContentLength
	}
	fmt.Println(sum)
}
