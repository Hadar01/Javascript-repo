"""Exact (all-x) probe for the rotation-merge question on a public invsqrt kmx (Agent A).
Records: live-qubit count and zero-qubit set at every depth-0 op in [lo, hi]; the value of the rotated wire at
every non-Clifford Z_POW (as packed bit arrays over all x); per Z_POW the angle.
usage: python merge_probe.py circuit.kmx out.npz lo hi [seed]"""
import sys, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
MAXX = 3133452; W = 22

def main(path, out, lo, hi, seed=0):
    ops = load(path)
    nq = 1 + max(int(a[1:]) for _, args, _ in ops for a in args if a.startswith('q'))
    n = MAXX; nw = (n + 63) // 64
    xs = np.arange(1, n + 1, dtype=np.uint64)
    def pack(bits):
        b = np.zeros(nw * 64, dtype=np.uint8); b[:n] = bits
        return np.packbits(b, bitorder='little').view(np.uint64).copy()
    mask = pack(np.ones(n, dtype=np.uint8))
    S = [np.zeros(nw, np.uint64) for _ in range(nq)]
    for i in range(W): S[i] = pack(((xs >> np.uint64(i)) & np.uint64(1)).astype(np.uint8))
    zero = np.zeros(nw, np.uint64)
    class Bits(dict):
        def __missing__(self, k): return zero
    B = Bits(); stack = [mask]; rng = np.random.default_rng(seed)
    q = lambda a: int(a[1:])
    live_k, live_n, live_zero = [], [], []
    zk, zang, zval = [], [], []
    for k, (op, args, cond) in enumerate(ops):
        if lo <= k <= hi and len(stack) == 1:
            nz = [i for i in range(nq) if S[i].any()]
            live_k.append(k); live_n.append(len(nz))
            live_zero.append(sum(1 << i for i in range(nq) if i not in nz))
        act = stack[-1] if cond is None else stack[-1] & B[q(cond)]
        if op == 'PUSH_CONDITION': stack.append(act); continue
        if op == 'POP_CONDITION':
            if len(stack) > 1: stack.pop()
            continue
        if op == 'Z_POW':
            from fractions import Fraction
            ang = Fraction(args[1])
            if ang.denominator > 4:
                zk.append(k); zang.append(float(ang)); zval.append((S[q(args[0])] & act).copy())
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
    np.savez_compressed(out, live_k=np.array(live_k), live_n=np.array(live_n),
                        live_zero=np.array([str(z) for z in live_zero]), zk=np.array(zk), zang=np.array(zang),
                        zval=np.stack(zval), nq=nq)
    print('ops', len(ops), 'rotations', len(zk), 'live max in range', max(live_n))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
