#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING.
"""Check the server benchmark's verdicts and run real samples without compilers."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import report  # noqa: E402
import servers  # noqa: E402


ANSWER = (b"2000 clients, 6000 requests, 6000 served, 0 bad\n"
          b"stats.json: 2001 connections, 6001 requests, 0 bad\n")


def fixture(mode, marker):
    if mode == "child":
        marker.write_text(str(os.getpid()))
        time.sleep(30)
        return 0
    if mode == "detached":
        subprocess.Popen([sys.executable, __file__, "child", str(marker)], start_new_session=True)
        while not marker.exists():
            time.sleep(0.01)
        os.write(1, b"partial\n")
        time.sleep(30)
        return 0
    traced = next(int(line.split()[1]) for line in Path("/proc/self/status").read_text().splitlines()
                  if line.startswith("TracerPid:"))
    answer = ANSWER
    if mode == "extra" or (mode == "trace-extra" and traced):
        answer += b"extra\n"
    if mode == "binary":
        answer += b"\xff"
    if mode == "no-newline":
        answer = answer[:-1]
    os.write(1, answer)
    if mode == "trace-timeout" and traced:
        time.sleep(30)
    return 7 if mode == "timed-error" or (mode == "trace-error" and traced) else 0


def observed(mode, marker, timeout=4, memory_timeout=4):
    command = [sys.executable, __file__, mode, str(marker)]
    return servers.run_one(command, timeout=timeout, memory_timeout=memory_timeout)


def reference(name, n, first):
    output = servers.expected_output(name, n)
    clean = {"status": 0, "stdout": output, "stderr": ""}
    return {"timed": dict(clean, wall_s=2 if first else 1, cleanup={"ok": True}),
            "memory": dict(clean, peak_kib=4096 if first else 2048, ok=True)}


def pair(name, n):
    rounds = [{"round": number, "first": "go" if number % 2 else "paslang",
               "go": reference(name, n, True), "paslang": reference(name, n, False)}
              for number in (1, 2)]
    return {"cpu": "native", "pair": name, "n": n, "rounds": rounds}


def check_observations(folder):
    with patch.object(servers, "settle", lambda: None):
        good = observed("good", folder / "unused")
        assert good["timed"]["stdout"].encode() == ANSWER
        assert good["memory"]["ok"] and good["memory"]["stdout"].encode() == ANSWER
        assert good["memory"]["peak_kib"] > 0
        for mode, suffix in (("extra", b"extra\n"), ("binary", b"\xff")):
            result = observed(mode, folder / "unused")
            assert result["timed"]["stdout"].encode("utf-8", "surrogateescape") == ANSWER + suffix
            value = pair("httpd", 2000)
            value["rounds"][0]["paslang"] = result
            assert servers.summarize(value, 2)["verdict"] == "INVALID"
        value = pair("httpd", 2000)
        newline = observed("no-newline", folder / "unused")
        assert newline["timed"]["stdout"].encode() == ANSWER[:-1]
        value["rounds"][0]["go"] = newline
        assert servers.summarize(value, 2)["verdict"] == "INVALID"
        for mode in ("trace-error", "trace-extra", "trace-timeout", "timed-error"):
            result = observed(mode, folder / "unused", memory_timeout=1 if mode == "trace-timeout" else 4)
            value["rounds"][0]["go"] = result
            assert servers.summarize(value, 2)["verdict"] == "INVALID"
            if mode == "timed-error":
                assert result["timed"]["status"] == 7 and result["memory"] is None
            else:
                assert result["timed"]["status"] == 0 and not result["memory"]["ok"]
                status = {"trace-error": 7, "trace-extra": 0, "trace-timeout": "timeout"}[mode]
                assert result["memory"]["status"] == status
        marker = folder / "detached.pid"
        started = time.monotonic()
        timeout = observed("detached", marker, timeout=1.5)
        assert time.monotonic() - started < 10
        assert timeout["timed"]["status"] == "timeout" and timeout["timed"]["stdout"] == "partial\n"
        assert timeout["timed"]["cleanup"]["ok"] and timeout["memory"] is None
        pid = int(marker.read_text())
        assert not Path("/proc", str(pid)).exists(), "detached child was not reaped"


def check_report(folder):
    path = folder / "servers.json"
    pairs = [pair(name, n) for name, loads in servers.PAIRS for n in loads]
    record = {"format": servers.FORMAT, "runs": 2, "cpus": ["native"], "ok": True,
              "requested_pairs": len(pairs), "completed_pairs": len(pairs), "pairs": pairs}
    def render(value):
        path.write_text(json.dumps(value))
        lines = []
        report.servers(lines.append, path)
        return lines

    assert "Aggregate server verdict PASS." in render(record)
    for change in ("missing-round", "missing-pair", "sticky-status", "budget", "memory", "cleanup"):
        invalid = copy.deepcopy(record)
        first = invalid["pairs"][0]["rounds"][0]["paslang"]
        if change == "missing-round":
            invalid["pairs"][0]["rounds"].pop()
        elif change == "missing-pair":
            invalid["pairs"].pop()
        elif change == "sticky-status":
            first["timed"]["status"] = 7
        elif change == "budget":
            for round_ in invalid["pairs"][0]["rounds"]:
                round_["paslang"]["timed"]["wall_s"] = round_["go"]["timed"]["wall_s"]
        elif change == "memory":
            first["memory"]["peak_kib"] = -1
            summarized = servers.summarize(invalid["pairs"][0], invalid["runs"])
            assert summarized["paslang_mb"][0] is None
        else:
            first["timed"]["cleanup"]["ok"] = False
        assert "Aggregate server verdict FAIL." in render(invalid), change
    assert "Legacy record with summary measurements." in render({"pairs": []})


def main():
    with tempfile.TemporaryDirectory(prefix="server-bench-check-") as name:
        folder = Path(name)
        check_observations(folder)
        check_report(folder)
    print("server benchmark: exact timed and traced output, status, timeout, cleanup and report verdicts")


if __name__ == "__main__":
    if len(sys.argv) == 3:
        raise SystemExit(fixture(sys.argv[1], Path(sys.argv[2])))
    main()
