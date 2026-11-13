// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// GPL version 3 or later; see COPYING. No warranty.
// Standard-library benchmark twin of b5map.paslang and b5map.go.

use std::collections::HashMap;

fn main() {
    let mut m: HashMap<i64, i64> = HashMap::new();
    for i in 1..=1_000_000i64 {
        m.insert(i * 7919, i);
    }
    let mut t: i64 = 0;
    for i in 1..=1_000_000i64 {
        t += m[&(i * 7919)];
    }
    println!("{} {}", m.len(), t);
}
