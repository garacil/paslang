#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Typed JSON held to Go's v2, schema by schema (P205, P206).

Random record types with fixed seeds, in what paslang and Go both write:
integers, Booleans, strings, Doubles, arrays, records, maps of strings,
pointers, bytes and json, with the directives a name, omitempty,
omitzero, quoted, ignore, embed and unknown; random values of them. One
paslang program and one Go program are written with the same types and
values; each prints every value with JsonEncode / json.Marshal
(Deterministic), on one line and a value a line; then reads that text
back into a new value and writes it again (JsonDecode / json.Unmarshal),
reads a second text of the type, written here, into the value with
Merge (Go's own merge), and says whether a text with a member of
another kind is refused. The paslang lines must be Go's. Go's lines are kept in testdata/json/model.expect, so the check
runs where Go is not; with Go, the file is held to what Go prints now
(--update rewrites it).

  scripts/jsonmodel.py compiler build [qemu] [--update]
"""
import base64
import json
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPECT = ROOT / "testdata" / "json" / "model.expect"
SCHEMAS = 150
SEED = 205


class Field:
    def __init__(self, name, kind, elem=None, rec=None):
        self.name = name        # the Pascal and Go field name, F0...
        self.kind = kind        # int bool str float arr rec map ptr bytes json
        self.elem = elem        # arr, map: the element Field (its kind/elem/rec)
        self.rec = rec          # rec, ptr: the record's index
        self.jname = None       # a name given
        self.opts = []          # omitempty omitzero quoted ignore embed unknown


def rand_name(r):
    # no comma, backslash, quote or backquote: Go's tag reserves them
    # (v2 fields.go parseFieldOptions); jsonbind1 holds such names
    pool = ["a", "b", "x", "name", "Ünï", "é", "with space", "tab\tc", "ctl\u0001", "<&>",
            "日本", "emoji\U0001F600", "k", "dup", "zz", "_", "A1"]
    return r.choice(pool) + str(r.randrange(1000))


def gen_type(r, depth, nrec, here):
    kinds = ["int", "bool", "str", "float", "arr", "map", "bytes", "json"]
    if here + 1 < nrec:
        kinds += ["rec", "ptr"]
    if depth > 1:
        kinds = ["int", "bool", "str", "float"]
    k = r.choice(kinds)
    f = Field("", k)
    if k in ("arr", "map"):
        f.elem = gen_type(r, depth + 1, nrec, here)
    if k in ("rec", "ptr"):
        f.rec = r.randrange(here + 1, nrec)
    return f


def gen_schema(r):
    nrec = r.randint(1, 3)
    recs = []
    for i in range(nrec):
        fields = []
        names = set()
        unknown = False
        for j in range(r.randint(1, 7)):
            f = gen_type(r, 0, nrec, i)
            f.name = "F%d" % j
            roll = r.random()
            if f.kind == "rec" and roll < 0.25:
                f.opts = ["embed"]
            elif f.kind == "json" and not unknown and roll < 0.3:
                f.opts = ["unknown"]
                unknown = True
            elif roll < 0.08:
                f.opts = ["ignore"]
            else:
                if r.random() < 0.4:
                    f.jname = rand_name(r)
                if r.random() < 0.25:
                    f.opts.append("omitempty")
                if r.random() < 0.25:
                    f.opts.append("omitzero")
                if f.kind in ("int", "float") and r.random() < 0.3:
                    f.opts.append("quoted")
            fields.append(f)
        recs.append(fields)
    # JSON names unique in each record, its embedded records' included
    def names_of(i, seen):
        out = []
        for f in recs[i]:
            if "ignore" in f.opts or "unknown" in f.opts:
                continue
            if "embed" in f.opts:
                out += names_of(f.rec, seen)
                continue
            out.append(f.jname or f.name)
        return out
    for i in range(nrec - 1, -1, -1):
        while True:
            ns = names_of(i, set())
            dup = [n for n in ns if ns.count(n) > 1]
            if not dup:
                break
            for f in recs[i]:
                if (f.jname or f.name) in dup and "embed" not in f.opts:
                    f.jname = (f.jname or f.name) + "_" + str(r.randrange(10 ** 6))
                    break
            else:
                for f in recs[i]:
                    if "embed" in f.opts:
                        f.opts = []
                        break
    return recs


def gen_value(r, f, recs, depth):
    k = f.kind
    if k == "int":
        return r.choice([0, 1, -1, r.randrange(-10 ** 6, 10 ** 6),
                         r.randrange(-2 ** 63, 2 ** 63)])
    if k == "bool":
        return r.random() < 0.5
    if k == "str":
        return r.choice(["", "plain", "quote\"back\\slash", "new\nline\ttab", "ctl\u0002\u001f",
                         "ünïcödé 日本 \U0001F600", "<html>&amp;", "\u007f del", "x" * 70])
    if k == "float":
        return r.choice([0.0, 1.5, -2.25, 0.1, 1e21, 1e-7, 123456789.125, 3.0e-300,
                         r.uniform(-1e6, 1e6), float(r.randrange(-1000, 1000))])
    if k == "bytes":
        return bytes(r.randrange(256) for _ in range(r.randrange(0, 9)))
    if k == "json":
        return r.choice(['{"a":1,"b":[true,null]}', '[1,"two",3.5]', '"text"', '42', 'null',
                         '{}', '[]', '{"nested":{"k":"v"}}'])
    if k == "arr":
        if depth > 2:
            return []
        return [gen_value(r, f.elem, recs, depth + 1) for _ in range(r.randrange(0, 4))]
    if k == "map":
        if depth > 2:
            return {}
        return {rand_name(r): gen_value(r, f.elem, recs, depth + 1) for _ in range(r.randrange(0, 4))}
    if k == "rec":
        return gen_rec(r, f.rec, recs, depth + 1)
    if k == "ptr":
        if depth > 2 or r.random() < 0.3:
            return None
        return gen_rec(r, f.rec, recs, depth + 1)
    raise ValueError(k)


def gen_rec(r, i, recs, depth):
    v = {}
    for f in recs[i]:
        if "unknown" in f.opts:
            v[f.name] = r.choice(['{"u1":1,"u2":"x"}', '{}', '{"extra":[1,2]}'])
        elif r.random() < 0.2 and f.kind not in ("rec",):
            v[f.name] = zero_of(f)
        else:
            v[f.name] = gen_value(r, f, recs, depth)
    return v


def zero_of(f):
    return {"int": 0, "bool": False, "str": "", "float": 0.0, "arr": [], "map": {}, "ptr": None,
            "bytes": b"", "json": "null"}[f.kind]


# ---- the text of a value, for the decodes ----

def val_json(f, x, quoted=False):
    k = f.kind
    if k == "int":
        t = str(x)
    elif k == "float":
        t = repr(x)
    elif k == "bool":
        return "true" if x else "false"
    elif k == "str":
        return json.dumps(x, ensure_ascii=False)
    elif k == "bytes":
        return '"' + base64.b64encode(x).decode() + '"'
    elif k == "json":
        return x
    elif k == "arr":
        return "[" + ",".join(val_json(f.elem, e) for e in x) + "]"
    elif k == "map":
        return "{" + ",".join(json.dumps(a, ensure_ascii=False) + ":" + val_json(f.elem, b)
                              for a, b in x.items()) + "}"
    elif k in ("rec", "ptr"):
        if x is None:
            return "null"
        return obj_json(f.rec, x, ALL_RECS[0])
    else:
        raise ValueError(k)
    return '"' + t + '"' if quoted else t


def members_json(i, v, recs, out, ignored):
    for f in recs[i]:
        if "unknown" in f.opts:
            continue
        if "embed" in f.opts:
            members_json(f.rec, v[f.name], recs, out, ignored)
        elif "ignore" in f.opts:
            # the Go field's own name: a member no field takes
            ignored.append(f.name)
        elif "omitzero" in f.opts and (v[f.name] in (b"", []) or
                                       (f.kind == "json" and v[f.name] == "null")):
            # an empty array or bytes and a null json are nil in paslang,
            # where Go's v2 reads a slice or a Value that is not nil and
            # omitzero then writes it: such a member is left out
            continue
        else:
            out.append((f.jname if f.jname is not None else f.name,
                        val_json(f, v[f.name], "quoted" in f.opts)))


def obj_json(i, v, recs, extra=()):
    out, ignored = [], []
    members_json(i, v, recs, out, ignored)
    names = {a for a, b in out}
    out += [(n, "1") for n in dict.fromkeys(ignored) if n not in names]
    out += list(extra)
    return "{" + ",".join(json.dumps(a, ensure_ascii=False) + ":" + b for a, b in out) + "}"


ALL_RECS = [None]


def second_text(r, recs):
    """A second value of the top record, with no member a json unknown
    keeps (Go's v2 appends to its text, so a name it already has would
    be there twice) and members no field takes."""
    ALL_RECS[0] = recs
    v2 = gen_rec(r, 0, recs, 0)
    def clear(i, v):
        for f in recs[i]:
            if "unknown" in f.opts:
                v[f.name] = "{}"
            elif "embed" in f.opts:
                clear(f.rec, v[f.name])
    clear(0, v2)
    extra = [("zq_%d" % r.randrange(1000), str(r.randrange(100))) for _ in range(r.randrange(0, 3))]
    extra = list(dict(extra).items())
    return obj_json(0, v2, recs, extra)


def bad_text(r, recs, v):
    """The text of v with one member of another kind, or an array."""
    ALL_RECS[0] = recs
    fs = [f for f in recs[0] if f.kind in ("int", "bool", "str", "float") and not
          ({"ignore", "embed", "unknown"} & set(f.opts))]
    if not fs:
        return "[]"
    f = r.choice(fs)
    wrong = {"int": '"x"', "bool": "1", "str": "1", "float": '"x"'}[f.kind]
    out = []
    members_json(0, v, recs, out, [])
    name = f.jname if f.jname is not None else f.name
    out = [(a, wrong if a == name else b) for a, b in out]
    return "{" + ",".join(json.dumps(a, ensure_ascii=False) + ":" + b for a, b in out) + "}"


# ---- Pascal ----

def pas_str(s):
    """A Pascal literal of s: its characters, a control byte as #nn."""
    out = []
    lit = ""
    for ch in s:
        o = ord(ch)
        if o < 32 or o == 127:
            if lit:
                out.append("'" + lit + "'")
                lit = ""
            out.append("#%d" % o)
        elif ch == "'":
            lit += "''"
        else:
            lit += ch
    if lit or not out:
        out.append("'" + lit + "'")
    return "".join(out)


def float_lit(x):
    t = repr(x)
    if "e" in t and "." not in t.split("e")[0]:
        a, b = t.split("e")
        t = a + ".0e" + b
    if "." not in t and "e" not in t:
        t += ".0"
    return t


class PasGen:
    def __init__(self, c, recs):
        self.c = c
        self.recs = recs
        self.temps = []
        self.n = 0

    def tname(self, i):
        return "TC%dR%d" % (self.c, i)

    def ftype(self, f):
        k = f.kind
        return {"int": "Integer", "bool": "Boolean", "str": "string", "float": "Double",
                "bytes": "array of Byte", "json": "json"}.get(k) or (
            "array of " + self.ftype(f.elem) if k == "arr" else
            "map[string] of " + self.ftype(f.elem) if k == "map" else
            self.tname(f.rec) if k == "rec" else "PC%dR%d" % (self.c, f.rec))

    def types(self):
        out = []
        for i in range(len(self.recs) - 1, -1, -1):
            out.append("  %s = record" % self.tname(i))
            for f in self.recs[i]:
                d = ""
                if f.jname is not None or f.opts:
                    d = " json"
                    if f.jname is not None:
                        d += " " + pas_str(f.jname)
                    for o in f.opts:
                        d += " " + o
                out.append("    %s: %s%s;" % (f.name, self.ftype(f), d))
            out.append("  end;")
            out.append("  PC%dR%d = ^%s;" % (self.c, i, self.tname(i)))
        return out

    def temp(self, typ):
        self.n += 1
        nm = "c%dt%d" % (self.c, self.n)
        self.temps.append((nm, typ))
        return nm

    def val(self, f, v, stm):
        k = f.kind
        if k == "int":
            return str(v) if v != -2 ** 63 else "(-9223372036854775807 - 1)"
        if k == "bool":
            return "True" if v else "False"
        if k == "str":
            return pas_str(v)
        if k == "float":
            return float_lit(v)
        if k == "json":
            return "JsonParse(%s)" % pas_str(v)
        if k == "bytes":
            t = self.temp("array of Byte")
            stm.append("SetLength(%s, %d);" % (t, len(v)))
            for i, b in enumerate(v):
                stm.append("%s[%d] := %d;" % (t, i, b))
            return t
        if k == "arr":
            t = self.temp(self.ftype(f))
            stm.append("SetLength(%s, %d);" % (t, len(v)))
            for i, e in enumerate(v):
                stm.append("%s[%d] := %s;" % (t, i, self.val(f.elem, e, stm)))
            return t
        if k == "map":
            t = self.temp(self.ftype(f))
            stm.append("New(%s);" % t)
            for key, e in v.items():
                stm.append("%s[%s] := %s;" % (t, pas_str(key), self.val(f.elem, e, stm)))
            return t
        if k == "rec":
            return self.rec(f.rec, v, stm)
        if k == "ptr":
            if v is None:
                return "nil"
            t = self.temp("PC%dR%d" % (self.c, f.rec))
            r = self.rec(f.rec, v, stm)
            stm.append("New(%s);" % t)
            stm.append("%s^ := %s;" % (t, r))
            return t
        raise ValueError(k)

    def rec(self, i, v, stm):
        t = self.temp(self.tname(i))
        for f in self.recs[i]:
            stm.append("%s.%s := %s;" % (t, f.name, self.val(f, v[f.name], stm)))
        return t


# ---- Go ----

def go_str(s):
    out = '"'
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out += '\\"'
        elif ch == "\\":
            out += "\\\\"
        elif o < 32 or o == 127:
            out += "\\x%02x" % o
        else:
            out += ch
    return out + '"'


class GoGen:
    def __init__(self, c, recs):
        self.c = c
        self.recs = recs

    def tname(self, i):
        return "C%dR%d" % (self.c, i)

    def ftype(self, f):
        k = f.kind
        return {"int": "int64", "bool": "bool", "str": "string", "float": "float64",
                "bytes": "[]byte", "json": "jsontext.Value"}.get(k) or (
            "[]" + self.ftype(f.elem) if k == "arr" else
            "map[string]" + self.ftype(f.elem) if k == "map" else
            self.tname(f.rec) if k == "rec" else "*" + self.tname(f.rec))

    def types(self):
        out = []
        for i, fs in enumerate(self.recs):
            out.append("type %s struct {" % self.tname(i))
            for f in fs:
                if "ignore" in f.opts:
                    tag = "-"
                else:
                    tag = f.jname if f.jname is not None else ""
                    for o in f.opts:
                        # Go's string; Go's embed on a jsontext.Value is
                        # paslang's unknown, an embedded fallback (fields.go)
                        tag += "," + {"quoted": "string", "unknown": "embed"}.get(o, o)
                if tag == "":
                    out.append("\t%s %s" % (f.name, self.ftype(f)))
                else:
                    out.append("\t%s %s `json:%s`" % (f.name, self.ftype(f), go_str(tag)))
            out.append("}")
        return out

    def val(self, f, v):
        k = f.kind
        if k == "int":
            return "int64(%d)" % v if v != -2 ** 63 else "math.MinInt64"
        if k == "bool":
            return "true" if v else "false"
        if k == "str":
            return go_str(v)
        if k == "float":
            return "float64(%s)" % repr(v)
        if k == "json":
            # paslang's null json is nil, its zero: Go's nil Value
            if v == "null":
                return "jsontext.Value(nil)"
            return "jsontext.Value(%s)" % go_str(v)
        # an empty dynamic array of paslang is nil: Go's nil slice, not []T{}
        if k == "bytes":
            if not v:
                return "[]byte(nil)"
            return "[]byte{%s}" % ", ".join(str(b) for b in v)
        if k == "arr":
            if not v:
                return "%s(nil)" % self.ftype(f)
            return "%s{%s}" % (self.ftype(f), ", ".join(self.val(f.elem, e) for e in v))
        if k == "map":
            return "%s{%s}" % (self.ftype(f), ", ".join("%s: %s" % (go_str(a), self.val(f.elem, b))
                                                       for a, b in v.items()))
        if k == "rec":
            return self.rec(f.rec, v)
        if k == "ptr":
            if v is None:
                return "nil"
            return "&" + self.rec(f.rec, v)
        raise ValueError(k)

    def rec(self, i, v):
        return "%s{%s}" % (self.tname(i), ", ".join("%s: %s" % (f.name, self.val(f, v[f.name]))
                                                     for f in self.recs[i]))


def build_sources():
    r = random.Random(SEED)
    pas_types, pas_body, pas_vars = [], [], []
    go_types, go_body = [], []
    for c in range(SCHEMAS):
        recs = gen_schema(r)
        v = gen_rec(r, 0, recs, 0)
        pg = PasGen(c, recs)
        pas_types += pg.types()
        stm = []
        top = pg.rec(0, v, stm)
        pas_vars += ["  %s: %s;" % (n, t) for n, t in pg.temps]
        pas_body += stm
        pas_body.append("WriteLn(JsonEncode(%s));" % top)
        pas_body.append("WriteLn(JsonEncode(%s, JsonPretty));" % top)
        # the decodes' texts from a generator of their own, so the schemas
        # and values stay P205's
        r2 = random.Random(SEED * 1000 + c)
        text2 = second_text(r2, recs)
        bad = bad_text(r2, recs, v)
        pas_vars += ["  c%dw, c%dm: %s;" % (c, c, pg.tname(0))]
        pas_body.append("JsonDecode(JsonEncode(%s), c%dw);" % (top, c))
        pas_body.append("WriteLn(JsonEncode(c%dw));" % c)
        pas_body.append("c%dm := %s;" % (c, top))
        pas_body.append("JsonDecode(%s, c%dm, mopts);" % (pas_str(text2), c))
        pas_body.append("WriteLn(JsonEncode(c%dm));" % c)
        pas_body.append("if TryJsonDecode(%s, c%dw, err) then WriteLn('ok') else WriteLn('error');" %
                        (pas_str(bad), c))
        gg = GoGen(c, recs)
        go_types += gg.types()
        go_body.append("\t{")
        go_body.append("\t\tv := %s" % gg.rec(0, v))
        go_body.append("\t\tshow(v)")
        go_body.append("\t\trt(v)")
        go_body.append("\t\tmg(v, %s)" % go_str(text2))
        go_body.append("\t\tbad[%s](%s)" % (gg.tname(0), go_str(bad)))
        go_body.append("\t}")
    pas = ["{ written by scripts/jsonmodel.py (P205, P206) }", "program jsonmodel;", "type"]
    pas += pas_types + ["var", "  mopts: TJsonOptions;", "  err: EJsonError;"] + pas_vars
    pas += ["begin", "mopts := JsonDefaults;", "mopts.Merge := True;"] + pas_body + ["end."]
    go = ["// written by scripts/jsonmodel.py (P205, P206)", "package main", "", "import (",
          '\t"encoding/json/jsontext"', '\t"encoding/json/v2"', '\t"fmt"', '\t"math"', ")", "",
          "var _ = math.MinInt64", ""]
    go += go_types
    go += ["", "func show(v any) {",
           "\tb, err := json.Marshal(v, json.Deterministic(true))",
           "\tif err != nil {", "\t\tpanic(err)", "\t}", "\tfmt.Println(string(b))",
           '\tb, err = json.Marshal(v, json.Deterministic(true), jsontext.WithIndent("  "))',
           "\tif err != nil {", "\t\tpanic(err)", "\t}", "\tfmt.Println(string(b))", "}", "",
           "func line(v any) {",
           "\tb, err := json.Marshal(v, json.Deterministic(true))",
           "\tif err != nil {", "\t\tpanic(err)", "\t}", "\tfmt.Println(string(b))", "}", "",
           "func rt[T any](v T) {",
           "\tb, err := json.Marshal(v, json.Deterministic(true))",
           "\tif err != nil {", "\t\tpanic(err)", "\t}",
           "\tvar w T",
           "\tif err := json.Unmarshal(b, &w); err != nil {", "\t\tpanic(err)", "\t}",
           "\tline(w)", "}", "",
           "func mg[T any](v T, s string) {",
           "\tw := v",
           "\tif err := json.Unmarshal([]byte(s), &w); err != nil {", "\t\tpanic(err)", "\t}",
           "\tline(w)", "}", "",
           "func bad[T any](s string) {",
           "\tvar w T",
           "\tif err := json.Unmarshal([]byte(s), &w); err != nil {",
           '\t\tfmt.Println("error")', "\t} else {", '\t\tfmt.Println("ok")', "\t}", "}", "",
           "func main() {"] + go_body + ["}"]
    return "\n".join(pas) + "\n", "\n".join(go) + "\n"


def run_go(work, src):
    go = shutil.which("go")
    if not go:
        return None
    d = work / "go"
    d.mkdir(exist_ok=True)
    (d / "main.go").write_text(src)
    env = dict(os.environ, GOCACHE=str(work / "gocache"), GOFLAGS="-mod=mod",
               HOME=os.environ.get("HOME", str(work)))
    if not (d / "go.mod").exists():
        subprocess.run([go, "mod", "init", "jsonmodel"], cwd=d, env=env, check=True,
                       capture_output=True)
    p = subprocess.run([go, "run", "."], cwd=d, env=env, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit("go: " + p.stderr[-3000:])
    return p.stdout


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    update = "--update" in sys.argv
    compiler, build = Path(args[0]).resolve(), Path(args[1]).resolve()
    qemu = args[2:]
    work = build / "jsonmodel"
    work.mkdir(parents=True, exist_ok=True)
    pas, go = build_sources()
    (work / "jsonmodel.paslang").write_text(pas)
    want = run_go(work, go)
    if want is not None:
        if update:
            EXPECT.write_text(want)
        elif not EXPECT.exists() or EXPECT.read_text() != want:
            sys.exit("testdata/json/model.expect is not what Go prints: scripts/jsonmodel.py "
                     "--update rewrites it")
    else:
        want = EXPECT.read_text()
    targets = [("amd64", [], [])]
    if qemu:
        targets.append(("arm64", ["-target", "arm64", "-Fu", str(build / "a64")], qemu))
    for name, flags, runner in targets:
        exe = work / ("jsonmodel-" + name)
        subprocess.run([str(compiler)] + flags + ["-o", str(exe), str(work / "jsonmodel.paslang")],
                       cwd=ROOT, check=True)
        p = subprocess.run(runner + [str(exe)], capture_output=True, text=True, timeout=300)
        if p.returncode != 0:
            sys.exit("jsonmodel %s exited %d: %s" % (name, p.returncode, p.stderr[-2000:]))
        got = p.stdout
        if got != want:
            gl, wl = got.split("\n"), want.split("\n")
            for i in range(max(len(gl), len(wl))):
                g = gl[i] if i < len(gl) else "<none>"
                w = wl[i] if i < len(wl) else "<none>"
                if g != w:
                    sys.exit("jsonmodel %s line %d:\n  paslang %s\n  Go      %s" % (name, i + 1, g, w))
    print("ok jsonmodel (%d schemas held to Go's v2: written compact and a value a line, read "
          "back, merged and refused%s)" % (SCHEMAS, ", amd64 and arm64" if qemu else ""))


if __name__ == "__main__":
    main()
