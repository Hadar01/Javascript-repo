"""Fast invsqrt check: the unmodified official verify() with fewer shots per x.

usage: python quick_check.py circuit.kmb [--shots-per-x 1] [--workers 2] [--salt s]
shots_per_x=1 tests every x once (one HMR history each); batch 2044 divides 3,133,452.
The cost it prints uses the same formula as the official run (mean over the shots taken).
"""
import argparse, json, os, sys, time, pathlib
COMP = os.environ.get('COMP', '/tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/kg/data')
sys.path.insert(0, os.path.join(COMP, 'verifiers'))
import kickmix as km
from fractions import Fraction
from invsqrt import verify_submission_invsqrt as v
REF = 2076774.233715282
ap = argparse.ArgumentParser(); ap.add_argument('f'); ap.add_argument('--shots-per-x', type=int, default=1)
ap.add_argument('--workers', type=int, default=2); ap.add_argument('--salt', default='quick')
ap.add_argument('--batch', type=int, default=2044)
a = ap.parse_args()
p = pathlib.Path(a.f)
c = km.Circuit.from_file(str(p), format=p.suffix[1:])
spec = v.ProblemSpecInvSqrt(width=22, max_x=3133452, beta=Fraction(1), precision_bits=24,
                            shots_per_x=a.shots_per_x, system_qubits=6540)
t = time.time()
try:
    r = v.verify(c, spec, salt=a.salt, batch_size=a.batch, max_workers=a.workers)
    r['ratio'] = REF / r['score']
except Exception as e:
    r = {'status': 'FAIL', 'error': str(e)}
r['seconds'] = round(time.time() - t)
print(json.dumps(r, indent=1))
