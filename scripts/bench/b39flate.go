// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// P427: DEFLATE against compress/flate, the Go side of
// scripts/bench/b39flate.paslang: the same worksheet compressed at level 6
// four times and read back once (deflate), or compressed at level 1 once
// and read back twenty times (inflate).
package main

import (
	"bytes"
	"compress/flate"
	"fmt"
	"io"
	"os"
	"strconv"
)

func sheet() []byte {
	var b bytes.Buffer
	b.WriteString("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n" +
		"<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheetData>")
	for r := 1; r <= 30000; r++ {
		b.WriteString("<row r=\"" + strconv.Itoa(r) + "\" spans=\"1:8\">")
		for c := 0; c < 8; c++ {
			k := r*8 + c
			ref := string(rune(65+c)) + strconv.Itoa(r)
			switch c % 3 {
			case 0:
				b.WriteString("<c r=\"" + ref + "\" t=\"inlineStr\"><is><t>item " + strconv.Itoa(k%977) + " &amp; co</t></is></c>")
			case 1:
				b.WriteString("<c r=\"" + ref + "\" s=\"2\"><v>" + strconv.Itoa(k*7%100003) + "." + strconv.Itoa(k%100) + "</v></c>")
			default:
				b.WriteString("<c r=\"" + ref + "\"/>")
			}
		}
		b.WriteString("</row>")
	}
	b.WriteString("</sheetData></worksheet>")
	return b.Bytes()
}

func compress(text []byte, level int) []byte {
	var out bytes.Buffer
	w, _ := flate.NewWriter(&out, level)
	w.Write(text)
	w.Close()
	return out.Bytes()
}

func inflate(comp []byte) []byte {
	r := flate.NewReader(bytes.NewReader(comp))
	b, err := io.ReadAll(r)
	if err != nil {
		panic(err)
	}
	return b
}

func sum(b []byte) int {
	s := 0
	for _, c := range b {
		s = (s*31 + int(c)) & 0xFFFFFFFF
	}
	return s
}

func main() {
	text := sheet()
	section := ""
	if len(os.Args) > 1 {
		section = os.Args[1]
	}
	if section == "build" {
		fmt.Println(len(text))
		return
	}
	if section == "deflate" {
		var comp []byte
		for i := 0; i < 4; i++ {
			comp = compress(text, 6)
		}
		back := inflate(comp)
		fmt.Println(len(text), sum(back))
		return
	}
	comp := compress(text, 1)
	total := 0
	var back []byte
	for i := 0; i < 20; i++ {
		back = inflate(comp)
		total += len(back)
	}
	fmt.Println(len(text), sum(back), total)
}
