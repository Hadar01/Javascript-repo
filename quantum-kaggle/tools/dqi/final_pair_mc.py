"""Final-selection model: distribution of the private DQI ratio for candidate files, alone and as a best-of-two pair.

Kaggle's final score is the better private score of the two selected submissions. invsqrt and dfthcsos are fixed
across salts (measured), so a pair's final score depends only on each file's DQI failure count K on the private salt.
The DQI test seed is sha256(circuit .kmb) + salt, so two DIFFERENT DQI files get independent draws; the same file in
both submissions gets the same draw (a pair adds nothing then).

Model per file: p ~ Beta(k + 1/2, n - k + 1/2) (Jeffreys, from pooled failures k over n shots),
K ~ Binomial(102400, p), ratio(K) from the verifier's own repetition overhead and the file's Q and mean T.

usage: final_pair_mc.py <comp> name:Q:meanT:k:n [name:Q:meanT:k:n ...]
"""
import sys, os, itertools, numpy as np
comp = sys.argv[1]; sys.path[:0] = [os.path.join(comp, 'verifiers')]
from dqi import verify_submission_dqi as v
REF, N, SIMS = 24439463583672.93, 102400, 400000
rng = np.random.default_rng(7)
Rk = np.array([v.repetition_overhead(v.clopper_pearson_upper_bound(k, N)) for k in range(40)])
files = {}
for arg in sys.argv[2:]:
    name, Q, T, k, n = arg.split(':'); Q, T, k, n = int(Q), float(T), int(k), int(n)
    p = rng.beta(k + 0.5, n - k + 0.5, SIMS); K = np.minimum(rng.binomial(N, p), 39)
    files[name] = REF / (Rk[K] * Q * Q * T)
    r = files[name]
    print(f'{name:10s} pooled {k}/{n}: ratio@K=0 {REF/(Rk[0]*Q*Q*T):.4f}  E {r.mean():.4f}  '
          f'P(K=0) {np.mean(K==0):.3f}  5%/50%/95% {np.percentile(r,5):.4f}/{np.percentile(r,50):.4f}/{np.percentile(r,95):.4f}')
for a, b in itertools.combinations(files, 2):
    m = np.maximum(files[a], files[b])
    print(f'pair {a}+{b}: E[max] {m.mean():.4f}  5%/50%/95% {np.percentile(m,5):.4f}/{np.percentile(m,50):.4f}/'
          f'{np.percentile(m,95):.4f}  gain over best single {m.mean()-max(files[a].mean(), files[b].mean()):+.4f}')
