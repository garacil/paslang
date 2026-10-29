// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// P425: the fused multiply-add, the Go side of scripts/bench/b44fma.paslang:
// Horner's rule of degree 16 with math.FMA at thirty million points; the sums
// are folded into one hash of the bits.
package main

import (
	"fmt"
	"math"
)

func horner(x float64) float64 {
	r := 0.0
	for i := 1; i <= 16; i++ {
		r = math.FMA(r, x, float64(i))
	}
	return r
}

func main() {
	total := 0.0
	for k := 0; k < 30000000; k++ {
		x := float64(k%2000)/2000.0 - 0.5
		total += horner(x)
	}
	fmt.Println(int64(math.Float64bits(total)))
}
