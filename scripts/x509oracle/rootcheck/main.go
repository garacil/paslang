// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// rootcheck prints the system roots Go loads (SSL_CERT_FILE and
// SSL_CERT_DIR honoured): their count and the SHA-256 of each subject,
// in the pool's order.
package main

import (
	"crypto/sha256"
	"crypto/x509"
	"encoding/hex"
	"fmt"
)

func main() {
	p, err := x509.SystemCertPool()
	if err != nil {
		fmt.Println("error", err)
		return
	}
	subs := p.Subjects()
	fmt.Println("count", len(subs))
	for _, s := range subs {
		h := sha256.Sum256(s)
		fmt.Println(hex.EncodeToString(h[:]))
	}
}
