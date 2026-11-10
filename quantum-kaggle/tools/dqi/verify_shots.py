"""Run the unmodified official verify() on pre-generated shots (its `shots=` argument)."""
import sys, os, json, numpy as np
comp, kmb, prefix, N = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
sys.path[:0] = [os.path.join(comp, 'verifiers')]
import kickmix as km
from dqi import verify_submission_dqi as v
syn = np.fromfile(prefix + '.syn', dtype=np.uint16).reshape(N, 70).astype(np.int64)
mb = np.fromfile(prefix + '.mbuc', dtype=np.uint16).reshape(N, 4095).astype(np.int64)
ph = np.fromfile(prefix + '.phase', dtype=np.uint8).astype(bool)
c = km.Circuit.from_file(kmb, format='kmb')
for salt in sys.argv[5].split(','):
    r = v.verify(c, v.ProblemSpecDQI.benchmark_instance(num_shots=N), salt=salt, shots=(syn, mb, ph), max_workers=1)
    print(salt, r['value_errors'], r['phase_errors'], flush=True)
