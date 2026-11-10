"""Pool failure data per circuit (official sweeps + own paired census), CP 95% CIs, family split, E[ratio]."""
import json, glob, re, os, sys, numpy as np, collections
comp = sys.argv[1]; sys.path[:0] = [os.path.join(comp, 'verifiers')]
from dqi import verify_submission_dqi as v
from scipy.stats import beta, binom
REF = 24439463583672.93; N = 102400
def cp95(k, n):
    lo = 0.0 if k == 0 else beta.ppf(0.025, k, n - k + 1); hi = beta.ppf(0.975, k + 1, n - k)
    return lo, hi
Rk = [v.repetition_overhead(v.clopper_pearson_upper_bound(k, N)) for k in range(80)]
def eratio(p, Q, T):
    ks = np.arange(80); pk = binom.pmf(ks, N, p)
    return float((pk * np.array([REF / (Rk[k] * Q * Q * T) for k in ks])).sum() / pk.sum())
sw = collections.defaultdict(list)
for l in open('sweep.jsonl'):
    r = json.loads(l); sw[r['tag']].append(r)
census = json.load(open('bigfail_summary.json'))
for tag in ('v95', 'v100'):
    runs = sw.get(tag, []); kv = sum(r['value_errors'] for r in runs); kp = sum(r['phase_errors'] for r in runs)
    T = np.mean([r['toffoli_count'] for r in runs]) if runs else float('nan'); ns = len(runs) * N
    c = census.get(tag, dict(n=0, v=0, p=0, fails=[]))
    print(f"== {tag}: official sweeps {len(runs)} salts x 102,400 = {ns:,} shots: value {kv}, phase {kp}; mean T {T:.2f}")
    print('   per-salt ratios:', [round(r['ratio'], 4) for r in runs])
    print('   ratio mean over salts %.4f  min %.4f  max %.4f' % (np.mean([r['ratio'] for r in runs]), min(r['ratio'] for r in runs), max(r['ratio'] for r in runs)))
    print(f"   own census: {c['n']:,} shots: value {c['v']}, phase {c['p']}; weights of failures: {[ (f['kind'], f['weight']) for f in c['fails']]}")
    k = kv + kp + c['v'] + c['p']; n = ns + c['n']
    lo, hi = cp95(k, n); p = k / n
    print(f"   pooled: {k} failures / {n:,} shots -> p = {p:.3e}  (95% CP {lo:.2e} .. {hi:.2e})")
    for name, pp in (('p_hat', p), ('lo95', lo), ('hi95', hi)):
        print(f"   E[ratio | {name}={pp:.2e}] = {eratio(pp, 892, T):.4f}   E[failures/run] = {N*pp:.3f}")
