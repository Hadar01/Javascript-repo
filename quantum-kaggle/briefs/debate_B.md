# Debate round 1 — Agent B (DQI): rebuttal, cross-examination, allocation

GM conversion used below: cutting a task's cost by x multiplies the GM by (1−x)^(-1/3).

## (a) Cross-examination

**Brief A (invsqrt).**
1. The brief says the task is "near-saturated", yet quotes 10–15% headroom. Its own evidence argues against 15%:
   - LP-optimal angles.
   - The table rounding was searched exhaustively.
   - All 62 wires are live for a third of the run, with no linear relations among them.
   - Window resynthesis already applied up to 12 wires.
   - The rotation floor of ~33–34 is A's own estimate, and A admits the 8 spare rotations probably pay for qubits.
2. The qubit ideas are still untested: packing flags into vacated mantissa bits, and re-lookup costing ~170 Toffolis to break even at ~7 qubits. I would discount the estimate to **4–8%**, which is +1.3–2.7% GM.
3. A's "no variance risk" point is correct, and it is a real advantage of invsqrt.
4. A makes one claim in my favour: the #1 team includes the author of the Schur/continued-fraction DQI line. If their gap to public (×1.59 on the product of ratios) came mostly from DQI, that would mean DQI ≈ 100× is achievable.

**Brief C (chemistry).**
1. The λ_eff floor proof is sound. I checked it: |W| ≤ |W+s| + |s| ≤ |W+s| + a, so each bracket is ≥ 0. That lever is closed.
2. **The B ≤ 16 infeasibility rests on an informal argument**: "only positive terms, so no rotation can split." It is also derived from leaf spectra of the shifted ERI matrix, not from a constrained fit. Its prize is −32% cost, so it deserves 1–2 days of a real attempt before we close it. One example to try: many groups with B = 16 that share near-identical vectors.
3. The target of −30 to −40% on the angle loaders is over-optimistic. The public has already applied:
   - kernel-relation search;
   - π-gauge;
   - RM(1,4) coding.

   RM(2,4) already failed the 20 mHa gate. C's own top ideas are marked "medium-low, spec." and depend on GPU-hour refits we may not have. My estimate is **−15–25% on 8.3k Toffolis, i.e. ratio 12.3–13**, which is +3–5% GM.

**Defending my own 20–35% against "15 strong teams already iterated".**
1. **The crowd mostly does surgery on binaries, not redesign.** Since Oct 26 the architecture has not changed: in-place continued fraction, 42-AND multiplier, 52 workspace qubits. Every large gain came from an architecture jump:
   - Berlekamp–Massey → Schur: ×4.6 cost.
   - Retained-head chain / narrow return: −25% T.
   - Micro-surgery since Nov 1: −2.7% in total.
2. **Nobody has published a stage profile, a subquadratic key-equation core, or a multiplier search beyond 42.**
3. **The hosts committed a hash of an internal run that beats public on every task** (paper, Acknowledgments). Note this is evidence that headroom exists, not that it is large.
4. **Concession.** The 20–35% is a ceiling estimate. My probability-weighted expectation over 10 weeks is **−10 to −15% DQI cost**, which is +3.5–5.5% GM. The variance is high: the redesign either lands or yields nothing.

## (b) Techniques that transfer across tasks

- **One GF(2) bilinear/ANF synthesis engine** (flip-graph / SAT / kernel-relation search) serves all three tasks:
  - the GF(2^12) multiplier rank below 42 (DQI);
  - paired-product angle loaders (chemistry);
  - the 169-AND lookup decode and window resynthesis (invsqrt).
  Build it once.
- **Measurement-based erasure.** HMR, then a CZ or CCZ fix-up conditioned on the outcome, and the "free-coin" bit forcing. The verifiers charge mean executed gates, so fix-ups cost about half.
- **A live-qubit profiler and exchange-rate accounting.** Each qubit is worth about 886 Toffolis in DQI, 24.8 in invsqrt, and acts on Q linearly in chemistry. Most decisions reduce to this table.
- **Reachable-state / domain-aware deletion.** Examples: invsqrt's inactive CSWAP, chemistry's previous-batch contract, DQI's low-weight branches (P(w≤15) = 3e-8).
- **A multi-salt expected-cost harness and our own generators**, which the prize rules require.

## (c) Allocation: 4 people × 10 weeks (5th person optional)

| # | Owner | Work | Expected task gain | Expected GM |
|---|---|---|---|---|
| 1 | P1 | **DQI redesign**: profile in week 1, then cut multiplications per node, then the subquadratic core, with the qubit squeeze folded in. | −12% cost | **+4.4%** |
| 2 | P2 | **Shared synthesis engine** (from (b)): multiplier rank for DQI first, then chemistry loaders and invsqrt windows. | multiplier lottery: −2 to −5% DQI if rank < 42 | +1–2% |
| 3 | P3 | **Chemistry**: rounding that knows loader cost, plus the tree/sign co-design. Includes a 2-day falsification of B ≤ 16. | ratio +12% | **+3.8%** |
| 4 | P4 | **invsqrt**: qubit peak first, then merging the rotation passes. | −6% cost | +2.1% |
| 5 | P5 (optional) | Infrastructure: portfolio, multi-salt evaluation, generator reproducibility, tracking public releases. Protects gains rather than adding them. | — | — |

**Expected combined result:** about ×1.11–1.13 GM, from 25.1 to **≈27.5–28.5**. Top 1% is likely and top 10 is plausible.

**Reaching #1 (29.3) requires the DQI redesign to land at ≥ 90×.** That is why DQI gets the first and largest slot.

**Kill rule:** if the week-1 profile shows key-equation solving is below 60% of T, P1 moves to the synthesis engine and chemistry.
