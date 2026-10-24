// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// The second oracle of testdata/zip (P427): Go's archive/zip reads each
// archive scripts/zip_corpus.py hands it and says what it makes of it.
// It reads lines `ID HEX` (HEX is - for an empty archive) on standard input
// and writes `ID VERDICT`, the verdict spelled as zip_corpus.py spells it:
// err, or ok:COUNT:CRC32 of the listing (name, size and CRC-32 of each
// entry's bytes, one line each).
//
//	go run scripts/zip_oracle.go < lines > verdicts
package main

import (
	"archive/zip"
	"bufio"
	"bytes"
	"encoding/hex"
	"fmt"
	"hash/crc32"
	"io"
	"os"
	"strings"
)

func verdict(b []byte) string {
	r, err := zip.NewReader(bytes.NewReader(b), int64(len(b)))
	if err != nil {
		return "err"
	}
	var lst []byte
	for _, f := range r.File {
		rc, err := f.Open()
		if err != nil {
			return "err"
		}
		data, err := io.ReadAll(rc)
		rc.Close()
		if err != nil {
			return "err"
		}
		lst = append(lst, []byte(fmt.Sprintf("%s\t%d\t%d\n", f.Name, len(data), crc32.ChecksumIEEE(data)))...)
	}
	return fmt.Sprintf("ok:%d:%d", len(r.File), crc32.ChecksumIEEE(lst))
}

func main() {
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 1<<20), 1<<28)
	for sc.Scan() {
		f := strings.Fields(sc.Text())
		var b []byte
		if f[1] != "-" {
			b, _ = hex.DecodeString(f[1])
		}
		fmt.Println(f[0], verdict(b))
	}
}
