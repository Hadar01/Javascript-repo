"""Benchmark the XAG synthesizer on our invsqrt 57-bit table (Agent A)."""
import sys, time, pickle, itertools
sys.path.insert(0, '/home/user/Javascript-repo/quantum-kaggle/tools/invsqrt')
sys.path.insert(0, '/home/user/Javascript-repo/quantum-kaggle/tools/xag')
import model as M, xag

def table_targets(path):
    p = M.P(); key, tabs = pickle.load(open(path, 'rb'))
    lay, info = M.layout(p, tabs)
    widths = [info['RB'], info['wC'], p.w2, info['LB'], info['wH']]
    words = {}
    for (e, a), (k2, c, r0, h, l0) in lay.items(): words[a + 128 * e] = (r0, c, k2, l0, h)
    T = []
    for fi, w in enumerate(widths):
        for bit in range(w):
            v = 0
            for pt in range(256):
                if (words[pt][fi] >> bit) & 1: v |= 1 << pt
            T.append(v)
    return T

def anf(v, n=8):
    tt = [(v >> i) & 1 for i in range(1 << n)]
    for i in range(n):
        s = 1 << i
        for j in range(1 << n):
            if j & s: tt[j] ^= tt[j ^ s]
    return tt

if __name__ == '__main__':
    T = table_targets(sys.argv[1])
    keep = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    hdeg = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    order = sorted(range(len(T)), key=lambda i: sum(anf(T[i])))
    if hdeg >= 0:
        helpers = [c for d in range(2, hdeg + 1) for c in itertools.combinations(range(8), d)] if hdeg else []
    else:   # -1: all monomials of the low 4 and of the high 4 inputs (22 ANDs)
        helpers = [c for grp in (range(0, 4), range(4, 8)) for d in range(2, 5) for c in itertools.combinations(grp, d)]
    t0 = time.time()
    r = xag.synthesize(T, 8, seed=seed, keep_from=keep, helpers=helpers, order=order)
    xag.verify(r, T)
    print('keep_from', keep, 'helpers deg<=', hdeg, 'seed', seed, 'ANDs', r['ands'], 'wires', r['nwires'],
          'time', round(time.time() - t0), 'costs', r['costs'])
