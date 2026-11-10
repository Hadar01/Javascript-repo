"""Reachable-state 3-to-2 product merge search over CCX groups (Agent A).
For each triple of products XOR-ed into one target, with U = span{6 factor functions, 1} (all factors must be
in the live span at the placement op), map every sampled reachable state to its coordinate vector in U,
and search  Q = l1 m1 + l2 m2 + affine  on the reachable coordinate patterns (exhaustive).
usage: python triplemerge.py circuit.kmx out.json"""
import sys, json, itertools, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
from groups import find_groups
from pairmerge import simulate_values, Basis, MAXX

def unpack(v): return np.unpackbits(v.view(np.uint8), bitorder='little')

def main(path, out):
    ops = load(path); G = find_groups(ops)
    rng = np.random.default_rng(11); ns = 16384
    xs = np.sort(np.concatenate([np.arange(1, ns + 1, dtype=np.uint64),
                                 rng.choice(np.arange(ns + 1, MAXX + 1, dtype=np.uint64), ns, replace=False)]))
    want = set()
    for t, g in G: want.update(g)
    V0, mask = simulate_values(ops, xs, 1, want); V1, _ = simulate_values(ops, xs, 2, want)
    q = lambda a: int(a[1:])
    one = np.concatenate([mask, mask]); npts = len(xs) * 2
    hits = []; tried = 0; nospan = 0
    for t, g in G:
        tq = q(t); nq = V0[g[0]].shape[0]
        vals = lambda k, w: np.concatenate([V0[k][w], V1[k][w]])
        spans = {}
        def span_at(k):
            if k not in spans:
                live = [i for i in range(nq) if i != tq and (V0[k][i].any() or V1[k][i].any())]
                spans[k] = Basis([vals(k, i) for i in live] + [one])
            return spans[k]
        ccx = [k for k in g if ops[k][0] == 'CCX']
        for tri in itertools.combinations(ccx, 3):
            tried += 1
            F = []
            for k in tri: F += [vals(k, q(ops[k][1][0])), vals(k, q(ops[k][1][1]))]
            Q = np.zeros_like(one)
            for k in tri: Q ^= vals(k, q(ops[k][1][0])) & vals(k, q(ops[k][1][1]))
            place = None
            for pos in reversed(tri):
                if all(span_at(pos).contains(f) for f in F): place = pos; break
            if place is None: nospan += 1; continue
            # coordinates: bits of the 6 factor functions per point -> pattern id
            bits = np.stack([unpack(f)[:npts] for f in F])            # 6 x npts
            pid = (bits * (1 << np.arange(6))[:, None]).sum(0)
            qv = unpack(Q)[:npts]
            pats, inv = np.unique(pid, return_inverse=True)
            qpat = np.zeros(len(pats), np.uint8); qpat[inv] = qv
            P = len(pats)
            # functions on patterns as int bitmasks
            def fmask(lin, const):     # lin: 6-bit mask over factors
                v = 0
                for pi, pt in enumerate(pats):
                    if (bin(int(pt) & lin).count('1') + const) & 1: v |= 1 << pi
                return v
            L = {}
            for lin in range(64):
                for c in (0, 1):
                    L[(lin, c)] = fmask(lin, c)
            lvals = list(set(L.values()))
            aff = set(lvals)
            prods = set()
            for a_, b_ in itertools.combinations_with_replacement(lvals, 2): prods.add(a_ & b_)
            prods = list(prods)
            Qm = 0
            for pi in range(P):
                if qpat[pi]: Qm |= 1 << pi
            one_prod_aff = set()
            found = False
            pset = set(prods)
            if tried <= 6 or tried % 40 == 0: print('dbg', t, tri, 'patterns', P, 'linear funcs', len(lvals), 'products', len(prods), flush=True)
            for p1 in prods:
                r = Qm ^ p1
                for a_ in aff:
                    if (r ^ a_) in pset:
                        found = True; break
                if found: break
            if found:
                hits.append(dict(target=t, ops=list(tri), place=place))
                print('HIT', t, tri, flush=True)
    json.dump(hits, open(out, 'w'), indent=0)
    print('groups', len(G), 'triples tried', tried, 'nospan', nospan, 'hits', len(hits))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
