// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// GPL version 3 or later; see COPYING. No warranty.
package main

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
)

func boolean(value bool) int {
	if value {
		return 1
	}
	return 0
}

func main() {
	input := bufio.NewScanner(os.Stdin)
	input.Buffer(make([]byte, 4096), 1<<20)
	if !input.Scan() {
		panic("missing count")
	}
	count, err := strconv.Atoi(input.Text())
	if err != nil {
		panic(err)
	}
	for i := 0; i < count; i++ {
		if !input.Scan() {
			panic("missing path")
		}
		path := input.Text()
		fmt.Println(filepath.Clean(path))
		fmt.Println(boolean(filepath.IsAbs(path)), boolean(filepath.IsLocal(path)))
	}
	if err := input.Err(); err != nil {
		panic(err)
	}
}
