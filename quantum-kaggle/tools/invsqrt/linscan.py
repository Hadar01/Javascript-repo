"""Linear-equivalence scan of an invsqrt kmx circuit (Agent A).

For every depth-0, unconditioned Toffoli-like gate, test on a random sample of x whether its nonlinear
term (CCX: c1&c2, CSWAP: c&(a^b), CCZ: a&b&c) equals a GF(2)-linear function of the qubit values at that
point (plus constant).  If so the gate can be replaced by CNOTs / Z gates (0 Toffolis).  Candidates found on
the sample are then re-checked exactly on all x by `verify_candidates`.

usage: python linscan.py circuit.kmx out.json [nsample]
"""
import sys, json, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
MAXX = 3133452; W = 22


def gf2_express(rows, v):
    """rows: (k, nw) uint64 array of vectors; v: (nw,) vector.  Return list of row indices XORing to v, or None."""
    k = rows.shape[0]
    M = rows.copy(); tag = [1 << i for i in range(k)]
    vv = v.copy(); vt = 0
    piv = []
    r = 0
    nw = M.shape[1]
    # elimination by pivot bit (word, bit)
    for i in range(k):
        # find first nonzero bit of row i after previous eliminations
        row = M[i]
        nzw = np.flatnonzero(row)
        if len(nzw) == 0:
            continue
        w = int(nzw[0]); b = int(row[w]) & -int(row[w]); bit = (b).bit_length() - 1
        sel = (M[:, w] >> np.uint64(bit)) & np.uint64(1)
        for j in np.flatnonzero(sel):
            if j != i:
                M[j] ^= row; tag[j] ^= tag[i]
        if (int(vv[w]) >> bit) & 1:
            vv ^= row; vt ^= tag[i]
        piv.append((w, bit, i))
    if vv.any():
        return None
    return [i for i in range(k) if (vt >> i) & 1]


def scan(path, ns=16384, seed=3):
    ops = load(path)
    nq = 1 + max(int(a[1:]) for _, args, _ in ops for a in args if a.startswith('q'))
    rng = np.random.default_rng(seed)
    small = np.arange(1, ns + 1, dtype=np.uint64)          # all small x (large shifts: rare paths)
    big = rng.choice(np.arange(ns + 1, MAXX + 1, dtype=np.uint64), ns, replace=False)
    xs = np.sort(np.concatenate([small, big])); ns = len(xs)
    n = ns; nw = n // 64
    def pack(bits): return np.packbits(bits.astype(np.uint8), bitorder='little').view(np.uint64).copy()
    mask = pack(np.ones(n, dtype=np.uint8))
    S = [np.zeros(nw, np.uint64) for _ in range(nq)]
    for i in range(W): S[i] = pack((xs >> np.uint64(i)) & np.uint64(1))
    zero = np.zeros(nw, np.uint64)
    class Bits(dict):
        def __missing__(self, k): return zero
    B = Bits(); stack = [mask]; crng = np.random.default_rng(seed + 1)
    q = lambda a: int(a[1:])
    cands = []
    for k, (op, args, cond) in enumerate(ops):
        act = stack[-1] if cond is None else stack[-1] & B[q(cond)]
        if op == 'PUSH_CONDITION': stack.append(act); continue
        if op == 'POP_CONDITION':
            if len(stack) > 1: stack.pop()
            continue
        if op in ('CCX', 'CSWAP', 'CCZ') and len(stack) == 1 and cond is None:
            if op == 'CCX': t = S[q(args[0])] & S[q(args[1])]; excl = {q(args[2])}
            elif op == 'CSWAP': t = S[q(args[0])] & (S[q(args[1])] ^ S[q(args[2])]); excl = set()
            else: t = S[q(args[0])] & S[q(args[1])] & S[q(args[2])]; excl = set()
            cols = [i for i in range(nq) if i not in excl and S[i].any()]
            rows = np.stack([S[i] for i in cols] + [mask])
            sel = gf2_express(rows, t)
            if sel is not None:
                lin = [cols[i] if i < len(cols) else 'one' for i in sel]
                cands.append(dict(k=k, op=op, args=args, lin=lin))
        if op == 'X': S[q(args[0])] ^= act
        elif op == 'CX': S[q(args[1])] ^= S[q(args[0])] & act
        elif op == 'SWAP':
            a, b = q(args[0]), q(args[1]); d = (S[a] ^ S[b]) & act; S[a] ^= d; S[b] ^= d
        elif op == 'CCX':
            a, b, t_ = map(q, args); S[t_] ^= S[a] & S[b] & act
        elif op == 'CSWAP':
            c, a, b = map(q, args); d = (S[a] ^ S[b]) & act & S[c]; S[a] ^= d; S[b] ^= d
        elif op == 'HMR':
            t_ = q(args[0]); coin = crng.integers(0, 2**63, size=nw, dtype=np.uint64) ^ (crng.integers(0, 2, size=nw, dtype=np.uint64) << np.uint64(63))
            B[q(args[1])] = (B[q(args[1])] & ~act) | (coin & act); S[t_] &= ~act
        elif op == 'R': S[q(args[0])] &= ~act
        elif op == 'BIT_INVERT': B[q(args[0])] = B[q(args[0])] ^ act
        elif op == 'BIT_STORE0': B[q(args[0])] = B[q(args[0])] & ~act
        elif op == 'BIT_STORE1': B[q(args[0])] = B[q(args[0])] | act
    return cands


if __name__ == '__main__':
    c = scan(sys.argv[1], int(sys.argv[3]) if len(sys.argv) > 3 else 16384)
    json.dump(c, open(sys.argv[2], 'w'), indent=0)
    print('linear-equivalent Toffoli-like gates (sample):', len(c))
    for r in c: print(r)
