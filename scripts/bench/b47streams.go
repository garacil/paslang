// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// P656: equivalent to b47streams.paslang. ReadString returns owned lines,
// and net/http reads the 32 fixed-length responses from the same script.
package main

import (
	"bufio"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"strings"
	"time"
)

const (
	httpRequests  = 32
	httpBlocks    = 128
	blockBytes    = 65536
	linesPerBlock = 256
	lineBlocks    = 800
	lineBytes     = 111
	deadline      = 30 * time.Second
)

func check(err error) {
	if err != nil {
		panic(err)
	}
}

func serve(listener net.Listener, isHTTP bool) {
	stream, err := listener.Accept()
	check(err)
	defer stream.Close()
	check(stream.SetDeadline(time.Now().Add(deadline)))
	write := func(s string) {
		n, err := io.WriteString(stream, s)
		check(err)
		if n != len(s) {
			panic("short write")
		}
	}
	if isHTTP {
		header := fmt.Sprintf("HTTP/1.1 200 OK\r\nContent-Length: %d\r\n\r\n", httpBlocks*blockBytes)
		payload := strings.Repeat("x", blockBytes)
		reader := bufio.NewReaderSize(stream, 16384)
		for i := 0; i < httpRequests; i++ {
			for {
				line, err := reader.ReadString('\n')
				check(err)
				if line == "\r\n" {
					break
				}
			}
			write(header)
			for j := 0; j < httpBlocks; j++ {
				write(payload)
			}
		}
	} else {
		var payload strings.Builder
		for i := 0; i < linesPerBlock; i++ {
			payload.WriteString(strings.Repeat(string(rune('a'+i%26)), lineBytes))
			payload.WriteString("\r\n")
		}
		for i := 0; i < lineBlocks; i++ {
			write(payload.String())
		}
	}
}

func readHTTP(address string) {
	transport := &http.Transport{DisableCompression: true}
	defer transport.CloseIdleConnections()
	client := &http.Client{Transport: transport, Timeout: deadline}
	buffer := make([]byte, blockBytes)
	total := 0
	for i := 0; i < httpRequests; i++ {
		response, err := client.Get("http://" + address + "/")
		check(err)
		if response.StatusCode != http.StatusOK {
			panic(response.Status)
		}
		count := 0
		for {
			n, err := response.Body.Read(buffer)
			if n > 0 {
				if buffer[0] != 'x' || buffer[n-1] != 'x' {
					panic("wrong body")
				}
				count += n
			}
			if err == io.EOF {
				break
			}
			check(err)
		}
		check(response.Body.Close())
		if count != httpBlocks*blockBytes {
			panic("wrong body length")
		}
		total += count
	}
	fmt.Println("http", httpRequests, total)
}

func readLines(address string) {
	stream, err := net.DialTimeout("tcp4", address, deadline)
	check(err)
	defer stream.Close()
	check(stream.SetReadDeadline(time.Now().Add(deadline)))
	reader := bufio.NewReaderSize(stream, 16384)
	for i := 0; i < lineBlocks*linesPerBlock; i++ {
		line, err := reader.ReadString('\n')
		check(err)
		line = strings.TrimSuffix(strings.TrimSuffix(line, "\n"), "\r")
		expected := byte('a' + (i%linesPerBlock)%26)
		if len(line) != lineBytes || line[0] != expected || line[lineBytes-1] != expected {
			panic("wrong line")
		}
	}
	if line, err := reader.ReadString('\n'); line != "" || err != io.EOF {
		panic("expected EOF")
	}
	fmt.Println("lines", lineBlocks*linesPerBlock, lineBlocks*linesPerBlock*lineBytes)
}

func main() {
	isHTTP := len(os.Args) > 1 && os.Args[1] == "http"
	listener, err := net.Listen("tcp4", "127.0.0.1:0")
	check(err)
	defer listener.Close()
	done := make(chan struct{})
	go func() {
		serve(listener, isHTTP)
		close(done)
	}()
	if isHTTP {
		readHTTP(listener.Addr().String())
	} else {
		readLines(listener.Addr().String())
	}
	<-done
}
