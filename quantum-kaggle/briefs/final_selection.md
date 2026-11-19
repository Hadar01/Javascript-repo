# Final-selection analysis (2026-11-18, closed 2026-11-19): provisional selection, reopen only for a materially better candidate

**Provisional slot 1:** DQI `5f901c55` (with invsqrt `864f81cd` and chemistry `4d63be3d`). **Slot 2 stays open.**
DQI `4b350932` is the backup candidate. Kaggle keeps the better private score of the two selected submissions.

## 1. What the private salt can change (measured)

| Task | Salt sensitivity | Evidence |
|---|---|---|
| dfthcsos | none: cost bit-identical | salts fsel-chem-a/b both give 294,642,170.565169 |
| invsqrt | negligible: every x is tested, mean T over about 200M shots | a public notebook's figure and our run agree to the second decimal of cost |
| DQI mean T | about 1e-6 relative | 5f901c55: 367,109.4–367,110.9 over 10 salts + 16 census seeds |
| DQI failures K | the only material effect; each failure ≈ −0.46% of DQI ratio (≈ −0.15% overall) | below |

**Seeding.** `verify_submission_dqi` seeds the shot inputs and the measurement outcomes from sha256(circuit .kmb) + salt.
- Different files therefore get different seeds. We MODEL their draws as independent, which is a standard
  pseudorandomness assumption, not something the seed expression proves.
- The same file in both submissions gets the identical draw.
- Deliberately altering bytes to re-roll a draw is off-limits.

## 2. Observations, and whether they can be pooled

| Source | 5f901c55 | 4b350932 | Inputs |
|---|---|---|---|
| Official verifier, salts Fsel-00…09 | 1 / 1,024,000 | 5 / 1,024,000 | official sampler; different per file (different hash) |
| Official verifier, one extra salt | 1 / 102,400 (team-w-a) | 0 / 102,400 (team-f-a) | official sampler |
| Simulator census, seeds 2000–2015 | 0 / 262,144 | 0 / 262,144 | the SAME inputs for both files; own sampler reproducing the verifier's distribution, not the official code |

- **Duplicates** (`tools/dqi/dup_check.py`; inputs regenerated with the verifier's own seeds and sampler for all 22
  official runs):
  > All 2,252,800 official inputs were distinct. We model the official draws as independent under the verifier's
  > pseudorandom sampling assumptions.

  Zero duplicates confirms no repeated inputs; it does not prove statistical independence. The census inputs are shared
  by construction between the two files, so they count once in shared-rate pooling.
- **Census caveat:** the census sampler is an independent reimplementation; it has matched official failure counts on
  exact replays. Scenarios with and without the census are both reported.

**Cross-replay** (`tools/dqi/cross_replay.py`).
- Each file's 7 failing official inputs (2 + 5) were regenerated exactly and run through the OTHER file 64 times with
  fresh measurement randomness.
- **All 7 fail in the other file in 64 of 64 replicas** (value errors).
- That establishes **shared, measurement-insensitive failures on those 7 inputs**. It does not establish that the two
  files' failure sets are identical.
- **2 versus 5** (Fisher exact p = 0.45): the sample **does not demonstrate a rate difference**. That does not prove
  the difference is noise.
- So both a shared-rate scenario and a separate-rate scenario are carried below.

## 3. Private-score model (overall geometric mean), `tools/dqi/final_pair_mc.py`

**Evidence hierarchy.**
- **Primary evidence:** the official-only scenarios (official verifier, official sampler).
- **Sensitivity checks:** the census-inclusive scenarios (own sampler reimplementation, shared inputs).

**Specification (for reproducibility).**
- **Prior on each failure rate p:** Jeffreys, Beta(1/2, 1/2), so the posterior is Beta(k + 1/2, n − k + 1/2).
- **Shared-rate scenario:** one p for both files. **Separate-rate scenario:** an independent p per file.
- **Private draw:** K ~ Binomial(102,400, p), truncated at K = 39, which has negligible mass.
  - K maps to the DQI ratio through the verifier's `clopper_pearson_upper_bound` and `repetition_overhead`.
  - Two different files' K are modelled as independent given p.
- **Monte Carlo:** 20,000 posterior draws of p (numpy default_rng, seed 11). E[score | p] and the pair's E[max | p] are
  computed exactly over K for each draw. Future-draw quantiles use one K sample per p draw.
- **MC standard errors of the posterior means** (`model_output_2026-11-19.txt`):
  - ≤ 6e-5 for each single-file E[score];
  - ≤ 1e-5 for every pair gain, against gains of 0.0013–0.0027.
- **Inputs:** `tools/dqi/finalsel/config_2026-11-18.json`.
- **Diagnostics pinned in `tools/dqi/finalsel/`:** official sweeps, cross-replays, census and chemistry salt check,
  duplicate check, model output, artifact hashes.

- **Score:** (r_inv × r_dqi(K) × r_chem)^(1/3), with r_inv = 27.87955 and r_chem = 11.38873 fixed, and r_dqi(K) from the
  verifier's own repetition overhead.
- **Rate uncertainty:** propagated with a Jeffreys posterior on p.
- **How to read the columns:**
  - "90% CrI of E[score]" is uncertainty in our *estimate* of the expected score (from p);
  - "future draw 5/50/95%" is the spread of a single private draw under the assumed model.
- Config: `tools/dqi/finalsel/config_2026-11-18.json`.

| Scenario | File | p median [90% CrI] | P(K=0) median [90% CrI] | E[score] mean [90% CrI] | Future draw 5 / 50 / 95% |
|---|---|---|---|---|---|
| shared, official only (7 / 2.25M) | 5f901c55 | 3.2e-6 [1.6, 5.5] | 0.72 [0.57, 0.85] | 28.1755 [28.1664, 28.1827] | 28.1466 / 28.1897 / 28.1897 |
| | 4b350932 | same | same | 28.1388 [28.1297, 28.1460] | 28.1100 / 28.1530 / 28.1530 |
| shared, + census once (7 / 2.51M) | 5f901c55 | 2.8e-6 [1.4, 5.0] | 0.75 [0.60, 0.86] | 28.1769 [28.1686, 28.1834] | 28.1466 / 28.1897 / 28.1897 |
| | 4b350932 | same | same | 28.1402 [28.1319, 28.1467] | 28.1100 / 28.1530 / 28.1530 |
| separate, official only | 5f901c55 (2 / 1.13M) | 2.0e-6 [0.5, 5.0] | 0.82 [0.60, 0.95] | 28.1800 [28.1687, 28.1874] | 28.1466 / 28.1897 / 28.1897 |
| | 4b350932 (5 / 1.13M) | 4.6e-6 [2.0, 8.6] | 0.62 [0.41, 0.81] | 28.1324 [28.1172, 28.1442] | 28.0736 / 28.1530 / 28.1530 |
| separate, + census | 5f901c55 (2 / 1.39M) | 1.6e-6 [0.4, 4.0] | 0.85 [0.66, 0.96] | 28.1818 [28.1725, 28.1878] | 28.1466 / 28.1897 / 28.1897 |
| | 4b350932 (5 / 1.39M) | 3.7e-6 [1.6, 7.1] | 0.68 [0.48, 0.85] | 28.1362 [28.1234, 28.1458] | 28.0736 / 28.1530 / 28.1530 |

**Best-of-two pair 5f901c55 + 4b350932, gain in expected overall score over 5f901c55 alone** (rows 1 and 3 are the primary evidence):

| Scenario | Mean gain | 90% CrI |
|---|---|---|
| shared, official only | +0.0027 | [+0.0012, +0.0045] |
| shared, + census | +0.0024 | [+0.0011, +0.0041] |
| separate, official only | +0.0015 | [+0.0002, +0.0042] |
| separate, + census | +0.0013 | [+0.0002, +0.0034] |

**Reading.**
- In every scenario 5f901c55 has the higher expected overall score by about 0.036–0.048 points. The reliable driver is
  its 1,437.7 fewer mean Toffolis; the failure-rate difference is not demonstrated.
- The P(K=0) intervals are wide (roughly 0.4–0.96 across scenarios), so a clean public draw is one observation, not
  evidence of reliability.
- A second slot holding 4b350932 adds a small, positive expected gain in all scenarios: +0.0013 to +0.0027 overall,
  with MC s.e. ≤ 1e-5.
- **Decision (2026-11-19, supervisor):** keep 5f901c55 as provisional slot 1 and 4b350932 as the slot-2 fallback. No
  further analysis cycle for these two files. Reopen only when a materially better candidate appears.

## 4. Process for any new candidate before the deadline
1. Run the unchanged official verifier on fresh salts at an equal budget against slot 1.
2. Cross-replay its failures against slot 1 in both directions.
3. Check for duplicates.
4. Add it to the config and rerun the model in both scenarios.
5. Choose slot 2 by the expected overall score of the pair, with its credible interval.
