#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P460/P462: public types stay unique; private SysUtils stays outside PI."""
from collections import Counter
from pathlib import Path
import sys


def check(folder):
    sizes = []
    for index in range(1, 9):
        path = folder / ("pichain" + str(index) + ".pi")
        data = path.read_bytes()
        sizes.append(len(data))
        rows = data.decode().splitlines()
        unit = [row.split()[1].lower() for row in rows if row.startswith("UNIT ")]
        assert unit == ["pichain" + str(index)], (path, "wrong unit", unit)
        names, ids, origins = Counter(), set(), {}
        current = None
        for row in rows:
            words = row.split()
            if words[:1] == ["TYPE"]:
                assert len(words) >= 3, (path, "short TYPE")
                current = int(words[2])
                assert current > 0 and current not in ids, (path, "duplicate type id", current)
                ids.add(current)
                names[words[1].lower()] += 1
            elif words[:1] == ["ORIG"]:
                assert len(words) == 3 and current is not None, (path, "invalid ORIG")
                assert current not in origins, (path, "repeated ORIG for type", current)
                origins[current] = (words[1].lower(), int(words[2]))
        canonical = Counter(origins.get(tid, (unit[0], tid)) for tid in ids)
        assert all(count == 1 for count in canonical.values()), (path, "duplicate type origin")
        assert names["tsyserror"] == 0, (path, "private TSysError exported")
        assert not any(origin[0] == "sysutils" for origin in canonical), (
            path, "private SysUtils type exported")
        assert "USE sysutils" not in rows, (path, "private SysUtils import exported")
        if index == 1:
            assert "LINK sysutils" in rows, (path, "missing private SysUtils link")
        for number in range(1, index + 1):
            for name in ("tp" + str(number), "tc" + str(number), "tp" + str(number) + ".rec"):
                assert names[name] == 1, (path, name + " must occur once", names[name])
    assert sizes[-1] < 2 * sizes[0], (folder, "interface chain grows", sizes)
    print("pi-chain:", folder, "eight units, unique public types/origins, private SysUtils excluded;",
          sizes[0], "to", sizes[-1], "bytes")


def main():
    assert len(sys.argv) > 1, "usage: check_pi_chain.py DIRECTORY [DIRECTORY...]"
    for name in sys.argv[1:]:
        check(Path(name))


if __name__ == "__main__":
    main()
