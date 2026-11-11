# DQI decoder — measured profile (v95 public decoder, v100 diff) and failure analysis

Agent B, 2026-11-09. Nothing was submitted or committed.

**How to read the labels.**
- **MEASURED** numbers come from:
  - the circuit's own `INFO_TAG` stage markers; or
  - my independent bit-packed simulator (`csrc/prof.cc`). It reproduces the official verifier's mean T to within
    sampling noise (395,356.25 against 395,355.2) and gives 0 errors on 4,096 official-sampler shots. On the exact
    102,400 shots of the official run `Bsweep-00` it gives the same failure count as the verifier: 1 value error,
    0 phase errors;
  - the unmodified official verifier.
- **ESTIMATE** marks anything inferred from the generator source or from structural patterns.

**Artifacts** (all under `S=.../scratchpad/work_B`):
- `kmb.py`: numpy `.kmb` reader.
- `tagtree.py`, `tagseq.py`, `tgtwords.py`: static stage, tag and target-word censuses.
- `csrc/prof.cc`: the simulator, with per-stage mean T, live-qubit tracking, peak histograms and failure dumps.
- `sweep.py` and `sweep.jsonl`: official-verifier salt sweeps.
- `mysample.py`, `run_big.sh`, `bigfail/`: a paired census of ~1M shots per circuit.
- `run_w.sh`, `wfail/`: stress tests at fixed error weight.
- `replay_run.py`, `official_failshots.py`: exact replays of official runs.

## 0. Which circuit and which source

| | v95 (the one we submit) | v100 |
|---|---|---|
| file | `cand/pub/dqi.kmb` | `cand/pub3/dqi.kmb` |
| verifier `circuit_sha256` | f277b054… | (see `sweep.jsonl`) |
| Q | 892 | 892 |
| static T (max per shot) | 395,640 | 395,586 |
| mean T | 395,355.2 | 395,304.9 |

- The two differ only inside `convert` (−24 static T), `unconvert` (−24) and `unextract` (−6). Every stage boundary,
  peak and qubit count is identical.
- **The circuit carries its own stage tags** (17,700 `INFO_TAG`s). There are 11 top-level `@enter`/`@exit` marks:
  `mask_projection, initial, extract, synthesis, convert, scan, unconvert, unsynthesis, unextract, uninitial,
  restore_masks`. Below them are kernel tags: `inverse24 *`, `inverse12 *`, `multiply v`, `aligned_route`,
  `full_head_product`, `head_phase`, `head_pivot`, `gf_iadd`. **The stage boundaries below are therefore exact, not
  inferred.**
- **Generator source.** The Apache-2.0 generator lineage was found in Atakan Aldemir's Kaggle dataset
  `atakanaldemir/qcc-c44-five-helper-release-sources` (`release_source.xz`, 525 files). It contains SomeJoint's
  892-qubit "q26 + flag carry" decoder kit; the main file is `playbook/kit/decoder/final_decoder/decode.py`, plus
  Atakan's stream-rewrite plans. Its `decode()` emits exactly these 11 marks in this order.
- **v95 is that lineage after later stream rewrites** (product caches, measurement order, three cache routes). So
  the source explains the algorithm, but **rebuilding it would not give the v95 bytes**. I read the source and did
  not execute it.

## 1. Stage table (MEASURED; v95; mean over 4,096 shots from the official sampler; static = executed if all conditions true)

| stage | what it does (from source, ESTIMATE) | static T | mean T | % of T | HMR / shot | peak live Q | ops at 892 | separate excursions to 892 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| mask_projection | classical interpolation of 70 masks, Clifford phase on syndromes, 70 scan points zeroed | 0 | 0 | 0 | 0 | 840 | 0 | 0 |
| initial | fixed GF(2)-linear change of basis of the 70 syndrome words | 0 | 0 | 0 | 0 | 840 (883 briefly) | 0 | 0 |
| **extract** | in-place "confluent" continued-fraction / Schur extraction over 17 node groups in GF(2^24), then a 34-step GF(2^12) main chain, normal form and controlled inverse | 59,169 | **59,169.0** | 14.97 | 4,331 | **892** | 155,145 | 99 |
| **synthesis** | builds locator B and numerator A (continuant folds) from extracted heads | 31,635 | **31,635.0** | 8.00 | 1,324 | **892** | 1,341 | 1 |
| **convert** | half-degree Euclid: residue-converts A to A ≡ Ω·(σ′)⁻¹ mod σ (Forney folded in) | 60,687 | **60,687.0** | 15.35 | 6,377 | **892** | 10,112 | 16 |
| **scan** | Chien sweep, 4,025 of 4,095 points: XOR-sum, 12-bit zero test (11 ANDs), CZ with classically projected mask | 44,275 | **44,264.2** | 11.20 | 44,264 | 890 | 0 | 0 (4,025 to 890) |
| **unconvert** | reverse of convert | 62,558 | **62,478.6** | 15.80 | 11,062 | **892** | 33,831 | 50 |
| **unsynthesis** | reverse of synthesis | 40,429 | **40,429.0** | 10.23 | 3,883 | **892** | 77,407 | 117 |
| **unextract** | reverse of extract | 96,887 | **96,693.5** | 24.46 | 7,498 | **892** | 199,655 | 270 |
| uninitial / restore_masks | inverses of the linear maps | 0 | 0 | 0 | 0 | 840 | 0 | 0 |
| **total** | | **395,640** | **395,356.3** | 100 | | **892** | 477,491 | **553** |

### Grouped view (MEASURED)

| family | forward | reverse | fwd + rev | % of T | reverse − forward |
|---|---:|---:|---:|---:|---:|
| Extraction | 59,169 | 96,694 | **155,863** | **39.4%** | **+37,525 (9.5% of T)** |
| Conversion (Forney / residue) | 60,687 | 62,479 | **123,166** | **31.2%** | +1,792 |
| Synthesis | 31,635 | 40,429 | **72,064** | **18.2%** | +8,794 |
| Scan (Chien + phase) | 44,264 | — | **44,264** | **11.2%** | — |
| **All reverse stages** | 151,491 | 199,601 | | | **+48,110 (12.2% of T)** |

### Phase computation
The phase is applied **only in `scan`**, as a CZ between the zero flag, the summed A-word and the projected mask
bits.
- It costs **0 Toffolis**: `ccz(flag, A[0], m)` with classical m reduces to CZs.
- Scan Toffolis are exactly 4,025 points × 11 ANDs of the 12-bit zero test (all scan Toffolis target ancillas).
- The mean is 44,264.2 rather than 44,275 because a point whose projected mask is 0 is skipped (probability
  1/4096).
- Elsewhere, "phase" work is repayment of measurement-based uncomputation. Most of it is structural, i.e. the
  reverse-pass excess below. Toffolis that run only on HMR outcomes are small: static − mean = 79 in unconvert and
  194 in unextract.

### Inside extraction (MEASURED via tag sequence and target-word census; interpretation is ESTIMATE)
- **Forward.** There are 14 node blocks whose cost grows linearly: about 1.6k for the first, rising by ~368 Toffolis
  per block, up to 6.1k for the last. That is ≈184 Toffolis per chain step and ~266 chain steps, i.e. one GF(2^24)
  `mul24` of 99 ANDs plus one corrected product of 84–99 per step (source).
  - Each block ends with a 170-Toffoli GF(2^24) inverse (`inverse24` = 42 + 58 + 70).
  - The 34-step GF(2^12) main chain, normal form and controlled inverse add ≈3.0k.
- **Reverse.** The Toffolis aimed at the node words grow ≈566 per block, against ≈368 forward: 1.54× the forward
  cost per chain step.
  - Per node group gi, the **N-word targets roughly double** (S64: 3,153 → 6,165 for gi = 16; summed over groups
    +24.2k).
  - There is also +5.5k on ancillas, +1.0k CCZ (phase repayment), +1.3k CSWAP and +1.3k on the main-chain word.
  - ~~Source: the reverse re-runs the scalar chain twice.~~ **CORRECTED 2026-11-10 (v100 event-level census; source
    `exp/new/a01/companion.py`, "one scalar return").** v100 already runs **one** scalar return per node, not two.
    The older `final_decoder/decode.py` I first read does have the two-chain reverse; the lineage has since removed
    one chain.
  - Static accounting from 24-bit swap + Toffoli step signatures (`evacct.py`, `evgroups.py`):

    | Toffolis | forward | reverse |
    |---|---|---|
    | full chain steps | 196 steps, 36,155 | the same 196 steps, 36,155 |
    | 99-Toffoli scalar-type steps | 83, 8,217 | 294, 29,106 |
    | 12-bit 42-Toffoli steps | 43 | 94 |

  - So the reverse excess of +37.5k splits into:
    - **+23.0k** for the single scalar return (211 × `mul24` plus 51 × 42);
    - **+15.4k** for per-node glue: about 1.2k T + 75 CCZ + 96–120 CSWAP per node in reverse, against about 0.6k
      forward. This glue is the normalise-three, pay-before-retire and restore-direct steps of the companion.
  - **The one remaining scalar return is at the minimum for this architecture (argument, ESTIMATE).**
    - The forward stores normalised (N/D, L/D²) and HMR-measures D.
    - The reverse chain, run from D = 1, ends with the garbage scale λ = 1/D_f.
    - λ is a deterministic function of the restored node word u and the heads, so erasing it requires recomputing
      D_f(u, heads), i.e. one scalar chain.
    - Erasing λ by HMR instead creates a debt that again needs D_f.
    - Keeping D_f from the forward would cost 24 qubits per node.
    - The lineage reached the same "one scalar return" design.

### Inside conversion (MEASURED tag sequence)
This is a Euclid-style recursion of about 35 quotient steps.
- Each step costs one `inverse12` (58 T) plus an `aligned_route` (120 T), plus a polynomial update whose cost falls
  ~126 per step (3 × 42 ANDs per degree): 2,286 → 2,213 → 2,087 → … .
- CSWAPs (pivot and alignment routing under flags) total 4.6k forward and 5.7k reverse, about 2.6% of all T.
- convert ≈ unconvert. The reverse is a near-mirror (+1.8k).

## 2. Qubit timeline (MEASURED; "live" = nonzero in at least one of 4,096 shots, so it is a lower bound on allocated)

**Q = 892 = 840 syndrome qubits + 52 workspace.**

| point in circuit | live qubits | persistent state |
|---|---:|---|
| after `extract` | 841 | data in the 840 syndrome qubits + 1 pole flag |
| after `synthesis` | 841 | 13 ancillas (r word + pole), one syndrome word zero |
| during `scan` (steady) | 879 | 39 ancillas held through the scan: conversion flag bank (`KEEP_FULL`, 9 flags) + A/B overflow word + pole, etc.; the zero test adds 11 → 890 |
| end | 840 | — |

Coarse window maxima, per 1.5M ops:

| region | ops (M) | max live | note |
|---|---|---:|---|
| mask_projection, initial | 0–2.6 | 840 | |
| extract | 2.6–6.5 | 892 | |
| synthesis | 6.5–12.0 | 892 | mostly 877 |
| convert | 12.0–17.6 | 892 | median 885 |
| scan | 17.6–41.2 | 890 | flat |
| unconvert | 41.2–46.4 | 892 | |
| unsynthesis | 46.4–52.1 | 892 | |
| unextract | 52.1–57.9 | 892 | |

**Peak structure.**
- 892 is reached in **every** non-scan stage: **553 separate excursions**, 0.82% of all ops.
- Excursions by stage:

  | stage | excursions to 892 |
  |---|---:|
  | unextract | 270 |
  | unsynthesis | 117 |
  | extract | 99 |
  | unconvert | 50 |
  | convert | 16 |
  | synthesis | 1 |

- 891 is entered another 613 times and 890 another 4,725 times, including 4,025 in the scan.
- **Workspace reuse.**
  - 52 ancilla ids are shared by all kernels. Per-ancilla utilisation (fraction of ops holding data) runs from 0.23
    to 0.93; the most-used ids (860, 865–872, 887) are live 92–93% of the time.
  - The syndrome qubits themselves are workspace too. Extraction and synthesis are fully in place, and at the
    synthesis/convert boundary one syndrome word is all-zero and an ancilla word holds data instead.
- **Exchange rate.** 1 qubit = 2/892 = 0.224% of cost ≈ 886 Toffolis. Removing one qubit means removing all 553
  peak excursions, i.e. **≤ 1.6 Toffolis per excursion to break even**. The last qubit cannot be shaved locally;
  only an architecture change that lowers every stage's transient workspace by the same amount saves a qubit. This
  agrees with Alex Chilton's earlier measurement on an 877-qubit build.

## 3. Failure analysis

Final counts are in §3.4. The failure mechanisms (MEASURED):

1. **Low weight, deterministic, by design.**
   - Every shot with error weight w ≤ 17 fails (value error). Tested: 4,096 forced-weight shots each at
     w = 1–6, 8, 10, 12, 14–17, on both v95 and v100, **100% fail**. w ≥ 18 passes; see the stress table.
   - The verifier's weight law gives P(w ≤ 17) = **7.7 × 10⁻⁷**, i.e. 0.079 expected failures per 102,400 shots.
   - Cost ≈ 0.04% of expected ratio. Not worth fixing.
2. **v95 only: a w = 35 phase family.**
   - In my 1M-shot paired census, v95 fails on some w = 35 shots with a **phase** error; v100 never does.
   - The forced w = 35 stress test reproduces it: 1 in 4,096 on v95, 0 on v100.
   - It depends on HMR outcomes: the same input fails under 2 of 4 independent measurement-randomness seeds. That is
     the signature of a missing or wrong measurement-conditioned fix-up for a rare input class. Rate: see §3.4.
3. **Generic-weight value failures, deterministic in the input.**
   - One official v95 failure (salt `Bsweep-00`) is shot 3474, weight 27. My simulator reproduces it under different
     HMR randomness, so it does not depend on measurement outcomes.
   - Candidate classes (ESTIMATE, from the source's own disclosure): "rare degenerate pivot patterns, rare chance
     events such as an accidental zero in a 24-bit test". Root cause not yet isolated.
   - **Localised (MEASURED)** for official shot 97682 (Bsweep-00, w = 27) by comparing mirror states for that shot.
     - after `convert` = after `scan`: exact;
     - after `synthesis` = after `unconvert`: exact;
     - after `extract` ≠ after `unsynthesis`: 321 qubits differ.
     
     So **the synthesis round trip is not invertible for this input**. The source notes that "the forward synthesis
     multiplies; only its undo divides", so this is presumably an identity-at-zero division meeting a zero divisor
     (ESTIMATE). The other observed failures (w = 28, 30, 30) were not localised.
   - The w = 28 census failure fails on both v95 and v100, so this family is shared.

### 3.4 Results (MEASURED; pooled = 20 official salts + paired own census)

Protocol.
- **Official sweep.** Unmodified verifier, 20 salts `Bsweep-00`…`Bsweep-19` per circuit. Salt labels are shared, but
  the circuit hashes differ, so the shot sets are independent.
- **Own census.** 1,048,576 shots per circuit from my sampler, which uses the verifier's exact weight law. The census
  is *paired*: both circuits see the same shots. It was run on my simulator, which is validated against the verifier
  (same failure count on an exact replay).
- **Pooling.** The two data sets are pooled. Both are draws of (input, measurement outcomes) from the scored
  distribution.
- **E[ratio].** K ~ Binomial(102,400, p), passed through the verifier's own `clopper_pearson_upper_bound` and
  `repetition_overhead` (`expratio.py`, `final_stats.py`).
- **Held-out salts.** `Bval-00`…`Bval-09` have never been run and are reserved for final validation.

| | v95 (f277b054…) | **v100 (e9f54be3…, same file as public v101)** |
|---|---|---|
| mean T | 395,355.18 | **395,304.73** |
| official, 20 salts: value / phase | 5 / 1 | 6 / 0 |
| runs with 0 failures | 14 / 20 | 14 / 20 |
| mean ratio over salts | 65.129 | 65.137 |
| own census, 1,048,576 shots: value / phase | 3 (w = 17, 17, 28) / 4 (all w = 35) | 3 (the same shots) / 0 |
| **pooled failures / shots** | 13 / 3,096,576 | **9 / 3,096,576** |
| **p** (95% Clopper–Pearson) | 4.20e-6 [2.24e-6, 7.18e-6] | **2.91e-6 [1.33e-6, 5.52e-6]** |
| expected failures per scored run | 0.43 | 0.30 |
| **E[ratio]** at p̂ [CI ends] | **65.094** [65.151, 65.010] | **65.140** [65.186, 65.065] |

Family split (v95):

| family | v95 | v100 |
|---|---|---|
| w ≤ 17 (exact law, 100% fail) | 7.7e-7 | 7.7e-7 |
| generic value (5 seen in 3.1M) | ≈ 1.6e-6 [0.5e-6, 3.8e-6] | shared, same order |
| w = 35 phase (forced test: 15 / 151,552 w = 35 shots ⇒ 9.9e-5 per w = 35 shot × 0.0277) | 2.7e-6 [1.5e-6, 4.5e-6] | **absent**: 0 / 135,168 forced w = 35 shots |

**Conclusions.**
- **v100 is the base from now on.** It has lower T and no w = 35 phase family. Its E[ratio] is 65.140 against 65.094
  for v95.
- The "65.22 with 0 errors" headline of either file is a lucky draw: P(K = 0) is about 0.65 for v95 and 0.74 for
  v100.

## 4. Top 3 redesign candidates (ranked by measured share)

Cost = R·Q²·T. All gains assume **Q stays 892**: every stage already peaks at 892, so a redesign must not add
workspace anywhere. They also assume R is unchanged (no new failure families).

| # | target (measured share) | idea | gain if achieved | risk / qubit check |
|---|---|---|---|---|
| 1 (**CORRECTED 2026-11-10: the −24k target is not available in v100.** v100 already has the one-scalar-return; see §1. What remains in reverse extraction is the companion glue, ≈ +11–15k over forward, plus 8.8k in unsynthesis.) | **Reverse-pass excess: 48.1k = 12.2% of T.** Of this, unextract − extract = 37.5k (24.2k on node N-words) and unsynthesis − synthesis = 8.8k. | ~~Stop paying twice for normalisers.~~ (Superseded text follows.) Keep D (or λ = 1/D) live through the reverse chain and repay the gauge and invmask phases from it, then uncompute D with **one** reverse scalar chain instead of measuring it and rebuilding it twice. Equivalently, mirror the forward exactly so the reverse costs about the forward's 184 T/step instead of ~283. | **−24k T (one chain): cost ×0.939, DQI 65.2 → 69.4 (+6.4%).** Full parity (−37.5k): ×0.905, **→ 72.1**. Adding unsynthesis parity: −46k, ×0.884, → 73.8. | Medium. D is 24 qubits, but it is *already* live during these chains (they rebuild it), so holding it a little longer should not raise the peak. The unextract peak excursions (270) must be checked. |
| 2 | **Extraction chain steps: ~124k of the 156k = 31% of T** (266 forward steps × 184 + reverse steps × ~283) | (a) A cheaper GF(2^24) product. `mul24` is 99 ANDs and the corrected product 84–99. Every AND saved per step is worth ~0.13% of cost. (b) A lower-rank update per step, e.g. merge the corrected product and the head product into one bilinear form, or reuse factors' linear forms across the two products. | −10% of chain T ≈ −12k: cost ×0.970, **→ 67.2 (+3.1%)**. −20%: ×0.94, → 69.4. | High novelty and search effort (bilinear-rank / flip-graph search). Q-neutral if the kernels keep ≤ 43 private wires. |
| 3 | **Conversion: 123k = 31.2% of T**, quadratic Euclid with ~35 inverse + route steps and 10.3k CSWAP | (a) Remove CSWAP pivot routing (10.3k = 2.6%) by fixing the chart for the generic case (gap probability ~1/4096 per step; must stay exact or be priced). (b) Fuse conversion into synthesis: build the residue-converted numerator alongside B during synthesis. That would save up to the whole forward + reverse convert, but it is speculative. | (a) −5k: ×0.987, → 66.1 (+1.3%). (b) −30% of conversion ≈ −37k: ×0.906, → 72.0. | (a) low risk; (b) research. Any new pivot approximation adds rate p: each +1e-5 costs 0.45% of ratio. |

**Not recommended.**
- Qubit shaving (553 excursions, see §2).
- The scan: it sits at the 11-AND per-point floor and 70 points are already removed by the mask projection.
- Fixing the w ≤ 17 family: it is worth 0.04%.

~~**Order of attack.** Do #1 first.~~ **Revised 2026-11-10.** #1 in its stated form is already harvested in v100;
see the corrected §1.

What is left in the reverse extraction:
- the companion glue, ≈ +11–15k over forward (≈ +830 T per node, ×14 nodes);
- the unsynthesis excess, +8.8k, mostly 34 extra `inverse12` and the divisions of the undo;
- `mul24` cost: about 770 `mul24`-type products sit in extraction alone, so each AND saved in `mul24` is worth
  ≈ 770 T (0.19%).

Pole-handling removal was checked and is negligible: v100 already uses CX pole gauges. Only 48 never-firing CSWAPs
remain in extract and unextract.

## 5. Option A, milestone 1: per-node glue accounting (v100, 2026-11-10)

Source: `glueacct.py` on the coarse event streams `ev_extract.txt` and `ev_unextract.txt`. Static Toffoli-likes.
Labels are as stated.

| per homogeneous node (14 nodes, gi = 3…16) | forward (MEASURED) | reverse (MEASURED) |
|---|---|---|
| chain steps | (2gi) × {99 \| 99 + 84–90} | the same steps, mirrored |
| normalisation | "paired": 2 × 99-T products, counted as chain steps, + ≈ 188 T + `inverse24` 170 | **G1 = 1,034–1,091 T + 75 CCZ + 96–120 CSWAP + 126 T in 42-T steps ≈ 1,330–1,410** |
| zero flag + pole route | ≈ 122 T + 24 CSWAP | — |
| local `inverse24` of the next group | — | ≈ 190 T (mirror of the forward 170) |
| scalar return | — | (2gi − 2) × 99 |

**Interpretation (ESTIMATE, from `exp/new/a01/companion.py` + `frozen_chart.py` + `retained_core_safe27.py`).**
- **G1 = `normalize_three` + `pay_before_retire` + `restore_direct`.** The companion normalises three 24-bit values
  (N, √L and the copied ratio R) in the high-component chart.
  - Each value costs 4 × 42 T, the chart flag adds 12 + 36 CSWAP, and there are 3 `inverse12` (≈ 58 each).
  - Two `linear_inverse_character` phase repayments supply the CCZ.
  - R is what makes the single scalar return possible.
- **The companion is a trade.** Replacing the old two-chain return (≈ 580 T of paired-normalisation glue plus a
  second (2gi − 3) × 99 chain) by G1 + one chain pays off when (2gi − 3) × 99 > ≈ 830, i.e. for gi ≥ 6.
  - For gi = 3, 4, 5 the old return would be cheaper by ≈ 530, 330 and 140 T: **≈ 1.0k T in total (0.25%)**.
  - Building that needs the lineage's generator (forward token formats differ between the two designs).
- **No pure mirror exists.** The forward glue (≈ 630 per node) includes the gauge measurement of D, so the reverse
  cannot be a literal inverse of the forward (see §1).
- **Gate-level scan of all CCX** over 65,536 shots (2 × official-distribution, plus w = 18 and w = 35 stress sets):
  - 0 CCX are pure "uncompute-AND" (MBUC is already used everywhere).
  - 487 CCX have a product equal to one control on all sampled shots (CCX → CX candidates).
  - 397 CCX never fire.
  - Neither class is proven structural. Removing a gate saves 1 T (0.00025%), while any violation with rate above
    ~5e-9 per shot costs more through R. **Not recommended without proofs.**

**Status.** No safe large sub-step was identified in G1 without a source-level redesign of the companion. Executing
the downloaded generator to obtain sub-step marks was blocked by the session's permission policy.

## 6. Option C: the GF(2^24) 99-AND multiplier (2026-11-10)

**Result: no lower-rank formula was found. Nothing was built; v100 is unchanged.**

### 6.1 Kernel identity (MEASURED from v100; scripts `mulc/extract_kernel.py`, `symsim.py`, `analyze_tensor.py`)

- **Instances.** There are 6 tagged `multiply v` instances in extract and 6 in unextract. Their canonical op
  sequences are identical: 6,393 ops = 6,294 CX + 99 CCX, and no other op types.
- **Qubits.** Each instance touches exactly 72 qubits: x = q48–71 (syndrome words 4–5), y = q72–95 (words 6–7), and
  z = 24 ancillas. **There are no temporaries and no HMR.**
  - The linear forms are built in place on x and y by CX.
  - Each AND is XORed straight into z, with CX fan-out for multi-bit outputs.
  - x and y are restored exactly.
- **Map.** The kernel computes z ^= B(x, y).
  - Symbolically, B is bilinear (0 non-bilinear monomials) and symmetric.
  - It has no zero divisors (0 of 2,000 random x give a singular left-multiplication). So it is GF(2^24)
    multiplication up to fixed linear basis changes on the three registers. The register qubit orders differ,
    which is why the raw tensor is not associative in qubit order.
- **Formula.** The 99 rank-one terms read off the circuit are all symmetric, L_r(x)·L_r(y)·v_r. They reproduce B
  exactly on all 576 basis pairs.
- **Tower.** The terms form 11 consecutive blocks of 9. Each block's 9 masks span exactly 4 dimensions, and so do its
  9 output vectors.
  - This **confirms GF(16)^6: 11 evaluations (points 0…9 of GF(16), plus ∞) × GF(16) multiplication at rank 9
    (GF(4)^2, 3 × 3)**. It matches the source docstring of `exp/mul99/kernels.py`.
- **Workspace.** Zero extra qubits. A replacement formula of the same in-place form would be Q-neutral. Per the
  source, the chain-step instances (`mul24_xor99`) are the same tensor in a CNOT-related "extension" basis (ESTIMATE,
  not extracted).
- **Usage.** About 769 instances run in extraction per shot, ≈ 76k T, so each AND saved is worth ≈ 770 T (0.19%).

### 6.2 Search (derivations, not a literature lookup; arXiv is unreachable here)

Inner layers are provably optimal:
- μ_16(6) = 11 = 2·6 − 1. That is the general lower bound, attained because 6 ≤ 16/2 + 1.
- μ_2(4) = 9 is the known exact value.

**So the tower cannot improve layer by layer.** Alternative decompositions, using the best constructions I could
build:

| decomposition | inner rank | outer rank | total |
|---|---:|---:|---:|
| GF(16)^6 (current) | μ₂(4) = 9 | 11 | **99** |
| GF(4)^12, CRT over GF(4): 5 linear + 6 quadratic + 2 cubic places | 3 | 33 | 99 |
| GF(4)^12, elliptic CCMA, any trace t ∈ [−4, 4] (N1 + 2·N2 limits) | 3 | ≥ 33 | ≥ 99 |
| GF(4)^12 costed directly at GF(2) level (linear 3/deg, quadratic 4.5/deg, cubic 5/deg, need 23 deg) | — | — | 99 minimum |
| GF(8)^8, CRT: 9 linear + 3 quadratic | 6 | 18 | 108 |
| GF(8)^8, elliptic CCMA (N1 ≤ 14) | 6 | ≥ 17 | ≥ 102 |
| GF(64)^4 | 15 | 7 | 105 |
| GF(256)^3 | 24 | 5 | 120 |
| GF(4096)^2 (Karatsuba) | 42 | 3 | 126 |

**Shared-operand idea, not pursued.** The corrected product h·(D²)_lo, h·(D²)_hi costs 84. The GF(4) analogue of a
shared-operand product has rank 6 = 2 × 3 by JáJá's pencil theorem, so I found no evidence of a saving.

**No SAT or flip-graph search was run.** The only sub-layers small enough to search are provably optimal, and a
direct search for rank ≤ 98 on the 24 × 24 × 24 tensor is far beyond the timebox.

**Open lead.** A genus ≥ 2 Chudnovsky construction, or a published bound μ₄(12) ≤ 32, would give ≤ 96 ANDs, saving
≈ 2.3k T per AND-triple. That needs literature access.

## 7. Bridge: generator output 7bd10fca vs v100 (MEASURED, 2026-11-11)

Method: `prof.cc`, 4,096 official-sampler shots, the same inputs for both circuits, stages by INFO_TAG. The generator
names its unsynthesis stage `padded_unsynthesis`.

| stage | 7bd static | v100 static | 7bd mean | v100 mean | Δ mean (v100 − 7bd) | 7bd peak (892-excursions) | v100 peak (892-excursions) |
|---|---:|---:|---:|---:|---:|---|---|
| extract | 62,079 | 59,169 | 62,079.0 | 59,169.0 | **−2,910** | 892 (65) | 892 (99) |
| synthesis | 32,255 | 31,635 | 32,255.0 | 31,635.0 | −620 | 892 (1) | 892 (1) |
| convert | 60,060 | 60,663 | 59,851.3 | 60,663.0 | **+812** | **890 (0)** | 892 (16) |
| scan | 44,275 | 44,275 | 44,264.2 | 44,264.2 | 0 | **882** | 890 |
| unconvert | 76,478 | 62,534 | 61,350.9 | 62,454.6 | **+1,104** | **890 (0)** | 892 (50) |
| (padded_)unsynthesis | 58,633 | 40,429 | 41,734.9 | 40,429.0 | −1,306 | 892 (45) | 892 (117) |
| unextract | 124,423 | 96,881 | 101,967.4 | 96,690.1 | **−5,277** | 892 (108) | 892 (270) |
| **total** | 458,203 | 395,586 | **403,502.8** | **395,304.9** | **−8,198** | | |

Reading the table:
- **The "62k static" gap is mostly conditional fix-ups.** 7bd's reverse stages hold 54.7k static Toffolis inside
  HMR-conditioned blocks, which execute about half the time. In mean T, v100 is 8.2k cheaper.
  - The saving sits in extract (−2.9k), unextract (−5.3k) and unsynthesis (−1.3k).
- **v100 is worse in conversion.** Its convert, scan and unconvert block costs +1.9k mean T and is wider (892
  against 890).
- **The lineages diverged at source level.**
  - v100's reverse stages are not stream rewrites of 7bd10fca: the reverse-node glue has a different structure.
  - The prefix up to `extract` (mask projection + initial) is identical op for op.
  - The register layout is identical.
- **Conversion boundary (MEASURED on 4,096 + 4,096 held-out shots).** At `@enter:convert`, v100's 841 live qubits
  are an exact affine image of 7bd's state, and 7bd's other 841 live qubits are affine in v100's.
  - 7bd additionally carries 2 held flags (q865, q889), which its convert…unconvert block never touches.
  - Both blocks read only the 48,300 E bits from outside and have no live-out classical bits.
  - So the block is transplantable.

## 8. Candidate C1: v100 with the generator's conversion block (approach b, v100 splice)

**Construction** (`tools/dqi/splice/build_c1.sh`, deterministic, SHA-256-checked inputs):
1. Take v100 up to `@enter:convert`.
2. Insert `bridge_in`: 3,171 CNOTs implementing the affine map fitted on the boundary states (rank 842).
3. Insert 7bd10fca's ops from `@enter:convert` to `@exit:unconvert`. Its 841 internal classical bits are renumbered
   to fresh ids; E bits are kept.
4. Insert `bridge_out`: the inverse CNOTs.
5. Append v100 from `@exit:unconvert` onward.

Checks:
- The affine map is checked on 4,096 held-out official-sampler shots: 0 mismatches.
- A rebuild from scratch reproduces sha256 `ca59beb811b604c4c18114597745d96fa4ca62dafb131db7c274a558aa5ffb83`.

| | v100 | **C1** |
|---|---:|---:|
| mean T (`prof`, 4,096 shots) | 395,304.9 | **393,390.4** (−1,914.5) |
| static T | 395,586 | 408,927 (static includes the half-executed fix-ups) |
| Q | 892 | 892 |
| convert / scan / unconvert peak | 892 / 890 / 892 | **888 / 880 / 888** (66 excursions to 892 removed) |
| own census, 1,048,576 paired shots | 3 value (w = 17, 17, 28) | **the same 3 shots**, no others |
| forced-weight stress, w = 18…35, 8,192 shots each, + 3 extra w = 35 sets (172k shots) | 0 / 0 | 0 / 0 |

Credits: the block is from atakanaldemir/qcc-c44-five-helper-release-sources v1 (Apache-2.0; SomeJoint, Atakan
Aldemir, yoyobar, Ali Haydar Özdağ, manwithacat and the lineage in its CREDITS). The host is public v100 (lineage
credited in the heliosli and kirilltym notebooks). Notices are retained.

## 9. Structural step: can Q drop to 891? Step-1 estimate (2026-11-11). Result: NO within budget

The budget was Q ≤ 891 everywhere, at most +400 mean T against C1 (break-even +886), and failure rate unchanged.

### What the generator's width knobs do (read from source)

- **`--ceiling X`** (`tools/carry_width_select.py`) retunes only the existing width-adaptive selectors.
  - Inside functions that read `b.num_allocated_qubits`, it replaces the constant 892 with X (889 ≤ X ≤ 900).
  - It also replaces `ceiling` closures and defaults equal to 892.
- **`--flag-mbu-ceiling X`** (`tools/carry_flag_mbu.py`) picks, at X allocated qubits, a width-preserving variant of
  the HW06/HW07 zero-flag retirement (one clean flag, two dirty borrowed wires).
- **The pinned build already uses both at 891, yet still peaks at 892.**
  - 7bd10fca has 219 excursions to 892: extract 65, synthesis 1, padded_unsynthesis 45, unextract 108.
  - So fixed-width kernels, which no selector covers, set the peak.

### Route A: build from the generator (MEASURED from the §7 bridge)

- The generator's non-conversion stages already cost **+10.1k mean T** against v100's (C1 keeps v100's):
  extract +2.9k, synthesis +0.6k, unsynthesis +1.3k, unextract +5.3k.
- A generator-based Q = 891 decoder is therefore ≥ +10.1k mean T against C1 even before any narrowing penalty.
  That is 11× break-even and 25× the target.

### Route B: narrow C1 itself (MEASURED; `idle_at_peaks.py`, `freeable.py`, `andfree.py`)

C1 has **487 excursions to 892**, all in v100-derived stages:

| stage | excursions to 892 |
|---|---:|
| extract | 99 |
| synthesis | 1 |
| unsynthesis | 117 |
| unextract | 270 |

The conversion block is already ≤ 888.

For each excursion window I took the full state on 4,096 official-sampler shots and the live qubits untouched within
the window, and asked whether one of them can be removed cheaply:

| stage | windows | an idle qubit is an affine function of other idle qubits (0 T: CNOT out, CNOT back) | an idle qubit is an AND of two idle literals (1 T) | neither |
|---|---:|---:|---:|---:|
| extract | 99 | 5 | 0 | **94** |
| synthesis | 1 | 0 | 0 | **1** |
| unsynthesis | 117 | 58 | 0 | **59** |
| unextract | 270 | 104 | 0 | **166** |

The idle qubits at the peaks are data-bearing: syndrome-word coefficients and heads, between 25 and 855 of them
depending on the margin. They carry information and are not recomputable temporaries.

**Cost of Route B.**
- The 320 "neither" windows need a deeper nonlinear recompute, at ≥ 2 T each, so ≥ 640 T optimistic. Earlier
  measurements on an 877-qubit build put it at 23–42 T per window, i.e. ≈ 7–13k T.
- A global qubit renaming (interval colouring of live ranges, with rare-input-safe ranges) would also be needed.

**Conclusion.** Q = 891 is not reachable within +400 mean T by either route. Stopped at step 1 as instructed; no
generator run was made.

**Possible side gain (not pursued).** The 167 windows that are freeable at 0 T do not lower Q, because Q is the
maximum over all windows.
