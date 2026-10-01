#!/usr/bin/env python3
"""Keep the test gate's shell recipes bounded and syntactically valid."""
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.

import re
import subprocess
from pathlib import Path


def main():
    lines = Path(__file__).resolve().parents[1].joinpath("Makefile").read_text().splitlines()
    target = None
    command = ""
    checked = 0
    for line in lines + [""]:
        if not line.startswith("\t"):
            if line:
                match = re.match(r"^(check(?:-arm64)?):", line)
                target = match.group(1) if match else None
            continue
        if target is None:
            continue
        command += line[1:] + "\n"
        if line.endswith("\\"):
            continue
        # Half Linux's usual 128 KiB per-argument limit leaves room for
        # expanding paths and the golden lists. Split whole test blocks,
        # never a loop, and explicitly restore any required shell state.
        size = len(command.encode())
        if size > 65536:
            raise SystemExit(f"{target}: recipe is {size} bytes; split before 65536")
        shell = command.replace("$$", "\x00")
        while True:
            expanded = re.sub(r"\$\([^()]*\)", "X", shell)
            if expanded == shell:
                break
            shell = expanded
        shell = shell.replace("\x00", "$").lstrip("@-+")
        result = subprocess.run(["sh", "-n"], input=shell, text=True, capture_output=True)
        if result.returncode:
            raise SystemExit(f"{target}: {result.stderr.strip()}")
        checked += 1
        command = ""
    if checked < 4 or command:
        raise SystemExit("test recipes were not parsed completely")
    print(f"check_recipes: {checked} bounded, valid test recipes")


if __name__ == "__main__":
    main()
