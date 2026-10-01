/* This file is part of paslang.
 * Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
 * GPL version 3 or later; see COPYING. No warranty.
 * Independent Linux exec ABI fixture: duplicates and malformed raw entries
 * cannot be represented by Python's environment dictionary. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char large[sizeof("PASLANG_ENV_LONG=") + 65000];
    char *environment[20] = {
        "PASLANG_ENV_CASE=first", "PASLANG_ENV_CASE=second",
        "PASLANG_ENV_EMPTY=", "PASLANG_ENV_UTF8=niño雪",
        "PASLANG_ENV_EQUALS=a=b=c", "paslang_env_case=lower",
        "BROKEN", "=nameless", "", large
    };
    const char *gc[] = {"PASLANG_GC", "PASLANG_GCSTRESS", "PASLANG_GCVERIFY", "PASLANG_GCPOISON"};
    size_t prefix = strlen("PASLANG_ENV_LONG=");
    int count = 10;
    if (argc < 2) return 2;
    memcpy(large, "PASLANG_ENV_LONG=", prefix);
    memset(large + prefix, 'x', 65000);
    large[prefix + 64999] = 'Z';
    large[prefix + 65000] = 0;
    for (size_t i = 0; i < sizeof(gc) / sizeof(gc[0]); ++i) {
        const char *value = getenv(gc[i]);
        if (value) {
            size_t size = strlen(gc[i]) + strlen(value) + 2;
            char *entry = malloc(size);
            if (!entry) return 3;
            snprintf(entry, size, "%s=%s", gc[i], value);
            environment[count++] = entry;
        }
    }
    environment[count] = NULL;
    execve(argv[1], argv + 1, environment);
    perror("execve environment fixture");
    return 4;
}
