"""For (circuit_sha256, salt), reproduce the verifier's per-batch weight draws and count shots with weight <= W.
Uses the verifier's own _initial_seed / optimal_dqi_weights; mirrors its seed plumbing (verify() lines 358, 394-396, 364-365)."""
import sys, os, json, numpy as np
comp = sys.argv[1]; sys.path[:0] = [os.path.join(comp, 'verifiers')]
from dqi import verify_submission_dqi as v
spec = v.ProblemSpecDQI.benchmark_instance()
wp = v.optimal_dqi_weights(spec.m, spec.max_errors, spec.degree, spec.r) ** 2
W = int(sys.argv[2])
for line in open(sys.argv[3]):
    r = json.loads(line)
    base = v._initial_seed(r['circuit_sha256'], r['salt'])
    starts = range(0, spec.num_shots, 256)
    seeds = np.random.SeedSequence(base, pool_size=8).generate_state(8 * len(starts), dtype=np.uint64).reshape(-1, 2, 4)
    low = []
    for i, s in enumerate(starts):
        rng = np.random.default_rng(int.from_bytes(seeds[i, 0], 'little'))
        w = rng.choice(len(wp), size=256, p=wp)
        low += [(s + int(j), int(w[j])) for j in np.flatnonzero(w <= W)]
    print(r['tag'], r['salt'], 'fails', r['value_errors'], r['phase_errors'], '| shots with weight<=%d:' % W, low)
