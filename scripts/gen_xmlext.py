#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""gen_xmlext.py: testdata/xmlext.paslang and .out (P477). Documents with
external general entities, each with the bytes the entity has, read by
pasxml through a resolver that serves them from memory; the expected line of
each is what pyexpat makes of the same documents with an external entity
handler that serves the same bytes: OK, the text of the document in hex and
the names of its elements, or ERR. With dtd (P511) the reader also asks for the
external subset and the external parameter entities and expat is told to parse
parameter entities. The checks of the messages, of what the
resolver is asked and how often, and of the limits, which expat does not
have, are written by hand in the program (scripts/xmlext_hand.inc, whose
statements follow the marker, and xmlext_hand.out, the lines they print).

  scripts/gen_xmlext.py [PROGRAM [HAND.inc [HAND.out]]]   writes
                                   testdata/xmlext.paslang and .out"""
import os
import posixpath
import sys
import xml.parsers.expat as expat

HERE = os.path.dirname(os.path.abspath(__file__))

DT = '<!DOCTYPE doc [\n<!ELEMENT doc ANY>\n%s]>\n'


def ent(name='e', sysid='e.ent', pub=None):
    if pub is None:
        return '<!ENTITY %s SYSTEM "%s">\n' % (name, sysid)
    return '<!ENTITY %s PUBLIC "%s" "%s">\n' % (name, pub, sysid)


def doc(body, decls=None):
    return (DT % (decls if decls is not None else ent())) + body


U8 = lambda s: s.encode('utf-8')
cases = [
    ('text', doc('<doc>&e;</doc>'), {'e.ent': b'Data\n'}),
    ('empty', doc('<doc>&e;</doc>'), {'e.ent': b''}),
    ('markup', doc('<doc>&e;</doc>'), {'e.ent': b'<e/><e/><e/>'}),
    ('nested elements', doc('<doc>&e;</doc>'), {'e.ent': b'<a>x<b>y</b>z</a>'}),
    ('in an element', doc('<doc><p>&e;</p></doc>'), {'e.ent': b'<a>x</a>'}),
    ('public identifier', doc('<doc>&e;</doc>', ent(pub='  a   not\n very  interesting file ')), {'e.ent': b'xyzzy\n'}),
    ('text declaration', doc('<doc>&e;</doc>'), {'e.ent': b'<?xml version="1.0" encoding="UTF-8"?>text'}),
    ('text declaration, no version', doc('<doc>&e;</doc>'), {'e.ent': b"<?xml encoding='UTF-8'?>\nline"}),
    ('text declaration, ISO-8859-1', doc('<doc>&e;</doc>'), {'e.ent': b"<?xml version='1.0' encoding='ISO-8859-1'?>caf\xe9"}),
    ('text declaration, ASCII', doc('<doc>&e;</doc>'), {'e.ent': b'<?xml encoding="US-ASCII"?>abc'}),
    ('UTF-8 byte order mark', doc('<doc>&e;</doc>'), {'e.ent': b'\xef\xbb\xbfx'}),
    ('two UTF-8 byte order marks', doc('<doc>&e;</doc>'), {'e.ent': b'\xef\xbb\xbf\xef\xbb\xbfx'}),
    ('UTF-16 little endian', doc('<doc>&e;</doc>'), {'e.ent': b'\xff\xfeh\x00i\x00'}),
    ('UTF-16 big endian', doc('<doc>&e;</doc>'), {'e.ent': b'\xfe\xff\x00h\x00i'}),
    ('UTF-16 with a text declaration', doc('<doc>&e;</doc>'), {'e.ent': b'\xff\xfe' + '<?xml version="1.0" encoding="UTF-16"?>hi'.encode('utf-16-le')}),
    ('UTF-16 without a byte order mark', doc('<doc>&e;</doc>'), {'e.ent': '<?xml encoding="UTF-16"?>hi'.encode('utf-16-le')}),
    ('through an internal entity', doc('<doc>&i;</doc>', ent() + '<!ENTITY i "[&e;]">\n'), {'e.ent': b'Data'}),
    ('an entity in an entity', doc('<doc>&e;</doc>', ent() + ent('f', 'f.ent')), {'e.ent': b'<a>&f;</a>', 'f.ent': b'inner'}),
    ('twice', doc('<doc>&e;&e;</doc>'), {'e.ent': b'ab'}),
    ('character data', doc('<doc>&e;</doc>'), {'e.ent': b'<![CDATA[<x>]]>&#65;&lt;<!--c--><?pi d?>t'}),
    ('line ends', doc('<doc>&e;</doc>'), {'e.ent': b'a\r\nb\rc'}),
    ('in an attribute value', doc('<doc a="&e;"/>'), {'e.ent': b'x'}),
    ('unparsed', doc('<doc>&u;</doc>', '<!NOTATION n SYSTEM "n">\n<!ENTITY u SYSTEM "u.bin" NDATA n>\n'), {'u.bin': b'x'}),
    ('an element left open', doc('<doc>&e;</doc>'), {'e.ent': b'<a>'}),
    ('an end tag with no start', doc('<doc>&e;</doc>'), {'e.ent': b'</doc>'}),
    ('a loop', doc('<doc>&e;</doc>'), {'e.ent': b'x&e;'}),
    ('the resolver has none', doc('<doc>&e;</doc>'), {}),
    ('a text declaration with no encoding', doc('<doc>&e;</doc>'), {'e.ent': b'<?xml version="1.0"?>x'}),
    ('a text declaration with standalone', doc('<doc>&e;</doc>'), {'e.ent': b'<?xml encoding="UTF-8" standalone="yes"?>x'}),
    ('a text declaration in the middle', doc('<doc>&e;</doc>'), {'e.ent': b'a<?xml encoding="UTF-8"?>'}),
    ('a byte order mark and a backwards one', doc('<doc>&e;</doc>'), {'e.ent': b'\xef\xbb\xbf\xef\xbf\xbex'}),
    ('a character that is no character', doc('<doc>&e;</doc>'), {'e.ent': b'\x01'}),
    ('bytes that are no UTF-8', doc('<doc>&e;</doc>'), {'e.ent': b'\xc3\x28'}),
    ('an undeclared entity', doc('<doc>&e;</doc>'), {'e.ent': b'&zzz;'}),
    ('text after the root', doc('<doc/>&e;'), {'e.ent': b'x'}),
    ('a CDATA section left open', doc('<doc>&e;</doc>'), {'e.ent': b'<![CDATA[x'}),
]

DTDCASES = [
    ('an external subset', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>', {'x.dtd': b'<!ENTITY e "from the dtd">'}),
    ('the internal subset first', '<!DOCTYPE doc SYSTEM "x.dtd" [<!ENTITY e "internal">]>\n<doc>&e;</doc>', {'x.dtd': b'<!ENTITY e "external">'}),
    ('a public identifier for it', '<!DOCTYPE doc PUBLIC "-//X//DTD x//EN" "x.dtd">\n<doc>&e;</doc>', {'x.dtd': b'<!ENTITY e "p">'}),
    ('a parameter entity between declarations', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>',
     {'x.dtd': b"<!ENTITY % p \"<!ENTITY e 'v'>\"> %p;"}),
    ('a parameter entity in a declaration', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>',
     {'x.dtd': b"<!ENTITY % t \"'v2'\"> <!ENTITY e %t;>"}),
    ('a parameter entity in an entity value', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>',
     {'x.dtd': b'<!ENTITY % s "abc"> <!ENTITY e "x%s;y">'}),
    ('a quote in a parameter entity in an entity value', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>',
     {'x.dtd': b"<!ENTITY % q 'a\"b'> <!ENTITY e \"[%q;]\">"}),
    ('a parameter entity in a public identifier', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>',
     {'x.dtd': b"<!ENTITY % s 'x'> <!ENTITY e PUBLIC \"a%s;\" \"y.ent\">", 'y.ent': b'ent'}),
    ('INCLUDE', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>', {'x.dtd': b"<![INCLUDE[ <!ENTITY e 'inc'> ]]>"}),
    ('IGNORE', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>', {'x.dtd': b"<![IGNORE[ <!ENTITY e 'ign'> ]]> <!ENTITY e 'after'>"}),
    ('sections chosen by parameter entities', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>',
     {'x.dtd': b"<!ENTITY % on 'INCLUDE'> <!ENTITY % off 'IGNORE'> <![%on;[ <!ENTITY e 'a'> ]]> <![%off;[ <!ENTITY e 'b'> ]]>"}),
    ('a section ignored with one inside', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>',
     {'x.dtd': b"<![IGNORE[ <![INCLUDE[ x ]]> <!ENTITY e 'no'> ]]> <!ENTITY e 'yes'>"}),
    ('a section included in one', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>',
     {'x.dtd': b"<![INCLUDE[ <![INCLUDE[ <!ENTITY e 'deep'> ]]> ]]>"}),
    ('a section with a bad keyword', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc/>', {'x.dtd': b'<![FOO[ ]]>'}),
    ('a section left open', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc/>', {'x.dtd': b'<![INCLUDE[ <!ENTITY e "x">'}),
    ('an external parameter entity', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>',
     {'x.dtd': b'<!ENTITY % ext SYSTEM "p.ent"> %ext;', 'p.ent': b"<!ENTITY e 'fromext'>"}),
    ('with a text declaration', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>',
     {'x.dtd': b'<!ENTITY % ext SYSTEM "p.ent"> %ext;', 'p.ent': b"<?xml encoding='UTF-8'?><!ENTITY e 'te'>"}),
    ('in the internal subset', '<!DOCTYPE doc [<!ENTITY % ext SYSTEM "p.ent"> %ext;]>\n<doc>&e;</doc>', {'p.ent': b"<!ENTITY e 'ie'>"}),
    ('relative to the subset', '<!DOCTYPE doc SYSTEM "sub/x.dtd">\n<doc>&e;</doc>',
     {'sub/x.dtd': b'<!ENTITY % ext SYSTEM "p.ent"> %ext;', 'sub/p.ent': b"<!ENTITY e 'rel'>"}),
    ('and above it', '<!DOCTYPE doc SYSTEM "sub/x.dtd">\n<doc>&e;</doc>',
     {'sub/x.dtd': b'<!ENTITY % ext SYSTEM "../p.ent"> %ext;', 'p.ent': b"<!ENTITY e 'up'>"}),
    ('an entity of the subset, external', '<!DOCTYPE doc SYSTEM "sub/x.dtd">\n<doc>&e;</doc>',
     {'sub/x.dtd': b'<!ENTITY e SYSTEM "e.ent">', 'sub/e.ent': b'text of e'}),
    ('standalone and declared outside', '<?xml version="1.0" standalone="yes"?>\n<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>',
     {'x.dtd': b"<!ENTITY e 'x'>"}),
    ('standalone and declared in a parameter entity', '<?xml version="1.0" standalone="yes"?>\n<!DOCTYPE doc [<!ENTITY % p "<!ENTITY e \'v\'>"> %p;]>\n<doc>&e;</doc>', {}),
    ('not declared after the subset', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&zz;</doc>', {'x.dtd': b"<!ENTITY e 'x'>"}),
    ('not declared, a parameter entity there', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&zz;</doc>',
     {'x.dtd': b"<!ENTITY % p 'x'> %p; <!ENTITY e 'x'>"}),
    ('a parameter entity that is not there', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>', {'x.dtd': b"%nope; <!ENTITY e 'x'>"}),
    ('a loop of parameter entities', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc/>', {'x.dtd': b'<!ENTITY % a "&#37;a;"> %a;'}),
    ('a text declaration of the subset', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>',
     {'x.dtd': b"<?xml version='1.0' encoding='UTF-8'?><!ENTITY e 'td'>"}),
    ('a byte order mark in it', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>', {'x.dtd': b"\xef\xbb\xbf<!ENTITY e 'bom'>"}),
    ('UTF-16', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>', {'x.dtd': "<!ENTITY e 'w'>".encode('utf-16')}),
    ('comments and instructions', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>',
     {'x.dtd': b"<!-- c --><?pi x?><!ENTITY e 'ci'><!-- <!ENTITY e 'no'> -->"}),
    ('an element declaration', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc><b/></doc>', {'x.dtd': b'<!ELEMENT doc (b)> <!ELEMENT b EMPTY>'}),
    ('an attribute list', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc/>', {'x.dtd': b"<!ATTLIST doc a CDATA 'd'>"}),
    ('a notation and an unparsed entity', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc/>',
     {'x.dtd': b"<!NOTATION n SYSTEM 'x'><!ENTITY u SYSTEM 'u.bin' NDATA n>"}),
    ('something that is no declaration', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc/>', {'x.dtd': b'text'}),
    ('the subset is not there', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc/>', {}),
    ('a declaration cut by its parameter entity', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>',
     {'x.dtd': b"<!ENTITY % p \"<!ENTITY e 'x'\"> %p;>"}),
]
# without LoadSubset the subset and the external parameter entities are not asked for (expat's default)
NOLOAD = [
    ('the subset not loaded', '<!DOCTYPE doc SYSTEM "x.dtd">\n<doc>&e;</doc>', {'x.dtd': b'<!ENTITY e "from the dtd">'}),
    ('an external parameter entity not loaded', '<!DOCTYPE doc [<!ENTITY % ext SYSTEM "p.ent"> %ext; <!ENTITY e \'v\'>]>\n<doc>&e;</doc>', {'p.ent': b'x'}),
]
# the parameter entities of the internal subset are read without it (expat is told to parse them)
INTPE = [
    ('internal parameter entities are read', '<!DOCTYPE doc [<!ENTITY % p "<!ENTITY e \'v\'>"> %p;]>\n<doc>&e;</doc>', {}),
    ('a parameter entity makes an undeclared entity no matter', '<!DOCTYPE doc [<!ENTITY % p "<!ENTITY e \'v\'>"> %p;]>\n<doc>&zz;</doc>', {}),
    ('an undeclared entity with none', '<!DOCTYPE doc [<!ENTITY e \'v\'>]>\n<doc>&zz;</doc>', {}),
    ('a parameter entity that is not there', '<!DOCTYPE doc [%p; <!ENTITY e \'v\'>]>\n<doc>&e;</doc>', {}),
]


def oracle(d, ents, dtd=False):
    names, text = [], []
    p = expat.ParserCreate()
    p.buffer_text = True
    if dtd:
        p.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_ALWAYS)

    def wire(q):
        q.StartElementHandler = lambda n, a: names.append(n)
        q.CharacterDataHandler = lambda s: text.append(s)

    wire(p)

    def ext(context, base, systemId, publicId):
        # a system identifier is relative to the entity it is met in
        path = posixpath.normpath(posixpath.join(posixpath.dirname(base or ''), systemId))
        sub = p.ExternalEntityParserCreate(context)
        sub.SetBase(path)
        sub.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_ALWAYS) if dtd else None
        wire(sub)
        sub.ExternalEntityRefHandler = ext
        sub.Parse(ents[path], True)
        return 1
    p.ExternalEntityRefHandler = ext
    try:
        p.Parse(d.encode('utf-8'), True)
    except Exception:
        return None
    return ''.join(text).encode('utf-8').hex(), ','.join(names)


def lit(s):
    return "'" + s + "'"


out_lines = []
prog = []
allcases = ([c + (False, False) for c in cases] + [c + (True, True) for c in DTDCASES] +
            [c + (False, False) for c in NOLOAD] + [c + (False, True) for c in INTPE])
for i, (name, d, ents, load, dtd) in enumerate(allcases):
    r = oracle(d, ents, dtd)
    key = 'x%02d' % (i + 1)
    if r is None:
        out_lines.append('%s ERR' % key)
    else:
        out_lines.append('%s OK %s %s' % (key, r[0] or '-', r[1]))
    prog.append("  Begin_('%s');" % key)
    prog.append("  Doc_('%s');" % d.encode('utf-8').hex())
    for k, v in ents.items():
        prog.append("  Ent_('%s', '%s');" % (k, v.hex()))
    prog.append('  GoD_;' if load else '  Go_;')
    prog.append('')

hand = open(sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'xmlext_hand.inc')).read()
text = '''{ This file is part of paslang.
  Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
  paslang is free software under the GNU General Public License,
  version 3 or (at your option) any later version; see the file COPYING.

  P477: pasxml reads an external parsed entity through a resolver the program
  gives. Generated by scripts/gen_xmlext.py: %d documents whose entities have
  the bytes served from memory; the line each prints is what pyexpat makes of
  the same documents (the text of the document in hex and the names of its
  elements, or ERR); then the checks that expat has no word for. }
program xmlext;

uses
  sysutils, pasxml;

var
  Names, Datas: array of string;
  Key, DocHex, LastPub, LastSys: string;
  Calls: Integer;

function FromHex(const H: string): string;
var
  i: Integer;
begin
  SetLength(Result, Length(H) div 2);
  for i := 1 to Length(H) div 2 do
    Result[i] := Chr(StrToInt('$' + Copy(H, i * 2 - 1, 2)));
end;

function ToHex(const S: string): string;
const
  D = '0123456789abcdef';
var
  i: Integer;
begin
  Result := '';
  for i := 1 to Length(S) do
    Result := Result + D[(Ord(S[i]) shr 4) + 1] + D[(Ord(S[i]) and 15) + 1];
end;

procedure Begin_(const K: string);
begin
  Key := K;
  Names := nil;
  Datas := nil;
  Calls := 0;
end;

procedure Doc_(const H: string);
begin
  DocHex := H;
end;

procedure Ent_(const N, H: string);
begin
  SetLength(Names, Length(Names) + 1);
  SetLength(Datas, Length(Datas) + 1);
  Names[High(Names)] := N;
  Datas[High(Datas)] := H;
end;

function Serve(const PublicId, SystemId: string): string;
var
  i: Integer;
begin
  Calls := Calls + 1;
  LastPub := PublicId;
  LastSys := SystemId;
  for i := 0 to High(Names) do
    if Names[i] = SystemId then
    begin
      Result := FromHex(Datas[i]);
      Exit;
    end;
  raise Exception.Create('no entity ' + SystemId);
end;

procedure Walk(N: TXmlNode; var L: string);
var
  i: Integer;
begin
  for i := 0 to N.Count - 1 do
    if N.Item(i).Kind = xkElement then
    begin
      if L <> '' then
        L := L + ',';
      L := L + N.Item(i).Name;
      Walk(N.Item(i), L);
    end;
end;

procedure Run_(Dtd: Boolean);
var
  d: TXmlDoc;
  l, t: string;
begin
  try
    if Dtd then
      d := XmlParseDtd(FromHex(DocHex), @Serve, False)
    else
      d := XmlParseWith(FromHex(DocHex), @Serve, False);
    l := d.Root.Name;
    Walk(d.Root, l);
    t := ToHex(d.Root.Text);
    if t = '' then
      t := '-';
    WriteLn(Key, ' OK ', t, ' ', l);
  except
    on E: EXmlError do
      WriteLn(Key, ' ERR');
  end;
end;

procedure Go_;
begin
  Run_(False);
end;

procedure GoD_;
begin
  Run_(True);
end;

%s
begin
%s
%s
end.
''' % (len(cases), hand.split('@@MAIN@@')[0], '\n'.join(prog), hand.split('@@MAIN@@')[1])
open(sys.argv[1] if len(sys.argv) > 1 else 'testdata/xmlext.paslang', 'w').write(text)
open((sys.argv[1] if len(sys.argv) > 1 else 'testdata/xmlext.paslang')[:-8] + '.out', 'w').write(
    '\n'.join(out_lines) + '\n' + open(sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, 'xmlext_hand.out')).read())
