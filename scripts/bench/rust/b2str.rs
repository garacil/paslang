// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// GPL version 3 or later; see COPYING. No warranty.
// Standard-library benchmark twin of b2str.paslang and b2str.go.

fn main() {
    let mut total: usize = 0;
    for i in 1..=3_000_000i64 {
        let s = format!("item-{}", i);
        total += s.len();
    }
    println!("{}", total);
}
