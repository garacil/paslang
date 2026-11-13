// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// GPL version 3 or later; see COPYING. No warranty.
// Standard-library benchmark twin of b6smap.paslang and b6smap.go.

use std::collections::HashMap;

fn main() {
    let mut keys: Vec<String> = Vec::with_capacity(1_000_000);
    for i in 0..1_000_000i64 {
        keys.push(format!("key{}", i * 7919));
    }
    // The complete key store outlives the map and is never changed again.
    // Like the Go and paslang twins, inserting a key shares its bytes.
    let mut m: HashMap<&str, i64> = HashMap::new();
    for i in 0..1_000_000usize {
        m.insert(keys[i].as_str(), i as i64);
    }
    let mut t: i64 = 0;
    for i in 0..1_000_000usize {
        t += m[keys[i].as_str()];
    }
    println!("{} {}", m.len(), t);
}
