// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// pfuzz writes parse cases: certificates taken from case files, each
// as it is and mutated (bytes flipped, inserted, deleted, lengths
// changed; math/rand with a fixed seed), with what Go's
// ParseCertificate says of each.
//
// Usage: pfuzz casefile... > pfuzz.txt
package main

import (
	"bufio"
	"crypto/x509"
	"encoding/hex"
	"fmt"
	"math/rand/v2"
	"os"
	"strconv"
	"strings"
)

func b2i(b bool) string {
	if b {
		return "1"
	}
	return "0"
}

func summary(c *x509.Certificate) string {
	s := "v" + strconv.Itoa(c.Version) + " sig" + strconv.Itoa(int(c.SignatureAlgorithm)) + " pk" + strconv.Itoa(int(c.PublicKeyAlgorithm)) +
		" ca" + b2i(c.IsCA) + " bc" + b2i(c.BasicConstraintsValid) + " mpl" + strconv.Itoa(c.MaxPathLen) +
		" ku" + strconv.Itoa(int(c.KeyUsage)) + " nb" + strconv.FormatInt(c.NotBefore.Unix(), 10) + " na" + strconv.FormatInt(c.NotAfter.Unix(), 10) +
		" cn=" + c.Subject.CommonName + " serial=" + c.SerialNumber.String() + " dns=" + strings.Join(c.DNSNames, ",") + " ip="
	for _, ip := range c.IPAddresses {
		s += ip.String() + ","
	}
	s += " email=" + strings.Join(c.EmailAddresses, ",") + " uri="
	for _, u := range c.URIs {
		s += u.String() + ","
	}
	s += " eku="
	for _, e := range c.ExtKeyUsage {
		s += strconv.Itoa(int(e)) + ","
	}
	s += " crit=" + strconv.Itoa(len(c.UnhandledCriticalExtensions)) + " pol=" + strconv.Itoa(len(c.Policies)) +
		" rep=" + strconv.Itoa(c.RequireExplicitPolicy) + " iap=" + strconv.Itoa(c.InhibitAnyPolicy) +
		" pdns=" + strings.Join(c.PermittedDNSDomains, ",") + " xdns=" + strings.Join(c.ExcludedDNSDomains, ",") +
		" ski=" + hex.EncodeToString(c.SubjectKeyId) + " aki=" + hex.EncodeToString(c.AuthorityKeyId)
	return s
}

func main() {
	seen := map[string]bool{}
	var ders [][]byte
	for _, f := range os.Args[1:] {
		fh, err := os.Open(f)
		if err != nil {
			panic(err)
		}
		sc := bufio.NewScanner(fh)
		sc.Buffer(make([]byte, 1<<20), 1<<24)
		for sc.Scan() {
			l := sc.Text()
			for _, p := range []string{"leaf ", "inter ", "root "} {
				if strings.HasPrefix(l, p) {
					h := l[len(p):]
					if !seen[h] {
						seen[h] = true
						d, _ := hex.DecodeString(h)
						ders = append(ders, d)
					}
				}
			}
		}
		fh.Close()
	}
	r := rand.New(rand.NewPCG(430, 2))
	n := 0
	emit := func(name string, d []byte) {
		n++
		fmt.Printf("parse %d %s\nleaf %s\n", n, name, hex.EncodeToString(d))
		c, err := x509.ParseCertificate(d)
		if err != nil {
			fmt.Printf("want err %s\nend\n", err.Error())
		} else {
			fmt.Printf("want ok %s\nend\n", summary(c))
		}
	}
	step := len(ders)/400 + 1
	for i := 0; i < len(ders); i += step {
		d := ders[i]
		emit(fmt.Sprintf("orig-%d", i), d)
		for m := 0; m < 8; m++ {
			c := append([]byte{}, d...)
			for k := 1 + r.IntN(3); k > 0; k-- {
				p := r.IntN(len(c))
				switch r.IntN(5) {
				case 0:
					c[p] ^= byte(1 << r.IntN(8))
				case 1:
					c[p] = byte(r.IntN(256))
				case 2:
					c = append(c[:p], append([]byte{byte(r.IntN(256))}, c[p:]...)...)
				case 3:
					c = append(c[:p], c[p+1:]...)
				case 4:
					// a length octet one more or one less
					if c[p] < 0x80 && c[p] > 0 {
						c[p] += byte(r.IntN(3)) - 1
					}
				}
				if len(c) == 0 {
					break
				}
			}
			emit(fmt.Sprintf("mut-%d-%d", i, m), c)
		}
	}
}
