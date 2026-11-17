// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// paslang is free software under the GNU General Public License,
// version 3 or (at your option) any later version; see the file COPYING.

// rm PATH: Rust's std::fs::remove_dir_all of PATH, for
// scripts/bench_rmall.py (P631).
fn main() {
    let path = std::env::args().nth(1).expect("a path");
    if let Err(e) = std::fs::remove_dir_all(&path) {
        println!("error: {}", e);
        std::process::exit(1);
    }
}
