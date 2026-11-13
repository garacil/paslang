// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// GPL version 3 or later; see COPYING. No warranty.
// Standard-library benchmark twin of b14sort.paslang and b14sort.go.

use std::env;
use std::process;


fn next(x: &mut i64) -> u64 {
    *x = x.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
    *x as u64
}

fn main() {
    let mut x: i64 = 12345;
    let arg = env::args().nth(1).unwrap_or_default();
    match arg.as_str() {
        "ints" => {
            let n = 2_000_000usize;
            let mut a: Vec<i64> = (0..n).map(|_| (next(&mut x) >> 11) as i64).collect();
            a.sort_unstable();
            println!("{} {} {}", a[0], a[n / 2], a[n - 1]);
        }
        "strings" => {
            let n = 500_000usize;
            let mut a: Vec<String> = (0..n).map(|_| format!("k{}", next(&mut x) >> 40)).collect();
            a.sort_unstable();
            println!("{} {} {}", a[0], a[n / 2], a[n - 1]);
        }
        "reals" => {
            let n = 2_000_000usize;
            let mut a: Vec<f64> = (0..n).map(|_| (next(&mut x) >> 11) as f64 / 9007199254740992.0).collect();
            a.sort_unstable_by(|p, q| p.partial_cmp(q).unwrap());
            println!("{} {} {}", (a[0] * 1e15) as i64, (a[n / 2] * 1e15) as i64, (a[n - 1] * 1e15) as i64);
        }
        _ => {
            println!("b14sort: ints, strings or reals");
            process::exit(2);
        }
    }
}
