#!/usr/bin/env python3
"""P404: the expected output of testdata/sqlparse from SQLite itself.

SQLite 3.54.1's amalgamation (docs/ref/sqlite/amalg), built with
SQLITE_DEBUG and SQLITE_ENABLE_TREETRACE, prints with the trace flag
0x10000 (the CLI's .treetrace) the tree of a statement where
sqlite3Select, sqlite3Insert, sqlite3Update and sqlite3DeleteFrom begin
(treeview.c), before anything resolves it: the tree the parser built.
testdata/sqlparse prints the same trees from the unit sqlite's parser, so the
two must agree line for line.

A small C driver (DRIVER) links the amalgamation and, for each record of
the corpus, opens a fresh in-memory database, makes the tables and
attaches the schemas the statement names as preparing it asks for them
("no such table", "unknown database"; the tables with the columns COLS),
then turns the trace on and prepares the record's first statement
(prepares only: nothing runs), and prints SQLite's error or "ok". What is kept of
the trace: the rows of a VALUES list the parser codes at once
(sqlite3MultiValues calls sqlite3Select on its first row while it
parses), then the statement's own tree; the trees code generation prints
later are not the parser's. Statements that are not SELECT, VALUES,
INSERT, REPLACE, UPDATE or DELETE print no tree here. An error is kept
when the parser makes it (PARSE_ERRORS: the words of tokenize.c, parse.y,
and of the expr.c, select.c, build.c, window.c, trigger.c and insert.c
routines the parser calls); an error code generation makes after a
successful parse (no such table, ...) is an "ok" for the parser when the
statement's tree was printed; otherwise the record is left out ("skip"),
as code generation failed before the parser met what it would say.

usage:
  sqlparse_oracle.py build DIR            DIR/sqlparse-oracle with gcc
  sqlparse_oracle.py expect DRV CORPUS    the expected output, to stdout
  sqlparse_oracle.py rules DRV CORPUS     the rules of parse.y each
                                          record reduces
"""
import os
import re
import subprocess
import sys

ROOT = os.environ.get('PASLANG_ROOT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AMALG = os.path.join(ROOT, 'docs/ref/sqlite/amalg/sqlite-amalgamation-3540100')

SCHEMA = ''

DRIVER = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sqlite3.h"

#define COLS "a, b, c, d, e, f, x, y, z, w"

/* each record of the file: a fresh database, the schema, the trace on,
   the first statement prepared; "#n", the trace, "ok" or "error: " */
int main(int argc, char **argv){
  FILE *f = fopen(argv[1], "rb");
  int rules = argc > 2 && strcmp(argv[2], "rules") == 0;
  long sz, i, start = 0;
  char *buf;
  int n = 0;
  if( f==0 ) return 1;
  fseek(f, 0, SEEK_END); sz = ftell(f); fseek(f, 0, SEEK_SET);
  buf = malloc(sz + 1);
  if( fread(buf, 1, sz, f)!=(size_t)sz ) return 1;
  buf[sz] = 0;
  for(i = 0; i <= sz; i++){
    if( (i==sz || buf[i]=='\n') ){
      long ls = i;
      while( ls>start && buf[ls-1]!='\n' ) ls--;
      if( i - ls == 4 && memcmp(buf + ls, "----", 4)==0 ){
        sqlite3 *db;
        sqlite3_stmt *st = 0;
        unsigned int x = 0x10000, z = 0;
        int rc, tries;
        char masked[600] = "";
        char *rec;
        long len = ls - start;
        if( len>0 ) len--;
        rec = malloc(len + 1);
        memcpy(rec, buf + start, len);
        rec[len] = 0;
        n++;
        sqlite3_open(":memory:", &db);
        sqlite3_exec(db, "%SCHEMA%", 0, 0, 0);
        /* the tables and schemas the statement names, made as code
           generation asks for them, the trace off */
        for(tries = 0; tries < 12; tries++){
          const char *m;
          char *sq = 0;
          rc = sqlite3_prepare_v2(db, rec, -1, &st, 0);
          sqlite3_finalize(st);
          st = 0;
          if( rc==SQLITE_OK ) break;
          m = sqlite3_errmsg(db);
          if( strncmp(m, "no such table: ", 15)!=0 && strncmp(m, "unknown database ", 17)!=0 ){
            /* a syntax error may hide the table code generation looked
               for before it: the text before the error, alone */
            int off = sqlite3_error_offset(db);
            if( off>0 ){
              char *pre = sqlite3_mprintf("%.*s", off, rec);
              rc = sqlite3_prepare_v2(db, pre, -1, &st, 0);
              sqlite3_finalize(st);
              st = 0;
              sqlite3_free(pre);
              m = sqlite3_errmsg(db);
              if( rc==SQLITE_OK ) break;
              if( strncmp(m, "no such table: ", 15)!=0 && strncmp(m, "unknown database ", 17)!=0 ){
                snprintf(masked, sizeof(masked), "%s", m);
                break;
              }
            }
          }
          if( strncmp(m, "no such table: ", 15)==0 ){
            const char *nm = m + 15;
            const char *dot = strchr(nm, '.');
            if( dot ){
              sq = sqlite3_mprintf("CREATE TABLE \"%.*w\".\"%w\"(%s)", (int)(dot - nm), nm, dot + 1, COLS);
            }else{
              sq = sqlite3_mprintf("CREATE TABLE \"%w\"(%s)", nm, COLS);
            }
          }else if( strncmp(m, "unknown database ", 17)==0 ){
            sq = sqlite3_mprintf("ATTACH ':memory:' AS %s", m + 17);
          }
          if( sq==0 ) break;
          if( sqlite3_exec(db, sq, 0, 0, 0)!=SQLITE_OK ){
            sqlite3_free(sq);
            break;
          }
          sqlite3_free(sq);
        }
        if( rules ) sqlite3_exec(db, "PRAGMA parser_trace=ON", 0, 0, 0);
        printf("#%d\n", n);
        fflush(stdout);
        if( !rules ) sqlite3_test_control(SQLITE_TESTCTRL_TRACEFLAGS, 1, &x);
        rc = sqlite3_prepare_v2(db, rec, -1, &st, 0);
        sqlite3_test_control(SQLITE_TESTCTRL_TRACEFLAGS, 1, &z);
        fflush(stdout);
        /* the trace may end in a line cut without its newline: the
           result after a byte of its own */
        printf("\001");
        if( masked[0] ) printf("masked %s\n", masked);
        if( rc!=SQLITE_OK ){
          printf("offset %d\n", sqlite3_error_offset(db));
          printf("error: %s\n", sqlite3_errmsg(db));
        }else{
          printf("ok\n");
        }
        fflush(stdout);
        sqlite3_finalize(st);
        sqlite3_close(db);
        free(rec);
        start = i + 1;
      }
    }
  }
  return 0;
}
'''

PARSE_ERRORS = [
    r'near ".*": syntax error$', r'incomplete input$', r'unrecognized token: ".*"$',
    r'unknown table option: ', r'Expression tree is too large \(maximum depth \d+\)$',
    r'too many arguments on function ', r'ORDER BY may not be used with non-aggregate ',
    r'too many terms in ORDER BY clause$', r'variable number must be between \?1 and \?\d+$',
    r'too many SQL variables$', r'IN\(\.\.\.\) element has \d+ terms? - expected \d+$',
    r'\d+ columns assigned \d+ values$', r'too many columns in set list$',
    r'syntax error after column name ".*"$', r'(ORDER BY|LIMIT) clause should come after .* not before$',
    r'too many terms in compound SELECT$', r'all VALUES must have the same number of terms$',
    r'unknown join type: ', r'too many FROM clause terms, max: \d+$',
    r'a JOIN clause is required before (ON|USING)$', r'duplicate WITH table name: ',
    r'cannot use RETURNING in a trigger$', r'unsupported frame specification$',
    r'no such window: ', r'cannot override .* of window: ',
    r'DISTINCT is not supported for window functions$',
    r'qualified table names are not allowed on INSERT, UPDATE, and DELETE statements within triggers$',
    r'unsupported use of NULLS (FIRST|LAST)$',
    r'the (NOT INDEXED|INDEXED BY) clause is not allowed on UPDATE or DELETE statements within triggers$',
    r'Recursion limit$', r'string or blob too big$',
]

# messages code generation makes too: the parser's only before the
# statement's own tree is printed (in a SELECT, INSERT, UPDATE or DELETE),
# or, for NULLS, in a trigger's step
AMBIGUOUS = [
    r'all VALUES must have the same number of terms$', r'no such window: ',
    r'ORDER BY may not be used with non-aggregate ', r'too many terms in ORDER BY clause$',
    r'Expression tree is too large', r'DISTINCT is not supported for window functions$',
    r'unsupported use of NULLS (FIRST|LAST)$', r'cannot override .* of window: ',
    r'\d+ columns assigned \d+ values$',
]

DML = ('SELECT', 'VALUES', 'WITH', 'INSERT', 'REPLACE', 'UPDATE', 'DELETE')


def build(d):
    os.makedirs(d, exist_ok=True)
    src = os.path.join(d, 'sqlparse-oracle.c')
    with open(src, 'w') as f:
        f.write(DRIVER.replace('%SCHEMA%', SCHEMA))
    out = os.path.join(d, 'sqlparse-oracle')
    subprocess.check_call(['gcc', '-O1', '-DSQLITE_DEBUG', '-DSQLITE_ENABLE_TREETRACE',
                           '-DSQLITE_ENABLE_MATH_FUNCTIONS', '-DSQLITE_ENABLE_PERCENTILE',
                           '-DSQLITE_THREADSAFE=0', '-I' + AMALG, src, os.path.join(AMALG, 'sqlite3.c'),
                           '-lm', '-o', out])
    print(out)


def records(path):
    rec = []
    for line in open(path, encoding='utf-8', errors='surrogateescape').read().split('\n'):
        if line == '----':
            yield '\n'.join(rec)
            rec = []
        else:
            rec.append(line)


TOKEN = re.compile(r"""\s+|--[^\n]*|/\*.*?(\*/|$)|'(?:[^']|'')*'|"(?:[^"]|"")*"|`[^`]*`|\[[^\]]*\]|"""
                   r"""[A-Za-z_][A-Za-z_0-9$]*|.""", re.S)


def words(sql):
    for m in TOKEN.finditer(sql):
        t = m.group(0)
        if t.isspace() or t.startswith('--') or t.startswith('/*'):
            continue
        yield t


def is_dml(sql):
    """Whether the statement prints its tree: its first keyword, after
    EXPLAIN [QUERY PLAN], is SELECT, VALUES, WITH, INSERT, REPLACE,
    UPDATE or DELETE (only those begin with WITH)."""
    w = [x.upper() for x in words(sql)]
    i = 0
    if i < len(w) and w[i] == 'EXPLAIN':
        i += 1
        if i < len(w) and w[i] == 'QUERY':
            i += 1
            if i < len(w) and w[i] == 'PLAN':
                i += 1
    return i < len(w) and w[i] in DML




def normalize(line):
    line = re.sub(r'\((\d+)/[0-9A-Fa-f]+\)', r'(\1/P)', line)
    line = re.sub(r'OVER (.* )?\([0-9A-Fa-f]+\)$', lambda m: 'OVER ' + (m.group(1) or '') + '(P)', line)
    line = re.sub(r'WITH \(0x[0-9A-Fa-f]+(, pOuter=0x[0-9A-Fa-f]+)?\)',
                  lambda m: 'WITH (0xP' + (', pOuter=0xP' if m.group(1) else '') + ')', line)
    line = re.sub(r'sqlite_returning_[0-9A-Fa-f]+', 'sqlite_returning_P', line)
    line = re.sub(r' tab=\'.*?\' nCol=\d+ ptr=[0-9A-Fa-f]+ used=[0-9a-f]+(\+rowid)?', '', line)
    line = re.sub(r' notCte', '', line)
    return line


def coroutine_row(seg):
    """A tree sqlite3MultiValues printed while parsing: one SELECT of
    SF_MultiValue (0x400) with only its result set."""
    lines = seg.split('\n')
    if lines[0] != 'In sqlite3Select()' or len(lines) < 2:
        return False
    m = re.match(r"'-- SELECT \(\d+/P\) selFlags=0x([0-9a-f]+) ", lines[1])
    if not m or not (int(m.group(1), 16) & 0x400):
        return False
    return all(not re.match(r"^    [|']-- (?!result-set)", x) for x in lines[2:])


def outputs(drv, corpus, mode=None):
    """Each record's trace as the driver printed it, the error the text
    before its syntax error meets first in code generation (None for
    none), and its result."""
    args = [drv, corpus] + ([mode] if mode else [])
    p = subprocess.run(args, stdout=subprocess.PIPE, check=True)
    text = p.stdout.decode('utf-8', 'surrogateescape')
    res = []
    # a message may hold a newline (a token cut at the end of a line):
    # the record ends where the next one starts
    for m in re.finditer(r'(?:^|(?<=\n))#\d+\n(.*?)\x01(?:masked (.*?)\n(?=offset -?\d+\n|ok\n|error: ))?'
                         r'(?:offset (-?\d+)\n)?(ok|error: .*?)\n(?=#\d+\n|\Z)', text, re.S):
        res.append((m.group(1), m.group(2), m.group(4)))
    return res


HEADER = re.compile(r'In (sqlite3\w+)\(\) at [^\n]*\n')


def segments(trace):
    """The trace's trees: the text from each header to the next."""
    trace = '\n'.join(normalize(x) for x in trace.split('\n'))
    cuts = [m.start() for m in HEADER.finditer(trace)]
    segs = []
    for k, c in enumerate(cuts):
        end = cuts[k + 1] if k + 1 < len(cuts) else len(trace)
        segs.append(HEADER.sub(lambda m: 'In ' + m.group(1) + '()\n', trace[c:end], count=1))
    return segs


def parse_error(msg):
    return any(re.match(r, msg, re.S) for r in PARSE_ERRORS)


def expect(drv, corpus):
    out = sys.stdout
    skips = 0
    sqls = list(records(corpus))
    outs = outputs(drv, corpus)
    if len(outs) != len(sqls):
        raise SystemExit('driver: %d records of %d' % (len(outs), len(sqls)))
    for n, (sql, (trace, masked, result)) in enumerate(zip(sqls, outs), 1):
        kept = []
        top = False
        for seg in segments(trace):
            kept.append(seg)
            if not coroutine_row(seg):
                top = True
                break
        dml = is_dml(sql)
        err = result[7:] if result.startswith('error: ') else None
        trace = ''.join(kept) if dml else ''
        ambiguous = err is not None and any(re.match(r, err, re.S) for r in AMBIGUOUS)
        if err is None:
            res = 'ok'
        elif ambiguous:
            if dml:
                res = None if top else 'error: ' + err
            else:
                trig = re.match(r'(?is)\s*CREATE\s+(TEMP\s+|TEMPORARY\s+)?TRIGGER\b', sql)
                res = 'error: ' + err if trig and 'NULLS' in err else None
        elif parse_error(err):
            res = 'error: ' + err
            if masked is not None and not parse_error(masked) and err.startswith('near "'):
                # code generation failed before the parser met the error:
                # only a token the parser takes (a syntax error) can come
                # after the reduction that generated code; the tokenizer's
                # error comes before it
                res = None
                err = masked + ' (then ' + err + ')'
        elif dml and top:
            # code generation failed after the parse
            res = 'ok'
        else:
            res = None
        out.write('#%d\n' % n)
        if res is None:
            skips += 1
            out.write('skip: %s\n' % err)
        else:
            out.write(trace + res + '\n')
    if skips:
        sys.stderr.write('%d records fail in code generation first\n' % skips)


def rules(drv, corpus):
    for n, (trace, masked, result) in enumerate(outputs(drv, corpus, 'rules'), 1):
        rs = sorted({int(x) for x in re.findall(r'parser: Reduce (\d+) ', trace)})
        # a syntax error: the state it met and the token it could not take
        err = ''
        k = trace.find('parser: Syntax Error!')
        if k >= 0:
            st = re.findall(r"(?:go to state|in state) (\d+)", trace[:k])
            tk = re.findall(r"parser: Input '([^']*)'", trace[:k])
            err = ' | %s %s' % (st[-1] if st else '-', tk[-1] if tk else '-')
        print(n, ' '.join(str(x) for x in rs) + err)


if __name__ == '__main__':
    if sys.argv[1] == 'build':
        build(sys.argv[2])
    elif sys.argv[1] == 'expect':
        expect(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'rules':
        rules(sys.argv[2], sys.argv[3])
