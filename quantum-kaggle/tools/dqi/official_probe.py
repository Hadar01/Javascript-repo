"""Run given input shots (from own-sampler files) through the official kickmix Simulator, each replicated across a
256-shot batch (independent HMR outcomes), and report value/phase failure counts per input."""
import sys, os, numpy as np
comp, kmb, prefix, N = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]); shots = [int(x) for x in sys.argv[5].split(',')]
sys.path[:0] = [os.path.join(comp, 'verifiers')]
import kickmix as km
from dqi import verify_submission_dqi as v
spec = v.ProblemSpecDQI.benchmark_instance()
c = km.Circuit.from_file(kmb, format='kmb'); syq, mbb, anc = v.validate_registers(c, spec); sya, mba = km.array(syq), km.array(mbb)
syn = np.fromfile(prefix + '.syn', dtype=np.uint16).reshape(N, 70).astype(np.int64)
mb = np.fromfile(prefix + '.mbuc', dtype=np.uint16).reshape(N, 4095).astype(np.int64)
ph = np.fromfile(prefix + '.phase', dtype=np.uint8).astype(bool)
for s in shots:
    for seed in (1, 2):
        S_ = np.repeat(syn[s:s+1], 256, 0); M_ = np.repeat(mb[s:s+1], 256, 0); P_ = np.repeat(ph[s:s+1], 256)
        sim = km.Simulator(batch_size=256, debug_print=False, counting_operations=False, seed=seed)
        sim.use_same_registers_as(c); inb = v.to_bits(S_, 12); sim.write_across_shots(sya, inb); sim.write_across_shots(mba, v.to_bits(M_, 12)); sim.do(c)
        pf = sim.read_phase_flipped_across_shots(); rd = sim.read_across_shots(sya) ^ inb; junk = sim.read_across_shots(anc)
        ve = rd.any(0) | junk.any(0); pe = (pf ^ P_) & ~ve
        print('shot', s, 'seed', seed, 'value fails', int(ve.sum()), '/256  phase fails', int(pe.sum()), '/256', flush=True)
