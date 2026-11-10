"""Exact specification tests for one conditional-split carry-chain branch (Agent A).

The branch body [k0, k1] (k0 = its PUSH_CONDITION) is re-run on the reachable entry states of the lanes that
execute it: all x, two coin seeds, only lanes whose condition is true at k0.  The Gidney carry chain inside is
parsed from the CX/CX/CCX pattern; its carries c_1..c_n are recomputed classically and checked against the
forced execution (target ^= c_n).  Tests (sampled GF(2) span, positives re-checked exactly on all lanes):
  R0  linear dependencies among {1} + live entry wires  (a redundant live wire = a free ancilla)
  T1  c_k in lin-span(entry live, c_1..c_{k-1})          (CCX k replaceable by CNOTs)
  T2  c_{k+1} in quad-span(entry live with t -> t^c_n, c_1..c_{k-1})
                                                        (c_k erasable early with a Clifford-only fix-up)
  T3  t_old*c_n in quad-span(entry live, c_1..c_{n-1})    (ancilla-free phase variant of a B branch)
usage: python branch_spec.py circuit.kmx k0 k1 [target_wire]"""
import sys, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
MAXX = 3133452; W = 22
q = lambda a: int(a[1:])


def entry_state(ops, k0, seed):
    xs = np.arange(1, MAXX + 1, dtype=np.uint64)
    nq = 1 + max(int(a[1:]) for _, args, _ in ops for a in args if a.startswith('q'))
    n = len(xs); nw = (n + 63) // 64
    def pack(bits):
        b = np.zeros(nw * 64, dtype=np.uint8); b[:n] = bits
        return np.packbits(b, bitorder='little').view(np.uint64).copy()
    mask = pack(np.ones(n, dtype=np.uint8))
    S = np.zeros((nq, nw), np.uint64)
    for i in range(W): S[i] = pack(((xs >> np.uint64(i)) & np.uint64(1)).astype(np.uint8))
    zero = np.zeros(nw, np.uint64)
    class Bits(dict):
        def __missing__(self, k): return zero
    B = Bits(); stack = [mask]; rng = np.random.default_rng(seed)
    for k, (op, args, cond) in enumerate(ops):
        act = stack[-1] if cond is None else stack[-1] & B[q(cond)]
        if k == k0:
            return S, act, n
        if op == 'PUSH_CONDITION': stack.append(act); continue
        if op == 'POP_CONDITION':
            if len(stack) > 1: stack.pop()
            continue
        if op == 'X': S[q(args[0])] ^= act
        elif op == 'CX': S[q(args[1])] ^= S[q(args[0])] & act
        elif op == 'SWAP':
            a, b = q(args[0]), q(args[1]); d = (S[a] ^ S[b]) & act; S[a] ^= d; S[b] ^= d
        elif op == 'CCX':
            a, b, t = map(q, args); S[t] ^= S[a] & S[b] & act
        elif op == 'CSWAP':
            c, a, b = map(q, args); d = (S[a] ^ S[b]) & act & S[c]; S[a] ^= d; S[b] ^= d
        elif op == 'HMR':
            t = q(args[0]); coin = rng.integers(0, 2**63, size=nw, dtype=np.uint64) ^ (rng.integers(0, 2, size=nw, dtype=np.uint64) << np.uint64(63))
            B[q(args[1])] = (B[q(args[1])] & ~act) | (coin & act); S[t] &= ~act
        elif op == 'R': S[q(args[0])] &= ~act
        elif op == 'BIT_INVERT': B[q(args[0])] = B[q(args[0])] ^ act
        elif op == 'BIT_STORE0': B[q(args[0])] = B[q(args[0])] & ~act
        elif op == 'BIT_STORE1': B[q(args[0])] = B[q(args[0])] | act


def active_lanes(ops, k0, seeds=(1, 2)):
    """bool matrix (nq, m) of entry states over the executing lanes of all seeds."""
    cols = []
    for sd in seeds:
        S, act, n = entry_state(ops, k0, sd)
        a = np.unpackbits(act.view(np.uint8), bitorder='little')[:n].astype(bool)
        U = np.unpackbits(S.view(np.uint8), axis=1, bitorder='little')[:, :n]
        cols.append(U[:, a])
    return np.concatenate(cols, axis=1).astype(np.uint8)


def parse_chain(ops, k0, k1):
    """Gidney chain: before each CCX a b t, the carry-in w was CX'ed into a and b.  Returns cin, [(a,b,slot)]."""
    steps = []; recent = []
    depth = 0
    for k in range(k0 + 1, k1):
        op, args, cond = ops[k]
        if op == 'PUSH_CONDITION': depth += 1; continue
        if op == 'POP_CONDITION': depth -= 1; continue
        if depth or cond is not None: continue
        if op == 'CX': recent.append((q(args[0]), q(args[1])))
        if op == 'CCX':
            a, b, t = map(q, args)
            ws = [w for w, x in recent if x == a]; wsb = [w for w, x in recent if x == b]
            cin = [w for w in ws if w in wsb][-1]
            steps.append((cin, a, b, t, k)); recent = []
    return steps


class Span:
    """GF(2) span over packed sample vectors (python ints) with combination tags."""
    def __init__(self): self.piv = {}; self.names = []
    def add(self, v, name):
        tag = 1 << len(self.names); self.names.append(name)
        while v:
            top = v.bit_length() - 1
            if top in self.piv:
                pv, pt = self.piv[top]; v ^= pv; tag ^= pt
            else:
                self.piv[top] = (v, tag); return True
        return False
    def express(self, v):
        tag = 0
        while v:
            top = v.bit_length() - 1
            if top not in self.piv: return None
            pv, pt = self.piv[top]; v ^= pv; tag ^= pt
        return [self.names[i] for i in range(len(self.names)) if (tag >> i) & 1]


def toint(bits):
    return int.from_bytes(np.packbits(bits, bitorder='little').tobytes(), 'little')


def main(path, k0, k1, ns=16384):
    ops = load(path)
    steps = parse_chain(ops, k0, k1)
    U = active_lanes(ops, k0)
    nq, m = U.shape
    print('branch', k0, k1, 'executing lanes (2 seeds):', m, flush=True)
    cin = steps[0][0]
    pairs = [(a, b) for _, a, b, _, _ in steps]
    t = steps[-1][3]
    # carries from entry values
    C = [U[cin].copy()]
    for a, b in pairs:
        c = C[-1]; C.append((c & U[a]) ^ (c & U[b]) ^ (U[a] & U[b]))
    n = len(pairs)
    print('chain: cin q%d, pairs' % cin, ' '.join('(q%d,q%d)' % p for p in pairs), 'n', n, flush=True)
    # forced execution of the body (inner conditions ignored, HMR/R reset) -> check final target
    S = U.copy()
    for k in range(k0 + 1, k1):
        op, args, cond = ops[k]
        if op in ('PUSH_CONDITION', 'POP_CONDITION'): continue
        a = [q(x) for x in args if x.startswith('q')]
        if op == 'X': S[a[0]] ^= 1
        elif op == 'CX': S[a[1]] ^= S[a[0]]
        elif op == 'SWAP': S[[a[0], a[1]]] = S[[a[1], a[0]]]
        elif op == 'CCX': S[a[2]] ^= S[a[0]] & S[a[1]]
        elif op == 'CSWAP':
            d = S[a[0]] & (S[a[1]] ^ S[a[2]]); S[a[1]] ^= d; S[a[2]] ^= d
        elif op in ('HMR', 'R'): S[a[0]] = 0
    diff = [w for w in range(nq) if (S[w] != U[w]).any()]
    tgt = [w for w in diff if (S[w] == U[w] ^ C[n]).all()]
    print('wires changed by the branch:', ['q%d' % w for w in diff], 'equal to t^c_n:', ['q%d' % w for w in tgt], flush=True)
    if tgt: t = tgt[0]
    live = [w for w in range(nq) if U[w].any()]
    const1 = [w for w in live if U[w].all()]
    print('live at entry', len(live), 'constant-1 wires', ['q%d' % w for w in const1], flush=True)
    rng = np.random.default_rng(7)
    samp = np.sort(rng.choice(m, min(ns, m), replace=False))
    one = np.ones(m, np.uint8)
    # ---- R0: linear dependencies at entry
    sp = Span(); deps = []
    for w in live:
        if not sp.add(toint(U[w][samp]), 'q%d' % w):
            deps.append(w)
    sp.add(toint(one[samp]), '1')
    exact_deps = []
    for w in deps:
        sp2 = Span()
        for v in live:
            if v != w: sp2.add(toint(U[v][samp]), v)
        sp2.add(toint(one[samp]), '1')
        e = sp2.express(toint(U[w][samp]))
        if e is not None:
            acc = np.zeros(m, np.uint8)
            for v in e: acc ^= one if v == '1' else U[v]
            if (acc == U[w]).all(): exact_deps.append((w, e))
    print('R0 linear dependencies (sample):', ['q%d' % w for w in deps], 'exact:', exact_deps, flush=True)
    # ---- T1
    for k in range(1, n + 1):
        sp = Span()
        for w in live: sp.add(toint(U[w][samp]), 'q%d' % w)
        sp.add(toint(one[samp]), '1')
        for j in range(1, k): sp.add(toint(C[j][samp]), 'c%d' % j)
        e = sp.express(toint(C[k][samp]))
        print('T1 c%d linear:' % k, 'no' if e is None else ('sample', e), flush=True)
    # ---- quadratic span helper
    def quad_test(vars_, f, label):
        # vars_: list of (name, bool array over m lanes)
        sp = Span(); V = [(nm, x[samp]) for nm, x in vars_]
        sp.add(toint(one[samp]), '1')
        for nm, x in V: sp.add(toint(x), nm)
        for i in range(len(V)):
            for j in range(i + 1, len(V)):
                sp.add(toint(V[i][1] & V[j][1]), V[i][0] + '*' + V[j][0])
        e = sp.express(toint(f[samp]))
        if e is None:
            print(label, 'quadratic: no (refuted on %d-lane sample)' % len(samp), flush=True); return False
        D = dict(vars_); acc = np.zeros(m, np.uint8)
        for term in e:
            if term == '1': acc ^= one
            elif '*' in term:
                x, y = term.split('*'); acc ^= D[x] & D[y]
            else: acc ^= D[term]
        ok = bool((acc == f).all())
        print(label, 'quadratic on sample with', len(e), 'terms; EXACT on all lanes:', ok, flush=True)
        return ok
    base = [('q%d' % w, U[w]) for w in live]
    base_tnew = [('q%d' % w, (U[w] ^ C[n]) if w == t else U[w]) for w in live]
    # ---- T2
    for k in range(1, n):
        vars_ = base_tnew + [('c%d' % j, C[j]) for j in range(1, k)]
        quad_test(vars_, C[k + 1], 'T2 erase c%d early (c%d without it):' % (k, k + 1))
    # ---- T2b: as T2, but with the wires actually present at the erase of c_{k+1} in a Gidney unwind:
    #      b_j already holds the sum s_j = a_j ^ b_j ^ c_j for j >= k+1, t holds t ^ c_n.
    bpos = {b: j for j, (a, b) in enumerate(pairs)}
    for k in range(1, n):
        vs = []
        for w in live:
            if w == t: vs.append(('q%d' % w, U[w] ^ C[n]))
            elif w in bpos and bpos[w] >= k + 1: vs.append(('s%d' % bpos[w], U[w] ^ U[pairs[bpos[w]][0]] ^ C[bpos[w]]))
            else: vs.append(('q%d' % w, U[w]))
        quad_test(vs + [('c%d' % j, C[j]) for j in range(1, k)], C[k + 1],
                  'T2b erase c%d early, unwind wires (c%d without it):' % (k, k + 1))
    # ---- T3
    vars_ = base + [('c%d' % j, C[j]) for j in range(1, n)]
    quad_test(vars_, U[t] & C[n], 'T3 t_old*c_n (t=q%d):' % t)
    # ---- T3b: the same phase applied after the branch, over the wires present at its end
    fin = [('q%d' % w, S[w]) for w in range(nq) if S[w].any()]
    quad_test(fin, U[t] & C[n], 'T3b t_old*c_n over end-of-branch wires:')


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
