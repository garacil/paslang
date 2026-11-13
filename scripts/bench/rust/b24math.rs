// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// GPL version 3 or later; see COPYING. No warranty.
// Standard-library benchmark twin of b24math.paslang and b24math.go.

use std::env;
use std::process;

fn main() {
    let mut t: f64 = 0.0;
    let arg = env::args().nth(1).unwrap_or_default();
    match arg.as_str() {
        "sin" => {
            for i in 1..=10_000_000i64 {
                t += (i as f64 / 997.0).sin();
            }
        }
        "exp" => {
            for i in 1..=10_000_000i64 {
                let x = (i % 2000) as f64 / 1000.0 - 1.0;
                t += x.exp();
            }
        }
        "ln" => {
            for i in 1..=10_000_000i64 {
                t += (i as f64 / 997.0).ln();
            }
        }
        "sqrt" => {
            for i in 1..=10_000_000i64 {
                t += (i as f64 / 997.0).sqrt();
            }
        }
        "pow" => {
            for i in 1..=10_000_000i64 {
                t += (((i % 997 + 1) as f64) / 997.0).powf(1.37);
            }
        }
        "atan" => {
            for i in 1..=10_000_000i64 {
                t += (i as f64 / 997.0).atan();
            }
        }
        "tan" => {
            for i in 1..=10_000_000i64 {
                t += (i as f64 / 997.0).tan();
            }
        }
        "sinh" => {
            for i in 1..=10_000_000i64 {
                let x = (i % 2000) as f64 / 100.0 - 10.0;
                t += x.sinh();
            }
        }
        "tanh" => {
            for i in 1..=10_000_000i64 {
                let x = (i % 2000) as f64 / 500.0 - 2.0;
                t += x.tanh();
            }
        }
        "asinh" => {
            for i in 1..=10_000_000i64 {
                t += (i as f64 / 997.0).asinh();
            }
        }
        "log1p" => {
            for i in 1..=10_000_000i64 {
                t += (i as f64 / 997.0).ln_1p();
            }
        }
        _ => {
            println!("b24math: sin, exp, ln, sqrt, pow, atan, tan, sinh, tanh, asinh or log1p");
            process::exit(2);
        }
    }
    println!("{}", (t * 1000.0) as i64);
}
