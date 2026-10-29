#!/usr/bin/env python3
"""gen_sqllogic.py SEED NQ OUT.test [nohash] | --check: a sqllogictest script of random schemas, data, statements and queries,
the answers made by SQLite itself (Python's sqlite3 module, the system's libsqlite3), for scripts/sqllogic.paslang
to check passqlite against. Everything comes from SEED: the same seed gives the same script.

The values of a query are rendered as sqllogictest.c renders them by the type string of each column (T the text
SQLite gives, I the low 32 bits of the integer, R as printf('%.3f')), each through SQLite so that the oracle and the
runner convert alike. A query that fails in SQLite is written as a statement that must fail."""
import random
import sqlite3
import sys

INTS = [0, 1, -1, 2, 3, 5, 7, 10, 42, 100, -100, 255, 256, 1000, 65535, 2147483647, 2147483648, -2147483648,
        4294967296, 4611686018427387904, -9223372036854775808, 123456789012, 9007199254740992, 9007199254740993,
        -9007199254740993, 1000000, 99999999999]
REALS = [0.0, 0.5, 1.5, -2.25, 3.14159, 100.0, 1e10, 1e-5, -1e15, 123456789.123, 0.1, 0.2, 2.5, -0.0, 1e300, 5e-324,
         1.7976931348623157e308, 2.2250738585072014e-308, 0.30000000000000004, 1e15, 1e16, 123456789012345680.0, 4.35,
         -4.35e-7, 9007199254740993.0, 1.0000000000000002, 0.5e-3, 1e21, 3.0, 255.0]
TEXTS = ['', 'a', 'b', 'abc', 'ABC', 'aBc', 'Hello World', 'hello', 'x y z', '12', '1.5e3', ' 7 ', '0x1F', '-3',
         'café', '日本語', 'z' * 40, 'a%b', 'a_b', "it's", 'tab\there', 'NULL', 'true', '2020-02-29',
         '2021-12-31 23:59:59', '1e999', '.5', '+8', 'e5', 'AbC dEf', '\U0001F600', '0x10', '1e', '1e5', '  12  ', '12abc',
         '-', '+', '.', '1.', 'inf', '-inf', 'NaN', 'Infinity', '9223372036854775808', '-9223372036854775809', '1e400',
         '0.1e1', '00012', '1_000', '\u0663\u0662', 'a\u0301', 'ss\u00df', '\u0130i', '0.30000000000000004', '5.', '-0']
BLOBS = ["X''", "X'00'", "X'00ff'", "X'616263'", "X'ffffffff'", "X'30'", "X'4142'"]
DECL = ['INTEGER', 'REAL', 'TEXT', 'BLOB', 'NUMERIC', '', 'VARCHAR(20)', 'BOOLEAN', 'DATE', 'INT', 'FLOAT', 'CHAR(5)']
COLL = ['', '', '', ' COLLATE NOCASE', ' COLLATE BINARY', ' COLLATE RTRIM']


NOHASH = False


class Gen:
    def __init__(self, seed, db):
        self.r = random.Random(seed)
        self.db = db
        self.out = []
        self.tables = {}      # name -> [column names]
        self.nq = 0
        self.depth = 0
        self.bn = 0

    # ---- the script
    def emit(self, *ls):
        self.out.extend(ls)

    def stmt(self, sql, sub=False):
        try:
            self.db.execute(sql)
        except sqlite3.Error as ex:
            self.emit('# SQLite: ' + str(ex).replace('\n', ' '), 'statement error', sql, '')
            return False
        self.emit('statement ok', sql, '')
        return True

    def render(self, v, ty):
        """The text the runner writes for the value V of a column of type TY."""
        if v is None:
            return 'NULL'
        if ty == 'I':
            n = self.db.execute('SELECT CAST(? AS INTEGER)', (v,)).fetchone()[0] & 0xFFFFFFFF
            if n >= 0x80000000:
                n -= 0x100000000
            return str(n)
        if ty == 'R':
            return self.db.execute("SELECT printf('%.3f', CAST(? AS REAL))", (v,)).fetchone()[0].decode('ascii')
        if isinstance(v, bytes):
            b = v
        elif isinstance(v, str):
            b = v.encode('utf-8')
        else:
            b = self.db.execute('SELECT CAST(? AS TEXT)', (v,)).fetchone()[0]
        if len(b) == 0:
            return '(empty)'
        return ''.join(chr(c) if 32 <= c <= 126 else '@' for c in b)

    def query(self, sql, ncol, ordered):
        try:
            cur = self.db.execute(sql)
            rows = cur.fetchall()
            if ncol is None:
                ncol = len(cur.description) if cur.description else 0
        except sqlite3.Error as ex:
            self.emit('# SQLite: ' + str(ex).replace('\n', ' '), 'statement error', sql, '')
            return
        if ncol == 0:
            self.emit('statement ok', sql, '')
            return
        ty = ''.join(self.r.choice('TTTTIR') for _ in range(ncol))
        vals = []
        for row in rows:
            for k in range(ncol):
                vals.append((self.render(row[k], ty[k])))
        if any((v != '' and v.strip(' \t\n\v\f\r') == '') or v[:1] == '#' or v == '----' for v in vals):
            return          # not writable: the format reads a line of white space as empty, one starting with # as a comment
        mode = 'nosort' if ordered else 'rowsort'
        if not ordered:
            rws = [vals[i:i + ncol] for i in range(0, len(vals), ncol)]
            rws.sort(key=lambda w: [x.encode('utf-8', 'surrogateescape') for x in w])
            vals = [x for w in rws for x in w]
        self.nq += 1
        self.emit('query %s %s' % (ty, mode), sql, '----')
        if len(vals) > 8 and not NOHASH:
            import hashlib
            h = hashlib.md5(''.join(x + '\n' for x in vals).encode('utf-8')).hexdigest()
            self.emit('%d values hashing to %s' % (len(vals), h))
        else:
            self.emit(*vals)
        self.emit('')

    # ---- schema and data
    def literal(self, kind=None):
        r = self.r
        k = kind or r.choice('iiirrttbn')
        if k == 'i':
            return str(r.choice(INTS) if r.random() < 0.5 else r.randint(-20, 20))
        if k == 'r':
            return repr(r.choice(REALS))
        if k == 't':
            return "'" + r.choice(TEXTS).replace("'", "''") + "'"
        if k == 'b':
            return r.choice(BLOBS)
        return 'NULL'

    def make_table(self, name):
        r = self.r
        n = r.randint(2, 5)
        cols = ['c%d' % i for i in range(n)]
        defs = []
        pk = r.random() < 0.3
        for i, c in enumerate(cols):
            d = r.choice(DECL)
            s = c + (' ' + d if d else '')
            if i == 0 and pk:
                s += ' PRIMARY KEY'
            elif r.random() < 0.1:
                s += ' NOT NULL DEFAULT ' + self.literal('i')
            elif r.random() < 0.1:
                s += ' DEFAULT ' + self.literal()
            elif r.random() < 0.08:
                s += ' UNIQUE'
            s += r.choice(COLL) if d.startswith(('TEXT', 'VARCHAR', 'CHAR')) or d == '' else ''
            defs.append(s)
        tail = ''
        if r.random() < 0.1 and n > 2:
            tail = ', CHECK (%s IS NOT 99)' % cols[1]
        wr = ' WITHOUT ROWID' if pk and r.random() < 0.25 else ''
        if self.stmt('CREATE TABLE %s (%s%s)%s' % (name, ', '.join(defs), tail, wr)):
            self.tables[name] = cols
            nrows = r.randint(5, 40)
            for _ in range(nrows):
                vs = [self.literal() for _ in cols]
                if r.random() < 0.15:
                    vs = [self.literal('i') for _ in cols]
                self.stmt('INSERT OR IGNORE INTO %s VALUES (%s)' % (name, ', '.join(vs)))
            for _ in range(r.randint(0, 3)):
                cs = r.sample(cols, r.randint(1, min(2, n)))
                ix = 'CREATE %sINDEX %s_i%d ON %s (%s)' % (
                    'UNIQUE ' if False else '', name, r.randint(0, 99999), name,
                    ', '.join(c + r.choice(['', '', ' DESC', ' COLLATE NOCASE']) for c in cs))
                if r.random() < 0.2:
                    ix += ' WHERE %s IS NOT NULL' % cols[0]
                self.stmt(ix)

    # ---- expressions
    def col(self, scope):
        return self.r.choice(scope)

    def expr(self, scope, depth=0):
        r = self.r
        if depth >= 3 or r.random() < 0.25 + 0.15 * depth:
            return self.col(scope) if scope and r.random() < 0.7 else self.literal()
        k = r.randint(0, 22)
        e = lambda: self.expr(scope, depth + 1)
        if k == 0:
            return '(%s %s %s)' % (e(), r.choice(['+', '-', '*', '/', '%', '||', '&', '|', '<<', '>>']), e())
        if k == 1:
            return '(%s %s %s)' % (e(), r.choice(['=', '<>', '<', '<=', '>', '>=', 'IS', 'IS NOT', '==', '!=']), e())
        if k == 2:
            return '(%s %s %s)' % (e(), r.choice(['AND', 'OR']), e())
        if k == 3:
            return '(%s%s)' % (r.choice(['-', '+', '~', 'NOT ']), e())
        if k == 4:
            return '(%s %sBETWEEN %s AND %s)' % (e(), r.choice(['', 'NOT ']), e(), e())
        if k == 5:
            return '(%s %sIN (%s))' % (e(), r.choice(['', 'NOT ']), ', '.join(e() for _ in range(r.randint(1, 4))))
        if k == 6:
            return '(%s %s %s)' % (e(), r.choice(['LIKE', 'NOT LIKE', 'GLOB', 'NOT GLOB']),
                                   "'" + r.choice(['%', 'a%', '%b', 'a_c', 'A*', '*c', '[a-c]*', '?b?', '%é%', '1%']) + "'")
        if k == 7:
            return '(CASE %s WHEN %s THEN %s WHEN %s THEN %s ELSE %s END)' % (e(), e(), e(), e(), e(), e())
        if k == 8:
            return '(CASE WHEN %s THEN %s WHEN %s THEN %s END)' % (e(), e(), e(), e())
        if k == 9:
            return 'CAST(%s AS %s)' % (e(), r.choice(['INTEGER', 'REAL', 'TEXT', 'BLOB', 'NUMERIC', 'INT', 'VARCHAR(3)']))
        if k == 10:
            return '(%s COLLATE %s)' % (e(), r.choice(['NOCASE', 'BINARY', 'RTRIM']))
        if k == 11:
            return '(%s IS %sNULL)' % (e(), r.choice(['', 'NOT ']))
        f = r.choice([
            ('abs', 1), ('length', 1), ('lower', 1), ('upper', 1), ('typeof', 1), ('hex', 1), ('quote', 1),
            ('unicode', 1), ('sign', 1), ('likely', 1), ('unlikely', 1), ('trim', 1), ('ltrim', 1), ('rtrim', 1),
            ('trim', 2), ('ltrim', 2), ('rtrim', 2), ('instr', 2), ('nullif', 2), ('ifnull', 2), ('round', 1),
            ('round', 2), ('substr', 2), ('substr', 3), ('replace', 3), ('coalesce', 2), ('coalesce', 3),
            ('iif', 3), ('max', 2), ('min', 2), ('max', 3), ('printf', 2), ('char', 2), ('octet_length', 1),
            ('substring', 2), ('unhex', 1), ('concat', 3), ('concat_ws', 3), ('format', 2), ('ceil', 1),
            ('floor', 1), ('sqrt', 1), ('ln', 1), ('exp', 1), ('pow', 2), ('mod', 2), ('sin', 1), ('atan2', 2),
            ('hex', 1), ('zeroblob', 1), ('unistr', 1), ('glob', 2), ('like', 2),
            ('date', 2), ('time', 2), ('datetime', 2), ('julianday', 1), ('strftime', 2), ('unixepoch', 1),
            ('json_extract', 2), ('json_type', 1), ('json_valid', 1), ('json_array_length', 1), ('json_quote', 1),
            ('changes', 0),
        ])
        name, n = f
        if name == 'printf':
            fmt = r.choice(["'%d'", "'%5.2f'", "'%s'", "'%x'", "'%05d'", "'%e'", "'%g'", "'%q'", "'%-6s|'", "'%+d'",
                            "'%c'", "'%3$s %1$s'", "'%.3s'", "'%o'", "'%X'", "'%i'", "'%,d'", "'%!.15g'"])
            return 'printf(%s, %s)' % (fmt, e())
        if name == 'format':
            return 'format(%s, %s)' % (r.choice(["'%d'", "'%s'", "'%f'", "'%.3e'"]), e())
        if name == 'char':
            return 'char(%d, %d)' % (r.randint(1, 255), r.randint(1, 30000))
        if name == 'zeroblob':
            return 'zeroblob(%d)' % r.randint(0, 5)
        if name == 'unistr':
            return "unistr('a\\u00e9b')"
        if name == 'strftime':
            return "strftime(%s, %s)" % (r.choice(["'%Y-%m-%d'", "'%H:%M:%S'", "'%j'", "'%w'", "'%s'", "'%f'", "'%J'", "'%W'", "'%u'", "'%%'", "'%Y-%m-%dT%H:%M:%f'"]),
                                          r.choice(["'2020-02-29 12:34:56.789'", "'2000-01-01'", "'now' < 0", "2459000.5", "'1970-01-01 00:00:01'", "0", "1700000000", e()]))
        if name in ('date', 'time', 'datetime'):
            return "%s(%s, %s)" % (name, r.choice(["'2020-02-29 12:34:56'", "'2024-12-31'", "'12:00'", "0", "2459000.5", "'1900-01-01'", e()]),
                                   r.choice(["'+1 day'", "'-1 month'", "'start of month'", "'+1 year'", "'weekday 1'", "'unixepoch'", "'+3 hours'", "'start of year'", "'ceiling'", "'subsec'"]))
        if name == 'julianday' or name == 'unixepoch':
            return "%s(%s)" % (name, r.choice(["'2020-02-29 12:34:56'", "'2000-01-01'", "0", "2459000.5", e()]))
        if name.startswith('json'):
            doc = r.choice(["'{\"a\":1,\"b\":[1,2,3],\"c\":{\"d\":\"x\"}}'", "'[1,2,{\"k\":null}]'", "'[]'", "'{}'", "'3.5'", "'\"s\"'", "'nope'", e()])
            if name == 'json_extract':
                return 'json_extract(%s, %s)' % (doc, r.choice(["'$.a'", "'$.b[1]'", "'$.c.d'", "'$[2].k'", "'$'", "'$.zz'", "'$.b[#-1]'"]))
            return '%s(%s)' % (name, doc)
        args = ', '.join(e() for _ in range(n))
        return '%s(%s)' % (name, args)

    def cond(self, scope):
        return self.expr(scope, 1)

    # ---- queries
    def select_list(self, scope, n):
        return [self.expr(scope) for _ in range(n)]

    def simple_select(self):
        r = self.r
        t = r.choice(list(self.tables))
        cols = self.tables[t]
        scope = [t + '.' + c for c in cols] if r.random() < 0.3 else list(cols)
        n = r.randint(1, 4)
        sel = self.select_list(scope, n)
        d = 'DISTINCT ' if r.random() < 0.15 else ''
        sql = 'SELECT %s%s FROM %s' % (d, ', '.join(sel), t)
        if r.random() < 0.7:
            sql += ' WHERE ' + self.cond(scope)
        ordered = False
        if r.random() < 0.5:
            sql += ' ORDER BY ' + ', '.join(str(i + 1) + r.choice(['', ' DESC', ' ASC', ' NULLS FIRST', ' NULLS LAST']) for i in range(n))
            ordered = True
            if r.random() < 0.4:
                sql += ' LIMIT %d' % r.randint(0, 6)
                if r.random() < 0.5:
                    sql += ' OFFSET %d' % r.randint(0, 4)
        return sql, n, ordered

    def join_select(self):
        r = self.r
        names = list(self.tables)
        t1, t2 = r.choice(names), r.choice(names)
        a1, a2 = 'x', 'y'
        scope = ['%s.%s' % (a1, c) for c in self.tables[t1]] + ['%s.%s' % (a2, c) for c in self.tables[t2]]
        n = r.randint(1, 4)
        sel = self.select_list(scope, n)
        kind = r.choice(['JOIN', 'LEFT JOIN', 'CROSS JOIN', 'INNER JOIN', 'LEFT OUTER JOIN'])
        if r.random() < 0.15:
            kind = 'RIGHT JOIN' if r.random() < 0.5 else 'FULL OUTER JOIN'
        on = self.cond(scope) if kind != 'CROSS JOIN' or r.random() < 0.5 else '1'
        sql = 'SELECT %s FROM %s %s %s %s ON %s' % (', '.join(sel), t1, a1, kind, t2 + ' ' + a2, on)
        if r.random() < 0.4:
            sql += ' WHERE ' + self.cond(scope)
        ordered = True
        sql += ' ORDER BY ' + ', '.join(str(i + 1) for i in range(n))
        return sql, n, ordered

    def group_select(self):
        r = self.r
        t = r.choice(list(self.tables))
        cols = self.tables[t]
        g = r.choice(cols)
        aggs = []
        for _ in range(r.randint(1, 3)):
            c = self.expr(cols, 2)
            a = r.choice(['count(*)', 'count(%s)' % c, 'count(DISTINCT %s)' % c, 'sum(%s)' % c, 'total(%s)' % c,
                          'avg(%s)' % c, 'min(%s)' % c, 'max(%s)' % c, 'group_concat(%s)' % c,
                          "group_concat(%s, '|')" % c, 'sum(DISTINCT %s)' % c, 'min(%s, %s)' % (c, g),
                          "group_concat(%s, ',' ORDER BY %s)" % (c, g), 'median(%s)' % c if False else 'count(1)'])
            if r.random() < 0.2:
                a += ' FILTER (WHERE %s)' % self.cond(cols)
            aggs.append(a)
        sql = 'SELECT %s, %s FROM %s' % (g, ', '.join(aggs), t)
        if r.random() < 0.4:
            sql += ' WHERE ' + self.cond(cols)
        sql += ' GROUP BY ' + g
        if r.random() < 0.3:
            sql += ' HAVING %s' % r.choice(['count(*) > 1', 'count(*) >= 0', 'sum(%s) IS NOT NULL' % g, 'max(%s) IS NULL' % g])
        n = 1 + len(aggs)
        sql += ' ORDER BY ' + ', '.join(str(i + 1) for i in range(n))
        return sql, n, True

    def sub_select(self):
        r = self.r
        names = list(self.tables)
        t1, t2 = r.choice(names), r.choice(names)
        c1, c2 = r.choice(self.tables[t1]), r.choice(self.tables[t2])
        form = r.randint(0, 4)
        if form == 0:
            sql = 'SELECT %s FROM %s WHERE %s IN (SELECT %s FROM %s)' % (c1, t1, c1, c2, t2)
        elif form == 1:
            sql = 'SELECT %s FROM %s a WHERE EXISTS (SELECT 1 FROM %s b WHERE b.%s = a.%s)' % (c1, t1, t2, c2, c1)
        elif form == 2:
            sql = 'SELECT %s, (SELECT max(%s) FROM %s) FROM %s' % (c1, c2, t2, t1)
        elif form == 3:
            sql = 'SELECT %s, (SELECT count(*) FROM %s b WHERE b.%s <= a.%s) FROM %s a' % (c1, t2, c2, c1, t1)
        else:
            sql = 'SELECT %s FROM %s WHERE %s NOT IN (SELECT %s FROM %s WHERE %s IS NOT NULL)' % (c1, t1, c1, c2, t2, c2)
        n = 2 if form in (2, 3) else 1
        sql += ' ORDER BY ' + ', '.join(str(i + 1) for i in range(n))
        return sql, n, True

    def compound_select(self):
        r = self.r
        names = list(self.tables)
        parts = []
        n = r.randint(1, 2)
        for _ in range(r.randint(2, 3)):
            t = r.choice(names)
            parts.append('SELECT %s FROM %s' % (', '.join(self.expr(self.tables[t], 2) for _ in range(n)), t))
        sql = parts[0]
        for p in parts[1:]:
            sql += ' %s %s' % (r.choice(['UNION', 'UNION ALL', 'INTERSECT', 'EXCEPT']), p)
        sql += ' ORDER BY ' + ', '.join(str(i + 1) for i in range(n))
        return sql, n, True

    def window_select(self):
        r = self.r
        t = r.choice(list(self.tables))
        cols = self.tables[t]
        pc, oc, vc = r.choice(cols), r.choice(cols), r.choice(cols)
        fn = r.choice(['row_number()', 'rank()', 'dense_rank()', 'percent_rank()', 'cume_dist()', 'ntile(3)',
                       'lag(%s)' % vc, 'lead(%s, 1, 0)' % vc, 'first_value(%s)' % vc, 'last_value(%s)' % vc,
                       'nth_value(%s, 2)' % vc, 'sum(%s)' % vc, 'count(*)', 'min(%s)' % vc, 'max(%s)' % vc,
                       'avg(%s)' % vc, 'group_concat(%s)' % vc, 'total(%s)' % vc])
        part = 'PARTITION BY %s ' % pc if r.random() < 0.5 else ''
        frame = r.choice(['', '', ' ROWS BETWEEN 1 PRECEDING AND CURRENT ROW', ' ROWS UNBOUNDED PRECEDING',
                          ' RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING', ' ROWS BETWEEN 1 FOLLOWING AND 2 FOLLOWING',
                          ' GROUPS BETWEEN 1 PRECEDING AND 1 FOLLOWING', ' ROWS BETWEEN CURRENT ROW AND CURRENT ROW EXCLUDE TIES'])
        sql = 'SELECT %s, %s, %s OVER (%sORDER BY %s%s) FROM %s ORDER BY 1, 2, 3' % (
            pc, oc, fn, part, oc + r.choice(['', ' DESC']), frame, t)
        return sql, 3, True

    def cte_select(self):
        r = self.r
        if r.random() < 0.5:
            sql = ('WITH RECURSIVE c(x, y) AS (SELECT 1, %s UNION ALL SELECT x + 1, y * 2 FROM c WHERE x < %d) '
                   'SELECT x, y FROM c ORDER BY 1') % (self.literal('i'), r.randint(1, 12))
            return sql, 2, True
        t = r.choice(list(self.tables))
        cols = self.tables[t]
        sql = 'WITH w AS (SELECT %s AS a, %s AS b FROM %s) SELECT a, b, count(*) FROM w GROUP BY 1, 2 ORDER BY 1, 2, 3' % (
            self.expr(cols, 2), self.expr(cols, 2), t)
        return sql, 3, True

    def pure_select(self):
        n = self.r.randint(1, 4)
        return 'SELECT ' + ', '.join(self.expr([], 0) for _ in range(n)), n, False

    def values_select(self):
        r = self.r
        n = r.randint(1, 3)
        rows = ', '.join('(' + ', '.join(self.literal() for _ in range(n)) + ')' for _ in range(r.randint(1, 5)))
        return 'SELECT * FROM (VALUES %s) ORDER BY %s' % (rows, ', '.join(str(i + 1) for i in range(n))), n, True

    def dml(self):
        r = self.r
        t = r.choice(list(self.tables))
        cols = self.tables[t]
        k = r.randint(0, 6)
        if k == 0:
            self.stmt('INSERT OR %s INTO %s VALUES (%s)' % (r.choice(['IGNORE', 'REPLACE', 'ABORT']), t, ', '.join(self.literal() for _ in cols)))
        elif k == 1:
            self.stmt('UPDATE %s SET %s = %s WHERE %s' % (t, r.choice(cols), self.expr(cols, 2), self.cond(cols)))
        elif k == 2:
            self.stmt('DELETE FROM %s WHERE %s' % (t, self.cond(cols)))
        elif k == 3:
            self.stmt('INSERT OR IGNORE INTO %s SELECT %s FROM %s' % (t, ', '.join(self.expr(self.tables[t], 2) for _ in cols), t))
        elif k == 4:
            self.stmt('UPDATE OR IGNORE %s SET %s = %s' % (t, r.choice(cols), self.expr(cols, 2)))
        elif k == 5:
            c = cols[0]
            self.stmt('INSERT INTO %s (%s) VALUES (%s) ON CONFLICT DO NOTHING' % (t, c, self.literal('i')))
        else:
            self.stmt('REPLACE INTO %s VALUES (%s)' % (t, ', '.join(self.literal('i') for _ in cols)))
        # the whole table afterwards
        n = len(cols)
        self.query('SELECT * FROM %s ORDER BY %s' % (t, ', '.join(str(i + 1) for i in range(n))), n, True)


    # ---- schema blocks: DDL, triggers, constraints, pragmas, storage
    def block(self):
        """A little scenario with tables of its own, then the schema and the file's shape asked back."""
        r = self.r
        self.bn += 1
        p = 'b%d' % self.bn
        kind = r.randint(0, 9)
        qs = []
        if kind == 0:      # alter table
            self.stmt('CREATE TABLE %s_a (x INTEGER PRIMARY KEY, y TEXT, z REAL DEFAULT 1.5)' % p)
            for _ in range(r.randint(2, 6)):
                self.stmt("INSERT INTO %s_a (y, z) VALUES (%s, %s)" % (p, self.literal('t'), self.literal('r')))
            for _ in range(r.randint(1, 4)):
                a = r.choice([
                    'ALTER TABLE %s_a ADD COLUMN w%d %s DEFAULT %s' % (p, r.randint(0, 9), r.choice(['INTEGER', 'TEXT', '', 'REAL']), self.literal()),
                    'ALTER TABLE %s_a RENAME COLUMN y TO yy' % p, 'ALTER TABLE %s_a RENAME COLUMN z TO zz' % p,
                    'ALTER TABLE %s_a DROP COLUMN z' % p, 'ALTER TABLE %s_a DROP COLUMN y' % p,
                    'ALTER TABLE %s_a RENAME TO %s_b' % (p, p), 'CREATE INDEX %s_ix ON %s_a (y, z)' % (p, p),
                    'CREATE VIEW %s_v AS SELECT x, y FROM %s_a' % (p, p),
                    'CREATE TRIGGER %s_t AFTER INSERT ON %s_a BEGIN SELECT 1; END' % (p, p)])
                self.stmt(a)
        elif kind == 1:    # triggers writing a log
            self.stmt('CREATE TABLE %s_t (a INTEGER PRIMARY KEY, b TEXT)' % p)
            self.stmt('CREATE TABLE %s_l (n INTEGER PRIMARY KEY AUTOINCREMENT, ev TEXT, ov, nv)' % p)
            for ev, body in [('INSERT', "INSERT INTO %s_l (ev, nv) VALUES ('ins', new.b)" % p),
                             ('UPDATE', "INSERT INTO %s_l (ev, ov, nv) VALUES ('upd', old.b, new.b)" % p),
                             ('DELETE', "INSERT INTO %s_l (ev, ov) VALUES ('del', old.b)" % p)]:
                when = r.choice(['', ' WHEN new.a > 2' if ev != 'DELETE' else ' WHEN old.a > 2'])
                self.stmt('CREATE TRIGGER %s_%s %s %s ON %s_t%s BEGIN %s; END' % (p, ev[:1], r.choice(['AFTER', 'BEFORE']), ev, p, when, body))
            for _ in range(r.randint(3, 10)):
                a = r.choice(["INSERT INTO %s_t (b) VALUES (%s)" % (p, self.literal('t')),
                              "UPDATE %s_t SET b = b || 'x' WHERE a %% 2 = %d" % (p, r.randint(0, 1)),
                              "DELETE FROM %s_t WHERE a = %d" % (p, r.randint(1, 8)),
                              "INSERT OR REPLACE INTO %s_t VALUES (%d, %s)" % (p, r.randint(1, 8), self.literal('t'))])
                self.stmt(a)
            qs += ['SELECT n, ev, ov, nv FROM %s_l ORDER BY n' % p, 'SELECT a, b FROM %s_t ORDER BY a' % p]
        elif kind == 2:    # constraints and conflict clauses
            self.stmt('CREATE TABLE %s_c (a INTEGER PRIMARY KEY, b TEXT UNIQUE, c INTEGER NOT NULL DEFAULT 5 CHECK (c < 100), d REAL)' % p)
            for _ in range(r.randint(4, 14)):
                v = (self.literal('i'), self.literal('t'), self.literal('i'), self.literal('r'))
                a = r.choice(['INSERT', 'INSERT OR IGNORE', 'INSERT OR REPLACE', 'INSERT OR ROLLBACK', 'INSERT OR FAIL'])
                self.stmt('%s INTO %s_c VALUES (%s)' % (a, p, ', '.join(v)))
            self.stmt("INSERT INTO %s_c (a, b) VALUES (1, 'u') ON CONFLICT (a) DO UPDATE SET c = c + 1, b = excluded.b || '!'" % p)
            self.stmt("INSERT INTO %s_c (a, b) VALUES (2, 'v') ON CONFLICT (b) DO NOTHING" % p)
            qs += ['SELECT a, b, c, d FROM %s_c ORDER BY 1, 2, 3, 4' % p]
        elif kind == 3:    # generated columns and strict tables
            self.stmt('CREATE TABLE %s_g (a INTEGER, b INTEGER, c AS (a + b) VIRTUAL, d AS (a * b) STORED, e TEXT AS (printf(\'%%d-%%d\', a, b)))' % p)
            for _ in range(r.randint(2, 8)):
                self.stmt('INSERT INTO %s_g (a, b) VALUES (%s, %s)' % (p, self.literal('i'), self.literal('i')))
            self.stmt('CREATE TABLE %s_s (a INTEGER, b TEXT, c REAL, d ANY, e BLOB) STRICT' % p)
            for _ in range(r.randint(3, 8)):
                self.stmt('INSERT INTO %s_s VALUES (%s)' % (p, ', '.join(self.literal(k) for k in r.choice(['itrbn', 'iiiii', 'ttttt', 'nnnnn', 'irtbi']))))
            qs += ['SELECT a, b, c, d, e FROM %s_g ORDER BY 1, 2, 3, 4, 5' % p,
                   'SELECT a, typeof(a), b, typeof(b), c, typeof(c), d, typeof(d), e, typeof(e) FROM %s_s ORDER BY 1, 2, 3, 4' % p]
        elif kind == 4:    # foreign keys
            self.stmt('PRAGMA foreign_keys = ON')
            act = r.choice(['CASCADE', 'SET NULL', 'RESTRICT', 'NO ACTION', 'SET DEFAULT'])
            act2 = r.choice(['CASCADE', 'SET NULL', 'RESTRICT', 'NO ACTION'])
            self.stmt('CREATE TABLE %s_p (id INTEGER PRIMARY KEY, name TEXT UNIQUE)' % p)
            self.stmt('CREATE TABLE %s_k (n INTEGER PRIMARY KEY, pid INTEGER DEFAULT 1 REFERENCES %s_p (id) ON DELETE %s ON UPDATE %s, tag TEXT)' % (p, p, act, act2))
            for i in range(1, r.randint(3, 6)):
                self.stmt("INSERT INTO %s_p VALUES (%d, 'p%d')" % (p, i, i))
            for _ in range(r.randint(2, 8)):
                self.stmt("INSERT INTO %s_k (pid, tag) VALUES (%d, 'k')" % (p, r.randint(0, 6)))
            for _ in range(r.randint(1, 3)):
                self.stmt(r.choice(["DELETE FROM %s_p WHERE id = %d" % (p, r.randint(1, 5)),
                                    "UPDATE %s_p SET id = id + 10 WHERE id = %d" % (p, r.randint(1, 5))]))
            qs += ['SELECT id, name FROM %s_p ORDER BY 1' % p, 'SELECT n, pid, tag FROM %s_k ORDER BY 1' % p,
                   'PRAGMA foreign_key_check', 'PRAGMA foreign_key_list(%s_k)' % p]
            self.stmt('PRAGMA foreign_keys = OFF')
        elif kind == 5:    # transactions and savepoints
            self.stmt('CREATE TABLE %s_x (a INTEGER PRIMARY KEY, b)' % p)
            self.stmt('INSERT INTO %s_x (b) VALUES (1), (2), (3)' % p)
            self.stmt('BEGIN')
            self.stmt('INSERT INTO %s_x (b) VALUES (4)' % p)
            self.stmt('SAVEPOINT s1')
            self.stmt('DELETE FROM %s_x WHERE b < 3' % p)
            self.stmt('SAVEPOINT s2')
            self.stmt("UPDATE %s_x SET b = b * 10" % p)
            qs += ['SELECT a, b FROM %s_x ORDER BY 1' % p]
            self.stmt(r.choice(['ROLLBACK TO s2', 'ROLLBACK TO s1', 'RELEASE s1']))
            qs += ['SELECT a, b FROM %s_x ORDER BY 1' % p]
            self.stmt(r.choice(['COMMIT', 'ROLLBACK']))
            qs += ['SELECT a, b FROM %s_x ORDER BY 1' % p]
        elif kind == 6:    # returning and upsert with a rich table
            self.stmt('CREATE TABLE %s_r (id INTEGER PRIMARY KEY, v TEXT, n INTEGER DEFAULT 0)' % p)
            for i in range(r.randint(2, 6)):
                qs.append("INSERT INTO %s_r (v) VALUES (%s) RETURNING id, v, n + 1" % (p, self.literal('t')))
            qs.append("UPDATE %s_r SET n = n + id RETURNING id, n" % p)
            qs.append("DELETE FROM %s_r WHERE id %% 2 = 0 RETURNING *" % p)
            qs.append("INSERT INTO %s_r VALUES (1, 'again', 5) ON CONFLICT (id) DO UPDATE SET n = n + excluded.n RETURNING *" % p)
        elif kind == 7:    # indexes, analyze, the stat table
            self.stmt('CREATE TABLE %s_i (a INTEGER, b TEXT, c REAL)' % p)
            for _ in range(r.randint(20, 80)):
                self.stmt("INSERT INTO %s_i VALUES (%d, 'k%d', %s)" % (p, r.randint(0, 6), r.randint(0, 30), self.literal('r')))
            self.stmt('CREATE INDEX %s_i1 ON %s_i (a)' % (p, p))
            self.stmt('CREATE INDEX %s_i2 ON %s_i (b, a DESC) WHERE c IS NOT NULL' % (p, p))
            self.stmt('CREATE INDEX %s_i3 ON %s_i (lower(b), a + 1)' % (p, p))
            qs += ['SELECT count(*) FROM %s_i WHERE a = %d' % (p, r.randint(0, 6)),
                   'SELECT min(b), max(b), count(DISTINCT b) FROM %s_i' % p, 'PRAGMA integrity_check', 'PRAGMA index_list(%s_i)' % p,
                   'PRAGMA index_xinfo(%s_i2)' % p]
        elif kind == 8:    # views with joins, nested, and compound views
            self.stmt('CREATE TABLE %s_u (a, b)' % p)
            self.stmt('CREATE TABLE %s_w (a, c)' % p)
            for _ in range(r.randint(3, 9)):
                self.stmt('INSERT INTO %s_u VALUES (%d, %s)' % (p, r.randint(1, 5), self.literal('t')))
                self.stmt('INSERT INTO %s_w VALUES (%d, %s)' % (p, r.randint(1, 5), self.literal('i')))
            self.stmt('CREATE VIEW %s_v1 AS SELECT u.a AS a, b, c FROM %s_u u JOIN %s_w w ON u.a = w.a' % (p, p, p))
            self.stmt('CREATE VIEW %s_v2 AS SELECT a, count(*) AS n, group_concat(b) AS bs FROM %s_v1 GROUP BY a' % (p, p))
            self.stmt('CREATE VIEW %s_v3 AS SELECT a FROM %s_u UNION SELECT a FROM %s_w' % (p, p, p))
            qs += ['SELECT a, b, c FROM %s_v1 ORDER BY 1, 2, 3' % p, 'SELECT a, n FROM %s_v2 ORDER BY 1, 2' % p,
                   'SELECT a FROM %s_v3 ORDER BY 1' % p]
            self.stmt('CREATE TRIGGER %s_io INSTEAD OF INSERT ON %s_v1 BEGIN INSERT INTO %s_u VALUES (new.a, new.b); END' % (p, p, p))
            self.stmt("INSERT INTO %s_v1 VALUES (9, 'z', 1)" % p)
            qs += ['SELECT a, b FROM %s_u ORDER BY 1, 2' % p]
        else:              # the file's shape after bulk changes
            self.stmt('CREATE TABLE %s_f (a INTEGER PRIMARY KEY, b TEXT, c BLOB)' % p)
            self.stmt('CREATE INDEX %s_fi ON %s_f (b)' % (p, p))
            for i in range(r.randint(30, 120)):
                self.stmt("INSERT INTO %s_f (b, c) VALUES ('%s', zeroblob(%d))" % (p, 'v%d' % r.randint(0, 500) + 'x' * r.randint(0, 80), r.choice([0, 10, 200, 1500, 5000])))
            self.stmt('DELETE FROM %s_f WHERE a %% 3 = 0' % p)
            if r.random() < 0.5:
                self.stmt('VACUUM')
            qs += ['PRAGMA page_count', 'PRAGMA freelist_count', 'SELECT count(*), sum(length(c)), min(b), max(b) FROM %s_f' % p,
                   'PRAGMA integrity_check', "SELECT name, rootpage FROM sqlite_schema WHERE name LIKE '%s%%' ORDER BY name" % p]
        if r.random() < 0.7:
            qs.append("SELECT type, name, tbl_name, rootpage, sql FROM sqlite_schema WHERE name LIKE '%s%%' ORDER BY name" % p)
        qs += ['PRAGMA page_count', 'PRAGMA freelist_count']
        for q in qs:
            self.query(q, None, True)

    def sch(self):
        self.block()

    def run(self, nq):
        for i in range(self.r.randint(2, 3)):
            self.make_table('t%d' % (i + 1))
        if self.r.random() < 0.4 and self.tables:
            t = self.r.choice(list(self.tables))
            self.stmt('CREATE VIEW v1 AS SELECT %s FROM %s' % (', '.join(self.expr(self.tables[t], 2) + ' AS a%d' % i for i in range(2)), t))
        makers = [self.simple_select] * 6 + [self.join_select] * 3 + [self.group_select] * 3 + [self.sub_select] * 2 + \
                 [self.compound_select, self.window_select, self.window_select, self.cte_select, self.values_select] + \
                 [self.pure_select] * 8
        while self.nq < nq:
            if self.r.random() < 0.12:
                self.dml()
                continue
            if self.r.random() < 0.06:
                self.block()
                continue
            sql, n, ordered = self.r.choice(makers)()
            self.query(sql, n, ordered)


def make(seed, nq, nohash=False):
    """The text of the script of SEED with NQ queries."""
    global NOHASH
    NOHASH = nohash
    db = sqlite3.connect(':memory:')
    db.isolation_level = None
    db.text_factory = bytes
    g = Gen(seed, db)
    g.run(nq)
    return ('# generated by scripts/gen_sqllogic.py %d %d; the answers are SQLite %s\n\n' % (seed, nq, sqlite3.sqlite_version) +
            'hash-threshold %d\n\n' % (0 if NOHASH else 8) + '\n'.join(g.out) + '\n')


# the scripts testdata/sqllogic holds: seed and queries
KEPT = [(1, 120), (2, 120)]


def check():
    """The kept scripts made again; nothing is compared when this SQLite is not the one that made them."""
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bad = 0
    for seed, nq in KEPT:
        p = os.path.join(root, 'testdata', 'sqllogic', 'gen_%d.test' % seed)
        have = open(p, encoding='utf-8', errors='surrogateescape').read()
        want = 'the answers are SQLite '
        i = have.index(want) + len(want)
        ver = have[i:have.index('\n', i)]
        if ver != sqlite3.sqlite_version:
            print('gen_sqllogic: skipped, the oracle is SQLite %s and the scripts were made with %s' % (sqlite3.sqlite_version, ver))
            return 0
        if make(seed, nq) != have:
            print('gen_sqllogic: testdata/sqllogic/gen_%d.test is not what the generator writes' % seed)
            bad += 1
    if not bad:
        print('gen_sqllogic: %d scripts as the generator writes them' % len(KEPT))
    return 1 if bad else 0


def main():
    if sys.argv[1:] == ['--check']:
        sys.exit(check())
    nohash = len(sys.argv) > 4 and sys.argv[4] == 'nohash'
    seed, nq, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    with open(out, 'w', encoding='utf-8', errors='surrogateescape') as f:
        f.write(make(seed, nq, nohash))


if __name__ == '__main__':
    main()
