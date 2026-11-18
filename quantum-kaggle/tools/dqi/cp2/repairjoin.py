import pickle, json, numpy as np, collections
D = pickle.load(open('w_deps.pkl', 'rb')); hmr_op = np.array(D['hmr_op']); recs = D['recs']
cuts = np.array(json.load(open('w_cuts.json'))['w']); names = ['pre','ext','syn','conv','scan',"conv'","syn'","ext'",'post']
A = np.fromfile('w_hmr.bin', dtype=np.uint64).reshape(-1, 3); B = np.fromfile('w_hmrf.bin', dtype=np.uint64).reshape(-1, 3)
aop = (A[:, 0] & np.uint64((1 << 40) - 1)).astype(np.int64)
assert len(aop) == len(hmr_op) and (aop == hmr_op).all()
pcn = (A[:, 1] >> np.uint64(32)).astype(np.int64); key = list(zip(A[:, 2].tolist(), B[:, 2].tolist()))
st = np.searchsorted(cuts, hmr_op, side='right') - 1
# later re-measurement of the same function
pos = collections.defaultdict(list)
for i, k in enumerate(key):
    if k[0]: pos[k].append(i)
later = np.full(len(key), -1)
for k, v in pos.items():
    for a, b in zip(v, v[1:]): later[a] = b
# cluster recs
recs.sort(key=lambda r: r[0]); ops = np.array([r[0] for r in recs])
cl = np.split(np.arange(len(recs)), np.flatnonzero(np.diff(ops) > 20000) + 1)
R = np.fromfile('w_prod.bin', dtype=np.uint64).reshape(-1, 5); pop_ = (R[:, 0] & np.uint64((1 << 40) - 1)).astype(np.int64); cpc = (R[:, 0] >> np.uint64(40)).astype(np.int64)
meanw = dict(zip(pop_.tolist(), (cpc / 4096).tolist()))
summary = collections.Counter(); rows = []
for c in cl:
    dep = 0
    for i in c: dep |= recs[i][2]
    ids = [j for j in range(dep.bit_length()) if dep >> j & 1]
    stg = collections.Counter(names[st[j]] for j in ids)
    remat = sum(1 for j in ids if later[j] >= 0 and hmr_op[later[j]] > recs[c[-1]][0])
    dense = sum(1 for j in ids if pcn[j] >= 64)
    T = sum(meanw.get(recs[i][0], 1.0) for i in c)
    nm = names[np.searchsorted(cuts, recs[c[0]][0], side='right') - 1]
    rows.append((nm, len(c), round(T), len(ids), dict(stg), dense, remat))
for r in rows[:70]: print(r)
print('=== grouped')
g = collections.Counter(); gT = collections.Counter()
for (nm, n, T, nd, stg, dense, remat) in rows:
    k = (nm, n, nd, tuple(sorted(stg.items())), remat > 0)
    g[k] += 1; gT[k] += T
for k, v in sorted(g.items(), key=lambda kv: -gT[kv[0]]): print(k, 'clusters', v, 'mean T total', gT[k])
