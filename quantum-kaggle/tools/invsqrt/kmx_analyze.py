"""Bit-packed value analysis of an invsqrt kmx circuit over all x in [1, max_x].

Simulates qubit VALUES only (phases ignored) with every classical condition forced TRUE and,
in lockstep, forced FALSE, to check that conditioned blocks are value-neutral.
For each Toffoli-like gate it reports whether it can be removed or downgraded on the legal domain:
  CCX/CCZ:  product never 1 -> delete;  product == c1 (or c2) everywhere -> CX/CZ from the other control
  CSWAP:    c & (a^b) never 1 -> delete;  (a^b) implies c -> SWAP (free)
usage: python kmx_analyze.py circuit.kmx out.json
"""
import sys, json, re, numpy as np
MAXX = 3133452; W = 22
import os
PROBE = set(int(v) for v in os.environ.get('PROBE','').split(',') if v)
PROBED = {}
LIVE = int(os.environ.get('LIVE', '0')); LIVEP = []
def load(path):
    ops = []
    for line in open(path):
        t = line.split()
        if not t: continue
        cond = None
        if len(t) >= 3 and t[-2] == 'if':
            cond = t[-1]; t = t[:-2]
        ops.append((t[0], t[1:], cond))
    return ops

def main(path, out, seeds=4):
    ops = load(path)
    nq = 1 + max(int(a[1:]) for _, args, _ in ops for a in args if a.startswith('q'))
    nb = 1 + max([int(a[1:]) for _, args, c in ops for a in args + ([c] if c else []) if a.startswith('b')] + [0])
    n = MAXX; nw = (n + 63) // 64
    xs = np.arange(1, n + 1, dtype=np.uint64)
    def pack(bits):
        b = np.zeros(nw * 64, dtype=np.uint8); b[:n] = bits
        return np.packbits(b.reshape(-1, 8)[:, ::-1], axis=1).reshape(nw, 8)[:, ::-1].copy().view(np.uint64).reshape(nw)
    mask = pack(np.ones(n, dtype=np.uint8))
    q = lambda a: int(a[1:])
    stats = {}
    def anyb(v): return bool(np.any(v))
    problems = []
    for seed in range(seeds):
        rng = np.random.default_rng(seed)
        S = [np.zeros(nw, np.uint64) for _ in range(nq)]
        for i in range(W):
            S[i] = pack(((xs >> np.uint64(i)) & np.uint64(1)).astype(np.uint8))
        x0 = [s.copy() for s in S[:W]]
        zero = np.zeros(nw, np.uint64)
        class Bits(dict):
            def __missing__(self, key): return zero
        B = Bits()
        stack = [mask]
        for k, (op, args, cond) in enumerate(ops):
            if k in PROBE and op in ('CCX','CCZ','CSWAP'):
                a_, b_ = q(args[0]), q(args[1])
                L = S[a_] & S[b_]
                t_ = q(args[2]); srcs = []
                for j in range(k - 1, max(0, k - 40), -1):
                    o2, a2, c2 = ops[j]
                    if o2 == 'CX' and q(a2[1]) == t_: srcs.append(q(a2[0]))
                    elif o2 not in ('CX', 'PUSH_CONDITION', 'POP_CONDITION'): break
                src_or = bool(any(np.any(S[j2] & L) for j2 in srcs))
                PROBED.setdefault(k, []).append(dict(nL=int(sum(bin(int(w)).count('1') for w in L)), src_nonzero=src_or,
                    t_zero=not np.any(S[t_] & L), t_one=not np.any(~S[t_] & L), srcs=srcs))
            act = stack[-1] if cond is None else stack[-1] & B[q(cond)]
            if seed == 0 and LIVE and k % LIVE == 0:
                LIVEP.append((k, ''.join('1' if np.any(S[i]) else '.' for i in range(nq))))
            if op == 'PUSH_CONDITION': stack.append(act); continue
            if op == 'POP_CONDITION':
                if len(stack) > 1: stack.pop()
                continue
            if op == 'X': S[q(args[0])] ^= act
            elif op == 'CX': S[q(args[1])] ^= S[q(args[0])] & act
            elif op == 'SWAP':
                a, b = q(args[0]), q(args[1]); d = (S[a] ^ S[b]) & act; S[a] ^= d; S[b] ^= d
            elif op == 'CCX':
                a, b, t = map(q, args)
                p = S[a] & S[b] & act
                r = stats.setdefault(k, dict(k=k, op=op, args=args, act=0, fire=0, ne_c1=0, ne_c2=0))
                r['act'] += anyb(act); r['fire'] += anyb(p)
                r['ne_c1'] += anyb((p ^ S[a]) & act); r['ne_c2'] += anyb((p ^ S[b]) & act)
                S[t] ^= p
            elif op == 'CCZ':
                a, b, c = map(q, args)
                p = S[a] & S[b] & S[c] & act
                r = stats.setdefault(k, dict(k=k, op=op, args=args, act=0, fire=0, ne_ab=0, ne_ac=0, ne_bc=0))
                r['act'] += anyb(act); r['fire'] += anyb(p)
                r['ne_ab'] += anyb((p ^ (S[a] & S[b])) & act); r['ne_ac'] += anyb((p ^ (S[a] & S[c])) & act)
                r['ne_bc'] += anyb((p ^ (S[b] & S[c])) & act)
            elif op == 'CSWAP':
                c, a, b = map(q, args)
                dif = (S[a] ^ S[b]) & act; d = S[c] & dif
                r = stats.setdefault(k, dict(k=k, op=op, args=args, act=0, fire=0, not_swap=0))
                r['act'] += anyb(act); r['fire'] += anyb(d); r['not_swap'] += anyb(dif & ~S[c])
                S[a] ^= d; S[b] ^= d
            elif op == 'HMR':
                t = q(args[0]); coin = rng.integers(0, 2**63, size=nw, dtype=np.uint64) ^ (rng.integers(0, 2, size=nw, dtype=np.uint64) << np.uint64(63))
                B[q(args[1])] = (B[q(args[1])] & ~act) | (coin & act)
                S[t] &= ~act
            elif op == 'R':
                t = q(args[0])
                if anyb(S[t] & act): problems.append(('R_dirty', seed, k))
                S[t] &= ~act
            elif op == 'BIT_INVERT': B[q(args[0])] = B[q(args[0])] ^ act
            elif op == 'BIT_STORE0': B[q(args[0])] = B[q(args[0])] & ~act
            elif op == 'BIT_STORE1': B[q(args[0])] = B[q(args[0])] | act
        clean = all(not anyb(S[i]) for i in range(W, nq))
        restored = all(np.array_equal(S[i], x0[i]) for i in range(W))
        print('seed', seed, 'clean', clean, 'restored', restored, flush=True)
        if not (clean and restored): problems.append(('end', seed, clean, restored))
    cand = []
    for r in stats.values():
        if r['fire'] == 0: r['kind'] = 'delete'
        elif r['op'] == 'CCX' and (r['ne_c1'] == 0 or r['ne_c2'] == 0): r['kind'] = 'to_CX'
        elif r['op'] == 'CCZ' and min(r['ne_ab'], r['ne_ac'], r['ne_bc']) == 0: r['kind'] = 'to_CZ'
        elif r['op'] == 'CSWAP' and r['not_swap'] == 0: r['kind'] = 'to_SWAP'
        else: continue
        cand.append(r)
    json.dump(dict(problems=problems, n=len(stats), candidates=cand), open(out, 'w'), indent=0)
    for k_, l_ in LIVEP: print('LIVE %6d %3d %s' % (k_, l_.count('1'), l_))
    print('probe popcount(c1&c2) per seed', PROBED)
    print('problems', problems[:10], 'toffoli-like', len(stats), 'candidates', len(cand))
    for r in cand: print(r)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 4)
