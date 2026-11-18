#!/usr/bin/env python3
"""Check reviewed select-child traversal contracts against compiler source.

The lexer excludes comments and strings from executable-token matching. The
schema comes from pasast, each checked call is bound to one typed child and
its complete Sels loop, and rewrites must assign back to the same child.
Token seals deliberately require review after control-flow changes; this is
not a proof of Pascal execution semantics. Runtime regression tests and
compiler visitor-removal mutants remain separate checks.
"""
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

UNITS = ("pasparse", "pasopt", "pasemit")
ROUTINE = {"function", "procedure", "constructor", "destructor", "operator"}
WORD = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|[0-9]+|:=|<>|<=|>=|\.\.")


class Invalid(ValueError):
    pass


@dataclass(frozen=True)
class Token:
    value: str
    line: int
    column: int


def lex(source):
    tokens = []
    pos = 0
    line = column = 1
    while pos < len(source):
        start = pos
        char = source[pos]
        if char.isspace():
            pos += 1
        elif source.startswith("//", pos):
            stop = source.find("\n", pos)
            pos = len(source) if stop < 0 else stop
        elif source.startswith("{$", pos) or source.startswith("(*$", pos):
            # Directives can hide a visit from the compiler. Never erase them
            # as comments while keeping the inactive call in a reviewed seal.
            raise Invalid(f"compiler directive requires traversal review at {line}:{column}")
        elif char == "{" or source.startswith("(*", pos):
            stack = ["}" if char == "{" else "*)"]
            pos += 1 if char == "{" else 2
            while stack:
                if pos >= len(source):
                    raise Invalid(f"unterminated comment at {line}:{column}")
                if source.startswith(stack[-1], pos):
                    pos += len(stack.pop())
                elif source[pos] == "{":
                    stack.append("}")
                    pos += 1
                elif source.startswith("(*", pos):
                    stack.append("*)")
                    pos += 2
                else:
                    pos += 1
        elif char == "'":
            pos += 1
            while True:
                if pos >= len(source):
                    raise Invalid(f"unterminated string at {line}:{column}")
                if source[pos] == "'":
                    pos += 1
                    if pos < len(source) and source[pos] == "'":
                        pos += 1
                    else:
                        break
                else:
                    pos += 1
            # A string stays a single opaque token, never executable names.
            tokens.append(Token(source[start:pos], line, column))
        else:
            match = WORD.match(source, pos)
            pos += len(match[0]) if match else 1
            tokens.append(Token(source[start:pos].lower(), line, column))
        span = source[start:pos]
        if "\n" in span:
            line += span.count("\n")
            column = len(span.rsplit("\n", 1)[1]) + 1
        else:
            column += len(span)
    return tokens


def values(tokens):
    return [token.value for token in tokens]


def seal(tokens):
    return hashlib.sha256(json.dumps(values(tokens), ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def close(tokens, start):
    ends = {"(": ")", "[": "]"}
    stack = [ends[tokens[start].value]]
    for pos in range(start + 1, len(tokens)):
        value = tokens[pos].value
        if value in ends:
            stack.append(ends[value])
        elif value in (")", "]"):
            if not stack or value != stack.pop():
                raise Invalid("unbalanced delimiters")
            if not stack:
                return pos
    raise Invalid("unclosed delimiter")


def chunks(tokens, separator):
    start = pos = 0
    while pos < len(tokens):
        value = tokens[pos].value
        if value in ("(", "["):
            pos = close(tokens, pos)
        elif value == separator:
            yield tokens[start:pos]
            start = pos + 1
        pos += 1
    yield tokens[start:]


def routines(source):
    tokens = lex(source)
    implementations = [i for i, t in enumerate(tokens) if t.value == "implementation" and t.column == 1]
    if len(implementations) != 1:
        raise Invalid("expected exactly one implementation section")
    starts = [i for i, t in enumerate(tokens) if i > implementations[0]
              and t.column == 1 and t.value in ROUTINE]
    groups = {}
    for number, start in enumerate(starts):
        stop = starts[number + 1] if number + 1 < len(starts) else len(tokens)
        part = tokens[start:stop]
        pos = 1
        names = []
        while pos < len(part) and part[pos].value not in ("(", ":", ";"):
            names.append(part[pos].value)
            pos += 1
        name = "".join(names)
        if not re.fullmatch(r"[a-z_][a-z_0-9]*(?:\.[a-z_][a-z_0-9]*)*", name):
            # Operators are boundaries too, but cannot be statement walkers.
            if part[0].value == "operator":
                continue
            raise Invalid(f"unrecognized routine header: {name}")
        parameters = []
        if pos < len(part) and part[pos].value == "(":
            end = close(part, pos)
            for group in chunks(part[pos + 1:end], ";"):
                vv = values(group)
                if ":" not in vv:
                    continue
                colon = vv.index(":")
                if vv[colon + 1:] == ["pstmt"]:
                    parameters.extend(v for v in vv[:colon] if v not in ("const", "var", "out", ","))
            pos = end + 1
        while pos < len(part) and part[pos].value != ";":
            pos += 1
        if pos == len(part):
            raise Invalid(f"unterminated routine header: {name}")
        if pos + 1 < len(part) and part[pos + 1].value == "forward":
            continue  # A forward declaration is not an implementation body.
        groups.setdefault(name, []).append({
            "tokens": part, "parameters": parameters,
            "body": part[pos + 1:], "line": part[0].line,
            "signature": seal(part[:pos + 1])})
    result = {}
    for name, definitions in groups.items():
        for definition in definitions:
            key = name if len(definitions) == 1 else name + "#" + definition["signature"]
            if key in result:
                raise Invalid(f"duplicate implementation signature: {name}")
            result[key] = definition
    return result


def records(source):
    tokens = lex(source)
    result = {}
    for name in ("tstmt", "tselarm", "tcasearm"):
        starts = [i for i in range(len(tokens) - 2)
                  if values(tokens[i:i + 3]) == [name, "=", "record"]]
        if len(starts) != 1:
            raise Invalid(f"record declaration not unique: {name}")
        start = starts[0] + 3
        end = next((i for i in range(start, len(tokens)) if tokens[i].value == "end"), None)
        if end is None:
            raise Invalid(f"unclosed record: {name}")
        fields = {}
        for group in chunks(tokens[start:end], ";"):
            vv = values(group)
            if not vv:
                continue
            if vv.count(":") != 1:
                raise Invalid(f"record grammar needs review: {name}")
            colon = vv.index(":")
            for field in vv[:colon]:
                if field == ",":
                    continue
                if field in fields:
                    raise Invalid(f"duplicate record field: {name}.{field}")
                fields[field] = vv[colon + 1:]
        result[name] = fields
    return result


def aliases(source):
    tokens = lex(source)
    result = {}
    for name in ("pexpr", "pstmt", "texprarray", "tstmtarray", "tcasearmarray", "tselarmarray"):
        starts = [i for i in range(len(tokens) - 1)
                  if values(tokens[i:i + 2]) == [name, "="]]
        if len(starts) != 1:
            raise Invalid(f"child type declaration not unique: {name}")
        start = starts[0] + 2
        end = next((i for i in range(start, len(tokens)) if tokens[i].value == ";"), None)
        if end is None:
            raise Invalid(f"unclosed child type declaration: {name}")
        result[name] = values(tokens[start:end])
    return result


def first_argument(tokens, call):
    if call + 1 >= len(tokens) or tokens[call + 1].value != "(":
        return []
    end = close(tokens, call + 1)
    return next(chunks(tokens[call + 2:end], ","))


def recursive_child_walk(routine, statement_fields):
    header = values(routine["tokens"])
    paren = header.index("(") if "(" in header else header.index(";")
    own = header[paren - 1]
    body = routine["body"]
    for pos, token in enumerate(body):
        if token.value != own:
            continue
        arg = values(first_argument(body, pos))
        if len(arg) >= 4 and arg[0] in routine["parameters"] and arg[1:3] == ["^", "."]:
            if arg[3] in statement_fields:
                return True
    return False


def statement_end(tokens, start):
    """Bound the bodies used by select loops; reject unfamiliar grammar."""
    if start >= len(tokens):
        raise Invalid("missing loop body")
    value = tokens[start].value
    if value == "begin":
        pos = start + 1
        while pos < len(tokens) and tokens[pos].value != "end":
            if tokens[pos].value == ";":
                pos += 1
            else:
                pos = statement_end(tokens, pos)
        if pos == len(tokens):
            raise Invalid("unclosed begin in select loop")
        return pos + 1
    if value == "if":
        pos = start + 1
        while pos < len(tokens) and tokens[pos].value != "then":
            pos = close(tokens, pos) + 1 if tokens[pos].value in ("(", "[") else pos + 1
        pos = statement_end(tokens, pos + 1)
        if pos < len(tokens) and tokens[pos].value == "else":
            pos = statement_end(tokens, pos + 1)
        return pos
    if value in ("for", "while", "with"):
        pos = start + 1
        while pos < len(tokens) and tokens[pos].value != "do":
            pos = close(tokens, pos) + 1 if tokens[pos].value in ("(", "[") else pos + 1
        return statement_end(tokens, pos + 1)
    # Existing select traversal bodies have simple statements and begin/if.
    # A case/repeat/try here requires explicit review, rather than guessing.
    if value in ("case", "repeat", "try", "asm"):
        raise Invalid(f"select traversal body grammar needs review: {value}")
    pos = start
    while pos < len(tokens) and tokens[pos].value not in (";", "end", "else"):
        pos = close(tokens, pos) + 1 if tokens[pos].value in ("(", "[") else pos + 1
    if pos == start:
        raise Invalid("empty select traversal body")
    return pos


def select_loops(routine, root, array_field):
    tokens = routine["body"]
    for pos, token in enumerate(tokens):
        if token.value != "for" or pos + 13 >= len(tokens):
            continue
        index = tokens[pos + 1].value
        expected = ["for", index, ":=", "0", "to", "high", "(", root,
                    "^", ".", array_field, ")", "do"]
        if values(tokens[pos:pos + len(expected)]) != expected:
            continue
        start = pos + len(expected)
        end = statement_end(tokens, start)
        yield index, tokens[start:end]


def required_visits(routine, spec, child_fields, array_field):
    errors = []
    root = spec.get("root", "s")
    if root not in routine["parameters"]:
        return ["contract root is not a PStmt formal parameter"]
    requirements = {}
    for field, kind in child_fields.items():
        if kind == ["pstmt"]:
            requirements[field] = spec["statement"]
        elif kind == ["pexpr"] and spec.get("expression"):
            requirements[field] = spec["expression"]
    if "destination" in spec:
        requirements["dest"] = spec["destination"]
    found = set()
    for index, body in select_loops(routine, root, array_field):
        vv = values(body)
        for field, callee in requirements.items():
            path = [root, "^", ".", array_field, "[", index, "]", ".", field]
            for pos, token in enumerate(body):
                if token.value != callee or values(first_argument(body, pos)) != path:
                    continue
                if spec.get("rewrite") and field != "dest":
                    start = pos - 2 if vv[max(0, pos - 2):pos] == ["self", "."] else pos
                    if vv[max(0, start - len(path) - 1):start] != path + [":="]:
                        continue
                found.add(field)
    for field in sorted(requirements.keys() - found):
        errors.append(f"no bound {requirements[field]} visit of {array_field}[i].{field} in complete loop")
    return errors


def audit(root, contracts, sources=None, check_seals=True):
    errors = []
    ast_source = (root / "src/compiler/pasast.paslang").read_text()
    schema = records(ast_source)
    if aliases(ast_source) != contracts["aliases"]:
        return ["pasast child pointer/array aliases changed: review typed traversal"]
    if schema != contracts["records"]:
        return ["pasast TStmt/TSelArm/TCaseArm schema changed: classify all child fields"]
    arrays = [name for name, kind in schema["tstmt"].items() if kind == ["tselarmarray"]]
    if len(arrays) != 1:
        return ["select arm array field is not unique"]
    fields = {name: kind for name, kind in schema["tselarm"].items()
              if kind in (["pexpr"], ["pstmt"])}
    if set(map(tuple, fields.values())) != {("pexpr",), ("pstmt",)}:
        return ["select child pointer kinds changed"]
    discovered = {}
    dependencies_seen = set()
    for unit in UNITS:
        source = sources[unit] if sources else (root / "src/compiler" / (unit + ".paslang")).read_text()
        definitions = routines(source)
        for name, routine in definitions.items():
            key = unit + ":" + name
            if key in contracts["dependencies"]:
                dependencies_seen.add(key)
                if check_seals and seal(routine["tokens"]) != contracts["dependencies"][key]:
                    errors.append(key + ": limited-walker input guard changed; review required")
        inventory = {name: data for name, data in definitions.items() if data["parameters"]}
        expected = contracts["inventory"][unit]
        for name in sorted(inventory.keys() ^ expected.keys()):
            errors.append(f"{unit}:{name}: PStmt routine inventory changed; classify it")
        for name, routine in inventory.items():
            key = unit + ":" + name
            spec = contracts["walkers"].get(key)
            is_walker = recursive_child_walk(routine, schema["tstmt"])
            if is_walker and spec is None:
                errors.append(key + ": recursive typed-child walker has no contract")
            if spec and spec["mode"] == "walk":
                errors.extend(key + ": " + e for e in required_visits(routine, spec, fields, arrays[0]))
            if check_seals and name in expected and seal(routine["tokens"]) != expected[name]:
                errors.append(key + ": executable token body changed; review contract and control flow")
            discovered[key] = routine
    for key in contracts["dependencies"].keys() - dependencies_seen:
        errors.append(key + ": limited-walker input guard disappeared")
    for key in contracts["walkers"].keys() - discovered.keys():
        errors.append(key + ": contracted walker disappeared")
    return errors


def removal_controls(root, contracts):
    """In-memory source controls: assertions concern structural diagnostics."""
    sources = {unit: (root / "src/compiler" / (unit + ".paslang")).read_text() for unit in UNITS}
    schema = contracts["records"]["tselarm"]
    fields = {name: kind for name, kind in schema.items() if kind in (["pexpr"], ["pstmt"])}
    controls = []
    targets = (
        ('pasparse', 'stmtmod', 'exprmod', 'chan'),
        ('pasparse', 'stmtmod', 'exprmod', 'valx'),
        ('pasparse', 'nameposs', 'namepose', 'chan'),
        ('pasparse', 'nameposs', 'namepose', 'valx'),
        ('pasparse', 'stmtnames', 'exprnames', 'chan'),
        ('pasparse', 'stmtnames', 'exprnames', 'valx'),
        ('pasparse', 'renamecell', 'renamecelle', 'chan'),
        ('pasparse', 'renamecell', 'renamecelle', 'valx'),
        ('pasparse', 'cellcopy', 'cellcopy', 'body'),
        ('pasparse', 'stmtmod', 'sameid', 'dest'),
        ('pasparse', 'stmtnames', 'sameid', 'dest'),
        ('pasparse', 'renamecell', 'sameid', 'dest'),
        ('pasparse', 'stmtwritesout', 'ownvar', 'dest'),
        ('pasopt', 'forcounter', 'forcounter', 'body'),
        ('pasopt', 'writesname', 'addrof', 'chan'),
        ('pasopt', 'writesname', 'addrof', 'valx'),
        ('pasopt', 'writesname', 'writesname', 'body'),
        ('pasopt', 'writesname', 'sameid', 'dest'),
        ('pasopt', 'hasasms', 'hasasms', 'body'),
        ('pasemit', 'proofscans', 'proofscane', 'chan'),
        ('pasemit', 'proofscans', 'proofscane', 'valx'),
        ('pasemit', 'proofscans', 'proofscans', 'body'),
        ('pasemit', 'hasloop', 'hasloop', 'body'),
        ('pasemit', 'writesvar', 'samesym', 'dest'),
        ('pasemit', 'writesvar', 'writesvar', 'body'),
        ('pasemit', 'hasinnerfor', 'hasinnerfor', 'body'),
        ('pasemit', 'hascontinue', 'hascontinue', 'body'),
        ('pasemit', 'vneeds', 'vneede', 'chan'),
        ('pasemit', 'vneeds', 'vneede', 'valx'),
        ('pasemit', 'vneeds', 'vneeds', 'body'),
        ('pasemit', 'vscans', 'vscane', 'chan'),
        ('pasemit', 'vscans', 'vscane', 'valx'),
        ('pasemit', 'vscans', 'vadd', 'dest'),
        ('pasemit', 'vscans', 'vscans', 'body'),
        ('pasemit', 'haswith', 'haswith', 'body'),
        ('pasemit', 'vecins', 'vecins', 'body'),
        ('pasemit', 'hasasm', 'hasasm', 'body'),
    )
    classes = {"pasparse": "tparser.", "pasopt": "topt.", "pasemit": "temitter."}
    for unit, name, expr, field in targets:
        qualified = classes[unit] + name
        key = unit + ":" + qualified
        routine = routines(sources[unit])[qualified]
        body = routine["body"]
        candidates = [i for i, t in enumerate(body) if t.value == expr and
                      values(first_argument(body, i)) == ["s", "^", ".", "sels", "[", "i", "]", ".", field]]
        if len(candidates) != 1:
            raise Invalid(key + ": removal control target is not unique")
        # Removing only the callee token leaves the field text in place: a
        # name/field occurrence checker would incorrectly accept this mutant.
        index = candidates[0]
        mutant = dict(routine)
        mutant["body"] = body[:index] + [Token("removed_visit", body[index].line, body[index].column)] + body[index + 1:]
        problems = required_visits(mutant, contracts["walkers"][key], fields, "sels")
        if not any("." + field + " " in problem for problem in problems):
            raise Invalid(key + "." + field + ": source removal control escaped")
        controls.append(key + "." + field)
    # Wrap the whole loop so the false conditional also leaves valid Pascal.
    # The typed call and every ordinary executable token remain unchanged.
    target = ("  for i := 0 to High(S^.Sels) do\n"
              "    S^.Sels[i].Body := CellCopy(S^.Sels[i].Body, N, Cell, CT, T, Depth);")
    if sources["pasparse"].count(target) != 1:
        raise Invalid("CellCopy directive control target is not unique")
    for opening, closing, label in (
            ("{$IFDEF SELECT_WALKERS_DISABLED_CONTROL}", "{$ENDIF}", "brace"),
            ("(*$IFDEF SELECT_WALKERS_DISABLED_CONTROL*)", "(*$ENDIF*)", "paren")):
        mutant_sources = dict(sources)
        mutant_sources["pasparse"] = sources["pasparse"].replace(
            target, opening + "\n" + target + "\n" + closing, 1)
        try:
            audit(root, contracts, sources=mutant_sources)
        except Invalid as error:
            if not str(error).startswith("compiler directive requires traversal review at "):
                raise
        else:
            raise Invalid(label + " compiler-directive control escaped")
        controls.append("compiler-directive:" + label)
    return controls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--contracts", type=Path, default=Path(__file__).with_suffix(".json"))
    parser.add_argument("--self-test", action="store_true", help="also reject visitor-removal and compiler-directive controls")
    args = parser.parse_args()
    contracts = json.loads(args.contracts.read_text())
    try:
        if contracts.get("format") != 1:
            raise Invalid("unknown traversal contract format")
        for key, spec in contracts["walkers"].items():
            if spec.get("mode") not in ("walk", "limited") or not spec.get("reason"):
                raise Invalid(key + ": unclassified traversal contract")
        errors = audit(args.root, contracts)
        if errors:
            raise Invalid("\n".join(errors))
        controls = removal_controls(args.root, contracts) if args.self_test else []
    except (Invalid, KeyError, StopIteration) as error:
        raise SystemExit("select_walkers: " + str(error)) from error
    print("select_walkers: reviewed typed select child operations and source inventory match" +
          (f"; {len(controls)} source controls refused" if controls else ""))


if __name__ == "__main__":
    main()
