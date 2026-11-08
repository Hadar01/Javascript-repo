# Chemistry (dfthcsos) experiment log — Agent C, 2026-11-08

Baseline: public portfolio v95, `$S/cand/pub/dfthcsos/`, (8,143,44), brot 8, J 5.
λ_eff 46.891127, T 14,966 (8,304 in the angle circuits), Q 427, ratio **11.1981**.
Gate slack in that file: error_1 2.4e-10 Ha, error_2 2.2e-10 Ha, E_gap 2.5e-10 Ha.

## 1. Smaller tables (fewer rows, so one fewer address bit): stopped, does not reach the gate

- **Shape (4,143,88), 648 rows.**
  - Seed: merge the public groups in pairs (0,6), (1,4), (2,7), (3,5). Keep 143 of each pair's 286 vectors, chosen greedily by leaf reconstruction. Refit the weights by least squares (`tools/chem/seed_merge.py`).
  - Fit: float64 L-BFGS on the exact error_2 with κ·D(w), κ = 5e-5 (`tools/chem/fit_dfthc.py`). 2 cores, about 1.35 s per iteration.
  - error_2 after each 100 iterations:

    | iterations | 0 | 100 | 200 | 300 | 400 |
    |---|---|---|---|---|---|
    | error_2 (mHa) | 1026 | 143.8 | 109.1 | 96.7 | 89.4 |

  - The decrease is slowing. The stop rule (16 mHa before rounding) is about 6× away.
  - For comparison, the marculera README reports that direct fits at full-size shapes stall at 17–20 mHa even after 240k A100 iterations, and that cutting B from 180 to 143 (−20 % of the vectors) already costs about +5 mHa.
  - **Conclusion:** 572 vectors cannot reach 20 mHa with any CPU budget we have, and probably not at all. Stopped. (6,143,59), with 934 rows, would gain at most about 3 % by the cost model and has the same accuracy problem, so I did not run it.
- The out-of-memory kill at 18:44 was the invsqrt analyzer. My fit survived; I stopped it myself.

## 2. Refitting the weights at fixed words (circuits byte-identical)

- Code: `tools/chem/refit_fixed_words.py`.
  - Exact error_1 (with the verifier's linear_sum_assignment matching), error_2 via the K/Q expansion, Λ, E_gap and λ_eff², all with analytic gradients. Checked against finite differences and against the official verifier to 1e-10.
  - Two optimizers:
    - augmented Lagrangian with L-BFGS: made things worse (λ 46.8939);
    - active-face projected gradient with Newton restoration (`--face`): no descent direction found.
  - So the public weights sit at a local optimum on their face. ahmedberatozer's convex bound (λ_eff ≥ 46.8485) caps the possible gain at 0.09 %.
- **Margin candidate** `$S/cand/chem_refit_margin/`: e1 = e2 = 19.9990 mHa and E_gap = floor + 2.4e-4 Ha. Verified with `score_local.py --salt agentC-check`:
  `dfthcsos  PASS cost 2.99668e+08 ratio 11.1977 (15s)`, λ_eff 46.89288256025776, T 14966, Q 427.
  - This is 0.004 % below the public file. It is not needed, because **the metrics do not depend on the salt**: the words must agree on every shot, and error_1, error_2, Λ and E_gap are deterministic functions of the words and weights. The 2.4e-10 Ha slack is therefore exposed only to BLAS/FP reproducibility (about 1e-12 relative), not to the private-leaderboard salt.
  - Recommendation: keep the public file unchanged.

## 3. Conclusion

- No candidate beats 11.1981.
- The remaining chemistry gain needs a new lookup compiler plus loader-aware rounding, i.e. a new table and circuits. That is GPU-scale fitting (about 4.6 A100-hours per rounding in marculera's runs) plus a GF(2) tensor-rank compiler. It is not feasible on 2 CPUs in this session.
- The public pipeline (marculera `dfthc-compact-pipeline`, Apache-2.0) is now in `$S/dl/marculera/ds/`. It contains `tensorqrom.py`, `rmcode.py` and `quantize_rm.py`, the starting point for that work.

## 4. GPU notebook `notebooks/chem_gpu_refit.ipynb` (generator: `tools/chem/make_gpu_notebook.py`)

**Pipeline**
1. Round marculera's continuous `adam_8x143x45.npz` (error_2 14.155 mHa) to 8-bit words.
   - Script: `quantize_rm.py --open`, with her 59-stage, 60k-iteration L-BFGS schedule.
   - Lookup-aware code ladder `CODES` (default `0:1:2-14`).
   - Our resume patch `tools/chem/patch_quantize_resume.py` adds a checkpoint after every stage and a wall-clock budget (exit code 3 means "resume next session").
2. `finish_rm.py`: refine the one-body rows, then `refit_al` to 19.995 mHa.
3. qwertykeypadapple's kernel-relation search plus build.
4. Unmodified `dfthcsos.verify` at the default salt and at one private salt. The candidate folder and `candidate_verify.json` go to `/kaggle/working`.

**Datasets:** `marculera/dfthc-compact-pipeline`, `qwertykeypadapple/qcc-kernel-search-portfolio`, `sohier/verifiable-circuit-compilation-starter-kit`, plus the competition data.

**Local CPU tests (mock /kaggle layout)**
- The patched rounding runs, checkpoints, pauses with exit code 3 and resumes.
- The kernel-search build with the shipped plans reproduces 15,347 Toffolis and ratio 10.8334 (`--salt test`).

**Expected result: ratio about 10.85–11.05 at best, which probably does NOT beat 11.1981.**
- Rounding budget: Lera's 3-14 coding ended at 19.95 mHa, and each extra coded batch costs about 3.3 mHa² of noise. So `2-14` lands at about 20.03 mHa (borderline), and `0-14` at about 20.3 mHa (likely fails).
- The best open compiler, the kernel search, is about 3.6 % behind syed3000's closed one: about 4,300 vs 4,152 Toffolis per pass.

**GPU-hours:** P100 at roughly half an A100's speed. Lera's A100 rounding took 4.6 h, so expect about 9–10 h of rounding, plus about 2 h of CPU-bound finishing and search. That is 2 sessions and about 12 GPU-hours of quota.

**Better use of effort:** port syed3000's described compiler tricks into the open kernel search: helper products carried across batches via a commuting tree reorder and the π-gauge bit 7, and five-block coded plans at 195 products. That is CPU work, and it is the only lever likely to beat 11.198 on chemistry.
