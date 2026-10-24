// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// The oracle of testdata/mime (P433): what Go's mime, mime/multipart,
// mime/quotedprintable and net/mail make of each case scripts/mime_corpus.py
// hands it. It reads lines `ID KIND ARG...` (each ARG base64, - for empty) on
// standard input and writes `ID VERDICT`, the verdict cells joined by | (every
// byte outside ! to ~ but | written \xHH, - for nothing).
//
//	go run scripts/mime_oracle.go < lines > verdicts
package main

import (
	"bufio"
	"bytes"
	"encoding/base64"
	"fmt"
	"hash/crc32"
	"io"
	"mime"
	"mime/multipart"
	"mime/quotedprintable"
	"net/mail"
	"os"
	"sort"
	"strings"
	"time"
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

func params(m map[string]string) string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	var parts []string
	for _, k := range keys {
		parts = append(parts, q(k)+"="+q(m[k]))
	}
	if len(parts) == 0 {
		return "-"
	}
	return strings.Join(parts, ",")
}

func hdr(h map[string][]string) string {
	keys := make([]string, 0, len(h))
	for k := range h {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	var parts []string
	for _, k := range keys {
		vs := make([]string, 0)
		for _, v := range h[k] {
			vs = append(vs, q(v))
		}
		parts = append(parts, q(k)+"="+strings.Join(vs, "+"))
	}
	if len(parts) == 0 {
		return "-"
	}
	return strings.Join(parts, ",")
}

func addrs(l []*mail.Address) string {
	var parts []string
	for _, a := range l {
		parts = append(parts, q(a.Name)+"<"+q(a.Address)+">")
	}
	if len(parts) == 0 {
		return "-"
	}
	return strings.Join(parts, ",")
}

func arg(f []string, i int) string {
	if i >= len(f) || f[i] == "-" {
		return ""
	}
	b, _ := base64.StdEncoding.DecodeString(f[i])
	return string(b)
}

func run(f []string) string {
	kind := f[1]
	switch kind {
	case "qpdec":
		b, err := io.ReadAll(quotedprintable.NewReader(strings.NewReader(arg(f, 2))))
		if err != nil {
			return "err|" + q(string(b)) + "|" + q(err.Error())
		}
		return "ok|" + q(string(b))
	case "qpenc":
		var out bytes.Buffer
		w := quotedprintable.NewWriter(&out)
		w.Binary = arg(f, 3) == "1"
		w.Write([]byte(arg(f, 2)))
		w.Close()
		return "ok|" + q(out.String())
	case "wdec":
		s, err := new(mime.WordDecoder).Decode(arg(f, 2))
		if err != nil {
			return "err"
		}
		return "ok|" + q(s)
	case "hdec":
		s, err := new(mime.WordDecoder).DecodeHeader(arg(f, 2))
		if err != nil {
			return "err"
		}
		return "ok|" + q(s)
	case "wenc":
		e := mime.QEncoding
		if arg(f, 4) == "b" {
			e = mime.BEncoding
		}
		return "ok|" + q(e.Encode(arg(f, 2), arg(f, 3)))
	case "mt":
		mt, p, err := mime.ParseMediaType(arg(f, 2))
		if err != nil {
			return "err|" + q(mt) + "|" + q(err.Error())
		}
		return "ok|" + q(mt) + "|" + params(p)
	case "fmt":
		p := map[string]string{}
		kv := strings.Split(arg(f, 3), "\x00")
		for i := 0; i+1 < len(kv); i += 2 {
			p[kv[i]] = kv[i+1]
		}
		return "ok|" + q(mime.FormatMediaType(arg(f, 2), p))
	case "mp":
		r := multipart.NewReader(strings.NewReader(arg(f, 2)), arg(f, 3))
		raw := arg(f, 4) == "1"
		var out []string
		for {
			var p *multipart.Part
			var err error
			if raw {
				p, err = r.NextRawPart()
			} else {
				p, err = r.NextPart()
			}
			if err != nil {
				if err == io.EOF {
					out = append(out, "END")
				} else {
					out = append(out, "ERR", q(err.Error()))
				}
				break
			}
			b, berr := io.ReadAll(p)
			e := "-"
			if berr != nil {
				e = q(berr.Error())
			}
			out = append(out, "P", hdr(p.Header), fmt.Sprintf("%d:%08x", len(b), crc32.ChecksumIEEE(b)), e)
		}
		return strings.Join(out, "|")
	case "addr":
		a, err := mail.ParseAddress(arg(f, 2))
		if err != nil {
			return "err|" + q(err.Error())
		}
		return "ok|" + addrs([]*mail.Address{a}) + "|" + q(a.String())
	case "addrs":
		l, err := mail.ParseAddressList(arg(f, 2))
		if err != nil {
			return "err|" + q(err.Error())
		}
		var strs []string
		for _, a := range l {
			strs = append(strs, q(a.String()))
		}
		return "ok|" + addrs(l) + "|" + strings.Join(strs, ",")
	case "date":
		t, err := mail.ParseDate(arg(f, 2))
		if err != nil {
			return "err|" + q(err.Error())
		}
		_, off := t.Zone()
		return fmt.Sprintf("ok|%d|%d", t.Unix(), off)
	case "msg":
		m, err := mail.ReadMessage(strings.NewReader(arg(f, 2)))
		if err != nil {
			return "err|" + q(err.Error())
		}
		b, _ := io.ReadAll(m.Body)
		return "ok|" + hdr(m.Header) + "|" + fmt.Sprintf("%d:%08x", len(b), crc32.ChecksumIEEE(b))
	}
	_ = time.Now
	return "?"
}

func main() {
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 1<<20), 1<<26)
	for sc.Scan() {
		f := strings.Fields(sc.Text())
		fmt.Println(f[0], run(f))
	}
}
