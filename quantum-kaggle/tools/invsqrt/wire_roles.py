"""Classify every wire at given ops (Agent A): zero, x_n bit (possibly XOR an lz function), lz-only function,
GF(2)-linear in (x_n bits, lz-function), or other.  All x, coin seed 1 (values at depth 0 are coin-free).
usage: python wire_roles.py circuit.kmx op1,op2,..."""
import sys, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
from winsynth import record_states
MAXX = 3133452; W = 22


def main(path, opsarg):
    ops = load(path); at = sorted(int(x) for x in opsarg.split(','))
    xs = np.arange(1, MAXX + 1, dtype=np.uint64); n = len(xs)
    V, n = record_states(ops, xs, 1, set(at))
    bl = np.floor(np.log2(xs.astype(np.float64))).astype(np.int64) + 1
    lz = (W - bl).astype(np.int64)
    xn = (xs << lz.astype(np.uint64)) & np.uint64((1 << W) - 1)
    XN = [((xn >> np.uint64(j)) & np.uint64(1)).astype(np.uint8) for j in range(W)]
    for k in at:
        U = np.unpackbits(V[k].view(np.uint8), axis=1, bitorder='little')[:, :n]
        roles = []
        for w in range(U.shape[0]):
            u = U[w]
            if not u.any(): roles.append('0'); continue
            # function of lz only?
            ok = True; tab = {}
            for l in range(W):
                s = u[lz == l]
                if len(s) and s.min() != s.max(): ok = False; break
                if len(s): tab[l] = int(s[0])
            if ok:
                roles.append('F[%s]' % ''.join(str(tab.get(l, '-')) for l in range(W))); continue
            # x_n bit XOR lz-function?
            hit = None
            for j in range(W):
                d = u ^ XN[j]; ok = True; tab = {}
                for l in range(W):
                    s = d[lz == l]
                    if len(s) and s.min() != s.max(): ok = False; break
                    if len(s): tab[l] = int(s[0])
                if ok:
                    hit = 'xn%d' % j + ('' if not any(tab.values()) else '^F[%s]' % ''.join(str(tab.get(l, '-')) for l in range(W))); break
            roles.append(hit or '?')
        print('op', k, ops[k][0], ' '.join(ops[k][1]))
        print('  ' + ' '.join('q%d:%s' % (w, r) for w, r in enumerate(roles)), flush=True)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
