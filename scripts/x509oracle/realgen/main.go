// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// realgen writes cases for the two real chains fetched once from the
// network: each verified by Go against the system roots (Roots nil) at
// fixed times, for the right host name and for others.
package main

import (
	"crypto/x509"
	"encoding/hex"
	"encoding/pem"
	"fmt"
	"os"
	"time"
)

func main() {
	n := 0
	t1 := time.Date(2026, 10, 1, 12, 0, 0, 0, time.UTC)
	t2 := time.Date(2027, 3, 1, 0, 0, 0, 0, time.UTC)
	for _, c := range []struct{ file, host string; others []string }{
		{"x509/correo.7kas.com.pem", "correo.7kas.com", []string{"7kas.com", "mail.7kas.com", "CORREO.7KAS.COM."}},
		{"x509/api.deepseek.com.pem", "api.deepseek.com", []string{"deepseek.com", "a.b.deepseek.com", "Chat.DeepSeek.com", "api.deepseek.org"}},
	} {
		data, err := os.ReadFile(c.file)
		if err != nil {
			panic(err)
		}
		var ders [][]byte
		for {
			var b *pem.Block
			b, data = pem.Decode(data)
			if b == nil {
				break
			}
			ders = append(ders, b.Bytes)
		}
		hosts := append([]string{c.host}, c.others...)
		for _, h := range hosts {
			for _, tm := range []time.Time{t1, t2} {
				leaf, _ := x509.ParseCertificate(ders[0])
				ip := x509.NewCertPool()
				for _, d := range ders[1:] {
					ic, _ := x509.ParseCertificate(d)
					ip.AddCert(ic)
				}
				_, verr := leaf.Verify(x509.VerifyOptions{DNSName: h, Intermediates: ip, CurrentTime: tm})
				n++
				fmt.Printf("case %d real-%s-%s-%d\nsysroots\ntime %d\nhost %s\neku -\nleaf %s\n", n, c.host, h, tm.Unix(), tm.Unix(), h, hex.EncodeToString(ders[0]))
				for _, d := range ders[1:] {
					fmt.Printf("inter %s\n", hex.EncodeToString(d))
				}
				if verr == nil {
					fmt.Printf("want ok\nend\n")
				} else {
					fmt.Printf("want err %s\nend\n", verr.Error())
				}
			}
		}
		// without the intermediates the leaf alone does not reach a root
		leaf, _ := x509.ParseCertificate(ders[0])
		_, verr := leaf.Verify(x509.VerifyOptions{DNSName: c.host, Intermediates: x509.NewCertPool(), CurrentTime: t1})
		n++
		fmt.Printf("case %d real-%s-leaf-alone\nsysroots\ntime %d\nhost %s\neku -\nleaf %s\nwant err %s\nend\n", n, c.host, t1.Unix(), c.host, hex.EncodeToString(ders[0]), verr.Error())
	}
}
