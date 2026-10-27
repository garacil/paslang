// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// gen writes the test cases of pasx509: certificate hierarchies made
// with crypto/x509.CreateCertificate (and a few built by hand where
// CreateCertificate will not write what is needed), each verified by
// Go's crypto/x509 at a fixed time; the verdict and Go's error text go
// into the case file. The times and serial numbers are fixed; the keys
// are drawn once and the file is kept.
//
// Usage: gen > cases.txt
package main

import (
	"crypto"
	"crypto/ecdsa"
	"crypto/ed25519"
	"crypto/elliptic"
	"crypto/md5"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha1"
	"crypto/sha256"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/asn1"
	"encoding/hex"
	"fmt"
	"math/big"
	"net"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

var (
	T0 = time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC)
	NB = time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)
	NA = time.Date(2035, 1, 1, 0, 0, 0, 0, time.UTC)
)

var serial int64 = 1000

func nextSerial() *big.Int {
	serial++
	return big.NewInt(serial)
}

// ---- keys ----

type kind int

const (
	kP256 kind = iota
	kP384
	kRSA
)

var kindName = []string{"p256", "p384", "rsa"}

var pool = map[kind][]crypto.Signer{}
var poolNext = map[kind]int{}

func newKey(k kind) crypto.Signer {
	switch k {
	case kP256:
		p, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
		return p
	case kP384:
		p, _ := ecdsa.GenerateKey(elliptic.P384(), rand.Reader)
		return p
	default:
		p, err := rsa.GenerateKey(rand.Reader, 2048)
		if err != nil {
			panic(err)
		}
		return p
	}
}

// key gives a key of kind k; RSA keys are reused from a pool of six
// (generating them is slow), EC keys are fresh.
func key(k kind) crypto.Signer {
	if k != kRSA {
		return newKey(k)
	}
	if len(pool[k]) < 6 {
		pool[k] = append(pool[k], newKey(k))
		return pool[k][len(pool[k])-1]
	}
	i := poolNext[k]
	poolNext[k] = (i + 1) % 6
	return pool[k][i]
}

func kindOf(s crypto.Signer) kind {
	switch p := s.(type) {
	case *ecdsa.PrivateKey:
		if p.Curve == elliptic.P256() {
			return kP256
		}
		return kP384
	}
	return kRSA
}

// sigAlg picks the signature algorithm for a signer by index
func sigAlg(s crypto.Signer, i int) x509.SignatureAlgorithm {
	switch s.(type) {
	case *ecdsa.PrivateKey:
		return []x509.SignatureAlgorithm{x509.ECDSAWithSHA256, x509.ECDSAWithSHA384, x509.ECDSAWithSHA512}[i%3]
	case *rsa.PrivateKey:
		return []x509.SignatureAlgorithm{x509.SHA256WithRSA, x509.SHA384WithRSA, x509.SHA512WithRSA,
			x509.SHA256WithRSAPSS, x509.SHA384WithRSAPSS, x509.SHA512WithRSAPSS}[i%6]
	}
	return x509.PureEd25519
}

// ---- certificates ----

type node struct {
	der  []byte
	cert *x509.Certificate
	key  crypto.Signer
}

func create(tmpl *x509.Certificate, parent *node, k crypto.Signer) *node {
	if tmpl.SerialNumber == nil {
		tmpl.SerialNumber = nextSerial()
	}
	if tmpl.NotBefore.IsZero() {
		tmpl.NotBefore = NB
	}
	if tmpl.NotAfter.IsZero() {
		tmpl.NotAfter = NA
	}
	var pc *x509.Certificate
	var signer crypto.Signer
	if parent == nil {
		pc = tmpl
		signer = k
	} else {
		pc = parent.cert
		signer = parent.key
	}
	der, err := x509.CreateCertificate(rand.Reader, tmpl, pc, k.Public(), signer)
	if err != nil {
		panic(fmt.Sprintf("%s: %v", tmpl.Subject.CommonName, err))
	}
	c, err := x509.ParseCertificate(der)
	if err != nil {
		panic(err)
	}
	return &node{der, c, k}
}

func rootT(cn string) *x509.Certificate {
	return &x509.Certificate{
		Subject:               pkix.Name{CommonName: cn, Organization: []string{"Test PKI"}},
		IsCA:                  true,
		BasicConstraintsValid: true,
		KeyUsage:              x509.KeyUsageCertSign | x509.KeyUsageCRLSign,
	}
}

func interT(cn string) *x509.Certificate {
	t := rootT(cn)
	t.ExtKeyUsage = nil
	return t
}

func leafT(cn string, dns []string, ips []string) *x509.Certificate {
	t := &x509.Certificate{
		Subject:               pkix.Name{CommonName: cn},
		KeyUsage:              x509.KeyUsageDigitalSignature,
		ExtKeyUsage:           []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
		BasicConstraintsValid: true,
		DNSNames:              dns,
	}
	for _, s := range ips {
		t.IPAddresses = append(t.IPAddresses, net.ParseIP(s))
	}
	return t
}

func mkRoot(cn string, k crypto.Signer, i int) *node {
	t := rootT(cn)
	t.SignatureAlgorithm = sigAlg(k, i)
	return create(t, nil, k)
}

func mkInter(cn string, parent *node, k crypto.Signer, i int) *node {
	t := interT(cn)
	t.SignatureAlgorithm = sigAlg(parent.key, i)
	return create(t, parent, k)
}

func mkLeaf(t *x509.Certificate, parent *node, k crypto.Signer, i int) *node {
	t.SignatureAlgorithm = sigAlg(parent.key, i)
	return create(t, parent, k)
}

// ---- hand-built DER ----

func tlv(tag byte, parts ...[]byte) []byte {
	var c []byte
	for _, p := range parts {
		c = append(c, p...)
	}
	n := len(c)
	out := []byte{tag}
	switch {
	case n < 128:
		out = append(out, byte(n))
	case n < 256:
		out = append(out, 0x81, byte(n))
	case n < 65536:
		out = append(out, 0x82, byte(n>>8), byte(n))
	default:
		out = append(out, 0x83, byte(n>>16), byte(n>>8), byte(n))
	}
	return append(out, c...)
}

func mustMarshal(v any) []byte {
	b, err := asn1.Marshal(v)
	if err != nil {
		panic(err)
	}
	return b
}

func nameDER(cn string) []byte {
	return mustMarshal(pkix.Name{CommonName: cn}.ToRDNSequence())
}

func oidDER(o asn1.ObjectIdentifier) []byte { return mustMarshal(o) }

func intDER(v int64) []byte { return mustMarshal(v) }

func utc(t time.Time) []byte { return tlv(0x17, []byte(t.UTC().Format("060102150405Z"))) }

type ext struct {
	oid      asn1.ObjectIdentifier
	critical bool
	value    []byte
}

func extDER(e ext) []byte {
	parts := [][]byte{oidDER(e.oid)}
	if e.critical {
		parts = append(parts, []byte{1, 1, 0xff})
	}
	parts = append(parts, tlv(4, e.value))
	return tlv(0x30, parts...)
}

var (
	oidBC   = asn1.ObjectIdentifier{2, 5, 29, 19}
	oidKU   = asn1.ObjectIdentifier{2, 5, 29, 15}
	oidSAN  = asn1.ObjectIdentifier{2, 5, 29, 17}
	oidSKI  = asn1.ObjectIdentifier{2, 5, 29, 14}
	oidAKI  = asn1.ObjectIdentifier{2, 5, 29, 35}
	oidNC   = asn1.ObjectIdentifier{2, 5, 29, 30}
	oidCP   = asn1.ObjectIdentifier{2, 5, 29, 32}
	oidPC   = asn1.ObjectIdentifier{2, 5, 29, 36}
	oidPM   = asn1.ObjectIdentifier{2, 5, 29, 33}
	oidIAP  = asn1.ObjectIdentifier{2, 5, 29, 54}
	oidEKU  = asn1.ObjectIdentifier{2, 5, 29, 37}
	oidCRL  = asn1.ObjectIdentifier{2, 5, 29, 31}
	oidAIA  = asn1.ObjectIdentifier{1, 3, 6, 1, 5, 5, 7, 1, 1}
	oidPol1 = asn1.ObjectIdentifier{1, 3, 6, 1, 4, 1, 99999, 1}
	oidPol2 = asn1.ObjectIdentifier{1, 3, 6, 1, 4, 1, 99999, 2}
	oidAny  = asn1.ObjectIdentifier{2, 5, 29, 32, 0}
)

func bcExt(ca bool, mpl int) ext {
	var parts [][]byte
	if ca {
		parts = append(parts, []byte{1, 1, 0xff})
	}
	if mpl >= 0 {
		parts = append(parts, intDER(int64(mpl)))
	}
	return ext{oidBC, true, tlv(0x30, parts...)}
}

func kuExt(bits byte) ext {
	return ext{oidKU, true, []byte{3, 2, 0, bits}}
}

func sanDNS(names ...string) ext {
	var parts [][]byte
	for _, n := range names {
		parts = append(parts, tlv(0x82, []byte(n)))
	}
	return ext{oidSAN, false, tlv(0x30, parts...)}
}

func spkiOf(k crypto.Signer) []byte {
	b, err := x509.MarshalPKIXPublicKey(k.Public())
	if err != nil {
		panic(err)
	}
	return b
}

func skiOf(k crypto.Signer) []byte {
	var s struct {
		A asn1.RawValue
		B asn1.BitString
	}
	asn1.Unmarshal(spkiOf(k), &s)
	h := sha1.Sum(s.B.Bytes)
	return h[:]
}

// raw describes a certificate built by hand
type raw struct {
	version   int // -1: none (v1)
	serial    []byte
	sigOID    asn1.ObjectIdentifier
	sigNull   bool
	issuer    []byte
	subject   []byte
	notBefore []byte
	notAfter  []byte
	key       crypto.Signer // the subject's key
	exts      []ext
	hash      crypto.Hash
	pss       bool
	outerAlg  []byte // nil: same as inner
	trailing  []byte // after the certificate
	spki      []byte // nil: the key's
}

func algDER(r *raw) []byte {
	if r.pss {
		return pssAlg(r.hash)
	}
	if r.sigNull {
		return tlv(0x30, oidDER(r.sigOID), []byte{5, 0})
	}
	return tlv(0x30, oidDER(r.sigOID))
}

func pssAlg(h crypto.Hash) []byte {
	var ho asn1.ObjectIdentifier
	salt := int64(32)
	switch h {
	case crypto.SHA256:
		ho = asn1.ObjectIdentifier{2, 16, 840, 1, 101, 3, 4, 2, 1}
	case crypto.SHA384:
		ho = asn1.ObjectIdentifier{2, 16, 840, 1, 101, 3, 4, 2, 2}
		salt = 48
	default:
		ho = asn1.ObjectIdentifier{2, 16, 840, 1, 101, 3, 4, 2, 3}
		salt = 64
	}
	hashAI := tlv(0x30, oidDER(ho), []byte{5, 0})
	mgf := tlv(0x30, oidDER(asn1.ObjectIdentifier{1, 2, 840, 113549, 1, 1, 8}), hashAI)
	params := tlv(0x30, tlv(0xa0, hashAI), tlv(0xa1, mgf), tlv(0xa2, intDER(salt)))
	return tlv(0x30, oidDER(asn1.ObjectIdentifier{1, 2, 840, 113549, 1, 1, 10}), params)
}

func build(r *raw, signer crypto.Signer) []byte {
	var parts [][]byte
	if r.version >= 0 {
		parts = append(parts, tlv(0xa0, intDER(int64(r.version))))
	}
	if r.serial == nil {
		r.serial = mustMarshal(nextSerial())
	}
	parts = append(parts, r.serial, algDER(r), r.issuer)
	nb, na := r.notBefore, r.notAfter
	if nb == nil {
		nb = utc(NB)
	}
	if na == nil {
		na = utc(NA)
	}
	sp := r.spki
	if sp == nil {
		sp = spkiOf(r.key)
	}
	parts = append(parts, tlv(0x30, nb, na), r.subject, sp)
	if len(r.exts) > 0 {
		var es [][]byte
		for _, e := range r.exts {
			es = append(es, extDER(e))
		}
		parts = append(parts, tlv(0xa3, tlv(0x30, es...)))
	}
	tbs := tlv(0x30, parts...)
	var digest []byte
	switch r.hash {
	case crypto.MD5:
		h := md5.Sum(tbs)
		digest = h[:]
	case crypto.SHA1:
		h := sha1.Sum(tbs)
		digest = h[:]
	default:
		hh := r.hash.New()
		hh.Write(tbs)
		digest = hh.Sum(nil)
	}
	var sig []byte
	var err error
	switch k := signer.(type) {
	case *rsa.PrivateKey:
		if r.pss {
			sig, err = rsa.SignPSS(rand.Reader, k, r.hash, digest, &rsa.PSSOptions{SaltLength: rsa.PSSSaltLengthEqualsHash})
		} else {
			sig, err = rsa.SignPKCS1v15(rand.Reader, k, r.hash, digest)
		}
	case *ecdsa.PrivateKey:
		sig, err = ecdsa.SignASN1(rand.Reader, k, digest)
	}
	if err != nil {
		panic(err)
	}
	outer := r.outerAlg
	if outer == nil {
		outer = algDER(r)
	}
	der := tlv(0x30, tbs, outer, tlv(3, []byte{0}, sig))
	return append(der, r.trailing...)
}

// ---- output ----

type tc struct {
	name   string
	leaf   []byte
	inters [][]byte
	roots  [][]byte
	host   string
	t      time.Time
	ekus   []x509.ExtKeyUsage
}

var out = os.Stdout
var ncases int

func verdict(c tc) string {
	leaf, err := x509.ParseCertificate(c.leaf)
	if err != nil {
		return "err " + err.Error()
	}
	inter := x509.NewCertPool()
	for _, d := range c.inters {
		ic, err := x509.ParseCertificate(d)
		if err != nil {
			return "err " + err.Error()
		}
		inter.AddCert(ic)
	}
	roots := x509.NewCertPool()
	for _, d := range c.roots {
		rc, err := x509.ParseCertificate(d)
		if err != nil {
			continue
		}
		roots.AddCert(rc)
	}
	_, err = leaf.Verify(x509.VerifyOptions{
		DNSName:       c.host,
		Intermediates: inter,
		Roots:         roots,
		CurrentTime:   c.t,
		KeyUsages:     c.ekus,
	})
	if err != nil {
		return "err " + err.Error()
	}
	return "ok"
}

func emit(c tc) {
	ncases++
	if c.t.IsZero() {
		c.t = T0
	}
	fmt.Fprintf(out, "case %d %s\n", ncases, c.name)
	fmt.Fprintf(out, "time %d\n", c.t.Unix())
	h := c.host
	if h == "" {
		h = "-"
	}
	fmt.Fprintf(out, "host %s\n", h)
	if c.ekus == nil {
		fmt.Fprintf(out, "eku -\n")
	} else {
		var s []string
		for _, e := range c.ekus {
			s = append(s, strconv.Itoa(int(e)))
		}
		fmt.Fprintf(out, "eku %s\n", strings.Join(s, ","))
	}
	fmt.Fprintf(out, "leaf %s\n", hex.EncodeToString(c.leaf))
	for _, d := range c.inters {
		fmt.Fprintf(out, "inter %s\n", hex.EncodeToString(d))
	}
	for _, d := range c.roots {
		fmt.Fprintf(out, "root %s\n", hex.EncodeToString(d))
	}
	fmt.Fprintf(out, "want %s\n", verdict(c))
	fmt.Fprintf(out, "end\n")
}

func emitHost(name string, n *node, host string) {
	ncases++
	fmt.Fprintf(out, "vh %d %s\n", ncases, name)
	fmt.Fprintf(out, "leaf %s\n", hex.EncodeToString(n.der))
	fmt.Fprintf(out, "host %s\n", host)
	if err := n.cert.VerifyHostname(host); err != nil {
		fmt.Fprintf(out, "want err %s\n", err.Error())
	} else {
		fmt.Fprintf(out, "want ok\n")
	}
	fmt.Fprintf(out, "end\n")
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

func b2i(b bool) string {
	if b {
		return "1"
	}
	return "0"
}

func emitParse(name string, der []byte) {
	ncases++
	fmt.Fprintf(out, "parse %d %s\n", ncases, name)
	fmt.Fprintf(out, "leaf %s\n", hex.EncodeToString(der))
	c, err := x509.ParseCertificate(der)
	if err != nil {
		fmt.Fprintf(out, "want err %s\n", err.Error())
	} else {
		fmt.Fprintf(out, "want ok %s\n", summary(c))
	}
	fmt.Fprintf(out, "end\n")
}

// ---- the cases ----

func main() {
	matrix()
	special()
	constraints()
	hostnames()
	parses()
	fmt.Fprintf(os.Stderr, "cases %d\n", ncases)
}

// matrix: every combination of root, intermediate and leaf key, with
// the signature hash turning over, in eight situations each
func matrix() {
	idx := 0
	for rk := kP256; rk <= kRSA; rk++ {
		for ik := kP256; ik <= kRSA; ik++ {
			for lk := kP256; lk <= kRSA; lk++ {
				idx++
				tag := kindName[rk] + "-" + kindName[ik] + "-" + kindName[lk]
				dom := fmt.Sprintf("example%d.com", idx)
				root := mkRoot("Root "+tag, key(rk), idx)
				inter := mkInter("Inter "+tag, root, key(ik), idx+1)
				lt := leafT("www."+dom, []string{"www." + dom, "*." + dom}, []string{fmt.Sprintf("10.0.%d.1", idx), fmt.Sprintf("2001:db8::%x", idx)})
				leaf := mkLeaf(lt, inter, key(lk), idx+2)
				in := [][]byte{inter.der}
				rs := [][]byte{root.der}
				emit(tc{name: "matrix-ok-" + tag, leaf: leaf.der, inters: in, roots: rs, host: "www." + dom})
				emit(tc{name: "matrix-wild-" + tag, leaf: leaf.der, inters: in, roots: rs, host: "Api." + dom + "."})
				emit(tc{name: "matrix-wrong-host-" + tag, leaf: leaf.der, inters: in, roots: rs, host: "a.b." + dom})
				emit(tc{name: "matrix-expired-" + tag, leaf: leaf.der, inters: in, roots: rs, host: "www." + dom, t: NA.Add(time.Second)})
				emit(tc{name: "matrix-notyet-" + tag, leaf: leaf.der, inters: in, roots: rs, host: "www." + dom, t: NB.Add(-time.Hour)})
				emit(tc{name: "matrix-no-inter-" + tag, leaf: leaf.der, roots: rs, host: "www." + dom})
				emit(tc{name: "matrix-ip-" + tag, leaf: leaf.der, inters: in, roots: rs, host: fmt.Sprintf("10.0.%d.1", idx)})
				emit(tc{name: "matrix-ip6-" + tag, leaf: leaf.der, inters: in, roots: rs, host: fmt.Sprintf("[2001:db8::%x]", idx)})
				emit(tc{name: "matrix-ip-wrong-" + tag, leaf: leaf.der, inters: in, roots: rs, host: "192.0.2.7"})
				emit(tc{name: "matrix-noroot-" + tag, leaf: leaf.der, inters: in, roots: nil, host: "www." + dom})
			}
		}
	}
}

func special() {
	pk := func() crypto.Signer { return key(kP256) }
	root := mkRoot("Special Root", key(kP384), 0)
	inter := mkInter("Special Inter", root, pk(), 0)
	lt := func(cn string) *x509.Certificate { return leafT(cn, []string{cn}, nil) }
	rs := [][]byte{root.der}

	// boundaries of time
	leaf := mkLeaf(lt("time.test"), inter, pk(), 0)
	emit(tc{name: "time-at-notafter", leaf: leaf.der, inters: [][]byte{inter.der}, roots: rs, host: "time.test", t: NA})
	emit(tc{name: "time-at-notbefore", leaf: leaf.der, inters: [][]byte{inter.der}, roots: rs, host: "time.test", t: NB})
	emit(tc{name: "time-before-notbefore", leaf: leaf.der, inters: [][]byte{inter.der}, roots: rs, host: "time.test", t: NB.Add(-time.Second)})
	// a validity past 2049 is a GeneralizedTime
	gt := lt("gentime.test")
	gt.NotAfter = time.Date(2060, 3, 1, 0, 0, 0, 0, time.UTC)
	leafG := mkLeaf(gt, inter, pk(), 0)
	emit(tc{name: "generalized-time-ok", leaf: leafG.der, inters: [][]byte{inter.der}, roots: rs, host: "gentime.test"})
	emit(tc{name: "generalized-time-expired", leaf: leafG.der, inters: [][]byte{inter.der}, roots: rs, host: "gentime.test", t: time.Date(2061, 1, 1, 0, 0, 0, 0, time.UTC)})

	// an expired intermediate, a not yet valid one, an expired root
	it := interT("Expired Inter")
	it.NotAfter = time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	it.SignatureAlgorithm = x509.ECDSAWithSHA384
	interX := create(it, root, pk())
	leafX := mkLeaf(lt("x.test"), interX, pk(), 0)
	emit(tc{name: "expired-intermediate", leaf: leafX.der, inters: [][]byte{interX.der}, roots: rs, host: "x.test"})
	it2 := interT("Future Inter")
	it2.NotBefore = time.Date(2027, 1, 1, 0, 0, 0, 0, time.UTC)
	interF := create(it2, root, pk())
	leafF := mkLeaf(lt("f.test"), interF, pk(), 0)
	emit(tc{name: "future-intermediate", leaf: leafF.der, inters: [][]byte{interF.der}, roots: rs, host: "f.test"})
	rt := rootT("Expired Root")
	rt.NotAfter = time.Date(2026, 2, 1, 0, 0, 0, 0, time.UTC)
	rootX := create(rt, nil, pk())
	leafRX := mkLeaf(lt("rx.test"), rootX, pk(), 0)
	emit(tc{name: "expired-root", leaf: leafRX.der, roots: [][]byte{rootX.der}, host: "rx.test"})
	// expired leaf and expired intermediate: the leaf is checked first
	elt := lt("both.test")
	elt.NotAfter = time.Date(2026, 3, 1, 0, 0, 0, 0, time.UTC)
	leafEB := mkLeaf(elt, interX, pk(), 0)
	emit(tc{name: "expired-leaf-and-intermediate", leaf: leafEB.der, inters: [][]byte{interX.der}, roots: rs, host: "both.test"})

	// leaf directly under the root, and the leaf as its own root
	leafR := mkLeaf(lt("direct.test"), root, pk(), 1)
	emit(tc{name: "leaf-under-root", leaf: leafR.der, roots: rs, host: "direct.test"})
	selfT := lt("self.test")
	selfT.SignatureAlgorithm = x509.ECDSAWithSHA256
	self := create(selfT, nil, pk())
	emit(tc{name: "self-signed-unknown", leaf: self.der, roots: rs, host: "self.test"})
	emit(tc{name: "self-signed-in-roots", leaf: self.der, roots: [][]byte{self.der}, host: "self.test"})
	emit(tc{name: "self-signed-in-roots-wrong-host", leaf: self.der, roots: [][]byte{self.der}, host: "other.test"})
	selfCA := rootT("selfca.test")
	selfCA.DNSNames = []string{"selfca.test"}
	selfCAn := create(selfCA, nil, pk())
	emit(tc{name: "self-signed-ca-leaf-in-roots", leaf: selfCAn.der, roots: [][]byte{selfCAn.der}, host: "selfca.test"})

	// path length
	r0 := rootT("PathLen0 Root")
	r0.MaxPathLenZero = true
	r0.MaxPathLen = 0
	root0 := create(r0, nil, pk())
	i0 := mkInter("PathLen0 Inter", root0, pk(), 0)
	l0 := mkLeaf(lt("pl0.test"), i0, pk(), 0)
	emit(tc{name: "pathlen0-with-intermediate", leaf: l0.der, inters: [][]byte{i0.der}, roots: [][]byte{root0.der}, host: "pl0.test"})
	l0d := mkLeaf(lt("pl0d.test"), root0, pk(), 0)
	emit(tc{name: "pathlen0-direct", leaf: l0d.der, roots: [][]byte{root0.der}, host: "pl0d.test"})
	r1 := rootT("PathLen1 Root")
	r1.MaxPathLen = 1
	root1 := create(r1, nil, pk())
	i1a := mkInter("PathLen1 Inter A", root1, pk(), 0)
	i1b := mkInter("PathLen1 Inter B", i1a, pk(), 0)
	l1 := mkLeaf(lt("pl1.test"), i1b, pk(), 0)
	emit(tc{name: "pathlen1-two-intermediates", leaf: l1.der, inters: [][]byte{i1b.der, i1a.der}, roots: [][]byte{root1.der}, host: "pl1.test"})
	l1ok := mkLeaf(lt("pl1ok.test"), i1a, pk(), 0)
	emit(tc{name: "pathlen1-one-intermediate", leaf: l1ok.der, inters: [][]byte{i1a.der}, roots: [][]byte{root1.der}, host: "pl1ok.test"})
	ip0 := interT("Inter PathLen0")
	ip0.MaxPathLenZero = true
	inter0 := create(ip0, root, pk())
	sub0 := mkInter("Below PathLen0", inter0, pk(), 0)
	lsub := mkLeaf(lt("sub0.test"), sub0, pk(), 0)
	emit(tc{name: "intermediate-pathlen0-below", leaf: lsub.der, inters: [][]byte{sub0.der, inter0.der}, roots: rs, host: "sub0.test"})

	// a long chain of five intermediates
	prev := root
	var chainDer [][]byte
	for i := 0; i < 5; i++ {
		prev = mkInter(fmt.Sprintf("Long Inter %d", i), prev, key(kind(i%3)), i)
		chainDer = append([][]byte{prev.der}, chainDer...)
	}
	llong := mkLeaf(lt("long.test"), prev, pk(), 0)
	emit(tc{name: "long-chain", leaf: llong.der, inters: chainDer, roots: rs, host: "long.test"})
	shuffled := [][]byte{chainDer[2], chainDer[4], chainDer[0], chainDer[3], chainDer[1]}
	emit(tc{name: "long-chain-shuffled", leaf: llong.der, inters: shuffled, roots: rs, host: "long.test"})
	emit(tc{name: "long-chain-gap", leaf: llong.der, inters: [][]byte{chainDer[0], chainDer[1], chainDer[3], chainDer[4]}, roots: rs, host: "long.test"})

	// key usage of the issuer: no certSign
	ku := interT("NoCertSign Inter")
	ku.KeyUsage = x509.KeyUsageDigitalSignature
	interKU := create(ku, root, pk())
	lku := mkLeaf(lt("ku.test"), interKU, pk(), 0)
	emit(tc{name: "issuer-without-certsign", leaf: lku.der, inters: [][]byte{interKU.der}, roots: rs, host: "ku.test"})
	// the issuer is not a CA
	nca := interT("NotCA Inter")
	nca.IsCA = false
	interNCA := create(nca, root, pk())
	lnca := mkLeaf(lt("nca.test"), interNCA, pk(), 0)
	emit(tc{name: "issuer-not-ca", leaf: lnca.der, inters: [][]byte{interNCA.der}, roots: rs, host: "nca.test"})
	// the issuer without basic constraints at all (v3)
	nbc := interT("NoBC Inter")
	nbc.BasicConstraintsValid = false
	nbc.IsCA = false
	interNBC := create(nbc, root, pk())
	lnbc := mkLeaf(lt("nbc.test"), interNBC, pk(), 0)
	emit(tc{name: "issuer-without-basic-constraints", leaf: lnbc.der, inters: [][]byte{interNBC.der}, roots: rs, host: "nbc.test"})

	// extended key usage
	cl := lt("client.test")
	cl.ExtKeyUsage = []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth}
	lcl := mkLeaf(cl, inter, pk(), 0)
	emit(tc{name: "leaf-client-auth-only", leaf: lcl.der, inters: [][]byte{inter.der}, roots: rs, host: "client.test"})
	emit(tc{name: "leaf-client-auth-asked-client", leaf: lcl.der, inters: [][]byte{inter.der}, roots: rs, host: "client.test", ekus: []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth}})
	emit(tc{name: "leaf-client-auth-asked-any", leaf: lcl.der, inters: [][]byte{inter.der}, roots: rs, host: "client.test", ekus: []x509.ExtKeyUsage{x509.ExtKeyUsageAny}})
	ne := lt("noeku.test")
	ne.ExtKeyUsage = nil
	lne := mkLeaf(ne, inter, pk(), 0)
	emit(tc{name: "leaf-without-eku", leaf: lne.der, inters: [][]byte{inter.der}, roots: rs, host: "noeku.test"})
	ae := lt("anyeku.test")
	ae.ExtKeyUsage = []x509.ExtKeyUsage{x509.ExtKeyUsageAny}
	lae := mkLeaf(ae, inter, pk(), 0)
	emit(tc{name: "leaf-eku-any", leaf: lae.der, inters: [][]byte{inter.der}, roots: rs, host: "anyeku.test"})
	ue := lt("unknowneku.test")
	ue.ExtKeyUsage = nil
	ue.UnknownExtKeyUsage = []asn1.ObjectIdentifier{{1, 2, 3, 4}}
	lue := mkLeaf(ue, inter, pk(), 0)
	emit(tc{name: "leaf-unknown-eku-only", leaf: lue.der, inters: [][]byte{inter.der}, roots: rs, host: "unknowneku.test"})
	ie := interT("ClientOnly Inter")
	ie.ExtKeyUsage = []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth}
	interCE := create(ie, root, pk())
	lie := mkLeaf(lt("ieku.test"), interCE, pk(), 0)
	emit(tc{name: "intermediate-eku-client-only", leaf: lie.der, inters: [][]byte{interCE.der}, roots: rs, host: "ieku.test"})
	ie2 := interT("ServerClient Inter")
	ie2.ExtKeyUsage = []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth, x509.ExtKeyUsageClientAuth}
	interSC := create(ie2, root, pk())
	lie2 := mkLeaf(lt("ieku2.test"), interSC, pk(), 0)
	emit(tc{name: "intermediate-eku-server-client", leaf: lie2.der, inters: [][]byte{interSC.der}, roots: rs, host: "ieku2.test"})
	emit(tc{name: "intermediate-eku-asked-two", leaf: lie.der, inters: [][]byte{interCE.der}, roots: rs, host: "ieku.test", ekus: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth, x509.ExtKeyUsageClientAuth}})

	// an unknown critical extension
	uc := lt("crit.test")
	uc.ExtraExtensions = []pkix.Extension{{Id: asn1.ObjectIdentifier{1, 2, 3, 4, 5}, Critical: true, Value: []byte{5, 0}}}
	luc := mkLeaf(uc, inter, pk(), 0)
	emit(tc{name: "leaf-unknown-critical", leaf: luc.der, inters: [][]byte{inter.der}, roots: rs, host: "crit.test"})
	unc := lt("noncrit.test")
	unc.ExtraExtensions = []pkix.Extension{{Id: asn1.ObjectIdentifier{1, 2, 3, 4, 5}, Critical: false, Value: []byte{5, 0}}}
	lunc := mkLeaf(unc, inter, pk(), 0)
	emit(tc{name: "leaf-unknown-noncritical", leaf: lunc.der, inters: [][]byte{inter.der}, roots: rs, host: "noncrit.test"})
	icr := interT("Critical Inter")
	icr.ExtraExtensions = []pkix.Extension{{Id: asn1.ObjectIdentifier{1, 2, 3, 4, 6}, Critical: true, Value: []byte{5, 0}}}
	interCR := create(icr, root, pk())
	licr := mkLeaf(lt("icrit.test"), interCR, pk(), 0)
	emit(tc{name: "intermediate-unknown-critical", leaf: licr.der, inters: [][]byte{interCR.der}, roots: rs, host: "icrit.test"})
	rcr := rootT("Critical Root")
	rcr.ExtraExtensions = []pkix.Extension{{Id: asn1.ObjectIdentifier{2, 5, 29, 99}, Critical: true, Value: []byte{5, 0}}}
	rootCR := create(rcr, nil, pk())
	lrcr := mkLeaf(lt("rcrit.test"), rootCR, pk(), 0)
	emit(tc{name: "root-unknown-critical", leaf: lrcr.der, roots: [][]byte{rootCR.der}, host: "rcrit.test"})

	// wrong signatures: an issuer of the same name with another key
	impostorRoot := mkRoot("Special Root", pk(), 0)
	emit(tc{name: "root-same-name-other-key", leaf: leafR.der, roots: [][]byte{impostorRoot.der}, host: "direct.test"})
	emit(tc{name: "two-roots-same-name", leaf: leafR.der, roots: [][]byte{impostorRoot.der, root.der}, host: "direct.test"})
	rsaRoot := mkRoot("RSA Name Root", key(kRSA), 0)
	rsaImp := mkRoot("RSA Name Root", key(kRSA), 1)
	lrsa := mkLeaf(lt("rsaimp.test"), rsaRoot, pk(), 0)
	emit(tc{name: "rsa-root-other-key", leaf: lrsa.der, roots: [][]byte{rsaImp.der}, host: "rsaimp.test"})
	impInter := mkInter("Special Inter", root, pk(), 0)
	emit(tc{name: "intermediate-same-name-other-key", leaf: leaf.der, inters: [][]byte{impInter.der}, roots: rs, host: "time.test"})
	emit(tc{name: "intermediates-impostor-first", leaf: leaf.der, inters: [][]byte{impInter.der, inter.der}, roots: rs, host: "time.test"})

	// a root whose key does not match the signature algorithm family
	ecRoot := mkRoot("Family Root", pk(), 0)
	rsaFam := mkRoot("Family Root", key(kRSA), 0)
	lfam := mkLeaf(lt("fam.test"), rsaFam, pk(), 0)
	emit(tc{name: "signature-family-mismatch", leaf: lfam.der, roots: [][]byte{ecRoot.der}, host: "fam.test"})

	// Ed25519 and P-521 leaves (their keys are not used to verify)
	_, edPriv, _ := ed25519.GenerateKey(rand.Reader)
	led := mkLeaf(lt("ed.test"), inter, edPriv, 0)
	emit(tc{name: "ed25519-leaf", leaf: led.der, inters: [][]byte{inter.der}, roots: rs, host: "ed.test"})
	p521, _ := ecdsa.GenerateKey(elliptic.P521(), rand.Reader)
	l521 := mkLeaf(lt("p521.test"), inter, p521, 0)
	emit(tc{name: "p521-leaf", leaf: l521.der, inters: [][]byte{inter.der}, roots: rs, host: "p521.test"})

	// legacy common name and missing names
	cn := &x509.Certificate{Subject: pkix.Name{CommonName: "legacy.test"}, ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}}
	lcn := mkLeaf(cn, inter, pk(), 0)
	emit(tc{name: "legacy-common-name", leaf: lcn.der, inters: [][]byte{inter.der}, roots: rs, host: "legacy.test"})
	emit(tc{name: "legacy-common-name-other", leaf: lcn.der, inters: [][]byte{inter.der}, roots: rs, host: "other.test"})
	emit(tc{name: "no-names-ip-host", leaf: lcn.der, inters: [][]byte{inter.der}, roots: rs, host: "10.1.2.3"})
	emit(tc{name: "no-host-asked", leaf: lcn.der, inters: [][]byte{inter.der}, roots: rs, host: ""})
	ipOnly := leafT("iponly", nil, []string{"192.0.2.1", "::1"})
	lip := mkLeaf(ipOnly, inter, pk(), 0)
	emit(tc{name: "ip-only-dns-host", leaf: lip.der, inters: [][]byte{inter.der}, roots: rs, host: "iponly.test"})
	emit(tc{name: "ip-only-v6-loopback", leaf: lip.der, inters: [][]byte{inter.der}, roots: rs, host: "::1"})
	emit(tc{name: "ip-only-v4-mapped", leaf: lip.der, inters: [][]byte{inter.der}, roots: rs, host: "::ffff:192.0.2.1"})
	emit(tc{name: "ip-only-wrong", leaf: lip.der, inters: [][]byte{inter.der}, roots: rs, host: "192.0.2.2"})
	emit(tc{name: "ip-only-zone", leaf: lip.der, inters: [][]byte{inter.der}, roots: rs, host: "fe80::1%eth0"})

	// cross-signed loop: A signs B and B signs A; the leaf under B
	ka, kb := pk(), pk()
	ra := mkRoot("Loop A", ka, 0)
	rb := mkRoot("Loop B", kb, 0)
	aByB := create(interT("Loop A"), rb, ka)
	bByA := create(interT("Loop B"), ra, kb)
	lloop := mkLeaf(lt("loop.test"), bByA, pk(), 0)
	emit(tc{name: "cross-signed-loop-no-root", leaf: lloop.der, inters: [][]byte{aByB.der, bByA.der}, roots: rs, host: "loop.test"})
	emit(tc{name: "cross-signed-loop-root-b", leaf: lloop.der, inters: [][]byte{aByB.der, bByA.der}, roots: [][]byte{rb.der}, host: "loop.test"})

	// the signature check limit: many issuers of one name, none right
	var many [][]byte
	for i := 0; i < 105; i++ {
		many = append(many, mkInter("Crowded Inter", root, pk(), 0).der)
	}
	crowdedSigner := mkInter("Crowded Inter", root, pk(), 0)
	lcrowd := mkLeaf(lt("crowd.test"), crowdedSigner, pk(), 0)
	emit(tc{name: "signature-check-limit", leaf: lcrowd.der, inters: many, roots: rs, host: "crowd.test"})
	emit(tc{name: "signature-check-few", leaf: lcrowd.der, inters: append(append([][]byte{}, many[:20]...), crowdedSigner.der), roots: rs, host: "crowd.test"})

	// hand-built: SHA-1 and MD5 signatures, a v1 intermediate, UTCTime
	// with an offset, policy constraints
	rk := key(kRSA)
	rsaR := mkRoot("Hand Root", rk, 0)
	hlKey := pk()
	sha1Leaf := build(&raw{version: 2, sigOID: asn1.ObjectIdentifier{1, 2, 840, 113549, 1, 1, 5}, sigNull: true,
		issuer: rsaR.cert.RawSubject, subject: nameDER("sha1.test"), key: hlKey, hash: crypto.SHA1,
		exts: []ext{sanDNS("sha1.test")}}, rk)
	emit(tc{name: "sha1-rsa-signature", leaf: sha1Leaf, roots: [][]byte{rsaR.der}, host: "sha1.test"})
	md5Leaf := build(&raw{version: 2, sigOID: asn1.ObjectIdentifier{1, 2, 840, 113549, 1, 1, 4}, sigNull: true,
		issuer: rsaR.cert.RawSubject, subject: nameDER("md5.test"), key: hlKey, hash: crypto.MD5,
		exts: []ext{sanDNS("md5.test")}}, rk)
	emit(tc{name: "md5-rsa-signature", leaf: md5Leaf, roots: [][]byte{rsaR.der}, host: "md5.test"})
	ecKey := pk()
	ecR := mkRoot("Hand EC Root", ecKey, 0)
	sha1EC := build(&raw{version: 2, sigOID: asn1.ObjectIdentifier{1, 2, 840, 10045, 4, 1},
		issuer: ecR.cert.RawSubject, subject: nameDER("sha1ec.test"), key: hlKey, hash: crypto.SHA1,
		exts: []ext{sanDNS("sha1ec.test")}}, ecKey)
	emit(tc{name: "sha1-ecdsa-signature", leaf: sha1EC, roots: [][]byte{ecR.der}, host: "sha1ec.test"})
	pssLeaf := build(&raw{version: 2, issuer: rsaR.cert.RawSubject, subject: nameDER("pss.test"), key: hlKey,
		hash: crypto.SHA384, pss: true, exts: []ext{sanDNS("pss.test")}}, rk)
	emit(tc{name: "pss-sha384-hand", leaf: pssLeaf, roots: [][]byte{rsaR.der}, host: "pss.test"})
	ikV1 := pk()
	v1Inter := build(&raw{version: -1, sigOID: asn1.ObjectIdentifier{1, 2, 840, 113549, 1, 1, 11}, sigNull: true,
		issuer: rsaR.cert.RawSubject, subject: nameDER("V1 Inter"), key: ikV1, hash: crypto.SHA256}, rk)
	v1Leaf := build(&raw{version: 2, sigOID: asn1.ObjectIdentifier{1, 2, 840, 10045, 4, 3, 2},
		issuer: nameDER("V1 Inter"), subject: nameDER("v1.test"), key: hlKey, hash: crypto.SHA256,
		exts: []ext{sanDNS("v1.test")}}, ikV1)
	emit(tc{name: "v1-intermediate", leaf: v1Leaf, inters: [][]byte{v1Inter}, roots: [][]byte{rsaR.der}, host: "v1.test"})
	v1Root := build(&raw{version: -1, sigOID: asn1.ObjectIdentifier{1, 2, 840, 10045, 4, 3, 2},
		issuer: nameDER("V1 Root"), subject: nameDER("V1 Root"), key: ecKey, hash: crypto.SHA256}, ecKey)
	v1RootLeaf := build(&raw{version: 2, sigOID: asn1.ObjectIdentifier{1, 2, 840, 10045, 4, 3, 2},
		issuer: nameDER("V1 Root"), subject: nameDER("v1root.test"), key: hlKey, hash: crypto.SHA256,
		exts: []ext{sanDNS("v1root.test")}}, ecKey)
	emit(tc{name: "v1-root", leaf: v1RootLeaf, roots: [][]byte{v1Root}, host: "v1root.test"})
	offLeaf := build(&raw{version: 2, sigOID: asn1.ObjectIdentifier{1, 2, 840, 10045, 4, 3, 2},
		issuer: ecR.cert.RawSubject, subject: nameDER("offset.test"), key: hlKey, hash: crypto.SHA256,
		notBefore: tlv(0x17, []byte("260615130000+0200")), notAfter: tlv(0x17, []byte("260615140000-0130")),
		exts: []ext{sanDNS("offset.test")}}, ecKey)
	emit(tc{name: "utc-offset-valid", leaf: offLeaf, roots: [][]byte{ecR.der}, host: "offset.test", t: time.Date(2026, 6, 15, 11, 30, 0, 0, time.UTC)})
	emit(tc{name: "utc-offset-before", leaf: offLeaf, roots: [][]byte{ecR.der}, host: "offset.test", t: time.Date(2026, 6, 15, 10, 59, 59, 0, time.UTC)})
	emit(tc{name: "utc-offset-after", leaf: offLeaf, roots: [][]byte{ecR.der}, host: "offset.test", t: time.Date(2026, 6, 15, 15, 30, 1, 0, time.UTC)})
	noSecLeaf := build(&raw{version: 2, sigOID: asn1.ObjectIdentifier{1, 2, 840, 10045, 4, 3, 2},
		issuer: ecR.cert.RawSubject, subject: nameDER("nosec.test"), key: hlKey, hash: crypto.SHA256,
		notBefore: tlv(0x17, []byte("2501010000Z")), notAfter: tlv(0x18, []byte("20351231235959Z")),
		exts: []ext{sanDNS("nosec.test")}}, ecKey)
	emit(tc{name: "utc-without-seconds", leaf: noSecLeaf, roots: [][]byte{ecR.der}, host: "nosec.test"})
	emit(tc{name: "generalized-end-expired", leaf: noSecLeaf, roots: [][]byte{ecR.der}, host: "nosec.test", t: time.Date(2036, 1, 1, 0, 0, 0, 0, time.UTC)})

	// policies (RFC 5280 6.1, RFC 9618)
	polRoot := mkRoot("Policy Root", ecKey, 0)
	pcExt := func(req int) ext {
		return ext{oidPC, true, tlv(0x30, tlv(0x80, []byte{byte(req)}))}
	}
	cpExt := func(oids ...asn1.ObjectIdentifier) ext {
		var ps [][]byte
		for _, o := range oids {
			ps = append(ps, tlv(0x30, oidDER(o)))
		}
		return ext{oidCP, false, tlv(0x30, ps...)}
	}
	iKey := pk()
	mkPolInter := func(name string, exts ...ext) []byte {
		all := append([]ext{bcExt(true, -1), kuExt(0x06), {oidSKI, false, tlv(4, skiOf(iKey))}}, exts...)
		return build(&raw{version: 2, sigOID: asn1.ObjectIdentifier{1, 2, 840, 10045, 4, 3, 2},
			issuer: polRoot.cert.RawSubject, subject: nameDER(name), key: iKey, hash: crypto.SHA256, exts: all}, ecKey)
	}
	mkPolLeaf := func(iname, host string, exts ...ext) []byte {
		all := append([]ext{sanDNS(host)}, exts...)
		return build(&raw{version: 2, sigOID: asn1.ObjectIdentifier{1, 2, 840, 10045, 4, 3, 2},
			issuer: nameDER(iname), subject: nameDER(host), key: hlKey, hash: crypto.SHA256, exts: all}, iKey)
	}
	prs := [][]byte{polRoot.der}
	pi1 := mkPolInter("Pol Require", pcExt(0))
	emit(tc{name: "policy-require-none", leaf: mkPolLeaf("Pol Require", "pol1.test"), inters: [][]byte{pi1}, roots: prs, host: "pol1.test"})
	emit(tc{name: "policy-require-leaf-has", leaf: mkPolLeaf("Pol Require", "pol2.test", cpExt(oidPol1)), inters: [][]byte{pi1}, roots: prs, host: "pol2.test"})
	pi2 := mkPolInter("Pol Require Has", pcExt(0), cpExt(oidPol1))
	emit(tc{name: "policy-both-same", leaf: mkPolLeaf("Pol Require Has", "pol3.test", cpExt(oidPol1)), inters: [][]byte{pi2}, roots: prs, host: "pol3.test"})
	emit(tc{name: "policy-both-different", leaf: mkPolLeaf("Pol Require Has", "pol4.test", cpExt(oidPol2)), inters: [][]byte{pi2}, roots: prs, host: "pol4.test"})
	pi3 := mkPolInter("Pol Any", pcExt(0), cpExt(oidAny))
	emit(tc{name: "policy-any-intermediate", leaf: mkPolLeaf("Pol Any", "pol5.test", cpExt(oidPol2)), inters: [][]byte{pi3}, roots: prs, host: "pol5.test"})
	pi4 := mkPolInter("Pol Inhibit Any", pcExt(0), cpExt(oidAny), ext{oidIAP, true, intDER(0)})
	emit(tc{name: "policy-inhibit-any", leaf: mkPolLeaf("Pol Inhibit Any", "pol6.test", cpExt(oidPol2)), inters: [][]byte{pi4}, roots: prs, host: "pol6.test"})
	pi5 := mkPolInter("Pol Require Later", pcExt(1))
	emit(tc{name: "policy-require-skip1", leaf: mkPolLeaf("Pol Require Later", "pol7.test"), inters: [][]byte{pi5}, roots: prs, host: "pol7.test"})
	pmExt := ext{oidPM, true, tlv(0x30, tlv(0x30, oidDER(oidPol1), oidDER(oidPol2)))}
	pi6 := mkPolInter("Pol Map", pcExt(0), cpExt(oidPol1), pmExt)
	emit(tc{name: "policy-mapped", leaf: mkPolLeaf("Pol Map", "pol8.test", cpExt(oidPol2)), inters: [][]byte{pi6}, roots: prs, host: "pol8.test"})
	emit(tc{name: "policy-mapped-wrong", leaf: mkPolLeaf("Pol Map", "pol9.test", cpExt(oidPol1)), inters: [][]byte{pi6}, roots: prs, host: "pol9.test"})
	pmAny := ext{oidPM, true, tlv(0x30, tlv(0x30, oidDER(oidAny), oidDER(oidPol2)))}
	pi7 := mkPolInter("Pol Map Any", cpExt(oidPol1), pmAny)
	emit(tc{name: "policy-map-anypolicy", leaf: mkPolLeaf("Pol Map Any", "pol10.test", cpExt(oidPol2)), inters: [][]byte{pi7}, roots: prs, host: "pol10.test"})
	pi8 := mkPolInter("Pol Dup", cpExt(oidPol1, oidPol1))
	emit(tc{name: "policy-duplicate", leaf: mkPolLeaf("Pol Dup", "pol11.test"), inters: [][]byte{pi8}, roots: prs, host: "pol11.test"})
	emit(tc{name: "policy-require-eku-bad", leaf: mkPolLeaf("Pol Require", "pol12.test", ext{oidEKU, false, tlv(0x30, oidDER(asn1.ObjectIdentifier{1, 3, 6, 1, 5, 5, 7, 3, 2}))}), inters: [][]byte{pi1}, roots: prs, host: "pol12.test"})
}

func constraints() {
	ck := key(kP256)
	type ncs struct {
		pdns, xdns     []string
		pip, xip       []string
		pemail, xemail []string
		puri, xuri     []string
	}
	cidr := func(s string) *net.IPNet {
		_, n, err := net.ParseCIDR(s)
		if err != nil {
			panic(err)
		}
		return n
	}
	mkCA := func(name string, c ncs, crit bool) *node {
		t := rootT(name)
		t.PermittedDNSDomainsCritical = crit
		t.PermittedDNSDomains = c.pdns
		t.ExcludedDNSDomains = c.xdns
		for _, s := range c.pip {
			t.PermittedIPRanges = append(t.PermittedIPRanges, cidr(s))
		}
		for _, s := range c.xip {
			t.ExcludedIPRanges = append(t.ExcludedIPRanges, cidr(s))
		}
		t.PermittedEmailAddresses = c.pemail
		t.ExcludedEmailAddresses = c.xemail
		t.PermittedURIDomains = c.puri
		t.ExcludedURIDomains = c.xuri
		t.SignatureAlgorithm = x509.ECDSAWithSHA256
		return create(t, nil, ck)
	}
	type sans struct {
		dns, ips, emails, uris []string
	}
	n := 0
	mkLeafS := func(ca *node, s sans) *node {
		n++
		t := leafT(fmt.Sprintf("nc%d", n), s.dns, s.ips)
		t.EmailAddresses = s.emails
		for _, u := range s.uris {
			pu, err := url.Parse(u)
			if err != nil {
				panic(err)
			}
			t.URIs = append(t.URIs, pu)
		}
		return mkLeaf(t, ca, key(kP256), 0)
	}
	host := func(s sans) string {
		if len(s.dns) > 0 && !strings.HasPrefix(s.dns[0], "*") {
			return s.dns[0]
		}
		return ""
	}
	cases := []struct {
		name string
		c    ncs
		s    []sans
	}{
		{"dns-permitted", ncs{pdns: []string{"example.com"}}, []sans{
			{dns: []string{"example.com"}}, {dns: []string{"www.example.com"}}, {dns: []string{"a.b.example.com"}},
			{dns: []string{"example.org"}}, {dns: []string{"badexample.com"}}, {dns: []string{"WWW.EXAMPLE.COM"}},
			{dns: []string{"www.example.com", "www.example.org"}}, {dns: []string{"*.example.com"}}, {ips: []string{"10.0.0.1"}, dns: []string{"x.example.com"}},
			{emails: []string{"a@example.com"}, dns: []string{"m.example.com"}}, {uris: []string{"https://u.example.com/x"}, dns: []string{"u.example.com"}},
		}},
		{"dns-permitted-dot", ncs{pdns: []string{".example.com"}}, []sans{
			{dns: []string{"example.com"}}, {dns: []string{"www.example.com"}}, {dns: []string{"*.example.com"}}, {dns: []string{"x.y.example.com"}},
		}},
		{"dns-excluded", ncs{xdns: []string{"bad.example.com"}}, []sans{
			{dns: []string{"bad.example.com"}}, {dns: []string{"x.bad.example.com"}}, {dns: []string{"good.example.com"}},
			{dns: []string{"*.example.com"}}, {dns: []string{"*.bad.example.com"}}, {dns: []string{"notbad.example.com"}},
			{dns: []string{"BAD.Example.Com"}},
		}},
		{"dns-excluded-dot", ncs{xdns: []string{".bad.example.com", "evil.test"}}, []sans{
			{dns: []string{"bad.example.com"}}, {dns: []string{"x.bad.example.com"}}, {dns: []string{"*.bad.example.com"}},
			{dns: []string{"evil.test"}}, {dns: []string{"a.evil.test"}}, {dns: []string{"*.evil.test"}},
		}},
		{"dns-permit-and-exclude", ncs{pdns: []string{"example.com", "example.net"}, xdns: []string{"secret.example.com"}}, []sans{
			{dns: []string{"www.example.net"}}, {dns: []string{"a.secret.example.com"}}, {dns: []string{"secret.example.com"}},
			{dns: []string{"public.example.com", "secret.example.com"}}, {dns: []string{"other.org"}},
		}},
		{"dns-overlapping", ncs{pdns: []string{"a.example.com", "example.com", "b.a.example.com", "a-a.example.com", "example.com"}}, []sans{
			{dns: []string{"x.a.example.com"}}, {dns: []string{"a-a.example.com"}}, {dns: []string{"q.example.com"}}, {dns: []string{"example.org"}},
		}},
		{"ip-permitted", ncs{pip: []string{"10.0.0.0/8", "2001:db8::/32"}}, []sans{
			{ips: []string{"10.1.2.3"}}, {ips: []string{"11.1.2.3"}}, {ips: []string{"2001:db8::1"}}, {ips: []string{"2001:db9::1"}},
			{ips: []string{"10.1.2.3", "192.168.1.1"}}, {dns: []string{"ip.example.com"}, ips: []string{"10.9.9.9"}},
		}},
		{"ip-excluded", ncs{xip: []string{"192.168.0.0/16", "10.20.0.0/16"}}, []sans{
			{ips: []string{"192.168.5.5"}}, {ips: []string{"10.20.1.1"}}, {ips: []string{"10.21.1.1"}}, {ips: []string{"::1"}},
		}},
		{"ip-v4-only", ncs{pip: []string{"203.0.113.0/24"}}, []sans{
			{ips: []string{"::1"}}, {ips: []string{"203.0.113.9"}},
		}},
		{"email-permitted", ncs{pemail: []string{"example.com", "boss@corp.test"}}, []sans{
			{emails: []string{"a@example.com"}}, {emails: []string{"a@sub.example.com"}}, {emails: []string{"boss@corp.test"}},
			{emails: []string{"Boss@CORP.test"}}, {emails: []string{"other@corp.test"}}, {emails: []string{"a@example.org"}},
		}},
		{"email-excluded", ncs{xemail: []string{".spam.test", "bad@good.test"}}, []sans{
			{emails: []string{"x@a.spam.test"}}, {emails: []string{"x@spam.test"}}, {emails: []string{"bad@good.test"}}, {emails: []string{"ok@good.test"}},
		}},
		{"uri-permitted", ncs{puri: []string{"example.com"}}, []sans{
			{uris: []string{"https://example.com/a"}}, {uris: []string{"https://api.example.com:8443/a"}}, {uris: []string{"https://other.test/"}},
			{uris: []string{"https://10.0.0.1/"}}, {uris: []string{"urn:example"}}, {uris: []string{"https://[2001:db8::1]/"}},
		}},
		{"uri-excluded", ncs{xuri: []string{".example.com"}}, []sans{
			{uris: []string{"https://example.com/a"}}, {uris: []string{"https://x.example.com/a"}}, {uris: []string{"spiffe://trust.test/w"}},
		}},
		{"permit-all-empty", ncs{pdns: []string{""}}, []sans{
			{dns: []string{"anything.test"}},
		}},
		{"exclude-all-empty", ncs{xdns: []string{""}}, []sans{
			{dns: []string{"anything.test"}}, {ips: []string{"10.0.0.1"}},
		}},
		{"only-dns-constraint-ip-free", ncs{pdns: []string{"example.com"}}, []sans{
			{ips: []string{"10.0.0.1"}}, {emails: []string{"a@other.test"}},
		}},
	}
	for _, cs := range cases {
		ca := mkCA("NC "+cs.name, cs.c, false)
		for i, s := range cs.s {
			leaf := mkLeafS(ca, s)
			emit(tc{name: fmt.Sprintf("nc-%s-%d", cs.name, i), leaf: leaf.der, roots: [][]byte{ca.der}, host: host(s)})
		}
	}
	// constraints on an intermediate below an unconstrained root, and on
	// both
	root := mkRoot("NC Plain Root", ck, 0)
	it := interT("NC Inter")
	it.PermittedDNSDomains = []string{"inter.test"}
	it.SignatureAlgorithm = x509.ECDSAWithSHA256
	ik := key(kP256)
	inter := create(it, root, ik)
	for i, d := range []string{"a.inter.test", "a.other.test"} {
		l := mkLeaf(leafT(d, []string{d}, nil), inter, key(kP256), 0)
		emit(tc{name: fmt.Sprintf("nc-intermediate-%d", i), leaf: l.der, inters: [][]byte{inter.der}, roots: [][]byte{root.der}, host: d})
	}
	rt := rootT("NC Root Exclude")
	rt.ExcludedDNSDomains = []string{"x.inter.test"}
	rt.SignatureAlgorithm = x509.ECDSAWithSHA256
	rootX := create(rt, nil, ck)
	it2 := interT("NC Inter 2")
	it2.PermittedDNSDomains = []string{"inter.test"}
	it2.SignatureAlgorithm = x509.ECDSAWithSHA256
	inter2 := create(it2, rootX, ik)
	for i, d := range []string{"a.inter.test", "b.x.inter.test", "c.other.test"} {
		l := mkLeaf(leafT(d, []string{d}, nil), inter2, key(kP256), 0)
		emit(tc{name: fmt.Sprintf("nc-root-and-intermediate-%d", i), leaf: l.der, inters: [][]byte{inter2.der}, roots: [][]byte{rootX.der}, host: d})
	}
	// an intermediate's own names fall under the root's constraints
	it3 := interT("NC Inter Named")
	it3.DNSNames = []string{"inter.forbidden.test"}
	it3.SignatureAlgorithm = x509.ECDSAWithSHA256
	rt3 := rootT("NC Root Forbid")
	rt3.ExcludedDNSDomains = []string{"forbidden.test"}
	rt3.SignatureAlgorithm = x509.ECDSAWithSHA256
	root3 := create(rt3, nil, ck)
	inter3 := create(it3, root3, ik)
	l3 := mkLeaf(leafT("ok.allowed.test", []string{"ok.allowed.test"}, nil), inter3, key(kP256), 0)
	emit(tc{name: "nc-intermediate-own-san", leaf: l3.der, inters: [][]byte{inter3.der}, roots: [][]byte{root3.der}, host: "ok.allowed.test"})
}

// hostnames: VerifyHostname alone against a table of names
func hostnames() {
	root := mkRoot("Host Root", key(kP256), 0)
	mk := func(dns []string, ips []string) *node {
		return mkLeaf(leafT("host", dns, ips), root, key(kP256), 0)
	}
	a := mk([]string{"example.com", "*.example.com", "*.a.example.net", "Mixed.Case.Test", "under_score.test", "*.under_score.test",
		"xn--bcher-kva.test", "trailing.dot.test.", "f*o.wild.test", "*.*.double.test", "*", "-lead.test", "a..b.test", "", ".",
		"*.", "localhost", "*.co"}, []string{"192.0.2.10", "2001:db8::10", "127.0.0.1"})
	hosts := []string{"example.com", "EXAMPLE.COM", "example.com.", "www.example.com", "a.b.example.com", "x.a.example.net",
		"a.example.net", "mixed.case.test", "under_score.test", "x.under_score.test", "xn--bcher-kva.test", "trailing.dot.test",
		"trailing.dot.test.", "foo.wild.test", "f*o.wild.test", "a.b.double.test", "*.*.double.test", "anything", "-lead.test",
		"a..b.test", "", ".", "localhost", "LOCALHOST.", "x.co", "co", "192.0.2.10", "[192.0.2.10]", "192.0.2.010", "2001:db8::10",
		"[2001:db8::10]", "2001:DB8:0:0:0:0:0:10", "::ffff:127.0.0.1", "127.0.0.1", "127.1", "[127.0.0.1]", "1.2.3.4",
		"fe80::1%25eth0", "fe80::1%eth0", "[::1]", "*.example.com", "ex ample.com", "example.com..", "éxample.com",
		"www.example.com:443", "WWW.Example.Com.", ".example.com", "example", "a.b.c.example.com"}
	for _, h := range hosts {
		emitHost("table-"+h, a, h)
	}
	b := mk(nil, nil)
	for _, h := range []string{"host", "x.test", "10.0.0.1", "::1"} {
		emitHost("empty-"+h, b, h)
	}
	cnLeaf := mkLeaf(&x509.Certificate{Subject: pkix.Name{CommonName: "*.legacy.test"}}, root, key(kP256), 0)
	for _, h := range []string{"a.legacy.test", "legacy.test", "10.0.0.1"} {
		emitHost("cn-"+h, cnLeaf, h)
	}
	var many []string
	var manyIP []string
	for i := 0; i < 101; i++ {
		many = append(many, fmt.Sprintf("n%d.many.test", i))
		manyIP = append(manyIP, fmt.Sprintf("10.9.%d.%d", i/250, i%250+1))
	}
	m := mk(many, manyIP)
	emitHost("many-names", m, "zz.many.test")
	emitHost("many-ips", m, "10.10.10.10")
	emitHost("many-names-hit", m, "n100.many.test")
}

// parses: certificates built by hand, some malformed, read by
// ParseCertificate alone
func parses() {
	k := key(kP256)
	base := func() *raw {
		return &raw{version: 2, sigOID: asn1.ObjectIdentifier{1, 2, 840, 10045, 4, 3, 2}, issuer: nameDER("Parse CA"),
			subject: nameDER("parse.test"), key: k, hash: crypto.SHA256, exts: []ext{sanDNS("parse.test")}}
	}
	emitParse("good", build(base(), k))
	r := base()
	r.trailing = []byte{0}
	emitParse("trailing-data", build(r, k))
	r = base()
	r.serial = mustMarshal(big.NewInt(-5))
	emitParse("negative-serial", build(r, k))
	r = base()
	r.serial = []byte{2, 2, 0, 5}
	emitParse("serial-not-minimal", build(r, k))
	r = base()
	r.serial = mustMarshal(new(big.Int).Lsh(big.NewInt(1), 200))
	emitParse("serial-large", build(r, k))
	r = base()
	r.serial = []byte{2, 1, 0}
	emitParse("serial-zero", build(r, k))
	r = base()
	r.version = 3
	emitParse("version-4", build(r, k))
	r = base()
	r.version = 0
	emitParse("version-1-explicit", build(r, k))
	r = base()
	r.version = 1
	emitParse("version-2", build(r, k))
	r = base()
	r.outerAlg = tlv(0x30, oidDER(asn1.ObjectIdentifier{1, 2, 840, 10045, 4, 3, 3}))
	emitParse("outer-alg-mismatch", build(r, k))
	r = base()
	r.sigNull = true
	emitParse("ecdsa-alg-with-null", build(r, k))
	r = base()
	r.sigOID = asn1.ObjectIdentifier{1, 2, 3}
	emitParse("unknown-sig-alg", build(r, k))
	for _, tm := range []string{"250101000000Z", "250101000000+0100", "250101000000-0000", "250101000000+0000", "2501010000Z",
		"250101000060Z", "250230000000Z", "240229000000Z", "250101240000Z", "250101000000", "250101000000.5Z", "500101000000Z",
		"491231235959Z", "250101000000+2400", "250101000000+0160", "250101000000+2500", "25010100000Z", "2501010000000Z", "25O101000000Z"} {
		r = base()
		r.notBefore = tlv(0x17, []byte(tm))
		emitParse("utctime-"+tm, build(r, k))
	}
	for _, tm := range []string{"20250101000000Z", "20250101000000+0100", "202501010000Z", "20250101000000.5Z", "99991231235959Z",
		"00000101000000Z", "20240229000000Z", "21000229000000Z", "20000229000000Z"} {
		r = base()
		r.notAfter = tlv(0x18, []byte(tm))
		emitParse("gentime-"+tm, build(r, k))
	}
	r = base()
	r.notAfter = tlv(0x04, []byte("x"))
	emitParse("time-wrong-tag", build(r, k))
	r = base()
	r.exts = []ext{sanDNS("a.test"), sanDNS("b.test")}
	emitParse("duplicate-extension", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidAKI, true, tlv(0x30, tlv(0x80, []byte{1, 2, 3}))})
	emitParse("aki-critical", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidSKI, true, tlv(4, []byte{1, 2, 3})})
	emitParse("ski-critical", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidAKI, false, tlv(0x30, tlv(0x80, []byte{1, 2, 3}))}, ext{oidSKI, false, tlv(4, []byte{4, 5})})
	emitParse("aki-ski", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidNC, true, tlv(0x30)})
	emitParse("nc-empty", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidNC, true, tlv(0x30, tlv(0xa0, tlv(0x30, tlv(0x87, []byte{10, 0, 0, 0, 255, 0, 255, 0}))))})
	emitParse("nc-bad-mask", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidNC, true, tlv(0x30, tlv(0xa0, tlv(0x30, tlv(0x87, []byte{10, 0, 0, 0, 255, 0, 0}))))})
	emitParse("nc-ip-length", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidNC, true, tlv(0x30, tlv(0xa0, tlv(0x30, tlv(0x82, []byte("example.com.")))))})
	emitParse("nc-dns-trailing-dot", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidNC, true, tlv(0x30, tlv(0xa0, tlv(0x30, tlv(0x82, []byte("ex\xffample.com")))))})
	emitParse("nc-dns-not-ia5", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidNC, true, tlv(0x30, tlv(0xa1, tlv(0x30, tlv(0x86, []byte("10.0.0.1")))))})
	emitParse("nc-uri-ip", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidNC, true, tlv(0x30, tlv(0xa1, tlv(0x30, tlv(0x81, []byte("a..b@x.test")))))})
	emitParse("nc-email-bad", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidNC, true, tlv(0x30, tlv(0xa0, tlv(0x30, tlv(0xa4, nameDER("dir")))))})
	emitParse("nc-directory-name-critical", build(r, k))
	r = base()
	r.exts = []ext{{oidSAN, false, tlv(0x30, tlv(0x87, []byte{1, 2, 3, 4, 5}))}}
	emitParse("san-ip-length-5", build(r, k))
	r = base()
	r.exts = []ext{{oidSAN, false, tlv(0x30, tlv(0x87, []byte{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xff, 0xff, 1, 2, 3, 4}))}}
	emitParse("san-ip-v4-mapped", build(r, k))
	r = base()
	r.exts = []ext{{oidSAN, false, tlv(0x30, tlv(0x82, []byte("b\xc3\xa4d.test")))}}
	emitParse("san-dns-not-ia5", build(r, k))
	r = base()
	r.exts = []ext{{oidSAN, false, tlv(0x30, tlv(0x81, []byte("m\xc3\xa4il@x.test")))}}
	emitParse("san-email-not-ia5", build(r, k))
	r = base()
	r.exts = []ext{{oidSAN, false, tlv(0x30, tlv(0x86, []byte("https://exa mple.com/")))}}
	emitParse("san-uri-bad", build(r, k))
	r = base()
	r.exts = []ext{{oidSAN, false, tlv(0x30, tlv(0x86, []byte("https://a..b/")))}}
	emitParse("san-uri-bad-domain", build(r, k))
	r = base()
	r.exts = []ext{{oidSAN, false, tlv(0x30, tlv(0x86, []byte("https://user@host.test:8443/p?q#f")), tlv(0x81, []byte("x@y.test")),
		tlv(0x87, []byte{0x20, 1, 0xd, 0xb8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1}))}}
	emitParse("san-mixed", build(r, k))
	r = base()
	r.exts = []ext{{oidSAN, true, tlv(0x30, tlv(0xa4, nameDER("dir")))}}
	emitParse("san-critical-only-dirname", build(r, k))
	r = base()
	r.exts = []ext{{oidSAN, false, tlv(0x31)}}
	emitParse("san-not-sequence", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidBC, true, tlv(0x30, []byte{1, 1, 0xff}, []byte{2, 1, 0xff})})
	emitParse("bc-negative-pathlen", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidBC, true, tlv(0x30, []byte{1, 1, 1})})
	emitParse("bc-bool-not-der", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidBC, true, tlv(0x30, []byte{1, 1, 0xff}, []byte{2, 1, 3})})
	emitParse("bc-pathlen-3", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidBC, true, tlv(0x30, []byte{1, 1, 0xff}, []byte{2, 9, 0, 0x80, 0, 0, 0, 0, 0, 0, 0})})
	emitParse("bc-pathlen-huge", build(r, k))
	r = base()
	r.exts = append(r.exts, kuExt(0x86))
	emitParse("ku-bits", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidKU, true, []byte{3, 3, 7, 0x80, 0x80}})
	emitParse("ku-decipher-only", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidKU, true, []byte{3, 2, 3, 0x81}})
	emitParse("ku-padding-not-zero", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidEKU, false, tlv(0x30, oidDER(asn1.ObjectIdentifier{1, 3, 6, 1, 5, 5, 7, 3, 1}), oidDER(asn1.ObjectIdentifier{1, 3, 6, 1, 4, 1, 311, 10, 3, 3}), oidDER(asn1.ObjectIdentifier{1, 9}))})
	emitParse("eku-mixed", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidEKU, false, tlv(0x30, tlv(6, []byte{0x2b, 0x80, 1}))})
	emitParse("eku-oid-not-minimal", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidCP, false, tlv(0x30, tlv(0x30, oidDER(oidPol1)), tlv(0x30, oidDER(oidPol1)))})
	emitParse("policies-duplicate", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidPC, true, tlv(0x30, tlv(0x80, []byte{2}), tlv(0x81, []byte{0}))}, ext{oidIAP, true, intDER(3)})
	emitParse("policy-constraints", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidAIA, true, tlv(0x30)})
	emitParse("aia-critical", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidAIA, false, tlv(0x30, tlv(0x30, oidDER(asn1.ObjectIdentifier{1, 3, 6, 1, 5, 5, 7, 48, 1}), tlv(0x86, []byte("http://ocsp.test"))))},
		ext{oidCRL, false, tlv(0x30, tlv(0x30, tlv(0xa0, tlv(0xa0, tlv(0x86, []byte("http://crl.test/x.crl"))))))})
	emitParse("aia-crl", build(r, k))
	r = base()
	r.exts = append(r.exts, ext{oidCRL, false, tlv(0x30, tlv(0x31))})
	emitParse("crl-bad", build(r, k))
	r = base()
	r.subject = tlv(0x30, tlv(0x31, tlv(0x30, oidDER(asn1.ObjectIdentifier{2, 5, 4, 3}), tlv(0x13, []byte("bad_printable")))))
	emitParse("name-bad-printable", build(r, k))
	r = base()
	r.subject = tlv(0x30, tlv(0x31, tlv(0x30, oidDER(asn1.ObjectIdentifier{2, 5, 4, 3}), tlv(0x1e, []byte{0, 'h', 0, 'i', 0xd8, 0}))))
	emitParse("name-bmp-surrogate", build(r, k))
	r = base()
	r.subject = tlv(0x30, tlv(0x31, tlv(0x30, oidDER(asn1.ObjectIdentifier{2, 5, 4, 3}), tlv(0x1e, []byte{0, 'h', 0, 0xe9, 0, 0}))))
	emitParse("name-bmp-ok", build(r, k))
	r = base()
	r.subject = tlv(0x30, tlv(0x31, tlv(0x30, oidDER(asn1.ObjectIdentifier{2, 5, 4, 3}), tlv(0x14, []byte{'c', 0xe9}))))
	emitParse("name-t61", build(r, k))
	r = base()
	r.subject = tlv(0x30, tlv(0x31, tlv(0x30, oidDER(asn1.ObjectIdentifier{2, 5, 4, 3}), tlv(0x0c, []byte{'x', 0xc3}))))
	emitParse("name-utf8-bad", build(r, k))
	r = base()
	r.subject = tlv(0x30, tlv(0x31, tlv(0x30, oidDER(asn1.ObjectIdentifier{2, 5, 4, 3}), tlv(0x02, []byte{0, 1}))))
	emitParse("name-int-not-minimal", build(r, k))
	r = base()
	r.subject = tlv(0x30, tlv(0x31, tlv(0x30, oidDER(asn1.ObjectIdentifier{2, 5, 4, 3}), tlv(0x02, []byte{1}))), tlv(0x31, tlv(0x30, oidDER(asn1.ObjectIdentifier{2, 5, 4, 10}), tlv(0x13, []byte("Org")))))
	emitParse("name-int-cn-and-org", build(r, k))
	r = base()
	r.subject = tlv(0x30, tlv(0x31, tlv(0x30, oidDER(asn1.ObjectIdentifier{2, 5, 4, 3}), tlv(0x16, []byte("one"))), tlv(0x30, oidDER(asn1.ObjectIdentifier{2, 5, 4, 3}), tlv(0x13, []byte("two")))))
	emitParse("name-two-cn", build(r, k))
	r = base()
	r.subject = tlv(0x30, tlv(0x31, tlv(0x30, oidDER(asn1.ObjectIdentifier{2, 5, 4, 3}), tlv(0x12, []byte("12 3a")))))
	emitParse("name-numeric-bad", build(r, k))
	r = base()
	r.subject = tlv(0x30, tlv(0x31, tlv(0x30, oidDER(asn1.ObjectIdentifier{2, 5, 4, 3}), tlv(0x17, []byte("250101000000Z")))))
	emitParse("name-utctime-value", build(r, k))
	r = base()
	r.subject = tlv(0x30, tlv(0x31, tlv(0x30, oidDER(asn1.ObjectIdentifier{2, 5, 4, 3}), []byte{0x1f, 0x22, 0})))
	emitParse("name-high-tag", build(r, k))
	r = base()
	r.subject = tlv(0x30, tlv(0x30))
	emitParse("name-not-set", build(r, k))
	// a key the parser refuses: an RSA key without NULL, an EC point off the curve
	good := build(base(), k)
	emitParse("ec-point-off-curve", mutate(good, func(b []byte) []byte {
		i := indexOf(b, spkiOf(k))
		c := append([]byte{}, b...)
		c[i+len(spkiOf(k))-1] ^= 1
		return c
	}))
	emitParse("truncated", good[:len(good)-5])
	emitParse("length-not-minimal", append([]byte{0x30, 0x82, 0x00, byte(len(good) - 2)}, good[2:]...))
	emitParse("empty", []byte{})
	rk := key(kRSA)
	rr := base()
	rr.key = rk
	rsaGood := build(rr, k)
	emitParse("rsa-key", rsaGood)
	var spk struct {
		Alg asn1.RawValue
		Key asn1.RawValue
	}
	asn1.Unmarshal(spkiOf(rk), &spk)
	rr2 := base()
	rr2.key = rk
	rr2.spki = tlv(0x30, tlv(0x30, oidDER(asn1.ObjectIdentifier{1, 2, 840, 113549, 1, 1, 1})), spk.Key.FullBytes)
	emitParse("rsa-key-without-null", build(rr2, k))
	rr3 := base()
	rr3.spki = tlv(0x30, tlv(0x30, oidDER(asn1.ObjectIdentifier{1, 2, 840, 10045, 2, 1}), oidDER(asn1.ObjectIdentifier{1, 3, 36, 3, 3, 2, 8, 1, 1, 7})), tlv(3, append([]byte{0, 4}, make([]byte, 64)...)))
	emitParse("ec-brainpool", build(rr3, k))
	rr4 := base()
	rr4.spki = tlv(0x30, tlv(0x30, oidDER(asn1.ObjectIdentifier{1, 2, 840, 10045, 2, 1}), oidDER(asn1.ObjectIdentifier{1, 2, 840, 10045, 3, 1, 7})), tlv(3, append([]byte{0, 2}, make([]byte, 32)...)))
	emitParse("ec-compressed", build(rr4, k))
	rr5 := base()
	rr5.spki = tlv(0x30, tlv(0x30, oidDER(asn1.ObjectIdentifier{1, 2, 3, 4})), tlv(3, []byte{0, 1, 2, 3}))
	emitParse("unknown-key-algorithm", build(rr5, k))
	edr := base()
	_, edPriv, _ := ed25519.GenerateKey(rand.Reader)
	edr.key = edPriv
	emitParse("ed25519-key", build(edr, k))
	p521, _ := ecdsa.GenerateKey(elliptic.P521(), rand.Reader)
	pr := base()
	pr.key = p521
	emitParse("p521-key", build(pr, k))
	p224, _ := ecdsa.GenerateKey(elliptic.P224(), rand.Reader)
	pr = base()
	pr.key = p224
	emitParse("p224-key", build(pr, k))
	// RSA-PSS parameters: good, wrong salt, wrong MGF hash
	pss := base()
	pss.pss = true
	pss.hash = crypto.SHA256
	emitParse("pss-sha256", build(pss, rk))
	emitParse("pss-wrong-salt", mutateAlg(build(pss, rk), []byte{0xa2, 3, 2, 1, 32}, []byte{0xa2, 3, 2, 1, 20}))
	_ = sha256.Sum256
}

func indexOf(b, sub []byte) int {
	for i := 0; i+len(sub) <= len(b); i++ {
		if string(b[i:i+len(sub)]) == string(sub) {
			return i
		}
	}
	panic("not found")
}

func mutate(b []byte, f func([]byte) []byte) []byte { return f(b) }

// mutateAlg replaces every occurrence of old by new (same length)
func mutateAlg(b []byte, old, nw []byte) []byte {
	c := append([]byte{}, b...)
	for i := 0; i+len(old) <= len(c); i++ {
		if string(c[i:i+len(old)]) == string(old) {
			copy(c[i:], nw)
		}
	}
	return c
}

