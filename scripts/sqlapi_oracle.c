/* This file is part of paslang.
   Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
   paslang is free software under the GNU General Public License,
   version 3 or (at your option) any later version; see the file COPYING.

   testdata/sqlapi's oracle: SQLite 3.54.1 itself, built from the
   amalgamation the project keeps:
     gcc -O1 -w -Idocs/ref/sqlite/amalg/sqlite-amalgamation-3540100 \
       -o sqlapi_oracle scripts/sqlapi_oracle.c -lm
   run as testdata/sqlapi runs (DB SCRIPT [ENCODING]); its output is
   testdata/sqlite's NAME.out (scripts/check_sqlapi.py). */
/* P405 test oracle: a script run through SQLite's API as an application
   runs it: sqlite3_open_v2, then each statement prepared with
   sqlite3_prepare_v2 from where the last ended, stepped to its end and
   finalized; every result code, extended code and message, each row
   (type, text, and a real's bits), the connection's counts */
#include "sqlite3.c"
static void hexs(const unsigned char *z, int n){
  int i;
  if( z==0 ){ printf("~"); return; }
  if( n==0 ){ printf("-"); return; }
  for(i=0; i<n; i++) printf("%02x", z[i]);
}
static void logcb(void *arg, int code, const char *msg){
  printf("L %d ", code);
  hexs((const unsigned char*)msg, strlen(msg));
  printf("\n");
}

/* two test modules, the same in tapi: series (eponymous, a table-valued
   function series(start, stop, step)) and kv (CREATE VIRTUAL TABLE, rows
   kept in memory, written, transactions and MATCH reported as V lines) */
typedef struct SerCur { sqlite3_vtab_cursor base; sqlite3_int64 i, start, stop, step; } SerCur;
static int serConnect(sqlite3 *db, void *pAux, int argc, const char *const*argv, sqlite3_vtab **ppVtab, char **pzErr){
  int rc = sqlite3_declare_vtab(db, "CREATE TABLE x(value, start hidden, stop hidden, step hidden)");
  if( rc==SQLITE_OK ){ sqlite3_vtab *p = sqlite3_malloc(sizeof(*p)); memset(p, 0, sizeof(*p)); *ppVtab = p; }
  return rc;
}
static int serDisconnect(sqlite3_vtab *p){ sqlite3_free(p); return 0; }
static int serBestIndex(sqlite3_vtab *tab, sqlite3_index_info *pInfo){
  int i, n = 0; char zCols[8]; int nCols = 0;
  for(i=0; i<pInfo->nConstraint; i++){
    const struct sqlite3_index_constraint *c = &pInfo->aConstraint[i];
    if( c->iColumn>=1 && c->op==SQLITE_INDEX_CONSTRAINT_EQ ){
      if( !c->usable ) return SQLITE_CONSTRAINT;
      if( nCols<7 ){
        pInfo->aConstraintUsage[i].argvIndex = ++n;
        pInfo->aConstraintUsage[i].omit = 1;
        zCols[nCols++] = (char)('0' + c->iColumn);
      }
    }
  }
  zCols[nCols] = 0;
  pInfo->idxNum = nCols;
  pInfo->idxStr = sqlite3_mprintf("%s", zCols);
  pInfo->needToFreeIdxStr = 1;
  pInfo->estimatedCost = nCols>=2 ? 10.0 : 1000000.0;
  pInfo->estimatedRows = nCols>=2 ? 10 : 1000;
  if( pInfo->nOrderBy==1 && pInfo->aOrderBy[0].iColumn==0 && !pInfo->aOrderBy[0].desc ){
    pInfo->orderByConsumed = 1;
  }
  return SQLITE_OK;
}
static int serOpen(sqlite3_vtab *p, sqlite3_vtab_cursor **pp){
  SerCur *c = sqlite3_malloc(sizeof(*c)); memset(c, 0, sizeof(*c)); *pp = &c->base; return SQLITE_OK;
}
static int serClose(sqlite3_vtab_cursor *c){ sqlite3_free(c); return SQLITE_OK; }
static int serFilter(sqlite3_vtab_cursor *cur, int idxNum, const char *idxStr, int argc, sqlite3_value **argv){
  SerCur *c = (SerCur*)cur; int i;
  c->start = 0; c->stop = 10; c->step = 1;
  for(i=0; i<argc && idxStr && idxStr[i]; i++){
    sqlite3_int64 v = sqlite3_value_int64(argv[i]);
    if( idxStr[i]=='1' ) c->start = v; else if( idxStr[i]=='2' ) c->stop = v; else c->step = v;
  }
  if( c->step<=0 ) c->step = 1;
  c->i = c->start;
  return SQLITE_OK;
}
static int serNext(sqlite3_vtab_cursor *cur){ SerCur *c = (SerCur*)cur; c->i += c->step; return SQLITE_OK; }
static int serEof(sqlite3_vtab_cursor *cur){ SerCur *c = (SerCur*)cur; return c->i > c->stop; }
static int serColumn(sqlite3_vtab_cursor *cur, sqlite3_context *ctx, int i){
  SerCur *c = (SerCur*)cur; sqlite3_int64 x;
  switch( i ){ case 0: x = c->i; break; case 1: x = c->start; break; case 2: x = c->stop; break; default: x = c->step; }
  sqlite3_result_int64(ctx, x); return SQLITE_OK;
}
static int serRowid(sqlite3_vtab_cursor *cur, sqlite3_int64 *p){ *p = ((SerCur*)cur)->i; return SQLITE_OK; }
static sqlite3_module serModule = { 0, 0, serConnect, serBestIndex, serDisconnect, 0, serOpen, serClose,
  serFilter, serNext, serEof, serColumn, serRowid };

#define KVMAX 64
typedef struct KvRow { sqlite3_int64 rowid; char k[32]; char v[32]; int live; } KvRow;
typedef struct KvTab { sqlite3_vtab base; KvRow a[KVMAX]; int n; sqlite3_int64 next; sqlite3 *db; } KvTab;
typedef struct KvCur { sqlite3_vtab_cursor base; int i; int one; } KvCur;
static int kvInit(sqlite3 *db, int argc, const char *const*argv, sqlite3_vtab **ppVtab, const char *zWhat){
  int i, rc;
  printf("V %s", zWhat);
  for(i=0; i<argc; i++) printf(" %s", argv[i]);
  printf("\n");
  rc = sqlite3_declare_vtab(db, "CREATE TABLE x(k TEXT, v)");
  if( rc==SQLITE_OK ){ KvTab *p = sqlite3_malloc(sizeof(*p)); memset(p, 0, sizeof(*p)); p->next = 1; p->db = db; *ppVtab = &p->base; }
  return rc;
}
static int kvCreate(sqlite3 *db, void *pAux, int argc, const char *const*argv, sqlite3_vtab **pp, char **e){
  return kvInit(db, argc, argv, pp, "create");
}
static int kvConnect(sqlite3 *db, void *pAux, int argc, const char *const*argv, sqlite3_vtab **pp, char **e){
  return kvInit(db, argc, argv, pp, "connect");
}
static int kvDisconnect(sqlite3_vtab *p){ printf("V disconnect\n"); sqlite3_free(p); return 0; }
static int kvDestroy(sqlite3_vtab *p){ printf("V destroy\n"); sqlite3_free(p); return 0; }
static int kvBestIndex(sqlite3_vtab *tab, sqlite3_index_info *pInfo){
  int i;
  pInfo->idxNum = 0; pInfo->estimatedCost = 100.0;
  for(i=0; i<pInfo->nConstraint; i++){
    if( pInfo->aConstraint[i].iColumn==-1 && pInfo->aConstraint[i].op==SQLITE_INDEX_CONSTRAINT_EQ
     && pInfo->aConstraint[i].usable ){
      pInfo->aConstraintUsage[i].argvIndex = 1; pInfo->aConstraintUsage[i].omit = 1;
      pInfo->idxNum = 1; pInfo->estimatedCost = 1.0; pInfo->estimatedRows = 1;
      pInfo->idxFlags = SQLITE_INDEX_SCAN_UNIQUE;
      break;
    }
  }
  return SQLITE_OK;
}
static int kvOpen(sqlite3_vtab *p, sqlite3_vtab_cursor **pp){
  KvCur *c = sqlite3_malloc(sizeof(*c)); memset(c, 0, sizeof(*c)); *pp = &c->base; return SQLITE_OK;
}
static int kvClose(sqlite3_vtab_cursor *c){ sqlite3_free(c); return SQLITE_OK; }
static void kvSkip(KvCur *c){
  KvTab *t = (KvTab*)c->base.pVtab;
  while( c->i<t->n && !t->a[c->i].live ) c->i++;
}
static int kvFilter(sqlite3_vtab_cursor *cur, int idxNum, const char *idxStr, int argc, sqlite3_value **argv){
  KvCur *c = (KvCur*)cur; KvTab *t = (KvTab*)cur->pVtab;
  c->i = 0; c->one = 0;
  if( idxNum==1 ){
    sqlite3_int64 r = sqlite3_value_int64(argv[0]);
    c->one = 1;
    while( c->i<t->n && !(t->a[c->i].live && t->a[c->i].rowid==r) ) c->i++;
  }else{
    kvSkip(c);
  }
  return SQLITE_OK;
}
static int kvNext(sqlite3_vtab_cursor *cur){
  KvCur *c = (KvCur*)cur; KvTab *t = (KvTab*)cur->pVtab;
  if( c->one ){ c->i = t->n; }else{ c->i++; kvSkip(c); }
  return SQLITE_OK;
}
static int kvEof(sqlite3_vtab_cursor *cur){ KvCur *c = (KvCur*)cur; return c->i >= ((KvTab*)cur->pVtab)->n; }
static int kvColumn(sqlite3_vtab_cursor *cur, sqlite3_context *ctx, int i){
  KvCur *c = (KvCur*)cur; KvTab *t = (KvTab*)cur->pVtab;
  if( sqlite3_vtab_nochange(ctx) ){ printf("V nochange %d\n", i); return SQLITE_OK; }
  sqlite3_result_text(ctx, i==0 ? t->a[c->i].k : t->a[c->i].v, -1, SQLITE_TRANSIENT);
  return SQLITE_OK;
}
static int kvRowid(sqlite3_vtab_cursor *cur, sqlite3_int64 *p){
  KvCur *c = (KvCur*)cur; *p = ((KvTab*)cur->pVtab)->a[c->i].rowid; return SQLITE_OK;
}
static int kvFind(KvTab *t, sqlite3_int64 r){
  int i; for(i=0; i<t->n; i++) if( t->a[i].live && t->a[i].rowid==r ) return i; return -1;
}
static int kvUpdate(sqlite3_vtab *tab, int argc, sqlite3_value **argv, sqlite3_int64 *pRowid){
  KvTab *t = (KvTab*)tab; int i;
  printf("V update %d %d\n", argc, sqlite3_vtab_on_conflict(t->db));
  if( argc==1 ){
    i = kvFind(t, sqlite3_value_int64(argv[0]));
    if( i>=0 ) t->a[i].live = 0;
    return SQLITE_OK;
  }
  if( sqlite3_value_type(argv[0])==SQLITE_NULL ){
    sqlite3_int64 r;
    const unsigned char *k = sqlite3_value_text(argv[2]);
    if( k && strcmp((const char*)k, "bad")==0 ){
      tab->zErrMsg = sqlite3_mprintf("kv refuses %s", k);
      return SQLITE_CONSTRAINT;
    }
    if( t->n>=KVMAX ) return SQLITE_FULL;
    r = sqlite3_value_type(argv[1])==SQLITE_NULL ? t->next : sqlite3_value_int64(argv[1]);
    if( r>=t->next ) t->next = r+1;
    i = t->n++;
    t->a[i].rowid = r; t->a[i].live = 1;
    snprintf(t->a[i].k, 32, "%s", k ? (const char*)k : "");
    snprintf(t->a[i].v, 32, "%s", sqlite3_value_text(argv[3]) ? (const char*)sqlite3_value_text(argv[3]) : "");
    *pRowid = r;
    return SQLITE_OK;
  }
  i = kvFind(t, sqlite3_value_int64(argv[0]));
  if( i>=0 ){
    t->a[i].rowid = sqlite3_value_int64(argv[1]);
    if( !sqlite3_value_nochange(argv[2]) ) snprintf(t->a[i].k, 32, "%s", sqlite3_value_text(argv[2]) ? (const char*)sqlite3_value_text(argv[2]) : "");
    if( !sqlite3_value_nochange(argv[3]) ) snprintf(t->a[i].v, 32, "%s", sqlite3_value_text(argv[3]) ? (const char*)sqlite3_value_text(argv[3]) : "");
  }
  return SQLITE_OK;
}
static int kvBegin(sqlite3_vtab *p){ printf("V begin\n"); return SQLITE_OK; }
static int kvSync(sqlite3_vtab *p){ printf("V sync\n"); return SQLITE_OK; }
static int kvCommit(sqlite3_vtab *p){ printf("V commit\n"); return SQLITE_OK; }
static int kvRollback(sqlite3_vtab *p){ printf("V rollback\n"); return SQLITE_OK; }
static int kvRename(sqlite3_vtab *p, const char *z){ printf("V rename %s\n", z); return SQLITE_OK; }
static void kvMatch(sqlite3_context *ctx, int argc, sqlite3_value **argv){
  const char *a = (const char*)sqlite3_value_text(argv[0]);
  const char *b = (const char*)sqlite3_value_text(argv[1]);
  sqlite3_result_int(ctx, a && b && strstr(b, a)!=0);
}
static int kvFindFunction(sqlite3_vtab *p, int nArg, const char *zName,
    void (**pxFunc)(sqlite3_context*,int,sqlite3_value**), void **ppArg){
  if( strcmp(zName, "match")==0 && nArg==2 ){ *pxFunc = kvMatch; *ppArg = 0; return 1; }
  return 0;
}
static int kvIntegrity(sqlite3_vtab *p, const char *zSchema, const char *zTab, int mFlags, char **pzErr){
  printf("V integrity %s %s %d\n", zSchema, zTab, mFlags);
  if( strcmp(zTab, "k4")==0 ) *pzErr = sqlite3_mprintf("kv finds %s.%s wanting", zSchema, zTab);
  return SQLITE_OK;
}
static sqlite3_module kvModule = { 4, kvCreate, kvConnect, kvBestIndex, kvDisconnect, kvDestroy, kvOpen, kvClose,
  kvFilter, kvNext, kvEof, kvColumn, kvRowid, kvUpdate, kvBegin, kvSync, kvCommit, kvRollback, kvFindFunction,
  kvRename, 0, 0, 0, 0, kvIntegrity };

static void backupToFunc(sqlite3_context *ctx, int argc, sqlite3_value **argv){
  sqlite3 *src = sqlite3_context_db_handle(ctx);
  sqlite3 *dest;
  sqlite3_backup *b;
  int rc, np = sqlite3_value_int(argv[1]);
  rc = sqlite3_open_v2((const char*)sqlite3_value_text(argv[0]), &dest, SQLITE_OPEN_READWRITE|SQLITE_OPEN_CREATE, 0);
  b = sqlite3_backup_init(dest, "main", src, "main");
  if( b==0 ){
    printf("B init %d ", sqlite3_errcode(dest));
    hexs((const unsigned char*)sqlite3_errmsg(dest), strlen(sqlite3_errmsg(dest)));
    printf("\n");
    sqlite3_close(dest);
    sqlite3_result_int(ctx, -1);
    return;
  }
  do{
    rc = sqlite3_backup_step(b, np);
    printf("B step %d %d %d\n", rc, sqlite3_backup_remaining(b), sqlite3_backup_pagecount(b));
  }while( rc==SQLITE_OK );
  rc = sqlite3_backup_finish(b);
  printf("B finish %d %d\n", rc, sqlite3_errcode(dest));
  printf("B close %d\n", sqlite3_close(dest));
  sqlite3_result_int(ctx, rc);
}

static void serFunc(sqlite3_context *ctx, int argc, sqlite3_value **argv){
  sqlite3_int64 sz = 0;
  unsigned char *p = sqlite3_serialize(sqlite3_context_db_handle(ctx), (const char*)sqlite3_value_text(argv[0]), &sz, 0);
  printf("Ser %lld %d\n", sz, p!=0);
  if( p ){ sqlite3_result_blob64(ctx, p, sz, SQLITE_TRANSIENT); sqlite3_free(p); }
}
/* fpdigits(N): SQLITE_DBCONFIG_FP_DIGITS set to N (0 leaves it); the digits after */
static void fpdigitsFunc(sqlite3_context *ctx, int argc, sqlite3_value **argv){
  int out = -1;
  int rc = sqlite3_db_config(sqlite3_context_db_handle(ctx), SQLITE_DBCONFIG_FP_DIGITS, sqlite3_value_int(argv[0]), &out);
  sqlite3_result_int(ctx, rc*1000 + out);
}

static void deserFunc(sqlite3_context *ctx, int argc, sqlite3_value **argv){
  int n = sqlite3_value_bytes(argv[1]);
  unsigned char *p = sqlite3_malloc64(n ? n : 1);
  int rc;
  memcpy(p, sqlite3_value_blob(argv[1]), n);
  rc = sqlite3_deserialize(sqlite3_context_db_handle(ctx), (const char*)sqlite3_value_text(argv[0]), p, n, n,
    SQLITE_DESERIALIZE_FREEONCLOSE|SQLITE_DESERIALIZE_RESIZEABLE);
  printf("Deser %d\n", rc);
  sqlite3_result_int(ctx, rc);
}

static int revCmp(void *p, int n1, const void *z1, int n2, const void *z2){
  int r = memcmp(z1, z2, n1<n2 ? n1 : n2);
  if( r==0 ) r = n1-n2;
  return r<0 ? 1 : (r>0 ? -1 : 0);
}
static int lenCmp(void *p, int n1, const void *z1, int n2, const void *z2){
  int r;
  if( n1!=n2 ) return n1<n2 ? -1 : 1;
  r = memcmp(z1, z2, n1);
  return r<0 ? -1 : (r>0 ? 1 : 0);
}
static void collNeeded(void *p, sqlite3 *db, int enc, const char *z){
  printf("N %d %s\n", enc, z);
  if( strcmp(z, "lazy")==0 ) sqlite3_create_collation(db, "lazy", SQLITE_UTF8, 0, revCmp);
}

int main(int argc, char **argv){
  FILE *f = fopen(argv[2], "rb");
  static char sql[1000000];
  size_t n = fread(sql, 1, sizeof(sql)-1, f);
  const char *at = sql, *tail;
  sqlite3 *db;
  int rc, i;
  sql[n] = 0;
  sqlite3_config(SQLITE_CONFIG_LOG, logcb, 0);
  rc = sqlite3_open_v2(argv[1], &db, SQLITE_OPEN_READWRITE|SQLITE_OPEN_CREATE, 0);
  sqlite3_create_module(db, "series", &serModule, 0);
  sqlite3_create_module(db, "kv", &kvModule, 0);
  sqlite3_create_function(db, "backup_to", 2, SQLITE_UTF8, 0, backupToFunc, 0, 0);
  sqlite3_create_function(db, "ser", 1, SQLITE_UTF8, 0, serFunc, 0, 0);
  sqlite3_create_function(db, "deser", 2, SQLITE_UTF8, 0, deserFunc, 0, 0);
  sqlite3_create_function(db, "fpdigits", 1, SQLITE_UTF8, 0, fpdigitsFunc, 0, 0);
  sqlite3_create_collation(db, "rev", SQLITE_UTF8, 0, revCmp);
  sqlite3_create_collation(db, "len16", SQLITE_UTF16LE, 0, lenCmp);
  sqlite3_create_collation(db, "lenbe", SQLITE_UTF16BE, 0, lenCmp);
  sqlite3_collation_needed(db, 0, collNeeded);
  /* a third argument: the new database's encoding, set before the script */
  if( argc>3 ){
    char q[64];
    snprintf(q, sizeof(q), "PRAGMA encoding='%s'", argv[3]);
    sqlite3_exec(db, q, 0, 0, 0);
  }
  printf("O %d %d ", rc, sqlite3_extended_errcode(db));
  hexs((const unsigned char*)sqlite3_errmsg(db), strlen(sqlite3_errmsg(db)));
  printf("\n");
  while( at[0] ){
    sqlite3_stmt *st = 0;
    int ncol;
    rc = sqlite3_prepare_v2(db, at, -1, &st, &tail);
    printf("P %d %d %d ", rc, sqlite3_extended_errcode(db), (int)(tail-sql));
    hexs((const unsigned char*)sqlite3_errmsg(db), strlen(sqlite3_errmsg(db)));
    printf("\n");
    if( rc ){ if( tail<=at ) break; at = tail; continue; }
    if( st==0 ){ at = tail; continue; }
    printf("S ");
    hexs((const unsigned char*)sqlite3_sql(st), strlen(sqlite3_sql(st)));
    printf(" %d %d %d\n", sqlite3_stmt_readonly(st), sqlite3_stmt_isexplain(st), sqlite3_bind_parameter_count(st));
    /* every parameter bound, by its index: an integer, a real, a text, a
       blob, NULL and a zeroblob in turn; its name and the bind's answer */
    if( sqlite3_bind_parameter_count(st)>0 ){
      int np = sqlite3_bind_parameter_count(st), k;
      printf("B %d", np);
      for(k=1; k<=np; k++){
        const char *nm = sqlite3_bind_parameter_name(st, k);
        char tb[32];
        unsigned char bb[2];
        int brc = 0;
        switch( k % 6 ){
          case 0: brc = sqlite3_bind_int64(st, k, (sqlite3_int64)k*1000+7); break;
          case 1: brc = sqlite3_bind_double(st, k, k+0.25); break;
          case 2: snprintf(tb, sizeof(tb), "p%d", k); brc = sqlite3_bind_text(st, k, tb, -1, SQLITE_TRANSIENT); break;
          case 3: bb[0] = (unsigned char)k; bb[1] = 0xff; brc = sqlite3_bind_blob(st, k, bb, 2, SQLITE_TRANSIENT); break;
          case 4: brc = sqlite3_bind_null(st, k); break;
          default: brc = sqlite3_bind_zeroblob(st, k, k); break;
        }
        printf(" ");
        if( nm ) hexs((const unsigned char*)nm, strlen(nm)); else printf("~");
        printf(":%d", brc);
      }
      printf(" %d\n", sqlite3_bind_parameter_index(st, "$x"));
    }
    ncol = sqlite3_column_count(st);
    printf("C %d", ncol);
    for(i=0; i<ncol; i++){
      const char *z = sqlite3_column_name(st, i);
      printf(" ");
      hexs((const unsigned char*)z, z ? strlen(z) : 0);
      z = sqlite3_column_decltype(st, i);
      printf("/");
      hexs((const unsigned char*)z, z ? strlen(z) : 0);
    }
    printf("\n");
    while( (rc = sqlite3_step(st))==SQLITE_ROW ){
      printf("R");
      for(i=0; i<ncol; i++){
        int t = sqlite3_column_type(st, i);
        printf(" %d:", t);
        if( t==SQLITE_FLOAT ){
          double d = sqlite3_column_double(st, i);
          unsigned long long b; memcpy(&b, &d, 8);
          printf("%016llx:", b);
        }
        if( t==SQLITE_BLOB ){
          hexs((const unsigned char*)sqlite3_column_blob(st, i), sqlite3_column_bytes(st, i));
        }else{
          const unsigned char *z = sqlite3_column_text(st, i);
          hexs(z, sqlite3_column_bytes(st, i));
        }
      }
      printf("\n");
    }
    printf("D %d %d ", rc, sqlite3_extended_errcode(db));
    hexs((const unsigned char*)sqlite3_errmsg(db), strlen(sqlite3_errmsg(db)));
    printf("\n");
    rc = sqlite3_finalize(st);
    printf("F %d %d %lld %lld %lld %d\n", rc, sqlite3_extended_errcode(db), (long long)sqlite3_changes64(db),
      (long long)sqlite3_total_changes64(db), (long long)sqlite3_last_insert_rowid(db), sqlite3_get_autocommit(db));
    at = tail;
  }
  rc = sqlite3_close(db);
  printf("Z %d\n", rc);
  return 0;
}
