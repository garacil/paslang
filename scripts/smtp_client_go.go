// smtp_client_go.go: what Go's net/smtp does with the scenarios of
// testdata/smtp.txt (scripts/smtp_cases.py writes it). Each scenario is a
// script for a server (replies given in turn) and a mail to send; this prints,
// for each, the lines the server received and how SendMail ended, in the
// format testdata/smtp.paslang prints for passmtp. Run:
//
//	go run scripts/smtp_client_go.go testdata/smtp.txt
package main

import (
	"bufio"
	"encoding/base64"
	"errors"
	"fmt"
	"net"
	"net/smtp"
	"os"
	"strings"
)

type scenario struct {
	name    string
	replies []string
	auth    []string
	from    string
	rcpts   []string
	msg     string
}

func un64(s string) string {
	if s == "-" {
		return ""
	}
	b, err := base64.StdEncoding.DecodeString(s)
	if err != nil {
		panic(err)
	}
	return string(b)
}

func esc(s string) string {
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		c := s[i]
		switch {
		case c == '\\':
			b.WriteString("\\\\")
		case c == '\r':
			b.WriteString("\\r")
		case c == '\n':
			b.WriteString("\\n")
		case c >= 32 && c < 127:
			b.WriteByte(c)
		default:
			fmt.Fprintf(&b, "\\x%02x", c)
		}
	}
	return b.String()
}

func read(path string) []*scenario {
	data, err := os.ReadFile(path)
	if err != nil {
		panic(err)
	}
	var out []*scenario
	var cur *scenario
	for _, ln := range strings.Split(string(data), "\n") {
		if ln == "" {
			continue
		}
		op, rest, _ := strings.Cut(ln, " ")
		switch op {
		case "case":
			cur = &scenario{name: rest}
		case "reply":
			cur.replies = append(cur.replies, un64(rest))
		case "auth":
			cur.auth = strings.Split(rest, " ")
		case "from":
			cur.from = un64(rest)
		case "rcpt":
			cur.rcpts = append(cur.rcpts, un64(rest))
		case "msg":
			cur.msg = un64(rest)
		case "end":
			out = append(out, cur)
		}
	}
	return out
}

func serve(l net.Listener, replies []string, out *strings.Builder, done chan struct{}) {
	defer close(done)
	conn, err := l.Accept()
	if err != nil {
		return
	}
	defer conn.Close()
	r := bufio.NewReader(conn)
	idx := 0
	last := ""
	closed := false
	// a reply is sent; when it was the script's last the server stops
	// writing (the client reads the end of the stream) and goes on reading
	send := func() {
		if closed {
			return
		}
		if idx < len(replies) {
			last = replies[idx]
			conn.Write([]byte(last))
			idx++
		}
		if idx >= len(replies) {
			conn.(*net.TCPConn).CloseWrite()
			closed = true
		}
	}
	send()
	for {
		if strings.HasPrefix(last, "354") {
			var data []byte
			for !strings.HasSuffix(string(data), "\r\n.\r\n") {
				b, err := r.ReadByte()
				if err != nil {
					if len(data) > 0 {
						fmt.Fprintf(out, "D: %s\n", esc(string(data)))
					}
					return
				}
				data = append(data, b)
			}
			fmt.Fprintf(out, "D: %s\n", esc(string(data)))
			last = ""
		} else {
			line, err := r.ReadString('\n')
			if err != nil {
				if line != "" {
					fmt.Fprintf(out, "C: %s\n", esc(line))
				}
				return
			}
			fmt.Fprintf(out, "C: %s\n", esc(strings.TrimSuffix(line, "\n")))
		}
		send()
	}
}

type loginAuth struct {
	user, pass string
	step       int
}

func (a *loginAuth) Start(s *smtp.ServerInfo) (string, []byte, error) {
	if !s.TLS && s.Name != "localhost" && s.Name != "127.0.0.1" && s.Name != "::1" {
		return "", nil, errors.New("unencrypted connection")
	}
	return "LOGIN", nil, nil
}

func (a *loginAuth) Next(from []byte, more bool) ([]byte, error) {
	if !more {
		return nil, nil
	}
	a.step++
	switch a.step {
	case 1:
		return []byte(a.user), nil
	case 2:
		return []byte(a.pass), nil
	}
	return nil, errors.New("unexpected server challenge")
}

func main() {
	for _, sc := range read(os.Args[1]) {
		l, err := net.Listen("tcp", "127.0.0.1:0")
		if err != nil {
			panic(err)
		}
		var out strings.Builder
		done := make(chan struct{})
		go serve(l, sc.replies, &out, done)
		var auth smtp.Auth
		if len(sc.auth) == 3 {
			u, p := un64(sc.auth[1]), un64(sc.auth[2])
			switch sc.auth[0] {
			case "plain":
				auth = smtp.PlainAuth("", u, p, "127.0.0.1")
			case "cram":
				auth = smtp.CRAMMD5Auth(u, p)
			case "login":
				auth = &loginAuth{user: u, pass: p}
			}
		}
		err = smtp.SendMail(l.Addr().String(), auth, sc.from, sc.rcpts, []byte(sc.msg))
		l.Close()
		<-done
		fmt.Printf("== %s\n%s", sc.name, out.String())
		if err != nil {
			fmt.Printf("=> error: %s\n", esc(err.Error()))
		} else {
			fmt.Printf("=> ok\n")
		}
	}
}
