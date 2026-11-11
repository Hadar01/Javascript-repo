"""At each 892-excursion window, test whether some idle live qubit is an affine function of the other idle live qubits
(on 4096 sampled shots). Such a qubit could be CNOT-uncomputed before the window and recomputed after (0 T)."""
import sys, numpy as np, json, collections
sys.path.insert(0, '.'); sys.path.insert(0, 'splice')
from kmb import read_kmb
d = read_kmb(sys.argv[1]); peaks = sys.argv[2]; names = json.load(open(sys.argv[3])); seg = np.fromfile(sys.argv[4], dtype=np.uint16)
op = d['op']; n = len(op); nq = (op >> 4) & 3; idx = np.arange(n, dtype=np.int64)
cols = []
for arr, m in ((d['qqq0'], nq == 3), (d['qqq1'], nq == 3), (d['qqq2'], nq == 3), (d['qq0'], nq == 2), (d['qq1'], nq == 2), (d['q0'], nq == 1)):
    cols.append((arr.astype(np.int64), idx[m]))
q = np.concatenate([c[0] for c in cols]); o = np.concatenate([c[1] for c in cols])
order = np.lexsort((o, q)); q = q[order]; o = o[order]; starts = np.searchsorted(q, np.arange(893))
def touched(qq, S, E):
    a, b = starts[qq], starts[qq + 1]; k = np.searchsorted(o[a:b], S)
    return k < b - a and o[a + k] <= E
wins = []
for line in open(peaks):
    t = line.split()
    if t[0] == 'S': wins.append([int(t[1]), None, t[2]])
    else: wins[-1][1] = int(t[1])
def gf2_rank_rows(Mbits):
    # rows packed into uint64 words; eliminate by picking pivot bit positions
    P = np.packbits(Mbits, axis=1, bitorder='little').view(np.uint64).copy()
    r = 0; nrow = P.shape[0]
    for row in range(nrow):
        v = P[row]
        nz = np.flatnonzero(v)
        if len(nz) == 0: continue
        w = nz[0]; bit = int(v[w]) & -int(v[w])
        col = (P[:, w] & np.uint64(bit)) != 0; col[row] = False
        P[col] ^= v; r += 1
    return r
stats = collections.defaultdict(collections.Counter); cache = {}
for S, E, mp in wins:
    st = names[seg[S]].split('/')[0]
    raw = np.fromfile(f'pkstates/c1_state_{S}.bin', dtype=np.uint64).reshape(892, -1)
    X = np.unpackbits(raw.view(np.uint8), axis=1, bitorder='little')
    live = [i for i, ch in enumerate(mp) if ch == '1']
    idle = [i for i in live if not touched(i, S, E)]
    M = np.concatenate([X[idle], np.ones((1, X.shape[1]), np.uint8)], 0)
    r = gf2_rank_rows(M)
    deficiency = len(idle) + 1 - r
    stats[st]['windows'] += 1; stats[st]['dependent_windows'] += deficiency > 0
    stats[st]['min_deficiency'] = min(stats[st].get('min_deficiency', 10**9), deficiency)
for st, c in stats.items(): print(st, dict(c))
