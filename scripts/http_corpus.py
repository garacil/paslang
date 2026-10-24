#!/usr/bin/env python3
"""P432: the corpus testdata/httpmsg.txt that testdata/httpmsg.paslang reads.

Each line is `ID KIND METHOD BASE64 VERDICT`: a message (KIND req, or resp
answering a request of METHOD) and what Go's net/http makes of it
(scripts/http_oracle.go): the start line, the fields, how the body is
framed, the body read to its end, the trailer, the bytes left over. The
messages are requests and responses of every framing, the same with
extensions, trailers, obsolete line folding and odd fields, each also cut
short, and with one byte inserted, replaced or taken out. Seeded.

    http_corpus.py [FILE]     write testdata/httpmsg.txt
"""
import base64
import os
import random
import subprocess
import sys

R = random.Random(4320)
CRLF = "\r\n"


def chunks(parts, ext="", trailer="", last="0"):
    out = ""
    for p in parts:
        out += "%x%s\r\n%s\r\n" % (len(p), ext, p)
    return out + last + ext + "\r\n" + trailer + "\r\n"


REQS = [
    "GET / HTTP/1.1\r\nHost: example.com\r\n\r\n",
    "GET /a/b?c=d&e=f HTTP/1.1\r\nHost: example.com\r\nUser-Agent: x\r\nAccept: */*\r\n\r\n",
    "GET /a HTTP/1.0\r\n\r\n",
    "GET /a HTTP/1.0\r\nConnection: keep-alive\r\n\r\n",
    "GET /a HTTP/1.1\r\nConnection: close\r\n\r\n",
    "GET /a HTTP/1.1\r\nConnection: Keep-Alive, Upgrade\r\n\r\n",
    "GET /a HTTP/1.1\r\nconnection: CLOSE\r\n\r\n",
    "GET /a HTTP/0.9\r\n\r\n",
    "GET /a HTTP/2.0\r\nHost: h\r\n\r\n",
    "GET /a HTTP/1.2\r\nHost: h\r\n\r\n",
    "GET /a HTTP/1\r\n\r\n",
    "GET /a HTTP/1.10\r\n\r\n",
    "GET /a http/1.1\r\n\r\n",
    "GET /a\r\n\r\n",
    "GET\r\n\r\n",
    "\r\nGET / HTTP/1.1\r\n\r\n",
    "GET  / HTTP/1.1\r\n\r\n",
    "GET / HTTP/1.1 \r\n\r\n",
    "GET / HTTP/1.1\n\n",
    "GET / HTTP/1.1\nHost: h\n\n",
    "G@T / HTTP/1.1\r\n\r\n",
    "get / HTTP/1.1\r\n\r\n",
    "POST /p HTTP/1.1\r\nHost: h\r\nContent-Length: 5\r\n\r\nhello",
    "POST /p HTTP/1.1\r\nHost: h\r\nContent-Length: 5\r\n\r\nhello world",
    "POST /p HTTP/1.1\r\nHost: h\r\nContent-Length: 5\r\n\r\nhe",
    "POST /p HTTP/1.1\r\nHost: h\r\nContent-Length: 0\r\n\r\n",
    "POST /p HTTP/1.1\r\nHost: h\r\nContent-Length: -1\r\n\r\n",
    "POST /p HTTP/1.1\r\nHost: h\r\nContent-Length: +5\r\n\r\nhello",
    "POST /p HTTP/1.1\r\nHost: h\r\nContent-Length: 5 \r\n\r\nhello",
    "POST /p HTTP/1.1\r\nHost: h\r\nContent-Length:  5\r\n\r\nhello",
    "POST /p HTTP/1.1\r\nHost: h\r\nContent-Length: 0x5\r\n\r\nhello",
    "POST /p HTTP/1.1\r\nHost: h\r\nContent-Length: 5,5\r\n\r\nhello",
    "POST /p HTTP/1.1\r\nHost: h\r\nContent-Length: 5\r\nContent-Length: 5\r\n\r\nhello",
    "POST /p HTTP/1.1\r\nHost: h\r\nContent-Length: 5\r\nContent-Length: 6\r\n\r\nhello!",
    "POST /p HTTP/1.1\r\nHost: h\r\nContent-Length: \r\n\r\n",
    "POST /p HTTP/1.1\r\nHost: h\r\nContent-Length: 99999999999999999999\r\n\r\n",
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\n\r\n" + chunks(["hello", " world"]),
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\n\r\n" + chunks([]),
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: Chunked\r\n\r\n" + chunks(["a"]),
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\nContent-Length: 5\r\n\r\n" + chunks(["hello"]),
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: gzip, chunked\r\n\r\n" + chunks(["hello"]),
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: identity\r\n\r\n",
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\nTransfer-Encoding: chunked\r\n\r\n" + chunks(["a"]),
    "POST /p HTTP/1.0\r\nHost: h\r\nTransfer-Encoding: chunked\r\nContent-Length: 3\r\n\r\nabc",
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\n\r\n" + chunks(["hello"], ext=";name=value"),
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\n\r\n" + chunks(["hello"], ext=" ; x"),
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\nTrailer: X-Sum, X-Other\r\n\r\n" + chunks(["hello"], trailer="X-Sum: 5\r\nX-Other: o\r\n"),
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\nTrailer: X-Sum\r\n\r\n" + chunks(["hello"]),
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\n\r\n" + chunks(["hello"], trailer="X-Late: 1\r\n"),
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\nTrailer: Content-Length\r\n\r\n" + chunks(["hello"]),
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\nTrailer: Transfer-Encoding\r\n\r\n" + chunks(["hello"]),
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhello\r\n0\r\n\r\nGET /next HTTP/1.1\r\n\r\n",
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\n\r\n5\nhello\r\n0\r\n\r\n",
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhello\n0\r\n\r\n",
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhelloXX0\r\n\r\n",
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\n\r\n\r\nhello\r\n0\r\n\r\n",
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\n\r\nzz\r\nhello\r\n0\r\n\r\n",
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\n\r\n10000000000000000\r\nx\r\n",
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\n\r\nFFFFFFFFFFFFFFF\r\nx\r\n",
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\n\r\n0005\r\nhello\r\n0000\r\n\r\n",
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\n\r\nA\r\n0123456789\r\n0\r\n\r\n",
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhello\r\n0",
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhel",
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\n\r\n",
    "POST /p HTTP/1.1\r\nHost: h\r\nTransfer-Encoding: chunked\r\n\r\n3\r\nabc\r\n0\r\nX: y\r\nZ: w\r\n\r\n",
    "GET http://example.com/a/b?c=d HTTP/1.1\r\nHost: other\r\n\r\n",
    "GET http://user:pw@example.com:8080/a HTTP/1.1\r\n\r\n",
    "GET https://example.com HTTP/1.1\r\n\r\n",
    "GET //example.com/a HTTP/1.1\r\n\r\n",
    "GET a HTTP/1.1\r\n\r\n",
    "GET ?q HTTP/1.1\r\n\r\n",
    "GET /a%zz HTTP/1.1\r\n\r\n",
    "GET /a b HTTP/1.1\r\n\r\n",
    "GET /%41 HTTP/1.1\r\nHost: h\r\n\r\n",
    "OPTIONS * HTTP/1.1\r\nHost: h\r\n\r\n",
    "CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n",
    "CONNECT /path HTTP/1.1\r\n\r\n",
    "CONNECT [::1]:80 HTTP/1.1\r\n\r\n",
    "CONNECT example.com HTTP/1.1\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: a\r\nHost: b\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: \r\n\r\n",
    "GET / HTTP/1.1\r\nHost:h\r\n\r\n",
    "GET / HTTP/1.1\r\nHost:    h   \r\n\r\n",
    "GET / HTTP/1.1\r\nHost : h\r\n\r\n",
    "GET / HTTP/1.1\r\n Host: h\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\nX-A: 1\r\n continued\r\n\tmore\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\nX-A: 1\r\n  \r\nX-B: 2\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\nNoColon\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\n: empty\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\nX Y: z\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\nX\tY: z\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\nX-A: a\x00b\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\nX-A: a\x7fb\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\nX-A: a\tb\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\nx-lower: a\r\nX-UPPER: b\r\nx-Mixed-CASE: c\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\nX-A: 1\r\nX-A: 2\r\nx-a: 3\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\nPragma: no-cache\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\nPragma: no-cache\r\nCache-Control: max-age=0\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\nPragma: other\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\nExpect: 100-continue\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\nX-A: \r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\nX-A:\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\nX-Long: " + "a" * 4000 + "\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\n" + "".join("X-%d: v\r\n" % i for i in range(40)) + "\r\n",
    "HEAD /a HTTP/1.1\r\nHost: h\r\nContent-Length: 5\r\n\r\n",
    "DELETE /a HTTP/1.1\r\nHost: h\r\n\r\n",
    "PUT /a HTTP/1.1\r\nHost: h\r\nContent-Length: 3\r\n\r\nabc",
    "PATCH /a HTTP/1.1\r\nHost: h\r\nContent-Length: 3\r\n\r\nabc",
    "PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\n\r\nGET /two HTTP/1.1\r\nHost: h\r\n\r\n",
    "GET / HTTP/1.1\r\nHost: h\r\n\r\n\r\n\r\n",
    "",
    "\r\n",
    "GET",
    "GET / HTTP/1.1",
    "GET / HTTP/1.1\r\n",
    "GET / HTTP/1.1\r\nHost: h",
    "GET / HTTP/1.1\r\nHost: h\r\n",
]

RESPS = [
    ("GET", "HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello"),
    ("GET", "HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello world"),
    ("GET", "HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhel"),
    ("GET", "HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"),
    ("GET", "HTTP/1.1 200 OK\r\n\r\nuntil the end"),
    ("GET", "HTTP/1.1 200 OK\r\nConnection: close\r\n\r\nuntil the end"),
    ("GET", "HTTP/1.1 200 OK\r\nConnection: keep-alive\r\n\r\nuntil the end"),
    ("GET", "HTTP/1.0 200 OK\r\n\r\nuntil the end"),
    ("GET", "HTTP/1.0 200 OK\r\nConnection: keep-alive\r\nContent-Length: 3\r\n\r\nabc"),
    ("GET", "HTTP/1.0 200 OK\r\nContent-Length: 3\r\n\r\nabc"),
    ("GET", "HTTP/0.9 200 OK\r\nContent-Length: 3\r\n\r\nabc"),
    ("GET", "HTTP/0.0 200 OK\r\nContent-Length: 3\r\n\r\nabc"),
    ("GET", "HTTP/2.0 200 OK\r\nContent-Length: 3\r\n\r\nabc"),
    ("GET", "HTTP/1.1 200\r\nContent-Length: 3\r\n\r\nabc"),
    ("GET", "HTTP/1.1 200 \r\nContent-Length: 3\r\n\r\nabc"),
    ("GET", "HTTP/1.1   200   OK  \r\nContent-Length: 3\r\n\r\nabc"),
    ("GET", "HTTP/1.1 20 OK\r\n\r\n"),
    ("GET", "HTTP/1.1 2000 OK\r\n\r\n"),
    ("GET", "HTTP/1.1 abc OK\r\n\r\n"),
    ("GET", "HTTP/1.1 +20 OK\r\nContent-Length: 0\r\n\r\n"),
    ("GET", "HTTP/1.1 -20 OK\r\n\r\n"),
    ("GET", "HTTP/1.1 099 Low\r\nContent-Length: 0\r\n\r\n"),
    ("GET", "HTTP/1.1 999 High\r\nContent-Length: 0\r\n\r\n"),
    ("GET", "HTTP/1.1\r\n\r\n"),
    ("GET", "HTTP/1.1 \r\n\r\n"),
    ("GET", "\r\nHTTP/1.1 200 OK\r\n\r\n"),
    ("GET", "HTTP 200 OK\r\n\r\n"),
    ("GET", "200 OK\r\n\r\n"),
    ("GET", "HTTP/1.1 200 OK\nContent-Length: 2\n\nhi"),
    ("GET", "HTTP/1.1 204 No Content\r\n\r\n"),
    ("GET", "HTTP/1.1 204 No Content\r\nContent-Length: 5\r\n\r\nhello"),
    ("GET", "HTTP/1.1 304 Not Modified\r\nContent-Length: 5\r\n\r\n"),
    ("GET", "HTTP/1.1 304 Not Modified\r\nTransfer-Encoding: chunked\r\n\r\n"),
    ("GET", "HTTP/1.1 100 Continue\r\n\r\nHTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nhi"),
    ("GET", "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\nraw"),
    ("GET", "HTTP/1.1 199 Odd\r\nContent-Length: 4\r\n\r\nabcd"),
    ("HEAD", "HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\n"),
    ("HEAD", "HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello"),
    ("HEAD", "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"),
    ("HEAD", "HTTP/1.1 200 OK\r\n\r\n"),
    ("HEAD", "HTTP/1.1 200 OK\r\nContent-Length: x\r\n\r\n"),
    ("HEAD", "HTTP/1.1 200 OK\r\nContent-Length: \r\n\r\n"),
    ("POST", "HTTP/1.1 201 Created\r\nLocation: /x\r\nContent-Length: 2\r\n\r\nok"),
    ("GET", "HTTP/1.1 301 Moved\r\nLocation: http://example.com/\r\nContent-Length: 0\r\n\r\n"),
    ("GET", "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n" + chunks(["hello", " world"])),
    ("GET", "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n" + chunks([])),
    ("GET", "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n" + chunks(["a" * 300, "b" * 17, "c"])),
    ("GET", "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nContent-Length: 4\r\n\r\n" + chunks(["abcd"])),
    ("GET", "HTTP/1.0 200 OK\r\nTransfer-Encoding: chunked\r\n\r\nuntil close"),
    ("GET", "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nTrailer: X-Sum\r\n\r\n" + chunks(["hello"], trailer="X-Sum: 5\r\n")),
    ("GET", "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n" + chunks(["hello"], ext=";a=b", trailer="X-Late: 1\r\nX-Late: 2\r\n")),
    ("GET", "HTTP/1.1 200 OK\r\nTransfer-Encoding: gzip\r\n\r\nxx"),
    ("GET", "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n3\r\nabc\r\n0\r\n\r\nHTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"),
    ("GET", "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Encoding: gzip\r\nVary: Accept-Encoding\r\nSet-Cookie: a=b; Path=/\r\nSet-Cookie: c=d\r\nContent-Length: 3\r\n\r\nabc"),
    ("GET", "HTTP/1.1 200 OK\r\nConnection: Close\r\nContent-Length: 3\r\n\r\nabc"),
    ("GET", "HTTP/1.1 200 OK\r\nconnection: close, other\r\ncontent-length: 3\r\n\r\nabc"),
    ("GET", "HTTP/1.1 200 OK\r\nContent-Length: 3\r\nContent-Length: 3\r\n\r\nabc"),
    ("GET", "HTTP/1.1 200 OK\r\nContent-Length: 3\r\nContent-Length: 4\r\n\r\nabcd"),
    ("GET", "HTTP/1.1 200 OK\r\nContent-Length: 3 \r\n\r\nabc"),
    ("GET", "HTTP/1.1 200 OK\r\nContent-Length: 03\r\n\r\nabc"),
    ("GET", "HTTP/1.1 200 OK\r\nContent-Length: 9223372036854775807\r\n\r\nabc"),
    ("GET", "HTTP/1.1 200 OK\r\nContent-Length: 9223372036854775808\r\n\r\nabc"),
    ("GET", "HTTP/1.1 200 OK\r\nX-A: 1\r\n folded\r\nContent-Length: 1\r\n\r\nx"),
    ("GET", "HTTP/1.1 200 OK\r\nBad Header: 1\r\n\r\n"),
    ("GET", "HTTP/1.1 200 OK\r\nNoColon\r\n\r\n"),
    ("GET", "HTTP/1.1 200 OK\r\n Leading: 1\r\n\r\n"),
    ("GET", "HTTP/1.1 200 OK\r\nPragma: no-cache\r\nContent-Length: 0\r\n\r\n"),
    ("GET", "HTTP/1.1 200 OK"),
    ("GET", "HTTP/1.1 200 OK\r\n"),
    ("GET", "HTTP/1.1 200 OK\r\nContent-Length: 5"),
    ("GET", "HTTP/1.1 200 OK\r\nContent-Length: 5\r\n"),
    ("GET", ""),
    ("GET", "\r\n"),
    ("GET", "HTTP/1.1 200 OK\r\n\r\n"),
    ("GET", "HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\nContent-Length: 9\r\n\r\nnot found"),
    ("GET", "HTTP/1.1 500 Internal Server Error\r\nConnection: close\r\n\r\nfail"),
    ("GET", "HTTP/1.1 503 Service Unavailable\r\nRetry-After: 120\r\nContent-Length: 0\r\n\r\n"),
]

CHARS = " :;,/?#[]@%.-_~!$&'()*+=<>\"\\|^`{}abcxyz019AZ\t\r\n\x00\x7f"


def mutate(s):
    k = R.randrange(4)
    if not s:
        return R.choice(CHARS)
    i = R.randrange(len(s) + (1 if k == 0 else 0))
    c = R.choice(CHARS)
    if k == 0:
        return s[:i] + c + s[i:]
    if k == 1:
        return s[:i] + c + s[i + 1:]
    if k == 2:
        return s[:i] + s[i + 1:]
    return s[:i]


def oracle(rows):
    here = os.path.dirname(os.path.abspath(__file__))
    inp = "".join("%d %s %s %s\n" % (i, k, m, base64.b64encode(s.encode("latin-1")).decode() or "-") for i, (k, m, s) in enumerate(rows))
    out = subprocess.run(["go", "run", os.path.join(here, "http_oracle.go")], input=inp, capture_output=True, text=True, check=True).stdout
    res = {}
    for ln in out.splitlines():
        i, v = ln.split(" ", 1)
        res[int(i)] = v
    return [res[i] for i in range(len(rows))]


def main():
    path = "testdata/httpmsg.txt" if len(sys.argv) < 2 else sys.argv[1]
    base = [("req", "GET", s) for s in REQS] + [("resp", m, s) for m, s in RESPS]
    rows = list(base)
    for kind, m, s in base:
        # cut at three places
        for f in (0.3, 0.6, 0.9):
            rows.append((kind, m, s[:int(len(s) * f)]))
    for i in range(2200):
        kind, m, s = R.choice(base)
        t = mutate(s)
        if i % 3 == 0:
            t = mutate(t)
        rows.append((kind, m, t))
    seen = set()
    uniq = []
    for r in rows:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    verdicts = oracle(uniq)
    with open(path, "w") as f:
        for i, ((kind, m, s), v) in enumerate(zip(uniq, verdicts)):
            f.write("%d %s %s %s %s\n" % (i, kind, m, base64.b64encode(s.encode("latin-1")).decode() or "-", v))
    print("http corpus:", len(uniq), "messages")


main()
