// dates3.go writes testdata/dates3.out: Go's time.Local for the dates of
// testdata/dates3.paslang (P131), SysUtils' file dates, offsets and
// conversions as Go works them out, under TZ set to each file of
// testdata/zoneinfo in turn, as make check runs it:
//
//   for z in Europe_Madrid America_New_York Asia_Kolkata Australia_Sydney Pacific_Chatham; do
//     TZ=$PWD/testdata/zoneinfo/$z go run scripts/zonego/dates3.go; done > testdata/dates3.out
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
	ms := [][6]int{{2026, 1, 15, 12, 0, 0}, {2026, 7, 15, 12, 0, 0}, {1999, 12, 31, 23, 30, 0}, {2038, 1, 19, 3, 14, 7},
		{1985, 6, 1, 6, 0, 0}, {2026, 10, 25, 12, 0, 0}, {2026, 3, 1, 0, 0, 0}, {2080, 8, 8, 8, 8, 8},
		{1970, 1, 2, 0, 0, 0}, {2010, 11, 7, 12, 0, 0}, {1950, 6, 15, 9, 30, 0}, {1901, 1, 1, 0, 0, 0}}
	for _, m := range ms {
		lt := time.Date(m[0], time.Month(m[1]), m[2], m[3], m[4], m[5], 0, time.Local)
		fd := lt.Unix()
		ut := time.Date(m[0], time.Month(m[1]), m[2], m[3], m[4], m[5], 0, time.UTC)
		fmt.Printf("%s fd %d ufd %d back %s univ %s +100 %s", f(ut), fd, ut.Unix(), f(time.Unix(fd, 0).In(time.Local)),
			f(time.Unix(fd, 0).UTC()), f(time.Unix(fd+8640000, 0).In(time.Local)))
		_, offU := ut.In(time.Local).Zone()
		_, offL := lt.Zone()
		dstU := ut.In(time.Local).IsDST()
		dstL := lt.IsDST()
		b := func(x bool) int { if x { return 1 }; return 0 }
		// FPC's sign: minutes to add to local for UTC; div truncates
		fmt.Printf(" offU %d %d offL %d %d", -offU/60, b(dstU), -offL/60, b(dstL))
		fmt.Printf(" u2l %s l2u %s\n", f(ut.Add(time.Duration(offU)*time.Second)), f(ut.Add(-time.Duration(offL)*time.Second)))
	}
}
