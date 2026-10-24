#!/usr/bin/env python3
"""testdata/mailtree.txt: messages and the tree Python's email package reads
from each (policy.default), one per line: ID base64(message) = dump.

The dump of an entity is {type|charset|disposition|filename|content-id|len:crc}
and, after it, [kid kid ...] for a multipart or an attached message (the
body's length and crc are - for those). Text bodies have their CRLF read as LF
on both sides. Texts are percent-escaped.

Run: python3 -I scripts/mail_tree_corpus.py testdata/mailtree.txt
"""
import base64
import binascii
import random
import sys
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser

R = random.Random(433)


def esc(s):
    out = []
    for b in s.encode("utf-8", "surrogateescape"):
        c = chr(b)
        if c.isalnum() and b < 128 or c in "._-@+=:;,'()~ ":
            out.append(c)
        else:
            out.append("%%%02X" % b)
    return "".join(out)


def dump(part):
    ctype = part.get_content_type()
    cs = part.get_content_charset() or ""
    disp = part.get_content_disposition() or ""
    fn = part.get_filename() or ""
    cid = part["Content-ID"]
    cid = str(cid).strip() if cid is not None else ""
    if cid.startswith("<") and cid.endswith(">"):
        cid = cid[1:-1]
    kids = list(part.iter_parts()) if part.is_multipart() else []
    if part.is_multipart() or ctype.startswith("message/") and kids:
        body = "-"
    else:
        data = part.get_payload(decode=True)
        if data is None:
            data = b""
        if ctype.startswith("text/"):
            data = data.replace(b"\r\n", b"\n")
        body = "%d:%08x" % (len(data), binascii.crc32(data))
    s = "{%s|%s|%s|%s|%s|%s}" % (esc(ctype), esc(cs.lower()), esc(disp), esc(fn), esc(cid), body)
    if kids:
        s += "[" + " ".join(dump(k) for k in kids) + "]"
    return s


def head(m, subj="Hi"):
    m["From"] = "A <a@b.c>"
    m["To"] = "d@e.f"
    m["Subject"] = subj
    m["Date"] = "Tue, 10 Jun 2003 04:00:00 +0000"
    m["Message-ID"] = "<x@y>"
    return m


def blob(n):
    return bytes(R.randrange(256) for _ in range(n))


TEXTS = [
    "hello\nworld\n", "plain ascii", "Señor José áéíóú €\n",
    "x" * 300 + "\n" + "y" * 1200 + "\n", "line one\r\nline two\r\n", "tab\there  \ntrailing   \nend",
    "", "=3D looks like qp = and =\n", "日本語のテキスト\n",
]
NAMES = ["a.txt", "report final.pdf", "Informe número 1.xlsx", 'quote"d.bin', "x" * 90 + ".dat",
         "日本語.txt", "semi;colon.txt", "a b c.csv", "plus+and=eq.txt"]


def messages():
    out = []
    # single text parts in each transfer encoding and charset
    for t in TEXTS:
        for cte in ("7bit", "8bit", "quoted-printable", "base64"):
            m = head(EmailMessage())
            try:
                m.set_content(t, cte=cte)
            except Exception:
                continue
            out.append(m)
        for cs in ("iso-8859-1", "utf-8", "windows-1252"):
            m = head(EmailMessage())
            try:
                m.set_content(t.encode(cs, "replace").decode(cs) if cs != "utf-8" else t, charset=cs, cte="quoted-printable")
            except Exception:
                continue
            out.append(m)
    # alternative
    for t in TEXTS[:4]:
        m = head(EmailMessage())
        m.set_content(t)
        m.add_alternative("<html><body><p>%s</p></body></html>" % t.replace("\n", "<br>"), subtype="html")
        out.append(m)
    # mixed with attachments
    for i, n in enumerate(NAMES):
        m = head(EmailMessage())
        m.set_content("body %d\n" % i)
        m.add_attachment(blob(R.choice([0, 1, 2, 3, 57, 76, 77, 1000, 5000])), maintype="application", subtype="octet-stream", filename=n)
        if i % 2:
            m.add_attachment("text attachment é\n".encode("utf-8"), maintype="text", subtype="plain", filename=n + ".txt")
        out.append(m)
    # alternative + attachments, related with inline images
    m = head(EmailMessage())
    m.set_content("plain\n")
    m.add_alternative("<p>html <img src='cid:img1'></p>", subtype="html")
    m.get_payload()[1].add_related(blob(200), maintype="image", subtype="png", cid="<img1@x>", filename="pic.png", disposition="inline")
    m.add_attachment(blob(300), maintype="application", subtype="pdf", filename="doc.pdf")
    out.append(m)
    # an attached message and a digest
    inner = head(EmailMessage(), "inner")
    inner.set_content("inner body\n")
    m = head(EmailMessage())
    m.set_content("outer\n")
    m.add_attachment(inner)
    out.append(m)
    m = head(EmailMessage())
    m.set_content("outer\n")
    m.add_attachment(inner, filename="inner.eml")
    out.append(m)
    # nested multipart
    m = head(EmailMessage())
    m.set_content("a\n")
    m.add_alternative("<b>b</b>", subtype="html")
    m.add_attachment("c\n", subtype="plain", filename="c.txt")
    m.add_attachment("<i>d</i>", subtype="html", filename="d.html")
    out.append(m)
    return out


RAW = [
    b"From: a@b.c\r\nSubject: no type\r\n\r\nplain body\r\n",
    b"From: a@b.c\r\nContent-Type: TEXT/PLAIN; Charset=\"ISO-8859-1\"\r\nContent-Transfer-Encoding: QUOTED-PRINTABLE\r\n\r\nSe=F1or =\r\nJos=E9\r\n",
    b"From: a@b.c\r\nContent-Type: text/plain;\r\n\tcharset=\"us-ascii\"\r\nContent-Transfer-Encoding: BASE64\r\n\r\naGVsbG8gd29ybGQ=\r\n",
    b"From: a@b.c\r\nContent-Type: application/octet-stream; name=x.bin\r\nContent-Transfer-Encoding: base64\r\nContent-Disposition: attachment; filename=x.bin\r\n\r\nAAECAwQFBgcICQ==\r\n",
    b"From: a@b.c\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Transfer-Encoding: base64\r\n\r\nw6HDqcOtw7PDug==\r\n",
    b"From: a@b.c\r\nContent-Type: multipart/mixed; boundary=\"=_b1\"\r\n\r\npreamble\r\n--=_b1\r\nContent-Type: text/plain\r\n\r\nfirst\r\n--=_b1\r\nContent-Type: image/gif; name=\"a.gif\"\r\nContent-Transfer-Encoding: base64\r\nContent-Disposition: attachment; filename=\"a.gif\"\r\n\r\nR0lGODlhAQABAAAAACw=\r\n--=_b1--\r\nepilogue\r\n",
    b"From: a@b.c\r\nContent-Type: multipart/mixed; boundary=x\r\n\r\n--x\r\n\r\nno part headers\r\n--x--\r\n",
    b"From: a@b.c\r\nContent-Type: multipart/digest; boundary=d\r\n\r\n--d\r\n\r\nFrom: z@y.x\r\nSubject: in digest\r\n\r\ndigest body\r\n--d--\r\n",
    b"From: a@b.c\r\nContent-Type: text/html; charset=windows-1252\r\nContent-Transfer-Encoding: quoted-printable\r\n\r\n<p>caf=E9 =80</p>\r\n",
    b"From: a@b.c\r\nContent-Type: application/pdf\r\nContent-Disposition: attachment;\r\n filename*0*=utf-8''Informe%20n%C3%BAmero;\r\n filename*1*=%201.pdf\r\nContent-Transfer-Encoding: base64\r\n\r\nJVBERg==\r\n",
    b"From: a@b.c\r\nContent-Type: text/plain; charset=koi8-r\r\n\r\n\xc1\xc2\xc3\r\n",
    b"From: a@b.c\r\nContent-Type: application/pdf\r\nContent-Disposition: attachment; filename*=iso-8859-1''Informe%20n%FAmero.pdf\r\nContent-Transfer-Encoding: base64\r\n\r\nJVBERg==\r\n",
    b"From: a@b.c\r\nContent-Type: application/pdf\r\nContent-Disposition: attachment;\r\n filename*0*=windows-1252''Cuenta%20%80;\r\n filename*1*=%20final.pdf\r\nContent-Transfer-Encoding: base64\r\n\r\nJVBERg==\r\n",
    b"From: a@b.c\r\nContent-Type: application/octet-stream; name*=iso-8859-15''Se%F1or%20%A4.bin\r\nContent-Transfer-Encoding: base64\r\n\r\nAAEC\r\n",
    b"From: a@b.c\nContent-Type: text/plain\n\nbare lf message\nsecond line\n",
]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "testdata/mailtree.txt"
    raws = []
    for m in messages():
        raws.append(m.as_bytes(policy=policy.SMTP))
        raws.append(m.as_bytes(policy=policy.default))
    raws += RAW
    seen = set()
    n = 0
    with open(path, "w") as f:
        for r in raws:
            if r in seen:
                continue
            seen.add(r)
            msg = BytesParser(policy=policy.default).parsebytes(r)
            f.write("%d %s = %s\n" % (n, base64.b64encode(r).decode(), dump(msg)))
            n += 1
    print("mail tree corpus:", n, "messages")


main()
