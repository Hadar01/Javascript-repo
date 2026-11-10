"""Re-run one official verification (same seeds as verify()) batch by batch with the official kickmix Simulator and
report every failing shot: batch, shot, weight, kind, dirty ancillas / changed syndrome bits. Mirrors verify() run_batch."""
import sys, os, json, numpy as np
comp, kmb, salt = sys.argv[1:4]; only = set(int(x) for x in sys.argv[4].split(',')) if len(sys.argv) > 4 else None
sys.path[:0] = [os.path.join(comp, 'verifiers')]
import kickmix as km
from dqi import verify_submission_dqi as v
spec = v.ProblemSpecDQI.benchmark_instance(); tables = v.FieldTables(km.GF2Field(12))
wp = v.optimal_dqi_weights(spec.m, spec.max_errors, spec.degree, spec.r) ** 2
circuit = km.Circuit.from_file(kmb, format='kmb'); sha = v._circuit_sha256(circuit)
syq, mbb, anc = v.validate_registers(circuit, spec); sya, mba = km.array(syq), km.array(mbb)
base = v._initial_seed(sha, salt); starts = range(0, spec.num_shots, 256)
seeds = np.random.SeedSequence(base, pool_size=8).generate_state(8 * len(starts), dtype=np.uint64).reshape(-1, 2, 4)
anc_ids = [int(str(q)[1:]) if str(q).startswith('q') else None for q in anc]
for i, s in enumerate(starts):
    if only is not None and i not in only: continue
    rs, ss = int.from_bytes(seeds[i, 0], 'little'), int.from_bytes(seeds[i, 1], 'little')
    rng = np.random.default_rng(rs); syn, mb, ph = v.sample_shots(spec, tables, rng, 256, wp)
    w = np.random.default_rng(rs).choice(len(wp), size=256, p=wp)
    sim = km.Simulator(batch_size=256, debug_print=False, counting_operations=True, seed=ss)
    sim.use_same_registers_as(circuit); inb = v.to_bits(syn, 12)
    sim.write_across_shots(sya, inb); sim.write_across_shots(mba, v.to_bits(mb, 12)); sim.do(circuit)
    pf = sim.read_phase_flipped_across_shots(); rd = sim.read_across_shots(sya) ^ inb; junk = sim.read_across_shots(anc)
    ve = rd.any(0) | junk.any(0); pe = (pf ^ ph) & ~ve
    for j in np.flatnonzero(ve | pe):
        print(json.dumps(dict(batch=i, shot=s + int(j), weight=int(w[j]), kind='value' if ve[j] else 'phase',
              changed_syndrome_bits=[int(x) for x in np.flatnonzero(rd[:, j])][:20], dirty_ancillas=[str(anc[int(x)]) for x in np.flatnonzero(junk[:, j])][:20])), flush=True)
print('done', salt, flush=True)
