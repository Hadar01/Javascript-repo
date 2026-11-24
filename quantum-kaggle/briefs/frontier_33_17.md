# The 33.17 public frontier, reproduced (2026-11-24)

Our mix11 (public 28.23837) had fallen to rank 1,221 of 3,656. The public board now has:
- 305 teams at 33.17067;
- the top 100 at 33.17069;
- #1 at 34.15280 (Entangled Team).

We reproduced the public 33.17 portfolio from published files and scored it with our unchanged official verifiers.

## Three-task comparison against mix11 (official verifiers, unmodified)

| Task | mix11 (ours) | 33.17 set | Ratio change | What changed in the circuit |
|---|---|---|---|---|
| invsqrt | `acc7b9c8`: 44 qubits, 1,450.44 Toffolis, T 4.0, 33 rotations; cost 74,361.8 (ratio 27.928) | `bb676b95`: **37 qubits**, 1,406.31 Toffolis, T 5.5, 33 rotations; cost **60,927.6** (ratio **34.086**) | **+22.1%** | Rithvik Redrouthu's 37-qubit circuit (`d2148a7c`, Syed Asad Ali's generator line) with varianceofx's three-T phase edit. The gain is mostly **7 fewer qubits** at a similar Toffoli count. |
| DQI | `f56b04c7`: 890 qubits, 365,848 Toffolis; ratio **70.795 at K=0** | `a931fcfe` (mix18) / `dbb2ada3` (mix19): **900 qubits**, **316,134 / 316,124 Toffolis**; ratio **80.118 / 80.121 at K=0** | **+13.2%** | tonylica's decoder `4b572141` on ThemBones' line. It spends **+10 qubits** (+2.3% in Q²) to save **13.6% of Toffolis**. `dbb2ada3` adds approximate rewrites (see below). |
| chemistry | 427 qubits, T 14,706, λ_eff 46.92156; cost 2.94642e8 (ratio 11.389) | **405 qubits**, T 13,214, λ_eff 46.91798; cost 2.51090e8 (ratio **13.364**) | **+17.3%** | maoxin123's v3 loaders: 3,357 Toffolis per pass, against 4,022 in ours. The structure needs **22 fewer qubits**. The weights barely matter. |
| **GM** | 28.238 (K=0) | **33.170 (K=0)** | +17.5% | |

**DQI: zero-failure versus fresh-salt results.**

| | K=0 ratio | Salt nov24-a (fresh) |
|---|---|---|
| a931fcfe | 80.118 | K=1: cost 3.06446e11, ratio 79.751 |
| dbb2ada3 | 80.121 | K=1: cost 3.06436e11, ratio 79.754 |

- Public draws:
  - `a931fcfe` is known to be K=0 (No Bodies' mix17 scored 33.17035 with it);
  - `dbb2ada3` will be known when mix19 scores.
- **This line fails more often than our old 890-qubit line.** goodpjw2008 reports about one inherited failed shot per
  102,400-shot run for `4b572141`. Our earlier line had 5 / 1,126,400.
- So a private draw has a sizeable chance of K ≥ 1, and each failure costs about 0.05 GM.
- Equal-budget sweeps are needed before final selection (the §4 process in `final_selection.md`).

**Approximate rewrites in the DQI line.** These were not in our earlier circuits. They are expected-value trades
rather than exact identities:
- goodpjw2008's ten zero-test cuts in 33.17067: CCX→CX at positions 17–24 of a 24-bit zero test. The wrong-shot
  probability halves per position; they report 6.8e-4 expected wrong shots per run, against −9 Toffolis per shot.
- Atakan Aldemir's eight conditional cleanup edits in `dbb2ada3`. His NOTICE: "universal DQI correctness is not claimed".
- This is the same class we excluded on 2026-11-22. Our exclusion rule asked for a proof. Their rule asks for an
  expected loss below the gain, with an extrapolated failure model.
- **A policy decision for the supervisor.**

## Provenance (sha256, source, version, licence)

| Component | sha256 | Source | Licence / notes |
|---|---|---|---|
| invsqrt | `bb676b95f94c923cc5482f6cd8d457ab5ff3e8180c8f7cfd2c9678335d0ba56b` | maoxin123, *qcc-33-17-3-357-toffoli-chemistry-loaders* v3. It is varianceofx's three-T edit (*vqcc-three-t-phase-compiler* v1) of rithvikredrouthu's `d2148a7c`. | Apache-2.0 chain. Syed Asad Ali is credited first per his NOTICE. |
| DQI (mix18) | `a931fcfee0f04d49…` | aakashhowlader, *no-bodies-mix17-vqcc-33-17035*: the No Bodies variant of tonylica's `4b572141` (*quantum-ai-32-85306-ready*), with the same gates. | tonylica's notes: Apache-2.0 own-work scope; it does not relicense inherited components or "the unlicensed QuantumAI generator" (hosts' material, usable for the competition). |
| DQI (mix19) | `dbb2ada3a4dade83…` | atakanaldemir, *qcc-shared-products-phase-cleanup-20261124*: ozertuu V46 (goodpjw2008 and evgendvorkin rewrites) plus 8 cleanup edits. | NOTICE kept; correctness is sampled, not universal. |
| chemistry loaders (15) | `angle_k_0` = `f2004c1f…` (all 15 identical in both sets) | maoxin123 v3: 3,357 Toffolis/pass, on the marculera / ThemBones / Almond Labs lineage. | Apache-2.0 chain. |
| chemistry npz | `17a7658245230231…` (Atakan); `508364c7…` (mix17) | Atakan's bounded scaling of prvsiyan's factor refit. | NOTICE kept. |

All three tasks PASS under our unmodified verifiers. Local GM on salt nov24-a is 33.11954 for mix17 (K=1). At K=0 it is
33.170.

## Submitted (2026-11-24)
- **mix18** (ref 58818853): `bb676b95` + `a931fcfe` + chemistry `17a76582`. Expected public about 33.1704, since the
  public draw of `a931fcfe` is known to be K=0.
- **mix19** (ref 58818871): `bb676b95` + `dbb2ada3` + chemistry `17a76582`. Its public draw is unknown.

## Where the remaining 2.96% to #1 has to come from
- #1 is at 34.15280, which is +2.96% GM over 33.17. That requires one of:
  - one task 8.4% cheaper with the other two fixed;
  - each task 2.9% cheaper.
- The 28 → 33 jump came from **structure and width** in every task:
  - invsqrt −7 qubits;
  - chemistry −22 qubits and −10% Toffolis;
  - DQI −13.6% Toffolis for +10 qubits.
- Micro-edits are worth about 1e-5 each.
- The folded-residual invsqrt idea is priced in `fusion_folded_pricing.md`. As a table design it loses to this
  baseline at every width.

## Next-stage screen: invsqrt width (2026-11-24)
- One qubit off `bb676b95` would be worth +2.8% on invsqrt, about +0.30 GM on its own. That is the largest per-unit
  lever in the portfolio.
- Exact width profile over all x (`tools/invsqrt/width_profile.py`, 2 coin seeds):
  - 10,645 of 60,766 ops need all 37 qubits;
  - they fall in **351 separate peak episodes**.
- A 1-qubit cut must relieve every episode, so the width is saturated in the same way as the DQI's 890th wire.
- Not a cheap next bet. Needs a structural redesign of the arithmetic, not a local edit.

## Next-stage screen: DQI a931fcfe profile (2026-11-24)
- Own simulator (`prof`), 4,096 official shots: mean 316,140.7 Toffolis, 0 value/phase errors, peak 900 qubits.
- Per-1M-op windows (`tools/dqi/finalsel/a931fcfe_timeline_1M.tsv`):
  - the Toffolis are spread over about 49 windows, the largest holding about 7% (op 31M, 22,954);
  - the width is at 900 in almost every window from op 21M on.
- No single dominant stage.
- A DQI saving at the size #1 needs (about 8% of DQI cost) requires a stage-level algorithmic redesign, not local
  edits. Mapping windows to decoder stages is the next step if this task is chosen.
