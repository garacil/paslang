// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// GPL version 3 or later; see COPYING. No warranty.
// Read-only metadata probe. The exact Go source/layout is checked before build.
package main

import (
    "encoding/json"
    _ "net/http" // Exercise the actual vendored x/sys/cpu initializer too.
    "os"
    "reflect"
    "runtime"
    _ "unsafe"
)

// internal/cpu explicitly publishes X86 with go:linkname. This declaration is
// only valid with the exact reviewed cpu.go and amd64 CacheLinePadSize=64.
//go:linkname x86 internal/cpu.X86
var x86 struct {
    _ [64]byte
    HasAES bool
    HasADX bool
    HasAVX bool
    HasAVXVNNI bool
    HasAVX2 bool
    HasAVX512 bool
    HasAVX512F bool
    HasAVX512CD bool
    HasAVX512BW bool
    HasAVX512DQ bool
    HasAVX512VL bool
    HasAVX512GFNI bool
    HasAVX512VAES bool
    HasAVX512VNNI bool
    HasAVX512VBMI bool
    HasAVX512VBMI2 bool
    HasAVX512BITALG bool
    HasAVX512VPOPCNTDQ bool
    HasAVX512VPCLMULQDQ bool
    HasBMI1 bool
    HasBMI2 bool
    HasERMS bool
    HasFSRM bool
    HasFMA bool
    HasGFNI bool
    HasOSXSAVE bool
    HasPCLMULQDQ bool
    HasPOPCNT bool
    HasRDTSCP bool
    HasSHA bool
    HasSSE3 bool
    HasSSSE3 bool
    HasSSE41 bool
    HasSSE42 bool
    HasVAES bool
    HasVPCLMULQDQ bool
    _ [64]byte
}

// Go internal/cpu/cpu_x86.s and AMD64 APM vol.3 CPUID pp.171-173.
func cpuid(eaxArg, ecxArg uint32) (eax, ebx, ecx, edx uint32)

func leaf(eax, ecx uint32) [4]uint32 {
    a,b,c,d := cpuid(eax,ecx)
    return [4]uint32{a,b,c,d}
}

func main() {
    leaves := map[string][4]uint32{"0":leaf(0,0), "80000000":leaf(0x80000000,0)}
    if leaves["0"][0] >= 1 { leaves["1"] = leaf(1,0) }
    if leaves["0"][0] >= 7 {
        leaves["7_0"] = leaf(7,0)
        if leaves["7_0"][0] >= 1 { leaves["7_1"] = leaf(7,1) }
    }
    if leaves["80000000"][0] >= 0x80000001 { leaves["80000001"] = leaf(0x80000001,0) }
    flags := map[string]bool{}
    value := reflect.ValueOf(x86)
    for i:=0; i<value.NumField(); i++ {
        if value.Field(i).Kind() == reflect.Bool {
            flags[value.Type().Field(i).Name] = value.Field(i).Bool()
        }
    }
    if err:=json.NewEncoder(os.Stdout).Encode(map[string]any{
        "internal":flags,"cpuid":leaves,"version":runtime.Version(),
        "goarch":runtime.GOARCH,"goos":runtime.GOOS,
    }); err != nil { panic(err) }
}
