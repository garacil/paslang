#!/usr/bin/env python3
"""A development check of pasimap against a real server, with Python's imaplib
as the second client: what testdata/imapsmoke-like runs of pasimap put in a
mailbox is read back here, and what is put here is read by pasimap.
Not part of make check (it needs a server: go-imap's imapmemserver on
127.0.0.1:9143, user/user, see docs of P433).

  python3 -I scripts/imap_python_check.py put     # APPEND three messages with imaplib
  python3 -I scripts/imap_python_check.py dump    # LIST and FETCH everything, one line each
"""
import email
import imaplib
import sys
import zlib
from email import policy

M = imaplib.IMAP4("127.0.0.1", 9143)
M.login("user", "user")
if sys.argv[1] == "put":
    for i, body in enumerate([b"Subject: one\r\n\r\nplain\r\n", b"Subject: two\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n" + "áéíóú €\r\n".encode() * 300, b"Subject: three\r\n\r\n" + bytes(range(256)) * 20]):
        typ, data = M.append("INBOX", "(\\Seen)" if i == 1 else None, None, body)
        print("append", i, typ, data)
else:
    typ, boxes = M.list()
    for b in boxes:
        print("list", b.decode())
    M.select("INBOX")
    typ, data = M.uid("search", None, "ALL")
    uids = data[0].split()
    print("uids", [int(u) for u in uids])
    for u in uids:
        typ, d = M.uid("fetch", u, "(FLAGS RFC822.SIZE BODY.PEEK[])")
        raw = d[0][1]
        print("uid", int(u), "meta", d[0][0].decode().split("{")[0].strip(), "len", len(raw), "crc", "%08x" % (zlib.crc32(raw) & 0xFFFFFFFF))
M.logout()
