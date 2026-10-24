#!/usr/bin/env python3
"""P427: the corpus testdata/flate.txt that testdata/flate.paslang reads.

Each line is `KIND ID VERDICT BASE64STREAM` (- for no bytes): KIND raw, zlib or gzip, VERDICT
`ok:LENGTH:CRC32` (the bytes the stream makes, as zlib makes them) or
`err` (zlib refuses it). The streams are what zlib writes at every level,
strategy and memory level, with flushes inside, on data of many shapes;
a few gzip files of several members; hand-made DEFLATE (stored blocks,
fixed Huffman, a distance at the window's edge); and mutants of those
(a bit flipped, a byte changed, cut short, bytes added), each with the
verdict zlib gives it. The program prints only the lines whose verdict it
does not share.

    flate_corpus.py                 write testdata/flate.txt
    flate_corpus.py --check FILE    read FILE again and give each line the
                                    verdict of the zlib installed (it
                                    must be the one in the file)

Everything is seeded, so the file is the same on each run, whatever the
Python (the streams are zlib's output: another zlib may write other bytes,
and the verdicts are the same).
"""
import base64
import os
import random
import struct
import subprocess
import sys
import zlib

R = random.Random(427)

WORDS = ("the of and to in is that for it as with was on be by at this from or have an are not but had which they you were "
         "all her she there would their we him been has when who will more no if out so said what up its about into than "
         "them can only other new some could time these two may then do first any my now such like our over man me even "
         "most made after also did many before must through back years where much your way well down should because each "
         "just those people mr how too little state good very make world still own see men work long get here between "
         "both life being under never day same another know while last might us great old year off come since against go "
         "came right used take three").split()


def text(n, seed):
    r = random.Random(seed)
    out = []
    size = 0
    while size < n:
        w = r.choice(WORDS)
        if r.random() < 0.1:
            w = w.capitalize() + "."
        out.append(w)
        size += len(w) + 1
    return (" ".join(out)).encode()[:n]


def rnd(n, seed):
    return random.Random(seed).randbytes(n)


def period(p, n, seed):
    base = random.Random(seed).randbytes(p)
    return (base * (n // p + 1))[:n]


def datasets():
    d = []
    d.append(("empty", b""))
    d.append(("one", b"a"))
    d.append(("two", b"ab"))
    d.append(("zeros1k", bytes(1000)))
    d.append(("zeros60k", bytes(60000)))
    d.append(("ones", b"\xff" * 40000))
    d.append(("text1k", text(1000, 1)))
    d.append(("text8k", text(8000, 2)))
    d.append(("text25k", text(25000, 3)))
    d.append(("random1k", rnd(1000, 4)))
    d.append(("random4k", rnd(4000, 5)))
    for p in (1, 2, 3, 4, 7, 16, 100, 258, 259, 300, 1000, 4096, 20000):
        d.append(("period%d" % p, period(p, 40000, p)))
    d.append(("longmatch", b"x" * 258 + b"y" + b"x" * 259 + b"z" + b"x" * 1000))
    mix = text(10000, 8) + rnd(2000, 9) + bytes(7000) + text(10000, 10) + period(5, 9000, 11)
    d.append(("mixed", mix))
    d.append(("alphabet", bytes(range(256)) * 100))
    d.append(("skew", bytes(random.Random(12).choice([0, 0, 0, 0, 0, 0, 1, 2, 3, 255]) for _ in range(20000))))
    d.append(("skew2", bytes(min(int(random.Random(13 + i).expovariate(0.3)), 255) for i in range(15000))))
    for i, n in enumerate((3, 10, 40, 100, 300, 700, 1500, 2500)):
        d.append(("small-text%d" % n, text(n, 50 + i)))
        d.append(("small-rnd%d" % n, rnd(n, 60 + i)))
        d.append(("small-per%d" % n, period(1 + i * 3, n, 70 + i)))
    return d


def comp(data, level, wbits, strategy=zlib.Z_DEFAULT_STRATEGY, mem=8):
    c = zlib.compressobj(level, zlib.DEFLATED, wbits, mem, strategy)
    return c.compress(data) + c.flush()


def comp_flushed(data, level, wbits, seed):
    r = random.Random(seed)
    c = zlib.compressobj(level, zlib.DEFLATED, wbits)
    out = b""
    i = 0
    while i < len(data):
        n = r.choice([1, 7, 100, 1000, 5000, 40000])
        out += c.compress(data[i:i + n])
        i += n
        k = r.random()
        if k < 0.3:
            out += c.flush(zlib.Z_SYNC_FLUSH)
        elif k < 0.4:
            out += c.flush(zlib.Z_FULL_FLUSH)
        elif k < 0.45:
            out += c.flush(zlib.Z_PARTIAL_FLUSH)
    return out + c.flush()


def verdict(kind, blob):
    if kind == "gzipm":
        import gzip
        try:
            out = gzip.decompress(blob)
            return "ok:%d:%08x" % (len(out), zlib.crc32(out) & 0xffffffff)
        except Exception:
            return "err"
    wbits = {"raw": -15, "zlib": 15, "gzip": 31}[kind]
    try:
        d = zlib.decompressobj(wbits)
        out = d.decompress(blob)
        if not d.eof or d.unused_data:
            return "err"
        return "ok:%d:%08x" % (len(out), zlib.crc32(out) & 0xffffffff)
    except zlib.error:
        return "err"


def go_verdicts(rows):
    """Go's compress/flate, zlib and gzip on each (scripts/flate_oracle.go)"""
    here = os.path.dirname(os.path.abspath(__file__))
    inp = "".join("%s %d %s\n" % (k, i, b.hex() if b else "-") for i, (k, b) in enumerate(rows))
    out = subprocess.run(["go", "run", os.path.join(here, "flate_oracle.go")], input=inp, capture_output=True, text=True,
                         check=True).stdout
    return [ln.split()[1] for ln in out.splitlines()]


def gzip_members(parts, level):
    out = b""
    for p in parts:
        out += comp(p, level, 31)
    return out


def verdict_gzip_multi(parts):
    full = b"".join(parts)
    return "ok:%d:%08x" % (len(full), zlib.crc32(full) & 0xffffffff)


def gzip_header(flags, mtime=0x11223344, name=b"", comment=b"", extra=b"", hcrc=False):
    h = struct.pack("<BBBBIBB", 31, 139, 8, flags, mtime, 0, 3)
    if flags & 4:
        h += struct.pack("<H", len(extra)) + extra
    if flags & 8:
        h += name + b"\0"
    if flags & 16:
        h += comment + b"\0"
    if flags & 2:
        h += struct.pack("<H", zlib.crc32(h) & 0xffff)
    return h


def raw_deflate_stored(data, final=True, blocks=None):
    out = b""
    parts = blocks if blocks is not None else [data]
    for i, p in enumerate(parts):
        last = final and i == len(parts) - 1
        out += bytes([1 if last else 0]) + struct.pack("<HH", len(p), len(p) ^ 0xffff) + p
    return out


class Bits:
    def __init__(self):
        self.v = 0
        self.n = 0
        self.out = bytearray()

    def put(self, val, nbits):
        self.v |= val << self.n
        self.n += nbits
        while self.n >= 8:
            self.out.append(self.v & 255)
            self.v >>= 8
            self.n -= 8

    def code(self, code, nbits):
        r = 0
        for _ in range(nbits):
            r = (r << 1) | (code & 1)
            code >>= 1
        self.put(r, nbits)

    def done(self):
        if self.n:
            self.out.append(self.v & 255)
        return bytes(self.out)


def fixed_lit(b, sym):
    if sym < 144:
        b.code(0x30 + sym, 8)
    elif sym < 256:
        b.code(0x190 + sym - 144, 9)
    elif sym < 280:
        b.code(sym - 256, 7)
    else:
        b.code(0xc0 + sym - 280, 8)


LB = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258]
LE = [0] * 8 + [1] * 4 + [2] * 4 + [3] * 4 + [4] * 4 + [5] * 4 + [0]
DB = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145,
      8193, 12289, 16385, 24577]
DE = [0, 0, 0, 0] + [i // 2 for i in range(1, 27)]
DE = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13]


def fixed_block(items, final=True):
    """items: ('lit', byte) or ('match', length, dist)"""
    b = Bits()
    b.put(1 if final else 0, 1)
    b.put(1, 2)
    for it in items:
        if it[0] == "lit":
            fixed_lit(b, it[1])
        else:
            ln, dist = it[1], it[2]
            s = max(i for i in range(29) if LB[i] <= ln)
            if ln == 258:
                s = 28
            fixed_lit(b, 257 + s)
            if LE[s]:
                b.put(ln - LB[s], LE[s])
            ds = max(i for i in range(30) if DB[i] <= dist)
            b.code(ds, 5)
            if DE[ds]:
                b.put(dist - DB[ds], DE[ds])
    fixed_lit(b, 256)
    return b.done()


def mutants(kind, blob, count, seed):
    r = random.Random(seed)
    out = []
    for i in range(count):
        m = bytearray(blob)
        k = r.randrange(7)
        if not m:
            m = bytearray(b"\0")
        if k == 0:
            m[r.randrange(len(m))] ^= 1 << r.randrange(8)
        elif k == 1:
            m[r.randrange(len(m))] = r.randrange(256)
        elif k == 2:
            m = m[:r.randrange(len(m))]
        elif k == 3:
            m = m + bytes(r.randrange(256) for _ in range(r.randrange(1, 5)))
        elif k == 4:
            j = r.randrange(len(m))
            m = m[:j] + m[j + 1:]
        elif k == 5:
            j = r.randrange(len(m) + 1)
            m = m[:j] + bytes([r.randrange(256)]) + m[j:]
        else:
            # the first bytes are the block header, the likeliest to break the tables
            j = r.randrange(min(len(m), 12))
            m[j] ^= 1 << r.randrange(8)
        out.append(bytes(m))
    return out


def build():
    lines = []
    n = 0

    rows = []
    pys = []

    def add(kind, blob, expect=None):
        nonlocal n
        rows.append((kind, blob))
        pys.append(expect if expect is not None else verdict(kind, blob))
        n += 1

    data = datasets()
    valid = []
    for name, d in data:
        big = len(d) >= 12000
        if big:
            for level, kind, wb in ((1, "raw", -15), (6, "zlib", 15), (9, "gzip", 31)):
                add(kind, comp(d, level, wb))
        else:
            for level in (0, 1, 4, 6, 9):
                for ki, (kind, wb) in enumerate((("raw", -15), ("zlib", 15), ("gzip", 31))):
                    if level not in (1, 6) and (ki + level + len(d)) % 3 != 0:
                        continue
                    b = comp(d, level, wb)
                    add(kind, b)
                    if len(b) <= 3000:
                        valid.append((kind, b))
        if not big:
            for st in (1, 2, 3, 4):
                b = comp(d, 6, 15, st)
                add("zlib", b)
                if len(b) <= 3000:
                    valid.append(("zlib", b))
            for mem in (1, 5, 9):
                b = comp(d, 6, -15, zlib.Z_DEFAULT_STRATEGY, mem)
                add("raw", b)
            for seed in range(2):
                b = comp_flushed(d, 6, -15, seed)
                add("raw", b)
                if len(b) <= 3000:
                    valid.append(("raw", b))
    # several gzip members
    for i, parts in enumerate([[b"a", b"b"], [text(3000, 20), b"", text(300, 21)], [bytes(70000), rnd(100, 22), b"z" * 5000]]):
        add("gzipm", gzip_members(parts, 6), verdict_gzip_multi(parts))
    # gzip headers with every optional field
    body = comp(text(2000, 30), 6, -15)
    payload = text(2000, 30)
    tail = struct.pack("<II", zlib.crc32(payload) & 0xffffffff, len(payload))
    ok = "ok:%d:%08x" % (len(payload), zlib.crc32(payload) & 0xffffffff)
    for flags in (0, 1, 2, 4, 8, 16, 4 | 8 | 16, 2 | 4 | 8 | 16, 1 | 2 | 8):
        h = gzip_header(flags, name=b"file.txt", comment=b"made by hand", extra=b"AB\x04\x00data")
        add("gzip", h + body + tail, ok)
    add("gzip", gzip_header(32) + body + tail, "err")
    add("gzip", gzip_header(128) + body + tail, "err")
    add("gzip", gzip_header(2)[:-1] + b"\x00" + body + tail, "err")
    add("gzip", struct.pack("<BBBBIBB", 31, 139, 9, 0, 0, 0, 3) + body + tail, "err")
    # hand-made DEFLATE
    add("raw", raw_deflate_stored(b""))
    add("raw", raw_deflate_stored(b"hello"))
    add("raw", raw_deflate_stored(b"", blocks=[b"ab", b"", b"cde", b""]))
    add("raw", raw_deflate_stored(b"x" * 65535))
    add("raw", raw_deflate_stored(b"x" * 100, final=False))
    bad = bytearray(raw_deflate_stored(b"hello"))
    bad[3] ^= 1
    add("raw", bytes(bad))
    add("raw", fixed_block([("lit", 97), ("match", 3, 1)]))
    add("raw", fixed_block([("lit", 97), ("match", 258, 1), ("match", 258, 1), ("match", 5, 1)]))
    add("raw", fixed_block([("lit", 97), ("match", 3, 2)]))
    add("raw", fixed_block([("lit", i % 256) for i in range(40000)] + [("match", 258, 32768), ("match", 10, 32767)]))
    add("raw", fixed_block([("lit", i % 256) for i in range(32768)] + [("match", 258, 32769)]))
    add("raw", fixed_block([("lit", 1), ("lit", 2), ("match", 3, 3)]))
    add("raw", fixed_block([("match", 3, 1)]))
    add("raw", bytes([3]))
    add("raw", bytes([7, 0]))
    add("raw", bytes([0x1f]))
    add("raw", b"")
    # a zlib stream with a bad header or checksum
    z = comp(text(500, 40), 6, 15)
    add("zlib", z[:-1] + bytes([z[-1] ^ 1]))
    add("zlib", bytes([0x78, 0x9d]) + z[2:])
    add("zlib", bytes([0x79, 0x9c]) + z[2:])
    add("zlib", bytes([0x78, 0xbb]) + z[2:])
    add("zlib", b"\x78")
    add("zlib", z + b"x")
    # mutants of valid streams, each with what zlib says
    r = random.Random(99)
    r.shuffle(valid)
    for i, (kind, blob) in enumerate(valid[:300]):
        for m in mutants(kind, blob, 4, 1000 + i):
            add(kind, m)
    # a verdict is firm when zlib and Go say the same; where they differ the
    # line holds both (either|ZLIB|GO) and a reader may say either
    gos = go_verdicts(rows)
    for i, (kind, blob) in enumerate(rows):
        v = pys[i] if pys[i] == gos[i] else "either|%s|%s" % (pys[i], gos[i])
        lines.append("%s %d %s %s" % (kind, i, v, base64.b64encode(blob).decode() if blob else "-"))
    return lines


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--check":
        bad = 0
        for ln in open(sys.argv[2]):
            kind, i, v, h = ln.split()
            blob = b"" if h == "-" else base64.b64decode(h)
            got = verdict(kind, blob)
            ok = got == v.split("|")[1] if v.startswith("either|") else got == v
            if not ok:
                bad += 1
                print("differs", kind, i, v, got)
        print("flate corpus check:", "ok" if not bad else "%d differ" % bad)
        sys.exit(1 if bad else 0)
    lines = build()
    path = "testdata/flate.txt" if len(sys.argv) < 2 else sys.argv[1]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("flate corpus:", len(lines), "streams,", sum(len(x) for x in lines) // 1024, "KiB")


main()
