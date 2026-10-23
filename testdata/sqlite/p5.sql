select sqlite_compileoption_used('THREADSAFE'), sqlite_compileoption_used('SQLITE_MAX_LENGTH'), sqlite_compileoption_used('MAX_LEN'), sqlite_compileoption_get(0) is not null, sqlite_compileoption_get(1000);
select load_extension('x');
select match('a','b');
select sqlite_log(3, 'hello log');
