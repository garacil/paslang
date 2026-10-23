// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// The oracle of testdata/zones (P435): what Go's time.LoadLocation gives
// for the zones and moments testdata/zones.paslang asks LoadZone, as the
// lines that program prints. It reads the system's zoneinfo, as the
// program does (ZONEINFO unset).
//
//	go run scripts/zone_oracle.go > testdata/zones.out
package main

import (
	"fmt"
	"time"
)

var gs uint64

func gnext() uint64 {
	gs += 0x9e3779b97f4a7c15
	z := gs
	z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9
	z = (z ^ (z >> 27)) * 0x94d049bb133111eb
	return z ^ (z >> 31)
}

type fnv struct{ h uint64 }

func newFnv() *fnv { return &fnv{0xcbf29ce484222325} }
func (f *fnv) add(s string) {
	for i := 0; i < len(s); i++ {
		f.h ^= uint64(s[i])
		f.h *= 0x100000001b3
	}
	f.h ^= 0xff
	f.h *= 0x100000001b3
}

func main() {
	zones := []string{"Europe/Madrid", "America/New_York", "Pacific/Kiritimati", "Asia/Kolkata", "Australia/Lord_Howe",
		"America/Sao_Paulo", "UTC", "", "Asia/Kathmandu", "Pacific/Chatham", "Europe/Dublin", "Africa/Casablanca",
		"Etc/GMT+5", "America/St_Johns"}
	fixed := []int64{0, 1000000000, 1700000000, 1711846800, 1711846799, 1729990800, 1729990799, 1893456000, 2147483647, 2556143999, 4102444800}
	for _, name := range zones {
		loc, err := time.LoadLocation(name)
		if err != nil {
			fmt.Printf("zone \"%s\" nil\n", name)
			continue
		}
		fmt.Printf("zone \"%s\" %s\n", name, loc.String())
		for _, t := range fixed {
			tm := time.Unix(t, 0).In(loc)
			ab, off := tm.Zone()
			fmt.Printf("  at %d %s %d dst %v %04d-%02d-%02d %02d:%02d:%02d\n", t, ab, off, tm.IsDST(), tm.Year(), int(tm.Month()), tm.Day(), tm.Hour(), tm.Minute(), tm.Second())
		}
		gs = 7
		f := newFnv()
		for k := 0; k < 20000; k++ {
			t := 315532800 + int64(gnext()>>11)%(2840140800-315532800)
			tm := time.Unix(t, 0).In(loc)
			ab, off := tm.Zone()
			f.add(fmt.Sprintf("%s %d %v %d-%d-%d %d:%d:%d", ab, off, tm.IsDST(), tm.Year(), int(tm.Month()), tm.Day(), tm.Hour(), tm.Minute(), tm.Second()))
		}
		fmt.Printf("  random moments %016x\n", f.h)
		f = newFnv()
		for k := 0; k < 20000; k++ {
			y := 1980 + int(gnext()>>40)%80
			mo := 1 + int(gnext()>>40)%12
			d := 1 + int(gnext()>>40)%28
			h := int(gnext()>>40) % 24
			mi := int(gnext()>>40) % 60
			se := int(gnext()>>40) % 60
			f.add(fmt.Sprintf("%d", time.Date(y, time.Month(mo), d, h, mi, se, 0, loc).Unix()))
		}
		fmt.Printf("  random readings %016x\n", f.h)
	}
	for _, name := range []string{"Nowhere/City", "../etc/passwd", "/usr/share/zoneinfo/UTC", "Europe/../UTC", "\\x", "Europe/Madrid/"} {
		_, err := time.LoadLocation(name)
		fmt.Printf("bad \"%s\" %v\n", name, err != nil)
	}
	// the readings a clock skipped or showed twice (Madrid, 2024)
	loc, _ := time.LoadLocation("Europe/Madrid")
	fmt.Printf("gap %d\n", time.Date(2024, 3, 31, 2, 30, 0, 0, loc).Unix())
	fmt.Printf("twice %d\n", time.Date(2024, 10, 27, 2, 30, 0, 0, loc).Unix())
}
