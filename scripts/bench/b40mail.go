// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// P433: mail, the Go side of scripts/bench/b40mail.paslang. Four sections
// (the argument names one): message reads 200 multipart messages (quoted-
// printable text, a base64 file) 100 times each into their parts with their
// bodies decoded, as net/mail, mime, mime/multipart, mime/quotedprintable and
// encoding/base64 do it together; addr parses address lists; build makes
// messages; words encodes and decodes header words.
package main

import (
	"bytes"
	"encoding/base64"
	"fmt"
	"io"
	"mime"
	"mime/multipart"
	"mime/quotedprintable"
	"net/mail"
	"os"
	"strconv"
	"strings"
)

func message(i int) string {
	var b strings.Builder
	b.WriteString("From: Ana <ana@example.com>\r\nTo: b@example.org\r\nSubject: Message " + strconv.Itoa(i) + "\r\n")
	b.WriteString("MIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary=\"BND" + strconv.Itoa(i) + "\"\r\n\r\n")
	b.WriteString("--BND" + strconv.Itoa(i) + "\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Transfer-Encoding: quoted-printable\r\n\r\n")
	for k := 0; k < 20; k++ {
		b.WriteString("line " + strconv.Itoa(k) + " of message " + strconv.Itoa(i) + " with =C3=A9 accents and a soft break =\r\nthat goes on\r\n")
	}
	b.WriteString("\r\n--BND" + strconv.Itoa(i) + "\r\nContent-Type: application/octet-stream; name=\"f.bin\"\r\nContent-Transfer-Encoding: base64\r\n")
	b.WriteString("Content-Disposition: attachment; filename=\"f.bin\"\r\n\r\n")
	raw := make([]byte, 3000+i*7)
	for j := range raw {
		raw[j] = byte(i*7 + j*13)
	}
	enc := base64.StdEncoding.EncodeToString(raw)
	for len(enc) > 76 {
		b.WriteString(enc[:76] + "\r\n")
		enc = enc[76:]
	}
	b.WriteString(enc + "\r\n--BND" + strconv.Itoa(i) + "--\r\n")
	return b.String()
}

type stat struct{ parts, bytes int }

func first(v []string) string {
	if len(v) > 0 {
		return v[0]
	}
	return ""
}

func walk(hdr map[string][]string, body []byte, st *stat) {
	mt, params, err := mime.ParseMediaType(first(hdr["Content-Type"]))
	if err != nil && mt == "" {
		mt = "text/plain"
	}
	if strings.HasPrefix(mt, "multipart/") && params["boundary"] != "" {
		mr := multipart.NewReader(bytes.NewReader(body), params["boundary"])
		for {
			p, err := mr.NextRawPart()
			if err != nil {
				break
			}
			b, _ := io.ReadAll(p)
			walk(p.Header, b, st)
		}
		return
	}
	data := body
	switch strings.ToLower(strings.TrimSpace(first(hdr["Content-Transfer-Encoding"]))) {
	case "base64":
		clean := make([]byte, 0, len(body))
		for _, c := range body {
			if c != '\r' && c != '\n' && c != ' ' {
				clean = append(clean, c)
			}
		}
		data, _ = base64.StdEncoding.DecodeString(string(clean))
	case "quoted-printable":
		data, _ = io.ReadAll(quotedprintable.NewReader(bytes.NewReader(body)))
	}
	st.parts++
	st.bytes += len(data)
}

func secMessage() {
	msgs := make([]string, 200)
	for i := range msgs {
		msgs[i] = message(i)
	}
	st := &stat{}
	for rep := 0; rep < 100; rep++ {
		for _, m := range msgs {
			mm, err := mail.ReadMessage(strings.NewReader(m))
			if err != nil {
				continue
			}
			b, _ := io.ReadAll(mm.Body)
			walk(mm.Header, b, st)
		}
	}
	fmt.Println(st.parts, st.bytes)
}

var addrLists = []string{
	"Ana <ana@example.com>, bea@example.org",
	"\"García, José\" <jose@example.com>, =?UTF-8?Q?Mar=C3=ADa?= <maria@example.org>",
	"group: a@b.c, d@e.f;, Carlos <carlos@example.net>",
	"first.last@sub.example.co.uk",
	"Name (comment) <addr@example.com>, other@example.org (Other)",
	"\"quoted \\\"name\\\"\" <q@example.com>",
	"x@[192.168.1.1], y@example.com",
	"Ana <ana@example.com>, Bea <bea@example.org>, Carlos <carlos@example.net>, Diana <diana@example.edu>, Eva <eva@example.io>",
}

func secAddr() {
	n, bytesN := 0, 0
	for rep := 0; rep < 20000; rep++ {
		for _, s := range addrLists {
			l, err := mail.ParseAddressList(s)
			if err != nil {
				continue
			}
			for _, a := range l {
				n++
				bytesN += len(a.Name) + len(a.Address)
			}
		}
	}
	fmt.Println(n, bytesN)
}

func secBuild() {
	total := 0
	for rep := 0; rep < 2000; rep++ {
		var out bytes.Buffer
		out.WriteString("From: " + (&mail.Address{Name: "Ana Pérez", Address: "ana@example.com"}).String() + "\r\n")
		out.WriteString("To: " + (&mail.Address{Name: "Bea", Address: "bea@example.org"}).String() + "\r\n")
		out.WriteString("Subject: " + mime.QEncoding.Encode("utf-8", "Informe número "+strconv.Itoa(rep)) + "\r\n")
		out.WriteString("MIME-Version: 1.0\r\n")
		mw := multipart.NewWriter(&out)
		mw.SetBoundary("BOUNDARY")
		out.WriteString("Content-Type: multipart/mixed; boundary=BOUNDARY\r\n\r\n")
		h := map[string][]string{"Content-Type": {"text/plain; charset=utf-8"}, "Content-Transfer-Encoding": {"quoted-printable"}}
		w, _ := mw.CreatePart(h)
		qw := quotedprintable.NewWriter(w)
		qw.Write([]byte(strings.Repeat("Señor García: texto con acentos áéíóú.\r\n", 20)))
		qw.Close()
		h2 := map[string][]string{"Content-Type": {"application/octet-stream; name=f.bin"}, "Content-Transfer-Encoding": {"base64"}}
		w2, _ := mw.CreatePart(h2)
		raw := make([]byte, 3000)
		for j := range raw {
			raw[j] = byte(rep + j*13)
		}
		enc := base64.StdEncoding.EncodeToString(raw)
		for len(enc) > 76 {
			w2.Write([]byte(enc[:76] + "\r\n"))
			enc = enc[76:]
		}
		w2.Write([]byte(enc))
		mw.Close()
		if out.Len() > 0 {
			total++
		}
	}
	fmt.Println(total)
}

func secWords() {
	n, total := 0, 0
	dec := new(mime.WordDecoder)
	for rep := 0; rep < 50000; rep++ {
		w := mime.QEncoding.Encode("utf-8", "Señor García "+strconv.Itoa(rep))
		s, err := dec.DecodeHeader(w)
		if err != nil {
			continue
		}
		n++
		total += len(s)
	}
	fmt.Println(n, total)
}

func main() {
	sec := "message"
	if len(os.Args) > 1 {
		sec = os.Args[1]
	}
	switch sec {
	case "message":
		secMessage()
	case "addr":
		secAddr()
	case "build":
		secBuild()
	case "words":
		secWords()
	}
}
