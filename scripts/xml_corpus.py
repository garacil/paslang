#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""The oracle of testdata/xmlcorpus (P426): expat's own reading of a
corpus of XML documents, as the lines testdata/xmlcorpus.paslang prints.

The corpus is documents written for each production of XML 1.0 (Fifth
Edition) and Namespaces in XML 1.0 (Third Edition), and the same documents
with bytes changed, inserted and removed (a fixed seed). Every document is
read twice, with namespaces and without; expat, through Python's pyexpat,
says whether it is well-formed and gives the start tags (the attributes in
order of name), the text (adjacent pieces joined), the comments and the
processing instructions, which are written as hex and hashed (FNV-1a 64).
What expat and a reader that does not read external entities, does not
check namespace names as URIs and does not expand markup inside an entity
give differently is left out of the corpus (see skip()).

  scripts/xml_corpus.py            write testdata/xmlcorpus.txt and .out
  scripts/xml_corpus.py --check    fail if either differs from what this makes
"""
import os
import random
import re
import sys
import pyexpat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def dump(data, ns):
    out = []
    st = {'line': bytearray(), 'depth': 0}

    def flush():
        if st['line'] and st['depth'] > 0:
            out.append('T ' + bytes(st['line']).hex())
        st['line'] = bytearray()

    def start(name, attrs):
        flush()
        names = sorted((k, v) for k, v in attrs.items())
        out.append('S ' + name.encode().hex() + ''.join(' ' + k.encode().hex() + '=' + v.encode().hex() for k, v in names))
        st['depth'] += 1

    def end(name):
        flush()
        out.append('E')
        st['depth'] -= 1

    p = pyexpat.ParserCreate(namespace_separator=' ' if ns else None)
    p.StartElementHandler = start
    p.EndElementHandler = end
    p.CharacterDataHandler = lambda d: st['line'].extend(d.encode('utf-8'))
    p.CommentHandler = lambda d: (flush(), out.append('C ' + d.encode().hex()))
    p.ProcessingInstructionHandler = lambda t, d: (flush(), out.append('P ' + t.encode().hex() + ' ' + d.encode().hex()))
    try:
        p.Parse(data, True)
    except Exception:
        return None
    flush()
    return '\n'.join(out + ['OK'])


def fnv(s):
    h = 0xcbf29ce484222325
    for b in s.encode():
        h ^= b
        h = (h * 0x100000001b3) & 0xffffffffffffffff
    return '%016x' % h


# ---- the documents ----
HAND = [
    b'<a/>', b'<a></a>', b'<a>text</a>', b'<a b="1"/>', b"<a b='1'/>", b'<a b="1" c="2">x</a>',
    b'<a b = "1" c\n=\t"2" />', b'<a b="1"c="2"/>', b'<a b="1" b="2"/>', b'<a b=1/>', b'<a b/>', b'<a b="1/>',
    b'<a b="<"/>', b'<a b="&lt;&gt;&amp;&apos;&quot;"/>', b'<a b="&#65;&#x42;&#X43;"/>', b'<a b="&#x;"/>', b'<a b="&#;"/>',
    b'<a b="&#0;"/>', b'<a b="&#1;"/>', b'<a b="&#9;&#10;&#13;"/>', b'<a b="&#xD800;"/>', b'<a b="&#x110000;"/>',
    b'<a b="&#xFFFE;"/>', b'<a b="&#x10FFFF;"/>', b'<a b="&amp"/>', b'<a b="&"/>', b'<a b="&foo;"/>',
    b'<a>&lt;&gt;&amp;&apos;&quot;</a>', b'<a>&#65;&#x42;</a>', b'<a>&foo;</a>', b'<a>&</a>', b'<a>&amp</a>',
    b'<a>]]></a>', b'<a>]]</a>', b'<a>]></a>', b'<a><![CDATA[]]></a>', b'<a><![CDATA[<>&]]></a>',
    b'<a><![CDATA[]]]]><![CDATA[>]]></a>', b'<a><![CDATA[x</a>', b'<![CDATA[x]]><a/>', b'<a/><![CDATA[x]]>',
    b'<a><!-- c --></a>', b'<a><!----></a>', b'<a><!-- -- --></a>', b'<a><!-- a- --></a>', b'<a><!-- a--></a>',
    b'<a><!--- a --></a>', b'<a><!-- a ---></a>', b'<a><!-- x</a>', b'<!-- before --><a/><!-- after -->',
    b'<a><?pi?></a>', b'<a><?pi data?></a>', b'<a><?pi   data  ?></a>', b'<a><?pi?data?></a>', b'<a><?pi ?></a>',
    b'<a><?xml?></a>', b'<a><?XML x?></a>', b'<a><?xml-stylesheet href="x"?></a>', b'<a><? x?></a>', b'<a><?x', b'<a><?x y',
    b'<?pi x?><a/>', b'<a/><?pi x?>', b'<?xml version="1.0"?><a/>', b"<?xml version='1.0'?><a/>",
    b'<?xml version="1.0" encoding="UTF-8"?><a/>', b'<?xml version="1.0" encoding="utf-8" standalone="yes"?><a/>',
    b'<?xml version="1.0" standalone="no"?><a/>', b'<?xml version="1.0" standalone="maybe"?><a/>',
    b'<?xml version="1.1"?><a/>', b'<?xml version="2.0"?><a/>', b'<?xml version="1.x"?><a/>', b'<?xml version=""?><a/>',
    b'<?xml encoding="UTF-8" version="1.0"?><a/>', b'<?xml version="1.0" encoding="UTF-8" ?><a/>',
    b'<?xml version="1.0"encoding="UTF-8"?><a/>', b'<?xml  version = "1.0"  ?><a/>', b'<?xml?><a/>', b'<?xml ?><a/>',
    b' <?xml version="1.0"?><a/>', b'\n<?xml version="1.0"?><a/>', b'<a/><?xml version="1.0"?>', b'<a><?xml version="1.0"?></a>',
    b'<?xml version="1.0" encoding="US-ASCII"?><a/>', b'<?xml version="1.0" encoding="bad name"?><a/>',
    b'', b' ', b'\n', b'text', b'<', b'<a', b'<a>', b'<a></b>', b'<a><b></a></b>', b'</a>', b'<a/>x', b'x<a/>', b'<a/><b/>',
    b'<a/> ', b' <a/>', b'<a/>\n\n', b'\n\n<a/>', b'<a>\n</a>', b'<a>\r\n</a>', b'<a>\r</a>', b'<a>a\r\nb\rc\nd</a>',
    b'<a b="x\r\ny\rz\nw\tv"/>', b'<a><b/><c/><b/></a>', b'<a><b><c><d/></c></b></a>',
    b'<1a/>', b'<-a/>', b'<.a/>', b'<_a/>', b'<a-b.c_d/>', b'<a:b/>', b'<:a/>', b'<a:/>', b'<a:b:c/>', b'< a/>', b'<a />', b'<a\n/>',
    b'<a/ >', b'<a / >', b'<a>< b/></a>', b'<a></ a>', b'<a></a >', b'<a></a\n>', b'<a b="1" ></a>',
    b'<\xc3\xa9/>', b'<a \xc3\xa9="1"/>', b'<a>\xc3\xa9\xe2\x82\xac\xf0\x9f\x98\x80</a>', b'<a>\xc3</a>', b'<a>\xc0\x80</a>',
    b'<a>\xed\xa0\x80</a>', b'<a>\xf4\x90\x80\x80</a>', b'<a>\xef\xbf\xbe</a>', b'<a>\xef\xbf\xbf</a>', b'<a>\xef\xbf\xbd</a>',
    b'<a>\x00</a>', b'<a>\x01</a>', b'<a>\x08</a>', b'<a>\x09\x0a\x0d</a>', b'<a>\x0b</a>', b'<a>\x0c</a>', b'<a>\x1f</a>', b'<a>\x7f</a>',
    b'<a b="\x01"/>', b'<a><!--\x01--></a>', b'<a><?p \x01?></a>', b'<a><![CDATA[\x01]]></a>', b'<\x01/>',
    b'\xef\xbb\xbf<a/>', b'\xef\xbb\xbf<?xml version="1.0"?><a/>', b' \xef\xbb\xbf<a/>', b'<a/>\xef\xbb\xbf',
    b'\xef\xbb\xbf\xef\xbb\xbf<a/>', b'<a>\xef\xbb\xbf</a>',
    # UTF-16 and ISO-8859-1
    '<a b="é">€</a>'.encode('utf-16'), '<a b="é">€</a>'.encode('utf-16-le'), '<a b="é">€</a>'.encode('utf-16-be'),
    b'\xff\xfe<\x00a\x00/\x00>\x00', b'\xfe\xff\x00<\x00a\x00/\x00>', b'\xff\xfe<\x00a\x00/\x00>', b'\xff\xfe<\x00a\x00',
    '<?xml version="1.0" encoding="UTF-16"?><a>é</a>'.encode('utf-16'),
    '<?xml version="1.0" encoding="UTF-16"?><a>é</a>'.encode('utf-16-le'),
    '<?xml version="1.0" encoding="UTF-16"?><a>é</a>'.encode('utf-16-be'),
    '<?xml version="1.0" encoding="ISO-8859-1"?><a>é</a>'.encode('latin-1'),
    '<?xml version="1.0" encoding="iso-8859-1"?><a b="ñ">é</a>'.encode('latin-1'),
    b'<?xml version="1.0" encoding="ISO-8859-1"?><a>\x80</a>',
    # namespaces
    b'<a xmlns="u"/>', b'<a xmlns="u"><b/></a>', b'<a xmlns="u"><b xmlns=""/></a>', b'<a xmlns:p="u"><p:b/></a>',
    b'<p:a xmlns:p="u"/>', b'<p:a/>', b'<a><p:b xmlns:p="u"/></a>', b'<a><p:b xmlns:p="u"/><p:c/></a>',
    b'<a xmlns:p="u" p:x="1"/>', b'<a p:x="1" xmlns:p="u"/>', b'<a p:x="1"/>', b'<a xmlns:p="u" xmlns:q="u" p:x="1" q:x="2"/>',
    b'<a xmlns:p="u" xmlns:q="v" p:x="1" q:x="2"/>', b'<a xmlns="u" x="1"/>', b'<a xmlns:p="u" p:x="1" x="2"/>',
    b'<a xmlns:p=""/>', b'<a xmlns:xml="http://www.w3.org/XML/1998/namespace"/>', b'<a xmlns:xml="u"/>',
    b'<a xmlns:p="http://www.w3.org/XML/1998/namespace"/>', b'<a xmlns="http://www.w3.org/XML/1998/namespace"/>',
    b'<a xmlns:xmlns="u"/>', b'<a xmlns:xmlns="http://www.w3.org/2000/xmlns/"/>', b'<a xmlns:p="http://www.w3.org/2000/xmlns/"/>',
    b'<a xmlns="http://www.w3.org/2000/xmlns/"/>', b'<a xml:lang="es"/>', b'<xml:a/>', b'<a xml:space="preserve"> </a>',
    b'<xmlns:a/>', b'<a xmlns:p:q="u"/>', b'<p:q:r xmlns:p="u"/>', b'<a xmlns:p="u"><p:b p:x="1" p:x="2"/></a>',
    b'<a xmlns:p="u" xmlns:p="v"/>', b'<a xmlns:p="u"><b xmlns:p="v"><p:c/></b><p:d/></a>',
    b'<a xmlns:p="u"><p:b xmlns:p=""/></a>', b'<a xmlns="u" xmlns:p="u"><b p:x="1"/></a>',
    b'<a xmlns:\xc3\xa9="u"><\xc3\xa9:b/></a>', b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t xml:space="preserve"> hola &amp; adi\xc3\xb3s </t></is></c><c r="B1"><v>12.5</v></c></row></sheetData></worksheet>',
    # DOCTYPE and entities
    b'<!DOCTYPE a><a/>', b'<!DOCTYPE a ><a/>', b'<!DOCTYPE a SYSTEM "x.dtd"><a/>', b"<!DOCTYPE a SYSTEM 'x.dtd'><a/>",
    b'<!DOCTYPE a PUBLIC "-//X//EN" "x.dtd"><a/>', b'<!DOCTYPE a PUBLIC "-//X//EN"><a/>', b'<!DOCTYPE a PUBLIC "x" "y" ><a/>',
    b'<!DOCTYPE a [ ]><a/>', b'<!DOCTYPE a []><a/>', b'<!DOCTYPE a [<!ELEMENT a EMPTY>]><a/>', b'<!DOCTYPE a [<!ELEMENT a ANY>]><a/>',
    b'<!DOCTYPE a [<!ELEMENT a (#PCDATA)>]><a>x</a>', b'<!DOCTYPE a [<!ELEMENT a (b,c?,(d|e)*)>]><a/>',
    b'<!DOCTYPE a [<!ELEMENT a (b|c,d)>]><a/>', b'<!DOCTYPE a [<!ELEMENT a (#PCDATA|b)>]><a/>', b'<!DOCTYPE a [<!ELEMENT a (#PCDATA|b)*>]><a/>',
    b'<!DOCTYPE a [<!ELEMENT a ()>]><a/>', b'<!DOCTYPE a [<!ELEMENT a>]><a/>', b'<!DOCTYPE a [<!ELEMENT>]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA #IMPLIED>]><a/>', b'<!DOCTYPE a [<!ATTLIST a x CDATA "d" y ID #REQUIRED>]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x (p|q) "p">]><a/>', b'<!DOCTYPE a [<!ATTLIST a x NOTATION (n) #IMPLIED>]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA #FIXED "d">]><a/>', b'<!DOCTYPE a [<!ATTLIST a x CDATA>]><a/>', b'<!DOCTYPE a [<!ATTLIST a x FOO #IMPLIED>]><a/>',
    b'<!DOCTYPE a [<!ENTITY e "v">]><a>&e;</a>', b'<!DOCTYPE a [<!ENTITY e "v">]><a b="&e;"/>',
    b'<!DOCTYPE a [<!ENTITY e "a&#38;b">]><a>&e;</a>', b'<!DOCTYPE a [<!ENTITY e "a&amp;b">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "&f;"><!ENTITY f "v">]><a>&e;</a>', b'<!DOCTYPE a [<!ENTITY e "&e;">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "x"><!ENTITY e "y">]><a>&e;</a>', b'<!DOCTYPE a [<!ENTITY e "v">]><a>&f;</a>',
    b'<!DOCTYPE a [<!ENTITY e SYSTEM "x">]><a/>', b'<!DOCTYPE a [<!ENTITY e SYSTEM "x">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e SYSTEM "x" NDATA n>]><a/>', b'<!DOCTYPE a [<!ENTITY % p "v">]><a/>',
    b'<!DOCTYPE a [<!ENTITY % p "v"> %p;]><a/>', b'<!DOCTYPE a [<!ENTITY e "%p;">]><a/>', b'<!DOCTYPE a [<!ENTITY e "&">]><a/>',
    b'<!DOCTYPE a [<!ENTITY e "&#65;">]><a>&e;</a>', b'<!DOCTYPE a [<!ENTITY e "&#0;">]><a/>', b'<!DOCTYPE a [<!ENTITY e \'"\'>]><a>&e;</a>',
    b'<!DOCTYPE a [<!NOTATION n SYSTEM "x">]><a/>', b'<!DOCTYPE a [<!NOTATION n PUBLIC "x">]><a/>', b'<!DOCTYPE a [<!NOTATION n PUBLIC "x" "y">]><a/>',
    b'<!DOCTYPE a [<!NOTATION n>]><a/>', b'<!DOCTYPE a [<!-- c --><?pi x?>]><a/>', b'<!DOCTYPE a [<!-- c -- -->]><a/>',
    b'<!DOCTYPE a [<!FOO>]><a/>', b'<!DOCTYPE a [<!ELEMENT a EMPTY>]', b'<!DOCTYPE a [', b'<!DOCTYPE a', b'<!DOCTYPE>', b'<!DOCTYPE ><a/>',
    b'<!DOCTYPE a><!DOCTYPE a><a/>', b'<a/><!DOCTYPE a>', b'<a><!DOCTYPE a></a>', b'<!DOCTYPE a SYSTEM><a/>', b'<!doctype a><a/>',
    b'<!DOCTYPE a [<!ELEMENT a (b)><!ATTLIST a x CDATA "&lt;">]><a/>', b'<!DOCTYPE a [<!ATTLIST a x CDATA "<">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "&e;"><!ENTITY e "v">]><a/>',
    b'<!DOCTYPE lolz [<!ENTITY l0 "lol"><!ENTITY l1 "&l0;&l0;&l0;&l0;&l0;&l0;&l0;&l0;&l0;&l0;"><!ENTITY l2 "&l1;&l1;&l1;&l1;&l1;&l1;&l1;&l1;&l1;&l1;">]><lolz>&l2;</lolz>',
    b'<!DOCTYPE a [<!ENTITY e1 "&e2;"><!ENTITY e2 "&e3;"><!ENTITY e3 "&e1;">]><a>&e1;</a>',
    # odd constructs
    b'<a><b/></a><c/>', b'<a>text<b/>more<c/>end</a>', b'<a b="x" c=\'y\' d="z"/>', b'<a   b="1"   />', b'<a\tb="1"\n/>',
    b'<a b="a>b"/>', b"<a b='a\"b'/>", b'<a b="a\'b"/>', b'<a b="&quot;"/>', b'<a b=""/>', b'<a b="  x   y  "/>',
    b'<![endif]-->', b'<!-->', b'<!--', b'<!-', b'<!', b'<!ELEMENT a>', b'<?', b'<?>', b'<??>', b'<?a?>', b'<a><?a?></a>',
    b'<a>' + b'<b>' * 50 + b'</b>' * 50 + b'</a>', b'<a>' + b'x' * 300 + b'</a>', b'<' + b'a' * 100 + b'/>',
    b'<a ' + b' '.join(b'a%d="%d"' % (i, i) for i in range(40)) + b'/>',
]

# P446: the DOCTYPE's declarations applied. Entities whose text is markup, read as content;
# the attributes the subset declares, defaulted and normalized by their type.
DTD = [
    # markup in an entity
    b'<!DOCTYPE a [<!ENTITY e "<b/>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b>x</b>y">]><a>1&e;2</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b>x</b>y">]><a>&e;&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "pre<b/>post">]><a>[&e;]</a>',
    b'<!DOCTYPE a [<!ENTITY e1 "<c>&e2;</c>"><!ENTITY e2 "t<d/>">]><a>&e1;</a>',
    b'<!DOCTYPE a [<!ENTITY e2 "t<d/>"><!ENTITY e1 "<c>&e2;</c>">]><a>&e1;</a>',
    b'<!DOCTYPE a [<!ENTITY e1 "<c>&e2;</c>"><!ENTITY e2 "t<d/>">]><a>&e1;&e2;&e1;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b/>">]>&e;',
    b'<!DOCTYPE a [<!ENTITY e "<a/>">]>&e;',
    b'<!DOCTYPE a [<!ENTITY e "<b/>">]><a/>&e;',
    b'<!DOCTYPE a [<!ENTITY e "<b>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b>">]><a>&e;</b></a>',
    b'<!DOCTYPE a [<!ENTITY e "</b>">]><a><b>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "</a><a>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b></a>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b">]><a>&e;></a>',
    b'<!DOCTYPE a [<!ENTITY e "<b x=\'v>">]><a>&e;\'/></a>',
    b'<!DOCTYPE a [<!ENTITY e "<b/>">]><a x="&e;"/>',
    b'<!DOCTYPE a [<!ENTITY e "x&#60;y">]><a x="&e;"/>',
    b'<!DOCTYPE a [<!ENTITY e "x&#60;y">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "x&#60;/a>">]><a>&e;',
    b'<!DOCTYPE a [<!ENTITY e "&#38;#60;">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "&#38;#60;b/>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "&#60;!-- c -->">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<!--c--><?p d?><![CDATA[x<y]]>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<![CDATA[x">]><a>&e;]]></a>',
    b'<!DOCTYPE a [<!ENTITY e "]]>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<?xml version=\'1.0\'?>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<?xml?>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<!DOCTYPE b>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<?p?>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b/>">]><a>&f;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b/>&f;">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b/>&f;"><!ENTITY f "t">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b>&e;</b>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "&f;<x/>"><!ENTITY f "&e;">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b/>"><!ENTITY e "<c/>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b/>">]><a>&e;<!--c-->&e;<?p?>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b x=\'1\' y=\"2\"/>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b x=\'1\' x=\'2\'/>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b x=\'&amp;\'/>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b x=\'&lt;&#38;\'>&lt;t&#38;</b>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<p:b/>">]><a xmlns:p="u">&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<p:b/>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b xmlns=\'u\'><c/></b><d/>">]><a>&e;<c/></a>',
    b'<!DOCTYPE a [<!ENTITY e "<b xmlns:p=\'u\'/>">]><a>&e;<p:c/></a>',
    b'<!DOCTYPE a [<!ENTITY e "<b a:c=\'1\'/>">]><a xmlns:a="u">&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "x\r\ny\rz<b/>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b/>">]><a>' + b'&e;' * 30 + b'</a>',
    b'<!DOCTYPE a [<!ENTITY l0 "<l/>"><!ENTITY l1 "&l0;&l0;&l0;&l0;&l0;&l0;&l0;&l0;&l0;&l0;"><!ENTITY l2 "&l1;&l1;&l1;&l1;&l1;&l1;&l1;&l1;&l1;&l1;">]><a>&l2;</a>',
    b'<!DOCTYPE a [<!ENTITY e1 "<x>&e2;</x>"><!ENTITY e2 "&e3;"><!ENTITY e3 "&e1;">]><a>&e1;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b/>">]><a><c>&e;</c></a>',
    b'<!DOCTYPE a [<!ENTITY e "<b/>">]><a b="x"><c b="y">&e;</c></a>',
    b'<!DOCTYPE a [<!ENTITY e SYSTEM "x"><!ENTITY f "<b/>">]><a>&f;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b/>">]><a>&e</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b/>">]><a>&e ;</a>',
    b'<!DOCTYPE a [<!ENTITY e "<b/>">]><a>&#x3C;e;</a>',
    # the declarations of attributes
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "1">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "1">]><a x="2"/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "1">]><a y="2"/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "1">]><a><b/></a>',
    b'<!DOCTYPE a [<!ATTLIST b x CDATA "1">]><a><b/><b x="3"/></a>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "1"><!ATTLIST a x CDATA "2">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "1" y CDATA "2" z CDATA "3">]><a y="9"/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "1"><!ATTLIST a y CDATA "2">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA #FIXED "1">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA #FIXED "1">]><a x="2"/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA #IMPLIED y CDATA #REQUIRED>]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x (p|q) "p">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x (p|q) "r">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x NOTATION (n) "n">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "&#65;&amp;&lt;">]><a/>',
    b'<!DOCTYPE a [<!ENTITY e "v"><!ATTLIST a x CDATA "[&e;]">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "[&e;]"><!ENTITY e "v">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "[&e;]">]><a/>',
    b'<!DOCTYPE a [<!ENTITY e "<b/>"><!ATTLIST a x CDATA "[&e;]">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "a\tb\nc">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "  a  b  ">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x NMTOKEN "  a  b  ">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x NMTOKENS "  a  b  ">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x NMTOKENS "  a  b  ">]><a x="  c   d  "/>',
    b'<!DOCTYPE a [<!ATTLIST a x NMTOKENS CDATA>]><a x="  c   d  "/>',
    b'<!DOCTYPE a [<!ATTLIST a x ID #IMPLIED>]><a x="  c   d  "/>',
    b'<!DOCTYPE a [<!ATTLIST a x IDREFS #IMPLIED>]><a x=" c\td\ne\r\nf "/>',
    b'<!DOCTYPE a [<!ATTLIST a x ENTITY #IMPLIED y ENTITIES #IMPLIED>]><a x="  c " y="  d  e "/>',
    b'<!DOCTYPE a [<!ATTLIST a x (p|q) #IMPLIED>]><a x="  p  "/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA #IMPLIED>]><a x="  p  q "/>',
    b'<!DOCTYPE a [<!ATTLIST a x NMTOKEN #IMPLIED>]><a x="&#32; p &#32;&#9;q"/>',
    b'<!DOCTYPE a [<!ATTLIST a x NMTOKEN #IMPLIED>]><a x="&#9;p&#9;"/>',
    b'<!DOCTYPE a [<!ATTLIST a x NMTOKEN "&#9;p&#9;">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x NMTOKEN "">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x NMTOKEN "   ">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x NMTOKEN "   ">]><a x="   "/>',
    b'<!DOCTYPE a [<!ATTLIST a xmlns CDATA "u">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a xmlns CDATA "u">]><a><b/></a>',
    b'<!DOCTYPE a [<!ATTLIST b xmlns CDATA "u">]><a><b/></a>',
    b'<!DOCTYPE a [<!ATTLIST a xmlns:p CDATA "u">]><p:a/>',
    b'<!DOCTYPE a [<!ATTLIST p:a xmlns:p CDATA "u">]><p:a/>',
    b'<!DOCTYPE a [<!ATTLIST p:a xmlns:p CDATA "u" p:x CDATA "1">]><p:a/>',
    b'<!DOCTYPE a [<!ATTLIST a xmlns:p CDATA "u" p:x CDATA "1">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a p:x CDATA "1">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a xmlns:p CDATA "u" xmlns:q CDATA "u" p:x CDATA "1" q:x CDATA "2">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a xmlns:p CDATA "u" xmlns:q CDATA "v" p:x CDATA "1" q:x CDATA "2">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a xmlns CDATA "http://www.w3.org/XML/1998/namespace">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a xmlns:p CDATA "">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a xmlns CDATA #FIXED "u">]><a xmlns="v"/>',
    b'<!DOCTYPE a [<!ATTLIST a xmlns:x NMTOKEN #IMPLIED>]><a xmlns:x=" u " xmlns:y="u"/>',
    b'<!DOCTYPE a [<!ATTLIST a xmlns:x NMTOKEN #IMPLIED>]><a xmlns:x=" u " xmlns:y="u" x:z="1" y:z="2"/>',
    b'<!DOCTYPE a [<!ATTLIST a xmlns:x NMTOKEN #IMPLIED xmlns:y NMTOKEN #IMPLIED>]><a xmlns:x=" u " xmlns:y="u " x:z="1" y:z="2"/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "1" x CDATA "2">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "1" y CDATA "2"><!ELEMENT a (b)>]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "1"><!ATTLIST b y CDATA "2">]><a><b/><b y="3"/><b x="4"/></a>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "1"><!ATTLIST b y CDATA "2">]><b/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "1">]><a x="1" x="2"/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "1">]><a x=1/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "1">]><a x/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "1">]><a y="&e;"/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "a b">]><a/><!--c-->',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "' + b'v' * 300 + b'">]><a/>',
    b'<!DOCTYPE a [' + b''.join(b'<!ATTLIST a x%d CDATA "%d">' % (i, i) for i in range(60)) + b']><a x30="z"/>',
    b'<!DOCTYPE a [' + b''.join(b'<!ATTLIST e%d x CDATA "%d">' % (i, i) for i in range(60)) + b']><e7><e59/><e60/></e7>',
    b'<!DOCTYPE a [<!ENTITY e "<b/>"><!ATTLIST b x CDATA "1">]><a>&e;</a>',
    b'<!DOCTYPE a SYSTEM "x"><a>&e;</a>',
    b'<!DOCTYPE a PUBLIC "p" "x"><a x="&e;">&e;</a>',
    b'<?xml version="1.0" standalone="yes"?><!DOCTYPE a SYSTEM "x"><a>&e;</a>',
    b'<?xml version="1.0" standalone="no"?><!DOCTYPE a SYSTEM "x"><a>&e;</a>',
    b'<!DOCTYPE a SYSTEM "x" [<!ENTITY e "<b/>"><!ATTLIST a x CDATA "1">]><a>&e;&f;</a>',
    b'<!DOCTYPE a SYSTEM "x" [<!ENTITY e "v">]><a x="&f;">&e;</a>',
    b'<!DOCTYPE a [<!ENTITY % p "v"> %p; <!ATTLIST a x CDATA "1">]><a/>',
    b'<?xml version="1.0" standalone="yes"?><!DOCTYPE a [<!ENTITY % p "v"> %p; <!ATTLIST a x CDATA "1">]><a/>',
    b'<?xml version="1.0" standalone="no"?><!DOCTYPE a [<!ENTITY % p "v"> %p; <!ATTLIST a x CDATA "1">]><a/>',
    b'<!DOCTYPE a [<!ATTLIST a x CDATA "1"> <!ENTITY % p "v"> %p;]><a/>',
    b'<!DOCTYPE a [<!ENTITY % p "v"> %p; <!ENTITY e "<b/>">]><a>&e;</a>',
    b'<?xml version="1.0" standalone="yes"?><!DOCTYPE a [<!ENTITY % p "v"> %p; <!ENTITY e "<b/>">]><a>&e;</a>',
    b'<!DOCTYPE a [<!ATTLIST b x NMTOKEN "  1  "><!ENTITY e "<b x=\'  2   3 \'/>">]><a>&e;</a>',
]


def mutations(seeds, n, seed):
    rnd = random.Random(seed)
    chars = [b'<', b'>', b'&', b';', b'"', b"'", b'/', b'?', b'!', b'-', b'[', b']', b':', b' ', b'\n', b'\r', b'=', b'#', b'x',
             b'\x00', b'\x0b', b'\xc3', b'\xa9', b'\xef\xbf\xbe', b'\xed\xa0\x80', b'&amp;', b'&#65;', b'&#0;', b'&#x110000;',
             b'<![CDATA[', b']]>', b'<!--', b'-->', b'--', b'xmlns:', b'xmlns="u"', b'xml:', b'<?', b'?>', b'a:b', b'p:q:r']
    out = []
    for _ in range(n):
        d = bytearray(rnd.choice(seeds))
        for _ in range(rnd.randint(1, 3)):
            k = rnd.randint(0, 3)
            pos = rnd.randint(0, len(d))
            if k == 0 and d:
                del d[pos:pos + rnd.randint(1, 4)]
            elif k == 1:
                d[pos:pos] = rnd.choice(chars)
            elif k == 2 and d and pos < len(d):
                d[pos] = rnd.randint(0, 255)
            else:
                d[pos:pos] = rnd.choice(chars) + rnd.choice(chars)
        out.append(bytes(d))
    return out


def skip(d):
    """what expat and this reader read differently on purpose"""
    # a space in a namespace name: expat refuses it, XML does not
    for m in re.finditer(rb'xmlns(?::[^=\s]*)?\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', d):
        v = m.group(1) if m.group(1) is not None else m.group(2)
        if re.search(rb'[\s]', v) or b'&' in v:
            return True
    # the same in the default value an ATTLIST gives to xmlns or xmlns:p
    for m in re.finditer(rb'xmlns(?::[^\s]*)?\s+\w+\s+(?:#FIXED\s+)?(?:"([^"]*)"|\'([^\']*)\')', d):
        v = m.group(1) if m.group(1) is not None else m.group(2)
        if re.search(rb'[\s]', v) or b'&' in v:
            return True
    # past a parameter entity reference that is not read the declarations are skipped (XML 1.0 5.1),
    # and expat does not check a character reference in what it skips; XML 1.0 4.1 (Legal Character) does
    if re.search(rb'%[\w.:-]+;', d) and re.search(rb'&#(?:0+|x0+|x?110000|[xX][dD][89a-fA-F][0-9a-fA-F]{2}|[xX][fF]{3}[eEfF])[0-9]*;', d):
        return True
    # the same: expat does not check a declared default value for < when it skips the declaration
    pe = re.search(rb'%[\w.:-]+;', d)
    if pe and re.search(rb'<!ATTLIST[^"\']*(?:"[^"]*<[^"]*"|\'[^\']*<[^\']*\')', d[pe.end():]):
        return True
    # and for a reference in a literal that is no reference
    if pe and re.search(rb'<!(?:ATTLIST|ENTITY)[^"\']*["\'][^"\']*&(?![#\w][\w.:-]*;)', d[pe.end():]):
        return True
    # a character above U+FFFF in a name: expat refuses it, the Fifth Edition allows it
    if b'<!ENTITY' in d and re.search(rb'&#(?:[xX]0*(?:[1-9a-eA-E][0-9a-fA-F]{4}|10[0-9a-fA-F]{4})|0*[0-9]{5,});', d):
        return True
    # a name in a declaration whose local part starts with a digit, a dot or a hyphen: the reading of
    # Qualified Names in Declarations here refuses it (a local part is an NCName), expat only counts colons
    if b'<!DOCTYPE' in d and re.search(rb'[\w.-]:[0-9.-]', d):
        return True
    # encodings neither reads
    m = re.search(rb'encoding\s*=\s*["\']([^"\']*)["\']', d[:200])
    if m and m.group(1).lower() not in (b'utf-8', b'utf-16', b'us-ascii', b'iso-8859-1', b'utf8'):
        return True
    # UTF-16 without a byte order mark and without <? to show it: expat guesses, XML does not
    if len(d) >= 2 and (d[0] == 0 or d[1] == 0) and not (d[:2] in (b'\xff\xfe', b'\xfe\xff') or d[:4] in (b'<\x00?\x00', b'\x00<\x00?')):
        return True
    # what the DOCTYPE's declarations give a parser that applies them: an attribute's default, and
    # a comment or a processing instruction inside the subset, which expat reports and this reader skips
    sub = re.search(rb'<!DOCTYPE[^\[>]*\[(.*?)\]\s*>', d, re.S)
    if sub and (b'<!--' in sub.group(1) or b'<?' in sub.group(1)):
        return True
    # a reference to an external entity: expat skips it, this reader refuses it
    if b'<!ENTITY' in d and (b'SYSTEM' in d or b'PUBLIC' in d) and b'&' in d:
        return True
    return False


def corpus():
    docs = list(HAND)
    seeds = [d for d in HAND if 5 < len(d) < 400 and b'<!DOCTYPE' not in d and not d.startswith((b'\xff', b'\xfe'))]
    docs += mutations(seeds, 2500, 20261023)
    docs += DTD
    docs += mutations([d for d in DTD if len(d) < 400], 1500, 20261027)
    seen, out = set(), []
    for d in docs:
        if d in seen or skip(d):
            continue
        seen.add(d)
        out.append(d)
    return out


def make():
    txt, res = [], []
    for i, d in enumerate(corpus()):
        txt.append('%d %s' % (i, d.hex() if d else '-'))
        for mode, ns in (('ns', True), ('flat', False)):
            r = dump(d, ns)
            res.append('%d %s %s' % (i, mode, 'err' if r is None else 'ok ' + fnv(r)))
    return '\n'.join(txt) + '\n', '\n'.join(res) + '\n'


if __name__ == '__main__':
    txt, res = make()
    paths = (os.path.join(ROOT, 'testdata/xmlcorpus.txt'), os.path.join(ROOT, 'testdata/xmlcorpus.out'))
    if '--check' in sys.argv:
        bad = [p for p, t in zip(paths, (txt, res)) if not os.path.exists(p) or open(p).read() != t]
        if bad:
            print('xml_corpus: differs:', ' '.join(bad))
            sys.exit(1)
        print('xml_corpus: testdata/xmlcorpus.txt and .out are what the script makes')
    else:
        for p, t in zip(paths, (txt, res)):
            open(p, 'w').write(t)
        print('xml_corpus: %d documents' % len(txt.splitlines()))
