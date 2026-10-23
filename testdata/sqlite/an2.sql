select tbl, idx, stat from sqlite_stat1 order by tbl, idx;
explain query plan select * from t1 where a = 3 and b = 5;
explain query plan select * from t1 where b = 5;
drop table sqlite_stat1;
analyze t4;
select * from sqlite_stat1;
