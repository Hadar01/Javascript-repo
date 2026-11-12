"""Exact width profile of a kickmix invsqrt circuit (Agent A).

Simulates every x in [1, max_x] for each given coin seed (bit-packed) and records, for every op, which qubits
are live (nonzero on at least one lane, any seed) BEFORE and AFTER the op.  A qubit is needed at op k if it
is live before or after k, or is touched by k (an op cannot act on a qubit that does not exist).
Output: npz with needed[k, q] (bool), plus a printed list of the ops where all 62 are needed.
usage: python width_profile.py circuit.kmx out.npz [seeds=1,2]"""
import sys, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
MAXX = 3133452; W = 22
q = lambda a: int(a[1:])


def run(ops, seed, nq):
    xs = np.arange(1, MAXX + 1, dtype=np.uint64); n = len(xs); nw = (n + 63) // 64
    def pack(bits):
        b = np.zeros(nw * 64, np.uint8); b[:n] = bits; return np.packbits(b, bitorder='little').view(np.uint64).copy()
    full = pack(np.ones(n, np.uint8)); S = np.zeros((nq, nw), np.uint64)
    for i in range(W): S[i] = pack(((xs >> np.uint64(i)) & np.uint64(1)).astype(np.uint8))
    zero = np.zeros(nw, np.uint64)
    class Bits(dict):
        def __missing__(self, k): return zero
    B = Bits(); stack = [full]; rng = np.random.default_rng(seed)
    nz = np.array([S[w].any() for w in range(nq)])
    before = np.zeros((len(ops), nq), bool); after = np.zeros((len(ops), nq), bool)
    touched = np.zeros((len(ops), nq), bool)
    for k, (op, args, cond) in enumerate(ops):
        before[k] = nz
        a = [q(x) for x in args if x.startswith('q')]
        for w in a: touched[k, w] = True
        act = stack[-1] if cond is None else stack[-1] & B[q(cond)]
        if op == 'PUSH_CONDITION': stack.append(act); after[k] = nz; continue
        if op == 'POP_CONDITION':
            if len(stack) > 1: stack.pop()
            after[k] = nz; continue
        if op == 'X': S[a[0]] ^= act
        elif op == 'CX': S[a[1]] ^= S[a[0]] & act
        elif op == 'SWAP':
            d = (S[a[0]] ^ S[a[1]]) & act; S[a[0]] ^= d; S[a[1]] ^= d
        elif op == 'CCX': S[a[2]] ^= S[a[0]] & S[a[1]] & act
        elif op == 'CSWAP':
            d = (S[a[1]] ^ S[a[2]]) & act & S[a[0]]; S[a[1]] ^= d; S[a[2]] ^= d
        elif op == 'HMR':
            coin = rng.integers(0, 2**63, size=nw, dtype=np.uint64) ^ (rng.integers(0, 2, size=nw, dtype=np.uint64) << np.uint64(63))
            b = q(args[1]); B[b] = (B[b] & ~act) | (coin & act); S[a[0]] &= ~act
        elif op == 'R': S[a[0]] &= ~act
        elif op == 'BIT_INVERT': B[q(args[0])] = B[q(args[0])] ^ act
        elif op == 'BIT_STORE0': B[q(args[0])] = B[q(args[0])] & ~act
        elif op == 'BIT_STORE1': B[q(args[0])] = B[q(args[0])] | act
        for w in a: nz[w] = S[w].any()
        after[k] = nz
    return before, after, touched


def main(path, out, seeds='1,2'):
    ops = load(path)
    nq = 1 + max(int(a[1:]) for _, args, _ in ops for a in args if a.startswith('q'))
    need = np.zeros((len(ops), nq), bool); live = np.zeros((len(ops), nq), bool)
    for sd in (int(s) for s in seeds.split(',')):
        bf, af, tc = run(ops, sd, nq)
        live |= bf
        need |= bf | af | tc
    np.savez_compressed(out, need=need, live=live)
    cnt = need.sum(1)
    full_ops = np.flatnonzero(cnt == nq)
    print('ops', len(ops), 'max needed', cnt.max(), 'ops needing all %d:' % nq, len(full_ops))
    # group into regions (gap > 1 op starts a new region)
    regs = []
    for k in full_ops:
        if regs and k - regs[-1][1] <= 1: regs[-1][1] = k
        else: regs.append([k, k])
    print('regions:', len(regs))
    for a, b in regs: print('  %d-%d (%d ops)' % (a, b, b - a + 1))


if __name__ == '__main__':
    main(*sys.argv[1:])
