"""GF(2) linear algebra on packed uint8 rows (numpy)."""
import numpy as np
def solve_affine(Vs, Ws):
    """Vs: (nv x shots) 0/1 source states; Ws: (nw x shots) targets. Find A (nw x nv), c (nw) with W = A V + c over all shots.
    Returns A, c, rank, residual-ok flag."""
    nv, ns = Vs.shape
    X = np.concatenate([Vs, np.ones((1, ns), np.uint8)], 0).T.copy()      # shots x (nv+1)
    Y = Ws.T.copy()                                                         # shots x nw
    M = np.concatenate([X, Y], 1).astype(np.uint8)
    rows, cols = M.shape; r = 0; piv = []
    for c in range(nv + 1):
        p = np.flatnonzero(M[r:, c])
        if len(p) == 0: continue
        p = p[0] + r
        if p != r: M[[r, p]] = M[[p, r]]
        mask = M[:, c].astype(bool); mask[r] = False
        M[mask] ^= M[r]
        piv.append(c); r += 1
        if r == rows: break
    ok = not M[r:, nv + 1:].any()     # remaining rows must have zero targets (consistency)
    coef = np.zeros((nv + 1, Ws.shape[0]), np.uint8)
    for i, c in enumerate(piv): coef[c] = M[i, nv + 1:]
    A = coef[:nv].T.copy(); cvec = coef[nv].copy()
    return A, cvec, r, ok
def rank(M):
    M = M.copy() % 2; r = 0
    for c in range(M.shape[1]):
        p = np.flatnonzero(M[r:, c])
        if len(p) == 0: continue
        p = p[0] + r
        if p != r: M[[r, p]] = M[[p, r]]
        mask = M[:, c].astype(bool); mask[r] = False
        M[mask] ^= M[r]; r += 1
        if r == M.shape[0]: break
    return r
def cnot_synthesis(M):
    """In-place circuit for state -> M state (M invertible n x n over GF(2)).
    Eliminate M to I with row ops; returns gate list in application order."""
    M = (M.copy() % 2).astype(np.uint8); n = M.shape[0]; ops = []
    for c in range(n):
        if not M[c, c]:
            p = np.flatnonzero(M[c + 1:, c])
            assert len(p), 'singular'
            p = int(p[0]) + c + 1
            M[c] ^= M[p]; ops.append(('add', c, p))          # row c += row p
        for r in np.flatnonzero(M[:, c]):
            if r != c: M[r] ^= M[c]; ops.append(('add', int(r), c))
    assert (M == np.eye(n, dtype=np.uint8)).all()
    # op_K...op_1 M = I  =>  M = op_1...op_K ; state' = M s : apply op_K first ... op_1 last
    gates = [('CX', s, r) for (_, r, s) in reversed(ops)]   # row r += row s  ==  CX control s target r
    return gates
