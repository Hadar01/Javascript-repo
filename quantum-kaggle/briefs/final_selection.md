# Final-selection analysis (2026-11-18). No pair chosen yet.

Kaggle's final score is the better private score of the two submissions we select. This note measures what drives
that score for our candidates and how much a second submission adds.

## 1. What the private salt can change (measured)

| Task | Salt sensitivity | Evidence |
|---|---|---|
| dfthcsos | none: cost bit-identical | salts fsel-chem-a/b: 294,642,170.565169 both |
| invsqrt | negligible: every x tested, mean T over about 200M shots | public notebook vs our run agree to the second decimal of cost |
| DQI mean T | about 1e-6 relative | 5f901c55: 367,109.4–367,110.9 over 10 salts plus 16 census seeds |
| DQI failures K | the only material effect: each failure ≈ −0.46% of DQI ratio | below |

**Seeding.** `verify_submission_dqi` seeds tests from sha256(circuit .kmb) + salt (likewise invsqrt).
- Two DIFFERENT DQI files get independent private draws.
- The SAME file in both submissions gets the identical draw, so the second submission adds nothing on DQI.
- Deliberately altering bytes to re-roll a draw is off-limits.

## 2. Failure behaviour and overlap

Equal budget: the unchanged official verifier on Fsel-00…09 for both files, plus a shared 16 × 16,384-shot simulator
census.

| File | Official failures (10 salts) | Census failures (262,144 shots) | Pooled |
|---|---:|---:|---:|
| 5f901c55 (current) | 1 (+1 on team-w-a) | 0 | 2 / 1,388,544 |
| 4b350932 | 5 | 0 | 5 / 1,388,544 |

**Overlap** (`tools/dqi/cross_replay.py`): every failing input of either file was regenerated exactly with the
verifier's seeds and run through the OTHER file 64 times with fresh measurement randomness.
- **7 of 7 fail in the other file in all 64 of 64 replicas**, all as value errors.
- The two decoders share their failure modes on this evidence: a deterministic input class.
- **2 vs 5 is not a demonstrated difference** (Fisher exact p = 0.45). Treat the rate as common: 7 / 2,777,088
  ≈ 2.5e-6.

## 3. Private DQI ratio distributions (`tools/dqi/final_pair_mc.py`)

Model: Jeffreys posterior on the common p, K ~ Binomial(102,400, p), and the verifier's own repetition overhead.

| Option | Ratio at K=0 | E[ratio] | P(K=0) | 5% / 50% / 95% |
|---|---:|---:|---:|---|
| 5f901c55 alone | 70.5519 | 70.4649 | 0.76 | 70.229 / 70.552 / 70.552 |
| 4b350932 alone | 70.2767 | 70.1898 | 0.76 | 69.955 / 70.277 / 70.277 |
| best of 5f901c55 + 4b350932 | — | 70.4816 | — | 70.229 / 70.552 / 70.552 |

Splitting the effects:
- **Gate savings:** 5f901c55 is 1,437.7 mean T cheaper, worth +0.39% in DQI ratio. This is the dominant, reliable
  difference.
- **Error frequency:** not demonstrated different between the files.
- **Shared failure modes:** confirmed for every observed failure. A pair therefore only helps through independent
  draws of a shared rate: +0.017 DQI ratio (≈ +0.008% overall).

## 4. Implications for the final choice (to be made later)

- Slot 1 should hold the cheapest DQI file with no demonstrated reliability deficit (currently 5f901c55), plus the
  best deterministic invsqrt and chemistry files.
- Slot 2 adds value only through a DIFFERENT DQI file with a ratio at K=0 close to slot 1's. Its gain is bounded by
  P(slot 1 fails) × P(slot 2 clean) × (gap in ratio). With today's candidates that is about +0.017 DQI ratio.
- A clean public draw is one observation: P(K=0) ≈ 0.76 for any of these files.
- Re-run this analysis on any new candidate DQI file before the deadline (equal-budget sweeps, a cross-replay of its
  failures, then the model).
