#!/usr/bin/env python3
# This file is part of paslang's tests.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later. See COPYING.

"""Check SQLite's Linux sync selection, errors and file interoperability."""

import errno
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
from tempfile import mkdtemp

PROGRAM = """program sqlitesync;
uses sqlite;

procedure InsertRow(Db: TSqlite);
begin
  Db.Exec('BEGIN IMMEDIATE');
  Db.Exec('INSERT INTO t VALUES (1)');
  Db.Exec('COMMIT');
end;

var
  Db: TSqlite;
  Mode: string;
  I: Integer;
begin
  Db := TSqlite.Open(ParamStr(1));
  Mode := ParamStr(2);
  try
    if Mode = 'read' then
      WriteLn(Db.QueryValue('SELECT count(*) FROM t', []).I)
    else
    begin
      if Mode = 'fullfsync' then
        Db.Exec('PRAGMA fullfsync=ON');
      if Mode = 'delete' then
      begin
        if Db.QueryValue('PRAGMA journal_mode=DELETE', []).S <> 'delete' then
          Halt(2);
        Db.Exec('PRAGMA synchronous=EXTRA');
        if Db.QueryValue('PRAGMA synchronous', []).I <> 3 then
          Halt(3);
      end
      else
      begin
        if Db.QueryValue('PRAGMA journal_mode=WAL', []).S <> 'wal' then
          Halt(2);
        Db.Exec('PRAGMA synchronous=FULL; PRAGMA wal_autocheckpoint=0');
        if Db.QueryValue('PRAGMA synchronous', []).I <> 2 then
          Halt(3);
      end;
      try
        Db.Exec('CREATE TABLE IF NOT EXISTS t(x INTEGER)');
        if Mode = 'fault' then
          InsertRow(Db)
        else
        begin
          for I := 1 to 4 do InsertRow(Db);
          if Mode = 'wal' then
          begin
            Db.Exec('PRAGMA wal_checkpoint(RESTART)');
            InsertRow(Db);
            Db.Exec('PRAGMA wal_checkpoint(TRUNCATE)');
          end;
        end;
        WriteLn('committed');
      except
        on E: ESqliteError do
          WriteLn('sqlite error ', E.ExtendedCode, ' errno ', sqlite3_system_errno(Db.Handle));
      end;
    end;
  finally
    Db.Disconnect;
  end;
end.
"""

SYNC_CALL = re.compile(r'\b(fdatasync|fsync)\(\d+<([^>]+)>')


def run(command, expected):
    result = subprocess.run(command, capture_output=True, timeout=40)
    if (result.returncode, result.stdout, result.stderr) != (0, expected, b''):
        raise SystemExit(f'{command!r}: {result.returncode}, {result.stdout!r}, {result.stderr!r}')


def trace(command, trace_file, tracer, expected, injection=None):
    if tracer:
        prefix = [tracer, '-f', '-qq', '-y', '-o', trace_file, '-e', 'trace=fsync,fdatasync']
        if injection:
            prefix.extend(['-e', f'inject={injection}'])
        command = prefix + command
    run(command, expected)
    return trace_file.read_text() if tracer else ''


def check_files(command, work, tracer):
    for mode, rows in [('wal', 5), ('delete', 4), ('fullfsync', 4)]:
        case = work / mode
        case.mkdir()
        database = case / 'data.db'
        log = trace([*command, database, mode], case / 'trace', tracer, b'committed\n')
        if tracer:
            calls = SYNC_CALL.findall(log)
            expected = 'fsync' if mode == 'fullfsync' else 'fdatasync'
            journal = database.with_name('data.db-journal' if mode == 'delete' else 'data.db-wal')
            file_sync = [name for name, path in calls if path == str(journal)]
            assert file_sync and set(file_sync) == {expected}, (mode, log)
            dir_sync = [name for name, path in calls if path == str(case)]
            assert dir_sync and set(dir_sync) == {'fsync'}, (mode, log)
            if mode == 'delete':
                assert len(dir_sync) >= 2, log
            if mode != 'fullfsync':
                assert all(name == 'fdatasync' for name, path in calls if path.endswith('/data.db')), log
        with sqlite3.connect(database) as db:
            assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
            assert db.execute('SELECT count(*) FROM t').fetchone() == (rows,)
            db.execute('INSERT INTO t VALUES (2)')
        db.close()
        run([*command, database, 'read'], f'{rows + 1}\n'.encode())


def check_errors(command, work, tracer):
    for error in ('ENOSYS', 'EINTR', 'EIO', 'ENOSPC'):
        case = work / error
        case.mkdir()
        database = case / 'data.db'
        with sqlite3.connect(database) as db:
            assert db.execute('PRAGMA journal_mode=WAL').fetchone() == ('wal',)
            db.execute('CREATE TABLE t(x INTEGER)')
        db.close()
        unsupported = error == 'ENOSYS'
        expected = (b'committed\n' if unsupported else
                    f'sqlite error 1034 errno {getattr(errno, error)}\n'.encode())
        log = trace([*command, database, 'fault'], case / 'trace', tracer,
                    expected, f'fdatasync:error={error}:when=1')
        assert f'= -1 {error}' in log and '(INJECTED)' in log, log
        calls = SYNC_CALL.findall(log)
        wal = str(database) + '-wal'
        first_data = calls.index(('fdatasync', wal))
        if unsupported:
            assert calls[first_data + 1] == ('fsync', wal), log
        else:
            assert ('fsync', wal) not in calls[first_data + 1:], log


def check_directory_errors(command, work, tracer):
    # SQLite's journal-creation fence is best effort. EXTRA's fence
    # after deleting the journal reports a directory sync failure.
    for when, expected in [(1, b'committed\n'), (2, b'sqlite error 1290 errno 5\n')]:
        case = work / f'dir-error-{when}'
        case.mkdir()
        database = case / 'data.db'
        with sqlite3.connect(database) as db:
            db.execute('CREATE TABLE t(x INTEGER)')
        db.close()
        log = trace([*command, database, 'delete'], case / 'trace', tracer,
                    expected, f'fsync:error=EIO:when={when}')
        injected = [line for line in log.splitlines() if '(INJECTED)' in line]
        assert len(injected) == 1 and f'<{case}>' in injected[0], log


def main():
    if len(sys.argv) != 4:
        raise SystemExit('usage: check_sqlite_sync.py compiler builddir qemu')
    compiler, build, qemu = (Path(arg).resolve() for arg in sys.argv[1:])
    work = Path(mkdtemp(prefix='sqlite-sync-', dir=build))
    source = work / 'sqlitesync.paslang'
    source.write_text(PROGRAM)
    tracer = shutil.which('strace')
    for target, sdk, launch in [('amd64', build, []),
                                ('arm64', build / 'a64', [qemu, '-cpu', 'cortex-a53'])]:
        case = work / target
        case.mkdir()
        program = case / 'sqlitesync'
        subprocess.run([compiler, '-target', target, '-cpu', 'base', '-Fu', sdk,
                        '-o', program, source], check=True, timeout=40)
        check_files([*launch, program], case, tracer)
        if tracer:
            check_errors([*launch, program], case, tracer)
            check_directory_errors([*launch, program], case, tracer)
        checks = 'interop, sync selection and injected errors' if tracer else 'interop'
        print(f'ok SQLite sync {target}: {checks}')


if __name__ == '__main__':
    main()
