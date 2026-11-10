"""Regenerate the exact test shots of one official verifier run (circuit_sha256 + salt) with the verifier's own
sampler and seed plumbing; write them in 4096-shot chunks for the independent simulator. Also writes weights."""
import sys, os, numpy as np
comp, sha, salt, out = sys.argv[1:5]
sys.path[:0] = [os.path.join(comp, 'verifiers')]
import kickmix as km
from dqi import verify_submission_dqi as v
spec = v.ProblemSpecDQI.benchmark_instance(); tables = v.FieldTables(km.GF2Field(12))
wp = v.optimal_dqi_weights(spec.m, spec.max_errors, spec.degree, spec.r) ** 2
base = v._initial_seed(sha, salt); starts = range(0, spec.num_shots, 256)
seeds = np.random.SeedSequence(base, pool_size=8).generate_state(8 * len(starts), dtype=np.uint64).reshape(-1, 2, 4)
chunk = 16
for c in range(0, len(starts), chunk):
    syn, mb, ph, ws = [], [], [], []
    for i in range(c, min(c + chunk, len(starts))):
        rng = np.random.default_rng(int.from_bytes(seeds[i, 0], 'little'))
        s_, m_, p_ = v.sample_shots(spec, tables, rng, 256, wp)
        rng2 = np.random.default_rng(int.from_bytes(seeds[i, 0], 'little')); ws.append(rng2.choice(len(wp), size=256, p=wp))
        syn.append(s_); mb.append(m_); ph.append(p_)
    pre = f"{out}_{c // chunk:02d}"
    np.concatenate(syn).astype(np.uint16).tofile(pre + '.syn'); np.concatenate(mb).astype(np.uint16).tofile(pre + '.mbuc')
    np.concatenate(ph).astype(np.uint8).tofile(pre + '.phase'); np.concatenate(ws).astype(np.uint8).tofile(pre + '.w')
print('done')
