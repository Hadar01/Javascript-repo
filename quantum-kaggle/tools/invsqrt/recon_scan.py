"""Erase -> reconstruct pairs and qubit slack (Agent A).

Sampled simulation (random x, random coins).  For every unconditional HMR with a nonzero erased value v,
find the first later op, right after a Toffoli-like write at condition depth 0, where v is GF(2)-linear in the
live wires again (the value has been reconstructed, possibly in a different linear form).  Also records the
live-qubit profile (wires nonzero on any sampled lane, at depth 0), so that for each pair we know the minimum
slack (62 - live) over the interval: slack >= 1 everywhere means the value could have been kept instead.
usage: python recon_scan.py circuit.kmx out.json [window] [n_sample]"""
import sys, json, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
from branch_spec import Span
MAXX = 3133452; W = 22; QMAX = 62
q = lambda a: int(a[1:])


def main(path, out, window=4000, n=8192, seed=21):
    ops = load(path)
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
    live = np.zeros(len(ops), np.int16)
    pend = {}; pairs = []
    for k, (op, args, cond) in enumerate(ops):
        nzl = int(sum(1 for w in range(nq) if S[w].any()))
        live[k] = nzl
        act = stack[-1] if cond is None else stack[-1] & B[q(cond)]
        if op == 'PUSH_CONDITION': stack.append(act); continue
        if op == 'POP_CONDITION':
            if len(stack) > 1: stack.pop()
            continue
        a = [q(x) for x in args if x.startswith('q')]
        if op == 'X': S[a[0]] ^= act
        elif op == 'CX': S[a[1]] ^= S[a[0]] & act
        elif op == 'SWAP':
            d = (S[a[0]] ^ S[a[1]]) & act; S[a[0]] ^= d; S[a[1]] ^= d
        elif op == 'CCX': S[a[2]] ^= S[a[0]] & S[a[1]] & act
        elif op == 'CSWAP':
            d = (S[a[1]] ^ S[a[2]]) & act & S[a[0]]; S[a[1]] ^= d; S[a[2]] ^= d
        elif op == 'HMR':
            v = S[a[0]] & act
            if len(stack) == 1 and cond is None and v.any() and not (v == full).all():
                pend[k] = (toint(v), a[0])
            coin = crng.integers(0, 2**63, size=nw, dtype=np.uint64) ^ (crng.integers(0, 2, size=nw, dtype=np.uint64) << np.uint64(63))
            b = q(args[1]); B[b] = (B[b] & ~act) | (coin & act); S[a[0]] &= ~act
        elif op == 'R': S[a[0]] &= ~act
        elif op == 'BIT_INVERT': B[q(args[0])] = B[q(args[0])] ^ act
        elif op == 'BIT_STORE0': B[q(args[0])] = B[q(args[0])] & ~act
        elif op == 'BIT_STORE1': B[q(args[0])] = B[q(args[0])] | act
        if op in ('CCX', 'CSWAP') and len(stack) == 1 and cond is None and pend:
            for h in [h for h in pend if k - h > window]: del pend[h]
            sp = Span(); sp.add(one, '1')
            for w in range(nq):
                if S[w].any(): sp.add(toint(S[w]), w)
            for h in list(pend):
                e = sp.express(pend[h][0])
                if e is not None:
                    pairs.append(dict(hmr=h, wire=pend[h][1], recon=k, gate=' '.join([op] + args), nterms=len(e)))
                    del pend[h]
        if k % 5000 == 0: print('op', k, 'pending', len(pend), 'pairs', len(pairs), flush=True)
    for p in pairs:
        seg = live[p['hmr'] + 1:p['recon'] + 1]
        p['max_live'] = int(seg.max()) if len(seg) else 0
        p['min_slack'] = QMAX - p['max_live']
    np.save(out.replace('.json', '_live.npy'), live)
    json.dump(pairs, open(out, 'w'))
    ok = [p for p in pairs if p['min_slack'] >= 1]
    print('pairs', len(pairs), 'with slack>=1 over the whole interval', len(ok))
    for p in ok: print(p)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], *(int(x) for x in sys.argv[3:]))
