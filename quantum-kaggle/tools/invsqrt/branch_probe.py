"""Exact probe of one conditional branch (Agent A).  The branch body is executed on ALL x lanes starting from
the (coin-randomised) state at its PUSH; inner HMRs reset their qubit; inner conditions are ignored for values
(phase-only fix-ups) except value-changing inner ops, which are applied under their own coin.
For every Toffoli-like gate inside: fire count, product==control, and GF(2)-linear-in-live-wires (sampled,
then exact).  usage: python branch_probe.py circuit.kmx push_op pop_op"""
import sys, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
from winsynth import record_states
from linscan import gf2_express
MAXX = 3133452

def main(path, k0, k1):
    ops = load(path)
    xs = np.arange(1, MAXX + 1, dtype=np.uint64)
    V, n = record_states(ops, xs, 1, {k0})
    S = V[k0].copy(); nq = S.shape[0]; nw = S.shape[1]
    q = lambda a: int(a[1:])
    rng = np.random.default_rng(3)
    b = np.zeros(nw * 64, np.uint8); b[:n] = 1
    full = np.packbits(b, bitorder='little').view(np.uint64).copy()
    # small sample of lanes for the linear test: all x <= 8192 and random others
    samp = np.unique(np.concatenate([np.arange(0, 8192), rng.choice(np.arange(8192, n), 8192, replace=False)]))
    unp = lambda v: np.unpackbits(v.view(np.uint8), bitorder='little')[:n]
    pc = lambda v: int(sum(bin(int(w)).count('1') for w in v))
    for k in range(k0 + 1, k1):
        op, args, cond = ops[k]
        if op in ('PUSH_CONDITION', 'POP_CONDITION'): continue
        a = [q(x) for x in args if x.startswith('q')]
        if op in ('CCX', 'CCZ', 'CSWAP'):
            if op == 'CCX': prod = S[a[0]] & S[a[1]]; excl = {a[2]}
            elif op == 'CCZ': prod = S[a[0]] & S[a[1]] & S[a[2]]; excl = set()
            else: prod = S[a[0]] & (S[a[1]] ^ S[a[2]]); excl = set()
            fires = pc(prod)
            eq = [w for w in a[:2] if not (prod ^ S[w]).any()] if op == 'CCX' else []
            cols = [i for i in range(nq) if i not in excl and S[i].any()]
            P = unp(prod)[samp]
            rows = np.stack([np.packbits(unp(S[i])[samp], bitorder='little').view(np.uint8) for i in cols] +
                            [np.packbits(np.ones(len(samp), np.uint8), bitorder='little').view(np.uint8)])
            pad = (-rows.shape[1]) % 8
            rows = np.pad(rows, ((0, 0), (0, pad))).view(np.uint64)
            pv = np.pad(np.packbits(P, bitorder='little'), (0, pad)).view(np.uint64)
            sel = gf2_express(rows, pv)
            lin = None
            if sel is not None:
                acc = np.zeros(nw, np.uint64)
                for s_ in sel: acc ^= S[cols[s_]] if s_ < len(cols) else full
                lin = 'EXACT' if not (acc ^ prod).any() else 'sample-only'
            print(k, op, args, 'fires', fires, 'eq_control', eq, 'linear', lin, flush=True)
        if cond is not None and op not in ('CX', 'X', 'SWAP', 'CCX', 'CSWAP'):
            continue
        if op == 'X': S[a[0]] ^= full
        elif op == 'CX' and cond is None: S[a[1]] ^= S[a[0]]
        elif op == 'SWAP': S[[a[0], a[1]]] = S[[a[1], a[0]]]
        elif op == 'CCX' and cond is None: S[a[2]] ^= S[a[0]] & S[a[1]]
        elif op == 'CSWAP' and cond is None:
            d = S[a[0]] & (S[a[1]] ^ S[a[2]]); S[a[1]] ^= d; S[a[2]] ^= d
        elif op in ('HMR', 'R'): S[a[0]] = 0

if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
