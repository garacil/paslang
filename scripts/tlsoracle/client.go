// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

package main

import (
	"bufio"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"time"
)

// Check certificate authentication, the handshake and the HTTP exchange
// with an independent TLS stack over TCP.
func checkServer(addr, root string) error {
	pem, err := os.ReadFile(root)
	if err != nil {
		return err
	}
	roots := x509.NewCertPool()
	if !roots.AppendCertsFromPEM(pem) {
		return fmt.Errorf("cannot read test root")
	}
	cfg := &tls.Config{RootCAs: roots, ServerName: "localhost", NextProtos: []string{"http/1.1"},
		MinVersion: tls.VersionTLS13, MaxVersion: tls.VersionTLS13}
	conn, err := tls.DialWithDialer(&net.Dialer{Timeout: 5 * time.Second}, "tcp", addr, cfg)
	if err != nil {
		return err
	}
	defer conn.Close()
	if err := conn.SetDeadline(time.Now().Add(5 * time.Second)); err != nil {
		return err
	}
	if conn.ConnectionState().NegotiatedProtocol != "http/1.1" {
		return fmt.Errorf("unexpected ALPN")
	}
	if _, err := io.WriteString(conn, "GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"); err != nil {
		return err
	}
	resp, err := http.ReadResponse(bufio.NewReader(conn), nil)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return err
	}
	if resp.StatusCode != http.StatusOK || string(body) != "hello over TLS\n" {
		return fmt.Errorf("unexpected response status or body")
	}
	return nil
}
