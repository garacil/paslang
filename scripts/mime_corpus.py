#!/usr/bin/env python3
"""P433: the corpus testdata/mime.txt that testdata/mime.paslang reads.

Each line is `ID KIND ARG... = VERDICT`: a case (KIND qpdec, qpenc, wdec,
hdec, wenc, mt, fmt, mp, addr, addrs, date, msg; ARGs base64) and what Go's
mime, multipart, quotedprintable and net/mail make of it
(scripts/mime_oracle.go). The cases are seeds taken from the RFCs and Go's own
tests, each also with a byte put in, changed or taken out. Seeded.

    mime_corpus.py [FILE]      write testdata/mime.txt
"""
import re
import base64
import os
import random
import subprocess
import sys

R = random.Random(4330)


def b(s):
    if isinstance(s, str):
        s = s.encode("utf-8")
    return base64.b64encode(s).decode() or "-"


QPDEC = [
    "hello", "caf=C3=A9", "a=3Db", "soft=\r\nbreak", "soft=\nbreak", "a=\r\n", "trailing=  \r\nx", "x=",
    "=", "=4", "=41=42=43", "=4G", "=g1", "=zz", "a b \r\n", "a b \t\r\nc", "line1\r\nline2\r\n", "line1\nline2\n",
    "tab\there", "bare\rcr", "ctl\x01x", "high\xe9", "=3d=3D", "a=3Db=", "a=\r", "=\r\n=\r\n", "long" * 40 + "=\r\nmore",
    "x =20\r\n", "x\t=\r\ny", "=C3=A9=C3", "a= \r\nb", "a=  x\r\nb", "a=  \r\n", "a=  ", "=E2=82=AC", "",
    "a\r\n\r\nb", "=0D=0A", "=0d=0a", "=\t\r\nx", "q=22uoted=22", "dot.\r\n.dot", "=3F=5F=3D",
]
QPENC = [
    "hello", "caf\u00e9", "a=b", "line1\r\nline2", "line1\nline2", "trailing space \r\nx", "tab\t\r\n", "x" * 100, "x" * 76, "x" * 75,
    "é" * 50, "a b c " * 30, "\r\n\r\n", "end space ", "end tab\t", " ", "\x00\x01\x02", "caf\u00e9\r\n" * 20, "=" * 30,
    "mix \u20ac and ascii " * 10, "\r", "\r\r\n", "a\n\rb", "", "x\ty\tz\t" * 20,
]
WORDS = [
    "=?UTF-8?Q?caf=C3=A9?=", "=?utf-8?b?Y2Fmw6k=?=", "=?ISO-8859-1?Q?caf=E9?=", "=?iso-8859-1?B?Y2Fm6Q==?=",
    "=?us-ascii?q?hello_world?=", "=?US-ASCII?Q?h=E9llo?=", "=?windows-1252?Q?caf=E9?=", "=?iso-8859-15?Q?=A4?=",
    "=?UTF-8?Q?=E2=82=AC?=", "=?UTF-8?q?a_b?=", "=?UTF-8?Q?a=?=", "=?UTF-8?Q?a=2?=", "=?UTF-8?Q?a=zz?=", "=?UTF-8?X?abc?=",
    "=?UTF-8?B?!!!?=", "=?UTF-8?B?YQ?=", "=?UTF-8?B?YQ==?=", "=??Q?abc?=", "=?UTF-8??abc?=", "=?UTF-8?Q?abc", "UTF-8?Q?abc?=",
    "=?UTF-8?Q?a?= =?UTF-8?Q?b?=", "=?UTF-8?Q?a?=  =?UTF-8?Q?b?=", "=?UTF-8?Q?a?=\r\n =?UTF-8?Q?b?=", "x =?UTF-8?Q?a?= y",
    "x=?UTF-8?Q?a?=y", "a =?UTF-8?Q?b?= c =?UTF-8?B?ZA==?= e", "=?UTF-8?Q?a?= text =?UTF-8?Q?b?=", "plain", "=?", "?=", "=??=",
    "=?UTF-8?Q??=", "=?UTF-8?Q?a?==?UTF-8?Q?b?=", "=?koi8-r?Q?abc?=", "=?UTF-8?Q?=C3?=", "=?UTF-8?Q?=ZZ?= =?UTF-8?Q?ok?=",
    "Re: =?UTF-8?Q?Informaci=C3=B3n?= del pedido", "=?UTF-8?B?" + base64.b64encode("ñandú ".encode() * 6).decode() + "?=",
    "=?UTF-8?Q?a_b_c?=", "=?UTF-8?Q?" + "x" * 80 + "?=", "=?utf-8?Q?\x01?=", "=?utf-8?Q?\xe9?=",
]
WENC = [
    ("utf-8", "hello", "q"), ("utf-8", "café", "q"), ("utf-8", "café", "b"), ("iso-8859-1", "caf\xe9", "q"), ("iso-8859-1", "caf\xe9", "b"),
    ("utf-8", "ñandú " * 20, "q"), ("utf-8", "ñandú " * 20, "b"), ("utf-8", "日本語" * 10, "b"), ("utf-8", "日本語" * 10, "q"),
    ("utf-8", "a=b?c_d", "q"), ("utf-8", "tab\there", "q"), ("utf-8", "€" * 30, "q"), ("utf-8", "€" * 30, "b"), ("UTF-8", "é", "q"),
    ("utf-8", "", "q"), ("utf-8", "\x01", "b"), ("us-ascii", "caf\xe9", "q"), ("utf-8", "x" * 200 + "é", "b"), ("utf-8", "é" * 40, "q"),
    ("utf-8", "é" * 22, "b"), ("utf-8", "é" * 23, "b"), ("utf-8", "é" * 21, "q"), ("utf-8", "é" * 22, "q"),
]
MT = [
    "text/plain", "text/plain; charset=utf-8", "TEXT/HTML; Charset=\"UTF-8\"", "multipart/mixed; boundary=\"=_abc\"", "text/plain;",
    "text/plain; ", "text/plain ; charset=us-ascii", "application/octet-stream; name=\"a b.txt\"", "attachment; filename=a.csv",
    "attachment; filename*=UTF-8''%E2%82%AC%20rates.csv", "attachment; filename*0=\"a\"; filename*1=\"b\"", "attachment; filename*0*=UTF-8''a%20; filename*1*=b%20c",
    "attachment; filename*0*=utf-8''a; filename*1=b", "attachment; filename=\"a\"; filename*=utf-8''b", "attachment; filename*=latin1''%E9",
    "inline", "", ";", "text", "/plain", "text/", "text/plain/x", "text/plain; =x", "text/plain; a", "text/plain; a=", "text/plain; a=\"b",
    "text/plain; a=\"b\\\"c\"", "text/plain; a=b; a=c", "text/plain; a=b; a=b", "text/plain; A=b; a=c", "text/plain; a=b c",
    "text/plain; charset=\"utf-8\"; format=flowed", "text/plain;charset=utf-8;format=flowed", "text/plain; charset=utf-8 ;", "text/pl@in",
    "application/x-www-form-urlencoded", "message/rfc822", "image/png; name=a.png; x=\"\"", "x/y; a=\"\\\\\"", "x/y; a=\"line\r\nbreak\"",
    "x/y; a*=utf-8''%zz", "x/y; a*0=1; a*2=3", "x/y; a*1=2", "x/y; a*0*=us-ascii''x; a*1*=%41", "x/y; a*=ISO-8859-1'es'%E9",
]
FMT = [
    ("text/plain", {}), ("TEXT/HTML", {"charset": "utf-8"}), ("multipart/mixed", {"boundary": "a b"}), ("attachment", {"filename": "a.csv"}),
    ("attachment", {"filename": "añb.csv"}), ("attachment", {"filename": "a\"b\\c"}), ("attachment", {"filename": "a b"}), ("text", {}),
    ("te xt/plain", {}), ("text/pl ain", {}), ("a/b", {"x y": "z"}), ("a/b", {"b": "2", "a": "1", "C": "3"}), ("a/b", {"n": ""}),
    ("a/b", {"n": "é*'%"}), ("", {}), ("a/b", {"n": "x;y"}), ("a/b", {"n": "x\ty"}), ("a/b", {"n": "caf\u00e9 ☕"}),
]
BOUND = "frontier"
MP = [
    ("--frontier\r\nContent-Type: text/plain\r\n\r\nhello\r\n--frontier--\r\n", BOUND, 0),
    ("preamble\r\n--frontier\r\nA: b\r\n\r\nx\r\n--frontier\r\nC: d\r\n\r\ny\r\n--frontier--\r\nepilogue", BOUND, 0),
    ("--frontier\nContent-Type: text/plain\n\nunix\n--frontier--\n", BOUND, 0),
    ("--frontier\r\n\r\nempty headers\r\n--frontier--", BOUND, 0),
    ("--frontier\r\nA: b\r\n\r\n\r\n--frontier--\r\n", BOUND, 0),
    ("--frontier\r\nA: b\r\n\r\nno end", BOUND, 0),
    ("--frontier\r\nA: b\r\n\r\nbody\r\n--frontier", BOUND, 0),
    ("--frontier\r\nA: b\r\n\r\nbody\r\n--frontierX\r\nstill body\r\n--frontier--\r\n", BOUND, 0),
    ("--frontier\r\nA: b\r\n\r\nbody\r\n--frontier-x\r\nmore\r\n--frontier--\r\n", BOUND, 0),
    ("--frontier \r\nA: b\r\n\r\nbody\r\n--frontier\t\r\nA: c\r\n\r\nz\r\n--frontier--  \r\n", BOUND, 0),
    ("--frontier\r\nContent-Transfer-Encoding: quoted-printable\r\n\r\ncaf=C3=A9 =\r\nok\r\n--frontier--\r\n", BOUND, 0),
    ("--frontier\r\nContent-Transfer-Encoding: quoted-printable\r\n\r\ncaf=C3=A9 =\r\nok\r\n--frontier--\r\n", BOUND, 1),
    ("--frontier\r\nContent-Transfer-Encoding: Quoted-Printable\r\n\r\nbad=ZZ=\r\n--frontier--\r\n", BOUND, 0),
    ("--frontier\r\nA: b\r\n\r\nx\r\n--frontier--\r\n", "", 0),
    ("--frontier\r\nA: b\r\n\r\nx\r\n--frontier--\r\n", "other", 0),
    ("", BOUND, 0), ("--frontier--", BOUND, 0), ("--frontier--\r\n", BOUND, 0), ("--frontier\r\n", BOUND, 0), ("--frontier\r\nA: b", BOUND, 0),
    ("--frontier\r\nA: b\r\n", BOUND, 0), ("--frontier\r\n bad: first\r\n\r\nx\r\n--frontier--", BOUND, 0), ("--frontier\r\nNoColon\r\n\r\nx\r\n--frontier--", BOUND, 0),
    ("--frontier\r\nA: b\r\n\r\nx\r\n\r\n--frontier--\r\n", BOUND, 0), ("--frontier\r\nA: b\r\n\r\nx\r\njunk\r\n--frontier--\r\n", BOUND, 0),
    ("junk\r\n--frontier\r\nA: b\r\n\r\nx\r\n--frontier--\r\n", BOUND, 0),
    ("--frontier\r\nA: b\r\n\r\nx\r\n--frontier--\r\n--frontier\r\nA: c\r\n\r\ny\r\n--frontier--\r\n", BOUND, 0),
    ("--frontier\r\nA: 1\r\nA: 2\r\n b\r\n\r\nx\r\n--frontier--\r\n", BOUND, 0),
    ("--frontier\r\nContent-Disposition: form-data; name=\"f\"; filename=\"a.txt\"\r\n\r\ndata\r\n--frontier--\r\n", BOUND, 0),
    ("--a b\r\nA: b\r\n\r\nx\r\n--a b--\r\n", "a b", 0),
    ("--frontier\r\nA: b\r\n\r\n" + "x" * 5000 + "\r\n--frontier--\r\n", BOUND, 0),
    ("--frontier\r\nA: b\r\n\r\n" + "\r\n--frontie" * 3 + "\r\n--frontier--\r\n", BOUND, 0),
    ("--frontier\r\nA: b\r\n\r\nx\r\n--frontier--\r\n", BOUND, 1),
    ("--frontier\r\nA: b\r\n\r\n--frontier\r\n--frontier--\r\n", BOUND, 0),
]

ADDR = [
    "Barry Gibbs <bg@example.com>", "bg@example.com", "<bg@example.com>", "John Q. Public <john.q.public@example.com>",
    "\"Joe Q. Public\" <john.q.public@example.com>", "Mary Smith <mary@x.test>, jdoe@example.org, Who? <one@y.test>",
    "A Group:Ed Jones <c@a.test>,joe@where.test,John <jdoe@one.test>;", "Undisclosed recipients:;", "Group: ;",
    "john@example.com (John Doe)", "john@example.com (=?UTF-8?Q?Jos=C3=A9?= Doe)", "=?UTF-8?Q?Jos=C3=A9?= <jose@example.com>",
    "=?ISO-8859-1?Q?Jos=E9?= <jose@example.com>", "=?windows-1252?Q?Jos=E9?= <jose@example.com>", "=?utf-8?b?w6k=?= <e@x.y>",
    "José <jose@example.com>", "\"José\" <jose@example.com>", "Jos\u00e9 =?UTF-8?Q?Gar=C3=A7on?= <j@x.y>", "a@b", "a@b.c.d",
    "a.b@c.d", ".a@b.c", "a..b@c.d", "a.@b.c", "\"a b\"@c.d", "\"\"@c.d", "a@[1.2.3.4]", "a@[IPv6:::1]", "a@[IPv6:1::2]", "a@[1.2.3]",
    "a@[::1]", "a@[1.2.3.4", "a@", "@b.c", "a", "a b", "<a@b.c", "a@b.c>", "<>", "", " ", ",", "a@b.c,", ",a@b.c", "a@b.c, ,d@e.f",
    "a@b.c d@e.f", "a@b.c;", "Name <a@b.c> extra", "Name <a@b.c> (comment)", "(comment) a@b.c", "a@b.c (unclosed", "a@b.c (nested (comment))",
    "\"unclosed <a@b.c>", "\"a\\\"b\" <a@b.c>", "\"a\\\x01b\" <a@b.c>", "Na\"me <a@b.c>", "Name, Other <a@b.c>", "Name; Other <a@b.c>",
    "a@b.c, d@e.f, g@h.i", "<a@b.c>, <d@e.f>", "Ñandú <n@x.y>", "日本語 <j@x.y>", "a@日本.jp", "a\x01@b.c", "a\xff@b.c", "a@b\xffc",
    "Re: <a@b.c>", "Mary <m@x.y>, Joe <j@x.y>, Ann <a@x.y>", "First Last <fl@x.y>, \"Last, First\" <lf@x.y>", "a@b.c, Group: d@e.f, g@h.i;",
    "G1: a@b.c; G2: d@e.f;", "G: G2: a@b.c;;", "<a@b.c>(c)", "x <a@b.c>,", "=?UTF-8?Q?a?==?UTF-8?Q?b?= <a@b.c>", "=?UTF-8?Q?a?= =?UTF-8?Q?b?= c <a@b.c>",
    "a =?UTF-8?Q?b?= c <a@b.c>", "=?koi8-r?Q?a?= <a@b.c>", "=?UTF-8?Q?=ZZ?= <a@b.c>",
]
DATE = [
    "Fri, 21 Nov 1997 09:55:06 -0600", "21 Nov 1997 09:55:06 -0600", "Fri, 21 Nov 97 09:55:06 -0600", "Fri, 21 Nov 1997 09:55 -0600",
    "Fri, 1 Nov 1997 09:55:06 +0000", "Fri, 01 Nov 1997 09:55:06 GMT", "Fri, 01 Nov 1997 09:55:06 UT", "Fri, 01 Nov 1997 09:55:06 UTC",
    "Fri, 01 Nov 1997 09:55:06 -0000", "Fri, 01 Nov 1997 09:55:06 +0530", "Fri, 01 Nov 1997 09:55:06 +0545", "Fri, 01 Nov 1997 09:55:06 +1400",
    "Fri, 01 Nov 1997 09:55:06 +2500", "Fri, 01 Nov 1997 09:55:06 +0061", "Fri, 01 Nov 1997 09:55:06 +0060", "Fri, 01 Nov 1997 09:55:06 +24:00",
    "Fri, 01 Nov 1997 09:55:06 -0600 (CST)", "Fri, 01 Nov 1997 09:55:06 -0600 (CST", "Fri, 01 Nov 1997 09:55:06 -0600 junk", "fri, 01 nov 1997 09:55:06 -0600",
    "Xxx, 01 Nov 1997 09:55:06 -0600", "Fri, 01 Nov 1997 09:55:06.123 -0600", "Fri, 01 Nov 1997 09:55:06,5 -0600", "Fri, 01 Nov 1997 25:55:06 -0600",
    "Fri, 01 Nov 1997 09:60:06 -0600", "Fri, 01 Nov 1997 09:55:60 -0600", "Fri, 31 Nov 1997 09:55:06 -0600", "Fri, 29 Feb 1997 09:55:06 -0600",
    "Fri, 29 Feb 2000 09:55:06 -0600", "Fri, 29 Feb 1900 09:55:06 -0600", "Fri, 00 Nov 1997 09:55:06 -0600", "Fri, 32 Nov 1997 09:55:06 -0600",
    "Fri, 01 Foo 1997 09:55:06 -0600", "Fri, 01 Nov 997 09:55:06 -0600", "Fri, 01 Nov 19970 09:55:06 -0600", "Fri,01 Nov 1997 09:55:06 -0600",
    "Fri, 01  Nov 1997 09:55:06 -0600", "Fri, 01 Nov 1997 9:55:06 -0600", "Fri, 01 Nov 1997 09:5:06 -0600", "Fri, 01 Nov 1997 09:55:6 -0600",
    "Fri, 01 Nov 1997 09:55:06-0600", "Fri, 01 Nov 1997 09:55:06 -060", "Fri, 01 Nov 1997 09:55:06 -06000", "Fri, 01 Nov 1997 09:55:06",
    "", " ", "Fri, 01 Nov 1997", "Tue, 10 Jun 2003 04:00:00 +0000", "Thu, 13 Feb 1969 23:32:54 -0330", "Mon, 02 Jan 2006 15:04:05 MST",
    "  Fri, 21 Nov 1997 09:55:06 -0600", "Fri, 21 Nov 1997 09:55:06 -0600\r\n", "Fri, 21 Nov 1997\r\n 09:55:06 -0600", "Fri, 21 Nov 1997\r09:55:06 -0600",
    "Fri, 21 Nov 1997 09:55:06 +0100 (CET)", "Sat, 31 Dec 2022 23:59:59 +1300", "Sun, 01 Jan 2023 00:00:00 -1200", "1 Jan 70 00:00 +0000",
    "1 Jan 68 00:00 +0000", "1 Jan 69 00:00 +0000", "Fri, 21 Nov 1997 09:55:06 GMT+3", "Fri, 21 Nov 1997 09:55:06 UT ", "Fri, 21 Nov 1997 09:55:06 +0000 (UT)",
    "2006-01-02T15:04:05Z", "Mon, 2 Jan 2006 15:04:05 -0700", "Mon, 02 Jan 06 15:04 -0700", "02 Jan 2006 15:04:05 -0700", "Tue, 10 Jun 2003 04:00:00 +0000 (GMT)",
]
MSG = [
    "From: a@b.c\r\nTo: d@e.f\r\nSubject: hi\r\n\r\nbody\r\n", "From: a@b.c\nSubject: unix\n\nbody\n", "Subject: folded\r\n line two\r\n\tline three\r\n\r\nb",
    "A: 1\r\nA: 2\r\nB: 3\r\n\r\n", "a: lower\r\nX-Weird_Header: v\r\n\r\n", "Subject: no blank line", "Subject: x\r\n", "\r\nbody only", "",
    " leading: space\r\n\r\n", "NoColon\r\n\r\n", "A: 1\r\nNoColon\r\n\r\nb", ": empty key\r\nA: 1\r\n\r\n", "A :spaced\r\n\r\n", "A:\r\n\r\n", "A:   v  \r\n\r\n",
    "From a@b.c Mon Jan  1 00:00:00 2000\r\nSubject: mbox\r\n\r\nb", "A: \xe9\r\n\r\n", "A: 1\r\n  \r\nB: 2\r\n\r\n", "A: 1\r\n\r\n\r\nB: not header\r\n",
    "Content-Type: multipart/mixed; boundary=x\r\n\r\n--x\r\n\r\nhi\r\n--x--\r\n", "A: 1\rB: 2\r\n\r\n",
]

CHARS = " :;,/?#[]@%.-_~!$&'()*+=<>\"\\|^`{}abcxyz019AZ\t\n\r"


def mutate(s):
    k = R.randrange(3)
    if not s:
        return R.choice(CHARS)
    i = R.randrange(len(s) + (1 if k == 0 else 0))
    c = R.choice(CHARS)
    if k == 0:
        return s[:i] + c + s[i:]
    if k == 1:
        return s[:i] + c + s[i + 1:]
    return s[:i] + s[i + 1:]


def build():
    rows = []
    for a in ADDR:
        rows.append(("addr", [a]))
        rows.append(("addrs", [a]))
    for d in DATE:
        rows.append(("date", [d]))
    for m in MSG:
        rows.append(("msg", [m]))
    for s in QPDEC:
        rows.append(("qpdec", [s]))
    for s in QPENC:
        rows.append(("qpenc", [s, "0"]))
        rows.append(("qpenc", [s, "1"]))
    for w in WORDS:
        rows.append(("wdec", [w]))
        rows.append(("hdec", [w]))
    for cs, t, e in WENC:
        rows.append(("wenc", [cs, t, e]))
    for m in MT:
        rows.append(("mt", [m]))
    for t, p in FMT:
        rows.append(("fmt", [t, "\x00".join(x for kv in p.items() for x in kv) if p else ""]))
    for body, bd, raw in MP:
        rows.append(("mp", [body, bd, str(raw)]))
    base = list(rows)
    for i in range(1800):
        kind, args = R.choice(base)
        a = list(args)
        if kind == "mp":
            a[0] = mutate(a[0])
            if i % 3 == 0:
                a[0] = mutate(a[0])
        elif kind in ("wenc", "fmt", "qpenc"):
            a[1 if kind != "wenc" else 1] = mutate(a[1]) if kind != "fmt" else a[1]
        else:
            a[0] = mutate(a[0])
            if i % 3 == 0:
                a[0] = mutate(a[0])
        rows.append((kind, a))
    return rows


def oracle(lines):
    here = os.path.dirname(os.path.abspath(__file__))
    inp = "".join("%d %s %s\n" % (i, k, " ".join(b(x) for x in a)) for i, (k, a) in enumerate(lines))
    env = dict(os.environ, TZ="UTC")
    out = subprocess.run(["go", "run", os.path.join(here, "mime_oracle.go")], input=inp, capture_output=True, text=True, check=True, env=env).stdout
    res = {}
    for ln in out.splitlines():
        i, v = ln.split(" ", 1)
        res[int(i)] = v
    return [res[i] for i in range(len(lines))]


def main():
    path = "testdata/mime.txt" if len(sys.argv) < 2 else sys.argv[1]
    rows = build()
    seen = set()
    uniq = []
    for kind, a in rows:
        key = (kind, tuple(a))
        if key in seen:
            continue
        seen.add(key)
        uniq.append((kind, a))
    verdicts = oracle(uniq)
    # Go knows the North American zone names only when its local zone has them
    # (it takes any other name for UTC); RFC 5322's obs-zone gives them their
    # offsets, as the numeric zone does, so a date with such a name may be
    # either of the two verdicts: either#GO#NUMERIC
    na = {"EST": "-0500", "EDT": "-0400", "CST": "-0600", "CDT": "-0500",
          "MST": "-0700", "MDT": "-0600", "PST": "-0800", "PDT": "-0700"}
    pat = re.compile(r"(?<![A-Za-z])(EST|EDT|CST|CDT|MST|MDT|PST|PDT)(?![A-Za-z])")
    alt = []
    for kind, a in uniq:
        if kind == "date" and pat.search(a[0]):
            alt.append((kind, [pat.sub(lambda m: na[m.group(1)], a[0])]))
    altv = dict(zip([x[1][0] for x in alt], oracle(alt))) if alt else {}
    with open(path, "w") as f:
        for i, ((kind, a), v) in enumerate(zip(uniq, verdicts)):
            if kind == "date" and pat.search(a[0]):
                w = altv[pat.sub(lambda m: na[m.group(1)], a[0])]
                if w != v:
                    v = "either#%s#%s" % (v, w)
            f.write("%d %s %s = %s\n" % (i, kind, " ".join(b(x) for x in a), v))
    print("mime corpus:", len(uniq), "cases")


main()
