#!/usr/bin/env python3
"""P436: the template workbooks of testdata/xlsx, made with zipfile alone.

    xlsx_make.py [FILE]       write testdata/xlsxtpl.txt: one line each,
                              `NAME BASE64` of an XLSX file

tpl1 is laid out as Excel writes a file: compact XML, shared strings (one
with rich runs and one with a phonetic run), a style table, a visible sheet
of cells (text, numbers, a Boolean, an error, formulas with their values,
styled empty cells, merged cells, a list validation, conditional formatting,
a defined name), a hidden sheet and a very hidden one, a calculation chain,
core and application properties; some entries stored, some deflated, with
their own times. tpl2 is the other way: pretty-printed XML with white space
between the cells, the 1904 date system, inline strings and no shared
strings table, no calculation chain, absolute targets in its relationships,
and the sheet's cells with no r.
Every file is the same each time it is made.
"""
import base64
import io
import sys
import zipfile

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
HDR = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'


def entry(zf, name, data, method=zipfile.ZIP_DEFLATED, when=(2024, 3, 31, 12, 30, 58), attr=0):
    zi = zipfile.ZipInfo(name, date_time=when)
    zi.compress_type = method
    zi.external_attr = attr
    zf.writestr(zi, data)


def tpl1():
    ct = (HDR + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
          '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
          '<Override PartName="/xl/worksheets/sheet3.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
          '<Override PartName="/xl/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
          '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
          '<Override PartName="/xl/calcChain.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.calcChain+xml"/>'
          '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
          '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
          '</Types>')
    rels = (HDR + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>')
    wb = (HDR + '<workbook xmlns="%s" xmlns:r="%s">' % (NS, RNS) +
          '<fileVersion appName="xl" lastEdited="7" lowestEdited="7" rupBuild="22228"/>'
          '<workbookPr defaultThemeVersion="166925"/>'
          '<bookViews><workbookView xWindow="0" yWindow="0" windowWidth="28800" windowHeight="12300"/></bookViews>'
          '<sheets><sheet name="Datos" sheetId="1" r:id="rId1"/><sheet name="Listas" sheetId="2" state="hidden" r:id="rId2"/>'
          '<sheet name="Oculta" sheetId="3" state="veryHidden" r:id="rId3"/></sheets>'
          '<definedNames><definedName name="_xlnm.Print_Area" localSheetId="0">Datos!$A$1:$F$8</definedName>'
          '<definedName name="Total">Datos!$D$5</definedName></definedNames>'
          '<calcPr calcId="191029"/></workbook>')
    wbrels = (HDR + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
              '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
              '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
              '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet3.xml"/>'
              '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>'
              '<Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
              '<Relationship Id="rId6" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
              '<Relationship Id="rId7" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/calcChain" Target="calcChain.xml"/>'
              '</Relationships>')
    sst = (HDR + '<sst xmlns="%s" count="9" uniqueCount="7">' % NS +
           '<si><t>Nombre</t></si>'
           '<si><t>Importe</t></si>'
           '<si><t>Fecha</t></si>'
           '<si><r><rPr><b/><sz val="11"/></rPr><t>Total </t></r><r><t>general</t></r></si>'
           '<si><t>Ana &amp; Luis</t></si>'
           '<si><t xml:space="preserve">  con espacios  </t></si>'
           '<si><t>漢字</t><rPh sb="0" eb="2"><t>かんじ</t></rPh></si>'
           '</sst>')
    styles = (HDR + '<styleSheet xmlns="%s">' % NS +
              '<numFmts count="1"><numFmt numFmtId="164" formatCode="dd/mm/yyyy"/></numFmts>'
              '<fonts count="2"><font><sz val="11"/><name val="Calibri"/><family val="2"/></font>'
              '<font><b/><sz val="11"/><name val="Calibri"/><family val="2"/></font></fonts>'
              '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
              '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
              '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
              '<cellXfs count="5"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
              '<xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
              '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
              '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
              '<xf numFmtId="4" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>'
              '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
              '<dxfs count="1"><dxf><font><b/></font></dxf></dxfs>'
              '</styleSheet>')
    sheet1 = (HDR + '<worksheet xmlns="%s" xmlns:r="%s">' % (NS, RNS) +
              '<sheetPr><tabColor rgb="FFFF0000"/></sheetPr>'
              '<dimension ref="A1:F6"/>'
              '<sheetViews><sheetView tabSelected="1" workbookViewId="0"><selection activeCell="A1" sqref="A1"/></sheetView></sheetViews>'
              '<sheetFormatPr defaultRowHeight="15"/>'
              '<cols><col min="1" max="1" width="18.7109375" customWidth="1"/><col min="2" max="6" width="12.7109375" customWidth="1"/></cols>'
              '<sheetData>'
              '<row r="1" spans="1:6"><c r="A1" s="3" t="s"><v>0</v></c><c r="B1" s="3" t="s"><v>1</v></c><c r="C1" s="3" t="s"><v>2</v></c><c r="D1" s="3"><v>1</v></c></row>'
              '<row r="2" spans="1:6"><c r="A2" s="1"/><c r="B2" s="4"><v>1234.5</v></c><c r="C2" s="2"><v>45382</v></c><c r="D2" t="b"><v>1</v></c><c r="E2" t="e"><v>#DIV/0!</v></c></row>'
              '<row r="3" spans="1:6"><c r="A3" t="s"><v>4</v></c><c r="B3" s="4"><v>10</v></c><c r="C3" s="2"/><c r="D3" t="s"><v>5</v></c></row>'
              '<row r="4" spans="1:6" ht="30" customHeight="1"><c r="A4" t="s"><v>6</v></c><c r="B4" s="4"><v>20.25</v></c></row>'
              '<row r="5" spans="1:6"><c r="A5" t="s"><v>3</v></c><c r="B5" s="4"><f>SUM(B2:B4)</f><v>1264.75</v></c><c r="D5"><f>B5*2</f><v>2529.5</v></c><c r="F5" t="str"><f>"x"&amp;A3</f><v>xAna &amp; Luis</v></c></row>'
              '<row r="6" spans="1:6"><c r="A6" t="inlineStr"><is><t>ya en línea</t></is></c><c r="F6" s="1"/></row>'
              '</sheetData>'
              '<mergeCells count="1"><mergeCell ref="A8:C8"/></mergeCells>'
              '<conditionalFormatting sqref="B2:B6"><cfRule type="cellIs" dxfId="0" priority="1" operator="greaterThan"><formula>1000</formula></cfRule></conditionalFormatting>'
              '<dataValidations count="1"><dataValidation type="list" allowBlank="1" showInputMessage="1" showErrorMessage="1" sqref="A2:A6"><formula1>Listas!$A$1:$A$3</formula1></dataValidation></dataValidations>'
              '<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>'
              '</worksheet>')
    sheet2 = (HDR + '<worksheet xmlns="%s"><dimension ref="A1:A3"/><sheetViews><sheetView workbookViewId="0"/></sheetViews>' % NS +
              '<sheetFormatPr defaultRowHeight="15"/><sheetData>'
              '<row r="1"><c r="A1" t="inlineStr"><is><t>uno</t></is></c></row>'
              '<row r="2"><c r="A2" t="inlineStr"><is><t>dos</t></is></c></row>'
              '<row r="3"><c r="A3" t="inlineStr"><is><t>tres</t></is></c></row>'
              '</sheetData><pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/></worksheet>')
    sheet3 = (HDR + '<worksheet xmlns="%s"><sheetData/></worksheet>' % NS)
    calc = (HDR + '<calcChain xmlns="%s"><c r="B5" i="1"/><c r="D5"/><c r="F5"/></calcChain>' % NS)
    core = (HDR + '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:creator>plantilla</dc:creator>'
            '<dcterms:created xsi:type="dcterms:W3CDTF">2024-03-31T12:30:58Z</dcterms:created></cp:coreProperties>')
    app = (HDR + '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Microsoft Excel</Application></Properties>')
    theme = (HDR + '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office"><a:themeElements>'
             '<a:clrScheme name="Office"><a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1><a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>'
             '<a:dk2><a:srgbClr val="44546A"/></a:dk2><a:lt2><a:srgbClr val="E7E6E6"/></a:lt2><a:accent1><a:srgbClr val="4472C4"/></a:accent1>'
             '<a:accent2><a:srgbClr val="ED7D31"/></a:accent2><a:accent3><a:srgbClr val="A5A5A5"/></a:accent3><a:accent4><a:srgbClr val="FFC000"/></a:accent4>'
             '<a:accent5><a:srgbClr val="5B9BD5"/></a:accent5><a:accent6><a:srgbClr val="70AD47"/></a:accent6><a:hlink><a:srgbClr val="0563C1"/></a:hlink>'
             '<a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme>'
             '<a:fontScheme name="Office"><a:majorFont><a:latin typeface="Calibri Light"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>'
             '<a:minorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont></a:fontScheme>'
             '<a:fmtScheme name="Office"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>'
             '<a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="19050"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>'
             '<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>'
             '<a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>'
             '</a:themeElements></a:theme>')
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        entry(zf, "[Content_Types].xml", ct)
        entry(zf, "_rels/.rels", rels, zipfile.ZIP_STORED, (1980, 1, 1, 0, 0, 0))
        entry(zf, "docProps/app.xml", app)
        entry(zf, "docProps/core.xml", core)
        entry(zf, "xl/workbook.xml", wb)
        entry(zf, "xl/_rels/workbook.xml.rels", wbrels)
        entry(zf, "xl/theme/theme1.xml", theme)
        entry(zf, "xl/styles.xml", styles)
        entry(zf, "xl/sharedStrings.xml", sst)
        entry(zf, "xl/worksheets/sheet1.xml", sheet1, zipfile.ZIP_DEFLATED, (2024, 3, 31, 12, 30, 58), 0o100644 << 16)
        entry(zf, "xl/worksheets/sheet2.xml", sheet2)
        entry(zf, "xl/worksheets/sheet3.xml", sheet3, zipfile.ZIP_STORED)
        entry(zf, "xl/calcChain.xml", calc)
    return bio.getvalue()


def tpl2():
    ct = (HDR + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
          '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
          '  <Default Extension="xml" ContentType="application/xml"/>\n'
          '  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>\n'
          '  <Override PartName="/xl/worksheets/hoja.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>\n'
          '  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>\n'
          '</Types>\n')
    rels = (HDR + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="/xl/workbook.xml"/>\n'
            '</Relationships>\n')
    wb = (HDR + '<workbook xmlns="%s" xmlns:r="%s">\n' % (NS, RNS) +
          '  <workbookPr date1904="1"/>\n'
          '  <sheets>\n    <sheet name="Lote" sheetId="7" r:id="rIdA"/>\n  </sheets>\n</workbook>\n')
    wbrels = (HDR + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
              '  <Relationship Id="rIdA" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="/xl/worksheets/hoja.xml"/>\n'
              '  <Relationship Id="rIdB" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>\n'
              '</Relationships>\n')
    styles = (HDR + '<styleSheet xmlns="%s">\n  <fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>\n' % NS +
              '  <fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>\n'
              '  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>\n'
              '  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>\n'
              '  <cellXfs count="3">\n    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>\n'
              '    <xf numFmtId="14" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>\n'
              '    <xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>\n  </cellXfs>\n</styleSheet>\n')
    sheet = (HDR + '<worksheet xmlns="%s">\n' % NS +
             '  <dimension ref="A1:C2"/>\n'
             '  <sheetData>\n'
             '    <row>\n      <c t="inlineStr"><is><t>Código</t></is></c>\n      <c t="inlineStr"><is><t>Fecha</t></is></c>\n      <c t="inlineStr"><is><t>Cantidad</t></is></c>\n    </row>\n'
             '    <row r="2">\n      <c s="2" t="inlineStr"><is><t>0042</t></is></c>\n      <c s="1"><v>0</v></c>\n    </row>\n'
             '    <row r="4"/>\n'
             '  </sheetData>\n</worksheet>\n')
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        entry(zf, "[Content_Types].xml", ct)
        entry(zf, "_rels/.rels", rels)
        entry(zf, "xl/workbook.xml", wb)
        entry(zf, "xl/_rels/workbook.xml.rels", wbrels)
        entry(zf, "xl/styles.xml", styles)
        entry(zf, "xl/worksheets/hoja.xml", sheet)
    return bio.getvalue()


def main():
    path = "testdata/xlsxtpl.txt" if len(sys.argv) < 2 else sys.argv[1]
    lines = []
    for name, blob in (("tpl1", tpl1()), ("tpl2", tpl2())):
        lines.append("%s %s" % (name, base64.b64encode(blob).decode()))
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("xlsx templates:", [len(l) for l in lines])


main()
