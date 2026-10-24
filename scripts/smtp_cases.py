#!/usr/bin/env python3
"""testdata/smtp.txt: the scenarios of the SMTP client test. A scenario is a
script for a server (the replies it gives in turn: the greeting first, then one
for each line the client sends, or for each DATA block after a 354) and what
the client does (a mail from, to, with a message, and an optional login). The
paslang test (testdata/smtp.paslang) runs them against passmtp with a server
of its own and prints what the server received and how the client ended;
scripts/smtp_client_go.go prints the same for Go's net/smtp. The two outputs
must be identical.

Run: python3 -I scripts/smtp_cases.py testdata/smtp.txt
"""
import base64
import sys


def b(x):
    if isinstance(x, str):
        x = x.encode("utf-8", "surrogateescape")
    return base64.b64encode(x).decode() if x else "-"


GREET = "220 mail.example.com ESMTP ready\r\n"
EHLO = "250-mail.example.com\r\n250-SIZE 35882577\r\n250-8BITMIME\r\n250 PIPELINING\r\n"
EHLO_AUTH = "250-mail.example.com\r\n250-8BITMIME\r\n250 AUTH PLAIN LOGIN\r\n"
OK = "250 OK\r\n"
GO = "354 End data with <CR><LF>.<CR><LF>\r\n"
QUEUED = "250 2.0.0 queued as 12345\r\n"
BYE = "221 Bye\r\n"
BASIC = [GREET, EHLO, OK, OK, GO, QUEUED, BYE]
MSG = "From: a@example.com\r\nTo: b@example.org\r\nSubject: hi\r\n\r\nhello\r\n"

CASES = []


def case(name, replies, frm="a@example.com", rcpts=("b@example.org",), msg=MSG, auth=None):
    CASES.append((name, replies, frm, list(rcpts), msg, auth))


case("basic", BASIC)
case("two-recipients", [GREET, EHLO, OK, OK, "251 User not local; will forward\r\n", GO, QUEUED, BYE], rcpts=("b@example.org", "c@example.net"))
case("helo-fallback", [GREET, "502 5.5.1 Command not implemented\r\n", "250 mail.example.com\r\n", OK, OK, GO, QUEUED, BYE])
case("ehlo-fails-helo-fails", [GREET, "502 no\r\n", "500 no helo either\r\n", "221 Bye\r\n"])
case("utf8-and-8bit", [GREET, "250-mail.example.com\r\n250-8BITMIME\r\n250-SMTPUTF8\r\n250 SIZE 100\r\n", OK, OK, GO, QUEUED, BYE])
case("ext-only-greeting-line", [GREET, "250 mail.example.com\r\n", OK, OK, GO, QUEUED, BYE])
case("no-8bitmime", [GREET, "250-mail.example.com\r\n250 SIZE 10\r\n", OK, OK, GO, QUEUED, BYE])
case("auth-plain", [GREET, EHLO_AUTH, "235 2.7.0 Authentication successful\r\n", OK, OK, GO, QUEUED, BYE], auth=("plain", "user", "pa55word"))
case("auth-plain-refused", [GREET, EHLO_AUTH, "535 5.7.8 Authentication credentials invalid\r\n", "501 cancelled\r\n", BYE], auth=("plain", "user", "bad"))
case("auth-plain-challenge", [GREET, EHLO_AUTH, "334 VXNlcm5hbWU6\r\n", "501 cancelled\r\n", BYE], auth=("plain", "user", "pw"))
case("auth-plain-no-auth-ext", [GREET, EHLO, BYE], auth=("plain", "user", "pw"))
case("auth-plain-after-helo", [GREET, "500 no ehlo\r\n", "250 hi\r\n", OK, OK, GO, QUEUED, BYE], auth=("plain", "user", "pw"))
case("auth-cram-md5", [GREET, "250-mail.example.com\r\n250 AUTH CRAM-MD5\r\n", "334 " + base64.b64encode(b"<1896.697170952@postoffice.example.net>").decode() + "\r\n",
                       "235 ok\r\n", OK, OK, GO, QUEUED, BYE], auth=("cram", "tim", "tanstaaftanstaaf"))
case("auth-login", [GREET, "250-mail.example.com\r\n250 AUTH LOGIN\r\n", "334 VXNlcm5hbWU6\r\n", "334 UGFzc3dvcmQ6\r\n", "235 ok\r\n", OK, OK, GO, QUEUED, BYE], auth=("login", "user", "secret"))
case("auth-login-too-many-challenges", [GREET, "250-mail.example.com\r\n250 AUTH LOGIN\r\n", "334 VXNlcm5hbWU6\r\n", "334 UGFzc3dvcmQ6\r\n", "334 Zm9v\r\n", "501 x\r\n", BYE], auth=("login", "user", "secret"))
case("auth-bad-base64-challenge", [GREET, "250-mail.example.com\r\n250 AUTH CRAM-MD5\r\n", "334 !!!notbase64\r\n", "501 x\r\n", BYE], auth=("cram", "tim", "x"))
case("auth-unexpected-2xx", [GREET, EHLO_AUTH, "250 odd\r\n", "501 x\r\n", BYE], auth=("plain", "u", "p"))
case("mail-refused", [GREET, EHLO, "550 5.1.0 sender rejected\r\n", BYE])
case("rcpt-refused", [GREET, EHLO, OK, "550 5.1.1 No such user here\r\n", BYE])
case("rcpt-second-refused", [GREET, EHLO, OK, OK, "550 5.1.1 No such user\r\n", BYE], rcpts=("b@example.org", "c@example.net"))
case("rcpt-252", [GREET, EHLO, OK, "252 cannot verify but will try\r\n", GO, QUEUED, BYE])
case("rcpt-450", [GREET, EHLO, OK, "450 4.2.0 mailbox busy\r\n", BYE])
case("data-refused", [GREET, EHLO, OK, OK, "554 5.3.0 transaction failed\r\n", BYE])
case("data-final-refused", [GREET, EHLO, OK, OK, GO, "554 5.7.1 message rejected as spam\r\n", BYE])
case("data-final-multiline", [GREET, EHLO, OK, OK, GO, "250-queued as\r\n250-12345\r\n250 on mx1\r\n", BYE])
case("quit-wrong-code", [GREET, EHLO, OK, OK, GO, QUEUED, "250 not bye\r\n"])
case("greeting-refused", ["554 5.3.2 no service\r\n"])
case("greeting-multiline", ["220-mail.example.com\r\n220 ESMTP\r\n", EHLO, OK, OK, GO, QUEUED, BYE])
case("greeting-wrong-class", ["421 4.3.2 shutting down\r\n"])
case("greeting-short", ["ok\r\n"])
case("greeting-code-invalid", ["abc def\r\n"])
case("greeting-code-99", ["099 x\r\n"])
case("greeting-no-space", ["220\r\n"])
case("greeting-eof", [])
case("close-after-ehlo", [GREET, EHLO])
case("partial-last-line", [GREET, "250 mail.example.com"])
case("reply-mixed-codes", [GREET, "250-first\r\n999 odd\r\nnot a code\r\n250 last\r\n", OK, OK, GO, QUEUED, BYE])
case("reply-lf-only", [GREET, "250-mail\n250 8BITMIME\n", OK, OK, GO, QUEUED, BYE])
case("empty-message", BASIC, msg="")
case("no-trailing-newline", BASIC, msg="Subject: x\r\n\r\nno newline")
case("bare-lf", BASIC, msg="Subject: x\n\nline one\nline two\n")
case("lone-cr", BASIC, msg="Subject: x\r\n\r\na\rb\r\rc\r")
case("ends-with-cr", BASIC, msg="Subject: x\r\n\r\nbody\r")
case("ends-with-crlf", BASIC, msg="Subject: x\r\n\r\nbody\r\n")
case("ends-with-lf", BASIC, msg="Subject: x\r\n\r\nbody\n")
case("dots", BASIC, msg=".leading\r\n..two\r\n.\r\nmid.dle\r\n.")
case("dot-after-lf", BASIC, msg="a\n.b\n..c\n")
case("only-dot", BASIC, msg=".")
case("only-lf", BASIC, msg="\n")
case("only-crlf", BASIC, msg="\r\n")
case("utf8-body", BASIC, msg="Subject: café\r\n\r\nñandú\r\n")
case("long-body", BASIC, msg="Subject: x\r\n\r\n" + ("0123456789" * 8 + "\r\n") * 300)
case("cr-in-address", BASIC, frm="a@example.com\r\nRCPT TO:<evil@x.y>")
case("lf-in-rcpt", BASIC, rcpts=("b@example.org\nDATA",))
case("angle-in-address", BASIC, frm="<a@example.com>")
case("empty-from", BASIC, frm="")
case("no-recipients", [GREET, EHLO, OK, GO, "554 no valid recipients\r\n", BYE], rcpts=())


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "testdata/smtp.txt"
    out = []
    for name, replies, frm, rcpts, msg, auth in CASES:
        out.append("case " + name)
        for r in replies:
            out.append("reply " + b(r))
        if auth:
            out.append("auth %s %s %s" % (auth[0], b(auth[1]), b(auth[2])))
        out.append("from " + b(frm))
        for r in rcpts:
            out.append("rcpt " + b(r))
        out.append("msg " + b(msg))
        out.append("end")
    open(path, "w").write("\n".join(out) + "\n")
    print("smtp scenarios:", len(CASES))


main()
