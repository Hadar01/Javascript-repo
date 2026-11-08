# Brief B — DQI Reed–Solomon syndrome decoder (Benchmark II)

Agent B (combinatorial optimization / DQI decoder). Status: research only. I executed no downloaded code. The only
code I ran was two small numpy scripts I wrote myself, to recompute the verifier's weight distribution and R(ε).

**Sources actually read:** `paper.txt` (§I, §II, §III.B, references), `pages.md`, both DQI verifier files line by line,
and the notebooks in `nb/`: heliosli, alexchilton (§3, §5, §6b, §8), dmitriigluzdov §2, somejoint, kirilltym
pi-gauge, lightningv08 §4, manwithacat and leoprovorov (grep).
**Not read (fetch failed):** arXiv is not reachable from this sandbox (`ENOTFOUND arxiv.org`, also emergentmind). For
Khattar et al. 2510.10967 I have only a search-engine abstract: 5.72M Toffolis, "leading-order space 2nb qubits",
implicit Bézout access. For Jordan et al., Gidney 1709.06648, Gu et al. 2610.22367, Long et al., Kepley–Steinwandt
and van Hoof, everything below comes from my background knowledge or from what the notebooks quote. I mark that
material **[KNOWLEDGE]**, and **[SPEC]** marks speculation.

---

## 1. Theory in plain language

### 1.1 OPI and DQI
- **OPI (Optimal Polynomial Intersection).** For each of the m = q−1 = 4095 nonzero points α^i of GF(q), q = 2^12, we
  are given an allowed set F_i of size r = 2016 (a bent-function support). We want a polynomial Q_x of degree < n = 70
  whose values land in as many F_i as possible. Checking a candidate classically is easy, so the problem gives a
  verifiable advantage. (paper §III.B.1, Eq. 32)
- **DQI.** The goal is to prepare Σ_x P(f(x))|x⟩ with P of degree ℓ = 35. Expanding P(f) in the Fourier (character)
  basis turns it into a superposition over sparse "error" vectors e of weight ≤ ℓ. The algorithm prepares
  Σ_e a_e |e⟩|Bᵀe⟩, where Bᵀe is the syndrome of e in the dual RS code [4095, 4025, 71]. It then has to erase |e⟩
  knowing only the syndrome, which is exactly syndrome decoding. A final Walsh–Hadamard (the QFT over GF(2^12)^70)
  then gives the optimization state (Eqs. 33–36). Uniqueness holds because 2ℓ ≤ n < d = 71.
- **MBUC variant (the one benchmarked).** Khattar et al. erase each error symbol e_j right away by an X-basis
  measurement with outcome c_j ∈ {0,1}^12. That leaves the sign (−1)^{c·bin(e)}, and the decoder's only job is to put
  that sign back: U_c|s⟩ = (−1)^{c·bin(e(s))}|s⟩ (Eq. 38). So **the circuit never needs to output e. It only needs one
  phase bit, and it must restore s and leave no garbage.** Garbage would decohere the superposition. This is why
  everything has to be reversible or measurement-uncomputed with exact phase fix-ups.

### 1.2 The phase-sign trick
popcount(e_j ∧ M_j) is a GF(2)-linear functional of e_j, which can be written Tr(μ_j e_j) for some μ_j that depends on
M_j. Consequences:
- The phase of a **product** (−1)^{L(a·b)} is bilinear in the bits of a and b, so it needs only **CZ gates (0
  Toffolis)** once a and b sit on wires. The Forney value e_j = Ω/σ′ is therefore never formed: the circuit computes
  an inverse (or an "amplitude polynomial" C = Ω/σ′ mod σ) and pairs it with Ω by CZs. (ref circuit
  `gf2_phase_by_product`, `dqi_reference_circuit.py:583`; alexchilton §6b.)
- Linearity in e gives the **classical mask projection**: Σ_j Tr(μ_j e_j) changes only by the free phase
  Tr(Σ_i c_i S_i) if μ_j is replaced by μ_j − Σ_i c_i α^{(i+1)j}. Choosing the 70 classical c_i (as linear functions
  of the M bits) to cancel μ at 70 positions removes 70 scan points. That is 70 × 11 = 770 Toffolis, already in the
  public decoder (lightningv08 §4). It cannot remove more than 70 points, because there are only 70×12 GF(2) degrees
  of freedom.

### 1.3 Classical RS decoding and reversible cost
- **Key equation** σ(z)S(z) ≡ Ω(z) mod z^70 (Eq. 40). σ is the locator (degree w = number of errors), Ω the evaluator.
- **Berlekamp–Massey (BM):** 2t = 70 iterations, each with a discrepancy (inner product of length ≤ L) and an update
  of σ and B. About 2 × 35 mults per iteration, roughly 2–5k field mults one way. Reversibly it needs history or
  in-place tricks. A public BM port measured 2,114 Toffolis per iteration forward, 148k total, with the reverse 93k
  (alexchilton §6b).
- **Extended Euclid (EEA)** on z^70 and S, which is what the reference does: synchronized Proos–Zalka steps, 222
  pointer-driven steps, unary iteration (`dqi_reference_circuit.py:166-215, 613-615`). Very wasteful.
- **Continued fraction / Schur (current public SOTA family).** For a generic syndrome, the continued fraction of
  S(z)/z^70 has **35 linear partial quotients = 70 field elements**, the same size as the syndrome. So the decoder
  can turn S into the quotients **in place** ("Schur extraction", O(t²) mults, "595 node pairs" = 35·34/2). It then
  synthesizes (N, B) ← (l_i N + q_i B, N) to get σ and an amplitude polynomial C = A/B′ mod B, scans, and runs
  everything backwards. **This is why the public decoder needs only 52 qubits beyond the 840 syndrome qubits.**
  (alexchilton §3; dmitriigluzdov §2.)
- **Chien search.** At each position j, evaluate σ(α^{-j}) by in-place multiplication of every coefficient by a
  classical constant. That is CNOT-only, so 0 Toffolis. Then XOR-sum into one word (CNOT), zero-test it (12-bit AND
  chain = **11 Toffolis**, erased by measurement for free), and CZ the zero flag with the parity L_j(C(x_j)). Lower
  bound: the phase (−1)^{AND12 · L} has degree 13, and CZ(g, h) is free, so 11 ANDs is optimal per point
  **[KNOWLEDGE, standard multiplicative-complexity argument]**. Scan ≈ 4025 × 11 ≈ **44k Toffolis, a floor for a
  pointwise scan.**
- **Forney:** e_j = Ω(x_j^{-1}) / σ′(x_j^{-1}). The reference pays one Itoh–Tsujii inversion per point (351 Toffolis ×
  4095 ≈ 1.44M, `:579-589`). The public decoders avoid per-point inversion entirely: Gu et al. compute
  "Ψ = 1/σ′ mod σ once"; the Schur design computes "C = A/B′ mod B".

### 1.4 GF(2^12) arithmetic in Toffolis (kickmix + MBUC)
| op | cost |
|---|---|
| add, square, multiply by a constant, Frobenius, change of basis | 0 Toffolis (CNOT) |
| quantum × quantum product, out of place | rank of the bilinear algorithm. **Public: 42 ANDs**. Reference: 63 (Karatsuba); Khattar et al. hand-tuned: 51 |
| erase a product while both factors stay on wires | 0 (HMR + conditioned CZs, Gidney trick) |
| x += a·b in place | 42 ANDs; 1–2 ancillas suffice in principle (linear forms made in place by CNOT basis changes) **[SPEC: standard but not checked here]** |
| inversion | reference Itoh–Tsujii 315 Toffolis + 48 scaffold qubits; tower GF(((2²)³)²) ≈ 65–69 ANDs (alexchilton §6b) |
| zero test / equality of 12 bits | 11 |
| phase of a linear functional of a product | 0 |

Nobody has found a multiplier below 42 (alexchilton "what did not work", jday96314's searches). Barbulescu et al.
style exhaustive bounds do not reach n = 12 **[KNOWLEDGE]**.

---

## 2. Contract and cost anatomy (verifier file:line, `data/verifiers/dqi/verify_submission_dqi.py`)

- **Registers (205-230):** exactly S0..S69 (12 qubits each, 840 total) and E0..E4094 (12 classical bits each); no
  other named registers. Every other qubit is an ancilla and must end in |0⟩ (383-389).
- **Pass/fail per shot (389-390):** a value error is a changed syndrome or a dirty ancilla. A phase error is a wrong
  sign on an otherwise clean shot.
- **Z_POW is banned (349).** Only X/CX/CCX/CSWAP/Z/CZ/CCZ/HMR/R/conditions are useful.
- **Shots (56, 236-260):** 102,400 shots in batches of 256. The weight k comes from w_k² (principal eigenvector of the
  tridiagonal A, 174-184). Positions are uniform without replacement, values uniform nonzero, and M is uniform 12-bit,
  zero included.
- **Seeds (300-304, 358, 395):** SHA-256 of the .kmb (plus salt) seeds both the inputs and the HMR outcomes. The
  **leaderboard uses a secret salt** (pages.md:305), so you cannot grind seeds, and the failure count on the LB is a
  random draw.
- **ε+ (139-171, 408):** one-sided Clopper–Pearson at δ = 2^-128. With 0 failures ε+ = 8.66e-4, so **R floor =
  1.19126** for every exact circuit.
- **Score (415-420):** `R(eps_plus) * num_qubits**2 * toffolis`. T = **mean** Toffoli-like gates per shot over all
  shots (416), so gates skipped by a false classical condition do not count. Q = `circuit.num_qubits` (417): the
  qubit-id high-water mark, so freed and reused qubits are free.
- **Reference (paper §III.B.2; `dqi_reference_circuit.py`):** Q = 1,893 and T = 5,725,461.
  Cost = 1.19126 × 1893² × 5.725e6 = **2.4439e13**, matching REF_COST in the notebooks.
  - Qubits: 2(n+3)·12 = 1,752 for reg_a/reg_b (the first array reuses the syndromes, `:103-104`), 5 pointers of 8
    bits, flags, and the 48-qubit Itoh–Tsujii scaffold.
  - Toffolis: the Chien/Forney sweep is 4095 × (11 + 351 + 12 AND) ≈ 1.5M (`:571-599`). The forward and reverse EEA
    are the remaining ≈ 4.2M (222 steps × unary-iterated swaps and 63-Toffoli mults).
- **Best public (heliosli / kirilltym `4432ec5f`, kirilltym pi-gauge L1239-1275):** Q = 892, T = 395,356 (max
  395,641), 0/0 errors at the default salt. Cost = 1.19126 × 892² × 395,356 = **3.747e11**, ratio **65.22×**.
  - Q = 840 syndrome + **52 workspace**.
  - T breakdown [SPEC, estimated from the earlier Schur build in alexchilton §3: forward extraction 114k, reverse
    extraction 133k at T = 535k]. Today's 395k is roughly: extraction forward + reverse ≈ 200–230k (~55%), synthesis
    of σ and C forward + reverse ≈ 80–110k (~25%), scan ≈ 44k (11%), pole/flag/conversion glue ≈ 15–25k.
  - **Nobody has published an exact per-stage profile of the 892-qubit circuit.** Getting one with kickmix's flame
    chart is task #1.
- **History of the public frontier (cost):**

  | date | Q / T | cost | decoder |
  |---|---|---|---|
  | Oct 23 | 1818 / 583k | 2.3e12 | BM |
  | Oct 26 | 883 / 536k | 5.0e11 | Schur |
  | Oct 26 | 883 / 519k | 4.95e11 | Bézout middle |
  | Oct 29 | 897 / 413k | 4.1e11 | |
  | Oct 31 | 900 / 408k | 3.93e11 | |
  | Nov 1 | 892 / 405k | 3.85e11 | flag carry |
  | Nov 8 | 892 / 395k | 3.747e11 | |

  The last week brought only ~2.7%, all micro-surgery (product caching, measurement order, flag carry). **The public
  line looks like a local optimum of one architecture.**
- **Exchange rates at the frontier:** 1 qubit = 2/892 = 0.224% of cost, about **886 Toffolis**. Total qubit headroom
  is bounded: Q ≥ 840 hard, and (850/892)² = 0.908.

---

## 3. Failure-rate trade-off

My own computation of R against the failure count k out of 102,400 (same formula as verifier lines 130-171):

| k | 0 | 1 | 2 | 5 | 10 | 20 | 50 | 100 | 500 | 2833 (=P(w=35)) |
|---|---|---|---|---|---|---|---|---|---|---|
| R | 1.1913 | 1.1967 | 1.2014 | 1.2131 | 1.2290 | 1.2548 | 1.3134 | 1.3887 | 1.8131 | 5.13 |
| R/R0 | 1 | +0.46% | +0.85% | +1.8% | +3.2% | +5.3% | +10% | +17% | +52% | ×4.3 |

Error-weight distribution, from the verifier's w² (mean 31.05; matches paper):

| w | ≤15 | ≤18 | ≤20 | ≤22 | ≤24 | ≤26 | ≤28 | ≤30 | 34 | 35 |
|---|---|---|---|---|---|---|---|---|---|---|
| P(cumulative) or P(w) | 3e-8 | 3.5e-6 | 5.4e-5 | 6.2e-4 | 5.1e-3 | 3.0e-2 | 0.126 | 0.367 | 0.092 | 0.0277 |

Conclusions:
1. **Truncating the decoder to fewer than 35 errors is hopeless.** Dropping only w = 35 makes ε ≈ 2.8% and R × 4.3. No
   Q or T saving can pay for that, because a 35→34 capacity cut shrinks the core by at most ~6%.
2. **Break-even rule for an approximation that fails with probability p:**
   ΔT_saved > ~1.86e8 · p Toffolis (≈ 0.46% of cost per expected failure). For a qubit saving the bar is ~2 qubits
   per expected LB failure.
   - p = 1e-7: worth it if it saves > 19 Toffolis.
   - p = 1e-6: > 186 Toffolis.
   - p = 1e-5: > 1,860 Toffolis.
3. **Low weights are free to break.** Every code path needed only for w ≤ 15 (P = 3e-8) can be deleted (pole flags,
   empty-tail handling, zero syndrome, which has P ≈ 3e-26). w ≤ 18 is worth ~650 Toffolis. The public decoder
   already exploits this ("pole fires only on w ≤ 5", Gluzdov §2).
4. **Degenerate continued fractions are not free.** An accidental higher-degree quotient happens with probability
   about w/q ≈ 31/4096 ≈ **0.76% per shot**. That branch must be exact (R would otherwise be ×1.9). Second-order events
   (degree-3 quotient ~2e-6; two degree-2 jumps ~3e-5) sit right at break-even (~370 and ~5,000 Toffolis). This is
   where careful "handle exactly / drop" bookkeeping still pays. [SPEC: rates are my order-of-magnitude estimates]
5. **LB noise.** With a hidden salt, a circuit with true rate p shows Poisson(102,400 p) failures. Each failure is
   −0.46% of DQI cost, or −0.15% of GM. Rank on expected cost, as manwithacat does with 48 salts, and never on one lucky
   draw. The private LB redraws.

---

## 4. Ranked optimization ideas beyond the 892-qubit public decoder

Gains are on DQI cost. GM effect ≈ one third of that. "Effort" means engineer-days for someone who already
understands the stack.

1. **Profile first: exact stage-by-stage T and live-qubit map of `4432ec5f`** using the kickmix flame chart and
   `mark()` tags. Without it every number below is ±30%. Effort: 1 day. Gain: enables everything else.
2. **Subquadratic key-equation core (half-GCD / superfast Schur) using in-place Karatsuba over GF(2^12)[z]**
   [SPEC, highest ceiling]. The extraction and synthesis are O(t²) ≈ 1.2–2.5k field mults each way. Splitting the
   35 steps into two halves turns the middle work into polynomial products of degree ~17. Schoolbook costs 289
   coefficient mults per product; in-place Karatsuba costs ~90 (van Hoof-style schemes; ancilla-free in the GF(2)
   case **[KNOWLEDGE]**, and the same structure lifts to GF(4096) coefficients). Realistic: **−15 to −30% T** if Q
   stays ≤ ~900. Risk: high, because degenerate pivots complicate the recursion and the Karatsuba temporaries may
   cost qubits (each 12-qubit word costs 2.7% of cost). Effort: 2–4 weeks.
3. **Cut mults per Schur node pair.** Currently ~114k / 595 ≈ 192 Toffolis per pair forward (≈ 4.6 mults), and the
   reverse pays +31 per pair for norm-measurement phase repayment (alexchilton §3). Ideas:
   - projective / inversion-free (homogeneous) updates that defer all divisions to one normalization per node;
   - reuse the 42 linear forms of a factor shared by several products (same scalar times many coefficients). The
     AND count does not fall, but the qubits do.
   - make reverse = forward-mirror exactly by keeping the norm on wires (costs 12 qubits; net negative unless
     transient).
   Realistic: −5 to −12% T. Effort: 1–2 weeks.
4. **Cheaper GF(2^12) multiplier (< 42 ANDs).** It pays everywhere: ~85% of T is multiplication, so each AND saved ≈
   −2% cost. Searching for bilinear rank-41/40 formulas of the field multiplication (not just polynomial product: the
   reduction modulo α^12+α^6+α^4+α+1 can be folded in, and **any isomorphic field basis is legal** at CNOT-only
   conversion cost) is a well-defined SAT/flip-graph search (AlphaTensor-style). Realistic: 0 to −5%; unknown whether
   rank < 42 exists. Effort: a background compute job. **Cheap to try in parallel.**
5. **Qubit squeeze toward 860–875** [SPEC]. 52 workspace wires cover cached heads, pole flags, the product cache and
   the multiplier window. Each qubit is worth 886 Toffolis; Alex Chilton found that local peak-shaving costs 23–42
   Toffolis per window × ~2000 windows. So only architecture-level changes pay: an in-place multiply-accumulate with ≤
   2 ancillas, flags carried in HMR records, and recomputation instead of caching where the cache saves < 886
   Toffolis per qubit. Realistic: −2 to −8% cost. Effort: 1–2 weeks, and coupled with #2/#3.
6. **Approximation bookkeeping (Section 3).** Delete exact handling for w ≤ 15. Price every rare branch against
   1.86e8·p. Realistic: −0.5 to −2%. Effort: days. Low risk only if you measure rates on ≥ 1M shots under many salts.
7. **Scan micro-gains.** The scan is ≈ 11% of T and per point it is already at its 11-AND floor; the 70-point mask
   projection is done. The only route left is fewer points, which would need a non-pointwise root-finding algorithm. I
   believe that is more expensive (extended-syndrome tricks need 35 quantum mults per step). Realistic: ≈ 0.
8. **Mean-T tricks using classical data.** M_j = 0 skipping is worth 1/4096. "Free coins" (HMR on known-zero wires,
   then force the bit to 0) only shave fix-ups. Realistic: < 0.3%.

**Combined [SPEC]:** #2 + #3 + #5 could plausibly take the cost from 3.75e11 to ~2.5–3.0e11, i.e. **DQI ratio 80–100×**.
#4 is a lottery ticket on top.

---

## 5. Position statement for the debate

- **Arithmetic of the leaderboard.** With invsqrt and chemistry at public levels (21.75, 11.2), we reach **top 1%
  (26.25) at DQI ≈ 74.3×** (−12% DQI cost), top 10 (27.0) at ≈ 81×, and #1 (29.3) at ≈ 103×. Under the geometric mean
  a 1% cost cut is worth exactly the same in every task. The question is only where 1% is cheapest.
- **My claim: DQI has the largest *structural* headroom of the three in relative terms that are actually reachable,
  plausibly 20–35%.** The organizers state that all three benchmarks beat the public results internally (paper
  Acknowledgments) and call every part of the baseline improvable. The public DQI line has converged on one
  architecture (in-place continued fraction, 42-AND multiplier, 892 qubits) and is now polishing at ~0.3%/day. A
  different key-equation algorithm (subquadratic or fewer mults per node) is something an expert team can do and the
  crowd of notebook mergers has not done.
  - **invsqrt** at 62 qubits looks saturated: LP-optimal angles, an exhaustive search of the binding segments,
    1 qubit ≈ 1.6%.
  - **Chemistry** at 11.2× is the furthest from its reference in ratio, but its levers sit in the verifier's
    analytical cost model and the 20 mHa gates, which many teams are grinding.
- **Costs and risks of DQI.** Circuits are huge (58M ops, ~530 MB .kmb). The verifier needs ~6 GB per worker and
  minutes per run, so iteration is slow. Correctness is fragile: rare degenerate pivots and LB failure noise of
  ±0.5–1% per failure. The payoff is lumpy: a redesign either lands −20% or nothing.
- **Recommendation.** Make DQI a **co-priority, not the sole priority**. Put 1 dedicated person/agent on a decoder
  redesign (#1 → #3 → #2, with #5 folded in) and 1 background compute job on #4. Leave the other two tasks with the
  rest of the team. If the profile (#1) shows extraction plus synthesis below ~60% of T, downgrade #2 and shift effort
  to chemistry. Do **not** spend effort on DQI micro-surgery of the public binary (≤ 1–2% left, crowded).

---

## 6. What a human must read to check these claims

1. `data/verifiers/dqi/verify_submission_dqi.py` lines 130-171 (R, CP bound), 174-260 (distribution), 334-441
   (pass criteria, mean-T, Q, score).
2. `paper.txt` §III.B (lines ~630–862): Eqs. (38), (40), (43), reference numbers 1,893 / 5,725,461, and the R floor
   1.19.
3. `data/verifiers/dqi/dqi_reference_circuit.py:522-610` (Chien/Forney with per-point inversion and the CZ phase
   product).
4. `nb/alexchilton--...txt` §3, §5, §6b, §8 (lines 824–896, 922–950, 1057–1102): Schur design, 595 node pairs,
   per-stage Toffolis, 42-AND multiplier, failed ideas.
5. `nb/dmitriigluzdov--...txt` lines 100–122: what the 892-qubit decoder does and approximates.
6. `nb/kirilltym--quantum-circuits-pi-gauge-weight-refinement.txt` lines 1239–1275: the 892 Q / 395,356 T report.
7. Re-run my two numbers yourself: w² from verifier `optimal_dqi_weights` (P(w=35) = 2.77%, mean 31.05) and the R
   table via `clopper_pearson_upper_bound` + `repetition_overhead`.
8. Ideally (I could not): Khattar et al. arXiv:2510.10967 §§ on the EEA, multiplier and MBUC; Gu et al.
   arXiv:2610.22367 (1,837 Q / 442k T truncated-BM decoder); van Hoof (in-place Karatsuba over GF(2)) for idea #2.
