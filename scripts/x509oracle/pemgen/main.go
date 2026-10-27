// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// pemgen writes PEM decoding cases: texts made from valid blocks and
// then mutated (math/rand with a fixed seed), each with what Go's
// encoding/pem Decode gives, call after call: the type, the headers
// (sorted by key), the bytes and the length of the rest.
package main

import (
	"encoding/hex"
	"encoding/pem"
	"fmt"
	"math/rand/v2"
	"sort"
	"strings"
)

func decodeAll(data []byte) string {
	var parts []string
	for i := 0; i < 50; i++ {
		b, rest := pem.Decode(data)
		if b == nil {
			parts = append(parts, fmt.Sprintf("none:%d", len(rest)))
			break
		}
		var keys []string
		for k := range b.Headers {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		var hs []string
		for _, k := range keys {
			hs = append(hs, hex.EncodeToString([]byte(k))+"="+hex.EncodeToString([]byte(b.Headers[k])))
		}
		parts = append(parts, fmt.Sprintf("B:%s:%s:%s:%d", hex.EncodeToString([]byte(b.Type)), strings.Join(hs, ";"), hex.EncodeToString(b.Bytes), len(rest)))
		data = rest
	}
	return strings.Join(parts, " ")
}

func main() {
	r := rand.New(rand.NewPCG(430, 1))
	rb := func(n int) []byte {
		b := make([]byte, n)
		for i := range b {
			b[i] = byte(r.IntN(256))
		}
		return b
	}
	block := func() string {
		typ := []string{"CERTIFICATE", "RSA PRIVATE KEY", "X", "A B", "CERTIFICATE REQUEST"}[r.IntN(5)]
		var h map[string]string
		if r.IntN(4) == 0 {
			h = map[string]string{"Proc-Type": "4,ENCRYPTED", "DEK-Info": "AES-128-CBC,00"}
		}
		return string(pem.EncodeToMemory(&pem.Block{Type: typ, Headers: h, Bytes: rb(r.IntN(120))}))
	}
	alphabet := []string{"-", "\n", "\r", " ", "\t", ":", "=", "A", "B", "E", "N", "D", "-----", "-----END ", "-----BEGIN ", "\r\n", "x", "+", "/"}
	n := 0
	emit := func(text string) {
		n++
		fmt.Printf("pem %d\ntext %s\nwant %s\nend\n", n, hex.EncodeToString([]byte(text)), decodeAll([]byte(text)))
	}
	// fixed edge cases
	for _, t := range []string{
		"", "-----BEGIN X-----\n-----END X-----\n", "-----BEGIN X-----\n-----END X-----", "-----BEGIN X-----\n-----END Y-----\n",
		"junk\n-----BEGIN X-----\nQUJD\n-----END X-----\ntrailer", "-----BEGIN X-----\r\nQUJD\r\n-----END X-----\r\n",
		"-----BEGIN X-----\nK: V\n\nQUJD\n-----END X-----\n", "-----BEGIN X-----\nK: V\n-----END X-----\n",
		"-----BEGIN X-----\nQU JD\n\tQUJD\n-----END X-----\n", "-----BEGIN X-----\nQUJ\n-----END X-----\n",
		"-----BEGIN X-----   \nQUJD\n-----END X-----   \n", "-----BEGIN X-----\nQUJD\n-----END X----- junk\n",
		"x-----BEGIN X-----\nQUJD\n-----END X-----\n", "-----BEGIN X-----\nQUJD\n-----END X-----\n-----BEGIN Y-----\nREVG\n-----END Y-----\n",
		"-----BEGIN X-----\n-----BEGIN X-----\nQUJD\n-----END X-----\n", "-----BEGIN -----\nQUJD\n-----END -----\n",
		"-----BEGIN X-----\nA: 1\nA: 2\nB:\n\nQUJD\n-----END X-----\n", "-----BEGIN X-----\n  Key  :  Va: lue  \n\nQUJD\n-----END X-----\n",
		"-----BEGIN X-----\nQUJD====\n-----END X-----\n", "-----BEGIN X-----\nQQ==\n-----END X-----\n",
	} {
		emit(t)
	}
	for i := 0; i < 2500; i++ {
		var sb strings.Builder
		for j := r.IntN(3); j >= 0; j-- {
			if r.IntN(3) == 0 {
				sb.WriteString("junk text\n")
			}
			sb.WriteString(block())
		}
		t := []byte(sb.String())
		for m := r.IntN(4); m > 0; m-- {
			p := r.IntN(len(t) + 1)
			switch r.IntN(3) {
			case 0:
				t = append(t[:p], append([]byte(alphabet[r.IntN(len(alphabet))]), t[p:]...)...)
			case 1:
				if p < len(t) {
					k := 1 + r.IntN(4)
					if p+k > len(t) {
						k = len(t) - p
					}
					t = append(t[:p], t[p+k:]...)
				}
			case 2:
				if p < len(t) {
					t[p] = alphabet[r.IntN(len(alphabet))][0]
				}
			}
		}
		emit(string(t))
	}
}
