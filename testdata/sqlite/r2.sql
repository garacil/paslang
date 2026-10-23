select a % 7, count(*), sum(a) from t group by 1 order by 2 desc, 1;
select b from t order by length(b), a limit 20;
select a, length(b) from t order by b desc limit 10;
select distinct a % 13 from t order by 1;
select count(*) from (select a from t order by b);
select a % 5 as k, group_concat(a, ',') from (select a from t where a < 60 order by a desc) group by k;
select a from t order by a % 3, a desc limit 15;
