"""Jointly compatible retention set under a per-op free-wire capacity profile.

Edges (i, j) need one free wire at every op in [i, j] (hand-offs between free wires are free CNOT moves). A set of
edges is jointly feasible iff at every op the number of edges covering it is <= the number of free wires there.
Greedy by right endpoint (accept if the covered range still has capacity >= 1), implemented with a lazy range-add /
range-min segment tree over the compressed endpoints. Each segment's capacity is the minimum over its ops.
usage: compose.py <edge_minfree.npy> <profile .u16> <extra wires> [max distance]"""
import sys, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0]); from rangemin import RMin
E = np.load(sys.argv[1]); prof = np.fromfile(sys.argv[2], np.uint16); extra = int(sys.argv[3])
maxd = int(sys.argv[4]) if len(sys.argv) > 4 else 10**12
I, J = E[:, 0], E[:, 1]; keep = (J - I) <= maxd; I, J = I[keep], J[keep]
pts = np.unique(np.concatenate([I, J]))                       # elementary segments [pts[t], pts[t+1]) and the point pts[-1]
R = RMin(prof)
cap = np.array([R(int(pts[t]), int(pts[t + 1]) - 1) if t + 1 < len(pts) else R(int(pts[t]), int(pts[t])) for t in range(len(pts))],
               dtype=np.int64) + extra
n = len(cap); size = 1
while size < n: size *= 2
mn = np.full(2 * size, 10**9, np.int64); lz = np.zeros(2 * size, np.int64); mn[size:size + n] = cap
for v in range(size - 1, 0, -1): mn[v] = min(mn[2 * v], mn[2 * v + 1])
def upd(v, lo, hi, l, r, d):
    if r < lo or hi < l: return
    if l <= lo and hi <= r: mn[v] += d; lz[v] += d; return
    m = (lo + hi) // 2; upd(2 * v, lo, m, l, r, d); upd(2 * v + 1, m + 1, hi, l, r, d); mn[v] = min(mn[2 * v], mn[2 * v + 1]) + lz[v]
def qry(v, lo, hi, l, r):
    if r < lo or hi < l: return 10**9
    if l <= lo and hi <= r: return mn[v]
    m = (lo + hi) // 2; return min(qry(2 * v, lo, m, l, r), qry(2 * v + 1, m + 1, hi, l, r)) + lz[v]
sys.setrecursionlimit(10000)
li = np.searchsorted(pts, I); ri = np.searchsorted(pts, J)     # edge covers segments li .. ri (ri = the segment starting at j)
order = np.argsort(J, kind='stable'); acc = []
for e in order:
    l, r = int(li[e]), int(ri[e])
    if qry(1, 0, size - 1, l, r) >= 1: upd(1, 0, size - 1, l, r, -1); acc.append(e)
acc = np.array(acc, dtype=int); d = (J - I)[acc] if len(acc) else np.array([])
print(f'edges considered {len(I)}  extra wires {extra}  jointly compatible (greedy) {len(acc)}', end='')
if len(acc): print(f'  distance median {int(np.median(d))}  max {int(d.max())}')
else: print()
