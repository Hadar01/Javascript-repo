"""Run the unmodified official DQI verifier on a circuit under a list of salts; append JSONL results."""
import sys, os, json, time, argparse
ap = argparse.ArgumentParser()
ap.add_argument('--comp', required=True); ap.add_argument('--circuit', required=True)
ap.add_argument('--tag', required=True); ap.add_argument('--salts', required=True)  # comma list
ap.add_argument('--workers', type=int, default=3); ap.add_argument('--out', required=True)
a = ap.parse_args()
sys.path[:0] = [os.path.join(a.comp, 'verifiers')]
import kickmix as km
from dqi import verify_submission_dqi as v
REF = 24439463583672.93
c = km.Circuit.from_file(a.circuit, format='kmb')
for salt in a.salts.split(','):
    t0 = time.time()
    r = v.verify(c, v.ProblemSpecDQI.benchmark_instance(), salt=salt, max_workers=a.workers)
    rec = {k: r[k] for k in ('value_errors', 'phase_errors', 'toffoli_count', 'num_qubits', 'repetition_factor',
                             'effective_error_rate', 'score', 'max_toffoli_count', 'circuit_sha256')}
    rec.update(tag=a.tag, salt=salt, ratio=REF / r['score'], seconds=round(time.time() - t0, 1))
    with open(a.out, 'a') as f: f.write(json.dumps(rec) + '\n')
    print(json.dumps(rec), flush=True)
