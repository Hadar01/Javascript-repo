"""Score candidate circuits locally with the unmodified official verifiers.

usage: python score_local.py --comp <competition data dir> [--salt S] [--invsqrt f] [--dqi f] [--dfthcsos dir]
"""
import argparse, json, math, os, sys, time, pathlib, secrets

REF = {'invsqrt': 2076774.233715282, 'dfthcsos': 3355599588.3155375, 'dqi': 24439463583672.93}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--comp', required=True)
    ap.add_argument('--salt', default=None)
    ap.add_argument('--invsqrt'); ap.add_argument('--dqi'); ap.add_argument('--dfthcsos')
    ap.add_argument('--workers', type=int, default=None)
    a = ap.parse_args()
    sys.path[:0] = [os.path.join(a.comp, 'verifiers')]
    import kickmix as km
    salt = a.salt or ('team-' + secrets.token_hex(8))
    out = {'salt': salt}
    def load(p):
        p = pathlib.Path(p); return km.Circuit.from_file(str(p), format=p.suffix.removeprefix('.'))
    for task in ('dfthcsos', 'dqi', 'invsqrt'):
        path = getattr(a, task)
        if not path:
            continue
        t0 = time.time()
        if task == 'invsqrt':
            from invsqrt import verify_submission_invsqrt as v
            r = v.verify(load(path), v.ProblemSpecInvSqrt.for_n_p(10), salt=salt, max_workers=a.workers)
        elif task == 'dqi':
            from dqi import verify_submission_dqi as v
            r = v.verify(load(path), v.ProblemSpecDQI.benchmark_instance(), salt=salt, max_workers=a.workers)
        else:
            from dfthcsos import verify as v
            r = v.verify(str(path), salt=salt)
        ratio = REF[task] / float(r['score'])
        out[task] = {'ratio': ratio, 'seconds': round(time.time() - t0),
                     **{k: v_ for k, v_ in r.items() if isinstance(v_, (int, float, str, bool))}}
        print(f"{task:9s} {r['status']} cost {float(r['score']):.6g} ratio {ratio:.4f} ({time.time()-t0:.0f}s)", flush=True)
    rs = [out[t]['ratio'] for t in ('invsqrt', 'dqi', 'dfthcsos') if t in out]
    if len(rs) == 3:
        out['geo_mean'] = math.prod(rs) ** (1 / 3); print('GEO MEAN', round(out['geo_mean'], 5))
    print(json.dumps(out, indent=1, default=str))

if __name__ == '__main__':
    main()
