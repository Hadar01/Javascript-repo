"""Deferred-kick search (Agent A): can an HMR's costly fix-up be replaced by a free (Clifford) phase later?

For every unconditional HMR whose fix-up (ops conditioned on its bit, see hmr_map.py) contains Toffoli-like
gates, take the erased value v (function of x on the sampled lanes).  Walk forward through the circuit; at
every depth-0 op test whether v is GF(2)-linear in the live wires (then the kick can be repaid there with Z
gates), and at a coarser grid whether v is quadratic (CZ gates).  The earliest such op is reported.
Positives are sample-level only; they must be re-checked on all x before any use.
usage: python kick_defer.py circuit.kmx hmr.json out.json [grid] [n_sample]"""
import sys, json, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
from branch_spec import Span
MAXX = 3133452; W = 22
q = lambda a: int(a[1:])


def main(path, hmr_path, out, grid=500, n=16384, seed=11):
    ops = load(path)
    R = {r['op']: r for r in json.load(open(hmr_path))}
    split = {18662, 18705, 18631}
    targets = {k for k, r in R.items() if r['fix_toff'] > 0 and not r['conditioned'] and not r['zero']}
    nq = 1 + max(int(a[1:]) for _, args, _ in ops for a in args if a.startswith('q'))
    rng = np.random.default_rng(seed)
    xs = np.sort(rng.choice(np.arange(1, MAXX + 1, dtype=np.uint64), n, replace=False)); nw = n // 64
    pack = lambda bits: np.packbits(bits.astype(np.uint8), bitorder='little').view(np.uint64).copy()
    full = pack(np.ones(n)); S = np.zeros((nq, nw), np.uint64)
    for i in range(W): S[i] = pack((xs >> np.uint64(i)) & np.uint64(1))
    zero = np.zeros(nw, np.uint64)
    class Bits(dict):
        def __missing__(self, k): return zero
    B = Bits(); crng = np.random.default_rng(seed + 1); stack = [full]
    toint = lambda v: int.from_bytes(v.tobytes(), 'little')
    one = toint(full)
    pend = {}; found = {}
    dirty = True
    for k, (op, args, cond) in enumerate(ops):
        depth = len(stack) - 1
        if depth == 0 and cond is None and pend and dirty:
            live = [w for w in range(nq) if S[w].any()]
            sp = Span(); sp.add(one, '1')
            for w in live: sp.add(toint(S[w]), w)
            for h in list(pend):
                e = sp.express(pend[h])
                if e is not None:
                    found[h] = dict(op=k, kind='linear', terms=['1' if t == '1' else 'q%d' % t for t in e]); del pend[h]
            if k % grid == 0 and pend:
                V = [(w, S[w]) for w in live]
                for i in range(len(V)):
                    for j in range(i + 1, len(V)): sp.add(toint(V[i][1] & V[j][1]), (V[i][0], V[j][0]))
                for h in list(pend):
                    e = sp.express(pend[h])
                    if e is not None:
                        found[h] = dict(op=k, kind='quadratic', nterms=len(e)); del pend[h]
            dirty = False
        act = stack[-1] if cond is None else stack[-1] & B[q(cond)]
        if op == 'PUSH_CONDITION': stack.append(act); continue
        if op == 'POP_CONDITION':
            if len(stack) > 1: stack.pop()
            continue
        a = [q(x) for x in args if x.startswith('q')]
        if op in ('X', 'CX', 'SWAP', 'CCX', 'CSWAP', 'HMR', 'R'): dirty = True
        if op == 'X': S[a[0]] ^= act
        elif op == 'CX': S[a[1]] ^= S[a[0]] & act
        elif op == 'SWAP':
            d = (S[a[0]] ^ S[a[1]]) & act; S[a[0]] ^= d; S[a[1]] ^= d
        elif op == 'CCX': S[a[2]] ^= S[a[0]] & S[a[1]] & act
        elif op == 'CSWAP':
            d = (S[a[1]] ^ S[a[2]]) & act & S[a[0]]; S[a[1]] ^= d; S[a[2]] ^= d
        elif op == 'HMR':
            if k in targets: pend[k] = toint(S[a[0]])
            coin = crng.integers(0, 2**63, size=nw, dtype=np.uint64) ^ (crng.integers(0, 2, size=nw, dtype=np.uint64) << np.uint64(63))
            b = q(args[1]); B[b] = (B[b] & ~act) | (coin & act); S[a[0]] &= ~act
        elif op == 'R': S[a[0]] &= ~act
        elif op == 'BIT_INVERT': B[q(args[0])] = B[q(args[0])] ^ act
        elif op == 'BIT_STORE0': B[q(args[0])] = B[q(args[0])] & ~act
        elif op == 'BIT_STORE1': B[q(args[0])] = B[q(args[0])] | act
    res = []
    for h in sorted(targets):
        r = R[h]; f = found.get(h)
        res.append(dict(hmr=h, wire=r['wire'], bit=r['bit'], fix_toff=r['fix_toff'], fix_first=r['fix_toff_ops'][:1],
                        split=h in split, defer=f))
        print(h, 'q%d->b%d' % (r['wire'], r['bit']), 'fixToff %.3f' % r['fix_toff'], 'fix at', r['fix_toff_ops'][:2],
              'split' if h in split else '', '->', f, flush=True)
    json.dump(res, open(out, 'w'))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3], *(int(x) for x in sys.argv[4:]))
