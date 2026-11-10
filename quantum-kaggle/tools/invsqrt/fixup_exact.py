"""Exact version of fixup_scan (Agent A): reachable patterns of each block's wires are taken over ALL x and
the union of several coin seeds, ignoring whether the block fires (a sound superset, since coins are
independent of x).  Tests per innermost Clifford+Toffoli conditional block:
  (a) value change (out xor in) GF(2)-affine in the block wires and phase quadratic -> 0 Toffolis
Saving = execution frequency (measured) x Toffolis.
usage: python fixup_exact.py circuit.kmx out.json [seeds]"""
import sys, json, itertools, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
from fixup_scan import innermost_blocks, gf2_solvable, TOFF
MAXX = 3133452; W = 22


def run(ops, blocks, seed):
    starts = {b[0]: b for b in blocks}
    nq = 1 + max(int(a[1:]) for _, args, _ in ops for a in args if a.startswith('q'))
    xs = np.arange(1, MAXX + 1, dtype=np.uint64); n = len(xs); nw = (n + 63) // 64
    def pack(bits):
        b = np.zeros(nw * 64, dtype=np.uint8); b[:n] = bits
        return np.packbits(b, bitorder='little').view(np.uint64).copy()
    unp = lambda v: np.unpackbits(v.view(np.uint8), bitorder='little')[:n]
    mask = pack(np.ones(n, dtype=np.uint8))
    S = np.zeros((nq, nw), np.uint64)
    for i in range(W): S[i] = pack(((xs >> np.uint64(i)) & np.uint64(1)).astype(np.uint8))
    zero = np.zeros(nw, np.uint64)
    class Bits(dict):
        def __missing__(self, k): return zero
    B = Bits(); stack = [mask]; crng = np.random.default_rng(seed)
    q = lambda a: int(a[1:])
    out = {}
    for k, (op, args, cond) in enumerate(ops):
        act = stack[-1] if cond is None else stack[-1] & B[q(cond)]
        if op == 'PUSH_CONDITION':
            stack.append(act)
            if k in starts:
                k0, k1, body, T = starts[k]
                bw = sorted(set(q(x) for j in body for x in ops[j][1] if x.startswith('q')))
                pid = np.zeros(n, np.int64)
                for i, w in enumerate(bw): pid |= unp(S[w]).astype(np.int64) << i
                out[k] = (bw, np.unique(pid), float(unp(act).mean()))
            continue
        if op == 'POP_CONDITION':
            if len(stack) > 1: stack.pop()
            continue
        if op == 'X': S[q(args[0])] ^= act
        elif op == 'CX': S[q(args[1])] ^= S[q(args[0])] & act
        elif op == 'SWAP':
            a, b = q(args[0]), q(args[1]); d = (S[a] ^ S[b]) & act; S[a] ^= d; S[b] ^= d
        elif op == 'CCX':
            a, b, t = map(q, args); S[t] ^= S[a] & S[b] & act
        elif op == 'CSWAP':
            c, a, b = map(q, args); d = (S[a] ^ S[b]) & act & S[c]; S[a] ^= d; S[b] ^= d
        elif op == 'HMR':
            t = q(args[0]); coin = crng.integers(0, 2**63, size=nw, dtype=np.uint64) ^ (crng.integers(0, 2, size=nw, dtype=np.uint64) << np.uint64(63))
            B[q(args[1])] = (B[q(args[1])] & ~act) | (coin & act); S[t] &= ~act
        elif op == 'R': S[q(args[0])] &= ~act
        elif op == 'BIT_INVERT': B[q(args[0])] = B[q(args[0])] ^ act
        elif op == 'BIT_STORE0': B[q(args[0])] = B[q(args[0])] & ~act
        elif op == 'BIT_STORE1': B[q(args[0])] = B[q(args[0])] | act
    return out


def main(path, outp, seeds=3):
    ops = load(path); blocks = innermost_blocks(ops)
    acc = {}
    for sd in range(seeds):
        r = run(ops, blocks, 100 + sd)
        for k, (bw, pats, f) in r.items():
            if k not in acc: acc[k] = [bw, set(pats.tolist()), [f]]
            else: acc[k][1] |= set(pats.tolist()); acc[k][2].append(f)
    q = lambda a: int(a[1:])
    report = []; hits = []
    for k0, k1, body, T in blocks:
        if k0 not in acc: continue
        bw, pats, fr = acc[k0]; freq = float(np.mean(fr))
        pats = np.array(sorted(pats), np.int64); m = len(bw); idx = {w: i for i, w in enumerate(bw)}
        cur = pats.copy(); ph = np.zeros(len(pats), np.int64)
        bit = lambda v, w: (v >> idx[w]) & 1
        for j in body:
            op, args, _ = ops[j]; a = [q(x) for x in args]
            if op == 'X': cur ^= 1 << idx[a[0]]
            elif op == 'CX': cur ^= bit(cur, a[0]) << idx[a[1]]
            elif op == 'SWAP':
                d = bit(cur, a[0]) ^ bit(cur, a[1]); cur ^= (d << idx[a[0]]) | (d << idx[a[1]])
            elif op == 'CCX': cur ^= (bit(cur, a[0]) & bit(cur, a[1])) << idx[a[2]]
            elif op == 'CSWAP':
                d = bit(cur, a[0]) & (bit(cur, a[1]) ^ bit(cur, a[2])); cur ^= (d << idx[a[1]]) | (d << idx[a[2]])
            elif op == 'Z': ph ^= bit(cur, a[0])
            elif op == 'CZ': ph ^= bit(cur, a[0]) & bit(cur, a[1])
            elif op == 'CCZ': ph ^= bit(cur, a[0]) & bit(cur, a[1]) & bit(cur, a[2])
            elif op == 'NEG': ph ^= 1
        coord = [((pats >> i) & 1).astype(np.uint8) for i in range(m)]
        lin = [np.ones(len(pats), np.uint8)] + coord
        quad = lin + [coord[i] & coord[j] for i, j in itertools.combinations(range(m), 2)]
        delta = cur ^ pats
        dl = [((delta >> i) & 1).astype(np.uint8) for i in range(m)]
        affine = all(gf2_solvable(np.stack(lin).T, d) for d in dl)
        qp = gf2_solvable(np.stack(quad).T, ph.astype(np.uint8))
        info = dict(k0=k0, T=T, freq=round(freq, 4), mean_toff=round(freq * T, 4), wires=m,
                    patterns=int(len(pats)), affine_values=affine, quadratic_phase=qp)
        report.append(info)
        if affine and qp:
            hits.append(info); print('HIT', info, flush=True)
    report.sort(key=lambda r: -r['mean_toff'])
    json.dump(dict(hits=hits, blocks=report), open(outp, 'w'), indent=0)
    print('blocks', len(report), 'hits', len(hits), 'mean Toffolis covered', round(sum(r['mean_toff'] for r in report), 2))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 3)
