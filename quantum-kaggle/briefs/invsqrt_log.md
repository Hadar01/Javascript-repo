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

---
## Step 2 (priorities 1–3): stopped at a blocker

### 1. Custom lookup at ≤ 150 Toffolis: not achievable with generic methods
- I computed the ANF of all 57 table bits (r0, C, K2, L0, H) over the 8 address bits (e, a6..a0).
  - Every bit except the top two H bits is ANF-dense: 100–140 monomials of degree ≥ 2 each.
  - Together they use 247 of the 247 possible such monomials.
  - So a monomial bank, hi/lo split products, or select-swap at this size all cost ≥ 255, the same as unary iteration (kickmix's 254 + 25).
- The public 169-AND decode is a whole-table XOR-AND-graph synthesis. Its CCX controls are pairs of linear forms of the address bits, and earlier output wires are reused as factors. That is SAT- or window-resynthesis-level work.
- I wrote a greedy XAG synthesizer (`xag.py`). For a fixed first factor l1, the condition t+s = l1·l2 is LINEAR in (s, l2). It also makes un-lookup free: erase in reverse order with Clifford fix-ups.
  - It fails at the start: with only the 9 address/constant wires, random factor sampling finds no decomposition.
  - It needs a constructive seeding strategy. Not done.
- Expected gain even if solved: about 80–110 Toffolis, i.e. ratio 12.4 → ~13.

### 2. Freeing x[17..20]
- This requires the address to be recoverable cheaply from table registers that are not modified during the Y rows (C, K2, or a kept H).
- A plausible route is comparator functions of the monotone coarse field C. Estimated −4 qubits for +40–60 Toffolis, about break-even to a small win.

### 3. Normalisation 79 → 47 CSWAPs
- The public network is a sequence of controlled interval reversals: rev[0..11], (12,21), rev[0..19], rev[0..20], rev[1..21], (0,4), rev[6..20], rev[16..20].
- Its control is a single wire (q48) that is re-targeted by CNOT and HMR between groups, so intermediate states are mirrored and pairs of reversals compose into shifts.
- Reproducing it needs a small search over reversal/control sequences. Worth about 63 Toffolis (~3.5%).

### Why ratio 21 is out of reach this session
The gap is mostly qubits: 94 now, versus 62 for the public circuit.

| change | qubits | Toffolis |
|---|---|---|
| erase K2 by measurement and recompute it via a cheap partial XAG lookup | −9 | +~30 |
| free the address bits | −8 | +~60 |
| two-chunk L carries | −8 | +~140 |
| custom lookup | | −~100 |
| normalisation network | | −~60 |

This gets to about Q 69, C ~1830, cost ~126k, ratio ~16.5.

The rest (to 62 qubits at C ~1540) needs the public's remaining tricks. Its live set during the arithmetic is only 36 non-x qubits, less than R (19) + L (21) in our layout. So it must release or narrow R and L during the rows, for example by measuring out R's low bits progressively and recomputing them cheaply, or by "write-only runs".

### Recommended next step
Semantic lifting of the public circuit with our bit-packed simulator (`kmx_analyze.py`). For each live qubit at each checkpoint, test over all 3.1M x whether its value equals a bit of a known quantity: x_n, the address, table fields, R, partial sums of the Q rows, the flags.

This turns the opaque stream into an architecture diagram in hours rather than days. After that, we can re-implement it readably in `gen2.py`.

---
## Step 3 attempt (implementing the decoded tricks): hard blocker, nothing built

**Step 1, carry-light row adders.** The forward half works on paper:
- A ripple whose carries are X-measured right after use, with the kick stored in a classical bit. This needs 2 ancillas and n−1 Toffolis.
- The complement-trick subtraction ~(~s+v) reproduces the forward carries bit for bit (proof in my notes: d_i = [s_<i < v_<i + cin] = c_i). So the reverse can repay the forward kicks for free.

The reverse is the blocker. Its own carries must be erased unitarily, or every measurement kick needs yet another recomputation (an infinite regress). The options:

| reverse adder | ancillas | Toffolis | problem |
|---|---|---|---|
| Gidney top-down | n | n | defeats the purpose |
| Cuccaro in place | 1 | 2n | fails where the row operand is shorter than the target: our LSB-aligned rows have n−m = 3..16 bits of pure carry propagation with no operand qubit to hold the carry, so the high part again needs n−m ancillas or an O(k)-Toffoli dirty-ancilla incrementer |
| block-Gidney with comparator-erased boundary carries | about n/2 | 1.5n | about break-even at our qubit price |

Two ways out, both deep:
- **(a) Bias-grown narrow accumulator** T = 2^b − Σ (n−m ≤ 2 for every row), with the K0 table value phased separately. Cost about +22 rotations. But with kickmix's unary lookup (all 57 output bits plus 8 ancillas written at once), the lookup itself then becomes the 92-qubit peak.
  - That needs a split or progressive lookup, which needs the cheap XAG lookup (blocked earlier).
  - Or it needs two lookups, at +280 Toffolis.
- **(b) Carry-save pending-carry flushing** in the in-place L register. This is research-level; the redundancy in the pending digit makes the absorb step non-injective without an extra qubit per stage.

**Steps 2, 4, 5** (rebuild K2, flags in x, free the address) each depend on either the cheap XAG lookup (2, 5) or on fixing the low-δ rows corrupted by stored flags (4).

**Step 3, y at 26 bits:** the earlier sweep found it infeasible with our rounding scheme (fy 26–27 infeasible for f1 17–19). The public circuit reaches it with a different scheme that we have not yet decoded.

**Conclusion.** Reaching ratio ≥ 21 needs two multi-day components:
1. A whole-table XAG synthesizer of about 3 ANDs per output bit. That enables progressive and partial lookups, rebuilding K2, and the address recovery.
2. Carry-light reverse adders, with the public's reverse scheme decoded at gate level. That scheme uses nested conditional repayment blocks keyed on the stored carry bits, plus conditional duplicate branches.

Our generator remains at ratio 12.40 (`$S/cand/inv_a2.kmb`).

---
## Component 1: the XAG synthesizer (`quantum-kaggle/tools/xag/`), 2026-11-09

### Library: `xag.py`

**Synthesis**
- `synthesize` (unbounded) and `synthesize_budget` (cap on live helper wires) take a multi-output truth table over n inputs. Functions are stored as 2^n-bit ints.
- Greedy: for each target, find the least k such that t = Σ_j f_j·g_j ⊕ s with f, g, s in the GF(2) span of the live wires (inputs, helper products, earlier targets).
- With the f_j fixed at random, the condition is linear in (s, g_j). Each try is one Gaussian elimination over GF(2): 256 equations in (k+1)·D unknowns.
- When k ≥ 2, the products are kept as helper wires to grow the span; earlier targets are reused as factors.
- Seed: all monomials of degree ≥ 2 within the low 4 and the high 4 inputs, sharing prefixes (22 ANDs). This makes products of span elements reach degree 8.
- When over budget, the oldest non-base helpers are erased by X-measurement. The fix-up CZ(f, g) is Clifford once f and g are re-expressed in the live span.

**Emitter**
- `Emitter.forward` emits kickmix gates: linear forms are made temporarily on pivot qubits by CNOT/X; each product is one `init_and` or `ccx` straight into the target qubit.
- `reverse_fresh` is a measurement-based un-lookup with **0 Toffolis**:
  - non-base helpers are erased first;
  - each target is then X-measured, with fix-up (−1)^t = Π CZ(f_j, g_j)·Z(s) from a fresh decomposition over the still-live wires (any number of products is free, since CZ between linear forms is Clifford);
  - base monomials are erased last.

**Test** (`test_emit.py`): kickmix simulation on all 256 addresses.
- Forward: every target bit is correct.
- Forward + reverse: all qubits clean, phase 0.

### Benchmark: our invsqrt 57-bit table (8-bit address)

| method | Toffolis lookup + unlookup | total qubits (8 addr + 57 targets + helpers) |
|---|---|---|
| kickmix unary init/del_lookup | 254 + 25 = 279 | 73 |
| XAG, unbounded | **142 + 0** (seeds give 141–143) | 185 |
| XAG, helper budget 40 (+22 base) | 163 + 0 | 132 |
| XAG, helper budget 25 | 181 + 0 | 118 |
| XAG, helper budget 12 | 219 + 0 | 105 |

The public decode is about 169 ANDs. Our unbounded result is below that, and budgets ≤ 25 stay below 200.

**Synthesis cost:** about 1–3 s per run, pure Python.

**Not yet done:**
- SAT window resynthesis: pycryptosat is not installed.
- Bilinear-map input for the DQI multiplier.
- Qubit-aware integration into `gen2.py`. The lookup-time live set is now 57 targets + 22 base + budget, so a progressive, field-by-field construction is the next step for the invsqrt qubit peak.
