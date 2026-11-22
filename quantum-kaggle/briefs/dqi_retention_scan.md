# DQI product-retention scan, checkpoint 1 (2026-11-22)

**Verdict.** No valid retention site exists at the current width (Q = 890). The stop condition is met: what remains is
either invalid on rare shots or needs extra width that costs more than it saves. Nothing was built or submitted, and
the provisional pair mix11 + mix12 is unchanged.

**Subject.** The pinned frontier DQI `f56b04c7` (sha256 in `tools/dqi/retain/results_2026-11-22/base_sha256.txt`).

**Target.** About 42 Toffolis/shot for the top 100, with ≥ 100 preferred.

## Method
Tool: `tools/dqi/retain_scan.cc`. It is an own bit-packed simulator with the same semantics as `prof.cc`.
- **Accuracy check:** on the discovery sample the sampled mean of executed Toffoli-like gates is 365,847.80/shot,
  against 365,848.04 from the official verifier.

**Identity is tested on values, not wire names.**
- At each Toffoli-like gate the tool hashes the executed product plane, including the condition stack and any per-op
  condition:
  - CCX: cond·a·b;
  - CSWAP: cond·c·(x⊕y);
  - CCZ: all three pair products.
- The two factor planes are hashed too. This separates "same factors" from "equal product by coincidence".
- Discovery used 16,384 official-distribution shots, seed 777001.

**The retention construction, if a site qualified** (all added gates are Clifford or HMR, 0 Toffolis):
- At source i: `CX t f; <gate i>; CX t f`, leaving f = P_i whatever t held before.
- At destination j: the Toffoli is replaced by `CX f t_j`, keeping j's condition.
  - Then `HMR f m`, followed by `CZ a_j b_j` under (j's condition AND m).
  - This is exact when P_i = cond_j·a_j·b_j as functions of every input and coin. f is 0 wherever j's condition is false.
- Hand-offs of f between free wires cost CNOTs only. So a pair is width-feasible iff some free wire exists at every
  op in [i, j]. The free wire need not be the same one throughout.

**Workspace check** (per-op profile of wires that the op does not touch):
- certain-zero: last write was an unconditional R/HMR (or never written, and not an input);
- sample-zero: zero on every sample. This is weaker, because a wire can hold a rare value.

**Composition.**
- A set of pairs is jointly feasible iff, at every op, the number of covering pairs ≤ the number of free wires.
- We take a greedy by right endpoint over compressed segments, using a lazy segment tree (`retain/compose.py`).

**Stress validation** (`retain_scan check`, `retain/tally.py`): 17 independent sets of 16,384 shots, 278,528 shots in
all.
- 8 official-distribution sets (131,072 shots).
- 4 sets at error weight 35, 2 at 34, 1 at 33 and 1 at 32: the rare-coincidence regime.
- 1 set uniform over weights 17–35.
- A self-check on the discovery sample gives 0 violations, as it must.

## Funnel (as requested)

| Stage | Count | Toffolis/shot |
|---|---:|---:|
| Raw matches: gate pairs with identical executed product, product ≠ 0 on ≥ 100 of 16,384 shots | 164,185 pairs; 131,933 consecutive (nearest earlier match) | — |
| (excluded at intake: products 0 on all samples) | 1,895 gate records | — |
| (excluded at intake: products 1 on only 1–99 shots, too rare to test) | 16,771 consecutive pairs | — |
| Semantically plausible: source can hold the value (CCX/CSWAP), same factor planes, not a plain uncompute | 131,411 | 131,411 |
| Individually width-feasible at Q = 890, certain-zero wires, hand-offs allowed | 11 (one cluster, op 21.58M, 173 ops apart) | 11 |
| Individually width-feasible at Q = 890, sample-zero wires | 121 (the 11 plus 110 in 4 groups, 20K–147K ops apart) | 121 |
| Survive the 17-set stress validation | 110; all 11 of the 21.58M cluster fail on weight-35 shots | 110 |
| Jointly compatible | ≤ 4: each of the 4 groups passes a bottleneck with a single sample-zero wire | ≤ 4 |
| That bottleneck wire is free | **0**: in all 4 it is q889, holding a rare AND flag | 0 |
| **Estimated net saving at Q = 890** | | **0** |

**The q889 bottleneck.**
- q889 is written by `CCX q873 q864 → q889` (op 48,908,876).
- It is idle across the group-2 interval and consumed by `CX q889 q840` (op 48,936,033).
- So it is zero on our samples, but it is a live, rarely-1 flag. Borrowing it would corrupt exactly the shots it exists
  for.
- The other three groups use the same wire for the same role.
- This agrees with goodpjw2008's width analysis: the 890th wire often holds a "pivot is zero" flag or a retained AND.

**The 21.58M cluster** (11 pairs).
- Valid on every official sample, but violated on weight-35 shots.
- This reproduces independently goodpjw2008's rejected conditional swaps.

**Where the distance goes.**
- 123,589 of the 131,411 pairs are ≥ 1M ops apart: forward-pass products repeated in the reverse pass.
- None of them is width-feasible, because the decoder reaches 890 live qubits in about 1,700 separate episodes.

## Extra width does not pay

| Width | Jointly compatible pairs (upper bound, not stress-validated) | Cost of the width | Net |
|---|---:|---:|---:|
| Q = 891 | 116 | ≈ 823 Toffoli-equivalents (Q² × 0.225%) | ≈ −707 |
| Q = 892 | 221 | ≈ 1,647 | ≈ −1,426 |

## Side findings (not retention; excluded)

**(a) "Product equals one factor" downgrades** (CCX → CX, no workspace).
- 218 frequent-product gates (201.5 Toffolis/shot) and 1,546 rare-product ones (1,537/shot) pass on the discovery
  sample.
- After the 17 stress sets, 103 (95/shot) and 53 (48/shot) survive.
- All 113 of the frequent-product candidates that survived the first 12 sets lie in the tails of 17 zero-test AND
  chains, so the identity fails exactly on coincidental register matches. That is what the chains exist to detect.
- **The break-even makes sampling useless here.** One added failure costs about 0.46% of the DQI ratio, while one
  Toffoli saves 2.7e-6. So a downgrade pays only if it is wrong on fewer than about 6e-9 of shots.
- No sample can show that; it needs a structural proof, and none exists for these chains. Excluded.

**(b) Gates whose product is 0 on all samples.**
- There are 1,895 product records (1,437 CCX), including 349 uncompute-shaped CCX worth 305.5 Toffolis/shot.
- They are presumably coincidence detectors that fire only on rare shots. The same break-even applies. Excluded.

## Checklist against the funding conditions
- **Identity:** value planes were compared, including conditions, and the factors themselves. Pairs were stress-validated
  on 17 sets.
- **Phase and cleanup:** the construction was specified (source CX bracket; destination CX; HMR with a conditioned CZ
  on the destination's controls). It was never needed.
- **Workspace:** certain-zero and sample-zero wires were profiled per op, with hand-offs allowed.
- **Composition:** solved under a capacity constraint.
- **Net and execution-weighted:**
  - all width-feasible candidates are unconditional (weight 1.0);
  - the added gates are free;
  - none survives, so the net saving is 0.

## Files
- `tools/dqi/retain_scan.cc`: modes hash / free / profile / check.
- `tools/dqi/retain/`: `recs.py`, `rangemin.py`, `compose.py`, `tally.py`.
- `tools/dqi/retain/results_2026-11-22/`: candidates, check outputs (tgz), stress tally, composition, bottleneck wires.
- The discovery hashes and per-op profiles are about 260 MB and live in the session scratchpad (`ret/`). Regenerate
  them with `gen_inputs.py <comp> 16384 777001` plus `retain_scan hash|profile` (17–22 s each).
