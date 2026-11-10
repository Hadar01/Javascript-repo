"""E[ratio] under K ~ Binomial(102400, p), using the verifier's own clopper_pearson_upper_bound and repetition_overhead.
usage: expratio.py comp Q T p1 [p2 ...]"""
import sys, os, math
import numpy as np
comp = sys.argv[1]; Q = int(sys.argv[2]); T = float(sys.argv[3]); ps = [float(x) for x in sys.argv[4:]]
sys.path[:0] = [os.path.join(comp, 'verifiers')]
from dqi import verify_submission_dqi as v
from scipy.stats import binom
REF = 24439463583672.93; N = 102400
Rk = [v.repetition_overhead(v.clopper_pearson_upper_bound(k, N)) for k in range(60)]
for p in ps:
    ks = np.arange(60); pk = binom.pmf(ks, N, p); tail = 1 - pk.sum()
    ratios = np.array([REF / (Rk[k] * Q * Q * T) for k in ks])
    er = float((pk * ratios).sum() / pk.sum())
    print(f"p={p:.3e}  E[K]={N*p:.3f}  P(K=0)={pk[0]:.3f}  E[ratio]={er:.4f}  ratio@K=0 {ratios[0]:.4f} K=1 {ratios[1]:.4f} K=2 {ratios[2]:.4f}  (tail>59: {tail:.1e})")
