"""Benchmark Agent A's XAG synthesizer (tools/xag/xag.py, unmodified, imported) on one dfthcsos loader circuit.
Targets: the 35 signed-gauge output bits of circuit k's delta, extended to all 2048 addresses by their ANF over
high monomials < H (the compiler's exact model). Helpers: the 69 nonlinear high monomials and the low monomials
not carried in the word top bits. Reports products = ANDs - helper ANDs.
usage: QK_SCRIPTS=... python xag_loader_bench.py TABLE.npz K [keep_from] [seed] [tries]"""
import os, sys, time, itertools
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent)); sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'xag'))
import helper_build as hb
hb.setup_paths(Path(os.environ['QK_SCRIPTS']))
import xag, rmcode, tensorqrom as tq
from fourqrom import batch_deltas

table, K = sys.argv[1], int(sys.argv[2])
keep = int(sys.argv[3]) if len(sys.argv) > 3 else 2
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 0
tries = int(sys.argv[5]) if len(sys.argv) > 5 else 12
z = np.load(table); words, deg = z['angle_words'].astype(np.int64), z['codes'].astype(np.int64)
d = list(batch_deltas(words, 5))[K]
degs = rmcode.output_degrees(deg, K, 5, 8); d = rmcode.pad(d, degs, 8); d = hb.fill_dontcare(d, degs, len(words))
C = tq.anf_tensor(d, 8, 4)                  # (16, H, 35)
L, H, O = C.shape
n = 11
pts = np.arange(1 << n); lo, hi = pts & 15, pts >> 4
mono_l = np.array([[(l & S) == S for l in range(16)] for S in range(16)], np.uint8)       # [S, l]
mono_h = np.array([[(h & M) == M for h in range(128)] for M in range(H)], np.uint8)       # [M, h]
targets = []
for o in range(O):
    val = (mono_l[:, lo].T.astype(np.int64) @ C[:, :, o].astype(np.int64) % 2)            # (2048, H): sum_S m_S(l) C[S,M]
    f = np.sum(val * mono_h[:, hi].T, axis=1) % 2
    targets.append(int(''.join(map(str, f[::-1])), 2))
hm = hb.helper_masks(words)
cols = [K * 5 + j for j in range(5)]
carried = {int(hm[c]) for c, cp in zip(cols, [c - 5 for c in cols]) if K and hm[c] and hm[c] == hm[cp]}
low_helpers = [tuple(i for i in range(4) if S >> i & 1) for S in range(16) if bin(S).count('1') >= 2 and S not in carried]
high_helpers = [tuple(4 + i for i in range(7) if M >> i & 1) for M in range(H) if bin(M).count('1') >= 2]
# carried low monomials are free inputs: model them as helpers too but subtract their ANDs
carried_h = [tuple(i for i in range(4) if S >> i & 1) for S in sorted(carried)]
helpers = high_helpers + low_helpers + carried_h
t0 = time.time()
order = sorted(range(O), key=lambda i: -int(np.sum(C[1:, 1:, i])))
r = xag.synthesize(targets, n, seed=seed, keep_from=keep, tries=tries, helpers=helpers, order=order)
xag.verify(r, targets)
nb = r['nbase']
print(f'circuit {K}: ANDs {r["ands"]} = helpers {nb} + products {r["ands"] - nb}; carried free {len(carried_h)}; '
      f'cost counting carried as free: {r["ands"] - len(carried_h)}; wires {r["nwires"]}; {time.time()-t0:.0f}s; costs {r["costs"]}')
