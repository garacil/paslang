// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// GPL version 3 or later; see COPYING. No warranty.
// Standard-library benchmark twin of b31map.paslang and b31map.go.

use std::collections::HashMap;
use std::env;
use std::process;

fn main() {
    let mut m: HashMap<i64, i64> = HashMap::new();
    let mut d: HashMap<i64, f64> = HashMap::new();
    let arg = env::args().nth(1).unwrap_or_default();
    if arg != "sums" && arg != "bits" {
        for i in 1..=1_000_000i64 {
            m.insert(i * 7919, i);
        }
    }
    let mut t: i64 = 0;
    match arg.as_str() {
        "iter" => {
            for _r in 1..=20 {
                for (k, v) in &m {
                    t += k ^ v;
                }
            }
        }
        "delete" => {
            for i in 1..=1_000_000i64 {
                m.remove(&(i * 7919));
            }
            t = 1;
        }
        "update" => {
            for _r in 1..=10 {
                for i in 1..=1_000_000i64 {
                    *m.entry(i * 7919).or_insert(0) += 1;
                }
            }
            t = m.get(&7919).copied().unwrap_or(0) + m.get(&(7919 * 1_000_000)).copied().unwrap_or(0);
        }
        "sums" => {
            for _r in 1..=10 {
                for i in 1..=1_000_000i64 {
                    *d.entry(i * 7919).or_insert(0.0) += 0.5;
                }
            }
            t = (d.get(&7919).copied().unwrap_or(0.0)
                + d.get(&(7919 * 1_000_000)).copied().unwrap_or(0.0)) as i64
                + d.len() as i64;
        }
        "bits" => {
            for r in 1..=10i64 {
                for i in 1..=1_000_000i64 {
                    *m.entry(i * 7919).or_insert(0) ^= r;
                }
            }
            t = m.get(&7919).copied().unwrap_or(0)
                + m.get(&(7919 * 1_000_000)).copied().unwrap_or(0);
        }
        _ => {
            println!("b31map: iter, delete, update, sums or bits");
            process::exit(2);
        }
    }
    println!("{} {}", t, m.len());
}
