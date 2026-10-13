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

// P223: the real functions, the twin of b24math.paslang (its comment
// says what each section does).
package main

import (
	"fmt"
	"math"
	"os"
)

func main() {
	t := 0.0
	arg := ""
	if len(os.Args) > 1 {
		arg = os.Args[1]
	}
	switch arg {
	case "sin":
		for i := 1; i <= 10000000; i++ {
			t += math.Sin(float64(i) / 997)
		}
	case "exp":
		for i := 1; i <= 10000000; i++ {
			x := float64(i%2000)/1000 - 1
			t += math.Exp(x)
		}
	case "ln":
		for i := 1; i <= 10000000; i++ {
			t += math.Log(float64(i) / 997)
		}
	case "sqrt":
		for i := 1; i <= 10000000; i++ {
			t += math.Sqrt(float64(i) / 997)
		}
	case "pow":
		for i := 1; i <= 10000000; i++ {
			t += math.Pow(float64(i%997+1)/997, 1.37)
		}
	case "atan":
		for i := 1; i <= 10000000; i++ {
			t += math.Atan(float64(i) / 997)
		}
	default:
		fmt.Println("b24math: sin, exp, ln, sqrt, pow or atan")
		os.Exit(2)
	}
	fmt.Println(int64(t * 1000))
}
