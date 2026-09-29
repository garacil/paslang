// The Go twin of testdata/narrowgo.paslang (P99): the same lines, where
// the rules of the narrow integers are Go's.
package main

import "fmt"

func main() {
	var b uint8 = 255
	b = b + 1
	var w uint16 = 65535
	w = w + 1
	var s8 int8 = 127
	s8 = s8 + 1
	var s16 int16 = -32768
	s16 = s16 - 1
	var u32 uint32 = 4294967295
	u32 = u32 + 1
	var s32 int32 = 2147483647
	s32 = s32 + 1
	fmt.Println(b, w, s8, s16, u32, s32)
	x := 300
	fmt.Println(uint8(x), int8(x-100), uint16(-x), uint32(-x), int32(4294967295+x))
	x = -1
	fmt.Println(uint8(x), uint16(x), uint32(x), int16(x))
	s8 = -128
	var m1 int8 = -1
	s8 = s8 / m1
	fmt.Println(s8)
	s8 = -7
	fmt.Println(s8/2, s8%3, s8>>1)
	b = 200
	fmt.Println(b>>1, b/3, b%7, b<<1, b*2, b+100)
	s16 = -1
	s32 = -256
	u32 = 4294967295
	fmt.Println(s16>>4, s32>>4, u32>>31)
	b = 1
	b = -b
	s8 = -128
	s8 = -s8
	fmt.Println(b, s8, ^b, ^s8)
	w = 300
	w = w * w
	s32 = 100000
	s32 = s32 * s32
	fmt.Println(w, s32)
	b = 200
	s8 = -100
	fmt.Println(int16(b)+int16(s8), int32(uint16(65535))+int32(int16(-1)))
}
