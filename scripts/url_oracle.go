// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// The oracle of testdata/url (P432): what Go's net/url makes of each
// string scripts/url_corpus.py hands it. It reads lines `ID BASE64` on
// standard input and writes `ID VERDICT`, the verdict being cells joined
// by | (every byte outside ! to ~ but | written \xHH): the result of Parse
// (ok and the parts of the URL, String, EscapedPath, RequestURI, Hostname,
// Port, or the error), of ParseRequestURI, of resolving it against three
// bases, and of ParseQuery on its RawQuery (the values Encode gives and
// the error).
//
//	go run scripts/url_oracle.go < lines > verdicts
package main

import (
	"bufio"
	"encoding/base64"
	"fmt"
	"net/url"
	"os"
	"strings"
)

func q(s string) string {
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c > 0x20 && c < 0x7f && c != '|' {
			b.WriteByte(c)
		} else {
			fmt.Fprintf(&b, "\\x%02x", c)
		}
	}
	if b.Len() == 0 {
		return "-"
	}
	return b.String()
}

func b2s(b bool) string {
	if b {
		return "1"
	}
	return "0"
}

func dump(u *url.URL, err error) string {
	if err != nil {
		return "err|" + q(err.Error())
	}
	user, pass := "", ""
	hasPass := false
	if u.User != nil {
		user = u.User.Username()
		pass, hasPass = u.User.Password()
	}
	cells := []string{"ok", q(u.Scheme), q(u.Opaque), b2s(u.User != nil), q(user), b2s(hasPass), q(pass), q(u.Host), q(u.Path),
		q(u.RawPath), q(u.RawQuery), q(u.Fragment), q(u.RawFragment), b2s(u.ForceQuery), b2s(u.OmitHost), q(u.String()),
		q(u.EscapedPath()), q(u.RequestURI()), q(u.Hostname()), q(u.Port())}
	return strings.Join(cells, "|")
}

func main() {
	bases := []string{"http://a/b/c/d;p?q", "http://user:pw@h:81/x/y/", "mailto:x@y.z"}
	var bu []*url.URL
	for _, b := range bases {
		u, _ := url.Parse(b)
		bu = append(bu, u)
	}
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 1<<20), 1<<26)
	for sc.Scan() {
		f := strings.Fields(sc.Text())
		raw := ""
		if f[1] != "-" {
			b, _ := base64.StdEncoding.DecodeString(f[1])
			raw = string(b)
		}
		u, err := url.Parse(raw)
		cells := []string{dump(u, err)}
		u2, err2 := url.ParseRequestURI(raw)
		cells = append(cells, dump(u2, err2))
		for _, b := range bu {
			if err != nil {
				cells = append(cells, "-")
				continue
			}
			cells = append(cells, q(b.ResolveReference(u).String()))
		}
		if err != nil {
			cells = append(cells, "-")
		} else {
			v, qerr := url.ParseQuery(u.RawQuery)
			e := ""
			if qerr != nil {
				e = qerr.Error()
			}
			cells = append(cells, q(v.Encode()), q(e))
		}
		fmt.Println(f[0], strings.Join(cells, "|"))
	}
}
