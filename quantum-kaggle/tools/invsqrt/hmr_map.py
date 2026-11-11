"""Measurement-boundary map of an invsqrt kickmix circuit (Agent A).

Bit-packed simulation over a random sample of x (with random HMR coins).  For every HMR:
  * the erased wire, its execution frequency, and whether the erased value is identically 0 on the lanes
    that execute it ("zero erase": no kick, no fix-up needed);
  * the fix-up: every later op whose condition (own `if` bit or an enclosing PUSH_CONDITION) has this HMR in
    its provenance (bits derived through BIT_INVERT/BIT_STORE under conditions inherit provenance);
    Toffoli-like gates are charged at their measured mean execution frequency to the most recent HMR of the
    innermost condition's provenance;
  * reconstruction: the first later op after which some wire holds the erased value again (or its
    complement), on the sampled lanes (unconditional HMRs only).
Writes a JSON list (one record per HMR) and prints a ranking.
usage: python hmr_map.py circuit.kmx out.json [n_sample]"""
import sys, json, hashlib, collections, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load
MAXX = 3133452; W = 22
q = lambda a: int(a[1:])
TOFF = ('CCX', 'CCZ', 'CSWAP')


def main(path, out, n=1 << 16, seed=3):
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
    B = Bits(); crng = np.random.default_rng(seed + 6)
    prov = collections.defaultdict(frozenset)          # bit -> HMR ops determining it
    stack = [(full, frozenset(), None)]                # (active mask, provenance of conditions, innermost cond prov)
    pc = lambda v: int(np.unpackbits(v.view(np.uint8)).sum())
    H = {}                                              # hmr op -> record
    CT = []                                             # conditional Toffoli-like gates
    pending = {}                                        # value hash -> hmr op (reconstruction search)
    hv = lambda v: hashlib.blake2b(v.tobytes(), digest_size=12).digest()
    for k, (op, args, cond) in enumerate(ops):
        top_act, top_prov, top_inner = stack[-1]
        act = top_act if cond is None else top_act & B[q(cond)]
        inner = top_inner if cond is None else prov[q(cond)]
        allprov = top_prov if cond is None else top_prov | prov[q(cond)]
        if op == 'PUSH_CONDITION':
            stack.append((act, allprov, inner)); continue
        if op == 'POP_CONDITION':
            if len(stack) > 1: stack.pop()
            continue
        conditioned = len(stack) > 1 or cond is not None
        # fix-up bookkeeping
        if conditioned and inner:
            f = pc(act) / n
            last = max(inner)
            r = H.get(last)
            if op in TOFF: CT.append(dict(op=k, freq=f, inner=sorted(inner), outer=sorted(allprov - inner)))
            if r is not None:
                if op in TOFF: r['fix_toff'] += f; r['fix_toff_ops'].append(k)
                elif op not in ('BIT_INVERT', 'BIT_STORE0', 'BIT_STORE1'): r['fix_cliff'] += 1
                r['fix_last'] = k
        a = [q(x) for x in args if x.startswith('q')]
        if op == 'X': S[a[0]] ^= act
        elif op == 'CX': S[a[1]] ^= S[a[0]] & act
        elif op == 'SWAP':
            d = (S[a[0]] ^ S[a[1]]) & act; S[a[0]] ^= d; S[a[1]] ^= d
        elif op == 'CCX': S[a[2]] ^= S[a[0]] & S[a[1]] & act
        elif op == 'CSWAP':
            d = (S[a[1]] ^ S[a[2]]) & act & S[a[0]]; S[a[1]] ^= d; S[a[2]] ^= d
        elif op == 'HMR':
            w, b = a[0], q(args[1])
            v = S[w] & act
            f = pc(act) / n
            nz = bool(v.any())
            H[k] = dict(op=k, wire=w, bit=b, freq=round(f, 4), conditioned=conditioned, zero=not nz,
                        ones=round(pc(v) / max(1, pc(act)), 4), fix_toff=0.0, fix_toff_ops=[], fix_cliff=0,
                        fix_last=None, recon=None, prev_toff=None)
            # nearest preceding Toffoli that wrote this wire
            for j in range(k - 1, max(-1, k - 400), -1):
                oj, aj, cj = ops[j]
                if oj in ('CCX', 'CSWAP') and ('q%d' % w) in aj[-2:]:
                    H[k]['prev_toff'] = j; break
            if nz and not conditioned:
                for hh in (hv(v), hv(v ^ full)): pending.setdefault(hh, []).append(k)
            coin = crng.integers(0, 2**63, size=nw, dtype=np.uint64) ^ (crng.integers(0, 2, size=nw, dtype=np.uint64) << np.uint64(63))
            B[b] = (B[b] & ~act) | (coin & act); S[w] &= ~act
            prov[b] = frozenset([k])
        elif op == 'R': S[a[0]] &= ~act
        elif op == 'BIT_INVERT':
            b = q(args[0]); B[b] = B[b] ^ act; prov[b] = prov[b] | allprov
        elif op == 'BIT_STORE0':
            b = q(args[0]); B[b] = B[b] & ~act; prov[b] = (prov[b] | allprov) if conditioned else frozenset()
        elif op == 'BIT_STORE1':
            b = q(args[0]); B[b] = B[b] | act; prov[b] = (prov[b] | allprov) if conditioned else frozenset()
        # reconstruction search on written wires
        if op in ('X', 'CX', 'SWAP', 'CCX', 'CSWAP') and pending:
            for w in (a[-2:] if op in ('SWAP', 'CSWAP') else a[-1:]):
                hh = hv(S[w])
                if hh in pending:
                    for h0 in pending.pop(hh):
                        if H[h0]['recon'] is None: H[h0]['recon'] = dict(op=k, wire=w, gate=op, depth=len(stack) - 1)
    recs = [H[k] for k in sorted(H)]
    json.dump(recs, open(out, 'w'))
    json.dump(CT, open(out.replace('.json', '_ct.json'), 'w'))
    tot = sum(r['fix_toff'] for r in recs)
    print('HMR', len(recs), 'zero-erase', sum(r['zero'] for r in recs), 'conditioned', sum(r['conditioned'] for r in recs),
          'with Toffoli fix-up', sum(1 for r in recs if r['fix_toff'] > 0), 'mean fix-up Toffolis %.2f' % tot)
    for r in sorted(recs, key=lambda r: -r['fix_toff'])[:40]:
        print(r['op'], 'q%d->b%d' % (r['wire'], r['bit']), 'freq', r['freq'], 'fixToff %.3f' % r['fix_toff'],
              'n', len(r['fix_toff_ops']), 'first', r['fix_toff_ops'][:3], 'cliff', r['fix_cliff'], 'recon', r['recon'])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1 << 16)
