"""Cross-checked retention estimate: a pair (i<j) counts only if the products at i and j are equal on EVERY input set
given, and a host window covers it in EVERY set. Prints counts, density profile, and writes the greedy pair list.
usage: retain2.py stage_cuts.json tag prefix1 [prefix2 ...]"""
import sys, json, numpy as np, collections, bisect, heapq
cuts = json.load(open(sys.argv[1]))[sys.argv[2]]; names = ['pre','ext','syn','conv','scan',"conv'","syn'","ext'",'post']
pres = sys.argv[3:]
def load(pre):
    r = np.fromfile(pre + '_prod.bin', dtype=np.uint64).reshape(-1, 5)
    op = r[:, 0].astype(np.int64); kind = ((r[:, 1] >> np.uint64(32)) & np.uint64(0xff)).astype(int)
    cond = (r[:, 1] & np.uint64(1)).astype(bool); pc = (r[:, 1] >> np.uint64(40)).astype(np.int64)
    # per (op, slot) product id = hash; slot 0 = (a,b), 1 = (a,c), 2 = (b,c)
    prod = {}
    for i in np.flatnonzero(~cond):
        slots = [0] if kind[i] == 1 else [0, 1, 2]
        for s in slots:
            h = int(r[i, 2 + s])
            if h: prod[(int(op[i]), s)] = h
    return prod, dict(zip(op.tolist(), pc.tolist()))
sets = [load(p) for p in pres]
base = sets[0][0]
# consecutive pairs in set 0
occ = collections.defaultdict(list)
for k, h in base.items(): occ[h].append(k)
pairs = []
for h, v in occ.items():
    v.sort()
    for a, b in zip(v, v[1:]):
        if a[0] == b[0]: continue
        ok = all(s[0].get(a) is not None and s[0].get(a) == s[0].get(b) for s in sets[1:])
        pairs.append((b[0], a[0], h, a[1], b[1], ok))
print('pairs in set 0:', len(pairs), '; equal in all sets:', sum(p[5] for p in pairs))
def windows(pre):
    idle = np.fromfile(pre + '_idle.bin', dtype=np.int64).reshape(-1, 3); return idle[np.argsort(idle[:, 0])]
W0 = windows(pres[0]); others = [windows(p) for p in pres[1:]]
def covered_sets(wins, plist):
    order = sorted(range(len(plist)), key=lambda x: plist[x][1]); wi = 0; active = []; cand = {}
    for x in order:
        j, i = plist[x][0], plist[x][1]
        while wi < len(wins) and wins[wi, 0] < i:
            heapq.heappush(active, (int(wins[wi, 1]), int(wins[wi, 0]), int(wins[wi, 2]), wi)); wi += 1
        while active and active[0][0] <= i: heapq.heappop(active)
        c = [w for w in active if w[0] > j]
        if c: cand[x] = c
    return cand
good = [p for p in pairs if p[5]]
cand = covered_sets(W0, good)
for ow in others:
    c2 = covered_sets(ow, good)
    for x in list(cand):
        if x not in c2: del cand[x]; continue
        qs = {w[2] for w in c2[x]}; cand[x] = [w for w in cand[x] if w[2] in qs]
        if not cand[x]: del cand[x]
print('pairs equal in all sets with a host window in all sets:', len(cand))
busy = {}; used_s = {}; used_e = {}; got = []
for x in sorted(cand, key=lambda x: good[x][0]):
    j, i, h = good[x][0], good[x][1], good[x][2]
    if j in used_e or (i in used_s and used_s[i] != h) or (j in used_s and used_s[j] != h) or (i in used_e and used_e[i] != h): continue
    best = None
    for (e, s, q, idx) in cand[x]:
        bu = busy.get(idx, s)
        if bu < i and (best is None or bu > best[0]): best = (bu, idx, q)
    if best is None: continue
    busy[best[1]] = j; used_s[i] = h; used_e[j] = h; got.append((i, j, best[2], good[x][3], good[x][4]))
st = collections.Counter(names[bisect.bisect_right(cuts, g[1]) - 1] for g in got)
pc0 = sets[0][1]
dens = np.array([pc0.get(g[1], -1) for g in got])
print('greedy retained:', len(got), dict(st))
if len(dens): print('product popcount (of 4096) at j: min', dens.min(), 'p10', int(np.percentile(dens, 10)), 'median', int(np.median(dens)), 'max', dens.max(), '; count <= 8:', int((dens <= 8).sum()))
np.save(sys.argv[3] + '_retain_pairs.npy', np.array(got, dtype=np.int64))
