"""Continuous DF-THC fit of error_2 (+ kappa * D(w)) with L-BFGS, numpy/scipy only (Agent C).

error_2^2 = ||sum_k x_k x_k^T - M||_F^2,  M = tei + (S(x)I + I(x)S)/2 as an N^2 x N^2 matrix,
x_k = vec(X_rc), X_rc = sum_b w_brc u_b u_b^T (u_b unit).  Gradients are analytic.

usage: python fit_dfthc.py --data DIR(with oei/tei/ecore npy + fixed_shifts) --seed seed.npz --out out.npz
       [--iters 2000] [--kappa 5e-5]
seed.npz holds U (R,B,N) and W (R,B,C) (lowercase w).
"""
import argparse, time, numpy as np
from scipy.optimize import minimize

N = 76


def load_target(tei_path, shifts_path):
    tei = np.load(tei_path).astype(np.float64)
    fs = np.load(shifts_path, allow_pickle=False)
    r, c = np.tril_indices(N)
    m = np.zeros((N, N), np.float32); m[r, c] = fs['Hsym_lower'].astype(np.float32)
    S = (m + m.T - np.diag(np.diag(m))).astype(np.float64)
    d = np.arange(N)
    tei[:, :, d, d] += 0.5 * S[:, :, None]
    tei[d, d, :, :] += 0.5 * S[None, :, :]
    M = tei.reshape(N * N, N * N)
    M = 0.5 * (M + M.T)
    return M


class Fit:
    def __init__(self, M, R, B, C, kappa=0.0):
        self.M, self.R, self.B, self.C, self.kappa = M, R, B, C, kappa
        self.nM2 = float(np.sum(M * M))

    def unpack(self, z):
        R, B, C = self.R, self.B, self.C
        U = z[:R * B * N].reshape(R, B, N)
        w = z[R * B * N:].reshape(R, B, C)
        return U, w

    def fg(self, z):
        U, w = self.unpack(z)
        nrm = np.linalg.norm(U, axis=2, keepdims=True)
        u = U / nrm
        X = np.einsum('rbp,rbq,rbc->rcpq', u, u, w, optimize=True)  # (R,C,N,N)
        Xm = X.reshape(-1, N * N)
        G = Xm @ Xm.T
        MX = Xm @ self.M
        f = self.nM2 - 2 * np.sum(Xm * MX) + np.sum(G * G)
        gX = (-4 * MX + 4 * G @ Xm).reshape(self.R, self.C, N, N)
        # chain to w and u
        gu_all = np.einsum('rbc,rcpq,rbq->rbp', w, gX, u, optimize=True)  # sum_c w * G u
        gw = np.einsum('rbp,rcpq,rbq->rbc', u, gX, u, optimize=True)
        gu = 2 * gu_all
        # D(w) penalty: 1/2 sum_rc [(sum|w|)^2 - (sum w)^2]
        if self.kappa:
            a = np.abs(w).sum(1); s = w.sum(1)
            f = f + self.kappa * 0.5 * np.sum(a * a - s * s)
            gw = gw + self.kappa * (a[:, None, :] * np.sign(w) - s[:, None, :])
        # projection through normalization
        gU = (gu - np.sum(gu * u, axis=2, keepdims=True) * u) / nrm
        return f, np.concatenate([gU.ravel(), gw.ravel()])

    def err2(self, z):
        f, _ = self.fg(z)
        return np.sqrt(max(f, 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tei', required=True); ap.add_argument('--shifts', required=True)
    ap.add_argument('--seed', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--iters', type=int, default=2000); ap.add_argument('--kappa', type=float, default=0.0)
    ap.add_argument('--chunk', type=int, default=100)
    a = ap.parse_args()
    M = load_target(a.tei, a.shifts)
    s = np.load(a.seed)
    U0, w0 = s['U'].astype(np.float64), s['W'].astype(np.float64)
    R, B, C = w0.shape
    fit = Fit(M, R, B, C, a.kappa)
    z = np.concatenate([U0.ravel(), w0.ravel()])
    t0 = time.time()
    f0, _ = fit.fg(z)
    print(f'start shape {R,B,C} obj^0.5 {1e3*np.sqrt(f0):.3f} mHa', flush=True)
    done = 0
    while done < a.iters:
        res = minimize(fit.fg, z, jac=True, method='L-BFGS-B',
                       options=dict(maxiter=a.chunk, maxcor=30, gtol=1e-12, ftol=1e-16))
        z = res.x; done += a.chunk
        kap = a.kappa
        a_ = np.abs(fit.unpack(z)[1]).sum(1); s_ = fit.unpack(z)[1].sum(1)
        D = 0.5 * np.sum(a_ ** 2 - s_ ** 2)
        e = np.sqrt(max(res.fun - kap * D, 0))
        print(f'it {done} err2 {1e3*e:.3f} mHa D {D:.3f} t {time.time()-t0:.0f}s', flush=True)
        U, w = fit.unpack(z)
        np.savez(a.out, U=U / np.linalg.norm(U, axis=2, keepdims=True), W=w)
        if res.status == 0 and res.nit < a.chunk:
            print('converged'); break


if __name__ == '__main__':
    main()
