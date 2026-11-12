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

## 5. Porting syed3000's loader tricks into the open compiler (2026-11-09): blocker

**What the public table's words actually contain**
- Bit 7 of word j is bit 6 XOR h_j(l), where h_j is a degree-2 low-address monomial: l0l1, l0l2, l1l2, l0l3, l1l3 for j = 0..4.
- A few late columns carry no helper: 51, 56, 60, 61, 65, 66, 68–71, 73, 74.
- So after `b7 ^= b6`, the incoming words already hold 5 of the 11 nonlinear low monomials.
- This explains syed3000's per-circuit cost. Toffolis = products + 69 (high cache) + 11 − (helpers that persist from batch k−1 to batch k).
  - Products are 217, 216 ×3, then 195 ×11, i.e. 3,009 per pass.
  - Every coded circuit, including the late ones (271–274 Toffolis), sits at 195 products.

**Code written**
- `tools/chem/helper_build.py`: a modified tensorqrom builder.
  - Persisting helpers are used as low-cache qubits.
  - Changed helpers are corrected with h_in XOR h_out from the cache, which is correct both forward and in reverse.
  - Words with no helper lend their cleared top bit as scratch.
  - Also has `fill_dontcare` (fills the 12 unused rows of the last block) and `--only/--base` to mix single circuits with the public ones.
- `tools/chem/dc_search.py`: qwertykeypadapple's kernel search on the filled deltas.

**Verified hybrid** (our circuits 4 and 13, the public file for the rest; submission.npz byte-identical to the public one), `score_local.py --salt agentC-helper`:
`dfthcsos  PASS cost 3.00137e+08 ratio 11.1802 (15s)`, lambda_eff 46.89112671293601, toffoli_count 14990.0, num_qubits 427.
- Circuits 4 and 13 cost 276 / 280 Toffolis (201 products) against syed3000's 270 / 274 (195 products).
- The helper carry works: our cache matches theirs at 75–79. The whole gap is products.

**Blocker: products**
- On these exact words the open kernel search gives 223 uncoded and 201 coded, against syed3000's 216 and 195. The don't-care fill did not help (201 → 201).
- No single circuit of ours beats the matching public one, so a per-circuit hybrid cannot win.
- Headroom exists in principle. Each Toffoli adds s ⊗ (rank-2 matrix) to the low(15) × high(76) × output(35) GF(2) tensor. Dimension counting gives a lower bound of about 168 terms for coded circuits and about 187 for uncoded, against 195 / 216 today. Reaching it needs a GF(2) tensor-decomposition search (flip-graph style). That is research, not a port.
- Flip-graph feasibility on the current plans looks poor. The 401 rank-1 features share no b factor and almost no a factor (26 shares), so a Kauers–Moosbauer walk has very few reductions available.

## 6. Agent A's XAG synthesizer on a loader (2026-11-09): does not win

- Bench: `tools/chem/xag_loader_bench.py` imports `tools/xag/xag.py` unmodified.
- Inputs:
  - Targets: circuit 4 of the public table, i.e. the 35 signed-gauge output bits of the delta, extended to all 2048 addresses through their ANF over high monomials < 77.
  - Helpers: the 69 high monomials, 6 low monomials and the 5 carried top-bit helpers (80 helper ANDs; the carried 5 are counted as free).

| run | products | wires |
|---|---|---|
| keep_from=2, seed 0, 4 tries | 291 | 418, i.e. over the 128-qubit cap |
| keep_from=1, seed 1, 12 tries | 291 | 418, i.e. over the 128-qubit cap |
| keep_from=99 (no kept helper wires, fits the cap), seed 2, 12 tries | 667 | 127 |
| open kernel search (ours, §5) | 201 | 126 |
| syed3000 (public) | 195 | ≤128 |

- Why it loses: the per-target greedy with random fixed factors does not share rank-one features across outputs the way the tensor search does. Each Toffoli in the loaders fans out to up to 22 outputs.
- Not integrated. No candidate.

## 7. Chemistry feasibility day (2026-11-12): compiler experiment on the SUBMITTED loaders

**Outcome: no verified cheaper loader, and no costed route from the tested mechanism. Continuation is not recommended
on this evidence.** Table and weights were kept fixed throughout.

**1. Baseline (our submission, public v112 chem `8d4c99a2…`, ratio 11.2378).** From the unchanged verifier's full
output:

| Item | Value |
|---|---|
| Total T | 14,908 |
| Angle loaders | 4,123 T per pass × 2 = 8,246 |
| Heuristic (formula-priced, not compiler-controlled) | 6,662 T |
| Q | 427 |
| Loader cap | 128 qubits |

Per-loader static Toffoli-like counts (`operation_statistics`) sum to 4,123, equal to the verifier's executed mean:

| Loaders | Toffolis each |
|---|---|
| k0 | 297 |
| k1–k3 | 290 |
| k4–k14 | 267–270 |

Widths are 126–128. The submitted loaders already beat marculera's c44 set on k1–k5 (4,132 total there), so the
earlier "201 vs 195 products" gap is not the current baseline.

**2. Pinned loader.** `angle_k_9`, sha256 `c9d692b4…f04452`, 267 CCX:
- 11 selection qubits, 5 × 8 word qubits, 76 workspace qubits;
- 36,182 CX;
- 76 HMR and 76 R uncomputes, whose fix-ups are CZ only, so cleanup is Toffoli-free.

**3. Reproducible start.** `tools/chem/loader_span_scan.py` simulates ANGLE_0…ANGLE_k exactly as the verifier does
(`scoreinfra/circuits.py`):
- addresses 0…num_vectors−1 = 0…1,219;
- words start at zero;
- each circuit runs forward with words = batch k−1, **and again on the reverse traversal with words = batch k**.

**4. Mechanism tested: cross-output shared products.** At every CCX, is the product it XORs into its target already a
GF(2) combination of the other live qubits (plus 1) on every reachable state? If so it becomes CNOTs, with no width
and no Toffoli. This is exact on the reachable subspace, because CX and CCX act on basis states without phase.

| Scope | Hits |
|---|---|
| Forward states only, all 2,048 selection values (first run) | 1 in k9: CCX q0 q1 → q120 equals q17 ⊕ q18, the word_0 top-bit gauge helper |
| Forward **and reverse** entry states | 0 in k9: that identity fails when the words hold batch 9, so the first hit was a false positive |
| Exact verifier reachable set (1,220 addresses × forward and reverse), all 15 loaders, 4,123 CCX | **0** |

**5. Decision.** No loader beats the submitted one under this mechanism. Not tested:
- multi-gate re-synthesis, i.e. a lower-rank shared decomposition across outputs or a flip-graph search over the
  extracted bilinear terms;
- loader-aware re-rounding of the words (a table change, excluded today).

The dimension-count figure (~168) is a heuristic, not evidence that a cheaper decomposition exists for this table.
