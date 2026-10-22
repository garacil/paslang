#!/usr/bin/env python3
"""P404: how testdata/sqlparse.sql was made, and its expected output.

1. harvest: the SQL of SQLite's own tests (test/*.test of 3.54.1 in
   docs/ref/sqlite: the braced execsql, catchsql, db eval,
   do_execsql_test, do_catchsql_test and do_eqp_test blocks), split as
   sqlite3_complete splits it: about 32,000 statements.
2. mutate: each of those SQLite accepts changed a few ways from a fixed
   seed (a token deleted, doubled, swapped with the next, one put in,
   the text cut after one): about 80,000 wrong and right statements.
3. select: statements that reduce every rule of parse.y the harvest
   reaches twice (the fewest, the shortest first); for each parser state
   a syntax error or the end of the input is met in, the shortest
   statement that meets it there; the three shortest of each other error
   of the parser. SQLite's own parser trace (PRAGMA parser_trace in the
   debug build) says which rules and which state.
4. hand: statements written for the rules SQLite's tests never reduce,
   every error of the parser at the limits that set it off, keywords as
   names, the tokenizer's corners, every kind of statement.
5. Statements whose code generation fails before the parser is done
   (sqlparse_oracle.py's "skip") are left out; the expected output is
   SQLite's (sqlparse_oracle.py expect).

usage: sqlparse_corpus.py DRIVER CORPUS EXPECTED
       (DRIVER: sqlparse_oracle.py build DIR)
"""
import os
import random
import re
import sqlite3
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sqlparse_oracle as oracle  # noqa: E402

TESTS = os.path.join(oracle.ROOT, 'docs/ref/sqlite/src/sqlite-src-3540100/test')
DEBUG_PRAGMA = re.compile(r'(?is)\s*pragma\s+(\w+\s*\.\s*)?(vdbe_\w+|parser_trace|sql_trace)\b')
KEY = re.compile(r'(?:execsql|catchsql|db\s+eval|do_execsql_test\s+\S+|do_catchsql_test\s+\S+|do_eqp_test\s+\S+)\s*\{')


def harvest():
    seen = set()
    out = []
    for f in sorted(os.listdir(TESTS)):
        if not f.endswith('.test'):
            continue
        text = open(os.path.join(TESTS, f), encoding='latin-1').read()
        for m in KEY.finditer(text):
            i = m.end()
            depth = 1
            j = i
            while j < len(text) and depth:
                c = text[j]
                if c == '\\':
                    j += 2
                    continue
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                j += 1
            cur = ''
            for line in text[i:j - 1].split('\n'):
                cur += line + '\n'
                if sqlite3.complete_statement(cur):
                    s = cur.strip()
                    cur = ''
                    if not s or s == ';' or '----' in s.split('\n') or len(s) > 4000 or s in seen:
                        continue
                    if DEBUG_PRAGMA.match(s):
                        # the debug build's tracing pragmas print into the
                        # driver's output as soon as they are prepared
                        continue
                    seen.add(s)
                    out.append(s)
    return out


TOKEN = re.compile(r"""\s+|--[^\n]*|/\*.*?(\*/|$)|'(?:[^']|'')*'|"(?:[^"]|"")*"|`[^`]*`|\[[^\]]*\]|"""
                   r"""[A-Za-z_][A-Za-z_0-9$]*|\d+(\.\d*)?([eE][-+]?\d+)?|\|\||<=|>=|<>|!=|==|<<|>>|->>|->|.""", re.S)
INS = ['(', ')', ',', ';', 'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'NULL', 'IN', 'AS', 'ON',
       'JOIN', 'ORDER', 'BY', 'GROUP', 'HAVING', 'LIMIT', 'OFFSET', 'UNION', 'ALL', 'VALUES', 'SET',
       'INTO', 'TABLE', 'INDEX', 'CREATE', 'DROP', 'WITH', 'OVER', 'FILTER', 'WINDOW', 'PARTITION',
       'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'IS', 'BETWEEN', 'LIKE', 'ESCAPE', 'COLLATE', 'CAST',
       'DEFAULT', 'PRIMARY', 'KEY', 'UNIQUE', 'CHECK', 'REFERENCES', 'CONSTRAINT', '1', "'x'", 'x',
       '*', '+', '-', '=', '.', '?', ':a', 'RETURNING', 'DO', 'NOTHING', 'CONFLICT', 'RAISE', 'EXISTS',
       'DISTINCT', 'USING', 'NATURAL', 'LEFT', 'OUTER', 'CROSS', 'INDEXED', 'ROWS', 'RANGE', 'GROUPS',
       'PRECEDING', 'FOLLOWING', 'CURRENT', 'ROW', 'UNBOUNDED', 'EXCLUDE', 'NO', 'OTHERS', 'TIES',
       'MATERIALIZED', 'RECURSIVE', 'TRIGGER', 'BEFORE', 'AFTER', 'INSTEAD', 'OF', 'BEGIN', 'FOR', 'EACH',
       'GENERATED', 'ALWAYS', 'STORED', 'VIRTUAL', 'WITHOUT', 'ROWID', 'STRICT', 'X\'00\'', '1_000',
       '0x_1', '1__2', '#1', '$', '@', '[a', '"b', "'c"]




def mutate(recs, n_per=3):
    rnd = random.Random(404)
    out = set()
    for r in recs:
        if len(r) > 600:
            continue
        t = [m.group(0) for m in TOKEN.finditer(r)]
        sig = [i for i, x in enumerate(t) if not x.isspace() and not x.startswith('--') and not x.startswith('/*')]
        if len(sig) < 2:
            continue
        for _ in range(n_per):
            i = rnd.choice(sig)
            k = rnd.randrange(5)
            u = list(t)
            if k == 0:
                del u[i]
            elif k == 1:
                u.insert(i, u[i])
            elif k == 2:
                j = sig[sig.index(i) + 1] if sig.index(i) + 1 < len(sig) else None
                if j is None:
                    continue
                u[i], u[j] = u[j], u[i]
            elif k == 3:
                u.insert(i, ' ' + rnd.choice(INS) + ' ')
            else:
                u = u[:i + 1]
            s = ''.join(u).strip()
            if s and '\n----\n' not in s and s != r:
                out.add(s)
    return sorted(out)


def hand():
    S = []
    def a(x):
        S.append(x)

    # rules the harvest does not reach
    a("BEGIN DEFERRED;")
    a("BEGIN TRANSACTION tx;")
    a("CREATE TABLE r1(a REFERENCES p(x) ON INSERT CASCADE ON DELETE SET NULL MATCH full);")
    a("SELECT group_concat(a ORDER BY b) FILTER (WHERE a>1) OVER w FROM t WINDOW w AS (PARTITION BY c);")
    a("SELECT a IS DISTINCT FROM b, a IS NOT DISTINCT FROM b FROM t;")
    a("ATTACH DATABASE ':memory:' AS aux9 KEY 'secret';")
    a("SELECT sum(a) OVER w2 FROM t WINDOW w1 AS (ORDER BY b), w2 AS (w1 PARTITION BY c);")
    a(";")
    a("CREATE TABLE g1(a, b GENERATED ALWAYS AS (a*2) STORED, c AS (a+1) VIRTUAL, d AS (a));")
    a("PRAGMA cache_size = DEFAULT;")
    a("CREATE VIRTUAL TABLE v1 USING m(a (b (c) d), e, (f));")
    # the parser's own errors, at their limits
    a("CREATE TABLE o1(a) WITHOUT rowid, STRICT;")
    a("CREATE TABLE o2(a) WITHOUT x;")
    a("CREATE TABLE o3(a) strictly;")
    # a view prints no tree: the deepest expression allowed checked without
    # a thousand-level trace
    a("CREATE VIEW vd1 AS SELECT " + "+".join(["1"] * 1000) + ";")
    a("SELECT " + "+".join(["1"] * 1001) + ";")
    a("CREATE VIEW vd2 AS SELECT " + "- " * 999 + "1;")
    a("SELECT " + "- " * 1000 + "1;")
    a("SELECT " + "- " * 20 + "1;")
    a("SELECT f(" + ",".join(["1"] * 1000) + ");")
    a("SELECT f(" + ",".join(["1"] * 1001) + ");")
    a("SELECT max(a ORDER BY b) OVER () FROM t;")
    a("SELECT group_concat(a ORDER BY " + ",".join(["b"] * 2000) + ") FROM t;")
    a("SELECT group_concat(a ORDER BY " + ",".join(["b"] * 2001) + ") FROM t;")
    for v in ["?0", "?1", "?32766", "?32767", "?99999999999999999999", "?00001"]:
        a("SELECT %s;" % v)
    a("SELECT ?32766, ?;")
    a("SELECT ?32765, ?, :a;")
    a("SELECT " + ",".join(["?"] * 32767) + ";")
    a("SELECT ?5, ?, :a, @a, $a, $a::b(c d), :a, ?2, ?7;")
    a("SELECT (1,2) IN ((1,2),(3));")
    a("SELECT (1,2) IN ((1,2),(3,4,5));")
    a("SELECT (1,2,3) IN ((1,2,3),(4,5,6));")
    a("UPDATE t SET (a,b) = (1,2,3);")
    a("UPDATE t SET (a,b,c) = (1,2);")
    a("UPDATE t SET (a,b) = (SELECT 1,2), c = 3;")
    a("UPDATE t SET " + ",".join(["a=1"] * 2000) + ";")
    a("UPDATE t SET " + ",".join(["a=1"] * 2001) + ";")
    a("CREATE VIEW v2(a COLLATE nocase) AS SELECT 1;")
    a("CREATE VIEW v3(a DESC) AS SELECT 1;")
    a("WITH c(a ASC) AS (SELECT 1) SELECT * FROM c;")
    a("SELECT 1 ORDER BY 1 UNION SELECT 2;")
    a("SELECT 1 LIMIT 1 UNION ALL SELECT 2;")
    a("SELECT 1 ORDER BY 1 INTERSECT SELECT 2;")
    a("SELECT 1 LIMIT 1 EXCEPT SELECT 2;")
    a(" UNION ".join(["SELECT 1"] * 500) + ";")
    a(" UNION ".join(["SELECT 1"] * 501) + ";")
    a("VALUES " + ",".join(["(1)"] * 600) + ";")
    a("VALUES(1),(1,2);")
    a("VALUES(1,2),(3,4),(5);")
    a("SELECT * FROM (VALUES(1,2),(3,'x'),(NULL,4.5));")
    a("WITH w AS (SELECT 1) SELECT * FROM (VALUES(1),(2));")
    a("VALUES(1),(abs(2)),(a);")
    a("VALUES(CAST(1 AS TEXT)),(2);")
    for j in ["NATURAL INNER OUTER", "LEFT INNER", "FOO", "OUTER", "LEFT x y", "NATURAL FULL OUTER", "CROSS",
              "RIGHT OUTER", "FULL", "INNER NATURAL", "LEFT LEFT LEFT"]:
        a("SELECT * FROM t %s JOIN t2;" % j)
    a("SELECT * FROM " + ",".join(["t"] * 200) + ";")
    a("SELECT * FROM " + ",".join(["t"] * 201) + ";")
    a("SELECT * FROM t ON 1;")
    a("SELECT * FROM t USING(a);")
    a("SELECT * FROM (t ON 1);")
    a("WITH a AS (SELECT 1), A AS (SELECT 2) SELECT 1;")
    a("WITH a AS (SELECT 1), b AS (SELECT 2), a AS (SELECT 3), a AS (SELECT 4) SELECT 1;")
    a("CREATE TRIGGER r1 AFTER INSERT ON t BEGIN INSERT INTO t2 VALUES(1,2) RETURNING *; END;")
    a("SELECT sum(a) OVER (ROWS BETWEEN CURRENT ROW AND 1 PRECEDING) FROM t;")
    a("SELECT sum(a) OVER (ROWS BETWEEN 1 FOLLOWING AND CURRENT ROW) FROM t;")
    a("SELECT sum(a) OVER (ROWS BETWEEN 1 FOLLOWING AND 1 PRECEDING) FROM t;")
    a("SELECT sum(a) OVER (GROUPS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING EXCLUDE TIES) FROM t;")
    a("SELECT sum(a) OVER (RANGE BETWEEN a+1 PRECEDING AND ?1 FOLLOWING EXCLUDE NO OTHERS) FROM t;")
    a("SELECT sum(a) OVER (ROWS 5 PRECEDING EXCLUDE CURRENT ROW), sum(a) OVER (ROWS CURRENT ROW EXCLUDE GROUP) FROM t;")
    a("SELECT sum(a) OVER w FROM t WINDOW w AS (nosuch ORDER BY b);")
    a("SELECT sum(a) OVER w2 FROM t WINDOW w1 AS (PARTITION BY a), w2 AS (w1 PARTITION BY b);")
    a("SELECT sum(a) OVER w2 FROM t WINDOW w1 AS (ORDER BY a), w2 AS (w1 ORDER BY b);")
    a("SELECT sum(a) OVER w2 FROM t WINDOW w1 AS (ROWS 1 PRECEDING), w2 AS (w1);")
    a("SELECT sum(a) OVER w2 FROM t WINDOW w1 AS (PARTITION BY a), w2 AS (W1 ORDER BY b);")
    a("SELECT count(DISTINCT a) OVER () FROM t;")
    a("SELECT count(DISTINCT a) FILTER (WHERE b) FROM t;")
    a("SELECT count(DISTINCT a) FILTER (WHERE b) OVER (ORDER BY c) FROM t;")
    a("CREATE TRIGGER r2 AFTER INSERT ON t BEGIN UPDATE main.t2 SET a=1; END;")
    a("CREATE TEMP TRIGGER r3 AFTER INSERT ON t BEGIN UPDATE main.t2 SET a=1; END;")
    a("CREATE TRIGGER temp.r4 AFTER INSERT ON t BEGIN DELETE FROM main.t2; END;")
    a("CREATE TRIGGER r5 AFTER INSERT ON t BEGIN INSERT INTO t2 VALUES(1,2) ON CONFLICT(a NULLS FIRST) DO NOTHING; END;")
    a("CREATE TRIGGER r6 AFTER INSERT ON t BEGIN INSERT INTO t2 VALUES(1,2) ON CONFLICT(a DESC NULLS LAST) DO NOTHING; END;")
    a("CREATE TRIGGER r7 AFTER INSERT ON t BEGIN UPDATE t2 INDEXED BY i SET a=1; END;")
    a("CREATE TRIGGER r8 AFTER INSERT ON t BEGIN DELETE FROM t2 NOT INDEXED; END;")
    a("SELECT " + "(" * 2500 + "1" + ")" * 2500 + ";")
    a("SELECT " + "(" * 1200 + "1" + ")" * 1200 + ";")
    for u in ["SELECT 1_;", "SELECT x'0';", "SELECT 'abc", "SELECT [a", "SELECT $;", "SELECT 1e;", "SELECT 0x;",
              "SELECT #;", "SELECT !;", "SELECT 1__2;", "SELECT 0x_1;", "SELECT 1._5;", "SELECT 1_.5;",
              "SELECT 0x1_F_;", "SELECT `a", "SELECT \"a", "SELECT 1 /* open", "SELECT ?a;", "SELECT :;",
              "SELECT @1;", "SELECT $a(b;", "SELECT 1abc;", "SELECT 1.5e+;", "SELECT x'ag';", "SELECT X'abc';",
              "SELECT \x01;", "SELECT \x7f;", "SELECT 1 \xc3\xa9;", "\xef\xbb\xbfSELECT 1;", "SELECT \xef\xbb;"]:
        a(u)
    for q in ["SELECT 1_000, 1_0.5_5e1_0, 0x1_F, .5_5, 1e1_0;", "SELECT 0x7FFFFFFF, 0x80000000, 2147483647, 2147483648, -2147483648;",
              "SELECT 00000000000000000000001, 0x000000000000000000001, 1e309, .5, 5., 0.5e-3;",
              "SELECT X'', x'0aFF', 'it''s', \"q\"\"q\", [a b], `c``d`;"]:
        a(q)
    # keywords that fall back to names: as a column, a table and an alias
    fb = ['ABORT', 'ACTION', 'AFTER', 'ANALYZE', 'ASC', 'ATTACH', 'BEFORE', 'BEGIN', 'BY', 'CASCADE', 'CAST',
          'COLUMN', 'CONFLICT', 'DATABASE', 'DEFERRED', 'DESC', 'DETACH', 'DO', 'EACH', 'END', 'EXCLUSIVE',
          'EXPLAIN', 'FAIL', 'FOR', 'IGNORE', 'IMMEDIATE', 'INITIALLY', 'INSTEAD', 'LIKE', 'GLOB', 'REGEXP',
          'MATCH', 'NO', 'PLAN', 'QUERY', 'KEY', 'OF', 'OFFSET', 'PRAGMA', 'RAISE', 'RECURSIVE', 'RELEASE',
          'REPLACE', 'RESTRICT', 'ROW', 'ROWS', 'SAVEPOINT', 'TEMP', 'TEMPORARY', 'TRIGGER', 'VACUUM', 'VIEW',
          'VIRTUAL', 'WITH', 'WITHOUT', 'NULLS', 'FIRST', 'LAST', 'CURRENT', 'FOLLOWING', 'PARTITION',
          'PRECEDING', 'RANGE', 'UNBOUNDED', 'EXCLUDE', 'GROUPS', 'OTHERS', 'TIES', 'GENERATED', 'ALWAYS',
          'MATERIALIZED', 'REINDEX', 'RENAME', 'CURRENT_TIME', 'CURRENT_DATE', 'CURRENT_TIMESTAMP', 'IF',
          'WINDOW', 'OVER', 'FILTER', 'ROWID', 'STRICT']
    for k in fb:
        a("SELECT %s, %s.%s, %s(1) FROM %s AS %s WHERE %s = %s;" % (k, k, k, k, k, k, k, k))
        a("CREATE TABLE %s(%s %s);" % (k, k, k))
        a("UPDATE %s SET %s = %s;" % (k, k, k))
    # keywords that are not names
    for k in ['SELECT', 'FROM', 'WHERE', 'TABLE', 'INDEX', 'ORDER', 'GROUP', 'UNION', 'NOT', 'NULL', 'AND', 'OR',
              'IN', 'IS', 'BETWEEN', 'CASE', 'WHEN', 'THEN', 'ELSE', 'JOIN', 'ON', 'USING', 'SET', 'VALUES', 'INTO',
              'DEFAULT', 'PRIMARY', 'UNIQUE', 'CHECK', 'REFERENCES', 'CONSTRAINT', 'DISTINCT', 'ALL', 'EXISTS',
              'LIMIT', 'HAVING', 'COLLATE', 'ESCAPE', 'NATURAL', 'LEFT', 'RETURNING', 'NOTHING', 'INDEXED', 'AS',
              'TO', 'ADD', 'ALTER', 'DROP', 'CREATE', 'TRANSACTION', 'COMMIT', 'ROLLBACK', 'DEFERRABLE', 'FOREIGN',
              'ISNULL', 'NOTNULL', 'AUTOINCREMENT', 'EXCEPT', 'INTERSECT', 'INSERT', 'UPDATE', 'DELETE', 'UNIQUE']:
        a("SELECT 1 AS %s;" % k)
        a("SELECT %s FROM t;" % k)
    # WINDOW, OVER and FILTER by what is around them
    a("SELECT window, over, filter FROM t;")
    a("SELECT 1 FROM t window;")
    a("SELECT 1 FROM t AS window WINDOW window AS ();")
    a("SELECT f(x) over FROM t;")
    a("SELECT f(x) over over FROM t WINDOW over AS ();")
    a("SELECT f(x) filter FROM t;")
    a("SELECT f(x) filter (where x) FROM t;")
    a("SELECT (1) over;")
    a("SELECT f(x) OVER /* c */ ( -- d\n ) FROM t;")
    a("SELECT x FROM t WINDOW w AS (), window AS ();")
    # every kind of statement
    for x in ["COMMIT;", "END TRANSACTION;", "ROLLBACK;", "ROLLBACK TO SAVEPOINT s;", "ROLLBACK TRANSACTION TO s;",
              "SAVEPOINT s;", "RELEASE s;", "RELEASE SAVEPOINT s;", "BEGIN IMMEDIATE;", "BEGIN EXCLUSIVE TRANSACTION;",
              "DROP TABLE IF EXISTS main.t;", "DROP VIEW v;", "DROP INDEX IF EXISTS i;", "DROP TRIGGER IF EXISTS temp.r;",
              "CREATE UNIQUE INDEX IF NOT EXISTS main.i1 ON t(a COLLATE nocase DESC, b+1, c ASC) WHERE a>0;",
              "CREATE TEMP VIEW IF NOT EXISTS v4(x, y) AS WITH c AS (SELECT 1) SELECT * FROM c, t;",
              "CREATE TABLE IF NOT EXISTS temp.t9(a INTEGER PRIMARY KEY DESC ON CONFLICT REPLACE AUTOINCREMENT, "
              "b TEXT NOT NULL ON CONFLICT FAIL DEFAULT 'x' COLLATE binary UNIQUE ON CONFLICT IGNORE, "
              "c DEFAULT (1+2) CHECK (c>0) REFERENCES p(x) ON UPDATE CASCADE ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED, "
              "d DEFAULT -1, e DEFAULT +1.5, f DEFAULT true, g DEFAULT CURRENT_TIMESTAMP, h CONSTRAINT nn NOT NULL, "
              "CONSTRAINT pk PRIMARY KEY(a, b DESC) ON CONFLICT ABORT, UNIQUE(c, d), CHECK(d<e) ON CONFLICT ROLLBACK, "
              "FOREIGN KEY(e, f) REFERENCES p(x, y) NOT DEFERRABLE INITIALLY IMMEDIATE) WITHOUT ROWID, STRICT;",
              "CREATE TABLE t10 AS SELECT * FROM t;",
              "CREATE TRIGGER IF NOT EXISTS r9 BEFORE UPDATE OF a, b ON t FOR EACH ROW WHEN new.a>0 BEGIN "
              "SELECT RAISE(IGNORE); SELECT RAISE(ABORT, 'x'); SELECT RAISE(FAIL, 'y'); SELECT RAISE(ROLLBACK, 'z'); "
              "UPDATE OR REPLACE t2 SET a=new.a FROM t3 WHERE b=1; INSERT OR IGNORE INTO t2(a) SELECT 1 UPSERT; "
              "DELETE FROM t2 WHERE a=old.a; END;",
              "CREATE TRIGGER r10 INSTEAD OF DELETE ON v BEGIN INSERT INTO t2 DEFAULT VALUES; END;",
              "ALTER TABLE t RENAME TO t11;", "ALTER TABLE t ADD COLUMN z INTEGER DEFAULT 0 NOT NULL;",
              "ALTER TABLE t ADD y;", "ALTER TABLE t DROP COLUMN a;", "ALTER TABLE t RENAME COLUMN a TO aa;",
              "ALTER TABLE t RENAME b TO bb;", "ALTER TABLE t DROP CONSTRAINT c1;", "ALTER TABLE t ALTER COLUMN a DROP NOT NULL;",
              "ALTER TABLE t ALTER a SET NOT NULL ON CONFLICT ABORT;", "ALTER TABLE t ADD CONSTRAINT c2 CHECK (a > 0);",
              "ALTER TABLE t ADD CHECK (b IS NOT NULL) ON CONFLICT FAIL;",
              "ATTACH 'f.db' AS aux8;", "DETACH aux8;", "DETACH DATABASE aux8;", "VACUUM;", "VACUUM main;",
              "VACUUM INTO 'x.db';", "VACUUM temp INTO :f;", "PRAGMA foreign_keys;", "PRAGMA main.cache_size=-2000;",
              "PRAGMA table_info(t);", "PRAGMA page_size = +4096;", "PRAGMA x = ON;", "PRAGMA x = DELETE;",
              "PRAGMA x('y');", "PRAGMA x(-1.5);", "REINDEX;", "REINDEX nocase;", "REINDEX main.t;", "ANALYZE;",
              "ANALYZE t;", "ANALYZE main.t;", "EXPLAIN SELECT 1;", "EXPLAIN QUERY PLAN SELECT * FROM t;",
              "EXPLAIN QUERY PLAN WITH c AS (SELECT 1) DELETE FROM t WHERE a IN c;",
              "CREATE VIRTUAL TABLE IF NOT EXISTS temp.v5 USING fts5(a, b, tokenize='porter');",
              "CREATE VIRTUAL TABLE v6 USING m;", "CREATE VIRTUAL TABLE v7 USING m();",
              "SELECT 1; SELECT 2;", "-- only a comment", "/* only a comment */", "", "   ;  ; ",
              "SELECT 1\x00 garbage that is not read;", "SELECT 'a\x00b';",
              "INSERT INTO t DEFAULT VALUES RETURNING *, a+1 AS x;", "REPLACE INTO t(a) VALUES(1);",
              "INSERT OR ROLLBACK INTO t SELECT * FROM t2 ON CONFLICT DO NOTHING;",
              "INSERT INTO t(a,b) SELECT a,b FROM t2 WHERE true ON CONFLICT(a) WHERE b>0 DO UPDATE SET b=excluded.b WHERE a<>0 "
              "ON CONFLICT(b) DO NOTHING ON CONFLICT DO UPDATE SET c=1 RETURNING a;",
              "WITH RECURSIVE c(x) AS MATERIALIZED (SELECT 1 UNION ALL SELECT x+1 FROM c LIMIT 5), "
              "d AS NOT MATERIALIZED (SELECT 2) INSERT INTO t SELECT * FROM c, d;",
              "UPDATE OR ABORT t SET a=1, (b,c)=(SELECT 1,2), d=d+1 FROM t2 JOIN t3 USING(a) WHERE t.a=t2.a RETURNING *;",
              "UPDATE t NOT INDEXED SET a=1;", "UPDATE t INDEXED BY i SET a=1;", "DELETE FROM main.t AS x WHERE x.a=1 RETURNING x.b;",
              "DELETE FROM t INDEXED BY i;",
              "SELECT DISTINCT a, ALL b FROM t;", "SELECT ALL * , t.* FROM t;",
              "SELECT * FROM t AS x NATURAL LEFT OUTER JOIN t2 y USING (a) CROSS JOIN (SELECT 1) AS z RIGHT JOIN t3 ON 1 "
              "FULL OUTER JOIN t4, (t5 JOIN t6 ON 1) AS w INNER JOIN f(1,2) AS g;",
              "SELECT * FROM main.t INDEXED BY i NOT NULL;", "SELECT * FROM t NOT INDEXED;",
              "SELECT * FROM ((t));", "SELECT * FROM (t AS a), (t2 INDEXED BY i);", "SELECT * FROM (f(1));",
              "SELECT * FROM (SELECT 1) JOIN ((SELECT 2) JOIN (SELECT 3));",
              "SELECT a FROM t WHERE a IN t2 AND b NOT IN main.t3 AND c IN f(1,2) AND d IN ();",
              "SELECT a FROM t WHERE abs(a) NOT IN () AND count(a) IN () OR (a,b) IN (VALUES(1,2)) AND a IN (1);",
              "SELECT a NOT LIKE b ESCAPE c, a GLOB b, a REGEXP b, a MATCH b, a NOT MATCH b, a NOT GLOB b FROM t;",
              "SELECT a ISNULL, a NOTNULL, a NOT NULL, a IS NULL, a IS NOT NULL, 1 ISNULL, -'x' NOTNULL, +x'00' IS NULL FROM t;",
              "SELECT a BETWEEN 1 AND 2, a NOT BETWEEN b AND c, CASE a WHEN 1 THEN 2 ELSE 3 END, CASE WHEN a THEN b END FROM t;",
              "SELECT CAST(a AS VARCHAR(10)), CAST(b AS DECIMAL(5, -2)), CAST(c AS), CAST(d AS \"x y\" z) FROM t;",
              "SELECT a COLLATE nocase COLLATE \"rtrim\", ~a, -a, +a, - -a, - + -a, NOT a, a->'b', a->>'$.c' FROM t;",
              "SELECT EXISTS (SELECT 1), (SELECT 2), (a, b), (((a))) FROM t;",
              "SELECT a || b, a * b / c % d + e - f << g >> h & i | j, a < b, a <= b, a > b, a >= b, a = b, a == b, a <> b, a != b FROM t;",
              "SELECT a AND b OR c AND NOT d, a IS b, a IS NOT b, a IS NOT TRUE, a IS FALSE, true, FALSE, 'true', \"false\" FROM t;",
              "SELECT count(*), count(DISTINCT a), f(), current_time, current_date, current_timestamp, f(*) FROM t;",
              "SELECT a FROM t GROUP BY a, b HAVING count(*) > 1 ORDER BY a ASC NULLS FIRST, b DESC NULLS LAST, c NULLS LAST, d DESC NULLS FIRST LIMIT 1, 2;",
              "SELECT a FROM t LIMIT 1 OFFSET 2;",
              "SELECT a FROM t UNION SELECT b FROM t2 UNION ALL SELECT c FROM t3 INTERSECT SELECT d FROM t4 EXCEPT VALUES(1) ORDER BY 1 LIMIT 3;",
              "SELECT a FROM t WHERE a = (SELECT b FROM t2 WHERE b = (SELECT c FROM t3)) AND a IN (SELECT b FROM t2 ORDER BY 1);",
              "SELECT 'x' FROM t WHERE a IN (b, c, 1) AND a IN (1) AND a IN (?) AND a IN (b COLLATE x) AND (a,b) IN ((1,2),(3,4));",
              "SELECT 1 x, 2 \"y z\", 3 AS [w], 4 AS 'v', 5 'u' FROM t AS \"t\" ;",
              ]:
        a(x)
    return S


def write(path, recs):
    with open(path, 'w', encoding='utf-8', errors='surrogateescape') as f:
        for r in recs:
            f.write(r + '\n----\n')


def judged(drv, recs, d, name):
    """Each statement, the last line of its expected output (ok, error:
    or skip:), the rules it reduces and the state of its syntax error."""
    path = os.path.join(d, name + '.sql')
    write(path, recs)
    exp_path = os.path.join(d, name + '.exp')
    with open(exp_path, 'w') as f:
        old = sys.stdout
        sys.stdout = f
        try:
            oracle.expect(drv, path)
        finally:
            sys.stdout = old
    exp = open(exp_path, encoding='utf-8', errors='surrogateescape').read()
    last = {}
    for m in re.finditer(r'(?m)^#(\d+)\n(.*?)(?=^#\d+\n|\Z)', exp, re.S):
        last[int(m.group(1))] = m.group(2).rstrip('\n').split('\n')[-1]
    rules = {}
    for n, (trace, masked, result) in enumerate(oracle.outputs(drv, path, 'rules'), 1):
        rs = set(int(x) for x in re.findall(r'parser: Reduce (\d+) ', trace))
        st = ''
        k = trace.find('parser: Syntax Error!')
        if k >= 0:
            sts = re.findall(r"(?:go to state|in state) (\d+)", trace[:k])
            st = sts[-1] if sts else '-'
        rules[n] = (rs, st)
    return [(r, last[n], rules[n][0], rules[n][1]) for n, r in enumerate(recs, 1)]


def select(harv, muts):
    cand = harv + muts
    cover = {}
    for s, r, rs, st in harv:
        for x in rs:
            cover[x] = 2
    chosen = []
    pool = [c for c in harv if not c[1].startswith('skip')]
    while True:
        best, bs = None, 0
        for c in pool:
            g = sum(1 for x in c[2] if cover.get(x, 0) > 0)
            if g > bs or (g == bs and g > 0 and len(c[0]) < len(best[0])):
                best, bs = c, g
        if best is None or bs == 0:
            break
        chosen.append(best)
        pool.remove(best)
        for x in best[2]:
            if cover.get(x, 0) > 0:
                cover[x] -= 1
    bystate = {}
    for c in cand:
        if (c[1].startswith('error: near') or c[1] == 'error: incomplete input') and c[3]:
            k = (c[3], c[1].startswith('error: near'))
            if k not in bystate or len(c[0]) < len(bystate[k][0]):
                bystate[k] = c
    errs = [bystate[k] for k in sorted(bystate, key=lambda k: (int(k[0]) if k[0].isdigit() else 0, k[1]))]
    kinds = {}
    for c in cand:
        if c[1].startswith('error: ') and not c[1].startswith('error: near') and c[1] != 'error: incomplete input':
            kinds.setdefault(re.sub(r'(: ).*', r'\1', c[1]), []).append(c)
    for kind in sorted(kinds):
        errs += sorted(kinds[kind], key=lambda c: len(c[0]))[:3]
    out = []
    seen = set()
    for c in chosen + errs:
        if c[0] not in seen:
            seen.add(c[0])
            out.append(c[0])
    return out


def main():
    drv, corpus, expected = sys.argv[1:4]
    d = tempfile.mkdtemp(prefix='sqlparse-corpus-')
    harv = judged(drv, harvest(), d, 'harvest')
    ok = [c[0] for c in harv if c[1] == 'ok']
    muts = judged(drv, mutate(ok), d, 'mutate')
    recs = select(harv, muts) + hand()
    final = [c[0] for c in judged(drv, recs, d, 'final') if not c[1].startswith('skip')]
    write(corpus, final)
    with open(expected, 'w') as f:
        old = sys.stdout
        sys.stdout = f
        try:
            oracle.expect(drv, corpus)
        finally:
            sys.stdout = old
    sys.stderr.write('%d statements\n' % len(final))


if __name__ == '__main__':
    main()
