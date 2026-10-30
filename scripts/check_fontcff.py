#!/usr/bin/env python3
"""P513: checks pasfontcff, the reader of Compact Font Format files paspdf asks
what a glyph is. Not part of make check (it wants the machine's fonts and
docs/ref); run it after a change to src/lib/pasfontcff.paslang.

    python3 scripts/check_fontcff.py BUILD [--fonts DIR] [--fuzz COPIES]

BUILD is a directory with the compiled units. Three checks:

  fonts   the CFF table of every OpenType font under DIR (default
          /usr/share/fonts) is written out as a bare CFF (a .ttf may be an OpenType font too) and read by
          scripts/fontcff_dump.paslang, which prints the number of glyphs,
          whether the font is CID-keyed, the name of each glyph (or the CID and the
          glyph it selects) and the glyph of each code of the font's encoding; this
          file reads the same bytes again, written again in Python from Adobe
          Technical Note 5176, and the lines must be the same;
  built   the same for fonts made here by scripts/gen_pdffont.py's make_cff in
          every form of the charset (formats 0, 1 and 2, ISOAdobe, Expert,
          ExpertSubset) and of the encoding (the operator left out, Expert, formats
          0 and 1, supplements), name-keyed and CID-keyed;
  fuzz    with --fuzz COPIES, scripts/fontcff_fuzz.paslang bends each CFF of the
          first fonts COPIES times and uses every part of the reader on each; it
          must return every time.

Exit status 1 if any check fails."""
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)


def tables():
    import gen_fontnames
    return gen_fontnames.cff_tables()


def reference(d, tabs):
    """what pasfontcff must print for the bytes of a bare CFF file"""
    STR, ENCS, SETS = tabs

    def idx(p):
        cnt = struct.unpack('>H', d[p:p + 2])[0]
        if cnt == 0:
            return [], p + 2
        osz = d[p + 2]
        if not 1 <= osz <= 4:
            raise ValueError('offsize')
        offs = [int.from_bytes(d[p + 3 + i * osz:p + 3 + (i + 1) * osz], 'big') for i in range(cnt + 1)]
        if offs[0] != 1 or any(b < a for a, b in zip(offs, offs[1:])):
            raise ValueError('offsets')
        base = p + 3 + (cnt + 1) * osz - 1
        if base + offs[-1] > len(d):
            raise ValueError('past the end')
        return [(base + offs[i], offs[i + 1] - offs[i]) for i in range(cnt)], base + offs[-1]

    def dictparse(b):
        ops = {}
        st = []
        i = 0
        while i < len(b):
            b0 = b[i]
            if b0 <= 21:
                op = b0
                i += 1
                if b0 == 12:
                    op = 1200 + b[i]
                    i += 1
                ops[op] = st
                st = []
            else:
                if b0 == 28:
                    v = struct.unpack('>h', b[i + 1:i + 3])[0]
                    i += 3
                elif b0 == 29:
                    v = struct.unpack('>i', b[i + 1:i + 5])[0]
                    i += 5
                elif b0 == 30:
                    i += 1
                    while True:
                        x = b[i]
                        i += 1
                        if (x & 15) == 15 or (x >> 4) == 15:
                            break
                    v = 0
                elif 32 <= b0 <= 246:
                    v = b0 - 139
                    i += 1
                elif 247 <= b0 <= 250:
                    v = (b0 - 247) * 256 + b[i + 1] + 108
                    i += 2
                elif 251 <= b0 <= 254:
                    v = -(b0 - 251) * 256 - b[i + 1] - 108
                    i += 2
                else:
                    raise ValueError('reserved byte')
                st.append(v)
        return ops

    try:
        if d[0] != 1 or d[2] < 4 or d[2] >= len(d) or not 1 <= d[3] <= 4:
            return ['invalid']
        names, p = idx(d[2])
        tops, p = idx(p)
        strs, p2 = idx(p)
        try:
            idx(p)
        except Exception:
            strs = []
        ops = dictparse(d[tops[0][0]:tops[0][0] + tops[0][1]])
        cs = ops.get(17, [0])[-1]
        if cs < 1:
            return ['invalid']
        items, _ = idx(cs)
        n = len(items)
        if n < 1:
            return ['invalid']
        iscid = 1230 in ops
        chop = ops.get(15, [0])[-1]
        charset = [0] * n
        if chop <= 2:
            if not iscid:
                tab = SETS[chop] if 0 <= chop <= 2 else []
                for i in range(n):
                    if i < len(tab):
                        charset[i] = tab[i]
            else:
                charset = list(range(n))
        else:
            fmt = d[chop]
            p = chop + 1
            g = 1
            try:
                if fmt == 0:
                    while g < n:
                        charset[g] = struct.unpack('>H', d[p:p + 2])[0]
                        g += 1
                        p += 2
                elif fmt in (1, 2):
                    while g < n:
                        first = struct.unpack('>H', d[p:p + 2])[0]
                        if fmt == 1:
                            left = d[p + 2]
                            p += 3
                        else:
                            left = struct.unpack('>H', d[p + 2:p + 4])[0]
                            p += 4
                        for i in range(left + 1):
                            if g < n:
                                charset[g] = first + i
                                g += 1
            except (struct.error, IndexError):
                pass
        out = ['glyphs %d cid %s' % (n, 'True' if iscid else 'False')]

        def sname(sid):
            if sid < 391:
                return STR[sid]
            k = sid - 391
            if k < len(strs):
                return d[strs[k][0]:strs[k][0] + strs[k][1]].decode('latin-1')
            return ''

        if iscid:
            inv = {}
            for g in range(n - 1, -1, -1):
                inv[charset[g]] = g
            for g in range(n):
                out.append('c %d %d %d' % (g, charset[g], inv.get(charset[g], 0)))
        else:
            for g in range(n):
                out.append('n %d %s' % (g, '.notdef' if g == 0 else sname(charset[g])))
            eop = ops.get(16, [0])[-1]
            enc = [0] * 256

            def gof(sid):
                for g in range(1, n):
                    if charset[g] == sid:
                        return g
                return 0

            try:
                if 0 <= eop <= 1:
                    for c in range(256):
                        s = ENCS[eop][c]
                        if s:
                            enc[c] = gof(s)
                elif eop > 1:
                    fmt = d[eop]
                    p = eop + 1
                    if fmt & 0x7F == 0:
                        k = d[p]
                        p += 1
                        for i in range(k):
                            if i + 1 < n:
                                enc[d[p + i]] = i + 1
                        p += k
                    elif fmt & 0x7F == 1:
                        k = d[p]
                        p += 1
                        g = 1
                        for i in range(k):
                            first, left = d[p], d[p + 1]
                            p += 2
                            for c in range(first, first + left + 1):
                                if c <= 255 and g < n:
                                    enc[c] = g
                                g += 1
                    else:
                        raise IndexError
                    if fmt & 0x80:
                        k = d[p]
                        p += 1
                        for i in range(k):
                            c = d[p]
                            sid = struct.unpack('>H', d[p + 1:p + 3])[0]
                            p += 3
                            g = gof(sid)
                            if g > 0:
                                enc[c] = g
            except (struct.error, IndexError):
                pass
            for c in range(256):
                if enc[c] > 0:
                    out.append('e %d %d' % (c, enc[c]))
        return out
    except Exception:
        return ['invalid']


def built_fonts():
    """the CFF fonts of every form scripts/gen_pdffont.py can make"""
    import gen_pdffont as F
    out = []
    glyphs = [34, 35, 391, 392, 36, 37, 38, 39]
    own = ['alpha', 'uni00E9']
    encs = [None, 1, ('fmt0', [0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47]), ('fmt1', [(0x41, 3), (0x50, 2)]),
            ('fmt0', [0x41, 0x42], [(0x43, 391), (0x44, 392)]), ('fmt1', [(0x61, 6)], [(0x20, 1)])]
    for cs in ('fmt0', 'fmt1', 'fmt2', 0, 1, 2):
        for enc in encs:
            out.append(('charset %s encoding %s' % (cs, enc), F.make_cff(glyphs, own, cs, enc)))
    for cs in ('fmt0', 'fmt1', 'fmt2'):
        out.append(('cid charset %s' % cs, F.make_cff([100, 101, 300, 5, 6], [], cs, None, cid=True)))
    return out


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    build = args.pop(0)
    fonts_dir = '/usr/share/fonts'
    fuzz = 0
    while args:
        a = args.pop(0)
        if a == '--fonts':
            fonts_dir = args.pop(0)
        elif a == '--fuzz':
            fuzz = int(args.pop(0))
        else:
            sys.exit('unknown argument ' + a)
    tabs = tables()
    tmp = tempfile.mkdtemp()
    exes = {}
    for prog in ('fontcff_dump', 'fontcff_fuzz'):
        exe = os.path.join(tmp, prog)
        r = subprocess.run(['paslangc', '-Fu', build, '-o', exe, os.path.join(HERE, prog + '.paslang')], capture_output=True, text=True)
        if r.returncode:
            sys.exit('compiling %s: %s' % (prog, r.stderr))
        exes[prog] = exe
    cffs = []
    for dp, dn, fn in os.walk(fonts_dir):
        for f in sorted(fn):
            if f.lower().endswith(('.otf', '.ttf')):
                d = open(os.path.join(dp, f), 'rb').read()
                if d[:4] != b'OTTO':
                    continue
                for i in range(struct.unpack('>H', d[4:6])[0]):
                    tag, cs, off, ln = struct.unpack('>4sIII', d[12 + 16 * i:28 + 16 * i])
                    if tag == b'CFF ':
                        cffs.append((os.path.join(dp, f), d[off:off + ln]))
    cffs.sort()
    bad = 0
    for what, data in cffs + built_fonts():
        fn = os.path.join(tmp, 'f.cff')
        open(fn, 'wb').write(data)
        got = subprocess.run([exes['fontcff_dump'], fn], capture_output=True, text=True, timeout=120).stdout.split('\n')[:-1]
        want = reference(data, tabs)
        if got != want:
            bad += 1
            print('DIFFERENT', what)
            for a, b in zip(got, want):
                if a != b:
                    print('  pasfontcff:', a, ' reference:', b)
                    break
    print('CFF fonts %d (%d of the machine, %d built): differ %d' % (len(cffs) + len(built_fonts()), len(cffs), len(built_fonts()), bad))
    failed = bad
    if fuzz:
        for i, (what, data) in enumerate((cffs + built_fonts())[:40]):
            fn = os.path.join(tmp, 'g.cff')
            open(fn, 'wb').write(data)
            r = subprocess.run([exes['fontcff_fuzz'], fn, str(100 + i), str(fuzz)], capture_output=True, text=True, timeout=600)
            if r.returncode:
                failed += 1
                print('FUZZ FAILED', what, r.returncode, r.stderr[-200:])
        print('fuzz: 40 fonts, %d copies each' % fuzz)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
