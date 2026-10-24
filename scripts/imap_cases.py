#!/usr/bin/env python3
"""testdata/imap.txt: the scenarios of the IMAP client test. A scenario is a
script for a server (the greeting, then what it sends for each command the
client completes, a "+" first for a literal that waits; an item that starts
with ! is sent at once after the one before it) and the operations the client
runs one after the other (login, select, fetch...). testdata/imap.paslang runs
them against pasimap with a server of its own over TCP on 127.0.0.1 and prints
what the server received (S:) and what each operation gave (R:). The server
texts are the examples of RFC 3501 section 8 and what go-imap's server (the
oracle of development) and Python's imaplib were seen to send and take.

Run: python3 -I scripts/imap_cases.py testdata/imap.txt
"""
import base64
import sys


def b(x):
    if isinstance(x, str):
        x = x.encode("utf-8", "surrogateescape")
    return base64.b64encode(x).decode() if x else "-"


SC = []
CAPS = "IMAP4rev1 LITERAL+ SASL-IR UIDPLUS MOVE IDLE ENABLE UNSELECT CHILDREN NAMESPACE AUTH=PLAIN"


class Sc:
    def __init__(self, name, greeting="* OK [CAPABILITY %s] ready\r\n" % CAPS):
        self.name = name
        self.items = [greeting]
        self.ops = []
        self.n = 1
        SC.append(self)

    def op(self, name, args, replies, tags=1):
        """replies use {t} for the tag of the command"""
        t = "A%d" % self.n
        self.ops.append((name, args))
        for r in replies:
            self.items.append(r.replace("{t}", t))
        self.n += tags
        return self

    def raw(self, items):
        self.items += items
        return self


def Z(s):
    return s


# ---- greeting, capability, login ----
s = Sc("login-list-select")
s.op("login", ["user", "pa ss"], ["{t} OK [CAPABILITY IMAP4rev1 LITERAL+ UIDPLUS MOVE IDLE] Logged in\r\n"])
s.op("list", ["", "*"], [
    '* LIST () "/" "Archive"\r\n* LIST (\\Subscribed) "/" "Drafts"\r\n* LIST (\\Subscribed) "/" INBOX\r\n'
    '* LIST (\\HasNoChildren) "/" "Pap&AOk-les &- m&AOE-s"\r\n* LIST (\\Noselect \\HasChildren) NIL {5}\r\nTrash\r\n'
    '* LIST () "." "[Gmail]/Sent Mail"\r\n* LIST () "/" [Gmail]/Drafts\r\n{t} OK LIST completed\r\n'])
s.op("select", ["INBOX", "0"], [
    "* 18 EXISTS\r\n* 2 RECENT\r\n* OK [UNSEEN 17] Message 17 is the first unseen\r\n* OK [UIDVALIDITY 3857529045] UIDs valid\r\n"
    "* OK [UIDNEXT 4392] Predicted next UID\r\n* FLAGS (\\Answered \\Flagged \\Deleted \\Seen \\Draft)\r\n"
    "* OK [PERMANENTFLAGS (\\Deleted \\Seen \\*)] Limited\r\n{t} OK [READ-WRITE] SELECT completed\r\n"])
s.op("status", ["INBOX"], ['* STATUS INBOX (MESSAGES 18 UIDNEXT 4392 UIDVALIDITY 3857529045 UNSEEN 1 RECENT 2)\r\n{t} OK STATUS completed\r\n'])
s.op("noop", [], ["* 19 EXISTS\r\n* 3 RECENT\r\n{t} OK NOOP completed\r\n"])
s.op("logout", [], ["* BYE IMAP4rev1 Server logging out\r\n{t} OK LOGOUT completed\r\n"])

s = Sc("no-caps-in-greeting", greeting="* OK IMAP ready\r\n")
s.op("caps", [], ["* CAPABILITY IMAP4rev1 STARTTLS AUTH=PLAIN X-GM-EXT-1\r\nA1 OK CAPABILITY completed\r\n"], tags=1)
s.ops = []  # the client asks by itself, as A1
s.n = 2
s.op("login", ["u", "p"], ["{t} OK Logged in\r\n"])
s.op("caps", [], [], tags=0)

s = Sc("login-refused")
s.op("login", ["user", "wrong"], ["{t} NO [AUTHENTICATIONFAILED] Authentication failed.\r\n"])
s.op("login", ["user", "again"], ["{t} BAD Unknown command\r\n"])
s.op("noop", [], ["* BYE Too many failed attempts\r\n{t} NO closed\r\n"])

s = Sc("login-special-chars")
s.op("login", ['us"er', 'p\\w"d'], ["{t} OK Logged in\r\n"])
s.op("login", ["", ""], ["{t} OK Logged in\r\n"])
s.op("login", ["user", "line\r\nbreak"], ["{t} OK Logged in\r\n"])
s.op("login", ["us\u00e9r", "p\u00e1ss"], ["{t} OK Logged in\r\n"])
s = Sc("login-literal-wait", greeting="* OK [CAPABILITY IMAP4rev1] ready\r\n")
s.op("login", ["user", "two\nlines"], ["+ Ready for literal data\r\n", "{t} OK Logged in\r\n"])
s.op("login", ["u\u00e9", "x"], ["+ go\r\n", "{t} OK Logged in\r\n"])
s.op("login", ["a", "b\nc"], ["{t} NO [ALERT] no literals here\r\n"])

s = Sc("login-disabled", greeting="* OK [CAPABILITY IMAP4rev1 STARTTLS LOGINDISABLED] ready\r\n")
s.op("login", ["user", "pw"], [], tags=0)

s = Sc("preauth", greeting="* PREAUTH [CAPABILITY IMAP4rev1 IDLE] Logged in as someone\r\n")
s.op("caps", [], [], tags=0)
s.op("select", ["INBOX", "1"], ["* 0 EXISTS\r\n* OK [UIDVALIDITY 1] v\r\n* OK [UIDNEXT 1] n\r\n{t} OK [READ-ONLY] EXAMINE completed\r\n"])

s = Sc("greeting-bye", greeting="* BYE [ALERT] Too many connections\r\n")
s = Sc("greeting-garbage", greeting="HTTP/1.1 400 Bad Request\r\n")
s = Sc("greeting-eof", greeting="")
s.items = []
s = Sc("greeting-unsolicited-tagged", greeting="A0 OK hi\r\n")

# ---- authenticate ----
s = Sc("plain-sasl-ir")
s.op("plain", ["me", "secret"], ["{t} OK [CAPABILITY IMAP4rev1] Authenticated\r\n"])
s = Sc("plain-continued", greeting="* OK [CAPABILITY IMAP4rev1 AUTH=PLAIN] ready\r\n")
s.op("plain", ["me", "secret"], ["+ \r\n", "{t} OK Authenticated\r\n"])
s = Sc("plain-refused", greeting="* OK [CAPABILITY IMAP4rev1 AUTH=PLAIN] ready\r\n")
s.op("plain", ["me", "bad"], ["+ \r\n", "{t} NO [AUTHENTICATIONFAILED] Invalid credentials\r\n"])
s = Sc("xoauth2-ok")
s.op("xoauth", ["me@example.com", "ya29.token"], ["{t} OK Authenticated\r\n"])
s = Sc("xoauth2-error-challenge")
s.op("xoauth", ["me@example.com", "stale"], ["+ eyJzdGF0dXMiOiI0MDAiLCJzY2hlbWVzIjoiYmVhcmVyIn0=\r\n", "{t} NO [AUTHENTICATIONFAILED] Invalid credentials (Failure)\r\n"])
s = Sc("challenge-unexpected")
s.op("login", ["u", "p"], ["+ surprise\r\n", "{t} BAD cancelled\r\n"])

# ---- search and fetch ----
HDR = "Date: Tue, 14 Nov 2023 23:13:20 +0100\r\nFrom: Ana <ana@example.com>\r\nSubject: Hola\r\n\r\n"
BODY1 = HDR + "cuerpo\r\n"
BODY2 = "Subject: dos\r\n\r\n" + "x" * 40 + "\r\n"
s = Sc("search")
s.op("search", ["ALL"], ["* SEARCH 2 84 882\r\n{t} OK UID SEARCH completed\r\n"])
s.op("search", ['SUBJECT "ab"'], ["* SEARCH\r\n{t} OK UID SEARCH completed\r\n"])
s.op("search", ["UNSEEN"], ["* SEARCH 5\r\n* SEARCH 7 8\r\n{t} OK done\r\n"])
s.op("search", ["BAD"], ["{t} BAD [CLIENTBUG] Could not parse command\r\n"])

s = Sc("fetch-bodies")
s.op("fetch", ["1:2", "(UID FLAGS RFC822.SIZE INTERNALDATE BODY.PEEK[])"], [
    "* 1 FETCH (UID 11 FLAGS (\\Seen \\Answered $Forwarded) RFC822.SIZE %d INTERNALDATE \"17-Jul-1996 02:44:25 -0700\" BODY[] {%d}\r\n%s)\r\n" % (len(BODY1), len(BODY1), BODY1)
    + "* 2 FETCH (UID 12 FLAGS () INTERNALDATE \" 7-Jul-2026 10:00:00 +0000\" BODY[] {%d}\r\n%s RFC822.SIZE %d)\r\n" % (len(BODY2), BODY2, len(BODY2))
    + "{t} OK UID FETCH completed\r\n"])
s.op("fetch", ["11", "(BODY.PEEK[HEADER] BODY.PEEK[TEXT])"], [
    "* 1 FETCH (UID 11 BODY[HEADER] {%d}\r\n%s BODY[TEXT] {8}\r\ncuerpo\r\n)\r\n{t} OK done\r\n" % (len(HDR), HDR)])
s.op("fetch", ["11", "(RFC822.HEADER RFC822.TEXT RFC822)"], [
    "* 1 FETCH (UID 11 RFC822.HEADER {%d}\r\n%s RFC822.TEXT \"short\" RFC822 {%d}\r\n%s)\r\n{t} OK done\r\n" % (len(HDR), HDR, len(BODY1), BODY1)])
s.op("fetch", ["999", "(BODY.PEEK[])"], ["{t} OK UID FETCH completed (nothing)\r\n"])
s.op("fetchraw", ["11"], ["* 1 FETCH (UID 11 BODY[] {%d}\r\n%s)\r\n{t} OK done\r\n" % (len(BODY1), BODY1)])
s.op("fetchraw", ["12"], ["{t} OK nothing\r\n"])

s = Sc("fetch-shapes")
s.op("fetch", ["1:*", "(UID FLAGS BODY.PEEK[1.2]<0> BODYSTRUCTURE X-GM-MSGID)"], [
    '* 1 FETCH (X-GM-MSGID 1278455344230334865 UID 5 FLAGS (\\Seen) BODY[1.2]<0> NIL BODYSTRUCTURE (("text" "plain" ("charset" "utf-8") NIL NIL "quoted-printable" 24 2 NIL NIL NIL NIL)("application" "octet-stream" ("name" "a\\"b.bin") NIL NIL "base64" 12 NIL ("attachment" ("filename" "a\\"b.bin")) NIL NIL) "mixed" ("boundary" "xx") NIL NIL NIL))\r\n'
    '* 2 FETCH (UID 6 BODY[1.2]<0> {0}\r\n FLAGS ())\r\n'
    '* 3 FETCH (UID 7 BODY[] "quoted \\"text\\" with \\\\ backslash")\r\n'
    '* 4 FETCH (UID 8 FLAGS (\\Seen \\*) BODY[HEADER.FIELDS (SUBJECT FROM)] {12}\r\nSubject: x\r\n)\r\n'
    '{t} OK UID FETCH completed\r\n'])

s = Sc("fetch-unsolicited")
s.op("fetch", ["3", "(UID FLAGS)"], [
    "* 5 EXISTS\r\n* 1 FETCH (FLAGS (\\Seen))\r\n* 2 EXPUNGE\r\n* 3 FETCH (UID 33 FLAGS (\\Flagged))\r\n* OK [ALERT] attention\r\n{t} OK Fetch done\r\n"])
s.op("state", [], [], tags=0)

s = Sc("envelope")
ENV1 = ('* 1 FETCH (UID 1 ENVELOPE ("Mon, 7 Feb 1994 21:52:25 -0800" "=?UTF-8?Q?Se=C3=B1or_Garc=C3=ADa?=" '
        '(("Fred Foobar" NIL "foobar" "Blurdybloop.example")) (("Fred Foobar" NIL "foobar" "Blurdybloop.example")) (("Fred Foobar" NIL "foobar" "Blurdybloop.example")) '
        '((NIL NIL "mooch" "owatagu.siam.example")) NIL NIL NIL "<B27397-0100000@Blurdybloop.example>"))\r\n')
ENV2 = ('* 2 FETCH (UID 2 ENVELOPE (NIL NIL ((NIL NIL "group" NIL)("=?utf-8?q?Jos=C3=A9?=" NIL "jose" "example.org")(NIL NIL NIL NIL)) '
        'NIL NIL (("A" "@route" "a" "b.c") ("B" NIL "b" NIL)) (("Cc" NIL "cc" "x.y")) (("Bcc" NIL "bcc" "x.y")) "<prev@x>" NIL))\r\n')
s.op("env", ["1:2"], [ENV1 + ENV2 + "{t} OK done\r\n"])
s.op("env", ["3"], ["* 3 FETCH (UID 3 FLAGS ())\r\n* 4 FETCH (UID 4 ENVELOPE (NIL NIL))\r\n{t} OK done\r\n"])

s = Sc("search-with")
s.op("searchwith", ["CHARSET UTF-8 SUBJECT %s SINCE 1-Oct-2026 FROM %s", "Factura n\u00famero", "ana@example.com"], ["* SEARCH 4 9\r\n{t} OK UID SEARCH completed\r\n"])
s.op("searchwith", ["TEXT %s", 'say "hi"\\'], ["* SEARCH\r\n{t} OK UID SEARCH completed\r\n"])
s.op("searchwith", ["TEXT %s %s", "one"], [], tags=0)
s.op("searchwith", ["ALL"], ["* SEARCH 1\r\n{t} OK done\r\n"])
s = Sc("search-with-wait", greeting="* OK [CAPABILITY IMAP4rev1] ready\r\n")
s.op("searchwith", ["CHARSET UTF-8 SUBJECT %s", "a\nb"], ["+ go\r\n", "* SEARCH 3\r\n{t} OK UID SEARCH completed\r\n"])
s = Sc("line-break-in-command")
s.op("store", ["1", "+FLAGS", "(\\Seen)\r\nA9 DELETE INBOX"], [], tags=0)
s.op("fetch", ["1\n2", "(UID)"], [], tags=0)
s.op("noop", [], ["{t} OK still alive\r\n"])

# ---- store, expunge, copy, move, append ----
s = Sc("store-expunge-copy")
s.op("store", ["1:3", "+FLAGS", "(\\Deleted)"], ["* 1 FETCH (UID 1 FLAGS (\\Deleted))\r\n* 2 FETCH (UID 2 FLAGS (\\Deleted))\r\n{t} OK STORE completed\r\n"])
s.op("expunge", [], ["* 1 EXPUNGE\r\n* 1 EXPUNGE\r\n* 5 EXISTS\r\n{t} OK EXPUNGE completed\r\n"])
s.op("copy", ["4:5", "Archive/2026"], ["{t} OK [COPYUID 1 4:5 1:2] COPY completed\r\n"])
s.op("copy", ["4", "Nowhere"], ["{t} NO [TRYCREATE] Mailbox doesn't exist\r\n"])
s.op("move", ["4", "Trash"], ["* OK [COPYUID 1 4 9] Moved\r\n* 3 EXPUNGE\r\n{t} OK Move completed\r\n"])
s = Sc("move-fallback", greeting="* OK [CAPABILITY IMAP4rev1 UIDPLUS] ready\r\n")
s.op("move", ["4,6:8", "Trash"], ["{t} OK [COPYUID 1 4,6:8 1:4] COPY completed\r\n", "A2 OK STORE completed\r\n", "A3 OK UID EXPUNGE completed\r\n"], tags=3)
s = Sc("move-fallback-plain-expunge", greeting="* OK [CAPABILITY IMAP4rev1] ready\r\n")
s.op("move", ["4"], ["{t} OK copied\r\n", "A2 OK stored\r\n", "A3 OK expunged\r\n"], tags=3)
s.ops = [("move", ["4", "Trash"])]

SMALL = "Subject: small\r\n\r\nhi\r\n"
BIG = "Subject: big\r\n\r\n" + ("0123456789" * 8 + "\r\n") * 60
s = Sc("append-literal-plus")
s.op("append", ["INBOX", "(\\Seen)", SMALL], ["{t} OK [APPENDUID 38505 3955] APPEND completed\r\n"])
s.op("append", ["Sent Items", "", BIG], ["{t} OK [APPENDUID 1 77] APPEND completed\r\n"])
s.op("append", ["Drafts", "", ""], ["{t} OK APPEND completed\r\n"])
s = Sc("append-literal-sync", greeting="* OK [CAPABILITY IMAP4rev1] ready\r\n")
s.op("append", ["INBOX", "(\\Seen \\Draft)", SMALL], ["+ Ready for literal data\r\n", "{t} OK [APPENDUID 38505 3955] APPEND completed\r\n"])
s.op("append", ["Papel\u00e9s", "", BIG], ["+ go ahead\r\n", "{t} OK APPEND completed\r\n"])
s.op("append", ["Missing", "", SMALL], ["{t} NO [TRYCREATE] Mailbox doesn't exist: Missing\r\n"])
s = Sc("append-literal-minus", greeting="* OK [CAPABILITY IMAP4rev1 LITERAL-] ready\r\n")
s.op("append", ["INBOX", "", SMALL], ["{t} OK APPEND completed\r\n"])
s.op("append", ["INBOX", "", "Subject: x\r\n\r\n" + "y" * 5000], ["+ Ready\r\n", "{t} OK APPEND completed\r\n"])
s = Sc("append-refused-before-literal", greeting="* OK [CAPABILITY IMAP4rev1] ready\r\n")
s.op("append", ["INBOX", "", SMALL], ["{t} NO [OVERQUOTA] Quota exceeded\r\n"])
s.op("append", ["INBOX", "", SMALL], ["{t} OK APPEND completed with no literal wait\r\n"])

s = Sc("mailbox-commands")
s.op("create", ["Archive/2026"], ["{t} OK CREATE completed\r\n"])
s.op("create", ["Caf\u00e9 & T\u00e9"], ["{t} OK CREATE completed\r\n"])
s.op("create", ["\u65e5\u672c\u8a9e/\U0001F600"], ["{t} OK CREATE completed\r\n"])
s.op("create", ["INBOX"], ["{t} NO [ALREADYEXISTS] Mailbox already exists\r\n"])
s.op("delete", ["Old"], ["{t} OK DELETE completed\r\n"])
s.op("rename", ["Old", "New Name"], ["{t} OK RENAME completed\r\n"])
s.op("subscribe", ["Archive/2026"], ["{t} OK SUBSCRIBE completed\r\n"])
s.op("unsubscribe", ["Archive/2026"], ["{t} OK UNSUBSCRIBE completed\r\n"])
s.op("close", [], ["{t} OK CLOSE completed\r\n"])
s.op("select", ["inbox", "0"], ["* 1 EXISTS\r\n{t} OK [READ-WRITE] done\r\n"])
s.op("select", ["Nope", "0"], ["{t} NO [NONEXISTENT] Unknown Mailbox: Nope\r\n"])
s.op("status", ["Caf\u00e9"], ['* STATUS "Caf&AOk-" (MESSAGES 3 UIDNEXT 9)\r\n{t} OK STATUS completed\r\n'])

# ---- IDLE ----
s = Sc("idle")
s.op("idle", ["3000"], ["+ idling\r\n", "!* 4 EXISTS\r\n", "{t} OK IDLE terminated\r\n"])
s.op("idle", ["100"], ["+ idling\r\n", "{t} OK IDLE terminated\r\n"])
s.op("idle", ["3000"], ["+ idling\r\n", "!* 2 EXPUNGE\r\n", "!* 1 FETCH (FLAGS (\\Seen))\r\n", "{t} OK IDLE terminated\r\n"])
s.op("idle", ["100"], ["{t} NO [UNAVAILABLE] try later\r\n"])
s = Sc("idle-unsupported", greeting="* OK [CAPABILITY IMAP4rev1] ready\r\n")
s.op("idle", ["100"], [], tags=0)

# ---- failures of the connection and of the grammar ----
s = Sc("bye-in-command")
s.op("noop", [], ["* BYE Autologout; idle for too long\r\n"], tags=0)
s = Sc("eof-after-command")
s.op("noop", [], [], tags=0)
s = Sc("wrong-tag")
s.op("noop", [], ["A9 OK whoever\r\n"], tags=0)
s = Sc("bad-lines")
s.op("noop", [], ["\r\n"], tags=0)
s = Sc("bad-lines-2")
s.op("noop", [], ["A1\r\n"], tags=0)
s = Sc("bad-lines-3")
s.op("noop", [], ["A1 MAYBE what\r\n"], tags=0)
s = Sc("unclosed-list")
s.op("fetch", ["1", "(UID)"], ["* 1 FETCH (UID 1 FLAGS (\\Seen\r\n{t} OK done\r\n"], tags=0)
s = Sc("unclosed-quote")
s.op("fetch", ["1", "(UID)"], ['* 1 FETCH (UID 1 BODY[] "abc\r\n{t} OK done\r\n'], tags=0)
s = Sc("bad-literal")
s.op("fetch", ["1", "(UID)"], ["* 1 FETCH (UID 1 BODY[] {12x}\r\n{t} OK done\r\n"], tags=0)
s = Sc("huge-literal")
s.op("fetch", ["1", "(UID)"], ["* 1 FETCH (UID 1 BODY[] {99999999999}\r\n{t} OK done\r\n"], tags=0)
s = Sc("short-literal")
s.op("fetch", ["1", "(UID)"], ["* 1 FETCH (UID 1 BODY[] {50}\r\nonly a few bytes"], tags=0)
s = Sc("continuation-after-command")
s.op("noop", [], ["+ idle?\r\n", "{t} OK NOOP completed\r\n"])


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "testdata/imap.txt"
    out = []
    for sc in SC:
        out.append("case " + sc.name)
        for it in sc.items:
            out.append("reply " + b(it))
        for name, args in sc.ops:
            out.append("op %s %s" % (name, " ".join(b(a) for a in args)) if args else "op " + name)
        out.append("end")
    open(path, "w").write("\n".join(out) + "\n")
    print("imap scenarios:", len(SC))


main()
