"""Conditional fix-up block scan with reachable-state phase resynthesis (Agent A).

For every innermost classically-conditioned block (PUSH_CONDITION ... POP_CONDITION with no nested condition
and no HMR/R/Z_POW inside) that contains Toffoli-like gates:
  * simulate the circuit (bit-packed) on sample states with random coins; at the block start record the
    state and the set of lanes where the block executes;
  * evaluate the block on those lanes: output values and phase parity;
  * if the block is value-neutral and its phase function lies in the GF(2) span of
    {1, wires, products of two wires} (on the executing lanes), all its Toffolis can be replaced by Z/CZ
    gates under the same condition.  Saving = execution frequency x Toffolis in the block.
Hits are re-checked exactly on all x by the caller.
usage: python fixup_scan.py circuit.kmx out.json [nsmall nbig]"""
import sys, json, itertools, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
MAXX = 3133452; W = 22
TOFF = ('CCX', 'CSWAP', 'CCZ')
OK = ('X', 'CX', 'SWAP', 'CCX', 'CSWAP', 'Z', 'CZ', 'CCZ', 'NEG')


def innermost_blocks(ops):
    res = []; stack = []
    for k, (op, args, cond) in enumerate(ops):
        if op == 'PUSH_CONDITION':
            stack.append([k, False])
            if len(stack) > 1: stack[-2][1] = True     # parent has a nested block
        elif op == 'POP_CONDITION' and stack:
            k0, nested = stack.pop()
            if nested: continue
            body = list(range(k0 + 1, k))
            if any(ops[j][0] not in OK or ops[j][2] is not None for j in body): continue
            T = sum(1 for j in body if ops[j][0] in TOFF)
            if T: res.append((k0, k, body, T))
    return res


def main(path, out, nsmall=16384, nbig=16384, seed=5):
    ops = load(path)
    blocks = innermost_blocks(ops)
    starts = {b[0]: b for b in blocks}
    nq = 1 + max(int(a[1:]) for _, args, _ in ops for a in args if a.startswith('q'))
    rng = np.random.default_rng(seed)
    xs = np.sort(np.concatenate([np.arange(1, nsmall + 1, dtype=np.uint64),
                                 rng.choice(np.arange(nsmall + 1, MAXX + 1, dtype=np.uint64), nbig, replace=False)]))
    n = len(xs); nw = (n + 63) // 64
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
    B = Bits(); stack = [mask]; crng = np.random.default_rng(seed + 7)
    q = lambda a: int(a[1:])
    rec = {}
    for k, (op, args, cond) in enumerate(ops):
        act = stack[-1] if cond is None else stack[-1] & B[q(cond)]
        if op == 'PUSH_CONDITION':
            stack.append(act)
            if k in starts: rec[k] = (S.copy(), act.copy())
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
    hits = []; report = []
    for k0, k1, body, T in blocks:
        if k0 not in rec: continue
        S0, act = rec[k0]
        lanes = np.flatnonzero(unp(act))
        freq = len(lanes) / n
        if len(lanes) == 0: continue
        vals = np.stack([unp(S0[i])[lanes] for i in range(nq)]).astype(np.uint8)   # nq x L
        cur = vals.copy(); ph = np.zeros(len(lanes), np.uint8)
        for j in body:
            op, args, _ = ops[j]; a = [q(x) for x in args]
            if op == 'X': cur[a[0]] ^= 1
            elif op == 'CX': cur[a[1]] ^= cur[a[0]]
            elif op == 'SWAP': cur[[a[0], a[1]]] = cur[[a[1], a[0]]]
            elif op == 'CCX': cur[a[2]] ^= cur[a[0]] & cur[a[1]]
            elif op == 'CSWAP':
                d = cur[a[0]] & (cur[a[1]] ^ cur[a[2]]); cur[a[1]] ^= d; cur[a[2]] ^= d
            elif op == 'Z': ph ^= cur[a[0]]
            elif op == 'CZ': ph ^= cur[a[0]] & cur[a[1]]
            elif op == 'CCZ': ph ^= cur[a[0]] & cur[a[1]] & cur[a[2]]
            elif op == 'NEG': ph ^= 1
        neutral = bool((cur == vals).all())
        info = dict(k0=k0, k1=k1, T=T, freq=round(freq, 4), mean_toff=round(freq * T, 3), neutral=neutral)
        if neutral:
            bw = sorted(set(q(x) for j in body for x in ops[j][1] if x.startswith('q')))
            live = [i for i in bw if vals[i].any() and not vals[i].all()]
            # dedupe reachable patterns of the block wires
            pat = np.stack([vals[i] for i in live] + [ph]).T if live else ph[:, None]
            up, inv = np.unique(pat[:, :-1], axis=0, return_inverse=True) if live else (None, None)
            if live:
                inv = inv.reshape(-1)
                phu = np.zeros(len(up), np.int64) - 1
                consistent = True
                for r, pv in zip(inv, ph):
                    if phu[r] < 0: phu[r] = pv
                    elif phu[r] != pv: consistent = False; break
                info['patterns'] = int(len(up)); info['block_wires'] = len(live)
                if not consistent:
                    info['quad_phase'] = False; report.append(info); continue
                vals_u = up.T.astype(np.uint8); ph = phu.astype(np.uint8)
                lanes_u = len(up)
            cols0 = None
            if not live:
                info['quad_phase'] = not ph.any() or ph.all()
                if info['quad_phase']: hits.append(info)
                report.append(info); continue
            V = vals_u
            cols = [np.ones(lanes_u, np.uint8)] + [V[i] for i in range(len(live))] + \
                   [V[i] & V[j] for i, j in itertools.combinations(range(len(live)), 2)]
            A = np.stack(cols).T.astype(np.uint8)         # P x m
            info['quad_phase'] = gf2_solvable(A, ph)
            if info['quad_phase']:
                hits.append(info); print('HIT', info, flush=True)
        report.append(info)
    report.sort(key=lambda r: -r['mean_toff'])
    json.dump(dict(hits=hits, blocks=report), open(out, 'w'), indent=0)
    print('innermost Clifford+Toffoli conditional blocks:', len(blocks), 'evaluated', len(report),
          'value-neutral', sum(r['neutral'] for r in report), 'hits', len(hits),
          'total mean Toffolis in these blocks', round(sum(r['mean_toff'] for r in report), 2))


def gf2_solvable(A, b):
    """Is A c = b solvable over GF(2)?  A: L x m uint8, b: L uint8.  Row-reduce on bit-packed columns."""
    L, m = A.shape
    M = np.concatenate([A, b[:, None]], 1).astype(np.uint8)
    Mp = np.packbits(M, axis=1, bitorder='little').view(np.uint8)
    # work column by column on the unpacked matrix but with boolean rows (L can be ~20k, m ~2000)
    M = M.astype(bool)
    r = 0
    for c in range(m):
        if r >= L: break
        rows = np.flatnonzero(M[r:, c])
        if len(rows) == 0: continue
        p = rows[0] + r
        if p != r: M[[r, p]] = M[[p, r]]
        sel = np.flatnonzero(M[:, c]); sel = sel[sel != r]
        if len(sel): M[sel] ^= M[r]
        r += 1
    # inconsistent if any row has zeros in A part but 1 in b
    return not np.any(M[r:, m])


if __name__ == '__main__':
    a = sys.argv
    main(a[1], a[2], *(int(v) for v in a[3:5]))
