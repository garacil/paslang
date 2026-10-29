# SQLite in paslang

`uses sqlite` is SQLite 3.54.1 written in paslang: the library itself, not a
binding to a C library, and its files are SQLite's to the byte, so a database a
paslang program writes is one the `sqlite3` program reads and the other way
round, at the same time. The manual's chapter 16 says what the unit is; this
chapter is for using it. It goes from a first table to transactions, the file on
the disk and the memory the connection holds, the write-ahead log, functions of
the program that SQL calls, and routines that share a database. Every program in
it is in `examples/` with the output it prints beside it, and `make check` runs
them all, so what is printed here is what the unit does today. Where a number or a
word of SQLite's is quoted, SQLite's own documentation (the pages named in
brackets, from the sqlite.org documentation of 3.54.1) is where it comes from; the
answers in these programs were checked against the `sqlite3` program and Python's
`sqlite3` module, which are the system's SQLite 3.54.0.

The chapter is not a course on SQL. SQLite's own pages are that, and the unit
speaks SQLite's SQL to the letter: every statement, pragma, function, window,
JSON and date function, virtual table, `ATTACH` and `VACUUM INTO` of 3.54.1.

## 1. A first database

A connection is a `TSqlite`. `TSqlite.Open(path)` opens a file, makes it when it is
not there, and `':memory:'` is a database that lives and dies with the connection.
`Exec` runs SQL, `Query` reads rows, `QueryValue` reads one value, and `Free`
closes the connection.

```pascal
{ SQLite from paslang: open a database, make a table, put rows in with
  their values bound, read them back, and see an error come as an object. }
program sqlbasic;

uses sqlite;

var
  db: TSqlite;
  rows: TSqliteRows;
  n: Integer;

begin
  db := TSqlite.Open(':memory:');
  try
    db.Exec('CREATE TABLE item(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, ' +
      'price REAL, stock INTEGER DEFAULT 0)');
    n := db.Exec('INSERT INTO item(name, price, stock) VALUES(?, ?, ?)', ['pen', 1.25, 40]);
    WriteLn('pen: ', n, ' row, rowid ', db.LastInsertRowId);
    db.Exec('INSERT INTO item(name, price, stock) VALUES(?, ?, ?)', ['ink', 7.5, 6]);
    db.Exec('INSERT INTO item(name, price) VALUES(?, ?)', ['cap', nil]);
    WriteLn('items: ', db.QueryValue('SELECT count(*) FROM item', []).I);

    rows := db.Query('SELECT name, price, stock FROM item ORDER BY name');
    while rows.Next do
    begin
      Write(rows.Column(0).S, ' ');
      if rows.Column(1).Kind = SQLITE_NULL then
        Write('no price')
      else
        Write(rows.Column(1).R:0:2);
      WriteLn(' stock ', rows.Column(2).I);
    end;

    n := db.Exec('UPDATE item SET stock = stock + ? WHERE price < ?', [10, 5]);
    WriteLn('restocked ', n, ' rows, now ', db.QueryValue('SELECT stock FROM item WHERE name = ?', ['pen']).I);

    try
      db.Exec('INSERT INTO item(name) VALUES(?)', ['pen']);
    except
      on E: ESqliteError do
        WriteLn('code ', E.Code, ' extended ', E.ExtendedCode, ': ', E.Message);
    end;
    WriteLn('still ', db.QueryValue('SELECT count(*) FROM item', []).I, ' items');
  finally
    db.Free;
  end;
end.
```

prints

```
pen: 1 row, rowid 1
items: 3
cap no price stock 0
ink 7.50 stock 6
pen 1.25 stock 40
restocked 1 rows, now 50
code 19 extended 2067: UNIQUE constraint failed: item.name
still 3 items
```

Four things in it are the rules of the unit.

- **`Exec(sql)` runs every statement of a text; `Exec(sql, [args])` runs one
  statement with its parameters**: argument 1 goes to parameter 1, argument 2 to
  parameter 2, and so on. A `?` is the number after the largest so far, a named
  parameter (`:name`, `@name`, `$name`) is numbered when it first appears, and
  `?NNN` is number NNN [lang_expr.html]. It gives the rows the statement changed.
  A parameter with no argument is NULL, as in C; an argument for a parameter that
  does not exist is SQLITE_RANGE (code 25, "column index out of range"). Never put
  a value into the SQL text: bound, it cannot be taken for SQL.
- **A value goes in as what it is.** An integer or a Boolean is an integer (a
  Boolean is 0 or 1), a real is a real, a string is text, `nil` is NULL, and
  `SqliteBlob(bytes)` is a blob (section 2).
- **`Query` gives a `TSqliteRows`.** `Next` moves to the next row and says whether
  there was one; `Column(i)` is the value as a `TSqliteValue` (its `Kind`, and
  `I`, `R` or `S`), `ColumnCount` and `ColumnName(i)` describe the row, and
  `Values` is the whole row. A query lasts until its last row has been read or
  `Finish` is called; a connection that is closed with a query open does not
  complain. `QueryValue(sql, args)` is the first column of the first row, and a
  NULL when there is no row.
- **An error is an `ESqliteError`.** `Code` is SQLite's result code, `ExtendedCode`
  the finer one (a constraint's kind among them), and `Message` SQLite's words,
  the same ones the `sqlite3` program prints. `SqliteErrStr(code)` is the English
  of a code, and the codes and flags of `sqlite3.h` are all there under their own
  names (`SQLITE_CONSTRAINT_UNIQUE`, `SQLITE_OPEN_READONLY`, ...). A statement
  that fails changes nothing: the unique violation above leaves the three rows.

`TSqlite.Open(path, flags)` takes `sqlite3_open_v2`'s flags. `SQLITE_OPEN_READONLY`
opens a file that must be there and refuses to write it; `SQLITE_OPEN_URI` makes the
name an URI with its options (`file:data.db?mode=ro`). `LastInsertRowId` and
`Changes` are `sqlite3_last_insert_rowid` and `sqlite3_changes64`. Underneath
`TSqlite` is SQLite's C interface under its own names, on the connection
`db.Handle`; the sections that follow use a few of its routines, and section 8
the rest.

## 2. Values and types

SQLite is typed by the value, not by the column [datatype3.html]. A value is one
of five storage classes: NULL, INTEGER (up to eight bytes, signed), REAL (an
IEEE double), TEXT and BLOB. A column has an affinity, which is a preference:
a value stored in the column is converted to the affinity's class when it can be
converted without losing anything, and kept as it is when it cannot. The affinity
comes from the declared type by five rules, in this order: a type that contains
"INT" is INTEGER; "CHAR", "CLOB" or "TEXT", TEXT; "BLOB", or no type at all, BLOB (no
conversion); "REAL", "FLOA" or "DOUB", REAL; anything else is NUMERIC. A table
declared `STRICT` keeps to its column types instead and refuses a value that does
not fit.

```pascal
{ What a value is in SQLite: the five storage classes, what a paslang value
  becomes when it is bound, what a column's affinity does to it, and the
  places where SQLite is not Pascal. }
program sqltypes;

uses sqlite;

var
  db: TSqlite;

{ the storage class of what was bound, and the value as SQL writes it }
procedure Bound(const Name: string; const Arg: array of const);
var
  rows: TSqliteRows;
begin
  rows := db.Query('SELECT typeof(?1), quote(?1)', Arg);
  rows.Next;
  WriteLn(Name, ': ', rows.Column(0).S, ' ', rows.Column(1).S);
  rows.Finish;
end;

{ a row of a query, each value by its storage class }
procedure Row(const Sql: string);
var
  rows: TSqliteRows;
  i: Integer;
begin
  rows := db.Query(Sql);
  while rows.Next do
  begin
    for i := 0 to rows.ColumnCount - 1 do
    begin
      if i > 0 then
        Write(' | ');
      case rows.Column(i).Kind of
        SQLITE_INTEGER: Write(rows.Column(i).I, ' integer');
        SQLITE_FLOAT: Write(rows.Column(i).R:0:1, ' real');
        SQLITE_TEXT: Write('''', rows.Column(i).S, ''' text');
        SQLITE_BLOB: Write(Length(rows.Column(i).S), ' bytes blob');
        SQLITE_NULL: Write('NULL');
      end;
    end;
    WriteLn;
  end;
end;

begin
  db := TSqlite.Open(':memory:');
  try
    WriteLn('-- what a bound value becomes');
    Bound('42', [42]);
    Bound('3.5', [3.5]);
    Bound('text', ['text']);
    Bound('nil', [nil]);
    Bound('blob', [SqliteBlob(#0#255)]);
    Bound('True', [True]);

    WriteLn('-- affinity: the column decides, a value that cannot be converted stays as it is');
    db.Exec('CREATE TABLE t(i INTEGER, r REAL, s TEXT, n NUMERIC, b BLOB)');
    db.Exec('INSERT INTO t VALUES(?, ?, ?, ?, ?)', ['12', 3, 45, '7.0', 'x']);
    db.Exec('INSERT INTO t VALUES(?, ?, ?, ?, ?)', ['abc', '2.5', 1.5, 'n/a', nil]);
    Row('SELECT * FROM t');

    WriteLn('-- a STRICT table keeps to its types');
    db.Exec('CREATE TABLE u(i INTEGER, s TEXT) STRICT');
    try
      db.Exec('INSERT INTO u VALUES(?, ?)', ['abc', 'x']);
    except
      on E: ESqliteError do
        WriteLn(E.Message);
    end;

    WriteLn('-- integers do not wrap');
    Row('SELECT 9223372036854775807, 9223372036854775807 + 1, 9223372036854775807 + 0.0');
    try
      db.Exec('SELECT abs(-9223372036854775807 - 1)');
    except
      on E: ESqliteError do
        WriteLn(E.Message);
    end;

    WriteLn('-- comparing');
    Row('SELECT 1 = 1.0, ''1'' = 1, NULL = NULL, NULL IS NULL, ''a'' < ''B'', ''a'' < ''B'' COLLATE NOCASE');

    WriteLn('-- NULL, numbers, text and blobs sort in that order');
    db.Exec('CREATE TABLE m(v)');
    db.Exec('INSERT INTO m VALUES(?), (?), (?), (?), (?), (?)', ['b', 2.5, nil, SqliteBlob('z'), 1, 'a']);
    Row('SELECT v FROM m ORDER BY v');

    WriteLn('-- text is UTF-8: a character is not a byte');
    Row('SELECT length(''é''), length(CAST(''é'' AS BLOB)), upper(''é'' || ''e'')');
    WriteLn(Length(db.QueryValue('SELECT ''é''', []).S), ' bytes in the paslang string');
  finally
    db.Free;
  end;
end.
```

prints

```
-- what a bound value becomes
42: integer 42
3.5: real 3.5
text: text 'text'
nil: null NULL
blob: blob X'00FF'
True: integer 1
-- affinity: the column decides, a value that cannot be converted stays as it is
12 integer | 3.0 real | '45' text | 7 integer | 'x' text
'abc' text | 2.5 real | '1.5' text | 'n/a' text | NULL
-- a STRICT table keeps to its types
cannot store TEXT value in INTEGER column u.i
-- integers do not wrap
9223372036854775807 integer | 9223372036854775808.0 real | 9223372036854775808.0 real
integer overflow
-- comparing
1 integer | 0 integer | NULL | 1 integer | 0 integer | 1 integer
-- NULL, numbers, text and blobs sort in that order
NULL
1 integer
2.5 real
'a' text
'b' text
1 bytes blob
-- text is UTF-8: a character is not a byte
1 integer | 2 integer | 'éE' text
2 bytes in the paslang string
```

What to take from it:

- A paslang `Integer` or `Int64` binds as an INTEGER, a `Double` as a REAL, a
  `string` as TEXT and `True` as 1; to bind bytes as a BLOB, wrap them in
  `SqliteBlob`. The string of a TEXT value and of a BLOB value are both a paslang
  `string`; `Kind` says which was stored.
- The column's affinity acts on the way in. The text `'12'` became the integer 12
  in an INTEGER column and the integer 3 became the real 3.0 in a REAL column;
  `'abc'` stayed text in an INTEGER column because it cannot be a number, and
  in a STRICT table it is an error.
- An integer that overflows becomes a real (`9223372036854775807 + 1`), except in
  the places where SQLite raises "integer overflow" instead (`abs` of the smallest
  integer).
- `NULL = NULL` is NULL, not true; use `IS NULL`. A text compares by its bytes
  (`'a' < 'B'` is false) unless a collation says otherwise (`BINARY`, `NOCASE`
  which folds ASCII only, `RTRIM`, or one of your own, section 8). In an `ORDER BY`
  NULLs come first, then the numbers, the texts and the blobs.
- Text is UTF-8, and SQLite's `length` of a text counts characters, of a blob
  bytes; `upper` and `lower` change ASCII letters only. A paslang `string` holds
  the bytes, so `Length` of a column's `S` is the byte count.

## 3. Transactions

No read or write happens outside a transaction [lang_transaction.html]. A
statement that is not inside one starts its own and commits it when it finishes;
`BEGIN` makes the transaction last until `COMMIT` or `ROLLBACK`, and a
transaction that is still open when the connection is closed is rolled back.
A transaction is `DEFERRED` (the default: it takes its lock when it first reads
or writes), `IMMEDIATE` (it takes the write lock now, and `BEGIN IMMEDIATE` fails
with SQLITE_BUSY when another connection holds it) or `EXCLUSIVE` (the same in
WAL mode; in the rollback journal modes it also keeps other connections from
reading). `BEGIN` does not nest; `SAVEPOINT` does.

An error in a statement undoes that statement and nothing before it
[lang_conflict.html]: a constraint failure in the second `UPDATE` of a transaction
leaves the first one done, and the transaction open. `UPDATE OR ROLLBACK` (and
`INSERT OR ROLLBACK`) says the opposite: the whole transaction goes. Some errors
(SQLITE_FULL, SQLITE_IOERR, SQLITE_INTERRUPT, SQLITE_NOMEM) may or may not roll the
transaction back; the program asks with `sqlite3_get_autocommit` (is it outside
a transaction?) or `sqlite3_txn_state` (none, read or write), or just runs
`ROLLBACK`, which fails harmlessly when there is nothing to roll back.

The unit of work in paslang is `BEGIN`, `try`, `COMMIT`, and a `ROLLBACK` in the
handler before the error goes on:

```pascal
{ Transactions: what one is, what a failed statement leaves behind, the
  pattern for a unit of work with try, and savepoints inside it. }
program sqltxn;

uses sqlite;

var
  db: TSqlite;

function YesNo(B: Boolean): string;
begin
  if B then
    Result := 'yes'
  else
    Result := 'no';
end;

function InTransaction: string;
begin
  Result := YesNo(sqlite3_get_autocommit(db.Handle) = 0);
end;

procedure Balances(const Title: string);
var
  rows: TSqliteRows;
begin
  Write(Title, ':');
  rows := db.Query('SELECT owner, balance FROM account ORDER BY id');
  while rows.Next do
    Write(' ', rows.Column(0).S, '=', rows.Column(1).I);
  WriteLn('  (in a transaction: ', InTransaction, ')');
end;

{ move Amount from account Src to account Dst, or change nothing }
procedure Transfer(Src, Dst, Amount: Integer);
begin
  db.Exec('BEGIN');
  try
    db.Exec('UPDATE account SET balance = balance + ? WHERE id = ?', [Amount, Dst]);
    db.Exec('UPDATE account SET balance = balance - ? WHERE id = ?', [Amount, Src]);
    db.Exec('COMMIT');
  except
    on E: ESqliteError do
    begin
      WriteLn('  ', E.Message);
      Balances('  the failed statement is undone, the one before it is not');
      db.Exec('ROLLBACK');
      raise;
    end;
  end;
end;

begin
  db := TSqlite.Open(':memory:');
  try
    db.Exec('CREATE TABLE account(id INTEGER PRIMARY KEY, owner TEXT, balance INTEGER CHECK(balance >= 0))');
    db.Exec('INSERT INTO account(owner, balance) VALUES(''ada'', 100), (''bob'', 20)');
    Balances('start');

    Transfer(1, 2, 30);
    Balances('after 30 from ada to bob');

    try
      Transfer(2, 1, 500);
    except
      on E: ESqliteError do
        WriteLn('  Transfer raised, code ', E.Code, ' extended ', E.ExtendedCode);
    end;
    Balances('after 500 from bob to ada');

    WriteLn('-- a transaction as SQLite counts it');
    WriteLn('none ', YesNo(sqlite3_txn_state(db.Handle, '') = SQLITE_TXN_NONE));
    db.Exec('BEGIN');
    WriteLn('begun, still none ', YesNo(sqlite3_txn_state(db.Handle, '') = SQLITE_TXN_NONE));
    db.QueryValue('SELECT count(*) FROM account', []);
    WriteLn('read ', YesNo(sqlite3_txn_state(db.Handle, '') = SQLITE_TXN_READ));
    db.Exec('UPDATE account SET balance = balance + 1');
    WriteLn('write ', YesNo(sqlite3_txn_state(db.Handle, '') = SQLITE_TXN_WRITE));
    db.Exec('ROLLBACK');
    WriteLn('rolled back ', YesNo(sqlite3_txn_state(db.Handle, '') = SQLITE_TXN_NONE));

    WriteLn('-- OR ROLLBACK ends the whole transaction');
    db.Exec('BEGIN');
    db.Exec('UPDATE account SET balance = balance + 1');
    try
      db.Exec('UPDATE OR ROLLBACK account SET balance = -1 WHERE id = 1');
    except
      on E: ESqliteError do
        WriteLn(E.Message);
    end;
    WriteLn('in a transaction: ', InTransaction);
    Balances('unchanged');

    WriteLn('-- savepoints nest, and a rollback to one keeps it');
    db.Exec('SAVEPOINT work');
    db.Exec('UPDATE account SET balance = balance + 10 WHERE id = 1');
    db.Exec('SAVEPOINT risky');
    db.Exec('UPDATE account SET balance = balance + 1000 WHERE id = 1');
    Balances('inside risky');
    db.Exec('ROLLBACK TO risky');
    Balances('rolled back to risky');
    db.Exec('RELEASE work');
    Balances('released (the outermost savepoint commits)');
  finally
    db.Free;
  end;
end.
```

prints

```
start: ada=100 bob=20  (in a transaction: no)
after 30 from ada to bob: ada=70 bob=50  (in a transaction: no)
  CHECK constraint failed: balance >= 0
  the failed statement is undone, the one before it is not: ada=570 bob=50  (in a transaction: yes)
  Transfer raised, code 19 extended 275
after 500 from bob to ada: ada=70 bob=50  (in a transaction: no)
-- a transaction as SQLite counts it
none yes
begun, still none yes
read yes
write yes
rolled back yes
-- OR ROLLBACK ends the whole transaction
CHECK constraint failed: balance >= 0
in a transaction: no
unchanged: ada=70 bob=50  (in a transaction: no)
-- savepoints nest, and a rollback to one keeps it
inside risky: ada=1080 bob=50  (in a transaction: yes)
rolled back to risky: ada=80 bob=50  (in a transaction: yes)
released (the outermost savepoint commits): ada=80 bob=50  (in a transaction: no)
```

The two `UPDATE`s of `Transfer` change money in two rows; the second one breaks
the account's `CHECK`. Inside the handler the first change is still there (ada has
570), which is the rule above; the `ROLLBACK` takes it back, and `raise` hands the
error on. The savepoints at the end show `ROLLBACK TO`, which undoes what came
after a savepoint and leaves the savepoint, and `RELEASE`, which on the outermost
savepoint commits.

Keep a write transaction short. There is one writer at a time on a file, and
readers in the rollback modes keep it from committing (section 9).

## 4. The file

A database is one file of pages [fileformat2.html]. The page size is a power of two
from 512 to 65536 (4096 by default), set with `PRAGMA page_size` before the first
table is made; the first page begins with a header of 100 bytes whose first 16
bytes read `SQLite format 3` and a zero, and whose next fields give the page size,
the number of pages, the text encoding (1 is UTF-8), the schema cookie, and two
numbers the application owns, `user_version` and `application_id`. A file is
exactly `PageCount` pages of `PageSize` bytes, and the unit reads the header for
you: `PageSize`, `PageCount`, `Encoding`, `UserVersion` and `SchemaCookie`.

```pascal
{ The file SQLite keeps and what moves between it and memory: the pages and
  the header, the rollback journal while a transaction writes, a connection
  closed in the middle of one, VACUUM INTO, a backup of a database in memory
  into a file, and a database as a string of bytes. }
program sqlfile;

uses sqlite, sysutils;

var
  dir, path, second: string;
  db, other: TSqlite;
  err: TSysError;

function YesNo(B: Boolean): string;
begin
  if B then
    Result := 'yes'
  else
    Result := 'no';
end;

{ the big-endian number of N bytes at offset At of a file's header }
function Be(const S: string; At, N: Integer): Integer;
var
  i: Integer;
begin
  Result := 0;
  for i := 1 to N do
    Result := Result * 256 + Ord(S[At + i]);
end;

procedure Forget(const Name: string);
begin
  if FileExists(Name) then
    DeleteFile(Name);
end;

procedure Header;
var
  data: string;
begin
  ReadFile(path, data);
  WriteLn('magic ', Copy(data, 1, 15), ', page size ', Be(data, 16, 2), ', pages ', Be(data, 28, 4),
    ', encoding ', Be(data, 56, 4), ', user version ', Be(data, 60, 4));
  WriteLn('the file is ', FileSize(path), ' bytes: ', db.PageCount, ' pages of ', db.PageSize);
end;

procedure Pragmas;
const
  Names: array[0..6] of string = ('journal_mode', 'synchronous', 'locking_mode', 'auto_vacuum', 'cache_size',
    'foreign_keys', 'encoding');
var
  k: Integer;
  v: TSqliteValue;
begin
  for k := 0 to 6 do
  begin
    v := db.QueryValue('PRAGMA ' + Names[k], []);
    if v.Kind = SQLITE_TEXT then
      WriteLn('  ', Names[k], ' = ', v.S)
    else
      WriteLn('  ', Names[k], ' = ', v.I);
  end;
end;

procedure Backup;
var
  b: TSqlite3Backup;
  rc: Integer;
begin
  db := TSqlite.Open(':memory:');
  try
    db.Exec('CREATE TABLE note(id INTEGER PRIMARY KEY, body TEXT)');
    db.Exec('INSERT INTO note(body) VALUES(?), (?), (?)', ['one', 'two', 'three']);
    other := TSqlite.Open(second);
    try
      b := sqlite3_backup_init(other.Handle, 'main', db.Handle, 'main');
      rc := sqlite3_backup_step(b, -1);
      WriteLn('backup step done: ', YesNo(rc = SQLITE_DONE), ', pages ', sqlite3_backup_pagecount(b));
      sqlite3_backup_finish(b);
    finally
      other.Free;
    end;
  finally
    db.Free;
  end;
  other := TSqlite.Open(second);
  try
    WriteLn('the file has ', other.QueryValue('SELECT count(*) FROM note', []).I, ' notes, check: ',
      other.QueryValue('PRAGMA integrity_check', []).S);
  finally
    other.Free;
  end;
end;

procedure Serialized;
var
  bytes: string;
  size: Int64;
begin
  db := TSqlite.Open(':memory:');
  try
    db.Exec('CREATE TABLE t(x)');
    db.Exec('INSERT INTO t VALUES(1), (2), (3)');
    bytes := sqlite3_serialize(db.Handle, '', size, 0);
    WriteLn('serialized: ', size, ' bytes = ', db.PageCount, ' pages of ', db.PageSize);
    other := TSqlite.Open(':memory:');
    try
      sqlite3_deserialize(other.Handle, '', bytes, size, size, SQLITE_DESERIALIZE_RESIZEABLE);
      WriteLn('read back: ', other.QueryValue('SELECT sum(x) FROM t', []).I);
    finally
      other.Free;
    end;
  finally
    db.Free;
  end;
end;

begin
  if not TryCreateTempDirectoryAt(CurrentDirectoryHandle, '', 'paslang-sql-*', dir, err) then
    err.RaiseError;
  path := dir + '/shop.db';
  second := dir + '/second.db';
  try
    WriteLn('-- a file, its pages and its header');
    db := TSqlite.Open(path);
    try
      db.Exec('PRAGMA page_size = 1024');
      db.Exec('PRAGMA user_version = 42');
      db.Exec('CREATE TABLE t(id INTEGER PRIMARY KEY, pad BLOB)');
      db.Exec('INSERT INTO t(pad) SELECT zeroblob(200) FROM (WITH RECURSIVE n(i) AS ' +
        '(SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < 300) SELECT i FROM n)');
      Header;
      WriteLn('settings:');
      Pragmas;

      WriteLn('-- the rollback journal exists while a transaction has written');
      db.Exec('BEGIN');
      WriteLn('begun: journal ', YesNo(FileExists(path + '-journal')));
      db.Exec('UPDATE t SET pad = zeroblob(10) WHERE id < 10');
      WriteLn('written: journal ', YesNo(FileExists(path + '-journal')));
      db.Exec('COMMIT');
      WriteLn('committed: journal ', YesNo(FileExists(path + '-journal')));

      WriteLn('-- closed in the middle of a transaction, it is rolled back');
      db.Exec('BEGIN');
      db.Exec('DELETE FROM t');
      WriteLn('inside: ', db.QueryValue('SELECT count(*) FROM t', []).I, ' rows');
    finally
      db.Free;
    end;
    db := TSqlite.Open(path);
    try
      WriteLn('reopened: ', db.QueryValue('SELECT count(*) FROM t', []).I, ' rows');

      WriteLn('-- deleting rows frees pages for reuse, VACUUM INTO writes a compact copy');
      db.Exec('DELETE FROM t WHERE id > 20');
      WriteLn('after the delete: ', db.PageCount, ' pages, ', db.QueryValue('PRAGMA freelist_count', []).I, ' free');
      db.Exec('VACUUM INTO ?', [second]);
      other := TSqlite.Open(second);
      try
        WriteLn('the copy: ', other.PageCount, ' pages, ', other.QueryValue('SELECT count(*) FROM t', []).I, ' rows');
      finally
        other.Free;
      end;
    finally
      db.Free;
    end;
    Forget(second);

    WriteLn('-- a database in memory saved to a file');
    Backup;

    WriteLn('-- a database as bytes');
    Serialized;
  finally
    Forget(path);
    Forget(path + '-journal');
    Forget(second);
    Forget(second + '-journal');
    if not RemoveDir(dir) then
      RaiseLastOSError;
  end;
end.
```

prints

```
-- a file, its pages and its header
magic SQLite format 3, page size 1024, pages 77, encoding 1, user version 42
the file is 78848 bytes: 77 pages of 1024
settings:
  journal_mode = delete
  synchronous = 2
  locking_mode = normal
  auto_vacuum = 0
  cache_size = -2000
  foreign_keys = 0
  encoding = UTF-8
-- the rollback journal exists while a transaction has written
begun: journal no
written: journal yes
committed: journal no
-- closed in the middle of a transaction, it is rolled back
inside: 0 rows
reopened: 300 rows
-- deleting rows frees pages for reuse, VACUUM INTO writes a compact copy
after the delete: 77 pages, 70 free
the copy: 5 pages, 20 rows
-- a database in memory saved to a file
backup step done: yes, pages 2
the file has 3 notes, check: ok
-- a database as bytes
serialized: 8192 bytes = 2 pages of 4096
read back: 6
```

The rollback journal is how SQLite makes a commit atomic [atomiccommit.html].
A writer takes a shared lock to read, a reserved lock when it starts to write, and
before it changes the file it copies the original content of every page it will
change into a journal file, `shop.db-journal`, and syncs it. At the commit it
takes an exclusive lock, writes the changed pages to the file, syncs it, and
deletes the journal; that deletion is the commit. A program, a computer or a
power supply that stops in the middle leaves a journal behind, and the next
connection to open the file finds it, plays it back and goes on as if the
transaction had never begun (the example shows the journal appear at the first
write and go at the commit, and a connection closed in the middle of a transaction
rolls it back).

`PRAGMA journal_mode` chooses how [pragma.html]: `DELETE` (the default: the journal
is deleted at each commit), `TRUNCATE` (emptied instead, which many file systems
do faster), `PERSIST` (its header zeroed), `MEMORY` (kept in memory: a crash in
the middle of a commit very likely corrupts the file), `OFF` (no journal, no
`ROLLBACK`, the same risk) and `WAL` (section 6). A database in memory can only be
`MEMORY` or `OFF`. `PRAGMA synchronous` says how hard it tries to reach the disk:
`FULL` (2, the default) waits for every critical write to be safely written;
`NORMAL` (1) waits less often, which in WAL mode costs the last transactions in a
power failure and nothing else; `OFF` (0) does not wait. A program that crashes
loses no transaction it committed, at any setting; the setting is about the
machine going down.

Four ways to take a database from one place to another:

- **`VACUUM INTO 'file'`** writes a compact copy of the database to a new file: the
  pages packed, the free ones left out. Plain `VACUUM` does the same in place.
- **The backup interface**, `sqlite3_backup_init`, `sqlite3_backup_step` and
  `sqlite3_backup_finish`, copies a database to another connection page by
  page, which is how a database in memory is saved to a file. A step of -1 copies all of it.
- **`sqlite3_serialize`** gives the bytes of a database as the file would hold
  them, and **`sqlite3_deserialize`** makes a database in memory of such bytes.
- **`ATTACH 'file' AS name`** opens a second file on the same connection, so that
  one statement can name tables of both (`name.table`). A transaction over two files
  is atomic as a whole in the rollback modes (a super-journal ties the two), and
  only file by file in WAL mode.

The file is shared by connections of any program: the unit takes SQLite's own
POSIX advisory locks on the same bytes, so a paslang program and the `sqlite3`
program can use one file together. The usual care applies: not over a network
file system, and the file with its `-journal` or `-wal` is the database, so copy or
move them together.

## 5. Memory

A connection holds a page cache, and the pages in it are paslang memory, the
collector's. `PRAGMA cache_size = N` suggests the size: a positive N is a number of
pages, a negative one a number of kibibytes, and the default is -2000, about two
megabytes for each open database file. The cache is kept between transactions,
so the second read of a page is memory. Temporary tables and indexes go in files,
and in memory after `PRAGMA temp_store = 2`; `PRAGMA mmap_size` is 0, no mapping
of the file, as in SQLite's own build; and a database in memory (`':memory:'`) is
a pager with no file at all, as fast as the cache can be and gone with the
connection. A temporary database (the file name `''`) is a file that is deleted
when the connection closes.

What the unit does not do is keep a count: `sqlite3_memory_used` is 0, because the
collector's heap is the program's, and `HeapStat` is where a program looks.
Close a connection you have done with: until then it keeps its page cache, and in
WAL mode its place among the readers.

The limits of the build are the defaults of SQLite's (`sqlite3_compileoption_get`
lists them): 1,000,000,000 bytes in a string or a blob and in a statement, 2000
columns, 1000 levels of expression, 1000 function arguments, 32766 parameters, 10
attached databases, 4,294,967,294 pages.

## 6. The write-ahead log

In WAL mode a commit does not touch the database file [wal.html]. Changes are
appended to a second file, `name-wal`, and a commit is a record that says so. The
original content stays in the file, so readers go on reading it while a writer
appends: readers do not block the writer and the writer does not block readers.
A reader remembers where the log ended when its transaction began and sees the
database as it was at that point until the transaction ends. There is still one
writer at a time.

Moving the log's content into the file is a checkpoint. By default one runs
after a commit that makes the log 1000 pages or longer, and when the last
connection closes (`PRAGMA wal_autocheckpoint`, `sqlite3_wal_autocheckpoint`, and
a hook, `sqlite3_wal_hook`, that is called after each commit, can change that).
A program can run one itself with `PRAGMA wal_checkpoint(MODE)`, which gives three
numbers: 1 if it could not finish for a reader, the frames in the log, and the
frames copied into the file. `PASSIVE` copies what it can without waiting;
`FULL` waits, in the busy handler, until no writer is active and every reader
sees the latest commit, and then copies all the log; `RESTART` also waits until
every reader reads the file alone, so that the next writer starts the log from its
beginning; and `TRUNCATE` does that and then makes the log empty
[c3ref/wal_checkpoint_v2.html]. A checkpoint can only copy up to the oldest end
mark of a reader, so a reader that keeps a transaction open holds the log back.

```pascal
{ The write-ahead log: a reader and a writer on the same file at the same
  time, the snapshot a reader keeps, the checkpoint that copies the log into
  the file, and what the log leaves on the disk. }
program sqlwal;

uses sqlite, sysutils;

var
  dir, path: string;
  writer, reader: TSqlite;
  err: TSysError;

function YesNo(B: Boolean): string;
begin
  if B then
    Result := 'yes'
  else
    Result := 'no';
end;

procedure Forget(const Name: string);
begin
  if FileExists(Name) then
    DeleteFile(Name);
end;

procedure Files;
begin
  Write('  the files: log ', YesNo(FileExists(path + '-wal')));
  if FileExists(path + '-wal') then
    Write(' (', FileSize(path + '-wal'), ' bytes)');
  WriteLn(', index ', YesNo(FileExists(path + '-shm')), ', journal ', YesNo(FileExists(path + '-journal')));
end;

function Count(Db: TSqlite): Int64;
begin
  Result := Db.QueryValue('SELECT count(*) FROM t', []).I;
end;

{ PRAGMA wal_checkpoint(Mode) gives three numbers: 1 when it could not finish for a reader,
  the frames in the log, the frames copied into the file }
procedure Checkpoint(const Mode: string);
var
  rows: TSqliteRows;
begin
  rows := writer.Query('PRAGMA wal_checkpoint(' + Mode + ')');
  rows.Next;
  WriteLn('  checkpoint ', Mode, ': blocked ', YesNo(rows.Column(0).I = 1), ', log ', rows.Column(1).I,
    ' frames, copied ', rows.Column(2).I);
  rows.Finish;
end;

begin
  if not TryCreateTempDirectoryAt(CurrentDirectoryHandle, '', 'paslang-sql-*', dir, err) then
    err.RaiseError;
  path := dir + '/log.db';
  try
    writer := TSqlite.Open(path);
    try
      WriteLn('journal mode: ', writer.QueryValue('PRAGMA journal_mode = WAL', []).S);
      writer.Exec('CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT)');
      writer.Exec('INSERT INTO t(v) VALUES(?)', ['first']);
      Files;
      Checkpoint('PASSIVE');
      Files;

      WriteLn('-- a reader keeps its snapshot while the writer goes on');
      reader := TSqlite.Open(path);
      try
        reader.Exec('BEGIN');
        WriteLn('reader sees ', Count(reader), ' row');
        writer.Exec('INSERT INTO t(v) VALUES(?)', ['second']);
        writer.Exec('INSERT INTO t(v) VALUES(?)', ['third']);
        WriteLn('writer committed, sees ', Count(writer), ' rows; reader still sees ', Count(reader));
        Checkpoint('PASSIVE');
        Checkpoint('TRUNCATE');
        reader.Exec('COMMIT');
        WriteLn('reader ended its transaction and sees ', Count(reader));
        Checkpoint('TRUNCATE');
        Files;
      finally
        reader.Free;
      end;

      WriteLn('-- the log starts again with the next commit');
      writer.Exec('INSERT INTO t(v) VALUES(?)', ['fourth']);
      Files;
    finally
      writer.Free;
    end;
    WriteLn('-- the last connection closed: the log is checkpointed and removed');
    Files;
    reader := TSqlite.Open(path);
    try
      WriteLn('journal mode, kept in the file: ', reader.QueryValue('PRAGMA journal_mode', []).S, ', rows ', Count(reader));
    finally
      reader.Free;
    end;
  finally
    Forget(path);
    Forget(path + '-wal');
    Forget(path + '-shm');
    Forget(path + '-journal');
    if not RemoveDir(dir) then
      RaiseLastOSError;
  end;
end.
```

prints

```
journal mode: wal
  the files: log yes (12392 bytes), index yes, journal no
  checkpoint PASSIVE: blocked no, log 3 frames, copied 3
  the files: log yes (12392 bytes), index yes, journal no
-- a reader keeps its snapshot while the writer goes on
reader sees 1 row
writer committed, sees 3 rows; reader still sees 1
  checkpoint PASSIVE: blocked no, log 2 frames, copied 0
  checkpoint TRUNCATE: blocked yes, log 2 frames, copied 0
reader ended its transaction and sees 3
  checkpoint TRUNCATE: blocked no, log 0 frames, copied 0
  the files: log yes (0 bytes), index yes, journal no
-- the log starts again with the next commit
  the files: log yes (4152 bytes), index yes, journal no
-- the last connection closed: the log is checkpointed and removed
  the files: log no, index no, journal no
journal mode, kept in the file: wal, rows 4
```

The first checkpoint copies the three frames the table and its row made. The
reader that begins and then waits holds the log at the end it saw: after two more
commits the checkpoint copies none of them and `TRUNCATE` finds a reader and says
so, at once, because the connection has no busy timeout (with
`sqlite3_busy_timeout` it would wait for the reader). When the reader ends, `TRUNCATE` empties
the log, and the next commit writes a frame again, in a log that begins at its start.
When the last connection is closed the log is checkpointed and both extra files
are removed.

Choosing WAL, from the documentation: it is faster for most work and lets reading
and writing go on together; it needs all the connections on one machine (the
`-shm` file is shared memory, so no network file systems); the page size cannot be
changed once it is in effect; and a database in it is a file plus a log, to be
kept together. The mode is a property of the file: set it once, and every
connection that opens the file afterwards is in it. `PRAGMA synchronous = NORMAL`
is the usual companion (section 4).

## 7. Where the documentation is

SQLite's own documentation is the reference for everything the unit does that
SQLite does: the SQL (`lang.html` and its pages), the pragmas, the functions
(`lang_corefunc.html`, `lang_aggfunc.html`, `lang_datefunc.html`,
`json1.html`, `windowfunctions.html`, `lang_mathfunc.html`), the file format and
the C interface (`c3ref/`, whose routines are all in the unit under the same
names; where C hands back a NULL text or an out parameter, paslang takes a
`string` and an `out`). `docs/SQLITE.md` in the repository is the study the
unit was written from, with the sources it follows.

## 8. Your own functions, collations and hooks

SQL can call the program. The routines are SQLite's C interface, and a callback is
a routine value: `@Name` of a procedure with the right parameters. An application
function is a `procedure(Ctx: TSqlite3Context; Argc: Integer; const Argv: array of
TSqlite3Value)`; it reads its arguments with `sqlite3_value_int64`,
`sqlite3_value_double`, `sqlite3_value_text`, `sqlite3_value_blob` and
`sqlite3_value_type`, and sets its result with one of `sqlite3_result_int64`,
`_double`, `_text`, `_blob`, `_null`, or `sqlite3_result_error` to make the
statement fail with a message. `sqlite3_create_function` registers a scalar function
(`xFunc`) or an aggregate (`xStep` and `xFinal`); give `SQLITE_DETERMINISTIC` in
the flags when the same arguments always give the same result: SQLite then allows
the function where it must be deterministic (the `WHERE` of a partial index, a
generated column) and may take it out of an inner loop
[c3ref/c_deterministic.html]. An aggregate keeps its state in an object of a
class of its own, which `sqlite3_aggregate_context(Ctx, TMyState)` makes the
first time and gives back every time, one for each group; a window function
(`sqlite3_create_window_function`) also takes a row back out with `xInverse` and
reads the value so far with `xValue`.

```pascal
{ Functions of the program that SQL calls: a scalar function, one that
  refuses its argument, an aggregate that keeps its state in an object, a
  window function (an aggregate that can also take a row back out), and a
  collation, the order of a text. }
program sqlfunc;

uses sqlite;

type
  { an aggregate's state: SQLite keeps one for each group, as an object }
  TSpread = class
    Seen: Integer;
    Lo, Hi: Double;
  end;

  { a window's running sum: rows come in at one end and go out at the other }
  TRunning = class
    Total: Int64;
  end;

var
  db: TSqlite;

{ clamp(x, lo, hi): x kept between lo and hi, NULL for NULL }
procedure Clamp(Ctx: TSqlite3Context; Argc: Integer; const Argv: array of TSqlite3Value);
var
  v: Double;
begin
  if sqlite3_value_type(Argv[0]) = SQLITE_NULL then
  begin
    sqlite3_result_null(Ctx);
    Exit;
  end;
  v := sqlite3_value_double(Argv[0]);
  if v < sqlite3_value_double(Argv[1]) then
    v := sqlite3_value_double(Argv[1]);
  if v > sqlite3_value_double(Argv[2]) then
    v := sqlite3_value_double(Argv[2]);
  sqlite3_result_double(Ctx, v);
end;

{ half(n): n / 2 for an even integer, an error for the rest }
procedure Half(Ctx: TSqlite3Context; Argc: Integer; const Argv: array of TSqlite3Value);
var
  n: Int64;
begin
  n := sqlite3_value_int64(Argv[0]);
  if n mod 2 <> 0 then
    sqlite3_result_error(Ctx, 'half: ' + IntToStr(n) + ' is odd')
  else
    sqlite3_result_int64(Ctx, n div 2);
end;

{ spread(x): the largest x minus the smallest, NULLs left out }
procedure SpreadStep(Ctx: TSqlite3Context; Argc: Integer; const Argv: array of TSqlite3Value);
var
  s: TSpread;
  v: Double;
begin
  if sqlite3_value_type(Argv[0]) = SQLITE_NULL then
    Exit;
  s := TSpread(sqlite3_aggregate_context(Ctx, TSpread));
  v := sqlite3_value_double(Argv[0]);
  if (s.Seen = 0) or (v < s.Lo) then
    s.Lo := v;
  if (s.Seen = 0) or (v > s.Hi) then
    s.Hi := v;
  s.Seen := s.Seen + 1;
end;

procedure SpreadFinal(Ctx: TSqlite3Context);
var
  s: TSpread;
begin
  s := TSpread(sqlite3_aggregate_context(Ctx, TSpread));
  if s.Seen = 0 then
    sqlite3_result_null(Ctx)
  else
    sqlite3_result_double(Ctx, s.Hi - s.Lo);
end;

{ running(x): the sum of the rows in the window }
procedure RunningStep(Ctx: TSqlite3Context; Argc: Integer; const Argv: array of TSqlite3Value);
var
  s: TRunning;
begin
  s := TRunning(sqlite3_aggregate_context(Ctx, TRunning));
  s.Total := s.Total + sqlite3_value_int64(Argv[0]);
end;

procedure RunningInverse(Ctx: TSqlite3Context; Argc: Integer; const Argv: array of TSqlite3Value);
var
  s: TRunning;
begin
  s := TRunning(sqlite3_aggregate_context(Ctx, TRunning));
  s.Total := s.Total - sqlite3_value_int64(Argv[0]);
end;

procedure RunningValue(Ctx: TSqlite3Context);
begin
  sqlite3_result_int64(Ctx, TRunning(sqlite3_aggregate_context(Ctx, TRunning)).Total);
end;

{ filenum: file2 before file10, the digits compared as numbers }
function FileNum(Arg: TObject; const A, B: string): Integer;
var
  i, j, x, y: Integer;
begin
  i := 1;
  j := 1;
  while (i <= Length(A)) and (j <= Length(B)) do
  begin
    if (A[i] >= '0') and (A[i] <= '9') and (B[j] >= '0') and (B[j] <= '9') then
    begin
      x := 0;
      while (i <= Length(A)) and (A[i] >= '0') and (A[i] <= '9') do
      begin
        x := x * 10 + Ord(A[i]) - 48;
        i := i + 1;
      end;
      y := 0;
      while (j <= Length(B)) and (B[j] >= '0') and (B[j] <= '9') do
      begin
        y := y * 10 + Ord(B[j]) - 48;
        j := j + 1;
      end;
      if x <> y then
      begin
        if x < y then
          Result := -1
        else
          Result := 1;
        Exit;
      end;
    end
    else
    begin
      if A[i] <> B[j] then
      begin
        if A[i] < B[j] then
          Result := -1
        else
          Result := 1;
        Exit;
      end;
      i := i + 1;
      j := j + 1;
    end;
  end;
  Result := (Length(A) - i) - (Length(B) - j);
end;

procedure Show(const Title, Sql: string);
var
  rows: TSqliteRows;
  i: Integer;
begin
  Write(Title, ':');
  rows := db.Query(Sql);
  while rows.Next do
    for i := 0 to rows.ColumnCount - 1 do
      case rows.Column(i).Kind of
        SQLITE_INTEGER: Write(' ', rows.Column(i).I);
        SQLITE_FLOAT: Write(' ', rows.Column(i).R:0:2);
        SQLITE_TEXT: Write(' ', rows.Column(i).S);
        SQLITE_NULL: Write(' NULL');
      end;
  WriteLn;
end;

begin
  db := TSqlite.Open(':memory:');
  try
    sqlite3_create_function(db.Handle, 'clamp', 3, SQLITE_UTF8 or SQLITE_DETERMINISTIC, nil, @Clamp, nil, nil);
    sqlite3_create_function(db.Handle, 'half', 1, SQLITE_UTF8 or SQLITE_DETERMINISTIC, nil, @Half, nil, nil);
    sqlite3_create_function(db.Handle, 'spread', 1, SQLITE_UTF8, nil, nil, @SpreadStep, @SpreadFinal);
    sqlite3_create_window_function(db.Handle, 'running', 1, SQLITE_UTF8, nil, @RunningStep, @RunningValue,
      @RunningValue, @RunningInverse, nil);
    sqlite3_create_collation(db.Handle, 'filenum', SQLITE_UTF8, nil, @FileNum);

    db.Exec('CREATE TABLE reading(day INTEGER, temp REAL, name TEXT)');
    db.Exec('INSERT INTO reading VALUES(1, 4.5, ''file10''), (2, 21.0, ''file2''), (3, NULL, ''file1''), ' +
      '(4, -3.0, ''File3''), (5, 12.25, ''file20'')');

    Show('scalar', 'SELECT day, clamp(temp, 0, 20) FROM reading');
    Show('in a WHERE', 'SELECT day FROM reading WHERE clamp(temp, 0, 20) = 20');
    Show('aggregate', 'SELECT spread(temp), spread(temp) FILTER (WHERE day > 3), spread(temp) FILTER (WHERE day = 3) FROM reading');
    Show('per group', 'SELECT day % 2, spread(temp) FROM reading GROUP BY day % 2');
    Show('window', 'SELECT day, running(day) OVER (ORDER BY day ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) FROM reading');
    Show('binary order', 'SELECT name FROM reading ORDER BY name');
    Show('file-number order', 'SELECT name FROM reading ORDER BY name COLLATE filenum');

    try
      db.Exec('SELECT half(day) FROM reading');
    except
      on E: ESqliteError do
        WriteLn('error: code ', E.Code, ', ', E.Message);
    end;
  finally
    db.Free;
  end;
end.
```

prints

```
scalar: 1 4.50 2 20.00 3 NULL 4 0.00 5 12.25
in a WHERE: 2
aggregate: 24.00 15.25 NULL
per group: 0 24.00 1 7.75
window: 1 1 2 3 3 5 4 7 5 9
binary order: File3 file1 file10 file2 file20
file-number order: File3 file1 file2 file10 file20
error: code 1, half: 1 is odd
```

`sqlite3_create_collation` registers a comparison, the order of a text, used by
`COLLATE name`, in a column's declaration and by an index. Its function gives a
number below, at or above zero, and must be a consistent order, or an index made
with it is wrong. (`natural` is an SQL word; the collation is called `filenum`.)

Other things the connection lets the program hook, all by routine values:
`sqlite3_commit_hook` (which can turn a commit into a rollback), `_rollback_hook`,
`_update_hook` (every row inserted, changed or deleted), `_wal_hook`,
`sqlite3_set_authorizer` (what a statement may do, asked as it is prepared),
`sqlite3_progress_handler` with `sqlite3_interrupt` (to stop a long query),
`sqlite3_trace_v2` and `sqlite3_busy_handler`. A virtual table is a
`TSqlite3Module` of routine values over classes derived from `TSqlite3Vtab` and
`TSqlite3VtabCursor`, and `testdata/sqlapi.paslang` in the repository has two
(`series` and `kv`).

## 9. Routines

A paslang program runs routines, and SQLite is made for it. The unit follows
SQLite's default build: every call on a connection holds the connection's mutex, which the routine that holds it may take again (a function of
the application can run SQL on the connection that calls it). Two ways to share a
database, both in the example:

```pascal
{ SQLite and routines: two connections to one file in the rollback-journal
  mode, where a reader keeps a writer from committing; then one connection
  for each routine in WAL mode, their writers waiting for each other (parked,
  not blocking a thread), and one connection that several routines share. }
program sqlconc;

uses sqlite, sysutils;

const
  Writers = 4;
  Rows = 25;

var
  dir, path: string;
  err: TSysError;
  wg: WaitGroup;
  shared: TSqlite;
  failed: Integer;

procedure Fail(const Where: string; E: ESqliteError);
begin
  AtomicAdd(@failed, 1);
  WriteLn(Where, ': ', E.Message);
end;

{ a routine with a connection of its own: its writes wait in SQLite's busy handler
  for the writer that holds the file }
procedure Writer(K: Integer);
var
  db: TSqlite;
  i: Integer;
begin
  try
    db := TSqlite.Open(path);
    try
      sqlite3_busy_timeout(db.Handle, 20000);
      for i := 1 to Rows do
        db.Exec('INSERT INTO log(writer, n) VALUES(?, ?)', [K, i]);
    finally
      db.Free;
    end;
  except
    on E: ESqliteError do
      Fail('writer', E);
  end;
  wg.Done;
end;

{ routines that share one connection: each call holds its mutex }
procedure Sharer(K: Integer);
var
  i: Integer;
begin
  try
    for i := 1 to Rows do
      shared.Exec('INSERT INTO log(writer, n) VALUES(?, ?)', [K, i]);
  except
    on E: ESqliteError do
      Fail('sharer', E);
  end;
  wg.Done;
end;

{ a reader holds the file for as long as its transaction lasts: a writer
  cannot commit meanwhile, and its transaction stays open to be tried again }
procedure Locks;
var
  other: TSqlite;
begin
  other := TSqlite.Open(path);
  try
    shared.Exec('BEGIN');
    WriteLn('the reader sees ', shared.QueryValue('SELECT count(*) FROM log', []).I, ' rows');
    other.Exec('BEGIN IMMEDIATE');
    other.Exec('INSERT INTO log(writer, n) VALUES(0, 0)');
    try
      other.Exec('COMMIT');
    except
      on E: ESqliteError do
        WriteLn('the writer cannot commit: code ', E.Code, ' ', E.Message);
    end;
    shared.Exec('COMMIT');
    other.Exec('COMMIT');
    WriteLn('the reader has ended, the writer has committed: ', shared.QueryValue('SELECT count(*) FROM log', []).I,
      ' row');
    shared.Exec('DELETE FROM log');
  finally
    other.Free;
  end;
end;

procedure Report(Db: TSqlite);
var
  rows: TSqliteRows;
begin
  rows := Db.Query('SELECT writer, count(*), min(n), max(n) FROM log GROUP BY writer ORDER BY writer');
  while rows.Next do
    WriteLn('  writer ', rows.Column(0).I, ': ', rows.Column(1).I, ' rows, n from ', rows.Column(2).I,
      ' to ', rows.Column(3).I);
  WriteLn('  ', Db.QueryValue('SELECT count(*) FROM log', []).I, ' rows in all');
end;

var
  k: Integer;

begin
  if not TryCreateTempDirectoryAt(CurrentDirectoryHandle, '', 'paslang-sql-*', dir, err) then
    err.RaiseError;
  path := dir + '/log.db';
  try
    shared := TSqlite.Open(path);
    try
      shared.Exec('CREATE TABLE log(id INTEGER PRIMARY KEY, writer INTEGER, n INTEGER)');
      WriteLn('-- journal mode ', shared.QueryValue('PRAGMA journal_mode', []).S);
      Locks;
      WriteLn('-- journal mode ', shared.QueryValue('PRAGMA journal_mode = WAL', []).S);
      shared.Exec('PRAGMA synchronous = NORMAL');

      WriteLn('-- ', Writers, ' routines, a connection each');
      wg.Add(Writers);
      for k := 1 to Writers do
        pas Writer(k);
      wg.Wait;
      Report(shared);

      WriteLn('-- ', Writers, ' routines, one connection');
      shared.Exec('DELETE FROM log');
      wg.Add(Writers);
      for k := 1 to Writers do
        pas Sharer(k);
      wg.Wait;
      Report(shared);
      WriteLn('failures: ', failed);
    finally
      shared.Free;
    end;
  finally
    DeleteFile(path);
    DeleteFile(path + '-wal');
    DeleteFile(path + '-shm');
    if not RemoveDir(dir) then
      RaiseLastOSError;
  end;
end.
```

prints

```
-- journal mode delete
the reader sees 0 rows
the writer cannot commit: code 5 database is locked
the reader has ended, the writer has committed: 1 row
-- journal mode wal
-- 4 routines, a connection each
  writer 1: 25 rows, n from 1 to 25
  writer 2: 25 rows, n from 1 to 25
  writer 3: 25 rows, n from 1 to 25
  writer 4: 25 rows, n from 1 to 25
  100 rows in all
-- 4 routines, one connection
  writer 1: 25 rows, n from 1 to 25
  writer 2: 25 rows, n from 1 to 25
  writer 3: 25 rows, n from 1 to 25
  writer 4: 25 rows, n from 1 to 25
  100 rows in all
failures: 0
```

- **A connection for each routine** is the way. Each routine opens its own, and
  the file's locks decide who goes. A routine that waits for a lock, with
  `sqlite3_busy_timeout(db.Handle, ms)` set, **parks** and lets the others run:
  it does not hold a thread. The example shows why WAL matters here: in the
  rollback journal modes a reader that keeps its transaction open keeps the writer
  from committing (code 5, "database is locked", the transaction still open to be
  retried), and in WAL mode four writers, each committing a row at a time, get
  all their rows in with no one failing. Without a busy timeout a statement that
  finds the file locked fails at once with that code.
- **One connection for several routines** works, since the mutex serializes the
  calls, but the transaction belongs to the connection, not to the routine: a
  `BEGIN` in one routine puts the others' statements inside it. Share a
  connection for single statements and give a routine that needs a transaction a
  connection of its own. A prepared statement belongs to one routine at a time.

## 10. How it is checked

The unit is checked against SQLite itself, so that this chapter's answers are
SQLite's. `testdata/sqlapi` compares the C interface with SQLite's own
on UTF-8 and UTF-16 databases; `testdata/sqlcompat` writes, reads, recovers and
checkpoints files with the system's SQLite on the other side, including a program
killed in the middle of a commit; `testdata/sqlmath` compares 20000 arguments of
each math function bit for bit; and `testdata/sqllogic.paslang` is a runner of
sqllogictest, the corpus SQLite checks other engines with: all of its 622 scripts,
1,480,832 records, run with no difference. `scripts/gen_sqllogic.py` writes random
schemas, data, statements and queries and asks the `sqlite3` program for the
answers (`make sqldiff`); 8,000 seeds gave none that differs. `make sqllogic SLT=DIR`
runs a directory of sqllogictest scripts.

## 11. What is not there

The `sqlite3` program is built with more than the unit has: FTS3, FTS4 and FTS5
(full-text search), R-Tree and Geopoly, the `dbstat` and `sqlite_dbpage` tables,
`ANALYZE` with the statistics SQLITE_ENABLE_STAT4 adds, `percentile`, the session
extension and the preupdate hook. The unit has none of them
(`CREATE VIRTUAL TABLE ... USING fts5` says "no such module"), and it loads no
extension library. Its build is the one `sqlite3_compileoption_get` lists: math
functions, serialized threading, 4096-byte pages, a 2000-kibibyte cache, 1000-page
WAL checkpoints. `sqlite3_memory_used` is 0. After `Disconnect` every method of
`TSqlite` raises an `ESqliteError` with SQLITE_MISUSE (21), the code SQLite gives
to the use of a closed connection; after `Free` the object is gone, as any
object is.
