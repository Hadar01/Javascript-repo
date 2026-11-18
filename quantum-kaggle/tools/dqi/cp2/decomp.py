"""Forward/reverse Toffoli decomposition per stage pair (sample-based product functions on two input sets).
For each Toffoli: kind (CCX/CCZ), classically conditioned or not (mean weight = executed fraction), product hash(es).
'mirror' = a reverse Toffoli whose (a&b) product function also occurs among the forward stage's products
(on both input sets); 'new' = not. Forward 'fwd-only' = forward products never recomputed in the reverse stage."""
import sys, json, numpy as np, collections, bisect
cuts = json.load(open(sys.argv[1]))[sys.argv[2]]; pres = sys.argv[3:]
names = ['pre','ext','syn','conv','scan',"conv'","syn'","ext'",'post']
R = [np.fromfile(p, dtype=np.uint64).reshape(-1, 5) for p in pres]
op = (R[0][:, 0] & np.uint64((1 << 40) - 1)).astype(np.int64); cpc = (R[0][:, 0] >> np.uint64(40)).astype(np.int64)
kind = ((R[0][:, 1] >> np.uint64(32)) & np.uint64(0xff)).astype(int); cond = (R[0][:, 1] & np.uint64(1)).astype(bool)
st = np.array([bisect.bisect_right(cuts, int(o)) - 1 for o in op])
key = [tuple(int(x[i, 2]) for x in R) for i in range(len(op))]     # (a&b) hash on each set
ccz = [tuple(int(x[i, k]) for x in R for k in (2, 3, 4)) for i in range(len(op))]
w = cpc / 4096.0
for f, r in [(1, 7), (2, 6), (3, 5)]:
    F = np.flatnonzero(st == f); Rr = np.flatnonzero(st == r)
    fk = collections.Counter(key[i] for i in F if kind[i] == 1 and key[i][0])
    rk = collections.Counter(key[i] for i in Rr if kind[i] == 1 and key[i][0])
    def summ(idx, other):
        out = collections.Counter()
        for i in idx:
            k = 'CCZ' if kind[i] == 0 else ('CCX-cond' if cond[i] else 'CCX')
            if kind[i] == 1:
                k += '-mirror' if key[i] in other else '-new'
                if key[i][0] == 0: k = k.replace('mirror', 'zero').replace('new', 'zero')
            out[k + '|static'] += 1; out[k + '|mean'] += w[i]
        return out
    sf = summ(F, rk); sr = summ(Rr, fk)
    print(f'== {names[f]} -> {names[r]}')
    ks = sorted(set(k.split('|')[0] for k in list(sf) + list(sr)))
    for k in ks:
        print(f"  {k:18s} fwd static {sf[k+'|static']:7d} mean {sf[k+'|mean']:9.1f} | rev static {sr[k+'|static']:7d} mean {sr[k+'|mean']:9.1f} | diff mean {sr[k+'|mean']-sf[k+'|mean']:+9.1f}")
