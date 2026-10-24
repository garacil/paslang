// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// The oracle of testdata/httpmsg (P432): what Go's net/http makes of each
// message scripts/http_corpus.py hands it. It reads lines `ID KIND METHOD
// BASE64` on standard input (KIND req or resp; METHOD is the method of the
// request a response answers) and writes `ID VERDICT`: the verdict is
// cells joined by | (every byte outside ! to ~ but | written \xHH, - for
// nothing): err and Go's error text, or ok and the method, the target, the
// protocol, the version, the host, the URL, the status line, Close, the
// content length, whether it is chunked, the header fields (keys sorted,
// each key=value+value), the body (length:crc32 or err:text), the trailer
// fields and the bytes left over.
//
//	go run scripts/http_oracle.go < lines > verdicts
package main

import (
	"bufio"
	"bytes"
	"encoding/base64"
	"fmt"
	"hash/crc32"
	"io"
	"net/http"
	"os"
	"sort"
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

func hdr(h http.Header) string {
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

func body(r io.Reader) string {
	b, err := io.ReadAll(r)
	if err != nil {
		return "err:" + q(err.Error())
	}
	return fmt.Sprintf("%d:%08x", len(b), crc32.ChecksumIEEE(b))
}

func run(kind, method string, msg []byte) string {
	rd := bytes.NewReader(msg)
	br := bufio.NewReader(rd)
	if kind == "req" {
		req, err := http.ReadRequest(br)
		if err != nil {
			return "err|" + q(err.Error())
		}
		te := "0"
		if len(req.TransferEncoding) > 0 {
			te = "1"
		}
		u := ""
		if req.URL != nil {
			u = req.URL.String()
		}
		bd := body(req.Body)
		left, tr := fmt.Sprint(rd.Len()+br.Buffered()), hdr(req.Trailer)
		if strings.HasPrefix(bd, "err:") {
			left, tr = "?", "?"
		}
		return strings.Join([]string{"ok", q(req.Method), q(req.RequestURI), q(req.Proto), fmt.Sprint(req.ProtoMajor),
			fmt.Sprint(req.ProtoMinor), q(req.Host), q(u), "-", b2s(req.Close), fmt.Sprint(req.ContentLength), te, hdr(req.Header),
			bd, tr, left}, "|")
	}
	resp, err := http.ReadResponse(br, &http.Request{Method: method})
	if err != nil {
		return "err|" + q(err.Error())
	}
	te := "0"
	if len(resp.TransferEncoding) > 0 {
		te = "1"
	}
	bd := body(resp.Body)
	left, tr := fmt.Sprint(rd.Len()+br.Buffered()), hdr(resp.Trailer)
	if strings.HasPrefix(bd, "err:") {
		left, tr = "?", "?"
	}
	return strings.Join([]string{"ok", "-", "-", q(resp.Proto), fmt.Sprint(resp.ProtoMajor), fmt.Sprint(resp.ProtoMinor), "-", "-",
		q(resp.Status), b2s(resp.Close), fmt.Sprint(resp.ContentLength), te, hdr(resp.Header), bd, tr, left}, "|")
}

func main() {
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 1<<20), 1<<26)
	for sc.Scan() {
		f := strings.Fields(sc.Text())
		var msg []byte
		if f[3] != "-" {
			msg, _ = base64.StdEncoding.DecodeString(f[3])
		}
		fmt.Println(f[0], run(f[1], f[2], msg))
	}
}
