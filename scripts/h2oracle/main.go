// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// The HTTP/2 oracle of pashttp2 (P617): Go's net/http server on
// 127.0.0.1, over TLS with h2 chosen by ALPN or in the clear with prior
// knowledge (RFC 9113 3.2 and 3.3), with the handlers the client's
// tests ask. It writes its root in PEM to DIR/ca.pem, prints its port
// and serves until killed.
//
//	h2oracle -mode tls|h2c|h1 -dir DIR [-streams N]
package main

import (
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/hex"
	"encoding/pem"
	"flag"
	"fmt"
	"io"
	"math/big"
	"net"
	"net/http"
	"os"
	"sort"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
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

// the octets a request for n of them gets: the same from any offset
func pattern(n int) []byte {
	b := make([]byte, n)
	for i := range b {
		b[i] = byte(i*7 + i>>8)
	}
	return b
}

var served, posted, gone, inflight, most atomic.Int64

// what the connections of the server are, so that /count says how many
// were made
var conns sync.Map

func handler(restart func()) http.Handler {
	mux := http.NewServeMux()
	// the request as the server saw it: its method, path, protocol, the
	// fields asked for by name, and the length and SHA-256 of its content
	mux.HandleFunc("/echo", func(w http.ResponseWriter, r *http.Request) {
		served.Add(1)
		body, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, err.Error(), 400)
			return
		}
		if r.Method == "POST" {
			posted.Add(1)
		}
		sum := sha256.Sum256(body)
		var names []string
		for k := range r.Header {
			names = append(names, strings.ToLower(k))
		}
		sort.Strings(names)
		w.Header().Set("Content-Type", "text/plain")
		w.Header().Set("X-Proto", r.Proto)
		var sb strings.Builder
		fmt.Fprintf(&sb, "%s %s %s host=%s len=%d sha=%s\n", r.Method, r.URL.RequestURI(), r.Proto, r.Host, len(body),
			hex.EncodeToString(sum[:8]))
		for _, k := range names {
			fmt.Fprintf(&sb, "%s: %s\n", k, strings.Join(r.Header.Values(k), " | "))
		}
		io.WriteString(w, sb.String())
	})
	// n octets of the pattern, in pieces of chunk when it is given
	mux.HandleFunc("/big", func(w http.ResponseWriter, r *http.Request) {
		served.Add(1)
		n, _ := strconv.Atoi(r.URL.Query().Get("n"))
		chunk, _ := strconv.Atoi(r.URL.Query().Get("chunk"))
		b := pattern(n)
		if r.URL.Query().Get("len") != "no" {
			w.Header().Set("Content-Length", strconv.Itoa(n))
		}
		if chunk <= 0 {
			w.Write(b)
			return
		}
		for len(b) > 0 {
			k := min(chunk, len(b))
			w.Write(b[:k])
			w.(http.Flusher).Flush()
			b = b[k:]
		}
	})
	mux.HandleFunc("/slow", func(w http.ResponseWriter, r *http.Request) {
		served.Add(1)
		// how many of these run at once, at most: what a limit of streams shows
		n := inflight.Add(1)
		for {
			m := most.Load()
			if n <= m || most.CompareAndSwap(m, n) {
				break
			}
		}
		defer inflight.Add(-1)
		ms, _ := strconv.Atoi(r.URL.Query().Get("ms"))
		select {
		case <-time.After(time.Duration(ms) * time.Millisecond):
			io.WriteString(w, "slow done\n")
		case <-r.Context().Done():
			gone.Add(1)
		}
	})
	mux.HandleFunc("/status", func(w http.ResponseWriter, r *http.Request) {
		served.Add(1)
		code, _ := strconv.Atoi(r.URL.Query().Get("code"))
		if loc := r.URL.Query().Get("to"); loc != "" {
			w.Header().Set("Location", loc)
		}
		w.WriteHeader(code)
		if code != 204 && code != 304 && r.Method != "HEAD" {
			fmt.Fprintf(w, "status %d\n", code)
		}
	})
	mux.HandleFunc("/trailers", func(w http.ResponseWriter, r *http.Request) {
		served.Add(1)
		w.Header().Set("Trailer", "X-Sum, X-Count")
		io.WriteString(w, "with trailers\n")
		w.Header().Set("X-Sum", "abc123")
		w.Header().Set("X-Count", "14")
	})
	mux.HandleFunc("/early", func(w http.ResponseWriter, r *http.Request) {
		served.Add(1)
		w.Header().Set("Link", "</style.css>; rel=preload")
		w.WriteHeader(103)
		w.Header().Set("Content-Type", "text/plain")
		io.WriteString(w, "after the hints\n")
	})
	mux.HandleFunc("/cookies", func(w http.ResponseWriter, r *http.Request) {
		served.Add(1)
		http.SetCookie(w, &http.Cookie{Name: "a", Value: "1"})
		http.SetCookie(w, &http.Cookie{Name: "b", Value: "2"})
		fmt.Fprintf(w, "%d cookie fields: %s\n", len(r.Header.Values("Cookie")), strings.Join(r.Header.Values("Cookie"), "; "))
	})
	// the content of the request, back as it comes: both directions at once
	mux.HandleFunc("/pipe", func(w http.ResponseWriter, r *http.Request) {
		served.Add(1)
		io.Copy(w, r.Body)
	})
	// an answer before the request's content was read
	mux.HandleFunc("/refuse", func(w http.ResponseWriter, r *http.Request) {
		served.Add(1)
		w.WriteHeader(413)
		io.WriteString(w, "too much\n")
	})
	mux.HandleFunc("/count", func(w http.ResponseWriter, r *http.Request) {
		// once every slow request has ended, so that those given up are counted
		for i := 0; i < 400 && inflight.Load() > 0; i++ {
			time.Sleep(5 * time.Millisecond)
		}
		n := 0
		conns.Range(func(k, v any) bool { n++; return true })
		fmt.Fprintf(w, "served=%d posted=%d gone=%d most=%d conns=%d\n", served.Load(), posted.Load(), gone.Load(),
			most.Load(), n)
	})
	// the server goes away in order (GOAWAY) once this is answered, and
	// another listens on the same port
	mux.HandleFunc("/goaway", func(w http.ResponseWriter, r *http.Request) {
		served.Add(1)
		io.WriteString(w, "going away\n")
		go restart()
	})
	return mux
}

func main() {
	port := flag.Int("port", 0, "port")
	mode := flag.String("mode", "tls", "tls, h2c or h1")
	dir := flag.String("dir", ".", "where ca.pem goes")
	streams := flag.Int("streams", 0, "SETTINGS_MAX_CONCURRENT_STREAMS")
	flag.Parse()
	caKey, _ := ecdsa.GenerateKey(elliptic.P384(), rand.Reader)
	caT := &x509.Certificate{SerialNumber: big.NewInt(1), Subject: pkix.Name{CommonName: "pashttp2 test root"},
		NotBefore: notBefore, NotAfter: notAfter, IsCA: true, BasicConstraintsValid: true,
		KeyUsage: x509.KeyUsageCertSign | x509.KeyUsageCRLSign}
	ca := mkCert(caT, caT, &caKey.PublicKey, caKey)
	os.WriteFile(*dir+"/ca.pem", pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: ca.Raw}), 0644)
	k, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	leafT := &x509.Certificate{SerialNumber: big.NewInt(2), Subject: pkix.Name{CommonName: "localhost"},
		NotBefore: notBefore, NotAfter: notAfter, DNSNames: []string{"localhost"},
		IPAddresses: []net.IP{net.ParseIP("127.0.0.1")},
		KeyUsage: x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}}
	leaf := mkCert(leafT, ca, &k.PublicKey, caKey)
	cert := tls.Certificate{Certificate: [][]byte{leaf.Raw, ca.Raw}, PrivateKey: k}

	ln, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", *port))
	if err != nil {
		panic(err)
	}
	addr := ln.Addr().String()
	var mu sync.Mutex
	var srv *http.Server
	var start func(ln net.Listener)
	restart := func() {
		mu.Lock()
		old := srv
		mu.Unlock()
		// a moment for the answer to leave, then GOAWAY and the wait for
		// the streams on their way
		time.Sleep(50 * time.Millisecond)
		go old.Shutdown(context.Background())
		// the old server stops listening at once and serves its streams
		// to their end; the new one listens as soon as the port is free
		for i := 0; ; i++ {
			nl, err := net.Listen("tcp", addr)
			if err == nil {
				start(nl)
				return
			}
			if i > 1000 {
				fmt.Fprintln(os.Stderr, "listen again:", err)
				os.Exit(1)
			}
			time.Sleep(5 * time.Millisecond)
		}
	}
	start = func(ln net.Listener) {
		s := &http.Server{Handler: handler(restart)}
		s.Protocols = new(http.Protocols)
		switch *mode {
		case "tls":
			s.Protocols.SetHTTP2(true)
			s.Protocols.SetHTTP1(true)
			s.TLSConfig = &tls.Config{Certificates: []tls.Certificate{cert}}
		case "h2c":
			s.Protocols.SetUnencryptedHTTP2(true)
		case "h1":
			// a server that knows no HTTP/2: what a client of it must say
			s.Protocols.SetHTTP1(true)
			if *dir != "" {
				s.TLSConfig = &tls.Config{Certificates: []tls.Certificate{cert}}
			}
		default:
			fmt.Fprintln(os.Stderr, "unknown mode", *mode)
			os.Exit(2)
		}
		if *streams > 0 {
			s.HTTP2 = &http.HTTP2Config{MaxConcurrentStreams: *streams}
		}
		s.ConnState = func(c net.Conn, st http.ConnState) {
			if st == http.StateNew {
				conns.Store(c.RemoteAddr().String(), true)
			}
		}
		mu.Lock()
		srv = s
		mu.Unlock()
		go func() {
			if s.TLSConfig != nil {
				s.ServeTLS(ln, "", "")
			} else {
				s.Serve(ln)
			}
		}()
	}
	start(ln)
	fmt.Println(ln.Addr().(*net.TCPAddr).Port)
	os.Stdout.Sync()
	select {}
}
