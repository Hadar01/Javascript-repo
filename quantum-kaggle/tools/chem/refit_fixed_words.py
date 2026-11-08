"""Refit the weights (w, W) of a dfthcsos submission at fixed angle words (circuits unchanged).

Minimizes lambda_eff^2 = E_gap (2 Lambda - E_gap) subject to
    error_1 <= t1, error_2 <= t2, E_gap >= floor + gap_margin
with an augmented Lagrangian (L-BFGS inner solves, exact analytic gradients) followed by a Newton
feasibility repair on the active constraints.  All metrics follow dfthcsos/scoreinfra/dfthc_math.py:
error_2 uses the K/Q expansion at fixed unit vectors (exact), error_1 uses the verifier's
linear_sum_assignment matching of the submitted one-body rows to eigenvectors of h1'.
Own implementation (Agent C); idea of refitting weights at fixed words: phucthaiv02 / heliosli /
marculera / maoxin123 / ahmedberatozer (public, Apache-2.0 notebooks).

usage: python refit_fixed_words.py --sub DIR/submission.npz --data WORKDIR(oei.npy,tei.npy,ecore.npy)
          --shifts fixed_shifts.npz --out new_submission.npz [--margin 2e-6]
"""
import argparse, time
import numpy as np
from scipy.optimize import minimize, linear_sum_assignment

N, ETA, EUP, GAP_FLOOR = 76, 113, -22140.27335, 3.914898


def sym_lower(lower):
    m = np.zeros((N, N), np.float32); r, c = np.tril_indices(N)
    m[r, c] = lower.astype(np.float32)
    return m + m.T - np.diag(np.diag(m))


def decode(words, edges, brot):
    ang = words / (1 << (brot - 1)); V = np.zeros((len(words), N)); V[:, 0] = 1
    for t, (p, c) in enumerate(edges):
        a = V[:, p].copy(); b = V[:, c].copy(); th = np.pi * ang[:, t]
        V[:, p] = np.cos(th) * a - np.sin(th) * b; V[:, c] = np.sin(th) * a + np.cos(th) * b
    return V


class Problem:
    def __init__(self, sub, datadir, shifts, brot=8):
        z = np.load(sub, allow_pickle=False)
        self.arrays = {k: np.array(z[k]) for k in z.files}
        w = z['W'].astype(np.float64); self.R, self.B, self.C = R, B, C = w.shape
        self.w0 = w; self.W0 = z['H2_I'].astype(np.float64) - w.sum(1)
        V = decode(z['angle_words'], z['tree_edges'], brot)
        V /= np.linalg.norm(V, axis=1, keepdims=True)
        self.v1 = V[:N]; self.u = V[N:].reshape(R, B, N)
        fs = np.load(shifts, allow_pickle=False)
        S = sym_lower(fs['Hsym_lower']).astype(np.float64)
        beta1 = float(fs['H1_I']) - 0.5 * float(np.trace(S))
        oei = np.load(f'{datadir}/oei.npy'); tei = np.load(f'{datadir}/tei.npy').astype(np.float64)
        ecore = float(np.load(f'{datadir}/ecore.npy'))
        h1thc = oei - 0.5 * np.einsum('prrq->pq', tei)
        self.h0 = h1thc - 0.5 * ETA * S + beta1 * np.eye(N)
        self.c0 = EUP - ecore + ETA * beta1                    # E_gap = c0 + (sum|ev|-sum ev) + 0.5 sum W^2
        T = tei; d = np.arange(N)
        T[:, :, d, d] += 0.5 * S[:, :, None]; T[d, d, :, :] += 0.5 * S[None, :, :]
        T = T.reshape(N * N, N * N); T = 0.5 * (T + T.T)
        flat = self.u.reshape(R * B, N)
        self.K = ((flat @ flat.T) ** 2).reshape(R, B, R, B).transpose(0, 2, 1, 3)  # (R,R,B,B)
        P = np.einsum('mp,mq->mpq', flat, flat).reshape(R * B, N * N)
        TP = T @ P.T
        self.Q = np.stack([P[r * B:(r + 1) * B] @ TP[:, r * B:(r + 1) * B] for r in range(R)])
        self.Q = 0.5 * (self.Q + self.Q.swapaxes(1, 2))
        self.T2 = float(np.sum(T * T))
        self.Pu = np.einsum('rbp,rbq->rbpq', self.u, self.u)

    def pack(self, w, W):
        return np.concatenate([w.ravel(), W.ravel()])

    def unpack(self, z):
        n = self.R * self.B * self.C
        return z[:n].reshape(self.R, self.B, self.C), z[n:].reshape(self.R, self.C)

    def evaluate(self, z, grad=True):
        w, W = self.unpack(z); R, B, C = self.R, self.B, self.C
        # error_2
        A = np.einsum('rbc,rsbe,sed->rscd', w, self.K, w, optimize=True)
        F = np.sum(A * A)
        L = np.einsum('rbc,rbe,rec->', w, self.Q, w, optimize=True)
        e2sq = F - 2 * L + self.T2
        # h1'
        X = np.einsum('rbpq,rbc->rcpq', self.Pu, w, optimize=True)
        h = self.h0 - np.einsum('rc,rcpq->pq', W, X, optimize=True)
        ev, Qv = np.linalg.eigh(h)
        lam1 = np.sum(np.abs(ev))
        a = np.abs(w).sum(1); s = w.sum(1); wB = W + s
        Lam = lam1 + 0.25 * np.sum((a + np.abs(wB)) ** 2)
        E = self.c0 + (lam1 - ev.sum()) + 0.5 * np.sum(W ** 2)
        J = E * (2 * Lam - E)
        # error_1 (verifier matching)
        ov = np.abs(self.v1 @ Qv)
        ri, ci = linear_sum_assignment(-ov)
        lm = np.empty(N); lm[ri] = ev[ci]
        Rm = np.einsum('j,jp,jq->pq', lm, self.v1, self.v1) - h
        e1sq = np.sum(Rm * Rm)
        out = dict(J=J, lam=np.sqrt(J) if J > 0 else np.nan, Lam=Lam, E=E, e1=np.sqrt(e1sq), e2=np.sqrt(max(e2sq, 0)),
                   e1sq=e1sq, e2sq=e2sq)
        if not grad:
            return out
        sg = np.sign(ev)
        Gs = (Qv * sg) @ Qv.T
        HJ = (2 * Lam - 2 * E) * (Gs - np.eye(N)) + 2 * E * Gs      # dJ/dh
        HE = Gs - np.eye(N)                                          # dE/dh
        # de1sq/dh: R = sum lm v v^T - h, lm_j = ev[ci_j]; d ev_i/dh = q_i q_i^T
        coef = np.einsum('pq,jp,jq->j', Rm, self.v1, self.v1)       # <R, v_j v_j^T>
        qm = Qv[:, ci]                                               # eigvec matched to row ri
        H1 = 2 * (qm * coef[ri]) @ qm.T - 2 * Rm

        def chain(H):  # gradient wrt (w, W) of a function whose dh-gradient is H
            uHu = np.einsum('rbp,pq,rbq->rb', self.u, H, self.u)
            gw = -uHu[:, :, None] * W[:, None, :]
            gW = -np.einsum('rcpq,pq->rc', X, H)
            return gw, gW
        gwJ, gWJ = chain(HJ)
        fac = 0.5 * (a + np.abs(wB))
        dLam_w = fac[:, None, :] * (np.sign(w) + np.sign(wB)[:, None, :])
        dLam_W = fac * np.sign(wB)
        gwJ += 2 * E * dLam_w
        gWJ += 2 * E * dLam_W + (2 * Lam - 2 * E) * W
        gwE, gWE = chain(HE); gWE = gWE + W
        gw1, gW1 = chain(H1)
        dF = 4 * np.einsum('rsbe,sed,rscd->rbc', self.K, w, A, optimize=True)
        dL = 2 * np.einsum('rbe,rec->rbc', self.Q, w, optimize=True)
        gw2 = dF - 2 * dL
        out.update(gJ=self.pack(gwJ, gWJ), gE=self.pack(gwE, gWE), g1=self.pack(gw1, gW1),
                   g2=self.pack(gw2, np.zeros_like(W)))
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sub', required=True); ap.add_argument('--data', required=True)
    ap.add_argument('--shifts', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--margin', type=float, default=2e-6)
    ap.add_argument('--rounds', type=int, default=8); ap.add_argument('--inner', type=int, default=300)
    ap.add_argument('--brot', type=int, default=8)
    a = ap.parse_args()
    t0 = time.time()
    P = Problem(a.sub, a.data, a.shifts, a.brot)
    t1 = t2 = 0.020 - a.margin; g0 = GAP_FLOOR + a.margin
    z = P.pack(P.w0, P.W0)
    o = P.evaluate(z, grad=False)
    print(f"setup {time.time()-t0:.0f}s start lam {o['lam']:.9f} e1 {1e3*o['e1']:.7f} e2 {1e3*o['e2']:.7f} E {o['E']:.9f}", flush=True)
    J0 = o['J']
    cons = lambda o: np.array([o['e1sq'] - t1 ** 2, o['e2sq'] - t2 ** 2, g0 - o['E']])
    scale = np.array([1 / t1 ** 2, 1 / t2 ** 2, 1.0])
    y = np.zeros(3); mu = 1e4

    def fun(zz):
        o = P.evaluate(zz)
        c = cons(o) * scale
        gc = [o['g1'] * scale[0], o['g2'] * scale[1], -o['gE'] * scale[2]]
        f = o['J'] / J0; g = o['gJ'] / J0
        for i in range(3):
            v = y[i] + mu * c[i]
            if v > 0:
                f += (v * v - y[i] ** 2) / (2 * mu); g = g + v * gc[i]
            else:
                f -= y[i] ** 2 / (2 * mu)
        return f, g

    best = None
    for rnd in range(a.rounds):
        res = minimize(fun, z, jac=True, method='L-BFGS-B', options=dict(maxiter=a.inner, maxcor=30))
        z = res.x; o = P.evaluate(z, grad=False); c = cons(o) * scale
        y = np.maximum(0, y + mu * c); mu = min(mu * 3, 1e9)
        print(f"round {rnd} lam {o['lam']:.9f} e1 {1e3*o['e1']:.7f} e2 {1e3*o['e2']:.7f} E {o['E']:.9f} y {y}", flush=True)
    # feasibility repair: Newton on violated/active constraints (min-norm step)
    for it in range(50):
        o = P.evaluate(z); c = cons(o)
        act = [i for i in range(3) if c[i] > -1e-12 * (t1 ** 2 if i < 2 else 1)]
        viol = [i for i in range(3) if c[i] > 0]
        if not viol:
            break
        Gm = np.stack([o['g1'], o['g2'], -o['gE']])[viol]
        target = c[viol] + np.array([1e-9 if i < 2 else 1e-9 for i in viol])
        step = Gm.T @ np.linalg.solve(Gm @ Gm.T, target)
        z = z - step
    o = P.evaluate(z, grad=False)
    print(f"final lam {o['lam']:.9f} e1 {1e3*o['e1']:.7f} e2 {1e3*o['e2']:.7f} E {o['E']:.9f} feasible {np.all(cons(o) <= 0)}", flush=True)
    w, W = P.unpack(z)
    arr = dict(P.arrays)
    arr['W'] = w.astype(P.arrays['W'].dtype); arr['H2_I'] = (W + w.sum(1)).astype(P.arrays['H2_I'].dtype)
    np.savez(a.out, **arr)
    print('wrote', a.out)




# ---------------------------------------------------------------------------
# Active-face projected gradient (smooth face: zero pattern of w frozen), used by `face_main`.
# ---------------------------------------------------------------------------

def face_refine(P, z, t1, t2, g0, iters=300, log=print):
    mask = np.ones_like(z, dtype=bool)
    n = P.R * P.B * P.C
    mask[:n] = z[:n] != 0                       # keep exact zeros of w (sign faces of |w|)

    def cons(o):
        return np.array([o['e1sq'] - t1 ** 2, o['e2sq'] - t2 ** 2, g0 - o['E']])

    def cgrads(o):
        return np.stack([o['g1'], o['g2'], -o['gE']]) * mask

    def restore(z, max_it=30):
        for _ in range(max_it):
            o = P.evaluate(z); c = cons(o)
            if np.all(c <= 0):
                return z, o
            Gm = cgrads(o)
            # push all three to their targets slightly inside (Newton, min-norm)
            tgt = c + np.array([1e-12, 1e-12, 1e-12])
            act = np.array([i for i in range(3) if c[i] > -1e-9 * (t1 ** 2 if i < 2 else 1) or c[i] > 0])
            Ga = Gm[act]
            z = z - Ga.T @ np.linalg.solve(Ga @ Ga.T, tgt[act])
        o = P.evaluate(z)
        return (z, o) if np.all(cons(o) <= 0) else (None, o)

    z, o = restore(z)
    if z is None:
        raise RuntimeError('cannot restore feasibility')
    step = 1e-3
    for it in range(iters):
        g = o['gJ'] * mask
        Gm = cgrads(o)
        # project out the constraint normals (all three treated as active: they all sit at the bound)
        coef = np.linalg.solve(Gm @ Gm.T, Gm @ g)
        d = -(g - Gm.T @ coef)
        dn = np.linalg.norm(d)
        if dn == 0:
            break
        accepted = False
        while step > 1e-12:
            zn, on = restore(z + step * d / dn)
            if zn is not None and on['J'] < o['J']:
                # zero-crossing guard: keep sign faces of w and wB
                w0, W0 = P.unpack(z); w1, W1 = P.unpack(zn)
                if np.all(np.sign(w1) == np.sign(w0)) and np.all(np.sign(W1 + w1.sum(1)) == np.sign(W0 + w0.sum(1))):
                    z, o = zn, on; accepted = True; step *= 2; break
            step *= 0.3
        if not accepted:
            log(f'face it {it}: no descent, stop'); break
        if it % 10 == 0:
            log(f"face it {it} lam {o['lam']:.10f} e1 {1e3*o['e1']:.7f} e2 {1e3*o['e2']:.7f} E {o['E']:.10f} step {step:.2e}")
    return z, o


def face_main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sub', required=True); ap.add_argument('--data', required=True)
    ap.add_argument('--shifts', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--margin', type=float, default=1e-6); ap.add_argument('--iters', type=int, default=300)
    ap.add_argument('--brot', type=int, default=8)
    a = ap.parse_args()
    P = Problem(a.sub, a.data, a.shifts, a.brot)
    z = P.pack(P.w0, P.W0)
    o = P.evaluate(z, grad=False)
    print(f"start lam {o['lam']:.10f} e1 {1e3*o['e1']:.7f} e2 {1e3*o['e2']:.7f} E {o['E']:.10f}", flush=True)
    z, o = face_refine(P, z, 0.020 - a.margin, 0.020 - a.margin, GAP_FLOOR + a.margin, a.iters,
                       log=lambda s: print(s, flush=True))
    print(f"final lam {o['lam']:.10f} e1 {1e3*o['e1']:.7f} e2 {1e3*o['e2']:.7f} E {o['E']:.10f}", flush=True)
    w, W = P.unpack(z)
    arr = dict(P.arrays)
    arr['W'] = w.astype(P.arrays['W'].dtype); arr['H2_I'] = (W + w.sum(1)).astype(P.arrays['H2_I'].dtype)
    np.savez(a.out, **arr); print('wrote', a.out)


if __name__ == '__main__':
    import sys as _s
    if '--face' in _s.argv:
        _s.argv.remove('--face'); face_main()
    else:
        main()
