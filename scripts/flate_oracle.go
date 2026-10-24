// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// The second oracle of testdata/flate (P427): Go's compress/flate, zlib
// and gzip read each stream scripts/flate_corpus.py hands it. It reads
// lines `KIND ID HEX` (KIND raw, zlib, gzip or gzipm; HEX is - for no
// bytes) on standard input and writes `ID VERDICT`: err, or ok:LENGTH:CRC32
// of the bytes the stream makes. A stream with bytes after its end is err
// (a gzip file goes on with more members, as Go's reader does).
//
//	go run scripts/flate_oracle.go < lines > verdicts
package main

import (
	"bufio"
	"bytes"
	"compress/flate"
	"compress/gzip"
	"compress/zlib"
	"encoding/hex"
	"fmt"
	"hash/crc32"
	"io"
	"os"
	"strings"
)

func verdict(kind string, b []byte) string {
	br := bytes.NewReader(b)
	var rd io.Reader
	var err error
	switch kind {
	case "raw":
		rd = flate.NewReader(br)
	case "zlib":
		rd, err = zlib.NewReader(br)
	default:
		rd, err = gzip.NewReader(br)
	}
	if err != nil {
		return "err"
	}
	out, err := io.ReadAll(rd)
	if err != nil || br.Len() != 0 {
		return "err"
	}
	return fmt.Sprintf("ok:%d:%08x", len(out), crc32.ChecksumIEEE(out))
}

func main() {
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 1<<20), 1<<28)
	for sc.Scan() {
		f := strings.Fields(sc.Text())
		var b []byte
		if f[2] != "-" {
			b, _ = hex.DecodeString(f[2])
		}
		fmt.Println(f[1], verdict(f[0], b))
	}
}
