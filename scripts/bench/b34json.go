// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
//
// paslang is free software: you can redistribute it and/or modify it
// under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// paslang is distributed in the hope that it will be useful, but
// WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
// General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with paslang.  If not, see <https://www.gnu.org/licenses/>.


// P203: JSON, the twin of b34json.paslang (its comment says what each
// section does).
package main

import (
	jsonv1 "encoding/json"
	"encoding/json/jsontext"
	"encoding/json/v2"
	"fmt"
	"os"
)

var files = []string{"canada_geometry", "citm_catalog", "golang_source",
	"string_escaped", "string_unicode", "synthea_fhir", "twitter_status"}

const rounds = 10

// count is the values of a parsed any, its containers' children
// included, walked with an explicit stack.
func count(v any) int {
	n := 0
	stack := []any{v}
	for len(stack) > 0 {
		x := stack[len(stack)-1]
		stack = stack[:len(stack)-1]
		n++
		switch y := x.(type) {
		case []any:
			stack = append(stack, y...)
		case map[string]any:
			for _, z := range y {
				stack = append(stack, z)
			}
		}
	}
	return n
}

func main() {
	sec := os.Args[1]
	texts := make([][]byte, len(files))
	for i, f := range files {
		b, err := os.ReadFile("build/bench/json/" + f + ".json")
		if err != nil {
			fmt.Println("no build/bench/json/" + f + ".json: run.py writes it")
			os.Exit(1)
		}
		texts[i] = b
	}
	total := 0
	switch sec {
	case "parse", "parse1":
		for r := 0; r < rounds; r++ {
			for _, b := range texts {
				var v any
				var err error
				if sec == "parse" {
					err = json.Unmarshal(b, &v)
				} else {
					err = jsonv1.Unmarshal(b, &v)
				}
				if err != nil {
					panic(err)
				}
				total += count(v)
			}
		}
	case "canonical":
		for r := 0; r < rounds; r++ {
			for _, b := range texts {
				v := jsontext.Value(append([]byte(nil), b...))
				if err := v.Canonicalize(); err != nil {
					panic(err)
				}
				total += len(v)
			}
		}
	default:
		docs := make([]any, len(texts))
		for i, b := range texts {
			if err := json.Unmarshal(b, &docs[i]); err != nil {
				panic(err)
			}
		}
		for r := 0; r < rounds; r++ {
			for _, d := range docs {
				var t []byte
				var err error
				switch sec {
				case "compact":
					t, err = json.Marshal(d)
				case "compact1":
					t, err = jsonv1.Marshal(d)
				case "pretty":
					t, err = json.Marshal(d, jsontext.WithIndent("  "))
				case "pretty1":
					t, err = jsonv1.MarshalIndent(d, "", "  ")
				}
				if err != nil {
					panic(err)
				}
				if len(t) > 0 {
					total++
				}
			}
		}
	}
	fmt.Println(total)
}
