#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
#
# paslang is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# paslang is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with paslang.  If not, see <https://www.gnu.org/licenses/>.

"""The manual and the examples must not drift.

Every ```pascal block of docs/MANUAL.md that declares a program or a unit
must be byte for byte the file of that name under examples/ (after the
license notice that heads the file), and the
``` block that follows a line reading "prints" must be that file's .out.
Every example program must have an .out and be named in the examples
block of the Makefile. Exit 1 on the first difference, with the reason.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "docs" / "MANUAL.md"
EXAMPLES = ROOT / "examples"
MAKEFILE = ROOT / "Makefile"


def find_source(name: str) -> Path | None:
    for cand in (EXAMPLES / f"{name}.paslang",
                 EXAMPLES / "pasroutines" / f"{name}.paslang",
                 EXAMPLES / "units" / f"{name}.paslang"):
        if cand.exists():
            return cand
    return None


def program_text(src: Path) -> str:
    """The file without the license notice that heads it: the manual
    shows the program alone."""
    text = src.read_text()
    if text.startswith("{ This file is part of paslang."):
        text = text[text.index("}\n") + 2:].lstrip("\n")
    return text


def blocks(text: str):
    """Yield (language, body, index_of_line_after_block) for fenced blocks."""
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        m = re.match(r"^```(\w*)\s*$", lines[i])
        if m:
            lang = m.group(1)
            j = i + 1
            while j < len(lines) and lines[j] != "```":
                j += 1
            yield lang, "\n".join(lines[i + 1:j]) + "\n", j + 1, lines
            i = j + 1
        else:
            i += 1


def main() -> int:
    problems = []
    text = MANUAL.read_text()
    seen = set()
    for lang, body, after, lines in blocks(text):
        if lang != "pascal":
            continue
        m = re.search(r"^(program|unit)\s+(\w+)\s*;", body, re.M)
        if not m:
            continue
        name = m.group(2)
        src = find_source(name)
        if src is None:
            problems.append(f"manual block for {name} has no file under examples/")
            continue
        seen.add(src)
        if program_text(src) != body:
            problems.append(f"{src.relative_to(ROOT)} differs from its block in the manual")
        # The output block: the next fenced block after a line "prints".
        k = after
        while k < len(lines) and lines[k].strip() == "":
            k += 1
        if k < len(lines) and lines[k].strip() == "prints":
            k += 1
            while k < len(lines) and lines[k].strip() == "":
                k += 1
            if k < len(lines) and lines[k].startswith("```"):
                j = k + 1
                while j < len(lines) and lines[j] != "```":
                    j += 1
                out = "\n".join(lines[k + 1:j]) + "\n"
                exp = src.with_suffix(".out")
                if not exp.exists():
                    problems.append(f"{exp.relative_to(ROOT)} is missing")
                elif exp.read_text() != out:
                    problems.append(f"{exp.relative_to(ROOT)} differs from the output printed in the manual")
    mk = MAKEFILE.read_text()
    start = mk.find('==== examples ====')
    end = mk.find('ok examples', start)
    block = mk[start:end] if start >= 0 and end >= 0 else ""
    names = set(re.findall(r"[A-Za-z0-9_]+", block))
    for src in sorted(list(EXAMPLES.glob("*.paslang")) +
                      list(EXAMPLES.glob("pasroutines/*.paslang")) +
                      list(EXAMPLES.glob("units/*.paslang"))):
        head = src.read_text(errors="replace")
        is_unit = re.search(r"^unit\s+\w+\s*;", head, re.M) is not None
        if not is_unit and not src.with_suffix(".out").exists():
            problems.append(f"{src.relative_to(ROOT)} has no .out")
        if src.stem not in names:
            problems.append(f"{src.relative_to(ROOT)} is not run by the examples block of the Makefile")
    for p in problems:
        print("check_examples:", p)
    if problems:
        return 1
    print(f"check_examples: {len(seen)} manual programs match their files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
