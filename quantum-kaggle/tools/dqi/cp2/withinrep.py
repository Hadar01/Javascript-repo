"""Repeated product functions WITHIN a stage (dense products, equal on two input sets): duplicated computations.
Reports per stage: number of repeated product instances, and clusters (pairs of op windows that share many products)."""
import sys, json, numpy as np, collections, bisect
cuts = json.load(open(sys.argv[1]))[sys.argv[2]]; p0, p1 = sys.argv[3], sys.argv[4]
names = ['pre','ext','syn','conv','scan',"conv'","syn'","ext'",'post']
R0 = np.fromfile(p0, dtype=np.uint64).reshape(-1, 5); R1 = np.fromfile(p1, dtype=np.uint64).reshape(-1, 5)
op = (R0[:, 0] & np.uint64((1 << 40) - 1)).astype(np.int64)
kind = ((R0[:, 1] >> np.uint64(32)) & np.uint64(0xff)).astype(int); cond = (R0[:, 1] & np.uint64(1)).astype(bool)
pc = (R0[:, 1] >> np.uint64(40)).astype(np.int64)
st = np.searchsorted(np.array(cuts), op, side='right') - 1
sel = (kind == 1) & ~cond & (pc >= 64)
key = list(zip(R0[:, 2].tolist(), R1[:, 2].tolist()))
for s in range(1, 8):
    idx = np.flatnonzero(sel & (st == s))
    occ = collections.defaultdict(list)
    for i in idx: occ[key[i]].append(int(op[i]))
    reps = {k: v for k, v in occ.items() if len(v) > 1}
    extra = sum(len(v) - 1 for v in reps.values())
    # cluster by coarse windows of 20000 ops: count shared products between window pairs
    pairs = collections.Counter()
    for v in reps.values():
        ws = sorted(set(x // 20000 for x in v))
        for a in range(len(ws)):
            for b in range(a + 1, len(ws)): pairs[(ws[a], ws[b])] += 1
    print(f"{names[s]:5s} dense uncond CCX {len(idx):6d} distinct {len(occ):6d} repeated-extra {extra:5d}; top window pairs (op/20000) {pairs.most_common(6)}")
