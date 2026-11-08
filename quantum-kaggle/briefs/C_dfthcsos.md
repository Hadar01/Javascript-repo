# Agent C brief: `dfthcsos` (FeMoCo DF-THC + SOSSA block encoding)

Author: Agent C (quantum chemistry / block-encoding). Date: 2026-11-08.
Paths below are relative to `K=.../scratchpad/kg`. My scripts are in `K/work_C/`. They are my own numpy code and never import the downloaded modules.

**What I actually read:** the companion paper `paper.txt` §III.C (Eqs. 44–78) and App. A; the whole verifier (`verify.py`, `scoreinfra/*.py`, `SCORING_README.md`); and the notebooks heliosli (both), marculera, ahmedberatozer v23, somejoint, kirilltym, and lightningv08.
**What I could not read:** arXiv was blocked (`getaddrinfo ENOTFOUND arxiv.org`), so I did not read Low et al. 2502.15882, Lee et al., Babbush et al., Berry et al., von Burg et al., Low–Kliuchnikov–Schaeffer or Gidney. Background statements about those papers come from memory and are marked "(background)".

**Checks I ran myself:**
- I reimplemented the scoring metrics in numpy (`work_C/metrics.py`, with my own FCIDUMP parser `work_C/parse.py`). On the sample submission they reproduce the verifier's numbers exactly: Λ = 308.4559397330944, E_gap = 3.965477244291833, λ_eff = 49.30136925057438, error_2 = 18.64 mHa.
- I reimplemented the heuristic cost model (`work_C/cost.py`). It reproduces the baseline exactly: 846 + 9461 + 3450 Toffolis, 90 persistent and 544 temporary qubits.

---

## 0. TL;DR

1. **λ_eff is already at its floor (0.2 % headroom).** With the fixed shift (S, β₁) and the E_gap floor, I prove in §2.4 that λ_eff ≥ √(3.914898 × 559.1325) = **46.786**. The public best is **46.8926**. The whole "Λ / E_gap / weights refit" lever is spent.
2. **Q = 427 is locked by the cost formula.** It is 84 persistent state-prep qubits, plus 40 word qubits (J·brot = 5·8), plus 303 temporary qubits for the inner QROAM.
   - The 303 is fixed by the formula's own choice of QROAM block size (k₂ = 4) once brot = 8 and B ∈ [129, 143].
   - Every alternative I scanned is worse or physically infeasible. B ≤ 128 jumps Q to about 700. B ≤ 16 would drop Q to about 355, but the leading ERI eigen-leaves are full rank (computed, §3.2). brot = 7 doubles the rounding noise.
3. **T = 14,966 splits into a locked part and the angle circuits:**
   - **Formula part, 6,662 Toffolis, essentially locked:** Givens 2,250 + inner prep 4,095 + outer prep 317. This is 44.5 % of T. It moves only by about 9.3 Toffolis per square removed from R·C.
   - **ANGLE circuits, 8,304 Toffolis (4,152 per pass, about 277 per circuit), 55.5 % of T.** This is the only real chemistry lever.
4. **Chemistry ratio as a function of T** (λ_eff 46.8, Q 427): ratio = 167,800 / T.

   | Angle Toffolis (both passes) | Total T | Chemistry ratio |
   |---|---|---|
   | 8,304 (public) | 14,966 | 11.2× |
   | 6,000 | 12,660 | about 13.3× |
   | 4,500 | 11,160 | about 15× |
   | 0 (hard ceiling) | 6,662 | 25.2× |

5. **What chemistry is worth to the team.** Because the score is a geometric mean, +25 % on any single task gives +7.7 % on the total.
   - Chemistry +25 % (11.2 → 14) needs the angle circuits cut by 36 %: 8,304 → about 5,300 Toffolis.
   - The headroom is real but bounded, and it sits almost entirely in **Boolean-oracle (lookup) synthesis co-designed with angle rounding**. That is a compilation problem much closer to the fusion/DQI experts' skill set than to "chemistry".
   - There is also a separate **$10k single-task prize for chemistry** (pages.md:364).

---

## 1. Theory in plain language

**Hamiltonian.** FeMoCo in a 76-orbital active space with 113 electrons, written in second quantization:
H = Σ h¹_pq E_pq + ½ Σ h²_pqrs E_pq E_rs, with E_pq = Σ_σ a†_pσ a_qσ (paper Eq. 45).
Writing down h² takes O(N⁴) numbers, so every modern algorithm compresses it.

**Block encoding, LCU and Λ.** Write H = Σ_ℓ α_ℓ U_ℓ, a weighted sum of unitaries. PREPARE loads √α_ℓ into an ancilla register, SELECT applies U_ℓ, and the result is H/Λ in the top-left block, with Λ = Σ|α_ℓ|.
Qubitized phase estimation then needs about πΛ/(2ε) calls to reach energy precision ε. Runtime is therefore (cost per call) × Λ, which is the paper's outer objective C_BE·λ_eff (Eq. 63) (background: Babbush et al. 2018; Berry et al. 2019).

**SOSSA / spectrum amplification** (Low et al. 2025, read only through the companion paper).
- Write H − E_SOS = Σ_x O_x† O_x, a sum of squares, so the operator is positive semidefinite (paper Eqs. 50, 57).
- Block-encode the O_x instead of H. Phase estimation then sees √(H − E_SOS) near the ground state.
- With gap E_gap = E_gs − E_SOS, the effective normalization is λ_eff = Λ·g_amp = √(E_gap(2Λ − E_gap)) (Eqs. 60–61).
- When E_gap ≪ Λ this is ≈ √(2Λ·E_gap), a square-root saving. A tighter SOS bound (smaller E_gap) is worth as much as a smaller Λ.
- The verifier replaces the true E_gs by a fixed E_upper = −22140.27335 Ha (paper Eq. 76; `reference.py` line 56). It also imposes E_gap > 3.914898 Ha, which is the DMRG-minus-SOS-SDP difference (`verify.py` lines 125–130).

**DF and THC factorizations** (background: Berry et al. 1902.02134, von Burg 2007.14460, Lee et al. 2011.03494).
- **Double factorization (DF)** writes h² ≈ Σ_ℓ L_ℓ⊗L_ℓ and then eigendecomposes each leaf L_ℓ.
- **Tensor hypercontraction (THC)** writes h² ≈ Σ_{μν} ζ_μν χ_μ χ_μ χ_ν χ_ν, using one shared pool of M orbital vectors.
- **DF-THC here** (Eqs. 48–49) is a hybrid. There are R groups ρ. Group ρ owns B unit vectors u_b^(ρ) and C "copies" (leaves) X^(ρc) = Σ_b w_b^(ρc) u_b u_bᵀ, and h̃² = Σ_{ρc} X^(ρc)⊗X^(ρc).
  - The one-body part is absorbed exactly into h¹′ (Eq. 52).
  - Each square carries an identity offset W^(ρc) (Eq. 50).
  - Λ = ‖h¹′‖_* + ¼Σ_{ρc}(|W+Σ_b w_b| + Σ_b|w_b|)² (Eq. 56).
  - E_SOS = −ηβ₁ − (‖h¹′‖_* − Tr h¹′) − ½ΣW² (Eq. 57), plus the core energy.

**Givens rotations and Majorana trees.**
- Each unit vector u ∈ ℝ⁷⁶ is produced from e₀ by N − 1 = 75 Givens rotations along a user-chosen spanning tree rooted at orbital 0, with parents listed before children (`dfthc_math.py` lines 104–125; App. A.1).
- On the quantum side, each rotation is a controlled phase-gradient adder of b bits, costing 2b − 1 Toffolis (App. A, paper line 1646). It is paid on both U_T and U_T† (`costs_prepare.py` lines 141–147).
- The angles θ_t are loaded coherently, per address, by the ANGLE_k oracles. There are J words per batch and K = ⌈75/J⌉ batches. Circuit k XORs batch k ⊕ batch k−1 into the word registers (README "What a submission must do"; App. A, Eq. A13).

**QROM / QROAM** (background: Babbush 2018 unary iteration; Low–Kliuchnikov–Schaeffer select-swap; Berry 2019 QROAM; Gidney measurement-based uncomputation).
- A plain QROM over L entries costs about L Toffolis, whatever the output width.
- Select-swap with λ copies costs about L/λ + b(λ − 1) Toffolis but needs about λ·b qubits. The `QR()` function is exactly this formula (`costs_prepare.py` lines 34–45).
- Measurement-based uncomputation (HMR plus a classically conditioned CZ) makes uncomputing a lookup almost free in Toffolis: √L-type cost, or 0 for a simple AND.
- The verifier counts a conditioned gate only on shots where its bit is 1 (`circuits.py` lines 445–447 and 556).

**Angle precision.** Words have brot bits and θ/π = word/2^(brot−1).
- Rounding to brot bits perturbs every vector. That raises error_1 and error_2 (both gated at 20 mHa) and slightly perturbs λ_eff.
- Fewer bits make everything cheaper: Givens cost is linear in brot, the angle circuits load fewer bit-planes, and the word registers are smaller (J·brot qubits).

---

## 2. Exact contract and cost anatomy

### 2.1 Submission
`submission.npz` holds six arrays (README "Submission files"):
- `U` (R, B, 76): only its shape is used.
- `W` (R, B, C): the lowercase weights w.
- `H2_I` (R, C) = W + Σ_b w, so the verifier recovers W = H2_I − Σ_b w (`verify.py` lines 161–168).
- `H1_I` and `Hsym_lower`: **ignored**. They are replaced by the fixed shifts, with S rounded to float32 and β₁ = 4.955104996915907 (`verify.py` line 218; `reference.py` lines 108–118).
- `tree_edges` (75, 2): checked to be rooted at 0 with parents before children (`dfthc_math.py` lines 424–428).

The circuits are `angle_k_0..K-1` (.kmb or .kmx).
- The `selection` register must have **exactly** ⌈log₂(76 + RB)⌉ qubits (`circuits.py` lines 471–477).
- Registers `word_0..word_{J−1}` must all have width brot. **brot and J are read from the circuits.**
- No `Z_POW`, so every phase must be a multiple of π (`circuits.py` lines 419–430).
- Every circuit must leave the workspace at |0⟩, the selection unchanged and the phase unflipped, on all 64 shots per address, both forward and reverse (`circuits.py` lines 402–416 and 533–555).

**Reachable-state contract** (`circuits.py` lines 522–531). After each circuit the simulator clears and rewrites the *expected* previous batch, so circuit k is only ever tested on z = batch[k−1](a). It may use the current contents of the word registers as an input. The host (Tanuj Khattar) confirmed this "reachable forward/reverse contract", as cited by kirilltym.

### 2.2 Gates (all strict)
- error_1 ≤ 20 mHa and error_2 ≤ 20 mHa, computed on the **decoded, quantized** words (`verify.py` lines 122–123 and 373–381).
- 0 < E_gap < 2Λ, plus a 100-digit Decimal recheck that agrees to within 1e-6 (`dfthc_math.py` lines 360–373).
- Λ > 49.0 (`verify.py` line 129). This never binds: Λ is about 282.
- E_gap > 3.914898 (`verify.py` line 130). **This one binds.**
- Each ANGLE circuit ≤ 128 qubits (`verify.py` lines 134 and 539–553). **This binds the loader design.**

### 2.3 Score
score = λ_eff × T × Q (`verify.py` lines 546–555). The ratio is 3,355,599,588.3 / score.

- **T = A + O + I + G**, where (`verify.py` lines 472–493; `costs_prepare.py`):
  - **A**: simulated mean Toffoli-like gates (CCX, CCZ, CSWAP) per shot over the forward and reverse passes of all ANGLE circuits, averaged uniformly over addresses (`circuits.py` line 556).
  - **O, outer prep**: with X_o = 76 + RC, O = 8⌈log X_o⌉ + QR(X_o, b₁) + b₁ + QI(X_o) + b₁ + 1, and b₁ = ⌈log X_o⌉ + 10 (`costs_prepare.py` lines 103–113).
  - **I, inner prep**: with b₂ = ⌈log₂ B⌉ + 11 (`costs_prepare.py` lines 115–139):
    - RC·⌈(B+1)/2^k₂⌉ + 2^k₂·b₂
    - \+ QR(RC, B+1) + (B+1) + 76 + b₂
    - \+ 8⌈log₂(B+1)⌉
  - **G, Givens**: 2·75·(2·brot − 1) (`costs_prepare.py` lines 141–147).
- **Q = P_out + P_in + J·brot + max(tmp_out, tmp_in, tmp_angles)** (`verify.py` lines 491–493).
  - tmp_angles = (ANGLE qubits) − (selection) − J·brot (`verify.py` lines 405–408). It is always ≤ 128 − 11 − 40 = 77, so it **never sets Q**.
  - P_out = 2⌈log X_o⌉ + 22 (`costs_prepare.py` lines 151–167).
  - P_in = b₂ + 10 + ⌈log R⌉ + 2 + ⌈log(B+1)⌉ + 2 (`costs_prepare.py` lines 169–190).
  - tmp_in = ⌈log(RC·⌈(B+1)/2^k₂⌉)⌉ + (2^k₂ − 1)·b₂ + ⌈log(B+1)⌉ − 2.
- **How k₂ is chosen** (`costs_prepare.py` lines 84–99): start from the select-swap optimum of `QR(RCB, b₂)`, then lower it until the temporary qubits are below brot·75. For the **Toffoli** count only, k₂ is also lowered until B ≥ 2^k₂ (`costs_prepare.py` lines 124–128). **The qubit formula does not apply that second lowering.**
- **Fixed by the competition:** chi = 10 (`verify.py` line 139) and N = 76.
- **User-controlled:** (R, B, C), brot, J, the circuits, the tree, the vectors and the weights.

### 2.4 Theorem: λ_eff floor (my derivation, checked numerically)

From `dfthc_math.py` lines 348–362:
- Λ = Σ|λ_j| + ¼Σ(|W + s| + a)², where s = Σ_b w_b and a = Σ_b |w_b| for each (ρ, c).
- E_gap = E_up − E_core + ηβ₁ + (Σ|λ| − Σλ) + ½ΣW².

The constant −(E_up − E_core + ηβ₁) = **559.1325 Ha** depends only on the fixed shift. Then

2Λ − E_gap = 559.1325 + 2·Σ(positive eigenvalues of h¹′) + ½Σ_{ρc}[(|W+s| + a)² − W²].

Each bracket is ≥ 0, because |W+s| + a ≥ |W+s| + |s| ≥ |W|. Therefore

λ_eff² = E_gap(2Λ − E_gap) ≥ 3.914898 × 559.1325, so **λ_eff ≥ 46.786**.

| Submission | λ_eff | E_gap (Ha) | Excess over 559.13 |
|---|---|---|---|
| Public best (ahmedberatozer v23) | 46.89259 | 3.914898003 (at the floor) | 2.55 Ha |
| Baseline | 49.30 | 3.9655 | 53.8 Ha (2·pos = 3.2, sign-mixing = 50.6) |

ahmedberatozer reports Σpos = 1.1258, mix = 0.1475 and a numerical relaxation bound of 46.8485. Both agree with my decomposition.

**Conclusion:** the maximum possible λ gain is 46.893 / 46.786, i.e. **0.23 %**. Realistically it is under 0.1 %, which is about +0.03 % on the score.

### 2.5 Cost anatomy: reference vs public best

| | Reference (65, 60, 60), brot 12, J 8 | Public best (8, 143, 44), brot 8, J 5 |
|---|---|---|
| λ_eff | 49.301 | 46.893 |
| Λ | 308.46 (λ_h1 12.9, λ_h2 295.6) | ≈ 282.8 |
| E_gap | 3.9655 | 3.914898 |
| ANGLE Toffolis (both passes) | 79,480 (10 × 3,974 × 2) | **8,304** (15 circuits, about 277 per circuit per pass) |
| Outer / Inner / Givens | 846 / 9,461 / 3,450 | 317 / 4,095 / 2,250 |
| T | 93,237 | **14,966** |
| Q (persistent + words + temporary) | 90 + 96 + 544 = 730 | 84 + 40 + 303 = **427** |
| error_1 / error_2 | (baseline) / 18.6 mHa | 19.999997 / 19.999997 mHa |
| Ratio | 1 | **11.198** |

Gain decomposition: λ ×1.051, T ×6.23, Q ×1.71. Sources: ahmedberatozer v23 lines 31–43; my `cost.py`.

---

## 3. Levers, quantified

### 3.1 Λ vs E_gap, and refitting the weights
- **Spent** (§2.4). The public pipeline already refits W and H2_I at fixed words. It uses block SQP and Newton steps, and pushes error_1, error_2 and E_gap to within 3e-9 of their gates.
- The only value left in the weights is **indirect**. Any slack in the 20 mHa budget can buy cheaper words (§3.5) instead of lower λ.

### 3.2 Factorization shape (R, B, C)
- **B.** Inner-prep cost steps at ⌈(B+1)/16⌉. B = 143 gives (B+1)/16 = 9 exactly, so it is the largest B at that price. B ≤ 128 makes b₂ = 18 and allows k₂ = 5 under brot·75 = 600, which raises the temporary qubits to about 569 and Q to about 698 (my scan; ahmedberatozer confirms Q 698 at B = 128). **B ∈ [129, 143] is therefore forced at brot 8.**
- **The tempting B ≤ 16 kink** (my scan, `work_C/scan2.py`). At B = 15, QR's natural choice is k₂ = 4 with b₂ = 15. The heuristic T falls to about 3.9k (from 6.66k) and Q to about 358.
  - If it were feasible it would be worth −32 % cost.
  - **It is infeasible.** I eigendecomposed the 5776×5776 ERI supermatrix including the fixed S shift (`work_C/dfprobe.py`, `work_C/leaf.py`). The leading eigen-leaves of FeMoCo are essentially **full rank, with flat spectra of about 0.4–0.5**.
  - Truncating leaf 0 alone to rank 16 costs **6.8 Ha** of error_2. Leaves 1–3 need rank about 60–70 to reach the mHa scale.
  - Because the sum ΣX⊗X has only positive terms, no rotation of the leaves can split a near-rank-1 supermatrix component into low-rank squares. The format forces one uniform B for all groups, so **B ≳ 76 is required**.
- **RC.** Each square costs about 9.2 Toffolis (inner) plus about 0.3 (outer). Truncation alone at rank RC gives:

  | RC | Truncation error |
  |---|---|
  | 300 | 16.7 mHa |
  | 352 | 7.4 mHa |
  | 414 | 3.5 mHa |

  The public table spends about 12 mHa on fit and the rest on rounding noise. Moving RC by ±30 changes T by about 2 %.
- **R vs C at fixed RC and B.** The heuristic cost does not change. Rows A = 76 + 143R grow with R, and the loader cache term grows with rows (§3.6). R = 8 puts A at 1220, just under the 1232 = 77×16 sweet spot.
- **Better fits.** The marculera pipeline (clustered Cholesky seed, k-means "compact groups", Adam/L-BFGS) shows that a better fit lets the same table round under the gate with fewer copies or one fewer group. That was worth about 2–3 %.

### 3.3 Angle precision brot
- **brot 9 or more:** the temporary-qubit limit rises to 675, so k₂ = 5 and Q ≈ 690. Rejected.
- **brot 7:** Q −5 and Givens −300. The loaders lose one effective bit-plane (about −14 % of the angle cost, ≈ −1,150 T). In total about −10 % cost.
  - **But the rounding noise doubles.** At 8 bits the noise is about 14–16 mHa in quadrature with a 12 mHa fit. At 7 bits it would be about 30 mHa, more than the gate by itself.
  - Infeasible unless a radically better lattice rounding appears (speculative, low probability).
- **Givens tree shape:** it does **not** enter any cost formula, since G depends only on brot. It affects only (a) the rounding sensitivity and (b) the structure of the word table, i.e. how compressible it is for the loaders. **The tree is a free co-design knob** (§4).

### 3.4 J (words per circuit) and qubits
- Q = 387 + brot·J. The ANGLE width is 11 + 8J + cache (about 72) + scratch, and must stay ≤ 128, so **J ≤ 5**.
- J = 4 saves 8 qubits (−1.9 %). The 19 loaders would each have to cost ≤ 226 Toffolis per pass to break even (ahmedberatozer), against about 277 now. The public J4 smoke test reached 255. **Small or negative.**

### 3.5 Loader circuits (the only big lever)
State of the art (lightningv08, marculera "tensorqrom/rmcode", qwertykeypadapple kernel search; read in the notebooks):
- **Address split.** The 11-bit address is split into 7 high bits and 4 low bits. A **one-hot cache** of the 77 high values costs about 72 Toffolis. It is uncomputed by measurement-based uncomputation for 0 Toffolis.
- **Output bits.** Each output bit is written as ⊕_S m_S(low)·g_S(high). Each (bit, S) coordinate costs one product of a linear form in the cache with a low monomial. **The number of addresses barely matters; the number of (output bit × low monomial) coordinates does.**
- **Paired products.** GF(2) kernel relations let one Toffoli serve two coordinates. With J = 5 there are 35 bits × 15 monomials = 525 coordinates, minus 75 relations, giving 225 products plus 72 for the cache: about 297 per circuit. The current best is about 277.
- **Data tricks already in use:**
  - "π-gauge": bit7 = bit6, so each word has 7 independent bits.
  - "Coded bit 0": a Reed–Muller RM(1,4) affine pattern per 16-row block, saving 624 Toffolis in total.
  - Rows dealt across blocks.
- **Already tried and failed:** RM(2,4) coding on bits 1–3 would save about 450 more, but rounding then reaches 24 mHa and fails the gate.
- **Cost model:** angle Toffolis per pass ≈ K·cache + 75·b_eff·(2^m − 1)/2·(1 − ρ_rel). With m = 4 low bits (forced by the 128-qubit cap), b_eff = 7 and ρ_rel ≈ 0.14:

  | Term | Toffolis per pass | Share |
  |---|---|---|
  | Data | ≈ 3,400 | 80 % |
  | Cache (15 × about 72) | ≈ 1,080 | 20 % |

### 3.6 Qubit reuse
The temporary workspace is shared via a max, so the loaders get up to 77 workspace qubits for free. The binding constraint is the per-circuit cap of 128, not Q. There is nothing left to win in Q from the loaders.

---

## 4. Ranked ideas beyond the public best

Gains are on the chemistry ratio, which is now 11.20. "Spec." marks speculation.

| # | Idea | Mechanism | Estimated gain | Confidence |
|---|---|---|---|---|
| 1 | **Rounding that knows the loader cost** | Today the noise budget is spent uniformly. Add the loader's (bit, monomial) count as a penalty to progressive rounding: zero low bits in insensitive columns (effectively variable precision per tree edge, which the Givens formula does not charge for), plus more RM-coded planes where the noise budget allows. Trade the remaining weight-refit slack for words. | −10…−20 % angle Toffolis → ratio 11.9–12.8 | Medium (spec.) |
| 2 | **Tree + compact groups → structured columns** | Compact groups are about 18–20 orbitals wide. Choose the tree, the root path, the row order and the signs (u → −u, π-gauge) so that each 16-row block has many near-zero or exactly π/2 angles. Then high bit-planes are constant within a block, and the m_S coordinates vanish (free). Needs exact sparsity constraints in the fit. | −10…−25 % angle Toffolis | Medium-low (spec.) |
| 3 | **Use the previous batch as free cache** (reachable contract) | Circuit k sees batch k−1 in the word registers. Co-design adjacent angle columns to be correlated (a tree ordering where consecutive edges carry similar angles), so batch k = f(batch k−1) ⊕ (small residual). That reduces data coordinates. | −5…−15 % | Low-medium (spec.) |
| 4 | **Cheaper or shared cache** | Spend some of the 72 cache Toffolis × 15 circuits × 2 passes (2,160 Toffolis, 14 % of T) differently: a partial one-hot plus some high-bit monomials, or a 5+6 split where some columns use m = 3 with a bigger cache in circuits with spare qubits. | −3…−8 % of T | Medium |
| 5 | Better synthesis per circuit (kernel / relation search, exact ANF minimization, CCZ-phase tricks) | Pure compilation; the same skills as invsqrt and DQI | −3…−10 % angle Toffolis | Medium |
| 6 | Squeeze RC (340 → about 320) with a better fit, e.g. longer L-BFGS, compactness screening, 46 → 44 copies | Fewer squares | −1…−3 % | High that it works, low value |
| 7 | J = 4 with loaders ≤ 220 per pass | Saves 8 qubits | ≤ +2 % | Low |
| 8 | λ_eff polishing | §2.4 floor | ≤ 0.2 % | Certain that it is tiny |

**Ruled out:** B ≤ 128 or brot ≥ 9 (Q explodes); B ≤ 16 (full-rank leaves, §3.2); brot 7 (noise); further Λ reduction (floor).

**Loophole to avoid.** The verifier simulates computational-basis addresses. A circuit that *measured the selection register* and classically conditioned gates on the result would pass the checks while being physically invalid, because it collapses the superposition. Do not do this: it is disqualification risk. The paper and the hosts stress that the contract is *verifiable*.

A combined realistic target is ideas 1+2+4+5 cutting the angle circuits from 8,304 to about 5,500–6,000. That gives **chemistry about 13–14.5×**, or **+5…+9 % on the total score**. Reaching 15× needs angle Toffolis of about 4,500.

---

## 5. Position statement for the debate

**Hypothesis tested: "chemistry has the lowest ratio, so it has the most headroom."** Mostly false.
- The low ratio comes from the formula. 44.5 % of T and about 90 % of Q are analytic black boxes (Outer, Inner, Givens, persistent registers) whose minima the public has already reached: B = 143, k₂ = 4, brot = 8, J = 5.
- λ_eff is within 0.2 % of a provable floor.
- The absolute ceiling, with zero-cost loaders, is 25×.

**Where the headroom is.** Only in the 8.3k angle-circuit Toffolis. A 30–40 % cut there (→ 13.5–14×, +6–8 % total score) is plausible but research-grade. It requires coupling the rounding and factorization pipeline (GPU hours, A100-scale L-BFGS) with a GF(2) lookup compiler.

**Recommendation.**
- Make chemistry the **second priority**. Assign one person or agent to the loader + rounding co-design (ideas 1, 2 and 4).
- Fund it only if invsqrt and DQI show diminishing returns, or if we target the **$10k chemistry single-task prize**, which other teams also chase and where a 5 % edge wins.
- The compilation tricks overlap with the other two tasks, so the Boolean-synthesis expert should own the loader part. Chemistry-specific work (refits, shape) is nearly exhausted and should get **little** effort.
- Cheap wins worth doing anyway: reproduce the public 11.198 file (credited, licence-compliant) so our GM is not handicapped, then try idea 4 and idea 1.

---

## 6. What a human must read to check these claims

1. `data/verifiers/dfthcsos/scoreinfra/dfthc_math.py` lines 348–362 (Λ, E_SOS, E_gap), together with `verify.py` lines 125–130. Check the λ_eff floor derivation in §2.4. Constant: E_core = −21021.2140122 (last FCIDUMP line), β₁ = 4.955104996915907 (fixed_shifts.npz), so 113·β₁ − (E_up − E_core) = 559.1325.
2. `scoreinfra/costs_prepare.py` lines 84–190 (the k₂ choice and the qubit formula). Check that the 303 temporary qubits and the B-threshold behaviour follow, e.g. by running my `work_C/cost.py`.
3. `verify.py` lines 389–517 (how Q excludes selection and takes the max of temporaries; the 128-qubit cap applies to the angle circuits only).
4. `scoreinfra/circuits.py` lines 522–556 (reachable-state reset; Toffoli = mean executed gates).
5. The ahmedberatozer v23 notebook text (`nb/ahmedberatozer--...txt`, lines 31–43 and 102–111 of its markdown dump) for the public best's exact numbers, and lightningv08 §3 for the loader cost model.
6. `work_C/leaf.py` output (eigen-leaf spectra) for the infeasibility of B ≤ 16.
7. Paper §III.C, Eqs. 56–61 and 76–78, for the intended semantics.
