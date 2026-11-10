"""Per stage: static Toffoli-like counts by target word (CCX target; CCZ/CSWAP separate)."""
import sys, numpy as np, collections
sys.path.insert(0, '.')
from kmb import read_kmb
d = read_kmb(sys.argv[1]); op = d['op']; tags = d['tags']
pos = np.flatnonzero(op == 6)
nq = (op >> 4) & 3; is3 = nq == 3; i3 = np.cumsum(is3) - is3
bounds = {}
for t, p in zip(tags, pos):
    k, n = t.split(':', 1)
    if '/' not in n and n in ('extract','unextract','synthesis','unsynthesis','convert','unconvert','scan'):
        bounds.setdefault(n, [0, 0])[0 if k == '@enter' else 1] = p
for st in sys.argv[2].split(','):
    a, b = bounds[st]; idx = np.flatnonzero(is3[a:b]) + a
    kind = op[idx] & 0x0f; t = d['qqq2'][i3[idx]]
    c = collections.Counter()
    for kd, q in zip(kind, t):
        if kd == 1: c['S%02d' % (q // 12) if q < 840 else 'anc'] += 1
        else: c['CCZ' if kd == 0 else 'CSWAP'] += 1
    print(st, sum(c.values()), ' '.join(f"{k}:{v}" for k, v in sorted(c.items())))
