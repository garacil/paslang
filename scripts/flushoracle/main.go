// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// flushoracle URL: Go's net/http client reads an event stream of
// httpserver (testdata/httpflush serve, P661) and says, event by event,
// whether each came at least 200 ms after the one before: the server
// writes them 300 ms apart and flushes each, so a stream held until the
// handler ends would bring them together.
package main

import (
	"bufio"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"
)

func main() {
	resp, err := http.Get(os.Args[1])
	if err != nil {
		fmt.Println("go:", err)
		os.Exit(1)
	}
	defer resp.Body.Close()
	fmt.Println("go:", resp.Status, resp.Header.Get("Content-Type"), resp.TransferEncoding)
	r := bufio.NewReader(resp.Body)
	var last time.Time
	n := 0
	for {
		line, err := r.ReadString('\n')
		if strings.HasPrefix(line, "data: ") {
			n++
			now := time.Now()
			if n == 1 {
				fmt.Printf("go: event %d: %s", n, line[6:])
			} else {
				fmt.Printf("go: event %d, 200 ms or more after the one before %v: %s", n,
					now.Sub(last) >= 200*time.Millisecond, line[6:])
			}
			last = now
		}
		if err != nil {
			break
		}
	}
	fmt.Println("go: the stream ended after", n, "events")
}
