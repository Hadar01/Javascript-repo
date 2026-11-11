"""For each 892-excursion window: (a) affine-redundant idle qubit (0 T), else (b) idle live qubit equal to AND of two
idle literals (x or NOT x) of other idle live qubits (recompute 1 T, MBUC uncompute 0 T). Report counts per stage."""
import sys, numpy as np, json, collections
exec(open('freeable.py').read().split("stats = collections.defaultdict")[0])
def affine_redundant(Xb):
    M = np.concatenate([Xb, np.ones((1, Xb.shape[1]), np.uint8)], 0)
    return len(Xb) + 1 - gf2_rank_rows(M)
stats = collections.defaultdict(collections.Counter)
for S, E, mp in wins:
    st = names[seg[S]].split('/')[0]
    raw = np.fromfile(f'pkstates/c1_state_{S}.bin', dtype=np.uint64).reshape(892, -1)
    live = [i for i, ch in enumerate(mp) if ch == '1']
    idle = [i for i in live if not touched(i, S, E)]
    X = raw[idle]                                  # idle x words (packed shots)
    stats[st]['windows'] += 1
    Xb = np.unpackbits(X.view(np.uint8), axis=1, bitorder='little')
    if affine_redundant(Xb) > 0: stats[st]['free_affine'] += 1; continue
    found = False
    lits = np.concatenate([X, ~X], 0)             # literals
    for t in range(len(idle)):
        tq = X[t]
        if not tq.any(): continue
        sup = np.flatnonzero(np.all((lits & tq) == tq, axis=1))     # literals covering q's ones
        sup = [s for s in sup if s % len(idle) != t]
        if len(sup) < 2: continue
        L = lits[sup]
        for i in range(len(sup)):
            prod = L[i] & L[i+1:]
            if np.any(np.all(prod == tq, axis=1)): found = True; break
        if found: break
    stats[st]['and_of_two_literals' if found else 'none'] += 1
for st, c in stats.items(): print(st, dict(c))
