/* This file is part of paslang.
 * Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
 * GPL version 3 or later; see COPYING. No warranty.
 * Foreign executable oracle: actual post-exec FD and signal state. */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdlib.h>
#include <sys/stat.h>

int main(int argc, char **argv) {
    struct stat actual, expected;
    struct sigaction action;
    sigset_t mask;
    if (argc != 6) return 2;
    unsigned closed = (unsigned)strtoul(argv[1], NULL, 10);
    int foreign = (int)strtol(argv[2], NULL, 10);
    for (int fd = 0; fd < 3; ++fd) {
        int result = fstat(fd, &actual);
        if (closed & (1u << fd)) {
            if (result != -1 || errno != EBADF) return 10 + fd;
        } else {
            if (result || stat(argv[fd + 3], &expected)) return 20 + fd;
            if (actual.st_dev != expected.st_dev || actual.st_ino != expected.st_ino)
                return 30 + fd;
            if (fcntl(fd, F_GETFD) != 0) return 40 + fd;
        }
    }
    if (fcntl(foreign, F_GETFD) != -1 || errno != EBADF) return 50;
    if (sigaction(SIGSEGV, NULL, &action) || action.sa_handler != SIG_DFL) return 51;
    if (sigaction(SIGPIPE, NULL, &action) || action.sa_handler != SIG_DFL) return 52;
    if (sigaction(SIGUSR2, NULL, &action) || action.sa_handler != SIG_IGN) return 53;
    if (sigprocmask(SIG_SETMASK, NULL, &mask) || sigismember(&mask, SIGSEGV)) return 54;
    return 0;
}
