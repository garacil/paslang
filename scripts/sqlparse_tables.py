#!/usr/bin/env python3
"""P404: the tables of the unit sqlite's SQL parser, made from SQLite 3.54.1's
own sources in docs/ref/sqlite (src/parse.y, tool/lemon.c, lempar.c,
tool/mkkeywordhash.c, and the built-in function tables of func.c,
date.c, json.c, window.c and alter.c).

lemon is built with gcc and run on parse.y with no options (-S, as
main.mk runs it), so the tables are those of SQLite's own parser (the
amalgamation's are the same); mkkeywordhash gives the keywords. The
parser's states, actions, lookaheads, fallbacks and rules, and the
keywords sorted for a binary search, are printed as paslang constants;
then the built-in functions, a name, its number of arguments and
whether a call of it with constant arguments is constant
(exprNodeIsConstantFunction), for the options of the system's library
(ENABLE_MATH_FUNCTIONS, ENABLE_PERCENTILE, C99 math), checked against
that library's pragma_function_list when Python's sqlite3 has it.

usage: sqlparse_tables.py > tables.paslang
       sqlparse_tables.py check src/lib/sqlite.paslang
"""
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile

ROOT = os.environ.get('PASLANG_ROOT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'docs/ref/sqlite/src/sqlite-src-3540100')


def lemon(d):
    """parse.c, parse.h and keywordhash.h in d."""
    subprocess.check_call(['gcc', '-O1', '-o', d + '/lemon', SRC + '/tool/lemon.c'])
    subprocess.check_call(['gcc', '-O1', '-o', d + '/mkkeywordhash', SRC + '/tool/mkkeywordhash.c'])
    shutil.copy(SRC + '/src/parse.y', d + '/parse.y')
    shutil.copy(SRC + '/tool/lempar.c', d + '/lempar.c')
    subprocess.check_call([d + '/lemon', '-S', 'parse.y'], cwd=d, stdout=subprocess.DEVNULL)
    with open(d + '/keywordhash.h', 'w') as f:
        subprocess.check_call([d + '/mkkeywordhash'], stdout=f)


def parser_tables(d):
    pc = open(d + '/parse.c').read()
    ph = open(d + '/parse.h').read()
    kw = open(d + '/keywordhash.h').read()

    def table(name):
        m = re.search(r'static const [\w ]+? ' + name + r'\[\] = \{(.*?)\};', pc, re.S)
        if not m:
            raise SystemExit('no table ' + name)
        body = re.sub(r'/\*.*?\*/', '', m.group(1), flags=re.S)
        return [int(x) for x in re.findall(r'-?\d+', body)]


    def define(name):
        m = re.search(r'#define ' + name + r'\s+\(?(-?\d+)\)?', pc)
        if not m:
            raise SystemExit('no define ' + name)
        return int(m.group(1))


    def arr(name, typ, vals, per=12):
        out = ['  %s: array[0..%d] of %s = (' % (name, len(vals) - 1, typ)]
        for i in range(0, len(vals), per):
            chunk = ', '.join(str(v) for v in vals[i:i + per])
            out.append('    ' + chunk + (',' if i + per < len(vals) else ');'))
        return '\n'.join(out)


    tks = re.findall(r'#define (TK_\w+)\s+(\d+)', ph)
    consts = ['  { the token codes of parse.h }']
    for n, v in tks:
        consts.append('  %s = %s;' % (n, v))
    for n in ('YYNOCODE', 'YYWILDCARD', 'YYNSTATE', 'YYNRULE', 'YYNRULE_WITH_ACTION', 'YYNTOKEN',
              'YY_MAX_SHIFT', 'YY_MIN_SHIFTREDUCE', 'YY_MAX_SHIFTREDUCE', 'YY_ERROR_ACTION',
              'YY_ACCEPT_ACTION', 'YY_NO_ACTION', 'YY_MIN_REDUCE', 'YY_MAX_REDUCE', 'YY_ACTTAB_COUNT',
              'YY_SHIFT_COUNT', 'YY_REDUCE_COUNT'):
        consts.append('  %s = %d;' % (n, define(n)))

    act = table('yy_action')
    la = table('yy_lookahead')
    so = table('yy_shift_ofst')
    ro = table('yy_reduce_ofst')
    df = table('yy_default')
    fb = table('yyFallback')
    lhs = table('yyRuleInfoLhs')
    nrhs = table('yyRuleInfoNRhs')
    assert len(act) == define('YY_ACTTAB_COUNT'), (len(act),)
    assert len(df) == define('YYNSTATE')
    assert len(lhs) == len(nrhs) == define('YYNRULE')

    # the keywords: name -> code
    text = re.search(r'static const char zKWText\[\d+\] = \{(.*?)\};', kw, re.S).group(1)
    chars = re.findall(r"'(.)'", text)
    ktext = ''.join(chars)


    def ktab(name):
        m = re.search(r'static const [\w ]+? ' + name + r'\[\d+\] = \{0,(.*?)\};', kw, re.S)
        return [x.strip() for x in m.group(1).replace('\n', ' ').split(',') if x.strip()]


    klen = [int(x) for x in ktab('aKWLen')]
    koff = [int(x) for x in ktab('aKWOffset')]
    kcode = ktab('aKWCode')
    tkv = dict(tks)
    kws = sorted({(ktext[o:o + n], c) for n, o, c in zip(klen, koff, kcode)})
    assert len(kws) == len(klen), (len(kws), len(klen))

    out = []
    out.append('const')
    out.extend(consts)
    out.append('')
    out.append('const')
    out.append(arr('yy_action', 'Word', act))
    out.append(arr('yy_lookahead', 'Word', la))
    out.append(arr('yy_shift_ofst', 'Word', so))
    out.append(arr('yy_reduce_ofst', 'SmallInt', ro))
    out.append(arr('yy_default', 'Word', df))
    out.append(arr('yyFallback', 'Word', fb))
    out.append(arr('yyRuleInfoLhs', 'Word', lhs))
    out.append(arr('yyRuleInfoNRhs', 'SmallInt', nrhs))
    out.append('  SqlKwCount = %d;' % len(kws))
    out.append("  SqlKwName: array[0..%d] of string = (" % (len(kws) - 1))
    for i, (n, c) in enumerate(kws):
        out.append("    '%s'%s" % (n, ',' if i < len(kws) - 1 else ');'))
    out.append('  SqlKwCode: array[0..%d] of Word = (' % (len(kws) - 1))
    codes = [tkv[c] for n, c in kws]
    for i in range(0, len(codes), 12):
        out.append('    ' + ', '.join(codes[i:i + 12]) + (',' if i + 12 < len(codes) else ');'))
    return '\n'.join(out)


def function_table():
    src = SRC + '/src'
    res = []
    DEFINED = {'SQLITE_ENABLE_MATH_FUNCTIONS': 1, 'SQLITE_ENABLE_PERCENTILE': 1,
               'SQLITE_HAVE_C99_MATH_FUNCS': 1}

    # the macro's flags: constant (CONSTANT or SLOCHNG) and aggregate (an
    # xFinalize); None is decided by the macro's own arguments
    KIND = {
        'FUNCTION': (1, 0), 'VFUNCTION': (0, 0), 'SFUNCTION': (0, 0), 'MFUNCTION': (1, 0),
        'JFUNCTION': (1, 0), 'INLINE_FUNC': (1, 0), 'TEST_FUNC': (1, 0), 'DFUNCTION': (1, 0),
        'PURE_DATE': (1, 0), 'FUNCTION2': (1, 0), 'STR_FUNCTION': (1, 0), 'LIKEFUNC': (1, 0),
        'WAGGREGATE': (0, 1), 'INTERNAL_FUNCTION': (1, 0), 'WINDOWFUNCALL': (0, 1),
        'WINDOWFUNCNOOP': (0, 1), 'WINDOWFUNCX': (0, 1),
    }


    def cond(expr):
        expr = expr.strip()
        m = re.match(r'defined\((\w+)\)$', expr)
        if m:
            return m.group(1) in DEFINED
        if re.match(r'\w+$', expr):
            return bool(DEFINED.get(expr, 0))
        m = re.match(r'!defined\((\w+)\)$', expr)
        if m:
            return m.group(1) not in DEFINED
        m = re.match(r'defined\((\w+)\) \|\| defined\((\w+)\)$', expr)
        if m:
            return m.group(1) in DEFINED or m.group(2) in DEFINED
        raise SystemExit('condition ' + expr)


    def table(fname, tname):
        text = open(src + '/' + fname).read()
        m = re.search(r'static FuncDef ' + tname + r'\[\] = \{(.*?)\n  \};', text, re.S)
        body = m.group(1)
        out = []
        stack = []
        buf = ''
        for line in body.split('\n'):
            s = line.strip()
            if s.startswith('#'):
                d = s[1:].strip()
                if d.startswith('ifdef '):
                    stack.append(d[6:].split()[0] in DEFINED)
                elif d.startswith('ifndef '):
                    stack.append(d[7:].split()[0] not in DEFINED)
                elif d.startswith('if '):
                    stack.append(cond(d[3:]))
                elif d.startswith('else'):
                    stack[-1] = not stack[-1]
                elif d.startswith('endif'):
                    stack.pop()
                continue
            if not all(stack):
                continue
            s = re.sub(r'/\*.*?\*/', '', s)
            buf += ' ' + s
        for mac, args in re.findall(r'(\w+)\(([^()]*(?:\([^()]*\)[^()]*)*)\)', buf):
            if mac not in KIND:
                continue
            a = [x.strip() for x in args.split(',')]
            name = a[0].strip('"')
            out.append((name, int(a[1]), KIND[mac]))
        return out


    funcs = []
    funcs += table('func.c', 'aBuiltinFunc')
    funcs += table('date.c', 'aDateTimeFuncs')
    funcs += table('json.c', 'aJsonFunc')
    funcs += table('window.c', 'aWindowFuncs')
    funcs += table('alter.c', 'aAlterTableFuncs')

    # the oracle: every function the library lists is here with its arguments
    # and its kind; a constant one is SQLITE_DETERMINISTIC there (0x800)
    db = sqlite3.connect(':memory:')
    got = {(n, a): (c, g) for n, a, (c, g) in funcs}
    try:
        listed = db.execute('select * from pragma_function_list').fetchall()
    except sqlite3.Error:
        listed = []
    for name, builtin, typ, enc, narg, flags in listed:
        if not builtin or name in ('match', 'fts3_tokenizer', 'fts5', 'fts5_source_id', 'snippet',
                                   'offsets', 'matchinfo', 'optimize', 'rtreenode', 'rtreedepth',
                                   'rtreecheck', 'highlight', 'bm25', 'fts5_get_locale',
                                   'fts5_insttoken', 'fts5_locale', 'fts5_fold', 'fts5_isalnum',
                                   'fts5_expr', 'fts5_expr_tcl', 'fts5_api_from_db',
                                   'fts5_columnsize', 'fts5_columntext', 'fts5_columntotalsize',
                                   'fts5_test_poslist', 'fts5_test_poslist2', 'fts5_rowid'):
            continue
        key = (name, narg)
        if key not in got:
            raise SystemExit('missing %r' % (key,))
        c, g = got[key]
        if (typ != 's') != bool(g):
            raise SystemExit('kind %r %s' % (key, typ))
        if g == 0 and c and not (flags & 0x800) and name not in (
                'sqlite_version', 'sqlite_source_id', 'sqlite_compileoption_used',
                'sqlite_compileoption_get', 'current_time', 'current_timestamp', 'current_date'):
            raise SystemExit('constant %r %x' % (key, flags))

    const = sorted({(n.lower(), a) for n, a, (c, g) in funcs if c and not g})
    anyf = sorted({(n.lower(), a) for n, a, (c, g) in funcs})
    res.append('const')
    res.append('  { the built-in functions (func.c, date.c, json.c, window.c, alter.c):')
    res.append('    a name and its number of arguments, -1 any, -3 one or more, -4 two')
    res.append('    or more, and 1 when a call with constant arguments is constant }')
    res.append('  SqlFnCount = %d;' % len(anyf))
    res.append('  SqlFnName: array[0..%d] of string = (' % (len(anyf) - 1))
    res.append(',\n'.join("    '%s'" % n for n, a in anyf) + ');')
    res.append('  SqlFnArgs: array[0..%d] of SmallInt = (' % (len(anyf) - 1))
    vals = [str(a) for n, a in anyf]
    res.append(',\n'.join('    ' + ', '.join(vals[i:i + 16]) for i in range(0, len(vals), 16)) + ');')
    res.append('  SqlFnConst: array[0..%d] of Byte = (' % (len(anyf) - 1))
    vals = [str(int((n, a) in const)) for n, a in anyf]
    res.append(',\n'.join('    ' + ', '.join(vals[i:i + 16]) for i in range(0, len(vals), 16)) + ');')
    return '\n'.join(res)


def generate():
    d = tempfile.mkdtemp(prefix='sqlparse-tables-')
    try:
        lemon(d)
        return parser_tables(d) + '\n\n' + function_table() + '\n'
    finally:
        shutil.rmtree(d)


if __name__ == '__main__':
    text = generate()
    if len(sys.argv) > 2 and sys.argv[1] == 'check':
        if text not in open(sys.argv[2]).read():
            raise SystemExit('the tables in %s are not those parse.y and the function tables make' % sys.argv[2])
        print('ok sqlparse tables')
    else:
        sys.stdout.write(text)
