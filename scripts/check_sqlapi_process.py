#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P592: SQL oracles require successful processes, preserving all evidence.

check_sqlapi_process.py CHECKER BUILDDIR [--baseline OLD_CHECKER]
Uses isolated executable stubs and private fixtures, without SQLite work.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import tempfile
from unittest.mock import patch

sys.dont_write_bytecode = True
NORMAL = {"one": b"normal utf8\n", "one.le": b"normal utf16le\n", "one.be": b"normal utf16be\n"}
CORPUS = b"corpus answer\n"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def load(path):
    spec = importlib.util.spec_from_file_location("sqlapi_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(work, name, codes=None, *, mismatch=None, diagnostic="", term=False):
    folder = work / name
    folder.mkdir()
    source = folder / "source"
    source.mkdir()
    (source / "one.sql").write_text("private fixture\n")
    for label, data in NORMAL.items():
        (source / (label + ".out")).write_bytes(data)
    corpus = source / "c_stub.sql"
    corpus.write_text("private corpus fixture\n")
    with tarfile.open(source / "corpus.tar.xz", "w:xz") as archive:
        archive.add(corpus, arcname=corpus.name)
    (source / "corpus.sha256").write_text("c_stub " + hashlib.sha256(CORPUS).hexdigest() + "\n")
    settings = {"codes": codes or {}, "mismatch": mismatch, "diagnostic": diagnostic, "term": term}
    (folder / "settings.json").write_text(json.dumps(settings))
    stub = folder / "program"
    stub.write_text("""#!/usr/bin/env python3
import json, sys, signal
from pathlib import Path
settings=json.loads((Path(__file__).parent/'settings.json').read_text())
label='c_stub' if Path(sys.argv[2]).stem=='c_stub' else 'one'
if len(sys.argv)>3: label += '.le' if sys.argv[3]=='UTF-16le' else '.be'
values={'one':b'normal utf8\\n','one.le':b'normal utf16le\\n','one.be':b'normal utf16be\\n','c_stub':b'corpus answer\\n'}
sys.stdout.buffer.write(b'wrong\\n' if settings['mismatch']==label else values[label]); sys.stdout.flush()
sys.stderr.write(settings['diagnostic']); sys.stderr.flush()
if settings['term']: signal.raise_signal(signal.SIGTERM)
sys.exit(settings['codes'].get(label,0))
""")
    stub.chmod(0o755)
    return folder, source, stub


def invoke(checker, folder, source, program, *, launcher=None, timeout=False):
    module = load(checker)
    module.SRC, module.GROUPS = str(source), ["one"]
    arguments = [str(checker), str(program), str(folder / "results")]
    if launcher:
        arguments.append(str(launcher))
    arguments.append("--corpus")
    output = io.StringIO()
    code, diagnostic = 0, ""
    with patch.object(sys, "argv", arguments), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        try:
            if timeout:
                error = subprocess.TimeoutExpired([str(program)], 900, output=NORMAL["one"], stderr=b"partial diagnostic\n")
                with patch.object(module.subprocess, "run", side_effect=error):
                    module.main()
            else:
                module.main()
        except SystemExit as error:
            code = error.code if isinstance(error.code, int) else 1
            diagnostic = str(error.code)
    (folder / "checker-output.txt").write_text(output.getvalue() + diagnostic + "\n")
    return code, diagnostic


def evidence(folder):
    runs = sorted((folder / "results").glob("process-*/*"))
    found = []
    for run in runs:
        for name in ("command.json", "status.json", "stdout", "stderr"):
            require((run / name).is_file(), "missing process evidence " + str(run / name))
        command = json.loads((run / "command.json").read_text())
        status = json.loads((run / "status.json").read_text())
        require(command["timeout_seconds"] == 900 and command["cwd"] == str(folder / "results"), "command contract changed")
        found.append((command, status, (run / "stdout").read_bytes(), (run / "stderr").read_bytes()))
    return found


def main():
    args = sys.argv[1:]
    baseline = None
    if len(args) == 4 and args[2] == "--baseline":
        baseline = Path(args[3]).resolve()
        args = args[:2]
    require(len(args) == 2, __doc__)
    checker, build = (Path(arg).resolve() for arg in args)
    build.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="sqlapi-process-", dir=build))
    print("sqlapi process artifacts: " + str(work), flush=True)
    verdicts = []
    if baseline:
        for label in ("one", "c_stub"):
            folder, source, program = fixture(work, "old-" + label, {label: 7}, diagnostic="synthetic exit7\n")
            code, diagnostic = invoke(baseline, folder, source, program)
            require(code == 0, "old checker did not reproduce matching-stdout/nonzero false pass: " + diagnostic)
            verdicts.append("old false pass " + label)
    folder, source, program = fixture(work, "positive", diagnostic="successful diagnostic\n")
    code, diagnostic = invoke(checker, folder, source, program)
    require(code == 0, "valid stdout/status rejected: " + diagnostic)
    runs = evidence(folder)
    require(len(runs) == 4 and all(s["returncode"] == 0 and not s["timed_out"] for _, s, _, _ in runs), "positive run count or status")
    require([out for _, _, out, _ in runs] == [*NORMAL.values(), CORPUS], "UTF8/UTF16/corpus output contract changed")
    require(all(err == b"successful diagnostic\n" for _, _, _, err in runs), "successful stderr not preserved")
    verdicts.append("zero exit, distinct UTF8/16 answers and corpus accepted; stderr preserved")
    launcher = work / "launch-program"
    launcher.write_text("#!/bin/sh\nexec \"$@\"\n")
    launcher.chmod(0o755)
    folder, source, program = fixture(work, "launcher")
    code, diagnostic = invoke(checker, folder, source, program, launcher=launcher)
    require(code == 0, "launcher contract rejected: " + diagnostic)
    require(all(command["argv"][:2] == [str(launcher), str(program)] for command, _, _, _ in evidence(folder)), "launcher prefix lost")
    verdicts.append("launcher prefix retained")
    for label in ("one", "one.le", "one.be", "c_stub"):
        folder, source, program = fixture(work, "exit7-" + label, {label: 7}, diagnostic="synthetic exit7\n")
        code, diagnostic = invoke(checker, folder, source, program)
        require(code != 0 and "exited 7" in diagnostic, "matching-output exit7 accepted or failed for wrong reason: " + label)
        _, status, out, err = evidence(folder)[-1]
        require(status["returncode"] == 7 and out == (CORPUS if label == "c_stub" else NORMAL[label]) and err == b"synthetic exit7\n", "exit7 evidence lost")
        verdicts.append("exit7 rejected " + label)
    for label in ("one", "c_stub"):
        folder, source, program = fixture(work, "mismatch-" + label, mismatch=label)
        code, diagnostic = invoke(checker, folder, source, program)
        require(code != 0 and "differs from SQLite" in diagnostic, "existing stdout/hash mismatch no longer rejected")
        require(evidence(folder)[-1][1]["returncode"] == 0, "mismatch control failed as a process instead")
        verdicts.append("mismatch rejected " + label)
    folder, source, program = fixture(work, "timeout")
    code, diagnostic = invoke(checker, folder, source, program, timeout=True)
    require(code != 0 and "timed out after 900 seconds" in diagnostic, "timeout with matching partial stdout accepted")
    _, status, out, err = evidence(folder)[-1]
    require(status["timed_out"] and status["returncode"] is None and out == NORMAL["one"] and err == b"partial diagnostic\n", "timeout evidence lost")
    verdicts.append("timeout rejected before comparison; partial bytes preserved")
    folder, source, program = fixture(work, "signal", term=True)
    code, diagnostic = invoke(checker, folder, source, program)
    require(code != 0 and "exited -15" in diagnostic and evidence(folder)[-1][1]["returncode"] == -signal.SIGTERM, "signal exit not retained")
    verdicts.append("signal rejected")
    folder, source, program = fixture(work, "launch-error")
    code, diagnostic = invoke(checker, folder, source, program.with_name("missing-program"))
    require(code != 0 and "could not start" in diagnostic and evidence(folder)[-1][1]["launch_error"], "launch failure evidence missing")
    verdicts.append("launch failure rejected")
    (work / "verdicts.json").write_text(json.dumps(verdicts, indent=2) + "\n")
    print("sqlapi-process: " + str(len(verdicts)) + " isolated process/output controls passed", flush=True)


if __name__ == "__main__":
    main()
