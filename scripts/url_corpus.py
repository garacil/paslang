#!/usr/bin/env python3
"""P432: the corpus testdata/url.txt that testdata/url.paslang reads.

Each line is `ID BASE64 VERDICT`: a string (- for the empty one) and what Go's
net/url makes of it (scripts/url_oracle.go): Parse and ParseRequestURI, the
string resolved against three bases, and its query parsed and encoded. The
strings are RFC 3986's examples, the cases of Go's own tests that matter, and
the same with one character inserted, replaced or taken out. Everything is
seeded.

    url_corpus.py [FILE]      write testdata/url.txt
"""
import base64
import os
import random
import subprocess
import sys

R = random.Random(432)

SEEDS = """
http://www.google.com
http://www.google.com/
http://www.google.com/file%20one%26two
http://www.google.com/#file%20one%26two
ftp://webmaster@www.google.com/
ftp://john%20doe@www.google.com/
http://www.google.com/?
http://www.google.com/?foo=bar?
http://www.google.com/?q=go+language#foo
http://www.google.com/?q=go+language#foo&bar
http://www.google.com/?q=go+language#foo%26bar
file:///home/adg/rabbits
file:///C:/FooBar/Baz.txt
MaIlTo:webmaster@golang.org
a/b/c
//foo
//foo/bar
/foo?query=http://bad
/foo?query=http://bad#frag
http://[fe80::1]/
http://[fe80::1]:8080/
http://[fe80::1%25en0]/
http://[fe80::1%25en0]:8080/
http://[::ffff:1.2.3.4]/
http://[1.2.3.4]/
http://[::1]/
http://[2001:db8::1]:443/x
http://[2001:db8:0:0:0:0:0:1]/
http://192.168.0.1:80/
http://host:/p
http://host:abc/
http://a:b:c@host
http://a:b@c:d@host/
mailto:a@b.c?subject=x
tel:+1-816-555-1212
urn:isbn:0451450523
javascript:alert(1)
http://x/a b
http://x/%zz
http:// x
?
#
:
a:
1a:b
::
http://?
http://#
//:80
///
///x
x:///y
http:///
http://user:pass@host:8080/path/to?x=1&y=2#frag
http://x/a%2fb
http://x/a%2Fb/c
http://x/~user
http://x/a;b,c
http://xn--bcher-kva.de/
http://%41/
http://%ff/
http://a%25b/
http://[::1]:abc/
http://[::1
http://::1/
http://x?a=b
http://x#a
.
..
./a:b
a:b/c
*
/
//
g:h
g
./g
g/
/g
//g
?y
g?y
#s
g#s
g?y#s
;x
g;x
g;x?y#s
.
./
..
../
../g
../..
../../
../../g
../../../g
../../../../g
/./g
/../g
g.
.g
g..
..g
./../g
./g/.
g/./h
g/../h
g;x=1/./y
g;x=1/../y
g?y/./x
g?y/../x
g#s/./x
g#s/../x
http:g
http://g
http://a/b/c/d;p?q
http://a/b/c/../../../g
http://a/b/c/.
http://a/b/c/..
//a/b//c
http://a//b
http://a/./b/./
/a/b/../../c
a/../../b
http://x/%
http://x/%4
http://x/a?b=%zz
http://x/a?b=1;c=2
http://x/a?%7Bk%7D=%7Bv%7D&k=v&k=w&a+b=c+d
http://x/a?&&&
http://x/a?=
http://x/a?=&=
http://x/a?k
http://x/a?k=&l
http://x/p?x=%E4%BD%A0
http://x/日本
http://日本/
http://x/é
http://[é]/
http://x:80x/
http://x:-80/
http://x:65536/
http://x:999999999999/
https://user:@host/
https://:pw@host/
https://@host/
https://us%3Aer:p%40ss@host/
http://us er@host/
http://u%zz@host/
http:?x
http:#x
http:/x
http:x
HTTP://HOST/PATH
Http://Host:80/Path
a%20b
a%3Ab
%3A
%zz
%
x:%
x:%zz
//%zz
//x/%zz
//[::1]
//[::1]:8
//[::1]x
//x%20y
//x%25y
//x:%
//x:1:2
http://x:1:2
ftp://x:1:2
file://localhost/etc/passwd
file:/etc/passwd
file:etc
file:///
file:////etc
/\\x
\\\\x
http://x/\\y
http://x/a|b
http://x/a^b
http://x/a`b
http://x/a{b}
http://x/a<b>
http://x/a"b
http://x/a'b
http://x/a(b)
http://x/a*b
http://x/a!b
http://x/a$b
http://x/a&b
http://x/a+b
http://x/a,b
http://x/a:b
http://x/a=b
http://x/a@b
http://x/a[b]
http://x/a?b?c
http://x/a#b#c
http://x/a#b?c
http://x?#
http://x?a#
http://x#?
http://x/a%2F%2f
//x//y
////x
http://x//y
""".strip("\n").split("\n")

CHARS = " :/?#[]@%.-_~!$&'()*+,;=<>\"\\|^`{}abcxyz019AZ\t\n\x7f"


def mutate(s):
    k = R.randrange(3)
    b = s
    if not b:
        return R.choice(CHARS)
    i = R.randrange(len(b) + (1 if k == 0 else 0))
    c = R.choice(CHARS)
    if k == 0:
        return b[:i] + c + b[i:]
    if k == 1:
        return b[:i] + c + b[i + 1:]
    return b[:i] + b[i + 1:]


def oracle(inputs):
    here = os.path.dirname(os.path.abspath(__file__))
    inp = "".join("%d %s\n" % (i, base64.b64encode(s.encode("latin-1", "replace") if False else s.encode("utf-8")).decode() or "-") for i, s in enumerate(inputs))
    out = subprocess.run(["go", "run", os.path.join(here, "url_oracle.go")], input=inp, capture_output=True, text=True, check=True).stdout
    res = {}
    for ln in out.splitlines():
        i, v = ln.split(" ", 1)
        res[int(i)] = v
    return [res[i] for i in range(len(inputs))]


def main():
    path = "testdata/url.txt" if len(sys.argv) < 2 else sys.argv[1]
    inputs = list(SEEDS)
    inputs.append("")
    n = len(inputs)
    for i in range(1100):
        inputs.append(mutate(R.choice(SEEDS)))
        if i % 3 == 0:
            inputs[-1] = mutate(inputs[-1])
    seen = set()
    uniq = []
    for s in inputs:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    verdicts = oracle(uniq)
    with open(path, "w") as f:
        for i, (s, v) in enumerate(zip(uniq, verdicts)):
            f.write("%d %s %s\n" % (i, base64.b64encode(s.encode("utf-8")).decode() or "-", v))
    print("url corpus:", len(uniq), "strings")


main()
