// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// GPL version 3 or later; see COPYING. No warranty.

// Go's strconv as the second oracle of scripts/nummodel.py (P200): reads
// the cases and the model's answers (go run . CASES EXPECT) and checks
// every value against Go: ParseFloat for 64 and 32 bits, ParseInt and
// ParseUint for an integer literal, and the shortest form of a float as
// encoding/json/internal/jsonwire's AppendFloat lays it out (ECMAScript's
// form: 'e' below 1e-6 and from 1e21, e-07 made e-7).
package main

import (
	"bufio"
	"fmt"
	"math"
	"os"
	"strconv"
	"strings"
)

func es6(f float64, bits int) string {
	abs := math.Abs(f)
	fmtc := byte('f')
	if abs != 0 && !math.IsInf(f, 0) && !math.IsNaN(f) {
		if bits == 64 && (abs < 1e-6 || abs >= 1e21) || bits == 32 && (float32(abs) < 1e-6 || float32(abs) >= 1e21) {
			fmtc = 'e'
		}
	}
	dst := strconv.AppendFloat(nil, f, fmtc, -1, bits)
	if fmtc == 'e' {
		n := len(dst)
		if n >= 4 && dst[n-4] == 'e' && dst[n-3] == '-' && dst[n-2] == '0' {
			dst[n-2] = dst[n-1]
			dst = dst[:n-1]
		}
	}
	return string(dst)
}

func b2i(b bool) int {
	if b {
		return 1
	}
	return 0
}

func main() {
	cf, _ := os.Open(os.Args[1])
	ef, _ := os.Open(os.Args[2])
	cs := bufio.NewScanner(cf)
	es := bufio.NewScanner(ef)
	cs.Buffer(make([]byte, 1<<20), 1<<20)
	es.Buffer(make([]byte, 1<<20), 1<<20)
	bad, n := 0, 0
	for cs.Scan() {
		line := cs.Text()
		if line == "" {
			break
		}
		es.Scan()
		want := es.Text()
		n++
		k, t := line[0], line[2:]
		got := ""
		switch k {
		case 'p', 'j':
			if strings.HasPrefix(want, "bad") {
				continue
			}
			var ln int
			fmt.Sscan(want, &ln)
			s := t[:ln]
			f64, e64 := strconv.ParseFloat(s, 64)
			f32, e32 := strconv.ParseFloat(s, 32)
			intlit := !strings.ContainsAny(s, ".eE")
			oki, oku := 0, 0
			var vi int64
			var vu uint64
			if intlit {
				if v, err := strconv.ParseInt(s, 10, 64); err == nil {
					oki, vi = 1, v
				}
				if v, err := strconv.ParseUint(strings.TrimPrefix(strings.TrimPrefix(s, "+"), "-"), 10, 64); err == nil && (!strings.HasPrefix(s, "-") || v == 0) {
					oku, vu = 1, v
				}
			}
			got = fmt.Sprintf("%d %d %d %d %d %d %d %d %d", ln, int64(math.Float64bits(f64)), b2i(e64 == nil),
				math.Float32bits(float32(f32)), b2i(e32 == nil), oki, vi, oku, int64(vu))
		case 'a':
			v, _ := strconv.ParseInt(t, 10, 64)
			got = es6(math.Float64frombits(uint64(v)), 64)
		case 'b':
			v, _ := strconv.ParseInt(t, 10, 64)
			got = es6(float64(math.Float32frombits(uint32(v))), 32)
		case 'i':
			got = t
		case 'u':
			v, _ := strconv.ParseInt(t, 10, 64)
			got = strconv.FormatUint(uint64(v), 10)
		}
		if got != want {
			bad++
			if bad < 20 {
				fmt.Printf("case %q: model %q, Go %q\n", line[:min(len(line), 120)], want, got)
			}
		}
	}
	fmt.Printf("%d cases, %d differ from Go\n", n, bad)
}
