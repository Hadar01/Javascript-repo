# Project memory — Google Quantum AI: Verifiable Quantum Circuit Compilation

## Mission
Reach the top 100, then the top 1% (about rank 26), then **win**. Keep iterating until 2027-01-20 23:59 UTC.

## Competition facts (snapshot 2026-11-08)
- URL: https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation (id 161954)
- Prize pool $150k: 1st $50k, then $25k / $10k / 3×$5k. Also $10k mid-competition (2026-11-20, public notebook required),
  $10k longest-leader, and 3×$10k single-task prizes.
- Max team size 5. Merge deadline 2027-01-13. 5 submissions/day. Scoring takes ~45 min.
- Companion paper: arXiv:2610.23832 (Khattar, Rubin, Gidney, Broughton, Low, Babbush).
- Score = (Π_b cost_ref/cost_b)^(1/3) over three tasks:
  - invsqrt (fusion, 1/√x phasing): cost = Q × (Toffoli + T/4)
  - dqi (RS(4095,4025) decoder over GF(2^12)): cost = R(ε+) × Q² × T
  - dfthcsos (FeMoCo block encoding): cost = λ_eff × T × Q, with ≤128 qubits per angle circuit,
    ≤20 mHa error, and limits on Λ and E_gap

## Leaderboard snapshot (2026-11-08, 2602 teams)
| Rank | Score |
|---|---|
| 1 | 29.30 |
| 10 | 27.03 |
| 26 (top 1%) | 26.25 |
| 100 | 25.17 |
| 500 | 25.01 |

- Public plateau ≈ 25.1, from heliosli's "The dataset is public now" notebook:
  invsqrt 21.75× (62 qubits), dqi 65.2× (892 qubits), dfthcsos 11.2× ((8,143,44) table, 15 angle circuits).
- Improvement in the product of ratios needed over 25.1:
  - ×1.008 for top 100
  - ×1.144 for top 1%
  - ×1.59 for #1

## Status log
- 2026-11-08: Found the competition and downloaded the data, the paper and 15 top notebooks (in the session scratchpad;
  re-download with the Kaggle API, which the proxy authenticates). Launched three expert agents
  (invsqrt / DQI / chemistry) to read the paper, the cited references, the verifiers and the notebooks.
  The experts debated (see quantum-kaggle/briefs/). The plan and reading guide are in quantum-kaggle/PLAN.md.
- Key conclusions:
  - The chemistry λ_eff floor is 46.786 (public best 46.893), so weight refitting is finished as a lever.
  - The chemistry levers left are the angle-loader Toffolis and the row-budget loophole:
    a table with ≤ ~650 rows saves an address bit; shape (4,143,88) is predicted at 14.3×, but no table that size
    has been shown to meet 20 mHa yet.
  - DQI: profile the stages first; expected −10–15% cost.
  - invsqrt: qubits 62→60 and rotations 41→35; expected −5–10% cost.
  - Shared tool to build: a GF(2) AND-count minimiser for the DQI multiplier, chemistry loaders and the invsqrt table.
  - Forecast with focused effort: 27.5–29.5.
- NEXT ACTION: Phase 0 of PLAN.md. Submit the public portfolio (about 25.1), build the verifier harness and the
  qubit/Toffoli profiler in Kaggle, then run the chemistry row-budget fit.
- Constraint: running the downloaded kickmix.so locally was blocked by the permission policy. Run circuits in
  Kaggle notebooks instead, or ask the user to allow local runs.

## Repo layout
- PLAN.md: reading guide and phased plan
- briefs/: three expert briefs plus three debate rebuttals
- tools/chem_cost_model/: Agent C's numpy reimplementation of the chemistry metric and costs (stress.py reproduces the public 11.199×). It was written against scratchpad paths; set the data paths before use.
