#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Runs a command with its standard input nonblocking, as a shell may
hand it over (P217): a paslang program keeps the flags it finds, so the
tests of ReadLn that park on the poller give it an input that already
is nonblocking. Usage: nonblocking.py command [arguments]."""
import os
import sys

if len(sys.argv) < 2:
    raise SystemExit("usage: nonblocking.py command [arguments]")
os.set_blocking(0, False)
os.execvp(sys.argv[1], sys.argv[1:])
