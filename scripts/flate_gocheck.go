// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// The oracle of pasflate's writer (P449): Go's compress/flate and gzip
// write what testdata/flatec writes. It reads the lines `NAME HEX` that
// `flatec data` writes and, for each shape and each level -2 and 0 to 9,
// writes the two lines flatec writes: the size and the FNV-1a of the raw
// stream and of the gzip file, and the size and FNV-1a of the raw stream
// of the data written in pieces with flushes between (the sizes and the
// flushes from a xorshift32 stream seeded by the name and the level, as
// flatec does). After the shapes come the three sweeps, at each level the
// size and the FNV-1a of the streams of many cuts of the data one after the
// other: the lengths 0 to 300 of text5k and of random70k, and 34 lengths
// round the limits of the windows and blocks of text400k, 26 lengths of
// random70k round where stored blocks begin and end, the lengths 1 to 1500
// of skew100k, and nine blocks of random bytes of 258 to 65535 repeated to
// 140000 bytes.
//
//	go run scripts/flate_gocheck.go < shapes > lines
package main

import (
	"bufio"
	"bytes"
	"compress/flate"
	"compress/gzip"
	"encoding/hex"
	"fmt"
	"hash/fnv"
	"os"
	"strings"
)

func xorShift(x uint32) uint32 {
	x ^= x << 13
	x ^= x >> 17
	x ^= x << 5
	return x
}

func hash(b []byte) uint64 {
	h := fnv.New64a()
	h.Write(b)
	return h.Sum64()
}

func chunked(name string, data []byte, level int) []byte {
	sizes := []int{1, 3, 7, 100, 1000, 5000, 33000, 70000}
	sum := uint32(0)
	for _, c := range []byte(name) {
		sum += uint32(c)
	}
	x := (2463534242 ^ (sum * 2654435761) ^ (uint32(level+3) * 40503)) | 1
	var buf bytes.Buffer
	w, err := flate.NewWriter(&buf, level)
	if err != nil {
		panic(err)
	}
	for pos := 0; pos < len(data); {
		x = xorShift(x)
		m := sizes[x&7]
		x = xorShift(x)
		n := 1 + int(x%uint32(m))
		if n > len(data)-pos {
			n = len(data) - pos
		}
		w.Write(data[pos : pos+n])
		pos += n
		x = xorShift(x)
		if x%5 == 0 {
			w.Flush()
		}
	}
	w.Close()
	return buf.Bytes()
}

var sweepSizes = []int{12, 13, 14, 31, 32, 33, 127, 128, 129, 255, 256, 257, 4095, 4096, 4097, 32767, 32768,
	32769, 65534, 65535, 65536, 65537, 131070, 131071, 131072, 131073, 262143, 262144, 327674, 327675, 327676, 327677, 327680,
	392000}

func raw(data []byte, level int) []byte {
	var buf bytes.Buffer
	w, err := flate.NewWriter(&buf, level)
	if err != nil {
		panic(err)
	}
	w.Write(data)
	w.Close()
	return buf.Bytes()
}

var randSizes = []int{1023, 1024, 1025, 1026, 4095, 4096, 4097, 8191, 8192, 8193, 16383, 16384, 16385, 32767,
	32768, 32769, 65533, 65534, 65535, 65536, 65537, 65538, 69999, 70000, 2047, 2049}

var periods = []int{258, 259, 4097, 16382, 16383, 16384, 16385, 32763, 32764, 32765, 32766, 32767, 32768, 32769, 65534, 65535}

var soupSizes = []int{200000, 150000, 100000, 65535, 65536, 40000, 20000, 5000, 1000}

var pieceSizes = []int{65534, 65535, 65536, 32768, 100000}

var sparseK = []int{60, 80, 100, 120, 135, 150, 170, 200, 300}

func sweep(which int, text, rnd, long, skew, soup []byte, level int) string {
	h := fnv.New64a()
	total := 0
	add := func(b []byte) {
		h.Write(b)
		total += len(b)
	}
	switch which {
	case 0:
		for n := 0; n <= 300; n++ {
			add(raw(text[:n], level))
		}
	case 1:
		for n := 0; n <= 300; n++ {
			add(raw(rnd[:n], level))
		}
	case 3:
		for _, n := range randSizes {
			add(raw(rnd[:n], level))
		}
	case 4:
		for n := 1; n <= 1500; n++ {
			add(raw(skew[:n], level))
		}
	case 6:
		for j := 1; j <= 10; j++ {
			rep := make([]byte, 50)
			for i := 1; i <= 50; i++ {
				rep[i-1] = byte(97 + (i-1)%j)
			}
			for n := 0; n <= 40; n++ {
				add(raw(rep[:n], level))
			}
		}
	case 10:
		for _, k := range sparseK {
			var rep []byte
			n := 0
			for len(rep) < 65535 && n+1 < 69000 {
				e := n + k
				if e > len(rnd) {
					e = len(rnd)
				}
				rep = append(rep, rnd[n:e]...)
				n += k
				if len(rep) > 200 {
					rep = append(rep, rep[len(rep)-151:len(rep)-143]...)
				}
			}
			add(raw(rep[:65535], level))
			add(raw(rep[:40000], level))
		}
	case 9:
		for n := 11; n <= 15; n++ {
			for j := 0; j < 4; j++ {
				var buf bytes.Buffer
				w, err := flate.NewWriter(&buf, level)
				if err != nil {
					panic(err)
				}
				w.Write(text[:3000+7*j])
				w.Flush()
				w.Write(text[99+j*50 : 99+j*50+n])
				w.Close()
				add(buf.Bytes())
			}
		}
	case 7:
		for _, n := range soupSizes {
			add(raw(soup[:n], level))
		}
	case 8:
		for _, ps := range pieceSizes {
			for j := 0; j < 2; j++ {
				var buf bytes.Buffer
				w, err := flate.NewWriter(&buf, level)
				if err != nil {
					panic(err)
				}
				for n := 0; n < 300000; n += ps {
					e := n + ps
					if e > len(long) {
						e = len(long)
					}
					w.Write(long[n:e])
					if j == 1 {
						w.Flush()
					}
				}
				w.Close()
				add(buf.Bytes())
			}
		}
	case 5:
		for _, p := range periods {
			rep := append([]byte(nil), rnd[:p]...)
			for len(rep) < 140000 {
				rep = append(rep, rep...)
			}
			add(raw(rep[:140000], level))
		}
	default:
		for _, n := range sweepSizes {
			add(raw(long[:n], level))
		}
	}
	return fmt.Sprintf("%d %016x", total, h.Sum64())
}

func main() {
	shapes := map[string][]byte{}
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 1<<20), 1<<28)
	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()
	for sc.Scan() {
		f := strings.Fields(sc.Text())
		var data []byte
		if len(f) > 1 {
			data, _ = hex.DecodeString(f[1])
		}
		shapes[f[0]] = data
		if f[0] == "text400k" || f[0] == "soup200k" {
			continue
		}
		for level := -2; level <= 9; level++ {
			if level == -1 {
				continue
			}
			var rw, gz bytes.Buffer
			w, err := flate.NewWriter(&rw, level)
			if err != nil {
				panic(err)
			}
			w.Write(data)
			w.Close()
			g, err := gzip.NewWriterLevel(&gz, level)
			if err != nil {
				panic(err)
			}
			g.Write(data)
			g.Close()
			fmt.Fprintf(out, "%s %d level %d: %d %016x %016x 1\n", f[0], len(data), level, rw.Len(), hash(rw.Bytes()), hash(gz.Bytes()))
			c := chunked(f[0], data, level)
			fmt.Fprintf(out, "%s %d pieces %d: %d %016x\n", f[0], len(data), level, len(c), hash(c))
		}
	}
	for level := -2; level <= 9; level++ {
		if level == -1 {
			continue
		}
		for i, name := range []string{"text", "random", "sizes", "randsizes", "skew", "periods", "tiny", "soup", "pieces", "after", "sparse"} {
			fmt.Fprintf(out, "sweep %s %d: %s\n", name, level, sweep(i, shapes["text5k"], shapes["random70k"], shapes["text400k"], shapes["skew100k"], shapes["soup200k"], level))
		}
	}
}
