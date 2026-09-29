#!/usr/bin/env python3
"""Writes docs/manual/index.html, the paslang book in one page, from the
canonical Markdown: the programmer's manual (docs/MANUAL.md, every
program of which make check runs) and the chapters a programmer needs
to get the most out of the language (TYPES.md, QUAD.md, GC.md,
KERNELS.md, VISION.md). Nothing is written by hand here: change the
Markdown and run this again (make manual).

The Markdown the documents use: # ## ### headings, paragraphs, fenced
code (```pascal, ```bash, ```), tables, - and 1. lists (nested by two
spaces), `code`, **bold**, *emphasis* and [text](url). Anything else is
kept as text.
"""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / 'docs'
OUT = DOCS / 'manual' / 'index.html'

PARTS = [
    ('manual', 'MANUAL.md', 'The programmer\'s manual'),
    ('types', 'TYPES.md', 'Types and the modern ABI'),
    ('quad', 'QUAD.md', 'Quad: IEEE binary128'),
    ('gc', 'GC.md', 'The heap and the collector'),
    ('kernels', 'KERNELS.md', 'Kernels and -cpu'),
    ('vision', 'VISION.md', 'Vision'),
]

KEYWORDS = set('''program unit uses interface implementation initialization finalization
begin end var const type procedure function constructor destructor class object record
array of set string integer boolean real char pointer nil not and or xor div mod shl shr
sar rol ror nand nor xnor andnot in is as if then else case for to downto do while repeat
until with try except finally raise on inherited property published private protected
public strict operator inline cdecl forward overload override abstract virtual reintroduce
default out packed goto label exit break continue generic specialize pas chan select send
recv close makechan map tree heap store lock once mutex rwmutex waitgroup cond asm safe
new writeln write readln sleep halt true false result self'''.split())
TYPES = set('''byte word uint32 int32 int8 int16 int64 uint64 uint16 uint8 shortint smallint
longint longword dword cardinal qword sizeint nativeint ptrint rune ansichar double single
quad v128 v256 pbyte pword pdword pinteger pint64 psingle pdouble pquad pchar pboolean
ppointer pint8 pint16 pint32 puint8 puint16 puint32 pshortint psmallint plongword
tpasmutex tpasrwmutex tpaswaitgroup tpascond tpasonce'''.split())


def esc(s):
    return html.escape(s, quote=False)


def highlight_pascal(code):
    """A small tokenizer: comments, directives, strings, numbers, words."""
    out = []
    i = 0
    n = len(code)
    while i < n:
        c = code[i]
        if c == '{':
            j = code.find('}', i)
            j = n if j < 0 else j + 1
            cls = 'dir' if code.startswith('{$', i) else 'cmt'
            out.append('<span class="%s">%s</span>' % (cls, esc(code[i:j])))
            i = j
        elif code.startswith('(*', i):
            j = code.find('*)', i)
            j = n if j < 0 else j + 2
            out.append('<span class="cmt">%s</span>' % esc(code[i:j]))
            i = j
        elif code.startswith('//', i):
            j = code.find('\n', i)
            j = n if j < 0 else j
            out.append('<span class="cmt">%s</span>' % esc(code[i:j]))
            i = j
        elif c == "'":
            j = i + 1
            while j < n:
                if code[j] == "'":
                    if j + 1 < n and code[j + 1] == "'":
                        j += 2
                        continue
                    break
                if code[j] == '\n':
                    break
                j += 1
            j = min(j + 1, n)
            out.append('<span class="str">%s</span>' % esc(code[i:j]))
            i = j
        elif c == '#' and i + 1 < n and code[i + 1].isdigit():
            j = i + 1
            while j < n and code[j].isdigit():
                j += 1
            out.append('<span class="str">%s</span>' % esc(code[i:j]))
            i = j
        elif c == '$' and i + 1 < n and code[i + 1] in '0123456789abcdefABCDEF':
            j = i + 1
            while j < n and code[j] in '0123456789abcdefABCDEF':
                j += 1
            out.append('<span class="num">%s</span>' % esc(code[i:j]))
            i = j
        elif c.isdigit():
            j = i
            while j < n and (code[j].isdigit() or code[j] in '.eE'):
                if code[j] == '.' and j + 1 < n and code[j + 1] == '.':
                    break
                j += 1
            out.append('<span class="num">%s</span>' % esc(code[i:j]))
            i = j
        elif c.isalpha() or c == '_':
            j = i
            while j < n and (code[j].isalnum() or code[j] == '_'):
                j += 1
            w = code[i:j]
            lw = w.lower()
            if lw in KEYWORDS:
                out.append('<span class="kw">%s</span>' % esc(w))
            elif lw in TYPES:
                out.append('<span class="typ">%s</span>' % esc(w))
            else:
                out.append(esc(w))
            i = j
        else:
            out.append(esc(c))
            i += 1
    return ''.join(out)


def inline(text):
    """Inline Markdown to HTML: code spans are set aside first, so bold,
    emphasis and links wrap around them; the rest is escaped."""
    codes = []

    def keep(m):
        codes.append('<code>%s</code>' % esc(m.group(1)))
        return '\x00%d\x00' % (len(codes) - 1)
    s = re.sub(r'`([^`]+)`', keep, text)
    s = esc(s)
    s = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', lambda m: '<a href="%s">%s</a>' % (link(m.group(2)), m.group(1)), s)
    s = re.sub(r'\*\*([^*]+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<![\w*])\*([^*\s][^*]*?)\*(?![\w*])', r'<em>\1</em>', s)
    return re.sub(r'\x00(\d+)\x00', lambda m: codes[int(m.group(1))], s)


def link(url):
    """A link to another document of the book goes to its part."""
    for part, name, _ in PARTS:
        if url == name or url.endswith('/' + name):
            return '#' + part
    if url.endswith('.md'):
        return 'https://github.com/' if False else url
    return url


def slug(s, used):
    base = re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-') or 'section'
    x = base
    k = 2
    while x in used:
        x = '%s-%d' % (base, k)
        k += 1
    used.add(x)
    return x


def render(md, part, used, toc):
    """Markdown to HTML; fills toc with (level, id, title)."""
    lines = md.split('\n')
    out = []
    i = 0
    n = len(lines)
    first = True

    def flush_para(buf):
        if buf:
            out.append('<p>%s</p>' % inline(' '.join(buf)))
            buf.clear()

    para = []
    while i < n:
        line = lines[i]
        s = line.rstrip()
        if s.startswith('```'):
            flush_para(para)
            lang = s[3:].strip()
            j = i + 1
            code = []
            while j < n and not lines[j].startswith('```'):
                code.append(lines[j])
                j += 1
            body = '\n'.join(code)
            if lang == 'pascal':
                out.append('<pre class="code pascal"><code>%s</code></pre>' % highlight_pascal(body))
            elif lang:
                out.append('<pre class="code %s"><code>%s</code></pre>' % (esc(lang), esc(body)))
            else:
                out.append('<pre class="out"><code>%s</code></pre>' % esc(body))
            i = j + 1
            continue
        m = re.match(r'^(#{1,3})\s+(.*)$', s)
        if m:
            flush_para(para)
            level = len(m.group(1))
            title = m.group(2).strip()
            if level == 1:
                if first:
                    first = False
                    out.append('<h1 id="%s">%s</h1>' % (part, inline(title)))
                else:
                    hid = slug(title, used)
                    out.append('<h2 id="%s">%s</h2>' % (hid, inline(title)))
                    toc.append((2, hid, title))
                i += 1
                continue
            hid = slug(title, used)
            out.append('<h%d id="%s">%s</h%d>' % (level, hid, inline(title), level))
            toc.append((level, hid, title))
            i += 1
            continue
        if s.startswith('|'):
            flush_para(para)
            rows = []
            while i < n and lines[i].startswith('|'):
                rows.append(lines[i])
                i += 1
            cells = [[c.strip().replace('\x01', '|') for c in r.replace('\\|', '\x01').strip().strip('|').split('|')] for r in rows]
            if len(cells) >= 2 and all(re.match(r'^:?-+:?$', c) for c in cells[1] if c):
                head, body = cells[0], cells[2:]
            else:
                head, body = None, cells
            out.append('<div class="tbl"><table>')
            if head:
                out.append('<thead><tr>%s</tr></thead>' % ''.join('<th>%s</th>' % inline(c) for c in head))
            out.append('<tbody>')
            for r in body:
                out.append('<tr>%s</tr>' % ''.join('<td>%s</td>' % inline(c) for c in r))
            out.append('</tbody></table></div>')
            continue
        m = re.match(r'^(\s*)([-*]|\d+\.)\s+(.*)$', line)
        if m and not line.startswith('    '):
            flush_para(para)
            # a list: items at the same indentation, continuation lines indented past the marker
            stack = []  # (indent, tag)
            item = None  # the words of the item being read, rendered when it ends

            def close_item():
                if item is not None:
                    out.append('<li>%s</li>' % inline(' '.join(item)))
            while i < n:
                l2 = lines[i]
                m2 = re.match(r'^(\s*)([-*]|\d+\.)\s+(.*)$', l2)
                if not m2:
                    if l2.strip() == '':
                        # a blank line ends the list unless the next line is an item or a continuation
                        if i + 1 < n and (re.match(r'^(\s*)([-*]|\d+\.)\s+', lines[i + 1]) or (lines[i + 1].startswith('  ') and stack)):
                            i += 1
                            continue
                        break
                    if l2.startswith(' ') and stack:
                        item.append(l2.strip())
                        i += 1
                        continue
                    break
                close_item()
                indent = len(m2.group(1))
                tag = 'ol' if m2.group(2)[0].isdigit() else 'ul'
                while stack and stack[-1][0] > indent:
                    out.append('</%s>' % stack.pop()[1])
                if not stack or stack[-1][0] < indent:
                    stack.append((indent, tag))
                    out.append('<%s>' % tag)
                item = [m2.group(3)]
                i += 1
            close_item()
            while stack:
                out.append('</%s>' % stack.pop()[1])
            continue
        if s == '':
            flush_para(para)
            i += 1
            continue
        para.append(s.strip())
        i += 1
    flush_para(para)
    return '\n'.join(out)


CSS = r'''
:root { color-scheme: light; --bg: #fbfaf7; --fg: #1c1b19; --mute: #6b675f; --line: #e2ded6;
  --side: #f2efe8; --code: #f4f1ea; --out: #eef2ee; --acc: #8a3b12; --link: #0b5aa8;
  --kw: #7a1f6b; --str: #0b6e3f; --cmt: #6b675f; --num: #8a3b12; --typ: #0b4f8a; --dir: #6b675f; --hit: #fff1a8; }
:root:not([data-theme="light"]) { }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { color-scheme: dark;
  --bg: #16171a; --fg: #e8e6e1; --mute: #a19d95; --line: #2c2e33; --side: #1c1e22; --code: #202227;
  --out: #1d2320; --acc: #e39a6b; --link: #7fb3ea; --kw: #d99ad0; --str: #8fd3a8; --cmt: #a19d95;
  --num: #e39a6b; --typ: #8ec2f2; --dir: #a19d95; --hit: #5a4d10; } }
:root[data-theme="dark"] { color-scheme: dark;
  --bg: #16171a; --fg: #e8e6e1; --mute: #a19d95; --line: #2c2e33; --side: #1c1e22; --code: #202227;
  --out: #1d2320; --acc: #e39a6b; --link: #7fb3ea; --kw: #d99ad0; --str: #8fd3a8; --cmt: #a19d95;
  --num: #e39a6b; --typ: #8ec2f2; --dir: #a19d95; --hit: #5a4d10; }
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.6 -apple-system, "Segoe UI", Roboto, "Noto Sans", Ubuntu, sans-serif; }
a { color: var(--link); text-decoration: none; } a:hover { text-decoration: underline; }
.wrap { display: flex; min-height: 100vh; }
nav.side { width: 300px; flex: none; position: sticky; top: 0; height: 100vh; overflow-y: auto;
  background: var(--side); border-right: 1px solid var(--line); padding: 16px 12px 40px; }
nav.side h2 { font-size: 13px; letter-spacing: .08em; text-transform: uppercase; color: var(--mute); margin: 18px 6px 6px; }
nav.side .part { font-weight: 600; margin: 10px 6px 4px; font-size: 15px; }
nav.side ul { list-style: none; margin: 0; padding: 0; }
nav.side li a { display: block; padding: 3px 8px; border-radius: 6px; font-size: 14px; color: var(--fg); }
nav.side li.l3 a { padding-left: 22px; font-size: 13px; color: var(--mute); }
nav.side li a:hover, nav.side li a.on { background: var(--code); text-decoration: none; }
nav.side input { width: 100%; padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px;
  background: var(--bg); color: var(--fg); font-size: 14px; }
.topbar { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.topbar button { border: 1px solid var(--line); background: var(--bg); color: var(--fg); border-radius: 8px;
  padding: 6px 10px; cursor: pointer; font-size: 13px; }
main { flex: 1; min-width: 0; padding: 32px 40px 80px; }
main > section { max-width: 76ch; margin: 0 auto 64px; }
h1 { font-size: 34px; line-height: 1.2; margin: 0 0 12px; letter-spacing: -.01em; }
h2 { font-size: 26px; margin: 48px 0 12px; padding-top: 16px; border-top: 1px solid var(--line); }
h3 { font-size: 19px; margin: 28px 0 8px; }
p { margin: 0 0 14px; }
code { font: 14px/1.5 ui-monospace, "SFMono-Regular", Menlo, Consolas, "Liberation Mono", monospace;
  background: var(--code); padding: 1px 5px; border-radius: 4px; }
pre { margin: 0 0 16px; padding: 12px 14px; border-radius: 8px; overflow-x: auto; background: var(--code);
  border: 1px solid var(--line); }
pre code { background: none; padding: 0; font-size: 13.5px; }
pre.out { background: var(--out); }
pre.out::before { content: "prints"; display: block; font: 11px/1 sans-serif; letter-spacing: .1em;
  text-transform: uppercase; color: var(--mute); margin-bottom: 8px; }
.kw { color: var(--kw); font-weight: 600; } .str { color: var(--str); } .cmt { color: var(--cmt); font-style: italic; }
.num { color: var(--num); } .typ { color: var(--typ); } .dir { color: var(--dir); }
.tbl { overflow-x: auto; margin: 0 0 16px; }
table { border-collapse: collapse; width: 100%; font-size: 14.5px; }
th, td { text-align: left; vertical-align: top; padding: 6px 10px; border-bottom: 1px solid var(--line); }
th { color: var(--mute); font-weight: 600; }
ul, ol { margin: 0 0 14px; padding-left: 26px; } li { margin: 3px 0; }
strong { font-weight: 650; } em { font-style: italic; }
.partbanner { color: var(--mute); font-size: 13px; letter-spacing: .1em; text-transform: uppercase; margin: 0 0 4px; }
.hit { background: var(--hit); }
.search-results { margin: 8px 6px; font-size: 13px; color: var(--mute); }
.search-results a { display: block; color: var(--fg); padding: 3px 4px; }
.search-results small { color: var(--mute); display: block; }
.menu { display: none; }
@media (max-width: 900px) {
  .wrap { display: block; }
  nav.side { position: relative; height: auto; width: auto; border-right: 0; border-bottom: 1px solid var(--line); }
  nav.side ul.toc { display: none; } nav.side.open ul.toc { display: block; }
  .menu { display: inline-block; }
  main { padding: 20px 16px 60px; }
  h1 { font-size: 28px; } h2 { font-size: 22px; }
}
@media print { nav.side { display: none; } main { padding: 0; } main > section { max-width: none; } pre { white-space: pre-wrap; } }
'''

JS = r'''
(function () {
  var root = document.documentElement;
  var stored = null;
  try { stored = localStorage.getItem('paslang-theme'); } catch (e) {}
  if (stored === 'dark' || stored === 'light') root.setAttribute('data-theme', stored);
  var btn = document.getElementById('theme');
  btn.addEventListener('click', function () {
    var dark = root.getAttribute('data-theme') === 'dark' ||
      (!root.getAttribute('data-theme') && window.matchMedia('(prefers-color-scheme: dark)').matches);
    var next = dark ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('paslang-theme', next); } catch (e) {}
  });
  document.getElementById('menu').addEventListener('click', function () {
    document.querySelector('nav.side').classList.toggle('open');
  });
  var links = Array.prototype.slice.call(document.querySelectorAll('nav.side ul.toc a'));
  var heads = links.map(function (a) { return document.getElementById(a.getAttribute('href').slice(1)); });
  function mark() {
    var y = window.scrollY + 80, on = 0;
    for (var i = 0; i < heads.length; i++) if (heads[i] && heads[i].offsetTop <= y) on = i;
    links.forEach(function (a, i) { a.classList.toggle('on', i === on); });
  }
  window.addEventListener('scroll', mark); mark();
  var box = document.getElementById('q'), res = document.getElementById('results');
  var secs = Array.prototype.slice.call(document.querySelectorAll('main h2, main h3'));
  function textOf(h) {
    var t = '', e = h.nextElementSibling;
    while (e && !/^H[123]$/.test(e.tagName)) { t += ' ' + e.textContent; e = e.nextElementSibling; }
    return t;
  }
  var index = secs.map(function (h) { return { h: h, title: h.textContent, text: (h.textContent + textOf(h)).toLowerCase() }; });
  box.addEventListener('input', function () {
    var q = box.value.trim().toLowerCase();
    res.innerHTML = '';
    if (q.length < 2) return;
    var n = 0;
    index.forEach(function (it) {
      var k = it.text.indexOf(q);
      if (k < 0 || n >= 40) return;
      n++;
      var a = document.createElement('a');
      a.href = '#' + it.h.id;
      a.textContent = it.title;
      var s = document.createElement('small');
      var from = Math.max(0, k - 40);
      s.textContent = '…' + it.text.slice(from, k + 60).replace(/\s+/g, ' ') + '…';
      a.appendChild(s);
      res.appendChild(a);
    });
    if (!n) res.textContent = 'nothing matches';
  });
})();
'''


def main():
    used = set()
    sections = []
    nav = []
    for part, name, label in PARTS:
        md = (DOCS / name).read_text(encoding='utf-8')
        toc = []
        body = render(md, part, used, toc)
        sections.append('<section id="s-%s"><div class="partbanner">%s</div>%s</section>' % (part, esc(label), body))
        items = ['<li class="l%d"><a href="#%s">%s</a></li>' % (lvl, hid, inline(title)) for lvl, hid, title in toc]
        nav.append('<div class="part"><a href="#%s">%s</a></div>%s' % (part, esc(label), ''.join(items)))
    page = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>paslang: the book</title>
<style>%s</style>
</head>
<body>
<div class="wrap">
<nav class="side">
  <div class="topbar">
    <button id="menu" class="menu" type="button">Contents</button>
    <button id="theme" type="button">Light / dark</button>
  </div>
  <input id="q" type="search" placeholder="Search the book" autocomplete="off">
  <div id="results" class="search-results"></div>
  <h2>Contents</h2>
  <ul class="toc">%s</ul>
</nav>
<main>
%s
</main>
</div>
<script>%s</script>
</body>
</html>
''' % (CSS, ''.join(nav), '\n'.join(sections), JS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding='utf-8')
    print('wrote', OUT, len(page), 'bytes,', sum(1 for _ in re.finditer(r'<h[23] ', page)), 'sections')


if __name__ == '__main__':
    sys.exit(main())
