# Brief A: the invsqrt benchmark (Benchmark I, phasing by 1/√x)

Author: Agent A (fusion/invsqrt). Written 2026-11-08.
Paths: `K=/tmp/claude-0/-home-user-Javascript-repo/948a0d77-c08e-599f-bb10-c0ad3e21c7ce/scratchpad/kg`.
Verifier = `$K/data/verifiers/invsqrt/verify_submission_invsqrt.py` (written "V:line" below). Reference generator = `$K/data/verifiers/invsqrt/nr_reference_circuit.py` ("R:line"). Paper = `$K/paper.txt` (arXiv:2610.23832).

**Sources I actually read:** the full paper text, §I to §III.A and App. B in detail; the verifier and the reference generator, line by line; pages.md; the metric notebook; the invsqrt parts of all the notebooks in `$K/nb`. I also extracted the 93-qubit-line sources embedded in alexchilton's notebook, to `$K/alex_src/` (parsed with `ast.literal_eval`, never executed). From outside I read one thing, the Qualtran `docs/kickmix/kickmix_instructions.md` (via raw.githubusercontent.com).
**Fetches that failed:** arxiv.org and pnas.org do not resolve in this sandbox. I could not read any of the cited papers: Rubin PNAS 2024, Gidney 1709.06648, Häner et al. 1805.12445, Su et al. 2105.12767, Kliuchnikov 2203.10064, Babbush 2603.28846, Long et al., or Gidney 2505.15917. Anything I say about them comes from the paper's summary or my own background knowledge, and is marked [bg]. arxiv.org has to be allowed in the session network settings to fix this.
**Nothing downloaded was executed.** All numbers marked "measured" come from verifier JSON receipts printed inside the notebooks.

---

## 1. Theory in plain language

**Why 1/√x.** The setting is first-quantized Trotter simulation of η = 218 electrons on a grid, for stopping power in inertial-confinement-fusion plasma (Rubin et al., PNAS 2024; paper §III.A.1). The electron–electron Coulomb term V = Σ 1/|r_i − r_j| is diagonal in the position basis. One Trotter step therefore needs, for every pair: compute w = Σ_d (r_i,d − r_j,d)², compute 1/√w, phase by e^{−iδ/√w}, and uncompute (paper Eqs. 9–12). Only the 1/√w → phase → uncompute part is benchmarked. The input is the 22-bit w (n_p = 10, w ∈ [1, 3·(2¹⁰−2)²] = [1, 3,133,452]), and β = 1. The routine runs about η² times per Trotter step, so constant factors matter a great deal.

**Phase kickback / phasing by a computed value.** Suppose a register holds the bits y_j of a fixed-point number y = Σ y_j 2^{j−F}. Then applying Z_POW (a phase rotation) of angle 2^{j−F} turns to each bit j multiplies the state by e^{2πi y}. That is "phasing by y" (R:343–348). The phase depends only on the computed value, and the y register is then uncomputed. So the net map is |x⟩|0⟩ → e^{2πi/√x}|x⟩|0⟩, and the only output is the phase.

Bits of weight 1/2 and 1/4 turn are Clifford (Z, S) and free. Weight 1/8 is a T gate. Every finer weight is a non-Clifford rotation, which must be synthesized into T gates.

**Phase-gradient alternative [bg].** In the usual fault-tolerant setting you add y into a "phase gradient" register Σ_k e^{−2πik/2^b}|k⟩. That costs about b Toffolis per use, and the gradient state is prepared once. **This is impossible in kickmix.** Kickmix instructions never create superpositions (paper §II.A; the instruction list has no H except inside HMR). alexchilton also reports that "a phase-gradient register needs the same 33 rotations plus 30 qubits". So for this benchmark the rotations are a real per-call cost.

**Rotation pricing.** Z_POW angles are classed at V:140–146: multiples of ½ turn-unit are Clifford, multiples of ¼ are T, everything else is a rotation. Each rotation costs 0.56·log₂(1/ε)+5.3 T (Kliuchnikov et al. "mixed fallback", V:148–149). ε is not free. The verifier takes the **smallest absolute leftover margin over all x**, min_x(tol(x) − |err(x)|) in turns, multiplies by π, and splits it evenly across the n_rot rotations (V:316–323):

  ε = π · min_margin / n_rot

The cost is C = Toffoli + T/4 (V:323–324). One rotation is therefore about 7.2 Toffoli-equivalents at the public circuit's ε.

**Fixed-point Newton–Raphson (the reference).**
- Normalize x by counting leading zero *pairs* s, so x_norm = x·2^{2s} with M ∈ [1,4).
- Take an initial guess y₀ ≈ 1/√M from a cubic: four intervals and two polynomial sets, with the [2,4) cases obtained by rescaling the coefficients by 2^{-j}/√2 (App. B.1).
- Do one NR step, p = y₀(3 − M y₀²) = 2/√M, which roughly doubles the number of correct bits.
- Denormalize with y₁ = p·2^s, phase by the bits of y₁, and run everything in reverse (R:1–21; paper §III.A.2 and App. B).
- The NR step costs a squaring plus two multiplications, around 2,350 Toffolis per direction. That is why it was the first thing the community deleted.

**Polynomial / piecewise approximation (what the public line does).** Skip NR and evaluate one low-degree polynomial per segment, accurate to 2^-24 relative error by itself.
- Many segments make the degree small. The public line uses 256 segments (7 mantissa bits plus the exponent parity) and degree 2.
- The coefficients come from a QROM (table lookup) addressed by the high mantissa bits.
- Horner's rule is used: R = K1 − C2·δ, y = K0 − R·δ.
- A *centered signed-digit* δ = Σ (2d_i−1)2^{i−22} makes every Horner row an unconditional add or subtract of a shifted register. The row only needs CNOT flips, not a controlled multiply, using Y − A = ¬(¬Y + A) (`$K/alex_src/stage_ref.py.txt:11–13`, 237, 244).

**QROM / lookup.** A table of N words is read by unary iteration, about N Toffolis [bg], or by QROAM, which uses fewer Toffolis but more qubits.
- Uncomputing a lookup by measurement is much cheaper than computing it. You HMR all output qubits, then apply a phase fix-up that is itself a small lookup (Gidney/Berry et al. [bg]). In kickmix this is `del_lookup` (stage_ref:259).
- The public 62-qubit line decodes its 256-entry table with "algebraic three-product decodes, 169 AND gates in all" (dmitriigluzdov nb line 95).

**Measurement-based uncomputation.**
- If a qubit holds a Boolean function f(x) of other qubits, HMR (X-measurement plus reset) gives a random bit b and the phase (−1)^{b·f(x)} (paper Eq. 1).
- A Clifford-plus-AND fix-up conditioned on b cancels that phase. For a temporary AND the fix-up is one CZ, so uncomputing an AND is free (Gidney 2018 [bg]; paper §II.A).
- The same trick applies to adder carries ("measured carry uncomputation", dmitriigluzdov 96) and to whole lookups.
- Classically conditioned blocks run only on shots where the condition holds. **The verifier charges the *mean* executed count per shot** (V:29–30, 317–319). A fix-up that costs k Toffolis therefore costs k/2 on average. This explains why the public file has 1,404 static Toffolis but only 1,245.1 on average.
- In-place permutations (the CSWAP shift networks) cannot be measured away. They have to be reversed gate by gate.

**Gidney adder [bg].** An n-bit addition costs n−1 Toffolis using temporary-AND carries, and the carries are uncomputed for free by measurement. The cost is n−1 extra ancilla qubits at the peak. That ancilla cost hurts here because cost ∝ Q.

---

## 2. Exact contract and cost anatomy

### 2.1 Contract (verifier)
- **Register schema** (V:178–194). There is exactly one register, named `x`: 22 distinct qubits, little-endian. Every other qubit is scratch and must return to |0⟩. **Q = `circuit.num_qubits`** (V:327), which is the peak allocation, x included.
- **Inputs.** Every x ∈ [1, 3,133,452] is tested, with shot i using x = (i mod max_x)+1 (V:200–202). With 64 shots per x (V:70, 110) that is 200,540,928 shots. Nothing is sampled, so the circuit cannot exploit a non-uniform input distribution. The Legendre gaps (numbers of the form 4^a(8b+7) are not sums of three squares) are still tested even though they are physically unreachable.
- **Pass/fail per shot.**
  - x must be restored (V:275–276).
  - Scratch must be clean (V:277–281).
  - The phase error (θ − target) mod 1, in units of 2⁻⁶⁴ turns, must satisfy |error| ≤ tol(x) = floor(2⁶⁵/√x) >> 25, which is about 2⁻²⁴/√x turns (V:117–131, 283–293).
  - **Any single failing shot fails the whole submission** (V:289–293 raises). Probabilistic failures are not allowed; this is the k = 0 regime, unlike DQI.
- **HMR / R randomness.** The simulator draws measurement outcomes from a seed made from the circuit's SHA-256 plus the secret Kaggle salt (V:152–163, 257, 309–310; metric nb lines 155–175). The 64 shots per x sample 64 random outcome histories per input. Correctness must hold for all histories, or the failure has to be so rare it is never sampled. Relying on that is fragile and against the spirit of the contract; I do not recommend it.
- **Cost.**
  - toffoli_count is the mean number of executed CCX/CCZ/CSWAP per shot.
  - t_base is the mean number of T-class Z_POWs.
  - n_rot is the mean number of executed non-Clifford Z_POWs.
  - ε = π·min_margin·2⁻⁶⁴/n_rot (V:320).
  - C = toffoli + (t_base + n_rot·(0.56 log₂(1/ε)+5.3))/4.
  - **score = Q·C** (V:316–328).
- **Format pitfall.** `to_file` writes text kmx by default, but the leaderboard picks the format from the file suffix, so pass `format='kmb'`. Several teams lost submissions to this (alexchilton nb).

### 2.2 Reference circuit (paper §III.A.2, App. B.3; R:351–377)

Reported values: **Q = 260, 7,735 Toffolis, 1 T, 37 rotations, so C = 7,988 and Q·C = 2.0768×10⁶.** The exact value used by the leaderboard is 2,076,774.23 (manwithacat nb line 100). Worst relative error is 2^-25.07, about half of the tolerance.

Forward Toffoli budget at n_p = 10, from App. B:

| stage | Toffolis (forward) |
|---|---|
| normalize (n_p(n_p+2)) | 120 |
| select interval | 3 |
| in-place cubic Horner | 1,071 |
| square y₀² | 442 |
| ×x_norm | 1,043 |
| 3 − z | 28 |
| ×y₀ | 867 |
| denormalize (30 n_p CSWAP) | 300 |
| **forward total** | **≈3,874** |

The reverse pass costs about the same, minus the free AND uncomputes, giving 7,735 in total. Each rotation costs ≈27.3 T at the reference's own ε. The registers I count from R:365–369 are:

| register | qubits |
|---|---|
| x | 22 |
| y1 | 40 |
| flags | 10 |
| selectors | 3 |
| 4 coefficient registers ×17 | 68 |
| square | 28 |
| z | 30 |
| scratch | 30 |
| **sum** | **231** |

The other 29 to reach 260 are presumably kickmix's internal adder/AND workspace.

### 2.3 How the public line got there
1. **≈103 qubits (Sumit Chongder).** Delete NR. Use binary normalization (shift stages of 16, 8, 4, 2, 1 into M ∈ [1,2), with the exponent parity e). Read one 256-entry QROM addressed by (7 mantissa bits, e) holding quadratic coefficients. Evaluate a centered signed-digit Horner with Gidney adders, then binary denormalization and one Z_POW per bit, followed by a mirrored uncompute. Source: `$K/alex_src/stage_ref.py.txt:5–18`.
2. **93 qubits, about 1,470 Toffolis, 44 rotations, cost 165,026, 12.6× (anazemcev, Rudra, Kirill, alexchilton).**
   - Phase and release the constant high word early.
   - Split the y register into a 21-bit low part plus the high constant.
   - Borrow x[21], which is always 1 after normalization, as a clean carry wire.
   - Turn moves into empty qubits into AND+CNOT instead of CSWAP (−1%).
   - Share prefix-AND flags (−0.3%).
   - Drop the coefficient width F2 from 10 to 9 bits (one qubit, −1%).
3. **63 → 62 qubits (mrmeows/team selenium → busyaprime → yoyobar with "GPT-6 Astra" → Syed V5/V11 → Hosen42 → Maoxin → Kirill/Atakan/Özer).** Their own descriptions (dmitriigluzdov nb lines 88–99; yoyobar; kirilltym-pi lines 6–30):
   - an 8-bit semi-log table, a degree-2 Horner and a **two-pass phase with 41 rotations**;
   - **deferred fan-in lookup** (169 ANDs);
   - **measured carry uncomputation** of the pre/post-low add/sub, the Q rows and the high-R un-ripple (X-measure plus conditional CZ instead of a reverse ripple);
   - carry-save merges;
   - **exact window resynthesis** of every window of up to 12 wires from its truth table including phases (seven windows went from three Toffolis to two);
   - removal of HMRs on provably-|0⟩ qubits (mean T 20.5 → 14.5 → 1.0 now);
   - a thermometer-code shift register erased top-down by measurement;
   - normalize/denormalize CSWAP networks cut to 47 and 48 CSWAPs;
   - "domain-aware" deletion of a CSWAP that is provably inactive on all legal inputs (Atakan);
   - Hosen42's "measure-first / carry erasure".

### 2.4 Public best (`13b5bf7a…`, 62 qubits), measured receipt (kirilltym-pi lines 1538–1552)

| quantity | value |
|---|---|
| Q | **62** |
| mean Toffolis / shot | **1,245.12** (static max 1,404) |
| T | 1.0 |
| rotations | **41**, ε = 2.434×10⁻¹³, so 28.76 T each |
| rotation Toffoli-equivalents | 41·28.76/4 = **294.84 (19.1% of C)** |
| C | **1,540.21** |
| Q·C | **95,492.95** |
| ratio | **21.748×** |
| worst error/tol | 0.99932 at x = 161 |
| reaction depth | 728 |
| instructions | 53,688 |

**Rough split of the 1,245 Toffolis.** This is my estimate from the descriptions, not a flame chart:

| part | Toffolis |
|---|---|
| normalize + unnormalize CSWAPs + flags | ≈105 |
| lookup (169) + measured unlookup | ≈200–230 |
| R rows, both directions | ≈100–150 |
| y rows (14 rows × ≈20 bits, compute + uncompute, carries partly measured) | ≈500–600 |
| two-pass phase shifting / merging | ≈100–150 |

Rotations add another 295 Toffoli-equivalents on top. alexchilton (nb line 901) says that in the 63-qubit version "all 63 wires hold nonzero values for a third of the run, mostly in the 32 Horner rows, with no linear relation among them".

**Exchange rates at the public best:**
- 1 qubit = 1/62 = **1.61%** of cost = **24.8 Toffolis**.
- 1 Toffoli = 0.065%.
- 1 rotation ≈ 7.19 Toffoli-equivalents = 0.47%.

---

## 3. Error budget
- **Tolerance.** tol(x) = 2⁻²⁴/√x turns (relative 5.96×10⁻⁸). At x = 1 it is 5.96×10⁻⁸ turns; at max_x it is **3.37×10⁻¹¹ turns, about 2⁻³⁴·⁸**.
- **Two consumers share it:**
  - (a) Simulated arithmetic error: polynomial approximation, truncation and rounding. This is checked per x against the relative tolerance.
  - (b) Unsimulated rotation-synthesis error. This is charged against the **absolute** minimum margin over x, which in practice sits at large x where tol is smallest.
- **Polynomial error has essentially no slack.** The public file sits at 0.9993·tol at x = 161. manwithacat's study ("Is the 63-qubit inverse square root optimal?", cited by alexchilton nb line 47) says the shipped table rounding is the only one that passes over the nine binding segments, and the 44 (now 41) angles are at the LP optimum. Removing coefficient bits or Horner rows in the same design will break the tolerance unless the error is redistributed, for example through segment boundaries, a different δ width or non-uniform segments.
- **Rotation error is cheap to trade.** dC/d log₂(margin) = −0.56·n_rot/4 = **−5.7 Toffoli-equivalents per halving or doubling of the absolute margin**. So spending the absolute margin at large x to remove arithmetic costs only about 6 Toffoli-equivalents per factor of 2. Conversely, buying margin is almost worthless.
- **Rotation-count floor (my estimate).** With a binary-weighted phase register, the weights needed run from 2⁻⁴ down to about 2⁻³⁵ or 2⁻³⁶ turns, since the LSB must be well below 3.4×10⁻¹¹. That is **≈32–33 rotations**, plus 2 Clifford and 1 T bits.

  A counting argument also applies to any scheme that phases Boolean wires with fixed single-qubit angles. Subset sums of k angles mod 1 need about 2^k ≥ 1/(2·3.4×10⁻¹¹) points to hit large-x targets, so k ≳ 34 for roughly uniform coverage. Log-distributed subset sums could in principle go lower, but I know of no construction (speculation).

  The public file uses 41, so **at most 8 rotations ≈ 58 Toffoli-equivalents ≈ 3.7%** is available here. The two-pass design probably spends those 8 extra rotations to save qubits, so the gain is not free.
- **No probabilistic failures** (V:289–293). The paper's 2√ε fidelity bound (§II.C, Eq. 3) is the justification for fuzz testing in general. For invsqrt every x is enumerated, so effectively ε = 0 is required over the sampled HMR histories.

---

## 4. Optimization ideas beyond the public 62-qubit circuit (ranked by expected value per effort)

Baseline: Q = 62, C = 1,540. Gains are on the invsqrt cost; the GM gain is about ⅓ of that.

1. **Cut qubits (62 → 58–60): −3% to −6.5%.** This is the biggest lever per unit of work, because one qubit = 24.8 Toffolis.
   - **Information slack.** After normalization the circuit holds x_norm (22) + shift flags (≈5) = 27 qubits for log₂(3.13M) = 21.6 bits. The bottom s′ bits of x_norm are known zeros and the top bit is a known 1 (already borrowed).
   - **Idea (speculative): pack the flags into the vacated low mantissa bits.** Use a floating-point-like in-place encoding, or a thermometer code that overwrites zeros. Alternatively, recompute flags from x_norm when needed instead of storing them. That could free 2–4 qubits.
   - **Also:** time-slice the Horner rows so the R register and the low-y register never peak together, for example by computing the R digits in a carry-save form inside the y accumulator. Or re-measure the coefficient registers (HMR) after their last forward use and re-look-up for the reverse pass. Re-lookup costs about 170+ Toffolis, which breaks even at about 7 qubits. That only pays if the freed register is live at the peak.
   - **First step:** a live-qubit profile (kickmix flame chart) to see which registers set the 62-qubit peak.
2. **Remove rotations by merging the two phase passes: −2% to −3.7%.** Make rotation weights distinct. Wherever two passes apply rotations of the same weight, add the overlapping bits first (about 1–2 Toffolis per bit) and rotate once. Each rotation removed saves 7.2 − (≈2) Toffoli-equivalents. Target 41 → 34–35. Check the qubit cost: if merging needs a wider register at the peak, the trade is lost.
3. **Re-optimize the approximation jointly with the rotation budget: −1% to −4% (speculative).**
   - Today the y LSB is chosen for the polynomial; the rotation margin is a by-product.
   - Better: (a) **non-uniform segmentation**, with more segments where the second derivative of 1/√M is large (small M) and fewer near M = 2. The table could be indexed by a cheaper address function, saving lookup ANDs or one δ row.
   - (b) **Choose δ width (14) and the R-row drop set by a joint integer program** over table words, Horner rounding and carry-ins, with exact all-x checking. Each δ-row dropped saves about 2×20 Toffolis (≈2.6%).
   - (c) **Minimax with the error weighting the verifier actually uses:** relative error per x plus an absolute-margin term at large x.
4. **Cheaper normalization / denormalization: −1% to −3%.**
   - The total is about 95 CSWAPs for normalize/unnormalize plus the denormalize shifts. CSWAP networks cannot be measured away, but out-of-place copies can.
   - Option: compute only the bits the arithmetic needs (14 δ bits + 7 address bits) out-of-place with a multiplexer, then HMR-uncompute. The fix-up phase is (−1)^{Σ m_j x_{j+s}}: CZs between x bits and a one-hot s indicator, all Clifford. **Forward cost about 11 shift values × ≈21 bits of ANDs, roughly 230 Toffolis, against ≈95+95 today. Probably not a win** except for parts of the network. Worth a quick count.
   - Alternative: apply the shift to the *phase angles* rather than the register. For the top bits, which are few, a flag-controlled Z_POW is a Toffoli plus a rotation (bad). For the 2–3 Clifford/T-weight bits a controlled S/T is cheap. That might remove a few CSWAPs.
5. **Lookup cost (≈170 compute + measured uncompute): −0.5% to −2%.**
   - Reduce the table to fewer distinct output functions: share K2 across neighbouring segments, or store K1/K0 differences and let a Horner row absorb them.
   - Exploit the exponent parity e more cleverly, since the √2 scaling relates its two halves.
   - The window resynthesis done by the community suggests the decode is near-optimal *for this table*. Gains need a table that is algebraically cheaper, chosen by a search that co-optimizes words and AND count, like the chemistry teams' "soft words".
6. **Mean-cost tricks: −0.5% to −1.5%.** Push as much fix-up work as possible inside HMR-conditioned branches, which execute on half the shots. Prefer HMR-based uncompute everywhere, for carries, temporary products and lookup outputs. The public file already does a lot of this (1,404 static versus 1,245 mean).
7. **Gate-level superoptimization: −0.3% to −1%.** Continue exact window resynthesis with wider windows (more than 12 wires), domain-aware deletions (gates inactive on all reachable states) and AND merges. This is well-trodden territory, with diminishing returns of about 1–3 Toffolis per find.
8. **Bigger redesigns (high risk, unknown sign).**
   - (a) A cubic with 32 segments: measured as a net loss (−207 lookup Toffolis, +450 row Toffolis).
   - (b) Linear interpolation with a 2,048–4,096 entry table: the lookup is too expensive in Toffolis, or in qubits for QROAM.
   - (c) Bipartite/multipartite tables whose outputs are *phased rather than added*: needs about 2¹⁷ entries at 25-bit precision, so it is out.
   - (d) Bring back an NR step with a low-precision 12–13-bit guess: needs a squaring and two multiplies (about 1,000+ Toffolis), so it is likely out.
   - (e) Phase the K0 part directly from the lookup instead of adding it: saves about 40 adder Toffolis but costs about 20 extra rotations, so it is a loss.

   My judgment: the degree-2 / 256-segment / signed-digit design is the right family. The remaining gains are in qubit peak, rotation count and joint precision tuning.

**Speculative combined target:** Q ≈ 58–59 and C ≈ 1,420–1,470, giving Q·C ≈ 83k–87k, **24–25×** (+11–15% over public). A heroic outcome is Q ≈ 55, C ≈ 1,350, giving 74k, about 28×. Google's internal hash (paper footnote 2) is undisclosed. The paper says all three benchmarks "can be further improved beyond the circuits reported to date".

---

## 5. Position statement for the debate

- **Arithmetic of the GM.** Score = (r_inv·r_dqi·r_chem)^{1/3}. A 1% cut in any task's cost raises the GM by 0.332%, whatever task it is. From the public plateau ≈25.09:

  | target | GM needed | needed product of ratios | invsqrt alone would need |
  |---|---|---|---|
  | top 1% (≈26.25) | +4.6% | ×1.145 | 21.75 → 24.9× (Q·C 83.4k, −12.7%) |
  | top 10 (≈27.0) | | ×1.25 | 27.2× |
  | #1 (29.30) | | ×1.59 | 34.6× (Q·C ≈ 60k): implausible with what I know |

- **Headroom estimate.** About +10–15% on invsqrt is realistic with sustained work: 3–4 qubits plus about 6 rotations plus precision re-tuning. That is worth **+3.3% to +5% GM, roughly 25.1 → 25.9–26.3**, which alone is about the top-1% line. Beyond that, ×1.25–1.3 (27–28×) requires a structural qubit-peak breakthrough (speculative).
- **Why prioritize it:**
  - (i) **Fast verification.** Exhaustive verification takes about 12 minutes (kirilltym receipts: 708–757 s), and it is deterministic and salt-robust, because all x are tested and correctness must hold for every HMR history. Our gains will carry from public to private LB with no variance risk. DQI's R(ε₊) depends on failure counts under a secret salt.
  - (ii) **Cheap iteration.** The design space is small and understood. A local numpy model that reproduces the arithmetic exactly (as the public generators have) lets us screen thousands of precision configurations in seconds before building circuits.
  - (iii) **Linear qubit exchange rate.** One qubit equals 1.6%, and the qubit peak is where a clever idea pays.
  - (iv) **Side prize.** A $10k single-task prize for fusion exists.
- **Why not over-prioritize it:**
  - The public line has had about 15 teams and AI agents grinding gate-level edits. The remaining easy wins are gone; null results are documented (alexchilton nb lines 37, 47, 52).
  - The leader (#1 "James & Geremie & Tony", including jsday96) is the author of the Schur/continued-fraction DQI decoder lineage. That strongly suggests the top scores are driven by DQI and/or chemistry, where public ratios may be far from optimal. Chemistry is the weakest public ratio (11.2×), and at a fixed total effort a doubling of the weakest task pays the same as doubling the strongest. DQI pays Q², so one DQI qubit at Q ≈ 890 is worth 0.22%.
- **Recommendation.** Put **one dedicated agent-track on invsqrt** with the explicit goal Q ≤ 60 and n_rot ≤ 35 (target 24–25×, +4% GM). Build our own generator first, which the prize rules require anyway (Kirill's note: "hosts require a generator that rebuilds the exact circuits"). Put the remaining effort on whichever of DQI or chemistry the other experts show has more than 20% headroom.

---

## 6. What a human must read to check these claims
- **Paper (arXiv:2610.23832):**
  - §II.A (kickmix gates, HMR kickback)
  - §II.C (fuzz testing, Eq. 3, the 2√ε bound, Fiat–Shamir salt)
  - §III.A.2 (reference numbers Q = 260, C = 7,988) and §III.A.3 (contract)
  - App. B.2 (normalization CSWAP counts) and App. B.3 (stage-by-stage Toffoli counts)
- **Verifier** `verify_submission_invsqrt.py`: `reference_values` (117–131), `z_pow_class`/`rotation_t_count` (140–149), the per-shot check (275–296), the cost block (316–328). Reference generator `build_nr_circuit` (351–377).
- **Notebooks:**
  - kirilltym-pi lines 1538–1552: the receipt for the public-best 62-qubit file.
  - dmitriigluzdov lines 78–99: the 62-qubit design description.
  - alexchilton lines 28–52 (nulls), 883–902 (qubit-peak analysis), 995–1044 (93-qubit design), and `$K/alex_src/stage_ref.py.txt` (a readable generator of the ancestor design).
- **Outside sources (not fetched here; please read):**
  - Gidney, "Halving the cost of quantum addition" (temporary AND, measured uncompute)
  - Kliuchnikov et al. 2203.10064 (the 0.56 log₂(1/ε)+5.3 formula)
  - Rubin et al. PNAS 2024 / 2308.12352 (where the 24-bit requirement comes from)
  - Babbush et al. 2603.28846 and Long et al. (record-and-replay; carry and measurement tricks from the ecdsa.fail competition)
  - Qualtran `docs/kickmix/kickmix_instructions.md` (read: CSWAP = CX·CCX·CX, so it is one Toffoli; CCZ is the only 3-qubit phase gate; conditioned instructions run only when the condition stack is true)
