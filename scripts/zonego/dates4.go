// dates4.go writes testdata/dates4.out: Go's time.Date for the local dates of
// testdata/dates4.paslang (P461), the seconds around the changes of summer
// time of the five zones in 2026, a time the clock showed twice or skipped
// included: the moment Date gives it, the offset it takes off the time, and
// the time the clock shows at that moment, under TZ set to each file of
// testdata/zoneinfo in turn, as make check runs it:
//
//   for z in Europe_Madrid America_New_York Asia_Kolkata Australia_Sydney Pacific_Chatham; do
//     TZ=$PWD/testdata/zoneinfo/$z go run scripts/zonego/dates4.go; done > testdata/dates4.out
//
// This file is part of paslang. Copyright (C) 2026 Germán Luis Aracil Boned
// <garacilb@gmail.com>. paslang is free software under the GNU General Public
// License, version 3 or (at your option) any later version; see the file COPYING.

package main

import (
	"fmt"
	"time"
)

func f(t time.Time) string { return t.Format("2006-01-02 15:04:05") }

func main() {
	ms := [][6]int{
		{2026, 10, 25, 1, 59, 59}, {2026, 10, 25, 2, 0, 0}, {2026, 10, 25, 2, 7, 23},
		{2026, 10, 25, 2, 59, 59}, {2026, 10, 25, 3, 0, 0}, {2026, 3, 29, 1, 59, 59},
		{2026, 3, 29, 2, 0, 0}, {2026, 3, 29, 2, 30, 0}, {2026, 3, 29, 3, 0, 0}, {2026, 11, 1, 0, 59, 59},
		{2026, 11, 1, 1, 0, 0}, {2026, 11, 1, 1, 30, 0}, {2026, 11, 1, 2, 0, 0}, {2026, 3, 8, 1, 59, 59},
		{2026, 3, 8, 2, 0, 0}, {2026, 3, 8, 2, 30, 0}, {2026, 3, 8, 3, 0, 0}, {2026, 4, 5, 1, 59, 59},
		{2026, 4, 5, 2, 0, 0}, {2026, 4, 5, 2, 30, 0}, {2026, 4, 5, 3, 0, 0}, {2026, 10, 4, 1, 59, 59},
		{2026, 10, 4, 2, 0, 0}, {2026, 10, 4, 2, 30, 0}, {2026, 10, 4, 3, 0, 0}, {2026, 4, 5, 3, 29, 59},
		{2026, 4, 5, 3, 30, 0}, {2026, 4, 5, 3, 44, 59}, {2026, 4, 5, 3, 45, 0}, {2026, 4, 5, 4, 0, 0},
		{2026, 9, 27, 2, 30, 0}, {2026, 9, 27, 2, 45, 0}, {2026, 9, 27, 3, 0, 0}, {2026, 9, 27, 3, 15, 0},
		{2026, 9, 27, 3, 45, 0}, {2026, 9, 27, 4, 0, 0},
	}
	for _, m := range ms {
		lt := time.Date(m[0], time.Month(m[1]), m[2], m[3], m[4], m[5], 0, time.Local)
		ut := time.Date(m[0], time.Month(m[1]), m[2], m[3], m[4], m[5], 0, time.UTC)
		fmt.Printf("%s utc %s off %d back %s\n", f(ut), f(lt.UTC()), ut.Unix()-lt.Unix(), f(lt))
	}
}
