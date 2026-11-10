"""Per node-group cost in extract/unextract: region = span of Toffolis targeting words 4gi..4gi+3; cost = all Toffolis in span."""
import sys, numpy as np
sys.path.insert(0, '.')
from kmb import read_kmb
d = read_kmb(sys.argv[1]); op = d['op']; tags = d['tags']; pos = np.flatnonzero(op == 6)
nq = (op >> 4) & 3; is3 = nq == 3; i3 = np.cumsum(is3) - is3
B = {}
for t, p in zip(tags, pos):
    k, n = t.split(':', 1)
    if n in ('extract', 'unextract'): B.setdefault(n, [0, 0])[0 if k == '@enter' else 1] = p
for st in ('extract', 'unextract'):
    a, b = B[st]; idx = np.flatnonzero(is3[a:b]) + a; tg = d["qqq2"][i3[idx]].astype(np.int64); kind = op[idx] & 0x0f
    w = np.where((kind == 1) & (tg < 840), tg // 12, -1)
    print(st, 'total', len(idx))
    tot = 0; rows = []
    for gi in range(17):
        m = (w >= 4 * gi) & (w < 4 * gi + 4)
        if not m.any(): continue
        lo, hi = idx[m].min(), idx[m].max()
        inspan = int(((idx >= lo) & (idx <= hi)).sum()); tot += inspan
        rows.append((gi, inspan, int(m.sum())))
    print('  gi:cost_in_span(own-word-targets) ' + ' '.join(f"{g}:{c}({o})" for g, c, o in rows))
    print('  sum of spans', tot, ' remainder (main 12-bit chain, normal form, etc.)', len(idx) - tot)
