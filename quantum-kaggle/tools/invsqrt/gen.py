"""Our own parameterised invsqrt circuit generator (Agent A).  All code is ours; design credits in model.py.

usage: python gen.py OUT.kmb [--tabs tabs.pkl]
"""
import argparse, pickle, sys, os
from fractions import Fraction
import numpy as np
import kickmix as km
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M

W = M.W


# ------------------------------------------------------------------ primitives
def gadd(b, a, t, cin=None, sub=False, top_reuse=True, borrowed=()):
    """t += a + cin  (or t -= a + cin when sub) modulo 2^len(t).  Gidney adder: len(t)-1 ANDs,
    carries uncomputed by measurement.  The last carry is written straight into t[-1] (top_reuse)."""
    a = list(a); t = list(t); m, n = len(a), len(t)
    assert m <= n
    if sub:
        b.x(km.array(t))
    if n == 1:
        if m: b.cx(a[0], t[0])
        if cin is not None: b.cx(cin, t[0])
        if sub: b.x(km.array(t))
        return
    ncar = n - 1 - (1 if top_reuse else 0)
    bor = list(borrowed)[:ncar]
    fresh = b.alloc_qubits(ncar - len(bor)) if ncar > len(bor) else km.array([])
    car = bor + list(fresh)          # car[i] holds carry into bit i+1
    c = [cin] + [None] * (n - 1)     # c[i] = carry into bit i (qubit) or None (known 0)
    kind = [None] * (n - 1)
    for i in range(n - 1):
        last = top_reuse and i == n - 2
        out = t[n - 1] if last else car[i]
        ci = c[i]
        if i < m:
            if ci is None:
                (b.ccx if last else b.init_and)(a[i], t[i], out); kind[i] = 'a'
            else:
                b.cx(ci, a[i]); b.cx(ci, t[i])
                (b.ccx if last else b.init_and)(a[i], t[i], out)
                b.cx(ci, out); kind[i] = 'b'
        else:
            if ci is None:
                kind[i] = 'none'; continue
            (b.ccx if last else b.init_and)(ci, t[i], out); kind[i] = 'c'
        if not last:
            c[i + 1] = out
    # top bit
    if m == n: b.cx(a[n - 1], t[n - 1])
    if not top_reuse and c[n - 1] is not None: b.cx(c[n - 1], t[n - 1])
    for i in reversed(range(n - 1)):
        last = top_reuse and i == n - 2
        ci = c[i]; k = kind[i]
        if k == 'a':
            if not last: b.del_and(a[i], t[i], car[i])
            b.cx(a[i], t[i])
        elif k == 'b':
            if not last:
                b.cx(ci, car[i]); b.del_and(a[i], t[i], car[i])
            b.cx(ci, a[i]); b.cx(a[i], t[i])
        elif k == 'c':
            if not last: b.del_and(ci, t[i], car[i])
            b.cx(ci, t[i])
    if len(fresh): b.free(fresh)
    if sub:
        b.x(km.array(t))


def signed_row(b, d, src, tgt, cin, inverse, borrowed=()):
    """tgt -= (2d-1) * (src + cin)   [forward];  inverse undoes it.  Uses ~(~T + v) = T - v."""
    b.cx(d, km.array(list(tgt)))
    gadd(b, src, tgt, cin, sub=inverse, borrowed=borrowed)
    b.cx(d, km.array(list(tgt)))


# ------------------------------------------------------------------ normalisation
STAGES = [(4, 16), (3, 8), (2, 4), (1, 2), (0, 1)]


def chain_flags(b, x, f, compute):
    """XOR into f[4], f[3], f[2] the bits 4,3,2 of lz (leading zeros), from one prefix-AND chain on the
    *unshifted* x (idea: Alex Chilton's shared-prefix flags)."""
    bits = [x[W - 1 - m] for m in range(20)]          # x21 .. x2
    b.x(km.array(bits))
    ch = b.alloc_qubits(19)
    b.init_and(bits[0], bits[1], ch[0])
    for m in range(1, 19): b.init_and(ch[m - 1], bits[m + 1], ch[m])
    p = {j: ch[4 * j - 2] for j in range(1, 6)}          # p_j = [lz >= 4 j]
    b.cx(p[4], f[4])
    b.cx(p[2], f[3]); b.cx(p[4], f[3])
    for j in range(1, 6): b.cx(p[j], f[2])
    for m in reversed(range(1, 19)): b.del_and(ch[m - 1], bits[m + 1], ch[m])
    b.del_and(bits[0], bits[1], ch[0])
    b.free(ch)
    b.x(km.array(bits))


def normalize(b, x, f):
    chain_flags(b, x, f, True)
    for k, d in STAGES:
        if d == 2:
            b.x(x[W - 2:W]); b.init_and(x[W - 1], x[W - 2], f[1]); b.x(x[W - 2:W])
        if d == 1:
            b.cx(x[W - 1], f[0]); b.x(f[0])
        for i in reversed(range(W - d)):
            b.cswap(f[k], x[i], x[i + d])


def unnormalize(b, x, f):
    for k, d in reversed(STAGES):
        for i in range(W - d):
            b.cswap(f[k], x[i], x[i + d])
        if d == 1:
            b.x(f[0]); b.cx(x[W - 1], f[0])
        if d == 2:
            b.x(x[W - 2:W]); b.del_and(x[W - 1], x[W - 2], f[1]); b.x(x[W - 2:W])
    chain_flags(b, x, f, False)


# ------------------------------------------------------------------ phase with de-normalisation
def shift_stages(b, f, reg, occ0, inverse):
    """Left-shift reg by a = f1 + 2 f2 + 4 f3 + 8 f4.  Moves into always-clean positions use AND+CNOT
    forward and are erased by measurement in reverse (idea: Alex Chilton's empty-target moves)."""
    stages = [(1, 1), (2, 2), (3, 4), (4, 8)]
    occ = []; o = occ0
    for k, d in stages: occ.append(o); o = min(o + d, len(reg))
    seq = list(enumerate(stages))
    if not inverse:
        for idx, (k, d) in seq:
            for i in reversed(range(occ[idx])):
                if i + d >= len(reg): continue
                if i + d >= occ[idx]:
                    b.init_and(f[k], reg[i], reg[i + d]); b.cx(reg[i + d], reg[i])
                else:
                    b.cswap(f[k], reg[i], reg[i + d])
    else:
        for idx, (k, d) in reversed(seq):
            for i in range(occ[idx]):
                if i + d >= len(reg): continue
                if i + d >= occ[idx]:
                    b.cx(reg[i + d], reg[i]); b.del_and(f[k], reg[i], reg[i + d])
                else:
                    b.cswap(f[k], reg[i], reg[i + d])


def phase_Y(b, p, f, Y):
    word = list(Y[p.gy:])
    ext = b.alloc_qubits(10)
    reg = km.array(word + list(ext))
    shift_stages(b, f, reg, len(word), False)
    for j in range(len(reg)):
        ex = p.gy + j - p.fy - 10            # weight 2^ex turns
        if ex < 0:
            b.z_pow(reg[j], Fraction(2) ** (ex + 1))
    shift_stages(b, f, reg, len(word), True)
    b.free(ext)


# ------------------------------------------------------------------ circuit
def build(p, tabs, wR, wY):
    b = km.CircuitBuilder()
    x = b.create_quantum_register(W, name='x')
    f = b.alloc_qubits(5)
    normalize(b, x, f)
    R = b.alloc_qubits(wR); K2 = b.alloc_qubits(p.w2); Y = b.alloc_qubits(wY)
    tgt = km.array(list(R) + list(K2) + list(Y))
    table = [0] * 256
    for (e, a), (k2, k1, k0) in tabs.items():
        assert 0 <= k2 < 2**p.w2 and 0 <= k1 < 2**wR and 0 <= k0 < 2**wY
        table[a + 128 * e] = k1 | (k2 << wR) | (k0 << (wR + p.w2))
    addr = km.array(list(x[14:21]) + [f[0]])
    delta = x[0:M.DB]
    b.init_lookup(table=table, address=addr, target=tgt)

    def rrows(inv):
        rows = p.r2rows()
        for i in (reversed(rows) if inv else rows):
            sh = p.sh2[i]
            assert sh >= 0
            signed_row(b, delta[i], K2[sh:], R, K2[sh - 1] if sh >= 1 else None, inv)

    def yrows(inv):
        rows = list(reversed(range(M.DB)))
        for i in (reversed(rows) if inv else rows):
            sh = p.sh1[i]
            assert sh >= 0
            signed_row(b, delta[i], R[sh:], Y, R[sh - 1] if sh >= 1 else None, inv)

    rrows(False); yrows(False)
    phase_Y(b, p, f, Y)
    yrows(True); rrows(True)
    b.del_lookup(table=table, address=addr, target=tgt)
    b.free(tgt)
    unnormalize(b, x, f)
    b.free(f)
    return b.finish_circuit()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--tabs')
    a = ap.parse_args()
    p = M.P()
    if a.tabs and os.path.exists(a.tabs):
        key, tabs = pickle.load(open(a.tabs, 'rb')); assert key == p.key()
    else:
        tabs, _ = M.fit_tables(p)
    cert = M.certify(p, tabs); print('model', cert)
    wR = cert['rmax'].bit_length(); wY = cert['ymax'].bit_length()
    c = build(p, tabs, wR, wY)
    s = c.operation_statistics()
    print('qubits', c.num_qubits, 'toffoli(static)', s.num_toffoli_like, 'rot', s.num_z_pow(min_clifford_hierarchy_level=4),
          'T', s.num_t_like)
    c.to_file(a.out, format='kmb')
