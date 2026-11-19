"""Final-selection model for the private leaderboard, scored on the OVERALL geometric mean.

Kaggle keeps the better private score of the two selected submissions. invsqrt and dfthcsos costs are fixed across
salts (measured), so a submission's private score depends only on its DQI failure count K:
    score(K) = (r_inv * r_dqi(K) * r_chem) ** (1/3),  r_dqi(K) = REF / (R(K) Q^2 T)
with R(K) the verifier's own repetition overhead. The DQI test seed is sha256(circuit) + salt; we MODEL two different
DQI files as independent draws (a standard pseudorandomness assumption, not something the seed expression proves).

Failure-rate uncertainty is propagated with a Jeffreys posterior p ~ Beta(k + 1/2, n - k + 1/2). Two kinds of output:
  * uncertainty in the ESTIMATE: E[score | p] and P(K=0 | p) as functions of the posterior p (credible intervals);
  * spread of a FUTURE DRAW: predictive quantiles of score, marginal over p and K, under the assumed model.
Scenarios: 'shared' = one p for both files (pooled counts, with shared inputs counted once); 'separate' = own p each.

usage: final_pair_mc.py <comp> <config.json>
config: {"r_inv":..., "r_chem":..., "Q":890,
         "files": {"name": {"T": mean_T}, ...},
         "scenarios": [{"label": "...", "rates": {"name": [k, n], ...}  or  "shared": [k, n]}, ...],
         "pairs": [["a","b"], ...]}
"""
import sys, os, json, numpy as np
comp, cfg = sys.argv[1], json.load(open(sys.argv[2]))
sys.path[:0] = [os.path.join(comp, 'verifiers')]
from dqi import verify_submission_dqi as v
from scipy.stats import binom
REF, N, P_SIMS, KMAX = 24439463583672.93, 102400, 20000, 40
rng = np.random.default_rng(11)
Rk = np.array([v.repetition_overhead(v.clopper_pearson_upper_bound(k, N)) for k in range(KMAX)])
ks = np.arange(KMAX)


def score_of_k(T):
    r_dqi = REF / (Rk * cfg['Q'] ** 2 * T)
    return (cfg['r_inv'] * r_dqi * cfg['r_chem']) ** (1 / 3)


def q(a, lo=5, hi=95):
    return f'{np.percentile(a, lo):.5f} / {np.percentile(a, 50):.5f} / {np.percentile(a, hi):.5f}'


for sc in cfg['scenarios']:
    print(f"\n=== scenario: {sc['label']}")
    names = list(cfg['files'])
    if 'shared' in sc:
        k, n = sc['shared']; p_shared = rng.beta(k + 0.5, n - k + 0.5, P_SIMS)
        P = {nm: p_shared for nm in names}
    else:
        P = {nm: rng.beta(sc['rates'][nm][0] + 0.5, sc['rates'][nm][1] - sc['rates'][nm][0] + 0.5, P_SIMS) for nm in names}
    pmf = {nm: binom.pmf(ks[None, :], N, P[nm][:, None]) for nm in names}       # (P_SIMS, KMAX)
    S = {nm: score_of_k(cfg['files'][nm]['T']) for nm in names}
    for nm in names:
        e_given_p = (pmf[nm] * S[nm][None, :]).sum(1) / pmf[nm].sum(1)
        p0 = pmf[nm][:, 0]
        Kdraw = np.minimum(rng.binomial(N, P[nm]), KMAX - 1); pred = S[nm][Kdraw]
        print(f"{nm:9s} score@K=0 {S[nm][0]:.5f} | p median {np.median(P[nm]):.2e} 90%CrI [{np.percentile(P[nm],5):.2e}, "
              f"{np.percentile(P[nm],95):.2e}] | P(K=0|p) median {np.median(p0):.3f} 90%CrI [{np.percentile(p0,5):.3f}, "
              f"{np.percentile(p0,95):.3f}] | E[score|p] mean {e_given_p.mean():.5f} 90%CrI [{np.percentile(e_given_p,5):.5f}, "
              f"{np.percentile(e_given_p,95):.5f}] | future-draw 5/50/95% {q(pred)}")
    for a, b in cfg['pairs']:
        # E[max | p_a, p_b] exactly over the two independent K distributions
        Sa, Sb = S[a], S[b]
        M = np.maximum(Sa[:, None], Sb[None, :])                                # (KMAX, KMAX)
        e_pair = np.einsum('ni,nj,ij->n', pmf[a], pmf[b], M)
        e_best_single = np.maximum((pmf[a] * Sa).sum(1), (pmf[b] * Sb).sum(1))
        gain = e_pair - e_best_single
        Ka = np.minimum(rng.binomial(N, P[a]), KMAX - 1); Kb = np.minimum(rng.binomial(N, P[b]), KMAX - 1)
        pred = np.maximum(Sa[Ka], Sb[Kb])
        se = lambda x: x.std(ddof=1) / np.sqrt(len(x))   # Monte Carlo s.e. of a posterior mean over P_SIMS draws
        print(f"   MC s.e. (P_SIMS={P_SIMS}, seed 11): E[score] {a} {se((pmf[a]*Sa).sum(1)/pmf[a].sum(1)):.1e}, "
              f"{b} {se((pmf[b]*Sb).sum(1)/pmf[b].sum(1)):.1e}; pair gain {se(gain):.1e}")
        print(f"pair {a}+{b}: E[max|p] mean {e_pair.mean():.5f} 90%CrI [{np.percentile(e_pair,5):.5f}, "
              f"{np.percentile(e_pair,95):.5f}] | gain over best single: mean {gain.mean():+.5f} 90%CrI "
              f"[{np.percentile(gain,5):+.5f}, {np.percentile(gain,95):+.5f}] | future-draw 5/50/95% {q(pred)}")
