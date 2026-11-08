# Debate round 1 — Agent C (chemistry)

## (a) Cross-examination

**A (invsqrt)**
- The arithmetic is sound: 1 qubit ≈ 24.8 Toffolis, and 41 rotations against a floor of about 33–34.
- **Error:** "Chemistry is weakest, and doubling the weakest pays the same." True for the geometric mean, but chemistry *cannot* double.
  - Getting from 11.2× to 22.4× needs T ≈ 7.5k.
  - The analytic part alone is 6.66k, which would leave loaders of about 0.8k, against 8.3k today.
  - The ceiling with free loaders is 25×.
- **Over-optimistic:** the 62→58 qubits by packing flags into vacated mantissa bits is unsupported until someone produces a live-qubit profile. I would count +5–10% for invsqrt, not 10–15%.

**B (DQI)**
- **103× already exceeds B's own range.** It means a −37% cost cut, larger than B's own 20–35% headroom estimate, and it assumes rivals stand still.
- **Half-GCD / Karatsuba is the weak link.**
  - B itself prices a 12-qubit word at 2.7% of cost.
  - Out-of-place Karatsuba on degree-17 polynomials needs tens of temporary words. That is +100s of qubits, i.e. +50–100% cost.
  - So it only pays if it is ancilla-free *in place over GF(2¹²)[z]*, and nobody has shown that.
  - The 0.76%-per-shot degenerate pivots must stay exact inside the recursion.
- **The breakdown is unmeasured:** B's T split is admittedly ±30%.
- I would discount to −10–20% cost, i.e. DQI ≈ 72–80×.
- B's statement that chemistry's levers are in the analytic model is correct, and my brief confirms it.

## (b) Stress test of "λ_eff and Q are locked"

Script: `work_C/stress.py`. It is my cost model plus a calibrated loader model that reproduces the public 14,965 Toffolis, 427 qubits and 11.199× exactly.

- **λ_eff:** the lock is a theorem. 2Λ−E_gap ≥ 559.13 holds for *any* tree, words or weights, so λ_eff ≥ 46.786. No loophole.
- **Q:** confirmed locked.
  - **J:**

    | J | Q | Ratio |
    |---|---|---|
    | 1 | 395 | 7.9× |
    | 3 | 411 | 10.7× |
    | 4 | 419 | 11.0× |
    | 5 | 427 | 11.2× |
    | 6 | 435 | 7.8× |

    At J=6 the 128-qubit cap forces 5 low bits.
  - **Reusing inner-QROAM temporaries:** already free. Temporaries combine by max, so angle workspace never sets Q. The binding constraint is the 128-qubit per-circuit cap, not Q.
  - **Tree:** appears in no cost term. It is a free compressibility knob only.
- **Correction to my own brief — one real loophole: the row count A = 76+RB.**
  - If A ≤ ~650, the cache fits with only **3** low address bits. That roughly halves the bit-plane term.
  - The model predicts, at B=143 (the heuristic part is unchanged):

    | Shape (R, B, C) | Rows A | Ratio |
    |---|---|---|
    | (8, 143, 44) | 1220 | 11.2× |
    | (4, 143, 88) | 648 | **14.3×** |
    | (2, 143, 176) | 362 | **15.6×** |
    | (1, 143, 352) | 219 | 18.0× |

  - **The question is accuracy.** Is a 20 mHa table possible with 572 vectors? (Public tables use 1,144; ahmedberatozer's (4, 255, 128) used 1,020.)
  - (1, 143, 352) is THC with only 143 = 1.9N vectors, almost certainly infeasible.
  - (4, 143, 88) is unknown. It is the **single highest-value chemistry experiment**: about 2 GPU-days of the public L-BFGS fit plus rounding.
  - This is speculation until fitted.

## (c) Techniques that transfer between tasks

1. **GF(2) bilinear-rank / ANF synthesis.** The DQI 42-AND multiplier search, the chemistry paired-product loader, and the invsqrt 169-AND table decode are the same problem: minimize ANDs for a fixed Boolean or bilinear map. Build one SAT / flip-graph tool for all three.
2. **Data co-design ("soft words").** Choose the table contents so the lookup is cheap: chemistry angle rounding, invsqrt coefficient rounding.
3. **Measurement-based uncomputation (HMR plus conditioned fix-ups)** and branch placement exploiting mean-cost counting, in all three tasks.
4. **Exact window resynthesis and live-qubit profiling,** used in invsqrt and DQI, and in chemistry loaders under the 128-qubit cap.
5. **Multi-salt expected-cost evaluation** for DQI.

## (d) Allocation (4 people, 10 weeks)

| Rank | Track | People | Expected task gain | Expected score gain |
|---|---|---|---|---|
| 1 | Shared GF(2) synthesis tool (c1), then DQI multiplier and Schur-node cuts, then DQI qubit squeeze | 1.5 | DQI −10–18% cost | +3.5–6% |
| 2 | Chemistry: fit (4,143,88) and (6,143,59) row-budget tables (weeks 1–2, go/no-go); else loader-aware rounding plus compiler | 1 | 13–15× (−15–25% cost) | +5–9% |
| 3 | invsqrt: profile, then qubit peak 62→60 and rotations 41→36 | 1 | −5–10% cost | +1.7–3.4% |
| 4 | Integration: reproduce public SOTA files, generators for prize compliance, multi-salt checks | 0.5 | Protects baseline | — |

- **Combined realistic outcome:** +10–18% score, i.e. 25.1 → 27.6–29.6.
- **Kill criteria:**
  - DQI redesign: stop if the week-2 profile shows the key-equation core below 60% of T.
  - Chemistry row-budget test: stop if error₂ at 572 vectors exceeds 16 mHa before rounding.
