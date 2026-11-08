"""Per-x phase error / absolute margin of an invsqrt circuit (1 shot per x), using verifier helpers.
usage: python margins.py circuit.kmb out.npz"""
import sys, os, numpy as np, pathlib
COMP = os.environ.get('COMP', '/tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/kg/data')
sys.path.insert(0, os.path.join(COMP, 'verifiers'))
import kickmix as km
from invsqrt import verify_submission_invsqrt as v
p = pathlib.Path(sys.argv[1]); c = km.Circuit.from_file(str(p), format=p.suffix[1:])
spec = v.ProblemSpecInvSqrt.for_n_p(10)
target, tol = v.reference_values(spec, np.arange(1, spec.max_x + 1, dtype=np.uint64))
x_reg, scratch = v.validate_registers(c, spec)
B = 2044; sim = km.Simulator(batch_size=B, seed=1)
err = np.zeros(spec.max_x, np.int64)
for st in range(0, spec.max_x, B):
    xs = np.arange(st + 1, st + B + 1, dtype=np.uint64)
    sim.clear_for_shot(); sim.write_across_shots(x_reg, v.to_bits(xs, 22)); sim.do(c)
    th = np.array([v.half_turns_to_units(sim.read_shot_phase(i)) for i in range(B)], dtype=np.uint64)
    err[st:st + B] = (th - target[st:st + B]).view(np.int64)
marg = tol.astype(np.float64) - np.abs(err).astype(np.float64)
np.savez(sys.argv[2], err=err, tol=tol)
o = np.argsort(marg)[:15]
print('min margin (turns)', marg.min() / 2**64, 'at x', o + 1)
print('margins/2^64', marg[o] / 2**64)
print('ratio err/tol at those', np.abs(err[o]) / tol[o])
