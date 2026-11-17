# Chemistry compatibility audit and table-encoding review (2026-11-17)

Subject: the chemistry files in our current best submission (mix9, public score 28.07494). These are hayatohikawa's
C8-milestone `dfthcsos/`, with `submission.npz` sha256 `7e6e65d7…`; loaders are Lera's (marculera) 4,025-Toffoli/pass
build with boristown/atakanaldemir weights. Everything below uses the unchanged official verifier (kickmix 1.0.0 from
PyPI) unless stated otherwise.

## 1. Current state

| Item | Value |
|---|---|
| Ratio | 11.3840 (cost 294,763,813.6) |
| λ_eff | 46.92179 (proven floor for this shift ≈ 46.786, so weights can add at most ≈ 0.29%) |
| T total | 14,712 |
| Angle loaders | 4,025 T/pass × 2 |
| Formula-priced heuristic | 6,662 T (outer prep 317 + inner prep 4,095 + Givens 2,250) |
| Q | 427 = 84 heuristic persistent + 40 word qubits (5 × 8) + 303 temporary |
| Table | (R, B, C) = (8, 143, 44); 1,220 rows × 75 angles; brot = 8 (θ/π = word/128); 15 loaders × 5 words |
| error_1 | 19.999998000 mHa (gate 20 mHa, margin 2.0e-9 Ha) |
| error_2 | 19.999998499 mHa (margin 1.5e-9 Ha) |
| E_gap | 3.9148980015 Ha (floor 3.914898, margin 1.5e-9 Ha) |

## 2. Table encoding: is a coarser word worth GPU time?

Measured with the verifier's own `evaluate_words`, weights held fixed:

| Words | error_1 (mHa) | error_2 (mHa) | λ_eff | Passes |
|---|---:|---:|---:|---|
| Submitted 8-bit | 20.0000 | 20.0000 | 46.92 | yes |
| Rounded to 7 bits | 1,947.5 | 444.9 | 75.10 | no |
| Truncated to 7 bits | 2,082.6 | 443.7 | 73.17 | no |
| 8-bit plus random ±1 LSB noise | 2,183.4 | 471.3 | 79.69 | no |

- **The weights are co-fitted to these exact rounded words.** Any re-rounding, even ±1 LSB at 8 bits, costs about 100×
  the gate. A coarser encoding therefore needs a full new fit and rounding (the GPU pipeline), not a requantization.
- **Savings if a 7-bit table existed:**
  - Givens rotations 2,250 → 1,950 T (verifier formula).
  - Loaders, assuming they scale with output bits (an estimate): about 4,025 → 3,520 T per pass.
  - Persistent word qubits 40 → 35, so Q 427 → 422. Temporaries (303) and state prep do not change with brot.
  - Total: about −10% chemistry cost, about +3.6% overall, **only if** the 20 mHa gates could still be met.
- **Feasibility estimate (not a proof).** Lera's documented 8-bit pipeline goes from 14.16 mHa (continuous fit) to
  19.95 mHa after rounding and refit. In quadrature that is a rounding contribution of about 14 mHa. Halving the angle
  resolution roughly doubles that to about 28 mHa, which exceeds the 20 mHa gate even with a perfect continuous fit.
- **Recommendation:** do not spend GPU time on a 7-bit table unless someone shows a rounding scheme whose error does
  not scale with the step size.

## 3. Compatibility audit

| Check | Result |
|---|---|
| Accuracy metrics vs BLAS threads (1, 2, 4; scipy-openblas) | error_1, E_gap, Λ, λ_eff bit-identical; error_2 varies by ≈ 3e-17 Ha, about 10⁸ × smaller than the 1.5e-9 Ha margin |
| Dependence on the salt | none: error_1, error_2, Λ and E_gap depend only on the recovered words and the weights. The words must agree on every shot, so a fresh private salt cannot move them (see `chem_log.md`) |
| Loader width cap | 126–128 qubits, within the 128 cap |
| PyPI kickmix vs bundled `kickmix.so` | identical (§4) |

## 4. Verifier benchmark (all three tasks)

**Same verifier code, two simulator builds.** The current submission (mix9) was scored on salt `bench-1`, once with
kickmix 1.0.0 from PyPI (our local setup, and the hosts' planned metric) and once with the competition's bundled
`kickmix.so` (sha256 `c66b3216…`). Only the import path differed.

| Task | Fields compared | Differences | Seconds, PyPI / bundled |
|---|---:|---:|---|
| invsqrt (27.6599) | 16 | 0 | 305 / 193 |
| dqi (70.2767) | 22 | 0 | 96 / 80 |
| dfthcsos (11.3840) | 13 | 0 | 13 / 11 |
| geometric mean | 28.074952032161487 | identical to the last bit | |

Timings are indicative only: two expert agents were using the CPU at the same time.

**Local vs Kaggle public board.** Every one of our 9 submissions so far scored on Kaggle exactly the value we
predicted locally, to all printed decimals. For the DQI files with rare failures, the prediction is conditional on the
board's own draw; for example, C1 and C2 both scored their zero-failure local values. The local loop is therefore a
faithful stand-in for the public metric. The private board differs only by a fresh salt, which can change DQI failure
counts (each failure ≈ −0.46% of DQI ratio) but not the invsqrt or chemistry scores.
