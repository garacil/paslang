function MsgOf(const Src: string; R: TXmlResolver; Limit: Integer): string;
var
  rd: TXmlReader;
  tok: TXmlToken;
begin
  Result := 'OK';
  try
    rd := TXmlReader.Create(Src);
    rd.Namespaces := False;
    rd.Resolver := R;
    if Limit > 0 then
      rd.MaxExpansion := Limit;
    while rd.Next(tok) do
      ;
  except
    on E: EXmlError do
      Result := E.Message;
  end;
end;

procedure Chk(const Id: string; Ok: Boolean; const Why: string);
begin
  if Ok then
    WriteLn(Id, ' ok')
  else
    WriteLn(Id, ' WRONG ', Why);
end;

function Has(const S, Sub: string): Boolean;
begin
  Result := Pos(Sub, S) > 0;
end;

function Doc1(const Decls, Body: string): string;
begin
  Result := '<!DOCTYPE doc [' + Chr(10) + '<!ELEMENT doc ANY>' + Chr(10) + Decls + ']>' + Chr(10) + Body;
end;

function RaiseXml(const PublicId, SystemId: string): string;
begin
  raise EXmlError.CreateAt(0, 1, 1, 'mine');
end;

var
  m, src, decls: string;
  d: TXmlDoc;
  rd: TXmlReader;
  tok: TXmlToken;
  n, k: Integer;
@@MAIN@@
  { what the program is told, and not told }
  Begin_('h');
  Ent_('e.ent', '44617461');
  src := Doc1('<!ENTITY e SYSTEM "e.ent">' + Chr(10), '<doc>&e;</doc>');
  m := MsgOf(src, nil, 0);
  Chk('h01 no resolver', Has(m, 'reference to the external entity &e;'), m);
  Calls := 0;
  m := MsgOf(src, @Serve, 0);
  Chk('h02 resolver asked once', (m = 'OK') and (Calls = 1) and (LastSys = 'e.ent') and (LastPub = ''), m);
  m := MsgOf(Doc1('<!ENTITY e SYSTEM "gone.ent">' + Chr(10), '<doc>&e;</doc>'), @Serve, 0);
  Chk('h03 resolver refuses', Has(m, 'the resolver refused &e;') and Has(m, 'no entity gone.ent'), m);
  try
    rd := TXmlReader.Create(Doc1('<!ENTITY e SYSTEM "gone.ent">' + Chr(10), '<doc>&e;</doc>'));
    rd.Resolver := @Serve;
    while rd.Next(tok) do
      ;
    Chk('h04 place of the refusal', False, 'read');
  except
    on E: EXmlError do
      Chk('h04 place of the refusal', (E.Line = 5) and (E.Column = 6), IntToStr(E.Line) + ':' + IntToStr(E.Column));
  end;
  m := MsgOf(Doc1('<!ENTITY e SYSTEM "e.ent">' + Chr(10), '<doc a="&e;"/>'), @Serve, 0);
  Chk('h05 in an attribute value', Has(m, 'in an attribute value'), m);
  m := MsgOf(Doc1('<!NOTATION n SYSTEM "n">' + Chr(10) + '<!ENTITY u SYSTEM "e.ent" NDATA n>' + Chr(10), '<doc>&u;</doc>'), @Serve, 0);
  Chk('h06 unparsed', Has(m, 'unparsed entity &u;'), m);
  Begin_('h');
  Ent_('e.ent', '3c3f786d6c2076657273696f6e3d22312e30223f3e78');
  m := MsgOf(src, @Serve, 0);
  Chk('h07 text declaration with no encoding', Has(m, 'text declaration'), m);
  Begin_('h');
  Ent_('e.ent', '44617461');
  Ent_('f.ent', '6162');
  m := MsgOf(Doc1('<!ENTITY e PUBLIC "  a   not' + Chr(10) + ' very  interesting file " "e.ent">' + Chr(10), '<doc>&e;</doc>'), @Serve, 0);
  Chk('h08 public identifier', (m = 'OK') and (LastPub = 'a not very interesting file') and (LastSys = 'e.ent'), LastPub);
  Calls := 0;
  m := MsgOf(Doc1('<!ENTITY f SYSTEM "f.ent">' + Chr(10), '<doc>&f;&f;&f;</doc>'), @Serve, 0);
  Chk('h09 asked once for three references', (m = 'OK') and (Calls = 1), IntToStr(Calls));
  { a chain of 25 entities, one in the next: past the depth 20 of the entities }
  Begin_('h');
  decls := '';
  for k := 0 to 24 do
  begin
    decls := decls + '<!ENTITY e' + IntToStr(k) + ' SYSTEM "e' + IntToStr(k) + '.ent">' + Chr(10);
    if k < 24 then
      Ent_('e' + IntToStr(k) + '.ent', ToHex('<a>&e' + IntToStr(k + 1) + ';</a>'))
    else
      Ent_('e24.ent', ToHex('x'));
  end;
  m := MsgOf(Doc1(decls, '<doc>&e0;</doc>'), @Serve, 0);
  Chk('h10 entities nested too deep', Has(m, 'nested too deep'), m);
  Begin_('h');
  Ent_('e.ent', ToHex('0123456789012345678901234567890123456789'));
  m := MsgOf(src, @Serve, 10);
  Chk('h11 more than MaxExpansion', Has(m, 'MaxExpansion'), m);
  m := MsgOf(src, @Serve, 100);
  Chk('h12 within MaxExpansion', m = 'OK', m);
  Begin_('h');
  Ent_('e.ent', ToHex('<e/><e/><e/>'));
  rd := TXmlReader.Create(src);
  rd.Resolver := @Serve;
  n := 0;
  while rd.Next(tok) do
    if (tok.Kind = xtStart) and tok.Ent then
      n := n + 1;
  Chk('h13 tokens read from the entity', n = 3, IntToStr(n));
  d := XmlParseWith(src, @Serve, True);
  Chk('h14 the document written as it was', (d.Xml = src) and (d.Root.Count = 3), IntToStr(d.Root.Count));
  rd := TXmlReader.Create(src);
  Chk('h15 no resolver by default', rd.Resolver = nil, 'set');
  m := MsgOf(src, @RaiseXml, 0);
  Chk('h16 an XML error of the resolver is its own', Has(m, 'mine') and (not Has(m, 'refused')), m);
  { the external subset and the external parameter entities (P511) }
  Begin_('h');
  Ent_('x.dtd', ToHex('<!ENTITY e ''from the dtd''> <!ATTLIST doc a CDATA ''dflt''>'));
  src := '<!DOCTYPE doc PUBLIC "  -//X//DTD  x//EN " "x.dtd">' + Chr(10) + '<doc>&e;</doc>';
  Calls := 0;
  m := MsgOf(src, @Serve, 0);
  Chk('h17 the subset is not asked for by default', (m = 'OK') and (Calls = 0), IntToStr(Calls));
  d := XmlParseDtd(src, @Serve, False);
  Chk('h18 the subset is read with LoadSubset', (d.Root.Text = 'from the dtd') and (d.Root.Attr('a') = 'dflt'), d.Root.Text);
  Chk('h19 asked once, with the identifiers', (Calls = 1) and (LastSys = 'x.dtd') and (LastPub = '-//X//DTD x//EN'), LastPub);
  Begin_('h');
  Ent_('x.dtd', ToHex('text'));
  try
    XmlParseDtd(src, @Serve, False);
    Chk('h20 a subset that is no declarations', False, 'read');
  except
    on E: EXmlError do
      Chk('h20 a subset that is no declarations', Has(E.Message, 'invalid markup') and Has(E.Message, 'external subset') and (E.Line = 1), E.Message);
  end;
  Begin_('h');
  m := MsgOf(src, @Serve, 0);
  Chk('h21 no subset to read is no matter without LoadSubset', m = 'OK', m);
  try
    XmlParseDtd(src, @Serve, False);
    Chk('h22 the resolver refuses the subset', False, 'read');
  except
    on E: EXmlError do
      Chk('h22 the resolver refuses the subset', Has(E.Message, 'the resolver refused the external subset') and Has(E.Message, 'no entity x.dtd'), E.Message);
  end;
  Begin_('h');
  Ent_('x.dtd', ToHex('<!ENTITY % a ''&#37;b;''> <!ENTITY % b ''&#37;a;''> %a;'));
  try
    XmlParseDtd(src, @Serve, False);
    Chk('h23 parameter entities that loop', False, 'read');
  except
    on E: EXmlError do
      Chk('h23 parameter entities that loop', Has(E.Message, 'nested too deep'), E.Message);
  end;
  Begin_('h');
  Ent_('x.dtd', ToHex('<!ENTITY % big ''0123456789012345678901234567890123456789''> <!ENTITY e ''%big;%big;''>'));
  d := XmlParseDtd(src, @Serve, False);
  Chk('h24 text through a parameter entity', d.Root.Text = '01234567890123456789012345678901234567890123456789012345678901234567890123456789', d.Root.Text);
  rd := TXmlReader.Create(src);
  rd.Resolver := @Serve;
  rd.LoadSubset := True;
  rd.MaxExpansion := 100;
  try
    while rd.Next(tok) do
      ;
    Chk('h25 parameter entities are held to MaxExpansion', False, 'read');
  except
    on E: EXmlError do
      Chk('h25 parameter entities are held to MaxExpansion', Has(E.Message, 'MaxExpansion'), E.Message);
  end;

