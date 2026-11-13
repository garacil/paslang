// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// GPL version 3 or later; see COPYING. No warranty.
// Standard-library benchmark twin of b7narrow.paslang and b7narrow.go.

fn main() {
    let n: usize = 64 * 1024 * 1024;
    let mut data = vec![0u8; n];
    let mut x: i64 = 12345;
    for i in 0..n {
        x = x.wrapping_mul(1103515245).wrapping_add(12345);
        data[i] = (x >> 16) as u8;
    }
    let mut tab = [0u8; 256];
    for i in 0..256usize {
        tab[i] = (i * 7 + 3) as u8;
    }
    let mut hist = [0i64; 256];
    for _pass in 1..=4 {
        for i in 0..n {
            data[i] = tab[data[i] as usize];
        }
        for i in 0..n {
            hist[data[i] as usize] += 1;
        }
    }
    let mut sum: i64 = 0;
    for i in 0..256usize {
        sum += hist[i] * i as i64;
    }
    println!("{}", sum);
}
