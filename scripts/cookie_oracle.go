// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.
//
// The oracle of testdata/cookiejar (P564): the script testdata/cookiejar.txt
// run through Go's net/http/cookiejar (no public suffix list, as httpclient's
// jar) and http.ParseSetCookie; every get prints the Cookie header Go would
// send, in Go's order, as testdata/cookiejar prints its own. Lines after !
// are the standard's alone (the clock, the limits) and are skipped.
//
//   go run scripts/cookie_oracle.go testdata/cookiejar.txt
package main

import (
	"bufio"
	"fmt"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"os"
	"strings"
)

func main() {
	f, err := os.Open(os.Args[1])
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	jar, _ := cookiejar.New(nil)
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Text()
		if line == "" || strings.HasPrefix(line, "#") || strings.HasPrefix(line, "! ") {
			continue
		}
		cmd, arg, _ := strings.Cut(line, " ")
		switch cmd {
		case "set":
			rawurl, hdr, _ := strings.Cut(arg, " ")
			u, err := url.Parse(rawurl)
			if err != nil {
				continue
			}
			c, err := http.ParseSetCookie(hdr)
			if err == nil {
				jar.SetCookies(u, []*http.Cookie{c})
			}
		case "get":
			u, err := url.Parse(arg)
			if err != nil {
				continue
			}
			req, _ := http.NewRequest("GET", arg, nil)
			for _, c := range jar.Cookies(u) {
				req.AddCookie(c)
			}
			fmt.Printf("get %s -> [%s]\n", arg, req.Header.Get("Cookie"))
		case "clear":
			jar, _ = cookiejar.New(nil)
			fmt.Println("clear")
		}
	}
}
