// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// GPL version 3 or later; see COPYING. No warranty.
// P471: the same validated scalar-to-SEC 1 public key as b45nist.paslang.
package main

import (
	"bytes"
	"crypto/ecdh"
	"fmt"
	"os"
	"time"
)

func main() {
	curve, size := ecdh.P256(), 32
	if len(os.Args) > 1 && os.Args[1] == "p384" {
		curve, size = ecdh.P384(), 48
	}
	privateKey := bytes.Repeat([]byte{1}, size)
	report := len(os.Args) > 2 && os.Args[2] == "report"
	derive := func() []byte {
		key, err := curve.NewPrivateKey(privateKey)
		if err != nil {
			panic(err)
		}
		return key.PublicKey().Bytes()
	}
	var started time.Time
	if report {
		started = time.Now()
	}
	publicKey := derive()
	if report {
		cold := time.Since(started).Nanoseconds()
		started = time.Now()
		for i := 0; i < 100; i++ {
			publicKey = derive()
		}
		fmt.Println(cold, time.Since(started).Nanoseconds())
	}
	if len(publicKey) != 2*size+1 {
		panic("invalid public key length")
	}
	fmt.Printf("%x\n", publicKey)
}
