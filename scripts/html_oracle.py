#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""The oracle of testdata/htmltok (P565): Python's html.parser and
html.unescape read the same cases and must give the same tokens, text
and decoded references, where the two agree by design. The html cases:
every token line after the case is compared with the events of
HTMLParser (convert_charrefs on, CR LF and CR made LF first as the
standard's input stream is; a start-and-end tag is a start tag marked /;
a processing instruction is the standard's bogus comment; a declaration
is a doctype or a bogus comment). The text cases: the same reading of
the events as HtmlToText's (blocks as line breaks, a tab between cells,
script, style, head and template dropped, white space collapsed outside
pre). The unesc and esc cases: html.unescape and html.escape. Cases
where Python is known to differ from the standard carry no check: a
reference to a control character or a noncharacter (Python drops it), a text that ends
inside a tag (Python keeps it as text), a plaintext element.

usage: html_oracle.py OUTPUT
"""

import html
import html.parser
import re
import sys

BLOCK = {'div', 'tr', 'li', 'dd', 'dt', 'section', 'article', 'header', 'footer', 'nav', 'aside', 'main', 'form', 'fieldset',
         'address', 'figure', 'figcaption', 'details', 'summary', 'center', 'dir', 'menu', 'tbody', 'thead', 'tfoot', 'caption',
         'legend', 'option', 'body', 'html', 'dl', 'colgroup'}
PARAGRAPH = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'ul', 'ol', 'blockquote', 'pre', 'hr'}
RAW = {'script', 'style', 'xmp', 'iframe', 'noembed', 'noframes'}
RCDATA = {'textarea', 'title'}


def vis(s):
    out = []
    for b in s.encode('utf-8', 'surrogatepass'):
        if b == 10:
            out.append('\\n')
        elif b == 9:
            out.append('\\t')
        elif b == 92:
            out.append('\\\\')
        elif b < 32 or b > 126:
            out.append('\\x%02x' % b)
        else:
            out.append(chr(b))
    return ''.join(out)


def unvis(s):
    out = bytearray()
    i = 0
    while i < len(s):
        c = s[i]
        if c == '\\' and i + 1 < len(s):
            d = s[i + 1]
            if d == 'n':
                out.append(10)
            elif d == 'r':
                out.append(13)
            elif d == 't':
                out.append(9)
            elif d == '\\':
                out.append(92)
            elif d == 'x':
                out.append(int(s[i + 2:i + 4], 16))
                i += 2
            else:
                out.append(ord(d))
            i += 2
        else:
            out += c.encode('utf-8')
            i += 1
    return out.decode('utf-8', 'replace')


def normalize(s):
    return s.replace('\r\n', '\n').replace('\r', '\n')


def python_drops(src):
    """a numeric reference Python's html.unescape handles unlike the standard: a code point it drops (controls,
    noncharacters: html._invalid_codepoints), or &#x; with no digit, which it leaves and Go decodes"""
    if '&#x;' in src or '&#X;' in src:
        return True
    for m in re.finditer(r'&#([xX]([0-9a-fA-F]+)|([0-9]+));?', src):
        v = int(m.group(2), 16) if m.group(2) else int(m.group(3))
        if v in html._invalid_codepoints:
            return True
    return False


class Tokens(html.parser.HTMLParser):
    """the events as testdata/htmltok prints its tokens"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines = []
        self.text = ''

    def flush(self):
        if self.text != '':
            self.lines.append('  text [%s]' % vis(self.text.replace('\x00', '')))
            self.text = ''

    def handle_data(self, data):
        self.text += data

    def tag(self, name, attrs, closing):
        self.flush()
        seen = set()
        parts = ['  start ' + name]
        for k, v in attrs:
            if k in seen:
                continue
            seen.add(k)
            parts.append('%s="%s"' % (k, vis(v if v is not None else '')))
        if closing:
            parts.append('/')
        self.lines.append(' '.join(parts))

    def handle_starttag(self, tag, attrs):
        self.tag(tag, attrs, False)

    def handle_startendtag(self, tag, attrs):
        self.tag(tag, attrs, True)

    def handle_endtag(self, tag):
        self.flush()
        self.lines.append('  end ' + tag)

    def handle_comment(self, data):
        self.flush()
        self.lines.append('  comment [%s]' % vis(data))

    def handle_decl(self, decl):
        self.flush()
        words = decl.split(None, 2)
        if words and words[0].lower() == 'doctype':
            name = words[1].lower() if len(words) > 1 else ''
            rest = words[2].strip() if len(words) > 2 else ''
            self.lines.append('  doctype %s [%s]' % (name, vis(rest)))
        else:
            self.lines.append('  comment [%s]' % vis(decl))

    def unknown_decl(self, data):
        self.flush()
        # <![CDATA[x]]> in HTML content is a bogus comment whose data runs from after <! to the first >
        self.lines.append('  comment [[%s]]]' % vis(data))

    def handle_pi(self, data):
        self.flush()
        self.lines.append('  comment [%s]' % vis('?' + data))

    def done(self):
        self.close()
        self.flush()
        return self.lines


class Text(html.parser.HTMLParser):
    """HtmlToText's reading of the events"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.lf = 0
        self.pending = False
        self.pre = 0
        self.skip = 0
        self.in_head = False
        self.drop_lf = False

    def brk(self, two):
        if not self.out:
            return
        if self.lf == 0:
            self.out.append('\n')
            self.lf = 1
        if two and self.lf == 1:
            self.out.append('\n')
            self.lf = 2
        self.pending = False

    def handle_data(self, d):
        if self.in_head or self.skip:
            return
        if self.drop_lf:
            self.drop_lf = False
            if d.startswith('\n'):
                d = d[1:]
        for ch in d:
            if ch == '\xa0':
                ch = ' '
                if self.pre:
                    self.out.append(' ')
                    continue
            if self.pre:
                self.out.append(ch)
                self.lf = 1 if ch == '\n' else 0
            elif ch in ' \t\n\x0c':
                self.pending = True
            elif ch == '\x00':
                continue
            else:
                if self.pending and self.lf == 0 and self.out:
                    self.out.append(' ')
                self.pending = False
                self.out.append(ch)
                self.lf = 0

    def handle_starttag(self, d, attrs):
        if d == 'head':
            self.in_head = True
        elif d == 'body':
            self.in_head = False
        elif d == 'template':
            self.skip += 1
        elif d == 'br':
            if self.out:
                self.out.append('\n')
                self.lf += 1
                self.pending = False
        elif d in ('td', 'th'):
            if self.lf == 0 and self.out:
                self.out.append('\t')
            self.pending = False
        elif d in PARAGRAPH:
            self.brk(True)
            if d == 'pre':
                self.pre += 1
                self.drop_lf = True
        elif d in BLOCK:
            self.brk(False)
        elif d == 'textarea':
            self.drop_lf = True

    def handle_startendtag(self, d, attrs):
        self.handle_starttag(d, attrs)

    def handle_endtag(self, d):
        if d == 'head':
            self.in_head = False
        elif d == 'template':
            if self.skip:
                self.skip -= 1
        elif d in PARAGRAPH:
            if d == 'pre' and self.pre:
                self.pre -= 1
            self.brk(True)
        elif d in BLOCK:
            self.brk(False)

    def done(self):
        self.close()
        return ''.join(self.out).rstrip('\n \t')


def main():
    lines = open(sys.argv[1], errors='replace').read().split('\n')
    bad = n = skipped = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if line.startswith('html '):
            src = unvis(line[5:])
            got = []
            while i < len(lines) and lines[i].startswith('  '):
                if not (lines[i].startswith('  spans') or lines[i].startswith('  has ')):
                    got.append(lines[i])
                i += 1
            if re.search(r'<[A-Za-z][^>]*$', normalize(src)) or '<plaintext' in src.lower() or '\x00' in src or python_drops(src):
                skipped += 1
                continue
            n += 1
            p = Tokens()
            p.feed(normalize(src))
            want = p.done()
            if want != got:
                bad += 1
                print('html_oracle: %s\n  python: %s\n  paslang: %s' % (line, want, got))
        elif line.startswith('text '):
            m = re.match(r'^text (.*) -> (.*)$', line)
            if not m:
                continue
            n += 1
            p = Text()
            p.feed(normalize(unvis(m.group(1))))
            want = vis(p.done())
            if want != m.group(2):
                bad += 1
                print('html_oracle: %s\n  python: %s' % (line, want))
        elif line.startswith('unesc '):
            m = re.match(r'^unesc (.*) -> (.*)$', line)
            if not m:
                continue
            src = unvis(m.group(1))
            if python_drops(src):
                skipped += 1
                continue
            n += 1
            want = vis(html.unescape(src))
            if want != m.group(2):
                bad += 1
                print('html_oracle: %s\n  python: %s' % (line, want))
        elif line.startswith('esc '):
            m = re.match(r'^esc (.*) -> (.*)$', line)
            if not m:
                continue
            n += 1
            want = vis(html.escape(unvis(m.group(1)), quote=True).replace('&quot;', '&#34;').replace('&#x27;', '&#39;'))
            if want != m.group(2):
                bad += 1
                print('html_oracle: %s\n  python: %s' % (line, want))
    if n < 60:
        print('html_oracle: only %d cases checked' % n)
        sys.exit(1)
    if bad:
        sys.exit(1)
    print('html_oracle: %d cases agree with html.parser and html.unescape, %d left to the standard alone' % (n, skipped))


if __name__ == '__main__':
    main()
