"""Builds an optimized kickmix circuit for the invsqrt benchmark (Benchmark I).

|x>|0> -> exp(2 pi i / sqrt(x)) |x>|0>,   x in [1, 3133452], 22-bit register 'x'.

Design (all arithmetic exactly mirrored by the numpy model below):
  1. Normalize x by single-bit binary stages (16, 8, 4, 2, 1) into M = x_norm / 2^21 in [1, 2);
     flags f0..f4 hold the shift count s' in binary.  e = f0 (parity), s = s' >> 1.
     1/sqrt(x) = 2^(s-10) * y,  y = 2^((e-1)/2) / sqrt(M)  in (0.5, 1].
  2. One 256-entry QROM indexed by (7 mantissa bits, e) XORs quadratic coefficients directly into
     the working registers (no separate coefficient copies).
  3. Centered signed-digit Horner: delta_c = sum_i (2 d_i - 1) 2^(i-22) over the 14 low bits.
     R = K1 - C2*delta_c,  y = K0 - R*delta_c.  Each row is an UNcontrolled Gidney addition
     wrapped in CNOT flips (Y - A = ~(~Y + A)), with a rounding carry-in.
  4. The y register is split: rows only touch a 21-bit low register L; the constant high part
     sits in a separate register and the overflow bit is merged in before phasing.
  5. Binary de-normalization (shift by s), one Z_POW per bit, then exact mirror uncompute.
     Lookup uncompute is measurement based (del_lookup); normalization flags are cleared by HMR
     with classically conditioned phase fixups.
Usage:  python build_invsqrt.py OUT.kmb   (needs kickmix importable and numpy)
"""
import sys, math
from fractions import Fraction
import numpy as np
import kickmix as km

W = 22; MB = 21; DB = 14; NSEG = 128
F2, F1, FYR, GY, DROP2 = 10, 19, 26, 2, (5,)     # precision configuration (verified)

# ----------------------------------------------------------------- numpy model / tables
def fitc(lo, hi, mid, scale, deg=2, iters=80):
    f = lambda M: scale / np.sqrt(M)
    d = np.linspace(lo - mid, hi - mid, 3001)
    A = np.vander(d, deg + 1, increasing=True)
    w = np.sqrt(mid + d) / scale
    wt = np.ones_like(d)
    for _ in range(iters):                       # Lawson iterations -> weighted minimax
        sw = w * np.sqrt(wt)
        coef = np.linalg.lstsq(A * sw[:, None], f(mid + d) * sw, rcond=None)[0]
        err = np.abs((A @ coef - f(mid + d)) * w)
        wt = wt * err; wt /= wt.sum()
    return coef

class Cfg:
    def __init__(self, f2, f1, fyr, gy, drop2=()):
        self.f2, self.f1, self.fyr, self.gy = f2, f1, fyr, gy
        self.fy = fyr + gy
        self.w2 = f2 - 1
        self.sh2 = [f2 + 22 - i - f1 for i in range(DB)]
        self.sh1 = [f1 + 22 - i - self.fy for i in range(DB)]
        self.drop2 = set(drop2)
    def rrow_list(self):
        return [i for i in reversed(range(DB)) if i not in self.drop2 and self.sh2[i] < self.w2]

def rd(v, s):
    if s < 0: return v << (-s)
    r = v >> s
    if s >= 1: r = r + ((v >> (s - 1)) & 1)
    return r

def pipeline(cfg, K2, K1, d):
    sig = [2 * ((d >> i) & 1) - 1 for i in range(DB)]
    R = np.full_like(d, K1)
    for i in cfg.rrow_list():
        R = R - sig[i] * rd(K2, cfg.sh2[i])
    Q = np.zeros_like(d)
    for i in reversed(range(DB)):
        Q = Q + sig[i] * rd(R, cfg.sh1[i])
    return R, Q

def build_tables(cfg, search=2):
    tabs = {}; worst = 0
    dmid = (2**DB - 1) / 2**(MB + 1)
    d = np.arange(2**DB, dtype=np.int64)
    g = cfg.gy
    for e in (0, 1):
        scale = 2**((e - 1) / 2)
        for a in range(NSEG):
            lo = 1 + a * 2.0**(DB - MB); mid = lo + dmid
            c = fitc(lo, lo + 2.0**(DB - MB), mid, scale)
            C1, C2 = -c[1], c[2]
            M = lo + d * 2.0**-MB
            fM = scale / np.sqrt(M); tgt = fM * 2.0**cfg.fy; w = 1 / fM
            K2c = int(round(C2 * 2**cfg.f2)); K1c = int(round(C1 * 2**cfg.f1))
            best = None
            for K2 in range(K2c - 1, K2c + 2):
                for K1 in range(K1c - search, K1c + search + 1):
                    R, Q = pipeline(cfg, K2, K1, d)
                    def mx(K0):
                        Y = ((K0 - Q) >> g) << g
                        return float(np.max(np.abs(Y - tgt) * w))
                    t = tgt + Q
                    a_, b_ = math.floor(t.min()), math.ceil(t.max())
                    while b_ - a_ > 2:
                        m1 = a_ + (b_ - a_) // 3; m2 = b_ - (b_ - a_) // 3
                        if mx(m1) < mx(m2): b_ = m2
                        else: a_ = m1
                    for K0 in range(a_, b_ + 1):
                        v = mx(K0) / 2.0**cfg.fy
                        if best is None or v < best[0]: best = (v, K2, K1, K0)
            tabs[(e, a)] = best[1:]
            worst = max(worst, best[0])
    return tabs, worst

def layout(cfg, tabs, LB=21, S=20):
    d = np.arange(2**DB, dtype=np.int64)
    assert max(t[0] for t in tabs.values()) < (1 << cfg.w2)
    Rmax = 0; per = {}; Ymax = 0
    for key, (K2, K1, K0) in tabs.items():
        R, Q = pipeline(cfg, K2, K1, d)
        assert R.min() >= 0
        Rmax = max(Rmax, int(R.max()), K1)
        per[key] = (int(Q.min()), int(Q.max()))
        Ymax = max(Ymax, K0 - per[key][0])
    w1 = Rmax.bit_length()
    lo_tab, hi_tab = {}, {}
    for key, (K2, K1, K0) in tabs.items():
        qmin, qmax = per[key]
        base = K0 % (1 << S); j = 0
        while base + j * (1 << S) - qmax < 0: j += 1
        k0lo = base + j * (1 << S)
        assert k0lo - qmin < (1 << LB), 'layout infeasible'
        lo_tab[key] = k0lo; hi_tab[key] = (K0 - k0lo) >> S
        assert hi_tab[key] >= 0
    whi = max(max(hi_tab.values()).bit_length(), 1)
    return dict(w1=w1, LB=LB, S=S, whi=whi, lo=lo_tab, hi=hi_tab)

# ----------------------------------------------------------------- circuit pieces
def and_all_into(b, controls, target):
    k = len(controls)
    if k == 1: b.cx(controls[0], target); return
    if k == 2: b.ccx(controls[0], controls[1], target); return
    anc = b.alloc_qubits(k - 2)
    b.init_and(controls[0], controls[1], anc[0])
    for j in range(1, k - 2): b.init_and(anc[j - 1], controls[j + 1], anc[j])
    b.ccx(anc[k - 3], controls[k - 1], target)
    for j in reversed(range(1, k - 2)): b.del_and(anc[j - 1], controls[j + 1], anc[j])
    b.del_and(controls[0], controls[1], anc[0])
    b.free(anc)

def phase_all(b, controls):
    k = len(controls)
    if k == 1: b.z(controls[0]); return
    if k == 2: b.cz(controls[0], controls[1]); return
    anc = b.alloc_qubits(k - 2)
    b.init_and(controls[0], controls[1], anc[0])
    for j in range(1, k - 2): b.init_and(anc[j - 1], controls[j + 1], anc[j])
    b.cz(anc[k - 3], controls[k - 1])
    for j in reversed(range(1, k - 2)): b.del_and(anc[j - 1], controls[j + 1], anc[j])
    b.del_and(controls[0], controls[1], anc[0])
    b.free(anc)

NSTAGES = [(4, 16), (3, 8), (2, 4), (1, 2), (0, 1)]

def normalize(b, x, f):
    for (k, d) in NSTAGES:
        top = x[W - d:W]
        if d == 1:
            b.cx(x[W - 1], f[0]); b.x(f[0])
        else:
            b.x(top); and_all_into(b, list(top), f[k]); b.x(top)
        for i in reversed(range(0, W - d)): b.cswap(f[k], x[i], x[i + d])

def unnormalize(b, x, f):
    for (k, d) in reversed(NSTAGES):
        for i in range(0, W - d): b.cswap(f[k], x[i], x[i + d])
        top = x[W - d:W]
        if d == 1:
            b.x(f[0]); b.cx(x[W - 1], f[0])
        else:
            m = b.alloc_bits(1)[0]
            b.hmr(f[k], m)
            b.push_condition(m)                     # fixup runs on half the shots on average
            b.x(top); phase_all(b, list(top)); b.x(top)
            b.pop_condition()
            b.free(m)

def gadd(b, a, t, cin=None, sub=False):
    """t += a + cin (or t -= a + cin), Gidney adder: len(t)-1 Toffolis, uncompute by HMR."""
    a = list(a); t = list(t); o = len(a); n = len(t)
    assert o <= n
    if sub: b.x(km.array(t))
    c = b.alloc_qubits(n - 1) if n > 1 else km.array([])
    def C(i): return cin if i == 0 else c[i - 1]
    for i in range(0, n - 1):
        if i == 0 and cin is None:
            if o: b.init_and(a[0], t[0], C(1))
        elif i < o:
            b.cx(C(i), a[i]); b.cx(C(i), t[i]); b.init_and(a[i], t[i], C(i + 1)); b.cx(C(i), C(i + 1))
        else:
            b.init_and(C(i), t[i], C(i + 1))
    if n - 1 < o: b.cx(a[n - 1], t[n - 1])
    if n > 1 or cin is not None: b.cx(C(n - 1), t[n - 1])
    for i in reversed(range(0, n - 1)):
        if i == 0 and cin is None:
            if o: b.del_and(a[0], t[0], C(1)); b.cx(a[0], t[0])
        elif i < o:
            b.cx(C(i), C(i + 1)); b.del_and(a[i], t[i], C(i + 1)); b.cx(C(i), a[i]); b.cx(a[i], t[i])
        else:
            b.del_and(C(i), t[i], C(i + 1)); b.cx(C(i), t[i])
    if n > 1: b.free(c)
    if sub: b.x(km.array(t))

def shift_stages(b, f, reg, L, inverse):
    stages = [(1, 1), (2, 2), (3, 4), (4, 8)]
    occ = []; o = L
    for (k, d) in stages: occ.append(o); o = min(o + d, len(reg))
    seq = list(enumerate(stages))
    if not inverse:
        for idx, (k, d) in seq:
            for i in reversed(range(0, occ[idx])):
                if i + d < len(reg): b.cswap(f[k], reg[i], reg[i + d])
    else:
        for idx, (k, d) in reversed(seq):
            for i in range(0, occ[idx]):
                if i + d < len(reg): b.cswap(f[k], reg[i], reg[i + d])

def build_circuit(cfg, tabs, lay):
    w2, w1, LB, S, whi = cfg.w2, lay['w1'], lay['LB'], lay['S'], lay['whi']
    gy, fy = cfg.gy, cfg.fy
    b = km.CircuitBuilder()
    x = b.create_quantum_register(W, name='x')
    f = b.alloc_qubits(5)
    c2 = b.alloc_qubits(w2); R = b.alloc_qubits(w1); Lr = b.alloc_qubits(LB); Yh = b.alloc_qubits(whi)
    tgt = km.array(list(Lr) + list(R) + list(c2) + list(Yh))
    table = [0] * 256
    for (e, a), (K2, K1, K0) in tabs.items():
        table[a + 128 * e] = lay['lo'][(e, a)] | (K1 << LB) | (K2 << (LB + w1)) | (lay['hi'][(e, a)] << (LB + w1 + w2))
    addr = km.array(list(x[14:21]) + [f[0]])
    delta = x[0:DB]
    def rrows(inverse):
        seq = cfg.rrow_list()
        if inverse: seq = list(reversed(seq))
        for i in seq:
            sh = cfg.sh2[i]
            if sh >= 0: off = c2[sh:w2]; t = R[0:w1]; cin = c2[sh - 1] if sh >= 1 else None
            else: off = c2[0:w2]; t = R[-sh:w1]; cin = None
            b.cx(delta[i], t); gadd(b, off, t, cin, sub=inverse); b.cx(delta[i], t)
    def yrows(inverse):
        seq = list(reversed(range(DB)))
        if inverse: seq.reverse()
        for i in seq:
            sh = cfg.sh1[i]; assert 0 <= sh < w1
            t = Lr[0:LB]; cin = R[sh - 1] if sh >= 1 else None
            b.cx(delta[i], t); gadd(b, R[sh:w1], t, cin, sub=inverse); b.cx(delta[i], t)
    normalize(b, x, f)
    b.init_lookup(table=table, address=addr, target=tgt)
    rrows(False); yrows(False)
    ext = b.alloc_qubits(10)
    if LB > S: gadd(b, Lr[S:LB], Yh)
    Cx = km.array(list(Lr[gy:S]) + list(Yh) + list(ext))
    shift_stages(b, f, Cx, S - gy + whi, False)
    for j in range(len(Cx)):
        e = gy + j - fy - 10                       # bit weight 2^e turns
        if e < 0: b.z_pow(Cx[j], Fraction(2)**(e + 1))
    shift_stages(b, f, Cx, S - gy + whi, True)
    if LB > S: gadd(b, Lr[S:LB], Yh, sub=True)
    b.free(ext)
    yrows(True); rrows(True)
    b.del_lookup(table=table, address=addr, target=tgt)
    b.free(tgt)
    unnormalize(b, x, f)
    b.free(f)
    return b.finish_circuit()

def main(out):
    cfg = Cfg(F2, F1, FYR, GY, DROP2)
    tabs, worst = build_tables(cfg)
    print(f'model worst relative error / 2^-24 = {worst * 2**24:.3f}')
    lay = layout(cfg, tabs)
    c = build_circuit(cfg, tabs, lay)
    s = c.operation_statistics()
    print('qubits', c.num_qubits, 'toffoli(static)', s.num_toffoli_like,
          'rotations', s.num_z_pow(min_clifford_hierarchy_level=4))
    c.to_file(out)
    print('wrote', out)

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'invsqrt.kmb')