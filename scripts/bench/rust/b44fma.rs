// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// GPL version 3 or later; see COPYING. No warranty.
// Fused Horner twin of b44fma.paslang and b44fma.go: sixteen coefficients
// at thirty million points, retaining the complete final sum's bit pattern.

fn horner(x: f64) -> f64 {
    let mut r = 0.0_f64;
    for i in 1..=16_i64 {
        r = r.mul_add(x, i as f64);
    }
    r
}

fn main() {
    let mut total = 0.0_f64;
    for k in 0..30_000_000_i64 {
        let x = (k % 2000) as f64 / 2000.0 - 0.5;
        total += horner(x);
    }
    println!("{}", total.to_bits() as i64);
}
