"""Duplicate-shot check across official DQI verifier runs.

Regenerates every official shot exactly as verify() does (circuit sha256 + salt -> per-batch seeds -> sample_shots)
for each (circuit, salt) run and counts duplicate syndrome vectors within and across runs. The syndrome alone
determines the decoder's value path, so duplicates there would make pooled failure counts non-independent.

usage: dup_check.py <comp> <circuit.kmb>:<salt,salt,...> [...]
"""
import sys, os, hashlib, collections, numpy as np
comp = sys.argv[1]; sys.path[:0] = [os.path.join(comp, 'verifiers')]
import kickmix as km
from dqi import verify_submission_dqi as v
spec = v.ProblemSpecDQI.benchmark_instance(); tables = v.FieldTables(km.GF2Field(12))
wp = v.optimal_dqi_weights(spec.m, spec.max_errors, spec.degree, spec.r) ** 2
seen = collections.Counter(); total = 0
for arg in sys.argv[2:]:
    path, salts = arg.rsplit(':', 1)
    sha = v._circuit_sha256(km.Circuit.from_file(path, format='kmb'))
    for salt in salts.split(','):
        base = v._initial_seed(sha, salt); starts = range(0, spec.num_shots, 256)
        seeds = np.random.SeedSequence(base, pool_size=8).generate_state(8 * len(starts), dtype=np.uint64).reshape(-1, 2, 4)
        for i, s in enumerate(starts):
            rs = int.from_bytes(seeds[i, 0], 'little')
            syn, mb, ph = v.sample_shots(spec, tables, np.random.default_rng(rs), 256, wp)
            for row in np.ascontiguousarray(syn):
                seen[hashlib.blake2b(row.tobytes(), digest_size=16).digest()] += 1
            total += 256
        print(f'{os.path.basename(os.path.dirname(path))}/{os.path.basename(path)} {salt}: cumulative shots {total}, '
              f'distinct syndromes {len(seen)}', flush=True)
dups = {h: c for h, c in seen.items() if c > 1}
print('TOTAL shots', total, 'distinct', len(seen), 'syndromes seen more than once', len(dups),
      'extra copies', sum(c - 1 for c in dups.values()))
