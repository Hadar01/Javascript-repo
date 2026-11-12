"""Can an idle wire be freed over its idle interval? (Agent A)

For each candidate (wire w, idle interval [s, e]) the value v of w is constant over [s, e].  Test, on a
stratified sample (all x <= n/2 plus random others) and then exactly on all x for positives:
  at s : v linear in the other live wires  -> erase by CNOTs (0 Toffolis)
         v quadratic                       -> erase by HMR + CZ fix-up (0 Toffolis)
  at e : v linear in the other live wires  -> restore by CNOTs (0 Toffolis)
         v quadratic (rank reported)       -> restore with about rank/2 Toffolis
usage: python idle_free.py circuit.kmx w:s:e [w:s:e ...]"""
import sys, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
from winsynth import record_states
from branch_spec import Span, toint
MAXX = 3133452; W = 22


def test(U, w, quad=True):
    nq = U.shape[0]; m = U.shape[1]
    others = [i for i in range(nq) if i != w and U[i].any()]
    sp = Span(); one = np.ones(m, np.uint8); sp.add(toint(one), '1')
    for i in others: sp.add(toint(U[i]), 'q%d' % i)
    e = sp.express(toint(U[w]))
    if e is not None: return 'linear', e
    if not quad: return None, None
    for a in range(len(others)):
        for b in range(a + 1, len(others)):
            sp.add(toint(U[others[a]] & U[others[b]]), 'q%d*q%d' % (others[a], others[b]))
    e = sp.express(toint(U[w]))
    return ('quadratic', e) if e is not None else (None, None)


def rank1(U, w):
    """Is v = L0 ^ (l1 . L2) with l1 a single live wire (or its complement) and L0, L2 linear in the other
    live wires?  Then one CCX restores v.  Solved as a GF(2) system per choice of l1."""
    nq = U.shape[0]; m = U.shape[1]
    others = [i for i in range(nq) if i != w and U[i].any()]
    v = U[w]; one = np.ones(m, np.uint8)
    for l1w in others:
        for pol in (0, 1):
            l1 = U[l1w] ^ pol
            # unknown coefficient vector over cols0 (L0) and cols2 (L2): lanes where l1=0 -> L0 = v ;
            # lanes where l1=1 -> L0 ^ L2 = v.  Build columns as lane-vectors.
            cols = [U[i] for i in others] + [one]
            colsB = [c & l1 for c in cols]
            sp = Span()
            for i, c in enumerate(cols): sp.add(toint(c), ('a', i))
            for i, c in enumerate(colsB): sp.add(toint(c), ('b', i))
            if sp.express(toint(v)) is not None:
                return 'q%d%s' % (l1w, "'" if pol else '')
    return None


def main(path, cands, n=12288):
    ops = load(path)
    C = [tuple(int(x) for x in c.split(':')) for c in cands]
    rng = np.random.default_rng(17)
    small = np.arange(1, n // 2 + 1, dtype=np.uint64)
    xs = np.sort(np.concatenate([small, rng.choice(np.arange(n // 2 + 1, MAXX + 1, dtype=np.uint64), n // 2, replace=False)]))
    at = set()
    for w, s, e in C: at.add(s); at.add(e)
    V, nn = record_states(ops, xs, 1, at)
    unp = lambda S: np.unpackbits(S.view(np.uint8), axis=1, bitorder='little')[:, :nn]
    for w, s, e in C:
        r = []
        for k in (s, e):
            kind, ex = test(unp(V[k]), w)
            r.append((kind, len(ex) if ex else None))
        r1 = rank1(unp(V[e]), w) if r[1][0] != 'linear' else 'n/a'
        print('q%d idle %d-%d : at start %s, at end %s, one-CCX restore at end via %s' % (w, s, e, r[0], r[1], r1), flush=True)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
