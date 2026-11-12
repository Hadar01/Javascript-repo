"""Capacity test for freeing a qubit by compressing idle wires (Agent A).

At op k of a peak region [a, b]: D = live wires untouched on [a, b] (idle), B = the other live wires (busy,
usable only as read-only controls).  Any transformation that acts only on D (controlled by B) and frees
one qubit at k must map, for each value of B, the reachable D-patterns injectively into 2^(|D|-1)
patterns.  We count the reachable D-patterns per B-value over all x (coin seed 1; values at depth 0 are
coin-free) and report the maximum, plus the number of B-classes that violate the bound.
usage: python idle_capacity.py circuit.kmx k:a:b [k:a:b ...]"""
import sys, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
from winsynth import record_states
MAXX = 3133452


def main(path, specs):
    ops = load(path)
    S3 = [tuple(int(x) for x in s.split(':')) for s in specs]
    xs = np.arange(1, MAXX + 1, dtype=np.uint64)
    V, n = record_states(ops, xs, 1, {k for k, _, _ in S3})
    q = lambda t: int(t[1:])
    for k, a, b in S3:
        U = np.unpackbits(V[k].view(np.uint8), axis=1, bitorder='little')[:, :n]
        live = [w for w in range(U.shape[0]) if U[w].any()]
        touched = set()
        for j in range(a, b + 1):
            touched |= {q(t) for t in ops[j][1] if t.startswith('q')}
        D = [w for w in live if w not in touched]; Bw = [w for w in live if w in touched]
        def key(ws):
            h = np.zeros(n, np.uint64)
            for i, w in enumerate(ws): h ^= (U[w].astype(np.uint64) << np.uint64(i % 64)) * np.uint64(0x9E3779B97F4A7C15 if i >= 64 else 1)
            return h
        # exact keys: pack B wires into two uint64 words (<=128 wires), D into one (<=64)
        def pack(ws):
            out = []
            for c in range(0, len(ws), 63):
                h = np.zeros(n, np.uint64)
                for i, w in enumerate(ws[c:c + 63]): h |= U[w].astype(np.uint64) << np.uint64(i)
                out.append(h)
            return out
        kb = pack(Bw); kd = pack(D)
        rec = np.rec.fromarrays(kb + kd)
        uniq = np.unique(rec)
        bkeys = np.rec.fromarrays([uniq[f] for f in uniq.dtype.names[:len(kb)]])
        _, cnt = np.unique(bkeys, return_counts=True)
        bound = 2 ** (len(D) - 1)
        print('op %d region %d-%d: live %d, idle D=%d %s, busy %d; reachable states %d; B-classes %d; '
              'max D-patterns per B-class %d vs bound 2^(|D|-1)=%d; violating classes %d'
              % (k, a, b, len(live), len(D), ['q%d' % w for w in D], len(Bw), len(uniq), len(cnt), cnt.max(), bound,
                 int((cnt > bound).sum())), flush=True)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
