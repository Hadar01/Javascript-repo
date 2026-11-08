# invsqrt optimisation log (Agent A), 2026-11-08

Baseline: public v95 `$S/cand/pub/invsqrt.kmb`. File sha 1c5b1ee2…. Ratio 21.7762 (official run, per the coordinator).
62 qubits, 1,243.12 mean Toffolis, 1 T, 41 rotations at ε = 2.434e-13 (28.76 T each), C = 1,538.21.

**Result of this session: no circuit cheaper than the baseline. Nothing was submitted or committed.**

## Tools written (`quantum-kaggle/tools/invsqrt/`)

- **`quick_check.py`**
  - Runs the unmodified official `verify()` with `shots_per_x=1`, testing all 3,133,452 x.
  - Batch size 2044, which divides max_x.
  - Takes 19 s on 2 cores. Use it as the fast gate before the 13-minute full run.
  - On the public file it gives PASS, ratio 21.776, 1,243.12 mean Toffolis, worst error 0.99932 of tolerance at x = 161.
- **`margins.py`**
  - Per-x phase error and absolute margin, using the verifier's own `reference_values` and `half_turns_to_units`.
- **`kmx_analyze.py`**
  - Bit-packed simulator of qubit values over all x. Classical bits and HMR coins are tracked with dict storage (an earlier version used ~25 GB; see the OOM note at the end).
  - Per Toffoli-like gate it reports: never fires (delete), product equals one control (downgrade to CX/CZ), or CSWAP equivalent to a SWAP.
  - `LIVE=500` prints a live-qubit profile.
  - `PROBE=k,...` checks control products at chosen gates.

## Findings on the public circuit (all measured)

1. **Structure, by op index in the 53.8k-op stream:**

   | ops | stage | Toffolis | live qubits |
   |---|---|---|---|
   | 0–2.5k | normalisation: 20-AND prefix chain, 47 CSWAPs, chain erased by HMR with free Z fix-ups | ≈104 | — |
   | 2.5k–15k | 256-entry lookup, mostly CX fan-out | ≈150 | **62 (peak)** |
   | 15.9k–16.3k | high phase pass: 16 rotations, lookup bits muxed by flags via CSWAPs | ≈62 | — |
   | 16.3k–25.7k | forward arithmetic | ≈270 | — |
   | 25.76k–25.96k | low phase pass: 26 rotations; a streaming 4-stage CSWAP delay line feeds one bit per rotation into q28, partly using x[0], x[2], x[3] as buffers | ≈100 | — |
   | 26k–35k | reverse arithmetic | ≈425 unconditional + ≈170 conditional (about half executed) | 62 again around 30k and 32.5k–34.5k |
   | 35k–50k | unlookup: HMR plus phase repair, almost all CZ | ≈0 | 40 |
   | 50k–53.8k | un-normalisation | ≈57 + conditional | — |

   **All 41 rotations act on the single wire q28.**
2. **The rotation angles are at the LP optimum.**
   - The minimum absolute margin is 3.1766e-12 turns.
   - It is equal, to about 1e-19, at 15 or more different x spread over the whole range (equioscillation).
   - So re-fitting the angles alone gains nothing.
   - Even a 10× margin increase would be worth only about 19 Toffoli-equivalents (1.2%).
3. **Domain-aware scan of unconditional gates:** across all 1,409 Toffoli-like gates, 0 are deletable or downgradable under the four simple patterns (never fires, product equals one control, CCZ reducible to CZ, CSWAP is really a SWAP). The public authors have already harvested these.
   - The only "candidates" were conditioned fix-up CCZs inside deeply nested condition stacks.
   - These are rarely executed (probability about 2^-k), and their firing depends on the coins, so they are not provably removable and are worth less than 1 Toffoli in total.
4. **Rotation merge (41 → 33): not a free win.**
   - The high and low passes overlap on 8 weights (half-turn angles 7.6e-6 … 9.8e-4).
   - Merging by addition costs about 1 Toffoli per weight, with carries erased by HMR and Clifford MAJ fix-ups. That would save about 42 Toffoli-equivalents (2.7%).
   - The catch: the high-pass source bits (lookup word) are released before the arithmetic. Keeping them costs at least 1 qubit at a 62-qubit peak (24.8 Toffoli-equivalents per qubit). Recomputing them with a partial lookup costs more than 60.
   - Net gain is roughly zero or negative unless the arithmetic peak is reorganised at the same time.
5. **The Gu et al. coulomb-potential design (README in `$S/E/dl/gu`) does not transfer directly.**
   - Its band is absolute (32/2^24 ≈ 2^-19), not 2^-24 relative.
   - Linear segments would need about 1,250 segments per exponent parity (h ≈ 8e-4) to reach 6e-8 relative error, so the lookup cost would explode.
   - The transferable part is the exact backward fit through the whole integer pipeline. The public table is already fitted end to end ("the only rounding that passes"), and the LP is at its optimum.

## Where a real gain must come from (estimates)

| lever | potential | requirement |
|---|---|---|
| a 61-qubit design | −1.6% per qubit | the lookup peak (2.5k–15k) and the reverse-arithmetic peaks must shrink together |
| overlap merge + 61 qubits together | ≈ −4% | a redesign of the K0 split / arithmetic schedule |
| low-pass delay line | ≈ −1% | it costs about 4 CSWAPs per rotation (≈100 Toffolis); any cheaper shift per bit (e.g. 3 stages by capping s and handling the small-x class separately, as Gu does for n₂ ≤ 3) would pay |
| reverse arithmetic (≈510 mean, against ≈270 forward) | the largest single lever, if the asymmetry is not essential | the obfuscated stream needs decompiling, or a fresh generator, to see why |

Recommendation: write our own readable generator reproducing the public architecture. Start from the Apache-2.0 93-qubit sources extracted to `$S/kg/alex_src`. Then attack the delay line and the reverse-arithmetic asymmetry. This is a multi-day job; nothing quick is left on this binary.

Note: one early run of `kmx_analyze.py` (before the dict fix) hit the OOM killer at about 25 GB. If any background job died at about 18:44, that was the cause.

---
## Milestone 1: our own generator (Agent A, all our code)

**Status:** working and passing, but not yet at public cost.

**Files** (in `quantum-kaggle/tools/invsqrt/`):
- `model.py`: exact integer model, backward/interval table fit and exact all-x certificate.
  - The certificate uses the verifier's own isqrt target and tolerance.
  - It also has the L/H and residual/coarse layout.
- `gen.py`: primitives and the v1 circuit:
  - Gidney adder with carry-in and top-carry reuse;
  - signed-digit rows using the ~(~T+v) trick;
  - prefix-chain flags and binary CSWAP normalisation;
  - barrel shift with empty-target moves and per-bit Z_POW.
- `gen2.py`: the v2 circuit, which adds:
  - L/H split of K0 (rows touch 21 bits);
  - residual/coarse split of K1 (R rows touch 12 bits);
  - early phase of H, then its measurement-based unlookup;
  - borrowed x[21].
- `upstream/`: copies of the Apache-2.0 93-qubit sources, for reading and credit only. Running them was refused by the permission classifier (downloaded code), so everything here was rewritten from scratch.

**Model** (f2 10, f1 19, fy 28, gy 2, w2 9, drop {5}, 256 quadratic segments):
- exact certificate: worst 0.910 of tolerance;
- minimum margin 9.6e7 units (5.2e-12 turns), better than the public 3.18e-12.

**Quick check results** (all x, 1 shot):

| file | Q | Toffolis | rotations | C | cost | ratio |
|---|---|---|---|---|---|---|
| inv_a1.kmb | 108 | 1714 | 33 | 1946.8 | 210,257 | 9.88 |
| inv_a2.kmb | 94 | 1469 | 44 | 1781.9 | 167,499 | 12.40 |

v2 reproduces the old 93-qubit public line (165k).

**Qubit anatomy at the v2 peak (Y rows):**

| register | qubits |
|---|---|
| x | 21 (+1 borrowed) |
| flags | 5 |
| r | 12 |
| C | 7 |
| K2 | 9 |
| L | 21 |
| Gidney carries | 19 |
| **total** | **94** |

The public line reaches 62 qubits. Its liveness profile shows x[17..20] zeroed during the arithmetic, so it re-encodes the address bits into the table/arithmetic registers, plus other tricks we have not yet reverse-engineered.

**Exchange rates in our design** at Q 94, C 1782:
- 1 qubit ≈ 19 Toffoli-equivalents.
- Cuccaro rows: worse (−19 qubits for +560 Toffolis).
- Erasing K2 and re-looking it up with kickmix's 254-Toffoli lookup: worse.
- Two-chunk carries with a comparator fix-up: about break-even.
- So the big win needs:
  - a cheap custom lookup (public 150 vs kickmix 254+25), which makes re-lookup and erase strategies pay;
  - address-bit re-encoding (frees about 4–8 x qubits);
  - cheaper normalisation (our 79+79 CSWAPs vs public 47+48).
