// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// P486: real arithmetic, the Go side of scripts/bench/b43real.paslang: the
// Mandelbrot set on a grid of 500 by 500 points, each point iterated up to 200
// times with float64s; the iterations are summed.
package main

import "fmt"

func iter(cr, ci float64) int {
	zr, zi := 0.0, 0.0
	n := 0
	for n < 200 && zr*zr+zi*zi < 4.0 {
		t := zr*zr - zi*zi + cr
		zi = 2.0*zr*zi + ci
		zr = t
		n++
	}
	return n
}

func main() {
	total := 0
	for y := 0; y < 500; y++ {
		for x := 0; x < 500; x++ {
			total += iter(float64(x)/250.0-1.5, float64(y)/250.0-1.0)
		}
	}
	fmt.Println(total)
}
