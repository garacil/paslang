// This file is part of paslang's benchmarks.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacil@tucall.com>
// GPL version 3 or later. See COPYING.

package main

import (
	"bytes"
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptrace"
	"os"
	"os/signal"
	"strconv"
	"sync"
	"syscall"
	"time"
)

const hello = "hello over TLS\n"
const timeout = 30 * time.Second

func version(tls12 bool) uint16 {
	if tls12 {
		return tls.VersionTLS12
	}
	return tls.VersionTLS13
}

// Use the same invocation and routes as testdata/tlsserver13.paslang.
func serve(cert, key, file string, tls12 bool) error {
	pair, err := tls.LoadX509KeyPair(cert, key)
	if err != nil {
		return err
	}
	config := &tls.Config{
		Certificates: []tls.Certificate{pair}, SessionTicketsDisabled: true,
		MinVersion: version(tls12), MaxVersion: tls.VersionTLS13,
		CurvePreferences: []tls.CurveID{tls.X25519},
		NextProtos:       []string{"http/1.1"},
	}
	listener, err := tls.Listen("tcp", "127.0.0.1:0", config)
	if err != nil {
		return err
	}
	defer listener.Close()
	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		io.WriteString(w, hello)
	})
	mux.HandleFunc("/file", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/octet-stream")
		http.ServeFile(w, r, file)
	})
	server := &http.Server{Handler: mux, ReadHeaderTimeout: 1800 * time.Millisecond}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM)
	defer stop()
	result := make(chan error, 1)
	fmt.Println(listener.Addr().(*net.TCPAddr).Port)
	go func() { result <- server.Serve(listener) }()
	select {
	case err := <-result:
		return err
	case <-ctx.Done():
		deadline, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		if err := server.Shutdown(deadline); err != nil {
			return err
		}
		err := <-result
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	}
}

type worker struct {
	client  *http.Client
	url     string
	body    []byte
	scratch []byte
	version uint16
	cipher  uint16
}

func (w *worker) request(reused bool) error {
	connections, wasReused := 0, false
	trace := &httptrace.ClientTrace{GotConn: func(info httptrace.GotConnInfo) {
		connections++
		wasReused = info.Reused
	}}
	req, err := http.NewRequestWithContext(
		httptrace.WithClientTrace(context.Background(), trace), http.MethodGet, w.url, nil)
	if err != nil {
		return err
	}
	resp, err := w.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK || resp.ContentLength != int64(len(w.body)) {
		return fmt.Errorf("unexpected HTTP status %d or length %d, want 200 and %d",
			resp.StatusCode, resp.ContentLength, len(w.body))
	}
	if resp.TLS == nil {
		return fmt.Errorf("missing TLS connection state")
	}
	if resp.TLS.Version != w.version || resp.TLS.CipherSuite != w.cipher ||
		resp.TLS.NegotiatedProtocol != "http/1.1" || resp.TLS.DidResume || resp.TLS.CurveID != tls.X25519 {
		return fmt.Errorf("unexpected TLS version %x, cipher %s, ALPN %q, resumed %t or key exchange %s",
			resp.TLS.Version, tls.CipherSuiteName(resp.TLS.CipherSuite),
			resp.TLS.NegotiatedProtocol, resp.TLS.DidResume, resp.TLS.CurveID)
	}
	if connections != 1 || wasReused != reused {
		return fmt.Errorf("expected one connection with reuse %t, got %d with reuse %t", reused, connections, wasReused)
	}
	for offset := 0; offset < len(w.body); {
		end := min(offset+len(w.scratch), len(w.body))
		chunk := w.scratch[:end-offset]
		if _, err := io.ReadFull(resp.Body, chunk); err != nil {
			return err
		}
		if !bytes.Equal(chunk, w.body[offset:end]) {
			return fmt.Errorf("response body differs at offset %d", offset)
		}
		offset = end
	}
	var extra [1]byte
	if n, err := resp.Body.Read(extra[:]); n != 0 || err != io.EOF {
		return fmt.Errorf("unexpected end of response body")
	}
	return nil
}

func load(addr, root, file, mode string, tls12, base bool, workers, iterations int) error {
	pem, err := os.ReadFile(root)
	if err != nil {
		return err
	}
	roots := x509.NewCertPool()
	if !roots.AppendCertsFromPEM(pem) {
		return fmt.Errorf("invalid test CA")
	}
	body := []byte(hello)
	url := "https://" + addr + "/"
	transfer := mode == "transfer"
	if transfer {
		url += "file"
		body, err = os.ReadFile(file)
		if err != nil {
			return err
		}
	}
	cipher := uint16(tls.TLS_AES_128_GCM_SHA256)
	if tls12 {
		cipher = tls.TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
		if base {
			cipher = tls.TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256
		}
	} else if base {
		cipher = tls.TLS_CHACHA20_POLY1305_SHA256
	}
	cfg := &tls.Config{
		RootCAs: roots, ServerName: "localhost", NextProtos: []string{"http/1.1"},
		MinVersion: version(tls12), MaxVersion: version(tls12),
		CurvePreferences: []tls.CurveID{tls.X25519, tls.CurveP256}, CipherSuites: []uint16{cipher},
	}
	group := make([]worker, workers)
	for i := range group {
		transport := &http.Transport{
			TLSClientConfig: cfg, DisableKeepAlives: !transfer, MaxConnsPerHost: 1,
			DisableCompression: true,
		}
		defer transport.CloseIdleConnections()
		group[i] = worker{&http.Client{Transport: transport, Timeout: timeout}, url,
			body, make([]byte, 32768), version(tls12), cipher}
		if err := group[i].request(false); err != nil {
			return fmt.Errorf("warm-up: %w", err)
		}
	}
	failures := make(chan error, workers)
	var work sync.WaitGroup
	start := time.Now()
	for i := range group {
		work.Go(func() {
			for range iterations {
				if err := group[i].request(transfer); err != nil {
					failures <- err
					return
				}
			}
		})
	}
	work.Wait()
	seconds := time.Since(start).Seconds()
	close(failures)
	for err := range failures {
		return err
	}
	return json.NewEncoder(os.Stdout).Encode(map[string]any{
		"seconds": seconds, "requests": workers * iterations,
		"bytes": workers * iterations * len(body), "cipher": tls.CipherSuiteName(cipher),
	})
}

func main() {
	var err error
	switch {
	case len(os.Args) == 7 && os.Args[4] == "" && os.Args[6] == "":
		err = serve(os.Args[1], os.Args[2], os.Args[3], os.Args[5] == "tls12")
	case len(os.Args) == 10 && os.Args[1] == "load":
		workers, _ := strconv.Atoi(os.Args[8])
		iterations, _ := strconv.Atoi(os.Args[9])
		if workers <= 0 || iterations <= 0 ||
			(os.Args[5] != "handshake" && os.Args[5] != "transfer") ||
			(os.Args[6] != "1.2" && os.Args[6] != "1.3") ||
			(os.Args[7] != "base" && os.Args[7] != "native") {
			err = fmt.Errorf("invalid load arguments")
		} else {
			err = load(os.Args[2], os.Args[3], os.Args[4], os.Args[5],
				os.Args[6] == "1.2", os.Args[7] == "base", workers, iterations)
		}
	default:
		err = fmt.Errorf("expected server arguments or load address root file mode version cpu workers iterations")
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
