// GF(2) affine-span tools over state dumps (rows = qubits, 4096 shots = 64 u64 words per row). Own code.
// span rank f...            : per file: nonzero rows, affine rank (rows + all-ones)
// span pair listA listB     : for each a in A, b in B: rA rB rank(A u B)   (dim(A n B) = rA + rB - rAB)
// span contain A B          : per nonzero row q of B: in affine span of A? exact equal/complement row in A?
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#define WW 64
typedef uint64_t u64;
typedef struct { int n; u64 *r; int *piv; } Basis;
static u64 *load(const char *p, int *nrows) {
  FILE *f = fopen(p, "rb"); if (!f) { fprintf(stderr, "open %s\n", p); exit(1); }
  fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
  *nrows = sz / (WW * 8); u64 *d = malloc(sz); if (fread(d, 1, sz, f) != (size_t)sz) exit(2); fclose(f); return d;
}
static void binit(Basis *b, int cap) { b->n = 0; b->r = malloc((size_t)cap * WW * 8); b->piv = malloc(cap * sizeof(int)); }
static int nz(const u64 *x) { for (int w = 0; w < WW; w++) if (x[w]) return 1; return 0; }
static int insert(Basis *b, const u64 *x0) {   // returns 1 if independent
  u64 x[WW]; memcpy(x, x0, sizeof x);
  for (int i = 0; i < b->n; i++) { int p = b->piv[i]; if ((x[p >> 6] >> (p & 63)) & 1) { u64 *y = b->r + (size_t)i * WW; for (int w = 0; w < WW; w++) x[w] ^= y[w]; } }
  for (int w = 0; w < WW; w++) if (x[w]) { int p = w * 64 + __builtin_ctzll(x[w]); memcpy(b->r + (size_t)b->n * WW, x, sizeof x); b->piv[b->n++] = p; return 1; }
  return 0;
}
static void build(Basis *b, const u64 *d, int n) { u64 ones[WW]; memset(ones, 0xff, sizeof ones); insert(b, ones); for (int q = 0; q < n; q++) if (nz(d + (size_t)q * WW)) insert(b, d + (size_t)q * WW); }
static int readlist(const char *p, char ***out) { FILE *f = fopen(p, "r"); char buf[4096]; int n = 0, cap = 16; char **v = malloc(cap * sizeof(char *));
  while (fscanf(f, "%4095s", buf) == 1) { if (n == cap) { cap *= 2; v = realloc(v, cap * sizeof(char *)); } v[n++] = strdup(buf); } fclose(f); *out = v; return n; }
int main(int argc, char **argv) {
  if (argc < 3) return 1;
  if (!strcmp(argv[1], "rank")) {
    for (int i = 2; i < argc; i++) { int n; u64 *d = load(argv[i], &n); int nzr = 0; for (int q = 0; q < n; q++) nzr += nz(d + (size_t)q * WW);
      Basis b; binit(&b, n + 1); build(&b, d, n); printf("%s %d %d\n", argv[i], nzr, b.n); free(d); free(b.r); free(b.piv); }
  } else if (!strcmp(argv[1], "pair")) {
    char **A, **B; int na = readlist(argv[2], &A), nb = readlist(argv[3], &B);
    for (int i = 0; i < na; i++) { int n; u64 *d = load(A[i], &n); Basis ba; binit(&ba, n + 1); build(&ba, d, n); int rA = ba.n;
      for (int j = 0; j < nb; j++) { int m; u64 *e = load(B[j], &m); Basis bb; binit(&bb, m + 1); build(&bb, e, m); int rB = bb.n;
        Basis u; binit(&u, n + m + 2); u.n = rA; memcpy(u.r, ba.r, (size_t)rA * WW * 8); memcpy(u.piv, ba.piv, rA * sizeof(int));
        for (int k = 0; k < rB; k++) insert(&u, bb.r + (size_t)k * WW);
        printf("%s %s %d %d %d\n", A[i], B[j], rA, rB, u.n); fflush(stdout); free(e); free(bb.r); free(bb.piv); free(u.r); free(u.piv); }
      free(d); free(ba.r); free(ba.piv); }
  } else if (!strcmp(argv[1], "hash")) {
    for (int i = 2; i < argc; i++) { int n; u64 *d = load(argv[i], &n); Basis b; binit(&b, n + 1); build(&b, d, n);
      for (int x = 0; x < b.n; x++) { int p = b.piv[x]; for (int y = 0; y < b.n; y++) if (y != x) { u64 *ry = b.r + (size_t)y * WW; if ((ry[p >> 6] >> (p & 63)) & 1) { u64 *rx = b.r + (size_t)x * WW; for (int w = 0; w < WW; w++) ry[w] ^= rx[w]; } } }
      int *ord = malloc(b.n * sizeof(int)); for (int x = 0; x < b.n; x++) ord[x] = x;
      for (int x = 1; x < b.n; x++) { int k = ord[x], j = x - 1; while (j >= 0 && b.piv[ord[j]] > b.piv[k]) { ord[j + 1] = ord[j]; j--; } ord[j + 1] = k; }
      u64 h = 1469598103934665603ULL; for (int x = 0; x < b.n; x++) { u64 *r = b.r + (size_t)ord[x] * WW; for (int w = 0; w < WW; w++) { h ^= r[w]; h *= 1099511628211ULL; } }
      printf("%s %d %016llx\n", argv[i], b.n, (unsigned long long)h); free(ord); free(d); free(b.r); free(b.piv); }
  } else if (!strcmp(argv[1], "contain")) {
    int n, m; u64 *a = load(argv[2], &n), *bq = load(argv[3], &m); Basis ba; binit(&ba, n + 1); build(&ba, a, n);
    for (int q = 0; q < m; q++) { const u64 *x = bq + (size_t)q * WW; if (!nz(x)) continue;
      Basis t = ba; t.r = malloc((size_t)(ba.n + 1) * WW * 8); t.piv = malloc((ba.n + 1) * sizeof(int)); memcpy(t.r, ba.r, (size_t)ba.n * WW * 8); memcpy(t.piv, ba.piv, ba.n * sizeof(int));
      int indep = insert(&t, x); int eq = -1, cp = -1;
      for (int p = 0; p < n; p++) { const u64 *y = a + (size_t)p * WW; int e = 1, c = 1; for (int w = 0; w < WW; w++) { if (y[w] != x[w]) e = 0; if (y[w] != ~x[w]) c = 0; } if (e && eq < 0) eq = p; if (c && cp < 0) cp = p; }
      printf("%d %d %d %d\n", q, !indep, eq, cp); free(t.r); free(t.piv); }
  }
  return 0;
}
