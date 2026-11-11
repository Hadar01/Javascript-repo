"""Clifford-reducibility scan of Toffoli-like gates against ALL live wires (Agent A).

Sampled simulation (random x, random coins).  At every CCZ (conditional or not) test whether its phase
a*b*c, restricted to the lanes that execute it, is quadratic in the live wires (then CZ/Z gates suffice);
at every CCX test whether a*b is GF(2)-linear in the live wires other than the target (then CNOTs suffice).
Sample positives are reported for an exact all-x re-check.
usage: python cond_quad.py circuit.kmx out.json [n_sample]"""
import sys, json, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
from branch_spec import Span
MAXX = 3133452; W = 22
q = lambda a: int(a[1:])


def main(path, out, n=16384, seed=31):
    ops = load(path)
    nq = 1 + max(int(a[1:]) for _, args, _ in ops for a in args if a.startswith('q'))
    rng = np.random.default_rng(seed)
    # stratified: every x <= n/2 (rare leading-zero paths) plus random others
    small = np.arange(1, n // 2 + 1, dtype=np.uint64)
    xs = np.sort(np.concatenate([small, rng.choice(np.arange(n // 2 + 1, MAXX + 1, dtype=np.uint64), n // 2, replace=False)]))
    nw = n // 64
    pack = lambda bits: np.packbits(bits.astype(np.uint8), bitorder='little').view(np.uint64).copy()
    full = pack(np.ones(n)); S = np.zeros((nq, nw), np.uint64)
    for i in range(W): S[i] = pack((xs >> np.uint64(i)) & np.uint64(1))
    zero = np.zeros(nw, np.uint64)
    class Bits(dict):
        def __missing__(self, k): return zero
    B = Bits(); crng = np.random.default_rng(seed + 1); stack = [full]
    unp = lambda v: np.unpackbits(v.view(np.uint8), bitorder='little')
    toint = lambda bits: int.from_bytes(np.packbits(bits, bitorder='little').tobytes(), 'little')
    hits = []; ntest = 0
    for k, (op, args, cond) in enumerate(ops):
        act = stack[-1] if cond is None else stack[-1] & B[q(cond)]
        if op == 'PUSH_CONDITION': stack.append(act); continue
        if op == 'POP_CONDITION':
            if len(stack) > 1: stack.pop()
            continue
        a = [q(x) for x in args if x.startswith('q')]
        if op in ('CCZ', 'CCX') and act.any():
            m = unp(act).astype(bool)
            if op == 'CCZ': f = S[a[0]] & S[a[1]] & S[a[2]]; excl = set()
            else: f = S[a[0]] & S[a[1]]; excl = {a[2]}
            fv = unp(f)[m]
            cols = [w for w in range(nq) if w not in excl and (unp(S[w])[m]).any()]
            V = [(w, unp(S[w])[m]) for w in cols]
            sp = Span(); sp.add(toint(np.ones(m.sum(), np.uint8)), '1')
            for w, x in V: sp.add(toint(x), w)
            le = sp.express(toint(fv)); lin = le is not None
            quad = None
            if op == 'CCZ' and not lin:
                for i in range(len(V)):
                    for j in range(i + 1, len(V)): sp.add(toint(V[i][1] & V[j][1]), (V[i][0], V[j][0]))
                qe = sp.express(toint(fv)); quad = qe is not None
            ntest += 1
            freq = float(m.mean())
            if lin or quad:
                h = dict(op=k, gate=' '.join([op] + args), cond=cond, depth=len(stack) - 1, freq=freq,
                         lanes=int(m.sum()), linear=lin, quadratic=quad,
                         expr=[str(t) for t in (le if lin else qe)])
                hits.append(h); print('HIT', h, flush=True)
        if op == 'X': S[a[0]] ^= act
        elif op == 'CX': S[a[1]] ^= S[a[0]] & act
        elif op == 'SWAP':
            d = (S[a[0]] ^ S[a[1]]) & act; S[a[0]] ^= d; S[a[1]] ^= d
        elif op == 'CCX': S[a[2]] ^= S[a[0]] & S[a[1]] & act
        elif op == 'CSWAP':
            d = (S[a[1]] ^ S[a[2]]) & act & S[a[0]]; S[a[1]] ^= d; S[a[2]] ^= d
        elif op == 'HMR':
            coin = crng.integers(0, 2**63, size=nw, dtype=np.uint64) ^ (crng.integers(0, 2, size=nw, dtype=np.uint64) << np.uint64(63))
            b = q(args[1]); B[b] = (B[b] & ~act) | (coin & act); S[a[0]] &= ~act
        elif op == 'R': S[a[0]] &= ~act
        elif op == 'BIT_INVERT': B[q(args[0])] = B[q(args[0])] ^ act
        elif op == 'BIT_STORE0': B[q(args[0])] = B[q(args[0])] & ~act
        elif op == 'BIT_STORE1': B[q(args[0])] = B[q(args[0])] | act
    print('tested', ntest, 'hits', len(hits))
    json.dump(hits, open(out, 'w'))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], *(int(x) for x in sys.argv[3:]))
