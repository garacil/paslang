/* This file is part of paslang.
   Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
   paslang is free software under the GNU General Public License,
   version 3 or (at your option) any later version; see the file COPYING.
   testdata/sqlmath's oracle: SQLite 3.54.1 built with its math functions,
   on the system's libm (glibc 2.44 on a processor with FMA made the
   committed answer):
     gcc -O1 -w -DSQLITE_ENABLE_MATH_FUNCTIONS \
       -Idocs/ref/sqlite/amalg/sqlite-amalgamation-3540100 \
       -o sqlmath_oracle scripts/sqlmath_oracle.c -lm
     ./sqlmath_oracle > testdata/sqlmath.out
   The same arguments as testdata/sqlmath.paslang (splitmix64 from 1 for
   each function), the same lines, the same FNV-1a 64 of them. */
#include "sqlite3.c"

static uint64_t gs;

static uint64_t gnext(void)
{
  uint64_t z = (gs += 0x9e3779b97f4a7c15ull);
  z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ull;
  z = (z ^ (z >> 27)) * 0x94d049bb133111ebull;
  return z ^ (z >> 31);
}

static double asd(uint64_t b) { double d; memcpy(&d, &b, 8); return d; }
static uint64_t asu(double d) { uint64_t b; memcpy(&b, &d, 8); return b; }

static double ggen(int mode)
{
  double u;
  uint64_t e;
  switch (mode) {
  case 0: return asd(gnext());
  case 5:
    e = (gnext() >> 11) % 61;
    return asd((gnext() & 0x800fffffffffffffull) | ((1023 + e - 30) << 52));
  case 6:
    e = (gnext() >> 11) % 2046 + 1;
    return asd((gnext() & 0x800fffffffffffffull) | (e << 52));
  }
  u = (double)(gnext() >> 11) * 0x1p-53;
  u = 2 * u - 1;
  switch (mode) {
  case 1: return u;
  case 2: return u * 20;
  case 3: return u * 1000;
  case 7: return 1 + u / 8;
  case 8: return u * 4;
  default: return u * 1e6;
  }
}

static sqlite3 *db;
static uint64_t h;

static void hadd(const char *s)
{
  for (; *s; s++) {
    h ^= (unsigned char)*s;
    h *= 0x100000001b3ull;
  }
}

static void run(const char *name, const char *sql, int nargs, int inty)
{
  sqlite3_stmt *st;
  char line[64];
  int i, rows = 0;
  if (sqlite3_prepare_v2(db, sql, -1, &st, 0) != SQLITE_OK) { printf("%s: %s\n", name, sqlite3_errmsg(db)); exit(1); }
  gs = 1;
  h = 0xcbf29ce484222325ull;
  for (i = 0; i < 20000; i++) {
    if (nargs == 0 && i > 0)
      break;
    if (nargs > 0) {
      double x = ggen(i % 9), y;
      sqlite3_bind_double(st, 1, x);
      if (nargs == 2) {
        if (inty)
          y = (double)(int64_t)((gnext() >> 11) % 2001) - 1000;
        else
          y = ggen((i / 9) % 9);
        sqlite3_bind_double(st, 2, y);
      }
    }
    if (sqlite3_step(st) != SQLITE_ROW) { printf("%s: %s\n", name, sqlite3_errmsg(db)); exit(1); }
    switch (sqlite3_column_type(st, 0)) {
    case SQLITE_NULL: strcpy(line, "n\n"); break;
    case SQLITE_INTEGER: sprintf(line, "i%lld\n", (long long)sqlite3_column_int64(st, 0)); break;
    default: sprintf(line, "%016llx\n", (unsigned long long)asu(sqlite3_column_double(st, 0)));
    }
    hadd(line);
    sqlite3_reset(st);
    rows++;
  }
  sqlite3_finalize(st);
  printf("%s %d %016llx\n", name, rows, (unsigned long long)h);
}

int main(void)
{
  if (sqlite3_open(":memory:", &db) != SQLITE_OK)
    return 1;
  run("ceil", "SELECT ceil(?1)", 1, 0);
  run("ceiling", "SELECT ceiling(?1)", 1, 0);
  run("floor", "SELECT floor(?1)", 1, 0);
  run("trunc", "SELECT trunc(?1)", 1, 0);
  run("ln", "SELECT ln(?1)", 1, 0);
  run("log", "SELECT log(?1)", 1, 0);
  run("log10", "SELECT log10(?1)", 1, 0);
  run("log2", "SELECT log2(?1)", 1, 0);
  run("logb", "SELECT log(?1, ?2)", 2, 0);
  run("exp", "SELECT exp(?1)", 1, 0);
  run("pow", "SELECT pow(?1, ?2)", 2, 0);
  run("power", "SELECT power(?1, ?2)", 2, 1);
  run("mod", "SELECT mod(?1, ?2)", 2, 0);
  run("acos", "SELECT acos(?1)", 1, 0);
  run("asin", "SELECT asin(?1)", 1, 0);
  run("atan", "SELECT atan(?1)", 1, 0);
  run("atan2", "SELECT atan2(?1, ?2)", 2, 0);
  run("cos", "SELECT cos(?1)", 1, 0);
  run("sin", "SELECT sin(?1)", 1, 0);
  run("tan", "SELECT tan(?1)", 1, 0);
  run("cosh", "SELECT cosh(?1)", 1, 0);
  run("sinh", "SELECT sinh(?1)", 1, 0);
  run("tanh", "SELECT tanh(?1)", 1, 0);
  run("acosh", "SELECT acosh(?1)", 1, 0);
  run("asinh", "SELECT asinh(?1)", 1, 0);
  run("atanh", "SELECT atanh(?1)", 1, 0);
  run("sqrt", "SELECT sqrt(?1)", 1, 0);
  run("radians", "SELECT radians(?1)", 1, 0);
  run("degrees", "SELECT degrees(?1)", 1, 0);
  run("pi", "SELECT pi()", 0, 0);
  sqlite3_close(db);
  return 0;
}
