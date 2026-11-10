"""Own vectorized sampler with the verifier's exact distribution (weights w_k^2 from the verifier's function,
uniform positions without replacement, uniform nonzero values, uniform 12-bit M). Also stores the error vectors.
usage: mysample.py comp N seed outprefix [forced_weight]"""
import sys, os, numpy as np
comp, N, seed, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
sys.path[:0] = [os.path.join(comp, 'verifiers')]
import kickmix as km
from dqi import verify_submission_dqi as v
spec = v.ProblemSpecDQI.benchmark_instance(); tb = v.FieldTables(km.GF2Field(12))
wp = v.optimal_dqi_weights(spec.m, spec.max_errors, spec.degree, spec.r) ** 2
rng = np.random.default_rng(seed)
wts = rng.choice(len(wp), size=N, p=wp)
if len(sys.argv) > 5: wts[:] = int(sys.argv[5])   # forced weight (stress test, NOT the official distribution)
mb = rng.integers(0, 4095, size=(N, 4095), endpoint=True, dtype=np.uint16)
syn = np.zeros((N, 70), np.int64); ph = np.zeros(N, np.uint8)
pos = np.full((N, 35), -1, np.int16); val = np.zeros((N, 35), np.uint16)
rows = np.arange(1, 71, dtype=np.int64)[:, None]
for k in np.unique(wts):
    idx = np.flatnonzero(wts == k)
    if k == 0: continue
    # positions without replacement: argsort of random keys (exact uniform subset)
    P = np.argpartition(rng.random((len(idx), 4095)), k, axis=1)[:, :k]
    V = rng.integers(1, 4095, size=(len(idx), k), endpoint=True)
    for j in range(len(idx)):
        p_, v_ = P[j], V[j]
        e = (tb.log[v_][None, :] + rows * p_[None, :]) % tb.order
        syn[idx[j]] = np.bitwise_xor.reduce(tb.antilog[e], axis=1)
        ph[idx[j]] = sum(int(x).bit_count() for x in (v_ & mb[idx[j], p_])) & 1
    pos[idx, :k] = P; val[idx, :k] = V
syn.astype(np.uint16).tofile(out + '.syn'); mb.tofile(out + '.mbuc'); ph.tofile(out + '.phase')
np.savez_compressed(out + '_err.npz', weight=wts.astype(np.uint8), pos=pos, val=val)
print('ok', N, 'mean weight', wts.mean())
