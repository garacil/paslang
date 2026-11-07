// This file is part of paslang's tests.
// Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
// GPL version 3 or later; see COPYING. No warranty.
//
// A guest for QEMU's user mode with no gdb (P582, scripts/check_gdbstub_threads.py): one thread forks FORKS
// times, waiting for each child before the next, while another makes threads that end at once, as fast as it
// can, and counts them in made. QEMU's fork takes its exclusive section and then the lock of a thread's making
// (fork_start(), linux-user/main.c); a thread's making or exit that takes the two the other way round stands
// against it for ever, which the first form of scripts/qemu/0005 did. The children end by exit and by
// exit_group in turn: exit is the system call a thread ends by, and QEMU takes the same two there. At its end
// the guest writes made, eight bytes, to its standard output.
// System calls by their numbers (asm-generic/unistd.h): clone 220, with the flags of a thread (CLONE_VM,
// CLONE_FS, CLONE_FILES, CLONE_SIGHAND, CLONE_THREAD, CLONE_SYSVSEM: 0x50f00) or with SIGCHLD alone (17), a
// fork; wait4 260, write 64, exit 93, exit_group 94. The threads that end at once touch no stack, so they
// share one. FORKS comes from the assembler's command line.
        .text
        .globl _start
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
        movz    x20, #FORKS
1:      mov     x0, #17
        mov     x1, #0
        mov     x2, #0
        mov     x3, #0
        mov     x4, #0
        mov     x8, #220
        svc     #0
        cbz     x0, forked
        cmp     x0, #0
        b.lt    failed
        mov     x1, #0
        mov     x2, #0
        mov     x3, #0
        mov     x8, #260
        svc     #0
        add     x19, x19, #1
        cmp     x19, x20
        b.lo    1b
        mov     x0, #1
        adrp    x1, made
        add     x1, x1, :lo12:made
        mov     x2, #8
        mov     x8, #64
        svc     #0
        mov     x0, #0
        mov     x8, #94
        svc     #0
forked:
        mov     x0, #0
        mov     x8, #93
        tbz     x19, #0, 2f
        mov     x8, #94
2:      svc     #0
failed:
        mov     x0, #2
        mov     x8, #94
        svc     #0
spawner:
        adrp    x21, made
        add     x21, x21, :lo12:made
3:      movz    x0, #0x0f00
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
        b.lt    3b
        ldr     x9, [x21]
        add     x9, x9, #1
        str     x9, [x21]
        b       3b
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
