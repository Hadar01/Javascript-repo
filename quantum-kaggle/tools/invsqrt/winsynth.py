"""Reachable-state window resynthesis search (Agent A).

Windows: start at a depth-0 unconditioned Toffoli-like gate; follow the circuit, skipping ops that touch no
window wire; include ops touching window wires (CX, X, SWAP, CCX, CSWAP, CZ, Z, CCZ) while the wire set stays
<= MAXW; stop at anything else touching a window wire (HMR, R, Z_POW, NEG, conditioned op, condition block)
or an op that would exceed MAXW.  For each window prefix ending at a Toffoli-like gate with T >= 2 Toffolis:
  inputs  R = reachable patterns of the window wires at the window start (sample of x, two coin seeds),
  map     F: R -> outputs, phase parity phi: R -> {0,1} (Z/CZ/CCZ inside the window).
Tests (exact on R):
  T' = 0 : F affine and phi quadratic                      (all Clifford)
  T' = 1 : F = A x + w (l.m) + c with phi quadratic         (one CCX)  [l, m linear forms, w a vector]
           or F affine and phi = l.m.n + quadratic          (one CCZ)
A hit with T' < T is a candidate saving of T - T' Toffolis (to be verified on all x).
usage: python winsynth.py circuit.kmx out.json [MAXW]"""
import sys, json, itertools, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
MAXX = 3133452; W = 22
TOFF = ('CCX', 'CSWAP', 'CCZ')
OKOPS = ('CX', 'X', 'SWAP', 'CCX', 'CSWAP', 'CZ', 'Z', 'CCZ')
import os
TMAX = int(os.environ.get('TMAX', '4'))


def record_states(ops, xs, seed, at):
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
    q = lambda a: int(a[1:])
    out = {}
    for k, (op, args, cond) in enumerate(ops):
        if k in at: out[k] = S.copy()
        act = stack[-1] if cond is None else stack[-1] & B[q(cond)]
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
    return out, n


def depth_map(ops):
    d = 0; D = []
    for op, args, cond in ops:
        if op == 'PUSH_CONDITION': D.append(d); d += 1; continue
        if op == 'POP_CONDITION': D.append(d); d = max(0, d - 1); continue
        D.append(d)
    return D


def windows(ops, maxw):
    D = depth_map(ops)
    res = []
    for s, (op, args, cond) in enumerate(ops):
        if op not in TOFF or D[s] != 0 or cond is not None: continue
        wires = set(a for a in args if a.startswith('q'))
        members = [s]; T = 1
        dirty = set()            # wires touched by skipped ops since the window start
        k = s + 1
        while k < len(ops):
            op2, args2, cond2 = ops[k]
            qs = set(a for a in args2 if a.startswith('q'))
            if op2 in ('PUSH_CONDITION', 'POP_CONDITION'):
                k += 1
                continue
            if not (qs & wires):
                dirty |= qs; k += 1; continue
            if D[k] != 0 or cond2 is not None or op2 not in OKOPS: break
            if len(wires | qs) > maxw: break
            if (qs - wires) & dirty: break
            wires |= qs; members.append(k)
            if op2 in TOFF:
                T += 1
                res.append((s, list(members), sorted(wires), T))
            k += 1
            if T >= TMAX: break
    return res


def evaluate(ops, members, wires, pats):
    """Apply window ops to integer patterns (bit i = wires[i]); return outputs and phase parities."""
    idx = {w: i for i, w in enumerate(wires)}
    out = pats.copy(); ph = np.zeros(len(pats), np.uint8)
    bit = lambda v, w: (v >> idx[w]) & 1
    for k in members:
        op, args, _ = ops[k]
        if op == 'X': out ^= 1 << idx[args[0]]
        elif op == 'CX': out ^= bit(out, args[0]) << idx[args[1]]
        elif op == 'SWAP':
            a, b = args; d = bit(out, a) ^ bit(out, b); out ^= (d << idx[a]) | (d << idx[b])
        elif op == 'CCX':
            a, b, t = args; out ^= (bit(out, a) & bit(out, b)) << idx[t]
        elif op == 'CSWAP':
            c, a, b = args; d = bit(out, c) & (bit(out, a) ^ bit(out, b)); out ^= (d << idx[a]) | (d << idx[b])
        elif op == 'Z': ph ^= bit(out, args[0]).astype(np.uint8)
        elif op == 'CZ': ph ^= (bit(out, args[0]) & bit(out, args[1])).astype(np.uint8)
        elif op == 'CCZ': ph ^= (bit(out, args[0]) & bit(out, args[1]) & bit(out, args[2])).astype(np.uint8)
    return out, ph


def gf2_rank(rows):
    rows = [int(r) for r in rows]; r = 0; basis = []
    for v in rows:
        for b in basis: v = min(v, v ^ b)
        if v: basis.append(v); r += 1
    return r


def in_span(cols, target):
    """cols: list of int vectors over the pattern index (bit p = value at pattern p); is target in span?"""
    basis = []
    for v in cols:
        for b in basis: v = min(v, v ^ b)
        if v: basis.append(v); basis.sort(reverse=True)
    t = target
    for b in basis: t = min(t, t ^ b)
    return t == 0


def main(path, out, maxw=6):
    ops = load(path)
    wins = windows(ops, maxw)
    starts = sorted(set(w[0] for w in wins))
    rng = np.random.default_rng(21); ns = 4096
    xs = np.sort(np.concatenate([np.arange(1, ns + 1, dtype=np.uint64),
                                 rng.choice(np.arange(ns + 1, MAXX + 1, dtype=np.uint64), ns, replace=False)]))
    V0, n = record_states(ops, xs, 1, set(starts)); V1, _ = record_states(ops, xs, 2, set(starts))
    def unpack(v): return np.unpackbits(v.view(np.uint8), bitorder='little')[:n].astype(np.int64)
    hits = []; tested = 0
    cache = {}
    for s, members, wires, T in wins:
        key = (s, tuple(wires))
        if key not in cache:
            cols = [np.concatenate([unpack(V0[s][int(w[1:])]), unpack(V1[s][int(w[1:])])]) for w in wires]
            pid = sum(c << i for i, c in enumerate(cols))
            cache[key] = np.unique(pid)
        pats = cache[key]
        m = len(wires); P = len(pats)
        outv, ph = evaluate(ops, members, wires, pats)
        tested += 1
        # helpers over patterns
        def vec(bits):  # bits: array over patterns -> int
            v = 0
            for i, b in enumerate(bits):
                if b: v |= 1 << i
            return v
        coord = [((pats >> i) & 1) for i in range(m)]
        lin_cols = [vec(c) for c in coord] + [vec(np.ones(P, np.int64))]
        quad_cols = lin_cols + [vec(coord[i] & coord[j]) for i, j in itertools.combinations(range(m), 2)]
        outbits = [vec((outv >> j) & 1) for j in range(m)]
        phv = vec(ph)
        def mkred(cols):
            basis = []
            for v in cols:
                for b in basis: v = min(v, v ^ b)
                if v: basis.append(v); basis.sort(reverse=True)
            def red(t):
                for b in basis: t = min(t, t ^ b)
                return t
            return red
        redL = mkred(lin_cols); redQ = mkred(quad_cols)
        rob = [redL(ob) for ob in outbits]
        affine_out = not any(rob)
        rph = redQ(phv)
        quad_phase = rph == 0
        best = None
        if affine_out and quad_phase:
            best = 0
        elif T >= 2:
            fl = []
            for c in range(1, 1 << m):
                fv = np.zeros(P, np.int64)
                for i in range(m):
                    if (c >> i) & 1: fv ^= coord[i]
                fl.append(vec(fv))
            full = (1 << P) - 1
            forms = fl + [f ^ full for f in fl]
            need = set(r for r in rob if r)
            if quad_phase and len(need) <= 1:
                for f, g in itertools.combinations(forms, 2):
                    rg = redL(f & g)
                    if rg and need <= {rg}:
                        best = 1; break
            has_ccz = any(ops[k][0] == 'CCZ' for k in members)
            if best is None and affine_out and has_ccz:
                for f, g, h in itertools.combinations(fl, 3):
                    if redQ(f & g & h) == rph: best = 1; break
        if best is not None and best < T:
            hits.append(dict(start=s, members=members, wires=wires, T=T, Tnew=best, patterns=int(P)))
            print('HIT', s, T, '->', best, wires, members, 'patterns', P, flush=True)
    json.dump(hits, open(out, 'w'), indent=0)
    print('windows tested', tested, 'max wires', maxw, 'hits', len(hits))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 6)
