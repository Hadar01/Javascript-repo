"""Semantic lifting of an invsqrt kmx circuit (Agent A).

Simulates qubit values (bit-packed) on a random sample of x with random HMR coins, records the full qubit
state at checkpoints, and classifies each qubit at each checkpoint.

usage: python decode.py circuit.kmx out.npz [nsample] [every]
"""
import sys, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load

MAXX = 3133452; W = 22


def simulate(ops, xs, every=250, seed=0, extra=()):
    n = len(xs); nw = (n + 63) // 64
    nq = 1 + max(int(a[1:]) for _, args, _ in ops for a in args if a.startswith('q'))
    def pack(bits):
        b = np.zeros(nw * 64, dtype=np.uint8); b[:n] = bits
        return np.packbits(b, bitorder='little').view(np.uint64).copy()
    mask = pack(np.ones(n, dtype=np.uint8))
    S = [np.zeros(nw, np.uint64) for _ in range(nq)]
    for i in range(W):
        S[i] = pack(((xs >> np.uint64(i)) & np.uint64(1)).astype(np.uint8))
    zero = np.zeros(nw, np.uint64)
    class Bits(dict):
        def __missing__(self, k): return zero
    B = Bits(); stack = [mask]; rng = np.random.default_rng(seed)
    q = lambda a: int(a[1:])
    cps = {}; depth_ok = []
    for k, (op, args, cond) in enumerate(ops):
        if len(stack) == 1 and (k % every == 0 or k in extra):
            cps[k] = np.stack(S)
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
        elif op == 'R':
            S[q(args[0])] &= ~act
        elif op == 'BIT_INVERT': B[q(args[0])] = B[q(args[0])] ^ act
        elif op == 'BIT_STORE0': B[q(args[0])] = B[q(args[0])] & ~act
        elif op == 'BIT_STORE1': B[q(args[0])] = B[q(args[0])] | act
    cps[len(ops)] = np.stack(S)
    return cps, nq


def unpack(words, n):
    b = np.unpackbits(words.view(np.uint8), bitorder='little')
    return b[:n]


if __name__ == '__main__':
    path, out = sys.argv[1], sys.argv[2]
    ns = int(sys.argv[3]) if len(sys.argv) > 3 else 1 << 16
    every = int(sys.argv[4]) if len(sys.argv) > 4 else 250
    ops = load(path)
    rng = np.random.default_rng(1)
    xs = np.sort(rng.choice(np.arange(1, MAXX + 1, dtype=np.uint64), ns, replace=False))
    cps, nq = simulate(ops, xs, every)
    ks = sorted(cps)
    arr = np.stack([np.stack([unpack(cps[k][i], ns) for i in range(nq)]) for k in ks]).astype(np.uint8)
    np.savez_compressed(out, xs=xs, ks=np.array(ks), vals=arr)
    print('checkpoints', len(ks), 'qubits', nq, 'shape', arr.shape)
