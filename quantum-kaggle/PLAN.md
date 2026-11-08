# Google Quantum AI – Verifiable Quantum Circuit Compilation: Reading Guide & Attack Plan
_Last updated 2026-11-08. Full expert briefs and debate in `briefs/`._

---

## 0. The situation in one table

| | invsqrt (fusion) | dqi (decoder) | dfthcsos (chemistry) | **Geo-mean** |
|---|---|---|---|---|
| Cost formula | Q × (Toffoli + T/4) | R(ε+) × Q² × T | λ_eff × T × Q | |
| Reference | 260 q, 7,988 Tof-eq | 1,893 q, 5.73M Tof | λ 49.3, 93,237 T, 730 q | 1.0 |
| **Public best** (anyone can copy) | 62 q, 1,540 → **21.75×** | 892 q, 395k → **65.2×** | λ 46.89, 14,966 T, 427 q → **11.2×** | **≈ 25.1** |
| Realistic headroom (after debate) | −5 to −10% cost | −10 to −15% cost | −15 to −25% cost (more if row-budget fit works) | |
| 1% better on this task → overall | +0.33% | +0.33% | +0.33% | |

Leaderboard targets (2026-11-08):

| Target | Score needed | Product of improvements needed over 25.1 |
|---|---|---|
| Top 100 | 25.17 | ×1.008 |
| **Top 1%** | **26.25** | **×1.144** |
| Top 10 | 27.0 | ×1.25 |
| #1 | 29.30 | ×1.59 |

Key insight: the geometric mean rewards *relative* improvements equally across tasks. That means total cost reduction across the
three tasks (multiplied) must be ≈14% for top 1% and ≈59% for #1.

---

## 1. What YOU should read, so you can check the agents' claims

Ordered. Roughly 15–20 hours total. Items 1–4 are mandatory, 5–8 per task, and 9+ are depth.

### Foundations (mandatory, ~5 h)
1. **Competition pages** (Overview → Evaluation → Data → *Domain Context*). The Domain Context page is a free
   "quantum for non-physicists" primer. (~45 min)
2. **Companion paper arXiv:2610.23832**, §I and §II (pp. 1–6). Cover: the kickmix gate set; why classical simulation verifies these
   circuits; fuzz testing + Fiat–Shamir salt; the **2√ε** distance bound. (~1.5 h)
3. **Toffoli / AND gate & measurement-based uncomputation**: C. Gidney, *Halving the cost of quantum addition*
   (arXiv:1709.06648, 4 pages). This single trick (compute AND with 1 Toffoli, uncompute for free by measuring) appears in
   every winning circuit. (~1 h)
4. **Qualtran kickmix docs** (github.com/quantumlib/Qualtran/tree/main/docs/kickmix): the instruction set and the
   `.kmx` text format. Note: CSWAP = 1 Toffoli; conditioned instructions only cost when executed (mean cost counts!). (~1 h)

Optional primer if new to qubits: *Quantum Computing for the Very Curious* (quantum.country/qcvc), first half only.

### Task 1 — invsqrt (~2 h)
5. Paper §III.A + Appendix B (reference: normalise x → polynomial guess → Newton step → phase via rotations).
   Then `verifiers/invsqrt/verify_submission_invsqrt.py` lines ~117–149 (reference values, rotation T-cost
   0.56·log₂(1/ε)+5.3) and ~275–328 (per-shot check, cost). **Check:** every x is tested, zero failures allowed.
   Background: Kliuchnikov et al. arXiv:2203.10064 (rotation cost formula); the "fast inverse square root" trick (Wikipedia).

### Task 2 — DQI (~4 h)
6. Paper §III.B incl. Eq. (43) R(ε). Then `verifiers/dqi/verify_submission_dqi.py` lines ~130–260 (R, Clopper–Pearson bound,
   error-weight distribution) and ~334–441 (pass criteria, mean-T, Q, score).
7. Classical Reed–Solomon decoding: any textbook chapter or the Wikipedia article on *Reed–Solomon error correction* +
   *Berlekamp–Massey* + *Chien search / Forney*. You need: syndrome → key equation → error locator → error values.
   GF(2^m) arithmetic: addition = XOR; multiplication = polynomial product mod an irreducible (the "42-AND multiplier").
   Then **Khattar et al. arXiv:2510.10967** (*Verifiable quantum advantage via optimized DQI circuits*), which covers the
   reversible decoder design. DQI itself: Jordan et al. arXiv:2408.08292, intro + §on OPI only.

### Task 3 — dfthcsos (~4 h)
8. Paper §III.C + Appendix A, then `verifiers/dfthcsos/SCORING_README.md` (read fully) and
   `scoreinfra/dfthc_math.py` lines ~348–362 (Λ, E_gap) and `scoreinfra/costs_prepare.py` lines ~84–190 (QROAM qubit formula).
   Concepts: *block encoding / LCU normalisation λ* (cost of phase estimation ∝ λ), *QROM/QROAM* lookup tables
   (Babbush et al. arXiv:1805.03662 §III; Berry et al. arXiv:1902.02134 Appendix on QROAM), *Givens rotations*,
   *tensor hypercontraction* (Lee et al. arXiv:2011.03494, intro). SOSSA / spectrum amplification: Low et al. arXiv:2502.15882.

### Depth (when you want an edge)
9. Babbush et al. arXiv:2603.28846 (origin of kickmix) and Long et al. 2026 (*record-and-replay arithmetic*). These are the tricks
   ~100 people found in the ecdsa.fail challenge, a direct precedent for this competition.
10. Gu et al. arXiv:2610.22367 (*Discovering SOTA quantum circuits with LLMs*), an alternative DQI decoder.
11. Gidney, *Windowed quantum arithmetic* (arXiv:1905.07682), for lookup-based arithmetic.

### How to check an agent's claim yourself
- Every cost number quoted in `briefs/` has a file:line reference into the verifier. Open it and recompute by hand.
- Any score claim must come from running the **unmodified** official verifier (in a Kaggle notebook). No exceptions.

---

## 2. Debate outcome (where the three experts converged)

- **λ_eff (chemistry) is at a proven floor** (46.786 vs 46.893 now), so weight refitting is done. **Q (chemistry) is locked**
  by the QROAM formula + 128-qubit cap. The only chemistry levers are angle-loader Toffolis (8.3k of 15.0k T) and
  **one new loophole: fewer loaded vectors** (a table with ≤ ~650 rows saves an address bit, so the loader cost roughly halves;
  model predicts 14.3× at shape (4,143,88)). *Unproven: needs a 20 mHa-accurate fit with half the vectors.*
- **DQI**: all big past gains came from *design changes*; the public design has been frozen since Oct 26 with only
  −2.7% patching in the last week. Nobody has published a stage profile. The redesign is high-variance; expected −10–15%.
- **invsqrt**: polynomial error budget is exhausted (0.9993 of tolerance). The remaining levers are qubits (62 → 59–60, 1.6% each)
  and rotations (41 → ~35, 0.47% each). Expected −5–10%.
- **All three agree a shared tool is the best investment**: a GF(2) AND-count minimiser / Boolean-lookup compiler
  (SAT / flip-graph / ANF resynthesis). It serves the DQI field multiplier, the chemistry angle loaders, and the invsqrt
  coefficient table simultaneously.
- Consensus forecast with focused effort: **≈ 27.5–29.5** (top-10 band; #1 needs upside on DQI or chemistry).

---

## 3. The plan

### Phase 0 — Baseline on the board (this week, by 2026-11-11)
- [ ] Fork the public re-verified portfolio notebook (heliosli "The dataset is public now") in Kaggle; run it; submit.
      Expected LB ≈ 25.1 → **~rank 100–500 immediately**. Respect licences (Apache-2.0) and credit authors.
- [ ] Set up our own Kaggle notebook "harness": loads kickmix + 3 unmodified verifiers, scores a candidate per task,
      prints per-task ratio. Every experiment goes through it. Test under several salts (DQI failure count is random).
- [ ] Write a **live-qubit + per-stage Toffoli profiler** for .kmx circuits. This is the #1 missing tool; nobody published one.

### Phase 1 — Cheap, likely wins → **top 1%** (weeks 1–3, target ≥ 26.3 by ~Nov 29)
Run all three in parallel:
1. **Chemistry row-budget experiment** (go/no-go at end of week 2): fit DF-THC tables at shapes (4,143,88) and (6,143,59)
   with the public L-BFGS pipeline, then rounding; gate: error ≤ 20 mHa, E_gap ≥ 3.914898. If it works: **11.2× → 14×+**,
   which is alone ≈ +8% overall, enough for top 1%. Kill if pre-rounding error > 16 mHa at 572 vectors.
2. **invsqrt rotation merge** (41 → ~35 rotations) + **profile-driven qubit squeeze** (62 → 60). ≈ +2–3% overall.
   Kill the qubit track if 60 qubits not reached by week 4.
3. **DQI stage profile** (week 1). Decide by week 2 whether the key-equation core is ≥ 60% of T; if yes, begin redesign.

### Phase 2 — The shared synthesis engine (weeks 2–7)
- Build the GF(2) AND-minimiser (SAT-based exact synthesis for small windows + flip-graph search for bilinear maps).
- Apply in order: chemistry angle loaders (loader-aware rounding, sparse columns, reuse previous batch as free input),
  DQI 42-AND GF(2^12) multiplier (each AND saved ≈ −2% DQI cost), invsqrt table decode.
- Expected: +4–6% overall.

### Phase 3 — DQI redesign (weeks 3–9, only if profile says go)
- Fewer multiplications per extraction step; in-place sub-quadratic key-equation core; qubit squeeze toward 860–875
  (Q² ⇒ each qubit ≈ 0.22% DQI cost).
- Price any rare-case shortcut with the break-even rule: drop a case of probability p only if it saves > 1.86e8·p Toffolis.

### Phase 4 — Lock in & prizes (weeks 9–10, by 2027-01-20)
- Final 2 selected submissions: our best + a safer variant (DQI failure-count variance ±0.5%/failure).
- Single-task prizes ($10k each): chemistry and invsqrt are plausible targets; track per-task best separately.
- Prize compliance: reproducible notebook, open licence, generator code for every circuit.
- Team: consider merging with strong teammates before **2027-01-13**.

### Rules we never break
- Never measure the chemistry selection register or exploit verifier quirks that are physically invalid (DQ risk).
- Never submit anything that hasn't passed the unmodified verifier locally.
- Update `MEMORY.md` after every submission: score, per-task ratios, what changed.
