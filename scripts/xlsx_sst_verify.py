#!/usr/bin/env python3
"""P454: the workbooks pasxlsx saves with shared strings, read by openpyxl and by LibreOffice.

    ./xlsxsst dump | xlsx_sst_verify.py [--lo]

testdata/xlsxsst.paslang with the argument dump writes `sst1` (tpl1 with
texts written as shared strings), `sst2` (tpl2, which has no table: the part is
made), `sst3` (rows with another row's attributes) and `sst4` (2,000
references to 500 texts). This checks, for each, what a reader sees and what
the table must hold: count equal to the number of t="s" cells of the whole
book, uniqueCount to the number of items, the items that were there kept and in
place, every new item <si><t xml:space="preserve">text</t></si>, the entries
that were not written the entries they were, and the part, its relationship
and its content type when it is new. With --lo LibreOffice (headless, the
flatpak on this machine) converts the first sheet to CSV and the cells are
compared. Python has to be the one of the venv with openpyxl. Exit 1 on a
difference.
"""
import base64
import csv
import io
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
try:
    import openpyxl
except ImportError:
    sys.exit("run with the venv's python: /home/german/.cache/paslang-vartmp/venv-xlsx/bin/python3")

src = open(os.path.join(here, "xlsx_make.py")).read().replace("\nmain()\n", "\n")
ns = {}
exec(compile(src, "xlsx_make.py", "exec"), ns)
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
bad = 0


def check(cond, what):
    global bad
    if not cond:
        bad += 1
        print("BAD", what)


def untouched(tpl, out, changed):
    a = zipfile.ZipFile(io.BytesIO(tpl))
    b = zipfile.ZipFile(io.BytesIO(out))
    names = [zi.filename for zi in a.infolist()]
    new = [zi.filename for zi in b.infolist() if zi.filename not in names]
    check([zi.filename for zi in b.infolist()][:len(names)] == names, "the entries and their order: %s" % b.namelist())
    for zi in a.infolist():
        if zi.filename in changed:
            continue
        bi = b.getinfo(zi.filename)
        check(a.read(zi.filename) == b.read(zi.filename), "content of " + zi.filename)
        check((zi.compress_type, zi.CRC, zi.date_time, zi.external_attr) == (bi.compress_type, bi.CRC, bi.date_time, bi.external_attr),
              "metadata of " + zi.filename)
    check(b.testzip() is None, "zip test")
    return new


def table(out):
    """count, uniqueCount, the items' xml, and the number of t="s" cells of the book"""
    z = zipfile.ZipFile(io.BytesIO(out))
    raw = z.read("xl/sharedStrings.xml").decode("utf-8")
    root = ET.fromstring(raw)
    items = re.findall(r"<si>.*?</si>", raw, re.S)
    refs = 0
    for n in z.namelist():
        if n.startswith("xl/worksheets/") and n.endswith(".xml"):
            for c in ET.fromstring(z.read(n)).iter("{%s}c" % NS["m"]):
                if c.get("t") == "s":
                    refs += 1
    return int(root.get("count")), int(root.get("uniqueCount")), items, refs, raw


def lo_csv(blob):
    with tempfile.TemporaryDirectory(dir="/home/german/.cache/paslang-vartmp") as d:
        os.chmod(d, 0o777)
        p = os.path.join(d, "a.xlsx")
        open(p, "wb").write(blob)
        os.chmod(p, 0o644)
        r = subprocess.run(["runuser", "-u", "german", "--", "env", "HOME=/home/german", "flatpak", "run",
                            "--command=/app/libreoffice/program/soffice", "org.libreoffice.LibreOffice", "--headless",
                            "--convert-to", "csv", "--outdir", d, p], capture_output=True, text=True, timeout=300)
        out = os.path.join(d, "a.csv")
        if not os.path.exists(out):
            print(r.stdout, r.stderr)
            return None
        return list(csv.reader(open(out, encoding="utf-8")))


rows = {}
for ln in sys.stdin:
    if ln.strip():
        n, b = ln.split()
        rows[n] = base64.b64decode(b)

# ---- sst1: tpl1, a table with nine references to seven items
tpl = ns["tpl1"]()
out = rows["sst1"]
untouched(tpl, out, {"xl/sharedStrings.xml", "xl/worksheets/sheet1.xml"})
tc, tu, titems, trefs, _ = table(tpl)
check((tc, tu, len(titems), trefs) == (9, 7, 7, 7), "the template's table is what the test says (its count is not exact): %r" % ((tc, tu, len(titems), trefs),))
c, u, items, refs, raw = table(out)
check(c == refs, "count %d is the number of t=\"s\" cells %d" % (c, refs))
check(u == len(items), "uniqueCount %d is the number of items %d" % (u, len(items)))
check(items[:7] == titems, "the items that were there are kept, in place")
check(len(items) == 13, "six new items: %d" % len(items))
for it in items[7:]:
    check(re.fullmatch(r'<si><t xml:space="preserve">[^<]*</t></si>', it) is not None, "new item form " + it)
check(raw.startswith('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count='), "declaration and root")
wb = openpyxl.load_workbook(io.BytesIO(out))
ws = wb["Datos"]
want = {"G1": "Nombre", "G2": "Total general", "G3": "Ana & Luis", "G4": "漢字", "G5": "  con espacios  ",
        "G6": 'nuevo <b> & "q" \nlínea', "G7": "Ñandú º", "A1": 5, "B1": None, "C1": "inline now", "A2": "Nombre",
        "H1": "via the option", "H2": "via the option", "H3": "inline again"}
for ref, v in want.items():
    got = ws[ref].value
    check(got == v, "%s: %r != %r" % (ref, got, v))
check(ws["G8"].value in (None, ""), "G8 empty")
check(ws["A2"].number_format == "@", "A2 keeps its style")
if "--lo" in sys.argv:
    c = lo_csv(out)
    check(c is not None, "LibreOffice opened sst1")
    if c:
        check(c[0][6] == "Nombre" and c[0][7] == "via the option", "LO row 1: %r" % c[0])
        check(c[1][0] == "Nombre" and c[1][6] == "Total general", "LO row 2: %r" % c[1])
        print("LibreOffice read sst1: row 1", c[0], "row 2", c[1])

# ---- sst2: tpl2 has no table
tpl = ns["tpl2"]()
out = rows["sst2"]
new = untouched(tpl, out, {"[Content_Types].xml", "xl/_rels/workbook.xml.rels", "xl/worksheets/hoja.xml"})
check(new == ["xl/sharedStrings.xml"], "the new part: %r" % new)
c, u, items, refs, raw = table(out)
check((c, u, len(items), refs) == (4, 3, 3, 4), "table %r" % ((c, u, len(items), refs),))
check(items == ['<si><t xml:space="preserve">uno</t></si>', '<si><t xml:space="preserve">dos</t></si>', '<si><t xml:space="preserve">tres&amp;</t></si>'], "items %r" % items)
z = zipfile.ZipFile(io.BytesIO(out))
rels = z.read("xl/_rels/workbook.xml.rels").decode()
check(re.search(r'<Relationship Id="rId\d+" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>', rels) is not None, "the relationship")
ids = re.findall(r'Id="([^"]+)"', rels)
check(len(ids) == len(set(ids)), "relationship ids are unique %r" % ids)
ct = z.read("[Content_Types].xml").decode()
check('<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>' in ct, "the content type")
wb = openpyxl.load_workbook(io.BytesIO(out))
ws = wb["Lote"]
check([ws[r].value for r in ("A1", "B1", "C1", "D1")] == ["uno", "dos", "uno", "tres&"], "tpl2 cells %r" % [ws[r].value for r in ("A1", "B1", "C1", "D1")])
if "--lo" in sys.argv:
    c = lo_csv(out)
    check(c is not None, "LibreOffice opened sst2")
    if c:
        check(c[0][:4] == ["uno", "dos", "uno", "tres&"], "LO sst2 row 1: %r" % c[0])
        print("LibreOffice read sst2: row 1", c[0])

# ---- sst5: a sheet that was not read is counted from its text
out = rows["sst5"]
c, u, items, refs, raw = table(out)
check((c, u, len(items), refs) == (8, 8, 8, 8), "sst5 table %r" % ((c, u, len(items), refs),))
wb = openpyxl.load_workbook(io.BytesIO(out))
check(wb["Listas"]["B1"].value == "solo en la otra hoja", "sst5 cell")

# ---- sst3: the rows' attributes
out = rows["sst3"]
x = zipfile.ZipFile(io.BytesIO(out)).read("xl/worksheets/sheet1.xml").decode()
tags = {int(m.group(1)): m.group(0) for m in re.finditer(r'<row r="(\d+)"[^>]*>', x)}
check('ht="30"' in tags[2] and 'customHeight="1"' in tags[2], "row 2 took the height: " + tags[2])
check('ht=' not in tags[4] and 'customHeight' not in tags[4], "row 4 lost it: " + tags[4])
check(tags[9] == '<row r="9" ht="30" customHeight="1"/>', "row 9: " + tags[9])
wb = openpyxl.load_workbook(io.BytesIO(out))
ws = wb["Datos"]
check(ws.row_dimensions[9].height == 30 and ws.row_dimensions[2].height == 30 and ws.row_dimensions[4].height is None, "row heights read by openpyxl")

# ---- sst4: 2,000 references to 500 texts
out = rows["sst4"]
c, u, items, refs, raw = table(out)
check((c, u, len(items), refs) == (2000, 500, 500, 2000), "volume table %r" % ((c, u, len(items), refs),))
wb = openpyxl.load_workbook(io.BytesIO(out), read_only=True)
ws = wb["Lote"]
n = 0
for row in ws.iter_rows(min_row=6, max_row=2005, min_col=1, max_col=1, values_only=True):
    i = n + 1
    if row[0] != "texto %d de la tabla" % (i % 500):
        check(False, "volume row %d: %r" % (i + 5, row[0]))
        break
    n += 1
check(n == 2000, "2,000 cells read: %d" % n)

print("xlsx sst verify:", "ok" if not bad else "%d bad" % bad)
sys.exit(1 if bad else 0)
