"""Generic XOR-AND-graph (XAG) synthesis of multi-output Boolean tables, with a kickmix emitter.

Agent A, quantum-kaggle team.  All code ours.

Model.  Functions of n input bits are ints with 2^n bits (bit p = value at input point p).  Wires are:
the constant 1, the n inputs, and AND-products  p = l1 & l2  where l1, l2 are XORs of earlier wires.
XOR is free (CNOT); every product costs one Toffoli.  A target t is realised when t is an XOR of wires.

Greedy synthesis.  For a target t and the current span V (dim D) of live wires, we look for
    t = l1*l2 + l3*l4 + ... + s        (k products, all l and s in V).
Fixing l1, l3, ... (random elements of V) the condition is LINEAR in the unknown coefficients of
(s, l2, l4, ...):  on every point p:  s(p) + sum_j l_{2j-1}(p) l_{2j}(p) = t(p).
That is 2^n equations in (k+1) D unknowns; generically solvable once (k+1) D >~ 2^n.  We try k = 0, 1, 2 ...
Products of a k >= keep_from decomposition are kept as helper wires (they enlarge V for later targets),
otherwise they are accumulated straight into the target qubit.

The plan is a list of steps:
    ('and', wire_id, (l1_mask, l2_mask))        new helper wire = l1 & l2
    ('target', t_index, [(l1, l2), ...], s)      target qubit = XOR of products + XOR of wires in s
masks are ints over wire ids (bit w = include wire w); wire 0 is the constant 1, wires 1..n are inputs.
"""
import random, itertools


class Span:
    """Reduced GF(2) basis of live wire functions; each vector carries its wire-mask expression."""
    def __init__(self):
        self.piv = {}        # pivot bit -> (vec, expr)

    def reduce(self, v, e=0):
        while v:
            pb = v.bit_length() - 1
            if pb not in self.piv: break
            pv, pe = self.piv[pb]; v ^= pv; e ^= pe
        return v, e

    def full_reduce(self, v, e=0):
        out_v, out_e = 0, e
        while v:
            pb = v.bit_length() - 1
            if pb in self.piv:
                pv, pe = self.piv[pb]; v ^= pv; out_e ^= pe
            else:
                out_v |= 1 << pb; v ^= 1 << pb
        return out_v, out_e

    def add(self, v, e):
        r, re_ = self.reduce(v, e)
        if r == 0: return False
        self.piv[r.bit_length() - 1] = (r, re_)
        return True

    def express(self, v):
        r, e = self.full_reduce(v, 0)
        return None if r else e

    @property
    def dim(self): return len(self.piv)

    def basis(self): return list(self.piv.values())


def gf2_solve(rows, ncols):
    """rows: list of (mask over ncols unknowns, rhs bit). Returns a solution int or None."""
    piv = {}
    order = []
    for m, r in rows:
        while m:
            pb = m.bit_length() - 1
            if pb in piv:
                pm, pr = piv[pb]; m ^= pm; r ^= pr
            else:
                break
        if m == 0:
            if r: return None
            continue
        pb = m.bit_length() - 1
        piv[pb] = (m, r); order.append(pb)
    # back substitution: free vars = 0
    sol = 0
    for pb in sorted(piv):                       # ascending: lower pivots first
        m, r = piv[pb]
        rest = m ^ (1 << pb)
        val = r ^ (bin(rest & sol).count('1') & 1)
        if val: sol |= 1 << pb
    return sol


def decompose(span, t, npts, k, rng, tries):
    """Try to write t = sum_{j<k} f_j * g_j + s with f_j random in V. Returns (s_expr, [(f_expr, g_expr)])."""
    B = span.basis(); D = len(B)
    if k == 0:
        e = span.express(t)
        return (e, []) if e is not None else None
    # point-major columns: colbits[p] = mask over basis indices with basis value 1 at p
    colbits = [0] * npts
    for i, (bv, _) in enumerate(B):
        v = bv
        while v:
            p = (v & -v).bit_length() - 1
            colbits[p] |= 1 << i
            v &= v - 1
    for _ in range(tries):
        fixed = []
        for j in range(k):
            fv = fe = 0
            for bv, be in B:
                if rng.random() < 0.5: fv ^= bv; fe ^= be
            fixed.append((fv, fe))
        rows = []
        for p in range(npts):
            m = colbits[p]
            for j, (fv, _) in enumerate(fixed):
                if (fv >> p) & 1: m |= colbits[p] << (D * (j + 1))
            rows.append((m, (t >> p) & 1))
        sol = gf2_solve(rows, D * (k + 1))
        if sol is None: continue
        def comb(off):
            v = e = 0
            for i, (bv, be) in enumerate(B):
                if (sol >> (off + i)) & 1: v ^= bv; e ^= be
            return v, e
        s = comb(0)
        prods = [(fixed[j], comb(D * (j + 1))) for j in range(k)]
        acc = s[0]
        for (fv, _), (gv, _) in prods: acc ^= fv & gv
        if acc != t: continue
        full = (1 << npts) - 1
        se = s[1]; keep = []
        for (fv, fe), (gv, ge) in prods:
            if fv == 0 or gv == 0 or fv == gv ^ full: continue
            if fv == gv or gv == full: se ^= fe; continue
            if fv == full: se ^= ge; continue
            keep.append((fe, ge))
        return se, keep
    return None


def synthesize(targets, n, seed=0, keep_from=2, tries=12, kmax=64, helpers=(), order=None, verbose=False):
    """targets: list of ints over 2^n points.  helpers: list of (i, j) input-index pairs/tuples of extra
    monomial products to create first.  Returns dict(plan, ands, wires, peak)."""
    rng = random.Random(seed)
    npts = 1 << n; full = (1 << npts) - 1
    span = Span(); funcs = {}
    span.add(full, 1); funcs[0] = full
    for j in range(n):
        v = 0
        for p in range(npts):
            if (p >> j) & 1: v |= 1 << p
        span.add(v, 1 << (1 + j)); funcs[1 + j] = v
    nxt = n + 1
    plan = []; ands = 0
    memo = {}
    for mono in helpers:                 # monomial helpers, sharing prefixes (one AND per new monomial)
        for L in range(2, len(mono) + 1):
            key = tuple(mono[:L])
            if key in memo: continue
            pe = (1 << (1 + mono[0])) if L == 2 else (1 << memo[tuple(mono[:L - 1])])
            nv = wire_value(funcs, pe) & funcs[1 + mono[L - 1]]
            plan.append(('and', nxt, (pe, 1 << (1 + mono[L - 1])))); ands += 1
            funcs[nxt] = nv; span.add(nv, 1 << nxt); memo[key] = nxt; nxt += 1
    order = list(range(len(targets))) if order is None else order
    costs = []
    for ti in order:
        t = targets[ti]
        res = None
        for k in range(0, kmax + 1):
            res = decompose(span, t, npts, k, rng, 1 if k == 0 else tries)
            if res is not None: break
        if res is None: raise RuntimeError('no decomposition for target %d' % ti)
        s, prods = res
        k = len(prods); costs.append(k); ands += k
        if k >= keep_from:
            # keep each product as a helper wire, then the target is linear
            pe = 0
            for f, g in prods:
                fv = wire_value(funcs, f); gv = wire_value(funcs, g)
                plan.append(('and', nxt, (f, g))); funcs[nxt] = fv & gv; span.add(fv & gv, 1 << nxt)
                pe ^= 1 << nxt; nxt += 1
            plan.append(('target', ti, [], s ^ pe))
        else:
            plan.append(('target', ti, prods, s))
        tw = nxt; nxt += 1
        funcs[tw] = t; span.add(t, 1 << tw)
        plan[-1] = plan[-1] + (tw,)
        if verbose: print('target', ti, 'k', k, 'dim', span.dim, 'ands', ands, flush=True)
    return dict(plan=plan, ands=ands, costs=costs, nwires=nxt, funcs=funcs, nbase=len(memo))


def wire_value(funcs, mask):
    v = 0; w = 0
    while mask:
        if mask & 1: v ^= funcs[w]
        mask >>= 1; w += 1
    return v


def verify(result, targets):
    funcs = result['funcs']
    for st in result['plan']:
        if st[0] == 'target':
            _, ti, prods, s, tw = st
            v = wire_value(funcs, s)
            for f, g in prods: v ^= wire_value(funcs, f) & wire_value(funcs, g)
            assert v == targets[ti], ti
    return True


# ---------------------------------------------------------------------------------------------------
# Budgeted synthesis with explicit live-wire bookkeeping (for qubit-limited circuits).

def build_span(live):
    sp = Span()
    for w in sorted(live): sp.add(live[w], 1 << w)
    return sp


def synthesize_budget(targets, n, budget=40, seed=0, keep_from=2, tries=12, kmax=64, helpers=(), order=None,
                      verbose=False):
    """Like synthesize(), but at most `budget` helper wires (non-input, non-target) are live at any time.
    When over budget, the oldest helpers are erased by measurement; a helper can be erased for free when
    both of its factor functions are still in the span of the other live wires (fix-up CZ(f, g)).
    Plan steps: ('and', w, (fe, ge)), ('target', ti, prods, s, w), ('erase', w, (fe, ge)) with masks over the
    wires live at that moment."""
    rng = random.Random(seed)
    npts = 1 << n; full = (1 << npts) - 1
    live = {0: full}
    for j in range(n):
        v = 0
        for p in range(npts):
            if (p >> j) & 1: v |= 1 << p
        live[1 + j] = v
    funcs = dict(live)
    factors = {}                       # helper wire -> (f_func, g_func)
    helper_order = []
    nxt = n + 1; plan = []; ands = 0; peak = 0

    def add_helper(fe, ge, sp_funcs):
        nonlocal nxt, ands
        fv = wire_value(sp_funcs, fe); gv = wire_value(sp_funcs, ge)
        w = nxt; nxt += 1
        plan.append(('and', w, (fe, ge))); ands += 1
        live[w] = fv & gv; funcs[w] = fv & gv; factors[w] = (fv, gv); helper_order.append(w)
        return w

    def enforce_budget(protect=()):
        nonlocal peak
        basew = set(memo.values())
        hl = [w for w in helper_order if w in live and w not in basew]
        while len(hl) > budget:
            done = False
            for w in hl:
                if w in protect: continue
                others = {k: v for k, v in live.items() if k != w}
                sp = build_span(others)
                fe = sp.express(factors[w][0]); ge = sp.express(factors[w][1])
                if fe is not None and ge is not None:
                    plan.append(('erase', w, (fe, ge))); del live[w]; done = True; break
            if not done: break
            hl = [w for w in helper_order if w in live and w not in basew]

    memo = {}
    for mono in helpers:
        for L in range(2, len(mono) + 1):
            key = tuple(mono[:L])
            if key in memo: continue
            pe = (1 << (1 + mono[0])) if L == 2 else (1 << memo[key[:-1]])
            memo[key] = add_helper(pe, 1 << (1 + mono[L - 1]), funcs)
    order = list(range(len(targets))) if order is None else order
    costs = []
    for ti in order:
        t = targets[ti]
        sp = build_span(live)
        res = None
        for k in range(0, kmax + 1):
            res = decompose(sp, t, npts, k, rng, 1 if k == 0 else tries)
            if res is not None: break
        if res is None: raise RuntimeError('no decomposition for target %d' % ti)
        s, prods = res; k = len(prods); costs.append(k)
        if k >= keep_from:
            pe = 0; new = []
            for f, g in prods:
                w = add_helper(f, g, funcs); pe ^= 1 << w; new.append(w)
            tw = nxt; nxt += 1
            plan.append(('target', ti, [], s ^ pe, tw))
        else:
            ands += k
            tw = nxt; nxt += 1
            plan.append(('target', ti, prods, s, tw))
        live[tw] = t; funcs[tw] = t
        peak = max(peak, len(live) - n - 1)
        enforce_budget()
        if verbose: print('target', ti, 'k', k, 'live', len(live), 'ands', ands, flush=True)
    return dict(plan=plan, ands=ands, costs=costs, nwires=nxt, funcs=funcs, peak_nonin=peak, nbase=len(memo),
                live_end=sorted(live))


# ---------------------------------------------------------------------------------------------------
# kickmix emitter

class Emitter:
    """Emit a synthesis plan with kickmix.  wires: dict wire_id -> km.q for inputs (1..n); wire 0 = const 1.
    targets: list of km.q (index = target index).  Helper qubits are allocated from the builder."""
    def __init__(self, b, km, input_qubits, target_qubits):
        self.b, self.km = b, km
        self.q = {1 + j: qq for j, qq in enumerate(input_qubits)}
        self.tq = list(target_qubits)
        self.helpers = {}

    def _realize(self, masks):
        """Make each linear form (wire mask) available on its own qubit. Returns (qubits, undo list)."""
        b = self.b; undo = []; outq = []; used = set()
        cur = {}                                  # wire -> its current extra XOR mask (wire w holds w ^ cur[w])
        for m in masks:
            # rewrite m in terms of current qubit contents
            mm = m
            for w, extra in cur.items():
                if (mm >> w) & 1: mm ^= extra
            const = mm & 1; mm >>= 1; mm <<= 1
            ws = [w for w in range(mm.bit_length()) if (mm >> w) & 1]
            cand = [w for w in ws if w not in used]
            if not cand:
                raise ValueError('degenerate linear form')
            p = cand[0]
            for w in ws:
                if w != p:
                    b.cx(self.q[w], self.q[p]); undo.append(('cx', w, p))
            if const:
                b.x(self.q[p]); undo.append(('x', p))
            cur[p] = cur.get(p, 0) ^ (mm ^ (1 << p)) ^ const
            used.add(p); outq.append(self.q[p])
        return outq, undo

    def _undo(self, undo):
        for u in reversed(undo):
            if u[0] == 'cx': self.b.cx(self.q[u[1]], self.q[u[2]])
            else: self.b.x(self.q[u[1]])

    def _xor_into(self, mask, tgt):
        if mask & 1: self.b.x(tgt)
        w = 1; mask >>= 1
        while mask:
            if mask & 1: self.b.cx(self.q[w], tgt)
            mask >>= 1; w += 1

    def _phase_linear(self, mask):
        """Apply (-1)^(XOR of wires in mask)."""
        if mask & 1: self.b.neg()
        w = 1; mask >>= 1
        while mask:
            if mask & 1: self.b.z(self.q[w])
            mask >>= 1; w += 1

    def forward(self, plan):
        b = self.b
        for st in plan:
            if st[0] == 'and':
                _, w, (fe, ge) = st
                (pf, pg), undo = self._realize([fe, ge])
                h = b.alloc_qubits(1)[0]
                b.init_and(pf, pg, h); self._undo(undo)
                self.q[w] = h; self.helpers[w] = h
            elif st[0] == 'target':
                _, ti, prods, s, w = st
                t = self.tq[ti]
                for fe, ge in prods:
                    (pf, pg), undo = self._realize([fe, ge])
                    b.ccx(pf, pg, t); self._undo(undo)
                self._xor_into(s, t)
                self.q[w] = t
            elif st[0] == 'erase':
                _, w, (fe, ge) = st
                self._erase_product(w, fe, ge)

    def _erase_product(self, w, fe, ge):
        b = self.b; km = self.km
        h = self.q[w]; bit = b.alloc_bits(1)[0]
        b.hmr(h, bit)
        del self.q[w]
        (pf, pg), undo = self._realize([fe, ge])
        b.push_condition(bit); b.cz(pf, pg); b.pop_condition()
        self._undo(undo)
        b.free(km.array([h])); b.free(bit)
        self.helpers.pop(w, None)

    def reverse(self, plan):
        """Measurement-based un-lookup: undo the plan in reverse order.  Erased helpers are recomputed."""
        b = self.b; km = self.km
        for st in reversed(plan):
            if st[0] == 'and':
                _, w, (fe, ge) = st
                self._erase_product(w, fe, ge)
            elif st[0] == 'target':
                _, ti, prods, s, w = st
                t = self.tq[ti]; bit = b.alloc_bits(1)[0]
                b.hmr(t, bit); del self.q[w]
                b.push_condition(bit)
                for fe, ge in prods:
                    (pf, pg), undo = self._realize([fe, ge])
                    b.cz(pf, pg); self._undo(undo)
                self._phase_linear(s)
                b.pop_condition(); b.free(bit)
            elif st[0] == 'erase':
                _, w, (fe, ge) = st
                (pf, pg), undo = self._realize([fe, ge])
                h = b.alloc_qubits(1)[0]
                b.init_and(pf, pg, h); self._undo(undo)
                self.q[w] = h; self.helpers[w] = h


def reverse_fresh(em, result, targets, n, seed=1, tries=12, kmax=80, nbase=None):
    """Un-lookup at zero Toffoli cost.  (1) erase the non-base helpers newest-first while all targets are
    still live (their factor functions are re-expressed in the live span; fix-up CZ is Clifford);
    (2) erase each target (reverse synthesis order) by X-measurement, the fix-up (-1)^t being a fresh
    decomposition sum_j CZ(f_j, g_j) Z(s) over the live wires (any number of products is free);
    (3) erase the base monomial helpers newest-first."""
    km, b = em.km, em.b
    rng = random.Random(seed); npts = 1 << n; full = (1 << npts) - 1
    funcs = result['funcs']
    ands = [st for st in result['plan'] if st[0] == 'and']
    if nbase is None: nbase = result.get('nbase', 0)
    base = set(st[1] for st in ands[:nbase])
    fac = {st[1]: st[2] for st in ands}
    # factor functions as recorded at creation time
    facf = {w: (wire_value(funcs, fe), wire_value(funcs, ge)) for w, (fe, ge) in fac.items()}

    def erase_func(w, qubit, func):
        live = {k: funcs[k] for k in em.q if k != w}; live[0] = full
        sp = build_span(live)
        res = None
        for k in range(0, kmax + 1):
            res = decompose(sp, func, npts, k, rng, 1 if k == 0 else tries)
            if res is not None: break
        if res is None: return False
        s, prods = res
        bit = b.alloc_bits(1)[0]
        b.hmr(qubit, bit); del em.q[w]
        b.push_condition(bit)
        for fe, ge in prods:
            (pf, pg), undo = em._realize([fe, ge]); b.cz(pf, pg); em._undo(undo)
        em._phase_linear(s)
        b.pop_condition(); b.free(bit)
        return True

    def erase_helper(w):
        live = {k: funcs[k] for k in em.q if k != w}; live[0] = full
        sp = build_span(live)
        fe, ge = sp.express(facf[w][0]), sp.express(facf[w][1])
        if fe is not None and ge is not None:
            em._erase_product(w, fe, ge); return True
        h = em.helpers[w]
        if erase_func(w, h, funcs[w]):
            b.free(km.array([h])); em.helpers.pop(w); return True
        return False

    pending = sorted([w for w in em.helpers if w not in base], reverse=True)
    for _ in range(4):
        left = []
        for w in pending:
            if not erase_helper(w): left.append(w)
        pending = left
        if not pending: break
    if pending: raise RuntimeError('cannot erase helpers %s' % pending[:5])
    tw_of = {st[1]: st[4] for st in result['plan'] if st[0] == 'target'}
    order = [st[1] for st in result['plan'] if st[0] == 'target']
    for ti in reversed(order):
        w = tw_of[ti]
        live = {k: funcs[k] for k in em.q if k != w}; live[0] = full
        sp = build_span(live)
        res = None
        for k in range(0, kmax + 1):
            res = decompose(sp, targets[ti], npts, k, rng, 1 if k == 0 else tries)
            if res is not None: break
        if res is None: raise RuntimeError('cannot erase target %d' % ti)
        s, prods = res
        t = em.tq[ti]; bit = b.alloc_bits(1)[0]
        b.hmr(t, bit); del em.q[w]
        b.push_condition(bit)
        for fe, ge in prods:
            (pf, pg), undo = em._realize([fe, ge]); b.cz(pf, pg); em._undo(undo)
        em._phase_linear(s)
        b.pop_condition(); b.free(bit)
    for w in sorted([k for k in em.helpers if k in base], reverse=True):
        if not erase_helper(w): raise RuntimeError('cannot erase base helper %d' % w)


# ---------------------------------------------------------------------------------------------------
# Context API for field-by-field table construction inside a larger circuit.

class XagContext:
    """Tracks live wires whose values are known functions of an n-bit address, inside a kickmix builder.

    ctx = XagContext(b, km, address_qubits)
    ctx.build(funcs, qubits, budget)  : make qubits[i] hold funcs[i] (qubits must be |0>); helpers are freed
    ctx.erase(qubits)                 : X-measure them back to |0> with Clifford-only phase repair
    ctx.forget(qubits) / ctx.know(qubits, funcs): qubits being modified by arithmetic / restored
    Every Toffoli is an AND of two XORs of live wires.  Returns of build(): number of ANDs emitted."""
    def __init__(self, b, km, address_qubits, seed=0, tries=12, kmax=96):
        self.b, self.km = b, km
        self.n = len(address_qubits); self.npts = 1 << self.n; self.full = (1 << self.npts) - 1
        self.rng = random.Random(seed); self.tries = tries; self.kmax = kmax
        self.wfunc = {0: self.full}; self.wq = {}; self.nxt = 1
        for j, q in enumerate(address_qubits):
            v = 0
            for p in range(self.npts):
                if (p >> j) & 1: v |= 1 << p
            self._add_wire(v, q)
        self.ands = 0

    def _add_wire(self, func, q):
        w = self.nxt; self.nxt += 1
        self.wfunc[w] = func; self.wq[w] = q
        return w

    def _span(self, exclude=()):
        sp = Span()
        for w, f in self.wfunc.items():
            if w not in exclude: sp.add(f, 1 << w)
        return sp

    def _em(self):
        em = Emitter.__new__(Emitter); em.b, em.km = self.b, self.km
        em.q = dict(self.wq); em.tq = []; em.helpers = {}
        return em

    def _decompose_any(self, func, exclude=()):
        sp = self._span(exclude)
        for k in range(0, self.kmax + 1):
            res = decompose(sp, func, self.npts, k, self.rng, 1 if k == 0 else self.tries)
            if res is not None: return res
        return None

    def _phase_fix(self, s, prods):
        em = self._em()
        for fe, ge in prods:
            (pf, pg), undo = em._realize([fe, ge]); self.b.cz(pf, pg); em._undo(undo)
        em._phase_linear(s)

    def _erase_wire(self, w):
        res = self._decompose_any(self.wfunc[w], exclude=(w,))
        if res is None: raise RuntimeError('cannot erase wire')
        s, prods = res
        q = self.wq[w]; bit = self.b.alloc_bits(1)[0]
        self.b.hmr(q, bit)
        del self.wfunc[w]; del self.wq[w]
        self.b.push_condition(bit); self._phase_fix(s, prods); self.b.pop_condition()
        self.b.free(bit)
        return q

    def build(self, funcs, qubits, budget=25, base=True, keep_from=2, base_drop=None):
        b, km = self.b, self.km
        start_ands = self.ands
        helpers_live = []          # wires of helpers in creation order
        basew = []
        def new_product(fe, ge):
            em = self._em()
            fv = wire_value(self.wfunc, fe); gv = wire_value(self.wfunc, ge)
            (pf, pg), undo = em._realize([fe, ge])
            h = b.alloc_qubits(1)[0]
            b.init_and(pf, pg, h); em._undo(undo); self.ands += 1
            return self._add_wire(fv & gv, h)
        if base:
            memo = {}
            inw = list(range(1, self.n + 1))
            half = self.n // 2
            for grp in (inw[:half], inw[half:]):
                for d in range(2, len(grp) + 1):
                    for c in itertools.combinations(grp, d):
                        pe = (1 << c[0]) if d == 2 else (1 << memo[c[:-1]])
                        memo[c] = new_product(pe, 1 << c[-1]); basew.append(memo[c])
        order = sorted(range(len(funcs)), key=lambda i: anf_weight(funcs[i], self.n))
        tw = {}
        for i in order:
            t = funcs[i]
            res = self._decompose_any(t)
            if res is None: raise RuntimeError('no decomposition')
            s, prods = res
            q = qubits[i]
            em = self._em()
            if len(prods) >= keep_from:
                pe = 0
                for fe, ge in prods:
                    w = new_product(fe, ge); pe ^= 1 << w; helpers_live.append(w)
                em = self._em(); em._xor_into(s ^ pe, q)
            else:
                for fe, ge in prods:
                    (pf, pg), undo = em._realize([fe, ge]); b.ccx(pf, pg, q); em._undo(undo); self.ands += 1
                em._xor_into(s, q)
            tw[i] = self._add_wire(t, q)
            if base_drop is not None and len(tw) == base_drop and basew:
                for w in reversed(basew):
                    qh = self._erase_wire(w); b.free(km.array([qh]))
                basew = []
            # budget: erase oldest helpers whose factors are expressible, else by decomposition
            while len(helpers_live) > budget:
                w = helpers_live.pop(0)
                qh = self._erase_wire(w); b.free(km.array([qh]))
        for w in reversed(helpers_live):
            qh = self._erase_wire(w); b.free(km.array([qh]))
        for w in reversed(basew):
            qh = self._erase_wire(w); b.free(km.array([qh]))
        return self.ands - start_ands

    def make_base(self):
        b, km = self.b, self.km; memo = {}; basew = []
        inw = list(range(1, self.n + 1)); half = self.n // 2
        for grp in (inw[:half], inw[half:]):
            for d in range(2, len(grp) + 1):
                for c in itertools.combinations(grp, d):
                    pe = (1 << c[0]) if d == 2 else (1 << memo[c[:-1]])
                    em = self._em(); fe, ge = pe, 1 << c[-1]
                    fv = wire_value(self.wfunc, fe); gv = wire_value(self.wfunc, ge)
                    (pf, pg), undo = em._realize([fe, ge]); h = b.alloc_qubits(1)[0]
                    b.init_and(pf, pg, h); em._undo(undo); self.ands += 1
                    memo[c] = self._add_wire(fv & gv, h); basew.append(memo[c])
        return basew

    def drop(self, wires):
        for w in reversed(wires):
            qh = self._erase_wire(w); self.b.free(self.km.array([qh]))

    def erase(self, qubits):
        qs = list(qubits)
        ws = [w for w, q in self.wq.items() if any(q == qq for qq in qs)]
        for w in sorted(ws, reverse=True):
            self._erase_wire(w)

    def forget(self, qubits):
        for w in [w for w, q in self.wq.items() if any(q == qq for qq in qubits)]:
            del self.wfunc[w]; del self.wq[w]

    def know(self, qubits, funcs):
        for q, f in zip(qubits, funcs): self._add_wire(f, q)


def anf_weight(v, n):
    N = 1 << n
    tt = [(v >> i) & 1 for i in range(N)]
    for i in range(n):
        s = 1 << i
        for j in range(N):
            if j & s: tt[j] ^= tt[j ^ s]
    return sum(tt)
