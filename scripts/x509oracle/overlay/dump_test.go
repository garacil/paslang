// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// Copied into crypto/x509 through go test -overlay (the Go tree is not
// touched): writes Go's own verify and name constraint test vectors as
// pasx509 case files, with Go's verdict and error text at each case's
// time.
package x509

import (
	"encoding/json"
	"path/filepath"
	"slices"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"encoding/hex"
	"encoding/pem"
	"fmt"
	"os"
	"strconv"
	"strings"
	"testing"
	"time"
)

func dumpDERs(pems []string) [][]byte {
	var out [][]byte
	for _, p := range pems {
		rest := []byte(p)
		for {
			var b *pem.Block
			b, rest = pem.Decode(rest)
			if b == nil {
				break
			}
			if b.Type == "CERTIFICATE" && len(b.Headers) == 0 {
				out = append(out, b.Bytes)
			}
		}
	}
	return out
}

func dumpCase(f *os.File, n int, name string, leaf []byte, inters, roots [][]byte, host string, tm time.Time, ekus []ExtKeyUsage, verdict error) {
	fmt.Fprintf(f, "case %d %s\n", n, strings.ReplaceAll(name, " ", "_"))
	fmt.Fprintf(f, "time %d\n", tm.Unix())
	if host == "" {
		host = "-"
	}
	fmt.Fprintf(f, "host %s\n", host)
	if ekus == nil {
		fmt.Fprintf(f, "eku -\n")
	} else {
		var s []string
		for _, e := range ekus {
			s = append(s, strconv.Itoa(int(e)))
		}
		fmt.Fprintf(f, "eku %s\n", strings.Join(s, ","))
	}
	fmt.Fprintf(f, "leaf %s\n", hex.EncodeToString(leaf))
	for _, d := range inters {
		fmt.Fprintf(f, "inter %s\n", hex.EncodeToString(d))
	}
	for _, d := range roots {
		fmt.Fprintf(f, "root %s\n", hex.EncodeToString(d))
	}
	if verdict == nil {
		fmt.Fprintf(f, "want ok\n")
	} else {
		fmt.Fprintf(f, "want err %s\n", verdict.Error())
	}
	fmt.Fprintf(f, "end\n")
}

func TestDumpVerifyTests(t *testing.T) {
	f, err := os.Create(os.Getenv("DUMP_DIR") + "/go-verify-tests.txt")
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	n := 0
	for _, test := range verifyTests {
		ct := test.currentTime
		if ct == 0 {
			ct = 1
		}
		tm := time.Unix(ct, 0).UTC()
		opts := VerifyOptions{Intermediates: NewCertPool(), Roots: NewCertPool(), DNSName: test.dnsName, CurrentTime: tm, KeyUsages: test.keyUsages}
		roots := dumpDERs(test.roots)
		inters := dumpDERs(test.intermediates)
		for _, r := range test.roots {
			opts.Roots.AppendCertsFromPEM([]byte(r))
		}
		for _, r := range test.intermediates {
			opts.Intermediates.AppendCertsFromPEM([]byte(r))
		}
		leafs := dumpDERs([]string{test.leaf})
		leaf, err := ParseCertificate(leafs[0])
		var verr error
		if err != nil {
			verr = err
		} else {
			_, verr = leaf.Verify(opts)
		}
		n++
		ekus := test.keyUsages
		if ekus != nil && len(ekus) == 0 {
			ekus = nil
		}
		dumpCase(f, n, "go-verify-"+test.name, leafs[0], inters, roots, test.dnsName, tm, ekus, verr)
	}
}

func TestDumpConstraintCases(t *testing.T) {
	f, err := os.Create(os.Getenv("DUMP_DIR") + "/go-constraint-tests.txt")
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	newKey := func() *ecdsa.PrivateKey {
		k, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
		if err != nil {
			panic(err)
		}
		return k
	}
	for i, test := range nameConstraintsTests {
		rootPool := NewCertPool()
		rootKey := newKey()
		rootName := "Root " + strconv.Itoa(i)
		var parent *Certificate
		parentKey := rootKey
		var rootDER, interDER [][]byte
		for _, root := range test.roots {
			rootCert, err := makeConstraintsCACert(root, rootName, rootKey, nil, rootKey)
			if err != nil {
				t.Fatalf("root: %s", err)
			}
			parent = rootCert
			rootPool.AddCert(rootCert)
			rootDER = append(rootDER, rootCert.Raw)
		}
		intermediatePool := NewCertPool()
		for level, intermediates := range test.intermediates {
			levelKey := newKey()
			levelName := "Intermediate level " + strconv.Itoa(level)
			var last *Certificate
			for _, intermediate := range intermediates {
				caCert, err := makeConstraintsCACert(intermediate, levelName, levelKey, parent, parentKey)
				if err != nil {
					t.Fatalf("%s: %s", levelName, err)
				}
				last = caCert
				intermediatePool.AddCert(caCert)
				interDER = append(interDER, caCert.Raw)
			}
			parent = last
			parentKey = levelKey
		}
		leafCert, err := makeConstraintsLeafCert(test.leaf, newKey(), parent, parentKey)
		if err != nil {
			t.Fatalf("leaf: %s", err)
		}
		tm := time.Unix(1500, 0).UTC()
		_, verr := leafCert.Verify(VerifyOptions{Roots: rootPool, Intermediates: intermediatePool, CurrentTime: tm, KeyUsages: test.requestedEKUs})
		ekus := test.requestedEKUs
		if len(ekus) == 0 {
			ekus = nil
		}
		dumpCase(f, i+1, fmt.Sprintf("go-nc-%d-%s", i, test.name), leafCert.Raw, interDER, rootDER, "", tm, ekus, verr)
	}
}

func TestDumpPKITS(t *testing.T) {
	certDir := "testdata/nist-pkits/certs"
	var testcases []struct {
		Name                        string
		CertPath                    []string
		InitialPolicySet            []string
		InitialPolicyMappingInhibit bool
		InitialExplicitPolicy       bool
		InitialAnyPolicyInhibit     bool
		ShouldValidate              bool
	}
	b, err := os.ReadFile("testdata/nist-pkits/vectors.json")
	if err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(b, &testcases); err != nil {
		t.Fatal(err)
	}
	f, err := os.Create(os.Getenv("DUMP_DIR") + "/go-pkits.txt")
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	tm := time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC)
	n := 0
	for _, tc := range testcases {
		var ders [][]byte
		for _, c := range tc.CertPath {
			d, err := os.ReadFile(filepath.Join(certDir, c))
			if err != nil {
				t.Fatal(err)
			}
			ders = append(ders, d)
		}
		// full verification: the first is the trust anchor, the last the leaf
		leafDER := ders[len(ders)-1]
		inters := ders[1 : len(ders)-1]
		roots := ders[:1]
		var verr error
		leaf, err := ParseCertificate(leafDER)
		if err != nil {
			verr = err
		} else {
			ip := NewCertPool()
			rp := NewCertPool()
			for _, d := range inters {
				c, err := ParseCertificate(d)
				if err != nil {
					verr = err
					break
				}
				ip.AddCert(c)
			}
			for _, d := range roots {
				if c, err := ParseCertificate(d); err == nil {
					rp.AddCert(c)
				}
			}
			if verr == nil {
				_, verr = leaf.Verify(VerifyOptions{Roots: rp, Intermediates: ip, CurrentTime: tm})
			}
		}
		n++
		var rinters [][]byte
		for i := len(inters) - 1; i >= 0; i-- {
			rinters = append(rinters, inters[i])
		}
		dumpCase(f, n, "pkits-"+tc.Name, leafDER, rinters, roots, "", tm, nil, verr)
		// policy validation alone, as TestNISTPKITSPolicy runs it
		var chain []*Certificate
		ok := true
		for _, d := range ders {
			c, err := ParseCertificate(d)
			if err != nil {
				ok = false
				break
			}
			chain = append(chain, c)
		}
		if !ok {
			continue
		}
		slices.Reverse(chain)
		var initial []OID
		var initialHex []string
		for _, p := range tc.InitialPolicySet {
			o := nistTestPolicies[p]
			initial = append(initial, o)
			initialHex = append(initialHex, hex.EncodeToString(o.der))
		}
		opts := VerifyOptions{CertificatePolicies: initial, inhibitPolicyMapping: tc.InitialPolicyMappingInhibit,
			requireExplicitPolicy: tc.InitialExplicitPolicy, inhibitAnyPolicy: tc.InitialAnyPolicyInhibit}
		valid := policiesValid(chain, opts)
		n++
		fmt.Fprintf(f, "pol %d pkits-policy-%s\n", n, strings.ReplaceAll(tc.Name, " ", "_"))
		for _, c := range chain {
			fmt.Fprintf(f, "leaf %s\n", hex.EncodeToString(c.Raw))
		}
		fmt.Fprintf(f, "policies %s\n", strings.Join(initialHex, ","))
		fmt.Fprintf(f, "flags %v %v %v\n", tc.InitialPolicyMappingInhibit, tc.InitialExplicitPolicy, tc.InitialAnyPolicyInhibit)
		if valid {
			fmt.Fprintf(f, "want ok\n")
		} else {
			fmt.Fprintf(f, "want err invalid policies\n")
		}
		fmt.Fprintf(f, "end\n")
	}
}
