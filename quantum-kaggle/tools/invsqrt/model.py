"""Exact integer model + table fit for our invsqrt generator (Agent A).

Design (credit: normalized signed-digit quadratic Horner of Sumit Chongder's public generator and its
descendants by anazemcev, Rudra Bhaskar, Kirill Tymchishin, Alex Chilton; backward/exact fitting idea as in
Gu et al. arXiv:2610.22367). All code here is our own.

  z  = leading zeros of the 22-bit x (0..21);  x_n = x << z (bit 21 set);  e = z & 1;  a = z >> 1 (0..10)
  M  = x_n / 2^21 in [1, 2);  1/sqrt(x) = 2^(a-10) * y,  y = M^-1/2 * 2^-((1-e)/2) in (0.5, 1]
  segment s = (e, x_n[20:14]) (256 segments);  d_i = x_n[i] for i < DB (DB = 14)
  R = K1 - sum_{i in R2} (2 d_i - 1) rd(K2, sh2_i)
  Y = K0 - sum_{i < DB}  (2 d_i - 1) rd(R,  sh1_i)
  phase (turns) = (Y >> GY) * 2^(GY - FY) * 2^(a - 10)
rd(v, s) = floor(v / 2^s) + bit_{s-1}(v)   (a shifted add with a carry-in; exact in the circuit)
"""
import math
import numpy as np

W = 22
DB = 14
MAXX = 3 * (2**10 - 2)**2


class P:
    """Precision parameters."""
    def __init__(self, f2=10, f1=19, fy=28, gy=2, w2=9, drop2=(5,)):
        self.f2, self.f1, self.fy, self.gy, self.w2 = f2, f1, fy, gy, w2
        self.sh2 = [f2 + 22 - i - f1 for i in range(DB)]
        self.sh1 = [f1 + 22 - i - fy for i in range(DB)]
        self.drop2 = set(drop2)

    def r2rows(self):
        return [i for i in reversed(range(DB)) if i not in self.drop2 and self.sh2[i] < self.w2]

    def key(self):
        return (self.f2, self.f1, self.fy, self.gy, self.w2, tuple(sorted(self.drop2)))


def rd(v, s):
    if s < 0:
        return v << (-s)
    if s == 0:
        return v
    return (v >> s) + ((v >> (s - 1)) & 1)


def pipeline(p, K2, K1, d):
    """R and Q = sum sig*rd(R) for local coordinates d (int array); K2, K1 scalars or arrays."""
    sig = [2 * ((d >> i) & 1) - 1 for i in range(DB)]
    R = np.zeros_like(d) + K1
    for i in p.r2rows():
        R = R - sig[i] * rd(np.zeros_like(d) + K2, p.sh2[i])
    Q = np.zeros_like(d)
    for i in reversed(range(DB)):
        Q = Q + sig[i] * rd(R, p.sh1[i])
    return R, Q


def fitc(lo, hi, mid, scale, iters=60):
    f = lambda M: scale / np.sqrt(M)
    u = np.linspace(lo - mid, hi - mid, 2001)
    A = np.vander(u, 3, increasing=True)
    w = np.sqrt(mid + u) / scale
    wt = np.ones_like(u)
    for _ in range(iters):
        sw = w * np.sqrt(wt)
        coef = np.linalg.lstsq(A * sw[:, None], f(mid + u) * sw, rcond=None)[0]
        err = np.abs((A @ coef - f(mid + u)) * w)
        wt = wt * err; wt /= wt.sum()
    return coef


def segment_bounds(p, e, a, d):
    """Admissible integer interval [lo, hi] for Y (before >> GY) at each d, using relative tol 2^-24."""
    M = 1 + a / 128 + d.astype(np.float64) * 2.0**-21
    scale = 2.0**(-(1 - e) / 2)
    y = scale / np.sqrt(M)
    tol = y * 2.0**-24
    # Y >> GY in units 2^(GY - FY):  value v = (Y >> GY); need |v 2^(GY-FY) - y| <= tol
    u = 2.0**(p.fy - p.gy)
    vlo = np.ceil((y - tol) * u); vhi = np.floor((y + tol) * u)
    return vlo, vhi, y


def fit_tables(p, search2=1, search1=3, verbose=False):
    """Per segment pick integers (K2, K1, K0) maximizing the worst relative slack. Exact in floating point
    up to the final integer certificate (certify())."""
    d = np.arange(2**DB, dtype=np.int64)
    tabs = {}
    worst = 0.0
    G = 2**p.gy
    for e in (0, 1):
        scale = 2.0**(-(1 - e) / 2)
        for a in range(128):
            lo = 1 + a / 128; hi = lo + 1 / 128
            mid = lo + (2**DB - 1) / 2 * 2.0**-21          # centre of the signed-digit coordinate
            c = fitc(lo, hi, mid, scale)
            K2c = int(round(c[2] * 2**p.f2)); K1c = int(round(-c[1] * 2**p.f1))
            vlo, vhi, y = segment_bounds(p, e, a, d)
            tolu = y * 2.0**-24 * 2.0**(p.fy - p.gy)
            best = None
            for K2 in range(K2c - search2, K2c + search2 + 1):
                for K1 in range(K1c - search1, K1c + search1 + 1):
                    R, Q = pipeline(p, K2, K1, d)
                    # need vlo*G <= K0 - Q <= vhi*G + G - 1
                    k0lo = int((vlo * G + Q).max()); k0hi = int((vhi * G + G - 1 + Q).min())
                    if k0lo > k0hi:
                        continue
                    for K0 in {(k0lo + k0hi) // 2, (k0lo + k0hi + 1) // 2}:
                        v = (K0 - Q) >> p.gy
                        slack = float(np.min((tolu - np.abs(v - y * 2.0**(p.fy - p.gy))) / tolu))
                        if best is None or slack > best[0]:
                            best = (slack, K2, K1, K0)
            if best is None:
                raise ValueError(f'segment {(e, a)} infeasible')
            tabs[(e, a)] = best[1:]
            worst = max(worst, 1 - best[0])
    if verbose:
        print('fit: worst |err|/tol (float model) =', worst)
    return tabs, worst


def model_phase_units(p, tabs, xs):
    """Exact model of the circuit's phase in units of 2^-64 turns (uint64) for x in xs."""
    xs = np.asarray(xs, dtype=np.int64)
    z = 21 - np.floor(np.log2(xs)).astype(np.int64)
    xn = xs << z
    e = z & 1; a = z >> 1
    idx = ((xn >> 14) & 127) + 128 * e
    packed = np.array([tabs[(ee, aa)] for ee in (0, 1) for aa in range(128)], dtype=np.int64)
    K2, K1, K0 = (packed[idx, j] for j in range(3))
    d = xn & (2**DB - 1)
    sig = [2 * ((d >> i) & 1) - 1 for i in range(DB)]
    R = K1.copy()
    for i in p.r2rows():
        R = R - sig[i] * rd(K2, p.sh2[i])
    Y = K0.copy()
    for i in reversed(range(DB)):
        Y = Y - sig[i] * rd(R, p.sh1[i])
    assert (Y >= 0).all() and (R >= 0).all()
    v = (Y >> p.gy).astype(np.uint64)
    # turns = v * 2^(gy - fy + a - 10);  units 2^-64  -> shift by 64 + gy - fy + a - 10 (>= 0 required)
    sh = (64 + p.gy - p.fy - 10 + a).astype(np.uint64)
    return (v << sh), R, Y


def certify(p, tabs, chunk=1 << 18):
    """Exact all-x check against the verifier's own arithmetic (target, tol from isqrt). Returns
    (worst ratio, min margin in 2^-64 units, max R, max Y)."""
    worst, margin, rmax, ymax = 0.0, 1 << 64, 0, 0
    for st in range(1, MAXX + 1, chunk):
        xs = np.arange(st, min(st + chunk, MAXX + 1), dtype=np.int64)
        act, R, Y = model_phase_units(p, tabs, xs)
        rmax = max(rmax, int(R.max())); ymax = max(ymax, int(Y.max()))
        roots = [math.isqrt((1 << 130) // int(x)) for x in xs]
        tgt = np.array([((r + 1) >> 1) & ((1 << 64) - 1) for r in roots], dtype=np.uint64)
        tol = np.array([min(r >> 25, 1 << 63) for r in roots], dtype=np.uint64)
        err = np.abs((act - tgt).view(np.int64)).view(np.uint64)
        if not (err <= tol).all():
            bad = np.flatnonzero(err > tol)[0]
            return dict(ok=False, x=int(xs[bad]), ratio=float(err[bad] / tol[bad]))
        worst = max(worst, float((err / tol).max()))
        margin = min(margin, int((tol - err).min()))
    return dict(ok=True, worst=worst, margin=margin, rmax=rmax, ymax=ymax)


if __name__ == '__main__':
    import time, pickle, sys
    p = P()
    t = time.time(); tabs, w = fit_tables(p, verbose=True); print('fit s', time.time() - t)
    t = time.time(); c = certify(p, tabs); print(c, 'cert s', time.time() - t)
    pickle.dump((p.key(), tabs), open(sys.argv[1] if len(sys.argv) > 1 else '/tmp/tabs.pkl', 'wb'))


def layout(p, tabs, LB=21, S=20, RB=12, RS=11):
    """Split K0 = H 2^S + L0 with L = L0 - Q in [0, 2^LB) for every d (rows touch only L), and
    K1 = C 2^RS + r0 with r = r0 - (K2 rows) in [0, 2^RB) (R rows touch only r)."""
    d = np.arange(2**DB, dtype=np.int64)
    out = {}
    wH = wC = 0
    for key, (K2, K1, K0) in tabs.items():
        R, Q = pipeline(p, K2, K1, d)
        C = int(R.min()) >> RS
        r0 = K1 - (C << RS)
        assert ((R - (C << RS)) >= 0).all() and ((R - (C << RS)) < 2**RB).all()
        qmin, qmax = int(Q.min()), int(Q.max())
        base = K0 % (1 << S); j = 0
        while base + j * (1 << S) - qmax < 0: j += 1
        L0 = base + j * (1 << S)
        assert L0 - qmin < (1 << LB), 'L layout infeasible'
        H = (K0 - L0) >> S
        assert H >= 0 and (K0 - L0) % (1 << S) == 0
        out[key] = (K2, C, r0, H, L0)
        wH = max(wH, H.bit_length()); wC = max(wC, (C + 1).bit_length())
    return out, dict(LB=LB, S=S, RB=RB, RS=RS, wH=wH, wC=wC)
