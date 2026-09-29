// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacil@tucall.com>
//
// paslang is free software: you can redistribute it and/or modify it
// under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// paslang is distributed in the hope that it will be useful, but
// WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
// General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with paslang.  If not, see <https://www.gnu.org/licenses/>.

// The Go twin of examples/dnsd.paslang: a DNS server over UDP with the
// same table (one.example, two.example, n.example), the messages built
// and read by hand as the paslang unit does, and the same self-test: n
// client goroutines ask a name each and check the answer.
package main

import (
	"encoding/binary"
	"fmt"
	"net"
	"os"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

var answered, missed, bad int64

func lookup(name string) uint32 {
	name = strings.TrimSuffix(name, ".")
	switch name {
	case "one.example":
		return 0x0A000001
	case "two.example":
		return 0x0A000002
	}
	if strings.HasSuffix(name, ".example") {
		v, err := strconv.Atoi(strings.TrimSuffix(name, ".example"))
		if err == nil && v >= 0 && v <= 65535 {
			return 0x0A000000 + uint32(v)
		}
	}
	return 0
}

func questionName(m []byte) (string, int) {
	p := 12
	var labels []string
	for p < len(m) {
		n := int(m[p])
		if n == 0 {
			return strings.Join(labels, "."), p + 1
		}
		if n&0xC0 != 0 || p+1+n > len(m) {
			return "", 0
		}
		labels = append(labels, string(m[p+1:p+1+n]))
		p += 1 + n
	}
	return "", 0
}

func replyHead(q []byte, flags uint16, an uint16, qend int) []byte {
	r := make([]byte, 0, qend+16)
	r = append(r, q[0], q[1])
	r = binary.BigEndian.AppendUint16(r, flags)
	r = append(r, 0, 1)
	r = binary.BigEndian.AppendUint16(r, an)
	r = append(r, 0, 0, 0, 0)
	r = append(r, q[12:qend+4]...)
	return r
}

func replyA(q []byte, qend int, ip uint32, ttl uint32) []byte {
	r := replyHead(q, 0x8180, 1, qend)
	r = append(r, 0xC0, 0x0C, 0, 1, 0, 1)
	r = binary.BigEndian.AppendUint32(r, ttl)
	r = append(r, 0, 4)
	r = binary.BigEndian.AppendUint32(r, ip)
	return r
}

func serve(c *net.UDPConn) {
	buf := make([]byte, 512)
	for {
		n, addr, err := c.ReadFromUDP(buf)
		if err != nil {
			return
		}
		q := buf[:n]
		name, qend := questionName(q)
		if name == "" || qend+4 > len(q) {
			atomic.AddInt64(&bad, 1)
			continue
		}
		ip := lookup(name)
		var reply []byte
		if ip == 0 {
			reply = replyHead(q, 0x8183, 0, qend)
			atomic.AddInt64(&missed, 1)
		} else {
			reply = replyA(q, qend, ip, 60)
			atomic.AddInt64(&answered, 1)
		}
		c.WriteToUDP(reply, addr)
	}
}

func queryA(name string, id uint16) []byte {
	q := binary.BigEndian.AppendUint16(nil, id)
	q = append(q, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0)
	for _, lab := range strings.Split(name, ".") {
		q = append(q, byte(len(lab)))
		q = append(q, lab...)
	}
	q = append(q, 0, 0, 1, 0, 1)
	return q
}

func answerA(m []byte, id uint16) string {
	if len(m) < 12 || binary.BigEndian.Uint16(m) != id {
		return ""
	}
	an := int(binary.BigEndian.Uint16(m[6:]))
	_, p := questionName(m)
	if p == 0 {
		return ""
	}
	p += 4
	for i := 0; i < an; i++ {
		if p+2 > len(m) {
			return ""
		}
		if m[p]&0xC0 == 0xC0 {
			p += 2
		} else {
			for p < len(m) && m[p] != 0 {
				p += 1 + int(m[p])
			}
			p++
		}
		if p+10 > len(m) {
			return ""
		}
		typ := binary.BigEndian.Uint16(m[p:])
		rdlen := int(binary.BigEndian.Uint16(m[p+8:]))
		p += 10
		if typ == 1 && rdlen == 4 && p+4 <= len(m) {
			return fmt.Sprintf("%d.%d.%d.%d", m[p], m[p+1], m[p+2], m[p+3])
		}
		p += rdlen
	}
	return ""
}

func client(port int, id int, wg *sync.WaitGroup) {
	defer wg.Done()
	c, err := net.ListenUDP("udp", &net.UDPAddr{IP: net.IPv4zero, Port: 0})
	if err != nil {
		atomic.AddInt64(&bad, 1)
		return
	}
	defer c.Close()
	server := &net.UDPAddr{IP: net.IPv4(127, 0, 0, 1), Port: port}
	q := queryA(fmt.Sprintf("%d.example", id), uint16(id))
	got := ""
	buf := make([]byte, 512)
	for try := 0; try < 3 && got == ""; try++ {
		if _, err := c.WriteToUDP(q, server); err != nil {
			break
		}
		c.SetReadDeadline(time.Now().Add(2 * time.Second))
		n, _, err := c.ReadFromUDP(buf)
		if err == nil {
			got = answerA(buf[:n], uint16(id))
		}
	}
	want := fmt.Sprintf("10.0.%d.%d", id>>8, id&255)
	if got != want {
		atomic.AddInt64(&bad, 1)
	}
}

func selfTest(n int) {
	s, err := net.ListenUDP("udp", &net.UDPAddr{IP: net.IPv4zero, Port: 0})
	if err != nil {
		fmt.Println("dnsd: cannot bind")
		os.Exit(1)
	}
	s.SetReadBuffer(8 << 20)
	port := s.LocalAddr().(*net.UDPAddr).Port
	go serve(s)
	var wg sync.WaitGroup
	wg.Add(n)
	for i := 1; i <= n; i++ {
		go client(port, i, &wg)
	}
	wg.Wait()
	fmt.Printf("%d clients, %d answered, %d missed, %d bad\n", n, atomic.LoadInt64(&answered), atomic.LoadInt64(&missed), atomic.LoadInt64(&bad))
	if answered != int64(n) || bad != 0 {
		os.Exit(1)
	}
}

func main() {
	if len(os.Args) >= 2 && os.Args[1] == "-selftest" {
		n := 2000
		if len(os.Args) >= 3 {
			n, _ = strconv.Atoi(os.Args[2])
		}
		selfTest(n)
		return
	}
	port := 5353
	if len(os.Args) >= 2 {
		port, _ = strconv.Atoi(os.Args[1])
	}
	s, err := net.ListenUDP("udp", &net.UDPAddr{Port: port})
	if err != nil {
		fmt.Println("dnsd: cannot bind port", port)
		os.Exit(1)
	}
	fmt.Println("dnsd: serving one.example, two.example and <n>.example on UDP port", port)
	serve(s)
}
