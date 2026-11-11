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

---
## Step 4: XAG lookup wired into the generator (gen3.py): passes, but worse; blocker

**What gen3 does**
- Uses `xag.XagContext`, which builds, erases, forgets and re-knows table fields inside the circuit.
- Builds H field by field, phases it, and erases it once the rest of the table is live.
- Then builds K2, C, r0 and L0, and erases K2 after the R rows, while C and L0 are still pure table values.
- Rebuilds K2 for the reverse R rows.
- Final erase: re-creates the base monomials, then measures everything out with Clifford-only fix-ups.
- The whole circuit **PASSES** the official verifier (quick check, all x), so the XAG machinery is correct in situ.

**Results**

| file | budget | Q | Toffolis (XAG ANDs) | C | cost | ratio |
|---|---|---|---|---|---|---|
| inv_a3.kmb | 25 | 135 | 1479 (314) | 1791.9 | 241,907 | 8.58 |
| inv_a3 variant | 8 | 119 | 1559 (394) | — | — | — |

**AND split** at budget 25: H 61 (base 22 + 39), rest 192, K2 rebuild 39, final base 22.

Building fields separately loses the cross-field reuse that gives 142 for the whole table, and pays the 22-AND base each time.

**Blocker: qubits**
- A whole-table XAG needs, at build time: x + flags (27) + all 57 outputs + 22 base helpers + budget ≥ 106 qubits.
- That is above the 94-qubit rows peak.
- Field by field it is still 119–135, because the base plus budget helpers (≥ 30 qubits) coexist with the live fields.
- At our exchange rate (about 19 Toffoli-equivalents per qubit), 30 helper qubits are worth about 570, against about 100 ANDs saved. Kickmix's unary lookup (8 ancillas) wins in this architecture.

**What would change this**
- The XAG must run where the table is not at the qubit peak.
- Or the table must shrink to about 40 live outputs, as in the public circuit.
- Or the synthesis must start with no base: products of linear forms only, with output bits reused as factors as soon as they exist.

All three need the overall qubit architecture redone, and the deciding factor is still the carry-light reverse adders.

**Best own circuit remains `$S/cand/inv_a2.kmb`** (94 Q, ratio 12.40).

---
## Rotation-merge re-check: exact costs (supervisor review), 2026-11-09, public v100

**Input file:** `$S/cand/pub3/invsqrt.kmb`, sha 034c7c2a…, 36,477 ops.

**Quick check (all x, 1 shot):** PASS. 62 qubits, mean Toffolis 1242.74, T 1, 41 rotations, ε 2.434e-13, C 1537.83, cost 95,345.6, ratio 21.7816.

**Tools:** `tools/invsqrt/merge_probe.py` (exact over all 3,133,452 x) and `decode.py` + `/tmp/lin_h.py` (8,192 sampled x).

### What was measured
1. **Rotations.**
   - High pass: 15 rotations, at ops 8373–8677, with half-turn weights 2^-17 … 2^-3, plus one T.
   - Low pass: 26 rotations, at ops 16138–16331, with weights 2^-35 … 2^-10.
   - They overlap on 8 weights, 2^-17 … 2^-10.

   | weight | high-pass 1s | low-pass 1s | both 1 |
   |---|---|---|---|
   | 2^-17 | 995,341 | 1,129,688 | 283,499 |
   | 2^-14 | 1,550,464 | 19,683 | 5,686 |
   | 2^-10 | 2,386,871 | 114 | 44 |

   Both bits are 1 at the same weight for some x at every overlap weight. So a merge needs a real add with a carry, not just an XOR.
2. **Storage interval.** A merged weight needs the high-pass bit h_w (a flag-muxed bit of the table high word) to survive from its high-pass op (8373–8431) to the low pass (16276–16331).
   - Within that interval the live count reaches **62** at ops 8373–8378, 8760, 9008, 14239–14241, 14433, 15102, 15526, 16008 and more.
   - **No qubit is zero throughout**, and **every one of the 62 qubits is acted on by some gate** inside [8433, 16276].
   - So each carried bit adds exactly +1 to the peak: **m merged weights → Q = 62 + m**.
3. **Recompute instead of store.**
   - At the low pass, the address bits are not available: x17–x20 are zeroed and reused, and no pure table wire is live (classification "T" count 0 at op 16250).
   - None of the 8 h_w is in the GF(2)-linear span of the live qubits at any checkpoint from 10500 to 16275. Recovering them would need a non-linear recomputation from arithmetic registers; we did not find a cheap one.
   - Moving the high pass later fails because H is unavailable after op ~10750 until the reverse rows have erased Y_low. Moving the low pass earlier fails because Y_low exists only after the forward rows (~15700).
4. **Rotation saving.** Merging m contiguous weights with a streaming carry saves m − 1 rotations: the carry-out at the top weight needs its own rotation. Each rotation is 28.765 T = 7.19 Toffoli-equivalents. ε rises slightly with fewer rotations, which is included below.

### Exact cost table

v100 baseline: 62 Q, C 1537.83, cost 95,345.6. Extra Toffolis per merged weight (adder carry, carry erase, deferred fix-up of the stored bit) are bracketed at 0 and 4.

| m merged | Q | rotations | ΔToffolis | C | cost | ratio | vs baseline |
|---|---|---|---|---|---|---|---|
| 1 | 63 | 41 | 0 | 1537.8 | 96,883 | 21.44 | +1.61% |
| 2 | 64 | 40 | 0–8 | 1530.4–1538.4 | 97,948–98,460 | 21.20–21.09 | +2.7…+3.3% |
| 4 | 66 | 38 | 0–16 | 1515.7–1531.7 | 100,035–101,091 | 20.76–20.54 | +4.9…+6.0% |
| 8 | 70 | 34 | 0–32 | 1486.2–1518.2 | 104,035–106,275 | 19.96–19.54 | +9.1…+11.5% |

The supervisor's scenario (63 Q with −42 C → 94,237, ratio 22.04) would need all 8 bits held in 1 extra qubit. Because the bits must survive several 62-live points with no idle or zero qubit and are not linearly recoverable, the storage cost we measured is 1 qubit per bit.

### Conclusion
With these merge layouts (store-and-merge, recompute, move either pass), no gain was found. Every tested m increases cost, by 1.6% to 11.5%. Not built.

A gain would need a non-linear recovery of the h_w window from the live state at the low pass costing fewer than about 7·(m−1) − 24.8·k Toffoli-equivalents with k extra qubits. We did not find or test such a recovery beyond the linear check.

---
## Low-pass delay line: exact measurement and rewrites tested (public v100, sha 034c7c2a…), 2026-11-09

### Measured (exact, all x)
- **Op range:** 16123–16335 (kmx line index), from the flag setup `CCX q23 q3 q21` to the last low-pass Z_POW. Then come the HMR clean-up and the Clifford fix-ups (Z/CZ only).
- **Cost:** **89 CSWAP + 4 CCX = 93 Toffolis**, static = mean. There is no PUSH_CONDITION in the range, so every Toffoli executes on every shot. That is 3.58 per rotation over 26 rotations.

**Stages** (control qubits per streamed bit):

| stage | controlled by | buffers | cost |
|---|---|---|---|
| shift by 1 | q18 | q0, a vacated x bit | 26 CSWAP + 1 CCX = 27 |
| shift by 2 | q27 | q2/q3 alternating, vacated x bits | 27 |
| combined shift 4/8 (shift ∈ {0,4,8}, since a ≤ 10) | q21, q23, and q21⊕q23 via CX conjugation | bank q50/q40/q41/q6 and bank q8–q11 | 26 + 12 = 38 (1.46 per bit) |
| start | `CCX q54 q18 q28` | — | 1 |

- **Drain:** the last 7 rotations (half-turn weights 2^-16 … 2^-10) take no new source and cost ≈ 25 Toffolis. They serve only large shifts: the 2^-10 rotation is 1 for 114 inputs, 2^-11 for 373, 2^-12 for 1,294.
- **Live qubits:** 57–62 inside the range. **The line sits on the 62-qubit peak**: 62 live at ops 16153–16175 and onwards.
- **Domain-aware scan:** over all x, 0 of the 93 Toffolis are deletable or downgradable (never fires, equals one control, SWAP-equivalent).

### Rewrites tested

| rewrite | exact effect | verdict |
|---|---|---|
| A. Cap the shift at 7 (drop the 8 stage) | Saves ≤ 12 CSWAPs (the q23 bank), plus ≈ 3 drain steps: ≤ ~20 Toffolis (≈ −1.3% of C). But 63 inputs (x < 64, shift 8–10) then get the wrong phase. The correction is a phase function on 63 points: in the parity basis, up to 63 rotations (7.19 Tof-eq each), or another shift network. | net loss in the forms tested |
| B. Shifts conditioned on classical bits | No classical copy of the shift flags exists. They are quantum functions of x, and measuring them would destroy x. | not applicable |
| C. Merge with an adjacent CSWAP network | The nearest networks are the high-pass mux (ops 8373–8687) and the (un)normalisation at the circuit ends. None is adjacent. | no merge found |
| D. More borrowed buffers | The vacated x bits are already used (q0, q2, q3, q6, q8–q11). A new scratch buffer adds a qubit at the 62 peak (+24.8 Tof-eq) for at most a few Toffolis. | net loss |
| E. Stage-encoding bound | Binary-stage streaming over 11 shift values needs about log2(11) = 3.46 swaps per streamed bit; v100 uses 3.58. The slack is about 0.12 × 26 ≈ 3 Toffolis (≈ 0.2% of C, cost about 95,160, ratio about 21.82) under this structure. | no construction found; not built |

### Conclusion
The rewrites tested (A–E) found no gain that beats cost 95,345.6. Nothing was built.

**Correction to my earlier estimate (step 2, "≈100 Toffolis, ≈ −1%"):** the line is 93 Toffolis, and nearly all of it is the information cost of muxing 11 shift values, done with vacated-bit buffers.

---
## maoxin123 c6519219 vs public v100 034c7c2a: diff analysis (Agent A), 2026-11-10

**Totals:** static Toffolis 1405 → 1393 (−12). CSWAP 226 → 205, CCX 1086 → 1095, CCZ 93 = 93. Still 62 qubits and 41 rotations.

| region (v100 lines) | content | v100 | c6519219 | Δ |
|---|---|---|---|---|
| 16123–16335 → 16114–16305 | **low-pass delay line** | 89 CSWAP + 4 CCX = 93 | 70 CSWAP + 11 CCX = 81 | **−12** |
| 15672–16122 | arithmetic tail before the low pass ("q25 merge") | 3 CSWAP + 53 CCX | 1 CSWAP + 54 CCX | −1 |
| 9111–9145 | arithmetic | 2 CCX | 1 CCX | −1 |
| 18192–18320 | reverse rows | 0 | 1 CCX | +1 |
| 8366–8687 (high-pass mux), 18564–19048, 36278 | reordered or re-registered, same counts | — | — | 0 |

**The delay-line rewrite**
1. **Stage order reversed.** v100 streams each bit through the 4/8 bank first, then the shift-2 stage (q27), then shift-1 (q18). c6519219 goes shift-1 → shift-2 → 4/8.
2. **Emptied stages are skipped in the drain.** After the last source (rotation 19), the shift-1 stage empties after 1 step and shift-2 after 2, so their gates are simply omitted. The 4/8 bank drains last at 1 Toffoli per step.
   - Per-rotation cost of the last 7 rotations: v100 3,4,4,4,3,4,4 = 26; c6519219 4,3,3,1,1,1,1 = 14.
3. **The last swap out of an emptied buffer becomes a move.** `CCX(flag, buf, q28); CX(q28, buf)` into q28, which is known zero once the source has stopped. It costs the same Toffoli, but leaves the buffer clean, so no later stage has to touch it. This is where CSWAPs became CCX.
4. **Buffers re-assigned.** The 4/8 banks now use vacated x bits q4–q7, plus q9, q40, q41, q50.

**Why it is still correct.** When a stage's flag is set, its buffer holds stream bits, and those bits leave through the move. When the flag is clear, the move's CCX does not fire, and the buffer keeps its x-bit data (vacated bits are 0 exactly when the flag is set). Once a buffer is empty and no input arrives, the stage acts as the identity.

**Correction of my delay-line conclusion (previous section).**
- The "≈ log2(11) = 3.46 swaps per bit" figure was **not a valid bound**: it ignored stage ordering and the drain. c6519219 achieves 81/26 = 3.12 per rotation.
- My single-gate scans could not find this because it is a coordinated reorder of the whole line.

### Generalising the pattern to c6519219: rewrites tested, no build

**Drain model.** Each stage costs its per-step price over its active steps, where active steps = input duration + delay, capped at the 26 low-pass steps.

| network (c6519219) | Toffolis | rewrite tested | exact projected Δ |
|---|---|---|---|
| Low-pass delay line (stage order 1, 2, 4/8) | 81 | All stage orders in the drain model: (1,2,48) = (2,1,48) = 81; (1,48,2) = 84; (48,2,1) = 93 (that is v100). | 0 (c6519219 is at the model minimum) |
| High-pass mux, lines 8368–8687 (select → shift 2 (q20) → shift 1 (q27)) | 69 | Reorder delay stages small-first. The high pass has **no drain**: residual buffer bits are phased with Clifford Z_POW on the buffer qubits (S† at start, S at end on q0, q2, q3: a ±θ trick that cancels on the x-data branch). Both orders are active on all 16 steps. | 0 |
| Normalisation, 47 CSWAPs (start) and 49 (end) | 96 | Controlled interval reversals, not a stream, so there is no drain to skip. | not applicable |
| Low-pass drain via the ±θ trick (rotate the residual buffer qubit directly) | 4 drain Toffolis on x-bit buffers q4–q7 | Needs a cancelling −θ rotation at the start: +1 rotation (7.19) − 1 Toffoli per step. | +6.2 per step (loss) |
| All 1,393 unconditional Toffoli-like gates | — | **Global linear-equivalence scan** (`tools/invsqrt/linscan.py`): is the nonlinear term GF(2)-linear in the live qubits? Screening sample = all x ≤ 16384 plus 16384 random larger x. | 0 candidates |
| Domain-aware scan | — | Never-fires, equals-a-control, or SWAP-equivalent (`kmx_analyze.py`, all x). | Only the 19 deeply nested conditional fix-up CCZs, which are not provable |

**Observation, not built.** The top low-pass rotations serve only small x:

| rotation (half-turn) | used only by |
|---|---|
| 2^-10 | x ≤ 252 (lz ≥ 14, so δ = 0 and the bit is a pure table function) |
| 2^-11 | x ≤ 1008 |
| 2^-12 | x ≤ 4032 |

Folding the 2^-10 bit into the high pass would require adding a table-derived bit (with carry) at high-pass time. No construction was attempted within the timebox.

**Conclusion.** These rewrites found no gain over c6519219 (cost 94,599.61 as claimed by maoxin123). Nothing built.

---
## Absorbing the top low-pass rotation(s) into the high-word data: exact check on c6519219, 2026-11-10

**Measured** (exact over all 3,133,452 x; probes `probe_mx2*.npz`)

| weight (half-turn) | inputs with l = 1 | all of them in | l a function of | collisions h∧l | addresses carrying l = 1, shared with |
|---|---|---|---|---|---|
| 2^-10 | 114 | x ≤ 252 (δ = 0) | **(address, shift a)**, not the address alone | 44 | 105 addresses, shared with 1,440,327 inputs x > 252 (shifts 0..6) |
| 2^-11 | 373 | x ≤ 1008 | neither the address nor (address, a): δ ≠ 0 for some | 122 | 219 addresses, 2,777,584 inputs |
| 2^-12 | 1,294 | x ≤ 4032 | neither | 383 | 255 addresses, 3,118,508 inputs |

- **Possible saving.** Dropping the 2^-10 low-pass rotation and its drain step saves 7.19 + 1 Tof-eq, plus ≈ 0.2 from a slightly larger ε with 40 rotations: ≈ −8.4 Tof-eq. That would be cost ≈ 94,078 (ratio ≈ 22.07) if free.
- **Option 1, add to the high-word table data.**
  - The high pass phases H·2^a, so a data change ΔH at an address shifts the phase of every input sharing that address by ΔH·2^(a−18) turns.
  - The minimal change that supplies 2^-11 turns at shift 7 adds ≥ 2^-18 turns (3.8e-6) at shift 0, to 1.44 M other inputs. The margin is 3.18e-12 turns.
  - **Fails tolerance**, so it cannot be done through data alone.
- **Option 2, a gated extra bit G = [a ≥ 7]·l(address, a), added into the high-pass stream at 2^-10.**
  - Because of the 44 collisions, the add needs a carry. The carry propagates up to 5 weights (to 2^-5).
  - The high pass runs at 61–62 live qubits throughout (275 ops at 62 between ops 8300 and 8720, including every op from the 2^-9 to the 2^-5 rotation), so the carry qubit adds +1 at the peak.
  - Even with zero cost for computing G and the carries: 63 × (1525.80 − 8.4) = 95,596, which is above 94,599.6. **Loss.**
- **2^-11 / 2^-12:** not functions of (address, shift), so they are not candidates for table absorption.

**Conclusion.** Both absorption variants tested lose, so nothing was built. A route that avoided both the carry (the 44 collisions) and the shared-address perturbation was not found.

---
## Window and merge resynthesis search on c6519219: coverage report (no saving found), 2026-11-10

**Result: no verified saving.** Nothing was built.

### Tools (all in `tools/invsqrt/`)
- `groups.py`, `pairmerge.py`, `triplemerge.py`, `winsynth.py`, `linscan.py`.
- Reachable-state samples:
  - group/merge scans: all x ≤ 16384, plus 16384 random larger x, × 2 coin seeds;
  - window scan: all x ≤ 4096, plus 4096 random, × 2 seeds.
- Every hit is meant to be re-checked exactly over all 3,133,452 x.

### Coverage

| search | candidates | test | hits |
|---|---|---|---|
| CCX groups into one target (target not read in between; CX into target allowed) | 53 groups with ≥ 2 CCX, sizes 2–6 | **pair 2→1**: p_i ⊕ p_j ⊕ l·m in the span of all live wires, with l, m over span{4 factors, 1}; 196 pairs testable (15 had factors not live at either op) | 0 |
| same groups | 150 triples (141 testable) | **triple 3→2**: exhaustive over reachable coordinate patterns of the 6 factors (60–64 of 64 patterns occur, so almost no don't-cares) | 0 |
| single gates | all 1,393 unconditioned Toffoli-like gates | nonlinear term GF(2)-linear in the live qubits, i.e. replaceable by CNOT/Z | 0 |
| window resynthesis, ≤ 6 / 7 / 8 wires | windows start at each of the 1,150 depth-0 unconditioned Toffolis; 484 starts reach ≥ 2 Toffolis before a boundary (HMR, conditioned op, condition block, Z_POW, a dirty wire). In total 647 windows: T = 2: 484, T = 3: 161, T = 4: 2 | exact map + phase on reachable patterns. Tests: T → 0 (affine map, quadratic phase); T → 1 (one CCX with fan-out, or one CCZ); T → T−1 independent products | 0 |
| domain-aware scan, all x | — | never fires / equals a control / SWAP-equivalent | only the 19 nested conditional fix-up CCZs (not provable) |

**One false hit** (window at op 92, 2 → 1) came from a window-walk bug: a wire joined the window after skipped ops had modified it. The exact all-x pattern table exposed it, and the walk now rejects such "dirty" joins.

### Not covered
- Windows that cross HMR erasures and their conditional fix-up blocks. The window walk stops there, which is where most of the remaining 666 starts end.
- Dependent multi-Toffoli resynthesis (T' ≥ 2 with chained products).
- Mean-cost conditional splits.
- Windows wider than 8 wires.
- SAT search: pycryptosat was not needed for the classes above, which reduce to exhaustive GF(2) linear algebra.

---
## v104 (26ebf39d) pass: diff, shifter port, mean-cost scans (Agent A), 2026-11-10

### 1. Diff 26ebf39d vs c6519219
The only changed region is the forward normalisation shifter (lines 94–260 → 94–496).
- CSWAP 47 → 46 (**−1 Toffoli**), with CX 330 / X 22 around it.
- **gengsr's idea:** a single control wire q48 is re-targeted by CNOTs between almost every CSWAP, so **each CSWAP has its own control function of lz**. These are XORs of the thermometer-chain bits, which are free.
  - A control only has to be right on the lz values where its two positions can differ; elsewhere it is a don't-care.
  - That freedom gives a 46-swap reversal network: rev[0..12], rev[0..18] scattered, rev[0..20], rev[1..20], (1,4), rev[5..20], (14,20), (15,20).
- The high-pass mux is a stream (select + shift-2/shift-1 delay stages), not a reversal network, so the idea does not transfer there.

### Port to the un-normalisation network (49 CSWAP + 8 CCX), `tools/invsqrt/port_shifter.py` (exact, all x)
- **Available control functions at the end.** The lz-functions live at the start of the end network are lz parity and the thresholds [lz ≥ 2], [lz ≥ 4], …, [lz ≥ 20], plus [lz ∈ {8,9}] and its complement. Their span has dimension 12, against 22 for arbitrary functions of lz.
- **Controls that fail.** For gengsr's inverse network, **17 of 46** per-CSWAP controls are not in that span on their care sets.
- **Adding products.** Greedily adding products of two available functions (1 AND each), 5 added products still leave 2 controls inexpressible. That means ≥ 6 extra ANDs to save ≤ 3 CSWAPs.
- **Layout.** The end network also uses a different layout (x_n bits 14–20 held in scratch qubits q57, q27, q61, q51, q28, q40; bit 15 encoded).

**Port: net loss in the form tested. Not built.**

### 2. Mean-cost conditional moves (`tools/invsqrt/condmove.py`, `/tmp/blockscan.py`)
- **Unconditioned CCX whose product is read only under classical conditions.**
  - Scanned until the target's next unconditional write or erase, requiring a common condition bit across all reads.
  - 1 candidate (op 19177, q23 = OR(q27, q21)). It is read unconditionally as the control of `CSWAP q23 q18 q3` at op 19330, so **0 real candidates**.
  - A first, looser version of the scanner reported 17 candidates. All of them are consumed in both branches of a b414/b308/b70003 split.
- **Conditional blocks.** There are 112 top-level conditional blocks with Toffolis: 236 conditional Toffolis on 60 distinct bits.
  - Repeated control pairs occur only in 12 "execute-once" chains (`PUSH b_once; PUSH b_coin; CCX …; POP; POP; BIT_STORE0 b_once if b_coin`, ops 32768–35661). Those are already deduplicated by design.
  - No merge was tested beyond this.

### 3. Windows through HMR plus fix-up blocks
Not implemented within the timebox.

### Result
No verified saving on 26ebf39d. Nothing built.

---
## v104 (26ebf39d): conditional fix-up block resynthesis, coverage report (Agent A), 2026-11-10

Bar: 94,537.6. **Result: no verified saving. Nothing built.**

### Where the mean conditional Toffolis are
Measured by `/tmp/condfreq.py`: 65,536 random x, coin-randomised, execution frequency per gate.
- 243 conditioned Toffoli-like gates, contributing **80.71 mean Toffolis**. The unconditioned depth-0 gates contribute about 1,150.
- The largest outer conditional blocks are the **conditional-split pairs**.

| outer block ops | condition | branch structure | mean Toffolis |
|---|---|---|---|
| 19358 / 19430 | b414 / ¬b414 | each branch re-runs a ~8-CCX carry chain with HMR-to-scratch erasure and a CCZ fix-up | 4.0 / 4.0 |
| 20000 / 20121 | b308 / ¬b308 | ~12-CCX chain per branch | 5.7 / 6.0 |
| 20997 / 21063 | b70003 / ¬b70003 | ~7–8-CCX chain per branch | 3.5 / 3.7 |
| then about 20 blocks | — | 2–3 gates each | about 1.0 each |

The branches are mutually exclusive with p = 1/2 each, so moving work between them leaves the mean unchanged unless a branch's chain itself gets shorter.

### Innermost Clifford+Toffoli conditional blocks
Scope: no nested condition, no HMR, R or Z_POW inside. Tools: `tools/invsqrt/fixup_scan.py` (sampled) and `fixup_exact.py` (exact).
- **Count:** 77 blocks, covering 16.26 mean Toffolis.
- **Test:** is the value change (out ⊕ in) affine in the block wires, and the phase quadratic, on the reachable patterns? A pass means every Toffoli becomes CNOT/CZ under the same condition.
- **Exact run:** patterns over ALL x, union of 3 coin seeds, which is a sound superset since coins are independent of x. **0 hits.**
- **Sampled pre-scan false positive:** the sampled scan (32,768 x, executing lanes only) reported 1 hit, CCZ q28 q23 q57 at op 9232 (frequency 0.0076, mean 0.008). Exactly, all 8 patterns of (q28, q23, q57) occur: 110 for 104 inputs and 111 for 88, coin-independent. So the phase is genuinely cubic.

### Not covered (≈ 64 of the 80.7 mean conditional Toffolis)
- Blocks with nested conditions or HMR inside: the conditional-split carry chains above, and the execute-once chains at ops 32768–35661.
- A general window model with coin inputs ((state, coin) → (state, phase), with its own measurement schedule) was not implemented within the timebox.
- The next step would be to resynthesise one branch of the b308 split (12 CCX, mean 6.0) as a carry-recomputation problem.

---
## v104 (26ebf39d): conditional-split branch resynthesis, b308 / b414 / b70003 (Agent A), 2026-11-10

Bar: 94,537.6 at Q = 62. **Result: no verified saving. Nothing built.**

Tools: `tools/invsqrt/branch_spec.py`, plus scratch scripts for live profiles, pair tables and idle-wire tests.
- `branch_spec.py` recomputes each branch on its executing lanes only: all x, 2 coin seeds, about 3.13M lanes.
- Sampled GF(2) span tests use 16,384 lanes; any positive is re-checked on all lanes.
- Positive controls behave as expected: c1 is quadratic in the entry wires; c6 is quadratic with c5 present and not without it; a random bit fails.

### Exact specs (executing lanes, forced execution matches the parsed chain)
Each branch is a Gidney adder.
- **What it computes:** b_k ← a_k ⊕ b_k ⊕ c_k for every pair, and t ← t ⊕ c_n, with c_{k+1} = MAJ(c_k, a_k, b_k).
- **Erasure:** the carries are erased by HMR, with fix-ups that are CZ or, after an early erase, CCZ.
- **B = A plus a phase:** B (split bit = 1) additionally applies the phase (−1)^{t_old · c_n}.
- **What the phase repays:** the kick of the overflow bit measured at 18748 (b414, q51), 18705 (b308, q57) and 18674 (b70003, q61). Our reading, not checked numerically: summed over a split bit's rows, these phases repay the measured top bit.

| pair (A / B ops) | chain (cin; (a,b) pairs) → t | live at entry | A mean | B mean | early-erase fix-ups |
|---|---|---|---|---|---|
| b308 20000 / 20121 | q18; (36,54)(37,14)(38,55)(39,52)(42,22)(24,29)(59,45)(43,46)(44,30)(60,31)(15,58) → q47 | 53 | 11 CCX + CCZ@b299 = 5.75 | 11 + CCZ@b299 + CCZ@b63034 = 6.00 | A erases c5 early; B erases c1 and c5 early |
| b414 19358 / 19430 | q18; (39,54)(42,14)(24,55)(59,52)(43,22)(44,29)(60,45)(15,46) → q30 | 53 | 8 CCX = 4.00 | 8 CCX = 4.00 | none (B peaks at 61, so its ancilla is free) |
| b70003 20997 / 21063 | q41; (42,46)(24,30)(59,31)(43,58)(44,47)(60,56)(15,48) → q16 | 56 | 7 CCX = 3.50 | 7 + CCZ@b63024 = 3.75 | B erases c1 early |

- **Slot arithmetic.** A needs n−1 carry slots; B needs n (the extra one holds the final product p for CZ(t, p) followed by CX(p → t)).
  - b308: 9 free slots, so A must erase 1 carry early and B must erase 2.
  - b70003: 6 free slots, so A erases none and B erases 1.
  - b414: 9 free slots, so neither erases.
- **Cost of an early erase.** Each costs one CCZ under a fresh coin: 0.5 per execution of the branch, 0.25 per shot.
- **All 11 split pairs in 18.8k–21.2k:**
  - Together they hold 37.75 mean Toffolis per shot (A 17.75, B 20.00).
  - Early-erase fix-ups account for 3.75 of that. The B-only part (the extra slot for p) accounts for 2.25 (9 pairs × 0.25).

### Constructions tested (all exact or sample-refuted on executing lanes)
- **R0 — redundant live wire** (linear dependency among the entry wires, which would give a free ancilla): none, in all 6 branches.
- **T1 — shorter chain** (some c_k linear in the entry wires plus lower carries): none, k = 1..n, all 6 branches.
- **T2 / T2b — free early erase** (c_{k+1} quadratic without c_k):
  - Tested against the entry wires, and against the wires actually present during the unwind (sums s_j for j ≥ k+1, t ⊕ c_n).
  - No k, in any of the 6 branches.
- **T3 / T3b — ancilla-free B** (t_old · c_n quadratic over the entry wires or over the end-of-branch wires): no, for all 3 targets.
- **Alternative B constructions** (expected mean change per pair, against the current 0.25):

| B construction | cost inside B | mean per pair | change |
|---|---|---|---|
| current: early erase, CCZ under a coin | 0.5 | 0.25 | — |
| CCX + CCZ(t, a′, b′) | 1.0 | 0.5 | +0.25 |
| CCX + CS†(a′, b′) via 3 T (S is free) | 0.75 | 0.375 | +0.125 |
| dirty-ancilla CCX pair | 1.0 | 0.5 | +0.25 |
| in-place Cuccaro MAJ for one slot | 1.0 | 0.5 | +0.25 |
| recompute the early-erased carry | 1.0 at p = 1/2 | 0.25 | 0 |

  The CS† row uses CC(XZ) = CZ(a,b) · S_t · CCX · CS(a,b) · S_t†.
- **Hoisting the common chain out of the split:** the prefix does not shrink, and B still needs its own slot at the top, so there is no change.
- **A free qubit for the whole split region.**
  - Only 9 wires are untouched across 18750–21150: q11, q12, q13, q17, q19, q20, q25, q26, q49.
  - None is linear or quadratic in the other live wires, at 18750 or at 21150.
  - Jointly they take 332 of 512 patterns, so they do not compress to 8 wires.
  - Going to Q = 63 would cost about 1,525 against at most about 217 saved (3.5 mean Toffolis × 62).

---
## Measurement-crossing search on a15b0d73 (alexchilton, 93,925.3), day-1 checkpoint (Agent A), 2026-11-11

**Verdict: (B).** The boundaries examined offer no feasible gain at Q = 62. Nothing was built.

### What changed from 26ebf39d
- **Totals:**
  - Mean Toffolis go from 1229.71 to 1219.83 (−9.88).
  - The static maximum goes from 1392 to 1381.
  - The rotations are unchanged: 41, ε = 2.43e-13.
  - Unconditioned static Toffolis go from 1149 to 1128.
  - Conditioned mean Toffolis go from 80.71 to 91.81.
- **Edits:**
  - All 204 CSWAPs are gone. They became CCX moves: in the shifter, in the high/low-pass muxes, and in the un-normalisation, which now ends with 8 HMR + CCZ fix-ups worth 4.0 mean.
  - A speculative measurement chain was added at 22222–22263: q44, q43, q59, q24 and q42 are measured until the first coin = 1, and the q60 accumulator only runs when a coin fired. This repays at 23783–23830.
  - The third small b414 split pair was removed.
  - The 18.2k region was rewritten (150 → 29 lines).
- **Split pairs:** the 10 remaining split pairs are identical to the 26ebf39d specs, shifted by −61 ops after 19.0k. The branch analysis of 2026-11-10 therefore still applies.

### Measurement-boundary map
Tools: `tools/invsqrt/hmr_map.py` (65,536 random x plus coins; it reproduces the official mean of 1219.8). Totals: 864 HMRs, 22 zero erases, 155 conditioned, 86 with Toffoli fix-ups.

| stage (ops) | HMR | unconditioned static Toffolis | conditioned mean Toffolis |
|---|---|---|---|
| normalisation 0–500 | 20 | 66 | 0 |
| table XAG 500–8400 | 13 | 167 | 0 |
| high pass and its delay-line fix-ups 8400–9320 | 27 | 65 | 1.99 |
| pre-rows 9320–12000 | 20 | 30 | 0 |
| forward rows 12000–16280 | 278 | 332 | 0 |
| low pass and its delay-line fix-ups 16280–18560 | 38 | 87 | 5.97 |
| reverse rows and split pairs 18560–25300 | 420 | 324 | 70.84 |
| CZ-only phase repair 25300–32700 | 8 | 0 | 0 |
| execute-once unlookup chains 32700–35700 | 9 | 0 | 8.99 |
| un-normalisation 35700–36800 | 31 | 57 | 4.01 |

**Ranking (correction plus reconstruction, mean Toffolis):**

| measurement cluster | correction mean | what it pays for |
|---|---|---|
| Split-pair HMRs for b308, b414, b70003 (18662, 18705, 18631) | 13.0 + 11.0 + 9.0 | Overflow-bit kicks repaid inside 10 split pairs. The pairs total 36.5 per shot; the B-only overhead is 2.0. |
| 18 reverse-row block-boundary carries (18632–22158) | ≈ 20.0 | 1.0 or 1.5 each: recompute one carry by CCX, then a CCZ, under the coin |
| Speculative chain (22222–22263) plus its re-measure (23830) | ≈ 10.4 | — |
| Unlookup execute-once chains (9 HMRs) | 9.0 | Shared AND terms are already computed at most once |
| Low-pass delay line (26 HMRs) | 6.0 | — |
| End of un-normalisation (8 HMRs) | 4.0 | — |
| High-pass delay line (15 HMRs) | 2.0 | — |

**Reconstruction.**
- The large one is by design: the reverse rows recompute the forward rows' carries (324 Toffolis against 332 forward).
- Erase → reconstruct pairs within 4,000 ops (`recon_scan.py`, exact check in scratch `br/recon_exact.py`):
  - 72 were found on the sample, 22 of them with slack on the sample.
  - On all x, 14 of the 22 were erasures of a value already linear in the live wires, so there is nothing to save.
  - The other 8 are real: ops 16189–16238 → 18510–18553, 8 CCX.

### Candidates priced (Toffolis saved / added / extra workspace at live = 62 / rotations)
1. **Keep the 8 low-pass-erased values instead of recomputing them at 18.5k.**
   - Saves 1.0 each, adds 0, rotations 0.
   - Each kept value needs +1 qubit at 193 ops where the exact live count is 62 (all x, 2 seeds, from 16342 onward, inside the low pass). **Infeasible.**
2. **Defer a costly fix-up to a later point where the erased value is linear or quadratic in the live wires** (`kick_defer.py`; 65 unconditioned HMRs with Toffoli fix-ups, linear test at every depth-0 op, quadratic test on a 500-op grid).
   - Only 3 hits on the sample:
     - 8821 (high pass): its value is quadratic at op 19000. But it is 1 of 15 HMRs sharing one fix-up cluster, so deferring it alone removes no Toffoli.
     - 16598: 0.001 mean.
     - 16603: a sample artifact (its value is zero on the sample).
   - **Saving ≈ 0.**
3. **Clifford reduction of any CCZ or CCX against all live wires** (`cond_quad.py`, 1,373 gates).
   - A random sample gave 93 hits; all are rare-lane artifacts. A stratified sample gave 29 hits, all in deep execute-once nests.
   - The 7 largest were re-tested exactly on all x (scratch `br/quad_exact.py`): **all refuted.**
4. **Merge fix-ups on related coins.**
   - Fix-ups that share controls (q23·q28, q18·q23, q27·q23) are the execute-once chains. Their cost of 1 − 2^-k already equals one merged CCZ.
   - The remaining early-erase CCZs under independent coins have disjoint cubic factors, so the saving 0.25·(c1 + c2 − c12) is 0.
5. **Fold the split-pair B overhead (2.0) into an existing block.** Yesterday's tested alternatives cost +0.125 to +0.25 per pair.
6. **Block-boundary fix-ups (≈ 20).**
   - Keeping c_{k−1} needs a slot through the row, and the rows peak at 62.
   - None of these values reappears later in linear or quadratic form, so deferral is not possible.

None of the candidates touches the rotations.

**Why no gain.** Every cheaper crossing found needs either one more live qubit at ops where live = 62 (the low pass, the row peaks, the B-branch peaks), or a phase that is not Clifford on the reachable states.
- A 1% gain at Q = 62 would need a structural change that frees a qubit across 16.3k–22k.
- Yesterday's idle-wire test (9 idle wires, 332 of 512 patterns) and today's exact live profile both rule out the obvious ways to do that.
