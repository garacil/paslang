select x.a, y.a, length(x.b) from t x, t y where y.a < 400 order by length(x.b) limit 40 offset 100000;
select x.a, y.a from t x, t y where y.a < 400 order by substr(x.b, 1, 2), y.a % 4 limit 40 offset 150000;
select x.a, y.a from t x, t y where y.a < 400 order by x.b desc limit 30 offset 77777;
select k, count(*) from (select (x.a + y.a) % 1000 as k from t x, t y where y.a < 400) group by k order by 2 desc, 1 limit 20;
