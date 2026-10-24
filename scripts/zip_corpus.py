#!/usr/bin/env python3
"""P427: the corpus testdata/zip.txt that testdata/zip.paslang reads.

Each line is `ID VERDICT BASE64` (- for no bytes): VERDICT is `err` or `ok:COUNT:CRC`, where
CRC is the CRC-32 of the listing of the entries, one `NAME TAB SIZE TAB
CRC32 LF` each in directory order, the CRC-32 of each entry the one of the
bytes zipfile reads. The archives are what Python's zipfile writes (stored
and deflated, at the levels, with directories, comments, UTF-8 names, an
empty entry, many entries, bytes in front, data descriptors); archives
that zip64 or encryption or another method make (they are refused here and
the verdict is err, though zipfile reads all but the encrypted one);
hand-made ones that fault (a signature, a size, a CRC, the directory's
offset and size, an end record cut off); and mutants of the valid ones,
with the verdict zipfile gives.

    zip_corpus.py [FILE]      write testdata/zip.txt (or FILE)
    zip_corpus.py --check F   give each line the verdict of the zipfile
                              installed
"""
import base64
import io
import os
import random
import subprocess
import struct
import sys
import zipfile
import zlib

R = random.Random(4270)


def listing(zf):
    out = b""
    for zi in zf.infolist():
        data = zf.read(zi)
        raw = zi.orig_filename.encode("utf-8" if zi.flag_bits & 0x800 else "cp437")
        out += raw + b"\t" + str(len(data)).encode() + b"\t" + str(zlib.crc32(data) & 0xffffffff).encode() + b"\n"
    return out


def verdict(blob):
    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
        lst = listing(zf)
        return "ok:%d:%d" % (len(zf.infolist()), zlib.crc32(lst) & 0xffffffff)
    except Exception:
        return "err"


def text(n, seed):
    r = random.Random(seed)
    words = "alpha beta gamma delta sheet row cell value style number total price date name id".split()
    out = []
    size = 0
    while size < n:
        w = r.choice(words)
        out.append(w)
        size += len(w) + 1
    return " ".join(out).encode()[:n]


class NoSeek(io.RawIOBase):
    """a stream zipfile cannot seek in, so that it writes data descriptors"""

    def __init__(self):
        self.b = io.BytesIO()

    def writable(self):
        return True

    def write(self, d):
        return self.b.write(d)

    def tell(self):
        return self.b.tell()


def make(entries, method=zipfile.ZIP_DEFLATED, level=6, comment=b"", prefix=b"", seekable=True):
    if seekable:
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, "w", method, compresslevel=level if method == zipfile.ZIP_DEFLATED else None) as zf:
            for e in entries:
                name, data = e[0], e[1]
                zi = zipfile.ZipInfo(name, date_time=(2024, 3, 31, 12, 30, 58))
                zi.compress_type = e[2] if len(e) > 2 else method
                if name.endswith("/"):
                    zi.external_attr = 0o40755 << 16
                zf.writestr(zi, data, compresslevel=level)
            zf.comment = comment
        return prefix + bio.getvalue()
    ns = NoSeek()
    with zipfile.ZipFile(ns, "w", method, compresslevel=level) as zf:
        for e in entries:
            zi = zipfile.ZipInfo(e[0], date_time=(2024, 3, 31, 12, 30, 58))
            zi.compress_type = method
            with zf.open(zi, "w") as f:
                f.write(e[1])
    return prefix + ns.b.getvalue()


def go_verdicts(blobs):
    """Go's archive/zip on each (scripts/zip_oracle.go)"""
    here = os.path.dirname(os.path.abspath(__file__))
    inp = "".join("%d %s\n" % (i, b.hex() if b else "-") for i, b in enumerate(blobs))
    out = subprocess.run(["go", "run", os.path.join(here, "zip_oracle.go")], input=inp, capture_output=True, text=True,
                         check=True).stdout
    return [ln.split()[1] for ln in out.splitlines()]


def eocd(blob):
    return blob.rfind(b"PK\x05\x06")


def build():
    lines = []
    n = 0

    blobs = []
    pys = []

    def add(blob, expect=None):
        nonlocal n
        blobs.append(blob)
        pys.append(expect if expect is not None else verdict(blob))
        n += 1

    base = [("a.txt", b"hello hello hello hello"), ("dir/", b""), ("dir/b.xml", text(1200, 1)), ("empty", b""),
            ("c.bin", bytes(R.randrange(256) for _ in range(200)))]
    valid = []
    for method in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
        for level in (0, 1, 6, 9):
            if method == zipfile.ZIP_STORED and level != 6:
                continue
            b = make(base, method, level)
            add(b)
            valid.append(b)
    add(make([]))
    add(make([("x", b"")]))
    add(make(base, comment=b"an archive comment"))
    add(make([("ñandú/ç.txt", b"utf8 name"), ("日本語.xml", text(300, 2))]))
    add(make([("f%03d.txt" % i, text(R.randrange(0, 700), 100 + i)) for i in range(120)]))
    add(make([("big.xml", text(90000, 3)), ("big2.bin", bytes(R.randrange(256) for _ in range(20000)))]))
    add(make(base, prefix=b"#!/bin/sh\nexit 0\n" + b"\0" * 300))
    add(make(base, seekable=False))
    add(make([("m1", text(100, 4), zipfile.ZIP_STORED), ("m2", text(2000, 5), zipfile.ZIP_DEFLATED)]))
    # refused here: zip64, another method, encryption
    z64 = io.BytesIO()
    with zipfile.ZipFile(z64, "w", zipfile.ZIP_DEFLATED) as zf:
        with zf.open("z64.txt", "w", force_zip64=True) as f:
            f.write(b"zip64 entry")
    add(z64.getvalue())
    for meth in (zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA):
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w", meth) as zf:
            zf.writestr("m.txt", text(500, 6))
        add(b.getvalue(), "err")
    enc = bytearray(make(base))
    # set the encryption bit in the first local header and in its directory record
    enc[6] |= 1
    d = enc.find(b"PK\x01\x02")
    enc[d + 8] |= 1
    add(bytes(enc), "err")
    # faults made by hand in a good archive
    good = make(base)
    e = eocd(good)
    off = struct.unpack("<I", good[e + 16:e + 20])[0]
    size = struct.unpack("<I", good[e + 12:e + 16])[0]

    def patch(b, at, bs):
        return b[:at] + bs + b[at + len(bs):]

    add(patch(good, 0, b"PK\x03\x05"))
    add(patch(good, off, b"PK\x01\x03"))
    add(patch(good, e + 16, struct.pack("<I", off + 1)))
    add(patch(good, e + 16, struct.pack("<I", len(good))))
    add(patch(good, e + 12, struct.pack("<I", size + 1)))
    add(patch(good, e + 12, struct.pack("<I", size - 1)))
    add(patch(good, e + 10, struct.pack("<H", 99)))
    add(patch(good, e + 8, struct.pack("<H", 1)))
    add(patch(good, e + 4, struct.pack("<H", 1)))
    add(patch(good, off + 16, struct.pack("<I", 12345)))
    add(patch(good, off + 20, struct.pack("<I", 5)))
    add(patch(good, off + 24, struct.pack("<I", 5)))
    add(patch(good, off + 24, struct.pack("<I", 0xffffffff)))
    add(patch(good, off + 42, struct.pack("<I", 0xffffffff)))
    add(patch(good, e + 20, struct.pack("<H", 40)))
    add(good[:e])
    add(good[:e + 10])
    add(good[:20])
    add(b"")
    add(b"PK\x05\x06" + b"\0" * 18)
    add(b"not a zip archive at all, but long enough to hold the end record 0123456789")
    # mutants of the valid ones
    for i, b in enumerate(valid):
        r = random.Random(500 + i)
        for _ in range(30):
            m = bytearray(b)
            k = r.randrange(5)
            if k == 0:
                m[r.randrange(len(m))] ^= 1 << r.randrange(8)
            elif k == 1:
                m[r.randrange(len(m))] = r.randrange(256)
            elif k == 2:
                m = m[:r.randrange(len(m))]
            elif k == 3:
                j = r.randrange(len(m))
                m = m[:j] + m[j + 1:]
            else:
                j = r.randrange(max(1, len(m) - 120), len(m))
                m[j] = r.randrange(256)
            add(bytes(m))
    # a verdict is firm when zipfile and Go say the same; where they differ
    # the line holds both (either|ZIPFILE|GO) and a reader may say either
    gos = go_verdicts(blobs)
    for i, b in enumerate(blobs):
        v = pys[i] if pys[i] == gos[i] else "either|%s|%s" % (pys[i], gos[i])
        lines.append("%d %s %s" % (i, v, base64.b64encode(b).decode() if b else "-"))
    return lines


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--check":
        bad = 0
        for ln in open(sys.argv[2]):
            i, v, h = ln.split()
            blob = b"" if h == "-" else base64.b64decode(h)
            got = verdict(blob)
            ok = got in v.split("|")[1:2] if v.startswith("either|") else got == v
            if not ok and not v.startswith("err"):
                bad += 1
                print("differs", i, v, got)
        print("zip corpus check:", "ok" if not bad else "%d differ" % bad)
        sys.exit(1 if bad else 0)
    lines = build()
    path = "testdata/zip.txt" if len(sys.argv) < 2 else sys.argv[1]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("zip corpus:", len(lines), "archives,", sum(len(x) for x in lines) // 1024, "KiB")


main()
