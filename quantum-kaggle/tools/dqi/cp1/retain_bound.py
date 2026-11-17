"""Sample-based estimate of how many more AND-products could be retained in idle qubits (product retention).
pairs: consecutive occurrences (i<j) of the same unconditioned product function (equal on all 4096 sample shots);
hosts: touch-based idle windows (qubit zero on all shots after its last touch s and untouched until e).
Greedy: pairs by end j; a window can host disjoint pairs; each op starts/ends at most one retention (chains of
the same product allowed). Also reports which stage the saved Toffoli (at j) lies in.
usage: retain_bound.py out/h890 stage_cuts.json tag"""
import sys, json, numpy as np, collections, bisect
pre, cutsf, tag = sys.argv[1], sys.argv[2], sys.argv[3]
cuts = json.load(open(cutsf))[tag]; names = ['pre', 'ext', 'syn', 'conv', 'scan', "conv'", "syn'", "ext'", 'post']
r = np.fromfile(pre + '_prod.bin', dtype=np.uint64).reshape(-1, 5)
op = r[:, 0].astype(np.int64); kind = (r[:, 1] >> np.uint64(32)).astype(int); cond = (r[:, 1] & np.uint64(1)).astype(bool)
occ = collections.defaultdict(list)
for i in np.flatnonzero(~cond):
    hs = [r[i, 2]] if kind[i] == 1 else [r[i, 2], r[i, 3], r[i, 4]]
    for h in hs:
        if h: occ[int(h)].append(int(op[i]))
pairs = []
for h, v in occ.items():
    v = sorted(set(v))
    for a, b in zip(v, v[1:]): pairs.append((b, a, h))
idle = np.fromfile(pre + '_idle.bin', dtype=np.int64).reshape(-1, 3)
print('repeat pairs', len(pairs), 'idle windows', len(idle))
# candidate windows per pair: sweep by i
order = sorted(range(len(pairs)), key=lambda x: pairs[x][1])
wins = idle[np.argsort(idle[:, 0])]; wi = 0; active = []   # active: list of (e, s, q, idx)
cand = {}
import heapq
for x in order:
    j, i, h = pairs[x]
    while wi < len(wins) and wins[wi, 0] < i:
        heapq.heappush(active, (int(wins[wi, 1]), int(wins[wi, 0]), int(wins[wi, 2]), wi)); wi += 1
    while active and active[0][0] <= i: heapq.heappop(active)
    c = [w for w in active if w[0] > j]
    if c: cand[x] = c
print('pairs with at least one idle host window covering them:', len(cand))
busy = {}; used_s = {}; used_e = {}; got = []
for x in sorted(cand, key=lambda x: pairs[x][0]):
    j, i, h = pairs[x]
    if j in used_e or (i in used_s and used_s[i] != h) or (j in used_s and used_s[j] != h) or (i in used_e and used_e[i] != h): continue
    best = None
    for (e, s, q, idx) in cand[x]:
        bu = busy.get(idx, s)
        if bu < i and (best is None or bu > best[0]): best = (bu, idx)
    if best is None: continue
    busy[best[1]] = j; used_s[i] = h; used_e[j] = h; got.append(x)
st = collections.Counter(names[bisect.bisect_right(cuts, pairs[x][0]) - 1] for x in got)
print('greedy retained pairs (upper-bound estimate):', len(got), 'by stage of the saved Toffoli:', dict(st))
