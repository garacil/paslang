// This file is part of paslang.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// GPL version 3 or later; see COPYING. No warranty.
// Standard-library benchmark twin of b8ptr.paslang and b8ptr.go.

struct Node {
    val: i64,
    next: Option<Box<Node>>,
}

fn main() {
    let n: usize = 32 * 1024 * 1024;
    let mut buf = vec![0u8; n];
    let mut sum: i64 = 0;
    for r in 1..=4usize {
        for i in 0..n {
            buf[i] = (i + r) as u8;
        }
        let mut i = 0;
        while i < n {
            sum += u32::from_le_bytes([buf[i], buf[i + 1], buf[i + 2], buf[i + 3]]) as i64;
            i += 4;
        }
    }
    let mut head: Option<Box<Node>> = None;
    for i in 1..=1_000_000i64 {
        head = Some(Box::new(Node { val: i, next: head }));
    }
    for _r in 1..=20 {
        let mut nd = &head;
        while let Some(b) = nd {
            sum += b.val;
            nd = &b.next;
        }
    }
    // the list is freed one node at a time: the default drop of a list of a million boxes recurses
    // a million deep and overflows the stack of the main thread
    let mut cur = head;
    while let Some(mut b) = cur {
        cur = b.next.take();
    }
    println!("{}", sum);
}
