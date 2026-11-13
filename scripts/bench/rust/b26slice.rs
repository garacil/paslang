// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// GPL version 3 or later; see COPYING. No warranty.
// Standard-library benchmark twin of b26slice.paslang and b26slice.go.

use std::env;
use std::process;

fn main() {
    let mut t: usize = 0;
    let arg = env::args().nth(1).unwrap_or_default();
    match arg.as_str() {
        "ints" => {
            let mut a: Vec<i64> = Vec::new();
            for i in 1..=20_000_000i64 {
                a.push(i * 3);
            }
            for i in 0..a.len() {
                t += (a[i] & 7) as usize;
            }
            println!("{} {}", a.len(), t);
        }
        "strings" => {
            let mut b: Vec<String> = Vec::new();
            for i in 1..=2_000_000i64 {
                b.push(format!("k{}", i));
            }
            for i in 0..b.len() {
                t += b[i].len();
            }
            println!("{} {}", b.len(), t);
        }
        _ => {
            println!("b26slice: ints or strings");
            process::exit(2);
        }
    }
}
