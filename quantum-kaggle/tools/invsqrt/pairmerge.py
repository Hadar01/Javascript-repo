"""Reachable-state pairwise AND merge search (Agent A).

For each group of CCX gates XOR-ing into one target (groups.py), and each pair of its products
p_i = a_i b_i, p_j = a_j b_j (values at their own times), search linear forms l, m over
span{a_i, b_i, a_j, b_j, 1} with  p_i + p_j + l*m  in the GF(2) span of the wires live at the group's last op
(target excluded) -- on a sample of reachable states (all x <= 16384, random larger x, two coin seeds).
A hit means the two CCX can be replaced by one CCX(l, m) + CNOTs at the group end: -1 Toffoli.
usage: python pairmerge.py circuit.kmx out.json"""
import sys, json, itertools, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
from groups import find_groups
MAXX = 3133452; W = 22


def simulate_values(ops, xs, seed, want):
    """Return {op_index: (nq, nw) array of qubit values just before op} for op indices in `want`."""
    nq = 1 + max(int(a[1:]) for _, args, _ in ops for a in args if a.startswith('q'))
    n = len(xs); nw = (n + 63) // 64
    def pack(bits):
        b = np.zeros(nw * 64, dtype=np.uint8); b[:n] = bits
        return np.packbits(b, bitorder='little').view(np.uint64).copy()
    mask = pack(np.ones(n, dtype=np.uint8))
    S = np.zeros((nq, nw), np.uint64)
    for i in range(W): S[i] = pack(((xs >> np.uint64(i)) & np.uint64(1)).astype(np.uint8))
    zero = np.zeros(nw, np.uint64)
    class Bits(dict):
        def __missing__(self, k): return zero
    B = Bits(); stack = [mask]; rng = np.random.default_rng(seed)
    q = lambda a: int(a[1:])
    out = {}
    for k, (op, args, cond) in enumerate(ops):
        if k in want: out[k] = S.copy()
        act = stack[-1] if cond is None else stack[-1] & B[q(cond)]
        if op == 'PUSH_CONDITION': stack.append(act); continue
        if op == 'POP_CONDITION':
            if len(stack) > 1: stack.pop()
            continue
        if op == 'X': S[q(args[0])] ^= act
        elif op == 'CX': S[q(args[1])] ^= S[q(args[0])] & act
        elif op == 'SWAP':
            a, b = q(args[0]), q(args[1]); d = (S[a] ^ S[b]) & act; S[a] ^= d; S[b] ^= d
        elif op == 'CCX':
            a, b, t = map(q, args); S[t] ^= S[a] & S[b] & act
        elif op == 'CSWAP':
            c, a, b = map(q, args); d = (S[a] ^ S[b]) & act & S[c]; S[a] ^= d; S[b] ^= d
        elif op == 'HMR':
            t = q(args[0]); coin = rng.integers(0, 2**63, size=nw, dtype=np.uint64) ^ (rng.integers(0, 2, size=nw, dtype=np.uint64) << np.uint64(63))
            B[q(args[1])] = (B[q(args[1])] & ~act) | (coin & act); S[t] &= ~act
        elif op == 'R': S[q(args[0])] &= ~act
        elif op == 'BIT_INVERT': B[q(args[0])] = B[q(args[0])] ^ act
        elif op == 'BIT_STORE0': B[q(args[0])] = B[q(args[0])] & ~act
        elif op == 'BIT_STORE1': B[q(args[0])] = B[q(args[0])] | act
    return out, mask


class Basis:
    def __init__(self, vecs):
        self.piv = []          # (word, bit, vec)
        for v in vecs: self.add(v)
    def reduce(self, v):
        v = v.copy()
        for w, b, pv in self.piv:
            if (int(v[w]) >> b) & 1: v ^= pv
        return v
    def add(self, v):
        r = self.reduce(v)
        nz = np.flatnonzero(r)
        if len(nz) == 0: return False
        w = int(nz[0]); bit = (int(r[w]) & -int(r[w])).bit_length() - 1
        # keep reduced: eliminate this pivot from previous vectors
        new = []
        for w2, b2, pv in self.piv:
            if (int(pv[w]) >> bit) & 1: pv = pv ^ r
            new.append((w2, b2, pv))
        self.piv = new + [(w, bit, r)]
        return True
    def contains(self, v):
        return not self.reduce(v).any()


def main(path, out):
    ops = load(path)
    G = find_groups(ops)
    rng = np.random.default_rng(11)
    ns = 16384
    xs = np.sort(np.concatenate([np.arange(1, ns + 1, dtype=np.uint64),
                                 rng.choice(np.arange(ns + 1, MAXX + 1, dtype=np.uint64), ns, replace=False)]))
    want = set()
    for t, g in G: want.update(g)
    V0, mask = simulate_values(ops, xs, 1, want)
    V1, _ = simulate_values(ops, xs, 2, want)
    q = lambda a: int(a[1:])
    hits = []; tried = 0; stats = {'nospan': 0, 'tested': 0}
    for t, g in G:
        tq = q(t)
        end = g[-1]
        nq = V0[end].shape[0]
        def vals(k, wire):
            return np.concatenate([V0[k][wire], V1[k][wire]])
        one = np.concatenate([mask, mask])
        spans = {}
        def span_at(k):
            if k not in spans:
                live = [i for i in range(nq) if i != tq and (V0[k][i].any() or V1[k][i].any())]
                spans[k] = Basis([vals(k, i) for i in live] + [one])
            return spans[k]
        ccx = [k for k in g if ops[k][0] == 'CCX']
        for i, j in itertools.combinations(ccx, 2):
            tried += 1
            fa, fb = vals(i, q(ops[i][1][0])), vals(i, q(ops[i][1][1]))
            ga, gb = vals(j, q(ops[j][1][0])), vals(j, q(ops[j][1][1]))
            target = (fa & fb) ^ (ga & gb)
            U = [fa, fb, ga, gb, one]
            span = None
            for pos in (j, i):
                sp = span_at(pos)
                if all(sp.contains(u) for u in U[:4]): span = sp; place = pos; break
            if span is None:
                stats['nospan'] += 1
                continue
            stats['tested'] += 1
            found = None
            combos = [c for c in itertools.product([0, 1], repeat=5) if any(c)]
            lin = []
            for c in combos:
                v = np.zeros_like(one)
                for bit, u in zip(c, U):
                    if bit: v ^= u
                lin.append((c, v))
            for (c1, l1), (c2, l2) in itertools.combinations_with_replacement(lin, 2):
                if span.contains(target ^ (l1 & l2)):
                    found = (c1, c2); break
            if found:
                hits.append(dict(target=t, ops=[i, j], place=place, group=g, l=found[0], m=found[1],
                                 a=ops[i][1][:2], b=ops[j][1][:2]))
                print('HIT', t, i, j, ops[i], ops[j], found, flush=True)
    json.dump(hits, open(out, 'w'), indent=0)
    print('groups', len(G), 'pairs tried', tried, stats, 'hits', len(hits))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
