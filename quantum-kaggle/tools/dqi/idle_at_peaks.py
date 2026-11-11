"""For each 892-excursion window [S,E] (from PEAK_LOG), find live qubits untouched within [S-M, E+M]:
these are the only candidates for spilling (measure+recompute) to lower Q. Reports per stage."""
import sys, numpy as np, json, collections
sys.path.insert(0, '.')
from kmb import read_kmb
d = read_kmb(sys.argv[1]); peaks = sys.argv[2]; names = json.load(open(sys.argv[3])); seg = np.fromfile(sys.argv[4], dtype=np.uint16)
op = d['op']; n = len(op); nq = (op >> 4) & 3
idx = np.arange(n, dtype=np.int64)
cols = []
m3 = nq == 3; m2 = nq == 2; m1 = nq == 1
for arr in (d['qqq0'], d['qqq1'], d['qqq2']): cols.append((arr.astype(np.int64), idx[m3]))
for arr in (d['qq0'], d['qq1']): cols.append((arr.astype(np.int64), idx[m2]))
cols.append((d['q0'].astype(np.int64), idx[m1]))
q = np.concatenate([c[0] for c in cols]); o = np.concatenate([c[1] for c in cols])
order = np.lexsort((o, q)); q = q[order]; o = o[order]
starts = np.searchsorted(q, np.arange(893))
wins = []
for line in open(peaks):
    t = line.split()
    if t[0] == 'S': wins.append([int(t[1]), None, t[2]])
    else: wins[-1][1] = int(t[1])
res = collections.defaultdict(lambda: collections.Counter())
examples = collections.defaultdict(list)
for M in (0, 2000, 20000, 200000):
    for S, E, mp in wins:
        st = names[seg[S]].split('/')[0]
        live = [i for i, ch in enumerate(mp) if ch == '1']
        idle = []
        for qq in live:
            a, b = starts[qq], starts[qq + 1]
            k = np.searchsorted(o[a:b], S - M)
            if k >= b - a or o[a + k] > E + M: idle.append(qq)
        res[(st, M)]['windows'] += 1
        res[(st, M)]['windows_with_idle'] += bool(idle)
        res[(st, M)]['min_idle'] = min(res[(st, M)].get('min_idle', 999), len(idle))
        if M == 20000 and len(examples[st]) < 3: examples[st].append((S, E, idle[:8]))
for (st, M), c in sorted(res.items()): print(f"{st:14s} margin {M:6d}: windows {c['windows']:4d}  with >=1 idle live qubit {c['windows_with_idle']:4d}  min #idle {c['min_idle']}")
for st, ex in examples.items(): print(st, ex)
