// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// P426: XML read token by token, the Go side of scripts/bench/b38xml.paslang:
// the same worksheet read five times with encoding/xml's Decoder.Token, the
// start tags, end tags, bytes of text, attributes and bytes of their values
// counted (xmlns declarations are not counted, as the paslang side leaves
// them out).
package main

import (
	"bytes"
	"encoding/xml"
	"fmt"
	"strconv"
)

func sheet() []byte {
	var b bytes.Buffer
	b.WriteString("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n" +
		"<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheetData>")
	for r := 1; r <= 20000; r++ {
		b.WriteString("<row r=\"" + strconv.Itoa(r) + "\" spans=\"1:8\">")
		for c := 0; c < 8; c++ {
			k := r*8 + c
			ref := string(rune(65+c)) + strconv.Itoa(r)
			switch c % 3 {
			case 0:
				b.WriteString("<c r=\"" + ref + "\" t=\"inlineStr\"><is><t>valor " + strconv.Itoa(k) + " &amp; x</t></is></c>")
			case 1:
				b.WriteString("<c r=\"" + ref + "\" s=\"1\"><v>" + strconv.Itoa(k) + ".5</v></c>")
			default:
				b.WriteString("<c r=\"" + ref + "\"/>")
			}
		}
		b.WriteString("</row>")
	}
	b.WriteString("</sheetData></worksheet>")
	return b.Bytes()
}

func main() {
	doc := sheet()
	starts, ends, text, attrs, vals := 0, 0, 0, 0, 0
	for rep := 0; rep < 5; rep++ {
		d := xml.NewDecoder(bytes.NewReader(doc))
		for {
			t, err := d.Token()
			if err != nil {
				break
			}
			switch v := t.(type) {
			case xml.StartElement:
				starts++
				for _, a := range v.Attr {
					if a.Name.Space == "xmlns" || (a.Name.Space == "" && a.Name.Local == "xmlns") {
						continue
					}
					attrs++
					vals += len(a.Value)
				}
			case xml.EndElement:
				ends++
			case xml.CharData:
				text += len(v)
			}
		}
	}
	fmt.Println(starts, ends, text, attrs, vals)
}
