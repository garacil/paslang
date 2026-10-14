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

// P206: typed JSON read, the twin of b36unbind.paslang: the text of
// 20000 items of b35bind's record (an integer, a string, an array of
// strings, a real, a Boolean, an array of records and a map) read 20
// times into a new slice (unmarshal: v2; unmarshal1: v1). It prints a
// sum of what was read.
package main

import (
	jsonv1 "encoding/json"
	"encoding/json/v2"
	"fmt"
	"math"
	"os"
	"strconv"
)

type Point struct {
	X float64 `json:"x"`
	Y float64 `json:"y"`
}

type Item struct {
	ID     int            `json:"id"`
	Name   string         `json:"name"`
	Tags   []string       `json:"tags"`
	Price  float64        `json:"price"`
	Active bool           `json:"active"`
	Pts    []Point        `json:"pts"`
	Attrs  map[string]int `json:"attrs"`
}

const n = 20000
const rounds = 20

func main() {
	sec := os.Args[1]
	items := make([]Item, n)
	for i := range items {
		it := &items[i]
		it.ID = i
		it.Name = "item " + strconv.Itoa(i)
		it.Tags = []string{"t" + strconv.Itoa(i%7), "u" + strconv.Itoa(i%11), "v"}
		it.Price = float64(i)*0.25 + 0.1
		it.Active = i%3 == 0
		it.Pts = make([]Point, 4)
		for k := range it.Pts {
			it.Pts[k] = Point{float64(i + k), float64(i) / 8}
		}
		it.Attrs = map[string]int{"c": i, "a": i + 1, "b": i + 2}
	}
	t, err := json.Marshal(items, json.Deterministic(true))
	if err != nil {
		panic(err)
	}
	total := 0
	for r := 0; r < rounds; r++ {
		var got []Item
		switch sec {
		case "unmarshal":
			err = json.Unmarshal(t, &got)
		case "unmarshal1":
			err = jsonv1.Unmarshal(t, &got)
		}
		if err != nil {
			panic(err)
		}
		for i := range got {
			a := 0
			if got[i].Active {
				a = 1
			}
			total += got[i].ID + len(got[i].Name) + len(got[i].Tags[1]) +
				int(math.RoundToEven(got[i].Pts[3].X)) + got[i].Attrs["b"] + a
		}
	}
	fmt.Println(total)
}
