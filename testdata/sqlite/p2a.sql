create table t(a integer primary key, b text, c int not null, d real);
create index tb on t(b);
create unique index tc on t(c);
create table s(x text, y int, primary key(x)) without rowid;
create index sy on s(y);
with recursive n(i) as (select 1 union all select i+1 from n where i<300) insert into t select i, 'b'||i, i, i*1.5 from n;
insert into s select b, c from t;
