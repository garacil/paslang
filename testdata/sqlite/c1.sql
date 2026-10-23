select 1;
select * from nope;
select 1/0, 2.5, null, x'00ff', 'a';
select abs(-9223372036854775808);
create table t(a,b);
insert into t values(1,2);
select * from t;
