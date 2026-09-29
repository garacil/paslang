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

package main

import (
	"fmt"
	"math/bits"
)

func main() {
	var s0, s1, s2, s3, sum uint64 = 1, 2, 3, 4, 0
	for i := 1; i <= 100000000; i++ {
		r := bits.RotateLeft64(s1*5, 7) * 9
		t := s1 << 17
		s2 ^= s0
		s3 ^= s1
		s1 ^= s2
		s0 ^= s3
		s2 ^= t
		s3 = bits.RotateLeft64(s3, 45)
		sum += r
	}
	fmt.Println(int64(sum), int64(s0))
}
