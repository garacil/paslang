// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// The TLS oracle of pastls (P431): a Go crypto/tls server per case on
// 127.0.0.1, configured as the case says, echoing each line with the
// session's version, suite and protocol. It writes its root in PEM to
// DIR/ca.pem, prints its port and serves until killed.
//
//	tlsoracle -case NAME -dir DIR
package main

import (
	"bufio"
	"crypto"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/rsa"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"flag"
	"fmt"
	"math/big"
	"net"
	"os"
	"time"
)

// the fixed time of the certificates: valid from 2026-01-01 to 2036-01-01
var notBefore = time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
var notAfter = time.Date(2036, 1, 1, 0, 0, 0, 0, time.UTC)

func mkCert(tmpl, parent *x509.Certificate, pub, priv any) *x509.Certificate {
	der, err := x509.CreateCertificate(rand.Reader, tmpl, parent, pub, priv)
	if err != nil {
		panic(err)
	}
	c, _ := x509.ParseCertificate(der)
	return c
}

func main() {
	port := flag.Int("port", 0, "port")
	name := flag.String("case", "tls13", "case")
	dir := flag.String("dir", ".", "where ca.pem goes")
	flag.Parse()
	caKey, _ := ecdsa.GenerateKey(elliptic.P384(), rand.Reader)
	caT := &x509.Certificate{SerialNumber: big.NewInt(1), Subject: pkix.Name{CommonName: "pastls test root"},
		NotBefore: notBefore, NotAfter: notAfter, IsCA: true, BasicConstraintsValid: true,
		KeyUsage: x509.KeyUsageCertSign | x509.KeyUsageCRLSign}
	ca := mkCert(caT, caT, &caKey.PublicKey, caKey)
	os.WriteFile(*dir+"/ca.pem", pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: ca.Raw}), 0644)
	var leafPub any
	var leafPriv crypto.Signer
	switch {
	case len(*name) > 3 && (*name)[len(*name)-3:] == "rsa":
		k, _ := rsa.GenerateKey(rand.Reader, 2048)
		leafPub, leafPriv = &k.PublicKey, k
	case len(*name) > 4 && (*name)[len(*name)-4:] == "p384":
		k, _ := ecdsa.GenerateKey(elliptic.P384(), rand.Reader)
		leafPub, leafPriv = &k.PublicKey, k
	default:
		k, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
		leafPub, leafPriv = &k.PublicKey, k
	}
	leafT := &x509.Certificate{SerialNumber: big.NewInt(2), Subject: pkix.Name{CommonName: "localhost"},
		NotBefore: notBefore, NotAfter: notAfter, DNSNames: []string{"localhost", "*.pastls.test"},
		IPAddresses: []net.IP{net.ParseIP("127.0.0.1")},
		KeyUsage: x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}}
	leaf := mkCert(leafT, ca, leafPub, caKey)
	cfg := &tls.Config{Certificates: []tls.Certificate{{Certificate: [][]byte{leaf.Raw, ca.Raw}, PrivateKey: leafPriv}},
		Time: func() time.Time { return time.Date(2027, 6, 1, 0, 0, 0, 0, time.UTC) }}
	switch *name {
	case "tls13", "tls13rsa", "tls13p384":
	case "hrr":
		cfg.CurvePreferences = []tls.CurveID{tls.CurveP256}
	case "hrr384":
		cfg.CurvePreferences = []tls.CurveID{tls.CurveP384}
	case "alpn":
		cfg.NextProtos = []string{"h2", "http/1.1"}
	case "certreq":
		cfg.ClientAuth = tls.RequestClientCert
	case "tls12-c02b", "tls12-c02c", "tls12-cca9", "tls12-c02f-rsa", "tls12-c030-rsa", "tls12-cca8-rsa", "tls12-c02b-p384":
		cfg.MaxVersion = tls.VersionTLS12
		var id uint16
		fmt.Sscanf((*name)[6:10], "%x", &id)
		cfg.CipherSuites = []uint16{id}
	case "tls12-noems":
		cfg.MaxVersion = tls.VersionTLS12
	case "tls12-p256":
		cfg.MaxVersion = tls.VersionTLS12
		cfg.CurvePreferences = []tls.CurveID{tls.CurveP256}
	case "tls12certreq":
		cfg.MaxVersion = tls.VersionTLS12
		cfg.ClientAuth = tls.RequestClientCert
	case "tls12alpn":
		cfg.MaxVersion = tls.VersionTLS12
		cfg.NextProtos = []string{"http/1.1"}
	default:
		fmt.Fprintln(os.Stderr, "unknown case", *name)
		os.Exit(2)
	}
	ln, err := tls.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", *port), cfg)
	if err != nil {
		panic(err)
	}
	fmt.Println(ln.Addr().(*net.TCPAddr).Port)
	os.Stdout.Sync()
	for {
		c, err := ln.Accept()
		if err != nil {
			continue
		}
		go func(c net.Conn) {
			defer c.Close()
			tc := c.(*tls.Conn)
			c.SetDeadline(time.Now().Add(20 * time.Second))
			if err := tc.Handshake(); err != nil {
				fmt.Fprintln(os.Stderr, "handshake:", err)
				return
			}
			st := tc.ConnectionState()
			r := bufio.NewReader(c)
			for {
				line, err := r.ReadString('\n')
				if err != nil {
					return
				}
				if line == "big\n" {
					b := make([]byte, 1<<20)
					for i := range b {
						b[i] = byte(i * 7)
					}
					c.Write(b)
					continue
				}
				fmt.Fprintf(c, "%x %x %s %s", st.Version, st.CipherSuite, st.NegotiatedProtocol, line)
			}
		}(c)
	}
}
