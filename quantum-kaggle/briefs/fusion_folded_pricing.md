# Folded-residual invsqrt: implementation checkpoint (2026-11-24)

**Idea** (branch `codex/fusion-folded-residual-probe`, `tools/invsqrt/folded_residual.js`).
- Approximate 1/√x by a straight line per segment.
- Correct the curvature with a small table shared by inputs equally far either side of the segment midpoint.
- Compensate each line's offset for the curvature it shares.

**What the probe establishes** (reproduced here):
- Without compensation: 445 of 3,133,452 inputs fall outside tolerance, worst 125.8%.
- With compensation, at the same table sizes (512 segments, 8 groups, 16 buckets): **0 outside, worst 81.7%**.
- That is a real improvement in the representation.

**Pricing** (`tools/invsqrt/folded_pricing.js`; reproduce with `node folded_pricing.js`).
- Cost = Q × (Toffolis + T/4), with Q the peak qubit count.
- **The baseline is the measured 33.17 invsqrt `bb676b95`:**
  - 37 qubits;
  - 1,406.31 Toffolis, plus T and 33 rotations worth 240.4 Toffoli-equivalents;
  - 1,646.7 Toffoli-equivalents per input, cost 60,927.6.
- Every row below is a **lower bound** for the folded design.
- Rotations are charged at the baseline's count and ε, which is generous.

| Variant | Q | Toffoli-eq | Cost | vs baseline |
|---|---:|---:|---:|---:|
| Baseline bb676b95 (measured) | 37 | 1,646.7 | 60,928 | — |
| A. Affine lookup only, by unary iteration (1,023 Toffolis); only the 29-bit offset word is ever held | 51 | 1,262 | 64,362 | **+5.6%** |
| B. A + unary-iteration ladder qubits | 60 | 1,262 | 75,720 | +24.3% |
| C. The probe's 382-AND lookup (split at 8 low bits: 248 stored monomials + 57-bit word) | 327 | 621 | 203,068 | +233% |
| D. C + correction lookup (82) + slope × u (≥ 336) | 327 | 1,039 | 339,754 | +458% |

**Break-even.**
- At Q = 51 the whole budget is < 1,194.7 Toffoli-eq. The rotations take 239 of it, leaving < 956 for every Toffoli.
- The affine lookup alone needs 1,023.

**Verdict: loses. The 1,024-row affine lookup consumed the advantage, through two effects at once.**
1. **Width.**
   - The baseline holds 22 input bits in 37 qubits.
   - Any lookup design has to materialise at least the 29-bit offset word (Q ≥ 51, +38%).
   - The probe's 382-AND count needs 248 stored monomials.
2. **Toffolis at narrow width.**
   - A narrow lookup costs about one Toffoli per row: 1,023, which is 62% of the baseline's entire per-input budget.
   - That is before the slope × u product, the correction table, the exponent-dependent shift of the phase word, and
     uncomputation.

**What would have to change for a table design to compete.**
- Total table rows must fall to roughly ≤ 300, with at most about 8 extra qubits.
- But linear segments at 2^-24 relative accuracy need about 512 segments; the probe needs 512 even with the shared
  correction.
- With 64 segments the cubic term alone is about 1.5e-7 relative, against the 6e-8 tolerance. So higher-order terms
  would be needed, i.e. multiplications. That is the table-plus-Horner family the 44- and 37-qubit arithmetic designs
  already beat.
- The compensation trick, which adjusts stored values for a shared correction, is worth keeping as a technique for any
  future table we do need.

**Status.** Experiment closed at this checkpoint. Nothing was built or submitted.
