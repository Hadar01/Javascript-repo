"""Exponent-conditional zero slots (Agent A).  At given ops, for every live wire w, list the exponent classes
k = lz >> 1 for which w is identically 0 (all x in that class).  A flag bit f(k) can be XORed into w without
losing information when f(k) = 1 only for classes where w is identically 0 and the class is decodable from the
remaining flags -- the trailing-zero packing used by the public circuits.  All x, coin seed 1.
usage: python kzero_slots.py circuit.kmx op1,op2,..."""
import sys, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
from winsynth import record_states
MAXX = 3133452; W = 22


def main(path, opsarg):
    ops = load(path); at = sorted(int(t) for t in opsarg.split(','))
    xs = np.arange(1, MAXX + 1, dtype=np.uint64)
    V, n = record_states(ops, xs, 1, set(at))
    bl = np.floor(np.log2(xs.astype(np.float64))).astype(np.int64) + 1
    k = (W - bl) >> 1
    masks = [k == j for j in range(11)]
    for op in at:
        U = np.unpackbits(V[op].view(np.uint8), axis=1, bitorder='little')[:, :n]
        out = []
        for w in range(U.shape[0]):
            if not U[w].any(): continue
            zk = [j for j in range(11) if not U[w][masks[j]].any()]
            if zk: out.append('q%d:k%s' % (w, ''.join('%d,' % j for j in zk).rstrip(',')))
        print('op', op, 'live', int(sum(U[w].any() for w in range(U.shape[0]))), 'conditional-zero wires:', ' '.join(out) or 'none', flush=True)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
