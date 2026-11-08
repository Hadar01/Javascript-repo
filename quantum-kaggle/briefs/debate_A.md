# Debate round 1: Agent A (invsqrt), rebuttal and cross-examination

## (a) Checks on the other briefs

**B (DQI): the arithmetic is right; the headline headroom claim is not supported.**

What I re-derived and confirmed:
- R(8.66e-4) = ln2 / −ln(0.5 + 2·0.02943) = 1.1912.
- Reference cost: 1.19126 · 1893² · 5.725e6 = 2.444e13.
- Public cost: 1.19126 · 892² · 395,356 = 3.747e11.
- Break-even rule ΔT > 1.86e8·p, from 0.46% per failure × 102,400 shots.
- DQI ratio needed for the top 1%: (26.25/25.09)³ · 65.2 ≈ 74.7.
- The metric's `verification_shot_divisor` must stay 1 (metric nb lines 255–263), so all 102,400 DQI shots are kept.

Where I disagree:
1. **The 20–35% figure rests on a breakdown B itself marks [SPEC].** No profile of the 892-qubit circuit exists yet. Idea #2 claims −15 to −30% of *all* T, but half-GCD only touches the middle O(t²) products. With t = 35 and degree ~17 halves, half-GCD's recursion overhead and its stored transition matrices usually eat the asymptotic gain. Each extra 12-qubit word costs 2.7% of DQI cost, and every temporary in a reversible half-GCD is such a word. I would put the probability-weighted gain at about −8 to −12% of DQI cost, not 20–35%.
2. **The qubit squeeze is capped at Q ≥ 840.** 892 → 866 is the most plausible case, about −5.7% of cost. That is fine, but it is not additive with a redesign that needs extra words.
3. **"invsqrt looks saturated" misreads the source.** The "LP-optimal angles / only rounding that passes" result is about table rounding inside one architecture. The current circuit has these openings:
   - It uses **41 rotations against a floor of about 33**; the 8 extra are worth 58 Toffoli-equivalents, or 3.7%.
   - It holds 22 bits of information in 27 live qubits, a potential 2–4 qubits at 1.6% each.
   - Its rotations are 19% of cost and were never jointly optimized with the arithmetic.

**C (chemistry): carefully done; mostly verified.**

What I checked:
- Ratio = 167,6xx / T. With T = 14,966 this gives 11.198, and with T = 6,662 it gives 25.2.
- Reference T: 79,480 + 846 + 9,461 + 3,450 = 93,237.
- The λ_eff floor: 46.8926² / 3.914898 = 561.68, which is 2.55 Ha above the floor of 559.13. The triangle-inequality step is correct.
- Score translations: 1.25^(1/3) = +7.7%, and 13–14.5× corresponds to +5.1% to +9.0% of GM.

My quarrel is framing, not arithmetic:
- C calls chemistry "second priority", yet its own lever, 8.3k loader Toffolis, is **a pure Boolean-synthesis problem with a 25× ceiling**.
- A −30% cut on the loaders is worth +5.5% GM, more than I claim for invsqrt.
- The open question for C: does rounding-aware word design (ideas 1–2) really survive the 20 mHa gate? Error_1 and error_2 already sit at 19.999997. The RM(2,4) attempt failed at 24 mHa, so slack is thin.

## (b) Techniques that transfer across tasks

1. **GF(2) table / ANF compiler.** The same problem appears twice:
   - invsqrt's 256-entry coefficient decode (169 ANDs, "algebraic three-product decodes");
   - chemistry's loaders (one-hot cache plus products of linear forms, kernel pairing).

   In both, the inputs are a truth table and free linear forms, and the goal is to minimize the number of ANDs. In both, the **words are co-designable with rounding**: invsqrt's K0/K1/K2 search and chemistry's "soft words". Building one shared tool pays twice.
2. **Exact window resynthesis with phases, and domain-aware (reachable-state) gate deletion.** Proven on invsqrt (7 windows went 3 → 2 Toffolis; a CSWAP inactive on all legal inputs was deleted). It applies directly to the DQI glue and to chemistry's reachable-state contract.
3. **Mean-count exploitation.** All three verifiers charge *executed* gates, so it pays to put fix-ups inside branches conditioned on HMR outcomes (half the shots), plus measurement-based carry and lookup erasure.
4. **Bilinear-rank / flip-graph search.** The GF(2¹²) multiplier below 42 ANDs; the same SAT tooling applies to the loader products.
5. **Live-qubit flame-chart profiling.** invsqrt pays 1.6% per qubit and DQI 0.22% per qubit.

## (c) Allocation (4 people, 10 weeks, starting from the 25.09 public portfolio)

| rank | track | people | expected gain on task | GM gain |
|---|---|---|---|---|
| 1 | Shared GF(2) lookup compiler → chemistry loaders (then the invsqrt table) | 1.25 | loaders −20…−30% → 12.6–13.4× | +4…+6% |
| 2 | DQI: profile in week 1; go/no-go on the redesign in week 2; multiplier search as a background job | 1.25 | −8…−12% cost | +2.8…+4.3% |
| 3 | invsqrt: qubit peak 62 → 59 and rotations 41 → 35, using our own exact-model generator (needed for the prize anyway) | 1.0 | −8…−12% | +2.8…+4.3% |
| 4 | Integration: local verifier farm, DQI salt sweeps, hash-pinned portfolio, licence and credits | 0.5 | protects against loss | n/a |

Combined expectation: about ×1.10–1.15 on GM, i.e. **27.6–28.9**, the top-10 band.

Kill rules:
- If the DQI profile shows extraction + synthesis below 60% of T, move its 1.25 people to the compiler track.
- If invsqrt cannot reach 60 qubits by week 4, stop at micro-gains.
