// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// GPL version 3 or later; see COPYING. No warranty.
// Standard-library benchmark twin of b1loop.paslang and b1loop.go.

fn main() {
    let n: i64 = 1_000_000_000;
    let mut s: i64 = 0;
    let mut i: i64 = 1;
    while i <= n {
        s = s.wrapping_add((i ^ s) & 255);
        i += 1;
    }
    println!("{}", s);
}
