"""Semantic decode of the 44/46-qubit invsqrt family (Agent A).

At checkpoints (depth-0 ops), every live wire is compared (on a stratified x sample) against the bits of a
library of integer functions of x, possibly XOR a function of the exponent class:
  x;  lz = leading zeros (22-bit);  k = lz >> 1, h = lz & 1;  n = x << 2k (even normalisation);
  m = x << lz (full normalisation);  v_s = isqrt(n << s) and the remainder (n << s) - v_s^2, s = 0..5;
  q_{a,s} = floor(2^a / v_s) for a in a range.
A wire matching bit j of function F (exactly, or XOR a function of lz) is labelled F[j] (or F[j]^lz).
usage: python decode44.py circuit.kmx step [n_sample]"""
import sys, math, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
from winsynth import record_states
MAXX = 3133452; W = 22


def library(xs):
    x = xs.astype(object)
    lz = np.array([W - int(v).bit_length() for v in x])
    k = lz >> 1; h = lz & 1
    F = {'x': [int(v) for v in x], 'lz': list(lz), 'k': list(k)}
    n = [int(v) << int(2 * kk) for v, kk in zip(x, k)]
    m = [int(v) << int(l) for v, l in zip(x, lz)]
    F['n'] = n; F['m'] = m
    for s in range(0, 6):
        vs = [math.isqrt(t << s) for t in n]
        F['v%d' % s] = vs
        F['r%d' % s] = [(t << s) - u * u for t, u in zip(n, vs)]
        for a in range(18, 36, 1):
            F['q%d_%d' % (a, s)] = [(1 << a) // u for u in vs]
    return F, lz


def main(path, step=500, n=8192):
    ops = load(path)
    rng = np.random.default_rng(2)
    xs = np.sort(np.concatenate([np.arange(1, n // 2 + 1, dtype=np.uint64),
                                 rng.choice(np.arange(n // 2 + 1, MAXX + 1, dtype=np.uint64), n // 2, replace=False)]))
    F, lz = library(xs)
    bits = {}
    for name, vals in F.items():
        arr = np.array(vals, dtype=object)
        mx = max(int(v) for v in vals).bit_length()
        for j in range(mx):
            b = np.array([(int(v) >> j) & 1 for v in vals], dtype=np.uint8)
            if b.any() and not b.all(): bits[(name, j)] = b
    # depth-0 checkpoints
    d = 0; cps = []
    for kk, (op, a, c) in enumerate(ops):
        if op == 'PUSH_CONDITION': d += 1
        elif op == 'POP_CONDITION': d -= 1
        elif d == 0 and kk % step == 0: cps.append(kk)
    V, nn = record_states(ops, xs, 1, set(cps))
    lzc = [lz == l for l in range(W)]
    for kk in cps:
        U = np.unpackbits(V[kk].view(np.uint8), axis=1, bitorder='little')[:, :nn]
        labels = []
        for w in range(U.shape[0]):
            u = U[w]
            if not u.any(): continue
            hit = None
            for key, b in bits.items():
                dlt = u ^ b
                if not dlt.any(): hit = '%s[%d]' % key; break
            if hit is None:
                for key, b in bits.items():
                    dlt = u ^ b; ok = True
                    for msk in lzc:
                        s = dlt[msk]
                        if len(s) and s.min() != s.max(): ok = False; break
                    if ok: hit = '%s[%d]^f(lz)' % key; break
            if hit is None:
                ok = True
                for msk in lzc:
                    s = u[msk]
                    if len(s) and s.min() != s.max(): ok = False; break
                if ok: hit = 'f(lz)'
            labels.append('q%d:%s' % (w, hit or '?'))
        print('op %d (%s) live %d: %s' % (kk, ops[kk][0], len(labels), ' '.join(labels)), flush=True)


if __name__ == '__main__':
    main(sys.argv[1], *(int(a) for a in sys.argv[2:]))
