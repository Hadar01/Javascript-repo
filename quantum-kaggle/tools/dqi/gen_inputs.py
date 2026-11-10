"""Generate DQI test shots with the official verifier's own sampler (unmodified) and write raw arrays.
usage: gen_inputs.py <comp_dir> <num_shots> <seed> <outprefix> [min_weight]
Writes <out>.syn (uint16 N x 70), <out>.mbuc (uint16 N x 4095), <out>.phase (uint8 N), <out>.weight (uint8 N)"""
import sys, os, numpy as np
comp, N, seed, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
sys.path[:0] = [os.path.join(comp, 'verifiers')]
import kickmix as km
from dqi import verify_submission_dqi as v
spec = v.ProblemSpecDQI.benchmark_instance(num_shots=N)
tables = v.FieldTables(km.GF2Field(spec.degree))
wp = v.optimal_dqi_weights(spec.m, spec.max_errors, spec.degree, spec.r) ** 2
if len(sys.argv) > 5:   # optional: force a fixed weight (stress tests); NOT the official distribution
    w = int(sys.argv[5]); wp = np.zeros_like(wp); wp[w] = 1.0
rng = np.random.default_rng(seed)
syn, mbuc, ph = v.sample_shots(spec, tables, rng, N, wp)
# recompute weights: number of nonzero error symbols isn't returned; re-derive from rng is not possible, so store via syndrome trick
syn.astype(np.uint16).tofile(out + '.syn'); mbuc.astype(np.uint16).tofile(out + '.mbuc'); ph.astype(np.uint8).tofile(out + '.phase')
print('wrote', N, 'shots; phase ones', int(ph.sum()), 'zero syndromes', int((syn == 0).all(1).sum()))
