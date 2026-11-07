// This file is part of paslang's tests.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// GPL version 3 or later; see COPYING. No warranty.
//
// A guest for QEMU's gdb stub (P582, scripts/check_gdbstub_threads.py): one thread calls probe COUNT times, the
// count in x0, and turns SPIN times in a loop between two calls, while another makes threads that end at once,
// as fast as it can, and counts them in made. The loop between the calls is where the other thread works when
// a stop holds every thread but the one that stopped: without it no thread would be made in a session.
// System calls by their numbers (asm-generic/unistd.h): clone 220 with the flags of a thread (CLONE_VM,
// CLONE_FS, CLONE_FILES, CLONE_SIGHAND, CLONE_THREAD, CLONE_SYSVSEM: 0x50f00), exit 93, exit_group 94. The
// threads that end at once touch no stack, so they share one. COUNT and SPIN come from the assembler's
// command line.
        .text
        .globl _start
        .globl probe
        .globl made
_start:
        movz    x0, #0x0f00
        movk    x0, #0x5, lsl #16
        adrp    x1, stack1_top
        add     x1, x1, :lo12:stack1_top
        mov     x2, #0
        mov     x3, #0
        mov     x4, #0
        mov     x8, #220
        svc     #0
        cbz     x0, spawner
        mov     x19, #0
        movz    x20, #COUNT
1:      add     x19, x19, #1
        mov     x0, x19
        bl      probe
        movz    x9, #(SPIN & 0xffff)
        movk    x9, #(SPIN >> 16), lsl #16
3:      subs    x9, x9, #1
        b.ne    3b
        cmp     x19, x20
        b.lo    1b
        mov     x0, #0
        mov     x8, #94
        svc     #0
probe:
        nop
        ret
spawner:
        adrp    x21, made
        add     x21, x21, :lo12:made
2:      movz    x0, #0x0f00
        movk    x0, #0x5, lsl #16
        adrp    x1, stack2_top
        add     x1, x1, :lo12:stack2_top
        mov     x2, #0
        mov     x3, #0
        mov     x4, #0
        mov     x8, #220
        svc     #0
        cbz     x0, child
        cmp     x0, #0
        b.lt    2b
        ldr     x9, [x21]
        add     x9, x9, #1
        str     x9, [x21]
        b       2b
child:
        mov     x0, #0
        mov     x8, #93
        svc     #0
        .bss
        .balign 16
made:
        .space  16
        .space  65536
stack1_top:
        .space  4096
stack2_top:
