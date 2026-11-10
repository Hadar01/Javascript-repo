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
  - Source: the reverse pass re-runs a "scalar chain" (D/N recurrence, one `mul24` per step) to rebuild each node's
    normaliser D. It needs D to repay the phases of the forward `gauge` HMR and of its own `invmask` HMR
    (`external_node_chain(..., reverse=True)`, `extraction(reverse=True)`).
  - **This recomputation is the single largest identifiable redundancy in the circuit.**

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

See the results block at the end (§3.4) for the final counts. Mechanisms MEASURED so far:

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

## 4. Top 3 redesign candidates (ranked by measured share)

Cost = R·Q²·T. All gains assume **Q stays 892**: every stage already peaks at 892, so a redesign must not add
workspace anywhere. They also assume R is unchanged (no new failure families).

| # | target (measured share) | idea | gain if achieved | risk / qubit check |
|---|---|---|---|---|
| 1 | **Reverse-pass excess: 48.1k = 12.2% of T.** Of this, unextract − extract = 37.5k (24.2k on node N-words) and unsynthesis − synthesis = 8.8k. | Stop paying twice for normalisers. Keep D (or λ = 1/D) live through the reverse chain and repay the gauge and invmask phases from it, then uncompute D with **one** reverse scalar chain instead of measuring it and rebuilding it twice. Equivalently, mirror the forward exactly so the reverse costs about the forward's 184 T/step instead of ~283. | **−24k T (one chain): cost ×0.939, DQI 65.2 → 69.4 (+6.4%).** Full parity (−37.5k): ×0.905, **→ 72.1**. Adding unsynthesis parity: −46k, ×0.884, → 73.8. | Medium. D is 24 qubits, but it is *already* live during these chains (they rebuild it), so holding it a little longer should not raise the peak. The unextract peak excursions (270) must be checked. |
| 2 | **Extraction chain steps: ~124k of the 156k = 31% of T** (266 forward steps × 184 + reverse steps × ~283) | (a) A cheaper GF(2^24) product. `mul24` is 99 ANDs and the corrected product 84–99. Every AND saved per step is worth ~0.13% of cost. (b) A lower-rank update per step, e.g. merge the corrected product and the head product into one bilinear form, or reuse factors' linear forms across the two products. | −10% of chain T ≈ −12k: cost ×0.970, **→ 67.2 (+3.1%)**. −20%: ×0.94, → 69.4. | High novelty and search effort (bilinear-rank / flip-graph search). Q-neutral if the kernels keep ≤ 43 private wires. |
| 3 | **Conversion: 123k = 31.2% of T**, quadratic Euclid with ~35 inverse + route steps and 10.3k CSWAP | (a) Remove CSWAP pivot routing (10.3k = 2.6%) by fixing the chart for the generic case (gap probability ~1/4096 per step; must stay exact or be priced). (b) Fuse conversion into synthesis: build the residue-converted numerator alongside B during synthesis. That would save up to the whole forward + reverse convert, but it is speculative. | (a) −5k: ×0.987, → 66.1 (+1.3%). (b) −30% of conversion ≈ −37k: ×0.906, → 72.0. | (a) low risk; (b) research. Any new pivot approximation adds rate p: each +1e-5 costs 0.45% of ratio. |

**Not recommended.**
- Qubit shaving (553 excursions, see §2).
- The scan: it sits at the 11-AND per-point floor and 70 points are already removed by the mask projection.
- Fixing the w ≤ 17 family: it is worth 0.04%.

**Order of attack.** Do #1 first. It is a pure uncomputation-schedule change inside a stage we can isolate by tags,
it is measured, and its gain is large. #2a can run as a background search. #3a is a cheap side task.
