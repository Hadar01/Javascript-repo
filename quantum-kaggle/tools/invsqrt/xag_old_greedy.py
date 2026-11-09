"""Greedy XOR-AND synthesis of a multi-output table over an n-bit address (Agent A, our code).

Every target bit t is realised as  t = l1*l2 (+) l3*l4 (+) ... (+) s  where every l and s lies in the GF(2) span
V of the wires available so far (address bits, constant 1, and previously synthesised targets).  Each product
costs one Toffoli (CCX straight into the target qubit, no helper qubits).  Erasing targets in reverse order
by X-measurement needs only Clifford fix-ups (CZ(l1, l2), Z(s)), so un-lookup is free.

For a fixed l1 the condition  t + s = l1*l2  is LINEAR in (s, l2): on points with l1 = 0 we need s = t and on
points with l1 = 1 we need s + l2 = t.  With k products, fixing l1, l3, ... leaves a linear system in
(s, l2, l4, ...).  We sample the fixed factors at random and solve by Gaussian elimination.
"""
import random


def popc(v): return bin(v).count('1')


class Span:
    """GF(2) span of wire functions; each basis vector remembers its expression as a wire mask."""
    def __init__(self, npts):
        self.N = npts; self.full = (1 << npts) - 1
        self.piv = {}              # pivot bit -> (vec, exprmask)
        self.vecs = []             # list of (vec, expr) basis in insertion order (for random sampling)

    def reduce(self, v, e=0):
        for pb in sorted(self.piv, reverse=True):
            if (v >> pb) & 1:
                pv, pe = self.piv[pb]; v ^= pv; e ^= pe
        return v, e

    def add(self, v, e):
        r, re = self.reduce(v, e)
        if r == 0: return False
        pb = r.bit_length() - 1
        # keep reduced form simple: eliminate pb from existing
        for k in list(self.piv):
            pv, pe = self.piv[k]
            if (pv >> pb) & 1: self.piv[k] = (pv ^ r, pe ^ re)
        self.piv[pb] = (r, re); self.vecs.append((v, e))
        return True

    def express(self, v):
        r, e = self.reduce(v, 0)
        return None if r else e

    @property
    def dim(self): return len(self.piv)

    def basis(self):
        return [self.piv[k] for k in sorted(self.piv)]

    def rand(self, rng, density=0.5):
        v = e = 0
        for bv, be in self.basis():
            if rng.random() < density: v ^= bv; e ^= be
        return v, e


def solve(rows, nunk):
    """rows: list of (coeffmask, rhs). Returns a solution mask or None."""
    piv = {}
    for m, r in rows:
        for pb in sorted(piv, reverse=True):
            if (m >> pb) & 1:
                pm, pr = piv[pb]; m ^= pm; r ^= pr
        if m == 0:
            if r: return None
            continue
        pb = m.bit_length() - 1
        for k in list(piv):
            pm, pr = piv[k]
            if (pm >> pb) & 1: piv[k] = (pm ^ m, pr ^ r)
        piv[pb] = (m, r)
    sol = 0
    for pb, (m, r) in piv.items():
        if r: sol |= 1 << pb          # free vars = 0; reduced form so pivot = rhs
    return sol


def try_k(span, t, fixed):
    """fixed: list of (vec, expr) for l1, l3, ...  Unknowns: s, then the partner of each fixed factor."""
    B = span.basis(); D = len(B); k = len(fixed)
    nunk = D * (k + 1)
    rows = []
    for pt in range(span.N):
        m = 0
        for i, (bv, _) in enumerate(B):
            if (bv >> pt) & 1:
                m |= 1 << i                               # s coefficient
                for j, (fv, _) in enumerate(fixed):
                    if (fv >> pt) & 1: m |= 1 << (D * (j + 1) + i)
        rows.append((m, (t >> pt) & 1))
    sol = solve(rows, nunk)
    if sol is None: return None
    def comb(off):
        v = e = 0
        for i, (bv, be) in enumerate(B):
            if (sol >> (off + i)) & 1: v ^= bv; e ^= be
        return v, e
    s = comb(0)
    prods = [(fixed[j], comb(D * (j + 1))) for j in range(k)]
    # verify
    acc = s[0]
    for (a, _), (b2, _) in prods: acc ^= a & b2
    assert acc == t
    return s, prods


def synth(targets, nbits, seed=0, tries=(1, 60, 400, 1500), maxk=12):
    """targets: list of ints (truth tables over 2^nbits points). Returns plan list and total products."""
    rng = random.Random(seed)
    N = 1 << nbits; span = Span(N)
    full = (1 << N) - 1
    # wires: 0 = constant 1 (pseudo), 1..nbits = address bits, then targets in order
    span.add(full, 1)
    for j in range(nbits):
        v = 0
        for pt in range(N):
            if (pt >> j) & 1: v |= 1 << pt
        span.add(v, 1 << (1 + j))
    plan = []; total = 0
    for ti, t in enumerate(targets):
        wire = 1 + nbits + ti
        e = span.express(t)
        if e is not None:
            plan.append(dict(s=e, prods=[])); span.add(t, 1 << wire); continue
        done = None
        for k in range(1, maxk + 1):
            for _ in range(tries[min(k, len(tries) - 1)] if k < len(tries) else tries[-1]):
                fixed = [span.rand(rng) for _ in range(k)]
                if any(f[0] in (0, full) for f in fixed): continue
                r = try_k(span, t, fixed)
                if r: done = r; break
            if done: break
        if not done: raise RuntimeError('no decomposition')
        s, prods = done
        plan.append(dict(s=s[1], prods=[(a[1], b2[1]) for a, b2 in prods]))
        total += len(prods)
        span.add(t, 1 << wire)
    return plan, total
