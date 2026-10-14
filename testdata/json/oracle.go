// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// GPL version 3 or later; see COPYING. No warranty.

// The oracle of P203's parser and writer, Go's encoding/json/v2 (built
// with GOEXPERIMENT=jsonv2 by scripts/check_json.py, a test tool only).
// Each line of the input is a document in hex, "-" the empty one. The
// mode (the first argument) says what to write for each:
//
//	p  "ok" and the document written compact (a string with the fewest
//	   escapes, a number as its text), or "err", the byte offset, the
//	   JSON Pointer in hex ("-" empty; past 100 bytes "sha256:" and
//	   the hex of its SHA-256) and the reason, as Go's
//	   jsontext.SyntacticError holds them
//	i  the same, the document a value a line, two spaces a level
//	c  the same, the document in RFC 8785's form (Value.Canonicalize)
//
// A written document longer than 200 bytes, and every one a value a
// line, is given as "sha256" and the hex of its SHA-256, so the
// expected outputs stay small and a line each.
package main

import (
	"bufio"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json/jsontext"
	"encoding/json/v2"
	"errors"
	"fmt"
	"os"
	"strings"
)

func write(b []byte, mode string) (string, error) {
	if mode == "c" {
		v := jsontext.Value(append([]byte(nil), b...))
		if err := v.Canonicalize(); err != nil {
			return "", err
		}
		return string(v), nil
	}
	d := jsontext.NewDecoder(bytes.NewReader(b))
	var out bytes.Buffer
	var opts []jsontext.Options
	if mode == "i" {
		opts = append(opts, jsontext.WithIndent("  "))
	}
	e := jsontext.NewEncoder(&out, opts...)
	for {
		tok, err := d.ReadToken()
		if err != nil {
			break
		}
		if tok.Kind() == '"' {
			tok = jsontext.String(tok.String())
		}
		if err := e.WriteToken(tok); err != nil {
			return "", err
		}
	}
	return strings.TrimSuffix(out.String(), "\n"), nil
}

func main() {
	mode := os.Args[1]
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 1<<20), 1<<28)
	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()
	for sc.Scan() {
		var b []byte
		if sc.Text() != "-" {
			var err error
			if b, err = hex.DecodeString(sc.Text()); err != nil {
				fmt.Fprintln(os.Stderr, "oracle: a line is no hex")
				os.Exit(2)
			}
		}
		var v jsontext.Value
		err := json.Unmarshal(b, &v)
		if err == nil {
			t, err := write(b, mode)
			if err != nil {
				fmt.Fprintln(os.Stderr, "oracle: cannot write a valid document:", err)
				os.Exit(2)
			}
			if mode == "i" || len(t) > 200 {
				sum := sha256.Sum256([]byte(t))
				t = "sha256 " + hex.EncodeToString(sum[:])
			}
			fmt.Fprintf(w, "ok %s\n", t)
			continue
		}
		var se *jsontext.SyntacticError
		if !errors.As(err, &se) {
			fmt.Fprintln(os.Stderr, "oracle: not a syntactic error:", err)
			os.Exit(2)
		}
		p := hex.EncodeToString([]byte(se.JSONPointer))
		if p == "" {
			p = "-"
		} else if len(se.JSONPointer) > 100 {
			sum := sha256.Sum256([]byte(se.JSONPointer))
			p = "sha256:" + hex.EncodeToString(sum[:])
		}
		fmt.Fprintf(w, "err %d %s %v\n", se.ByteOffset, p, se.Err)
	}
}
