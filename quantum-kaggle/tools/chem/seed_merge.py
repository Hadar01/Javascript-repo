"""Seed a (R/2, B, 2C) table from an (R, B, C) table by merging group pairs and keeping B of 2B vectors.

For each merged pair the 2B candidate vectors are chosen greedily (OMP-like) to best reconstruct the
2C leaves X_rc of the pair in Frobenius norm; weights are least-squares per leaf on the chosen set.
usage: python seed_merge.py in.npz out.npz
"""
import sys, numpy as np

N = 76


def leaves(U, w):
    u = U / np.linalg.norm(U, axis=2, keepdims=True)
    return np.einsum('rbp,rbq,rbc->rcpq', u, u, w)


def lsq_weights(V, Xs):
    # V (k,N) unit vectors, Xs (L,N,N) -> w (k,L) minimizing ||X - sum w v v^T||
    P = np.einsum('kp,kq->kpq', V, V).reshape(len(V), -1)
    w, *_ = np.linalg.lstsq(P.T, Xs.reshape(len(Xs), -1).T, rcond=None)
    return w


def choose(V, Xs, B):
    P = np.einsum('kp,kq->kpq', V, V).reshape(len(V), -1)
    T = Xs.reshape(len(Xs), -1)
    Gram = P @ P.T            # (K,K)
    cross = P @ T.T           # (K,L)
    sel = []
    # backward elimination is costly; use forward greedy on residual energy with LS refits
    remaining = list(range(len(V)))
    for _ in range(B):
        best, bestval = None, -1
        if sel:
            Gs = Gram[np.ix_(sel, sel)]; cs = cross[sel]
            ws = np.linalg.solve(Gs + 1e-12 * np.eye(len(sel)), cs)
            resid_corr = cross - Gram[:, sel] @ ws    # (K,L)
        else:
            resid_corr = cross
        score = np.sum(resid_corr ** 2, axis=1) / np.maximum(np.diag(Gram), 1e-12)
        score[sel] = -1
        best = int(np.argmax(score)); sel.append(best)
    return sel


def main():
    z = np.load(sys.argv[1]); U = z['U'].astype(np.float64); w = z['W'].astype(np.float64)
    R, B, C = w.shape
    u = U / np.linalg.norm(U, axis=2, keepdims=True)
    X = leaves(U, w)
    # orbital profiles for pairing
    prof = np.einsum('rbp,rbc->rp', u ** 2, w ** 2); prof /= prof.sum(1, keepdims=True)
    ov = prof @ prof.T
    left = list(range(R)); pairs = []
    while left:
        r = left.pop(0)
        q = max(left, key=lambda q: ov[r, q]); left.remove(q); pairs.append((r, q))
    print('pairs', pairs)
    Un = np.zeros((R // 2, B, N)); wn = np.zeros((R // 2, B, 2 * C))
    for i, (r, q) in enumerate(pairs):
        V = np.concatenate([u[r], u[q]])
        Xs = np.concatenate([X[r], X[q]])
        sel = choose(V, Xs, B)
        Un[i] = V[sel]
        wn[i] = lsq_weights(V[sel], Xs)
        res = np.linalg.norm(Xs - np.einsum('kp,kq,kl->lpq', V[sel], V[sel], wn[i]))
        print(f'pair {r},{q}: leaf residual {res:.4f} of {np.linalg.norm(Xs):.4f}', flush=True)
    np.savez(sys.argv[2], U=Un, W=wn)


if __name__ == '__main__':
    main()
