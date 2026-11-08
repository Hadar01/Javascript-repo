"""Classify qubits at checkpoints from decode.py output (Agent A).
usage: python classify.py dec.npz [step]
codes: . zero, 1 one, n/N normalised-x bit (N = negated), o/O original-x bit, z flag bit (lz bit),
       L GF(2)-linear in (x_n bits, lz bits, 1),
       T function of the 8-bit address (e, a) only,  0-9/a-e  function of address + top k bits of d (k in hex),
       D function of (address, d) (i.e. of x_n and e), X depends on the shift as well.
"""
import sys, numpy as np

d = np.load(sys.argv[1]); xs = d['xs'].astype(np.int64); ks = d['ks']; V = d['vals']
step = int(sys.argv[2]) if len(sys.argv) > 2 else 4
n = len(xs)
lz = 21 - np.floor(np.log2(xs)).astype(np.int64)
xn = xs << lz
e = lz & 1
a7 = (xn >> 14) & 127
addr = a7 + 128 * e
dd = xn & (2**14 - 1)
feats = {}
for j in range(22): feats[('n', j)] = ((xn >> j) & 1).astype(np.uint8)
for j in range(22): feats[('o', j)] = ((xs >> j) & 1).astype(np.uint8)
for j in range(5): feats[('z', j)] = ((lz >> j) & 1).astype(np.uint8)
lin_basis = [feats[('n', j)] for j in range(22)] + [feats[('z', j)] for j in range(5)] + [np.ones(n, np.uint8)]


def is_function_of(v, key):
    # v constant on each class of key?
    order = np.argsort(key, kind='stable'); k = key[order]; vv = v[order]
    brk = np.r_[True, k[1:] != k[:-1]]
    grp = np.cumsum(brk) - 1
    first = vv[brk][grp]
    return bool(np.all(first == vv))


def in_span(v, basis):
    # gaussian elimination on 64-bit packed columns over n samples (use first 2048 samples, then verify)
    m = 4096
    B = np.array([b[:m] for b in basis], dtype=np.uint8)
    M = np.concatenate([B, v[None, :m]], 0).T.copy()   # m x (nb+1)
    nb = len(basis)
    r = 0; piv = []
    for c in range(nb):
        rows = np.flatnonzero(M[r:, c]) + r
        if len(rows) == 0: continue
        p = rows[0]; M[[r, p]] = M[[p, r]]
        others = np.flatnonzero(M[:, c]); others = others[others != r]
        M[others] ^= M[r]
        piv.append(c); r += 1
        if r == m: break
    if np.any(M[r:, nb]): return None
    coef = np.zeros(nb, np.uint8)
    for i, c in enumerate(piv): coef[c] = M[i, nb]
    full = np.zeros(n, np.uint8)
    for c in np.flatnonzero(coef): full ^= basis[c]
    return coef if np.array_equal(full, v) else None


def code(v):
    if not v.any(): return '.'
    if v.all(): return '1'
    for (t, j), f in feats.items():
        if np.array_equal(v, f): return t
        if np.array_equal(v, 1 - f): return t.upper()
    if in_span(v, lin_basis) is not None: return 'L'
    if is_function_of(v, addr): return 'T'
    for kk in range(1, 15):
        if is_function_of(v, addr * 2**kk + (dd >> (14 - kk))): return '0123456789abcdef'[kk] if kk < 16 else '+'
    if is_function_of(v, addr * 2**14 + dd): return 'D'
    return 'X'


if __name__ == '__main__':
    nq = V.shape[1]
    print('      op  ' + ''.join(str(i // 10) for i in range(nq)))
    print('          ' + ''.join(str(i % 10) for i in range(nq)))
    for ci in range(0, len(ks), step):
        row = ''.join(code(V[ci, q]) for q in range(nq))
        print('%8d  %s' % (ks[ci], row))
