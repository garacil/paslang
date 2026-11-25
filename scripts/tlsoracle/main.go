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
	"crypto/ed25519"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/rsa"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"flag"
	"fmt"
	"io"
	"math/big"
	"net"
	"os"
	"strings"
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

func edKey() ed25519.PrivateKey {
	_, key, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		panic(err)
	}
	return key
}

type badSignature struct{ crypto.Signer }

func (s badSignature) Sign(random io.Reader, msg []byte, opts crypto.SignerOpts) ([]byte, error) {
	sig, err := s.Signer.Sign(random, msg, opts)
	if err == nil {
		sig[len(sig)-1] ^= 1
	}
	return sig, err
}

func main() {
	port := flag.Int("port", 0, "port")
	name := flag.String("case", "tls13", "case")
	dir := flag.String("dir", ".", "where ca.pem goes")
	client := flag.String("client", "", "connect to a TLS 1.3 server at this address")
	root := flag.String("root", "", "PEM root trusted by the client")
	flag.Parse()
	if *client != "" {
		if err := checkServer(*client, *root); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		return
	}
	ed := strings.Contains(*name, "ed25519")
	var caKey crypto.Signer
	if ed {
		caKey = edKey()
	} else {
		caKey, _ = ecdsa.GenerateKey(elliptic.P384(), rand.Reader)
	}
	caT := &x509.Certificate{SerialNumber: big.NewInt(1), Subject: pkix.Name{CommonName: "pastls test root"},
		NotBefore: notBefore, NotAfter: notAfter, IsCA: true, BasicConstraintsValid: true,
		KeyUsage: x509.KeyUsageCertSign | x509.KeyUsageCRLSign}
	ca := mkCert(caT, caT, caKey.Public(), caKey)
	os.WriteFile(*dir+"/ca.pem", pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: ca.Raw}), 0644)
	issuer, issuerKey := ca, caKey
	if ed {
		issuerKey = edKey()
		issuerT := *caT
		issuerT.SerialNumber = big.NewInt(3)
		issuerT.Subject = pkix.Name{CommonName: "pastls test intermediate"}
		issuer = mkCert(&issuerT, ca, issuerKey.Public(), caKey)
	}
	var leafPriv crypto.Signer
	switch {
	case ed && *name != "tls13ed25519-chain":
		leafPriv = edKey()
	case len(*name) > 3 && (*name)[len(*name)-3:] == "rsa":
		k, _ := rsa.GenerateKey(rand.Reader, 2048)
		leafPriv = k
	case len(*name) > 4 && (*name)[len(*name)-4:] == "p384":
		k, _ := ecdsa.GenerateKey(elliptic.P384(), rand.Reader)
		leafPriv = k
	default:
		k, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
		leafPriv = k
	}
	leafT := &x509.Certificate{SerialNumber: big.NewInt(2), Subject: pkix.Name{CommonName: "localhost"},
		NotBefore: notBefore, NotAfter: notAfter, DNSNames: []string{"localhost", "*.pastls.test"},
		IPAddresses: []net.IP{net.ParseIP("127.0.0.1")},
		KeyUsage:    x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}}
	leaf := mkCert(leafT, issuer, leafPriv.Public(), issuerKey)
	if strings.HasSuffix(*name, "-badcert") {
		leaf.Raw[len(leaf.Raw)-1] ^= 1
	}
	if strings.HasSuffix(*name, "-badsig") {
		leafPriv = badSignature{leafPriv}
	}
	cfg := &tls.Config{Certificates: []tls.Certificate{{Certificate: [][]byte{leaf.Raw, issuer.Raw}, PrivateKey: leafPriv}},
		Time: func() time.Time { return time.Date(2027, 6, 1, 0, 0, 0, 0, time.UTC) }}
	switch *name {
	case "tls13", "tls13rsa", "tls13p384", "tls13ed25519", "tls13ed25519-chain", "tls13ed25519-badcert", "tls13ed25519-badsig":
	case "hrr":
		cfg.CurvePreferences = []tls.CurveID{tls.CurveP256}
	case "hrr384":
		cfg.CurvePreferences = []tls.CurveID{tls.CurveP384}
	case "alpn":
		cfg.NextProtos = []string{"h2", "http/1.1"}
	case "certreq":
		cfg.ClientAuth = tls.RequestClientCert
	case "tls12-c02b", "tls12-c02c", "tls12-cca9", "tls12-c02f-rsa", "tls12-c030-rsa", "tls12-cca8-rsa", "tls12-c02b-p384", "tls12-c02b-ed25519", "tls12-c02b-ed25519-badsig":
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
