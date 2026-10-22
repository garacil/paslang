#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""P209: the compiler's json constants held to the parser a program runs.

Every document of JSONTestSuite's test_parsing (testdata/json/suite),
of Go's corpus (testdata/json/corpus) and of check_json.py's hand cases
is written as the text of a json constant, const C: json = '...', a run
of bytes between quotes (a quote doubled) and #0 for a NUL, on lines of
its own as its line feeds fall. A program the runtime runs parses each
with JsonParse and writes "ok" and the SHA-256 of its compact text, or
"err", the error's offset and its message. A document it takes must
compile, alone or among others, and the program made of it write that
text; one it refuses must stop the compile with "json constant: " and
the parser's message, its own place in it taken out, and at the line
and column of the offending byte in the source, which this script finds
by walking the literal as the compiler's LitPlace walks it.

usage: check_jsonconst.py COMPILER BUILDDIR"""
import glob
import hashlib
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TD = os.path.join(ROOT, 'testdata', 'json')

RUNNER = r"""program jcrun;

uses sysutils;

function FromHex(const H: string): string;
var
  i: Integer;
begin
  SetLength(Result, Length(H) div 2);
  for i := 1 to Length(H) div 2 do
    Result[i] := Chr(StrToInt('$' + Copy(H, 2 * i - 1, 2)));
end;

var
  line, s: string;
  j: json;
  e: EJsonError;
begin
  while True do
  begin
    ReadLn(line);
    if line = '' then
      Break;
    if line = '-' then
      s := ''
    else
      s := FromHex(line);
    if TryJsonParse(s, j, e) then
      WriteLn('ok ', LowerCase(Hex(Sha256(JsonEncode(j)))))
    else
      WriteLn('err ', e.Offset, ' ', e.Line, ' ', e.Column, ' ', e.Message);
  end;
end.
"""

HEAD = 'program jc;\n\nconst\n'


def literal(d):
    """The Pascal text of the bytes d: runs between quotes, #0 between them."""
    parts = []
    run = bytearray()
    for b in d:
        if b == 0:
            if run:
                parts.append(b"'" + bytes(run).replace(b"'", b"''") + b"'")
                run = bytearray()
            parts.append(b'#0')
        else:
            run.append(b)
    if run or not parts:
        parts.append(b"'" + bytes(run).replace(b"'", b"''") + b"'")
    return b''.join(parts)


def place(src, line, col, off):
    """LitPlace's walk of the compiler (pasparse): the line and the column
    of byte off of the constant that starts at line:col, or None."""
    lines = src.split(b'\n')
    i = sum(len(x) + 1 for x in lines[:line - 1]) + col - 1
    n = len(src)
    L, C, k = line, col, 0
    while i < n:
        c = src[i]
        if c == 39:
            i += 1
            C += 1
            while i < n:
                if src[i] == 39:
                    if i + 1 < n and src[i + 1] == 39:
                        if k == off:
                            return L, C
                        k += 1
                        i += 2
                        C += 2
                        continue
                    break
                if k == off:
                    return L, C
                k += 1
                if src[i] == 10:
                    L += 1
                    C = 1
                else:
                    C += 1
                i += 1
            i += 1
            C += 1
        elif c == 35 and i + 1 < n and 48 <= src[i + 1] <= 57:
            if k == off:
                return L, C
            k += 1
            i += 1
            C += 1
            while i < n and 48 <= src[i] <= 57:
                i += 1
                C += 1
        elif c in (32, 9, 13):
            i += 1
            C += 1
        elif c == 10:
            i += 1
            L += 1
            C = 1
        else:
            break
    return None


def documents():
    # check_json.py's hand cases, its list alone (the script runs when read)
    text = open(os.path.join(ROOT, 'scripts', 'check_json.py')).read()
    a = text.index('CASES = [')
    b = text.index('\n]\n', a) + 2
    ns = {}
    exec(text[a:b], ns)
    suite = [open(f, 'rb').read() for f in sorted(glob.glob(os.path.join(TD, 'suite', '*.json')))]
    import compression.zstd
    corpus = [compression.zstd.decompress(open(f, 'rb').read())
              for f in sorted(glob.glob(os.path.join(TD, 'corpus', '*.json.zst')))]
    return [('case', ns['CASES']), ('suite', suite), ('corpus', corpus)]


def compile_(compiler, build, work, name, src):
    path = os.path.join(work, name + '.paslang')
    with open(path, 'wb') as f:
        f.write(src)
    r = subprocess.run([compiler, '-Fu', build, '-o', os.path.join(work, name), path],
                       capture_output=True, timeout=600)
    return r.returncode, r.stdout.decode('utf-8', 'replace') + r.stderr.decode('utf-8', 'replace')


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    compiler = os.path.abspath(sys.argv[1])
    build = os.path.abspath(sys.argv[2])
    work = os.path.join(build, 'check-jsonconst')
    if os.path.exists(work):
        shutil.rmtree(work)
    os.makedirs(work)
    code, out = compile_(compiler, build, work, 'jcrun', RUNNER.encode())
    if code:
        sys.exit('jcrun does not compile: ' + out)
    groups = documents()
    docs = [d for _, ds in groups for d in ds]
    data = ''.join((d.hex() if d else '-') + '\n' for d in docs).encode()
    r = subprocess.run([os.path.join(work, 'jcrun')], input=data, capture_output=True, timeout=1800)
    if r.returncode:
        sys.exit('jcrun exited %d' % r.returncode)
    answers = r.stdout.decode('utf-8', 'surrogateescape').split('\n')[:len(docs)]
    took = [(d, a) for d, a in zip(docs, answers) if a.startswith('ok ')]
    refused = [(d, a) for d, a in zip(docs, answers) if a.startswith('err ')]
    # the documents taken: batches of constants, each program writing them
    batch, size, nb = [], 0, 0

    def flush(batch, nb):
        src = bytearray(HEAD.encode())
        for k, (d, _) in enumerate(batch):
            src += b'  C%d: json = ' % k + literal(d) + b';\n'
        src += b'\nbegin\n'
        for k in range(len(batch)):
            src += b'  WriteLn(JsonEncode(C%d));\n' % k
        src += b'end.\n'
        code, out = compile_(compiler, build, work, 'ok%d' % nb, bytes(src))
        if code:
            sys.exit('check_jsonconst: a batch of documents JsonParse takes does not compile: ' + out[-2000:])
        r = subprocess.run([os.path.join(work, 'ok%d' % nb)], capture_output=True, timeout=600)
        got = r.stdout.split(b'\n')
        for k, (d, a) in enumerate(batch):
            if 'ok ' + hashlib.sha256(got[k]).hexdigest() != a:
                sys.exit('check_jsonconst: the constant of %r is not what JsonParse makes of it' % d[:80])

    for d, a in took:
        batch.append((d, a))
        size += len(d)
        if size > 4000000 or len(batch) >= 200:
            flush(batch, nb)
            nb += 1
            batch, size = [], 0
    if batch:
        flush(batch, nb)
        nb += 1
    # the documents refused: each its own compile, stopped at its byte
    for k, (d, a) in enumerate(refused):
        m = re.match(r'err (-?\d+) (\d+) (\d+) (.*)$', a, re.S)
        off, line, col, msg = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
        if msg.startswith('json: '):
            msg = msg[6:]
        msg = msg.replace(' at %d:%d (byte %d)' % (line, col, off), '', 1)
        src = HEAD.encode() + b'  C: json = ' + literal(d) + b';\n\nbegin\nend.\n'
        code, out = compile_(compiler, build, work, 'bad', src)
        if code == 0:
            sys.exit('check_jsonconst: a constant JsonParse refuses compiles: %r' % d[:80])
        p = place(src, 4, 13, off)
        if p:
            want = 'json constant: %s at %d:%d in ' % (msg, p[0], p[1])
        else:
            want = 'json constant: %s at byte %d of the text that starts at 4:13 in ' % (msg, off)
        if want not in out:
            sys.exit('check_jsonconst: %r\n  wanted: %s\n  got:    %s' % (d[:80], want, out.strip()[-500:]))
    shutil.rmtree(work)
    print('check_jsonconst: %d documents taken as constants in %d programs, %d refused at their byte'
          % (len(took), nb, len(refused)))


if __name__ == '__main__':
    main()
