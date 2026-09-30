// zone1.go writes testdata/zone1.out: Go's time.Local for the moments
// and local dates of testdata/zone1.paslang (P131), under TZ set to each
// file of testdata/zoneinfo in turn, as make check runs it:
//
//   for z in Europe_Madrid America_New_York Asia_Kolkata Australia_Sydney Pacific_Chatham; do
//     TZ=$PWD/testdata/zoneinfo/$z go run scripts/zonego/zone1.go; done > testdata/zone1.out
//
// This file is part of paslang. Copyright (C) 2026 Germán Luis Aracil Boned
// <garacilb@gmail.com>. paslang is free software under the GNU General Public
// License, version 3 or (at your option) any later version; see the file COPYING.

package main

import (
	"fmt"
	"time"
)

func stamp(t time.Time) string { return t.Format("2006-01-02 15:04:05") }

func b(x bool) int {
	if x {
		return 1
	}
	return 0
}

func main() {
	moments := []int64{-5000000000, -2208988800, -1000000000, -1, 0, 1,
		500000000, 1000000000, 1234567890, 1500000000,
		1774746000, 1774749599, 1774749600, 1761440400,
		1761443999, 1761444000, 1772953200, 1772960400,
		1759586400, 1775311200, 2147483647, 2147483648,
		3500000000, 4102444800}
	for _, m := range moments {
		lt := time.Unix(m, 0).In(time.Local)
		abbr, off := lt.Zone()
		back := time.Date(lt.Year(), lt.Month(), lt.Day(), lt.Hour(), lt.Minute(), lt.Second(), 0, time.Local).Unix()
		fmt.Printf("%d %s %d %d %s %d %d %d %d\n", m, abbr, off, b(lt.IsDST()), stamp(lt), int(lt.Weekday()), lt.YearDay(), back, off)
	}
	locals := [][6]int{{2026, 3, 29, 2, 30, 0}, {2026, 10, 25, 2, 30, 0},
		{2026, 3, 8, 2, 30, 0}, {2026, 11, 1, 1, 30, 0},
		{2026, 4, 5, 2, 30, 0}, {2026, 10, 4, 2, 30, 0},
		{1900, 1, 1, 0, 0, 0}, {2080, 7, 1, 12, 0, 0},
		{1970, 1, 1, 0, 0, 0}, {2026, 9, 30, 14, 5, 7}}
	for _, l := range locals {
		t := time.Date(l[0], time.Month(l[1]), l[2], l[3], l[4], l[5], 0, time.Local)
		u := t.Unix()
		z := time.Unix(u, 0).In(time.Local)
		abbr, off := z.Zone()
		fmt.Printf("%d-%d-%d %d:%d %d %s %d %s\n", l[0], l[1], l[2], l[3], l[4], u, abbr, off, stamp(z))
	}
}
