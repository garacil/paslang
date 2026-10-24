#!/usr/bin/env python3
"""The composer (TMailBuilder) checked by Python's email package.

  python3 -I scripts/mail_build_verify.py gen testdata/mailbuild.txt
      writes the cases: one op per line, ID OP ARG... with the arguments in
      base64 ('-' for none); the ops are new from to cc bcc replyto subject
      text html att inl hdr date mid boundary expect build
  python3 -I scripts/mail_build_verify.py verify testdata/mailbuild.txt OUT
      reads what testdata/mailbuild.paslang printed for them (=== ID, then
      the message, or raised: text) and checks every message the way a mail
      reader reads it: seven bits, CRLF, line lengths, the fields, the
      bodies, the files, the structure.
"""
import base64
import random
import re
import sys
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser

R = random.Random(4331)


def b(x):
    if isinstance(x, str):
        x = x.encode("utf-8")
    return base64.b64encode(x).decode() if x else "-"


def ub(s):
    return b"" if s == "-" else base64.b64decode(s)


NAMES = ["Ana", "José María Pérez", 'O"Brien, Pat', "", "日本語", "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z", "María"]
ADDRS = ["ana@example.com", "jose.perez@example.org", "x@y.z", "long.address.with.dots@sub.domain.example.net", "tag+one@example.com"]
SUBJECTS = ["Hi", "Factura número 42", "", ("Re: " + "palabra " * 30).strip(), "日本語の件名", ("café " * 40).strip(), ("plain but long " * 12).strip()]
TEXTS = ["hello\n", "Señor García: aquí va el texto con acentos áéíóú.\n", "", "one line no newline",
         "line\r\nwith crlf\r\nand\rcr\n", "x" * 1500 + "\n", "=3D = equals and trailing space \nend", ".\n.dot lines\n..\n", "From the start\n"]
HTMLS = ["<p>hi</p>", "<p>Señor €</p>\n", "<a href=\"x?a=1&b=2\">" + "link " * 400 + "</a>\n", "<img src=\"cid:i1\">"]
FILES = [("a.txt", "text/plain"), ("report final.pdf", ""), ("Informe número 1.xlsx", ""), ('quote"d.bin', "application/octet-stream"),
         ("日本語.txt", ""), ("noext", ""), ("x" * 100 + ".dat", "application/x-custom"), ("m.eml", "message/rfc822")]


def blob(n):
    return bytes(R.randrange(256) for _ in range(n))


def cases():
    out = []
    n = 0

    def case(ops, expect=None):
        nonlocal n
        n += 1
        for op in ops:
            out.append("%d %s" % (n, op))
        if expect is not None:
            out.append("%d expect %s" % (n, b(expect)))
        out.append("%d build" % n)

    base = ["new", "from %s %s" % (b("Sender"), b("sender@example.com")), "to %s %s" % (b("Dest"), b("dest@example.org")), "date %s %s" % (b("1065000000"), b("7200")),
            "mid %s" % b("<id1@example.com>"), "boundary %s" % b("=_bnd")]
    case(base + ["subject %s" % b("Hi"), "text %s" % b("hello\n")])
    case(base + ["subject %s" % b("Factura número 42"), "text %s" % b(TEXTS[1])])
    case(base + ["subject %s" % b("alt"), "text %s" % b("plain\n"), "html %s" % b("<p>html</p>")])
    case(base + ["subject %s" % b("html only"), "html %s" % b(HTMLS[1])])
    case(base + ["subject %s" % b("files"), "text %s" % b("see files\n"), "att %s %s %s" % (b("a b.pdf"), b("application/pdf"), b(blob(5000))),
                 "att %s %s %s" % (b("Informe número 1.xlsx"), b(""), b(blob(77))), "att %s %s %s" % (b("empty.bin"), b(""), b(""))])
    case(base + ["subject %s" % b("related"), "text %s" % b("plain\n"), "html %s" % b(HTMLS[3]),
                 "inl %s %s %s %s" % (b("p.png"), b("image/png"), b("i1"), b(blob(300))),
                 "att %s %s %s" % (b("doc.pdf"), b(""), b(blob(200)))])
    case(base + ["subject %s" % b("inline without a page"), "text %s" % b("plain\n"), "inl %s %s %s %s" % (b("p.png"), b("image/png"), b("i1"), b(blob(30)))])
    case(["new", "from %s %s" % (b("Señora Sánchez"), b("s@example.com"))] + ["to %s %s" % (b(NAMES[i % len(NAMES)]), b("u%d@example.com" % i)) for i in range(14)] +
         ["cc %s %s" % (b("Copia"), b("cc@example.com")), "bcc %s %s" % (b("Oculto"), b("hidden@example.com")), "replyto %s %s" % (b("Reply"), b("reply@example.com")),
          "date %s %s" % (b("0"), b("0")), "mid %s" % b("x@y"), "subject %s" % b("many recipients"), "text %s" % b("x\n")])
    case(base + ["subject %s" % b(SUBJECTS[3]), "text %s" % b("x\n")])
    case(base + ["subject %s" % b(SUBJECTS[5]), "text %s" % b("x\n")])
    case(base + ["subject %s" % b(SUBJECTS[4]), "text %s" % b("x\n"), "hdr %s %s" % (b("In-Reply-To"), b("<abc@def>")),
                 "hdr %s %s" % (b("X-Note"), b("café con leche")), "hdr %s %s" % (b("References"), b("<a@b> <c@d> <e@f>"))])
    case(base + ["subject %s" % b("eml"), "text %s" % b("attached\n"), "att %s %s %s" % (b("m.eml"), b(""), b("From: a@b.c\nSubject: inner\n\ninner body\n"))])
    case(base + ["subject %s" % b("long line"), "text %s" % b("a" * 3000), "html %s" % b("<p>" + "b" * 2000 + "</p>")])
    case(base + ["subject %s" % b("empty")])
    # the ones that must be refused
    case(base + ["subject %s" % b("a\r\nBcc: evil@example.com"), "text %s" % b("x\n")], expect="raised")
    case(base + ["subject %s" % b("ok"), "hdr %s %s" % (b("X-A"), b("v\nBcc: evil@example.com")), "text %s" % b("x\n")], expect="raised")
    case(base + ["subject %s" % b("ok"), "hdr %s %s" % (b("X A"), b("v")), "text %s" % b("x\n")], expect="raised")
    case(base + ["subject %s" % b("ok"), "to %s %s" % (b("Evil"), b("a@b.c>\r\nBcc: x@y.z")), "text %s" % b("x\n")], expect="raised")
    case(base + ["subject %s" % b("ok"), "to %s %s" % (b("Evil\r\nBcc: x@y.z"), b("a@b.c")), "text %s" % b("x\n")], expect="raised")
    case(base + ["subject %s" % b("ok"), "to %s %s" % (b("No at"), b("noat")), "text %s" % b("x\n")], expect="raised")
    case(base + ["subject %s" % b("ok"), "att %s %s %s" % (b("x\r\ny"), b(""), b("d")), "text %s" % b("x\n")], expect="raised")
    case(["new", "from %s %s" % (b("S"), b("s@example.com")), "subject %s" % b("no recipient"), "text %s" % b("x\n")], expect="raised")
    case(base + ["boundary %s" % b("bad boundary!"), "subject %s" % b("ok"), "text %s" % b("x\n"), "att %s %s %s" % (b("a"), b(""), b("d"))], expect="raised")
    # random combinations
    for i in range(70):
        ops = ["new", "from %s %s" % (b(R.choice(NAMES)), b(R.choice(ADDRS))), "date %s %s" % (b(str(R.randrange(0, 2000000000))), b(str(R.choice([0, 3600, -18000, 19800, -3600 * 12]))))]
        for _ in range(R.randrange(1, 4)):
            ops.append("to %s %s" % (b(R.choice(NAMES)), b(R.choice(ADDRS))))
        if R.random() < 0.3:
            ops.append("cc %s %s" % (b(R.choice(NAMES)), b(R.choice(ADDRS))))
        if R.random() < 0.3:
            ops.append("bcc %s %s" % (b(R.choice(NAMES)), b(R.choice(ADDRS))))
        ops.append("subject %s" % b(R.choice(SUBJECTS)))
        hasHtml = R.random() < 0.5
        if R.random() < 0.8:
            ops.append("text %s" % b(R.choice(TEXTS)))
        if hasHtml:
            ops.append("html %s" % b(R.choice(HTMLS)))
        for k in range(R.randrange(0, 4)):
            wantInl = hasHtml and R.random() < 0.4
            nm, ty = R.choice([f for f in FILES if not (wantInl and f[1] == "message/rfc822")])
            data = blob(R.choice([0, 1, 2, 3, 75, 76, 77, 100, 3000]))
            if ty == "message/rfc822":
                data = b"From: a@b.c\nSubject: inner\n\nbody\n"
            if wantInl:
                ops.append("inl %s %s %s %s" % (b(nm), b(ty), b("cid%d" % k), b(data)))
            else:
                ops.append("att %s %s %s" % (b(nm), b(ty), b(data)))
        # every message is fixed so that what is written is the same each run
        ops.append("mid %s" % b(("m%d@example.com" % i) if i % 2 else ("<m%d@example.com>" % i)))
        ops.append("boundary %s" % b("B%d" % i))
        case(ops)
    return out


def gen(path):
    lines = cases()
    open(path, "w").write("\n".join(lines) + "\n")
    print("mail build cases:", len([l for l in lines if l.endswith(" build")]))


def addrs(v):
    return [(a.display_name, a.addr_spec) for a in v.addresses] if v is not None else []


def verify(spec, outp):
    cs = {}
    order = []
    for ln in open(spec).read().splitlines():
        i, op, *args = ln.split(" ")
        i = int(i)
        if i not in cs:
            cs[i] = {"to": [], "cc": [], "bcc": [], "atts": [], "hdr": [], "expect": None, "mid": None}
            order.append(i)
        c = cs[i]
        a = [ub(x) for x in args]
        t = lambda k: a[k].decode("utf-8")
        if op == "from":
            c["from"] = (t(0), t(1))
        elif op in ("to", "cc", "bcc"):
            c[op].append((t(0), t(1)))
        elif op == "replyto":
            c["replyto"] = (t(0), t(1))
        elif op in ("subject", "text", "html", "boundary"):
            c[op] = t(0)
        elif op == "att":
            c["atts"].append((t(0), t(1), a[2], False, ""))
        elif op == "inl":
            c["atts"].append((t(0), t(1), a[3], True, t(2)))
        elif op == "hdr":
            c["hdr"].append((t(0), t(1)))
        elif op == "date":
            c["date"] = (int(t(0)), int(t(1)))
        elif op == "mid":
            c["mid"] = t(0)
        elif op == "expect":
            c["expect"] = t(0)
    data = open(outp, "rb").read()
    parts = re.split(rb"^=== (\d+)\n", data, flags=re.M)
    got = {int(parts[k]): parts[k + 1] for k in range(1, len(parts), 2)}
    bad = 0

    def fail(i, why):
        nonlocal bad
        bad += 1
        if bad <= 20:
            print("CASE", i, why)

    ok = 0
    for i in order:
        c = cs[i]
        raw = got.get(i)
        if raw is None:
            fail(i, "no output")
            continue
        # the program ends with a line of the count, and each case with one LF
        raw = re.sub(rb"cases \d+\n$", b"", raw)
        if raw.endswith(b"\n"):
            raw = raw[:-1]
        if c["expect"] == "raised":
            if not raw.startswith(b"raised: "):
                fail(i, "should have raised, built %d bytes" % len(raw))
            else:
                ok += 1
            continue
        if raw.startswith(b"raised: "):
            fail(i, raw[:200].decode("utf-8", "replace"))
            continue
        if any(x >= 128 for x in raw):
            fail(i, "not 7-bit")
            continue
        if re.search(rb"(?<!\r)\n", raw) or re.search(rb"\r(?!\n)", raw):
            fail(i, "line ending")
            continue
        lines = raw.split(b"\r\n")
        if any(len(l) > 998 for l in lines):
            fail(i, "line over 998")
            continue
        hend = lines.index(b"")
        longh = [l for l in lines[:hend] if len(l) > 78 and b" " in l.strip()]
        if longh:
            fail(i, "header line over 78: %r" % longh[0][:100])
            continue
        m = BytesParser(policy=policy.default).parsebytes(raw)
        if m.defects:
            fail(i, "defects %r" % (m.defects,))
            continue
        if m.get("Bcc") is not None or "evil" in raw.decode().lower():
            fail(i, "Bcc leaked")
            continue
        why = None
        fr = addrs(m["From"])
        if fr != [c["from"]]:
            why = "From %r vs %r" % (fr, c["from"])
        for key, name in (("to", "To"), ("cc", "Cc")):
            if why is None and addrs(m[name]) != c[key]:
                why = "%s %r vs %r" % (name, addrs(m[name]), c[key])
        if why is None and "replyto" in c and addrs(m["Reply-To"]) != [c["replyto"]]:
            why = "Reply-To"
        if why is None and str(m["Subject"]) != c.get("subject", ""):
            why = "Subject %r vs %r" % (str(m["Subject"]), c.get("subject", ""))
        if why is None and "date" in c:
            u, off = c["date"]
            want = datetime.fromtimestamp(u, timezone(timedelta(seconds=off)))
            if m["Date"].datetime != want:
                why = "Date %r vs %r" % (m["Date"].datetime, want)
        if why is None and c["mid"] is not None:
            w = c["mid"] if c["mid"].startswith("<") else "<" + c["mid"] + ">"
            if str(m["Message-ID"]) != w:
                why = "Message-ID %r" % str(m["Message-ID"])
        if why is None and m["MIME-Version"] != "1.0":
            why = "MIME-Version"
        for hn, hv in c["hdr"]:
            if why is None and str(m[hn]) != hv:
                why = "header %s %r vs %r" % (hn, str(m[hn]), hv)
        if why is None:
            text, html = c.get("text", ""), c.get("html", "")
            if text:
                body = m.get_body(preferencelist=("plain",))
                got_t = body.get_content().replace("\r\n", "\n") if body is not None else None
                want_t = text.replace("\r\n", "\n").replace("\r", "\n")
                if got_t is None or got_t.replace("\r\n", "\n") != want_t:
                    why = "text %r vs %r" % (got_t, want_t)
            if why is None and html:
                body = m.get_body(preferencelist=("html",))
                got_h = body.get_content().replace("\r\n", "\n") if body is not None else None
                want_h = html.replace("\r\n", "\n").replace("\r", "\n")
                if got_h != want_h:
                    why = "html %r vs %r" % (got_h, want_h)
        if why is None:
            hasHtml = bool(c.get("html"))
            regs = [x for x in c["atts"] if not (x[3] and hasHtml)]
            inls = [x for x in c["atts"] if x[3] and hasHtml]
            got_a = [(p.get_filename() or "", p.get_content_type(), p.get_payload(decode=True)) for p in m.iter_attachments()]
            if regs and not (c.get("text") or hasHtml):
                got_a = got_a  # a lone attachment list is still the attachments
            want_a = []
            # a related message with no text beside the page has its inline files read as the attachments
            if not regs and hasHtml and not c.get("text") and inls:
                regs = inls
            for nm, ty, data, inl, cid in regs:
                if not ty:
                    ty = None
                want_a.append((nm, ty, data))
            if len(got_a) != len(want_a):
                why = "attachments %d vs %d" % (len(got_a), len(want_a))
            else:
                for (gn, gt, gd), (wn, wt, wd) in zip(got_a, want_a):
                    if gn != wn or gd != (wd if wd else b"") and not (gt == "message/rfc822"):
                        why = "attachment %r %d bytes vs %r %d bytes" % (gn, len(gd or b""), wn, len(wd))
                        break
                    if wt and gt != wt:
                        why = "attachment type %r vs %r" % (gt, wt)
                        break
            if why is None and inls:
                rel = [p for p in m.walk() if p.get_content_type() == "multipart/related"]
                if not rel:
                    why = "no multipart/related"
                else:
                    kids = list(rel[0].iter_parts())[1:]
                    for (nm, ty, data, inl, cid), k in zip(inls, kids):
                        if (k.get("Content-ID") or "").strip() != "<%s>" % cid or k.get_payload(decode=True) != (data or b"") or k.get_content_disposition() != "inline":
                            why = "inline part %r" % nm
                            break
        if why is None:
            top = m.get_content_type()
            hasHtml = bool(c.get("html"))
            regs = [x for x in c["atts"] if not (x[3] and hasHtml)]
            want_top = "multipart/mixed" if regs else ("multipart/alternative" if c.get("text") and hasHtml else ("multipart/related" if hasHtml and any(x[3] for x in c["atts"]) else ("text/html" if hasHtml else "text/plain")))
            if top != want_top:
                why = "top type %s vs %s" % (top, want_top)
        if why:
            fail(i, why)
        else:
            ok += 1
    print("cases %d, ok %d, failed %d" % (len(order), ok, bad))
    sys.exit(1 if bad else 0)


if sys.argv[1] == "gen":
    gen(sys.argv[2])
else:
    verify(sys.argv[2], sys.argv[3])
