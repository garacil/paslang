// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// rm PATH: Go's os.RemoveAll of PATH, for scripts/bench_rmall.py (P631).
package main

import (
	"fmt"
	"os"
)

func main() {
	if err := os.RemoveAll(os.Args[1]); err != nil {
		fmt.Println("error:", err)
		os.Exit(1)
	}
}
