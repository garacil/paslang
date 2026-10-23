// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// The oracle of testdata/codec (P435): what Go's encoding/base64, net/url,
// encoding/csv and strings give for the inputs testdata/codec.paslang
// feeds pascodec, as the lines that program prints. The folding is
// golang.org/x/text/unicode/norm's NFD without the marks plus the letters
// that do not decompose.
//
//	go run scripts/codec_oracle.go > testdata/codec.out
package main

import (
	"bytes"
	"encoding/base64"
	"encoding/csv"
	"encoding/hex"
	"fmt"
	"net/url"
	"strings"
	"unicode"

	"golang.org/x/text/unicode/norm"
)

var gs uint64

func gnext() uint64 {
	gs += 0x9e3779b97f4a7c15
	z := gs
	z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9
	z = (z ^ (z >> 27)) * 0x94d049bb133111eb
	return z ^ (z >> 31)
}

type fnv struct{ h uint64 }

func newFnv() *fnv { return &fnv{0xcbf29ce484222325} }
func (f *fnv) add(s string) {
	for i := 0; i < len(s); i++ {
		f.h ^= uint64(s[i])
		f.h *= 0x100000001b3
	}
	f.h ^= 0xff
	f.h *= 0x100000001b3
}
func (f *fnv) hex() string { return fmt.Sprintf("%016x", f.h) }

func hx(s string) string { return hex.EncodeToString([]byte(s)) }

func main() {
	// base64
	encs := []*base64.Encoding{base64.StdEncoding, base64.RawStdEncoding, base64.URLEncoding, base64.RawURLEncoding}
	for v, e := range encs {
		gs = 1
		f := newFnv()
		ok := 0
		for n := 0; n <= 300; n++ {
			b := make([]byte, n)
			for i := range b {
				b[i] = byte(gnext() >> 24)
			}
			s := e.EncodeToString(b)
			f.add(s)
			if d, err := e.DecodeString(s); err == nil && bytes.Equal(d, b) {
				ok++
			}
		}
		fmt.Printf("b64 %d %s roundtrip %d\n", v, f.hex(), ok)
	}
	bad := []string{"", "Zg==", "Zg=", "Zg", "Zm8=", "Zm8", "Zm9v", "Zm9vYg==", "Zm9vYg", "Zm9v\r\nYmFy", "Zm9v YmFy",
		"Zm=v", "Z===", "====", "Zg==Zg==", "Zh==", "Zm9vYmE=", "Zm9vYmE", "Zm9vYmFy", "-_-_", "+/+/", "Zg==\n",
		"Zg=\n=", "Zg==x", "A", "AA", "AAA", "AAAA", "AAAAA", "Zm9vYg=", "Zm9vYg===", "Z\ng==", "=Zg=", "Zg\r\n==\r\n"}
	for v, e := range encs {
		for i, s := range bad {
			d, err := e.DecodeString(s)
			if err != nil {
				fmt.Printf("b64d %d %d err\n", v, i)
			} else {
				fmt.Printf("b64d %d %d ok %s\n", v, i, hx(string(d)))
			}
		}
	}

	// url
	gs = 2
	fq, fp := newFnv(), newFnv()
	for c := 0; c < 256; c++ {
		fq.add(url.QueryEscape(string([]byte{byte(c)})))
		fp.add(url.PathEscape(string([]byte{byte(c)})))
	}
	fmt.Printf("url bytes %s %s\n", fq.hex(), fp.hex())
	fq, fp = newFnv(), newFnv()
	rt := 0
	for k := 0; k < 3000; k++ {
		n := int(gnext()>>40) % 31
		b := make([]byte, n)
		for i := range b {
			b[i] = byte(gnext() >> 24)
		}
		s := string(b)
		q, p := url.QueryEscape(s), url.PathEscape(s)
		fq.add(q)
		fp.add(p)
		a, e1 := url.QueryUnescape(q)
		c, e2 := url.PathUnescape(p)
		if e1 == nil && e2 == nil && a == s && c == s {
			rt++
		}
	}
	fmt.Printf("url random %s %s roundtrip %d\n", fq.hex(), fp.hex(), rt)
	un := []string{"", "abc", "a%20b", "a+b", "%", "%4", "%zz", "%41%42", "a%2", "%C3%A9", "%00", "100%", "%%41", "%4g", "+%2B+", "%2b"}
	for i, s := range un {
		a, e1 := url.QueryUnescape(s)
		c, e2 := url.PathUnescape(s)
		qs, ps := "err", "err"
		if e1 == nil {
			qs = "ok " + hx(a)
		}
		if e2 == nil {
			ps = "ok " + hx(c)
		}
		fmt.Printf("urlu %d q %s p %s\n", i, qs, ps)
	}

	// csv
	cases := []string{"", "a,b,c\n", "a,b,c", "a,b,c\r\n", "\"a\",\"b\"\n", "\"a\"\"b\",c\n", "a,\"b\nc\",d\ne,f,g\n", "a,b\n\nc,d\n",
		"a,\"b\r\nc\",d\r\n", "\"abc\n", "\"abc", "a\"b,c\n", "\"a\"b,c\n", "a,b\nc\n", "# c\na,b\n", "a, b ,c\n", " \"a\",b\n",
		"\xEF\xBB\xBFa,b\n", "a,b\rc,d\n", "a,b\r", ",,\n", "\"\",\"\"\n", "a;b;c\n", "\"a\" ,b\n", "\"a\n\"\"\nb\"\n", "x\n\"", "\"\n",
		"a,\"b\"\n", "a,\"b\"c\n", "a,b\n\"c\nd", "  \n a\n"}
	type opt struct {
		name              string
		comma, comment    rune
		lazy, trim        bool
		fields            int
	}
	opts := []opt{{"def", ',', 0, false, false, 0}, {"lazy", ',', 0, true, false, 0}, {"trim", ',', 0, false, true, 0},
		{"semi", ';', 0, false, false, -1}, {"hash", ',', '#', false, false, -1}, {"two", ',', 0, false, false, 2}}
	run := func(text string, o opt) string {
		text = strings.TrimPrefix(text, "\xEF\xBB\xBF")
		r := csv.NewReader(strings.NewReader(text))
		r.Comma, r.Comment, r.LazyQuotes, r.TrimLeadingSpace, r.FieldsPerRecord = o.comma, o.comment, o.lazy, o.trim, o.fields
		var sb strings.Builder
		for {
			rec, err := r.Read()
			if err != nil {
				if pe, ok := err.(*csv.ParseError); ok {
					kind := 0
					switch pe.Err {
					case csv.ErrBareQuote:
						kind = 1
					case csv.ErrQuote:
						kind = 2
					case csv.ErrFieldCount:
						kind = 3
					}
					fmt.Fprintf(&sb, "ERR %d %d %d %d", kind, pe.StartLine, pe.Line, pe.Column)
					if kind == 3 {
						// the fields were still returned
						for _, f := range rec {
							fmt.Fprintf(&sb, " %s", hx(f))
						}
					}
				}
				break
			}
			for i, f := range rec {
				if i > 0 {
					sb.WriteString(" ")
				}
				sb.WriteString(hx(f))
			}
			sb.WriteString(" | ")
		}
		return sb.String()
	}
	for i, c := range cases {
		for _, o := range opts {
			fmt.Printf("csv %d %s %s\n", i, o.name, run(c, o))
		}
	}
	gs = 3
	alpha := []string{"a", "b", "\"", "\"", ",", ",", "\n", "\n", "\r", " ", "#", ";", "xy"}
	for _, o := range opts {
		f := newFnv()
		for k := 0; k < 1500; k++ {
			n := int(gnext()>>40) % 14
			var sb strings.Builder
			for i := 0; i < n; i++ {
				sb.WriteString(alpha[int(gnext()>>40)%len(alpha)])
			}
			f.add(run(sb.String(), o))
		}
		fmt.Printf("csv random %s %s\n", o.name, f.hex())
	}
	// the writer
	gs = 4
	f := newFnv()
	walpha := []string{"a", "b", "\"", ",", "\n", "\r", " ", "\\.", "é", " ", ";", "x", ""}
	for k := 0; k < 2000; k++ {
		nf := 1 + int(gnext()>>40)%4
		rec := make([]string, nf)
		for j := range rec {
			n := int(gnext()>>40) % 4
			var sb strings.Builder
			for i := 0; i < n; i++ {
				sb.WriteString(walpha[int(gnext()>>40)%len(walpha)])
			}
			rec[j] = sb.String()
		}
		var buf bytes.Buffer
		w := csv.NewWriter(&buf)
		w.Write(rec)
		w.Flush()
		var buf2 bytes.Buffer
		w2 := csv.NewWriter(&buf2)
		w2.UseCRLF = true
		w2.Comma = ';'
		w2.Write(rec)
		w2.Flush()
		f.add(buf.String())
		f.add(buf2.String())
	}
	fmt.Printf("csv writer %s\n", f.hex())

	// letters
	gs = 5
	special := map[rune]string{'ß': "ss", 'ẞ': "SS", 'Æ': "AE", 'æ': "ae", 'Œ': "OE", 'œ': "oe", 'Ø': "O", 'ø': "o", 'Đ': "D", 'đ': "d",
		'Ð': "D", 'ð': "d", 'Þ': "TH", 'þ': "th", 'ı': "i", 'Ł': "L", 'ł': "l", 'Ŀ': "L", 'ŀ': "l", 'Ħ': "H", 'ħ': "h", 'Ŧ': "T", 'ŧ': "t",
		'Ĳ': "IJ", 'ĳ': "ij", 'ŉ': "'n", 'ĸ': "k", 'Ŋ': "NG", 'ŋ': "ng", 'ſ': "s"}
	fold := func(s string) string {
		var sb strings.Builder
		for _, r := range s {
			if r >= 0x80 && r < 0x180 {
				if t, ok := special[r]; ok {
					sb.WriteString(t)
					continue
				}
				for _, d := range norm.NFD.String(string(r)) {
					if !unicode.Is(unicode.Mn, d) {
						sb.WriteRune(d)
					}
				}
				continue
			}
			sb.WriteRune(r)
		}
		return sb.String()
	}
	fu, fl, ff := newFnv(), newFnv(), newFnv()
	for r := rune(0); r < 0x180; r++ {
		s := string(r)
		fu.add(strings.ToUpper(s))
		fl.add(strings.ToLower(s))
		ff.add(fold(s))
	}
	fmt.Printf("letters all %s %s %s\n", fu.hex(), fl.hex(), ff.hex())
	pool := []rune{'a', 'Z', ' ', '0', 'é', 'Ñ', 'ü', 'ß', 'ç', 'Á', 'ÿ', 'Ÿ', 'Œ', 'ł', 'İ', 'ı', 'ſ', '€', '中', '\n'}
	fu, fl, ff = newFnv(), newFnv(), newFnv()
	for k := 0; k < 2000; k++ {
		n := int(gnext()>>40) % 12
		var sb strings.Builder
		for i := 0; i < n; i++ {
			sb.WriteRune(pool[int(gnext()>>40)%len(pool)])
		}
		s := sb.String()
		fu.add(strings.ToUpper(s))
		fl.add(strings.ToLower(s))
		ff.add(fold(s))
	}
	fmt.Printf("letters random %s %s %s\n", fu.hex(), fl.hex(), ff.hex())
	fmt.Printf("spanish %s %s %s\n", hx(strings.ToUpper("Ñandú, camión, pingüino, ¿qué?")), hx(strings.ToLower("ÑANDÚ, CAMIÓN, PINGÜINO")), hx(fold("Ñandú, camión, pingüino, ¿qué? Ça va, Œuvre, Łódź")))
}
