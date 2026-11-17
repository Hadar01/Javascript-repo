"""Repeated AND-products in an executed circuit (sample-based, 4096 shots): upper bound for product retention.
Input: PROD_OUT records (op, kind|cond, h_ab, h_ac, h_bc) and LIVE_OUT per-op live counts."""
import sys, numpy as np, collections
pre = sys.argv[1]; Q = int(sys.argv[2])
r = np.fromfile(pre + '_prod.bin', dtype=np.uint64).reshape(-1, 5)
live = np.fromfile(pre + '_live.u16', dtype=np.uint16)
op = r[:, 0].astype(np.int64); kind = (r[:, 1] >> np.uint64(32)).astype(int); cond = (r[:, 1] & np.uint64(1)).astype(bool)
occ = collections.defaultdict(list)
for i in range(len(r)):
    if cond[i]: continue
    hs = [r[i, 2]] if kind[i] == 1 else [r[i, 2], r[i, 3], r[i, 4]]
    for h in hs:
        if h: occ[int(h)].append(int(op[i]))
pairs = []
for h, v in occ.items():
    v = sorted(set(v))
    for a, b in zip(v, v[1:]): pairs.append((a, b))
print('unconditioned Toffoli-like records', int((~cond).sum()), 'distinct products', len(occ), 'repeat pairs', len(pairs))
# sparse table for range max of live
import math
L = live.astype(np.int16); lg = [L]
k = 1
while (1 << k) <= len(L):
    prev = lg[-1]; lg.append(np.maximum(prev[:-(1 << (k - 1))], prev[(1 << (k - 1)):])); k += 1
def rmax(a, b):
    n = b - a + 1; j = n.bit_length() - 1
    return int(max(lg[j][a], lg[j][b - (1 << j) + 1]))
free = collections.Counter(); gaps = []
for a, b in pairs:
    m = rmax(a, b); free[Q - m] += 1; gaps.append(b - a)
print('pairs by free qubits over the interval (Q - max live):', sorted(free.items()))
gaps = np.array(gaps); print('gap ops: median', int(np.median(gaps)) if len(gaps) else 0, 'p90', int(np.percentile(gaps, 90)) if len(gaps) else 0)
