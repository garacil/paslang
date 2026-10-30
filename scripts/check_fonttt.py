#!/usr/bin/env python3
"""P512: checks pasfonttt, the reader of TrueType and OpenType tables paspdf
asks what a glyph is, on the fonts of this machine. Not part of make check
(the fonts are the machine's); run it after a change to src/lib/pasfonttt.paslang.

    python3 scripts/check_fonttt.py BUILD [--fonts DIR] [--fuzz COPIES] [--limit N]

BUILD is a directory with the compiled units (the build directory of a tree
that has made them). Three checks, each on every .ttf and .otf under DIR
(default /usr/share/fonts, N of them if --limit):

  reader     scripts/fonttt_dump.paslang prints the number of glyphs, the cmap
             subtables, the Unicode of each glyph (the inverse of the best
             Unicode subtable) and the post names; this file reads the same
             tables again, written again in Python, and the lines must be the
             same;
  coverage   scripts/fonttt_cov.paslang prints the codes the best Unicode
             subtable maps; fontconfig (FreeType) reports a charset for the
             file with fc-query, and the two must be the same but for the
             controls below U+0020, which fontconfig leaves out;
  fuzz       with --fuzz COPIES, scripts/fonttt_fuzz.paslang bends each of the
             first 40 fonts under 400 KB COPIES times and uses every part of
             the reader on each; it must return every time.

Exit status 1 if any check fails."""
import os
import re
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def mac_names():
    """the 258 names of the Macintosh ordering, from the generated unit"""
    s = open(os.path.join(ROOT, 'src', 'lib', 'pasfontnames.paslang'), encoding='utf-8').read()
    body = s[s.index('MacNames ='):s.index('MacStart')]
    names = ''.join(re.findall(r"'([^']*)'", body)).split('|')[:-1]
    assert len(names) == 258
    return names


def reference(path, mac):
    """what pasfonttt must print for the file, written again from the specifications"""
    d = open(path, 'rb').read()
    if d[:4] not in (b'\x00\x01\x00\x00', b'true', b'OTTO'):
        return ['invalid']
    n = struct.unpack('>H', d[4:6])[0]
    t = {}
    for i in range(min(n, 256)):
        if 12 + 16 * (i + 1) > len(d):
            break
        tag, cs, off, ln = struct.unpack('>4sIII', d[12 + 16 * i:28 + 16 * i])
        if off >= len(d):
            continue
        t[tag.decode('latin-1')] = (off, min(ln, len(d) - off))
    if n < 1 or n > 256 or 'maxp' not in t or t['maxp'][1] < 6:
        return ['invalid']
    ng = struct.unpack('>H', d[t['maxp'][0] + 4:t['maxp'][0] + 6])[0]
    if ng < 1:
        return ['invalid']
    out = ['glyphs %d' % ng]
    subs = []
    if 'cmap' in t and t['cmap'][1] >= 4:
        off, ln = t['cmap']
        nc = min(struct.unpack('>H', d[off + 2:off + 4])[0], 64)
        for i in range(nc):
            if 8 * (i + 1) + 4 > ln:
                break
            p, e, o = struct.unpack('>HHI', d[off + 4 + 8 * i:off + 12 + 8 * i])
            if o + 4 > ln:
                continue
            subs.append((p, e, off + o))
            out.append('cmap %d %d' % (p, e))

    def table(base):
        fmt = struct.unpack('>H', d[base:base + 2])[0]
        m = {}
        if fmt == 0:
            for c in range(256):
                if d[base + 6 + c]:
                    m[c] = d[base + 6 + c]
        elif fmt == 4:
            segx2 = struct.unpack('>H', d[base + 6:base + 8])[0]
            if segx2 < 2 or segx2 & 1:
                return m
            sc = segx2 // 2
            ends = struct.unpack('>%dH' % sc, d[base + 14:base + 14 + segx2])
            sp = base + 14 + segx2 + 2
            starts = struct.unpack('>%dH' % sc, d[sp:sp + segx2])
            dp = sp + segx2
            deltas = struct.unpack('>%dh' % sc, d[dp:dp + segx2])
            rp = dp + segx2
            ro = struct.unpack('>%dH' % sc, d[rp:rp + segx2])
            for s in range(sc):
                for c in range(starts[s], ends[s] + 1):
                    if c == 0xFFFF:
                        continue
                    if ro[s] == 0:
                        g = (c + deltas[s]) & 0xFFFF
                    else:
                        a = rp + 2 * s + ro[s] + 2 * (c - starts[s])
                        g = struct.unpack('>H', d[a:a + 2])[0] if a + 2 <= len(d) else 0
                        if g:
                            g = (g + deltas[s]) & 0xFFFF
                    if g:
                        m[c] = g
        elif fmt == 6:
            first, cnt = struct.unpack('>HH', d[base + 6:base + 10])
            for k in range(cnt):
                g = struct.unpack('>H', d[base + 10 + 2 * k:base + 12 + 2 * k])[0]
                if g:
                    m[first + k] = g
        elif fmt == 12:
            ngr = struct.unpack('>I', d[base + 12:base + 16])[0]
            ngr = min(ngr, (len(d) - base - 16) // 12)
            for k in range(ngr):
                s, e, g = struct.unpack('>III', d[base + 16 + 12 * k:base + 28 + 12 * k])
                for c in range(s, e + 1):
                    m[c] = g + c - s
        return m

    rank = {(3, 10): 0, (0, 4): 1, (0, 6): 2, (3, 1): 3, (0, 3): 4}

    def rk(pe):
        if pe in rank:
            return rank[pe]
        return 5 if pe[0] == 0 and pe[1] <= 2 else -1

    inv = {}
    for r in range(6):
        for p, e, base in subs:
            if rk((p, e)) == r:
                best = {}
                for c, g in table(base).items():
                    if 0 < g < ng and (g not in best or c < best[g]):
                        best[g] = c
                for g, c in best.items():
                    inv.setdefault(g, c)
    out += ['u %d %d' % (g, inv[g]) for g in sorted(inv)]
    if 'post' in t and t['post'][1] >= 32:
        po, pl = t['post']
        ver = struct.unpack('>I', d[po:po + 4])[0]
        if ver == 0x10000:
            out += ['n %d %s' % (g, mac[g]) for g in range(min(ng, 258))]
        elif ver == 0x20000:
            n2 = struct.unpack('>H', d[po + 32:po + 34])[0]
            if 34 + 2 * n2 <= pl:
                idx = struct.unpack('>%dH' % n2, d[po + 34:po + 34 + 2 * n2])
                p = po + 34 + 2 * n2
                e = po + pl
                strs = []
                while p < e and len(strs) < 65536:
                    strs.append((p, d[p]))
                    p += 1 + d[p]
                for g in range(min(ng, n2)):
                    i = idx[g]
                    if i < 258:
                        out.append('n %d %s' % (g, mac[i]))
                    elif i - 258 < len(strs):
                        p0, l = strs[i - 258]
                        if p0 + l <= po + pl - 1:
                            out.append('n %d %s' % (g, d[p0 + 1:p0 + 1 + l].decode('latin-1')))
    return out


def ranges(txt):
    s = set()
    for tok in txt.split():
        if '-' in tok:
            a, b = tok.split('-')
            s.update(range(int(a, 16), int(b, 16) + 1))
        else:
            s.add(int(tok, 16))
    return s


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    build = args.pop(0)
    fonts_dir = '/usr/share/fonts'
    fuzz = 0
    limit = 0
    while args:
        a = args.pop(0)
        if a == '--fonts':
            fonts_dir = args.pop(0)
        elif a == '--fuzz':
            fuzz = int(args.pop(0))
        elif a == '--limit':
            limit = int(args.pop(0))
        else:
            sys.exit('unknown argument ' + a)
    files = []
    for dp, dn, fn in os.walk(fonts_dir):
        for f in sorted(fn):
            if f.lower().endswith(('.ttf', '.otf')):
                files.append(os.path.join(dp, f))
    files.sort()
    if limit:
        files = files[:limit]
    if not files:
        print('check_fonttt.py: no fonts under', fonts_dir)
        return 0
    tmp = tempfile.mkdtemp()
    exes = {}
    for prog in ('fonttt_dump', 'fonttt_cov', 'fonttt_fuzz'):
        exe = os.path.join(tmp, prog)
        r = subprocess.run(['paslangc', '-Fu', build, '-o', exe, os.path.join(HERE, prog + '.paslang')], capture_output=True, text=True)
        if r.returncode:
            sys.exit('compiling %s: %s' % (prog, r.stderr))
        exes[prog] = exe
    mac = mac_names()
    bad = 0
    covbad = 0
    fc = subprocess.run(['fc-query', '--version'], capture_output=True).returncode == 0 if shutil_which('fc-query') else False
    for f in files:
        got = subprocess.run([exes['fonttt_dump'], f], capture_output=True, text=True, timeout=120).stdout.split('\n')[:-1]
        want = reference(f, mac)
        if got != want:
            bad += 1
            print('DIFFERENT', f)
            for a, b in zip(got, want):
                if a != b:
                    print('  pasfonttt:', a, ' reference:', b)
                    break
        if fc:
            cov = subprocess.run([exes['fonttt_cov'], f], capture_output=True, text=True, timeout=300).stdout.strip()
            q = subprocess.run(['fc-query', '--format', '%{charset}\n', f], capture_output=True, text=True).stdout.strip()
            if cov in ('invalid', 'none'):
                continue
            a = {c for c in ranges(cov) if c >= 0x20}
            b = {c for c in ranges(q) if c >= 0x20}
            if a != b:
                covbad += 1
                print('COVERAGE', f, 'pasfonttt only', sorted(a - b)[:5], 'fontconfig only', sorted(b - a)[:5])
    print('fonts %d: reader differs %d%s' % (len(files), bad, (', coverage differs %d' % covbad) if fc else ' (no fc-query: coverage not checked)'))
    failed = bad + covbad
    if fuzz:
        small = [f for f in files if os.path.getsize(f) < 400 * 1024][:40]
        for i, f in enumerate(small):
            r = subprocess.run([exes['fonttt_fuzz'], f, str(100 + i), str(fuzz)], capture_output=True, text=True, timeout=600)
            if r.returncode:
                failed += 1
                print('FUZZ FAILED', f, r.returncode, r.stderr[-200:])
        print('fuzz: %d fonts, %d copies each' % (len(small), fuzz))
    return 1 if failed else 0


def shutil_which(cmd):
    for d in os.environ.get('PATH', '').split(os.pathsep):
        if os.access(os.path.join(d, cmd), os.X_OK):
            return True
    return False


if __name__ == '__main__':
    sys.exit(main())
