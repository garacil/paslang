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
        # A comment is the command ':' with its words: a ';' inside it
        # ends it and runs the rest as a command, and a quote can hide
        # that ';' or swallow the line after (P202: "the: command not
        # found"). So a ':' line holds no quote and no ';' but the one
        # that closes it at its end.
        body = line[1:].strip()
        if body.startswith(": "):
            words = body[:-1].rstrip() if body.endswith("\\") else body
            if any(q in words for q in "'\"`") or ";" in words[:-1] or not words.endswith(";"):
                raise SystemExit(f"{target}: a ':' comment line must hold no quote and end at its only ';': {body[:80]}")
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
