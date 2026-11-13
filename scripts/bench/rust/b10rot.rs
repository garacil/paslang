// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// GPL version 3 or later; see COPYING. No warranty.
// Standard-library benchmark twin of b10rot.paslang and b10rot.go.

fn main() {
    let (mut s0, mut s1, mut s2, mut s3, mut sum): (u64, u64, u64, u64, u64) = (1, 2, 3, 4, 0);
    for _i in 1..=100_000_000u64 {
        let r = s1.wrapping_mul(5).rotate_left(7).wrapping_mul(9);
        let t = s1 << 17;
        s2 ^= s0;
        s3 ^= s1;
        s1 ^= s2;
        s0 ^= s3;
        s2 ^= t;
        s3 = s3.rotate_left(45);
        sum = sum.wrapping_add(r);
    }
    println!("{} {}", sum as i64, s0 as i64);
}
