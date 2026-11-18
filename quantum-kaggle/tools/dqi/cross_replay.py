"""Failure-overlap check between two DQI circuits, on the exact inputs where one of them failed an official run.

For each (salt) of circuit A: regenerate the official shots exactly as verify() does (same seeds), find A's failing
shots, then run each failing input through circuit A and circuit B, replicated R times with fresh measurement
randomness, and count value / phase failures. Mirrors verify_submission_dqi run_batch (see official_failshots.py).

usage: cross_replay.py <comp> <A.kmb> <B.kmb> <salt>[,<salt>...] [R=64]
"""
import sys, os, json, numpy as np
comp, ka, kb, salts = sys.argv[1:5]; R = int(sys.argv[5]) if len(sys.argv) > 5 else 64
sys.path[:0] = [os.path.join(comp, 'verifiers')]
import kickmix as km
from dqi import verify_submission_dqi as v

spec = v.ProblemSpecDQI.benchmark_instance(); tables = v.FieldTables(km.GF2Field(12))
wp = v.optimal_dqi_weights(spec.m, spec.max_errors, spec.degree, spec.r) ** 2
CA = km.Circuit.from_file(ka, format='kmb'); CB = km.Circuit.from_file(kb, format='kmb')


def run(circuit, syn, mb, ph, seed):
    syq, mbb, anc = v.validate_registers(circuit, spec); sya, mba = km.array(syq), km.array(mbb)
    n = syn.shape[0]
    sim = km.Simulator(batch_size=n, debug_print=False, counting_operations=False, seed=seed)
    sim.use_same_registers_as(circuit); inb = v.to_bits(syn, 12)
    sim.write_across_shots(sya, inb); sim.write_across_shots(mba, v.to_bits(mb, 12)); sim.do(circuit)
    pf = sim.read_phase_flipped_across_shots(); rd = sim.read_across_shots(sya) ^ inb; junk = sim.read_across_shots(anc)
    ve = rd.any(0) | junk.any(0); pe = (pf ^ ph) & ~ve
    return ve, pe


out = []
for salt in salts.split(','):
    sha = v._circuit_sha256(CA); base = v._initial_seed(sha, salt); starts = range(0, spec.num_shots, 256)
    seeds = np.random.SeedSequence(base, pool_size=8).generate_state(8 * len(starts), dtype=np.uint64).reshape(-1, 2, 4)
    for i, s in enumerate(starts):
        rs, ss = int.from_bytes(seeds[i, 0], 'little'), int.from_bytes(seeds[i, 1], 'little')
        rng = np.random.default_rng(rs); syn, mb, ph = v.sample_shots(spec, tables, rng, 256, wp)
        ve, pe = run(CA, syn, mb, ph, ss)
        for j in np.flatnonzero(ve | pe):
            kind = 'value' if ve[j] else 'phase'
            rep = lambda C, sd: run(C, np.repeat(syn[j:j + 1], R, 0), np.repeat(mb[j:j + 1], R, 0), np.repeat(ph[j:j + 1], R, 0), sd)
            a_v, a_p = rep(CA, 12345); b_v, b_p = rep(CB, 12345)
            rec = dict(salt=salt, batch=i, shot=s + int(j), kind=kind,
                       A_fail_of_R=int((a_v | a_p).sum()), B_fail_of_R=int((b_v | b_p).sum()),
                       B_value=int(b_v.sum()), B_phase=int(b_p.sum()), R=R)
            out.append(rec); print(json.dumps(rec), flush=True)
print('SUMMARY', json.dumps({'A': os.path.basename(ka), 'B': os.path.basename(kb), 'failing_inputs_of_A': len(out),
                             'also_fail_in_B_every_replica': sum(r['B_fail_of_R'] == R for r in out),
                             'fail_in_B_some_replica': sum(r['B_fail_of_R'] > 0 for r in out)}))
