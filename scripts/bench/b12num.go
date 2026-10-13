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

// P223: numbers as text, the twin of b12num.paslang (its comment says
// what each section does).
package main

import (
	"fmt"
	"os"
	"strconv"
)

const N = 1000000

func itoa() {
	total, sum := 0, 0
	for i := 1; i <= 10000000; i++ {
		s := strconv.Itoa(i*7919 - 40000000000)
		total += len(s)
		if i%1000 == 0 {
			for j := 0; j < len(s); j++ {
				sum += int(s[j])
			}
		}
	}
	fmt.Println(total, sum)
}

func ftoa() {
	total, sum := 0, 0
	for i := 1; i <= 3000000; i++ {
		s := strconv.FormatFloat(float64(i)/7, 'f', -1, 64)
		total += len(s)
		if i%1000 == 0 {
			for j := 0; j < len(s); j++ {
				sum += int(s[j])
			}
		}
	}
	fmt.Println(total, sum)
}

func fmtf() {
	total, sum := 0, 0
	for i := 1; i <= 2000000; i++ {
		s := fmt.Sprintf("%d:%s:%.3f", i, "ab", float64(i)/7)
		total += len(s)
		if i%1000 == 0 {
			for j := 0; j < len(s); j++ {
				sum += int(s[j])
			}
		}
	}
	fmt.Println(total, sum)
}

func atoi() {
	strs := make([]string, N)
	for k := 0; k < N; k++ {
		strs[k] = strconv.Itoa(k*7919 - 40000000000)
	}
	t := 0
	for r := 1; r <= 20; r++ {
		for k := 0; k < N; k++ {
			v, _ := strconv.Atoi(strs[k])
			t += v
		}
	}
	fmt.Println(t)
}

func atof() {
	strs := make([]string, N)
	for k := 0; k < N; k++ {
		strs[k] = strconv.FormatFloat(float64(k)/7, 'f', -1, 64)
	}
	t := 0.0
	for r := 1; r <= 2; r++ {
		for k := 0; k < N; k++ {
			v, _ := strconv.ParseFloat(strs[k], 64)
			t += v
		}
	}
	fmt.Println(int64(t))
}

func main() {
	arg := ""
	if len(os.Args) > 1 {
		arg = os.Args[1]
	}
	switch arg {
	case "itoa":
		itoa()
	case "ftoa":
		ftoa()
	case "fmt":
		fmtf()
	case "atoi":
		atoi()
	case "atof":
		atof()
	default:
		fmt.Println("b12num: itoa, ftoa, fmt, atoi or atof")
		os.Exit(2)
	}
}
